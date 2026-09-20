import os
import re
import wx
from theme_manager import apply_theme_from_settings
from export_manager import export_statisztika_pdf
from config_manager import load_settings, save_settings
from konyv_lista import bekerult_datum_kulcs, magyar_rendezesi_kulcs
from collections import defaultdict

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
        apply_theme_from_settings(self)

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
                    """A jelentésben megjelenő lista rendezési kulcsa.

                    A rend_kulcs mezőtípusának megfelelő rendezést alkalmazza
                    (szám az évnél/oldalszámnál, méret a méreteknél, dátum a
                    bekerülésnél, magyar ábécé egyébként) - ugyanazt a logikát,
                    amit a főablak könyvlistája is használ. Korábban ez a
                    függvény mindig egyszerű kisbetűs szövegként hasonlította
                    össze az értékeket, ezért pl. a "Bekerülés éve" szerinti
                    rendezés valójában a hónapnevek betűrendje szerint történt
                    (augusztus, december, február, január, ...), nem
                    időrendben.
                    """
                    nyers_ertek = konyv.get(rend_kulcs, "")

                    if rend_kulcs in ("oldalszam", "ev"):
                        szam_str = "".join(filter(str.isdigit, str(nyers_ertek)))
                        return int(szam_str) if szam_str else 0

                    if rend_kulcs == "meretek":
                        magassag_resz = str(nyers_ertek).split('x')[0].split('X')[0].strip()
                        match = re.search(r'\d+(?:[.,]\d+)?', magassag_resz)
                        return float(match.group(0).replace(',', '.')) if match else 0.0

                    if rend_kulcs == "bekerult":
                        return bekerult_datum_kulcs(nyers_ertek)

                    return magyar_rendezesi_kulcs(nyers_ertek)

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

        # Helyes toldalékolás meghatározása
        if evtized % 100 == 0:
            if evtized % 1000 == 0:
                toldalek = "-es"  # 1000-es, 2000-es, 3000-es ("ezer" -> magas)
            else:
                toldalek = "-as"  # 1500-as, 1800-as, 1900-as ("száz" -> mély)
        else:
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

    def _kereszttabla_rendezesi_kulcs(self, kulcs, ertek):
        """A kereszttáblás jelentés sor- és oszlopfejléceinek rendezési kulcsa.

        Alapból a Python sorted() egyszerű szöveges (lexikografikus) sorrendet
        adna, ami pl. a "9" és "150" oldalszámoknál, vagy eltérő számjegyű
        éveknél helytelen sorrendet eredményezne. Ehelyett a mező típusának
        megfelelően szám (év, oldalszám, bekerülés éve), méret vagy magyar
        ábécé szerint (a többi mezőnél, beleértve az évszázad/évtized
        feliratokat is, amikben a magyar_rendezesi_kulcs a római számokat is
        helyesen kezeli) rendezünk.
        """
        szoveg = str(ertek or "").strip()

        if kulcs in ("ev", "oldalszam", "bekerult"):
            szam_str = "".join(filter(str.isdigit, szoveg))
            return (0, int(szam_str)) if szam_str else (1, 0)

        if kulcs == "meretek":
            magassag_resz = szoveg.split('x')[0].split('X')[0].strip()
            match = re.search(r'\d+(?:[.,]\d+)?', magassag_resz)
            return (0, float(match.group(0).replace(',', '.'))) if match else (1, 0.0)

        return (0, magyar_rendezesi_kulcs(szoveg))

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
        megjelenített_nevek2 = {}

        # Virtuális mezők (évszázad, évtized) esetén az 'ev' mezőt kell lekérni a könyvből
        f_kulcs1 = "ev" if kulcs1 in ["evszazad", "evtized"] else kulcs1
        f_kulcs2 = "ev" if kulcs2 in ["evszazad", "evtized"] else kulcs2

        for konyv in osszes_konyv:
            v1_raw = (
                self.ertek_feldolgoz(kulcs1, konyv.get(f_kulcs1, ""))
                or "(Nincs megadva)"
            )
            v2_raw = (
                self.ertek_feldolgoz(kulcs2, konyv.get(f_kulcs2, ""))
                or "(Nincs megadva)"
            )

            norm_v1 = v1_raw.lower().strip()
            # A másodlagos szempontot (v2) is normalizáljuk, ugyanúgy mint
            # az elsődlegeset (v1) - enélkül pl. "Budapest" és "budapest"
            # két külön sorként szerepelt volna a kereszttábla belső
            # bontásában, feleslegesen szétdarabolva az összesítést.
            norm_v2 = v2_raw.lower().strip()

            if norm_v1 not in megjelenített_nevek:
                megjelenített_nevek[norm_v1] = v1_raw
            if norm_v2 not in megjelenített_nevek2:
                megjelenített_nevek2[norm_v2] = v2_raw

            matrix[norm_v1][norm_v2] += 1

        szoveg = "ÁLLOMÁNYSTATISZTIKAI JELENTÉS – KERESZTTÁBLÁS ELEMZÉS\n"
        szoveg += "────────────────────────────────────────────\n"
        szoveg += f"Elsődleges szempont: {nev_map.get(kulcs1, kulcs1)}\n"
        szoveg += f"Másodlagos szempont: {nev_map.get(kulcs2, kulcs2)}\n"
        if szuro_text:
            szoveg += f"Keresett érték: '{szures_kifejezes}'\n"
        szoveg += "\n"

        talalat_van = False
        for norm_r1 in sorted(matrix.keys(), key=lambda v: self._kereszttabla_rendezesi_kulcs(kulcs1, v)):
            # Pontos egyezés vizsgálata a részszöveg-keresés helyett
            if szuro_text and norm_r1 != szuro_text:
                continue

            talalat_van = True
            r1_nev = megjelenített_nevek[norm_r1]
            osszesen_r1 = sum(matrix[norm_r1].values())

            szoveg += f"Találatok száma: {osszesen_r1}\n"
            for norm_r2, db in sorted(matrix[norm_r1].items(), key=lambda x: self._kereszttabla_rendezesi_kulcs(kulcs2, x[0])):
                r2_nev = megjelenített_nevek2.get(norm_r2, norm_r2)
                szoveg += f"    - {r2_nev}: {db}\n"
            szoveg += "\n"

        if not talalat_van:
            szoveg += "Nincs a keresési feltételnek megfelelő találat."

        return szoveg
