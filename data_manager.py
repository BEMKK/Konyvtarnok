# data_manager.py

import json
import os
import logging
import uuid
from cryptography.fernet import Fernet
from import_manager import import_konyv_pdf

class KonyvAdatbazis:
    def __init__(self, fajlnev="allomanyjegyzek.json", key=None):
        self.fajlnev = fajlnev
        if key:
            self.key = key
        else:
            self.key = self._get_or_create_key()

        self.cipher = Fernet(self.key)
        self.konyvek = []
        self.AdatokBetoltese()

    def _get_or_create_key(self):
        appdata_dir = os.path.join(os.path.expanduser("~"), ".konyvtar_app")
        os.makedirs(appdata_dir, exist_ok=True)
        
        key_file_path = os.path.join(appdata_dir, "secret.key")

        if os.path.exists(key_file_path):
            with open(key_file_path, "rb") as kf:
                return kf.read()
        else:
            new_key = Fernet.generate_key()
            with open(key_file_path, "wb") as kf:
                kf.write(new_key)
            return new_key

    def is_duplikalat(self, uj_adatok):
        kulcs_mezok = ["cim", "szerzo", "kiado", "hely", "ev"]
        uj_kulcsok = tuple(
            str(uj_adatok.get(mezo, "")).strip().lower() 
            for mezo in kulcs_mezok
        )

        for konyv in self.konyvek:
            meglevo_kulcsok = tuple(
                str(konyv.get(mezo, "")).strip().lower() 
                for mezo in kulcs_mezok
            )
            if uj_kulcsok == meglevo_kulcsok:
                return True
                
        return False

    def AdatokBetoltese(self):
        if os.path.exists(self.fajlnev):
            try:
                with open(self.fajlnev, "rb") as f:
                    nyers_adat = f.read()

                # 2. Dekódolási kísérletek
                try:
                    decrypted_bytes = self.cipher.decrypt(nyers_adat)
                    self.konyvek = json.loads(decrypted_bytes.decode("utf-8"))
                except Exception:
                    # Ha a titkosított dekódolás nem sikerül, megpróbáljuk sima JSON-ként
                    self.konyvek = json.loads(nyers_adat.decode("utf-8"))
                    self.AdatokMentese()

                # 3. Hiányzó ID-k pótlása
                modositva = False
                for konyv in self.konyvek:
                    if isinstance(konyv, dict) and "id" not in konyv:
                        konyv["id"] = str(uuid.uuid4())
                        modositva = True
                if modositva:
                    self.AdatokMentese()

            except Exception as e:
                self.AlapertelmezettAdatok()
        else:
            self.AlapertelmezettAdatok()

    def AlapertelmezettAdatok(self):
        self.konyvek = []

    def AdatokMentese(self):
        try:
            json_str = json.dumps(self.konyvek, ensure_ascii=False, indent=4)
            encrypted_bytes = self.cipher.encrypt(json_str.encode("utf-8"))
            
            with open(self.fajlnev, "wb") as f:
                f.write(encrypted_bytes)
            return True
        except Exception as e:
            logging.error(f"Hiba a fájl titkosítása során: {e}")
            return False

    def get_osszes_cim(self):
        return [konyv["cim"] for konyv in self.konyvek]

    # --- ID ALAPÚ KERESÉS ---
    def get_konyv_by_id(self, konyv_id):
        for konyv in self.konyvek:
            if konyv.get("id") == konyv_id:
                return konyv
        return {}

    def get_konyv_adatok(self, cim):
        """Megtartva kompatibilitási okokból."""
        for konyv in self.konyvek:
            if konyv.get("cim") == cim:
                return konyv
        return {}

    # --- ID ALAPÚ MENTÉS ---
    def konyv_mentese_by_id(self, konyv_id, uj_adatok):
        for konyv in self.konyvek:
            if konyv.get("id") == konyv_id:
                konyv.update(uj_adatok)
                konyv["id"] = konyv_id  # ID megőrzése
                self.AdatokMentese()
                return True
        return False

    def konyv_mentese(self, eredeti_cim, uj_adatok):
        """Cím alapú mentés (visszafelé kompatibilitás)."""
        for konyv in self.konyvek:
            if konyv.get("cim") == eredeti_cim:
                konyv.update(uj_adatok)
                self.AdatokMentese()
                return True
        return False

    def uj_konyv_hozzaadasa(self, uj_adatok, engedelyez_duplikációt=False):
        if not engedelyez_duplikációt and self.is_duplikalat(uj_adatok):
            return False
        
        # Generálunk egyedi azonosítót az új könyvnek
        if "id" not in uj_adatok or not uj_adatok["id"]:
            uj_adatok["id"] = str(uuid.uuid4())

        self.konyvek.append(uj_adatok)
        self.AdatokMentese()
        return True

    # --- ID ALAPÚ TÖRLES ---
    def konyv_torlese_by_id(self, konyv_id):
        for i, konyv in enumerate(self.konyvek):
            if konyv.get("id") == konyv_id:
                del self.konyvek[i]
                self.AdatokMentese()
                return True
        return False

    def konyv_torlese(self, cim):
        for i, konyv in enumerate(self.konyvek):
            if konyv.get("cim") == cim:
                del self.konyvek[i]
                self.AdatokMentese()
                return True
        return False

    def importalt_konyv_hozzaadasa(self, fajlnev):
        if fajlnev.endswith(".pdf"):
            konyv = import_konyv_pdf(fajlnev)
        else:
            return False

        self.uj_konyv_hozzaadasa(konyv)
        return True

    def save_to_json(self, target_filepath):
        try:
            with open(target_filepath, "w", encoding="utf-8") as f:
                json.dump(self.konyvek, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logging.error(f"Hiba az állományjegyzék mentésekor ({target_filepath}): {e}", exc_info=True)
            return False

    def load_from_json(self, source_filepath):
        try:
            with open(source_filepath, "r", encoding="utf-8") as f:
                uj_adatok = json.load(f)
                if isinstance(uj_adatok, list):
                    for konyv in uj_adatok:
                        if isinstance(konyv, dict) and "id" not in konyv:
                            konyv["id"] = str(uuid.uuid4())
                    self.konyvek = uj_adatok
                    self.AdatokMentese()
                    return True
            return False
        except Exception as e:
            logging.error(f"Hiba az állományjegyzék betöltésekor ({source_filepath}): {e}", exc_info=True)
            return False