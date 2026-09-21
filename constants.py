APP_NAME = "KönyvTárnok"
APP_VERSION = "3.0.0"
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