import os
import re
import wx
import logging
from contextlib import nullcontext
from types import SimpleNamespace
from constants import KERESO_APP_TITLE
from theme_manager import apply_theme_from_settings
from config_manager import load_settings, save_settings, beallitas_mentese
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
    deziderata_regi_kulcsok_atalakitasa,
    load_kereso_json,
    kereso_cim_oszlop,
    KeresoJsonHiba,
    KERESO_JSON_FIGYELMEZTETO_MERET,
    is_same_book,
    MentesiHiba,
    allomany_szerkesztheto,
    undo_lepes,
)
from gyors_kereses import GyorsListaKereso, osszes_kijelolt_index
from help import sugo_megnyitasa
from settings import azonos_utvonal, beallitasok_megnyitasa_gyermekbol
from utils import masolas_vagolapra_szoveg, osszetett_rendezesi_kulcs
from menu_bar import KeresoMenuBar
from undo_manager import (
    UndoKezelo, frissit_undo_menu, szovegmezo_visszavonas,
)

# A Státusz oszlop sorainak háttérszíne (RGB). Ha egy tétel mindkét helyen
# szerepel, az "Állományban" szín az erősebb jelzés.
SZIN_ALLOMANYBAN = (220, 245, 220)
SZIN_DEZIDERATABAN = (255, 243, 205)


class KonyvtarnokKeresoApp(wx.Frame):
    def __init__(self, parent=None):
        # Az ablakcímet a _allapot_frissitese állítja be (még a Show() előtt).
        super().__init__(parent=parent, size=(1000, 600))

        self.parent = parent
        self.SetName(KERESO_APP_TITLE)

        # Visszavonás/mégis: a kereső csak a SAJÁT átemeléseit (állományba,
        # deziderátába) vonja vissza és ismétli meg. A kezelőnek nincs saját
        # tárolója (üres lista), így mások lépései nem kerülnek a vermébe; a
        # saját lépések viszont a főablak / a Dezideráta-ablak vermébe is
        # bekerülnek (kapcsolt lépések), ezért onnan is visszavonhatók.
        # Önálló futásnál (parent=None) nincs regiszter: nincs undo.
        regiszter = getattr(getattr(parent, "db", None), "undo_regiszter", None)
        self.undo = (
            UndoKezelo(regiszter, [], sajat_lepesek=True) if regiszter is not None else None
        )
        self.Bind(wx.EVT_CLOSE, self.on_close)

        self.panel = wx.Panel(self)
        self.panel.SetName("Főpanel")

        # 1. Az adatbázis (a felhasználó által megnyitott JSON) még üres; a
        # betöltés az ablak felépítése után történik (lásd lentebb), mert a
        # jelölőnégyzetek és a táblázat oszlopai a fájl oszlopaiból épülnek.
        self.oszlopok = []
        self.adatok = None
        self.json_utvonal = ""
        # A táblázat soraihoz tartozó EREDETI (forrás) sor-dictek. A
        # táblázat sorainak ListCtrl-adata (SetItemData) erre a listára
        # mutató index. Az átemelés és a státuszfrissítés ebből dolgozik, nem
        # a megjelenített cellaszövegekből (lásd _sor_eredeti_dict).
        self._talalat_sorok = []
        # A találati lista üres keresőmezőnél: "ures" | "osszes" (lásd a
        # Beállítások > KönyvTárnok-kereső fület és az _alapallapot_beallitasa-t).
        self.inditasi_lista = "ures"
        # Igaz, ha a táblázat jelenleg az alaplistát ("összes tétel") mutatja;
        # így az üres mező további szövegeseményei nem építik újra feleslegesen.
        self._alaplista_latszik = False
        # A legutóbbi keresés (vagy az alaplista) SZŰRETLEN, rendezetlen
        # eredménye. A Nézet menü rendezése és Státusz szűrése ebből építi
        # újra a táblázatot, új keresés nélkül.
        self._nyers_talalatok = []
        # Nézet: a választott rendezés (a beállításokból töltődik, lásd
        # lentebb) és a Státusz szűrés ("osszes" | "allomanyban" |
        # "deziderataban" | "egyikben_sem"; ez szándékosan nem mentődik,
        # indításkor "osszes").
        self.rendezes_kulcs = "cim"
        self.szuro_statusz = "osszes"
        self._rendezes_mentes_hiba_jelezve = False

        # Gyorskeresés (gépeléssel ugrás a listában)
        self.gyors_kereses = GyorsListaKereso()

        # UI elemek létrehozása
        self.init_ui()

        menusor = KeresoMenuBar()
        self.menusor = menusor
        self.SetMenuBar(menusor)
        self.menu_esemenyek_bekotese(menusor)

        # Az utoljára választott rendezés (ismeretlen/sérült érték esetén cím).
        # A betöltés előtt kell, mert az alaplista már ezzel épül fel.
        alap_rendezes = load_settings().get("kereso_rendezes", "cim")
        if alap_rendezes not in menusor.rendezes_elemek:
            alap_rendezes = "cim"
        self.rendezes_kulcs = alap_rendezes
        menusor.RendezesJelolese(alap_rendezes)

        # Status bar létrehozása az ablak alján
        self.CreateStatusBar()

        # A korábban megnyitott adatbázis betöltése (ha van); a téma
        # alkalmazása ELŐTT, hogy a most épített elemek is megkapják.
        self._betoltes_indulaskor()

        # Téma alkalmazása - a Show()-t csak EZUTÁN hívjuk (lásd az init_ui
        # végén lévő kommentet).
        config = apply_theme_from_settings(self)
        self.current_theme = config.get("tema", "vilagos")
        self.Show()

    # ==========================================================================
    # ADATBÁZIS (A FELHASZNÁLÓ ÁLTAL MEGNYITOTT JSON) KEZELÉSE
    # ==========================================================================
    def _allapot_frissitese(self):
        """Az ablakcím és az állapotsor beállítása a betöltött adatbázis szerint."""
        if self.adatok is None:
            self.SetTitle(KERESO_APP_TITLE)
            self.SetStatusText(
                "Nincs megnyitott adatbázis, használja a Fájl > Adatbázis megnyitása menüpontot)."
            )
        else:
            nev = os.path.basename(self.json_utvonal)
            self.SetTitle(f"{KERESO_APP_TITLE} – {nev}")
            self.SetStatusText(
                f"Keresés {len(self.adatok)} kötet adataiban, forrás: {nev}"
            )

    def _betoltes_indulaskor(self):
        """Megpróbálja betölteni a beállításokban tárolt adatbázist. Ha nincs
        beállított útvonal, vagy a fájl hiányzik, NEM dob fel ablakot, csak az
        állapotsor jelez; sérült fájlnál viszont hibaüzenet jelenik meg."""
        beallitasok = load_settings()
        self.inditasi_lista = self._ervenyes_inditasi_lista(
            beallitasok.get("kereso_inditasi_lista")
        )
        utvonal = beallitasok.get("kereso_json_utvonal", "")
        self._allapot_frissitese()
        if not utvonal:
            return
        if not os.path.isfile(utvonal):
            self.SetStatusText(
                f"A korábban megnyitott adatbázis nem található: {utvonal} "
                "(új megnyitása: Ctrl+O)."
            )
            return
        self._adatbazis_betoltese(utvonal, indulaskor=True)

    def adatbazis_megnyitasa(self):
        """Fájlválasztó + betöltés. True, ha sikerült új adatbázist megnyitni."""
        utvonal = load_settings().get("kereso_json_utvonal", "")
        kezdo_mappa = os.path.dirname(utvonal) if utvonal else ""
        if kezdo_mappa and not os.path.isdir(kezdo_mappa):
            kezdo_mappa = ""
        with wx.FileDialog(
            self,
            "Keresési adatbázis megnyitása",
            defaultDir=kezdo_mappa,
            wildcard="JSON fájlok (*.json)|*.json|Minden fájl (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return False
            kivalasztott = dlg.GetPath()
        return self._adatbazis_betoltese(kivalasztott)

    def _adatbazis_betoltese(self, utvonal, indulaskor=False):
        """Betölti és érvényesíti a megadott JSON-t. Hiba esetén a korábbi
        adatbázis és a mentett útvonal VÁLTOZATLAN marad. True, ha sikerült."""
        if not indulaskor:
            try:
                meret = os.path.getsize(utvonal)
            except OSError:
                meret = 0
            if meret > KERESO_JSON_FIGYELMEZTETO_MERET:
                valasz = wx.MessageBox(
                    f"A fájl nagy ({meret // (1024 * 1024)} MB), a megnyitás eltarthat "
                    "egy ideig. Folytatja?",
                    "Nagy fájl",
                    wx.YES_NO | wx.ICON_QUESTION,
                    self,
                )
                if valasz != wx.YES:
                    return False

        try:
            oszlopok, adatok = load_kereso_json(utvonal)
        except KeresoJsonHiba as e:
            wx.MessageBox(str(e), "Az adatbázis nem nyitható meg",
                          wx.OK | wx.ICON_ERROR, self)
            return False
        except Exception as e:
            logging.error("Váratlan hiba a kereső JSON betöltésekor", exc_info=True)
            wx.MessageBox(f"Váratlan hiba a fájl beolvasásakor:\n{e}",
                          "Hiba", wx.OK | wx.ICON_ERROR, self)
            return False

        # Innentől a betöltés sikeres: az állapot módosítása.
        self.oszlopok = oszlopok
        self.adatok = adatok
        self.json_utvonal = os.path.abspath(utvonal)

        # Az oszlopok újraépítése UTÁN jön az alapállapot (üres lista vagy az
        # összes tétel, a beállítástól függően): a sorok az új oszlopokra épülnek.
        self._tablazat_uritese()
        self._checkboxok_epitese()
        self._tablazat_oszlopai_epitese()
        self._alapallapot_beallitasa(ujra=True)
        self.frissit_torles_gomb_allapot()
        self.panel.Layout()
        self._allapot_frissitese()

        if not indulaskor:
            config = load_settings()
            config["kereso_json_utvonal"] = self.json_utvonal
            save_settings(config)
            # A most létrehozott jelölőnégyzetek is kapják meg az aktuális témát.
            apply_theme_from_settings(self)
            self.kereso_mezo.SetFocus()
        return True

    def _checkboxok_epitese(self):
        """(Újra)építi a keresési oszlopokat választó jelölőnégyzeteket a
        betöltött oszlopok alapján."""
        self.checkbox_sizer.Clear(delete_windows=True)
        self.checkboxok = {}
        self.cb_osszes_oszlop = None
        if self.oszlopok:
            # "Összes oszlop" jelölőnégyzet az oszlop-jelölőnégyzetek előtt:
            # bejelölése minden oszlopot kijelöl, a pipa kivétele pedig
            # mindegyikből kiveszi a pipát.
            self.cb_osszes_oszlop = wx.CheckBox(self.panel, label="Összes &oszlop")
            self.cb_osszes_oszlop.SetValue(True)
            self.cb_osszes_oszlop.Bind(wx.EVT_CHECKBOX, self.on_osszes_oszlop)
            self.checkbox_sizer.Add(self.cb_osszes_oszlop, flag=wx.RIGHT, border=10)

            for oszlop in self.oszlopok:
                cb = wx.CheckBox(self.panel, label=str(oszlop))
                cb.SetValue(True)
                cb.Bind(wx.EVT_CHECKBOX, self.on_oszlop_checkbox)
                self.checkbox_sizer.Add(cb, flag=wx.RIGHT, border=10)
                self.checkboxok[oszlop] = cb

            # Tabulátorsorrend: a jelölőnégyzetek a keresőmező és a két gomb
            # UTÁN jönnek (vizuálisan változatlanul a helyükön maradnak). Új
            # adatbázis betöltésekor a jelölőnégyzetek újraépülnek, és
            # létrehozási sorrendjük szerint a táblázat és a gombsor mögé
            # kerülnének, ezért itt kifejezetten visszahelyezzük őket.
            elozo = self.btn_kereses
            for cb in [self.cb_osszes_oszlop, *self.checkboxok.values()]:
                cb.MoveAfterInTabOrder(elozo)
                elozo = cb
        else:
            nincs_adat = wx.StaticText(
                self.panel,
                label="Nincs megnyitott adatbázis (Fájl > Adatbázis megnyitása, Ctrl+O).",
            )
            self.checkbox_sizer.Add(nincs_adat)

    def _tablazat_oszlopai_epitese(self):
        """(Újra)építi a találati táblázat oszlopait a betöltött oszlopok alapján."""
        self.tablazat.DeleteAllColumns()
        if self.oszlopok:
            for i, oszlop in enumerate(self.oszlopok):
                self.tablazat.InsertColumn(i, str(oszlop), width=130)
            self.tablazat.InsertColumn(len(self.oszlopok), "Státusz", width=200)
        else:
            self.tablazat.InsertColumn(0, "Üzenet", width=400)

    def _sor_alap_adatta_alakitasa(self, forras_dict):
        """Egy nyers sor (a keresési JSON-ból vagy a táblázatból kiolvasott
        dict) leképezése az állomány kanonikus (cim, szerzo, kiado, hely,
        ev, ...) mezőneveire (lásd data_manager.sor_alap_adatta_alakitasa)."""
        return sor_alap_adatta_alakitasa(forras_dict)

    def _tablazat_uritese(self):
        """Kiüríti a találati táblázatot és az eredeti sor-dictek tárolóját."""
        self.tablazat.DeleteAllItems()
        self._talalat_sorok = []
        self._nyers_talalatok = []
        self._alaplista_latszik = False

    @staticmethod
    def _ervenyes_inditasi_lista(ertek):
        """A beállított érték ellenőrzése: ismeretlen érték esetén "ures"."""
        return ertek if ertek in ("ures", "osszes") else "ures"

    def _sorok_megjelenitese(self, sorok, alaplista=False):
        """Egy új találati halmaz megjelenítése: a nyers találatokat eltárolja
        (a Nézet menü ebből építi újra a táblázatot), majd a jelenlegi
        rendezéssel és Státusz szűréssel kirajzolja. Közös a keresés
        (találatok) és az alaplista ("összes tétel" mód) számára, hogy a két
        megjelenítés ne térhessen el."""
        self._nezet_kirajzolasa(list(sorok), alaplista)

    def _rendez_es_szur(self, nyers_sorok, statusz_ctx):
        """A nyers találatokból a megjelenítendő sorok: Státusz szerint szűrve,
        a választott rendezéssel (a főlistával és a Dezideráta-kezelővel azonos
        összetett kulccsal, a sor kanonikus mezőin). Visszatérés: (sorok,
        {id(sor): (állományban, deziderátában)}) - utóbbi csak szűrésnél
        töltött, hogy a kirajzolás ne számolja újra a státuszt."""
        statuszok = {}
        sorok = nyers_sorok
        if self.szuro_statusz != "osszes":
            feltetel = self._STATUSZ_SZURO_FELTETELEK[self.szuro_statusz]
            sorok = []
            for sor in nyers_sorok:
                statusz = self._sor_statusza(sor, statusz_ctx)
                statuszok[id(sor)] = statusz
                if feltetel(*statusz):
                    sorok.append(sor)
        kulcs = self.rendezes_kulcs
        sorok = sorted(
            sorok,
            key=lambda sor: osszetett_rendezesi_kulcs(
                self._sor_alap_adatta_alakitasa(sor), kulcs
            ),
        )
        return sorok, statuszok

    def _nezet_kirajzolasa(self, nyers_sorok, alaplista=False):
        """Kiüríti a táblázatot, majd megjeleníti a nyers találatok szűrt és
        rendezett nézetét a Státusz oszloppal együtt.

        A táblázat a beszúrás idejére "befagyasztott" (Freeze), mert sok sornál
        a soronkénti újrarajzolás lenne a lassú rész."""
        self._tablazat_uritese()
        self._nyers_talalatok = nyers_sorok
        if not nyers_sorok:
            self.frissit_akadalymentesites(0)
            return

        statusz_ctx = self._statusz_kontextus()
        sorok, statuszok = self._rendez_es_szur(nyers_sorok, statusz_ctx)

        if not statusz_ctx.dezi_olvashato:
            self.SetStatusText(
                "A dezideráta-jegyzék nem olvasható, ezért a "
                "\u201eDeziderátában\u201d jelzés nem elérhető."
            )
        elif self.szuro_statusz != "osszes":
            # Aktív szűrésnél a főablakkal azonos felirat.
            self.SetStatusText(
                f"Találatok száma: {len(sorok)} a {len(nyers_sorok)} kötetből."
            )
        elif alaplista:
            self._allapot_frissitese()
        else:
            self.SetStatusText(f"Keresés {len(self.adatok)} kötet adataiban")

        self.tablazat.Freeze()
        try:
            for sor in sorok:
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
                self._statusz_beallitasa(sor_index, sor, statusz_ctx,
                                         statuszok.get(id(sor)))
        finally:
            self.tablazat.Thaw()

        self._alaplista_latszik = alaplista
        self.frissit_akadalymentesites(len(sorok))

    def _nezet_ujraepitese(self):
        """A táblázat újraépítése a legutóbbi nyers találatokból, a jelenlegi
        rendezéssel és szűréssel (a Nézet menü hívja, új keresés nélkül). A
        kijelölés és a fókusz a sorok azonossága alapján megmarad."""
        if not self.oszlopok or not self._nyers_talalatok:
            return
        lista = self.tablazat

        def azonosito(index):
            return id(self._sor_eredeti_dict(index))

        kijeloltek = {azonosito(i) for i in osszes_kijelolt_index(lista)}
        regi_fokusz = lista.GetFocusedItem()
        fokusz_sor = azonosito(regi_fokusz) if regi_fokusz != -1 else None
        volt_fokusz = lista.HasFocus()

        self._nezet_kirajzolasa(self._nyers_talalatok, self._alaplista_latszik)

        db = lista.GetItemCount()
        if db == 0:
            return
        uj_fokusz = None
        for i in range(db):
            azon = azonosito(i)
            if azon in kijeloltek:
                lista.Select(i)
            if azon == fokusz_sor:
                uj_fokusz = i
        if uj_fokusz is None and regi_fokusz != -1:
            # A fókuszált sor kiszűrődött: a hozzá legközelebbi sor kapja.
            uj_fokusz = min(regi_fokusz, db - 1)
        if uj_fokusz is not None:
            lista.Focus(uj_fokusz)
            lista.EnsureVisible(uj_fokusz)
        if volt_fokusz:
            lista.SetFocus()

    def _alapallapot_beallitasa(self, ujra=False):
        """A táblázat alapállapota, amikor a keresőmező üres: a beállítástól
        függően üres lista, vagy a betöltött adatbázis összes tétele. A lista
        így a keresőmező függvénye: szöveg esetén a szűrt találatok, üres
        mezőnél ez az alapállapot.

        Ha a mezőben szöveg van (pl. új adatbázis betöltésekor), a táblázat
        üres marad (mint korábban), a keresés az Enterrel indul.
        `ujra`: akkor is újraépíti az alaplistát, ha az már látszik."""
        van_szoveg = bool(self.kereso_mezo.GetValue().strip())
        if self.inditasi_lista == "osszes" and self.adatok and not van_szoveg:
            if ujra or not self._alaplista_latszik:
                self._sorok_megjelenitese(self.adatok, alaplista=True)
        else:
            self._tablazat_uritese()
            self.frissit_akadalymentesites(0)

    def beallitasok_alkalmazasa(self, config):
        """A főablak hívja a Beállítások mentése után, ha a kereső nyitva van.
        Átveszi az indulási lista beállítását, és ha az adatbázis útvonala
        megváltozott, megnyitja az újat.

        Visszatérési érték: False, ha az új adatbázis megnyitása nem sikerült
        (vagy a felhasználó elvetette); ilyenkor a hívó ne mentse el az új
        útvonalat. A hibaüzenetet az _adatbazis_betoltese már megjelenítette."""
        regi_mod = self.inditasi_lista
        self.inditasi_lista = self._ervenyes_inditasi_lista(
            config.get("kereso_inditasi_lista")
        )
        utvonal = config.get("kereso_json_utvonal", "")
        # Üres útvonal nem zárja be a megnyitott adatbázist: csak a következő
        # indításkor nem töltődik be semmi.
        betoltes_kiserlet = bool(utvonal) and not azonos_utvonal(utvonal, self.json_utvonal)
        sikeres = self._adatbazis_betoltese(utvonal) if betoltes_kiserlet else True
        if self.inditasi_lista != regi_mod and not (betoltes_kiserlet and sikeres):
            # (Sikeres betöltésnél az alapállapotot a betöltés már felépítette.)
            self._alapallapot_beallitasa(ujra=True)
            self.frissit_torles_gomb_allapot()
        return sikeres

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
        """Megkeresi a Cím oszlop nevét a betöltött oszlopnevek között (ugyanazon
        aliasok szerint, mint az átemelés; a megnyitáskor ellenőrzött, hogy
        van ilyen). None, ha nincs betöltött adatbázis."""
        return kereso_cim_oszlop(self.oszlopok)

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
        tetelek = [x for x in adat if isinstance(x, dict)]
        deziderata_regi_kulcsok_atalakitasa(tetelek)
        return tetelek, True

    @staticmethod
    def _csoportosit_cim_szerint(tetelek):
        """Tételek cím szerinti csoportosítása (kisbetűsen, levágva)."""
        csoportok = {}
        for t in tetelek:
            cim = str(t.get("cim", "")).strip().lower()
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

    def _sor_statusza(self, sor_adat, ctx):
        """(állományban van, deziderátában van) egy sorra. A Státusz cella és a
        Nézet > Státusz szűrés is ezt használja, hogy ne térhessenek el."""
        van_allomany = self._allomanyban_van_e(sor_adat, ctx.cim_oszlop, ctx.konyvek)
        van_dezi = self._deziderataban_van_e(sor_adat, ctx.cim_oszlop, ctx.dezi)
        return van_allomany, van_dezi

    def _statusz_beallitasa(self, sor_index, sor_adat, ctx, statusz=None):
        """Kiszámolja és beírja egy táblázatsor Státusz cellájába, hogy a
        tétel az állományban és/vagy a deziderátában szerepel-e, és ennek
        megfelelően színezi a sort. A statusz (_sor_statusza eredménye) kész
        értékként is átadható, ilyenkor nem számolja újra."""
        if statusz is None:
            statusz = self._sor_statusza(sor_adat, ctx)
        van_allomany, van_dezi = statusz

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
        # A vezérlők LÉTREHOZÁSI sorrendje egyben a tabulátorsorrend is (a
        # vizuális elrendezést a sizerek adják, az nem függ tőle), a
        # KeresoDialog (kereso.py) sorrendjével egyezően: Csak teljes szó ->
        # keresőmező -> Keresés törlése -> Keresés -> oszlopok jelölőnégyzetei
        # (lásd _checkboxok_epitese). A "Csak teljes szó" a címke ELŐTT jön
        # létre, mert a címke Alt-gyorsbillentyűje a nála közvetlenül
        # következő vezérlőre visz, ennek a keresőmezőnek kell lennie.
        # "Csak teljes szó": a keresett szavak egész szóként egyezzenek (ne
        # részszövegként).
        self.cb_teljes_szo = wx.CheckBox(self.panel, label="Cs&ak teljes szó")

        kereso_szoveg = wx.StaticText(
            self.panel, label="Keresendő ki&fejezés:"
        )
        self.kereso_mezo = wx.TextCtrl(self.panel, style=wx.TE_PROCESS_ENTER)
        self.kereso_mezo.Bind(wx.EVT_TEXT_ENTER, self.on_kereses)
        self.kereso_mezo.Bind(wx.EVT_TEXT, self.on_szoveg_valtozas)

        self.btn_kereses_torlese = wx.Button(self.panel, label="Keresés &törlése")
        self.btn_kereses_torlese.Enable(False)
        self.btn_kereses_torlese.Bind(wx.EVT_BUTTON, self.on_kereses_torlese)

        self.btn_kereses = wx.Button(self.panel, label="Ke&resés")
        self.btn_kereses.Bind(wx.EVT_BUTTON, self.on_kereses)

        kereso_sizer = wx.BoxSizer(wx.HORIZONTAL)
        kereso_sizer.Add(
            kereso_szoveg,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            border=5,
        )
        kereso_sizer.Add(self.kereso_mezo, proportion=1, flag=wx.EXPAND)
        kereso_sizer.Add(
            self.cb_teljes_szo,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            border=10,
        )
        kereso_sizer.Add(self.btn_kereses_torlese, flag=wx.LEFT, border=5)
        kereso_sizer.Add(self.btn_kereses, flag=wx.LEFT, border=5)

        fő_sizer.Add(kereso_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # --- Checkboxok az oszlopokhoz ---
        opciok_szoveg = wx.StaticText(
            self.panel, label="Keresés ezekben az oszlopokban:"
        )
        fő_sizer.Add(opciok_szoveg, flag=wx.LEFT | wx.RIGHT, border=10)

        self.checkboxok = {}
        self.cb_osszes_oszlop = None
        self.checkbox_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._checkboxok_epitese()
        fő_sizer.Add(self.checkbox_sizer, flag=wx.ALL, border=10)

        # --- Eredmény lista (wx.ListCtrl táblázat) ---
        # A szűrő-felirat a "Találatok" felirat ELŐTT jön létre, hogy annak
        # Alt-gyorsbillentyűje továbbra is közvetlenül a táblázatra vigyen.
        self.szuro_kijelzo = wx.StaticText(self.panel, label="")
        szuro_font = self.szuro_kijelzo.GetFont()
        szuro_font.MakeItalic()
        self.szuro_kijelzo.SetFont(szuro_font)

        self.eredmeny_szoveg = wx.StaticText(self.panel, label="Találatok:")
        eredmeny_fejlec = wx.BoxSizer(wx.HORIZONTAL)
        eredmeny_fejlec.Add(self.eredmeny_szoveg, flag=wx.ALIGN_CENTER_VERTICAL)
        eredmeny_fejlec.AddStretchSpacer(1)
        eredmeny_fejlec.Add(self.szuro_kijelzo, flag=wx.ALIGN_CENTER_VERTICAL)
        fő_sizer.Add(eredmeny_fejlec, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        self.tablazat = wx.ListCtrl(self.panel, style=wx.LC_REPORT)

        # Események bekötése
        self.tablazat.Bind(
            wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_helyi_menu
        )
        self.tablazat.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_helyi_menu)
        self.tablazat.Bind(wx.EVT_KEY_DOWN, self.on_billentyu_leutve)
        self.tablazat.Bind(wx.EVT_CHAR, self.on_char)

        self.frissit_akadalymentesites(0)

        self._tablazat_oszlopai_epitese()

        fő_sizer.Add(
            self.tablazat, proportion=1, flag=wx.EXPAND | wx.ALL, border=10
        )

        # --- Gombsor ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_osszes_kijelolese = wx.Button(
            self.panel, label="Összes kijelölése"
        )
        self.btn_masolas_vagolapra = wx.Button(
            self.panel, label="Másolás vágólapra"
        )
        self.btn_atemeles_allomanyba = wx.Button(
            self.panel, label="Átemelés az állományba"
        )
        self.btn_atemeles_deziderataba = wx.Button(
            self.panel, label="Átemelés a Deziderátába"
        )

        btn_sizer.Add(self.btn_osszes_kijelolese, 0, wx.RIGHT, 10)
        btn_sizer.Add(self.btn_masolas_vagolapra, 0, wx.RIGHT, 10)
        btn_sizer.Add(self.btn_atemeles_allomanyba, 0, wx.RIGHT, 10)
        btn_sizer.Add(self.btn_atemeles_deziderataba, 0, wx.RIGHT, 10)

        fő_sizer.Add(btn_sizer, 0, wx.ALIGN_LEFT | wx.ALL, 10)

        self.btn_osszes_kijelolese.Bind(
            wx.EVT_BUTTON, lambda e: self.osszes_kijelolese()
        )
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

    def on_osszes_oszlop(self, event):
        """Az "Összes oszlop" jelölőnégyzet: minden oszlop-jelölőnégyzetet
        a saját állapotára állítja (bejelölve mind be, pipa nélkül mind ki)."""
        ertek = self.cb_osszes_oszlop.GetValue()
        for cb in self.checkboxok.values():
            cb.SetValue(ertek)

    def on_oszlop_checkbox(self, event):
        """Egy oszlop-jelölőnégyzet változásakor az "Összes oszlop" jelölőnégyzet
        követi az állapotot: csak akkor van bejelölve, ha minden oszlop be van."""
        if self.cb_osszes_oszlop is not None:
            self.cb_osszes_oszlop.SetValue(
                all(cb.GetValue() for cb in self.checkboxok.values())
            )
        event.Skip()

    def menu_esemenyek_bekotese(self, menusor):
        """A menüsor elemeinek bekötése. A gyorsbillentyűket (Ctrl+C,
        Ctrl+A, Ctrl+D, Ctrl+F, Ctrl+W) maguk a menüelemek hordozzák, ezért külön
        gyorsítótábla nem szükséges."""
        self.Bind(wx.EVT_MENU, self.on_menu_megnyitas, menusor.megnyitas)
        self.Bind(wx.EVT_MENU, self.on_menu_visszavonas, menusor.undo)
        self.Bind(wx.EVT_MENU, self.on_menu_megis, menusor.redo)
        self.Bind(wx.EVT_MENU_OPEN, self.on_menu_nyitas)
        self.Bind(wx.EVT_MENU, self.on_menu_masolas, menusor.copy)
        self.Bind(wx.EVT_MENU, self.on_menu_osszes_kijelolese, menusor.select_all)
        self.Bind(wx.EVT_MENU, self.on_menu_egyik_sem_kijelolese, menusor.select_none)
        self.Bind(wx.EVT_MENU, self.on_menu_deziderata, menusor.deziderata)
        self.Bind(wx.EVT_MENU, self.on_menu_allomany, menusor.allomany)
        self.Bind(wx.EVT_MENU, self.on_kilepes, menusor.kilepes)
        self.Bind(wx.EVT_MENU, self.on_open_help, menusor.help)
        self.Bind(wx.EVT_MENU, self.on_menu_deziderata_kezelo, menusor.deziderata_kezelo)
        self.Bind(wx.EVT_MENU, self.on_beallitasok, menusor.beallitasok)
        for kulcs, elem in menusor.rendezes_elemek.items():
            self.Bind(wx.EVT_MENU, lambda e, k=kulcs: self.on_menu_rendezes(k), elem)
        for kulcs, elem in menusor.statusz_elemek.items():
            self.Bind(wx.EVT_MENU, lambda e, k=kulcs: self.on_menu_statusz_szures(k), elem)

    # --- VISSZAVONÁS / MÉGIS ---

    def on_close(self, event):
        # A saját vermek elvesznek; a kereső átemelései a főablak / a
        # Dezideráta-ablak vermében megmaradnak (kivéve a zárt dezideráta
        # módosítását, amelynek más verme nincs).
        if self.undo is not None:
            self.undo.bezar()
        event.Skip()

    def on_menu_nyitas(self, event):
        """Menü megnyitásakor a Visszavonás/Mégis tételek feliratába beírja a
        soron következő lépés leírását."""
        if self.undo is not None:
            frissit_undo_menu(self.menusor.undo, self.menusor.redo,
                              self.undo, self.FindFocus())
        # A Nézet menü rádiócsoportjai mindig a valódi állapotot mutassák.
        self.menusor.RendezesJelolese(self.rendezes_kulcs)
        self.menusor.StatuszJelolese(self.szuro_statusz)
        event.Skip()

    # --- NÉZET: RENDEZÉS ÉS STÁTUSZ SZŰRÉS ---

    def on_menu_rendezes(self, mezo_kulcs):
        self.rendezes_kulcs = mezo_kulcs
        self._nezet_ujraepitese()
        # A választott rendezés megmarad a következő indításra is.
        if not beallitas_mentese("kereso_rendezes", mezo_kulcs):
            if not self._rendezes_mentes_hiba_jelezve:
                self._rendezes_mentes_hiba_jelezve = True
                wx.MessageBox(
                    "A rendezés mentése nem sikerült, ezért a program újraindítás után "
                    "az előző rendezéssel nyílik meg.",
                    "Mentési hiba", wx.OK | wx.ICON_WARNING, self,
                )

    def on_menu_statusz_szures(self, kulcs):
        self.szuro_statusz = kulcs
        self._nezet_ujraepitese()

    def on_menu_visszavonas(self, event):
        self._visszavonas_vagy_megis(ismet=False)

    def on_menu_megis(self, event):
        self._visszavonas_vagy_megis(ismet=True)

    def _visszavonas_vagy_megis(self, ismet):
        # A menü Ctrl+Z / Ctrl+Y gyorsbillentyűje a keresőmezőtől is elveszi a
        # billentyűt: ott a mező saját szövegét vonjuk vissza (lásd
        # on_menu_masolas is).
        if szovegmezo_visszavonas(self.FindFocus(), ismet):
            return
        if self.undo is None:
            self.SetStatusText(
                "A visszavonás csak a főablakból indított keresőben érhető el."
            )
            return
        # A lépés minden érintett oldalát (állomány, deziderata) a regiszter
        # alkalmazza; a főablak és a Dezideráta-ablak nézetét, valamint e
        # táblázat Státusz oszlopát a tárolók frissítői újraszámolják.
        undo_lepes(self.undo, ismet, self, self.SetStatusText)

    def on_menu_megnyitas(self, event):
        """Fájl > Adatbázis megnyitása (Ctrl+O)."""
        self.adatbazis_megnyitasa()

    def on_menu_masolas(self, event):
        """Fájl > Másolás. Ha a keresőmezőben áll a fókusz, annak saját
        szövegét másolja (különben a menü Ctrl+C-je elnyelné a szokásos
        szövegmásolást), egyébként a kijelölt találatokat."""
        fokusz = self.FindFocus()
        if isinstance(fokusz, wx.TextCtrl):
            fokusz.Copy()
            return
        self.masolas_vagolapra()

    def on_menu_osszes_kijelolese(self, event):
        """Szerkesztés > Kijelölés > Összes elem. Ha a keresőmezőben áll a
        fókusz, annak szövegét jelöli ki (különben a menü Ctrl+A-ja elnyelné
        a szokásos szövegkijelölést), egyébként a találatok összes sorát."""
        fokusz = self.FindFocus()
        if isinstance(fokusz, wx.TextCtrl):
            fokusz.SelectAll()
            return
        self.osszes_kijelolese()

    def on_menu_egyik_sem_kijelolese(self, event):
        """Szerkesztés > Kijelölés > Egyik sem. Ha a keresőmezőben áll a
        fókusz, annak szövegkijelölését szünteti meg (a kurzor a helyén
        marad), egyébként a találatok kijelölését."""
        fokusz = self.FindFocus()
        if isinstance(fokusz, wx.TextCtrl):
            pont = fokusz.GetInsertionPoint()
            fokusz.SetSelection(pont, pont)
            return
        self.egyik_sem_kijelolese()

    def egyik_sem_kijelolese(self):
        """Megszünteti a találati táblázat összes kijelölését. A fókusz a
        táblázatban marad, ahol a felhasználó tartott."""
        if self.tablazat.GetSelectedItemCount() == 0:
            self.SetStatusText("Nincs kijelölt találat.")
            return
        self.tablazat.SetItemState(-1, 0, wx.LIST_STATE_SELECTED)
        self.SetStatusText("Kijelölés megszüntetve.")

    def osszes_kijelolese(self):
        """Kijelöli a találati táblázat összes sorát. A gomb, a menü és a
        táblázatbeli Ctrl+A is ezt hívja, hogy ugyanúgy viselkedjenek."""
        darab = self.tablazat.GetItemCount()
        if darab == 0:
            self.SetStatusText("Nincs kijelölhető találat.")
            return
        self.tablazat.Freeze()
        try:
            for i in range(darab):
                self.tablazat.Select(i, on=True)
        finally:
            self.tablazat.Thaw()
        self.SetStatusText(f"Összes találat kijelölve ({darab} db)")

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
        self.eredmeny_szoveg.SetLabel(f"Ta&lálatok ({darabszam} db):")
        self.tablazat.SetName(szoveg)
        self._szuro_cimke_frissitese(darabszam)

    # A Státusz szűrés értékei a felirathoz.
    _STATUSZ_SZURO_NEVEK = {
        "allomanyban": "Állományban",
        "deziderataban": "Deziderátában",
        "egyikben_sem": "Egyikben sem",
    }

    # Státusz szűrés: kulcs -> feltétel az (állományban, deziderátában) párra.
    # Az "egyikben_sem" azokat a tételeket adja, amelyek sem az állományban,
    # sem a deziderátában nincsenek (a Státusz cellájuk üres).
    _STATUSZ_SZURO_FELTETELEK = {
        "allomanyban":   lambda van_allomany, van_dezi: van_allomany,
        "deziderataban": lambda van_allomany, van_dezi: van_dezi,
        "egyikben_sem":  lambda van_allomany, van_dezi: not van_allomany and not van_dezi,
    }

    def _szuro_cimke_frissitese(self, darabszam):
        """A szűrő-felirat (főablak: szuro_kijelzo) beállítása: csak akkor
        látszik, ha a Státusz szűrés aktív és van mit szűrni; egyébként üres."""
        cimke = getattr(self, "szuro_kijelzo", None)
        if cimke is None:
            return
        szoveg = ""
        if self.szuro_statusz != "osszes" and self._nyers_talalatok:
            nev = self._STATUSZ_SZURO_NEVEK.get(self.szuro_statusz, self.szuro_statusz)
            szoveg = f"Szűrés: Státusz = '{nev}' ({darabszam} találat)"
        if cimke.GetLabel() != szoveg:
            cimke.SetLabel(szoveg)
            cimke.GetParent().Layout()

    def frissit_torles_gomb_allapot(self):
        """Engedélyezi a törlés gombot, ha van szöveg a mezőben vagy van találat a táblázatban.
        "Összes tétel" módban a táblázat tartalma önmagában nem ok a törlésre
        (az csak az alaplista), ott csak a mezőben lévő szöveg számít."""
        van_szoveg = bool(self.kereso_mezo.GetValue().strip())
        van_talalat = self.tablazat.GetItemCount() > 0 and self.inditasi_lista != "osszes"
        self.btn_kereses_torlese.Enable(van_szoveg or van_talalat)

    def on_szoveg_valtozas(self, event):
        """Ha a felhasználó kiüríti a keresőmezőt, a táblázat az alapállapotba
        kerül (üres lista vagy az összes tétel), és frissül a törlés gomb."""
        if not self.kereso_mezo.GetValue().strip():
            self._alapallapot_beallitasa()
        self.frissit_torles_gomb_allapot()
        event.Skip()

    def on_kereses_torlese(self, event):
        """Kiüríti a keresőmezőt és a találati táblázatot, majd fókuszba helyezi a mezőt."""
        # ChangeValue: nem vált ki EVT_TEXT-et, így az alapállapot (összes tétel
        # módban akár több ezer sor) csak egyszer épül fel.
        self.kereso_mezo.ChangeValue("")
        self._alapallapot_beallitasa()
        self.frissit_torles_gomb_allapot()
        self.btn_kereses_torlese.Enable(False)
        self.kereso_mezo.SetFocus()

    def on_kereses(self, event):
        """A keresés logikája gombnyomásra vagy Enterre (Pandas nélkül)."""
        if (self.adatok is not None and self.inditasi_lista == "osszes"
                and not self.kereso_mezo.GetValue().strip()):
            # Üres mező + "összes tétel" mód: a lista már az alapállapotot mutatja
            # (csak akkor építjük újra, ha valamiért nem az látszik).
            self._alapallapot_beallitasa()
            self.tablazat.SetFocus()
            return

        self._tablazat_uritese()

        if self.adatok is None:
            # Nincs adatbázis: felkínáljuk a megnyitást, és ha sikerül, a
            # keresés a beírt kifejezéssel folytatódik.
            valasz = wx.MessageBox(
                "Nincs megnyitott adatbázis. Megnyitja most?",
                "Nincs adatbázis",
                wx.YES_NO | wx.ICON_QUESTION,
                self,
            )
            if valasz != wx.YES or not self.adatbazis_megnyitasa():
                return

        keresett_szo = self.kereso_mezo.GetValue().strip().lower()
        if not keresett_szo:
            if self.inditasi_lista == "osszes":
                # Az adatbázis most, a felkínált megnyitással töltődött be, és a
                # betöltés már az alaplistát építette fel.
                self.tablazat.SetFocus()
                return
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
        #
        # "Csak teljes szó" bejelölve: a szavak csak egész szóként számítanak
        # egyezésnek (Unicode-barát szóhatárral), pl. a "dal" nem találja meg
        # a "Dalok" szót. Kikapcsolva a keresés részszöveges, mint eddig.
        szavak = keresett_szo.split()
        if self.cb_teljes_szo.GetValue():
            szo_mintak = [
                re.compile(r"(?<!\w)" + re.escape(szo) + r"(?!\w)", re.IGNORECASE)
                for szo in szavak
            ]

            def szo_talalt(minta, ertek):
                return minta.search(ertek) is not None
        else:
            szo_mintak = szavak

            def szo_talalt(szo, ertek):
                return szo in ertek

        szurt_adatok = []
        for sor in self.adatok:
            ertekek = [str(sor.get(oszlop, "")).lower() for oszlop in kijelolt_oszlopok]
            if all(any(szo_talalt(minta, ertek) for ertek in ertekek) for minta in szo_mintak):
                szurt_adatok.append(sor)

        # A találatok (vagy a 0 találat) megjelenítése a közös metódussal.
        self._sorok_megjelenitese(szurt_adatok)

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

        if self.szuro_statusz != "osszes":
            # Aktív Státusz szűrésnél a státusz változása sorokat vihet ki a
            # nézetből vagy hozhat be, ezért a cellák helyett újraépítünk.
            self._nezet_ujraepitese()
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
        """A szóköz ne nyissa meg a helyi menüt, hanem a gyorskereső pufferébe kerüljön.
        A többi gyorsbillentyűt a menüelemek hordozzák."""
        if event.GetKeyCode() == wx.WXK_SPACE:
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
        deziderata_item = menu.Append(wx.ID_ANY, "Felvétel a dezideráta-jegyzékbe\tCTRL+SHIFT+D")

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

    def _undo_csoport(self, leiras, tarolok):
        """A kereső egy átemelése EGY visszavonható lépés a megadott
        tárolókra. A lépés a kereső vermébe kerül, és a tárolók szerinti
        ablakéba is (állomány: főablak; dezideráta: a nyitott
        Dezideráta-ablak). Zárt Dezideráta-ablaknál a lépés csak a kereső
        vermében él, a főablak nem kapja meg. Önálló futásnál nincs undo."""
        if self.undo is None:
            return nullcontext()
        return self.undo.muvelet(leiras, tarolok)

    def atemeles_allomanyba(self):
        if not self.parent or not hasattr(self.parent, "db"):
            wx.MessageBox(
                "Az átemelés nem lehetséges, mert a kereső önállóan fut!",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return
        # Betöltési hiba után a főállomány védett: nem emelhetünk át bele.
        if not allomany_szerkesztheto(self.parent.db, self):
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
                self.parent._uj_konyvek_utani_frissites(
                    uj_konyv_objektumok, fokusz_az_ujra=True
                )
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
            with self._undo_csoport("átemelés az állományba", ["allomany"]):
                sikeres, visszautasitott, _, _ = konyvek_tomeges_felvetele(
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
            with self._undo_csoport("átemelés a deziderátába", ["deziderata"]):
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

            if not isinstance(adat, list):
                # Érvényes aláírás, de nem tétellista: nem írhatjuk felül.
                wx.MessageBox(
                    "A dezideráta-jegyzék tartalma nem tételek listája, ezért az "
                    "átemelés megszakadt.",
                    "Hiba", wx.OK | wx.ICON_ERROR
                )
                return

            with self._undo_csoport("átemelés a deziderátába", ["deziderata"]):
                deziderata_lista = [x for x in adat if isinstance(x, dict)]
                # A régi (angol kulcsú) tételek átalakítása, és a meglévő, még
                # id nélküli tételek is megkapják az id-t.
                deziderata_regi_kulcsok_atalakitasa(deziderata_lista)
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

    def on_open_help(self, event):
        sugo_megnyitasa(self, 5)

    def on_beallitasok(self, event):
        # A főablak Beállítások ablaka a 3. (0-tól számolt) fülön: KönyvTárnok-kereső.
        beallitasok_megnyitasa_gyermekbol(self, 3)

    def on_menu_deziderata_kezelo(self, event):
        if self.parent is not None and hasattr(self.parent, "on_deziderata"):
            self.parent.on_deziderata(event)

if __name__ == "__main__":
    app = wx.App()
    KonyvtarnokKeresoApp(parent=None)
    app.MainLoop()
