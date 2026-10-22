APP_NAME = "KönyvTárnok"
APP_VERSION = "3.20.2"
APP_STAGE = ""
APP_TITLE = APP_NAME

# A könyvlistában alapértelmezetten megjelenő oszlopok.
# EZ AZ EGYETLEN HELY, ahol ez a lista definiálva van (lásd a config_manager.py,
# a konyv_lista.py és a dialogs.py hivatkozásait).
DEFAULT_LATHATO_OSZLOPOK = ["cim", "szerzo", "kiado", "hely", "ev", "status"]


# ==============================================================================
# MEZŐREGISZTER - A KÖNYV (ÁLLOMÁNY) MEZŐINEK EGYETLEN FORRÁSA
# ==============================================================================
# EZ AZ EGYETLEN HELY, ahol egy állomány-mező kulcsa, feliratai, lista-
# oszlopának alapszélessége/súlya és a külső (kereső) JSON-ban használt
# fejlécnevei definiálva vannak. Egy mező átnevezése/átrendezése/átméretezése
# itt egyetlen sor átírását jelenti; minden más lista és szótár (űrlapfeliratok,
# lista-oszlopok, PDF-sablon, beállítások, kereső-átemelés) innen származik.
#
# Mezők (a sorrend számít: ez az űrlapok és a lista oszlopainak sorrendje is):
#   urlap           az adatlap/szerkesztő/PDF felirata (kettősponttal)
#   lista           a lista fejlécének (rövidebb) felirata; ha None, az urlap
#                   felirata a végi kettőspont nélkül
#   szelesseg/suly  a lista oszlopának alapszélessége pixelben, illetve a
#                   átméretezéskor a többletszélességből kapott részesedése;
#                   ha a szelesseg None, a mezőnek nincs oszlopa a listában
#   forras_fejlecek a KönyvTárnok-kereső külső JSON-jában használt fejlécnevek
#                   (a kanonikus kulcson kívül). SZÁNDÉKOSAN KÜLÖN ÉRTÉK, nem
#                   követi az urlap/lista feliratot: a külső fájl fejléce attól
#                   még nem változik, hogy a program feliratát átnevezzük.
#                   None = a mező nem jön át a keresőből; () = csak a pontos,
#                   kanonikus kulccsal jöhet át (lásd lentebb: forras, status).
class Mezo:
    __slots__ = ("urlap", "lista", "szelesseg", "suly", "forras_fejlecek")

    def __init__(self, urlap, lista=None, szelesseg=None, suly=None,
                 forras_fejlecek=None):
        self.urlap = urlap
        self.lista = lista if lista is not None else urlap.rstrip(":")
        self.szelesseg = szelesseg
        self.suly = suly
        self.forras_fejlecek = forras_fejlecek


# --- bibliográfiai adatok (az állományban és a deziderátában is ugyanezek) ---
_BIBLIOGRAFIAI_MEZOK = {
    "cim":             Mezo("Cím:", szelesseg=200, suly=3.0,
                            forras_fejlecek=("Cím",)),
    "alcim":           Mezo("Alcím:", szelesseg=180, suly=2.5,
                            forras_fejlecek=("Alcím",)),
    "szerzo":          Mezo("Szerző / Összeállító:", szelesseg=180, suly=2.0,
                            forras_fejlecek=("Szerző / Összeállító", "Összeállító")),
    "egyeb_szemelyek": Mezo("Egyéb személyek:", szelesseg=150, suly=2.0,
                            forras_fejlecek=("Egyéb személyek",)),
    "kiado":           Mezo("Kiadó:", szelesseg=180, suly=2.0,
                            forras_fejlecek=("Kiadó",)),
    "hely":            Mezo("Kiadás helye:", szelesseg=110, suly=1.0,
                            forras_fejlecek=("Kiadás helye",)),
    "ev":              Mezo("Kiadás éve:", szelesseg=90, suly=0.5,
                            forras_fejlecek=("Kiadás éve",)),
}

# --- a példány (az állományban lévő könyv) saját adatai ---
# FIGYELEM: a "forras" és a "status" kulcs a könyvnél a PÉLDÁNY forrását és
# státuszát jelenti. A kereső táblázatának "Státusz" (Állományban/
# Deziderátában) és "Forrás" (többforrásos nézet) oszlopa mást jelent, ezért
# ezekhez SZÁNDÉKOSAN nincs külső fejléc-alias (forras_fejlecek=()).
# A dezideráta "status"-a is más jelentésű (Jelenleg kapható / nem kapható),
# lásd lentebb a DEZIDERATA_SAJAT_MEZOK-at.
_PELDANY_MEZOK = {
    "oldalszam":    Mezo("Oldalszám:", szelesseg=80, suly=0.5,
                         forras_fejlecek=("Oldalszám",)),
    "meretek":      Mezo("Méret (Ma x sz, cm):", lista="Méret",
                         szelesseg=90, suly=0.5,
                         forras_fejlecek=("Méretek", "Méret")),
    "kotes":        Mezo("Kötés típusa:", lista="Kötés",
                         szelesseg=90, suly=0.5,
                         forras_fejlecek=("Kötés",)),
    "bekerult":     Mezo("Bekerülés dátuma:", lista="Bekerült",
                         szelesseg=100, suly=0.8),
    "forras":       Mezo("Példány forrása:", lista="Forrás",
                         szelesseg=80, suly=0.5, forras_fejlecek=()),
    "status":       Mezo("Példány státusza:", lista="Státusz",
                         szelesseg=100, suly=0.8, forras_fejlecek=()),
    "rovid_leiras": Mezo("Példány rövid leírása:",
                         forras_fejlecek=("Rövid leírás",)),
}

MEZOK = {**_BIBLIOGRAFIAI_MEZOK, **_PELDANY_MEZOK}

# A bibliográfiai mezők kulcsai (az állomány és a dezideráta közös magja).
BIBLIOGRAFIAI_KULCSOK = tuple(_BIBLIOGRAFIAI_MEZOK)

# A könyv adatlapján/szerkesztőjén megjelenő (kulcs, felirat) párok, két
# logikai csoportra bontva. (Az export_manager.py PDF-sablonja is ezeket
# használja - a nevek és az alak változatlan.)
BIBLIOGRAFIAI_MEZO_DEFINICIOK = [(k, m.urlap) for k, m in _BIBLIOGRAFIAI_MEZOK.items()]
PELDANY_MEZO_DEFINICIOK = [(k, m.urlap) for k, m in _PELDANY_MEZOK.items()]
MEZO_DEFINICIOK = BIBLIOGRAFIAI_MEZO_DEFINICIOK + PELDANY_MEZO_DEFINICIOK

# {kulcs: (fejléc felirata, alap szélesség)} - csak az oszloppal rendelkező
# mezők. A katalogus_pdf és más (defs-et átvevő) hívók számára változatlan alak.
OSZLOP_DEFINICIOK = {k: (m.lista, m.szelesseg)
                     for k, m in MEZOK.items() if m.szelesseg is not None}

# {kulcs: súly} - az átméretezéskor a szabad hely elosztásához
OSZLOP_SULYOK = {k: m.suly for k, m in MEZOK.items() if m.szelesseg is not None}

# A beállítások ablak oszlopválasztó jelölőnégyzeteinek (kulcs, felirat) párjai;
# a felirat megegyezik a lista tényleges oszlopfejlécével.
ELERHETO_OSZLOPOK = [(kulcs, adat[0]) for kulcs, adat in OSZLOP_DEFINICIOK.items()]

# A KönyvTárnok-kereső külső JSON-jának fejlécnevei -> kanonikus kulcs:
# {kulcs: (kulcs, külső fejléc, ...)}. A data_manager.sor_alap_adatta_
# alakitasa ez alapján képezi le a nyers sorokat az állomány mezőire.
KERESO_MEZO_ALIASOK = {
    k: (k,) + m.forras_fejlecek
    for k, m in MEZOK.items() if m.forras_fejlecek is not None
}


# ==============================================================================
# A DEZIDERATA MEZŐI
# ==============================================================================
# A dezideráta-tétel bibliográfiai mezői megegyeznek a könyvéivel (fent), de
# a többi mezője más: a "status" itt azt jelenti, hogy a tétel jelenleg
# kapható-e, a "forras" helyett "location" (lelőhely) van, és van prioritás,
# ár és link. Ezek kulcsai a deziderata.json-ban így vannak tárolva.
DEZIDERATA_SAJAT_MEZO_DEFINICIOK = [
    ("priority", "Prioritás:"),
    ("status", "Státusz:"),
    ("location", "Lelőhely:"),
    ("price", "Jelenlegi ár (ft):"),
    ("link", "Link:"),
]

# A dezideráta űrlapjának/adatlapjának (kulcs, felirat) párjai, sorrendben.
DEZIDERATA_MEZO_DEFINICIOK = (BIBLIOGRAFIAI_MEZO_DEFINICIOK
                              + DEZIDERATA_SAJAT_MEZO_DEFINICIOK)

# A dezideráta listájának (és a katalóguslapjának) oszlopai sorrendben:
# kulcs: (alap szélesség pixelben, kitöltési súly átméretezéskor). A fejléc
# felirata a DEZIDERATA_MEZO_DEFINICIOK-ból jön (kettőspont nélkül). A
# szélességek a főlistáétól szándékosan eltérnek (más a tartalom).
DEZIDERATA_OSZLOP_ADATOK = {
    "cim":             (200, 3.0),
    "alcim":           (170, 3.0),
    "szerzo":          (130, 2.0),
    "egyeb_szemelyek": (120, 2.0),
    "kiado":           (140, 2.0),
    "hely":            (100, 1.0),
    "ev":              ( 80, 0.5),
    "priority":        ( 85, 0.8),
    "status":          (130, 1.5),
}
DEZIDERATA_OSZLOP_KULCSOK = list(DEZIDERATA_OSZLOP_ADATOK)
