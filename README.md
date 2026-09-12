# KönyvTárnok

> **Verzió:** 0.23.3 Béta

## Leírás

A **KönyvTárnok** egy asztali alkalmazás könyvgyűjtemények nyilvántartására és kezelésére. A program a `wxPython` grafikus felületet használja, és a háttérben **Fernet szimmetrikus titkosítással** védett JSON‑alapú adatbázist kezel. Az alkalmazás elsősorban **Windows** környezetre készült.

## A program főbb funkciói

- **Könyvállomány kezelése** – könyvek felvétele, szerkesztése, megtekintése és törlése (egyedi és tömeges kijelöléssel).
- **Titkosított adatbázis** – az állományjegyzék (`allomanyjegyzek.json`) Fernet‑titkosítással védett; a kulcs a felhasználó mappájában tárolódik (`~/.konyvtar_app/secret.key`).
- **Import / Export** – könyvadatlapok importálása PDF fájlokból (`pdfplumber`) és exportálása PDF formátumba (`reportlab`), egyedi és kötegelt módban.
- **Állományjegyzék mentése / betöltése** – a teljes katalógus titkosítás nélküli JSON fájlba menthető és visszatölthető.
- **Dezideráta‑kezelő** – beszerzésre javasolt könyvek kívánságlistájának kezelése, saját titkosított adatbázissal (`deziderata.json`), átemelési lehetőséggel a fő állományba.
- **KönyvTárnok kereső** – külső referencia‑adatbázis (`Enekeskonyvek_adatai.xlsx`) keresése és összevetése a saját állománnyal; a találatok közvetlenül felvehetők a katalógusba vagy a dezideráta‑jegyzékbe.
- **Állománystatisztika** – részletes eloszlások, hiányzó adatok vizsgálata, kereszttáblás elemzés PDF exporttal.
- **Keresés és szűrés** – valós idejű kereső, részletes szűrés pontos egyezéssel, gépeléses gyorskeresés a listában.
- **Rendezés** – magyar ábécé szerinti rendezés (ékezetkezeléssel, római szám‑felismeréssel), többféle szempont szerint (cím, szerző, kiadó, év, oldalszám, méret, bekerülés dátuma).
- **Testreszabható megjelenés** – 4 beépített színtéma: Világos, Sötét, Pasztell kék, Rózsaszín.
- **Gyorsbillentyűk** – teljes billentyűzetes kezelhetőség (Ctrl+N, Ctrl+E, Delete, Ctrl+F, Ctrl+K, Ctrl+D, Ctrl+T stb.).
- **Kivételkezelés naplózással** – nem kezelt hiba esetén a részletek a `hibanaplo.log` fájlba kerülnek, és felugró ablakban értesíti a felhasználót.

## Telepítés

1. A program fejlesztéséhez és futtatásához **Python 3.10+** telepítése szükséges.
2. Telepítsd a függőségeket a QickInstallRequirements script futtatásával, vagy az alábbi paranccsal a projekt gyökerében:
   ```bash
   pip install -r requirements.txt
   ```
3. A projekt futtatható közvetlenül a forráskódból, vagy egyetlen hordozható `.exe` fájlként, `PyInstaller`‑rel csomagolva.

## Használat

Futtasd az alábbi parancsot a program forráskódjának mappájában, vagy kattints duplán a main.py, vagy a futtatas.bat fájlra:
```bash
python main.py
```

### Parancsfájlok

- `Futtatas.bat` – egyszerű indító script a forráskód futtatásához.
- `exe-port.bat` – PyInstaller build parancs, amely egyetlen hordozható `.exe` állományt épít az alkalmazás ikonjával és a referencia adatbázissal beágyazva.
- `QuickInstallRequirements.bat` – A függőségek gyors telepítésére.

## Függőségek

| Csomag | Verzió | Funkció |
|--------|--------|---------|
| `wxpython` | 4.2.5 | Grafikus felület (GUI keretrendszer) |
| `cryptography` | 50.0.0 | Adatbázis és dezideráta Fernet‑titkosítása |
| `reportlab` | 5.0.0 | PDF adatlapok és statisztikai jelentések generálása |
| `pdfplumber` | 0.11.10 | PDF könyvadatlapok beolvasása és importálása |

## Projektstruktúra

```
.
├─ README.md                   # Jelen dokumentáció
├─ requirements.txt            # Python függőségek
├─ main.py                     # Belépési pont – alkalmazásindítás, hibakezelő
├─ main_frame.py               # Főablak (eszközsáv, keresés, lista, állapotsor)
├─ menu_bar.py                 # Menüsor (Fájl, Rendezés, Eszközök)
├─ data_manager.py             # Titkosított adatbázis‑kezelő (KonyvAdatbazis)
├─ export_manager.py           # PDF export (egyedi, kötegelt, statisztika)
├─ import_manager.py           # PDF import (kulcsszó-alapú szövegfelismerés)
├─ config_manager.py           # Konfigurációkezelő (settings.json)
├─ theme_manager.py            # Téma‑kezelő (4 beépített színtéma)
├─ dialogs.py                  # Párbeszédablakok (szerkesztő, statisztika, keresés, beállítások, névjegy stb.)
├─ help.py              # Súgó és billentyűparancsok
├─ konyv_lista.py              # Virtuális könyvlista UI (rendezés, gyorskeresés)
├─ konyvtarnok_kereso.py                # KönyvTárnok kereső – külső referencia‑adatbázis kereső és átemelő modul
├─ deziderata.py               # Dezideráta‑kezelő – beszerzési kívánságlista modul
├─ update.py                   # Új verzió ellenőrzése a GitHub-on.
├─ sablon.py                   # PDF export sablongenerátor (bibliográfiai adatlap formázása)
├─ constants.py                # Alkalmazás‑állandók (név, verzió, állapot)
├─ ikon.ico                    # Alkalmazásikon
├─ Enekeskonyvek_adatai.json   # KönyvTárnok kereső referencia‑adatbázisa
├─ Futtatas.bat                # Indító script
├─ exe-port.bat         # PyInstaller build script
├─ QuickInstallRequirements.bat         # A függőségek gyors telepítésére.
├─ converter/excel_to_json.exe         # Excel fájlok JSON-ra történő gyors átalakítására szolgáló segédprogram.
├─ converter/excel_to_json.py         # A segédprogram forráskódja.
├─ converter/build.py         # Az excel-konvertáló pyinstaller fordítására szolgáló script.
```

## Tesztelés

A projekt jelenleg nincs automatizált tesztkerettel ellátva, de a következőképpen ellenőrizheted a funkciókat:

1. Futtasd a `main.py`‑t.
2. Vegyél fel új könyvet, szerkeszd, majd töröld.
3. Próbáld ki a PDF importot és exportot (Fájl menü → Könyvadatlapok importálása / exportálása).
4. Nyisd meg a KönyvTárnok keresőt (Eszközök → Keresés az adatbázisban) és keress a referencia‑adatbázisban.
5. Nyisd meg a Dezideráta‑kezelőt (Eszközök → Dezideráta‑kezelő).
6. Ellenőrizd, hogy a `hibanaplo.log` akkor jön létre, amikor nem kezelt hiba történik.

## Hozzájárulás

1. Forkold a repót.
2. Hozz létre egy új ágat (`git checkout -b feature/új-funkció`).
3. Készíts változtatásokat, majd nyújts be `pull request`‑et.
4. A referencia-adatbázis bővítéséhez bővítsd az excel fájlt a projekt Convert mappájában, majd a mellékelt segédprogrammal alakítsd json fájllá, és tedd a program gyökérmappájába.

## A projektről

Ez a projekt egy vibecoding kísérlet eredménye: a teljes alkalmazás kódját látássérültként, AI segítségével hoztam létre, fejlesztői előképzettség nélkül. A fejlesztés során a feladatom a funkciók megtervezése, az architektúra kijelölése, az AI-val való iteratív közös munka (promptolás), valamint a felület és a hibák tesztelése volt.

---

*Ez a README a projekt aktuális állapotát tükrözi (v0.23.3 Béta), és a fejlesztés előrehaladtával frissíthető.*
