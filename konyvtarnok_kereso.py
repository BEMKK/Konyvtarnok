import os
import sys
import json
import wx
import logging
from theme_manager import apply_theme_from_settings
from deziderata import DATA_FILE as DEZIDERATA_DATA_FILE
from data_manager import (
    load_hmac_json,
    save_hmac_json,
    tetelek_egyeznek,
    konyvek_tomeges_felvetele,
    kerj_tomeges_atemeles_megerositest,
    mutass_tomeges_atemeles_eredmenyt,
    KERESO_MEZO_ALIASOK,
    sor_alap_adatta_alakitasa,
    load_kereso_json,
    is_same_book,
)
from gyors_kereses import GyorsListaKereso, osszes_kijelolt_index
from utils import masolas_vagolapra_szoveg




class KonyvtarnokKeresoApp(wx.Frame):

    def __init__(self, parent=None):
        super().__init__(
            parent=parent, title="KönyvTárnok kereső", size=(1000, 600)
        )

        self.parent = parent
        self.SetName("KönyvTárnok kereső")

        self.panel = wx.Panel(self)
        self.panel.SetName("Főpanel")

        # 1. JSON fájl betöltése a háttérben
        self.json_fajlnev = "enekeskonyvek_adatai.json"  # Excel helyett JSON
        self.oszlopok = []
        self.adatok = self.adatok_betoltese()

        # Gyorskeresés (gépeléssel ugrás a listában)
        self.gyors_kereses = GyorsListaKereso()

        # UI elemek létrehozása
        self.init_ui()

        # Status bar létrehozása az ablak alján
        self.CreateStatusBar()
        osszesen = len(self.adatok) if self.adatok else 0
        self.SetStatusText(f"Keresés {osszesen} kötet adataiban")

        # Gyorsbillentyű tábla a Ctrl+W bezáráshoz
        self.init_shortcuts()

        # Téma alkalmazása
        config = apply_theme_from_settings(self)
        self.current_theme = config.get("tema", "vilagos")

    def adatok_betoltese(self):
        """Beolvassa a JSON fájlt a data_manager segédfüggvényével."""
        try:
            oszlopok, adatok, fajl_utvonal = load_kereso_json(self.json_fajlnev)
            if oszlopok is not None:
                self.oszlopok = oszlopok
                return adatok
            else:
                wx.MessageBox(
                    f"A(z) '{self.json_fajlnev}' nem található a program mappájában!\n\nKeresett útvonal:\n{fajl_utvonal}",
                    "Fájl hiányzik",
                    wx.OK | wx.ICON_WARNING,
                )
                return None
        except Exception as e:
            wx.MessageBox(
                f"Hiba a fájl beolvasásakor:\n{e}",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return None

    def _sor_alap_adatta_alakitasa(self, forras_dict):
        """Egy nyers sor (a keresési JSON-ból vagy a táblázatból kiolvasott
        dict) leképezése az állomány kanonikus (cim, szerzo, kiado, hely,
        ev, ...) mezőneveire (lásd data_manager.sor_alap_adatta_alakitasa)."""
        return sor_alap_adatta_alakitasa(forras_dict)

    # ==========================================================================
    # KÖZÖS "ÁLLOMÁNYBAN VAN-E" SEGÉDMETÓDUSOK
    # ==========================================================================
    # Ezt a három segédmetódust (a főablak állományának cím szerinti
    # csoportosítása, a Cím oszlop nevének megkeresése a betöltött JSON
    # oszlopai között, és az egyes sorok tényleges "Állományban van-e"
    # eldöntése) korábban az on_kereses és a frissit_allomany_statuszokat
    # egymástól függetlenül, szó szerint megegyező formában tartalmazta - a
    # kódkomment maga is jelezte, hogy a két helynek szándékosan szinkronban
    # kellene maradnia. Innentől mindkét hely ugyanezt a három metódust
    # hívja, így a szinkron nem kézi fegyelem kérdése többé.

    def _epit_konyvek_cim_szerint(self):
        """A főablak állományában lévő könyvek cím szerinti csoportosítása
        (kisbetűsen, levágva), hogy soronként csak az azonos című könyvek
        között kelljen elvégezni a teljes (tetelek_egyeznek) egyezés-
        vizsgálatot - ez nagy állomány esetén is gyors marad, miközben
        azonos című, de más kiadású/szerzőjű könyveket helyesen nem jelöl
        "Állományban"-ként."""
        konyvek_cim_szerint = {}
        if self.parent and hasattr(self.parent, "db"):
            if hasattr(self.parent.db, "konyvek") and self.parent.db.konyvek:
                for k in self.parent.db.konyvek:
                    cim = str(k.get("cim", "")).strip().lower()
                    if cim:
                        konyvek_cim_szerint.setdefault(cim, []).append(k)
        return konyvek_cim_szerint

    def _cim_oszlop_neve(self):
        """Megkeresi a Cím oszlop nevét a betöltött (kereső JSON-beli)
        oszlopnevek között, vagy - ha nem egyértelmű a fejléc - az első
        oszlopot adja vissza tartalékként."""
        for col in self.oszlopok:
            if str(col).strip().lower() in ["cím", "cim"]:
                return col
        return self.oszlopok[0] if self.oszlopok else None

    def _allomanyban_van_e(self, sor_adat, cim_oszlop_neve, konyvek_cim_szerint):
        """Eldönti, hogy egy sor (a táblázatból vagy a nyers keresési
        adatokból kiolvasott dict) szerepel-e már az állományban.

        A cím szerinti előszűrés (konyvek_cim_szerint) után a teljes,
        több mezőt (szerző, kiadó, hely, év) is figyelembe vevő
        tetelek_egyeznek vizsgálattal dönt, nem csak a cím alapján."""
        if not cim_oszlop_neve:
            return False
        sor_cime = str(sor_adat.get(cim_oszlop_neve, "")).strip().lower()
        if not sor_cime or sor_cime not in konyvek_cim_szerint:
            return False
        sor_alap_adat = self._sor_alap_adatta_alakitasa(sor_adat)
        return any(
            tetelek_egyeznek(sor_alap_adat, konyv)
            for konyv in konyvek_cim_szerint[sor_cime]
        )


    def init_ui(self):
        fő_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Kereső sáv ---
        kereso_szoveg = wx.StaticText(
            self.panel, label="Keresendő kifejezés:"
        )
        self.kereso_mezo = wx.TextCtrl(self.panel, style=wx.TE_PROCESS_ENTER)
        self.kereso_mezo.Bind(wx.EVT_TEXT_ENTER, self.on_kereses)
        self.kereso_mezo.Bind(wx.EVT_TEXT, self.on_szoveg_valtozas)

        kereso_gomb = wx.Button(self.panel, label="Keresés")
        kereso_gomb.Bind(wx.EVT_BUTTON, self.on_kereses)

        kereso_sizer = wx.BoxSizer(wx.HORIZONTAL)
        kereso_sizer.Add(
            kereso_szoveg,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            border=5,
        )
        kereso_sizer.Add(self.kereso_mezo, proportion=1, flag=wx.EXPAND)
        kereso_sizer.Add(kereso_gomb, flag=wx.LEFT, border=5)

        fő_sizer.Add(kereso_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # --- Checkboxok az oszlopokhoz ---
        opciok_szoveg = wx.StaticText(
            self.panel, label="Keresés ezekben az oszlopokban:"
        )
        fő_sizer.Add(opciok_szoveg, flag=wx.LEFT | wx.RIGHT, border=10)

        self.checkboxok = {}
        checkbox_sizer = wx.BoxSizer(wx.HORIZONTAL)

        if self.oszlopok:
            for oszlop in self.oszlopok:
                cb = wx.CheckBox(self.panel, label=str(oszlop))
                cb.SetValue(True)
                checkbox_sizer.Add(cb, flag=wx.RIGHT, border=10)
                self.checkboxok[oszlop] = cb
        else:
            nincs_adat = wx.StaticText(
                self.panel, label="Nincsenek elérhető oszlopok."
            )
            checkbox_sizer.Add(nincs_adat)

        fő_sizer.Add(checkbox_sizer, flag=wx.ALL, border=10)

        # --- Eredmény lista (wx.ListCtrl táblázat) ---
        self.eredmeny_szoveg = wx.StaticText(self.panel, label="Találatok:")
        fő_sizer.Add(self.eredmeny_szoveg, flag=wx.LEFT, border=10)

        self.tablazat = wx.ListCtrl(self.panel, style=wx.LC_REPORT)

        # Események bekötése
        self.tablazat.Bind(
            wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_helyi_menu
        )
        self.tablazat.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_helyi_menu)
        self.tablazat.Bind(wx.EVT_KEY_DOWN, self.on_billentyu_leutve)
        self.tablazat.Bind(wx.EVT_CHAR, self.on_char)

        self.frissit_akadalymentesites(0)

        if self.oszlopok:
            for i, oszlop in enumerate(self.oszlopok):
                self.tablazat.InsertColumn(i, str(oszlop), width=130)
            statusz_col_idx = len(self.oszlopok)
            self.tablazat.InsertColumn(
                statusz_col_idx, "Státusz", width=120
            )
        else:
            self.tablazat.InsertColumn(0, "Üzenet", width=400)

        fő_sizer.Add(
            self.tablazat, proportion=1, flag=wx.EXPAND | wx.ALL, border=10
        )

        self.panel.SetSizer(fő_sizer)
        self.kereso_mezo.SetFocus()
        self.Centre()
        self.Show()

    def init_shortcuts(self):
        """Gyorsbillentyűk beállítása (Ctrl+W a kilépéshez)."""
        KILEPES_ID = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, self.on_kilepes, id=KILEPES_ID)

        accel_tbl = wx.AcceleratorTable(
            [(wx.ACCEL_CTRL, ord("W"), KILEPES_ID)]
        )
        self.SetAcceleratorTable(accel_tbl)

    def on_kilepes(self, event):
        self.Close()

    def frissit_akadalymentesites(self, darabszam):
        """Beállítja a táblázat belső nevét és a felette lévő feliratot."""
        szoveg = f"Találatok listája, {darabszam} elem"
        self.eredmeny_szoveg.SetLabel(f"Találatok ({darabszam} db):")
        self.tablazat.SetName(szoveg)

    def on_szoveg_valtozas(self, event):
        """Ha a felhasználó kiüríti a keresőmezőt, a táblázat is kiürül."""
        if not self.kereso_mezo.GetValue().strip():
            self.tablazat.DeleteAllItems()
            self.frissit_akadalymentesites(0)
        event.Skip()

    def on_kereses(self, event):
        """A keresés logikája gombnyomásra vagy Enterre (Pandas nélkül)."""
        self.tablazat.DeleteAllItems()

        if self.adatok is None:
            wx.MessageBox(
                "Nincs betöltött adat!", "Hiba", wx.OK | wx.ICON_ERROR
            )
            return

        keresett_szo = self.kereso_mezo.GetValue().strip().lower()
        if not keresett_szo:
            wx.MessageBox(
                "Írj be valamit a keresőmezőbe!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        kijelolt_oszlopok = [
            oszlop for oszlop, cb in self.checkboxok.items() if cb.GetValue()
        ]

        if not kijelolt_oszlopok:
            wx.MessageBox(
                "Válassz ki legalább egy oszlopot a kereséshez!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        # Meglévő könyvek csoportosítása cím szerint a főablak állományából
        # (lásd _epit_konyvek_cim_szerint).
        konyvek_cim_szerint = self._epit_konyvek_cim_szerint()

        # Szűrés tisztán Python listával (Pandas DataFrame helyett)
        szurt_adatok = []
        for sor in self.adatok:
            talalat = False
            for oszlop in kijelolt_oszlopok:
                ertek = str(sor.get(oszlop, "")).lower()
                if keresett_szo in ertek:
                    talalat = True
                    break
            if talalat:
                szurt_adatok.append(sor)

        if szurt_adatok:
            talalatok_szama = len(szurt_adatok)
            statusz_col_idx = len(self.oszlopok)
            cim_oszlop_neve = self._cim_oszlop_neve()

            for sor in szurt_adatok:
                # Sor beszúrása a táblázatba
                elsocsella = str(sor.get(self.oszlopok[0], ""))
                sor_index = self.tablazat.InsertItem(
                    self.tablazat.GetItemCount(), elsocsella
                )
                for col_idx, col_name in enumerate(self.oszlopok[1:], start=1):
                    self.tablazat.SetItem(
                        sor_index, col_idx, str(sor.get(col_name, ""))
                    )

                # Státusz ellenőrzése (lásd _allomanyban_van_e).
                megvan = self._allomanyban_van_e(sor, cim_oszlop_neve, konyvek_cim_szerint)

                # UTOLSÓ OSZLOP: Státusz beírása
                if megvan:
                    self.tablazat.SetItem(
                        sor_index, statusz_col_idx, "Állományban"
                    )
                    self.tablazat.SetItemBackgroundColour(
                        sor_index, wx.Colour(220, 245, 220)
                    )
                else:
                    self.tablazat.SetItem(sor_index, statusz_col_idx, "")

            self.frissit_akadalymentesites(talalatok_szama)
        else:
            self.frissit_akadalymentesites(0)

        if self.tablazat.GetItemCount() > 0:
            for i in range(self.tablazat.GetItemCount()):
                self.tablazat.Select(i, on=False)

        self.tablazat.SetFocus()

    def frissit_allomany_statuszokat(self):
        """Újraszámolja és frissíti a táblázatban JELENLEG megjelenő (már
        korábbi kereséskor betöltött) találatok 'Állományban' státuszát, a
        főablak aktuális állománya alapján - anélkül, hogy új keresést
        kellene indítani.

        Ezt hívja meg a főablak minden olyan művelet (könyv törlése,
        szerkesztése, felvétele) után, amely megváltoztathatja, mely
        tételek szerepelnek már az állományban. E hívás nélkül a kereső
        ablak - ha nyitva marad - téves "Állományban" jelzést mutathat
        például egy időközben törölt tételre, egészen a következő kereső
        gomb megnyomásáig.

        Az egyezés-vizsgálat logikáját a _epit_konyvek_cim_szerint /
        _cim_oszlop_neve / _allomanyban_van_e közös segédmetódusok végzik,
        amelyeket az on_kereses is használ, hogy a két hely soha ne térjen
        el egymástól.
        """
        if not self.oszlopok:
            return

        sorok_szama = self.tablazat.GetItemCount()
        if sorok_szama == 0:
            return

        statusz_col_idx = len(self.oszlopok)
        konyvek_cim_szerint = self._epit_konyvek_cim_szerint()
        cim_oszlop_neve = self._cim_oszlop_neve()

        for sor_index in range(sorok_szama):
            # A sor adatait magából a táblázatból olvassuk vissza (nem a
            # self.adatok eredeti listájából), hogy pontosan azt a
            # tartalmat vizsgáljuk, ami a felhasználó előtt látszik.
            sor_adat = {
                oszlop: self.tablazat.GetItemText(sor_index, col_idx)
                for col_idx, oszlop in enumerate(self.oszlopok)
            }
            megvan = self._allomanyban_van_e(sor_adat, cim_oszlop_neve, konyvek_cim_szerint)

            if megvan:
                self.tablazat.SetItem(sor_index, statusz_col_idx, "Állományban")
                self.tablazat.SetItemBackgroundColour(
                    sor_index, wx.Colour(220, 245, 220)
                )
            else:
                self.tablazat.SetItem(sor_index, statusz_col_idx, "")
                self.tablazat.SetItemBackgroundColour(sor_index, wx.NullColour)

        self.tablazat.Refresh()

    def feldolgoz_kereso_karakter(self, karakter):
        """Kezeli a karakter hozzáadását a keresési pufferhez és a megfelelő
        sorra ugrást (lásd gyors_kereses.GyorsListaKereso)."""
        def kijeloles_beallitasa(talalt_idx):
            for i in range(self.tablazat.GetItemCount()):
                self.tablazat.Select(i, False)
            self.tablazat.Select(talalt_idx, True)
            self.tablazat.Focus(talalt_idx)
            self.tablazat.EnsureVisible(talalt_idx)

        self.gyors_kereses.feldolgoz(
            karakter,
            total_lekero=self.tablazat.GetItemCount,
            szoveg_lekero=self.tablazat.GetItemText,
            kivalasztott_lekero=self.tablazat.GetFirstSelected,
            kivalasztas_beallito=kijeloles_beallitasa,
        )

    def on_char(self, event):
        self.gyors_kereses.kezel_char_esemeny(event, self.feldolgoz_kereso_karakter)

    def on_billentyu_leutve(self, event):
        """Kezeli a táblázatban leütött gyorsbillentyűket (Ctrl+C, Ctrl+A, Ctrl+F, Ctrl+D)."""
        kod = event.GetKeyCode()
        control_lenyomva = event.ControlDown()

        if control_lenyomva and kod == ord("C"):
            self.masolas_vagolapra()
        elif control_lenyomva and kod == ord("F"):
            self.atemeles_allomanyba()
        elif control_lenyomva and kod == ord("D"):
            self.atemeles_deziderataba()
        elif control_lenyomva and kod == ord("A"):
            for i in range(self.tablazat.GetItemCount()):
                self.tablazat.Select(i, on=True)
        elif kod == wx.WXK_SPACE:
            # A szóköz billentyű ne nyissa meg a helyi menüt, de adja hozzá a keresési pufferhez
            self.feldolgoz_kereso_karakter(' ')
        else:
            event.Skip()

    def on_helyi_menu(self, event):
        """Létrehozza és megjeleníti a helyi menüt a kijelölt sorokon."""
        if self.tablazat.GetSelectedItemCount() == 0:
            return

        menu = wx.Menu()
        masolas_item = menu.Append(
            wx.ID_ANY, "Kijelöltek másolása a vágólapra\tCTRL+C"
        )
        atemeles_item = menu.Append(wx.ID_ANY, "Felvétel az állományba\tCTRL+F")
        deziderata_item = menu.Append(wx.ID_ANY, "Felvétel a dezideráta-jegyzékbe\tCTRL+D")

        menu.Bind(
            wx.EVT_MENU, lambda e: self.masolas_vagolapra(), masolas_item
        )
        menu.Bind(
            wx.EVT_MENU, lambda e: self.atemeles_allomanyba(), atemeles_item
        )
        menu.Bind(
            wx.EVT_MENU, lambda e: self.atemeles_deziderataba(), deziderata_item
        )

        self.PopupMenu(menu)
        menu.Destroy()

    def masolas_vagolapra(self):
        """Kiolvassa az összes kijelölt sort és a vágólapra helyezi őket (bezárás után is megmarad)."""
        kijelolt_indexek = osszes_kijelolt_index(self.tablazat)

        if not kijelolt_indexek:
            return

        oszlopok_szama = self.tablazat.GetColumnCount()
        mentendo_sorok = []

        for sor_idx in kijelolt_indexek:
            cella_ertekek = []
            for col_idx in range(oszlopok_szama):
                cella_ertekek.append(
                    self.tablazat.GetItemText(sor_idx, col_idx)
                )
            mentendo_sorok.append("\t".join(cella_ertekek))

        teljes_szoveg = "\n".join(mentendo_sorok)

        if not masolas_vagolapra_szoveg(teljes_szoveg):
            wx.MessageBox(
                "Nem sikerült megnyitni a vágólapot.",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )

    def atemeles_allomanyba(self):
        if not self.parent or not hasattr(self.parent, "db"):
            wx.MessageBox(
                "Az átemelés nem lehetséges, mert a kereső önállóan fut!",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return

        kijelolt_indexek = osszes_kijelolt_index(self.tablazat)

        if not kijelolt_indexek:
            wx.MessageBox(
                "Nincs kijelölve egyetlen elem sem!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_WARNING,
            )
            return

        db = len(kijelolt_indexek)
        if not kerj_tomeges_atemeles_megerositest(self, db, "találatot", "az állományba"):
            return

        excel_oszlopok_szama = len(self.oszlopok) if self.oszlopok else 0
        oszlop_nevek = [
            self.tablazat.GetColumn(i).GetText()
            for i in range(excel_oszlopok_szama)
        ]

        statusz_col_idx = excel_oszlopok_szama

        konyv_adatok = []
        for sor_idx in kijelolt_indexek:
            konyv_adat = {}
            for col_idx in range(excel_oszlopok_szama):
                kulcs = oszlop_nevek[col_idx]
                ertek = self.tablazat.GetItemText(sor_idx, col_idx)
                konyv_adat[kulcs] = ertek

            alap_adat = self._sor_alap_adatta_alakitasa(konyv_adat)
            alap_adat.update({
                "oldalszam": konyv_adat.get("oldalszam", ""),
                "meretek": konyv_adat.get("meretek", ""),
                "kotes": konyv_adat.get("kotes", ""),
                "rovid_cim": konyv_adat.get("rovid_cim", ""),
                "forras": konyv_adat.get("forras", ""),
                "status": konyv_adat.get("status", ""),
                "rovid_leiras": konyv_adat.get("rovid_leiras", ""),
            })
            konyv_adatok.append(alap_adat)

        # A lista frissítését a főablak szűrés-megőrző segédmetódusára
        # bízzuk (ugyanaz, mint kézi felvitelnél vagy JSON importnál), hogy
        # egy esetlegesen aktív szűrés/keresés ne sérüljön az átemelés
        # után - egy sima FeltoltLista() ugyanis figyelmen kívül hagyná az
        # aktív szűrést, és megtévesztő állapotot hagyna maga után (a
        # szűrő-felirat és a "Szűrés törlése" gomb aktív maradna, miközben
        # a teljes, szűretlen lista jelenne meg).
        def _frissites(uj_konyv_objektumok):
            if hasattr(self.parent, "_uj_konyvek_utani_frissites"):
                self.parent._uj_konyvek_utani_frissites(uj_konyv_objektumok)
            elif hasattr(self.parent, "lista"):
                self.parent.lista.FeltoltLista()
                if hasattr(self.parent, "FrissitStatusBar"):
                    self.parent.FrissitStatusBar()

        # A tényleges felvételi ciklust a data_manager.konyvek_tomeges_felvetele
        # közös segédfüggvénye végzi (ugyanaz, mint a Dezideráta-kezelő
        # "Felvétel az állományba" műveleténél).
        sikeres, visszautasitott, sikeres_relativ_indexek, _ = konyvek_tomeges_felvetele(
            self.parent.db, konyv_adatok, utani_frissites_fv=_frissites
        )

        # A sikeresen átemelt sorok "Státusz" oszlopát azonnal frissítjük,
        # hogy ne kelljen új keresést indítani az "Állományban" jelzés
        # megjelenéséhez.
        if self.oszlopok:
            sikeres_sor_indexek = [kijelolt_indexek[i] for i in sikeres_relativ_indexek]
            for sor_idx in sikeres_sor_indexek:
                self.tablazat.SetItem(sor_idx, statusz_col_idx, "Állományban")
                self.tablazat.SetItemBackgroundColour(
                    sor_idx, wx.Colour(220, 245, 220)
                )

        mutass_tomeges_atemeles_eredmenyt(
            self, sikeres, visszautasitott, "az állományhoz", "az állományban"
        )

    def atemeles_deziderataba(self):
        if not self.parent:
            wx.MessageBox(
                "Az átemelés nem lehetséges, mert a kereső önállóan fut!",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return

        kijelolt_indexek = osszes_kijelolt_index(self.tablazat)

        if not kijelolt_indexek:
            wx.MessageBox(
                "Nincs kijelölve egyetlen elem sem!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_WARNING,
            )
            return

        db = len(kijelolt_indexek)
        if not kerj_tomeges_atemeles_megerositest(self, db, "találatot", "a deziderátába"):
            return

        excel_oszlopok_szama = len(self.oszlopok) if self.oszlopok else 0
        oszlop_nevek = [
            self.tablazat.GetColumn(i).GetText()
            for i in range(excel_oszlopok_szama)
        ]

        json_fajl = DEZIDERATA_DATA_FILE

        try:
            adat, ervenyes = load_hmac_json(json_fajl)
        except Exception as e:
            logging.error(f"Hiba a dezideráta adatbázis beolvasásakor: {e}", exc_info=True)
            wx.MessageBox(f"Hiba a dezideráta beolvasásakor:\n{e}", "Hiba", wx.OK | wx.ICON_ERROR)
            return

        if not ervenyes:
            wx.MessageBox(
                "A dezideráta-jegyzék integritás-ellenőrzése sikertelen: a fájl megsérülhetett "
                "vagy jogosulatlanul módosították.\n\nAz átemelés emiatt megszakadt.",
                "Integritási hiba", wx.OK | wx.ICON_ERROR
            )
            return

        deziderata_lista = [x for x in adat if isinstance(x, dict)] if isinstance(adat, list) else []

        sikeres = 0
        visszautasitott = 0

        for sor_idx in kijelolt_indexek:
            konyv_adat = {}
            for col_idx in range(excel_oszlopok_szama):
                kulcs = oszlop_nevek[col_idx]
                ertek = self.tablazat.GetItemText(sor_idx, col_idx)
                konyv_adat[kulcs] = ertek

            alap_adat = self._sor_alap_adatta_alakitasa(konyv_adat)
            alap_adat.update({
                "priority": "Másodlagos",
                "status": "Jelenleg nem kapható",
                "location": "",
                "price": ""
            })

            if alap_adat["cim"].strip():
                mar_letezik = any(is_same_book(alap_adat, item) for item in deziderata_lista)
                if not mar_letezik:
                    deziderata_lista.append(alap_adat)
                    sikeres += 1
                else:
                    visszautasitott += 1

        if not save_hmac_json(json_fajl, deziderata_lista):
            wx.MessageBox(
                "Hiba történt a dezideráta mentése közben.",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return

        if hasattr(self.parent, "deziderata_frame") and self.parent.deziderata_frame is not None:
            self.parent.deziderata_frame.items = deziderata_lista
            self.parent.deziderata_frame.refresh_list()

        mutass_tomeges_atemeles_eredmenyt(
            self, sikeres, visszautasitott, "a dezideráta-jegyzékbe", "a dezideráta-jegyzékben"
        )


if __name__ == "__main__":
    app = wx.App()
    KonyvtarnokKeresoApp(parent=None)
    app.MainLoop()