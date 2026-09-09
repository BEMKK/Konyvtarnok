import os
import sys
import time
import json
import wx
import logging
from config_manager import load_settings
from theme_manager import apply_theme

class KonyvtarnokKeresoApp(wx.Frame):

    def __init__(self, parent=None):
        super().__init__(
            parent=None, title="KönyvTárnok kereső", size=(1000, 600)
        )

        self.parent = parent
        self.SetName("KönyvTárnok kereső")

        self.panel = wx.Panel(self)
        self.panel.SetName("Főpanel")

        # 1. JSON fájl betöltése a háttérben
        self.json_fajlnev = "Enekeskonyvek_adatai.json"  # Excel helyett JSON
        self.oszlopok = []
        self.adatok = self.adatok_betoltese()

        # Gyorskeresés pufferek
        self.beepitett_kereses_buffer = ""
        self.utolso_leutes_ideje = 0
        self.IDO_KUSZOB = 1.2

        # UI elemek létrehozása
        self.init_ui()

        # Gyorsbillentyű tábla a Ctrl+W bezáráshoz
        self.init_shortcuts()

        # Téma alkalmazása
        config = load_settings()
        self.current_theme = config.get("tema", "vilagos")
        apply_theme(self, self.current_theme)

    def adatok_betoltese(self):
        """Beolvassa a JSON fájlt a megfelelő mappából."""
        fajl_utvonal = None

        if getattr(sys, "frozen", False):
            # 1. Ha csomagolt EXE: először megnézzük az EXE mellett
            exe_mappa = os.path.dirname(sys.executable)
            fajl_utvonal = os.path.join(exe_mappa, self.json_fajlnev)

            # 2. Ha az EXE mellett nincs ott, a Temp (_MEIPASS) mappában keresünk
            if not os.path.exists(fajl_utvonal):
                temp_mappa = getattr(sys, "_MEIPASS", exe_mappa)
                fajl_utvonal = os.path.join(temp_mappa, self.json_fajlnev)
        else:
            # 3. Fejlesztői környezet (.py futtatása esetén ez fut le!)
            sajat_mappa = os.path.dirname(os.path.abspath(__file__))
            fajl_utvonal = os.path.join(sajat_mappa, self.json_fajlnev)

        # 4. Beolvasás ellenőrzése JSON modul segítségével
        if fajl_utvonal and os.path.exists(fajl_utvonal):
            try:
                with open(fajl_utvonal, "r", encoding="utf-8") as f:
                    adatok = json.load(f)

                if isinstance(adatok, list) and len(adatok) > 0:
                    # Dinamikusan kinyerjük az első elemből a mezőneveket (oszlopokat)
                    self.oszlopok = list(adatok[0].keys())

                    # Biztosítjuk, hogy minden érték sztring formátumú legyen a GUI-hoz
                    adat_lista = []
                    for sor in adatok:
                        szurt_sor = {k: str(v).strip() if v is not None else "" for k, v in sor.items()}
                        adat_lista.append(szurt_sor)

                    return adat_lista
                return []

            except Exception as e:
                logging.error(f"Hiba a JSON fájl ({fajl_utvonal}) beolvasásakor: {e}", exc_info=True)
                wx.MessageBox(
                    f"Hiba a fájl beolvasásakor:\n{e}",
                    "Hiba",
                    wx.OK | wx.ICON_ERROR,
                )
                return None
        else:
            wx.MessageBox(
                f"A(z) '{self.json_fajlnev}' nem található a program mappájában!\n\nKeresett útvonal:\n{fajl_utvonal}",
                "Fájl hiányzik",
                wx.OK | wx.ICON_WARNING,
            )
            return None

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

        # Meglévő könyvek címeinek összegyűjtése a főablaktól
        meglevo_cimek = set()
        if self.parent and hasattr(self.parent, "db"):
            if hasattr(self.parent.db, "konyvek") and self.parent.db.konyvek:
                for k in self.parent.db.konyvek:
                    cim = str(k.get("cim", "")).strip().lower()
                    if cim:
                        meglevo_cimek.add(cim)

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

            # Cím oszlop megkeresése
            cim_oszlop_neve = None
            for col in self.oszlopok:
                if str(col).strip().lower() in ["cím", "cim"]:
                    cim_oszlop_neve = col
                    break
            if not cim_oszlop_neve:
                cim_oszlop_neve = self.oszlopok[0]

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

                sor_cime = str(sor.get(cim_oszlop_neve, "")).strip().lower()

                # Státusz ellenőrzése
                megvan = False
                if sor_cime and meglevo_cimek:
                    megvan = sor_cime in meglevo_cimek

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

    def feldolgoz_kereso_karakter(self, karakter):
        """Kezeli a karakter hozzáadását a keresési pufferhez és a megfelelő sorra ugrást.
        
        Ha egyetlen betűt nyom le ismételten, a lista körkörösen lép a következő egyező elemre.
        """
        if not karakter:
            return

        aktualis_ido = time.time()
        elozo_buffer = self.beepitett_kereses_buffer

        if aktualis_ido - self.utolso_leutes_ideje > self.IDO_KUSZOB:
            self.beepitett_kereses_buffer = ""
            elozo_buffer = ""

        if karakter == ' ':
            if not self.beepitett_kereses_buffer:
                return
            self.beepitett_kereses_buffer += ' '
        elif karakter.strip():
            # Ismételt egykarakteres leütés detektálása (MIELŐTT a pufferhez adnánk)
            is_single_char_repeat = (
                len(elozo_buffer) == 1 and
                karakter.lower() == elozo_buffer.lower()
            )
            if is_single_char_repeat:
                # Nem bővítjük a puffert, marad az 1 karakteres állapot
                pass
            else:
                self.beepitett_kereses_buffer += karakter
        else:
            return

        self.utolso_leutes_ideje = aktualis_ido
        keresett = self.beepitett_kereses_buffer.lower()
        total = self.tablazat.GetItemCount()
        if total == 0:
            return

        # Ciklikus keresés: ha 1 karakteres puffer és ugyanazt nyomták le,
        # a jelenlegi kijelöléstől kezdve keresünk tovább (körkörösen)
        is_single_char_repeat = (
            len(keresett) == 1 and
            len(elozo_buffer) == 1 and
            keresett == elozo_buffer.lower()
        )

        current_idx = self.tablazat.GetFirstSelected()
        if is_single_char_repeat and current_idx != -1:
            start_idx = (current_idx + 1) % total
        else:
            start_idx = 0

        def keres_elo_tag(keresendo, tol, korokre=False):
            for i in range(tol, total):
                ertek = str(self.tablazat.GetItemText(i)).lower().strip()
                if ertek.startswith(keresendo):
                    return i
            if korokre:
                for i in range(0, tol):
                    ertek = str(self.tablazat.GetItemText(i)).lower().strip()
                    if ertek.startswith(keresendo):
                        return i
            return -1

        # 1. Pontos előtag egyezés keresése
        talalt = keres_elo_tag(keresett, start_idx, korokre=is_single_char_repeat)

        # 2. Ha nincs találat és nem körkörösen kerestünk, próbáljuk az elejéről
        if talalt == -1 and not is_single_char_repeat:
            talalt = keres_elo_tag(keresett, 0)


        if talalt != -1:
            for i in range(total):
                self.tablazat.Select(i, False)
            self.tablazat.Select(talalt, True)
            self.tablazat.Focus(talalt)
            self.tablazat.EnsureVisible(talalt)

    def on_char(self, event):
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_BACK:
            if len(self.beepitett_kereses_buffer) > 0:
                self.beepitett_kereses_buffer = self.beepitett_kereses_buffer[:-1]
            return

        karakter = ""
        unicode_key = event.GetUnicodeKey()
        if unicode_key != wx.WXK_NONE:
            try:
                karakter = chr(unicode_key).lower()
            except Exception:
                pass
        
        if not karakter and 32 <= key_code <= 255:
            try:
                karakter = chr(key_code).lower()
            except Exception:
                pass

        if karakter:
            self.feldolgoz_kereso_karakter(karakter)
        else:
            event.Skip()

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

        self.Bind(
            wx.EVT_MENU, lambda e: self.masolas_vagolapra(), masolas_item
        )
        self.Bind(
            wx.EVT_MENU, lambda e: self.atemeles_allomanyba(), atemeles_item
        )
        self.Bind(
            wx.EVT_MENU, lambda e: self.atemeles_deziderataba(), deziderata_item
        )

        self.PopupMenu(menu)
        menu.Destroy()

    def masolas_vagolapra(self):
        """Kiolvassa az összes kijelölt sort és a vágólapra helyezi őket (bezárás után is megmarad)."""
        kijelolt_indexek = []
        item = self.tablazat.GetFirstSelected()

        while item != -1:
            kijelolt_indexek.append(item)
            item = self.tablazat.GetNextSelected(item)

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

        sikeres = False
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(teljes_szoveg))
            wx.TheClipboard.Flush()  # Biztosítja, hogy az adatok a program bezárása után is a rendszer-vágólapon maradjanak
            wx.TheClipboard.Close()
            sikeres = True
        else:
            sikeres = self._masolas_win32_vagolapra(teljes_szoveg)

        if not sikeres:
            wx.MessageBox(
                "Nem sikerült megnyitni a vágólapot.",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )

    def _masolas_win32_vagolapra(self, szoveg):
        """Windows API segítségével másol a vágólapra (biztonsági tartalék)."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            GMEM_MOVEABLE = 0x0002
            CF_UNICODETEXT = 13

            if user32.OpenClipboard(None):
                user32.EmptyClipboard()
                encoded = szoveg.encode('utf-16le') + b'\x00\x00'
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
                if h_mem:
                    p_mem = kernel32.GlobalLock(h_mem)
                    ctypes.memmove(p_mem, encoded, len(encoded))
                    kernel32.GlobalUnlock(h_mem)
                    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                user32.CloseClipboard()
                return True
        except Exception as e:
            logging.error(f"Win32 vágólap másolási hiba: {e}")
        return False

    def atemeles_allomanyba(self):
        if not self.parent or not hasattr(self.parent, "db"):
            wx.MessageBox(
                "Az átemelés nem lehetséges, mert a kereső önállóan fut!",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return

        kijelolt_indexek = []
        item = self.tablazat.GetFirstSelected()

        while item != -1:
            kijelolt_indexek.append(item)
            item = self.tablazat.GetNextSelected(item)

        if not kijelolt_indexek:
            wx.MessageBox(
                "Nincs kijelölve egyetlen elem sem!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_WARNING,
            )
            return

        db = len(kijelolt_indexek)
        uzenet = f"Biztosan át szeretnéd emelni a kijelölt {db} db találatot az állományba?" if db > 1 else "Biztosan át szeretnéd emelni a kijelölt találatot az állományba?"
        
        confirm = wx.MessageBox(uzenet, "Átemelés megerősítése", wx.YES_NO | wx.ICON_QUESTION)
        if confirm != wx.YES:
            return

        excel_oszlopok_szama = len(self.oszlopok) if self.oszlopok else 0
        oszlop_nevek = [
            self.tablazat.GetColumn(i).GetText()
            for i in range(excel_oszlopok_szama)
        ]

        sikeres = 0
        visszautasitott = 0

        for sor_idx in kijelolt_indexek:
            konyv_adat = {}
            for col_idx in range(excel_oszlopok_szama):
                kulcs = oszlop_nevek[col_idx]
                ertek = self.tablazat.GetItemText(sor_idx, col_idx)
                konyv_adat[kulcs] = ertek

            alap_adat = {
                "cim": konyv_adat.get("cim", konyv_adat.get("Cím", "")),
                "alcim": konyv_adat.get("alcim", konyv_adat.get("Alcím", "")),
                "szerzo": konyv_adat.get(
                    "szerzo", konyv_adat.get("Összeállító", "")
                ),
                "egyeb_szemelyek": konyv_adat.get("egyeb_szemelyek", konyv_adat.get("Egyéb személyek", "")),
                "kiado": konyv_adat.get("kiado", konyv_adat.get("Kiadó", "")),
                "hely": konyv_adat.get(
                    "hely", konyv_adat.get("Kiadás helye", "")
                ),
                "ev": konyv_adat.get("ev", konyv_adat.get("Kiadás éve", "")),
                "oldalszam": konyv_adat.get("oldalszam", ""),
                "meretek": konyv_adat.get("meretek", ""),
                "kotes": konyv_adat.get("kotes", ""),
                "rovid_cim": konyv_adat.get("rovid_cim", ""),
                "forras": konyv_adat.get("forras", ""),
                "status": konyv_adat.get("status", ""),
                "rovid_leiras": konyv_adat.get("rovid_leiras", ""),
            }

            if alap_adat["cim"].strip():
                if self.parent.db.uj_konyv_hozzaadasa(alap_adat):
                    sikeres += 1
                else:
                    visszautasitott += 1

        if hasattr(self.parent, "lista"):
            self.parent.lista.FeltoltLista()
            self.parent.FrissitStatusBar()

        if sikeres > 0:
            uzenet = "Az átemelés sikeresen megtörtént!\n\n"
            uzenet += f"• Hozzáadva az állományhoz: {sikeres} db könyv.\n"
            if visszautasitott > 0:
                uzenet += "\nMegjegyzés:\n"
                uzenet += f"• {visszautasitott} db könyv már szerepel az állományban (duplikátum), így nem került újra felvételre."

            wx.MessageBox(uzenet, "Átemelés sikeres", wx.OK | wx.ICON_INFORMATION)

        elif visszautasitott > 0:
            wx.MessageBox(
                f"Az átemelés nem történt meg!\n\nA kiválasztott könyv(ek) ({visszautasitott} db) már szerepel(nek) az állományban.",
                "Átemelés sikertelen",
                wx.OK | wx.ICON_WARNING,
            )
        else:
            wx.MessageBox(
                "Nem sikerült átemelni a kiválasztott elemeket.",
                "Átemelés sikertelen",
                wx.OK | wx.ICON_ERROR,
            )

    def _get_cipher(self):
        """Meghatározza és visszaadja a Fernet cipher objektumot a titkosításhoz."""
        if self.parent and hasattr(self.parent, "db") and hasattr(self.parent.db, "cipher") and self.parent.db.cipher:
            return self.parent.db.cipher
        elif self.parent and hasattr(self.parent, "cipher") and self.parent.cipher:
            return self.parent.cipher

        try:
            from cryptography.fernet import Fernet
            appdata_dir = os.path.join(os.path.expanduser("~"), ".konyvtar_app")
            key_file_path = os.path.join(appdata_dir, "secret.key")
            if os.path.exists(key_file_path):
                with open(key_file_path, "rb") as kf:
                    key = kf.read()
                return Fernet(key)
        except Exception as e:
            logging.error(f"Nem sikerült betölteni a titkosítási kulcsot: {e}")
        return None

    def atemeles_deziderataba(self):
        import json
        import uuid

        if not self.parent:
            wx.MessageBox(
                "Az átemelés nem lehetséges, mert a kereső önállóan fut!",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return

        kijelolt_indexek = []
        item = self.tablazat.GetFirstSelected()

        while item != -1:
            kijelolt_indexek.append(item)
            item = self.tablazat.GetNextSelected(item)

        if not kijelolt_indexek:
            wx.MessageBox(
                "Nincs kijelölve egyetlen elem sem!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_WARNING,
            )
            return

        db = len(kijelolt_indexek)
        uzenet = f"Biztosan át szeretnéd emelni a kijelölt {db} db találatot a deziderátába?" if db > 1 else "Biztosan át szeretnéd emelni a kijelölt találatot a deziderátába?"
        
        confirm = wx.MessageBox(uzenet, "Átemelés megerősítése", wx.YES_NO | wx.ICON_QUESTION)
        if confirm != wx.YES:
            return

        excel_oszlopok_szama = len(self.oszlopok) if self.oszlopok else 0
        oszlop_nevek = [
            self.tablazat.GetColumn(i).GetText()
            for i in range(excel_oszlopok_szama)
        ]

        cipher = self._get_cipher()
        json_fajl = "deziderata.json"
        deziderata_lista = []

        if os.path.exists(json_fajl):
            try:
                with open(json_fajl, "rb") as f:
                    nyers_adat = f.read()

                if cipher:
                    try:
                        decrypted_bytes = cipher.decrypt(nyers_adat)
                        betoltott = json.loads(decrypted_bytes.decode("utf-8"))
                    except Exception:
                        betoltott = json.loads(nyers_adat.decode("utf-8"))
                else:
                    betoltott = json.loads(nyers_adat.decode("utf-8"))

                if isinstance(betoltott, list):
                    deziderata_lista = [x for x in betoltott if isinstance(x, dict)]
            except Exception as e:
                logging.error(f"Hiba a dezideráta adatbázis beolvasásakor: {e}", exc_info=True)
                deziderata_lista = []

        def norm(val):
            return str(val or "").strip().lower()

        def is_duplicate(candidate, target_list):
            for item in target_list:
                if (
                    norm(candidate.get("cim")) == norm(item.get("cim", item.get("title", ""))) and
                    norm(candidate.get("szerzo")) == norm(item.get("szerzo", item.get("author", ""))) and
                    norm(candidate.get("egyeb_szemelyek")) == norm(item.get("egyeb_szemelyek", item.get("egyeb_szemelyek", ""))) and
                    norm(candidate.get("kiado")) == norm(item.get("kiado", item.get("publisher", ""))) and
                    norm(candidate.get("hely")) == norm(item.get("hely", item.get("place", ""))) and
                    norm(candidate.get("ev")) == norm(str(item.get("ev", item.get("year", ""))))
                ):
                    return True
            return False

        sikeres = 0
        visszautasitott = 0

        for sor_idx in kijelolt_indexek:
            konyv_adat = {}
            for col_idx in range(excel_oszlopok_szama):
                kulcs = oszlop_nevek[col_idx]
                ertek = self.tablazat.GetItemText(sor_idx, col_idx)
                konyv_adat[kulcs] = ertek

            alap_adat = {
                "id": str(uuid.uuid4()),
                "cim": konyv_adat.get("cim", konyv_adat.get("Cím", "")),
                "szerzo": konyv_adat.get("szerzo", konyv_adat.get("Összeállító", "")),
                "egyeb_szemelyek": konyv_adat.get("egyeb_szemelyek", konyv_adat.get("Egyéb személyek", "")),
                "kiado": konyv_adat.get("kiado", konyv_adat.get("Kiadó", "")),
                "hely": konyv_adat.get("hely", konyv_adat.get("Kiadás helye", "")),
                "ev": konyv_adat.get("ev", konyv_adat.get("Kiadás éve", "")),
                "priority": "Másodlagos",
                "status": "Jelenleg nem kapható",
                "location": "",
                "price": ""
            }

            if alap_adat["cim"].strip():
                if not is_duplicate(alap_adat, deziderata_lista):
                    deziderata_lista.append(alap_adat)
                    sikeres += 1
                else:
                    visszautasitott += 1

        try:
            json_str = json.dumps(deziderata_lista, ensure_ascii=False, indent=4)
            if cipher:
                mentendo_bajtok = cipher.encrypt(json_str.encode("utf-8"))
            else:
                mentendo_bajtok = json_str.encode("utf-8")

            with open(json_fajl, "wb") as f:
                f.write(mentendo_bajtok)
        except Exception as e:
            logging.error(f"Hiba a dezideráta mentése közben: {e}", exc_info=True)
            wx.MessageBox(
                f"Hiba történt a dezideráta mentése közben:\n{e}",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return

        if hasattr(self.parent, "deziderata_frame") and self.parent.deziderata_frame is not None:
            self.parent.deziderata_frame.items = deziderata_lista
            self.parent.deziderata_frame.refresh_list()

        if sikeres > 0:
            uzenet = "Az átemelés sikeresen megtörtént!\n\n"
            uzenet += f"• Felvéve a dezideráta-jegyzékbe: {sikeres} db könyv.\n"
            if visszautasitott > 0:
                uzenet += "\nMegjegyzés:\n"
                uzenet += f"• {visszautasitott} db könyv már szerepel a kívánságlistán (duplikátum), így nem került újra felvételre."

            wx.MessageBox(uzenet, "Átemelés sikeres", wx.OK | wx.ICON_INFORMATION)

        elif visszautasitott > 0:
            wx.MessageBox(
                f"Az átemelés nem történt meg!\n\nA kiválasztott könyv(ek) ({visszautasitott} db) már szerepel(nek) a dezideráta-jegyzékben.",
                "Átemelés sikertelen",
                wx.OK | wx.ICON_WARNING,
            )
        else:
            wx.MessageBox(
                "Nem sikerült átemelni a kiválasztott elemeket.",
                "Átemelés sikertelen",
                wx.OK | wx.ICON_ERROR,
            )


if __name__ == "__main__":
    app = wx.App()
    KonyvtarnokKeresoApp(parent=None)
    app.MainLoop()