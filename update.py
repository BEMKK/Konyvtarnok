import urllib.request
import json
import webbrowser
import threading
import re
import datetime
import logging
import os
import sys
import time
import shutil
import tempfile
import subprocess
import wx

from constants import APP_VERSION
from config_manager import load_settings, save_settings

GITHUB_API_URL = "https://api.github.com/repos/BEMKK/Konyvtarnok/releases/latest"

# ==============================================================================
# ÖNFRISSÍTÉS (a futó .exe lecserélése) - CSAK WINDOWS/PYINSTALLER (--onefile)
# ==============================================================================
# A Windows engedi egy FUTÓ .exe ÁTNEVEZÉSÉT/törlését (a betöltő a
# programképet FILE_SHARE_DELETE móddal nyitja meg), csak a TARTALMÁT nem
# lehet felülírni. Ez teszi lehetővé, hogy a régi példány végig fusson
# (folyamatjelzővel), amíg az új el nem indul és jelzi, hogy készen áll -
# nincs köztes állapot, amikor a felhasználó "programtalan".
#
# Menete:
#   1. Az új .exe letöltése egy ideiglenes fájlba (a program mappájába).
#   2. A jelenleg futó .exe átnevezése "<név>.exe.old"-ra.
#   3. Az új .exe a felszabadult eredeti névre kerül.
#   4. Az új példány elindítása egy jelzőfájl útvonalával a parancssorban.
#   5. A régi példány várja (pollozással, időkorláttal) a jelzőfájlt, amit
#      az új példány a saját főablakának megjelenése UTÁN hoz létre
#      (lásd main.py: kezel_update_ready_jelzes).
#   6. Siker esetén a régi példány szépen bezárja magát; hiba/időtúllépés
#      esetén visszaáll az eredeti állapotba, és a régi verzióval fut tovább.
#   7. A hátrahagyott "<név>.exe.old" fájlt a KÖVETKEZŐ induláskor töröljük
#      (akkor már biztosan felszabadul a zár) - lásd cleanup_old_exe().

UPDATE_READY_ARG = "--update-ready"
JELZOFAJL_VARAKOZAS_MP = 20
JELZOFAJL_POLL_INTERVALL_MP = 0.3


def is_frozen():
    """Csak PyInstaller-lel csomagolt (telepített) exe esetén igaz - fejlesztői
    környezetben (python main.py) az önfrissítés ki van kapcsolva."""
    return getattr(sys, "frozen", False)


def get_current_exe_path():
    return os.path.abspath(sys.executable)


def cleanup_old_exe():
    """A main.py legelején hívandó: eltávolítja egy korábbi frissítés által
    hátrahagyott '<név>.exe.old' fájlt, ha az időközben felszabadult."""
    if not is_frozen():
        return
    old_path = get_current_exe_path() + ".old"
    if os.path.exists(old_path):
        try:
            os.remove(old_path)
        except OSError:
            # Még zárolva van (pl. lassan záródó vírusirtó-vizsgálat) -
            # nem baj, majd a következő induláskor újra megpróbáljuk.
            logging.debug("A korábbi .exe.old még nem törölhető, majd legközelebb.")


def kezel_update_ready_jelzes(argv):
    """A main.py-ban, KÖZVETLENÜL a frame.Show() UTÁN hívandó: ha ezt a
    példányt egy önfrissítés indította, létrehozza a jelzőfájlt, amire a
    régi (még futó) példány vár. Szándékosan a Show() UTÁN van, hogy a
    régi példány valóban csak akkor záruljon be, ha az új már látható."""
    if UPDATE_READY_ARG in argv:
        idx = argv.index(UPDATE_READY_ARG)
        try:
            jelzo_fajl = argv[idx + 1]
            with open(jelzo_fajl, "w", encoding="utf-8") as f:
                f.write("ready")
        except (IndexError, OSError) as e:
            logging.warning(f"Nem sikerült létrehozni a frissítés-jelzőfájlt: {e}")


def get_exe_asset_url(release_data):
    """Kikeresi a GitHub release mellékleteiből a Windows .exe letöltési
    URL-jét. Ha több .exe melléklet is szerepelne (pl. telepítő + hordozható
    verzió), ezt a szűrést kell itt pontosítani (pl. név szerint)."""
    for asset in release_data.get("assets", []):
        nev = asset.get("name", "")
        if nev.lower().endswith(".exe"):
            return asset.get("browser_download_url")
    return None


class FrissitesFolyamatDialog(wx.Dialog):
    """Nem-blokkoló (Show(), nem ShowModal()) folyamatjelző. Ezt a RÉGI,
    még futó példány jeleníti meg, ezért a teljes önfrissítés alatt lát
    valamit a felhasználó - nincs "üres" időszak a két ablak között."""

    def __init__(self, parent):
        super().__init__(
            parent, title="Frissítés",
            style=wx.CAPTION | wx.STAY_ON_TOP,
            size=(360, 120),
        )
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.label = wx.StaticText(self, label="Frissítés előkészítése...")
        sizer.Add(self.label, 0, wx.ALL | wx.EXPAND, 15)
        self.gauge = wx.Gauge(self, range=100, style=wx.GA_HORIZONTAL)
        sizer.Add(self.gauge, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 15)
        self.SetSizer(sizer)
        self.CentreOnParent()
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self.gauge.Pulse(), self._timer)
        self._timer.Start(80)

    def set_status(self, szoveg):
        wx.CallAfter(self.label.SetLabel, szoveg)

    def zar(self):
        self._timer.Stop()
        wx.CallAfter(self.Destroy)


def perform_self_update(parent, letoltes_url, uj_verzio):
    """Elindítja a teljes önfrissítési folyamatot háttérszálon: letöltés,
    a futó exe átnevezése, az új exe helyére másolása, az új példány
    elindítása, majd várakozás a jelzésére. A parent (a főablak) a
    folyamatjelző szülője, és siker esetén ez záródik be."""
    if not is_frozen():
        wx.MessageBox(
            "Az automatikus frissítés csak a telepített (exe) verzióban "
            "érhető el - fejlesztői környezetben töltsd le manuálisan.",
            "Frissítés", wx.OK | wx.ICON_INFORMATION, parent,
        )
        return

    dlg = FrissitesFolyamatDialog(parent)
    dlg.Show()

    def worker():
        exe_path = get_current_exe_path()
        exe_dir = os.path.dirname(exe_path)
        old_path = exe_path + ".old"
        tmp_path = None

        try:
            # 1. LETÖLTÉS ideiglenes fájlba (ugyanabba a mappába, hogy az
            # átnevezés/másolás biztosan ugyanazon a köteten maradjon).
            dlg.set_status(f"Új verzió letöltése (v{uj_verzio})...")
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".exe.download", dir=exe_dir)
            os.close(tmp_fd)
            req = urllib.request.Request(
                letoltes_url, headers={"User-Agent": f"KonyvTarnokApp/{APP_VERSION}"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp, open(tmp_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            if os.path.getsize(tmp_path) < 1024:
                raise RuntimeError("A letöltött fájl gyanúsan kicsi/sérült.")

            # 2. A FUTÓ EXE ÁTNEVEZÉSE - ez futás közben is megengedett.
            dlg.set_status("Telepítés...")
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass
            os.rename(exe_path, old_path)

            try:
                os.replace(tmp_path, exe_path)
                tmp_path = None
            except OSError:
                # Ha a másolás meghiúsul, mindenképp álljunk vissza
                # konzisztens állapotba: a régi exe kerüljön vissza az
                # eredeti nevére, hogy a program legközelebb elinduljon.
                os.rename(old_path, exe_path)
                raise

            # 3. ÚJ PÉLDÁNY INDÍTÁSA jelzőfájllal.
            dlg.set_status("Új verzió indítása...")
            jelzo_fd, jelzo_path = tempfile.mkstemp(suffix=".ready")
            os.close(jelzo_fd)
            os.remove(jelzo_path)  # csak a nevet akarjuk, a fájl még ne létezzen

            subprocess.Popen([exe_path, UPDATE_READY_ARG, jelzo_path])

            # 4. VÁRAKOZÁS az új példány jelzésére (időkorláttal).
            hatarido = time.time() + JELZOFAJL_VARAKOZAS_MP
            while time.time() < hatarido:
                if os.path.exists(jelzo_path):
                    try:
                        os.remove(jelzo_path)
                    except OSError:
                        pass
                    dlg.zar()
                    # A régi példány szépen, a normál EVT_CLOSE-on keresztül
                    # záródik be (nem ExitMainLoop-pal), hogy a főablakhoz
                    # esetleg kötött egyéb záráskori teendők is lefussanak.
                    wx.CallAfter(parent.Close)
                    return
                time.sleep(JELZOFAJL_POLL_INTERVALL_MP)

            # Időtúllépés: az új példány nem jelentkezett. A memóriában már
            # betöltött (régi) programkép futása ettől függetlenül zavartalan,
            # csak a lemezen lévő fájl más most - ezért biztonságos így
            # tovább futni, a felhasználót pedig értesítjük.
            raise RuntimeError("Az új verzió nem jelzett vissza a várt időn belül.")

        except Exception as e:
            logging.error("Hiba az önfrissítés közben", exc_info=True)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            dlg.zar()
            hiba_szoveg = str(e)

            def _hiba_uzenet():
                wx.MessageBox(
                    f"A frissítés telepítése nem sikerült, a program a "
                    f"jelenlegi verzióval folytatja.\n\nRészletek: {hiba_szoveg}",
                    "Frissítési hiba", wx.OK | wx.ICON_ERROR, parent,
                )
            wx.CallAfter(_hiba_uzenet)

    threading.Thread(target=worker, daemon=True).start()

def parse_version(version_str):
    """Átalakítja a verzió stringet (pl. 'v0.22.2', '0.23.0-beta') számok tuple-jává az összehasonlításhoz."""
    if not version_str:
        return (0, 0, 0)
    numbers = re.findall(r'\d+', str(version_str))
    return tuple(map(int, numbers)) if numbers else (0, 0, 0)

def should_check_for_updates(config=None):
    """Meghatározza a beállítások és a legutóbbi ellenőrzés alapján, hogy kell-e frissítést keresni."""
    if config is None:
        config = load_settings()
    
    if not config.get("auto_update_check", True):
        return False
    
    freq = config.get("update_frequency", "startup")
    if freq == "startup":
        return True
    
    last_date_str = config.get("last_update_check_date", "")
    if not last_date_str:
        return True
    
    try:
        last_date = datetime.date.fromisoformat(last_date_str)
        today = datetime.date.today()
        diff_days = (today - last_date).days
        
        if freq == "daily":
            return diff_days >= 1
        elif freq == "weekly":
            return diff_days >= 7
        elif freq == "monthly":
            return diff_days >= 30
        else:
            # Ismeretlen/érvénytelen gyakoriság-érték (pl. kézzel vagy
            # hibásan szerkesztett settings.json) esetén biztonságosan
            # engedélyezzük az ellenőrzést, ugyanúgy, ahogy a lenti
            # dátumértelmezési hiba esetén is True-val térünk vissza -
            # így egy sérült beállítás nem kapcsolja ki némán, örökre a
            # frissítés-keresést.
            return True
    except Exception as e:
        logging.warning(f"Dátum értelmezési hiba a frissítés ellenőrzésékor: {e}")
        return True
    
def fetch_latest_release():
    """Lekéri a legfrissebb kiadás adatait a GitHub REST API-n keresztül."""
    req = urllib.request.Request(
        GITHUB_API_URL,
        headers={"User-Agent": f"KonyvTarnokApp/{APP_VERSION}"}
    )
    with urllib.request.urlopen(req, timeout=6) as response:
        if response.status == 200:
            data = json.loads(response.read().decode('utf-8'))
            return data
    return None

class FrissitesDialog(wx.Dialog):
    """Párbeszédablak az új verzió értesítéséhez."""
    def __init__(self, parent, current_ver, latest_ver, release_url, release_notes="", exe_asset_url=None):
        super().__init__(parent, title="Frissítés", size=(480, 340), style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        self.release_url = release_url
        self.latest_ver = latest_ver
        # Az önfrissítés csak akkor kínálható fel, ha (a) csomagolt (frozen)
        # exe-ként fut a program, ÉS (b) a GitHub release-hez tartozik
        # ténylegesen .exe melléklet (lásd get_exe_asset_url).
        self.exe_asset_url = exe_asset_url if is_frozen() else None

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Fejléc
        lbl_title = wx.StaticText(self, label="Új verzió érhető el.")
        lbl_title.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        main_sizer.Add(lbl_title, 0, wx.ALL | wx.ALIGN_CENTER, 12)

        # Verzió infók
        ver_info = f"Jelenlegi: v{current_ver}\nÚj verzió:  v{latest_ver}"
        lbl_ver = wx.StaticText(self, label=ver_info)
        main_sizer.Add(lbl_ver, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        # Kiadási megjegyzések (ha vannak)
        if release_notes:
            lbl_notes = wx.StaticText(self, label="Kiadási megjegyzések:")
            main_sizer.Add(lbl_notes, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
            txt_notes = wx.TextCtrl(self, value=release_notes, style=wx.TE_MULTILINE | wx.TE_READONLY)
            main_sizer.Add(txt_notes, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        # Gombok
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        if self.exe_asset_url:
            btn_telepit = wx.Button(self, label="Frissítés telepítése")
            btn_telepit.SetDefault()
            btn_telepit.Bind(wx.EVT_BUTTON, self.on_telepites)
            btn_sizer.Add(btn_telepit, 0, wx.RIGHT, 10)

        btn_open = wx.Button(self, label="Frissítési oldal megnyitása")
        btn_close = wx.Button(self, wx.ID_CANCEL, label="Később")

        btn_open.Bind(wx.EVT_BUTTON, self.on_open_browser)

        btn_sizer.Add(btn_open, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_close, 0)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 12)

        self.SetSizer(main_sizer)
        self.Centre()

    def on_open_browser(self, event):
        webbrowser.open(self.release_url)
        self.EndModal(wx.ID_OK)

    def on_telepites(self, event):
        # A tényleges letöltést/cserét a főablakra (self.GetParent()) bízzuk,
        # mert ANNAK kell életben maradnia a folyamat alatt, és a
        # FrissitesDialog EndModal után megszűnik.
        parent = self.GetParent()
        self.EndModal(wx.ID_OK)
        perform_self_update(parent, self.exe_asset_url, self.latest_ver)

def check_for_updates_async(parent=None, is_manual=False):
    """
    Elindítja a frissítés-ellenőrzést háttérszálon.
    Ha is_manual=True, akkor figyelmen kívül hagyja a gyakorisági beállításokat.
    """
    config = load_settings()
    if not is_manual and not should_check_for_updates(config):
        return

    def _worker():
        try:
            release_data = fetch_latest_release()
            if release_data:
                # Dátum frissítése a beállításokban
                config["last_update_check_date"] = str(datetime.date.today())
                save_settings(config)

                tag_name = release_data.get("tag_name", "").strip()
                clean_tag = tag_name.lstrip("vV")
                latest_ver = clean_tag or release_data.get("name", "").strip().lstrip("vV")
                release_url = release_data.get("html_url", "https://github.com/BEMKK/Konyvtarnok/releases")
                release_notes = release_data.get("body", "")
                exe_asset_url = get_exe_asset_url(release_data)

                current_tuple = parse_version(APP_VERSION)
                latest_tuple = parse_version(latest_ver)

                if latest_tuple > current_tuple:
                    def _show():
                        dlg = FrissitesDialog(
                            parent, APP_VERSION, latest_ver, release_url, release_notes,
                            exe_asset_url=exe_asset_url,
                        )
                        dlg.ShowModal()
                        dlg.Destroy()
                    wx.CallAfter(_show)
                elif is_manual:
                    def _show_up_to_date():
                        wx.MessageBox(
                            f"Ön a legújabb, (v{APP_VERSION}) verziót használja.",
                            "Nincs újabb frissítés",
                            wx.OK | wx.ICON_INFORMATION,
                            parent
                        )
                    wx.CallAfter(_show_up_to_date)
            elif is_manual:
                def _show_error():
                    wx.MessageBox(
                        "Nem sikerült lekérni a frissítési adatokat.",
                        "Hiba a frissítés ellenőrzésekor",
                        wx.OK | wx.ICON_WARNING,
                        parent
                    )
                wx.CallAfter(_show_error)
        except Exception as e:
            logging.error("Hiba a frissítések ellenőrzésekor", exc_info=True)
            if is_manual:
                # FONTOS: a hibaüzenetet MÉG az except blokkon belül, egy
                # sima stringbe kell menteni. Az "except ... as e" által
                # kötött 'e' nevet Python a blokk végén automatikusan
                # eltávolítja (implicit "del e"), a wx.CallAfter viszont a
                # _show_exc függvényt csak KÉSŐBB, a fő eseményhurokban
                # hívja meg - vagyis már az except blokk lezárása után.
                # Ha 'e'-t közvetlenül használnánk a lenti f-stringben,
                # a tényleges híváskor NameError-t kapnánk a hibaüzenet
                # megjelenítése helyett.
                hiba_szoveg = str(e)

                def _show_exc():
                    wx.MessageBox(
                        f"Hiba történt a frissítések ellenőrzése közben:\n{hiba_szoveg}",
                        "Hiba a frissítés ellenőrzésekor",
                        wx.OK | wx.ICON_ERROR,
                        parent
                    )
                wx.CallAfter(_show_exc)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
