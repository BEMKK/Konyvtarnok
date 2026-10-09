APP_NAME = "KönyvTárnok"
APP_VERSION = "3.12.0"
APP_STAGE = ""
APP_TITLE = APP_NAME

# A könyvlistában alapértelmezetten megjelenő oszlopok.
# EZ AZ EGYETLEN HELY, ahol ez a lista definiálva van - korábban a
# config_manager.py, a konyv_lista.py (KonyvListaCtrl saját fallback-je) és
# a dialogs.py (BeallitasokDialog "Alapértelmezettek visszaállítása" gombja)
# egymástól függetlenül, három kicsit eltérő listát tartalmazott. Innentől
# mindhárom helyen ezt a konstanst importáljuk, hogy az "alapértelmezett
# oszlopok" fogalma mindenhol ugyanazt jelentse.
DEFAULT_LATHATO_OSZLOPOK = ["cim", "szerzo", "kiado", "hely", "ev", "status"]

# A könyv adatlapján/szerkesztőjén megjelenő mezők (kulcs, felirat) párjai,
# két logikai csoportra bontva (bibliográfiai adatok / a példány adatai).
# EZ AZ EGYETLEN HELY, ahol ez a mezősor és a hozzá tartozó feliratok
# definiálva vannak - korábban a konyvdialogs.py (KonyvReszletekDialog és
# KonyvSzerkesztoDialog mezői) és az export_manager.py (a PDF-export
# sablonszövege) egymástól függetlenül, kézzel tartotta szinkronban ugyanezt
# a mezőlistát és feliratkészletet, ami könnyen szétcsúszhatott volna, ha
# valaki csak az egyik helyen vesz fel/nevez át egy mezőt.
BIBLIOGRAFIAI_MEZO_DEFINICIOK = [
    ("cim", "Cím:"),
    ("alcim", "Alcím:"),
    ("szerzo", "Összeállító:"),
    ("egyeb_szemelyek", "Egyéb személyek:"),
    ("kiado", "Kiadó:"),
    ("hely", "Kiadás helye:"),
    ("ev", "Kiadás éve:"),
]

PELDANY_MEZO_DEFINICIOK = [
    ("oldalszam", "Oldalszám:"),
    ("meretek", "Méret (Ma x sz, cm):"),
    ("kotes", "Kötés típusa:"),
    ("rovid_cim", "Rövid cím:"),
    ("bekerult", "Bekerülés dátuma:"),
    ("forras", "Példány forrása:"),
    ("status", "Példány státusza:"),
    ("rovid_leiras", "Példány rövid leírása:"),
]

MEZO_DEFINICIOK = BIBLIOGRAFIAI_MEZO_DEFINICIOK + PELDANY_MEZO_DEFINICIOK

# A könyvlista oszlopai: kulcs -> (fejléc felirata, alap szélesség pixelben,
# kitöltési súly). EZ AZ EGYETLEN HELY, ahol az oszlopok felirata, alap
# szélessége és az átméretezéskor a többletszélességből kapott részesedése
# (súlya) definiálva van - korábban a feliratok/szélességek a
# KonyvListaCtrl.OSZLOP_DEFINICIOK-ban, a súlyok pedig az
# IgazitOszlopSzelesseg-ben (minden híváskor újra felépített helyi szótárban)
# éltek, a settings.py jelölőnégyzet-feliratai pedig innen származtak.
_OSZLOP_ADATOK = {
    "cim":             ("Cím",             200, 3.0),
    "alcim":           ("Alcím",           180, 2.5),
    "szerzo":          ("Összeállító",     180, 2.0),
    "egyeb_szemelyek": ("Egyéb személyek", 150, 2.0),
    "kiado":           ("Kiadó",           180, 2.0),
    "hely":            ("Kiadás helye",    110, 1.0),
    "ev":              ("Kiadás éve",       90, 0.5),
    "oldalszam":       ("Oldalszám",        80, 0.5),
    "meretek":         ("Méret",            90, 0.5),
    "kotes":           ("Kötés",            90, 0.5),
    "rovid_cim":       ("Rövid cím",       120, 1.5),
    "bekerult":        ("Bekerült",        100, 0.8),
    "forras":          ("Forrás",           80, 0.5),
    "status":          ("Státusz",         100, 0.8),
}

# {kulcs: (felirat, alap szélesség)} - a korábbi KonyvListaCtrl.OSZLOP_DEFINICIOK
# változatlan alakja, így a katalogus_pdf és más (defs-et átvevő) hívók
# módosítás nélkül tovább működnek.
OSZLOP_DEFINICIOK = {k: (nev, szel) for k, (nev, szel, _) in _OSZLOP_ADATOK.items()}

# {kulcs: súly} - az átméretezéskor a szabad hely elosztásához
OSZLOP_SULYOK = {k: suly for k, (_, _, suly) in _OSZLOP_ADATOK.items()}

# A beállítások ablak oszlopválasztó jelölőnégyzeteinek (kulcs, felirat) párjai;
# a felirat megegyezik a lista tényleges oszlopfejlécével.
ELERHETO_OSZLOPOK = [(kulcs, adat[0]) for kulcs, adat in OSZLOP_DEFINICIOK.items()]
