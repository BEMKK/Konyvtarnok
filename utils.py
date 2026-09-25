"""Közös, wxPython-tól (GUI-tól) teljesen független segédfüggvények.

Két, korábban külön helyen élő logikacsoportot fog össze:

1. Rendezési és dátumfeldolgozó segédfüggvények (HONAPOK, magyar_rendezesi_kulcs,
   bekerult_datum_kulcs, romai_szam_atlakito), amelyek korábban a konyv_lista.py
   (GUI lista-vezérlő) modulban éltek, jóllehet egyikük sem használ semmilyen
   wx-elemet. Emiatt olyan modulok is (pl. statisztika.py, deziderata.py),
   amelyeknek semmi közük a főablak könyvlistájához, feleslegesen importáltak
   a GUI modulból.

2. Az állománystatisztika tiszta számítási logikája (ertek_feldolgoz,
   evszazad_szoveg, evtized_szoveg, kereszttabla_rendezesi_kulcs,
   egyedi_kitoltetlen_statisztika, kereszttabla_statisztika), amelyek korábban
   a StatisztikaDialog (statisztika.py) metódusaiként léteztek. Egyikük sem
   használ wx-et vagy self-et a paraméterként átvett adatokon (könyvlista,
   mezőnevek) kívül, ezért önálló, automatizált teszttel is ellenőrizhető
   függvényekként élnek itt tovább; a StatisztikaDialog metódusai csak
   vékony hívó rétegként (self.db.konyvek átadásával) delegálnak ide.
"""
import re
import datetime
import logging
from collections import defaultdict

# ==============================================================================
# RENDEZÉSI ÉS DÁTUMFELDOLGOZÓ SEGÉDFÜGGVÉNYEK
# ==============================================================================

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
    except (ValueError, IndexError, AttributeError):
        pass
    except Exception as e:
        logging.debug(f"Dátum értelmezési hiba '{datum_str}': {e}")
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


# ==============================================================================
# ÁLLOMÁNYSTATISZTIKA - TISZTA SZÁMÍTÁSI LOGIKA (korábban StatisztikaDialog)
# ==============================================================================

def evszazad_szoveg(ev_str):
    """Egy évszám-tartalmú szövegből a hozzá tartozó (római számos) évszázad
    felirata, pl. '1987' -> 'XX. század'."""
    match = re.search(r'\b(\d{3,4})\b', str(ev_str or ""))
    if not match:
        return ""
    ev = int(match.group(1))

    szazad = (ev - 1) // 100 + 1

    romai_szamok = {
        15: "XV.", 16: "XVI.", 17: "XVII.", 18: "XVIII.",
        19: "XIX.", 20: "XX.", 21: "XXI."
    }
    return f"{romai_szamok.get(szazad, str(szazad) + '.')} század"


def evtized_szoveg(ev_str):
    """Egy évszám-tartalmú szövegből a hozzá tartozó évtized felirata,
    a helyes ('-as'/'-es') toldalékolással, pl. '1987' -> '1980-as évek'."""
    match = re.search(r'\b(\d{4})\b', str(ev_str or ""))
    if not match:
        return ""
    ev = int(match.group(1))
    evtized = (ev // 10) * 10

    # Helyes toldalékolás meghatározása
    if evtized % 100 == 0:
        if evtized % 1000 == 0:
            toldalek = "-es"  # 1000-es, 2000-es, 3000-es ("ezer" -> magas)
        else:
            toldalek = "-as"  # 1500-as, 1800-as, 1900-as ("száz" -> mély)
    else:
        tizes = (evtized // 10) % 10
        toldalek = "-es" if tizes in [1, 4, 5, 7, 9] else "-as"

    return f"{evtized}{toldalek} évek"


def ertek_feldolgoz(kulcs, ertek_str):
    """Egy nyers mezőérték statisztikai szempont szerinti feldolgozása
    (pl. évszázad/évtized virtuális mezőknél az 'ev' mezőből számolt felirat)."""
    val = str(ertek_str or "").strip()

    if kulcs == "bekerult" and val:
        match = re.search(r'\b(19\d\d|20\d\d)\b', val)
        if match:
            return match.group(1)

    if kulcs == "evszazad":
        return evszazad_szoveg(val)

    if kulcs == "evtized":
        return evtized_szoveg(val)

    return val


def statisztikai_szures(teljes_adatlista, kulcs, keresett_ertek):
    """Leszűri a könyvek listáját egy kiválasztott statisztikai mezőre és értékre.

    A szűrési feltételt (predikátum) egyetlen helyen, a belső predikatum()
    függvényben definiáljuk, és ugyanezt használjuk mind a leszűrt lista
    előállítására, mind a hívónak visszaadott predikátumra - korábban ez a
    feltétel egy ciklusban és egy külön predikatum() függvényben is,
    egymástól függetlenül, szó szerint meg volt ismételve.
    """
    is_hianyzo = keresett_ertek == "Nincs kitöltve"
    forras_kulcs = "ev" if kulcs in ["evszazad", "evtized"] else kulcs

    def predikatum(konyv):
        val = ertek_feldolgoz(kulcs, konyv.get(forras_kulcs, ""))
        if is_hianyzo:
            return not val
        return val.lower() == keresett_ertek.lower()

    leszurt_adatok = [konyv for konyv in teljes_adatlista if predikatum(konyv)]

    return leszurt_adatok, predikatum, is_hianyzo



def kereszttabla_rendezesi_kulcs(kulcs, ertek):
    """A kereszttáblás jelentés sor- és oszlopfejléceinek rendezési kulcsa.

    Alapból a Python sorted() egyszerű szöveges (lexikografikus) sorrendet
    adna, ami pl. a "9" és "150" oldalszámoknál, vagy eltérő számjegyű
    éveknél helytelen sorrendet eredményezne. Ehelyett a mező típusának
    megfelelően szám (év, oldalszám, bekerülés éve), méret vagy magyar
    ábécé szerint (a többi mezőnél, beleértve az évszázad/évtized
    feliratokat is, amikben a magyar_rendezesi_kulcs a római számokat is
    helyesen kezeli) rendezünk.
    """
    szoveg = str(ertek or "").strip()

    if kulcs in ("ev", "oldalszam", "bekerult"):
        szam_str = "".join(filter(str.isdigit, szoveg))
        return (0, int(szam_str)) if szam_str else (1, 0)

    if kulcs == "meretek":
        magassag_resz = szoveg.split('x')[0].split('X')[0].strip()
        match = re.search(r'\d+(?:[.,]\d+)?', magassag_resz)
        return (0, float(match.group(0).replace(',', '.'))) if match else (1, 0.0)

    return (0, magyar_rendezesi_kulcs(szoveg))


def egyedi_kitoltetlen_statisztika(konyvek, kulcs, megjelenitett_nev):
    """Kifejezetten az adott mező kitöltetlen sorait listázza ki egy
    könyvlistában."""
    osszes_szam = len(konyvek)
    if osszes_szam == 0:
        return "Az adatbázis üres."

    hianyos_konyvek = []
    forras_kulcs = "ev" if kulcs in ["evszazad", "evtized"] else kulcs
    for konyv in konyvek:
        val = ertek_feldolgoz(kulcs, konyv.get(forras_kulcs, ""))
        if not val:
            hianyos_konyvek.append(konyv)

    hiany_szam = len(hianyos_konyvek)
    szazalek = (hiany_szam / osszes_szam * 100) if osszes_szam > 0 else 0

    szoveg = "ADATMINŐSÉGI JELENTÉS – HIÁNYZÓ ADATOK\n"
    szoveg += "─" * 44 + "\n"
    szoveg += f"Mező neve: {megjelenitett_nev}\n"
    szoveg += f"Hiányzó adatok száma: {hiany_szam} db ({szazalek:.1f}%)\n"
    szoveg += f"Állomány összesen: {osszes_szam} db kötet\n\n"

    if hiany_szam > 0:
        szoveg += f"A kötetek listája, ahol a(z) '{megjelenitett_nev}' mező hiányzik:\n"
        for i, k in enumerate(hianyos_konyvek, 1):
            cim = k.get("cim", "Nincs cím")
            szerzo = k.get("szerzo", "")
            if szerzo:
                szoveg += f"  {i}. {szerzo}: {cim}\n"
            else:
                szoveg += f"  {i}. {cim}\n"
    else:
        szoveg += "Minden kötetnél ki van töltve ez a mező!"

    return szoveg


def kereszttabla_statisztika(konyvek, mezo_nevek, kulcs1, kulcs2, szures_kifejezes=""):
    """Kétdimenziós megoszlás listázása név-normalizálással és pontos szűréssel.

    mezo_nevek: {mezo_kulcs: megjelenitett_nev} szótár (pl. a StatisztikaDialog
    statisztikai_mezok listájából dict()-ként átadva), csak a jelentés
    fejlécének feliratozásához kell.
    """
    # Pontos szűrés előkészítése (ha konkrét értéket választottak ki)
    szuro_text = ""
    if szures_kifejezes and not szures_kifejezes.startswith("("):
        szuro_text = szures_kifejezes.lower().strip()

    matrix = defaultdict(lambda: defaultdict(int))
    megjelenített_nevek = {}
    megjelenített_nevek2 = {}

    # Virtuális mezők (évszázad, évtized) esetén az 'ev' mezőt kell lekérni a könyvből
    f_kulcs1 = "ev" if kulcs1 in ["evszazad", "evtized"] else kulcs1
    f_kulcs2 = "ev" if kulcs2 in ["evszazad", "evtized"] else kulcs2

    for konyv in konyvek:
        v1_raw = ertek_feldolgoz(kulcs1, konyv.get(f_kulcs1, "")) or "(Nincs megadva)"
        v2_raw = ertek_feldolgoz(kulcs2, konyv.get(f_kulcs2, "")) or "(Nincs megadva)"

        norm_v1 = v1_raw.lower().strip()
        # A másodlagos szempontot (v2) is normalizáljuk, ugyanúgy mint
        # az elsődlegeset (v1) - enélkül pl. "Budapest" és "budapest"
        # két külön sorként szerepelt volna a kereszttábla belső
        # bontásában, feleslegesen szétdarabolva az összesítést.
        norm_v2 = v2_raw.lower().strip()

        if norm_v1 not in megjelenített_nevek:
            megjelenített_nevek[norm_v1] = v1_raw
        if norm_v2 not in megjelenített_nevek2:
            megjelenített_nevek2[norm_v2] = v2_raw

        matrix[norm_v1][norm_v2] += 1

    szoveg = "ÁLLOMÁNYSTATISZTIKAI JELENTÉS – KERESZTTÁBLÁS ELEMZÉS\n"
    szoveg += "────────────────────────────────────────────\n"
    szoveg += f"Elsődleges szempont: {mezo_nevek.get(kulcs1, kulcs1)}\n"
    szoveg += f"Másodlagos szempont: {mezo_nevek.get(kulcs2, kulcs2)}\n"
    if szuro_text:
        szoveg += f"Keresett érték: '{szures_kifejezes}'\n"
    szoveg += "\n"

    talalat_van = False
    for norm_r1 in sorted(matrix.keys(), key=lambda v: kereszttabla_rendezesi_kulcs(kulcs1, v)):
        # Pontos egyezés vizsgálata a részszöveg-keresés helyett
        if szuro_text and norm_r1 != szuro_text:
            continue

        talalat_van = True
        r1_nev = megjelenített_nevek[norm_r1]
        osszesen_r1 = sum(matrix[norm_r1].values())

        szoveg += f"Találatok száma: {osszesen_r1}\n"
        for norm_r2, db in sorted(matrix[norm_r1].items(), key=lambda x: kereszttabla_rendezesi_kulcs(kulcs2, x[0])):
            r2_nev = megjelenített_nevek2.get(norm_r2, norm_r2)
            szoveg += f"    - {r2_nev}: {db}\n"
        szoveg += "\n"

    if not talalat_van:
        szoveg += "Nincs a keresési feltételnek megfelelő találat."

    return szoveg


# ==============================================================================
# VÁGÓLAP-KEZELŐ SEGÉDFÜGGVÉNYEK
# ==============================================================================

def masolas_win32_vagolapra(szoveg):
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


def masolas_vagolapra_szoveg(szoveg):
    """Szöveg másolása a vágólapra wx.TheClipboard segítségével, Win32 fallbackkel."""
    try:
        import wx
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(szoveg))
            wx.TheClipboard.Flush()
            wx.TheClipboard.Close()
            return True
    except Exception as e:
        logging.warning(f"wx.TheClipboard használata sikertelen: {e}")
    return masolas_win32_vagolapra(szoveg)

