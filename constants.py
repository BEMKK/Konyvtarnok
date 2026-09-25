APP_NAME = "KönyvTárnok"
APP_VERSION = "3.1.2"
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