import wx
from config_manager import load_settings
from constants import DEFAULT_LATHATO_OSZLOPOK
from konyv_lista import KonyvListaCtrl
from theme_manager import get_theme_names, apply_theme, apply_theme_from_settings

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

    # A jelölőnégyzetek felirata mostantól a KonyvListaCtrl.OSZLOP_DEFINICIOK
    # (konyv_lista.py) szótárból származik, ami a lista tényleges
    # oszlopfejléceit is meghatározza. Korábban ez a lista itt külön, kézzel
    # volt megismételve, aminek következtében néhány felirat (pl. "Méretek"
    # a lista tényleges "Méret" fejléce helyett, vagy "Bekerülés" a
    # "Bekerült" helyett) eltért a könyvlistában ténylegesen látott
    # oszlopnévtől.
    ELERHETO_OSZLOPOK = [
        (kulcs, adat[0]) for kulcs, adat in KonyvListaCtrl.OSZLOP_DEFINICIOK.items()
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

        # --- 4. FÜL: Frissítések ---
        panel_frissites = wx.Panel(self.notebook)
        frissites_sizer = wx.BoxSizer(wx.VERTICAL)

        self.cb_auto_update = wx.CheckBox(panel_frissites, label="Frissítések automatikus ellenőrzése")
        self.cb_auto_update.SetValue(config.get("auto_update_check", True))

        lbl_freq = wx.StaticText(panel_frissites, label="Ellenőrzés gyakorisága:")
        self.FREKVENCIA_OPCIOK = [
            ("startup", "Minden indításkor"),
            ("daily", "Naponta"),
            ("weekly", "Hetente"),
            ("monthly", "Havonta")
        ]
        self.choice_freq = wx.Choice(panel_frissites, choices=[nev for _, nev in self.FREKVENCIA_OPCIOK])
        
        akt_freq = config.get("update_frequency", "startup")
        freq_kulcsok = [k for k, _ in self.FREKVENCIA_OPCIOK]
        self.choice_freq.SetSelection(freq_kulcsok.index(akt_freq) if akt_freq in freq_kulcsok else 0)

        # Ha a checkbox nincs bepipálva, a választó legyen inaktív
        self.choice_freq.Enable(self.cb_auto_update.IsChecked())
        self.cb_auto_update.Bind(wx.EVT_CHECKBOX, lambda e: self.choice_freq.Enable(self.cb_auto_update.IsChecked()))

        btn_manual_check = wx.Button(panel_frissites, label="Frissítések keresése most...")
        btn_manual_check.Bind(wx.EVT_BUTTON, self.on_manual_update_check)

        frissites_sizer.Add(self.cb_auto_update, 0, wx.ALL, 10)
        frissites_sizer.Add(lbl_freq, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        frissites_sizer.Add(self.choice_freq, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        frissites_sizer.Add(btn_manual_check, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        panel_frissites.SetSizer(frissites_sizer)

        # Fülek hozzáadása a Notebook-hoz
        self.notebook.AddPage(panel_tema, "Téma és rendezés")
        self.notebook.AddPage(panel_oszlopok, "Megjelenítendő oszlopok")
        self.notebook.AddPage(panel_mappak, "Mappák és elérési utak")
        self.notebook.AddPage(panel_frissites, "Frissítések")

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
        for kulcs, cb in self.jelolo_negyzetek.items():
            cb.SetValue(kulcs in DEFAULT_LATHATO_OSZLOPOK)

    def on_manual_update_check(self, event):
        from update import check_for_updates_async
        check_for_updates_async(parent=self, is_manual=True)

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

    def GetAutoUpdateCheck(self):
        return self.cb_auto_update.IsChecked()

    def GetUpdateFrequency(self):
        idx = self.choice_freq.GetSelection()
        freq_kulcsok = [k for k, _ in self.FREKVENCIA_OPCIOK]
        return freq_kulcsok[idx] if 0 <= idx < len(freq_kulcsok) else "startup"
