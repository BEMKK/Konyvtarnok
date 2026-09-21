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
# FIGYELEM: az alábbi értéket ne változtasd meg, mert minden korábban mentett fájl aláírása érvénytelenné válik!
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

# ==============================================================================
# KÖZÖS "ADDITÍV JSON IMPORT" SEGÉDFÜGGVÉNY
# ==============================================================================
# Ezt a mintát (JSON fájl beolvasása, lista-e ellenőrzés, majd tételenkénti,
# duplikátum-szűrt hozzáadás egy már meglévő listához/adatbázishoz) korábban
# a főablak ("Állományjegyzék betöltése JSON fájlból") és a Dezideráta-kezelő
# ("Dezideráta betöltése") egymástól függetlenül, majdnem szó szerint
# megegyező formában valósította meg.
def additiv_lista_import(fajlnev, hozzaad_fv):
    """Beolvas egy JSON fájlt (listát vár), és a benne szereplő minden dict
    elemet átad a hozzaad_fv(elem) -> bool függvénynek, amely eldönti és
    végre is hajtja a tényleges hozzáadást (pl. duplikátum-ellenőrzéssel),
    majd True-val tér vissza, ha ténylegesen hozzáadta az elemet, egyébként
    False-szal (pl. mert már szerepelt duplikátumként).

    A nem dict típusú listaelemeket szó nélkül kihagyja.

    Visszatérési érték: (hozzaadva, kihagyva) számpár.

    ValueError-t dob, ha a fájl tartalma nem lista, hogy a hívó egységes
    hibaüzenetet tudjon megjeleníteni. Minden egyéb hibát (fájl-I/O, JSON
    dekódolási hiba) a hívóra bíz.
    """
    with open(fajlnev, "r", encoding="utf-8") as f:
        importalt_adatok = json.load(f)

    if not isinstance(importalt_adatok, list):
        raise ValueError("A kiválasztott JSON fájl formátuma nem megfelelő!")

    hozzaadva = 0
    kihagyva = 0
    for elem in importalt_adatok:
        if not isinstance(elem, dict):
            continue
        if hozzaad_fv(elem):
            hozzaadva += 1
        else:
            kihagyva += 1

    return hozzaadva, kihagyva

# ==============================================================================
# KÖZÖS "TÖMEGES FELVÉTEL AZ ÁLLOMÁNYBA" SEGÉDFÜGGVÉNY
# ==============================================================================
# Ezt a ciklust (kijelölt sorokból/tételekből épített könyvadat-dict-ek
# egymás utáni felvétele az adatbázisba, a sikeres/elutasított darabszám és
# az újonnan felvett könyvobjektumok gyűjtése, majd a nézet frissítése)
# korábban a Dezideráta-kezelő ("Felvétel az állományba") és a KönyvTárnok-
# kereső ("Felvétel az állományba") egymástól függetlenül, szinte szó
# szerint megegyező formában valósította meg.
def konyvek_tomeges_felvetele(db, konyv_adatok_listaja, utani_frissites_fv=None):
    """Több könyvadat-dict egymás utáni felvétele az adatbázisba.

    A duplikátum-szűrést a db.uj_konyv_hozzaadasa végzi. A cím nélküli
    (üres "cim" mezőjű) tételeket kihagyja. A sikeresen felvett tételek
    esetén a hívó által (opcionálisan) átadott utani_frissites_fv-et hívja
    meg az újonnan felvett könyvobjektumok listájával, hogy a hívó a saját
    (pl. főablak) nézetét ennek megfelelően frissíthesse - ugyanúgy, mint
    a kézi felvitel vagy a JSON import után.

    Visszatérési érték: (sikeres_db, elutasitott_db, sikeres_indexek,
    uj_konyv_objektumok), ahol a sikeres_indexek a konyv_adatok_listaja-beli
    indexei azoknak az elemeknek, amelyeket ténylegesen felvettünk - ez
    teszi lehetővé, hogy a hívó a saját listájában/táblázatában meg tudja
    jelölni, mely sorok kerültek át az állományba.
    """
    sikeres = 0
    elutasitott = 0
    sikeres_indexek = []
    uj_konyv_objektumok = []

    for idx, konyv_adat in enumerate(konyv_adatok_listaja):
        if not str(konyv_adat.get("cim", "")).strip():
            continue
        if db.uj_konyv_hozzaadasa(konyv_adat):
            sikeres += 1
            sikeres_indexek.append(idx)
            uj_konyv_objektumok.append(db.konyvek[-1])
        else:
            elutasitott += 1

    if utani_frissites_fv is not None:
        utani_frissites_fv(uj_konyv_objektumok)

    return sikeres, elutasitott, sikeres_indexek, uj_konyv_objektumok


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
            adat, ervenyes = load_hmac_json(self.fajlnev)
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


# ==============================================================================
# KÖZÖS "TÖMEGES ÁTEMELÉS" UI-SEGÉDFÜGGVÉNYEK
# ==============================================================================
# A tényleges felvételi ciklust már a konyvek_tomeges_felvetele közös
# segédfüggvény végzi, de a köré épülő megerősítő kérdést és az eredményt
# összegző üzenetablakot korábban a Dezideráta-kezelő ("Felvétel az
# állományba") és a KönyvTárnok-kereső (mindkét átemelési iránya: állományba
# és dezideráta-jegyzékbe) egymástól függetlenül, szinte szó szerint
# megegyező formában tartalmazta. Innentől mindhárom hely ezt a két közös
# függvényt használja.
def kerj_tomeges_atemeles_megerositest(parent, darab, tetel_nev, cel_nev):
    """Megerősítő kérdést jelenít meg egy tömeges átemelés (állományba vagy
    dezideráta-jegyzékbe emelés) előtt.

    tetel_nev: az átemelendő elem(ek) megnevezése ragozott alakban, pl.
    "tételt" (Dezideráta-kezelő) vagy "találatot" (KönyvTárnok-kereső).
    cel_nev: az átemelés célja ragozott alakban, pl. "az állományba" vagy
    "a deziderátába".

    Visszaadja True-t, ha a felhasználó igennel válaszolt.
    """
    uzenet = (
        f"Biztosan át szeretnéd emelni a kijelölt {darab} db {tetel_nev} {cel_nev}?"
        if darab > 1
        else f"Biztosan át szeretnéd emelni a kijelölt {tetel_nev} {cel_nev}?"
    )
    valasz = wx.MessageBox(uzenet, "Átemelés megerősítése", wx.YES_NO | wx.ICON_QUESTION, parent)
    return valasz == wx.YES


def mutass_tomeges_atemeles_eredmenyt(parent, sikeres, visszautasitott, hozzaadva_hova, mar_szerepel_hol):
    """Az átemelés eredményét (siker / részben duplikátum miatti elutasítás /
    teljes elutasítás) összegző üzenetablakot jelenít meg.

    hozzaadva_hova: pl. "az állományhoz" vagy "a dezideráta-jegyzékbe".
    mar_szerepel_hol: pl. "az állományban" vagy "a dezideráta-jegyzékben".
    """
    if sikeres > 0:
        uzenet = "Az átemelés sikeresen megtörtént!\n\n"
        uzenet += f"• Hozzáadva {hozzaadva_hova}: {sikeres} db könyv.\n"
        if visszautasitott > 0:
            uzenet += "\nMegjegyzés:\n"
            uzenet += f"• {visszautasitott} db könyv már szerepel {mar_szerepel_hol} (duplikátum), így nem került újra felvételre."
        wx.MessageBox(uzenet, "Átemelés sikeres", wx.OK | wx.ICON_INFORMATION, parent)
    elif visszautasitott > 0:
        wx.MessageBox(
            f"Az átemelés nem történt meg!\n\nA kiválasztott könyv(ek) ({visszautasitott} db) már szerepel(nek) {mar_szerepel_hol}.",
            "Átemelés sikertelen",
            wx.OK | wx.ICON_WARNING,
            parent,
        )
    else:
        wx.MessageBox(
            "Nem sikerült átemelni a kiválasztott elemeket.",
            "Átemelés sikertelen",
            wx.OK | wx.ICON_ERROR,
            parent,
        )

