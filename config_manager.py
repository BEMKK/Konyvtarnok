import copy
import os as _os
import json
import logging

from constants import DEFAULT_LATHATO_OSZLOPOK, DEFAULT_DEZIDERATA_LATHATO_OSZLOPOK
# Az alkalmazás alapmappájának (exe melletti, ill. szkript-mappa)
# meghatározása az utils.py-ba került, mert ezt korábban a
# config_manager.py, a data_manager.py, a deziderata.py és a main.py
# egymástól függetlenül, szó szerint megegyező formában tartalmazta.
from utils import alkalmazas_alapmappa

_BASE_DIR = alkalmazas_alapmappa()

SETTINGS_FILE = _os.path.join(_BASE_DIR, "settings.json")
DEFAULT_CONFIG = {
    "lathato_oszlopok": list(DEFAULT_LATHATO_OSZLOPOK),
    # A Dezideráta-kezelő listájában látható oszlopok (a "cim" mindig látszik).
    "deziderata_lathato_oszlopok": list(DEFAULT_DEZIDERATA_LATHATO_OSZLOPOK),
    "tema": "rendszer",
    "last_allomany_dir": "",
    "last_deziderata_dir": "",
    "last_pdf_dir": "",
    "last_stat_pdf_dir": "",
    "last_katalogus_dir": "",
    "kereso_json_utvonal": "",
    # A KönyvTárnok-kereső találati listája üres keresőmezőnél: "ures" | "osszes"
    "kereso_inditasi_lista": "ures",
    "alapertelmezett_rendezes": "cim",
    # A Dezideráta-kezelő és a KönyvTárnok-kereső utoljára választott
    # rendezése (Nézet > Rendezés). A szűrések szándékosan nem mentődnek.
    "deziderata_rendezes": "cim",
    "kereso_rendezes": "cim",
    "update_frequency": "startup",
    "last_update_check_date": ""
}

def load_settings():
    """Betölti a beállításokat a JSON fájlból. Ha nem létezik, az alapértelmezettel tér vissza."""
    if _os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Migráció: a régi auto_update_check=False beállítás helyett
                # most az update_frequency="never" érték jelzi a kikapcsolást.
                # A setdefault ciklus előtt kell lefutnia.
                if config.pop("auto_update_check", True) is False:
                    config["update_frequency"] = "never"
                # Összefésülés az alapértelmezettel (ha hiányozna valamilyen kulcs)
                for key, val in DEFAULT_CONFIG.items():
                    config.setdefault(key, copy.deepcopy(val))
                return config
        except Exception:
            logging.error("Hiba a beállítások betöltésekor", exc_info=True)
    return copy.deepcopy(DEFAULT_CONFIG)

def save_settings(config_data):
    """Elmenti a beállítások szótárát (dict) a JSON fájlba."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        logging.error("Hiba a beállítások mentésekor", exc_info=True)
        return False


def beallitas_mentese(kulcs, ertek):
    """Egyetlen beállítás (pl. egy ablak rendezése) elmentése. Ha az érték nem
    változott, nem ír a lemezre. True, ha az érték a fájlban van (mentés
    sikerült vagy nem kellett), False, ha a mentés nem sikerült."""
    config = load_settings()
    if config.get(kulcs) == ertek:
        return True
    config[kulcs] = ertek
    return save_settings(config)
