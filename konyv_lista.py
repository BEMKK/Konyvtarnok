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
from utils import osszetett_rendezesi_kulcs
from oszlop_szelesseg import hasznalhato_szelesseg, szamol_celok, igazit


class KonyvListaCtrl(wx.ListCtrl):
    # Az átméretezési események összevonásához (lásd OnSize).
    _igazitas_fuggoben = False

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

    def _oszlop_kulcsok(self):
        return [k for k in self.aktiv_oszlopok if k in self.OSZLOP_DEFINICIOK]

    def _celszelessegek(self, kulcsok):
        alapok = [self.OSZLOP_DEFINICIOK[k][1] for k in kulcsok]
        sulyok = [self.SULYOK.get(k, 1.0) for k in kulcsok]
        return szamol_celok(alapok, sulyok, hasznalhato_szelesseg(self))

    def InitOszlopok(self):
        self.ClearAll()
        kulcsok = self._oszlop_kulcsok()
        # Az oszlopok eleve a (közelítőleg) végleges szélességgel jönnek
        # létre, így indításkor nem kell utólag SetColumnWidth-et hívni.
        for idx, (kulcs, szelesseg) in enumerate(
                zip(kulcsok, self._celszelessegek(kulcsok))):
            self.InsertColumn(idx, self.OSZLOP_DEFINICIOK[kulcs][0], width=szelesseg)

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

    def KijelolesMegszuntetese(self):
        """Minden kijelölés megszüntetése (Szerkesztés > Kijelölés > Egyik sem).

        Egyetlen hívással (-1 = minden elem) dolgozik, a virtuális listán sem
        kell soronként végigmenni. A fókuszt szándékosan meghagyja, így a
        billentyűzetes navigáció onnan folytatódik, ahol a felhasználó tartott.
        """
        if self.GetItemCount() == 0:
            return
        self.SetItemState(-1, 0, wx.LIST_STATE_SELECTED)

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

        # Az összetett rendezési kulcs (hiányos értékek a végén, másodlagos és
        # harmadlagos mező) a utils-ban él, hogy a Dezideráta-kezelő és a
        # KönyvTárnok-kereső is ugyanezt használja.
        def rendezesi_kulcs(konyv):
            return osszetett_rendezesi_kulcs(konyv, akt_rendezes)

        self.jelenlegi_adatok.sort(key=rendezesi_kulcs)

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
                ertek = konyv.get(kulcs)
                return "" if ertek is None else str(ertek)
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
            szoveg_lekero=lambda i: self.jelenlegi_adatok[i].get("cim") or "",
            kivalasztott_lekero=self.GetFirstSelected,
            kivalasztas_beallito=kijeloles_beallitasa,
        )

    def OnChar(self, event):
        self.gyors_kereses.kezel_char_esemeny(event, self.FeldolgozKarakter)

    def OnSize(self, event):
        event.Skip()
        # Az egy eseményciklusban érkező több átméretezési eseményt egyetlen
        # igazításra vonjuk össze.
        if not self._igazitas_fuggoben:
            self._igazitas_fuggoben = True
            wx.CallAfter(self._KesleltetettIgazitas)

    def _KesleltetettIgazitas(self):
        self._igazitas_fuggoben = False
        if self:  # a vezérlő közben megsemmisülhetett
            self.IgazitOszlopSzelesseg()

    def IgazitOszlopSzelesseg(self):
        # Üres virtuális listán a SetColumnWidth Windowson érvénytelen elemre
        # hivatkozik (GetSubItemRect assertion), ezért ilyenkor kihagyjuk; az
        # oszlopok addig megtartják az utolsó szélességüket.
        if self.GetItemCount() == 0:
            return
        # Csak azokat az oszlopokat állítjuk át, amelyek szélessége érdemben
        # eltér a kívántól (lásd oszlop_szelesseg.igazit).
        igazit(self, self._celszelessegek(self._oszlop_kulcsok()))
