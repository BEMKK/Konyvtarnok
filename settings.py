import os
import wx
from constants import DEFAULT_LATHATO_OSZLOPOK, ELERHETO_OSZLOPOK
from help import HelpNotebookDialog, sugo_megnyitasa
from theme_manager import get_theme_names, apply_theme

class BeallitasokDialog(wx.Dialog):
    """Beállítások ablak az alkalmazás testreszabásához."""

    FREKVENCIA_OPCIOK = [
        ("startup", "Minden indításkor"),
        ("daily", "Naponta"),
        ("weekly", "Hetente"),
        ("monthly", "Havonta"),
        ("never", "Soha")
    ]

    # A jelölőnégyzetek (kulcs, felirat) párjai a constants.ELERHETO_OSZLOPOK
    # listából származnak (ami a lista tényleges oszlopfejléceit adja), így
    # a beállítások ablakhoz már nem kell behúzni a KonyvListaCtrl-t.
    # Osztályszintű néven a régi BeallitasokDialog.ELERHETO_OSZLOPOK hivatkozások
    # is működnek.
    ELERHETO_OSZLOPOK = ELERHETO_OSZLOPOK

    KERESO_INDITASI_OPCIOK = [
        ("ures", "Üres lista"),
        ("osszes", "A betöltött adatbázis összes tétele"),
    ]

    def __init__(self, parent, config, kezdo_ful=None):
        """A `config` a hívó által betöltött beállítás-szótár (load_settings()
        eredménye) - a dialógus maga nem olvassa újra a settings.json-t, így
        egyetlen forrásból dolgozik. A lathato_oszlopok és a tema kulcsot is
        ebből veszi.

        A `kezdo_ful` a megnyitáskor kiválasztott fül sorszáma (0-tól számolva,
        az AddPage-hívások sorrendjében): 0 Megjelenés, 1 Oszlopok a listában,
        2 Mappák és elérési utak, 3 KönyvTárnok-kereső, 4 Frissítések. None vagy
        érvénytelen szám esetén az első fül. Fül beszúrásakor/áthelyezésekor a
        hívók (konyvtarnok_kereso.py, deziderata.py: on_beallitasok) számait kell
        átírni.
        """
        super().__init__(parent, title="Beállítások", size=(600, 500), style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        self.lathato_oszlopok = config.get("lathato_oszlopok", DEFAULT_LATHATO_OSZLOPOK)
        self.aktiv_tema = config.get("tema", "rendszer")
        # Az OK-nál ehhez viszonyítjuk, hogy a kereső-adatbázis útvonala
        # megváltozott-e (csak a megváltozott, nem létező útvonalat utasítjuk el).
        self._eredeti_kereso_utvonal = config.get("kereso_json_utvonal", "")

        fo_sizer = wx.BoxSizer(wx.VERTICAL)

        # Notebook (Fülek) létrehozása
        self.notebook = wx.Notebook(self)

        # --- 1. FÜL: Megjelenítés / Téma ---
        panel_tema = wx.Panel(self.notebook)
        tema_sizer = wx.BoxSizer(wx.VERTICAL)

        lbl_tema = wx.StaticText(panel_tema, label="Téma")
        self.tema_valaszto = wx.Choice(panel_tema, choices=[nev for _, nev in get_theme_names()])
        self.tema_kulcsok = [kulcs for kulcs, _ in get_theme_names()]

        if self.aktiv_tema in self.tema_kulcsok:
            self.tema_valaszto.SetSelection(self.tema_kulcsok.index(self.aktiv_tema))
        else:
            self.tema_valaszto.SetSelection(0)

        # A Bind csak azután jöhet, hogy a választó létrejött
        self.tema_valaszto.Bind(wx.EVT_CHOICE, self.on_tema_valtas_elo_nezet)

        tema_sizer.Add(lbl_tema, 0, wx.ALL, 10)
        tema_sizer.Add(self.tema_valaszto, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
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
        btn_reset_def.Bind(wx.EVT_BUTTON, self.on_alapertelmezett_oszlopok)

        btn_oszlop_sizer.Add(btn_select_all, 0, wx.RIGHT, 5)
        btn_oszlop_sizer.Add(btn_reset_def, 0)
        oszlop_sizer.Add(btn_oszlop_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel_oszlopok.SetSizer(oszlop_sizer)

        # --- 3. FÜL: Alapértelmezett mappák ---
        panel_mappak = wx.Panel(self.notebook)
        mappa_sizer = wx.BoxSizer(wx.VERTICAL)

        # Könyvadatlapok alapértelmezett mappájának megadása
        lbl_pdf = wx.StaticText(panel_mappak, label="Könyvadatlapok alapértelmezett mappája:")
        pdf_box = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_pdf = wx.TextCtrl(panel_mappak, value=config.get("last_pdf_dir", ""))
        btn_pdf_talloz = wx.Button(panel_mappak, label="Tallózás...")
        btn_pdf_talloz.Bind(wx.EVT_BUTTON, lambda e: self._talloz_mappa(self.txt_pdf, "Könyvadatlapok kimeneti mappája"))
        pdf_box.Add(self.txt_pdf, 1, wx.RIGHT, 5)
        pdf_box.Add(btn_pdf_talloz, 0)

        # Statisztikai jelentések alapértelmezett mappája
        lbl_stat_pdf = wx.StaticText(panel_mappak, label="Statisztikai jelentések alapértelmezett mappája:")
        stat_pdf_box = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_stat_pdf = wx.TextCtrl(panel_mappak, value=config.get("last_stat_pdf_dir", ""))
        btn_stat_pdf_talloz = wx.Button(panel_mappak, label="Tallózás...")
        btn_stat_pdf_talloz.Bind(wx.EVT_BUTTON, lambda e: self._talloz_mappa(self.txt_stat_pdf, "Statisztikai jelentések alapértelmezett mappája"))
        stat_pdf_box.Add(self.txt_stat_pdf, 1, wx.RIGHT, 5)
        stat_pdf_box.Add(btn_stat_pdf_talloz, 0)

        # Katalóguslapok alapértelmezett mappája
        lbl_katalogus = wx.StaticText(panel_mappak, label="Katalóguslapok alapértelmezett mappája:")
        katalogus_box = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_katalogus = wx.TextCtrl(panel_mappak, value=config.get("last_katalogus_dir", ""))
        btn_katalogus_talloz = wx.Button(panel_mappak, label="Tallózás...")
        btn_katalogus_talloz.Bind(wx.EVT_BUTTON, lambda e: self._talloz_mappa(self.txt_katalogus, "Katalóguslapok alapértelmezett mappája"))
        katalogus_box.Add(self.txt_katalogus, 1, wx.RIGHT, 5)
        katalogus_box.Add(btn_katalogus_talloz, 0)

        # Állományjegyzék alapértelmezett import/export mappája (kizárólag a nyers JSON-hoz, a program egyébként az alapmappából tölt be!)
        lbl_allomanyjegyzek = wx.StaticText(panel_mappak, label="Állományjegyzék alapértelmezett import/export mappája:")
        allomanyjegyzek_box = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_allomanyjegyzek = wx.TextCtrl(panel_mappak, value=config.get("last_allomany_dir", ""))
        btn_allomany_talloz = wx.Button(panel_mappak, label="Tallózás...")
        btn_allomany_talloz.Bind(wx.EVT_BUTTON, lambda e: self._talloz_mappa(self.txt_allomanyjegyzek, "Állományjegyzék mappájának kiválasztása"))
        allomanyjegyzek_box.Add(self.txt_allomanyjegyzek, 1, wx.RIGHT, 5)
        allomanyjegyzek_box.Add(btn_allomany_talloz, 0)

        # Dezideráta-jegyzék alapértelmezett import/export mappája (kizárólag a nyers JSON-hoz, a program egyébként az alapmappából tölt be!)
        lbl_deziderata = wx.StaticText(panel_mappak, label="Dezideráta alapértelmezett import/export mappája:")
        deziderata_box = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_deziderata = wx.TextCtrl(panel_mappak, value=config.get("last_deziderata_dir", ""))
        btn_deziderata_talloz = wx.Button(panel_mappak, label="Tallózás...")
        btn_deziderata_talloz.Bind(wx.EVT_BUTTON, lambda e: self._talloz_mappa(self.txt_deziderata, "Dezideráta-jegyzék alapértelmezett mappája"))
        deziderata_box.Add(self.txt_deziderata, 1, wx.RIGHT, 5)
        deziderata_box.Add(btn_deziderata_talloz, 0)

        mappa_sizer.Add(lbl_pdf, 0, wx.ALL, 5)
        mappa_sizer.Add(pdf_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        mappa_sizer.Add(lbl_stat_pdf, 0, wx.ALL, 5)
        mappa_sizer.Add(stat_pdf_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        mappa_sizer.Add(lbl_katalogus, 0, wx.ALL, 5)
        mappa_sizer.Add(katalogus_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        mappa_sizer.Add(lbl_allomanyjegyzek, 0, wx.ALL, 5)
        mappa_sizer.Add(allomanyjegyzek_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        mappa_sizer.Add(lbl_deziderata, 0, wx.ALL, 5)
        mappa_sizer.Add(deziderata_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel_mappak.SetSizer(mappa_sizer)

        # --- 4. FÜL: KönyvTárnok-kereső ---
        panel_kereso = self.panel_kereso = wx.Panel(self.notebook)
        kereso_sizer = wx.BoxSizer(wx.VERTICAL)

        lbl_adatbazis = wx.StaticText(panel_kereso, label="Adatbázis (JSON fájl):")
        adatbazis_box = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_adatbazis = wx.TextCtrl(panel_kereso, value=self._eredeti_kereso_utvonal)
        btn_adatbazis_talloz = wx.Button(panel_kereso, label="Tallózás...")
        btn_adatbazis_talloz.Bind(wx.EVT_BUTTON, lambda e: self._talloz_fajl(self.txt_adatbazis, "JSON fájl kiválasztása"))
        adatbazis_box.Add(self.txt_adatbazis, 1, wx.RIGHT, 5)
        adatbazis_box.Add(btn_adatbazis_talloz, 0)

        lbl_inditas = wx.StaticText(panel_kereso, label="Üres keresőmező esetén:")
        self.choice_kereso_inditas = wx.Choice(
            panel_kereso, choices=[nev for _, nev in self.KERESO_INDITASI_OPCIOK]
        )
        inditas_kulcsok = [k for k, _ in self.KERESO_INDITASI_OPCIOK]
        akt_inditas = config.get("kereso_inditasi_lista", "ures")
        self.choice_kereso_inditas.SetSelection(
            inditas_kulcsok.index(akt_inditas) if akt_inditas in inditas_kulcsok else 0
        )

        kereso_sizer.Add(lbl_inditas, 0, wx.ALL, 10)
        kereso_sizer.Add(self.choice_kereso_inditas, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        kereso_sizer.Add(lbl_adatbazis, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        kereso_sizer.Add(adatbazis_box, 0, wx.EXPAND | wx.ALL, 10)
        panel_kereso.SetSizer(kereso_sizer)

        # --- 5. FÜL: Frissítések ---
        panel_frissites = wx.Panel(self.notebook)
        frissites_sizer = wx.BoxSizer(wx.VERTICAL)

        lbl_freq = wx.StaticText(panel_frissites, label="Frissítések automatikus ellenőrzése:")
        self.choice_freq = wx.Choice(panel_frissites, choices=[nev for _, nev in self.FREKVENCIA_OPCIOK])

        akt_freq = config.get("update_frequency", "startup")
        freq_kulcsok = [k for k, _ in self.FREKVENCIA_OPCIOK]
        self.choice_freq.SetSelection(freq_kulcsok.index(akt_freq) if akt_freq in freq_kulcsok else 0)

        btn_manual_check = wx.Button(panel_frissites, label="Frissítések keresése most...")
        btn_manual_check.Bind(wx.EVT_BUTTON, self.on_manual_update_check)

        frissites_sizer.Add(lbl_freq, 0, wx.ALL, 10)
        frissites_sizer.Add(self.choice_freq, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        frissites_sizer.Add(btn_manual_check, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        panel_frissites.SetSizer(frissites_sizer)

        # Fülek hozzáadása a Notebook-hoz
        self.notebook.AddPage(panel_tema, "Megjelenés")
        self.notebook.AddPage(panel_oszlopok, "Oszlopok a listában")
        self.notebook.AddPage(panel_mappak, "Mappák és elérési utak")
        self.notebook.AddPage(panel_kereso, "KönyvTárnok-kereső")
        self.notebook.AddPage(panel_frissites, "Frissítések")

        if isinstance(kezdo_ful, int) and 0 <= kezdo_ful < self.notebook.GetPageCount():
            self.notebook.SetSelection(kezdo_ful)

        fo_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        # --- Gombok ---
        gomb_sizer = wx.StdDialogButtonSizer()
        ok_gomb = wx.Button(self, wx.ID_OK, label="OK")
        megse_gomb = wx.Button(self, wx.ID_CANCEL, label="Mégse")
        sugo_gomb = wx.Button(self, wx.ID_HELP, label="Súgó")
        sugo_gomb.Bind(wx.EVT_BUTTON, self.on_open_help)
        # Az OK-t (gomb és Ctrl+S) mi kezeljük, hogy hibás adatbázis-útvonalnál
        # a párbeszédablak nyitva maradjon.
        ok_gomb.Bind(wx.EVT_BUTTON, self.on_ok)
        self.Bind(wx.EVT_MENU, self.on_ok, id=wx.ID_OK)

        gomb_sizer.AddButton(ok_gomb)
        gomb_sizer.AddButton(megse_gomb)
        gomb_sizer.AddButton(sugo_gomb)
        gomb_sizer.Realize()

        fo_sizer.Add(gomb_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(fo_sizer)

        # Ctrl+S = Mentés (ugyanaz, mint az OK gomb)
        gyorsbillentyuk = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('S'), wx.ID_OK)
        ])
        self.SetAcceleratorTable(gyorsbillentyuk)

        # A téma alkalmazása akkor történik, amikor már minden vezérlő létezik
        apply_theme(self, self.aktiv_tema)
        self.Centre()

    def on_ok(self, event):
        """Mentés előtti ellenőrzés: egy ÚJONNAN megadott, nem létező
        adatbázisfájlt nem fogadunk el (az útvonal változatlan, de időközben
        eltűnt értéke viszont nem akadályozza a többi beállítás mentését)."""
        utvonal = self.GetKeresoJsonUtvonal()
        if (utvonal and not os.path.isfile(utvonal)
                and not azonos_utvonal(utvonal, self._eredeti_kereso_utvonal)):
            wx.MessageBox(
                f"A megadott adatbázisfájl nem található:\n{utvonal}",
                "Hibás elérési út", wx.OK | wx.ICON_WARNING, self,
            )
            self.notebook.SetSelection(self.notebook.FindPage(self.panel_kereso))
            self.txt_adatbazis.SetFocus()
            return
        self.EndModal(wx.ID_OK)

    def on_tema_valtas_elo_nezet(self, event):
        uj_tema = self.GetKivalasztottTema()
        apply_theme(self, uj_tema)

    def on_mindet_kijelol(self, event):
        for cb in self.jelolo_negyzetek.values():
            cb.SetValue(True)

    def on_alapertelmezett_oszlopok(self, event):
        for kulcs, cb in self.jelolo_negyzetek.items():
            cb.SetValue(kulcs in DEFAULT_LATHATO_OSZLOPOK)

    def on_manual_update_check(self, event):
        # Szándékosan lokális (lusta) import: az update modul csak a kézi
        # ellenőrzés gombnál kell, és modulszintű importként körkörös importot
        # okozhatna (update -> ... -> settings). Ha az update.py sem közvetlenül,
        # sem közvetve nem importálja a settings modult, a fájl elejére áthelyezhető.
        from update import check_for_updates_async
        check_for_updates_async(parent=self, is_manual=True)

    def GetKivalasztottOszlopok(self):
        """Visszaadja a kiválasztott oszlopok kulcsainak listáját."""
        return [kulcs for kulcs, cb in self.jelolo_negyzetek.items() if cb.IsChecked()]

    def GetKivalasztottStatPdfDir(self):
        return self.txt_stat_pdf.GetValue().strip()

    def GetKivalasztottKatalogusDir(self):
        return self.txt_katalogus.GetValue().strip()

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

    def _talloz_fajl(self, text_ctrl, uzenet):
        aktualis = text_ctrl.GetValue().strip()
        kezdo_mappa = os.path.dirname(aktualis)
        dlg = wx.FileDialog(
            self, uzenet,
            defaultDir=kezdo_mappa if os.path.isdir(kezdo_mappa) else "",
            defaultFile=os.path.basename(aktualis),
            wildcard="JSON fájlok (*.json)|*.json|Minden fájl (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dlg.ShowModal() == wx.ID_OK:
            text_ctrl.SetValue(dlg.GetPath())
        dlg.Destroy()

    def GetKivalasztottPdfDir(self):
        return self.txt_pdf.GetValue().strip()

    def GetKeresoJsonUtvonal(self):
        return self.txt_adatbazis.GetValue().strip()

    def GetKeresoInditasiLista(self):
        """A kereső üres-mezős listaállapotának kulcsa ("ures" | "osszes")."""
        idx = self.choice_kereso_inditas.GetSelection()
        kulcsok = [k for k, _ in self.KERESO_INDITASI_OPCIOK]
        return kulcsok[idx] if 0 <= idx < len(kulcsok) else "ures"

    def GetKivalasztottAllomanyDir(self):
        return self.txt_allomanyjegyzek.GetValue().strip()

    def GetKivalasztottDeziderataDir(self):
        return self.txt_deziderata.GetValue().strip()

    def GetUpdateFrequency(self):
        idx = self.choice_freq.GetSelection()
        freq_kulcsok = [k for k, _ in self.FREKVENCIA_OPCIOK]
        return freq_kulcsok[idx] if 0 <= idx < len(freq_kulcsok) else "startup"

    def on_open_help(self, event):
        sugo_megnyitasa(self, 6)


# ==============================================================================
# SEGÉDFÜGGVÉNYEK: a Beállítások megnyitása a gyermekablakokból
# ==============================================================================
def azonos_utvonal(a, b):
    """Igaz, ha a két (nem üres) elérési út ugyanarra a fájlra mutat (az
    elválasztó-karakter, a relatív/abszolút alak és - Windowson - a kis- és
    nagybetű különbsége nem számít)."""
    if not a or not b:
        return False
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def beallitasok_megnyitasa_gyermekbol(ablak, ful):
    """A gyermekablak (kereső, Dezideráta) kéri a főablaktól a Beállítások
    megnyitását a `ful` sorszámú fülön (0-tól számolva, lásd a
    BeallitasokDialog.__init__ docstringjét). A főablak kezeli a mentést és az
    alkalmazást is, ezért a párbeszédablak nem itt jön létre."""
    foablak = ablak.GetParent()
    megnyito = getattr(foablak, "beallitasok_megnyitasa", None)
    if megnyito is None:
        # Önálló futás (nincs főablak): nincs mit megnyitni.
        wx.MessageBox(
            "A beállítások csak a főablakból érhetők el, a program önálló futtatásakor nem.",
            "Beállítások", wx.OK | wx.ICON_INFORMATION, ablak,
        )
        return
    megnyito(ful=ful, szulo=ablak)
