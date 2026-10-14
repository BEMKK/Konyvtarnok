import logging
import wx

from theme_manager import apply_theme_from_settings
from data_manager import szuresi_talalatok, load_hmac_json, DEFAULT_ADATBAZIS_FAJL
from deziderata import DATA_FILE as DEZIDERATA_DATA_FILE
from konyvdialogs import KonyvReszletekDialog, DeziderataReszletekDialog
from utils import masolas_vagolapra_szoveg


class KeresoDialog(wx.Dialog):
    """Összesített kereső párbeszédablak saját találati listával.

    Egyetlen felületen teszi lehetővé a keresést az állományjegyzékben,
    a dezideráta-jegyzékben vagy mindkettőben egyszerre. A találatokból
    közvetlenül megnyitható az adott tétel részletes adatlapja (olvasó nézet).

    Tabulátorsorrend (a vezérlők létrehozási sorrendje határozza meg):
    Keresés helye, Csak pontos egyezés, Keresett kifejezés, Keresés törlése,
    Keresés, Találati lista, Részletek, Bezárás.
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

        # 2. Csak pontos egyezés
        self.exact_match_cb = wx.CheckBox(self, label="Csak &pontos egyezés")

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

        # 6. Találati lista (felirat + táblázat)
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

        # 7. Részletek
        self.btn_reszletek = wx.Button(self, label="Részletek...")
        self.btn_reszletek.Bind(wx.EVT_BUTTON, self.on_reszletek)

        # 8. Bezárás
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

    def _get_allomany_adatok(self):
        """Visszaadja a könyvállomány legfrissebb adatait."""
        if hasattr(self.parent, "db") and getattr(self.parent.db, "konyvek", None) is not None:
            return list(self.parent.db.konyvek)
        if hasattr(self.parent, "teljes_adatlista") and self.parent.teljes_adatlista:
            return list(self.parent.teljes_adatlista)
        if (
            hasattr(self.parent, "parent")
            and hasattr(self.parent.parent, "db")
            and getattr(self.parent.parent.db, "konyvek", None) is not None
        ):
            return list(self.parent.parent.db.konyvek)

        try:
            adatok, ervenyes = load_hmac_json(DEFAULT_ADATBAZIS_FAJL)
            if isinstance(adatok, list):
                return [k for k in adatok if isinstance(k, dict)]
        except Exception as e:
            logging.warning(f"Hiba az állományfájl betöltésekor: {e}")
        return []

    def _get_deziderata_adatok(self):
        """Visszaadja a dezideráta jegyzék legfrissebb adatait."""
        if (
            hasattr(self.parent, "deziderata_frame")
            and self.parent.deziderata_frame is not None
            and hasattr(self.parent.deziderata_frame, "items")
        ):
            return list(self.parent.deziderata_frame.items)
        if hasattr(self.parent, "items") and hasattr(self.parent, "load_data"):
            return list(self.parent.items)
        if (
            hasattr(self.parent, "parent")
            and hasattr(self.parent.parent, "deziderata_frame")
            and self.parent.parent.deziderata_frame is not None
            and hasattr(self.parent.parent.deziderata_frame, "items")
        ):
            return list(self.parent.parent.deziderata_frame.items)

        try:
            adatok, ervenyes = load_hmac_json(DEZIDERATA_DATA_FILE)
            if isinstance(adatok, list):
                return [d for d in adatok if isinstance(d, dict)]
        except Exception as e:
            logging.warning(f"Hiba a deziderátafájl betöltésekor: {e}")
        return []

    def _get_db(self):
        """Visszaadja a KonyvAdatbazis példányt, ha elérhető."""
        if hasattr(self.parent, "db"):
            return self.parent.db
        if hasattr(self.parent, "parent") and hasattr(self.parent.parent, "db"):
            return self.parent.parent.db
        return None

    # =========================================================================
    # SZERKESZTÉSI VISSZAJELZÉSEK KEZELÉSE
    # =========================================================================

    def frissit_lista_szerkesztes_utan(self, konyv_id):
        """Ha a részletek dialógusból indított könyvszerkesztés sikeres volt."""
        if hasattr(self.parent, "frissit_lista_szerkesztes_utan"):
            self.parent.frissit_lista_szerkesztes_utan(konyv_id)
        elif hasattr(self.parent, "parent") and hasattr(self.parent.parent, "frissit_lista_szerkesztes_utan"):
            self.parent.parent.frissit_lista_szerkesztes_utan(konyv_id)
        self.on_kereses()

    def tetel_modositasa(self, tetel_id, uj_adatok, eredeti_sorindex=None):
        """Ha a részletek dialógusból indított dezideráta módosítás sikeres volt."""
        if hasattr(self.parent, "tetel_modositasa"):
            self.parent.tetel_modositasa(tetel_id, uj_adatok, eredeti_sorindex)
        elif (
            hasattr(self.parent, "deziderata_frame")
            and self.parent.deziderata_frame is not None
            and hasattr(self.parent.deziderata_frame, "tetel_modositasa")
        ):
            self.parent.deziderata_frame.tetel_modositasa(tetel_id, uj_adatok, eredeti_sorindex)
        self.on_kereses()

    # =========================================================================
    # AKADÁLYMENTESÍTÉS ÉS BILLENTYŰKEZELÉS
    # =========================================================================

    def frissit_akadalymentesites(self, darabszam):
        """Beállítja a táblázat belső nevét és a felette lévő feliratot."""
        szoveg = f"Találatok listája, {darabszam} elem"
        self.eredmeny_szoveg.SetLabel(f"Találatok ({darabszam} db):")
        self.list_ctrl.SetName(szoveg)

    def frissit_torles_gomb(self):
        """A Keresés törlése gomb csak akkor érhető el, ha van szöveg a mezőben
        vagy találat a listában."""
        van_szoveg = bool(self.text_ctrl.GetValue())
        van_talalat = self.list_ctrl.GetItemCount() > 0
        self.btn_clear.Enable(van_szoveg or van_talalat)

    def on_text_changed(self, event):
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
    # KERESÉS ÉS VEZÉRLÉS
    # =========================================================================

    def on_clear(self, event=None):
        """Kiüríti a keresőmezőt és a találati listát."""
        self.text_ctrl.Clear()
        self.list_ctrl.DeleteAllItems()
        self._talalatok = []
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

        pontos_egyezes = self.exact_match_cb.IsChecked()
        scope = self.scope_choice.GetSelection()  # 0: Mindenhol, 1: Dezideráta, 2: Állomány

        self.list_ctrl.DeleteAllItems()
        self._talalatok = []

        allomany_talalatok = []
        deziderata_talalatok = []

        # 1. Keresés az állományban (0: Mindenhol vagy 2: Állomány)
        if scope in (0, 2):
            allomany_konyvek = self._get_allomany_adatok()
            allomany_talalatok = szuresi_talalatok(
                allomany_konyvek, keresett_szoveg, pontos_egyezes
            )

        # 2. Keresés a deziderátában (0: Mindenhol vagy 1: Dezideráta)
        if scope in (0, 1):
            dezi_tetelek = self._get_deziderata_adatok()
            deziderata_talalatok = szuresi_talalatok(
                dezi_tetelek, keresett_szoveg, pontos_egyezes
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
            self.list_ctrl.SetFocus()
        else:
            # Találat nélkül a fókusz a keresőmezőn marad, hogy rögtön lehessen módosítani a kifejezést
            self.statusz_text.SetLabel("Nincs találat.")
            self.text_ctrl.SetFocus()

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
        """Visszaadja, hogy be van-e jelölve a pontos egyezés."""
        return self.exact_match_cb.IsChecked()
