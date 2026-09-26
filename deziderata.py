import json
import locale
import logging
import os
import sys
import webbrowser
import wx
from config_manager import load_settings, save_settings
from theme_manager import apply_theme_from_settings
from data_manager import (
    load_hmac_json,
    save_hmac_json,
    tetelek_egyeznek,
    additiv_lista_import,
    konyvek_tomeges_felvetele,
    kerj_tomeges_atemeles_megerositest,
    mutass_tomeges_atemeles_eredmenyt,
    DEZIDERATA_MEZO_ALIASOK,
    is_same_book,
)
from konyvdialogs import (
    DEZIDERATA_MEZO_DEFINICIOK,
    DeziderataReszletekDialog,
    AddItemDialog,
    EditItemDialog,
)
from gyors_kereses import GyorsListaKereso, osszes_kijelolt_index
# A magyar_rendezesi_kulcs az utils.py-ba került át: tisztán szövegfeldolgozó
# logika, semmi köze a konyv_lista.py-beli (GUI) KonyvListaCtrl-hez.
from utils import magyar_rendezesi_kulcs

# Magyar locale beállítása
try:
    locale.setlocale(locale.LC_ALL, "hu_HU.UTF-8")
except Exception:
    try:
        locale.setlocale(locale.LC_ALL, "hu_HU")
    except Exception as e:
        logging.debug(f"Magyar locale beállítása nem sikerült: {e}")

APP_NAME = "KönyvTárnok Dezideráta-kezelő"
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(BASE_DIR, "deziderata.json")

# ==============================================================================
# FŐABLAK ÉS ALKALMAZÁS LOGIKA
# ==============================================================================


class Deziderata(wx.Frame):
    def __init__(self, parent=None):
        super().__init__(parent, title=f"{APP_NAME}", size=(900, 500))
        self.parent = parent

        # Adatmodell: a tételek listája (szótárakból álló listaként)
        self.items = []

        self.statusbar = self.CreateStatusBar()

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # --- Gombok ---
        btn_box = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_details = wx.Button(panel, label="Tétel részletei")
        self.btn_add = wx.Button(panel, label="Új tétel hozzáadása")
        self.btn_edit = wx.Button(panel, label="Tétel szerkesztése")
        self.btn_allomany = wx.Button(panel, label="Felvétel az állományba")
        self.btn_delete = wx.Button(panel, label="Tétel eltávolítása")

        btn_box.Add(self.btn_details, 0, wx.ALL, 5)
        btn_box.Add(self.btn_add, 0, wx.ALL, 5)
        btn_box.Add(self.btn_edit, 0, wx.ALL, 5)
        btn_box.Add(self.btn_allomany, 0, wx.ALL, 5)
        btn_box.Add(self.btn_delete, 0, wx.ALL, 5)

        vbox.Add(btn_box, 0, wx.LEFT | wx.TOP, 5)

        # --- Lista (táblázat) ---
        self.list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN)

        # A táblázat oszlopfejléceit a konyvdialogs.DEZIDERATA_MEZO_DEFINICIOK
        # feliratkészletéből származtatjuk (a meződefiníció végén álló
        # kettőspontot levágva), ahelyett hogy itt egy második, kézzel
        # karbantartott listát tartanánk ugyanezekre a feliratokra - korábban
        # ez a két lista egymástól függetlenül létezett, ezért egy feliratot
        # csak az egyik helyen átnevezve a kettő csendben szétcsúszott volna.
        LISTA_OSZLOP_KULCSOK = [
            "cim", "szerzo", "egyeb_szemelyek", "kiado",
            "hely", "ev", "priority", "status",
        ]
        mezo_feliratok = dict(DEZIDERATA_MEZO_DEFINICIOK)
        columns = [mezo_feliratok[kulcs].rstrip(":") for kulcs in LISTA_OSZLOP_KULCSOK]

        for idx, col in enumerate(columns):
            self.list.InsertColumn(idx, col, width=120)

        vbox.Add(self.list, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(vbox)

        # --- Menüsor ---
        menubar = wx.MenuBar()
        menu_items = wx.Menu()

        item_details = menu_items.Append(wx.ID_ANY, "Tétel részletei")
        item_add = menu_items.Append(wx.ID_NEW, "Új tétel hozzáadása\tCTRL+N")
        item_edit = menu_items.Append(wx.ID_EDIT, "Tétel szerkesztése\tCTRL+E")
        item_allomany = menu_items.Append(wx.ID_ANY, "Tétel állományba vétele\tCTRL+F")
        item_delete = menu_items.Append(wx.ID_DELETE, "Tétel eltávolítása\tDelete")
        menu_items.AppendSeparator()
        item_import = menu_items.Append(wx.ID_ANY, "Dezideráta betöltése...\tCtrl+SHIFT+B")
        item_export = menu_items.Append(wx.ID_ANY, "Dezideráta mentése szerkeszthető JSON fájlba...\tCtrl+SHIFT+M")
        item_exit = menu_items.Append(wx.ID_EXIT, "Kilépés\tCtrl+W")

        menubar.Append(menu_items, "Tételek")
        self.SetMenuBar(menubar)

        # --- Események ---
        self.Bind(wx.EVT_MENU, self.on_reszletek, item_details)
        self.Bind(wx.EVT_MENU, self.on_add, item_add)
        self.Bind(wx.EVT_MENU, self.on_edit, item_edit)
        self.Bind(wx.EVT_MENU, self.on_atemeles_allomanyba, item_allomany)
        self.Bind(wx.EVT_MENU, self.on_delete, item_delete)
        self.Bind(wx.EVT_MENU, self.on_import_json, item_import)
        self.Bind(wx.EVT_MENU, self.on_export_json, item_export)
        self.Bind(wx.EVT_MENU, self.on_exit, item_exit)

        self.btn_details.Bind(wx.EVT_BUTTON, self.on_reszletek)
        self.btn_add.Bind(wx.EVT_BUTTON, self.on_add)
        self.btn_edit.Bind(wx.EVT_BUTTON, self.on_edit)
        self.btn_allomany.Bind(wx.EVT_BUTTON, self.on_atemeles_allomanyba)
        self.btn_delete.Bind(wx.EVT_BUTTON, self.on_delete)
        
        # Gyorskeresés (gépeléssel ugrás a listában)
        self.gyors_kereses = GyorsListaKereso()

        # Dupla kattintásra és Enter-re részletes nézet
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_reszletek)
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.list.Bind(wx.EVT_CHAR, self.on_char)
        self.list.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnListaJobbKlikk)

        self.list.SetFocus()

        # Adatok betöltése JSON-ból
        self.load_data()

        # Téma alkalmazása
        config = apply_theme_from_settings(self)
        self.current_theme = config.get("tema", "vilagos")

        self.Centre()
        self.Show()

    def rendez_listat(self):
        """A tételek ábécérendbe rendezése Cím szerint a magyar ábécé szabályai alapján."""
        def get_sort_key(item):
            val = item.get("cim", item.get("title", ""))
            return magyar_rendezesi_kulcs(val)

        self.items.sort(key=get_sort_key)

    # --- DUPLIKÁCIÓ ELLENŐRZŐ SEGÉDFÜGGVÉNY ---

    def is_duplicate(self, candidate, exclude_idx=None):
        """Megnézi, hogy a jelölt tétel létezik-e már a listában."""
        for idx, item in enumerate(self.items):
            if exclude_idx is not None and idx == exclude_idx:
                continue
            if is_same_book(candidate, item):
                return True
        return False

    # --- JSON KEZELŐ FÜGGVÉNYEK ---

    def load_data(self):
        try:
            betoltott_adat, ervenyes = load_hmac_json(DATA_FILE)
        except Exception as e:
            wx.MessageBox(
                f"Hiba az adatok betöltésekor: {e}",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            self.items = []
            self.FrissitStatusBar()
            return

        if not ervenyes:
            logging.error(
                f"A dezideráta-lista ({DATA_FILE}) HMAC-aláírása érvénytelen: "
                "a fájl megsérült vagy jogosulatlanul módosították."
            )
            wx.MessageBox(
                "Az adatfájl integritás-ellenőrzése sikertelen: a fájl "
                "megsérülhetett, vagy valaki módosította a programon kívül.\n\n"
                "Az adatok betöltése biztonsági okból megszakadt.",
                "Integritási hiba",
                wx.OK | wx.ICON_ERROR,
            )
            self.items = []
            self.FrissitStatusBar()
            return

        # Ellenőrizzük, hogy listát kaptunk-e, és rendeljük hozzá a self.items-hez!
        self.items = betoltott_adat if isinstance(betoltott_adat, list) else []

        # Lista frissítése a GUI-ban
        self.refresh_list()

    def save_data(self):
        if not save_hmac_json(DATA_FILE, self.items):
            wx.MessageBox(
                "Hiba az adatok mentésekor.",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )

    def FrissitStatusBar(self):
        """Frissíti a status bar szövegét az elemek száma alapján."""
        db_szam = self.list.GetItemCount()
        self.statusbar.SetStatusText(f"Dezideráta tételeinek száma: {db_szam}.")

    def refresh_list(self):
        """Frissíti a ListCtrl elemét a tételek ábécérendbe rendezése után."""
        self.rendez_listat()
        self.list.DeleteAllItems()
        for item in self.items:
            cim = item.get("cim", item.get("title", ""))
            szerzo = item.get("szerzo", item.get("author", ""))
            egyeb_szemelyek = item.get("egyeb_szemelyek", "")
            kiado = item.get("kiado", item.get("publisher", ""))
            hely = item.get("hely", item.get("place", ""))
            ev = str(item.get("ev", item.get("year", "")))
            priority = item.get("priority", "")
            status = item.get("status", "")

            index = self.list.InsertItem(self.list.GetItemCount(), cim)
            self.list.SetItem(index, 1, szerzo)
            self.list.SetItem(index, 2, egyeb_szemelyek)
            self.list.SetItem(index, 3, kiado)
            self.list.SetItem(index, 4, hely)
            self.list.SetItem(index, 5, ev)
            self.list.SetItem(index, 6, priority)
            self.list.SetItem(index, 7, status)

        self.FrissitStatusBar()

    # --- ESEMÉNYKEZELŐK ---

    def _MegjelenitPopUpMenut(self):
        indexek = osszes_kijelolt_index(self.list)
        if not indexek:
            return

        popup_menu = wx.Menu()
        megtekint_item = popup_menu.Append(wx.ID_ANY, "Tétel részletei")
        szerkeszt_item = popup_menu.Append(wx.ID_ANY, "Tétel szerkesztése")
        popup_menu.AppendSeparator()
        torol_item = popup_menu.Append(wx.ID_ANY, f"Kijelölt tételek eltávolítása ({len(indexek)} db)")

        self.Bind(wx.EVT_MENU, self.on_reszletek, megtekint_item)
        self.Bind(wx.EVT_MENU, self.on_edit, szerkeszt_item)
        self.Bind(wx.EVT_MENU, self.on_delete, torol_item)

        self.PopupMenu(popup_menu)
        popup_menu.Destroy()

    def OnListaJobbKlikk(self, event):
        idx = event.GetIndex()
        if idx not in osszes_kijelolt_index(self.list):
            self.list.Select(idx)
        self._MegjelenitPopUpMenut()

    def on_reszletek(self, event):
        """Megnyitja a kijelölt tétel részletes adatlapját."""
        selected_idx = self.list.GetFirstSelected()
        if selected_idx == -1:
            wx.MessageBox(
                "Kérjük, válasszon ki egy tételt a listából!",
                "Nincs kijelölés",
                wx.OK | wx.ICON_INFORMATION
            )
            return

        selected_data = self.items[selected_idx]
        dlg = DeziderataReszletekDialog(self, item_data=selected_data, index=selected_idx)
        dlg.ShowModal()
        dlg.Destroy()
        self.list.SetFocus()

    def on_add(self, event):
        dlg = AddItemDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.get_data()
            self.items.append(data)
            self.save_data()
            self.refresh_list()
            target_idx = -1
            for idx, item in enumerate(self.items):
                if is_same_book(item, data):
                    target_idx = idx
                    break
        
            if target_idx != -1:
                self.select_and_focus(target_idx)
            else:
                self.list.SetFocus()
        dlg.Destroy()

    def on_edit(self, event):
        selected_idx = self.list.GetFirstSelected()
        if selected_idx == -1:
            wx.MessageBox(
                "Kérlek, válassz ki egy tételt a szerkesztéshez!",
                "Nincs kijelölve tétel",
                wx.OK | wx.ICON_INFORMATION
            )
            return

        selected_data = self.items[selected_idx]
        dlg = EditItemDialog(self, selected_data, index=selected_idx)
        if dlg.ShowModal() == wx.ID_OK:
            updated_data = dlg.get_data()
            self.items[selected_idx] = updated_data
            self.save_data()
            self.refresh_list()

            target_idx = -1
            for idx, item in enumerate(self.items):
                if is_same_book(item, updated_data):
                    target_idx = idx
                    break

            if target_idx == -1 and self.list.GetItemCount() > 0:
                target_idx = min(selected_idx, self.list.GetItemCount() - 1)

            self.select_and_focus(target_idx)

        dlg.Destroy()

    def on_delete(self, event):
        """Kijelölt tétel(ek) törlése (tömeges törlés támogatásával)."""
        selected_indices = osszes_kijelolt_index(self.list)

        if not selected_indices:
            wx.MessageBox(
                "Kérlek, válassz ki legalább egy tételt a törléshez!",
                "Nincs kijelölve tétel",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        db = len(selected_indices)
        uzenet = (
            f"Biztosan törölni szeretnéd a kijelölt {db} db tételt?"
            if db > 1
            else "Biztosan törölni szeretnéd a kijelölt tételt?"
        )

        confirm = wx.MessageBox(
            uzenet,
            "Törlés megerősítése",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if confirm == wx.YES:
            for index in sorted(selected_indices, reverse=True):
                del self.items[index]

            self.save_data()
            self.refresh_list()
            osszesen = self.list.GetItemCount()
            if osszesen > 0:
                uj_idx = min(selected_indices[0], osszesen - 1)
                self.select_and_focus(uj_idx)
            else:
                self.list.SetFocus()

    def on_export_json(self, event):
        config = load_settings()
        default_dir = config.get("last_json_dir", "")

        fileDialog = wx.FileDialog(
            self,
            message="Jegyzék exportálása nyers JSON fájlba",
            defaultDir=default_dir,
            defaultFile="deziderata.json",
            wildcard="JSON fájlok (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )

        if fileDialog.ShowModal() == wx.ID_OK:
            pathname = fileDialog.GetPath()
            config["last_json_dir"] = os.path.dirname(pathname)
            save_settings(config)
            try:
                with open(pathname, "w", encoding="utf-8") as f:
                    json.dump(self.items, f, ensure_ascii=False, indent=4)
                    f.flush()  # Biztosítja, hogy az adatok azonnal kiírásra kerüljenek lemezre
                wx.MessageBox("Az adatok sikeresen exportálva!", "Siker", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Hiba történt az exportálás során: {e}", "Hiba", wx.OK | wx.ICON_ERROR)
        
        fileDialog.Destroy()

    def on_import_json(self, event):
        config = load_settings()
        default_dir = config.get("last_json_dir", "")

        with wx.FileDialog(
            self,
            message="Jegyzék betöltése",
            defaultDir=default_dir,
            wildcard="JSON fájlok (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            pathname = fileDialog.GetPath()
            config["last_json_dir"] = os.path.dirname(pathname)
            save_settings(config)

            def _hozzaad(item):
                if not self.is_duplicate(item):
                    self.items.append(item)
                    return True
                return False

            try:
                hozzaadva, kihagyva = additiv_lista_import(pathname, _hozzaad)
            except ValueError as e:
                wx.MessageBox(str(e), "Hiba", wx.OK | wx.ICON_ERROR)
                return
            except Exception as e:
                wx.MessageBox(f"Hiba történt az importálás során: {e}", "Hiba", wx.OK | wx.ICON_ERROR)
                return

            self.save_data()
            self.refresh_list()
            wx.MessageBox(
                f"Importálás befejeződött!\n\nHozzáadva: {hozzaadva} db\nKihagyva (már létező duplikátum): {kihagyva} db",
                "Siker",
                wx.OK | wx.ICON_INFORMATION
            )

    def on_exit(self, event):
        self.Close()

    def on_atemeles_allomanyba(self, event=None):
        if not self.GetParent() or not hasattr(self.GetParent(), "db"):
            wx.MessageBox(
                "Az átemelés nem lehetséges, mert a Dezideráta-kezelő önállóan fut!",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return

        kijelolt_indexek = osszes_kijelolt_index(self.list)

        if not kijelolt_indexek:
            wx.MessageBox(
                "Nincs kijelölve egyetlen elem sem!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_WARNING,
            )
            return

        db = len(kijelolt_indexek)
        if not kerj_tomeges_atemeles_megerositest(self, db, "tételt", "az állományba"):
            return

        parent_frame = self.GetParent()

        konyv_adatok = []
        for idx in kijelolt_indexek:
            item = self.items[idx]
            konyv_adatok.append({
                "cim": item.get("cim", item.get("title", "")),
                "alcim": "",
                "szerzo": item.get("szerzo", item.get("author", "")),
                "egyeb_szemelyek": item.get("egyeb_szemelyek", ""),
                "kiado": item.get("kiado", item.get("publisher", "")),
                "hely": item.get("hely", item.get("place", "")),
                "ev": str(item.get("ev", item.get("year", ""))),
                "oldalszam": "",
                "meretek": "",
                "kotes": "",
                "rovid_cim": "",
                "forras": item.get("location", ""),
                "status": "",
                "rovid_leiras": "",
            })

        # A lista frissítését a főablak szűrés-megőrző segédmetódusára
        # bízzuk (ugyanaz, mint kézi felvitelnél, JSON importnál vagy a
        # KönyvTárnok-kereső átemelésénél), hogy egy esetlegesen aktív
        # szűrés/keresés ne sérüljön az átemelés után - egy sima
        # FeltoltLista() ugyanis figyelmen kívül hagyná az aktív szűrést, és
        # megtévesztő állapotot hagyna maga után (a szűrő-felirat és a
        # "Szűrés törlése" gomb aktív maradna, miközben a teljes, szűretlen
        # lista jelenne meg).
        def _frissites(uj_konyv_objektumok):
            if hasattr(parent_frame, "_uj_konyvek_utani_frissites"):
                parent_frame._uj_konyvek_utani_frissites(uj_konyv_objektumok)
            elif hasattr(parent_frame, "lista"):
                parent_frame.lista.FeltoltLista()
                if hasattr(parent_frame, "FrissitStatusBar"):
                    parent_frame.FrissitStatusBar()

        # A tényleges felvételi ciklust a data_manager.konyvek_tomeges_felvetele
        # közös segédfüggvénye végzi (ugyanaz, mint a KönyvTárnok-kereső
        # "Felvétel az állományba" műveleténél).
        sikeres, visszautasitott, sikeres_relativ_indexek, _ = konyvek_tomeges_felvetele(
            parent_frame.db, konyv_adatok, utani_frissites_fv=_frissites
        )

        if sikeres > 0:
            sikeres_indexek = [kijelolt_indexek[i] for i in sikeres_relativ_indexek]
            for idx in sorted(sikeres_indexek, reverse=True):
                del self.items[idx]
            self.save_data()
            self.refresh_list()

        mutass_tomeges_atemeles_eredmenyt(
            self, sikeres, visszautasitott, "az állományhoz", "az állományban"
        )

    def feldolgoz_kereso_karakter(self, karakter):
        """Kezeli a karakter hozzáadását a keresési pufferhez és a megfelelő
        sorra ugrást (lásd gyors_kereses.GyorsListaKereso)."""
        def kijeloles_beallitasa(talalt_idx):
            for i in range(self.list.GetItemCount()):
                self.list.Select(i, False)
            self.list.Select(talalt_idx, True)
            self.list.Focus(talalt_idx)
            self.list.EnsureVisible(talalt_idx)

        self.gyors_kereses.feldolgoz(
            karakter,
            total_lekero=self.list.GetItemCount,
            szoveg_lekero=self.list.GetItemText,
            kivalasztott_lekero=self.list.GetFirstSelected,
            kivalasztas_beallito=kijeloles_beallitasa,
        )

    def on_char(self, event):
        self.gyors_kereses.kezel_char_esemeny(event, self.feldolgoz_kereso_karakter)

    def on_key_down(self, event):
        keycode = event.GetKeyCode()
        control_down = event.ControlDown()

        if control_down and keycode == ord('A'):
            for i in range(self.list.GetItemCount()):
                self.list.Select(i, on=True)
        elif keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_reszletek(event)
        elif keycode == wx.WXK_SPACE:
            # A szóköz billentyű ne nyissa meg a részleteket, de adja hozzá a keresési pufferhez
            self.feldolgoz_kereso_karakter(' ')
        elif keycode == wx.WXK_WINDOWS_MENU or (keycode == wx.WXK_F10 and event.ShiftDown()):
            self._MegjelenitPopUpMenut()
        else:
            event.Skip()

    def select_and_focus(self, index):
        if 0 <= index < self.list.GetItemCount():
            self.list.Select(index)
            self.list.Focus(index)
            self.list.EnsureVisible(index)
        self.list.SetFocus()

class App(wx.App):
    def OnInit(self):
        Deziderata()
        return True

if __name__ == "__main__":
    app = App(False)
    app.MainLoop()