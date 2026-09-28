import wx

from constants import DEFAULT_LATHATO_OSZLOPOK
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
    OSZLOP_DEFINICIOK = {
        "cim": ("Cím", 200),
        "alcim": ("Alcím", 180),
        "szerzo": ("Összeállító", 180),
        "egyeb_szemelyek": ("Egyéb személyek", 150),
        "kiado": ("Kiadó", 180),
        "hely": ("Kiadás helye", 110),
        "ev": ("Kiadás éve", 90),
        "oldalszam": ("Oldalszám", 80),
        "meretek": ("Méret", 90),
        "kotes": ("Kötés", 90),
        "rovid_cim": ("Rövid cím", 120),
        "bekerult": ("Bekerült", 100),
        "forras": ("Forrás", 80),
        "status": ("Státusz", 100)
    }

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

        # Az összes kijelölés törlése egyetlen hívással (-1 = minden elem);
        # virtuális listánál nem kell soronként végigmenni.
        self.SetItemState(-1, 0, wx.LIST_STATE_SELECTED)

        # Aktív oszlop nélkül nincs mit megjeleníteni (0 sor), de az adatok
        # (szűrés, rendezés) ilyenkor is frissülnek, nem maradnak régiek.
        count = len(self.jelenlegi_adatok) if self.aktiv_oszlopok else 0
        self.SetItemCount(count)
        if count > 0:
            self.Focus(0)
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
        szerel_szelesseg = self.GetClientSize().width - wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X)
        
        SULYOK = {
            "cim": 3.0, "alcim": 2.5, "szerzo": 2.0, "egyeb_szemelyek": 2.0,
            "kiado": 2.0, "rovid_cim": 1.5, "hely": 1.0, "bekerult": 0.8,
            "status": 0.8, "ev": 0.5, "oldalszam": 0.5, "meretek": 0.5,
            "kotes": 0.5, "forras": 0.5
        }
        
        osszes_alap = sum(self.OSZLOP_DEFINICIOK[k][1] for k in self.aktiv_oszlopok if k in self.OSZLOP_DEFINICIOK)
        
        if osszes_alap > 0 and szerel_szelesseg > osszes_alap:
            maradek_hely = szerel_szelesseg - osszes_alap
            osszes_suly = sum(SULYOK.get(k, 1.0) for k in self.aktiv_oszlopok if k in self.OSZLOP_DEFINICIOK)
            
            for i, kulcs in enumerate(self.aktiv_oszlopok):
                if kulcs in self.OSZLOP_DEFINICIOK:
                    alap = self.OSZLOP_DEFINICIOK[kulcs][1]
                    suly = SULYOK.get(kulcs, 1.0)
                    plusz_szelesseg = int(maradek_hely * (suly / osszes_suly))
                    self.SetColumnWidth(i, alap + plusz_szelesseg)
        else:
            for i, kulcs in enumerate(self.aktiv_oszlopok):
                if kulcs in self.OSZLOP_DEFINICIOK:
                    self.SetColumnWidth(i, self.OSZLOP_DEFINICIOK[kulcs][1])