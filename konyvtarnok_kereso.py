import wx
import logging
from contextlib import nullcontext
from types import SimpleNamespace
from theme_manager import apply_theme_from_settings
from deziderata import (
    DATA_FILE as DEZIDERATA_DATA_FILE,
    deziderata_tetelek_hozzaadasa,
    tetelek_idjainak_potlasa,
)
from data_manager import (
    load_hmac_json,
    save_hmac_json,
    tetelek_egyeznek,
    konyvek_tomeges_felvetele,
    kerj_tomeges_atemeles_megerositest,
    mutass_tomeges_atemeles_eredmenyt,
    sor_alap_adatta_alakitasa,
    allomany_rekord_forras_dictbol,
    deziderata_tetel_forras_dictbol,
    load_kereso_json,
    is_same_book,
    MentesiHiba,
)
from gyors_kereses import GyorsListaKereso, osszes_kijelolt_index
from utils import masolas_vagolapra_szoveg
from menu_bar import KeresoMenuBar

# A Státusz oszlop sorainak háttérszíne (RGB). Ha egy tétel mindkét helyen
# szerepel, az "Állományban" szín az erősebb jelzés.
SZIN_ALLOMANYBAN = (220, 245, 220)
SZIN_DEZIDERATABAN = (255, 243, 205)


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
        # A táblázat soraihoz tartozó EREDETI (forrás) sor-dictek. A
        # táblázat sorainak ListCtrl-adata (SetItemData) erre a listára
        # mutató index. Az átemelés és a státuszfrissítés ebből dolgozik, nem
        # a megjelenített cellaszövegekből (lásd _sor_eredeti_dict).
        self._talalat_sorok = []
        self.adatok = self.adatok_betoltese()

        # Gyorskeresés (gépeléssel ugrás a listában)
        self.gyors_kereses = GyorsListaKereso()

        # UI elemek létrehozása
        self.init_ui()

        menusor = KeresoMenuBar()
        self.SetMenuBar(menusor)
        self.menu_esemenyek_bekotese(menusor)

        # Status bar létrehozása az ablak alján
        self.CreateStatusBar()
        osszesen = len(self.adatok) if self.adatok else 0
        self.SetStatusText(f"Keresés {osszesen} kötet adataiban")

        # Téma alkalmazása - a Show()-t csak EZUTÁN hívjuk (lásd az init_ui
        # végén lévő kommentet).
        config = apply_theme_from_settings(self)
        self.current_theme = config.get("tema", "vilagos")
        self.Show()

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

    def _tablazat_uritese(self):
        """Kiüríti a találati táblázatot és az eredeti sor-dictek tárolóját."""
        self.tablazat.DeleteAllItems()
        self._talalat_sorok = []

    def _sor_eredeti_dict(self, sor_index):
        """Visszaadja a táblázat adott sorához tartozó EREDETI forrás-dictet.

        A megjelenített cellaszövegekből nem lehet hűen visszaépíteni a
        könyvet (a nem látható mezők elvesznének), ezért minden sor mellé
        eltároljuk a forrás dictjét. Ha ez valamiért nem érhető el, a
        látható cellákból épített dict a tartalék."""
        kulcs = self.tablazat.GetItemData(sor_index)
        if 0 <= kulcs < len(self._talalat_sorok):
            return self._talalat_sorok[kulcs]
        return {
            oszlop: self.tablazat.GetItemText(sor_index, col_idx)
            for col_idx, oszlop in enumerate(self.oszlopok)
        }

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

    def _van_egyezes(self, sor_adat, cim_oszlop_neve, cim_szerint, egyezes_fv):
        """Közös egyezés-vizsgálat: a cím szerint előszűrt csoportban
        (cim_szerint) megkeresi, van-e olyan tétel, amelyre az egyezes_fv
        (tetelek_egyeznek / is_same_book) igazat ad a sor kanonikus alakjára."""
        if not cim_oszlop_neve:
            return False
        sor_cime = str(sor_adat.get(cim_oszlop_neve, "")).strip().lower()
        if not sor_cime or sor_cime not in cim_szerint:
            return False
        sor_alap_adat = self._sor_alap_adatta_alakitasa(sor_adat)
        return any(egyezes_fv(sor_alap_adat, tetel) for tetel in cim_szerint[sor_cime])

    def _allomanyban_van_e(self, sor_adat, cim_oszlop_neve, konyvek_cim_szerint):
        """Eldönti, hogy egy sor (a táblázatból vagy a nyers keresési
        adatokból kiolvasott dict) szerepel-e már az állományban.

        A cím szerinti előszűrés (konyvek_cim_szerint) után a teljes,
        több mezőt (szerző, kiadó, hely, év) is figyelembe vevő
        tetelek_egyeznek vizsgálattal dönt, nem csak a cím alapján."""
        return self._van_egyezes(
            sor_adat, cim_oszlop_neve, konyvek_cim_szerint, tetelek_egyeznek
        )

    def _deziderataban_van_e(self, sor_adat, cim_oszlop_neve, dezi_cim_szerint):
        """Eldönti, hogy egy sor szerepel-e már a dezideráta-jegyzékben (a
        Dezideráta-kezelő saját duplikátum-ellenőrzésével, is_same_book)."""
        return self._van_egyezes(
            sor_adat, cim_oszlop_neve, dezi_cim_szerint, is_same_book
        )

    # ==========================================================================
    # DEZIDERÁTA-JEGYZÉK ELÉRÉSE (a Dezideráta-kezelő ablak lehet zárva is)
    # ==========================================================================

    def _deziderata_tetelek(self):
        """Visszaadja a dezideráta-jegyzék aktuális tételeit: (tételek, olvashato).

        A Dezideráta-kezelő ablak nem feltétlenül van nyitva a kereső
        futásakor (a főablakkal ellentétben), ezért két ág van:
        - ha az ablak nyitva van, a memóriabeli listáját (items) használjuk,
          mert az mindig a legfrissebb (minden módosítás után azonnal mentődik);
        - ha zárva van, a deziderata.json fájlt olvassuk be, a HMAC
          integritás-ellenőrzéssel együtt (ugyanúgy, mint az
          atemeles_deziderataba).

        Ha a fájl nem olvasható vagy az aláírása érvénytelen, üres listát és
        olvashato=False értéket adunk vissza (a hibát csak naplózzuk, mert a
        státusz-frissítés minden keresésnél lefut, és nem szabad minden
        alkalommal felugró ablakkal zavarni a felhasználót)."""
        frame = getattr(self.parent, "deziderata_frame", None) if self.parent else None
        if frame is not None and not getattr(frame, "_mentes_tiltva", False):
            return [x for x in frame.items if isinstance(x, dict)], True

        try:
            adat, ervenyes = load_hmac_json(DEZIDERATA_DATA_FILE)
        except Exception as e:
            logging.warning(f"A dezideráta-jegyzék nem olvasható a státuszhoz: {e}")
            return [], False
        if not ervenyes:
            logging.warning(
                "A dezideráta-jegyzék HMAC-aláírása érvénytelen, "
                "a 'Deziderátában' jelzés nem elérhető."
            )
            return [], False
        if not isinstance(adat, list):
            return [], True
        return [x for x in adat if isinstance(x, dict)], True

    @staticmethod
    def _csoportosit_cim_szerint(tetelek):
        """Tételek cím szerinti csoportosítása (kisbetűsen, levágva). A
        dezideráta régi, angol kulcsú tételeit (title) is felismeri."""
        csoportok = {}
        for t in tetelek:
            cim = str(t.get("cim", t.get("title", ""))).strip().lower()
            if cim:
                csoportok.setdefault(cim, []).append(t)
        return csoportok

    def _statusz_kontextus(self):
        """Egyszer felépíti mindazt, ami egy sor-csoport státuszának
        kiszámításához kell (az állomány és a dezideráta cím szerinti
        csoportosítása), hogy soronként ne kelljen újra összeállítani."""
        dezi_tetelek, dezi_olvashato = self._deziderata_tetelek()
        return SimpleNamespace(
            cim_oszlop=self._cim_oszlop_neve(),
            konyvek=self._epit_konyvek_cim_szerint(),
            dezi=self._csoportosit_cim_szerint(dezi_tetelek),
            dezi_olvashato=dezi_olvashato,
        )

    def _statusz_beallitasa(self, sor_index, sor_adat, ctx):
        """Kiszámolja és beírja egy táblázatsor Státusz cellájába, hogy a
        tétel az állományban és/vagy a deziderátában szerepel-e, és ennek
        megfelelően színezi a sort."""
        van_allomany = self._allomanyban_van_e(sor_adat, ctx.cim_oszlop, ctx.konyvek)
        van_dezi = self._deziderataban_van_e(sor_adat, ctx.cim_oszlop, ctx.dezi)

        cimkek = []
        if van_allomany:
            cimkek.append("Állományban")
        if van_dezi:
            cimkek.append("Deziderátában")

        if van_allomany:
            hatter = wx.Colour(*SZIN_ALLOMANYBAN)
        elif van_dezi:
            hatter = wx.Colour(*SZIN_DEZIDERATABAN)
        else:
            hatter = wx.NullColour

        self.tablazat.SetItem(sor_index, len(self.oszlopok), ", ".join(cimkek))
        self.tablazat.SetItemBackgroundColour(sor_index, hatter)


    def init_ui(self):
        fő_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Kereső sáv ---
        kereso_szoveg = wx.StaticText(
            self.panel, label="Keresendő kifejezés:"
        )
        self.kereso_mezo = wx.TextCtrl(self.panel, style=wx.TE_PROCESS_ENTER)
        self.kereso_mezo.Bind(wx.EVT_TEXT_ENTER, self.on_kereses)
        self.kereso_mezo.Bind(wx.EVT_TEXT, self.on_szoveg_valtozas)

        self.btn_kereses_torlese = wx.Button(self.panel, label="Keresés törlése")
        self.btn_kereses_torlese.Enable(False)
        self.btn_kereses_torlese.Bind(wx.EVT_BUTTON, self.on_kereses_torlese)

        kereso_gomb = wx.Button(self.panel, label="Keresés")
        kereso_gomb.Bind(wx.EVT_BUTTON, self.on_kereses)

        kereso_sizer = wx.BoxSizer(wx.HORIZONTAL)
        kereso_sizer.Add(
            kereso_szoveg,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            border=5,
        )
        kereso_sizer.Add(self.kereso_mezo, proportion=1, flag=wx.EXPAND)
        kereso_sizer.Add(self.btn_kereses_torlese, flag=wx.LEFT, border=5)
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
                statusz_col_idx, "Státusz", width=200
            )
        else:
            self.tablazat.InsertColumn(0, "Üzenet", width=400)

        fő_sizer.Add(
            self.tablazat, proportion=1, flag=wx.EXPAND | wx.ALL, border=10
        )

        # --- Gombsor ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_masolas_vagolapra = wx.Button(
            self.panel, label="Másolás vágólapra"
        )
        self.btn_atemeles_allomanyba = wx.Button(
            self.panel, label="Átemelés az állományba"
        )
        self.btn_atemeles_deziderataba = wx.Button(
            self.panel, label="Átemelés a Deziderátába"
        )

        btn_sizer.Add(self.btn_masolas_vagolapra, 0, wx.RIGHT, 10)
        btn_sizer.Add(self.btn_atemeles_allomanyba, 0, wx.RIGHT, 10)
        btn_sizer.Add(self.btn_atemeles_deziderataba, 0, wx.RIGHT, 10)

        fő_sizer.Add(btn_sizer, 0, wx.ALIGN_LEFT | wx.ALL, 10)

        self.btn_masolas_vagolapra.Bind(
            wx.EVT_BUTTON, lambda e: self.masolas_vagolapra()
        )
        self.btn_atemeles_allomanyba.Bind(
            wx.EVT_BUTTON, lambda e: self.atemeles_allomanyba()
        )
        self.btn_atemeles_deziderataba.Bind(
            wx.EVT_BUTTON, lambda e: self.atemeles_deziderataba()
        )
        # ---------------------------------------------

        self.panel.SetSizer(fő_sizer)
        self.kereso_mezo.SetFocus()
        self.Centre()
        # A Show()-t szándékosan NEM itt hívjuk meg: a __init__ csak a téma
        # alkalmazása (apply_theme_from_settings) UTÁN jeleníti meg az
        # ablakot, ugyanúgy, mint a Deziderata és a Konyvtarnok főablak -
        # így elkerülhető, hogy az ablak egy pillanatra a világos
        # alapértelmezett témával villanjon fel, mielőtt a beállított téma
        # (pl. sötét/pasztell) alkalmazásra kerülne.

    def menu_esemenyek_bekotese(self, menusor):
        """A menüsor elemeinek bekötése. A gyorsbillentyűket (Ctrl+C,
        Ctrl+D, Ctrl+F, Ctrl+W) maguk a menüelemek hordozzák, ezért külön
        gyorsítótábla nem szükséges."""
        self.Bind(wx.EVT_MENU, self.on_menu_masolas, menusor.copy)
        self.Bind(wx.EVT_MENU, self.on_menu_deziderata, menusor.deziderata)
        self.Bind(wx.EVT_MENU, self.on_menu_allomany, menusor.allomany)
        self.Bind(wx.EVT_MENU, self.on_kilepes, menusor.kilepes)

    def on_menu_masolas(self, event):
        """Fájl > Másolás. Ha a keresőmezőben áll a fókusz, annak saját
        szövegét másolja (különben a menü Ctrl+C-je elnyelné a szokásos
        szövegmásolást), egyébként a kijelölt találatokat."""
        fokusz = self.FindFocus()
        if isinstance(fokusz, wx.TextCtrl):
            fokusz.Copy()
            return
        self.masolas_vagolapra()

    def on_menu_deziderata(self, event):
        """Fájl > Átemelés a Deziderátába."""
        self.atemeles_deziderataba()

    def on_menu_allomany(self, event):
        """Fájl > Átemelés az állományba."""
        self.atemeles_allomanyba()

    def on_kilepes(self, event):
        self.Close()

    def frissit_akadalymentesites(self, darabszam):
        """Beállítja a táblázat belső nevét és a felette lévő feliratot."""
        szoveg = f"Találatok listája, {darabszam} elem"
        self.eredmeny_szoveg.SetLabel(f"Találatok ({darabszam} db):")
        self.tablazat.SetName(szoveg)

    def frissit_torles_gomb_allapot(self):
        """Engedélyezi a törlés gombot, ha van szöveg a mezőben vagy van találat a táblázatban."""
        van_szoveg = bool(self.kereso_mezo.GetValue().strip())
        van_talalat = self.tablazat.GetItemCount() > 0
        self.btn_kereses_torlese.Enable(van_szoveg or van_talalat)

    def on_szoveg_valtozas(self, event):
        """Ha a felhasználó kiüríti a keresőmezőt, a táblázat is kiürül, és frissül a törlés gomb."""
        if not self.kereso_mezo.GetValue().strip():
            self._tablazat_uritese()
            self.frissit_akadalymentesites(0)
        self.frissit_torles_gomb_allapot()
        event.Skip()

    def on_kereses_torlese(self, event):
        """Kiüríti a keresőmezőt és a találati táblázatot, majd fókuszba helyezi a mezőt."""
        self.kereso_mezo.Clear()
        self._tablazat_uritese()
        self.frissit_akadalymentesites(0)
        self.frissit_torles_gomb_allapot()
        self.btn_kereses_torlese.Enable(False)
        self.kereso_mezo.SetFocus()

    def on_kereses(self, event):
        """A keresés logikája gombnyomásra vagy Enterre (Pandas nélkül)."""
        self._tablazat_uritese()

        if self.adatok is None:
            wx.MessageBox(
                "Nincs betöltött adat!", "Hiba", wx.OK | wx.ICON_ERROR
            )
            return

        keresett_szo = self.kereso_mezo.GetValue().strip().lower()
        if not keresett_szo:
            wx.MessageBox(
                "Adja meg a keresendő kifejezést!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        kijelolt_oszlopok = [
            oszlop for oszlop, cb in self.checkboxok.items() if cb.GetValue()
        ]

        if not kijelolt_oszlopok:
            wx.MessageBox(
                "Jelöljön ki legalább egy oszlopot a kereséshez!",
                "Nincs kijelölve oszlop",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        # Szűrés tisztán Python listával (Pandas DataFrame helyett).
        # A kifejezést szavakra bontjuk: egy sor akkor találat, ha MINDEN szó
        # szerepel a kijelölt oszlopok valamelyikében (nem feltétlenül
        # ugyanabban az oszlopban). Pl. a "Kodály Rózsavölgyi" akkor is talál,
        # ha a két név külön oszlopban van.
        szavak = keresett_szo.split()
        szurt_adatok = []
        for sor in self.adatok:
            ertekek = [str(sor.get(oszlop, "")).lower() for oszlop in kijelolt_oszlopok]
            if all(any(szo in ertek for ertek in ertekek) for szo in szavak):
                szurt_adatok.append(sor)

        if szurt_adatok:
            talalatok_szama = len(szurt_adatok)
            statusz_ctx = self._statusz_kontextus()
            if statusz_ctx.dezi_olvashato:
                self.SetStatusText(f"Keresés {len(self.adatok)} kötet adataiban")
            else:
                self.SetStatusText(
                    "A dezideráta-jegyzék nem olvasható, ezért a "
                    "\u201eDeziderátában\u201d jelzés nem elérhető."
                )

            for sor in szurt_adatok:
                # Sor beszúrása a táblázatba
                elsocsella = str(sor.get(self.oszlopok[0], ""))
                sor_index = self.tablazat.InsertItem(
                    self.tablazat.GetItemCount(), elsocsella
                )
                self._talalat_sorok.append(sor)
                self.tablazat.SetItemData(sor_index, len(self._talalat_sorok) - 1)
                for col_idx, col_name in enumerate(self.oszlopok[1:], start=1):
                    self.tablazat.SetItem(
                        sor_index, col_idx, str(sor.get(col_name, ""))
                    )

                # UTOLSÓ OSZLOP: Státusz (Állományban / Deziderátában)
                self._statusz_beallitasa(sor_index, sor, statusz_ctx)

            self.frissit_akadalymentesites(talalatok_szama)
        else:
            self.frissit_akadalymentesites(0)

        if self.tablazat.GetItemCount() > 0:
            for i in range(self.tablazat.GetItemCount()):
                self.tablazat.Select(i, on=False)

        self.btn_kereses_torlese.Enable(True)
        self.tablazat.SetFocus()

    def frissit_statuszokat(self):
        """Újraszámolja és frissíti a táblázatban JELENLEG megjelenő (már
        korábbi kereséskor betöltött) találatok 'Állományban' és
        'Deziderátában' státuszát, az állomány és a dezideráta-jegyzék
        aktuális állapota alapján - anélkül, hogy új keresést kellene
        indítani.

        Ezt hívja meg a főablak minden olyan művelet (könyv törlése,
        szerkesztése, felvétele) után, amely megváltoztathatja az
        állományt, valamint a Dezideráta-kezelő minden mentése után (lásd
        Konyvtarnok.frissit_kereso_statuszokat). E hívás nélkül a kereső
        ablak - ha nyitva marad - téves jelzést mutathatna egy időközben
        törölt vagy átemelt tételre, egészen a következő kereső gomb
        megnyomásáig.

        Az egyezés-vizsgálat logikáját a közös segédmetódusok végzik,
        amelyeket az on_kereses is használ, hogy a két hely soha ne térjen
        el egymástól."""
        if not self.oszlopok:
            return

        sorok_szama = self.tablazat.GetItemCount()
        if sorok_szama == 0:
            return

        ctx = self._statusz_kontextus()

        for sor_index in range(sorok_szama):
            # A sor eredeti forrás-dictjéből dolgozunk (lásd _sor_eredeti_dict).
            self._statusz_beallitasa(sor_index, self._sor_eredeti_dict(sor_index), ctx)

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

    def _undo_csoport(self, leiras):
        """Visszavonható lépés a dezideráta módosítására ZÁRT ablaknál (a
        nyitott ablak a tetelek_felvetele-ben maga rögzíti). Zárt ablaknál a
        lépés a főablak verembe kerül."""
        undo = getattr(getattr(self.parent, "db", None), "undo", None)
        return undo.muvelet(leiras, ["deziderata"]) if undo is not None else nullcontext()

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
                "Nincs kijelölve egyetlen találat sem!",
                "Nincs kijelölt találat",
                wx.OK | wx.ICON_WARNING,
            )
            return

        db = len(kijelolt_indexek)
        if not kerj_tomeges_atemeles_megerositest(self, db, "találatot", "az állományba"):
            return

        # Az eredeti forrás-dictből építünk (nem a cellaszövegekből), az
        # ismeretlen mezők (pl. "megjegyzes") kiszűrésével - lásd
        # data_manager.allomany_rekord_forras_dictbol.
        konyv_adatok = [
            allomany_rekord_forras_dictbol(self._sor_eredeti_dict(sor_idx))
            for sor_idx in kijelolt_indexek
        ]

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
        # "Felvétel az állományba" műveleténél). Ha a mentés (lemezre írás)
        # meghiúsul, a data_manager.MentesiHiba kivételt kapjuk - ezt
        # szándékosan külön kezeljük, hogy ne keveredjen össze a
        # duplikátum miatti elutasítással (lásd data_manager.MentesiHiba).
        try:
            sikeres, visszautasitott, sikeres_relativ_indexek, _ = konyvek_tomeges_felvetele(
                self.parent.db, konyv_adatok, utani_frissites_fv=_frissites
            )
        except MentesiHiba as e:
            wx.MessageBox(
                f"Hiba történt az állományjegyzék mentése közben:\n{e}\n\n"
                "A már sikeresen felvett tételek megmaradnak, de a további "
                "kijelölt tételek felvétele emiatt megszakadt.",
                "Mentési hiba",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return

        # A "Státusz" oszlopot azonnal frissítjük, hogy ne kelljen új
        # keresést indítani az "Állományban" jelzés megjelenéséhez. A
        # teljes frissítés (a sorok kézi átírása helyett) azért kell, hogy
        # egy már a deziderátában is szereplő tétel "Deziderátában" jelzése
        # ne vesszen el.
        self.frissit_statuszokat()

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
                "Nincs kijelölve egyetlen találat sem!",
                "Nincs kijelölés",
                wx.OK | wx.ICON_WARNING,
            )
            return

        db = len(kijelolt_indexek)
        if not kerj_tomeges_atemeles_megerositest(self, db, "találatot", "a deziderátába"):
            return

        # A felvételre szánt tételek: a forrás eredeti dictjéből, fehérlistásan
        # (lásd deziderata_tetel_forras_dictbol). Az id-t és a duplikátum-
        # szűrést a deziderata.deziderata_tetelek_hozzaadasa adja, ugyanaz
        # nyitott és zárt Dezideráta-ablaknál.
        uj_tetelek = [
            deziderata_tetel_forras_dictbol(self._sor_eredeti_dict(sor_idx))
            for sor_idx in kijelolt_indexek
        ]

        frame = getattr(self.parent, "deziderata_frame", None)
        try:
            frame_nyitva = frame is not None and bool(frame)  # megsemmisült wx ablak -> False
        except RuntimeError:
            frame_nyitva = False

        if frame_nyitva and not getattr(frame, "_mentes_tiltva", False):
            # NYITOTT, használható ablak: a memóriabeli listáját módosítjuk
            # (a mentést és a lista frissítését is ő végzi), nem a lemezről
            # olvasott másolatot írjuk felül - így nem veszhet el egy még
            # el nem mentett/épp szerkesztett állapot, és az id-k egyeznek.
            eredmeny = frame.tetelek_felvetele(uj_tetelek)
            if eredmeny is None:
                return  # a hibát (letiltás / mentési hiba) az ablak már jelezte
            sikeres, visszautasitott = eredmeny
        else:
            # ZÁRT ablak (vagy betöltési hiba miatt letiltott ablak): a
            # fájlt közvetlenül, HMAC-ellenőrzéssel olvassuk és írjuk.
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

            with self._undo_csoport("átemelés a deziderátába"):
                deziderata_lista = [x for x in adat if isinstance(x, dict)] if isinstance(adat, list) else []
                # A meglévő, még id nélküli tételek is megkapják az id-t.
                tetelek_idjainak_potlasa(deziderata_lista)
                sikeres, visszautasitott, _ = deziderata_tetelek_hozzaadasa(
                    deziderata_lista, uj_tetelek
                )

                if sikeres:
                    if not save_hmac_json(json_fajl, deziderata_lista):
                        wx.MessageBox(
                            "Hiba történt a dezideráta mentése közben.",
                            "Hiba",
                            wx.OK | wx.ICON_ERROR,
                        )
                        return
                    # Letiltott (de még nyitott) ablaknál a most érvényes fájlt
                    # újratöltjük, ami fel is oldja a letiltást.
                    if frame_nyitva:
                        frame.load_data()

        # Az átemelt sorok azonnal "Deziderátában" jelzést kapnak.
        self.frissit_statuszokat()

        mutass_tomeges_atemeles_eredmenyt(
            self, sikeres, visszautasitott, "a dezideráta-jegyzékbe", "a dezideráta-jegyzékben"
        )


if __name__ == "__main__":
    app = wx.App()
    KonyvtarnokKeresoApp(parent=None)
    app.MainLoop()
