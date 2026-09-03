import json
import os
import logging

SETTINGS_FILE = "settings.json"
DEFAULT_CONFIG = {
    "lathato_oszlopok": ["cim", "szerzo", "kiado", "hely", "ev", "status"],
    "tema": "vilagos",
    "last_json_dir": "",
    "last_pdf_dir": "",
    "last_stat_pdf_dir": "",
    "alapertelmezett_rendezes": "cim"
}

def load_settings():
    """Betölti a beállításokat a JSON fájlból. Ha nem létezik, az alapértelmezettel tér vissza."""
    if os.path.exists(SETTINGS_FILE):
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
