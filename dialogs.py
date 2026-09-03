import re
import os
import sys
import wx
from constants import APP_NAME, APP_VERSION, APP_STAGE
from theme_manager import get_theme_names, apply_theme
from config_manager import load_settings, save_settings
from export_manager import export_statisztika_pdf
from collections import defaultdict

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
        config = load_settings()
        apply_theme(self, config.get("tema", "vilagos"))

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
        config = load_settings()
        apply_theme(self, config.get("tema", "vilagos"))

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
                            "A könyv mentése nem sikerült, mert a megadott adatok alapján már szerepel az állományban!).",
                            "Figyelmeztetés",
                            wx.OK | wx.ICON_WARNING,
                        )
                        return
                else:
                    konyv_id = self.konyv_adatok.get("id")
                    if konyv_id:
                        sikeres = self.db.konyv_mentese_by_id(konyv_id, uj_adatok)
                    else:
                        eredeti_cim = self.konyv_adatok.get("cim")
                        sikeres = self.db.konyv_mentese(eredeti_cim, uj_adatok)

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

class StatisztikaDialog(wx.Dialog):
    """Állomány statisztikai összesítő dialógus, feltételek szerinti darabszám-számítással."""

    def __init__(self, parent, db, meglevo_rendezes="cim"):
        super().__init__(
            parent,
            title="Állománystatisztika",
            size=(700, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.db = db
        self.meglevo_rendezes = meglevo_rendezes
        self.statisztikai_mezok = [
            ("szerzo", "Összeállító"),
            ("kiado", "Kiadó"),
            ("hely", "Kiadás helye"),
            ("ev", "Kiadás éve"),
            ("evszazad", "Kiadási évszázad"),
            ("evtized", "Kiadási évtized"),
            ("kotes", "Kötés típusa"),
            ("bekerult", "Bekerülés éve"),
            ("forras", "Példány forrása"),
            ("status", "Példány státusza"),
        ]

        self.rendezesi_opciok = [
            ("cim", "Cím szerint"),
            ("aktualis", "Aktuális rendezés szerint"),
            ("szempont", "Szűrési szempont szerint")
        ]

        self.init_ui()
        self.CentreOnParent()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Cím felirat
        cim_label = wx.StaticText(self, label="Válassza ki a statisztika feltételét:")
        font = cim_label.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        cim_label.SetFont(font)
        main_sizer.Add(cim_label, 0, wx.ALL, 15)

        # Mező választó sizer
        grid_sizer = wx.FlexGridSizer(rows=5, cols=2, hgap=10, vgap=12)
        grid_sizer.AddGrowableCol(1, 1)

        lbl_mezo = wx.StaticText(self, label="Szűrési szempont:")
        self.choice_mezo = wx.Choice(self, choices=[nev for _, nev in self.statisztikai_mezok])
        self.choice_mezo.SetSelection(0)
        self.choice_mezo.Bind(wx.EVT_CHOICE, self.on_mezo_changed)

        grid_sizer.Add(lbl_mezo, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 15)
        grid_sizer.Add(self.choice_mezo, 1, wx.EXPAND | wx.RIGHT, 15)

        lbl_ertek = wx.StaticText(self, label="Feltétel értéke:")
        self.combo_ertek = wx.ComboBox(self, style=wx.CB_DROPDOWN)
        self.frissit_ertekek_listaja()

        grid_sizer.Add(lbl_ertek, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 15)
        grid_sizer.Add(self.combo_ertek, 1, wx.EXPAND | wx.RIGHT, 15)

        lbl_rendezes = wx.StaticText(self, label="Találatok rendezése:")
        self.choice_rendezes = wx.Choice(self, choices=[nev for _, nev in self.rendezesi_opciok])
        self.choice_rendezes.SetSelection(0)

        grid_sizer.Add(lbl_rendezes, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 15)
        grid_sizer.Add(self.choice_rendezes, 1, wx.EXPAND | wx.RIGHT, 15)

        # 3. Két szempont összevetése (Checkbox)
        self.chk_masodik_mezo = wx.CheckBox(self, label="Második szempont hozzáadása (Összevetés)")
        self.chk_masodik_mezo.SetToolTip("Pipálja be, ha két tulajdonság kapcsolatát szeretné vizsgálni egy táblázatban.")
        self.chk_masodik_mezo.Bind(wx.EVT_CHECKBOX, self.on_masodik_mezo_toggle)

        grid_sizer.Add(wx.StaticText(self, label=""), 0) # Üres cella az igazításhoz
        grid_sizer.Add(self.chk_masodik_mezo, 0, wx.EXPAND | wx.RIGHT, 15)

        # 4. Második szempont mezője (alapértelmezetten rejtve/letiltva)
        self.lbl_mezo2 = wx.StaticText(self, label="Második szempont:")
        self.lbl_mezo2.Disable()
        self.choice_mezo2 = wx.Choice(self, choices=[nev for _, nev in self.statisztikai_mezok])
        self.choice_mezo2.SetSelection(1 if len(self.statisztikai_mezok) > 1 else 0)
        self.choice_mezo2.Disable()

        grid_sizer.Add(self.lbl_mezo2, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 15)
        grid_sizer.Add(self.choice_mezo2, 1, wx.EXPAND | wx.RIGHT, 15)

        main_sizer.Add(grid_sizer, 0, wx.EXPAND | wx.BOTTOM, 15)

        # Számolás gomb
        btn_szamol = wx.Button(self, label="Statisztika lekérdezése")
        btn_szamol.Bind(wx.EVT_BUTTON, self.on_szamol)
        main_sizer.Add(btn_szamol, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)

        # Eredmény megjelenítő doboz (NVDA barát olvasómező)
        self.eredmeny_ctrl = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.BORDER_SUNKEN
        )
        self.eredmeny_ctrl.SetMargins(15, 10)
        self.eredmeny_ctrl.SetValue("Kérjük, válasszon szempontot és értéket, majd kattintson a 'Statisztika lekérdezése' gombra.")
        main_sizer.Add(self.eredmeny_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Alsó gombok (Bezárás, Szűrés)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        btn_szures = wx.Button(self, wx.ID_OK, "Bezárás és lista szűrése")
        btn_szures.SetToolTip("Bezárja a statisztika ablakot, és a főlistát leszűri az aktuálisan kiválasztott statisztikai feltétel találataira.")
        btn_szures.Bind(wx.EVT_BUTTON, self.on_bezaras_es_szures)
        btn_sizer.Add(btn_szures, 0, wx.RIGHT, 10)

        btn_pdf = wx.Button(self, label="Jelentés exportálása")
        btn_pdf.SetToolTip("A generált statisztikai jelentés mentése PDF fájlba.")
        btn_pdf.Bind(wx.EVT_BUTTON, self.on_pdf_export)
        btn_sizer.Add(btn_pdf, 0, wx.RIGHT, 10)

        btn_bezaras = wx.Button(self, wx.ID_CANCEL, "Bezárás")
        btn_sizer.Add(btn_bezaras, 0)
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 15)

        self.SetSizer(main_sizer)

        # Téma alkalmazása
        config = load_settings()
        apply_theme(self, config.get("tema", "vilagos"))

    def get_aktualis_kulcs(self):
        sel = self.choice_mezo.GetSelection()
        if sel != wx.NOT_FOUND and sel < len(self.statisztikai_mezok):
            return self.statisztikai_mezok[sel][0]
        return "kotes"

    def on_mezo_changed(self, event):
        self.frissit_ertekek_listaja()

    def frissit_ertekek_listaja(self):
        kulcs = self.get_aktualis_kulcs()
        ertek_map = {}
    
        # Virtuális mezőknél a meglévő 'ev' oszlop adatait kell alapul venni
        forras_kulcs = "ev" if kulcs in ["evszazad", "evtized"] else kulcs

        for konyv in getattr(self.db, "konyvek", []):
            raw_val = konyv.get(forras_kulcs, "")
            val = self.ertek_feldolgoz(kulcs, raw_val)
            if val:
                low = val.lower()
                if low not in ertek_map:
                    ertek_map[low] = val

        # Rendezés kiadási év / szám szerint az évszázad és évtized mezőknél
        if kulcs == "evszazad":
            romai_sorrend = ["XV.", "XVI.", "XVII.", "XVIII.", "XIX.", "XX.", "XXI."]
            def evszazad_kulcs(s):
                for idx, r in enumerate(romai_sorrend):
                    if r in s:
                        return idx
                return 999
            rendezett_ertekek = sorted(ertek_map.values(), key=evszazad_kulcs)
        elif kulcs == "evtized":
            def evtized_kulcs(s):
                match = re.search(r'\d+', s)
                return int(match.group(0)) if match else 0
            rendezett_ertekek = sorted(ertek_map.values(), key=evtized_kulcs)
        else:
            rendezett_ertekek = sorted(ertek_map.values(), key=lambda s: s.lower())

        self.combo_ertek.Clear()
        osszes_opciok = ["(Összes érték szerinti megoszlás)", "Nincs kitöltve"] + rendezett_ertekek
        self.combo_ertek.Set(osszes_opciok)
        self.combo_ertek.SetSelection(0)

    def on_masodik_mezo_toggle(self, event):
        aktiv = self.chk_masodik_mezo.IsChecked()
        self.lbl_mezo2.Enable(aktiv)
        self.choice_mezo2.Enable(aktiv)

    def on_szamol(self, event):
        # Két szempont összevetése (Kereszttábla)
        if self.chk_masodik_mezo.IsChecked():
            kulcs1 = self.get_aktualis_kulcs()
            sel2 = self.choice_mezo2.GetSelection()
            if sel2 == wx.NOT_FOUND:
                return
            kulcs2 = self.statisztikai_mezok[sel2][0]

            if kulcs1 == kulcs2:
                wx.MessageBox("Kérjük, válasszon két különböző szempontot az összevetéshez!", "Figyelmeztetés", wx.OK | wx.ICON_WARNING, self)
                return

            keresett_szurest_ertek = self.combo_ertek.GetValue().strip()
            szoveg = self.general_kereszttabla(kulcs1, kulcs2, keresett_szurest_ertek)
            self.eredmeny_ctrl.SetValue(szoveg)
            self.eredmeny_ctrl.SetFocus()
            return

        # Egyetlen szempont szerinti elemzések
        kulcs = self.get_aktualis_kulcs()
        megjelenitett_nev = dict(self.statisztikai_mezok).get(kulcs, kulcs)
        keresett_ertek = self.combo_ertek.GetValue().strip()

        if not keresett_ertek:
            wx.MessageBox("Kérjük, adjon meg vagy válasszon ki egy feltétel értéket!", "Figyelmeztetés", wx.OK | wx.ICON_WARNING, self)
            return

        osszes_konyv = getattr(self.db, "konyvek", [])
        osszes_szam = len(osszes_konyv)

        if keresett_ertek == "Nincs kitöltve":
            szoveg = self.general_egyedi_kitoltetlen_statisztika(kulcs, megjelenitett_nev)
        elif keresett_ertek == "(Összes érték szerinti megoszlás)":
            szoveg = "ÁLLOMÁNYSTATISZTIKAI JELENTÉS – TELJES MEGOSZLÁS\n"
            szoveg += "─" * 44 + "\n"
            szoveg += f"Szűrési szempont: {megjelenitett_nev}\n"
            szoveg += f"Állomány összesen: {osszes_szam} db\n\n"

            megoszlas = {}
            megoszlas_nev = {}
            ures_db = 0
            forras_kulcs = "ev" if kulcs in ["evszazad", "evtized"] else kulcs
            for konyv in osszes_konyv:
                val = self.ertek_feldolgoz(kulcs, konyv.get(forras_kulcs, ""))
                if val:
                    low = val.lower()
                    if low not in megoszlas_nev:
                        megoszlas_nev[low] = val
                    megoszlas[low] = megoszlas.get(low, 0) + 1
                else:
                    ures_db += 1

            for low_val, count in sorted(megoszlas.items(), key=lambda item: item[1], reverse=True):
                szazalek = (count / osszes_szam * 100) if osszes_szam > 0 else 0
                szoveg += f"{megoszlas_nev[low_val]}: {count} db ({szazalek:.1f}%)\n"
            
            if ures_db > 0:
                szazalek = (ures_db / osszes_szam * 100) if osszes_szam > 0 else 0
                szoveg += f"\nNincs kitöltve: {ures_db} db ({szazalek:.1f}%)\n"
        else:
            talalatok = []
            forras_kulcs = "ev" if kulcs in ["evszazad", "evtized"] else kulcs
            for konyv in osszes_konyv:
                val = self.ertek_feldolgoz(kulcs, konyv.get(forras_kulcs, ""))
                if val.lower() == keresett_ertek.lower():
                    talalatok.append(konyv)

            talalat_szam = len(talalatok)

            szazalek = (talalat_szam / osszes_szam * 100) if osszes_szam > 0 else 0

            szoveg = "ÁLLOMÁNYSTATISZTIKAI JELENTÉS\n"
            szoveg += "─" * 44 + "\n"
            szoveg += f"Szűrési szempont: {megjelenitett_nev}\n"
            szoveg += f"Keresett érték: '{keresett_ertek}'\n\n"
            szoveg += f"Találatok száma: {talalat_szam}\n"
            szoveg += f"Arány az állományban: {szazalek:.1f}% (Összes: {osszes_szam} db)\n\n"

            if talalat_szam > 0:
                rend_kulcs = self.get_kivalasztott_rendezesi_kulcs()

                def riport_rendezes(konyv):
                    val = str(konyv.get(rend_kulcs, "") or "").lower()
                    return val

                talalatok.sort(key=riport_rendezes)

                szoveg += f"A talált kötetek listája:\n"
                for i, k in enumerate(talalatok, 1):
                    cim = k.get("cim", "Nincs cím")
                    szerzo = k.get("szerzo", "")
                    if szerzo:
                        szoveg += f"  {i}. {szerzo}: {cim}\n"
                    else:
                        szoveg += f"  {i}. {cim}\n"

        self.eredmeny_ctrl.SetValue(szoveg)
        self.eredmeny_ctrl.SetFocus()

    def on_bezaras_es_szures(self, event):
        sel = self.choice_mezo.GetSelection()
        keresett_ertek = self.combo_ertek.GetValue().strip()
        if sel == wx.NOT_FOUND or not keresett_ertek or keresett_ertek == "(Összes érték szerinti megoszlás)":
            wx.MessageBox("Kérjük, válasszon ki egy konkrét statisztikai értéket a szűréshez!", "Figyelmeztetés", wx.OK | wx.ICON_WARNING, self)
            return
        self.EndModal(wx.ID_OK)

    def on_pdf_export(self, event):
        szoveg = self.eredmeny_ctrl.GetValue().strip()
        if not szoveg or szoveg.startswith("Kérjük, válasszon"):
            wx.MessageBox("Nincs exportálható statisztikai eredmény!", "Figyelmeztetés", wx.OK | wx.ICON_WARNING, self)
            return

        config = load_settings()
        default_dir = config.get("last_stat_pdf_dir") or config.get("last_pdf_dir", "")

        kulcs = self.get_aktualis_kulcs()
        megjelenitett_nev = dict(self.statisztikai_mezok).get(kulcs, kulcs)
        keresett_ertek = self.combo_ertek.GetValue().strip()
        
        alap_fajlnev = f"statisztika_{megjelenitett_nev}_{keresett_ertek}" if keresett_ertek and keresett_ertek != "(Összes érték szerinti megoszlás)" else f"statisztika_{megjelenitett_nev}_teljes"
        biztonsagos_fajlnev = "".join([c for c in alap_fajlnev.lower().replace(" ", "_") if c.isalnum() or c in ('_', '-')]).strip('_') + ".pdf"

        ment_dlg = wx.FileDialog(
            self, 
            "Statisztika mentése PDF-ként", 
            defaultDir=default_dir,
            defaultFile=biztonsagos_fajlnev, 
            wildcard="PDF fájl (*.pdf)|*.pdf", 
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )
        if ment_dlg.ShowModal() == wx.ID_OK:
            fajlnev = ment_dlg.GetPath()
            try:
                export_statisztika_pdf(szoveg, fajlnev)
                config["last_stat_pdf_dir"] = os.path.dirname(fajlnev)
                save_settings(config)
                wx.MessageBox("A statisztikai jelentés sikeresen elmentve!", "Sikeres export", wx.OK | wx.ICON_INFORMATION, self)
            except Exception as e:
                wx.MessageBox(f"Hiba történt a PDF mentése során:\n{e}", "Hiba", wx.OK | wx.ICON_ERROR, self)
        ment_dlg.Destroy()

    def ertek_feldolgoz(self, kulcs, ertek_str):
        val = str(ertek_str or "").strip()

        if kulcs == "bekerult" and val:
            match = re.search(r'\b(19\d\d|20\d\d)\b', val)
            if match:
                return match.group(1)

        if kulcs == "evszazad":
            return self._get_evszazad(val)

        if kulcs == "evtized":
            return self._get_evtized(val)

        return val

    def _get_evszazad(self, ev_str):
        match = re.search(r'\b(\d{3,4})\b', str(ev_str or ""))
        if not match:
            return ""
        ev = int(match.group(1))
    
        szazad = (ev - 1) // 100 + 1
    
        romai_szamok = {
            15: "XV.", 16: "XVI.", 17: "XVII.", 18: "XVIII.", 
            19: "XIX.", 20: "XX.", 21: "XXI."
        }
        return f"{romai_szamok.get(szazad, str(szazad) + '.')} század"

    def _get_evtized(self, ev_str):
        match = re.search(r'\b(\d{4})\b', str(ev_str or ""))
        if not match:
            return ""
        ev = int(match.group(1))
        evtized = (ev // 10) * 10
        
        # Helyes toldalékolás meghatározása az utolsó előtti számjegy alapján
        tizes = (evtized // 10) % 10
        toldalek = "-es" if tizes in [1, 4, 5, 7, 9] else "-as"
        
        return f"{evtized}{toldalek} évek"

    def get_kivalasztott_rendezesi_kulcs(self):
        """Visszaadja a kiválasztott rendezési kulcsot."""
        sel = self.choice_rendezes.GetSelection()
        if sel != wx.NOT_FOUND and sel < len(self.rendezesi_opciok):
            valasztott = self.rendezesi_opciok[sel][0]
            if valasztott == "aktualis":
                return self.meglevo_rendezes
            elif valasztott == "szempont":
                szempont = self.get_aktualis_kulcs()
                # Ha a szűrési szempont évtized vagy évszázad, a kiadási év ("ev") szerint rendez
                if szempont in ["evszazad", "evtized"]:
                    return "ev"
                return szempont
            return valasztott
        return "cim"

    def general_egyedi_kitoltetlen_statisztika(self, kulcs, megjelenitett_nev):
        """Kifejezetten az adható mező kitöltetlen sorait listázza ki."""
        osszes_konyv = getattr(self.db, "konyvek", [])
        osszes_szam = len(osszes_konyv)
        if osszes_szam == 0:
            return "Az adatbázis üres."

        hianyos_konyvek = []
        forras_kulcs = "ev" if kulcs in ["evszazad", "evtized"] else kulcs
        for konyv in osszes_konyv:
            val = self.ertek_feldolgoz(kulcs, konyv.get(forras_kulcs, ""))
            if not val:
                hianyos_konyvek.append(konyv)

        hiany_szam = len(hianyos_konyvek)
        szazalek = (hiany_szam / osszes_szam * 100) if osszes_szam > 0 else 0

        szoveg = "ADATMINŐSÉGI JELENTÉS – HIÁNYZÓ ADATOK\n"
        szoveg += "─" * 44 + "\n"
        szoveg += f"Mező neve: {megjelenitett_nev}\n"
        szoveg += f"Hiányzó adatok száma: {hiany_szam} db ({szazalek:.1f}%)\n"
        szoveg += f"Állomány összesen: {osszes_szam} db kötet\n\n"

        if hiany_szam > 0:
            szoveg += f"A kötetek listája, ahol a(z) '{megjelenitett_nev}' mező hiányzik:\n"
            for i, k in enumerate(hianyos_konyvek, 1):
                cim = k.get("cim", "Nincs cím")
                szerzo = k.get("szerzo", "")
                if szerzo:
                    szoveg += f"  {i}. {szerzo}: {cim}\n"
                else:
                    szoveg += f"  {i}. {cim}\n"
        else:
            szoveg += "Minden kötetnél ki van töltve ez a mező!"

        return szoveg

    def general_kereszttabla(self, kulcs1, kulcs2, szures_kifejezes=""):
        """Kétdimenziós megoszlás listázása név-normalizálással és pontos szűréssel."""
        osszes_konyv = getattr(self.db, "konyvek", [])
        nev_map = dict(self.statisztikai_mezok)

        # Pontos szűrés előkészítése (ha konkrét értéket választottak ki)
        szuro_text = ""
        if szures_kifejezes and not szures_kifejezes.startswith("("):
            szuro_text = szures_kifejezes.lower().strip()

        matrix = defaultdict(lambda: defaultdict(int))
        megjelenített_nevek = {}

        # Virtuális mezők (évszázad, évtized) esetén az 'ev' mezőt kell lekérni a könyvből
        f_kulcs1 = "ev" if kulcs1 in ["evszazad", "evtized"] else kulcs1
        f_kulcs2 = "ev" if kulcs2 in ["evszazad", "evtized"] else kulcs2

        for konyv in osszes_konyv:
            v1_raw = (
                self.ertek_feldolgoz(kulcs1, konyv.get(f_kulcs1, ""))
                or "(Nincs megadva)"
            )
            v2 = (
                self.ertek_feldolgoz(kulcs2, konyv.get(f_kulcs2, ""))
                or "(Nincs megadva)"
            )

            norm_v1 = v1_raw.lower().strip()

            if norm_v1 not in megjelenített_nevek:
                megjelenített_nevek[norm_v1] = v1_raw

            matrix[norm_v1][v2] += 1

        szoveg = "ÁLLOMÁNYSTATISZTIKAI JELENTÉS – KERESZTTÁBLÁS ELEMZÉS\n"
        szoveg += "────────────────────────────────────────────\n"
        szoveg += f"Elsődleges szempont: {nev_map.get(kulcs1, kulcs1)}\n"
        szoveg += f"Másodlagos szempont: {nev_map.get(kulcs2, kulcs2)}\n"
        if szuro_text:
            szoveg += f"Keresett érték: '{szures_kifejezes}'\n"
        szoveg += "\n"

        talalat_van = False
        for norm_r1 in sorted(matrix.keys()):
            # Pontos egyezés vizsgálata a részszöveg-keresés helyett
            if szuro_text and norm_r1 != szuro_text:
                continue

            talalat_van = True
            r1_nev = megjelenített_nevek[norm_r1]
            osszesen_r1 = sum(matrix[norm_r1].values())

            szoveg += f"Találatok száma: {osszesen_r1}\n"
            for r2, db in sorted(matrix[norm_r1].items(), key=lambda x: str(x[0])):
                szoveg += f"    - {r2}: {db}\n"
            szoveg += "\n"

        if not talalat_van:
            szoveg += "Nincs a keresési feltételnek megfelelő találat."

        return szoveg

class KeresoDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Keresés és szűrés", size=(350, 180))
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(self, label="Keresett szöveg:")
        self.text_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.text_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_enter)

        input_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        input_sizer.Add(self.text_ctrl, 1, wx.ALL | wx.EXPAND, 5)

        # Pontos egyezés jelölőnégyzet
        self.exact_match_cb = wx.CheckBox(self, label="Csak pontos egyezés")

        # Gombok (OK és Mégse)
        btn_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(self, wx.ID_OK, label="Keresés")
        cancel_button = wx.Button(self, wx.ID_CANCEL, label="Mégse")

        btn_sizer.AddButton(ok_button)
        btn_sizer.AddButton(cancel_button)
        
        # Téma alkalmazása Realize előtt
        config = load_settings()
        apply_theme(self, config.get("tema", "vilagos"))

        btn_sizer.Realize()

        # Összeállítás
        main_sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(
            self.exact_match_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10
        )
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)
        
        self.CentreOnParent()

    def get_search_text(self):
        """Visszaadja a beírt keresőszöveget."""
        return self.text_ctrl.GetValue()

    def is_exact_match(self):
        """Visszaadja, hogy be van-e jelölve a pontos egyezés."""
        return self.exact_match_cb.IsChecked()

    def on_enter(self, event):
        self.EndModal(wx.ID_OK)

class BeallitasokDialog(wx.Dialog):
    """Beállítások ablak az alkalmazás testreszabásához."""

    RENDEZESI_OPOK = [
        ("cim", "Cím"),
        ("szerzo", "Összeállító"),
        ("kiado", "Kiadó"),
        ("ev", "Kiadás éve"),
        ("oldalszam", "Oldalszám"),
        ("meretek", "Méret"),
        ("bekerult", "Bekerülés dátuma")
    ]

    ELERHETO_OSZLOPOK = [
        ("cim", "Cím"),
        ("alcim", "Alcím"),
        ("szerzo", "Összeállító"),
        ("egyeb_szemelyek", "Egyéb személyek"),
        ("kiado", "Kiadó"),
        ("hely", "Kiadás helye"),
        ("ev", "Kiadás éve"),
        ("oldalszam", "Oldalszám"),
        ("meretek", "Méretek"),
        ("kotes", "Kötés"),
        ("rovid_cim", "Rövid cím"),
        ("bekerult", "Bekerülés"),
        ("forras", "Forrás"),
        ("status", "Státusz")
    ]

    def __init__(self, parent, lathato_oszlopok=None, aktiv_tema="vilagos"):
        super().__init__(parent, title="Beállítások", size=(420, 500), style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        config = load_settings()        
        self.lathato_oszlopok = lathato_oszlopok if lathato_oszlopok is not None else [k for k, _ in self.ELERHETO_OSZLOPOK]
        self.aktiv_tema = aktiv_tema

        fo_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Notebook (Fülek) létrehozása
        self.notebook = wx.Notebook(self)

        # --- 1. FÜL: Megjelenítés / Téma ---
        panel_tema = wx.Panel(self.notebook)
        tema_sizer = wx.BoxSizer(wx.VERTICAL)
        
        lbl_tema = wx.StaticText(panel_tema, label="Válassza ki az alkalmazás témáját:")
        self.tema_valaszto = wx.Choice(panel_tema, choices=[nev for _, nev in get_theme_names()])
        self.tema_kulcsok = [kulcs for kulcs, _ in get_theme_names()]
        
        if self.aktiv_tema in self.tema_kulcsok:
            self.tema_valaszto.SetSelection(self.tema_kulcsok.index(self.aktiv_tema))
        else:
            self.tema_valaszto.SetSelection(0)
            
        lbl_rendezes = wx.StaticText(panel_tema, label="Alapértelmezett rendezés:")
        self.rendezes_valaszto = wx.Choice(panel_tema, choices=[nev for _, nev in self.RENDEZESI_OPOK])
        
        akt_rend = config.get("alapertelmezett_rendezes", "cim")
        rend_kulcsok = [k for k, _ in self.RENDEZESI_OPOK]
        self.rendezes_valaszto.SetSelection(rend_kulcsok.index(akt_rend) if akt_rend in rend_kulcsok else 0)

        tema_sizer.Add(lbl_tema, 0, wx.ALL, 10)
        tema_sizer.Add(self.tema_valaszto, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        tema_sizer.Add(lbl_rendezes, 0, wx.ALL, 10)
        tema_sizer.Add(self.rendezes_valaszto, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        panel_tema.SetSizer(tema_sizer)

        # --- 2. FÜL: Oszlopok beállítása ---
        panel_oszlopok = wx.Panel(self.notebook)
        oszlop_sizer = wx.BoxSizer(wx.VERTICAL)
        lbl_oszlopok = wx.StaticText(panel_oszlopok, label="Válassza ki a listában megjelenő oszlopokat:")
        oszlop_sizer.Add(lbl_oszlopok, 0, wx.ALL, 10)
        
        # Gördíthető felület arra az esetre, ha tovább bővülne a mezők listája
        scroll = wx.ScrolledWindow(panel_oszlopok, style=wx.VSCROLL)
        scroll.SetScrollRate(0, 15)
        
        # cols=1 -> szigorúan egymás alatti, lineáris Tab sorrend
        grid_sizer = wx.FlexGridSizer(cols=1, vgap=6, hgap=0)
        self.jelolo_negyzetek = {}

        for kulcs, cimke in self.ELERHETO_OSZLOPOK:
            cb = wx.CheckBox(scroll, label=cimke)
            cb.SetValue(kulcs in self.lathato_oszlopok)
            if kulcs == "cim":
                cb.Disable()
            self.jelolo_negyzetek[kulcs] = cb
            grid_sizer.Add(cb, 0, wx.LEFT | wx.RIGHT | wx.TOP, 3)

        scroll.SetSizer(grid_sizer)
        oszlop_sizer.Add(scroll, 1, wx.EXPAND | wx.ALL, 10)
        btn_oszlop_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_select_all = wx.Button(panel_oszlopok, label="Mindet kijelöl")
        btn_reset_def = wx.Button(panel_oszlopok, label="Alapértelmezettek visszaállítása")
        
        btn_select_all.Bind(wx.EVT_BUTTON, self.on_mindet_kijelol)
        btn_reset_def.Bind(wx.EVT_BUTTON, self.on_alapértelmezett_oszlopok)

        btn_oszlop_sizer.Add(btn_select_all, 0, wx.RIGHT, 5)
        btn_oszlop_sizer.Add(btn_reset_def, 0)
        oszlop_sizer.Add(btn_oszlop_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel_oszlopok.SetSizer(oszlop_sizer)

        # --- 3. FÜL: Alapértelmezett mappák ---
        panel_mappak = wx.Panel(self.notebook)
        mappa_sizer = wx.BoxSizer(wx.VERTICAL)

        # PDF mappa mező és gomb
        lbl_pdf = wx.StaticText(panel_mappak, label="PDF fájlok alapértelmezett mappája:")
        pdf_box = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_pdf = wx.TextCtrl(panel_mappak, value=config.get("last_pdf_dir", ""))
        btn_pdf_talloz = wx.Button(panel_mappak, label="Tallózás...")
        btn_pdf_talloz.Bind(wx.EVT_BUTTON, lambda e: self._talloz_mappa(self.txt_pdf, "PDF mappa kiválasztása"))
        pdf_box.Add(self.txt_pdf, 1, wx.RIGHT, 5)
        pdf_box.Add(btn_pdf_talloz, 0)

        lbl_stat_pdf = wx.StaticText(panel_mappak, label="Statisztikai jelentések alapértelmezett mappája:")
        stat_pdf_box = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_stat_pdf = wx.TextCtrl(panel_mappak, value=config.get("last_stat_pdf_dir", ""))
        btn_stat_pdf_talloz = wx.Button(panel_mappak, label="Tallózás...")
        btn_stat_pdf_talloz.Bind(wx.EVT_BUTTON, lambda e: self._talloz_mappa(self.txt_stat_pdf, "Statisztika PDF mappa kiválasztása"))
        stat_pdf_box.Add(self.txt_stat_pdf, 1, wx.RIGHT, 5)
        stat_pdf_box.Add(btn_stat_pdf_talloz, 0)

        # JSON mappa mező és gomb
        lbl_json = wx.StaticText(panel_mappak, label="JSON fájlok alapértelmezett mappája:")
        json_box = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_json = wx.TextCtrl(panel_mappak, value=config.get("last_json_dir", ""))
        btn_json_talloz = wx.Button(panel_mappak, label="Tallózás...")
        btn_json_talloz.Bind(wx.EVT_BUTTON, lambda e: self._talloz_mappa(self.txt_json, "JSON mappa kiválasztása"))
        json_box.Add(self.txt_json, 1, wx.RIGHT, 5)
        json_box.Add(btn_json_talloz, 0)

        mappa_sizer.Add(lbl_pdf, 0, wx.ALL, 5)
        mappa_sizer.Add(pdf_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        mappa_sizer.Add(lbl_stat_pdf, 0, wx.ALL, 5)
        mappa_sizer.Add(stat_pdf_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        mappa_sizer.Add(lbl_json, 0, wx.ALL, 5)
        mappa_sizer.Add(json_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel_mappak.SetSizer(mappa_sizer)

        # Fülek hozzáadása a Notebook-hoz
        self.notebook.AddPage(panel_tema, "Téma és rendezés")
        self.notebook.AddPage(panel_oszlopok, "Megjelenítendő oszlopok")
        self.notebook.AddPage(panel_mappak, "Mappák és elérési utak")

        fo_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        # --- Gombok ---
        gomb_sizer = wx.StdDialogButtonSizer()
        ok_gomb = wx.Button(self, wx.ID_OK, label="Mentés")
        megse_gomb = wx.Button(self, wx.ID_CANCEL, label="Mégse")
        
        gomb_sizer.AddButton(ok_gomb)
        gomb_sizer.AddButton(megse_gomb)
        
        apply_theme(self, self.aktiv_tema)
        gomb_sizer.Realize()

        fo_sizer.Add(gomb_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(fo_sizer)
        self.Centre()

    def on_mindet_kijelol(self, event):
        for cb in self.jelolo_negyzetek.values():
            cb.SetValue(True)

    def on_alapértelmezett_oszlopok(self, event):
        alap_oszlopok = ["cim", "szerzo", "kiado", "hely", "ev", "status"]
        for kulcs, cb in self.jelolo_negyzetek.items():
            cb.SetValue(kulcs in alap_oszlopok)

    def GetKivalasztottOszlopok(self):
        """Visszaadja a kiválasztott oszlopok kulcsainak listáját."""
        return [kulcs for kulcs, cb in self.jelolo_negyzetek.items() if cb.IsChecked()]

    def GetKivalasztottRendezes(self):
        idx = self.rendezes_valaszto.GetSelection()
        return self.RENDEZESI_OPOK[idx][0] if idx != wx.NOT_FOUND else "cim"

    def GetKivalasztottStatPdfDir(self):
        return self.txt_stat_pdf.GetValue().strip()

    def GetKivalasztottTema(self):
        """Visszaadja a kiválasztott téma kulcsát."""
        sel_idx = self.tema_valaszto.GetSelection()
        if 0 <= sel_idx < len(self.tema_kulcsok):
            return self.tema_kulcsok[sel_idx]
        return "vilagos"

    def _talloz_mappa(self, text_ctrl, uzenet):
        dlg = wx.DirDialog(self, uzenet, defaultPath=text_ctrl.GetValue(), style=wx.DD_DEFAULT_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            text_ctrl.SetValue(dlg.GetPath())
        dlg.Destroy()

    def GetKivalasztottPdfDir(self):
        return self.txt_pdf.GetValue().strip()

    def GetKivalasztottJsonDir(self):
        return self.txt_json.GetValue().strip()

class NevjegyDialog(wx.Dialog):
    """Saját Névjegy párbeszédablak wx.Dialog alapokon."""
    def __init__(self, parent=None):
        super().__init__(parent, title="Névjegy", size=(420, 320), style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        
        sizer = wx.BoxSizer(wx.VERTICAL)

        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

        icon_path = os.path.join(base_dir, "ikon.png")

        try:
            if os.path.exists(icon_path):
                img = wx.Image(icon_path, wx.BITMAP_TYPE_PNG)
                img = img.Scale(80, 80, wx.IMAGE_QUALITY_HIGH)
                bitmap = wx.Bitmap(img)
                
                icon_bitmap = wx.StaticBitmap(self, bitmap=bitmap)
                sizer.Add(icon_bitmap, 0, wx.ALIGN_CENTER | wx.TOP, 15)
            else:
                print(f"Névjegy ikon nem található: {icon_path}")
        except Exception as e:
            print(f"Névjegy ikon hiba: {e}")

        cim_label = wx.StaticText(self, label=APP_NAME)
        font = cim_label.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        font.SetPointSize(11)
        cim_label.SetFont(font)
        sizer.Add(cim_label, 0, wx.ALIGN_CENTER | wx.TOP, 20)
        
        verzio_label = wx.StaticText(self, label=f"v{APP_VERSION} {APP_STAGE}".strip())
        sizer.Add(verzio_label, 0, wx.ALIGN_CENTER | wx.TOP, 5)
        
        leiras_label = wx.StaticText(self, label="Állomány- és Katalóguskezelő rendszer magángyűjtemények számára.")
        sizer.Add(leiras_label, 0, wx.ALIGN_CENTER | wx.ALL, 15)
        
        fejleszto_label = wx.StaticText(self, label="© 2026 KönyvTárnok")
        sizer.Add(fejleszto_label, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)
        
        ok_gomb = wx.Button(self, id=wx.ID_OK, label="OK")
        
        # Téma alkalmazása Realize/Hozzáadás után, de megjelenítés előtt
        config = load_settings()
        apply_theme(self, config.get("tema", "vilagos"))

        sizer.Add(ok_gomb, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)
        
        self.SetSizer(sizer)
        
        self.Centre()

class UjdonsagokDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Újdonságok", size=(460, 360), style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        cim_label = wx.StaticText(self, label="A verzió újdonságai:")
        font_cim = cim_label.GetFont()
        font_cim.SetWeight(wx.FONTWEIGHT_BOLD)
        font_cim.SetPointSize(12)
        cim_label.SetFont(font_cim)
        main_sizer.Add(cim_label, 0, wx.ALIGN_CENTER | wx.TOP, 15)
        
        verzio_label = wx.StaticText(self, label=f"v{APP_VERSION} {APP_STAGE}".strip())
        verzio_label.SetForegroundColour(wx.Colour(120, 120, 120))
        main_sizer.Add(verzio_label, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 5)        

        main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 15)
        
        ujdonsagok_lista = [
            "Az alkalmazás neve mostantól KönyvTárnok."
        ]

        szoveg_box = wx.BoxSizer(wx.VERTICAL)
        for elem in ujdonsagok_lista:
            pont_sizer = wx.BoxSizer(wx.HORIZONTAL)
            bullet = wx.StaticText(self, label="• ")
            bullet.SetForegroundColour(wx.Colour(0, 120, 215))
            
            txt = wx.StaticText(self, label=elem)
            txt.Wrap(380)
            
            pont_sizer.Add(bullet, 0, wx.TOP, 1)
            pont_sizer.Add(txt, 1, wx.EXPAND)
            szoveg_box.Add(pont_sizer, 0, wx.EXPAND | wx.BOTTOM, 8)

        main_sizer.Add(szoveg_box, 1, wx.EXPAND | wx.ALL, 20)

        # Gomb elhelyezése
        btn_sizer = wx.StdDialogButtonSizer()
        ok_gomb = wx.Button(self, id=wx.ID_OK, label="OK")
        ok_gomb.SetDefault()
        btn_sizer.AddButton(ok_gomb)
        
        # Téma alkalmazása Realize előtt
        config = load_settings()
        apply_theme(self, config.get("tema", "vilagos"))

        btn_sizer.Realize()
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)
        
        self.SetSizer(main_sizer)
        
        self.Centre()

class FajlutkozesDialog(wx.MessageDialog):
    def __init__(self, parent, fajlnev):
        msg = f"A(z) '{fajlnev}' fájl már létezik a célmappában.\nSzeretné felülírni?"
        super().__init__(
            parent, 
            msg, 
            "Fájlütközés", 
            wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT | wx.ICON_QUESTION
        )
        self.SetYesNoCancelLabels("Felülírás", "Kihagyás", "Mindet felülír")
