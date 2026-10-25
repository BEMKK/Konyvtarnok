# Changelog

A projekten végrehajtott lényegi változtatások dokumentációja.



## [3.20.3] - 2026-10-25

- Javítva a statisztika ablak képernyőolvasóval való fókuszkezelési hibája ablakváltás után.
- Duplikációellenőrzés a főablakban könyv szerkesztése után.
- A Keresés a gyűjteményekben dialog találati listája a keresőmező ürítésével is törlődik, hasonlóan a KönyvTárnok-keresőhöz.
- Javítva a hibaüzenet hiánya sikertelen állományjegyzék export esetén.



## [3.20.2] - 2026-10-22

- Javítva a státuszsor felirata szűrt lista esetén.
- Javítva a szűrt lista frissítése az egyes találatok szűrési feltételének megváltoztatásakor.



## [3.20.1] - 2026-10-19

- A Dezideráta-kezelő alcím-mezője az állományhoz hasonlóan többsoros, az adatlap nézetben pedig ugyanúgy a vonal felett jelenik meg.



## [3.20.0] - 2026-10-19

- Alcím mező a Dezideráta kezelőben.
- Mezőnevek egységesítése és közös definiálása.



## [3.19.0] - 2026-10-18

- Eltávolítva a rövid cím mező.



## [3.18.0] - 2026-10-17

- Oszlopok kiválasztására szolgáló jelölőnégyzetek a Keresés dialogban.
- Csak teljes szóra való keresés lehetősége a KönyvTárnok-keresőben.
- A Keresés a gyűjteményekben dialog mostantól csak a megadott öt oszlopban keres, és támogatja az "és" szókapcsolatot.



## [3.17.0] - 2026-10-15

- A Ctrl+S mostantól a beállítások ablakban is használható a módosítások mentésére.
- Javítva a Keresés a gyűjteményekben dialogban egy hiba, mely miatt az érvénytelen json fájlok is betöltődtek.
- Kisebb hibajavítások.



## [3.16.1] - 2026-10-14

- Javítva a duplikált ctrl és alt billentyűparancsok a keresőkben.



## [3.16.0] - 2026-10-14

- Javítva a könyvrészletek és súgó esetén képernyőolvasóval, ablakváltás után tapasztalt fókuszálási hiba.
- A Dezideráta-kezelőben a kapható tételek adatlapján szereplő linkek mostantól nem kattintással, hanem az erre szolgáló gombbal nyithatók meg.
- A gomb csak akkor jelenik meg, ha van megadva URL.
- A keresés a gyűjteményekben dialogban módosítottuk az elemek tabulátor sorrendjét.
- A keresés törlése gomb a KönyvTárnok-keresőhöz hasonlóan alapértelmezetten tiltott.
- Új billentyűparancsok a keresés dialogban és a KönyvTárnok-keresőben.



## [3.15.1] - 2026-10-13

- Javítva a Keresés a gyűjteményekben dialog hibája pontos egyezés bejelölése esetén.
- A kereső dialog fókusza 0 találat esetén is a listára kerül.
- Javítások és frissítések a súgóban és a billentyűparancsok listájában.



## [3.15.0] - 2026-10-13

- Átalakított kereső párbeszédablak (KeresoDialog) saját találati listával és hatókör-választóval (Mindenhol, Dezideráta, Állományjegyzék).
- A keresőablak egyszerre és közösen képes keresni mind az állományban, mind a deziderátában anélkül, hogy a főablak listáját felülírná vagy leszűrné.
- A találatokból (ListCtrl) a kiválasztott tétel részletes olvasó adatlapja közvetlenül megnyitható (Enter vagy dupla kattintás).
- A kereső párbeszédablak mostantól a Dezideráta-kezelőből is elérhető (Ctrl+Shift+F).
- Sorok vágólapra másolása (Ctrl+C) a kereső találati listájában.



## [3.14.0] - 2026-10-12

- Javítva a frissítés ellenőrzés billentyűparancsa (ctrl+U).
- Tizenegy új téma a beállításokban (köztük a rendszer téma, mely egyéni beállítások nélkül az alapértelmezett.
- A témaválasztó görgetésekor a kijelölt téma előnézete megjelenik a beállítások ablakban.
- A Dezideráta kezelő listájának fókusza az új tétel és szerkesztő dialog-ok mégse gombbal való bezárása után a listára kerül.
- A főablak listájának fókusza átemelés után a KönyvTárnok-keresőből vagy Dezideráta-kezelőből átemelt tételre ugrik.
- A Dezideráta ablakának fókusza KönyvTárnok-keresőből való átemelés és annak visszavonása után sem ugrik vissza a lista elejére.



## [3.13.0] - 2026-10-11

- Forrás megjelenítése a KönyvTárnok-keresőben.
- Új témák (zsályazöld, szépia papír, sötétkék és kontrasztos fekete).
- Javítva a visszavonás utáni fókuszálási hiba.
- Javítva a Deziderátából való átemelés közben tapasztalt mikrofagyás.
- A Dezideráta-kezelő listafókusza átemelés után a következő tételre kerül.


## [3.12.0] - 2026-10-10

- Keresőmező ürítése gomb a főablak Kereső dialog-ban.
- A katalóguslap exportálásának billentyűparancsa mostantól Ctrl+K a főablakban és a Deziderátában egyaránt.
- A főablak Keresőablaka a Ctrl+Shift+F billentyűkombinációval érhető el.
- Kijelölés menüpont és gomb a KönyvTárnok-keresőben.
- Összes oszlop kijelölésére szolgáló jelölőnégyzet a KönyvTárnok-keresőben a kereséshez.
- Kijelölés törlése funkció mindhárom modulban.
- Javítások és kiegészítések a súgóban.



## [3.11.0] - 2026-10-09

- A főablakhoz hasonló UUID alapú azonosítás a Dezideráta-kezelőben.
- Új, szerkesztés menü a főablakban és a Dezideráta-kezelőben.
- Mostantól a Dezideráta-kezelő és az állomány listájának tételei is vágólapra másolhatók.
- Menüsor a KönyvTárnok-keresőben
- Visszavonás és mégis funkció a főablakban és a Dezideráta-kezelőben.



## [3.10.0] - 2026-10-08

- A főablak és a Dezideráta-kezelő menüjének átrendezése, egységesítése és javítása.



## [3.9.1] - 2026-10-07

- PDF fájlok tördelésének javítása.
- Javítva az oszlopszélességi hiba a Dezideráta-kezelő ablakában és katalóguslapján.
- Kisebb uix és kódjavítások.



## [3.9.0] - 2026-10-07

- Katalóguslap exportálása a Dezideráta-kezelőben.



## [3.8.1] - 2026-10-05

- Javítva a Katalóguslap mentési hibája.



## [3.8.0] - 2026-10-05

- Új funkció a katalóguslap exportálása.
- Hozzáadva a könyvadatlap exportálása funkció a könyv adatlapjához és a popup menühöz.



## [3.7.0] - 2026-10-04

- A KönyvTárnok-kereső mostantól támogatja az "és" szókapcsolatot, vagyis egy sor akkor is találat, ha a keresett kifejezés szavai több oszlopban szerepelnek.



## [3.6.0] - 2026-10-03

- A Deziderátában lévő találatok jelzése a KönyvTárnok-kereső státusz oszlopában.
- A KönyvTárnok-kereső mostantól nem a látható oszlopokból, hanem a sorok eredeti dict-jéből építi az átemelt adatokat.



## [3.5.0] - 2026-10-02

- Hozzáadva a másolás vágólapra és a keresés törlése gomb a KönyvTárnok-keresőhöz.



## [3.4.0] - 2026-10-01

- A KönyvTárnok-kereső találatainak átemelése immár a felületen lévő gombokkal is elvégezhető.



## [3.3.3] - 2026-09-30

- Indításkor, valamint rendezés, szűrés és keresésnél a főablak első tétele már nem kerül automatikusan fókuszba és kijelölésre, a fókusz a lista első nyílbillentyű-lenyomásakor jelenik meg.



## [3.3.2] - 2026-09-29

- Kisebb uix javítások és finomítások.



## [3.3.1] - 2026-09-29

- Javítva a rádiógombok és jelölőnégyzetek akadálymentes felolvasásának hibája.



## [3.3.0] - 2026-09-29

- Javítva a frissítés letöltése után jelentkező ideiglenes mappa törlésének ütközése.
- Javítva a frissítést jelző párbeszédablak gombjainak feliratai.
- Eltávolítva a Dezideráta-kezelő Tétel részletei gomb az eszköztárról és menüpont a felső menüsorból.



## [3.2.1] - 2026-09-28

- Javítva a kezdőbetűvel való gyorskeresés pufferelési hibája.



## [3.2.0] - 2026-09-27

- A program mostantól képes letölteni az új verziót, és felülírni vele a régit.



## [3.1.2] - 2026-09-26

- Javítva a listafrissítés hibája a Dezideráta-kezelőben, mely akkor jelentkezett, ha a könyv szerkesztése dialog az adatlapról lett megnyitva.
- Javítva a statisztika kereszttáblás jelentése, mely eddig nem tartalmazta az elsődleges szempont értékét.
- Javítva a frissítés keresésekor felugró hibaüzenet internetkapcsolat hiánya esetén.
- Javítva a téma alkalmazása a beállítások ablak görgetésekor.
- Újabb kódrefaktorálás és javítások.



## [3.1.1] - 2026-09-25

- Javítva a listafrissítés hibája, mely akkor jelentkezett, ha a könyv szerkesztése dialog a könyvadatlapról lett megnyitva.
- Újabb kódrefaktorálás és javítások.



## [3.1.0] - 2026-09-22

- Új, áttekintés fül a súgóban, mely általános leírást ad az alkalmazásról és annak főbb funkcióiról, kezeléséről.



## \[3.0.1] - 2026-09-21

* Javítva az ikon hiánya a Névjegy-ablakban.
* Gépelési hibák javítása a súgóban.
* Javítva a kimásolt hibaüzenetek törlődése a vágólapról a program bezárásakor.
* Újabb kódszintű javítások (duplikációk, inkonzisztenciák megszüntetése, stb.)



## \[3.0.0] - 2026-09-21

* Megszűnt a v1.x verzióval titkosított JSON fájlok támogatása.
* Hozzáadva a jobbklikkes felugró menü a Dezideráta-kezelőhöz.
* Javítások a súgóban és a kódban.



## \[2.1.1] - 2026-09-20

* Újabb kódjavítások és refaktorálás



## \[2.1.0] - 2026-09-19

* Mostantól lehetőség van a hibanapló megnyitására vagy másolására közvetlenül a felugró ablakból.
* Javítások a Deziderátából és KönyvTárnok-keresőből való átemelés folyamatában.
* Kisebb kódjavítások és refaktorálás.



## \[2.0.0] - 2026-09-19

* Fernet-titkosítás kivezetése az adatbázis-fájlok hordozhatósága érdekében. A JSON fájlokat mostantól HMAC-SHA256 alapú adatintegritásvédelem védi.



## \[1.0.0] - 2026-09-18

* Első stabil verzió!
* A könyvadatlapok pdf fájlból történő importálása mostantól nem támogatott.



## \[0.24.0] - 2026-09-17

* Kisebb kódjavítások.



## \[0.23.8] - 2026-09-17

* Felugró ablak hozzáadása sikertelen JSON betöltés esetén.
* JSON importálása esetén a főprogramban, ha már vannak könyvek a listában, csak a hiányzó kötetek kerülnek felvételre.
* A súgó bővítve az új funkció leírásával."



## \[0.23.7] - 2026-09-16

* Javítva az állománystatisztikai jelentésben a találatok rendezésének hibája.
* Javítva a szűrés viselkedése új könyv hozzáadása, importálása és törlése esetén.
* Újabb kódjavítások.



## \[0.23.6] - 2026-09-14

* Javítva a fájlütközés-dialog hibája, mely bezáráskor automatikusan felülírt minden fájlt.
* Javítva az 1900-as évek toldalékolási hibája az állománystatisztikában.
* Újabb kódjavítások.



## \[0.23.5] - 2026-09-14

* Javítva a frissítési gyakoriság beállításának hibája.
* Javítva a 2000-es évek toldalékolási hibája az állománystatisztikában.



## \[0.23.4] - 2026-09-13

* Javítások a súgóban és a menüben.



## \[0.23.3] - 2026-09-12

* Súgó és GUI szövegek javítása.



## \[0.23.2] - 2026-09-11

* Hozzáadva a referencia-adatbázisban lévő kötetek számát mutató status-bar a KönyvTárnok-keresőhöz.



## \[0.23.1] - 2026-09-09

* Javítva a JSON fájlok alapértelmezett mentési és betöltési útvonalának hibája a Dezideráta-kezelőben.



## \[0.23.0] - 2026-09-09

* Hozzáadva a frissítés keresése funkció.
* Javítva a kezdőbetűvel való keresés hibája, mely hosszú magánhangzóval kezdődő cím hiánya esetén, hosszú magánhangzóra annak rövid párjára ugrott.



## \[0.22.2] - 2026-09-08

* Jelentősen kibővítve a súgó és a billentyűparancsok listája.
* A Dezideráta-kezelőből eltávolítva a Ctrl+R billentyűparancs, a tétel részletei dialog immár kizárólag enterrel vagy dupla kattintással nyitható meg.



## \[0.22.1] - 2026-09-06

* Javítva a right click menü billentyűzetes előhívása.



## \[0.22.0] - 2026-09-05

* A KönyvTárnok kereső excel helyett mostantól json-t kezel.



## \[0.21.0] - 2026-09-03

* Az alkalmazás és moduljai új nevet kaptak.



\[0.20.0] - 2026-08-30

* Hozzáadva a súgó funkció, mely az Újdonságok és Névjegy menüponttal együtt a Súgó menüből érhető el.



## \[0.19.0] - 2026-08-26

* Hozzáadva az állománystatisztika kereszttáblás szűrése, valamint a beállításokhoz a statisztikai jelentés exportálási célmappájának megadása.
* A főmenüből végzett listarendezés mostantól csak ideiglenes, alapértelmezett rendezés a beállításokban választható.



## \[0.18.0] - 2026-08-24

* Hozzáadva az állománystatisztika és elérési utak manuális megadása.
* Módosítva a rendezés menü szempontjai, a lista cím, összeállító, kiadó, kiadás éve, oldalszám, méret és bekerülés dátuma szerint rendezhető.



## \[0.17.0] - 2026-08-21

* Új az élő keresősáv a könyvlista azonnali szűrésére.



## \[0.16.0] - 2026-08-18

* Új funkció a felület témájának testreszabása, a világos mellett sötét, kék és rózsaszín téma választható.



## \[0.15.0] - 2026-08-15

* Hozzáadva a kereső dialog az állomány köteteinek keresésére és szűrésére.



## \[0.14.0] - 2026-08-14

* Hozzáadva a beállítások dialog a fő lista megjelenítendő oszlopainak testreszabására.



## \[0.13.0] - 2026-08-11

* Hozzáadva a lista rendezésének lehetősége a főmenüből cím, szerző, kiadó, kiadás helye, kiadás éve és státusz szerint.



## \[0.12.0] - 2026-08-09

* Hozzáadva az "Egyéb személyek" oszlop a Könyvtárnok keresőhöz.



## \[0.11.0] - 2026-08-06

* Eltávolítva az rtf fájlok importálásának lehetősége.
* A főprogram és a dezideráta kezelő mostantól titkosítva tárolja az adatokat a json-ban a külső módosítás elkerülése érdekében.



## \[0.10.0] - 2026-08-05

* Hozzáadva a KönyvTárnok kereső a könyvek külső adatbázisból való felvételére és adataik keresésére.



## \[0.9.0] - 2026-08-03

* Hozzáadva a Dezideráta-kezelő a beszerezni kívánt kötetek kezelésére.



## \[0.8.0] - 2026-08-01

* Hozzáadva a json fájlok mentésének és betöltésének lehetősége.



## \[0.7.0] - 2026-07-29

* Hozzáadva az Újdonságok dialog az aktuális verzió változtatásainak megjelenítésére.



## \[0.6.0] - 2026-07-28

* Hozzáadva a könyvadatlapok exportálásának lehetősége pdf formátumba.



## \[0.5.0] - 2026-07-26

* Megjelent a pdf és rtf fájlok importálási lehetősége.



## \[0.4.0] - 2026-07-24

* Gombsor a lista felett új könyv hozzáadására, kijelölt könyv szerkesztésére és törlésére.



## \[0.3.0] - 2026-07-22

* Kijelölt könyv adatlapjának megtekintésének lehetősége enterrel, annak szerkesztése nélkül.



## \[0.2.0] - 2026-07-20

* Több könyv kijelölésének és egyidejű eltávolításának lehetősége.



## \[0.1.0] - 2026-07-19

* Új, egypaneles nézet. A teljes ablakot a könyvek listája foglalja el.



## \[0.0.1] - 2026-07-18

* Alapverzió.

