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
import os
import sys
import datetime
import logging
import unicodedata
import platform
import subprocess
from collections import defaultdict

# ==============================================================================
# ALKALMAZÁS-ALAPMAPPA MEGHATÁROZÁSA
# ==============================================================================


def alkalmazas_alapmappa():
    """A program (exe vagy script) mappájához kötött abszolút alapútvonal,
    hogy a program adatfájljai (settings.json, allomanyjegyzek.json,
    deziderata.json, hibanaplo.log stb.) mindig ugyanoda kerüljenek,
    függetlenül attól, hogy milyen munkakönyvtárból indították a
    programot, illetve hogy lefagyasztott (PyInstaller) .exe-ként vagy
    sima Python szkriptként fut-e.

    Mivel az alkalmazás összes modulja egyetlen, közös mappában él, ez a
    segédfüggvény - bár maga az utils.py-ban van definiálva - ugyanazt az
    útvonalat adja vissza, mint amit a hívó modul a saját __file__-ja
    alapján számolna ki.

    Korábban ezt a néhány soros mintát (getattr(sys, 'frozen', False)
    ellenőrzés, majd sys.executable vagy a modul __file__-ja alapján
    számolt könyvtár) a config_manager.py, a data_manager.py, a
    deziderata.py és a main.py egymástól függetlenül, szó szerint
    megegyező formában tartalmazta.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ==============================================================================
# RENDEZÉSI ÉS DÁTUMFELDOLGOZÓ SEGÉDFÜGGVÉNYEK
# ==============================================================================

HONAPOK = {
    "január": 1, "február": 2, "március": 3, "április": 4,
    "május": 5, "június": 6, "július": 7, "augusztus": 8,
    "szeptember": 9, "október": 10, "november": 11, "december": 12
}


def _ekezet_nelkul(szoveg):
    """Kisbetűs, ékezet nélküli alak (pl. 'Július' -> 'julius')."""
    lebontott = unicodedata.normalize("NFD", szoveg.lower())
    return "".join(c for c in lebontott if not unicodedata.combining(c))


# A hónapnevek ékezet nélküli alakja is felismerhető legyen (pl. 'Julius').
_HONAPOK_EKEZET_NELKUL = {_ekezet_nelkul(nev): szam for nev, szam in HONAPOK.items()}

# 2024-07-28 / 2024.07.28. / 2024/07/28 (a nap elhagyható)
_DATUM_SZAMOS = re.compile(
    r"(\d{4})\s*[-./]\s*(\d{1,2})(?:\s*[-./]\s*(\d{1,2}))?\s*\.?")
# 2024 Július 28 / 2024. július 28. (a nap elhagyható)
_DATUM_SZOVEGES = re.compile(
    r"(\d{4})\.?\s+([^\W\d_]+)\.?(?:\s+(\d{1,2}))?\s*\.?")
# 2024 / 2024.
_DATUM_CSAK_EV = re.compile(r"(\d{4})\.?")


def bekerult_datum_kulcs(datum_str):
    """A bekerülés dátumának rendezési kulcsa (datetime.date).

    Elfogadott alakok: 'ÉÉÉÉ Hónap NN' (a program saját formátuma, pl.
    '2026 Július 28'), 'ÉÉÉÉ. hónap NN.', 'ÉÉÉÉ-HH-NN', 'ÉÉÉÉ.HH.NN.',
    'ÉÉÉÉ/HH/NN'. Ha a nap hiányzik, az 1. napot vesszük ('2026 Július'),
    ha csak az év van meg, január 1-jét. Ami nem értelmezhető (üres mező,
    ismeretlen hónapnév, érvénytelen nap), az 1900-01-01 marad, vagyis a
    rendezésben a nem datált tételek együtt, a lista szélén jelennek meg."""
    ervenytelen = datetime.date(1900, 1, 1)
    szoveg = str(datum_str if datum_str is not None else "").strip()
    if not szoveg:
        return ervenytelen
    try:
        m = _DATUM_SZAMOS.fullmatch(szoveg)
        if m:
            ev, honap, nap = m.group(1), m.group(2), m.group(3)
            return datetime.date(int(ev), int(honap), int(nap) if nap else 1)

        m = _DATUM_SZOVEGES.fullmatch(szoveg)
        if m:
            honap = _HONAPOK_EKEZET_NELKUL.get(_ekezet_nelkul(m.group(2)))
            if honap is None:
                return ervenytelen
            nap = m.group(3)
            return datetime.date(int(m.group(1)), honap, int(nap) if nap else 1)

        m = _DATUM_CSAK_EV.fullmatch(szoveg)
        if m:
            return datetime.date(int(m.group(1)), 1, 1)
    except ValueError:
        pass
    except Exception as e:
        logging.debug(f"Dátum értelmezési hiba '{datum_str}': {e}")
    return ervenytelen


def _egesz_romaira(n):
    """Egy egész szám (1..3999) szabályos római szám alakja, pl. 19 -> 'XIX'."""
    jegyek = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
              (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
              (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
    eredmeny = ""
    for ertek, jel in jegyek:
        while n >= ertek:
            eredmeny += jel
            n -= ertek
    return eredmeny


# A rendezéskor római számnak tekintett szavak szótára (pl. 'XIX' -> 19).
# Csak ez a kis, valóban előforduló tartomány számít római számnak (századok,
# uralkodói sorszámok, kötetszámok), ezért az 'M', 'D', 'C', 'L' betűket
# tartalmazó közönséges szavak ('Mi', 'Di', 'Civil'), valamint a
# szerzői monogramok ('M.', 'C.', 'D.', 'L.') nem kerülnek összetévesztésre.
# Ha ennél nagyobb sorszámokra is szükség van, csak ROMAI_MAX-ot kell emelni.
ROMAI_MAX = 49
ROMAI_SZAMOK = {_egesz_romaira(n): n for n in range(1, ROMAI_MAX + 1)}

# Csak NAGYBETŰS, szó határolta betűcsoport lehet római szám (az utána álló
# pont elhagyható). A kisbetűs 'Mi', 'Xi', 'Li' stb. így sosem jelölt.
ROMAI_MINTA = re.compile(r'\b[IVXLCDM]+\b\.?')


def romai_szam_atlakito(match):
    """re.sub-hoz: a találatot négyjegyű, nullával kitöltött számra cseréli,
    ha az szerepel a ROMAI_SZAMOK szótárban; különben változatlanul hagyja."""
    szoveg = match.group(0)
    s = szoveg.rstrip('.')
    ertek = ROMAI_SZAMOK.get(s)
    if ertek is None:
        return szoveg
    # Az önálló 'I' pont nélkül többnyire angol névmás ('I Am Legend'),
    # nem római szám; csak 'I.' alakban tekintjük annak.
    if s == "I" and not szoveg.endswith('.'):
        return szoveg
    return f"{ertek:04d}"


def szamjegysor_atlakito(match):
    """re.sub-hoz: egy számjegysorozatot hosszelőtaggal látja el, hogy a
    karakterenkénti összehasonlítás a számértéket kövesse.
    Pl. '9' -> '019', '10' -> '0210', '150' -> '03150'."""
    szamjegyek = match.group(0).lstrip('0') or '0'
    return f"{min(len(szamjegyek), 99):02d}{szamjegyek}"


HU_SORREND = " 0123456789aábcdeéfghiíjklmnoóöőpqrstuúüűvwxyz"
HU_TERKEP = {karakter: index for index, karakter in enumerate(HU_SORREND)}


def magyar_rendezesi_kulcs(szoveg):
    # 1. A római számok cseréje még az EREDETI (nagybetűs) szövegen történik,
    #    mert a kisbetűsítés után már nem lehetne megkülönböztetni a 'XX.'-et
    #    a 'xx'-től, illetve a 'Mi'-t az 'MI'-től.
    tisztitott = ROMAI_MINTA.sub(romai_szam_atlakito, str(szoveg).strip())
    tisztitott = tisztitott.lower()
    # 2. Az arab (és a fent átváltott római) számok számérték szerint rendeződnek.
    tisztitott = re.sub(r'[0-9]+', szamjegysor_atlakito, tisztitott)
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



def szam_mezo_kulcs(ertek):
    """Egy nyers mezőérték (pl. 'oldalszam' vagy 'ev') rendezési kulcsa:
    az érték ELSŐ számjegysorozatát adja vissza egész számként, vagy 0-t, ha
    nincs benne számjegy. (Korábban az összes számjegyet összefűzte, így pl.
    az '1987-1990' 19871990, az '1987 (2. kiad.)' 19872 lett.)"""
    match = re.search(r"\d+", str(ertek))
    return int(match.group(0)) if match else 0


def meret_mezo_kulcs(ertek):
    """A 'meretek' mező (pl. '21x14,5 cm') rendezési kulcsa: csak az 'x'
    vagy 'X' előtti (magassági) részt veszi figyelembe, abban keresi az
    első (tizedesvesszős/pontos) számot."""
    magassag_resz = str(ertek).split('x')[0].split('X')[0].strip()
    match = re.search(r'\d+(?:[.,]\d+)?', magassag_resz)
    if match:
        return float(match.group(0).replace(',', '.'))
    return 0.0


def konyv_mezo_rendezesi_kulcs(mezo_kulcs, nyers_ertek):
    """Egy könyv-rekord egyetlen mezőjének (nyers, karakterlánc) értékéből
    képzett rendezési kulcs, a mező típusának megfelelően: szám (oldalszám,
    kiadás éve), méret, dátum (bekerülés) vagy magyar ábécé szerint.

    Ezt a logikát korábban a konyv_lista.py (KonyvListaCtrl.FeltoltLista)
    és a statisztika.py (StatisztikaDialog.on_szamol belső riport_rendezes
    függvénye) egymástól függetlenül, szó szerint megegyező formában
    tartalmazta.
    """
    if mezo_kulcs in ("oldalszam", "ev"):
        return szam_mezo_kulcs(nyers_ertek)

    if mezo_kulcs == "meretek":
        return meret_mezo_kulcs(nyers_ertek)

    if mezo_kulcs == "bekerult":
        return bekerult_datum_kulcs(nyers_ertek)

    return magyar_rendezesi_kulcs(nyers_ertek)


def kereszttabla_rendezesi_kulcs(kulcs, ertek):
    """A kereszttáblás jelentés sor- és oszlopfejléceinek rendezési kulcsa.

    Alapból a Python sorted() egyszerű szöveges (lexikografikus) sorrendet
    adna, ami pl. a "9" és "150" oldalszámoknál, vagy eltérő számjegyű
    éveknél helytelen sorrendet eredményezne. Ehelyett a mező típusának
    megfelelően szám (év, oldalszám, bekerülés éve), méret vagy magyar
    ábécé szerint (a többi mezőnél, beleértve az évszázad/évtized
    feliratokat is, amikben a magyar_rendezesi_kulcs a római számokat is
    helyesen kezeli) rendezünk.

    Itt a "bekerult" már a statisztikához előfeldolgozott (csak évet
    tartalmazó) csoportcímke, nem a nyers dátum - ezért ugyanazt a
    számkinyerést (szam_mezo_kulcs) használjuk rá, mint az ev/oldalszam
    mezőknél, nem a konyv_mezo_rendezesi_kulcs dátumfeldolgozó ágát.
    A tényleges szám-/méret-kinyerést a szam_mezo_kulcs / meret_mezo_kulcs
    közös segédfüggvények végzik, hogy ez a logika ne legyen duplikálva.
    """
    szoveg = str(ertek or "").strip()

    if kulcs in ("ev", "oldalszam", "bekerult"):
        szam_str = "".join(filter(str.isdigit, szoveg))
        return (0, szam_mezo_kulcs(szoveg)) if szam_str else (1, 0)

    if kulcs == "meretek":
        magassag_resz = szoveg.split('x')[0].split('X')[0].strip()
        match = re.search(r'\d+(?:[.,]\d+)?', magassag_resz)
        return (0, meret_mezo_kulcs(szoveg)) if match else (1, 0.0)

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
    for norm_r1 in sorted(matrix.keys(), key=lambda v: kereszttabla_rendezesi_kulcs(kulcs1, megjelenített_nevek[v])):
        # Pontos egyezés vizsgálata a részszöveg-keresés helyett
        if szuro_text and norm_r1 != szuro_text:
            continue

        talalat_van = True
        r1_nev = megjelenített_nevek[norm_r1]
        osszesen_r1 = sum(matrix[norm_r1].values())

        # Az elsődleges szempont aktuális értékét (r1_nev) is ki kell írni,
        # különben - főleg szűrés nélküli, teljes kereszttábla esetén, ahol
        # egymás után több csoport blokkja is megjelenik - semmi nem
        # jelezné, melyik "Találatok száma" melyik csoportra vonatkozik.
        szoveg += f"{r1_nev}\n"
        szoveg += f"Találatok száma: {osszesen_r1}\n"
        for norm_r2, db in sorted(matrix[norm_r1].items(), key=lambda x: kereszttabla_rendezesi_kulcs(kulcs2, megjelenített_nevek2.get(x[0], x[0]))):
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

        # 64 bites pointerek és típusok explicit beállítása
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]

        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

        GMEM_MOVEABLE = 0x0002
        CF_UNICODETEXT = 13

        if user32.OpenClipboard(None):
            try:
                user32.EmptyClipboard()
                encoded = szoveg.encode('utf-16le') + b'\x00\x00'
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
                if not h_mem:
                    return False
                p_mem = kernel32.GlobalLock(h_mem)
                if not p_mem:
                    kernel32.GlobalFree(h_mem)
                    return False
                try:
                    ctypes.memmove(p_mem, encoded, len(encoded))
                finally:
                    kernel32.GlobalUnlock(h_mem)
                if not user32.SetClipboardData(CF_UNICODETEXT, h_mem):
                    kernel32.GlobalFree(h_mem)
                    return False
                return True
            finally:
                user32.CloseClipboard()
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

def fajl_megnyitasa(utvonal):
    """Megnyitja a fájlt a rendszer alapértelmezett alkalmazásával.

    Windowson os.startfile, macOS-en `open`, egyébként `xdg-open`. Siker
    esetén nem ad vissza semmit; ha nem sikerült, kivételt dob (OSError /
    subprocess.CalledProcessError), amit a hívó jeleníthet meg.
    """
    utvonal = str(utvonal)
    rendszer = platform.system()
    if rendszer == "Windows":
        os.startfile(utvonal)
    elif rendszer == "Darwin":
        subprocess.run(["open", utvonal], check=True)
    else:
        subprocess.run(["xdg-open", utvonal], check=True)
