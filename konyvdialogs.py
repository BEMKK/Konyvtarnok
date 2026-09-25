import wx
import webbrowser
from theme_manager import apply_theme_from_settings
# A mezőlista (kulcs, felirat) párjai a constants.py-ba kerültek át, hogy az
# export_manager.py PDF-sablonja ugyanabból az egyetlen forrásból építkezzen,
# mint az itteni adatlap/szerkesztő dialógusok - lásd a constants.py
# megjegyzését.
from constants import MEZO_DEFINICIOK

class KonyvReszletekDialog(wx.Dialog):
    """Könyv adatainak kizárólagos megjelenítése (Olvasó mód - NVDA kompatibilis)."""

    def __init__(self, parent, konyv_adatok, db=None):
        super().__init__(
            parent,
            title=f"Könyv adatlapja: {konyv_adatok.get('cim', '')}",
            size=(500, 580),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.konyv_adatok = konyv_adatok
        self.db = db

        self.init_ui()
        
        self.CentreOnParent()

    def general_szoveg(self):
        """Összeállítja a könyv adatait egy tiszta, jól olvasható szöveggé."""
        vonal = "-" * 40
        szoveg = f"{self.konyv_adatok.get('cim', 'Nincs cím')}\n"
        if self.konyv_adatok.get('alcim'):
            szoveg += f"{self.konyv_adatok.get('alcim')}\n"
        szoveg += f"{vonal}\n\n"

        for kulcs, felirat in MEZO_DEFINICIOK:
            if kulcs in ['cim', 'alcim']:
                continue
            ertek = str(self.konyv_adatok.get(kulcs, "") or "").strip()
            if ertek:
                if kulcs == "rovid_leiras":
                    szoveg += f"{felirat}\n{ertek}\n"
                else:
                    szoveg += f"{felirat} {ertek}\n"

        return szoveg

    def init_ui(self):
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Akadálymentes (NVDA barát) olvasópanel wx.TextCtrl-ből
        self.olvaso_panel = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.BORDER_SUNKEN
        )
        self.olvaso_panel.SetMargins(24, 10)
        self.olvaso_panel.SetValue(self.general_szoveg())

        self.main_sizer.Add(self.olvaso_panel, 1, wx.EXPAND | wx.ALL, 15)

        # Gombok elrendezése
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        if self.db:
            btn_szerkesztes = wx.Button(self, label="Szerkesztés")
            btn_szerkesztes.Bind(wx.EVT_BUTTON, self.on_szerkesztes)
            btn_sizer.Add(btn_szerkesztes, 0, wx.RIGHT, 10)

        btn_bezaras = wx.Button(self, wx.ID_CANCEL, "Bezárás")
        btn_sizer.Add(btn_bezaras, 0)

        self.main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)
        self.SetSizer(self.main_sizer)

        # Téma alkalmazása
        apply_theme_from_settings(self)

        # Fókusz áthelyezése a szövegmezőre, hogy az NVDA azonnal olvashassa
        wx.CallAfter(self.olvaso_panel.SetFocus)

    def on_szerkesztes(self, event):
        """Átvált szerkesztő módra egy szerkesztő dialógus megnyitásával.

        Mivel ez a dialógus (self) már ID_CANCEL-lel zár, mielőtt a
        beágyazott szerkesztő megnyílna, a hívó (main_frame.MegnyitReszletek)
        nem tud a mentés tényéről, és emiatt nem tudná a szokásos módon
        (dlg.ShowModal() == wx.ID_OK ág) frissíteni a főlistát/kijelölést.
        Ezért itt, a szerkesztő dialógus eredménye alapján, közvetlenül
        meghívjuk a szülő ablak (Konyvtarnok) közös
        frissit_lista_szerkesztes_utan segédmetódusát - ugyanazt, amit a
        közvetlen (menü/gomb) szerkesztési útvonal is használ -, hogy a két
        útvonal (adatlap-megtekintés utáni szerkesztés, illetve közvetlen
        szerkesztés) viselkedése ne térjen el egymástól.
        """
        self.EndModal(wx.ID_CANCEL)
        szulo = self.GetParent()
        dlg = KonyvSzerkesztoDialog(
            szulo, konyv_adatok=self.konyv_adatok, db=self.db
        )
        eredmeny = dlg.ShowModal()
        dlg.Destroy()

        if eredmeny == wx.ID_OK and hasattr(szulo, "frissit_lista_szerkesztes_utan"):
            szulo.frissit_lista_szerkesztes_utan(self.konyv_adatok.get("id"))

class KonyvSzerkesztoDialog(wx.Dialog):
    """Könyv szerkesztése vagy új könyv felvitele (Szerkesztő mód)."""

    def __init__(self, parent, konyv_adatok=None, db=None, uj_konyv=False):
        cimsor = (
            "Új könyv felvétele"
            if uj_konyv
            else f"Szerkesztés: {konyv_adatok.get('cim', '') if konyv_adatok else ''}"
        )
        super().__init__(
            parent,
            title=cimsor,
            size=(520, 620),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.db = db
        self.konyv_adatok = konyv_adatok or {}
        self.uj_konyv = uj_konyv
        self.controls = {}

        self.init_ui()
        
        self.CentreOnParent()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        scroll = wx.ScrolledWindow(self, style=wx.VSCROLL)
        scroll.SetScrollRate(0, 20)
        grid = wx.FlexGridSizer(cols=2, vgap=10, hgap=10)
        grid.AddGrowableCol(1, 1)

        for kulcs, cimke in MEZO_DEFINICIOK:
            lbl = wx.StaticText(scroll, label=cimke)
            lbl.SetFont(lbl.GetFont().Bold())

            ertek = str(self.konyv_adatok.get(kulcs) or "")
            if kulcs in ["kiado", "hely", "kotes", "forras", "status"] and self.db:
                # Egyedi értékek gyűjtése az adatbázisból (mint az állománystatisztika dialógusban)
                ertek_map = {}
                for konyv in getattr(self.db, "konyvek", []):
                    val = str(konyv.get(kulcs, "") or "").strip()
                    if val:
                        low = val.lower()
                        if low not in ertek_map:
                            ertek_map[low] = val
                rendezett_ertekek = sorted(ertek_map.values(), key=lambda s: s.lower())
                ctrl = wx.ComboBox(scroll, value=ertek, choices=rendezett_ertekek, style=wx.CB_DROPDOWN)
            elif kulcs in ["alcim", "rovid_leiras"]:
                ctrl = wx.TextCtrl(
                    scroll, value=ertek, style=wx.TE_MULTILINE, size=(-1, 60)
                )
            else:
                ctrl = wx.TextCtrl(scroll, value=ertek)

            self.controls[kulcs] = ctrl
            grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
            grid.Add(ctrl, 1, wx.EXPAND | wx.RIGHT, 5)

        scroll.SetSizer(grid)
        main_sizer.Add(scroll, 1, wx.EXPAND | wx.ALL, 15)

        # Művelet gombok
        btn_sizer = wx.StdDialogButtonSizer()
        btn_mentes = wx.Button(self, wx.ID_OK, "Mentés")
        btn_megse = wx.Button(self, wx.ID_CANCEL, "Mégse")

        btn_mentes.Bind(wx.EVT_BUTTON, self.on_mentes)
        btn_sizer.AddButton(btn_mentes)
        btn_sizer.AddButton(btn_megse)
        
        # Téma alkalmazása Realize előtt
        apply_theme_from_settings(self)

        btn_sizer.Realize()

        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 15)
        self.SetSizer(main_sizer)
        id_mentes_gyors = wx.NewIdRef()
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('S'), id_mentes_gyors)
        ])
        self.SetAcceleratorTable(accel_tbl)
        self.Bind(wx.EVT_MENU, self.on_mentes, id=id_mentes_gyors)

    def on_mentes(self, event):
        """Összegyűjti az adatokat és elmenti az adatbázisba."""
        uj_adatok = {
            kulcs: ctrl.GetValue().strip()
            for kulcs, ctrl in self.controls.items()
        }

        if not uj_adatok.get("cim"):
            wx.MessageBox(
                "A 'Cím' mező kitöltése kötelező!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if self.db:
            try:
                if self.uj_konyv:
                    sikeres = self.db.uj_konyv_hozzaadasa(uj_adatok)
                    if not sikeres:
                        wx.MessageBox(
                            "A könyv mentése nem sikerült, mert a megadott adatok alapján már szerepel az állományban!",
                            "Figyelmeztetés",
                            wx.OK | wx.ICON_WARNING,
                        )
                        return
                else:
                    konyv_id = self.konyv_adatok.get("id")
                    sikeres = self.db.konyv_mentese_by_id(konyv_id, uj_adatok)

                    if not sikeres:
                        wx.MessageBox(
                            "Nem található az eredeti könyv a módosításhoz.",
                            "Hiba",
                            wx.OK | wx.ICON_ERROR,
                        )
                        return

                self.EndModal(wx.ID_OK)
            except Exception as e:
                wx.MessageBox(
                    f"Hiba történt a mentés során:\n{e}",
                    "Hiba",
                    wx.OK | wx.ICON_ERROR,
                )
        else:
            self.EndModal(wx.ID_OK)


# ==============================================================================
# DEZIDERÁTA DIALÓGUSOK ÉS MEZŐDEFINÍCIÓK
# ==============================================================================

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

        apply_theme_from_settings(self)

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

        id_mentes_gyors = wx.NewIdRef()
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('S'), id_mentes_gyors)
        ])
        self.SetAcceleratorTable(accel_tbl)
        self.Bind(wx.EVT_MENU, self.on_ok, id=id_mentes_gyors)

        self.txt_cim.SetFocus()

        apply_theme_from_settings(self)

    def on_status_change(self, event):
        available = self.status_available.GetValue()
        self.txt_location.Enable(available)
        self.txt_price.Enable(available)
        self.txt_link.Enable(available)
        if event is not None and not available:
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
        self.EndModal(wx.ID_OK)

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

