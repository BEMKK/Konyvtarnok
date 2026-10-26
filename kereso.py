import logging
import wx

from theme_manager import apply_theme_from_settings
from data_manager import szuresi_talalatok, load_hmac_json, is_same_book, DEFAULT_ADATBAZIS_FAJL
from deziderata import DATA_FILE as DEZIDERATA_DATA_FILE
from konyvdialogs import KonyvReszletekDialog, DeziderataReszletekDialog
from utils import masolas_vagolapra_szoveg

# Kereshető oszlopok: (belső kulcs, megjelenített név). A kulcsok a kanonikus
# mezőnevek (cim, szerzo, kiado, hely, ev); a "Forrás" oszlop nem kereshető.
KERESHETO_OSZLOPOK = [
    ("cim", "Cím"),
    ("szerzo", "Összeállító"),
    ("kiado", "Kiadó"),
    ("hely", "Kiadás helye"),
    ("ev", "Kiadás éve"),
]


class KeresoDialog(wx.Dialog):
    """Összesített kereső párbeszédablak saját találati listával.

    Egyetlen felületen teszi lehetővé a keresést az állományjegyzékben,
    a dezideráta-jegyzékben vagy mindkettőben egyszerre. A találatokból
    közvetlenül megnyitható az adott tétel részletes adatlapja (olvasó nézet).

    Tabulátorsorrend (a vezérlők létrehozási sorrendje határozza meg):
    Keresés helye, Csak teljes szó, Keresett kifejezés, Keresés törlése,
    Keresés, Összes oszlop, az egyes oszlopok jelölőnégyzetei (Cím,
    Összeállító, Kiadó, Kiadás helye, Kiadás éve), Találati lista, Részletek,
    Bezárás.
    A kezdőfókusz a Keresett kifejezés mezőn van.
    """

    def __init__(self, parent):
        super().__init__(
            parent,
            title="Keresés a gyűjteményekben",
            size=(880, 560),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
        )
        self.parent = parent
        self._talalatok = []
        # Az utoljára LEFUTTATOTT keresés feltételei. A találati lista ezeknek
        # felel meg (nem az űrlap pillanatnyi állapotának), ezért szerkesztés
        # után ezekkel futtatjuk újra a keresést.
        self._utolso_kereses = None

        # =====================================================================
        # VEZÉRLŐK LÉTREHOZÁSA
        # A létrehozás sorrendje egyben a tabulátorsorrend is. A címke mindig
        # közvetlenül a hozzá tartozó vezérlő előtt jön létre, így a gyorsbillentyű
        # és a képernyőolvasó is helyesen párosítja őket.
        # =====================================================================

        # 1. Keresés helye
        self.label_scope = wx.StaticText(self, label="Keresés &helye:")
        self.scope_choice = wx.Choice(
            self, choices=["Mindenhol", "Dezideráta", "Állomány"]
        )
        self.scope_choice.SetSelection(0)
        self.scope_choice.SetName("Keresés helye")

        # 2. Csak teljes szó (a keresett szavak egész szóként egyezzenek)
        self.exact_match_cb = wx.CheckBox(self, label="Csak teljes &szó")

        # 3. Keresett kifejezés
        self.label_keresett = wx.StaticText(self, label="Keresett &kifejezés:")
        self.text_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.text_ctrl.SetName("Keresett kifejezés")
        self.text_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_kereses)
        self.text_ctrl.Bind(wx.EVT_TEXT, self.on_text_changed)

        # 4. Keresés törlése (alapértelmezetten letiltva)
        self.btn_clear = wx.Button(self, label="Keresés &törlése")
        self.btn_clear.Bind(wx.EVT_BUTTON, self.on_clear)
        self.btn_clear.Enable(False)

        # 5. Keresés
        self.btn_kereses = wx.Button(self, label="Ke&resés")
        self.btn_kereses.SetDefault()
        self.btn_kereses.Bind(wx.EVT_BUTTON, self.on_kereses)

        # 6. Keresési oszlopok: "Összes oszlop" + oszloponkénti jelölőnégyzetek
        # (ugyanúgy, mint a KönyvTárnok-keresőben)
        self.label_oszlopok = wx.StaticText(self, label="Keresés ezekben az oszlopokban:")
        self.cb_osszes_oszlop = wx.CheckBox(self, label="Összes &oszlop")
        self.cb_osszes_oszlop.SetValue(True)
        self.cb_osszes_oszlop.Bind(wx.EVT_CHECKBOX, self.on_osszes_oszlop)

        self.oszlop_checkboxok = {}
        for kulcs, nev in KERESHETO_OSZLOPOK:
            cb = wx.CheckBox(self, label=nev)
            cb.SetValue(True)
            cb.Bind(wx.EVT_CHECKBOX, self.on_oszlop_checkbox)
            self.oszlop_checkboxok[kulcs] = cb

        # 7. Találati lista (felirat + táblázat)
        self.eredmeny_szoveg = wx.StaticText(self, label="Találatok:")
        self.list_ctrl = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self.list_ctrl.InsertColumn(0, "Forrás", width=110)
        self.list_ctrl.InsertColumn(1, "Cím", width=240)
        self.list_ctrl.InsertColumn(2, "Összeállító", width=160)
        self.list_ctrl.InsertColumn(3, "Kiadó", width=150)
        self.list_ctrl.InsertColumn(4, "Kiadás helye", width=110)
        self.list_ctrl.InsertColumn(5, "Kiadás éve", width=85)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_reszletek)
        self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)
        self.frissit_akadalymentesites(0)

        # 8. Részletek
        self.btn_reszletek = wx.Button(self, label="Részletek...")
        self.btn_reszletek.Bind(wx.EVT_BUTTON, self.on_reszletek)

        # 9. Bezárás
        self.btn_bezaras = wx.Button(self, wx.ID_CANCEL, label="Bezárás")

        # Állapotsor (nem tabulátor-megálló)
        self.statusz_text = wx.StaticText(self, label="")

        # =====================================================================
        # ELRENDEZÉS
        # =====================================================================
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Beállítások sora (felül)
        options_sizer = wx.BoxSizer(wx.HORIZONTAL)
        options_sizer.Add(self.label_scope, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        options_sizer.Add(self.scope_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)
        options_sizer.Add(self.exact_match_cb, 0, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(options_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Keresett kifejezés sora
        input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        input_sizer.Add(self.label_keresett, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        input_sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.RIGHT, 5)
        input_sizer.Add(self.btn_clear, 0, wx.RIGHT, 5)
        input_sizer.Add(self.btn_kereses, 0)
        main_sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Oszlopválasztó sor (WrapSizer: keskeny ablaknál új sorba tör)
        main_sizer.Add(self.label_oszlopok, 0, wx.LEFT | wx.RIGHT, 10)
        oszlop_sizer = wx.WrapSizer(wx.HORIZONTAL)
        oszlop_sizer.Add(self.cb_osszes_oszlop, 0, wx.RIGHT | wx.TOP | wx.BOTTOM, 10)
        for cb in self.oszlop_checkboxok.values():
            oszlop_sizer.Add(cb, 0, wx.RIGHT | wx.TOP | wx.BOTTOM, 10)
        main_sizer.Add(oszlop_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Találati lista
        main_sizer.Add(self.eredmeny_szoveg, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        main_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Alsó állapotsor és gombsor
        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        bottom_sizer.Add(self.statusz_text, 0, wx.ALIGN_CENTER_VERTICAL)
        bottom_sizer.AddStretchSpacer(1)
        bottom_sizer.Add(self.btn_reszletek, 0, wx.RIGHT, 5)
        bottom_sizer.Add(self.btn_bezaras, 0)
        main_sizer.Add(bottom_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Téma alkalmazása
        apply_theme_from_settings(self)

        self.SetMinSize((650, 420))
        self.SetSizer(main_sizer)
        self.Layout()
        self.CentreOnParent()

        self.frissit_torles_gomb()
        self.text_ctrl.SetFocus()

    # =========================================================================
    # ADATFORRÁSOK LEKÉRÉSE
    # =========================================================================

    def _get_foablak(self):
        """Visszaadja a főablakot (Konyvtarnok), akár a főablakból, akár a
        Dezideráta-kezelőből nyitották meg a keresőt."""
        jeloltek = [self.parent]
        if hasattr(self.parent, "GetParent"):
            jeloltek.append(self.parent.GetParent())
        if hasattr(self.parent, "parent"):
            jeloltek.append(getattr(self.parent, "parent", None))
        for w in jeloltek:
            if w is not None and hasattr(w, "db"):
                return w
        return None

    def _get_allomany_adatok(self):
        """Visszaadja a könyvállomány legfrissebb adatait."""
        foablak = self._get_foablak()
        if foablak and getattr(foablak, "db", None) and getattr(foablak.db, "konyvek", None) is not None:
            return list(foablak.db.konyvek)
        if foablak and hasattr(foablak, "teljes_adatlista") and foablak.teljes_adatlista:
            return list(foablak.teljes_adatlista)

        try:
            adatok, ervenyes = load_hmac_json(DEFAULT_ADATBAZIS_FAJL)
            if not ervenyes:
                logging.error("Az állományfájl HMAC-ellenőrzése sikertelen, az adatok nem kerülnek betöltésre.")
                return []
            if isinstance(adatok, list):
                return [k for k in adatok if isinstance(k, dict)]
        except Exception as e:
            logging.warning(f"Hiba az állományfájl betöltésekor: {e}")
        return []

    def _get_deziderata_adatok(self):
        """Visszaadja a dezideráta jegyzék legfrissebb adatait."""
        if hasattr(self.parent, "items") and hasattr(self.parent, "load_data"):
            return list(self.parent.items)
        foablak = self._get_foablak()
        if (
            foablak
            and hasattr(foablak, "deziderata_frame")
            and foablak.deziderata_frame is not None
            and hasattr(foablak.deziderata_frame, "items")
        ):
            return list(foablak.deziderata_frame.items)

        try:
            adatok, ervenyes = load_hmac_json(DEZIDERATA_DATA_FILE)
            if not ervenyes:
                logging.error("A deziderátafájl HMAC-ellenőrzése sikertelen, az adatok nem kerülnek betöltésre.")
                return []
            if isinstance(adatok, list):
                return [d for d in adatok if isinstance(d, dict)]
        except Exception as e:
            logging.warning(f"Hiba a deziderátafájl betöltésekor: {e}")
        return []

    def _get_db(self):
        """Visszaadja a KonyvAdatbazis példányt, ha elérhető."""
        foablak = self._get_foablak()
        return foablak.db if foablak and hasattr(foablak, "db") else None

    # =========================================================================
    # SZERKESZTÉSI VISSZAJELZÉSEK KEZELÉSE
    # =========================================================================

    def frissit_lista_szerkesztes_utan(self, konyv_id):
        """Ha a részletek dialógusból indított könyvszerkesztés sikeres volt."""
        foablak = self._get_foablak()
        if foablak and hasattr(foablak, "frissit_lista_szerkesztes_utan"):
            foablak.frissit_lista_szerkesztes_utan(konyv_id)
        # A szerkesztés megváltoztathatta, hogy a tétel megfelel-e még a
        # keresési feltételeknek: újrakeresés, így ami már nem egyezik, eltűnik.
        self._ujrakereses()

    @staticmethod
    def _ablak_el(ablak):
        """True, ha az ablak létezik és a mögötte lévő wx-objektum nem szűnt meg."""
        if ablak is None:
            return False
        try:
            return bool(ablak)
        except RuntimeError:
            return False

    def _deziderata_ablak(self, megnyit=False):
        """Visszaadja azt az ablakot, amelyen keresztül a dezideráta módosítható
        (a keresőt megnyitó Dezideráta-kezelő, vagy a főablak Dezideráta-kezelője).

        megnyit=True esetén, ha a Dezideráta-kezelő még nincs nyitva, megnyitja
        - korábban ilyenkor a szerkesztés csendben elveszett.
        """
        if hasattr(self.parent, "tetel_modositasa"):
            return self.parent
        foablak = self._get_foablak()
        if foablak is None:
            return None
        frame = getattr(foablak, "deziderata_frame", None)
        if not self._ablak_el(frame):
            frame = None
            if megnyit and hasattr(foablak, "on_deziderata"):
                foablak.deziderata_frame = None
                foablak.on_deziderata(None)
                frame = getattr(foablak, "deziderata_frame", None)
        return frame if self._ablak_el(frame) and hasattr(frame, "tetel_modositasa") else None

    def is_duplicate(self, candidate, exclude_idx=None, exclude_id=None):
        """A dezideráta-szerkesztő (EditItemDialog) duplikáció-ellenőrzéséhez:
        van-e a jegyzékben másik, azonos tétel. Korábban a keresőből indított
        szerkesztésnél ez az ellenőrzés kimaradt, mert a szerkesztő szülője
        (ez az ablak) nem rendelkezett ilyen metódussal."""
        for item in self._get_deziderata_adatok():
            if exclude_id is not None and item.get("id") == exclude_id:
                continue
            if is_same_book(candidate, item):
                return True
        return False

    def tetel_modositasa(self, tetel_id, uj_adatok, eredeti_sorindex=None):
        """Ha a részletek dialógusból indított dezideráta módosítás sikeres volt.

        Ha a Dezideráta-kezelő nincs nyitva, megnyitja, hogy a módosítás
        ténylegesen elmentődjön. Ha így sem menthető, hibaüzenetet ad."""
        frame = self._deziderata_ablak(megnyit=True)
        if frame is not None:
            # Sikertelenség esetén (letiltott szerkesztés, eltűnt tétel) a
            # Dezideráta-kezelő maga ad hibaüzenetet.
            frame.tetel_modositasa(tetel_id, uj_adatok, eredeti_sorindex)
        else:
            wx.MessageBox(
                "A módosítást nem sikerült elmenteni: a Dezideráta-kezelő nem érhető el.",
                "Szerkesztés", wx.OK | wx.ICON_ERROR, parent=self,
            )
        # Sikertelen mentés után is újrakeresünk: a lista így a tényleges
        # adatokat mutatja.
        self._ujrakereses()

    # =========================================================================
    # AKADÁLYMENTESÍTÉS ÉS BILLENTYŰKEZELÉS
    # =========================================================================

    def frissit_akadalymentesites(self, darabszam):
        """Beállítja a táblázat belső nevét és a felette lévő feliratot."""
        szoveg = f"Találatok listája, {darabszam} elem"
        self.eredmeny_szoveg.SetLabel(f"Találatok ({darabszam} db):")
        self.list_ctrl.SetName(szoveg)

    def _lista_uritese(self):
        """Kiüríti a találati listát és a belső találattárolót."""
        self.list_ctrl.DeleteAllItems()
        self._talalatok = []

    def frissit_torles_gomb(self):
        """A Keresés törlése gomb csak akkor érhető el, ha van szöveg a mezőben
        vagy találat a listában."""
        van_szoveg = bool(self.text_ctrl.GetValue().strip())
        van_talalat = self.list_ctrl.GetItemCount() > 0
        self.btn_clear.Enable(van_szoveg or van_talalat)

    def on_text_changed(self, event):
        """Ha a felhasználó kiüríti a keresőmezőt, a találati lista is kiürül, és frissül a törlés gomb."""
        if not self.text_ctrl.GetValue().strip():
            self._lista_uritese()
            self._utolso_kereses = None
            self.frissit_akadalymentesites(0)
            self.statusz_text.SetLabel("")
        self.frissit_torles_gomb()
        event.Skip()

    def on_list_key_down(self, event):
        keycode = event.GetKeyCode()
        # Enter megnyitja a részleteket
        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_reszletek()
        # Ctrl+C másolja a kijelölt sort
        elif event.ControlDown() and keycode == ord('C'):
            self._masolas_vagolapra()
        else:
            event.Skip()

    def _masolas_vagolapra(self):
        idx = self.list_ctrl.GetFirstSelected()
        if idx != -1:
            oszlopok = [self.list_ctrl.GetItemText(idx, col) for col in range(6)]
            szoveg = "\t".join(oszlopok)
            masolas_vagolapra_szoveg(szoveg)

    # =========================================================================
    # OSZLOPVÁLASZTÓ
    # =========================================================================

    def on_osszes_oszlop(self, event):
        """Az „Összes oszlop” jelölőnégyzet: minden oszlop-jelölőnégyzetet
        a saját állapotára állít (bejelölve mind be, pipa nélkül mind ki)."""
        ertek = self.cb_osszes_oszlop.GetValue()
        for cb in self.oszlop_checkboxok.values():
            cb.SetValue(ertek)

    def on_oszlop_checkbox(self, event):
        """Egy oszlop változásakor az „Összes oszlop” követi az állapotot:
        csak akkor van bejelölve, ha minden oszlop be van jelölve."""
        self.cb_osszes_oszlop.SetValue(
            all(cb.GetValue() for cb in self.oszlop_checkboxok.values())
        )
        event.Skip()

    def _kijelolt_oszlopok(self):
        """A bejelölt oszlopok kulcsai (a KERESHETO_OSZLOPOK sorrendjében)."""
        return [k for k, cb in self.oszlop_checkboxok.items() if cb.GetValue()]

    # =========================================================================
    # KERESÉS ÉS VEZÉRLÉS
    # =========================================================================

    def on_clear(self, event=None):
        """Kiüríti a keresőmezőt és a találati listát."""
        self.text_ctrl.Clear()
        self._lista_uritese()
        self._utolso_kereses = None
        self.frissit_akadalymentesites(0)
        self.statusz_text.SetLabel("")
        self.frissit_torles_gomb()
        # A fókuszt a letiltódó gomb helyett a keresőmezőre tesszük
        self.text_ctrl.SetFocus()

    def on_kereses(self, event=None):
        """Végrehajtja a keresést a kiválasztott hatókörben."""
        keresett_szoveg = self.text_ctrl.GetValue().strip()
        if not keresett_szoveg:
            wx.MessageBox(
                "Kérjük, adja meg a keresett kifejezést!",
                "Keresés",
                wx.OK | wx.ICON_INFORMATION,
                parent=self,
            )
            self.text_ctrl.SetFocus()
            return

        kijelolt_oszlopok = self._kijelolt_oszlopok()
        if not kijelolt_oszlopok:
            wx.MessageBox(
                "Jelöljön ki legalább egy oszlopot a kereséshez!",
                "Nincs kijelölve oszlop",
                wx.OK | wx.ICON_INFORMATION,
                parent=self,
            )
            self.cb_osszes_oszlop.SetFocus()
            return

        # A keresés kizárólag a bejelölt oszlopokban fut (az "Összes oszlop"
        # is csak a táblázatban látható oszlopokat jelenti, a tétel további,
        # nem megjelenített mezőit - alcím, egyéb személyek, id stb. - nem).
        mezok = kijelolt_oszlopok

        # "Csak teljes szó": a keresett szavak egész szóként egyezzenek
        # (nem részszövegként). A szavak között "és" kapcsolat van: minden
        # szónak szerepelnie kell a kijelölt oszlopok valamelyikében.
        pontos_egyezes = self.exact_match_cb.IsChecked()
        scope = self.scope_choice.GetSelection()  # 0: Mindenhol, 1: Dezideráta, 2: Állomány

        self._utolso_kereses = {
            "keresett_szoveg": keresett_szoveg,
            "mezok": list(mezok),
            "pontos_egyezes": pontos_egyezes,
            "scope": scope,
        }
        self._kereses_vegrehajtasa(**self._utolso_kereses)

        # A fókusz minden keresés után a találati listára kerül - 0 találatnál
        # is, a KönyvTárnok-keresőhöz hasonlóan. A lista neve ilyenkor
        # "Találatok listája, 0 elem", így a képernyőolvasó felolvassa az
        # eredményt.
        self.list_ctrl.SetFocus()

        self.frissit_torles_gomb()
        self.Layout()

    def _kereses_vegrehajtasa(self, keresett_szoveg, mezok, pontos_egyezes, scope):
        """A megadott feltételekkel lefuttatja a keresést, és feltölti a találati
        listát (fókuszt nem mozgat, üzenetet nem ad)."""
        self._lista_uritese()

        allomany_talalatok = []
        deziderata_talalatok = []

        # 1. Keresés az állományban (0: Mindenhol vagy 2: Állomány)
        if scope in (0, 2):
            allomany_konyvek = self._get_allomany_adatok()
            allomany_talalatok = szuresi_talalatok(
                allomany_konyvek, keresett_szoveg, pontos_egyezes,
                mezok=mezok, szavankent=True,
            )

        # 2. Keresés a deziderátában (0: Mindenhol vagy 1: Dezideráta)
        if scope in (0, 1):
            dezi_tetelek = self._get_deziderata_adatok()
            deziderata_talalatok = szuresi_talalatok(
                dezi_tetelek, keresett_szoveg, pontos_egyezes,
                mezok=mezok, szavankent=True,
            )

        # 3. Eredmények összefűzése
        for k in allomany_talalatok:
            self._talalatok.append({"forras": "Állomány", "adat": k})
        for d in deziderata_talalatok:
            self._talalatok.append({"forras": "Dezideráta", "adat": d})

        # 4. Megjelenítés a listában
        for idx, talalat in enumerate(self._talalatok):
            k = talalat["adat"]
            forras = talalat["forras"]
            cim = str(k.get("cim", k.get("title", "")) or "")
            szerzo = str(k.get("szerzo", k.get("author", "")) or "")
            kiado = str(k.get("kiado", k.get("publisher", "")) or "")
            hely = str(k.get("hely", k.get("place", "")) or "")
            ev = str(k.get("ev", k.get("year", "")) or "")

            sor_idx = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), forras)
            self.list_ctrl.SetItem(sor_idx, 1, cim)
            self.list_ctrl.SetItem(sor_idx, 2, szerzo)
            self.list_ctrl.SetItem(sor_idx, 3, kiado)
            self.list_ctrl.SetItem(sor_idx, 4, hely)
            self.list_ctrl.SetItem(sor_idx, 5, ev)
            self.list_ctrl.SetItemData(sor_idx, idx)

        osszesen = len(self._talalatok)
        self.frissit_akadalymentesites(osszesen)

        if osszesen > 0:
            self.statusz_text.SetLabel(
                f"{osszesen} találat (Állomány: {len(allomany_talalatok)}, Dezideráta: {len(deziderata_talalatok)})"
            )
        else:
            self.statusz_text.SetLabel("Nincs találat.")

    def _kijelolt_talalat_kulcsa(self):
        """(kijelölt sor indexe, (forrás, id)) - az újrakeresés utáni
        visszaálláshoz. (-1, None), ha nincs kijelölés."""
        sor = self.list_ctrl.GetFirstSelected()
        if sor == -1:
            return -1, None
        adat_idx = self.list_ctrl.GetItemData(sor)
        if 0 <= adat_idx < len(self._talalatok):
            talalat = self._talalatok[adat_idx]
            return sor, (talalat["forras"], talalat["adat"].get("id"))
        return sor, None

    def _ujrakereses(self):
        """Az utoljára lefuttatott keresés megismétlése a friss adatokon.

        Szerkesztés után hívódik: ha a módosított tétel már nem felel meg a
        keresési feltételnek, eltűnik a találati listából. A kijelölés a
        tételen marad, ha az még szerepel a listában; különben a lista ugyanazon
        (vagy az utolsó) sorára kerül, így a billentyűzetes/képernyőolvasós
        felhasználó nem veszíti el a helyét."""
        if not self._utolso_kereses:
            return
        regi_sor, kulcs = self._kijelolt_talalat_kulcsa()
        self._kereses_vegrehajtasa(**self._utolso_kereses)

        db_van = self.list_ctrl.GetItemCount()
        if db_van:
            uj_sor = -1
            if kulcs is not None and kulcs[1] is not None:
                for i, talalat in enumerate(self._talalatok):
                    if (talalat["forras"], talalat["adat"].get("id")) == kulcs:
                        uj_sor = i
                        break
            if uj_sor == -1:
                uj_sor = min(max(regi_sor, 0), db_van - 1)
            self.list_ctrl.Select(uj_sor)
            self.list_ctrl.Focus(uj_sor)
            self.list_ctrl.EnsureVisible(uj_sor)
        self.list_ctrl.SetFocus()
        self.frissit_torles_gomb()
        self.Layout()

    def on_reszletek(self, event=None):
        """Megnyitja a kijelölt találat adatlapját."""
        selected_idx = self.list_ctrl.GetFirstSelected()
        if selected_idx == -1:
            wx.MessageBox(
                "Kérjük, jelöljön ki egy tételt a listából a részletek megtekintéséhez!",
                "Nincs kijelölés",
                wx.OK | wx.ICON_INFORMATION,
                parent=self,
            )
            return

        data_idx = self.list_ctrl.GetItemData(selected_idx)
        if 0 <= data_idx < len(self._talalatok):
            talalat = self._talalatok[data_idx]
            forras = talalat["forras"]
            adat = talalat["adat"]
            if forras == "Állomány":
                dlg = KonyvReszletekDialog(self, adat, db=self._get_db())
                dlg.ShowModal()
                dlg.Destroy()
            elif forras == "Dezideráta":
                dlg = DeziderataReszletekDialog(self, adat)
                dlg.ShowModal()
                dlg.Destroy()

    # Visszafelé kompatibilitási metódusok
    def get_search_text(self):
        """Visszaadja a beírt keresőszöveget."""
        return self.text_ctrl.GetValue()

    def is_exact_match(self):
        """Visszaadja, hogy be van-e jelölve a „Csak teljes szó”."""
        return self.exact_match_cb.IsChecked()
