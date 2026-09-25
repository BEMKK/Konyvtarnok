# KönyvTárnok

> **Verzió:** 3.1.1

## Leírás

A **KönyvTárnok** egy akadálymentes asztali alkalmazás könyvgyűjtemények nyilvántartására és kezelésére. A program a `wxPython` grafikus felületet használja, az adatokat pedig Hmac integritásvédelemmel ellátott JSON‑alapú adatbázisokban tárolja. Az alkalmazás elsősorban **Windows** környezetre készült.

## A program főbb funkciói

- **Könyvállomány kezelése** – könyvek felvétele, szerkesztése, megtekintése és törlése.
- **Védett adatbázis** – az állományjegyzék (`allomanyjegyzek.json`) és a dezideráta-jegyzék (`deziderata.json`) Hmac adatintegritásvédelemmel van ellátva.
- **PDF-export** – könyvadatlapok exportálása PDF formátumba (`reportlab`), egyedi és kötegelt módban.
- **Állományjegyzék mentése / betöltése** – a teljes katalógus védelem nélküli JSON fájlba menthető és visszatölthető.
- **Dezideráta‑kezelő** – beszerezni kívánt könyvek listájának kezelése, átemelési lehetőséggel a fő állományba.
- **KönyvTárnok kereső** – egy külső referencia‑adatbázisban (`Enekeskonyvek_adatai.json`) keres, a találatok közvetlenül felvehetők az állományba vagy a dezideráta‑jegyzékbe.
- **Állománystatisztika** – részletes eloszlások, hiányzó adatok vizsgálata, kereszttáblás elemzés PDF exporttal.
- **Keresés és szűrés** – valós idejű kereső, részletes szűrés pontos egyezéssel, gépeléses gyorskeresés a listában.
- **Rendezés** – az állomány magyar ábécé szerinti rendezése többféle szempont szerint: cím, szerző, kiadó, év, oldalszám, méret, bekerülés dátuma.
- **Testreszabható megjelenés** – négy beépített színtéma: Világos, Sötét, Pasztell kék, Rózsaszín, valamint a listában megjelenő oszlopok elrejtése vagy megjelenítése.
- **Gyorsbillentyűk** – teljes billentyűzetes kezelhetőség (lásd a súgóban a billentyűparancsok listáját).
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
| `reportlab` | 5.0.0 | PDF adatlapok és statisztikai jelentések generálása |

## Projektstruktúra

```
.
├─ README.md                   # Jelen dokumentáció
├─ requirements.txt            # Python függőségek
├─ main.py                     # Belépési pont – alkalmazásindítás, hibakezelő
├─ main_frame.py               # Főablak (eszközsáv, keresés, lista, állapotsor)
├─ menu_bar.py                 # Menüsor (Fájl, Rendezés, Eszközök)
├─ data_manager.py             # Adatbázis‑kezelő (KonyvAdatbazis)
├─ export_manager.py           # PDF export (egyedi, kötegelt, statisztika)
├─ config_manager.py           # Konfigurációkezelő (settings.json)
├─ theme_manager.py            # Téma‑kezelő (4 beépített színtéma)
├─ dialogs.py                  # Névjegy, újdonságok és fájlütközés párbeszédablak.
├─ konyvdialogs.py                  # Könyv szerkesztése és adatlap megjelenítő párbeszédablakok.
├─ settings.py                  # Beállítások ablak.
├─ kereso.py                  # Keresés és szűrés dialog.
├─ statisztika.py                  # Állománystatisztika párbeszédablak.
├─ help.py              # Súgó és billentyűparancsok
├─ konyv_lista.py              # Virtuális könyvlista UI (rendezés, gyorskeresés)
├─ konyvtarnok_kereso.py                # KönyvTárnok kereső – külső referencia‑adatbázis kereső és átemelő modul
├─ deziderata.py               # Dezideráta‑kezelő – beszerzési kívánságlista modul
├─ update.py                   # Új verzió ellenőrzése a GitHub-on.
├─ constants.py                # Alkalmazás‑állandók (név, verzió, állapot, alapértelmezett oszlopok, stb.)
├─ gyors_kereses.py                # A lista gépelés közbeni szűrése mindhárom modulban
├─ utils.py                # Rendezési és állománystatisztikai segédfügvények
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
3. Próbáld ki a PDF exportot (Fájl menü → Könyvadatlapok exportálása).
4. Nyisd meg a KönyvTárnok keresőt (Eszközök → KönyvTárnok-kereső) és keress a referencia‑adatbázisban.
5. Nyisd meg a Dezideráta‑kezelőt (Eszközök → Dezideráta‑kezelő).
6. Ellenőrizd, hogy a `hibanaplo.log` akkor jön létre, amikor nem kezelt hiba történik.

## Hozzájárulás

1. Forkold a repót.
2. Hozz létre egy új ágat (`git checkout -b feature/új-funkció`).
3. Készíts változtatásokat, majd nyújts be `pull request`‑et.
4. A referencia-adatbázis bővítéséhez bővítsd az excel fájlt a projekt Convert mappájában, majd a mellékelt segédprogrammal alakítsd json fájllá, és tedd a program gyökérmappájába. **Figyelem!** Az excel_to_json konvertáló használatához Openpyxl telepítése szükséges!

## A projektről

Ez a projekt egy vibecoding kísérlet eredménye: a teljes alkalmazás kódját látássérültként, AI segítségével hoztam létre, fejlesztői előképzettség nélkül. A fejlesztés során a feladatom a funkciók megtervezése, az architektúra kijelölése, az AI-val való iteratív közös munka (promptolás), valamint a felület és a hibák tesztelése volt.

---

*Ez a README a projekt aktuális állapotát tükrözi (v3.1.1), és a fejlesztés előrehaladtával frissíthető.*
