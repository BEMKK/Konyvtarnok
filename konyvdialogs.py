import wx
from theme_manager import apply_theme_from_settings

MEZO_DEFINICIOK = [
    ("cim", "Cím:"),
    ("alcim", "Alcím:"),
    ("szerzo", "Összeállító:"),
    ("egyeb_szemelyek", "Egyéb személyek:"),
    ("kiado", "Kiadó:"),
    ("hely", "Kiadás helye:"),
    ("ev", "Kiadás éve:"),
    ("oldalszam", "Oldalszám:"),
    ("meretek", "Méret (Ma x sz, cm):"),
    ("kotes", "Kötés típusa:"),
    ("rovid_cim", "Rövid cím:"),
    ("bekerult", "Bekerülés dátuma:"),
    ("forras", "Példány forrása:"),
    ("status", "Példány státusza:"),
    ("rovid_leiras", "Példány rövid leírása:")
]

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
        """Átvált szerkesztő módra egy szerkesztő dialógus megnyitásával."""
        self.EndModal(wx.ID_CANCEL)
        dlg = KonyvSzerkesztoDialog(
            self.GetParent(), konyv_adatok=self.konyv_adatok, db=self.db
        )
        dlg.ShowModal()
        dlg.Destroy()

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
