import json
import locale
import os
import sys
import time
import unicodedata
import webbrowser
import wx
from config_manager import load_settings
from theme_manager import apply_theme

# Magyar locale beállítása
try:
    locale.setlocale(locale.LC_ALL, "hu_HU.UTF-8")
except Exception:
    try:
        locale.setlocale(locale.LC_ALL, "hu_HU")
    except Exception:
        pass

APP_NAME = "KönyvTárnok Dezideráta-kezelő"
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(BASE_DIR, "deziderata.json")

# Mezők definíciója a részletes megjelenítéshez
DEZIDERATA_MEZO_DEFINICIOK = [
    ("cim", "Cím:"),
    ("szerzo", "Összeállító:"),
    ("egyeb_szemelyek", "Egyéb személyek:"),
    ("kiado", "Kiadó:"),
    ("hely", "Kiadás helye:"),
    ("ev", "Kiadás éve:"),
    ("priority", "Prioritás:"),
    ("status", "Státusz:"),
    ("location", "Lelőhely:"),
    ("price", "Jelenlegi ár (ft):"),
    ("link", "Link:"),
]

def is_same_book(item1, item2):
    """
    Két könyv/tétel egyezőségét vizsgálja.
    True, ha Cím ÉS Szerző ÉS Kiadó ÉS Kiadás helye ÉS Kiadás éve IS megegyezik.
    """
    def norm(val):
        return str(val or "").strip().lower()

    return (
        norm(item1.get("cim", item1.get("title", ""))) == norm(item2.get("cim", item2.get("title", ""))) and
        norm(item1.get("szerzo", item1.get("author", ""))) == norm(item2.get("szerzo", item2.get("author", ""))) and
        norm(item1.get("kiado", item1.get("publisher", ""))) == norm(item2.get("kiado", item2.get("publisher", ""))) and
        norm(item1.get("hely", item1.get("place", ""))) == norm(item2.get("hely", item2.get("place", ""))) and
        norm(str(item1.get("ev", item1.get("year", "")))) == norm(str(item2.get("ev", item2.get("year", ""))))
    )

# ==============================================================================
# DIALÓGUSOK
# ==============================================================================

class DeziderataReszletekDialog(wx.Dialog):
    """Dezideráta tétel adatainak kizárólagos megjelenítése (Olvasó mód - NVDA kompatibilis)."""

    def __init__(self, parent, item_data, index=None):
        super().__init__(
            parent,
            title=f"Tétel részletei: {item_data.get('cim', item_data.get('title', ''))}",
            size=(500, 580),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.item_data = item_data
        self.index = index

        self.init_ui()
        self.CentreOnParent()

        config = load_settings()
        apply_theme(self, config.get("tema", "vilagos"))

    def general_szoveg(self):
        """Összeállítja a tétel adatait egy tiszta, jól olvasható szöveggé."""
        vonal = "-" * 40
        cim = self.item_data.get('cim', self.item_data.get('title', 'Nincs cím'))
        szoveg = f"{cim}\n{vonal}\n\n"

        for kulcs, felirat in DEZIDERATA_MEZO_DEFINICIOK:
            if kulcs == 'cim':
                continue
            ertek = str(self.item_data.get(kulcs, "") or "").strip()
            if ertek:
                szoveg += f"{felirat} {ertek}\n"

        return szoveg

    def init_ui(self):
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Akadálymentes (NVDA barát) olvasópanel wx.TextCtrl-ből
        self.olvaso_panel = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.TE_AUTO_URL | wx.BORDER_SUNKEN
        )
        self.olvaso_panel.SetMargins(24, 10)
        self.olvaso_panel.SetValue(self.general_szoveg())
        self.olvaso_panel.Bind(wx.EVT_TEXT_URL, self.on_link_click)
        self.main_sizer.Add(self.olvaso_panel, 1, wx.EXPAND | wx.ALL, 15)

        # Gombok elrendezése
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        btn_szerkesztes = wx.Button(self, label="Szerkesztés")
        btn_szerkesztes.Bind(wx.EVT_BUTTON, self.on_szerkesztes)
        btn_sizer.Add(btn_szerkesztes, 0, wx.RIGHT, 10)

        btn_bezaras = wx.Button(self, wx.ID_CANCEL, "Bezárás")
        btn_sizer.Add(btn_bezaras, 0)

        self.main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)
        self.SetSizer(self.main_sizer)

        # Fókusz áthelyezése a szövegmezőre, hogy az NVDA azonnal olvashassa
        wx.CallAfter(self.olvaso_panel.SetFocus)

    def on_link_click(self, event):
        """Kattintáskor megnyitja a linket az alapértelmezett böngészőben."""
        evt = event.GetMouseEvent()
    
        # Kizárólag a bal egérgomb felengedésére (LeftUp) reagálunk,
        # így elkerüljük a dupla megnyitást (amelyet a Down + Up együttes lefutása okozott).
        if evt.LeftUp():
            start = event.GetURLStart()
            end = event.GetURLEnd()
            url = self.olvaso_panel.GetValue()[start:end].strip()
        
            if url:
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                webbrowser.open(url)
            
        event.Skip()

    def on_szerkesztes(self, event):
        """Átvált szerkesztő módra a szerkesztő dialógus megnyitásával."""
        self.EndModal(wx.ID_OK)
        dlg = EditItemDialog(self.GetParent(), data=self.item_data, index=self.index)
        if dlg.ShowModal() == wx.ID_OK:
            updated_data = dlg.get_data()
            if self.index is not None and hasattr(self.GetParent(), "items"):
                self.GetParent().items[self.index] = updated_data
                self.GetParent().save_data()
                self.GetParent().refresh_list()
        dlg.Destroy()


class BaseItemDialog(wx.Dialog):
    """Közös alaposztály a hozzáadó és szerkesztő ablakokhoz."""
    def __init__(self, parent, title, data=None):
        super().__init__(parent, title=title, size=(850, 520))

        if data is None:
            data = {}

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Layout sizer
        form = wx.FlexGridSizer(0, 2, 10, 10)
        form.AddGrowableCol(1, 1)

        def create_field(label_text, value=""):
            clean_label = label_text.rstrip(":")
            lbl = wx.StaticText(panel, label=label_text)
            txt = wx.TextCtrl(panel, value=str(value), name=clean_label)
            
            form.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            form.Add(txt, 1, wx.EXPAND)
            return txt

        # --- Mezők létrehozása ---
        self.txt_cim = create_field("Cím:", data.get("cim", data.get("title", "")))
        self.txt_szerzo = create_field("Összeállító:", data.get("szerzo", data.get("author", "")))
        self.txt_egyeb_szemelyek = create_field("Egyéb személyek:", data.get("egyeb_szemelyek", ""))
        self.txt_kiado = create_field("Kiadó:", data.get("kiado", data.get("publisher", "")))
        self.txt_hely = create_field("Kiadás helye:", data.get("hely", data.get("place", "")))
        self.txt_ev = create_field("Kiadás éve:", data.get("ev", data.get("year", "")))

        # --- Prioritás blokk ---
        form.Add(wx.StaticText(panel, label="Prioritás:"), 0, wx.ALIGN_CENTER_VERTICAL)
        
        self.priority_primary = wx.RadioButton(
            panel, label="Elsődleges", style=wx.RB_GROUP, name="Elsődleges prioritás"
        )
        self.priority_secondary = wx.RadioButton(
            panel, label="Másodlagos", name="Másodlagos prioritás"
        )

        if data.get("priority") == "Elsődleges":
            self.priority_primary.SetValue(True)
        elif data.get("priority") == "Másodlagos":
            self.priority_secondary.SetValue(True)

        prio_box = wx.BoxSizer(wx.HORIZONTAL)
        prio_box.Add(self.priority_primary)
        prio_box.Add(self.priority_secondary, 0, wx.LEFT, 10)
        form.Add(prio_box)

        # --- Státusz blokk ---
        form.Add(wx.StaticText(panel, label="Státusz:"), 0, wx.ALIGN_CENTER_VERTICAL)

        self.status_available = wx.RadioButton(
            panel, label="Jelenleg kapható", style=wx.RB_GROUP, name="Jelenleg kapható státusz"
        )
        self.status_unavailable = wx.RadioButton(
            panel, label="Jelenleg nem kapható", name="Jelenleg nem kapható státusz"
        )

        if data.get("status") == "Jelenleg kapható":
            self.status_available.SetValue(True)
        else:
            self.status_unavailable.SetValue(True)

        status_box = wx.BoxSizer(wx.HORIZONTAL)
        status_box.Add(self.status_available)
        status_box.Add(self.status_unavailable, 0, wx.LEFT, 10)
        form.Add(status_box)

        # --- Lelőhely + ár ---
        self.txt_location = create_field("Lelőhely:", data.get("location", ""))
        self.txt_price = create_field("Jelenlegi ár (ft):", data.get("price", ""))
        self.txt_link = create_field("Link:", data.get("link", ""))

        vbox.Add(form, 1, wx.ALL | wx.EXPAND, 15)

        # --- Gombok ---
        btn_ok = wx.Button(panel, wx.ID_OK, label="Mentés")
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, label="Mégse")

        btn_sizer = wx.StdDialogButtonSizer()
        btn_sizer.AddButton(btn_ok)
        btn_sizer.AddButton(btn_cancel)
        btn_sizer.Realize()

        vbox.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(vbox)

        # Eseménykezelés
        self.status_available.Bind(wx.EVT_RADIOBUTTON, self.on_status_change)
        self.status_unavailable.Bind(wx.EVT_RADIOBUTTON, self.on_status_change)
        btn_ok.Bind(wx.EVT_BUTTON, self.on_ok)
        self.on_status_change(None)

        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('S'), wx.ID_OK)
        ])
        self.SetAcceleratorTable(accel_tbl)

        self.txt_cim.SetFocus()

        config = load_settings()
        apply_theme(self, config.get("tema", "vilagos"))

    def on_status_change(self, event):
        available = self.status_available.GetValue()
        self.txt_location.Enable(available)
        self.txt_price.Enable(available)
        self.txt_link.Enable(available)
        if not available:
            self.txt_location.Clear()
            self.txt_price.Clear()
            self.txt_link.Clear()

    def on_ok(self, event):
        new_data = self.get_data()
        if hasattr(self.GetParent(), "is_duplicate"):
            current_idx = getattr(self, "current_index", None)
            if self.GetParent().is_duplicate(new_data, exclude_idx=current_idx):
                wx.MessageBox(
                    "Ez a tétel már szerepel a dezideráta-jegyzékben!\n(Ugyanaz a cím, szerző, kiadó, hely és év)",
                    "Duplikátum",
                    wx.OK | wx.ICON_WARNING,
                    parent=self
                )
                return
        event.Skip()

    def get_data(self):
        return {
            "cim": self.txt_cim.GetValue(),
            "szerzo": self.txt_szerzo.GetValue(),
            "egyeb_szemelyek": self.txt_egyeb_szemelyek.GetValue(),
            "kiado": self.txt_kiado.GetValue(),
            "hely": self.txt_hely.GetValue(),
            "ev": self.txt_ev.GetValue(),
            "priority": "Elsődleges" if self.priority_primary.GetValue() else "Másodlagos",
            "status": "Jelenleg kapható" if self.status_available.GetValue() else "Jelenleg nem kapható",
            "location": self.txt_location.GetValue(),
            "price": self.txt_price.GetValue(),
            "link": self.txt_link.GetValue()
        }


class AddItemDialog(BaseItemDialog):
    def __init__(self, parent):
        super().__init__(parent, title="Új tétel hozzáadása")


class EditItemDialog(BaseItemDialog):
    def __init__(self, parent, data, index=None):
        self.current_index = index
        title_text = data.get("cim", data.get("title", ""))
        dialog_title = f"Szerkesztés: {title_text}" if title_text else "Tétel szerkesztése"
        super().__init__(parent, title=dialog_title, data=data)


# ==============================================================================
# FŐABLAK ÉS ALKALMAZÁS LOGIKA
# ==============================================================================

class MainFrame(wx.Frame):
    def __init__(self, parent=None, cipher=None):
        super().__init__(parent, title=f"{APP_NAME}", size=(900, 500))
        self.parent = parent
        self.cipher = cipher  # <-- Eltároljuk az ablak példányában
        self.data = []

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

        columns = [
            "Cím",
            "Összeállító",
            "Egyéb személyek",
            "Kiadó",
            "Kiadás helye",
            "Kiadás éve",
            "Prioritás",
            "Státusz"
        ]

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
        item_export = menu_items.Append(wx.ID_ANY, "Dezideráta mentése titkosítás nélküli JSON fájlba...\tCtrl+SHIFT+M")
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
        
        # Gyorskeresés pufferek
        self.beepitett_kereses_buffer = ""
        self.utolso_leutes_ideje = 0
        self.IDO_KUSZOB = 1.2

        # Dupla kattintásra és Enter-re részletes nézet
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_reszletek)
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.list.Bind(wx.EVT_CHAR, self.on_char)

        self.list.SetFocus()

        # Adatok betöltése JSON-ból
        self.load_data()

        # Téma alkalmazása
        config = load_settings()
        self.current_theme = config.get("tema", "vilagos")
        apply_theme(self, self.current_theme)

        self.Centre()
        self.Show()

    def rendez_listat(self):
        """A tételek ábécérendbe rendezése Cím szerint (az ékezetes karaktereket az alapkarakterükhöz illesztve)."""
        def normalize_str(text):
            text = str(text or "").lower()
            # Eltávolítja az ékezeteket a pontos ábécés besoroláshoz (pl. Á -> A)
            normalized = unicodedata.normalize('NFD', text)
            clean = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
            return clean, text

        def get_sort_key(item):
            val = item.get("cim", item.get("title", ""))
            return normalize_str(val)

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
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "rb") as f:
                    nyers_adat = f.read()

                if self.cipher:
                    try:
                        # 1. Próbálkozás: visszafejtés
                        decrypted_bytes = self.cipher.decrypt(nyers_adat)
                        betoltott_adat = json.loads(decrypted_bytes.decode("utf-8"))
                    except Exception:
                        # 2. Próbálkozás: ha nem sikerül, akkor régi sima JSON
                        betoltott_adat = json.loads(nyers_adat.decode("utf-8"))
                        # Automatikus konvertálás titkosítottra a jövőre nézve
                else:
                    betoltott_adat = json.loads(nyers_adat.decode("utf-8"))

                # Ellenőrizzük, hogy listát kaptunk-e, és rendeljük hozzá a self.items-hez!
                if isinstance(betoltott_adat, list):
                    self.items = betoltott_adat
                else:
                    self.items = []

                # Ha titkosított környezetben futunk és nyers JSON-t olvastunk be, elmentjük
                if self.cipher:
                    self.save_data()

                # Lista frissítése a GUI-ban
                self.refresh_list()

            except Exception as e:
                wx.MessageBox(
                    f"Hiba az adatok betöltésekor: {e}",
                    "Hiba",
                    wx.OK | wx.ICON_ERROR,
                )
                self.items = []
        else:
            self.items = []
            self.FrissitStatusBar()

    def save_data(self):
        try:
            json_str = json.dumps(self.items, ensure_ascii=False, indent=4)
            
            if self.cipher:
                # Titkosítás bájtokká
                mentendo_adat = self.cipher.encrypt(json_str.encode("utf-8"))
            else:
                mentendo_adat = json_str.encode("utf-8")

            with open(DATA_FILE, "wb") as f:
                f.write(mentendo_adat)

        except Exception as e:
            wx.MessageBox(
                f"Hiba az adatok mentésekor: {e}",
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

    def on_reszletek(self, event):
        """Megnyitja a kijelölt tétel részletes adatlapját."""
        selected_idx = self.list.GetFirstSelected()
        if selected_idx == -1:
            wx.MessageBox(
                "Kérlek, válassz ki egy tételt a részletek megtekintéséhez!",
                "Nincs kijelölve tétel",
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
        selected_indices = []
        item = self.list.GetFirstSelected()
        while item != -1:
            selected_indices.append(item)
            item = self.list.GetNextSelected(item)

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
        fileDialog = wx.FileDialog(
            self,
            message="Jegyzék exportálása titkosítás nélkül",
            defaultFile="deziderata.json",
            wildcard="JSON fájlok (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )

        if fileDialog.ShowModal() == wx.ID_OK:
            pathname = fileDialog.GetPath()
            try:
                with open(pathname, "w", encoding="utf-8") as f:
                    json.dump(self.items, f, ensure_ascii=False, indent=4)
                    f.flush()  # Biztosítja, hogy az adatok azonnal kiírásra kerüljenek lemezre
                wx.MessageBox("Az adatok sikeresen exportálva!", "Siker", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Hiba történt az exportálás során: {e}", "Hiba", wx.OK | wx.ICON_ERROR)
        
        fileDialog.Destroy()

    def on_import_json(self, event):
        with wx.FileDialog(
            self,
            message="Jegyzék betöltése",
            wildcard="JSON fájlok (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            pathname = fileDialog.GetPath()
            try:
                with open(pathname, "r", encoding="utf-8") as f:
                    imported_data = json.load(f)
                
                if isinstance(imported_data, list):
                    hozzaadva = 0
                    kihagyva = 0
                    for item in imported_data:
                        if isinstance(item, dict):
                            if not self.is_duplicate(item):
                                self.items.append(item)
                                hozzaadva += 1
                            else:
                                kihagyva += 1
                    self.save_data()
                    self.refresh_list()
                    wx.MessageBox(
                        f"Importálás befejeződött!\n\nHozzáadva: {hozzaadva} db\nKihagyva (már létező duplikátum): {kihagyva} db",
                        "Siker",
                        wx.OK | wx.ICON_INFORMATION
                    )
                else:
                    wx.MessageBox("A kiválasztott JSON fájl formátuma nem megfelelő!", "Hiba", wx.OK | wx.ICON_ERROR)
            except Exception as e:
                wx.MessageBox(f"Hiba történt az importálás során: {e}", "Hiba", wx.OK | wx.ICON_ERROR)

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

        kijelolt_indexek = []
        item = self.list.GetFirstSelected()

        while item != -1:
            kijelolt_indexek.append(item)
            item = self.list.GetNextSelected(item)

        if not kijelolt_indexek:
            wx.MessageBox(
                "Nincs kijelölve egyetlen elem sem!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_WARNING,
            )
            return

        db = len(kijelolt_indexek)
        uzenet = f"Biztosan át szeretnéd emelni a kijelölt {db} db tételt az állományba?" if db > 1 else "Biztosan át szeretnéd emelni a kijelölt tételt az állományba?"
        
        confirm = wx.MessageBox(uzenet, "Átemelés megerősítése", wx.YES_NO | wx.ICON_QUESTION)
        if confirm != wx.YES:
            return

        sikeres = 0
        visszautasitott = 0
        sikeres_indexek = []
        for idx in kijelolt_indexek:
            item = self.items[idx]

            konyv_adat = {
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
            }

            if konyv_adat["cim"].strip():
                siker = self.GetParent().db.uj_konyv_hozzaadasa(konyv_adat)
                if siker:
                    sikeres += 1
                    sikeres_indexek.append(idx)
                else:
                    visszautasitott += 1

        parent_frame = self.GetParent()
        if hasattr(parent_frame, "lista"):
            parent_frame.lista.FeltoltLista()
            parent_frame.FrissitStatusBar()
        if sikeres > 0:
            for idx in sorted(sikeres_indexek, reverse=True):
                del self.items[idx]
            self.save_data()
            self.refresh_list()

        if sikeres > 0:
            uzenet = "Az átemelés sikeresen megtörtént!\n\n"
            uzenet += f"• Hozzáadva az állományhoz: {sikeres} db könyv.\n"
            if visszautasitott > 0:
                uzenet += "\nMegjegyzés:\n"
                uzenet += f"• {visszautasitott} db könyv már szerepel az állományban (duplikátum), így nem került újra felvételre."
            
            wx.MessageBox(uzenet, "Átemelés sikeres", wx.OK | wx.ICON_INFORMATION)

        elif visszautasitott > 0:
            wx.MessageBox(
                f"Az átemelés nem történt meg!\n\nA kiválasztott könyv(ek) ({visszautasitott} db) már szerepel(nek) az állományban.",
                "Átemelés sikertelen",
                wx.OK | wx.ICON_WARNING,
            )
        else:
            wx.MessageBox(
                "Nem sikerült átemelni a kiválasztott elemeket.",
                "Átemelés sikertelen",
                wx.OK | wx.ICON_ERROR,
            )

    def feldolgoz_kereso_karakter(self, karakter):
        """Kezeli a karakter hozzáadását a keresési pufferhez és a megfelelő sorra ugrást.
        
        Ha egyetlen betűt nyom le ismételten, a lista körkörösen lép a következő egyező elemre.
        """
        if not karakter:
            return

        aktualis_ido = time.time()
        elozo_buffer = self.beepitett_kereses_buffer

        if aktualis_ido - self.utolso_leutes_ideje > self.IDO_KUSZOB:
            self.beepitett_kereses_buffer = ""
            elozo_buffer = ""

        if karakter == ' ':
            if not self.beepitett_kereses_buffer:
                return
            self.beepitett_kereses_buffer += ' '
        elif karakter.strip():
            # Ismételt egykarakteres leütés detektálása (MIELŐTT a pufferhez adnánk)
            is_single_char_repeat = (
                len(elozo_buffer) == 1 and
                karakter.lower() == elozo_buffer.lower()
            )
            if is_single_char_repeat:
                # Nem bővítjük a puffert, marad az 1 karakteres állapot
                pass
            else:
                self.beepitett_kereses_buffer += karakter
        else:
            return

        self.utolso_leutes_ideje = aktualis_ido
        keresett = self.beepitett_kereses_buffer.lower()
        total = self.list.GetItemCount()
        if total == 0:
            return

        # Ciklikus keresés: ha 1 karakteres puffer és ugyanazt nyomták le,
        # a jelenlegi kijelöléstől kezdve keresünk tovább (körkörösen)
        is_single_char_repeat = (
            len(keresett) == 1 and
            len(elozo_buffer) == 1 and
            keresett == elozo_buffer.lower()
        )

        current_idx = self.list.GetFirstSelected()
        if is_single_char_repeat and current_idx != -1:
            start_idx = (current_idx + 1) % total
        else:
            start_idx = 0

        def keres_elo_tag(keresendo, tol, korokre=False):
            for i in range(tol, total):
                ertek = str(self.list.GetItemText(i)).lower().strip()
                if ertek.startswith(keresendo):
                    return i
            if korokre:
                for i in range(0, tol):
                    ertek = str(self.list.GetItemText(i)).lower().strip()
                    if ertek.startswith(keresendo):
                        return i
            return -1

        # 1. Pontos előtag egyezés keresése
        talalt = keres_elo_tag(keresett, start_idx, korokre=is_single_char_repeat)

        # 2. Ha nincs találat és nem körkörösen kerestünk, próbáljuk az elejéről
        if talalt == -1 and not is_single_char_repeat:
            talalt = keres_elo_tag(keresett, 0)

        # 3. Ékezetes párokat is megpróbáljuk
        if talalt == -1 and len(keresett) > 0:
            elso_kar = keresett[0]
            ekezet_parok = {
                'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ö': 'o', 'ő': 'o',
                'ú': 'u', 'ü': 'u', 'ű': 'u',
                'a': 'á', 'e': 'é', 'i': 'í', 'o': ['ó', 'ö', 'ő'], 'u': ['ú', 'ü', 'ű']
            }
            alternativ_karakterek = []
            if elso_kar in ekezet_parok:
                par = ekezet_parok[elso_kar]
                if isinstance(par, list):
                    alternativ_karakterek.extend(par)
                else:
                    alternativ_karakterek.append(par)

            for alt_kar in alternativ_karakterek:
                modositott = alt_kar + keresett[1:]
                talalt = keres_elo_tag(modositott, start_idx, korokre=is_single_char_repeat)
                if talalt == -1 and not is_single_char_repeat:
                    talalt = keres_elo_tag(modositott, 0)
                if talalt != -1:
                    break

        if talalt != -1:
            for i in range(total):
                self.list.Select(i, False)
            self.list.Select(talalt, True)
            self.list.Focus(talalt)
            self.list.EnsureVisible(talalt)

    def on_char(self, event):
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_BACK:
            if len(self.beepitett_kereses_buffer) > 0:
                self.beepitett_kereses_buffer = self.beepitett_kereses_buffer[:-1]
            return

        karakter = ""
        unicode_key = event.GetUnicodeKey()
        if unicode_key != wx.WXK_NONE:
            try:
                karakter = chr(unicode_key).lower()
            except Exception:
                pass
        
        if not karakter and 32 <= key_code <= 255:
            try:
                karakter = chr(key_code).lower()
            except Exception:
                pass

        if karakter:
            self.feldolgoz_kereso_karakter(karakter)
        else:
            event.Skip()

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
        MainFrame()
        return True

if __name__ == "__main__":
    app = App(False)
    app.MainLoop()