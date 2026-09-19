# data_manager.py

import hashlib
import hmac
import json
import os
import sys
import logging
import uuid
import wx

# A program (exe vagy script) mappájához kötött abszolút alapútvonal,
# hogy az állományjegyzék fájl mindig ugyanoda kerüljön, függetlenül
# attól, hogy milyen munkakönyvtárból indították a programot.
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_ADATBAZIS_FAJL = os.path.join(_BASE_DIR, "allomanyjegyzek.json")

# ==============================================================================
# HMAC-SHA256 ALAPÚ ADATINTEGRITÁS-VÉDELEM
# ==============================================================================
# FONTOS: ez NEM titkosítás. A JSON tartalom sima, olvasható szöveg marad.
# A HMAC-aláírás kizárólag azt garantálja, hogy a fájl azóta nem sérült/nem
# módosult, hogy ezzel a programmal utoljára elmentettük. Mivel a kulcs az
# alkalmazásba van beépítve (nem gépspecifikusan generált, mint a régi
# Fernet-kulcs volt), az adatfájl más gépre átmásolva is ellenőrizhető marad.
#
# FIGYELEM: cseréld le az alábbi értéket egy saját, hosszú, véletlenszerű
# bájtsorozatra (pl. `python -c "import secrets;print(secrets.token_hex(32))"`),
# és utána ne változtasd meg, mert minden korábban mentett fájl aláírása
# érvénytelenné válna vele.
_HMAC_KEY = b"f5b21b90aa5387ee5a6e6bf939bbee8014d0a5133e62b61a5411401b7ca9d6e7"


def _kanonikus_json(adat_lista):
    """Determinisztikus JSON-reprezentáció, hogy az aláírás mindig ugyanaz
    legyen ugyanarra a tartalomra, kulcssorrendtől függetlenül."""
    return json.dumps(adat_lista, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _alairas(adat_lista):
    """HMAC-SHA256 aláírás (hex) számítása az adat_lista kanonikus alakja fölött."""
    uzenet = _kanonikus_json(adat_lista).encode("utf-8")
    return hmac.new(_HMAC_KEY, uzenet, hashlib.sha256).hexdigest()


def save_hmac_json(fajlnev, adat_lista):
    """
    Elmenti az adat_lista-t {"signature": ..., "data": [...]} boríték
    formátumban. Visszatérési érték: True, ha sikerült a mentés.
    """
    boritek = {
        "signature": _alairas(adat_lista),
        "data": adat_lista,
    }
    try:
        json_str = json.dumps(boritek, ensure_ascii=False, indent=4)
        with open(fajlnev, "w", encoding="utf-8") as f:
            f.write(json_str)
        return True
    except Exception as e:
        logging.error(f"Hiba a HMAC-adatfájl mentésekor ({fajlnev}): {e}", exc_info=True)
        return False


def load_hmac_json(fajlnev):
    """
    Beolvassa és ellenőrzi a HMAC-borítékos JSON fájlt (csak ezt a formátumot,
    migráció nélkül).

    Visszatérési érték: (adat_lista, ervenyes_e)
      - Ha a fájl nem létezik: ([], True).
      - ValueError-t dob, ha a fájl JSON, de nem HMAC-boríték formátumú
        (pl. régi verzió) - ezt a hívó fogja kezelni/migrálni.
    """
    if not os.path.exists(fajlnev):
        return [], True

    with open(fajlnev, "r", encoding="utf-8") as f:
        nyers = json.load(f)

    if not isinstance(nyers, dict) or "data" not in nyers or "signature" not in nyers:
        raise ValueError(f"Ismeretlen fájlformátum (nem HMAC-boríték): {fajlnev}")

    adat = nyers["data"]
    ervenyes = hmac.compare_digest(_alairas(adat), str(nyers.get("signature", "")))
    return adat, ervenyes


def _migracio_regi_fernet_bajtokbol(nyers_bajtok):
    """
    Megpróbálja visszafejteni a régi (1.0.0-s) Fernet-titkosítású állományt.

    Csak akkor sikerülhet, ha a 'cryptography' csomag telepítve van ÉS
    megvan a régi, gépspecifikus ~/.konyvtar_app/secret.key. Ez a modul
    EGYETLEN olyan pontja, ahol még szükség lehet a cryptography csomagra,
    és az import szándékosan lokális (lazy) + try/except-be csomagolt, hogy
    normál (nem migrációs) futás esetén a program enélkül is elinduljon.

    Visszatérési érték: a visszafejtett lista, vagy None, ha nem sikerült.
    """
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None

    key_file_path = os.path.join(os.path.expanduser("~"), ".konyvtar_app", "secret.key")
    if not os.path.exists(key_file_path):
        return None

    try:
        with open(key_file_path, "rb") as kf:
            regi_kulcs = kf.read()
        decrypted_bytes = Fernet(regi_kulcs).decrypt(nyers_bajtok)
        adat = json.loads(decrypted_bytes.decode("utf-8"))
        return adat if isinstance(adat, list) else None
    except Exception:
        return None


def load_hmac_json_with_migration(fajlnev):
    """
    Betölti a fájlt, és ha szükséges, automatikusan migrálja HMAC-boríték
    formátumra (régi Fernet-titkosított VAGY régi sima/titkosítatlan JSON
    esetén egyaránt), majd azonnal újra is menti az új formátumban.

    Visszatérési érték: (adat_lista, ervenyes_e, migralt_e)
      - Új formátumú, érvényes fájl esetén: ervenyes_e mindig True.
      - Sérült/módosított HMAC-boríték esetén: ervenyes_e=False, az adat
        mégis visszaadva (a hívó dönti el, bízik-e benne).
    """
    if not os.path.exists(fajlnev):
        return [], True, False

    with open(fajlnev, "rb") as f:
        nyers_bajtok = f.read()

    # 1. próba: már az új HMAC-boríték formátum?
    try:
        nyers_json = json.loads(nyers_bajtok.decode("utf-8"))
        if isinstance(nyers_json, dict) and "data" in nyers_json and "signature" in nyers_json:
            adat = nyers_json["data"]
            ervenyes = hmac.compare_digest(_alairas(adat), str(nyers_json.get("signature", "")))
            return adat, ervenyes, False
    except Exception:
        pass

    # 2. próba: régi Fernet-titkosítás
    migralt = _migracio_regi_fernet_bajtokbol(nyers_bajtok)

    # 3. próba: régi, titkosítatlan sima JSON lista
    if migralt is None:
        try:
            lehetseges = json.loads(nyers_bajtok.decode("utf-8"))
            migralt = lehetseges if isinstance(lehetseges, list) else None
        except Exception:
            migralt = None

    if migralt is None:
        raise ValueError(f"Ismeretlen vagy sérült fájlformátum, migráció sikertelen: {fajlnev}")

    # Azonnal átírjuk az új HMAC-boríték formátumba, hogy legközelebb már
    # ne kelljen migrálni.
    save_hmac_json(fajlnev, migralt)
    return migralt, True, True

# ==============================================================================
# KÖZÖS EGYEZÉS-/DUPLIKÁTUM-VIZSGÁLAT
# ==============================================================================
# Ezt a logikát korábban három helyen (KonyvAdatbazis.is_duplikalat,
# deziderata.is_same_book, konyvtarnok_kereso.py "Állományban" jelzése)
# külön-külön, egymástól kicsit eltérő formában valósítottuk meg. Innentől
# ez az egyetlen, közös implementáció, amit mindenhonnan importálva
# használunk, hogy a "mi számít ugyanannak a könyvnek" szabály mindenhol
# ugyanaz legyen.
DEFAULT_MEZO_ALIASOK = {
    "cim": ("cim",),
    "szerzo": ("szerzo",),
    "kiado": ("kiado",),
    "hely": ("hely",),
    "ev": ("ev",),
}


def _norm_ertek(ertek):
    return str(ertek or "").strip().lower()


def _elso_kitoltott_ertek(tetel, kulcsok):
    """Az első nem üres értéket adja vissza a megadott kulcsok/aliasok közül
    (pl. hogy a 'cim' és a 'title' mezőnevet egyaránt kezelni tudjuk)."""
    for kulcs in kulcsok:
        ertek = tetel.get(kulcs)
        if ertek:
            return ertek
    return ""


def tetelek_egyeznek(tetel1, tetel2, mezo_aliasok=None):
    """
    Két könyv/tétel (dict) egyezőségét vizsgálja.

    A Cím mindig kötelező és pontosan egyeznie kell. A többi mezőnél
    (alapesetben szerző, kiadó, hely, kiadás éve) csak akkor számít
    eltérésnek, ha MINDKÉT oldalon ki van töltve és a tartalmuk különbözik -
    egy üres mező tehát nem zárja ki az egyezést, ha a többi kitöltött mező
    megegyezik.

    A mezo_aliasok egy {logikai_mezonev: (lehetseges, kulcsnevek, ...)}
    szótár, hogy eltérő adatforrások (pl. angol 'title'/'author' mezőnevű
    dezideráta-import) mezőneveit is kezelni tudjuk anélkül, hogy a hívóknak
    külön kellene normalizálniuk az adatokat.
    """
    aliasok = mezo_aliasok or DEFAULT_MEZO_ALIASOK

    cim1 = _norm_ertek(_elso_kitoltott_ertek(tetel1, aliasok["cim"]))
    cim2 = _norm_ertek(_elso_kitoltott_ertek(tetel2, aliasok["cim"]))
    if not cim1 or not cim2 or cim1 != cim2:
        return False

    for mezo, kulcsok in aliasok.items():
        if mezo == "cim":
            continue
        ertek1 = _norm_ertek(_elso_kitoltott_ertek(tetel1, kulcsok))
        ertek2 = _norm_ertek(_elso_kitoltott_ertek(tetel2, kulcsok))
        if ertek1 and ertek2 and ertek1 != ertek2:
            return False

    return True


class KonyvAdatbazis:
    def __init__(self, fajlnev=None):
        self.fajlnev = fajlnev or DEFAULT_ADATBAZIS_FAJL
        self.konyvek = []
        self.AdatokBetoltese()

    def is_duplikalat(self, uj_adatok):
        """
        Duplikátum-vizsgálat: megegyezik-e uj_adatok az állományban már
        szereplő valamelyik könyvvel (lásd tetelek_egyeznek).
        """
        if not _norm_ertek(uj_adatok.get("cim", "")):
            return False
        return any(tetelek_egyeznek(uj_adatok, konyv) for konyv in self.konyvek)

    def AdatokBetoltese(self):
        try:
            adat, ervenyes, _migralt = load_hmac_json_with_migration(self.fajlnev)
        except Exception as e:
            logging.error(f"Hiba az állományjegyzék betöltésekor: {e}", exc_info=True)
            wx.MessageBox(
                f"Hiba az adatok betöltésekor: {e}",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            self.AlapertelmezettAdatok()
            return

        if not ervenyes:
            logging.error(
                f"Az állományjegyzék ({self.fajlnev}) HMAC-aláírása érvénytelen: "
                "a fájl megsérült vagy jogosulatlanul módosították."
            )
            wx.MessageBox(
                "Az állományjegyzék integritás-ellenőrzése sikertelen: a fájl "
                "megsérülhetett, vagy valaki módosította a programon kívül.\n\n"
                "Az adatok betöltése biztonsági okból megszakadt.",
                "Integritási hiba",
                wx.OK | wx.ICON_ERROR,
            )
            self.AlapertelmezettAdatok()
            return

        self.konyvek = adat if isinstance(adat, list) else []

        # Hiányzó ID-k pótlása
        modositva = False
        for konyv in self.konyvek:
            if isinstance(konyv, dict) and "id" not in konyv:
                konyv["id"] = str(uuid.uuid4())
                modositva = True
        if modositva:
            self.AdatokMentese()

    def AlapertelmezettAdatok(self):
        self.konyvek = []

    def AdatokMentese(self):
        return save_hmac_json(self.fajlnev, self.konyvek)

    # --- ID ALAPÚ MENTÉS ---
    def konyv_mentese_by_id(self, konyv_id, uj_adatok):
        for konyv in self.konyvek:
            if konyv.get("id") == konyv_id:
                konyv.update(uj_adatok)
                konyv["id"] = konyv_id  # ID megőrzése
                return self.AdatokMentese()
        return False

    def uj_konyv_hozzaadasa(self, uj_adatok, engedelyez_duplikaciót=False):
        if not engedelyez_duplikaciót and self.is_duplikalat(uj_adatok):
            return False
        
        # Generálunk egyedi azonosítót az új könyvnek
        if "id" not in uj_adatok or not uj_adatok["id"]:
            uj_adatok["id"] = str(uuid.uuid4())

        self.konyvek.append(uj_adatok)
        return self.AdatokMentese()

    # --- ID ALAPÚ TÖRLES ---
    def konyv_torlese_by_id(self, konyv_id):
        for i, konyv in enumerate(self.konyvek):
            if konyv.get("id") == konyv_id:
                del self.konyvek[i]
                return self.AdatokMentese()
        return False

    def save_to_json(self, target_filepath):
        try:
            with open(target_filepath, "w", encoding="utf-8") as f:
                json.dump(self.konyvek, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logging.error(f"Hiba az állományjegyzék mentésekor ({target_filepath}): {e}", exc_info=True)
            return False

