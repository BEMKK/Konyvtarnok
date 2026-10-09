import wx
import os
import sys
import re
import logging
from constants import APP_TITLE
from dialogs import NevjegyDialog, UjdonsagokDialog, FajlutkozesDialog, exportal_egy_konyv
from kereso import KeresoDialog
from settings import BeallitasokDialog
from konyvdialogs import KonyvReszletekDialog, KonyvSzerkesztoDialog
from statisztika import StatisztikaDialog
from help import HelpNotebookDialog
from export_manager import tomeges_export_pdf, katalogus_mentese
from config_manager import load_settings, save_settings
from theme_manager import apply_theme
from konyvtarnok_kereso import KonyvtarnokKeresoApp
from menu_bar import MenuBar
from konyv_lista import KonyvListaCtrl
from deziderata import Deziderata, DeziderataFajlTarolo
from data_manager import additiv_lista_import, szoveg_szuro_egyezik, szuresi_talalatok, MentesiHiba
from utils import statisztikai_szures, masolas_vagolapra_szoveg
from update import check_for_updates_async
from undo_manager import frissit_undo_menu, szovegmezo_visszavonas


class Konyvtarnok(wx.Frame):
    def __init__(self, adatbazis):
        super().__init__(parent=None, title=APP_TITLE, size=(1050, 600))
        self.db = adatbazis
        self.teljes_adatlista = [] 
        # Az aktuálisan megjelenített (szűrt) könyvlista referenciája.
        # None, ha nincs aktív szűrés/keresés. Ugyanazokra a db.konyvek
        # elemekre mutat, ezért szerkesztés után is naprakész marad,
        # anélkül hogy a szűrés feltételét bármiből ki kellene találni.
        self.aktiv_szurt_lista = None
        # Az aktív szűrés feltételét visszaadó függvény (konyv -> bool),
        # hogy egy újonnan felvett könyvről el tudjuk dönteni, illeszkedik-e
        # rá az éppen aktív szűrésre. None, ha nincs aktív szűrés.
        self.aktiv_szuro_predikatum = None
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

        menusor = MenuBar()
        self.menusor = menusor
        self.SetMenuBar(menusor)

        self.statusbar = self.CreateStatusBar()
        
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        gomb_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        bmp_uj = wx.ArtProvider.GetBitmap(wx.ART_NEW, wx.ART_BUTTON, wx.Size(16, 16))
        bmp_torol = wx.ArtProvider.GetBitmap(wx.ART_DELETE, wx.ART_BUTTON, wx.Size(16, 16))

        gomb_uj = wx.Button(panel, label="Új könyv")
        gomb_uj.SetBitmap(bmp_uj)

        gomb_szerk = wx.Button(panel, label="Szerkesztés")
        gomb_torol = wx.Button(panel, label="Törlés")
        gomb_torol.SetBitmap(bmp_torol)
        gomb_katalogus = wx.Button(panel, label="Katalógus export")

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
        gomb_sizer.Add(gomb_katalogus, 0, wx.RIGHT, 15)

        gomb_sizer.AddStretchSpacer(1) 

        gomb_sizer.Add(kereso_cimke, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        gomb_sizer.Add(self.kereso_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
                
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
        id_kereso_fokusz = wx.NewIdRef()

        # A Delete billentyűt NEM kötjük itt külön is a törléshez: a Fájl
        # menü 'Könyv(ek) eltávolítása' pontja (menusor.torles) már saját
        # \tDelete gyorsbillentyűvel rendelkezik, és ugyanerre a
        # OnKonyvTorles kezelőre mutat. Egy második, ide kötött Delete-
        # bejegyzés ugyanarra a billentyűre ugyanazt a kezelőt hívná meg
        # kétszer egyetlen billentyűlenyomásra (pl. a törlés-megerősítő
        # ablak kétszeri megjelenését okozva).
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('F'), id_kereso_fokusz),
        ])
        self.SetAcceleratorTable(accel_tbl)

        # MENÜ ESEMÉNYEK (Visszaállítva!)
        self.Bind(wx.EVT_MENU, self.OnUjKonyv, menusor.uj_konyv)
        self.Bind(wx.EVT_MENU, self.OnKilepes, menusor.kilepes)
        self.Bind(wx.EVT_MENU, lambda e: self.MegnyitReszletek(szerkesztesre=True), menusor.szerk)
        self.Bind(wx.EVT_MENU, self.OnKonyvTorles, menusor.torles)
        self.Bind(wx.EVT_MENU, self.OnExportalas, menusor.export_elem)
        self.Bind(wx.EVT_MENU, self.OnJsonImport, menusor.json_import)
        self.Bind(wx.EVT_MENU, self.OnJsonExport, menusor.json_export)
        self.Bind(wx.EVT_MENU, self.OnKatalogusExport, menusor.katalogus)
        self.Bind(wx.EVT_MENU, self.OnMasolas, menusor.copy)
        self.Bind(wx.EVT_MENU, self.OnVisszavonas, menusor.undo)
        self.Bind(wx.EVT_MENU, self.OnMegis, menusor.redo)
        self.Bind(wx.EVT_MENU_OPEN, self.OnMenuNyitas)
        self.Bind(wx.EVT_MENU, self.OnMindentKijelol, menusor.select_all)
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
        gomb_katalogus.Bind(wx.EVT_BUTTON, self.OnKatalogusExport)
        self.gomb_szuro_torles.Bind(wx.EVT_BUTTON, lambda e: self.szuro_torlese())

        self.kereso_ctrl.Bind(wx.EVT_TEXT, self.OnKeresoValtozas)
        self.kereso_ctrl.Bind(wx.EVT_SEARCH, self.OnKeresoEnter)
        self.kereso_ctrl.Bind(wx.EVT_TEXT_ENTER, self.OnKeresoEnter)

        # LISTA ESEMÉNYEK (Visszaállítva!)
        self.lista.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnListaJobbKlikk)
        self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnListaDuplaKlikk)
        self.lista.Bind(wx.EVT_KEY_DOWN, self.OnListaEnter)

        self.Bind(wx.EVT_MENU, self.OnMindentKijelol, id=id_mindent_kijelol)

        # FÓKUSZ (kijelölés nélkül): indításkor az első tétel nincs kijelölve.
        self.lista.SetFocus()
        # if self.lista.GetItemCount() > 0:
        #     self.lista.Select(0)
            
        # Visszavonás/mégis: a könyvlista újrarajzolása akkor is, ha a
        # lépést a Dezideráta-ablakból vonták vissza; a dezideráta tárolója
        # pedig nyitott ablaknál az ablak, zártnál közvetlenül a fájl.
        self.db.nezet_frissito = self._nezet_frissitese_visszavonas_utan
        self.db.undo_regiszter.tarolo_regisztral("deziderata", self._deziderata_undo_tarolo)

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

        # Ha a "KönyvTárnok kereső" ablak épp nyitva van, az ottani
        # találati táblázat "Állományban" jelzése egy korábbi keresés
        # pillanatában lett kiszámolva. Mivel FrissitStatusBar minden
        # olyan művelet (törlés, szerkesztés, felvétel) után lefut, ami
        # megváltoztathatja az állományt, ez a legmegbízhatóbb pont arra,
        # hogy a kereső ablakot is naprakészen tartsuk - új keresés
        # indítása nélkül is.
        self.frissit_kereso_statuszokat()

    def frissit_kereso_statuszokat(self):
        """Ha a "KönyvTárnok kereső" ablak nyitva van, újraszámoltatja a
        találati táblázat 'Állományban' és 'Deziderátában' jelzéseit.

        Két helyről hívódik: a FrissitStatusBar-ból (az állomány
        változásakor) és a Dezideráta-kezelő mentéseiből (a dezideráta
        változásakor, lásd Deziderata.save_data) - utóbbiról azért, mert a
        dezideráta módosítása nem jár együtt a FrissitStatusBar hívásával."""
        if self.konyvtarnok_kereso_frame is not None:
            try:
                self.konyvtarnok_kereso_frame.frissit_statuszokat()
            except RuntimeError:
                # A wx ablakobjektum már megsemmisült (pl. bezárás közben
                # futott le ez a hívás) - jelöljük referenciamentesnek.
                self.konyvtarnok_kereso_frame = None

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

        # Ez a közvetlen (menü/gomb általi) szerkesztési útvonal: itt a dlg
        # maga ID_OK-val zár sikeres mentéskor, ezért itt tudjuk a szokásos
        # módon eldönteni, hogy valóban történt-e mentés. A KonyvReszletekDialog
        # "Szerkesztés" gombján keresztüli út más: ott a KonyvReszletekDialog
        # már ID_CANCEL-lel zár, mielőtt a beágyazott szerkesztő megnyílna,
        # ezért az az útvonal a lenti frissit_lista_szerkesztes_utan metódust
        # közvetlenül, önmaga hívja meg (lásd konyvdialogs.KonyvReszletekDialog
        # .on_szerkesztes) - hogy a két útvonal viselkedése ne térjen el.
        if dlg.ShowModal() == wx.ID_OK:
            self.frissit_lista_szerkesztes_utan(szerkesztett_id, eredeti_idx=idx)

        dlg.Destroy()
        self.lista.SetFocus()

    def frissit_lista_szerkesztes_utan(self, szerkesztett_id, eredeti_idx=None):
        """Frissíti a könyvlista nézetét (a rendezés és az esetlegesen aktív
        szűrés megőrzésével), a státuszsort, és a kijelölést egy könyv
        szerkesztése után.

        Ezt hívja meg mind a közvetlen szerkesztés (menü/gomb ->
        KonyvSzerkesztoDialog, lásd MegnyitReszletek), mind a "Könyv
        adatlapja" ablakban lévő "Szerkesztés" gombon keresztüli szerkesztés
        (KonyvReszletekDialog -> KonyvSzerkesztoDialog, lásd
        konyvdialogs.KonyvReszletekDialog.on_szerkesztes), hogy a két
        útvonal frissítési logikája ne térjen el egymástól.

        szerkesztett_id: a szerkesztett könyv adatbázis-beli azonosítója,
            amely alapján a listában lévő (esetlegesen rendezés miatt új
            helyre került) sorát megkeressük és újra kijelöljük.
        eredeti_idx: a szerkesztés előtti sorindex a listában (ha ismert),
            amit csak akkor használunk tartalék kijelölésként, ha az id
            alapú keresés nem járt sikerrel (pl. mert az aktív szűrés miatt
            a könyv már nem szerepel a látható listában).
        """
        self.teljes_adatlista = []
        # A korábban aktív szűrt listát jelenítjük meg újra (ha volt ilyen),
        # ahelyett hogy a szűrő-felirat szövegéből próbálnánk visszafejteni
        # a keresési feltételt. Mivel a szűrt lista ugyanazokra a könyv-
        # objektumokra mutat, mint az adatbázis, a szerkesztés hatása is
        # azonnal látszik rajta, a szűrés típusától (szöveges keresés vagy
        # statisztikai szűrés) függetlenül.
        if self.aktiv_szurt_lista is not None:
            self.lista.FeltoltLista(self.aktiv_szurt_lista)
        else:
            self.lista.FeltoltLista(self.db.konyvek)
        self.FrissitStatusBar()

        uj_idx = -1
        if szerkesztett_id is not None:
            for k, v in self.lista.sor_id_terkep.items():
                if v == szerkesztett_id:
                    uj_idx = k
                    break
        if uj_idx == -1 and eredeti_idx is not None and 0 <= eredeti_idx < self.lista.GetItemCount():
            uj_idx = eredeti_idx

        if uj_idx != -1 and self.lista.GetItemCount() > 0:
            self.lista.Select(uj_idx)
            self.lista.Focus(uj_idx)
            self.lista.EnsureVisible(uj_idx)

    def OnKonyvTorles(self, event):
        indexek = self.lista.GetKijeloltIndexek()
        if not indexek:
            wx.MessageBox("Kérjük, válasszon ki legalább egy könyvet a törléshez!", "Nincs kijelölés", wx.OK | wx.ICON_WARNING)
            return

        darab = len(indexek)
        uzenet = f"Biztosan törölni szeretné a(z) '{self.lista.GetItemText(indexek[0])}' című könyvet?" if darab == 1 else f"Biztosan törölni szeretné a kijelölt {darab} db könyvet?"

        kerdes = wx.MessageDialog(self, uzenet, "Törlés megerősítése", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        
        if kerdes.ShowModal() == wx.ID_YES:
            cel_index = min(indexek)

            torlendo_id_k = []
            for idx in indexek:
                konyv = self.lista.GetKonyvByRowIndex(idx)
                if konyv and konyv.get("id"):
                    torlendo_id_k.append(konyv.get("id"))
                elif konyv:
                    logging.warning(f"A könyvnek nincs ID-je, nem törölhető: {konyv.get('cim', '?')}")

            # A db.konyv_torlese_by_id visszatérési értékét (illetve az
            # esetleges MentesiHiba kivételt) korábban itt egyáltalán nem
            # néztük meg: egy sikertelen lemezre mentés esetén a könyv
            # csendben, mindenféle hibaüzenet nélkül "eltűnt" volna a
            # listából, majd újraindítás után visszatért volna, mert
            # valójában sosem lett elmentve. Most megszakítjuk a törlést és
            # jelezzük a hibát, amint az első ilyen eset előfordul.
            try:
                undo_leiras = (f"{len(torlendo_id_k)} könyv törlése"
                               if len(torlendo_id_k) > 1 else "könyv törlése")
                with self.db.undo.muvelet(undo_leiras):
                    for konyv_id in torlendo_id_k:
                        self.db.konyv_torlese_by_id(konyv_id)
            except MentesiHiba as e:
                wx.MessageBox(
                    f"Hiba történt a törlés mentése közben:\n{e}\n\n"
                    "A törlés emiatt megszakadt, a további kijelölt könyvek "
                    "esetleg nem lettek törölve.",
                    "Mentési hiba",
                    wx.OK | wx.ICON_ERROR,
                    self,
                )

            self.teljes_adatlista = []
            if self.aktiv_szurt_lista is not None:
                torolt_id_halmaz = set(torlendo_id_k)
                self.aktiv_szurt_lista = [
                    konyv for konyv in self.aktiv_szurt_lista
                    if konyv.get("id") not in torolt_id_halmaz
                ]
                self.lista.FeltoltLista(self.aktiv_szurt_lista)
                self._frissit_szuro_cimke_darabszamot(len(self.aktiv_szurt_lista))
            else:
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

    def OnMasolas(self, event):
        """Szerkesztés > Másolás (Ctrl+C): a kijelölt könyvek a vágólapra.

        A menü Ctrl+C gyorsbillentyűje elveszi a billentyűt a beviteli
        mezőktől is, ezért ha a fókusz a kereső szövegmezőben van, a mező
        saját másolását végezzük el, nem a lista kijelölését.
        """
        fokusz = self.FindFocus()
        if isinstance(fokusz, (wx.TextCtrl, wx.SearchCtrl)):
            if fokusz.CanCopy():
                fokusz.Copy()
            return

        szoveg = self.lista.GetKijeloltSzoveg()
        if not szoveg:
            return
        if not masolas_vagolapra_szoveg(szoveg):
            wx.MessageBox("Nem sikerült megnyitni a vágólapot.", "Hiba", wx.OK | wx.ICON_ERROR)
            return
        darab = self.lista.GetSelectedItemCount()
        self.statusbar.SetStatusText(f"{darab} könyv a vágólapra másolva.")

    def OnMindentKijelol(self, event):
        self.lista.SetFocus()
        for i in range(self.lista.GetItemCount()):
            self.lista.Select(i, True)

    # --- VISSZAVONÁS / MÉGIS ---

    def _deziderata_undo_tarolo(self):
        """A dezideráta undo-tárolója: nyitott ablaknál az ablak (memória),
        zártnál közvetlenül a deziderata.json (így a Dezideráta-kezelőből
        indult átemelés a főablakból akkor is visszavonható, ha az ablakot
        közben bezárták)."""
        frame = self.deziderata_frame
        if frame is not None:
            try:
                if bool(frame):
                    return frame.undo_tarolo
            except RuntimeError:
                pass
        return DeziderataFajlTarolo(frissito=self.frissit_kereso_statuszokat)

    def OnMenuNyitas(self, event):
        """Menü megnyitásakor a Visszavonás/Mégis tételek feliratába beírja a
        soron következő lépés leírását."""
        frissit_undo_menu(self.menusor.undo, self.menusor.redo,
                          self.db.undo, self.FindFocus())
        event.Skip()

    def OnVisszavonas(self, event):
        self._visszavonas_vagy_megis(ismet=False)

    def OnMegis(self, event):
        self._visszavonas_vagy_megis(ismet=True)

    def _visszavonas_vagy_megis(self, ismet):
        # A menü Ctrl+Z / Ctrl+Y gyorsbillentyűje elveszi a billentyűt a
        # beviteli mezőktől is: a kereső mezőben a mező saját szövegét vonjuk
        # vissza, nem az állományt (lásd OnMasolas is).
        if szovegmezo_visszavonas(self.FindFocus(), ismet):
            return

        kezelo = self.db.undo
        leiras = kezelo.ismetlendo_leiras() if ismet else kezelo.visszavonando_leiras()
        if leiras is None:
            self.statusbar.SetStatusText(
                "Nincs mit újra alkalmazni." if ismet else "Nincs visszavonható művelet."
            )
            return

        # A lépés minden érintett oldalát (állomány, adott esetben a
        # dezideráta is) a regiszter alkalmazza, és a nézeteket is frissíti.
        if not (kezelo.ismet() if ismet else kezelo.visszavon()):
            wx.MessageBox(
                "A művelet nem hajtható végre (a változás nem menthető), ezért "
                "az adatok a korábbi állapotukban maradtak.",
                "Mentési hiba", wx.OK | wx.ICON_ERROR, self,
            )
            return
        self.statusbar.SetStatusText(
            f"Újra alkalmazva: {leiras}." if ismet else f"Visszavonva: {leiras}."
        )

    def _nezet_frissitese_visszavonas_utan(self, kijelolendo_idk, kijelol=True):
        """Újraépíti a listát a visszaállított adatokból, megőrizve az aktív
        szűrést; kijelol=True esetén kijelöli az érintett (visszakerült/
        megváltozott) könyveket és ide viszi a fókuszt."""
        self.teljes_adatlista = []
        if self.aktiv_szurt_lista is not None:
            predikatum = self.aktiv_szuro_predikatum
            if predikatum is not None:
                def _illeszkedik(konyv):
                    try:
                        return bool(predikatum(konyv))
                    except Exception:
                        return False
                self.aktiv_szurt_lista = [k for k in self.db.konyvek if _illeszkedik(k)]
            else:
                korabbi_idk = {k.get("id") for k in self.aktiv_szurt_lista}
                self.aktiv_szurt_lista = [
                    k for k in self.db.konyvek if k.get("id") in korabbi_idk
                ]
            self.lista.FeltoltLista(self.aktiv_szurt_lista)
            self._frissit_szuro_cimke_darabszamot(len(self.aktiv_szurt_lista))
        else:
            self.lista.FeltoltLista()
        self.FrissitStatusBar()

        if not kijelol:
            return
        self.lista.SetFocus()
        if kijelolendo_idk:
            halmaz = set(kijelolendo_idk)
            indexek = [i for i, azon in self.lista.sor_id_terkep.items() if azon in halmaz]
            if indexek:
                for i in indexek:
                    self.lista.Select(i)
                self.lista.Focus(indexek[0])
                self.lista.EnsureVisible(indexek[0])

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
        export_item = popup_menu.Append(wx.ID_ANY, f"Kijelöltek exportálása ({len(indexek)} db)")

        self.Bind(wx.EVT_MENU, lambda e: self.MegnyitReszletek(szerkesztesre=False), megtekint_item)
        self.Bind(wx.EVT_MENU, lambda e: self.MegnyitReszletek(szerkesztesre=True), szerkeszt_item)
        self.Bind(wx.EVT_MENU, self.OnKonyvTorles, torol_item)
        self.Bind(wx.EVT_MENU, self.OnExportalas, export_item)

        self.PopupMenu(popup_menu)
        popup_menu.Destroy()

    def OnListaJobbKlikk(self, event):
        idx = event.GetIndex()
        if idx not in self.lista.GetKijeloltIndexek():
            self.lista.Select(idx)
        self._MegjelenitPopUpMenut()

    def _uj_konyvek_utani_frissites(self, uj_konyvek):
        """Egy vagy több újonnan felvett könyv (kézi felvitel, PDF import vagy
        JSON import) után frissíti a lista nézetét úgy, hogy egy esetlegesen
        aktív szűrés megmaradjon: a predikátumra illeszkedő új tételek
        bekerülnek a szűrt listába, a többi rejtve marad, amíg a szűrést
        nem törlik.

        Ez a metódus kifejezetten ADDITÍV műveletekhez való (a könyv(ek) a
        meglévő adatbázishoz lettek hozzáadva, a duplikátumok kihagyásával).
        Egy esetleges jövőbeli, teljes adatbázis-cserét végző művelethez nem
        ez, hanem a szűrés teljes újraszámolása lenne a helyes megoldás, mert
        ott a régi szűrt lista elemei már nem is léteznének az új adatban.

        Visszaadja azokat az új könyveket, amelyek ténylegesen láthatóvá
        váltak (a szűrt vagy a teljes listában megjelentek).
        """
        self.teljes_adatlista = []

        if self.aktiv_szurt_lista is None:
            self.lista.FeltoltLista()
            self.FrissitStatusBar()
            return list(uj_konyvek)

        lathato_uj_konyvek = []
        for konyv in uj_konyvek:
            illeszkedik = True
            if self.aktiv_szuro_predikatum is not None:
                try:
                    illeszkedik = bool(self.aktiv_szuro_predikatum(konyv))
                except Exception:
                    illeszkedik = False
            if illeszkedik:
                self.aktiv_szurt_lista.append(konyv)
                lathato_uj_konyvek.append(konyv)

        if lathato_uj_konyvek:
            self._frissit_szuro_cimke_darabszamot(len(self.aktiv_szurt_lista))

        self.lista.FeltoltLista(self.aktiv_szurt_lista)
        self.FrissitStatusBar()
        return lathato_uj_konyvek

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

            uj_cim = friss_adatok.get("cim")

            # Megkeressük a ténylegesen felvett könyv objektumát az
            # adatbázisban (a végén hozzáadva), hogy aktív szűrés esetén el
            # tudjuk dönteni, illeszkedik-e rá.
            uj_konyv_obj = None
            for konyv in reversed(self.db.konyvek):
                if konyv.get("cim") == uj_cim:
                    uj_konyv_obj = konyv
                    break

            lathato_uj_konyvek = self._uj_konyvek_utani_frissites(
                [uj_konyv_obj] if uj_konyv_obj is not None else []
            )

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
                if self.aktiv_szurt_lista is not None and uj_konyv_obj is not None and not lathato_uj_konyvek:
                    wx.MessageBox(
                        "A könyv sikeresen felvételre került, de az aktív szűrésnek "
                        "nem felel meg, ezért egyelőre nem jelenik meg a listában.\n"
                        "A 'Szűrés törlése' gombbal láthatóvá teheti.",
                        "Szűrés aktív", wx.OK | wx.ICON_INFORMATION, self
                    )
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

        if valasz == wx.ID_YES:
            return "FELULIRAS"
        elif valasz == wx.ID_YESTOALL:
            return "MINDET_FELULIR"
        elif valasz == wx.ID_NO:
            return "KIHAGYAS"
        else: # X gomb, ESC vagy "Összes kihagyása" (wx.ID_CANCEL)
            return "OSSZES_KIHAGYASA"

    def OnExportalas(self, event):
        indexek = self.lista.GetKijeloltIndexek()
        if not indexek:
            wx.MessageBox("Kérjük, válasszon ki legalább egy könyvet az exportáláshoz!", "Nincs kijelölés", wx.OK | wx.ICON_WARNING)
            return

        config = load_settings()
        default_dir = config.get("last_pdf_dir", "")

        if len(indexek) == 1:
            konyv_adatok = self.lista.GetKonyvByRowIndex(indexek[0])
            if konyv_adatok:
                exportal_egy_konyv(self, konyv_adatok)

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
        if megnyit_dlg.ShowModal() != wx.ID_OK:
            megnyit_dlg.Destroy()
            return

        kivalasztott_utvonal = megnyit_dlg.GetPath()
        megnyit_dlg.Destroy()

        config["last_json_dir"] = os.path.dirname(kivalasztott_utvonal)
        save_settings(config)

        # Additív import: minden tételt a meglévő állományhoz adunk hozzá, a
        # duplikátumellenőrzést a KonyvAdatbazis végzi el (uj_konyv_hozzaadasa).
        # A fájl beolvasását és a tételenkénti hozzáadás ciklusát a
        # data_manager.additiv_lista_import közös segédfüggvénye végzi (ezt a
        # mintát korábban itt és a Dezideráta-kezelő JSON importjában is
        # egymástól függetlenül, kézzel írtuk meg).
        uj_konyv_objektumok = []

        def _hozzaad(konyv):
            if hasattr(self.db, 'uj_konyv_hozzaadasa') and self.db.uj_konyv_hozzaadasa(konyv):
                uj_konyv_objektumok.append(self.db.konyvek[-1])
                return True
            return False

        try:
            with self.db.undo.muvelet("JSON importálás"):
                hozzaadva, kihagyva = additiv_lista_import(kivalasztott_utvonal, _hozzaad)
        except ValueError as e:
            wx.MessageBox(str(e), "Hiba", wx.OK | wx.ICON_ERROR)
            return
        except MentesiHiba as e:
            # Külön ág a data_manager.MentesiHiba-nak: ez azt jelenti, hogy
            # egy tétel importálása közben a lemezre mentés hiúsult meg (nem
            # duplikátum volt), ezért ezt nem szabad az általános "hiba
            # történt az importálás során" üzenettel összemosni, illetve a
            # már addig sikeresen importált (és elmentett) tételek
            # megmaradnak.
            wx.MessageBox(
                f"Hiba történt az állományjegyzék mentése közben:\n{e}\n\n"
                "Az addig sikeresen importált tételek megmaradnak, de az "
                "importálás emiatt megszakadt.",
                "Mentési hiba",
                wx.OK | wx.ICON_ERROR,
            )
            self._uj_konyvek_utani_frissites(uj_konyv_objektumok)
            return
        except Exception as e:
            logging.error(f"Hiba történt az importálás közben: {e}")
            wx.MessageBox(f"Hiba történt az importálás során:\n{e}", "Hiba", wx.OK | wx.ICON_ERROR)
            return

        lathato_uj_konyvek = self._uj_konyvek_utani_frissites(uj_konyv_objektumok)

        uzenet = f"Importálás befejeződött!\n\nHozzáadva: {hozzaadva} db\nKihagyva (már létező duplikátum): {kihagyva} db"
        if self.aktiv_szurt_lista is not None and uj_konyv_objektumok and not lathato_uj_konyvek:
            uzenet += "\n\nAz aktív szűrés miatt egyik újonnan felvett könyv sem látható jelenleg a listában."
        elif self.aktiv_szurt_lista is not None and len(lathato_uj_konyvek) < len(uj_konyv_objektumok):
            uzenet += f"\n\nAz aktív szűrés miatt csak {len(lathato_uj_konyvek)}/{len(uj_konyv_objektumok)} új könyv látható jelenleg a listában."

        wx.MessageBox(uzenet, "Siker", wx.OK | wx.ICON_INFORMATION)

    def OnJsonExport(self, event):
        config = load_settings()
        default_dir = config.get("last_json_dir", "")

        ment_dlg = wx.FileDialog(
            self, "Állományjegyzék exportálása nyers JSON fájlba", 
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

    def OnKatalogusExport(self, event):
        katalogus_mentese(self, list(self.lista.jelenlegi_adatok),
                          list(self.lista.aktiv_oszlopok))

    def on_kereses_dialógus_megnyitasa(self, event):
        dlg = KeresoDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            keresett_szoveg = dlg.get_search_text()
            pontos_egyezes = dlg.is_exact_match()
            if keresett_szoveg:
                self.kereso_ctrl.SetValue(keresett_szoveg)
                self.kereses_az_allomanyban(keresett_szoveg, pontos_egyezes)
        dlg.Destroy()

    def _frissit_szuro_cimke_darabszamot(self, uj_darabszam):
        """Frissíti a szűrő-felirat végén szereplő találatszámot (pl. törlés
        vagy hozzáadás után), anélkül hogy a szűrés szövegét/típusát
        megváltoztatná."""
        label = self.szuro_kijelzo.GetLabel()
        if label:
            uj_label = re.sub(r'\(\d+ találat\)', f'({uj_darabszam} találat)', label)
            self.szuro_kijelzo.SetLabel(uj_label)
            self.szuro_kijelzo.GetParent().Layout()

    def kereses_az_allomanyban(self, keresett_szoveg, pontos_egyezes=False):
        if not self.teljes_adatlista:
            if hasattr(self.db, 'konyvek'):
                self.teljes_adatlista = self.db.konyvek
            elif hasattr(self.db, 'get_osszes_konyv'):
                self.teljes_adatlista = self.db.get_osszes_konyv()

        # A tényleges egyezés-vizsgálatot a data_manager.szuresi_talalatok /
        # szoveg_szuro_egyezik közös (GUI-mentes) függvényei végzik, hogy azt
        # más ablakok (pl. egy jövőbeli kereső ablak) vagy tesztek is
        # közvetlenül újra tudják használni.
        keresett = keresett_szoveg.lower().strip()
        leszurt_adatok = szuresi_talalatok(self.teljes_adatlista, keresett_szoveg, pontos_egyezes)

        self.aktiv_szuro_predikatum = lambda k, _ker=keresett, _pe=pontos_egyezes: szoveg_szuro_egyezik(k, _ker, _pe)

        if not leszurt_adatok:
            self.aktiv_szurt_lista = []
            self.lista.FeltoltLista([])
            self.FrissitStatusBar()
            self.szuro_kijelzo.SetLabel(f"Nincs találat: '{keresett_szoveg}'")
            self.gomb_szuro_torles.Enable()
            self.Layout()
            return

        self.aktiv_szurt_lista = leszurt_adatok
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
        self.aktiv_szurt_lista = None
        self.aktiv_szuro_predikatum = None
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
        # A dialógus a kapott config-ból dolgozik, maga nem olvassa újra a
        # settings.json-t. Az oszlopoknál a lista jelenlegi állapota az irányadó
        # (ez eltérhet a fájltól, pl. ha egy korábbi mentés nem sikerült).
        config["lathato_oszlopok"] = list(self.lista.aktiv_oszlopok)
        dlg = BeallitasokDialog(self, config)
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
            config["auto_update_check"] = dlg.GetAutoUpdateCheck()
            config["update_frequency"] = dlg.GetUpdateFrequency()
            save_settings(config)
            
            if hasattr(self.lista, 'Rendezes'):
                self.lista.Rendezes(uj_rendezes)

            apply_theme(self, uj_tema)
            if self.deziderata_frame:
                apply_theme(self.deziderata_frame, uj_tema)
                self.deziderata_frame.current_theme = uj_tema
            if self.konyvtarnok_kereso_frame:
                apply_theme(self.konyvtarnok_kereso_frame, uj_tema)
                self.konyvtarnok_kereso_frame.current_theme = uj_tema

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
            self.deziderata_frame = Deziderata(parent=self)
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

            leszurt_adatok, predikatum, is_hianyzo = statisztikai_szures(self.teljes_adatlista, kulcs, keresett_ertek)

            if leszurt_adatok:
                # A kiválasztott/meghatározott rendezést érvényesítjük a listán
                self.lista.rendezes_kulcs = uj_rendezes
                self.lista.Rendezes(uj_rendezes)
                self.aktiv_szurt_lista = leszurt_adatok
                self.aktiv_szuro_predikatum = predikatum
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

    def OnFrissites(self, event):
        check_for_updates_async(parent=self, is_manual=True)

    def on_open_help(self, event):
        """Ez a metódus fut le a Súgó menüpontra vagy az F1-re kattintva."""
        dlg = HelpNotebookDialog(self)
        dlg.ShowModal()
        dlg.Destroy()
