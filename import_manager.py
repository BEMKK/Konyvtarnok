import re
import os
import pdfplumber
import logging

# Közös mező-leképezés a könnyebb karbantarthatóságért
KULCSSZAVAK = {
    "cím": "cim",
    "alcím": "alcim",
    "szerző": "szerzo",
    "összeállító": "szerzo",
    "egyéb személyek": "egyeb_szemelyek",
    "közreműködő": "egyeb_szemelyek",
    "kiadó": "kiado",
    "kiadás helye": "hely",
    "hely": "hely",
    "kiadás éve": "ev",
    "év": "ev",
    "oldalszám": "oldalszam",
    "terjedelem": "oldalszam",
    "méretek": "meretek",
    "méret": "meretek",
    "kötés": "kotes",
    "rövid cím": "rovid_cim",
    "bekerült": "bekerult",
    "forrás": "forras",
    "státusz": "status",
    "példány rövid leírása": "rovid_leiras",  # JAVÍTÁS: Pontos kisbetűs kulcs a biztonság kedvéért
    "rövid leírás": "rovid_leiras",
    "leírás": "rovid_leiras",
}

# Létrehozzuk a rendezett listát a hosszabb kulcsszavaktól a rövidebbek felé
RENDEZETT_KULCSSZAVAK = sorted(KULCSSZAVAK.items(), key=lambda x: len(x[0]), reverse=True)
# Címek/fejezetek, amiket az importálónak egyszerűen figyelmen kívül kell hagynia
# (A "példány rövid leírása" INNEN TÖRÖLVE LETT, mert azt mezőként kell kezelni!)
MEGJEGYZESEK_ES_FEJEZETEK = [
    "bibliográfiai adatok",
    "egyéb adatok",
    "példány adatai",
    "katalógus adatok",
]

def _szoveg_feldolgozas(szoveg):
    adat = {
        "cim": "", "alcim": "", "szerzo": "", "egyeb_szemelyek": "", 
        "kiado": "", "hely": "", "ev": "", "oldalszam": "",
        "meretek": "", "kotes": "", "rovid_cim": "", 
        "bekerult": "", "forras": "", "status": "", "rovid_leiras": ""
    }
    
    utolso_kulcs = None

    for sor in szoveg.splitlines():
        s = sor.strip()
        if not s:
            continue

        s_lower = s.lower()
        tisztitott_sor = s_lower.rstrip(":")

        # 1. FEJEZETCÍMEK ÁTUGRA (Kivételek, amiket teljesen figyelmen kívül hagyunk)
        if tisztitott_sor in MEGJEGYZESEK_ES_FEJEZETEK:
            continue

        # 2. ISMERT KULCS KERESÉSE (Kettősponttal VAGY anélkül)
        talalt_kulcs = None
        ertek_resz = ""

        if ":" in s:
            kulcs_resz, ertek_resz = s.split(":", 1)
            kulcs_tisztitott = kulcs_resz.strip().lower()

            for kulcsszo, adat_kulcs in RENDEZETT_KULCSSZAVAK:
                if kulcsszo == kulcs_tisztitott or kulcsszo in kulcs_tisztitott:
                    talalt_kulcs = adat_kulcs
                    break
        else:
            # HA NINCS KETTŐSPONT: megnézzük, hogy a teljes sor megegyezik-e valamelyik kulcsszóval!
            for kulcsszo, adat_kulcs in RENDEZETT_KULCSSZAVAK:
                if kulcsszo == tisztitott_sor:
                    talalt_kulcs = adat_kulcs
                    ertek_resz = ""  # Mivel az érték a következő sorban kezdődik
                    break

        # 3. FELDOLGOZÁSI LOGIKA
        if talalt_kulcs:
            # Új mezőt találtunk! Átállítjuk az utolso_kulcs-ot,
            # így az ezt követő sorok (a leírás törzsszövege) már ide gyűlnek.
            if ertek_resz.strip():
                adat[talalt_kulcs] = ertek_resz.strip()
            utolso_kulcs = talalt_kulcs

        elif utolso_kulcs:
            # Ha nem új kulcs, de van korábbi mezőnk (pl. rovid_leiras),
            # akkor a sort hozzáfűzzük a tartalomhoz.
            if adat[utolso_kulcs]:
                adat[utolso_kulcs] += "\n" + s
            else:
                adat[utolso_kulcs] = s

    # Szóközök feltakarítása a végén
    for k in adat:
        adat[k] = adat[k].strip()                

    return adat

def import_konyv_pdf(fajlnev):
    with pdfplumber.open(fajlnev) as pdf:
        szoveg = ""
        for oldal in pdf.pages:
            kivont = oldal.extract_text()
            if kivont:
                szoveg += kivont + "\n"
    return _szoveg_feldolgozas(szoveg)

import os

def import_tobb_fajl(fajl_list):
    """
    Egy listányi fájlnevet vár, és visszaadja az importált adatok listáját.
    Sikertelen import esetén nem száll el a program, hanem átugorja a hibás fájlt.
    """
    osszes_adat = []
    for fajlnev in fajl_list:
        if not os.path.exists(fajlnev):
            print(f"Hiba: A fájl nem található: {fajlnev}")
            continue
            
        ext = os.path.splitext(fajlnev)[1].lower()
        try:
            if ext == ".pdf":
                adat = import_konyv_pdf(fajlnev)
                osszes_adat.append(adat)
            else:
                print(f"Nem támogatott formátum: {fajlnev}")
        except Exception as e:
            logging.error(f"Hiba történt a(z) {fajlnev} feldolgozása közben", exc_info=True)
            
    return osszes_adat


if __name__ == "__main__":
    # Dinamikus tesztelés: parancssori argumentumokból olvassa be a fájlokat, 
    # így nem kell beégetni semmilyen fájlnevet.
    import sys
    
    teszt_fajlok = sys.argv[1:]
    
    if not teszt_fajlok:
        print("A futtatáshoz adj meg legalább egy fájlnevet argumentumként!")
        print("Példa: python modul.py konyv1.pdf konyv2.pdf")
    else:
        print("Fájlok importálása...")
        eredmenyek = import_tobb_fajl(teszt_fajlok)
        
        for i, adat in enumerate(eredmenyek, 1):
            print(f"\n{i}. könyv adatai:")
            print(adat)

def feldolgoz_es_importal(fajl_utvonalak, db):
    """
    Beolvassa a fájlokat, és közvetlenül az adatbázisba illeszti őket.
    Visszaadja a statisztikát és a hozzáadott címeit: (sikeres, hibas, duplikalt, hozzaadott_cimek).
    """
    importalt_konyvek = import_tobb_fajl(fajl_utvonalak)
    sikeres, hibas, duplikalt = 0, 0, 0
    hozzaadott_cimek = []

    for konyv in importalt_konyvek:
        cim = konyv.get("cim", "").strip()
        if not cim:
            hibas += 1
            continue
            
        if hasattr(db, 'is_duplikalat') and db.is_duplikalat(konyv):
            duplikalt += 1
        else:
            if hasattr(db, 'uj_konyv_hozzaadasa'):
                db.uj_konyv_hozzaadasa(konyv)
                sikeres += 1
                hozzaadott_cimek.append(cim)

    return sikeres, hibas, duplikalt, hozzaadott_cimek