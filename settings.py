import os
import wx
from constants import (
    DEFAULT_LATHATO_OSZLOPOK, ELERHETO_OSZLOPOK,
    DEFAULT_DEZIDERATA_LATHATO_OSZLOPOK, DEZIDERATA_ELERHETO_OSZLOPOK,
)
from help import sugo_megnyitasa
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
    DEZIDERATA_ELERHETO_OSZLOPOK = DEZIDERATA_ELERHETO_OSZLOPOK

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
        az AddPage-hívások sorrendjében): 0 Megjelenés, 1 Állománykezelő
        (oszlopok a listában + az állomány mappái), 2 Dezideráta-kezelő
        (oszlopok a listában + import/export mappa), 3 KönyvTárnok-kereső,
        4 Frissítések. None vagy érvénytelen szám esetén az első fül. Fül
        beszúrásakor/áthelyezésekor a hívók (konyvtarnok_kereso.py,
        deziderata.py: on_beallitasok) számait kell átírni.
        """
        # Az Állománykezelő fül (12 oszlopsor + 4 mappamező) magasabb ablakot kér;
        # az átméretezhető keret biztonsági háló kisebb képernyőre/nagyobb
        # betűméretre: ilyenkor a lista magassága alkalmazkodik.
        super().__init__(parent, title="Beállítások", size=(620, 700),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP)
        self.SetMinSize((560, 520))
        self.lathato_oszlopok = config.get("lathato_oszlopok", DEFAULT_LATHATO_OSZLOPOK)
        self.dez_lathato_oszlopok = config.get(
            "deziderata_lathato_oszlopok", DEFAULT_DEZIDERATA_LATHATO_OSZLOPOK)
        if not isinstance(self.dez_lathato_oszlopok, (list, tuple)):
            self.dez_lathato_oszlopok = DEFAULT_DEZIDERATA_LATHATO_OSZLOPOK
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

        # Az oszlopválasztó natív jelölőnégyzetes listavezérlője (wx.ListCtrl)
        # wxPython 4.1-től érhető el.
        self._oszlop_jelolo_tamogatott = hasattr(wx.ListCtrl, "EnableCheckBoxes")

        # --- 2. FÜL: Állománykezelő (oszlopok a listában + mappák) ---
        panel_allomany = wx.Panel(self.notebook)
        allomany_sizer = wx.BoxSizer(wx.VERTICAL)

        self.oszlop_lista, self.oszlop_kulcsok = self._oszlop_blokk(
            panel_allomany, allomany_sizer,
            self.ELERHETO_OSZLOPOK, self.lathato_oszlopok,
            "Listában megjelenő oszlopok", DEFAULT_LATHATO_OSZLOPOK,
        )
        # Állományjegyzék alapértelmezett import/export mappája (kizárólag a
        # nyers JSON-hoz, a program egyébként az alapmappából tölt be!)
        self.txt_allomanyjegyzek = self._mappa_sor(
            panel_allomany, allomany_sizer,
            "Állományjegyzék alapértelmezett import/export mappája:",
            config.get("last_allomany_dir", ""),
            "Állományjegyzék mappájának kiválasztása")
        allomany_sizer.AddSpacer(10)
        self.txt_pdf = self._mappa_sor(
            panel_allomany, allomany_sizer,
            "Könyvadatlapok alapértelmezett mappája:",
            config.get("last_pdf_dir", ""),
            "Könyvadatlapok kimeneti mappája")
        self.txt_stat_pdf = self._mappa_sor(
            panel_allomany, allomany_sizer,
            "Statisztikai jelentések alapértelmezett mappája:",
            config.get("last_stat_pdf_dir", ""),
            "Statisztikai jelentések alapértelmezett mappája")
        self.txt_katalogus = self._mappa_sor(
            panel_allomany, allomany_sizer,
            "Katalóguslapok alapértelmezett mappája:",
            config.get("last_katalogus_dir", ""),
            "Katalóguslapok alapértelmezett mappája")

        panel_allomany.SetSizer(allomany_sizer)

        # --- 3. FÜL: Dezideráta-kezelő (oszlopok a listában + mappa) ---
        panel_dez = wx.Panel(self.notebook)
        dez_sizer = wx.BoxSizer(wx.VERTICAL)

        self.dez_oszlop_lista, self.dez_oszlop_kulcsok = self._oszlop_blokk(
            panel_dez, dez_sizer,
            self.DEZIDERATA_ELERHETO_OSZLOPOK, self.dez_lathato_oszlopok,
            "Dezideráta-listában megjelenő oszlopok", DEFAULT_DEZIDERATA_LATHATO_OSZLOPOK,
        )
        # Dezideráta-jegyzék alapértelmezett import/export mappája (kizárólag
        # a nyers JSON-hoz, a program egyébként az alapmappából tölt be!)
        self.txt_deziderata = self._mappa_sor(
            panel_dez, dez_sizer,
            "Dezideráta alapértelmezett import/export mappája:",
            config.get("last_deziderata_dir", ""),
            "Dezideráta-jegyzék alapértelmezett mappája")
        dez_sizer.AddSpacer(10)
        panel_dez.SetSizer(dez_sizer)

        # --- 4. FÜL: KönyvTárnok-kereső (sorszáma: 3) ---
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

        # --- 5. FÜL: Frissítések (sorszáma: 4) ---
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
        self.notebook.AddPage(panel_allomany, "Állománykezelő")
        self.notebook.AddPage(panel_dez, "Dezideráta-kezelő")
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

    def _oszlop_blokk(self, panel, sizer, elerheto, lathato, lista_nev, alapertelmezett):
        """Felépíti egy fül oszlopválasztóját: felirat, jelölőnégyzetes lista
        és a két gomb. A Cím oszlop mindig látszik, ezért nincs a listában
        (a Get...Oszlopok metódusok mindig hozzáfűzik). A felirat a lista
        ELŐTT jön létre, hogy a képernyőolvasó annak szövegét társítsa hozzá.
        Visszaadja a (listavezérlő, kulcsok) párt; a kulcsok a lista sorainak
        sorrendjében állnak."""
        if self._oszlop_jelolo_tamogatott:
            cimke_szoveg = ("Válassza ki a listában megjelenő oszlopokat. "
                            "A Cím oszlop mindig látszik.")
        else:
            cimke_szoveg = ("Az oszlopok kiválasztásához wxPython 4.1 vagy újabb "
                            "verzió szükséges. A jelenlegi oszlopbeállítás változatlan marad.")
        lbl = wx.StaticText(panel, label=cimke_szoveg)
        lbl.Wrap(540)
        sizer.Add(lbl, 0, wx.ALL, 10)

        lista = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_SINGLE_SEL)
        lista.SetName(lista_nev)
        lista.InsertColumn(0, "Megjelenő oszlopok", width=400)
        kulcsok = []
        if self._oszlop_jelolo_tamogatott:
            lista.EnableCheckBoxes(True)
            for kulcs, cimke in elerheto:
                if kulcs == "cim":
                    continue  # mindig látszik, nem kapcsolható
                idx = lista.InsertItem(lista.GetItemCount(), cimke)
                lista.CheckItem(idx, kulcs in lathato)
                kulcsok.append(kulcs)
            if kulcsok:
                # Kijelölt, fókuszált első sor nélkül a képernyőolvasó a
                # listára lépéskor nem mondana semmit.
                lista.Select(0)
                lista.Focus(0)
        else:
            lista.Disable()
        lista.SetMinSize((-1, 130))
        lista.Bind(wx.EVT_SIZE, self.on_oszlop_lista_atmeretezes)
        sizer.Add(lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        gombok = wx.BoxSizer(wx.HORIZONTAL)
        btn_mind = wx.Button(panel, label="Összes kijelölése")
        btn_alap = wx.Button(panel, label="Alapértelmezettek visszaállítása")
        if not self._oszlop_jelolo_tamogatott:
            btn_mind.Disable()
            btn_alap.Disable()
        btn_mind.Bind(wx.EVT_BUTTON, lambda e: self._oszlopok_mind(lista, kulcsok))
        btn_alap.Bind(wx.EVT_BUTTON, lambda e: self._oszlopok_alapertelmezett(lista, kulcsok, alapertelmezett))
        gombok.Add(btn_mind, 0, wx.RIGHT, 5)
        gombok.Add(btn_alap, 0)
        sizer.Add(gombok, 0, wx.ALL | wx.ALIGN_CENTER, 8)
        return lista, kulcsok

    def _mappa_sor(self, panel, sizer, felirat, ertek, talloz_cim):
        """Mappaválasztó sor: felirat, szövegmező és Tallózás gomb. A felirat
        a mező ELŐTT jön létre (képernyőolvasós társítás). Visszaadja a mezőt."""
        lbl = wx.StaticText(panel, label=felirat)
        txt = wx.TextCtrl(panel, value=ertek)
        btn = wx.Button(panel, label="Tallózás...")
        btn.Bind(wx.EVT_BUTTON, lambda e: self._talloz_mappa(txt, talloz_cim))
        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(txt, 1, wx.RIGHT, 5)
        sor.Add(btn, 0)
        sizer.Add(lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        sizer.Add(sor, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)
        return txt

    def _oszlopok_mind(self, lista, kulcsok):
        for idx in range(len(kulcsok)):
            lista.CheckItem(idx, True)

    def _oszlopok_alapertelmezett(self, lista, kulcsok, alapertelmezett):
        for idx, kulcs in enumerate(kulcsok):
            lista.CheckItem(idx, kulcs in alapertelmezett)

    def on_oszlop_lista_atmeretezes(self, event):
        """Az egyetlen oszlop kitölti a lista szélességét."""
        event.Skip()
        lista = event.GetEventObject()
        szelesseg = lista.GetClientSize().GetWidth()
        if szelesseg > 40:
            lista.SetColumnWidth(0, szelesseg - 4)

    def on_manual_update_check(self, event):
        # Szándékosan lokális (lusta) import: az update modul csak a kézi
        # ellenőrzés gombnál kell, és modulszintű importként körkörös importot
        # okozhatna (update -> ... -> settings). Ha az update.py sem közvetlenül,
        # sem közvetve nem importálja a settings modult, a fájl elejére áthelyezhető.
        from update import check_for_updates_async
        check_for_updates_async(parent=self, is_manual=True)

    def _kivalasztott_oszlopok(self, lista, kulcsok, jelenlegi):
        """A jelölt oszlopok kulcsai a lista sorrendjében, elöl a Cím-mel. Ha
        a jelölőnégyzetes lista nem támogatott, a kapott beállítás marad."""
        if not self._oszlop_jelolo_tamogatott:
            return list(jelenlegi)
        kijelolt = ["cim"]
        for idx, kulcs in enumerate(kulcsok):
            if lista.IsItemChecked(idx):
                kijelolt.append(kulcs)
        return kijelolt

    def GetKivalasztottOszlopok(self):
        """Az állomány listájában látható oszlopok kulcsai (a Cím mindig
        szerepel, az ELERHETO_OSZLOPOK sorrendjében)."""
        return self._kivalasztott_oszlopok(
            self.oszlop_lista, self.oszlop_kulcsok, self.lathato_oszlopok)

    def GetKivalasztottDeziderataOszlopok(self):
        """A dezideráta listájában látható oszlopok kulcsai (a Cím mindig
        szerepel, a DEZIDERATA_OSZLOP_KULCSOK sorrendjében). Mentési kulcs:
        \"deziderata_lathato_oszlopok\"."""
        return self._kivalasztott_oszlopok(
            self.dez_oszlop_lista, self.dez_oszlop_kulcsok, self.dez_lathato_oszlopok)

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
