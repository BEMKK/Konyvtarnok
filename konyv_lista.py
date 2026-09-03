import wx
import time
import re
import datetime

HONAPOK = {
    "január": 1, "február": 2, "március": 3, "április": 4,
    "május": 5, "június": 6, "július": 7, "augusztus": 8,
    "szeptember": 9, "október": 10, "november": 11, "december": 12
}

def bekerult_datum_kulcs(datum_str):
    try:
        reszek = str(datum_str).strip().split()
        if len(reszek) >= 3:
            ev = int(reszek[0])
            honap = HONAPOK.get(reszek[1].lower(), 1)
            nap = int(reszek[2])
            return datetime.date(ev, honap, nap)
    except Exception:
        pass
    return datetime.date(1900, 1, 1)

def romai_szam_atlakito(match):
    romai_terkep = {
        'I': 1, 'V': 5, 'X': 10, 'L': 50,
        'C': 100, 'D': 500, 'M': 1000
    }
    s = match.group(0).rstrip('.').upper()
    if not s:
        return match.group(0)

    ertek = 0
    prev = 0
    for c in reversed(s):
        curr = romai_terkep.get(c, 0)
        if curr < prev:
            ertek -= curr
        else:
            ertek += curr
            prev = curr
    return f"{ertek:04d}"

def magyar_rendezesi_kulcs(szoveg):
    HU_SORREND = " aábcdeéfghiíjklmnoóöőpqrstuúüűvwxyz0123456789"
    HU_TERKEP = {karakter: index for index, karakter in enumerate(HU_SORREND)}
    
    tisztitott = str(szoveg).lower().strip()
    tisztitott = re.sub(
        r'\b(?=[MDCLXVI]+\bM{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3}))[MDCLXVI]+\.?',
        romai_szam_atlakito,
        tisztitott,
        flags=re.IGNORECASE
    )
    return [HU_TERKEP.get(c, ord(c) + 1000) for c in tisztitott]


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

        self.beepitett_kereses_buffer = ""
        self.utolso_leutes_ideje = 0
        self.IDO_KUSZOB = 1.2

        if aktiv_oszlopok is None:
            self.aktiv_oszlopok = ["cim", "szerzo", "kiado", "hely", "ev", "forras", "status"]
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
        indexek = []
        idx = self.GetFirstSelected()
        while idx != -1:
            indexek.append(idx)
            idx = self.GetNextSelected(idx)
        return indexek

    def GetKonyvByRowIndex(self, index):
        if 0 <= index < len(self.jelenlegi_adatok):
            return self.jelenlegi_adatok[index]
        return None

    def GetKijeloltKonyvID(self, index):
        return self.sor_id_terkep.get(index)

    def Rendezes(self, mezo_kulcs):
        self.rendezes_kulcs = mezo_kulcs
        # A szűrt lista megtartásával rendezünk újra
        self.FeltoltLista(self.jelenlegi_adatok)

    def FeltoltLista(self, adatok=None):
        self.sor_id_terkep.clear()

        if not self.aktiv_oszlopok:
            self.SetItemCount(0)
            return

        if adatok is not None:
            self.jelenlegi_adatok = list(adatok)
        else:
            self.jelenlegi_adatok = list(self.db.konyvek)

        akt_rendezes = self.rendezes_kulcs if self.rendezes_kulcs else "cim"

        def szam_kulcs(ertek):
            szam_str = "".join(filter(str.isdigit, str(ertek)))
            return int(szam_str) if szam_str else 0

        def meret_kulcs(ertek):
            # Csak az 'x' vagy 'X' előtti részt vágja le (magasság)
            magassag_resz = str(ertek).split('x')[0].split('X')[0].strip()
            # Megkeresi az első számot (tizedesvesszővel vagy ponttal)
            match = re.search(r'\d+(?:[.,]\d+)?', magassag_resz)
            if match:
                # Tört számmá alakítja (pl. "12,5" -> 12.5), így a 12.5 pontosan a 12 után kerül
                return float(match.group(0).replace(',', '.'))
            return 0.0

        def osszetett_rendezesi_kulcs(konyv):
            raw_val = konyv.get(akt_rendezes, "")
            
            # Ellenőrizzük, hogy a mező üres-e (None, üres sztring vagy csak szóközök)
            is_empty = raw_val is None or str(raw_val).strip() == ""
            hianyos = 1 if is_empty else 0

            # 1. Elsődleges rendezési érték kiszámítása
            if akt_rendezes in ("oldalszam", "ev"):
                elso = szam_kulcs(raw_val)
            elif akt_rendezes in ("meret", "meretek"):
                ertek = konyv.get("meretek", konyv.get("meret", ""))
                elso = meret_kulcs(ertek)
            elif akt_rendezes == "bekerult":
                elso = bekerult_datum_kulcs(raw_val)
            else:
                elso = magyar_rendezesi_kulcs(raw_val)
            
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

        self.jelenlegi_adatok.sort(key=osszetett_rendezesi_kulcs)        # ... (a függvény többi része változatlan)

        for idx, konyv in enumerate(self.jelenlegi_adatok):
            self.sor_id_terkep[idx] = konyv.get("id")

        try:
            item_count = self.GetItemCount()
            for i in range(item_count):
                self.Select(i, False)
            if item_count > 0:
                self.Focus(0)
        except Exception:
            pass

        count = len(self.jelenlegi_adatok)
        self.SetItemCount(count)
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
        if not karakter:
            return

        aktualis_ido = time.time()
        elozo_buffer = self.beepitett_kereses_buffer

        if aktualis_ido - self.utolso_leutes_ideje > self.IDO_KUSZOB:
            self.beepitett_kereses_buffer = ""
            elozo_buffer = ""

        is_single_char_repeat = (
            len(elozo_buffer) == 1 and
            karakter == elozo_buffer
        )

        if karakter == ' ':
            if not self.beepitett_kereses_buffer:
                return
            self.beepitett_kereses_buffer += ' '
        elif karakter.strip():
            if not is_single_char_repeat:
                self.beepitett_kereses_buffer += karakter
        else:
            return

        self.utolso_leutes_ideje = aktualis_ido

        cel_mezo = "cim"
        keresett = self.beepitett_kereses_buffer
        total = len(self.jelenlegi_adatok)
        if total == 0:
            return

        current_idx = self.GetFirstSelected()
        if is_single_char_repeat and current_idx != -1:
            start_idx = (current_idx + 1) % total
        else:
            start_idx = 0

        def keres_elo_tag(keresendo, tol, korokre=False):
            for i in range(tol, total):
                ertek = str(self.jelenlegi_adatok[i].get(cel_mezo, "")).lower().strip()
                if ertek.startswith(keresendo):
                    return i
            if korokre:
                for i in range(0, tol):
                    ertek = str(self.jelenlegi_adatok[i].get(cel_mezo, "")).lower().strip()
                    if ertek.startswith(keresendo):
                        return i
            return -1

        talalt = keres_elo_tag(keresett.lower(), start_idx, korokre=is_single_char_repeat)

        if talalt == -1 and not is_single_char_repeat:
            talalt = keres_elo_tag(keresett.lower(), 0)

        if talalt == -1 and len(keresett) > 0:
            elso_kar = keresett[0].lower()
            ekezet_parok = {
                'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ö': 'o', 'ő': 'o',
                'ú': 'u', 'ü': 'u', 'ű': 'u',
                'a': 'á', 'e': 'é', 'i': 'í', 'o': ['ó', 'ö', 'ő'], 'u': ['ú', 'ü', 'ű']
            }
            alternativ_karakterek = []
            if elso_kar in ekezet_parok:
                par = ekezet_parok[elso_kar]
                if isinstance(par, list):
                    alternativ_karakterek.extend(par)
                else:
                    alternativ_karakterek.append(par)

            for alt_kar in alternativ_karakterek:
                modositott = alt_kar + keresett[1:]
                talalt = keres_elo_tag(modositott.lower(), start_idx, korokre=is_single_char_repeat)
                if talalt == -1 and not is_single_char_repeat:
                    talalt = keres_elo_tag(modositott.lower(), 0)
                if talalt != -1:
                    break

        if talalt != -1:
            for sel_idx in self.GetKijeloltIndexek():
                self.Select(sel_idx, False)
            self.Select(talalt, True)
            self.Focus(talalt)
            self.EnsureVisible(talalt)

    def OnChar(self, event):
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
            self.FeldolgozKarakter(karakter)
        else:
            event.Skip()

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