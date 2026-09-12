import urllib.request
import json
import webbrowser
import threading
import re
import datetime
import logging
import wx

from constants import APP_VERSION, APP_NAME
from config_manager import load_settings, save_settings

GITHUB_API_URL = "https://api.github.com/repos/BEMKK/Konyvtarnok/releases/latest"

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
    except Exception as e:
        logging.warning(f"Dátum értelmezési hiba a frissítés ellenőrzésénél: {e}")
        return True
    
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
    def __init__(self, parent, current_ver, latest_ver, release_url, release_notes=""):
        super().__init__(parent, title="Új frissítés érhető el!", size=(480, 340), style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        self.release_url = release_url

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Fejléc
        lbl_title = wx.StaticText(self, label="Új verzió érhető el")
        lbl_title.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        main_sizer.Add(lbl_title, 0, wx.ALL | wx.ALIGN_CENTER, 12)

        # Verzió infók
        ver_info = f"Jelenlegi verzió: v{current_ver}\nÚj verzió:  v{latest_ver}"
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

                current_tuple = parse_version(APP_VERSION)
                latest_tuple = parse_version(latest_ver)

                if latest_tuple > current_tuple:
                    def _show():
                        dlg = FrissitesDialog(parent, APP_VERSION, latest_ver, release_url, release_notes)
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
                def _show_exc():
                    wx.MessageBox(
                        f"Hiba történt a frissítések ellenőrzése közben:\n{e}",
                        "Hiba a frissítés ellenőrzésekor",
                        wx.OK | wx.ICON_ERROR,
                        parent
                    )
                wx.CallAfter(_show_exc)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
