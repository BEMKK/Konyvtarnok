import sys as _sys
import os as _os
import json
import logging

from constants import DEFAULT_LATHATO_OSZLOPOK

if getattr(_sys, 'frozen', False):
    _BASE_DIR = _os.path.dirname(_sys.executable)
else:
    _BASE_DIR = _os.path.dirname(_os.path.abspath(__file__))

SETTINGS_FILE = _os.path.join(_BASE_DIR, "settings.json")
DEFAULT_CONFIG = {
    "lathato_oszlopok": list(DEFAULT_LATHATO_OSZLOPOK),
    "tema": "vilagos",
    "last_json_dir": "",
    "last_pdf_dir": "",
    "last_stat_pdf_dir": "",
    "alapertelmezett_rendezes": "cim",
    "auto_update_check": True,
    "update_frequency": "startup",
    "last_update_check_date": ""
}

def load_settings():
    """Betölti a beállításokat a JSON fájlból. Ha nem létezik, az alapértelmezettel tér vissza."""
    if _os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Összefésülés az alapértelmezettel (ha hiányozna valamilyen kulcs)
                for key, val in DEFAULT_CONFIG.items():
                    config.setdefault(key, val)
                return config
        except Exception as e:
            logging.error("Hiba a beállítások betöltésekor", exc_info=True)
    return DEFAULT_CONFIG.copy()

def save_settings(config_data):
    """Elmenti a beállítások szótárát (dict) a JSON fájlba."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logging.error("Hiba a beállítások mentésekor", exc_info=True)
        return False
