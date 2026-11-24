import re
import hashlib
import hmac
import json
import os
import logging
import uuid
import functools
from contextlib import nullcontext, contextmanager
import wx

# Az alkalmazás alapmappájának (exe melletti, ill. szkript-mappa)
# meghatározása az utils.py-ba került, mert ezt korábban a
# config_manager.py, a data_manager.py, a deziderata.py és a main.py
# egymástól függetlenül, szó szerint megegyező formában tartalmazta.
from utils import alkalmazas_alapmappa
from constants import (
    BIBLIOGRAFIAI_KULCSOK, KERESO_MEZO_ALIASOK, MEZOK,
    DEZIDERATA_STATUS_NEM_KAPHATO, DEZIDERATA_BESZERZES_MEZOKULCSOK,
)
from undo_manager import UndoRegiszter, UndoKezelo, ListaTarolo, utkozes_uzenet

_BASE_DIR = alkalmazas_alapmappa()

DEFAULT_ADATBAZIS_FAJL = os.path.join(_BASE_DIR, "allomanyjegyzek.json")


class MentesiHiba(Exception):
    """Azt jelzi, hogy egy könyv/tétel állományba vétele, módosítása vagy
    törlése a memóriában megtörtént, de a lemezre írás (AdatokMentese)
    sikertelen volt.

    Ezt szándékosan külön kivételként dobjuk, nem pedig a megszokott
    False visszatérési értékkel jelezzük, mert a hívók (pl.
    KonyvSzerkesztoDialog.on_mentes) a False-t eddig "már szerepel
    duplikátumként" / "nem található a könyv" jelentéssel bírónak
    tekintették. Egy lemezre írási hiba (pl. tele lemez, jogosultsági
    hiba) esetén viszont ez a két üzenet félrevezető lenne: a könyv
    valójában megtalálható/hozzáadható volt, csak a mentés hiúsult meg.
    A KonyvAdatbazis metódusai emiatt a mentés sikertelensége esetén
    visszavonják a memóriabeli módosítást is, hogy a memória és a lemezen
    lévő állapot ne csússzon szét, majd ezt a kivételt dobják.
    """
    pass


class SzerkesztesTiltvaHiba(MentesiHiba):
    """Az állományjegyzék betöltése nem sikerült (olvasási hiba, ismeretlen
    formátum vagy érvénytelen HMAC-aláírás), ezért a módosítás le van tiltva,
    hogy a program ne írja felül a meglévő (esetleg megmenthető) fájlt.

    A MentesiHiba leszármazottja, így azok a hívók is elkapják és megjelenítik,
    amelyek még nem ellenőrzik előre a db.mentes_tiltva jelzőt (védőháló);
    a felület a módosító műveletek elején az allomany_szerkesztheto()
    függvénnyel előre, barátságos üzenettel is megállítja a műveletet.
    """
    pass

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

    # A ciklust try/finally-be csomagoljuk: ha egy tétel felvétele közben
    # MentesiHiba (lemezre írási hiba) történik, a hívónak ezt a kivételt
    # kell látnia (nem szabad "elutasítottként", duplikátumként
    # elkönyvelni - lásd data_manager.MentesiHiba), de a nézetet a hívó
    # frissítő függvényén keresztül még ekkor is frissítjük a addig
    # ténylegesen sikeresen felvett tételekkel, hogy a felhasználó lássa,
    # meddig jutott a művelet.
    # Az egész tömeges felvétel EGY visszavonható lépés (a db.undo-ban). Ha a
    # hívó már nagyobb csoportot nyitott (pl. a Dezideráta átemelése, ami a
    # dezideráta oldalát is magában foglalja), ez abba beleolvad.
    undo = getattr(db, "undo", None)
    csoport = undo.muvelet("könyvek felvétele") if undo is not None else nullcontext()
    try:
        with csoport:
            for idx, konyv_adat in enumerate(konyv_adatok_listaja):
                if not str(konyv_adat.get("cim", "")).strip():
                    continue
                if db.uj_konyv_hozzaadasa(konyv_adat):
                    sikeres += 1
                    sikeres_indexek.append(idx)
                    uj_konyv_objektumok.append(db.konyvek[-1])
                else:
                    elutasitott += 1
    finally:
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
# Azok a mezők, amelyek az egyezés-vizsgálatban részt vesznek: a cím mindig
# kötelező és pontosan egyeznie kell, a többinél csak az számít eltérésnek, ha
# mindkét oldalon ki van töltve és különbözik. (Az állomány és a dezideráta
# bibliográfiai mezői azonos kulcsúak, ezért nincs külön szabály.)
EGYEZES_MEZOK = ("cim", "szerzo", "kiado", "hely", "ev")

# A KERESO_MEZO_ALIASOK (a kereső külső JSON-jának fejlécnevei -> kanonikus
# kulcs) a constants.py mezőregiszteréből származik (importálva fent).


def is_same_book(item1, item2):
    """
    Két könyv/tétel egyezőségét vizsgálja (lásd tetelek_egyeznek).
    """
    return tetelek_egyeznek(item1, item2)


def sor_alap_adatta_alakitasa(forras_dict):
    """Egy nyers sor (a keresési JSON-ból vagy a táblázatból kiolvasott dict)
    leképezése az állomány kanonikus mezőneveire."""
    alap_adat = {}
    for kulcs, aliasok in KERESO_MEZO_ALIASOK.items():
        ertek = ""
        for alias in aliasok:
            if forras_dict.get(alias):
                ertek = forras_dict.get(alias)
                break
        alap_adat[kulcs] = ertek
    return alap_adat


# ==============================================================================
# KÖZÖS ÁTEMELŐ (DICT -> KANONIKUS ALAK) SEGÉDFÜGGVÉNYEK
# ==============================================================================
# Az állomány és a dezideráta-jegyzék csak a lenti, explicit mezőlistákban
# szereplő kulcsokat fogadja el. Az átemelt rekordot mindig ezekből építjük
# FEHÉRLISTÁVAL, ezért egy forrás ismeretlen mezője (pl. "megjegyzes") sosem
# kerül át, és a forrás eredeti dictjét sem módosítjuk (a
# KonyvAdatbazis.uj_konyv_hozzaadasa ugyanis a kapott dictbe beleírja az
# "id"-t, és a dictet szó szerint menti).
ALLOMANY_MEZOK = BIBLIOGRAFIAI_KULCSOK + (
    "oldalszam", "meretek", "kotes", "bekerult", "forras", "status",
    "rovid_leiras",
)

# A dezideráta bibliográfiai mezői és a
# dezideráta-specifikus mezők alapértékei.
DEZIDERATA_BIBLIO_MEZOK = BIBLIOGRAFIAI_KULCSOK
DEZIDERATA_ALAPERTEKEK = {
    "priority": "Másodlagos",
    "status": DEZIDERATA_STATUS_NEM_KAPHATO,
    "location": "",
    "price": "",
}


def _tiszta_szoveg(ertek):
    return str(ertek if ertek is not None else "").strip()


def allomany_rekord_forras_dictbol(forras_dict):
    """Egy keresési forrás sor-dictjéből (az eredeti, nem a megjelenített
    cellaszövegekből) felépíti az állományba felvehető rekordot: pontosan az
    ALLOMANY_MEZOK kulcsaival, szövegként. Ami a forrásban nincs, az üres."""
    alap = sor_alap_adatta_alakitasa(forras_dict)
    return {mezo: _tiszta_szoveg(alap.get(mezo, "")) for mezo in ALLOMANY_MEZOK}


def deziderata_tetel_forras_dictbol(forras_dict):
    """Egy keresési forrás sor-dictjéből felépíti a dezideráta-jegyzékbe
    felvehető tételt: a bibliográfiai mezők a forrásból, a prioritás, státusz,
    hely és ár a DEZIDERATA_ALAPERTEKEK-ből. A forrás saját status mezője
    szándékosan nem kerül át (más jelentése van)."""
    alap = sor_alap_adatta_alakitasa(forras_dict)
    tetel = {mezo: _tiszta_szoveg(alap.get(mezo, "")) for mezo in DEZIDERATA_BIBLIO_MEZOK}
    tetel.update(DEZIDERATA_ALAPERTEKEK)
    return tetel


# ------------------------------------------------------------------------------
# RÉGI (ANGOL KULCSÚ) DEZIDERATA-TÉTELEK EGYSZERI ÁTALAKÍTÁSA
# ------------------------------------------------------------------------------
# A dezideráta korábbi változata angol kulcsokkal tárolta a bibliográfiai
# mezőket. A program többi része már kizárólag a kanonikus (magyar) kulcsokat
# ismeri, ezért a régi tételeket MINDEN beolvasási ponton (fájlbetöltés,
# JSON-import) azonnal átalakítjuk. EZ AZ EGYETLEN HELY, ahol ezek a régi
# nevek még szerepelnek. Ha már biztosan nincs régi fájl/export, a
# függvény és a hívásai egyben törölhetők.
_REGI_ANGOL_KULCSOK = {
    "title": "cim",
    "subtitle": "alcim",
    "author": "szerzo",
    "publisher": "kiado",
    "place": "hely",
    "year": "ev",
}


def deziderata_regi_kulcsok_atalakitasa(tetelek):
    """A tételek (dict-ek listája) régi, angol kulcsait kanonikussá alakítja,
    helyben. Ha a kanonikus mező már ki van töltve, annak értéke marad; a régi
    kulcs minden esetben törlődik. True-t ad, ha módosított valamit."""
    valtozott = False
    for tetel in tetelek:
        if not isinstance(tetel, dict):
            continue
        for regi, uj in _REGI_ANGOL_KULCSOK.items():
            if regi not in tetel:
                continue
            ertek = tetel.pop(regi)
            if not tetel.get(uj) and ertek:
                tetel[uj] = ertek
            elif uj not in tetel:
                tetel[uj] = ertek if ertek is not None else ""
            valtozott = True
    return valtozott


def allomany_rekord_dezideratabol(tetel):
    """Egy dezideráta-tételből felépíti az állományba felvehető rekordot. A dezideráta "location"
    mezője az állomány "forras" mezőjébe kerül; az oldalszám, méret, kötés és
    rövid leírás azonos kulccsal kerül át."""
    rekord = {mezo: "" for mezo in ALLOMANY_MEZOK}
    for mezo in BIBLIOGRAFIAI_KULCSOK:
        rekord[mezo] = _tiszta_szoveg(tetel.get(mezo, ""))
    rekord["forras"] = _tiszta_szoveg(tetel.get("location", ""))
    # A "Beszerzés alatt" státusznál felvehető további adatok (oldalszám, méret,
    # kötés, rövid leírás): kulcsaik megegyeznek az állomány kulcsaival, ezért
    # közvetlenül átadódnak. Ami nincs kitöltve, az üres marad.
    for mezo in DEZIDERATA_BESZERZES_MEZOKULCSOK:
        rekord[mezo] = _tiszta_szoveg(tetel.get(mezo, ""))
    return rekord


class KeresoJsonHiba(Exception):
    """A kereső JSON fájl nem használható. Az üzenet (str(e)) közvetlenül a
    felhasználónak szól, ezért érthető, magyar szöveg."""


# Ennél nagyobb fájl megnyitása előtt a felület megerősítést kér.
KERESO_JSON_FIGYELMEZTETO_MERET = 50 * 1024 * 1024  # 50 MB


def kereso_cim_oszlop(oszlopok):
    """Megkeresi a Cím oszlop nevét a betöltött oszlopnevek között, UGYANAZOKKAL
    az aliasokkal, amelyeket a sor_alap_adatta_alakitasa is használ (így ami
    itt Cím oszlopnak számít, az átemelésnél is Cím lesz). None, ha nincs."""
    for alias in KERESO_MEZO_ALIASOK["cim"]:
        if alias in oszlopok:
            return alias
    return None


def load_kereso_json(fajl_utvonal):
    """Beolvassa és ELLENŐRZI a felhasználó által megnyitott kereső JSON fájlt.

    Visszatérés: (oszlopok, adat_lista). Az oszlopok az ÖSSZES rekord
    kulcsainak egyesítése az első előfordulás sorrendjében; az adat_lista
    sorai szöveggé alakított, levágott értékű dictek.

    Hibánál KeresoJsonHiba-t dob, felhasználónak szóló üzenettel; ilyenkor
    semmilyen állapotot nem módosít, a hívó a korábbi adatot megtarthatja."""
    if not fajl_utvonal or not os.path.isfile(fajl_utvonal):
        raise KeresoJsonHiba(f"A fájl nem található:\n{fajl_utvonal}")

    try:
        with open(fajl_utvonal, "r", encoding="utf-8-sig") as f:
            adatok = json.load(f)
    except UnicodeDecodeError:
        raise KeresoJsonHiba("A fájl nem UTF-8 kódolású szöveg, ezért nem olvasható.")
    except json.JSONDecodeError as e:
        raise KeresoJsonHiba(
            f"A fájl nem érvényes JSON ({e.lineno}. sor, {e.colno}. oszlop): {e.msg}"
        )
    except OSError as e:
        raise KeresoJsonHiba(f"A fájl nem olvasható:\n{e}")

    if not isinstance(adatok, list):
        raise KeresoJsonHiba(
            "A fájl nem könyvek listáját tartalmazza. A kereső olyan JSON-t vár, "
            "amelynek minden eleme egy könyv adatait tartalmazó rekord.\n\n"
            "(Az állományjegyzék és a dezideráta saját mentési fájljai itt nem használhatók.)"
        )
    if not adatok:
        raise KeresoJsonHiba("A fájl üres listát tartalmaz, nincs benne egyetlen könyv sem.")

    for index, sor in enumerate(adatok, start=1):
        if not isinstance(sor, dict):
            raise KeresoJsonHiba(
                f"A(z) {index}. elem nem könyvrekord (a kereső minden elemtől "
                "\"mező: érték\" szerkezetet vár)."
            )

    oszlopok = []
    lathato = set()
    for sor in adatok:
        for kulcs in sor:
            if kulcs not in lathato:
                lathato.add(kulcs)
                oszlopok.append(kulcs)

    if kereso_cim_oszlop(oszlopok) is None:
        elvart = " vagy ".join(f"\"{a}\"" for a in KERESO_MEZO_ALIASOK["cim"])
        talalt = ", ".join(str(o) for o in oszlopok[:12])
        if len(oszlopok) > 12:
            talalt += ", ..."
        raise KeresoJsonHiba(
            f"A fájlban nincs Cím oszlop (elvárt oszlopnév: {elvart}).\n\n"
            f"A fájl oszlopai: {talalt}"
        )

    adat_lista = [
        {k: str(v).strip() if v is not None else "" for k, v in sor.items()}
        for sor in adatok
    ]
    return oszlopok, adat_lista



def _norm_ertek(ertek):
    return str(ertek or "").strip().lower()


def tetelek_egyeznek(tetel1, tetel2, mezok=EGYEZES_MEZOK):
    """
    Két könyv/tétel (dict) egyezőségét vizsgálja.

    A Cím mindig kötelező és pontosan egyeznie kell. A többi mezőnél
    (alapesetben szerző, kiadó, hely, kiadás éve) csak akkor számít
    eltérésnek, ha MINDKÉT oldalon ki van töltve és a tartalmuk különbözik -
    egy üres mező tehát nem zárja ki az egyezést, ha a többi kitöltött mező
    megegyezik.

    A mezok az összehasonlított kulcsok sorozata; az első elemnek a "cim"-nek
    kell lennie.
    """
    cim1 = _norm_ertek(tetel1.get("cim"))
    cim2 = _norm_ertek(tetel2.get("cim"))
    if not cim1 or not cim2 or cim1 != cim2:
        return False

    for mezo in mezok:
        if mezo == "cim":
            continue
        ertek1 = _norm_ertek(tetel1.get(mezo))
        ertek2 = _norm_ertek(tetel2.get(mezo))
        if ertek1 and ertek2 and ertek1 != ertek2:
            return False

    return True


def keres_egyezo_konyv(tetel, meglevo_konyvek):
    """
    Megkeresi a tetel-hez legjobban illeszkedő meglévő könyvet.
    Ha több illeszkedő könyv is van (tetelek_egyeznek alapján),
    azt választja, amelyikkel a legtöbb nem-üres mező egyezik meg.
    Visszatérés: a meglévő könyv dict-je, vagy None.
    """
    jeloltek = []
    for konyv in meglevo_konyvek:
        if tetelek_egyeznek(tetel, konyv):
            pont = 0
            for mezo in EGYEZES_MEZOK:
                v1 = _norm_ertek(tetel.get(mezo))
                v2 = _norm_ertek(konyv.get(mezo))
                if v1 and v2 and v1 == v2:
                    pont += 1
            jeloltek.append((pont, konyv))
    if not jeloltek:
        return None
    jeloltek.sort(key=lambda x: x[0], reverse=True)
    return jeloltek[0][1]


def hataroz_meg_potolhato_mezok(meglevo_konyv, uj_tetel, mezok=None):
    """
    Megvizsgálja, hogy a meglévő könyv mely kitöltetlen mezőit tudja pótolni
    az importált tétel. Csak olyan mezőket vesz figyelembe, amelyek a meglévő
    könyvben üresek, az új tételben viszont szerepelnek kitöltve.
    
    Visszatérés: {kulcs: uj_ertek} szótár, vagy üres szótár.
    """
    potolhato = {}
    vizsgalando = mezok if mezok is not None else MEZOK
    for kulcs in vizsgalando:
        if kulcs in ("id", "cim"):
            continue
        regi_ertek = str(meglevo_konyv.get(kulcs, "") or "").strip()
        uj_ertek = str(uj_tetel.get(kulcs, "") or "").strip()
        if not regi_ertek and uj_ertek:
            potolhato[kulcs] = uj_ertek
    return potolhato


def normalizal_import_elem(nyers_elem):
    """Egy nyers importált dict kanonikus alakba hozása az aliasok feloldásával."""
    alap = sor_alap_adatta_alakitasa(nyers_elem)
    for k, v in nyers_elem.items():
        if k not in alap and v is not None:
            alap[k] = str(v).strip()
    return alap


def _potolhato_leiras(potolhato, mezocimkek=None):
    """A pótolható mezők ember által olvasható leírása ("Felirat: érték, ...")."""
    reszek = []
    for k, v in potolhato.items():
        if mezocimkek and k in mezocimkek:
            felirat = mezocimkek[k]
        elif k in MEZOK:
            felirat = MEZOK[k].lista
        else:
            felirat = k
        reszek.append(f"{felirat}: {v}")
    return ", ".join(reszek)


def elemez_json_import(
    importalt_lista,
    meglevo_konyvek,
    mezok=None,
    mezocimkek=None,
    regikulcsok_atalakitasa=False,
):
    """
    Elemzi a JSON-ból betöltött listát a meglévő állományhoz vagy deziderátához viszonyítva.
    
    Különválogatja:
      - uj_tetelek: teljesen új könyvek/tételek, amik még nincsenek az állományban/listában.
      - kiegeszitheto_tetelek: olyan könyvek/tételek, amelyek megegyeznek egy meglévővel,
        de tartalmaznak kitöltetlen mezőkhöz új adatokat.
      - kihagyott_duplum_db: olyan duplikátumok száma, amelyek semmilyen új adatot
        nem adnak a meglévőhöz.
      - ervenytelen_db: nem megfelelő formátumú vagy cím nélküli tételek.
    
    Visszatérés: (uj_tetelek, kiegeszitheto_tetelek, kihagyott_duplum_db, ervenytelen_db)
    """
    uj_tetelek = []
    kiegeszitheto_tetelek = []
    kihagyott_duplum_db = 0
    ervenytelen_db = 0

    latott_ujak = []

    for nyers_elem in importalt_lista:
        if not isinstance(nyers_elem, dict):
            ervenytelen_db += 1
            continue

        if regikulcsok_atalakitasa:
            deziderata_regi_kulcsok_atalakitasa([nyers_elem])

        elem = normalizal_import_elem(nyers_elem)
        cim = str(elem.get("cim", "") or "").strip()
        if not cim:
            ervenytelen_db += 1
            continue

        meglevo = keres_egyezo_konyv(elem, meglevo_konyvek)
        if meglevo is not None:
            potolhato = hataroz_meg_potolhato_mezok(meglevo, elem, mezok=mezok)
            if potolhato:
                mar_benne = False
                for mar_van in kiegeszitheto_tetelek:
                    if mar_van["meglevo"].get("id") == meglevo.get("id"):
                        mar_van["potolhato"].update(potolhato)
                        # A leírást az összevont mezőkből újraépítjük, hogy a
                        # további rekordok pótlásai is látsszanak benne.
                        mar_van["leiras"] = _potolhato_leiras(
                            mar_van["potolhato"], mezocimkek)
                        mar_benne = True
                        break
                if not mar_benne:
                    kiegeszitheto_tetelek.append({
                        "meglevo": meglevo,
                        "uj": elem,
                        "potolhato": potolhato,
                        "leiras": _potolhato_leiras(potolhato, mezocimkek),
                    })
            else:
                kihagyott_duplum_db += 1
        else:
            if any(tetelek_egyeznek(elem, korabbi) for korabbi in latott_ujak):
                kihagyott_duplum_db += 1
            else:
                latott_ujak.append(elem)
                uj_tetelek.append(elem)

    return uj_tetelek, kiegeszitheto_tetelek, kihagyott_duplum_db, ervenytelen_db


def _undo_lepes(leiras):
    """Dekorátor: a módosító metódus hívása egy visszavonható lépés. Ha egy
    nagyobb művelet (import, tömeges felvétel/törlés, átemelés) már csoportot
    nyitott, a belső hívások beleolvadnak abba."""
    def dekorator(fv):
        @functools.wraps(fv)
        def burkolt(self, *args, **kwargs):
            with self.undo.muvelet(leiras):
                return fv(self, *args, **kwargs)
        return burkolt
    return dekorator


class AdatbazisTarolo(ListaTarolo):
    """Az állomány (db.konyvek) undo-tárolója."""

    def __init__(self, db):
        self.db = db

    def lista(self):
        return self.db.konyvek

    def mentes(self):
        return self.db.AdatokMentese()

    def frissit(self, valtozas, kijelol):
        if self.db.nezet_frissito is not None:
            self.db.nezet_frissito(valtozas.erintett_idk(), kijelol)


class KonyvAdatbazis:
    def __init__(self, fajlnev=None):
        self.fajlnev = fajlnev or DEFAULT_ADATBAZIS_FAJL
        self.konyvek = []
        # A főablak állítja be: a könyvlista újrarajzolása egy visszavonás/
        # mégis után, f(kijelolendo_idk, kijelol) alakban (a lista akkor is
        # frissül, ha a visszavonást a Dezideráta-ablakból indították).
        self.nezet_frissito = None
        # Visszavonás/mégis: az adatbázison él, így minden módosítást
        # elkap, bárhonnan (főablak, szerkesztő dialógus, Dezideráta-kezelő
        # átemelése, KönyvTárnok-kereső) is érkezik. A regiszter közös a
        # Dezideráta-kezelővel, így az átemelések kapcsolt lépések.
        self.undo_regiszter = UndoRegiszter()
        self.undo_regiszter.tarolo_regisztral("allomany", lambda: AdatbazisTarolo(self))
        self.undo = UndoKezelo(self.undo_regiszter, ["allomany"], elsodleges=True)
        # Kötegelt mentés (lásd kotegelt_mentes): amíg a mélység > 0, az
        # AdatokMentese csak jelzi, hogy van mentetlen változás.
        self._mentes_melyseg = 0
        self._mentes_fuggoben = False
        # True, ha az állományjegyzék betöltése nem sikerült (lásd
        # AdatokBetoltese). Ilyenkor a konyvek üres, a lemezen viszont lehet
        # (sérült, de megmenthető) adat, ezért minden módosítás és mentés
        # le van tiltva: különben az első új könyv felvétele a fájl teljes
        # tartalmát az egyetlen új könyvvel írná felül.
        self.mentes_tiltva = False
        self.AdatokBetoltese()

    def is_duplikalat(self, uj_adatok, exclude_id=None):
        """
        Duplikátum-vizsgálat: megegyezik-e uj_adatok az állományban már
        szereplő valamelyik könyvvel (lásd tetelek_egyeznek).
        Ha exclude_id meg van adva, az adott azonosítójú könyvet figyelmen
        kívül hagyja (szerkesztés esetére).
        """
        if not _norm_ertek(uj_adatok.get("cim", "")):
            return False
        return any(
            tetelek_egyeznek(uj_adatok, konyv)
            for konyv in self.konyvek
            if exclude_id is None or konyv.get("id") != exclude_id
        )

    def AdatokBetoltese(self):
        self.undo.torol()
        self.mentes_tiltva = False
        tiltas_szoveg = (
            "\n\nA fájl védelme érdekében az állományjegyzék szerkesztése, "
            "importálása és exportálása le van tiltva."
        )
        try:
            adat, ervenyes = load_hmac_json(self.fajlnev)
        except Exception as e:
            logging.error(f"Hiba az állományjegyzék betöltésekor: {e}", exc_info=True)
            self.AlapertelmezettAdatok()
            self.mentes_tiltva = True
            wx.MessageBox(
                f"Hiba az adatok betöltésekor: {e}" + tiltas_szoveg,
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return

        if not ervenyes:
            logging.error(
                f"Az állományjegyzék ({self.fajlnev}) HMAC-aláírása érvénytelen: "
                "a fájl megsérült vagy jogosulatlanul módosították."
            )
            self.AlapertelmezettAdatok()
            self.mentes_tiltva = True
            wx.MessageBox(
                "Az állományjegyzék integritás-ellenőrzése sikertelen: a fájl "
                "megsérülhetett, vagy valaki módosította a programon kívül.\n\n"
                "Az adatok betöltése biztonsági okból megszakadt." + tiltas_szoveg,
                "Integritási hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return

        if not isinstance(adat, list):
            # Érvényes aláírás, de nem könyvlista: a tartalom ismeretlen, ezért
            # nem szabad "üres listaként" továbbvinni és később felülírni.
            logging.error(f"Az állományjegyzék ({self.fajlnev}) tartalma nem lista.")
            self.AlapertelmezettAdatok()
            self.mentes_tiltva = True
            wx.MessageBox(
                "Az állományjegyzék fájl tartalma nem könyvek listája." + tiltas_szoveg,
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return

        self.konyvek = adat

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

    def _ellenoriz_irhato(self):
        """SzerkesztesTiltvaHiba-t dob, ha az állomány betöltése sikertelen
        volt (lásd mentes_tiltva). A módosító metódusok az elején hívják, még
        a memóriabeli változtatás előtt."""
        if self.mentes_tiltva:
            raise SzerkesztesTiltvaHiba(
                "Az állományjegyzék betöltése nem sikerült, ezért a módosítás "
                f"le van tiltva ({self.fajlnev})."
            )

    def _lemezre_ir(self):
        # Utolsó védőháló: betöltési hiba után semmiképp sem írjuk felül a fájlt.
        if self.mentes_tiltva:
            logging.error("Az állományjegyzék mentése letiltva (sikertelen betöltés után).")
            return False
        return save_hmac_json(self.fajlnev, self.konyvek)

    def AdatokMentese(self):
        if self.mentes_tiltva:
            logging.error("Az állományjegyzék mentése letiltva (sikertelen betöltés után).")
            return False
        if self._mentes_melyseg:
            # Kötegelt mód: a tényleges lemezre írás a köteg végén történik.
            self._mentes_fuggoben = True
            return True
        return self._lemezre_ir()

    @contextmanager
    def kotegelt_mentes(self):
        """Tömeges módosításnál (pl. átemelés) a tételenkénti, teljes fájlt
        újraíró mentés helyett a blokk végén EGYETLEN mentés történik.

        Ha ez a záró mentés meghiúsul, MentesiHiba kivételt dob (kivéve, ha a
        blokkból már egy másik kivétel indult el: akkor csak naplóz). Fontos:
        ilyenkor a memóriabeli módosítások nem gördülnek vissza tételenként,
        a hívónak kell kezelnie a MentesiHiba-t.
        """
        self._mentes_melyseg += 1
        kivetel_van = False
        try:
            yield
        except BaseException:
            kivetel_van = True
            raise
        finally:
            self._mentes_melyseg -= 1
            if self._mentes_melyseg == 0 and self._mentes_fuggoben:
                self._mentes_fuggoben = False
                if not self._lemezre_ir():
                    hiba = f"Nem sikerült elmenteni az állományjegyzéket ({self.fajlnev})."
                    if kivetel_van:
                        logging.error(hiba)
                    else:
                        raise MentesiHiba(hiba)

    # --- ID ALAPÚ MENTÉS ---
    @_undo_lepes("könyv módosítása")
    def konyv_mentese_by_id(self, konyv_id, uj_adatok, engedelyez_duplikaciot=False):
        """Frissíti a konyv_id azonosítójú könyvet uj_adatok-kal.

        Visszatérési érték: True sikeres mentés esetén; False, ha a
        konyv_id-hoz KIFEJEZETTEN nem található könyv az állományban, vagy
        ha a módosított adatok alapján a könyv már szerepelne duplikátumként.

        Ha a könyvet megtaláltuk és módosítottuk a memóriában, de a lemezre
        mentés meghiúsul, a módosítást visszavonjuk (az eredeti adatokat
        állítjuk vissza ugyanabban a dict-objektumban, hogy a listában
        (KonyvListaCtrl) és az esetleges aktív szűrésben lévő referenciák
        érvényben maradjanak), és MentesiHiba kivételt dobunk - ezt
        korábban a hívó a "nem található az eredeti könyv" esettel
        megegyező False értékként kapta meg, ami félrevezető volt egy
        ténylegesen sikeres keresés + sikertelen lemezre írás esetén.
        """
        self._ellenoriz_irhato()
        if not engedelyez_duplikaciot and self.is_duplikalat(uj_adatok, exclude_id=konyv_id):
            return False

        for konyv in self.konyvek:
            if konyv.get("id") == konyv_id:
                eredeti_adatok = dict(konyv)
                konyv.update(uj_adatok)
                konyv["id"] = konyv_id  # ID megőrzése
                if not self.AdatokMentese():
                    konyv.clear()
                    konyv.update(eredeti_adatok)
                    raise MentesiHiba(
                        f"Nem sikerült elmenteni a módosítást ({self.fajlnev})."
                    )
                return True
        return False

    @_undo_lepes("könyv felvétele")
    def uj_konyv_hozzaadasa(self, uj_adatok, engedelyez_duplikaciot=False):
        """Felveszi az uj_adatok könyvet az állományba.

        Visszatérési érték: True, ha sikeresen felvette és el is mentette;
        False, ha ez KIFEJEZETTEN duplikátum miatt maradt el.

        Ha a felvétel maga sikeres lenne, de a lemezre mentés (AdatokMentese)
        meghiúsul, a felvételt visszavonjuk (hogy a memória és a lemez ne
        csússzon szét), és MentesiHiba kivételt dobunk - ezt korábban a
        hívók (pl. a KonyvSzerkesztoDialog "Mentés" gombja) a duplikátum
        esettel azonos módon, False-ként kapták meg, ami téves "már
        szerepel duplikátumként" hibaüzenetet eredményezett egy valójában
        lemezre írási hiba esetén.
        """
        self._ellenoriz_irhato()
        if not engedelyez_duplikaciot and self.is_duplikalat(uj_adatok):
            return False
        
        # Generálunk egyedi azonosítót az új könyvnek
        if "id" not in uj_adatok or not uj_adatok["id"]:
            uj_adatok["id"] = str(uuid.uuid4())

        self.konyvek.append(uj_adatok)
        if not self.AdatokMentese():
            self.konyvek.pop()
            raise MentesiHiba(
                f"Nem sikerült elmenteni az állományjegyzéket ({self.fajlnev})."
            )
        return True

    # --- ID ALAPÚ TÖRLES ---
    @_undo_lepes("könyv törlése")
    def konyv_torlese_by_id(self, konyv_id):
        """Törli a konyv_id azonosítójú könyvet az állományból.

        Visszatérési érték: True sikeres törlés esetén; False, ha a
        konyv_id-hoz KIFEJEZETTEN nem található könyv.

        Ha a könyvet megtaláltuk és eltávolítottuk a memóriából, de a
        lemezre mentés meghiúsul, a törlést visszavonjuk (visszatesszük a
        könyvet az eredeti pozíciójára), és MentesiHiba kivételt dobunk -
        korábban ezt a hívó (main_frame.OnKonyvTorles) egyáltalán nem is
        ellenőrizte, ezért egy sikertelen mentés a felhasználó számára
        teljesen észrevétlenül hagyta volna a könyvet "törtnek" a
        felületen, miközben a lemezen (és újraindítás után) még mindig
        szerepelt volna.
        """
        self._ellenoriz_irhato()
        for i, konyv in enumerate(self.konyvek):
            if konyv.get("id") == konyv_id:
                del self.konyvek[i]
                if not self.AdatokMentese():
                    self.konyvek.insert(i, konyv)
                    raise MentesiHiba(
                        f"Nem sikerült elmenteni a törlést ({self.fajlnev})."
                    )
                return True
        return False

    def save_to_json(self, target_filepath):
        try:
            with open(target_filepath, "w", encoding="utf-8") as f:
                json.dump(self.konyvek, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logging.error(f"Hiba az állományjegyzék mentésekor ({target_filepath}): {e}", exc_info=True)
            return False


def allomany_szerkesztheto(db, parent=None):
    """True, ha az állományjegyzék módosítható. Ha a betöltés sikertelen volt
    (lásd KonyvAdatbazis.mentes_tiltva), tájékoztatja a felhasználót és False-t
    ad: a hívó ilyenkor azonnal álljon le, hogy a meglévő (esetleg sérült)
    fájl ne íródjon felül. A Dezideráta-kezelő _szerkesztes_engedelyezett
    metódusának megfelelője a főállományra."""
    if not getattr(db, "mentes_tiltva", False):
        return True
    wx.MessageBox(
        "Az állományjegyzék betöltése nem sikerült, ezért a módosítása, "
        "importálása és exportálása le van tiltva: a program nem írja "
        "felül a meglévő (esetleg sérült) fájlt.\n"
        "Kérjük, távolítsa el a meglévő JSON fájlt a program mappájából, és "
        "indítsa újra a programot!\n\n"
        f"Fájl: {db.fajlnev}\n\n"
        "Ha a fájl sérült, állítsa vissza egy biztonsági másolatból, vagy "
        "nevezze át (pl. allomanyjegyzek_serult.json), majd indítsa újra a "
        "programot.",
        "Szerkesztés letiltva",
        wx.OK | wx.ICON_WARNING,
        parent,
    )
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
        f"Biztosan át szeretné emelni a kijelölt {darab} db {tetel_nev} {cel_nev}?"
        if darab > 1
        else f"Biztosan át szeretné emelni a kijelölt {tetel_nev} {cel_nev}?"
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


# ==============================================================================
# KÖZÖS SZÖVEGES KERESÉSI/SZŰRÉSI PREDIKÁTUM
# ==============================================================================
# Ezt az egyezés-logikát (egy tétel minden mezőértékét végignézve részszöveg-
# vagy pontos egyezés vizsgálata) korábban a főablak (main_frame.py) tartotta
# saját, privát metódusaként, jóllehet nincs benne semmi, ami a GUI-hoz vagy
# kifejezetten a könyvekhez kötné - bármilyen dict/lista/objektum-alapú
# tételgyűjteményen (pl. egy jövőbeli kereső ablakon vagy egy teszten)
# ugyanígy használható.
def szoveg_szuro_egyezik(tetel, keresett, pontos_egyezes, mezok=None, szavankent=False):
    """Egy tétel egyezik-e a keresett szöveggel.

    mezok=None (alapeset): a tétel MINDEN mezőértékében keres, kivéve a
    belső "id" azonosítót (UUID): az nem a felhasználónak szánt adat, és
    rövid keresőszavaknál (pl. "4", "ab") téves találatokat adna.
    mezok=[...]: csak a megadott logikai mezőkben (pl. "cim", "szerzo",
    "kiado", "hely", "ev") keres. Listaként/tuple-ként megadott
    tételnél a mezőnevek nem értelmezhetők, ott a mezok figyelmen kívül marad.

    szavankent=False (alapeset): a TELJES keresett kifejezésnek egyben, egyetlen
    mezőértékben kell szerepelnie.
    szavankent=True: a kifejezést szavakra bontjuk, és a tétel akkor egyezik,
    ha MINDEN szó szerepel valamelyik (vizsgált) mezőértékben - nem
    feltétlenül ugyanabban. Pl. a "kodály zsoltár" akkor is talál, ha a
    Kodály a szerző, a zsoltár pedig a cím mezőben van.

    pontos_egyezes=True: a keresett szöveg (szavankent módban minden egyes
    szó) csak egész szóként számít egyezésnek, Unicode-barát szóhatárral.
    """
    if mezok is not None and not isinstance(tetel, (list, tuple)):
        if isinstance(tetel, dict):
            forras = tetel
        elif hasattr(tetel, '__dict__'):
            forras = vars(tetel)
        else:
            forras = {}
        ertekek = [forras.get(mezo) or "" for mezo in mezok]
    elif isinstance(tetel, dict):
        ertekek = [ertek for kulcs, ertek in tetel.items() if kulcs != "id"]
    elif isinstance(tetel, (list, tuple)):
        ertekek = tetel
    else:
        ertekek = ([ertek for kulcs, ertek in vars(tetel).items() if kulcs != "id"]
                   if hasattr(tetel, '__dict__') else [])

    ertek_szovegek = [str(ertek).lower().strip() for ertek in ertekek if ertek]

    szavak = keresett.split() if szavankent else []
    if not szavak:
        szavak = [keresett]

    for szo in szavak:
        if pontos_egyezes:
            # Egész szó / szókapcsolat egyezés, Unicode-barát szóhatárral
            minta = re.compile(
                r"(?<!\w)" + re.escape(szo) + r"(?!\w)", re.IGNORECASE
            )
            talalt = any(minta.search(ertek_str) for ertek_str in ertek_szovegek)
        else:
            talalt = any(szo in ertek_str for ertek_str in ertek_szovegek)
        if not talalt:
            return False
    return True

def szuresi_talalatok(tetelek, keresett_szoveg, pontos_egyezes=False, mezok=None, szavankent=False):
    """Egy tételgyűjtemény (pl. könyvek listája) leszűrése egy szöveges
    keresésre, a szoveg_szuro_egyezik predikátum alapján. A mezok
    megadásával a keresés a felsorolt mezőkre szűkíthető, a szavankent=True
    pedig "és" kapcsolatot jelent a kifejezés szavai között (lásd ott)."""
    keresett = keresett_szoveg.lower().strip()
    return [
        tetel for tetel in tetelek
        if szoveg_szuro_egyezik(tetel, keresett, pontos_egyezes, mezok, szavankent)
    ]


# ==============================================================================
# KÖZÖS "VISSZAVONÁS / MÉGIS" LÉPÉS
# ==============================================================================
# A főablak, a Dezideráta-kezelő és a KönyvTárnok-kereső visszavonás/mégis
# kezelője korábban a leírás lekérdezésétől az ütközés-/mentési hiba
# üzenetéig egymástól függetlenül, szinte szó szerint megegyező formában
# volt megírva; csak a státuszsor elérése és az ablak-specifikus őrfeltételek
# (szövegmező-visszavonás, szerkesztés tiltása) tértek el.
def undo_lepes(kezelo, ismet, parent, statusz):
    """Egy visszavonás (ismet=False) vagy mégis (ismet=True) végrehajtása a
    kezelőn, a megfelelő üzenetekkel.

    statusz: egy szöveget váró függvény (pl. a státuszsor SetStatusText-je).
    True-t ad, ha a lépés végrehajtódott; False-t, ha nem volt mit
    visszavonni/ismételni, vagy a lépés ütközés vagy mentési hiba miatt
    nem hajtható végre (ilyenkor a hibaüzenetet ez a függvény már
    megjelenítette).
    """
    leiras = kezelo.ismetlendo_leiras() if ismet else kezelo.visszavonando_leiras()
    if leiras is None:
        return False

    # A lépés minden érintett oldalát (állomány, adott esetben a dezideráta
    # is) a regiszter alkalmazza, és a nézeteket is frissíti.
    if not (kezelo.ismet() if ismet else kezelo.visszavon()):
        uzenet = utkozes_uzenet(kezelo, ismet)
        if uzenet:
            wx.MessageBox(
                uzenet, "A művelet most nem hajtható végre",
                wx.OK | wx.ICON_INFORMATION, parent,
            )
        else:
            wx.MessageBox(
                "A művelet nem hajtható végre (a változás nem menthető), ezért "
                "az adatok a korábbi állapotukban maradtak.",
                "Mentési hiba", wx.OK | wx.ICON_ERROR, parent,
            )
        return False

    statusz(f"Újra alkalmazva: {leiras}." if ismet else f"Visszavonva: {leiras}.")
    return True
