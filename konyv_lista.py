import wx

from constants import DEFAULT_LATHATO_OSZLOPOK, OSZLOP_DEFINICIOK, OSZLOP_SULYOK
from gyors_kereses import GyorsListaKereso, osszes_kijelolt_index
# A rendezési/dátumfeldolgozó segédfüggvények (magyar_rendezesi_kulcs,
# konyv_mezo_rendezesi_kulcs) az utils.py-ba kerültek át, mert tisztán
# szöveg-/adatfeldolgozó logika, semmi közük a wx-hez - így más, nem-GUI
# modulok (statisztika.py, deziderata.py) is ezekből, nem pedig ebből a
# vizuális komponensből (KonyvListaCtrl) importálhatják őket.
# A konyv_mezo_rendezesi_kulcs (mezőtípus szerinti: szám/méret/dátum/
# magyar ábécé rendezési kulcs) ugyanaz a közös függvény, amit a
# statisztika.py jelentés-rendezése is használ - korábban ez a logika a
# KonyvListaCtrl.FeltoltLista helyi szam_kulcs/meret_kulcs függvényeiben
# és a StatisztikaDialog.on_szamol helyi riport_rendezes függvényében
# egymástól függetlenül, szó szerint megegyező formában volt megírva.
from utils import magyar_rendezesi_kulcs, konyv_mezo_rendezesi_kulcs


class KonyvListaCtrl(wx.ListCtrl):
    # Az oszlopdefiníciók és a súlyok a constants.py-ban élnek (egyetlen
    # forrás); osztályszintű néven azért érhetők el itt is, hogy a
    # KonyvListaCtrl.OSZLOP_DEFINICIOK-ra hivatkozó kód változatlanul működjön.
    OSZLOP_DEFINICIOK = OSZLOP_DEFINICIOK
    SULYOK = OSZLOP_SULYOK

    def __init__(self, parent, db, aktiv_oszlopok=None):
        super().__init__(parent, style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.BORDER_SUNKEN | wx.LC_HRULES | wx.LC_VRULES)
        self.db = db
        self.sor_id_terkep = {}
        self.jelenlegi_adatok = []
        self.rendezes_kulcs = "cim"

        self.gyors_kereses = GyorsListaKereso()

        if aktiv_oszlopok is None:
            self.aktiv_oszlopok = list(DEFAULT_LATHATO_OSZLOPOK)
        else:
            self.aktiv_oszlopok = aktiv_oszlopok

        self.InitOszlopok()
        self.FeltoltLista()
        
        self.Bind(wx.EVT_CHAR, self.OnChar)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def InitOszlopok(self):
        self.ClearAll()
        for idx, kulcs in enumerate(self.aktiv_oszlopok):
            if kulcs in self.OSZLOP_DEFINICIOK:
                nev, szelesseg = self.OSZLOP_DEFINICIOK[kulcs]
                self.InsertColumn(idx, nev, width=szelesseg)

    def SetAktivOszlopok(self, aktiv_oszlopok):
        self.aktiv_oszlopok = aktiv_oszlopok
        self.InitOszlopok()
        self.FeltoltLista()

    def GetKijeloltIndexek(self):
        return osszes_kijelolt_index(self)

    def GetKijeloltSzoveg(self):
        """A kijelölt sorok tabulátorral tagolt szövege a LÁTHATÓ oszlopokkal.

        A lista virtuális (LC_VIRTUAL), ezért a GetItemText nem használható:
        az értékeket ugyanonnan olvassuk, ahonnan az OnGetItemText is, így
        pontosan azt kapjuk, amit a felhasználó a képernyőn lát (az oszlopok
        sorrendje is az aktuális). Üres kijelölésnél üres szöveget ad.
        """
        sorok = []
        for idx in sorted(self.GetKijeloltIndexek()):
            if not (0 <= idx < len(self.jelenlegi_adatok)):
                continue
            konyv = self.jelenlegi_adatok[idx]
            cellak = []
            for kulcs in self.aktiv_oszlopok:
                if kulcs not in self.OSZLOP_DEFINICIOK:
                    continue
                ertek = konyv.get(kulcs, "")
                ertek = "" if ertek is None else str(ertek)
                # A cellán belüli tabulátor/sortörés szétverné a sor- és
                # oszlopszerkezetet a beillesztéskor.
                cellak.append(" ".join(ertek.split()))
            sorok.append("\t".join(cellak))
        return "\n".join(sorok)

    def GetKonyvByRowIndex(self, index):
        if 0 <= index < len(self.jelenlegi_adatok):
            return self.jelenlegi_adatok[index]
        return None

    def Rendezes(self, mezo_kulcs):
        self.rendezes_kulcs = mezo_kulcs
        # A szűrt lista megtartásával rendezünk újra
        self.FeltoltLista(self.jelenlegi_adatok)

    def FeltoltLista(self, adatok=None):
        self.sor_id_terkep.clear()

        if adatok is not None:
            self.jelenlegi_adatok = list(adatok)
        else:
            self.jelenlegi_adatok = list(self.db.konyvek)

        akt_rendezes = self.rendezes_kulcs if self.rendezes_kulcs else "cim"

        def osszetett_rendezesi_kulcs(konyv):
            raw_val = konyv.get(akt_rendezes, "")
            
            # Ellenőrizzük, hogy a mező üres-e (None, üres sztring vagy csak szóközök)
            is_empty = raw_val is None or str(raw_val).strip() == ""
            hianyos = 1 if is_empty else 0

            # 1. Elsődleges rendezési érték kiszámítása - a mezőtípus szerinti
            # (szám/méret/dátum/magyar ábécé) döntést az utils.konyv_mezo_
            # rendezesi_kulcs közös függvénye végzi (lásd az importnál lévő
            # kommentet).
            elso = konyv_mezo_rendezesi_kulcs(akt_rendezes, raw_val)
            
            # 2. Másodlagos és harmadlagos rendezési értékek
            if akt_rendezes == "cim":
                masod = magyar_rendezesi_kulcs(konyv.get("szerzo", ""))
                harmad = magyar_rendezesi_kulcs(konyv.get("ev", ""))
            elif akt_rendezes == "szerzo":
                masod = magyar_rendezesi_kulcs(konyv.get("cim", ""))
                harmad = magyar_rendezesi_kulcs(konyv.get("ev", ""))
            else:
                masod = magyar_rendezesi_kulcs(konyv.get("cim", ""))
                harmad = magyar_rendezesi_kulcs(konyv.get("szerzo", ""))

            # A tuple első eleme a 'hianyos' jelző: 0 = van adat (előre), 1 = nincs adat (a lista végére)
            return (hianyos, elso, masod, harmad)

        self.jelenlegi_adatok.sort(key=osszetett_rendezesi_kulcs)

        for idx, konyv in enumerate(self.jelenlegi_adatok):
            self.sor_id_terkep[idx] = konyv.get("id")

        # Az összes kijelölés ÉS a fókusz törlése egyetlen hívással (-1 = minden
        # elem); virtuális listánál nem kell soronként végigmenni. A fókuszt még
        # a SetItemCount előtt töröljük, amikor a régi elemszám még érvényes.
        self.SetItemState(-1, 0, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)

        # Aktív oszlop nélkül nincs mit megjeleníteni (0 sor), de az adatok
        # (szűrés, rendezés) ilyenkor is frissülnek, nem maradnak régiek.
        count = len(self.jelenlegi_adatok) if self.aktiv_oszlopok else 0
        # A 0-ra állítás nullázza a natív lista belső állapotát (fókusz,
        # kijelölés), így szűkülő listánál nem maradhat érvénytelen index.
        self.SetItemCount(0)
        self.SetItemCount(count)
        # Szándékosan nincs self.Focus(0): a lista első sora így sem kijelölve,
        # sem fókuszban nincs, amíg a felhasználó nem lép a listában.
        # (Ha a fókusz nélküli állapot gondot okozna, a következő két sor
        # visszaállítja az első sor fókuszát.)
        # if count > 0:
        #     self.Focus(0)
        if count > 0:
            # Üres listánál az igazítás kimarad (lásd IgazitOszlopSzelesseg),
            # ezért a lista megtelésekor itt pótoljuk.
            self.IgazitOszlopSzelesseg()
        self.Refresh()

    def OnGetItemText(self, item, col):
        if 0 <= item < len(self.jelenlegi_adatok):
            konyv = self.jelenlegi_adatok[item]
            if 0 <= col < len(self.aktiv_oszlopok):
                kulcs = self.aktiv_oszlopok[col]
                return str(konyv.get(kulcs, ""))
        return ""

    def OnGetItemAttr(self, item):
        return None

    def FeldolgozKarakter(self, karakter):
        def kijeloles_beallitasa(talalt_idx):
            for sel_idx in self.GetKijeloltIndexek():
                self.Select(sel_idx, False)
            self.Select(talalt_idx, True)
            self.Focus(talalt_idx)
            self.EnsureVisible(talalt_idx)

        self.gyors_kereses.feldolgoz(
            karakter,
            total_lekero=lambda: len(self.jelenlegi_adatok),
            szoveg_lekero=lambda i: self.jelenlegi_adatok[i].get("cim", ""),
            kivalasztott_lekero=self.GetFirstSelected,
            kivalasztas_beallito=kijeloles_beallitasa,
        )

    def OnChar(self, event):
        self.gyors_kereses.kezel_char_esemeny(event, self.FeldolgozKarakter)

    def OnSize(self, event):
        event.Skip()
        self.IgazitOszlopSzelesseg()

    def IgazitOszlopSzelesseg(self):
        # Üres virtuális listán a SetColumnWidth Windowson érvénytelen elemre
        # hivatkozik (GetSubItemRect assertion), ezért ilyenkor kihagyjuk; az
        # oszlopok addig megtartják az utolsó szélességüket.
        if self.GetItemCount() == 0:
            return

        szerel_szelesseg = self.GetClientSize().width - wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X)
        
        osszes_alap = sum(self.OSZLOP_DEFINICIOK[k][1] for k in self.aktiv_oszlopok if k in self.OSZLOP_DEFINICIOK)
        
        if osszes_alap > 0 and szerel_szelesseg > osszes_alap:
            maradek_hely = szerel_szelesseg - osszes_alap
            osszes_suly = sum(self.SULYOK.get(k, 1.0) for k in self.aktiv_oszlopok if k in self.OSZLOP_DEFINICIOK)
            
            for i, kulcs in enumerate(self.aktiv_oszlopok):
                if kulcs in self.OSZLOP_DEFINICIOK:
                    alap = self.OSZLOP_DEFINICIOK[kulcs][1]
                    suly = self.SULYOK.get(kulcs, 1.0)
                    plusz_szelesseg = int(maradek_hely * (suly / osszes_suly))
                    self.SetColumnWidth(i, alap + plusz_szelesseg)
        else:
            for i, kulcs in enumerate(self.aktiv_oszlopok):
                if kulcs in self.OSZLOP_DEFINICIOK:
                    self.SetColumnWidth(i, self.OSZLOP_DEFINICIOK[kulcs][1])