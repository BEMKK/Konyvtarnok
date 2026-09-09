import wx
import os
import sys
import logging
from constants import APP_NAME, APP_VERSION, APP_TITLE
from dialogs import KonyvReszletekDialog, KonyvSzerkesztoDialog, NevjegyDialog, BeallitasokDialog, KeresoDialog, UjdonsagokDialog, StatisztikaDialog, FajlutkozesDialog
from help import HelpNotebookDialog
from export_manager import export_konyv_pdf, tomeges_export_pdf, get_biztonsagos_pdf_fajlnev
from import_manager import feldolgoz_es_importal
from config_manager import load_settings, save_settings
from theme_manager import apply_theme
from konyvtarnok_kereso import KonyvtarnokKeresoApp
from menu_bar import KonyvtarMenuBar
from konyv_lista import KonyvListaCtrl
from deziderata import MainFrame as Deziderata
from update import check_for_updates_async

class KonyvtarApp(wx.Frame):
    def __init__(self, adatbazis):
        super().__init__(parent=None, title=APP_TITLE, size=(1050, 600))
        self.db = adatbazis
        self.teljes_adatlista = [] 
        self.deziderata_frame = None
        self.konyvtarnok_kereso_frame = None

        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "ikon.ico")

        try:
            if os.path.exists(icon_path):
                icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO)
                self.SetIcon(icon)
            else:
                logging.warning(f"Az ikon nem található ezen az útvonalon: {icon_path}")
        except Exception as e:
            logging.error(f"Nem sikerült betölteni az alkalmazás ikonját: {e}")

        menusor = KonyvtarMenuBar()
        self.SetMenuBar(menusor)

        self.statusbar = self.CreateStatusBar()
        
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        gomb_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        bmp_uj = wx.ArtProvider.GetBitmap(wx.ART_NEW, wx.ART_BUTTON, wx.Size(16, 16))
        bmp_torol = wx.ArtProvider.GetBitmap(wx.ART_DELETE, wx.ART_BUTTON, wx.Size(16, 16))

        gomb_uj = wx.Button(panel, label="Új könyv")
        gomb_uj.SetBitmap(bmp_uj)

        gomb_szerk = wx.Button(panel, label="Kijelölt könyv szerkesztése")
        gomb_torol = wx.Button(panel, label="Kijelöltek törlése")
        gomb_torol.SetBitmap(bmp_torol)

        kereso_cimke = wx.StaticText(panel, label="Keresés:")
        self.kereso_ctrl = wx.SearchCtrl(panel, size=(220, -1))
        self.kereso_ctrl.SetDescriptiveText("Keresés az állományban")
        self.kereso_ctrl.ShowSearchButton(True)
        self.kereso_ctrl.ShowCancelButton(True)

        bmp_refresh = wx.ArtProvider.GetBitmap(wx.ART_UNDO, wx.ART_BUTTON, (16, 16))
        self.gomb_szuro_torles = wx.Button(panel, label="Szűrés törlése")
        self.gomb_szuro_torles.SetBitmap(bmp_refresh)
        self.gomb_szuro_torles.Disable()

        gomb_sizer.Add(gomb_uj, 0, wx.RIGHT, 15)
        gomb_sizer.Add(gomb_szerk, 0, wx.RIGHT, 15)
        gomb_sizer.Add(gomb_torol, 0, wx.RIGHT, 15)
        gomb_sizer.Add(kereso_cimke, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        gomb_sizer.Add(self.kereso_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
        
        gomb_sizer.AddStretchSpacer(1) 
        
        self.szuro_kijelzo = wx.StaticText(panel, label="")
        font = self.szuro_kijelzo.GetFont()
        font.MakeItalic()
        self.szuro_kijelzo.SetFont(font)

        gomb_sizer.Add(self.szuro_kijelzo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
        gomb_sizer.Add(self.gomb_szuro_torles, 0, wx.RIGHT, 10)
        
        sizer.Add(gomb_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.TOP, 15)

        # LISTA LÉTREHOZÁSA ÉS SIZERHEZ ADÁSA (Visszaállítva!)
        config = load_settings()
        self.lista = KonyvListaCtrl(panel, self.db)
        if "lathato_oszlopok" in config and hasattr(self.lista, 'SetAktivOszlopok'):
            self.lista.SetAktivOszlopok(config["lathato_oszlopok"])
            
        alap_rendezes = config.get("alapertelmezett_rendezes", "cim")
        if hasattr(self.lista, 'Rendezes'):
            self.lista.Rendezes(alap_rendezes)

        sizer.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        panel.SetSizer(sizer)

        # TÉMA ALKALMAZÁSA
        current_theme = config.get("tema", "vilagos")
        apply_theme(self, current_theme)

        # GYORSBILLENTYŰK (Visszaállítva!)
        id_mindent_kijelol = wx.NewIdRef()
        id_torles = wx.NewIdRef()
        id_kereso_fokusz = wx.NewIdRef()

        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('A'), id_mindent_kijelol),
            (wx.ACCEL_NORMAL, wx.WXK_DELETE, id_torles),
            (wx.ACCEL_CTRL, ord('F'), id_kereso_fokusz),
        ])
        self.SetAcceleratorTable(accel_tbl)

        # MENÜ ESEMÉNYEK (Visszaállítva!)
        self.Bind(wx.EVT_MENU, self.OnUjKonyv, menusor.uj_konyv)
        self.Bind(wx.EVT_MENU, self.OnKilepes, menusor.kilepes)
        self.Bind(wx.EVT_MENU, lambda e: self.MegnyitReszletek(szerkesztesre=True), menusor.szerk)
        self.Bind(wx.EVT_MENU, self.OnKonyvTorles, menusor.torles)
        self.Bind(wx.EVT_MENU, self.OnImportalas, menusor.import_elem)
        self.Bind(wx.EVT_MENU, self.OnExportalas, menusor.export_elem)
        self.Bind(wx.EVT_MENU, self.OnJsonImport, menusor.json_import)
        self.Bind(wx.EVT_MENU, self.OnJsonExport, menusor.json_export)
        self.Bind(wx.EVT_MENU, lambda e: self.OnRendezes("cim"), menusor.cim)
        self.Bind(wx.EVT_MENU, lambda e: self.OnRendezes("szerzo"), menusor.szerzo)
        self.Bind(wx.EVT_MENU, lambda e: self.OnRendezes("kiado"), menusor.kiado)
        self.Bind(wx.EVT_MENU, lambda e: self.OnRendezes("ev"), menusor.ev)
        self.Bind(wx.EVT_MENU, lambda e: self.OnRendezes("oldalszam"), menusor.oldalszam)
        self.Bind(wx.EVT_MENU, lambda e: self.OnRendezes("meretek"), menusor.meretek)
        self.Bind(wx.EVT_MENU, lambda e: self.OnRendezes("bekerult"), menusor.bekerult)
        self.Bind(wx.EVT_MENU, self.on_deziderata, menusor.deziderata)
        self.Bind(wx.EVT_MENU, self.on_kereses_dialógus_megnyitasa, menusor.find)
        self.Bind(wx.EVT_MENU, self.on_konyvtarnok_kereso, menusor.konyvtarnok_kereso_item)
        self.Bind(wx.EVT_MENU, self.OnStatisztika, menusor.statisztika)
        self.Bind(wx.EVT_MENU, self.OnBeallitasok, menusor.set)
        self.Bind(wx.EVT_MENU, self.on_open_help, menusor.help)
        self.Bind(wx.EVT_MENU, self.OnAbout, id=wx.ID_ABOUT)
        self.Bind(wx.EVT_MENU, self.OnUjdonsagok, menusor.Ujdonsagok)
        self.Bind(wx.EVT_MENU, self.OnFrissites, menusor.frissites)

        self.Bind(wx.EVT_MENU, lambda e: self.kereso_ctrl.SetFocus(), id=id_kereso_fokusz)

        # GOMB ÉS KERESŐ ESEMÉNYEK (Visszaállítva!)
        gomb_uj.Bind(wx.EVT_BUTTON, self.OnUjKonyv)
        gomb_szerk.Bind(wx.EVT_BUTTON, lambda e: self.MegnyitReszletek(szerkesztesre=True))
        gomb_torol.Bind(wx.EVT_BUTTON, self.OnKonyvTorles)
        self.gomb_szuro_torles.Bind(wx.EVT_BUTTON, lambda e: self.szuro_torlese())

        self.kereso_ctrl.Bind(wx.EVT_TEXT, self.OnKeresoValtozas)
        self.kereso_ctrl.Bind(wx.EVT_SEARCH, self.OnKeresoEnter)
        self.kereso_ctrl.Bind(wx.EVT_TEXT_ENTER, self.OnKeresoEnter)

        # LISTA ESEMÉNYEK (Visszaállítva!)
        self.lista.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnListaJobbKlikk)
        self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnListaDuplaKlikk)
        self.lista.Bind(wx.EVT_KEY_DOWN, self.OnListaEnter)

        self.Bind(wx.EVT_MENU, self.OnMindentKijelol, id=id_mindent_kijelol)
        self.Bind(wx.EVT_MENU, self.OnKonyvTorles, id=id_torles)

        # FÓKUSZ ÉS KIJELÖLÉS (Visszaállítva!)
        self.lista.SetFocus()
        if self.lista.GetItemCount() > 0:
            self.lista.Select(0)
            
        self.FrissitStatusBar()
        self.Show()
        wx.CallAfter(check_for_updates_async, parent=self, is_manual=False)

    # --- ESEMÉNYKEZELŐK ---

    def OnKeresoValtozas(self, event):
        keresett_szoveg = self.kereso_ctrl.GetValue().strip()
        if not keresett_szoveg:
            if self.gomb_szuro_torles.IsEnabled():
                self.szuro_torlese(torolje_a_mezoet=False)
        else:
            self.kereses_az_allomanyban(keresett_szoveg, pontos_egyezes=False)

    def OnKeresoEnter(self, event):
        self.lista.SetFocus()
        if self.lista.GetItemCount() > 0 and not self.lista.GetKijeloltIndexek():
            self.lista.Select(0)

    def OnListaEnter(self, event):
        key_code = event.GetKeyCode()
        if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.MegnyitReszletek(szerkesztesre=False)
        elif key_code == wx.WXK_SPACE:
            if hasattr(self.lista, "FeldolgozKarakter"):
                self.lista.FeldolgozKarakter(' ')
        elif key_code == wx.WXK_WINDOWS_MENU or (key_code == wx.WXK_F10 and event.ShiftDown()):
            self._MegjelenitPopUpMenut()
        else:
            event.Skip()

    def FrissitStatusBar(self):
        db_szam = self.lista.GetItemCount()
        self.statusbar.SetStatusText(f"Állományban lévő kötetek száma: {db_szam}.")

    def MegnyitReszletek(self, szerkesztesre=False):
        indexek = self.lista.GetKijeloltIndexek()
        if not indexek:
            wx.MessageBox("Kérjük, válasszon ki egy könyvet a listából!", "Nincs kijelölés", wx.OK | wx.ICON_WARNING)
            return
        idx = indexek[0]

        konyv_adatok = self.lista.GetKonyvByRowIndex(idx)
        if not konyv_adatok:
            return
        szerkesztett_id = konyv_adatok.get("id")
        if szerkesztesre:
            dlg = KonyvSzerkesztoDialog(self, konyv_adatok=konyv_adatok, db=self.db, uj_konyv=False)
        else:
            dlg = KonyvReszletekDialog(self, konyv_adatok=konyv_adatok, db=self.db)

        if dlg.ShowModal() == wx.ID_OK:
            self.teljes_adatlista = []
            if self.gomb_szuro_torles.IsEnabled() and self.szuro_kijelzo.GetLabel():
                label_text = self.szuro_kijelzo.GetLabel()
                if "'" in label_text:
                    keresett = label_text.split("'")[1]
                    self.kereses_az_allomanyban(keresett)
            else:
                self.lista.FeltoltLista(self.db.konyvek)
            self.FrissitStatusBar()

            uj_idx = -1
            if szerkesztett_id is not None:
                for k, v in self.lista.sor_id_terkep.items():
                    if v == szerkesztett_id:
                        uj_idx = k
                        break
            if uj_idx == -1 and 0 <= idx < self.lista.GetItemCount():
                uj_idx = idx

            if uj_idx != -1 and self.lista.GetItemCount() > 0:
                self.lista.Select(uj_idx)
                self.lista.Focus(uj_idx)
                self.lista.EnsureVisible(uj_idx)

        dlg.Destroy()
        self.lista.SetFocus()

    def OnKonyvTorles(self, event):
        indexek = self.lista.GetKijeloltIndexek()
        if not indexek:
            wx.MessageBox("Kérjük, válasszon ki legalább egy könyvet a törléshez!", "Nincs kijelölés", wx.OK | wx.ICON_WARNING)
            return

        darab = len(indexek)
        uzenet = f"Biztosan törölni szeretné a(z) '{self.lista.GetItemText(indexek[0])}' című könyvet?" if darab == 1 else f"Biztosan törölni szeretné a kijelölt {darab} db könyvet?"

        kerdes = wx.MessageDialog(self, uzenet, "Megerősítés", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        
        if kerdes.ShowModal() == wx.ID_YES:
            cel_index = min(indexek)

            torlendo_id_k = []
            for idx in indexek:
                konyv = self.lista.GetKonyvByRowIndex(idx)
                if konyv and konyv.get("id"):
                    torlendo_id_k.append(konyv.get("id"))
                elif konyv:
                    cim = konyv.get("cim")
                    if cim:
                        self.db.konyv_torlese(cim)
            for konyv_id in torlendo_id_k:
                self.db.konyv_torlese_by_id(konyv_id)

            self.teljes_adatlista = []
            self.lista.FeltoltLista()
            self.FrissitStatusBar()
            
            osszesen = self.lista.GetItemCount()
            if osszesen > 0:
                uj_idx = min(cel_index, osszesen - 1)
                self.lista.Select(uj_idx)
                self.lista.Focus(uj_idx)
                self.lista.EnsureVisible(uj_idx)

            self.lista.SetFocus()

        kerdes.Destroy()

    def OnMindentKijelol(self, event):
        self.lista.SetFocus()
        for i in range(self.lista.GetItemCount()):
            self.lista.Select(i, True)

    def OnListaDuplaKlikk(self, event):
        self.MegnyitReszletek(szerkesztesre=False)

    def _MegjelenitPopUpMenut(self):
        indexek = self.lista.GetKijeloltIndexek()
        if not indexek:
            return

        popup_menu = wx.Menu()
        megtekint_item = popup_menu.Append(wx.ID_ANY, "Könyvadatlap megtekintése")
        szerkeszt_item = popup_menu.Append(wx.ID_ANY, "Könyv szerkesztése")
        popup_menu.AppendSeparator()
        torol_item = popup_menu.Append(wx.ID_ANY, f"Kijelölt könyvek törlése ({len(indexek)} db)")

        self.Bind(wx.EVT_MENU, lambda e: self.MegnyitReszletek(szerkesztesre=False), megtekint_item)
        self.Bind(wx.EVT_MENU, lambda e: self.MegnyitReszletek(szerkesztesre=True), szerkeszt_item)
        self.Bind(wx.EVT_MENU, self.OnKonyvTorles, torol_item)

        self.PopupMenu(popup_menu)
        popup_menu.Destroy()

    def OnListaJobbKlikk(self, event):
        idx = event.GetIndex()
        if idx not in self.lista.GetKijeloltIndexek():
            self.lista.Select(idx)
        self._MegjelenitPopUpMenut()

    def OnUjKonyv(self, event):
        ures_adatok = {k: "" for k in ["cim", "alcim", "szerzo", "egyeb_szemelyek", "kiado", "hely", "ev", "oldalszam", "meretek", "kotes", "rovid_cim", "forras", "status", "rovid_leiras"]}
        dlg = KonyvSzerkesztoDialog(self, ures_adatok, self.db, uj_konyv=True)
    
        res = dlg.ShowModal()
    
        if res == wx.ID_OK:
            friss_adatok = {
                kulcs: ctrl.GetValue().strip()
                for kulcs, ctrl in dlg.controls.items()
            }
            dlg.Destroy()

            self.teljes_adatlista = []
            self.lista.FeltoltLista()
            self.FrissitStatusBar()

            uj_cim = friss_adatok.get("cim")
            uj_idx = -1

            if uj_cim:
                for idx in range(self.lista.GetItemCount() - 1, -1, -1):
                    konyv = self.lista.GetKonyvByRowIndex(idx)
                    if konyv and konyv.get("cim") == uj_cim:
                        uj_idx = idx
                        break

            if uj_idx != -1:
                def kijeloles_beallitasa(target_idx):
                    for selected_idx in self.lista.GetKijeloltIndexek():
                        self.lista.Select(selected_idx, False)

                    self.lista.SetFocus()
                    self.lista.EnsureVisible(target_idx)
                    self.lista.Focus(target_idx)
                    self.lista.Select(target_idx, True)

                wx.CallAfter(kijeloles_beallitasa, uj_idx)
            else:
                self.lista.SetFocus()
        else:
            dlg.Destroy()
            self.lista.SetFocus()

    def OnKilepes(self, event):
        self.Close()

    def kezel_fajlutkozes(self, fajlnev):
        dlg = FajlutkozesDialog(self, fajlnev)
        valasz = dlg.ShowModal()
        dlg.Destroy()

        if valasz == wx.ID_NO:
            return "KIHAGYAS"
        elif valasz == wx.ID_CANCEL:
            return "MINDET_FELULIR"
        return "FELULIRAS"

    def OnExportalas(self, event):
        indexek = self.lista.GetKijeloltIndexek()
        if not indexek:
            wx.MessageBox("Kérjük, válasszon ki legalább egy könyvet az exportáláshoz!", "Nincs kijelölés", wx.OK | wx.ICON_WARNING)
            return

        config = load_settings()
        default_dir = config.get("last_pdf_dir", "")

        if len(indexek) == 1:
            konyv_adatok = self.lista.GetKonyvByRowIndex(indexek[0])
            if not konyv_adatok:
                return

            alapértelmezett_fajlnev = get_biztonsagos_pdf_fajlnev(konyv_adatok)

            ment_dlg = wx.FileDialog(
                self, 
                "Könyvadatlap exportálása", 
                defaultDir=default_dir, 
                defaultFile=alapértelmezett_fajlnev, 
                wildcard="PDF fájl (*.pdf)|*.pdf", 
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
            )
            if ment_dlg.ShowModal() != wx.ID_OK:
                ment_dlg.Destroy()
                return
            
            fajlnev = ment_dlg.GetPath()
            config["last_pdf_dir"] = os.path.dirname(fajlnev)
            save_settings(config)
            ment_dlg.Destroy()

            try:
                export_konyv_pdf(konyv_adatok, fajlnev)
                wx.MessageBox("Exportálás sikeres!", "Exportálás", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                logging.error(f"Hiba történt exportálás közben: {e}")
                wx.MessageBox(f"Hiba történt exportálás közben:\n{e}", "Hiba", wx.OK | wx.ICON_ERROR)

        else:
            # ITT TÖRTÉNT A JAVÍTÁS: defaultPath=default_dir beállítása
            mappa_dlg = wx.DirDialog(self, "Válassza ki a mappát...", defaultPath=default_dir, style=wx.DD_DEFAULT_STYLE)
            if mappa_dlg.ShowModal() != wx.ID_OK:
                mappa_dlg.Destroy()
                return
            
            mentesi_utvonal = mappa_dlg.GetPath()
            config["last_pdf_dir"] = mentesi_utvonal
            save_settings(config)
            mappa_dlg.Destroy()

            konyvek_listaja = [
                self.lista.GetKonyvByRowIndex(idx) 
                for idx in indexek 
                if self.lista.GetKonyvByRowIndex(idx) is not None
            ]            

            sikeres = tomeges_export_pdf(
                konyvek_listaja, 
                mentesi_utvonal, 
                fajl_letezik_callback=self.kezel_fajlutkozes
            )
            
            wx.MessageBox(
                f"Tömeges exportálás kész!\nSikeresen mentve: {sikeres}/{len(indexek)} db PDF.", 
                "Exportálás eredménye", 
                wx.OK | wx.ICON_INFORMATION
            )

    def OnJsonImport(self, event):
        config = load_settings()
        default_dir = config.get("last_json_dir", "")

        megnyit_dlg = wx.FileDialog(
            self, "Állományjegyzék megnyitása (JSON)", 
            defaultDir=default_dir,
            wildcard="JSON fájl (*.json)|*.json", 
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )
        if megnyit_dlg.ShowModal() == wx.ID_OK:
            kivalasztott_utvonal = megnyit_dlg.GetPath()
            config["last_json_dir"] = os.path.dirname(kivalasztott_utvonal)
            save_settings(config)
        
            try:
                if hasattr(self.db, 'load_from_json') and self.db.load_from_json(kivalasztott_utvonal):
                    self.teljes_adatlista = []
                    self.lista.FeltoltLista()
                    self.FrissitStatusBar()
                    wx.MessageBox("Az adatok sikeresen beolvasásra kerültek!", "Sikeres import", wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox("Hiba történt a fájl feldolgozása során.", "Hiba", wx.OK | wx.ICON_ERROR)
            except Exception as e:
                logging.error(f"Hiba történt az importálás közben: {e}")
                wx.MessageBox(f"Hiba történt az importálás során:\n{e}", "Hiba", wx.OK | wx.ICON_ERROR)
        megnyit_dlg.Destroy()

    def OnJsonExport(self, event):
        config = load_settings()
        default_dir = config.get("last_json_dir", "")

        ment_dlg = wx.FileDialog(
            self, "Állományjegyzék mentése titkosítás nélkül", 
            defaultDir=default_dir,
            defaultFile="allomanyjegyzek.json", 
            wildcard="JSON fájl (*.json)|*.json", 
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )
        if ment_dlg.ShowModal() == wx.ID_OK:
            kivalasztott_utvonal = ment_dlg.GetPath()
            config["last_json_dir"] = os.path.dirname(kivalasztott_utvonal)
            save_settings(config)

            try:
                if hasattr(self.db, 'save_to_json'):
                    self.db.save_to_json(kivalasztott_utvonal)
                    wx.MessageBox("A teljes adatbázis kimentve!", "Sikeres mentés", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Hiba történt a mentés során:\n{e}", "Hiba", wx.OK | wx.ICON_ERROR)
        ment_dlg.Destroy()

    def OnImportalas(self, event):
        config = load_settings()
        default_dir = config.get("last_pdf_dir", "")

        megnyit_dlg = wx.FileDialog(
            self, 
            "Könyvadatlap(ok) importálása", 
            defaultDir=default_dir,
            wildcard="PDF fájl (*.pdf)|*.pdf", 
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE
        )
        if megnyit_dlg.ShowModal() != wx.ID_OK:
            megnyit_dlg.Destroy()
            return
        
        fajl_utvonalak = megnyit_dlg.GetPaths()
        if fajl_utvonalak:
            config["last_pdf_dir"] = os.path.dirname(fajl_utvonalak[0])
            save_settings(config)
        megnyit_dlg.Destroy()
        try:
            sikeres, hibas, duplikalt, hozzaadott_cimek = feldolgoz_es_importal(fajl_utvonalak, self.db)

            self.teljes_adatlista = []  
            self.lista.FeltoltLista()
            self.FrissitStatusBar()
            
            elso_uj_idx = -1
            if hozzaadott_cimek:
                elso_cim = hozzaadott_cimek[0]
                for idx, konyv in enumerate(self.lista.jelenlegi_adatok):
                    if konyv and konyv.get("cim") == elso_cim:
                        elso_uj_idx = idx
                        break

            if elso_uj_idx != -1:
                def kijeloles_beallitasa(target_idx):
                    for selected_idx in self.lista.GetKijeloltIndexek():
                        self.lista.Select(selected_idx, False)

                    self.lista.SetFocus()
                    self.lista.EnsureVisible(target_idx)
                    self.lista.Focus(target_idx)
                    self.lista.Select(target_idx, True)

                wx.CallAfter(kijeloles_beallitasa, elso_uj_idx)
            else:
                self.lista.SetFocus()

            if sikeres > 0:
                uzenet = f"Az importálás sikeresen megtörtént!\n\n"
                uzenet += f"• Hozzáadva: {sikeres} db új könyv.\n"
                
                if duplikalt > 0 or hibas > 0:
                    uzenet += "\nMegjegyzés:\n"
                    if duplikalt > 0:
                        uzenet += f"• {duplikalt} db könyv már állományban van, ezért nem lett újra felvéve.\n"
                    if hibas > 0:
                        uzenet += f"• {hibas} db fájlból nem sikerült kiolvasni a címet."
                
                wx.MessageBox(uzenet, "Importálás sikeres", wx.OK | wx.ICON_INFORMATION)

            elif duplikalt > 0:
                wx.MessageBox(
                    f"Az importálás sikertelen volt, mert a kiválasztott könyv(ek) ({duplikalt} db) már szerepel(nek) az állományban!", 
                    "Importálás sikertelen", 
                    wx.OK | wx.ICON_WARNING
                )

            else:
                wx.MessageBox(
                    "Az importálás sikertelen volt!\nA kiválasztott fájl(ok)ból nem sikerült érvényes könyvadatokat kinyerni.", 
                    "Importálás sikertelen", 
                    wx.OK | wx.ICON_ERROR
                )

        except Exception as e:
            wx.MessageBox(f"Hiba történt: {e}", "Hiba", wx.OK | wx.ICON_ERROR)

    def on_kereses_dialógus_megnyitasa(self, event):
        dlg = KeresoDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            keresett_szoveg = dlg.get_search_text()
            pontos_egyezes = dlg.is_exact_match()
            if keresett_szoveg:
                self.kereso_ctrl.SetValue(keresett_szoveg)
                self.kereses_az_allomanyban(keresett_szoveg, pontos_egyezes)
        dlg.Destroy()

    def kereses_az_allomanyban(self, keresett_szoveg, pontos_egyezes=False):
        keresett = keresett_szoveg.lower().strip()
        
        if not self.teljes_adatlista:
            if hasattr(self.db, 'konyvek'):
                self.teljes_adatlista = self.db.konyvek
            elif hasattr(self.db, 'get_osszes_konyv'):
                self.teljes_adatlista = self.db.get_osszes_konyv()

        leszurt_adatok = []
        for konyv in self.teljes_adatlista:
            if isinstance(konyv, dict):
                ertekek = konyv.values()
            elif isinstance(konyv, (list, tuple)):
                ertekek = konyv
            else:
                ertekek = vars(konyv).values() if hasattr(konyv, '__dict__') else []

            talalat = False
            for ertek in ertekek:
                if not ertek:
                    continue
                ertek_str = str(ertek).lower().strip()

                if pontos_egyezes:
                    if keresett == ertek_str:
                        talalat = True
                        break
                else:
                    if keresett in ertek_str:
                        talalat = True
                        break

            if talalat:
                leszurt_adatok.append(konyv)

        if not leszurt_adatok:
            self.lista.FeltoltLista([])
            self.FrissitStatusBar()
            self.szuro_kijelzo.SetLabel(f"Nincs találat: '{keresett_szoveg}'")
            self.gomb_szuro_torles.Enable()
            self.Layout()
            return

        self.lista.FeltoltLista(leszurt_adatok)
        talalatok_szama = len(leszurt_adatok)
        self.FrissitStatusBar()
        self.szuro_kijelzo.SetLabel(f"Találatok: '{keresett_szoveg}' ({talalatok_szama} találat)")
        self.gomb_szuro_torles.Enable()
        self.szuro_kijelzo.GetParent().Layout()  
        self.Layout()

    def szuro_torlese(self, torolje_a_mezoet=True):
        if hasattr(self.lista, 'FeltoltLista'):
            self.lista.FeltoltLista()
        else:
            self.lista.DeleteAllItems()

        self.teljes_adatlista = []
        self.FrissitStatusBar()
        self.szuro_kijelzo.SetLabel("")
        self.gomb_szuro_torles.Disable()
        if torolje_a_mezoet and hasattr(self, 'kereso_ctrl') and self.kereso_ctrl.GetValue():
            self.kereso_ctrl.SetValue("")
        self.Layout()

    def on_konyvtarnok_kereso(self, event):
        if self.konyvtarnok_kereso_frame is None:
            self.konyvtarnok_kereso_frame = KonyvtarnokKeresoApp(parent=self)
            self.konyvtarnok_kereso_frame.Bind(wx.EVT_CLOSE, self.on_konyvtarnok_kereso_close)
        else:
            self.konyvtarnok_kereso_frame.Raise()

    def on_konyvtarnok_kereso_close(self, event):
        self.konyvtarnok_kereso_frame = None
        event.Skip()

    def OnBeallitasok(self, event):
        config = load_settings()
        dlg = BeallitasokDialog(self, lathato_oszlopok=self.lista.aktiv_oszlopok, aktiv_tema=config.get("tema", "vilagos"))
        if dlg.ShowModal() == wx.ID_OK:
            uj_oszlopok = dlg.GetKivalasztottOszlopok()
            uj_tema = dlg.GetKivalasztottTema()
            uj_rendezes = dlg.GetKivalasztottRendezes()
            
            self.lista.SetAktivOszlopok(uj_oszlopok)
            
            config["lathato_oszlopok"] = uj_oszlopok
            config["tema"] = uj_tema
            config["alapertelmezett_rendezes"] = uj_rendezes
            config["last_pdf_dir"] = dlg.GetKivalasztottPdfDir()
            config["last_stat_pdf_dir"] = dlg.GetKivalasztottStatPdfDir()
            config["last_json_dir"] = dlg.GetKivalasztottJsonDir()
            save_settings(config)
            
            if hasattr(self.lista, 'Rendezes'):
                self.lista.Rendezes(uj_rendezes)

            apply_theme(self, uj_tema)
            if self.deziderata_frame:
                apply_theme(self.deziderata_frame, uj_tema)

            wx.MessageBox("A beállítások sikeresen mentésre kerültek!", "Beállítások", wx.OK | wx.ICON_INFORMATION)
        dlg.Destroy()

    def OnAbout(self, event):
        dlg = NevjegyDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def OnRendezes(self, mezo_kulcs):
        self.statusbar.SetStatusText(f"Rendezés {mezo_kulcs} szerint...")
        if hasattr(self.lista, 'Rendezes'):
            self.lista.Rendezes(mezo_kulcs)
        elif hasattr(self.lista, 'FeltoltLista'):
            self.lista.FeltoltLista()
        self.FrissitStatusBar()

    def on_deziderata(self, event):
        if self.deziderata_frame is None:
            self.deziderata_frame = Deziderata(parent=self, cipher=self.db.cipher)
            self.deziderata_frame.Bind(wx.EVT_CLOSE, self.on_deziderata_close)
        else:
            self.deziderata_frame.Raise()

    def on_deziderata_close(self, event):
        self.deziderata_frame = None
        event.Skip()

    def OnStatisztika(self, event):
        dlg = StatisztikaDialog(self, self.db, meglevo_rendezes=self.lista.rendezes_kulcs)
        if dlg.ShowModal() == wx.ID_OK:
            kulcs = dlg.get_aktualis_kulcs()
            keresett_ertek = dlg.combo_ertek.GetValue().strip()
            megjelenitett_nev = dict(dlg.statisztikai_mezok).get(kulcs, kulcs)

            # Lekérjük a választott rendezési kulcsot (évszázad/évtized esetén automatikusan "ev")
            uj_rendezes = dlg.get_kivalasztott_rendezesi_kulcs()
    
            if not self.teljes_adatlista:
                if hasattr(self.db, 'konyvek'):
                    self.teljes_adatlista = self.db.konyvek
                elif hasattr(self.db, 'get_osszes_konyv'):
                    self.teljes_adatlista = self.db.get_osszes_konyv()

            leszurt_adatok = []
            is_hianyzo = keresett_ertek == "Nincs kitöltve"
            forras_kulcs = "ev" if kulcs in ["evszazad", "evtized"] else kulcs

            for konyv in self.teljes_adatlista:
                val = dlg.ertek_feldolgoz(kulcs, konyv.get(forras_kulcs, ""))
                if is_hianyzo:
                    if not val:
                        leszurt_adatok.append(konyv)
                else:
                    if val.lower() == keresett_ertek.lower():
                        leszurt_adatok.append(konyv)

            if leszurt_adatok:
                # A kiválasztott/meghatározott rendezést érvényesítjük a listán
                self.lista.rendezes_kulcs = uj_rendezes
                self.lista.Rendezes(uj_rendezes)
                self.lista.FeltoltLista(leszurt_adatok)
        
                talalatok_szama = len(leszurt_adatok)
                self.FrissitStatusBar()
        
                label_val = "Hiányzó adatok" if is_hianyzo else f"'{keresett_ertek}'"
                self.szuro_kijelzo.SetLabel(f"Statisztika szűrés: {megjelenitett_nev} = {label_val} ({talalatok_szama} találat)")
                self.gomb_szuro_torles.Enable()
                self.szuro_kijelzo.GetParent().Layout()
                self.Layout()
            else:
                wx.MessageBox(f"Nincs találat a(z) '{keresett_ertek}' értékre.", "Szűrés", wx.OK | wx.ICON_INFORMATION, self)
        dlg.Destroy()

    def OnUjdonsagok(self, event):
        dlg = UjdonsagokDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def select_and_focus(self, index):
        if 0 <= index < self.lista.GetItemCount():
            self.lista.Select(index)
            self.lista.Focus(index)
            self.lista.EnsureVisible(index)
        self.lista.SetFocus()

    def OnFrissites(self, event):
        check_for_updates_async(parent=self, is_manual=True)

    def on_open_help(self, event):
        """Ez a metódus fut le a Súgó menüpontra vagy az F1-re kattintva."""
        dlg = HelpNotebookDialog(self)
        dlg.ShowModal()
        dlg.Destroy()
