import wx
from theme_manager import apply_theme_from_settings

class HelpNotebookDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent, 
            title="Súgó és használati útmutató", 
            size=(750, 550),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self.init_ui()
        self.CentreOnParent()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(self)

        pages_data = [
            (
                "Áttekintés",
                "AZ ALKALMAZÁS ÁTTEKINTÉSE ÉS FŐBB FUNKCIÓI\n\n"
                "1. Főablak:\n"
                "  A program megnyitásakor az alkalmazás főablaka jelenik meg, melyben a fő könyvállományt, vagyis a jelenleg birtokában lévő kötetek listáját láthatja és kezelheti.\n\n"
                "2. Eszköztár és státuszsor:\n"
                "  A főablakban és a dezideráta-kezelőben egyaránt megtalálható a lista feletti eszköztár, melynek gombjai a könyvekkel való műveletek (hozzáadás, szerkesztés, törlés) gyors elvégzésére szolgálnak. A jobb oldalon látható Szűrés törlése gomb alapértelmezetten le van tiltva mindaddig, amíg kereséssel vagy statisztikából nem szűri a listát. Az ablak alsó részén lévő státuszsor az állományban, illetve dezideráta-jegyzékben lévő kötetek számát mutatja.\n\n"
                "3. Menüsor:\n"
                "  A főablakban és a Dezideráta-kezelőben is található egy felső menüsor. A főablakban a fájl menüből indíthatók a könyv- és fájlműveletek (új könyv hozzáadása, könyv szerkesztése, törlése, pdf adatlap exportálása, JSON mentése/betöltése). A rendezés menüből rendezheti a listát cím, szerző, kiadó, kiadás helye és éve, méret, valamint bekerülés dátuma és oldalszám szerint. Az eszközök menüben találja a Dezideráta-kezelő, a KönyvTárnok-kereső és a Keresés a gyűjteményekben dialog menüpontokat, valamint az állománystatisztikát és a beállításokat. A súgó menüből az alkalmazás súgóját, névjegyét, a frissítések ellenőrzését, valamint a használt verzió újdonságainak listáját érheti el.\n\n"
                "4. Dezideráta-kezelő:\n"
                "  A Dezideráta-kezelőben a beszerezni kívánt könyvek listáját vezetheti. Az alapvető bibliográfiai adatok mellett megadhatja a tétel prioritását (elsődleges vagy másodlagos), valamint státuszát (jelenleg kapható/jelenleg nem kapható). Kapható státusz esetén lehetősége van megadni a tétel lelőhelyét, jelenlegi vagy becsült árát és esetleges linkjét is.\n\n"
                "5. KönyvTárnok-kereső:\n"
                "  A KönyvTárnok-keresővel tetszőleges, felhasználó által megnyitott JSON adatbázisban kereshet, a találatokat pedig lehetősége van átemelni az állományba vagy a deziderátába, illetve vágólapra másolni.\n"
            ),
            (
                "Állománykezelés",
                "MŰVELETEK KÖNYVEKKEL\n\n"
                "1. Új könyv felvétele:\n"
                "  Új könyv felvételéhez kattintson az 'Új könyv' gombra a lista feletti eszköztárban, nyomja meg a Ctrl + N billentyűkombinációt, vagy válassza a Fájl menü Új könyv felvétele menüpontját. A megnyíló ablakban töltse ki a könyv adatait (Cím, Alcím, Összeállító, Egyéb személyek, Kiadó, Kiadás helye és éve, Oldalszám, Méret, Kötés típusa, Bekerülés dátuma, Példány forrása, Státusz és Rövid leírás). A mentéshez kattintson a Mentés gombra vagy nyomja meg a Ctrl + S billentyűket. Fontos: a könyv címét minden esetben kötelező kitölteni!\n\n"
                "2. Könyv megtekintése és szerkesztése:\n"
                "  A listában lévő könyv részletes adatlapjának megtekintéséhez nyomja meg az Enter billentyűt a kijelölt elemen, kattintson rá duplán, vagy válassza a helyi menü 'Könyvadatlap megtekintése' pontját. A könyv adatainak módosításához kattintson a 'Kijelölt könyv szerkesztése' gombra, nyomja meg a Ctrl + E billentyűkombinációt, vagy válassza a Fájl -> Könyv szerkesztése menüpontot. Ha végzett a könyv adatainak szerkesztésével, kattintson a Mentés gombra, vagy nyomja meg a Ctrl+S billentyűkombinációt.\n\n"
                "3. Könyvek eltávolítása:\n"
                "  Egy vagy több könyv állományból való törléséhez jelölje ki a kívánt tételeket a listában, majd nyomja meg a Delete billentyűt, kattintson a 'Kijelöltek törlése' gombra, vagy válassza a Fájl -> Könyv(ek) eltávolítása menüpontot. A rendszer a törlés előtt megerősítést kér.\n\n"
                "4. Összes elem kijelölése:\n"
                "  A főlista összes kötetének egyidejű kijelöléséhez nyomja meg a Ctrl + A billentyűkombinációt.\n\n"
                "5. Másolás a vágólapra:\n"
                "  A lista kijelölt elemeit vágólapra másolhatja tabulátorral elválasztott szövegként, hasonlóan a KönyvTárnok-keresőhöz.\nA kijelölt elemek másolásához használja a Szerkesztés menü Másolás menüpontját, vagy nyomja meg a Ctrl + C billentyűparancsot.\n\n"
                "6. Gyorskeresés a listában:\n"
                "  Amikor a könyvlista fókuszban van, a kezdőbetű vagy szótag begépelésével is kijelölheti a kívánt kötetet.\n\n"
                "7. Visszavonás és ismétlés:\n"
                "  A legutóbbi művelet visszavonásához használja a Szerkesztés menü Visszavonás parancsát, vagy a Ctrl+Z billentyűparancsot.\nA művelet ismételt végrehajtásához válassza a menü Mégis menüpontját, vagy használja a Ctrl+Y billentyűket.\n"
            ),
            (
                "Keresés és statisztika",
                "KERESÉS, SZŰRÉS, RENDEZÉS ÉS ÁLLOMÁNYSTATISZTIKA\n\n"
                "1. Élő keresősáv a főablakban:\n"
                "  A főablak felső részén található keresőmezővel (Ctrl + F) gépelés közben azonnal szűrheti az állományt. A rendszer a könyvek minden adatmezőjében (cím, szerző, kiadó, év stb.) keres.\n\n"
                "2. Keresés a gyűjteményekben (összesített kereső):\n"
                "  Az Eszközök -> Keresés a gyűjteményekben menüponttal vagy a Ctrl + Shift + F billentyűkombinációval megnyitható keresőablakban (mely a Dezideráta-kezelőből is elérhető) közösen kereshet az állományban és a deziderátában. A keresőablak felső részén először a beállítások találhatók: a Keresés helye lenyíló lista (Mindenhol, Dezideráta, Állomány) és a Csak pontos egyezés jelölőnégyzet. Alattuk áll a keresett kifejezés mezője a Keresés törlése és a Keresés gombbal. A keresést a Keresés gombbal vagy a kifejezés mezőben leütött Entert kezdeményezheti. A Keresés törlése gomb alapértelmezetten le van tiltva, és csak akkor érhető el, ha a mezőben szöveg van, vagy a listában található találat. Megnyomásával a mező és a találati lista is kiürül, a fókusz pedig a keresőmezőre kerül. Az ablak megnyitásakor a fókusz a keresett kifejezés mezőjén áll. A Tab billentyűvel a következő sorrendben haladhat végig a vezérlőkön: Keresés helye, Csak pontos egyezés, Keresett kifejezés, Keresés törlése, Keresés, Találati lista, Részletek, Bezárás. Keresés után a fókusz a találati listára kerül. Ha nincs találat, a fókusz a keresőmezőben marad, így azonnal módosíthatja a kifejezést. A találati listából a kívánt tételre duplán kattintva, az Entert lenyomva vagy a Részletek gombot használva azonnal megtekintheti annak részletes adatlapját anélkül, hogy a főablak listáját felülírná. A kijelölt találat adatait a Ctrl + C billentyűparancs másolja a vágólapra. A vezérlők Alt billentyűs gyorsbillentyűkkel is elérhetők (Alt + H, Alt + P, Alt + K, Alt + T, Alt + R, Alt + Z, Alt + B), a felirataikban az aláhúzott betű jelzi őket. A teljes lista a Billentyűparancsok fülön található.\n\n"
                "3. Szűrés törlése:\n"
                "  Aktív szűrés vagy keresés esetén a lista feletti 'Szűrés törlése' gomb aktívvá válik, rákattintva visszaállíthatja a teljes könyvállomány megjelenítését.\n\n"
                "4. Állománystatisztika készítése:\n"
                "  Az Eszközök -> Állománystatisztika menüpontban (Ctrl + T) részletes kimutatásokat készíthet az állományról. Kiválaszthatja a statisztika alapját (pl. Kiadó, Kiadás éve, Kiadás évszázada, Kiadás évtizede, Kötés típusa, Példány forrása, Státusz stb.), majd szűrhet egy adott értékre vagy a hiányzó adatokra (\"Nincs kitöltve\"). A találatokat lehetősége van cím, szűrési szempont vagy az állomány aktuális rendezési szempontja szerint rendezni, valamint azokra fő listát leszűrni.\n\n"
                "5. Állomány rendezése:\n"
                "  A Nézet menü Rendezés menüpontjában vagy az Alt billentyűparancsokkal (lásd a billentyűparancsok listáját) tetszőlegesen sorba rendezheti a könyveket.\n"
            ),
                (
                "Adatmentés",
                "PDF ÉS JSON FÁJLOK KEZELÉSE\n\n"
                "1. Könyvadatlap exportálása PDF fájlba:\n"
                "  A kijelölt könyv(ek)ről nyomtatható PDF adatlapot generálhat a Fájl -> Könyvadatlap(ok) exportálása PDF-ként... menüpontban vagy a Ctrl + Shift + E billentyűkombinációval. Egyetlen könyv esetén egyedi fájlnevet adhat meg, több könyv kijelölése esetén pedig egy kiválasztott mappába tömegesen exportálhatja az adatlapokat. A program alapértelmezetten a könyv címét és kiadásának évét használja a pdf fájlneveként egyedi és tömeges exportnál is. Ha a könyv kiadási éve nincs kitöltve, a zárójelben a \"nincs_ev_megadva\" felirat szerepel.\n\n"
                "2. Állományjegyzék mentése JSON-ba (Biztonsági mentés):\n"
                "  A teljes állományjegyzék exportálható szerkeszthető, SHA integritásvédelem nélküli JSON fájlba a Fájl -> Állományjegyzék mentése JSON fájlba... menüpontban (Ctrl + Shift + M). Ez kiválóan alkalmas biztonsági mentésre. A JSON fájl alapértelmezetten az \"allomanyjegyzek.json\" nevet kapja.\n\n"
                "3. Állományjegyzék betöltése JSON-ból:\n"
                "  Egy korábban exportált (nyers, HMAC-védelem nélküli) JSON fájl importálásához használja a Fájl -> Állományjegyzék betöltése JSON fájlból... menüpontot (Ctrl + Shift + B). Az importálás előtt a program elemzi a fájlt: egy választó párbeszédablakban megjeleníti az új könyveket és a meglévő könyvek kiegészíthető adatait, amelyekből tetszőlegesen kiválaszthatja, mit szeretne importálni. A program mappájába, tehát a futtatható (exe) fájl mellé helyezett nyers JSON fájlok a program megnyitásakor nem kerülnek beolvasásra.\n\n"
                "4. Katalóguslap mentése PDF fájlba:\n"
                "  A program főablakában megjelenő listát a látható oszlopokkal PDF fájlba mentheti.\nEhhez kattintson az eszköztár Katalógus export gombjára, vagy a menüből válassza a Katalóguslap mentése pdf-be lehetőséget.\nHasználhatja a Ctrl + K billentyűparancsot is.\nHa nagyon sok oszlop van a listában, a program automatikusan csökkenti a PDF betűméretét.\n"
            ),
                        (
                "Dezideráta-kezelő",
                "A DEZIDERÁTA-KEZELŐ HASZNÁLATA\n\n"
                "1. A Dezideráta-kezelő megnyitása:\n"
                "  A beszerzendő vagy hiányzó könyvek nyilvántartására szolgáló modult az Eszközök -> Dezideráta-kezelő menüpontból vagy a Ctrl + D billentyűkombinációval nyithatja meg.\n\n"
                "2. Új tétel hozzáadása:\n"
                "  Új beszerzendő könyv felvételéhez nyomja meg az 'Új tétel' gombot vagy a Ctrl + N billentyűket. A megnyíló ablakban töltse ki a könyv adatait. Az alapadatok (cím, összeállító, egyéb személyek, kiadó, kiadás helye és éve) mellett megadhatja a tétel prioritását, státuszát (kapható/nem kapható). Kapható státusz esetén megjelenik három további mező, ahol a megvásárolható tétel lelőhelyét, jelenlegi vagy becsült árát és webes hivatkozását (link) is rögzítheti. Ha a könyv státuszát Nem kapható-ra állítja, az utóbbi három mező eltűnik, és tartalmuk törlődik a könyv adatlapjáról. Amikor végzett az adatok kitöltésével, kattintson a Mentés gombra, vagy nyomja meg a Ctrl+S billentyűt.\n\n"
                "3. Tételek megtekintése és szerkesztése:\n"
                "  A kijelölt tétel részleteit az Enter billentyűvel vagy dupla kattintással tekintheti meg. Ha a tétel kapható, és van megadva link, megjelenik a link megnyitására szolgáló gomb. A gombra kattintva a program megnyitja a megadott linket az alapértelmezett böngészőben.\nTétel szerkesztéséhez használja a 'Kijelölt tétel szerkesztése' gombot vagy a Ctrl + E billentyűparancsot. Az adatok módosítása után kattintson a Mentés gombra, vagy nyomja meg a Ctrl+S billentyűt.\n\n"
                "4. Tételek törlése:\n"
                "  A már nem kívánt tételeket a Delete billentyűvel vagy a törlés gombbal távolíthatja el.\n\n"
                "5. Tétel felvétele a fő könyvállományba:\n"
                "  Ha egy beszerzendő könyvet sikerült megvásárolni/megszerezni, a kijelölt tételt a Ctrl + F billentyűkombinációval vagy a 'Felvétel az állományba' gombbal közvetlenül átemelheti a fő katalógusba. Átemeléskor a program megkérdezi, hogy biztosan át szeretné e emelni a tételt. Amennyiben ezt szeretné, kattintson az Igen gombra.\n\n"
                "6. Dezideráta adatok mentése és betöltése:\n"
                "  A dezideráta jegyzék exportálható szerkeszthető, azaz SHA integritásvédelem nélküli JSON fájlba (Ctrl + Shift + M) és bármikor visszatölthető (Ctrl + Shift + B) a Tételek menüből. JSON fájl betöltése esetén a program elemzi az importált fájlt: a választó párbeszédablakban megjeleníti az új tételeket és a meglévő tételek kiegészíthető adatait, amelyekből kiválaszthatja az importálandókat. Mentéskor a fájl neve alapértelmezetten \"deziderata.json\"\n\n"
                "7. Katalóguslap mentése:\n"
                "  Az állományhoz hasonlóan a Deziderátáról is készíthető PDF katalóguslap.\nEhhez a főablakban megszokott módon használhatja a Ctrl + K billentyűparancsot, az eszköztár Katalógus export gombját, vagy a megfelelő menüpontot.\n\n"
                "8. Visszavonás és ismétlés:\n"
                "  A legutóbbi művelet visszavonásához használja a Szerkesztés menü Visszavonás parancsát, vagy a Ctrl+Z billentyűparancsot.\nA művelet ismételt végrehajtásához válassza a menü Mégis menüpontját, vagy használja a Ctrl+Y billentyűket.\n\n"
                "9. Másolás a vágólapra:\n"
                "  A lista kijelölt elemeit vágólapra másolhatja tabulátorral elválasztott szövegként, hasonlóan a KönyvTárnok-keresőhöz.\nA kijelölt elemek másolásához használja a Szerkesztés menü Másolás menüpontját, vagy nyomja meg a Ctrl + C billentyűparancsot.\n"
            ),
            (
                "KönyvTárnok kereső",
                "A KÖNYVTÁRNOK KERESŐ HASZNÁLATA\n\n"
                "1. A KönyvTárnok-kereső megnyitása:\n"
                "  A keresőablak megnyitásához válassza az Eszközök -> KönyvTárnok-kereső menüpontot, vagy nyomja meg a Ctrl + Shift + K billentyűkombinációt.\n\n"
                "2. Adatbázis megnyitása:\n"
                "  A kereső indításkor automatikusan betölti a legutoljára megnyitott adatbázist (ha volt). Új JSON adatbázis megnyitásához válassza a Fájl -> Adatbázis megnyitása menüpontot, vagy nyomja meg a Ctrl + O billentyűkombinációt. Az adatbázis egy tetszőleges JSON fájl lehet, amelynek minden eleme egy könyv adatait tartalmazó rekord (\"mező: érték\" szerkezetű dict). Sikeres megnyitás után az ablak címe és az állapotsor jelzi az aktív adatbázis nevét és a benne lévő kötetek számát.\n\n"
                "3. Keresés:\n"
                "  Írja be a keresendő szót vagy kifejezést a keresőmezőbe, majd nyomja meg a Keresés gombot vagy az Enter billentyűt a találatok megjelenítéséhez. Amint gépelni kezd, a Keresés törlése gomb aktívvá válik, ennek segítségével kiürítheti a keresőmezőt, valamint keresés után a találatok listáját is. A mező melletti Csak teljes szó jelölőnégyzettel megadhatja, hogy a keresett kifejezés csak egész szóként egyezzen (ne részszövegként). A lenti jelölőnégyzetekkel kiválaszthatja, mely oszlopokban szeretne keresni. Az Összes oszlop jelölőnégyzettel az összes oszlopot egyszerre jelölheti ki, illetve szüntetheti meg. A találatokban a Státusz oszlop jelzi, ha egy tétel már szerepel az állományban (zöld háttér) vagy a deziderátában (sárga háttér).\n\n"
                "4. Találatok kijelölése és másolása:\n"
                "  Az összes találatot kijelölheti a Ctrl + A billentyűparanccsal. A kijelölt sorok adatait a Ctrl + C gombokkal másolhatja a vágólapra.\n\n"
                "5. Találat átemelése a Deziderátába vagy az Állományba:\n"
                "  A kiválasztott találat(ok)at az erre szolgáló gombokkal, a jobbklikkre felugró helyi menüből és billentyűparancsokkal is átemelheti a deziderátába vagy az állományba.\nAdott találat átemeléséhez  használja a Ctrl + D billentyűkombinációt a Dezideráta-jegyzékbe, vagy a Ctrl + F billentyűkombinációt az állományba való átemeléshez. A másolást, valamint az átemeléseket a felugró menüből is elvégezheti. A menü előhívásához kattintson duplán a kívánt találatra, vagy nyomja meg rajta az Enter billentyűt.\n\n"
                "6. Gyorsbillentyűk a keresőablakban:\n"
                "  A keresőablak vezérlői Alt billentyűs gyorsbillentyűvel is elérhetők, a feliratokban az aláhúzott betű jelzi őket. Alt + K: keresendő kifejezés mezője, Alt + T: Keresés törlése, Alt + R: Keresés indítása, Alt + O: Összes oszlop jelölőnégyzet, Alt + S: Csak teljes szó jelölőnégyzet.\n"
            ),
            (
                "Beállítások",
                "BEÁLLÍTÁSOK ÉS TESTRESZABÁS\n\n"
                "1. A Beállítások ablak megnyitása:\n"
                "  Az alkalmazás testreszabásához válassza az Eszközök -> Beállítások menüpontot vagy nyomja meg a Ctrl + B billentyűkombinációt.\n\n"
                "2. Vizuális téma váltása:\n"
                "  A Megjelenés fülön beállíthatja az alkalmazás megjelenési témáját (pl. Világos vagy Sötét téma), amely mentés után azonnal érvényesül a főablakon, a párbeszédablakokon és a segédmodulokon is. Ehhez válassza ki a kívánt témát, majd kattintson a mentés gombra. A témaválasztó görgetésekor a kijelölt téma előnézete megjelenik a beállítások ablakon, így mentés nélkül is láthatja annak kinézetét.\n\n"
                "3. Látható oszlopok beállítása:\n"
                "  Az oszlopok a listában fülön kiválaszthatja, hogy a főablak könyvlistájában mely oszlopok (alcím, összeállító, kiadó, kiadás éve, méret, kötés, forrás, státusz stb.) jelenjenek meg. A Cím oszlop mindig aktív, és a jelölőnégyzete le van tiltva.\n\n"
                "4. Mappák automatikus megjegyzése:\n"
                "  A program automatikusan megjegyzi a legutóbb használt könyvadatlap, statisztika, katalóguslap, állományjegyzék,\n  és dezideráta-jegyzék mentési/betöltési mappáit, valamint a KönyvTárnok-kereső adatbázisának útvonalát.\n  Ezeket manuálisan is megadhatja a beállítások ablak Mappák és elérési utak fülén.\n\n"
                "5. Frissítések keresése:\n"
                "  A frissítések fülön megadhatja, hogy a program milyen gyakran ellenőrizze a frissítést.\n  Amennyiben a Soha opciót választja, a program nem ellenőrzi automatikusan az új verzió meglétét.\n  Amennyiben manuálisan szeretné ellenőrizni, hogy van e új frissítés a KönyvTárnok-hoz, kattintson a kombinált listamező melletti Frissítések keresése most gombra.\n\n"
                "6. Beállítások mentése:\n"
                "  Ha végzett a beállítások módosításával, a mentéshez kattintson az ok gombra, vagy nyomja meg a CTRL + S billentyűket.\n  Amennyiben a mentés meghiúsul, a program felugró üzenetben tájékoztat erről.\n  Ekkor a módosítások csak a program bezárásáig maradnak érvényben.\n"
            ),
            (
                "Frissítés",
                "FRISSÍTÉSEK KERESÉSE\n\n"
                "1. Új verzió ellenőrzése:\n"
                "  Új verzió ellenőrzéséhez használja a Súgó menü Frissítések keresése menüpontját, vagy nyomja meg a Ctrl+U billentyűkombinációt.\n  A program alapértelmezés szerint minden indításkor ellenőrzi a frissítéseket, ezt a beállítások ablakban módosíthatja.\n  Ha van elérhető új verzió, a felugró ablakban megjelenik annak leírása, valamint a letöltésre, a GitHub kiadási oldal megnyitására, és a frissítés elhalasztására szolgáló gombok.\n  Ha nincs elérhető frissítés, manuális ellenőrzés esetén a program felugró ablakban tájékoztat erről.\n\n"
                "2. Frissítés letöltése vagy elhalasztása:\n"
                "  Az új verzió letöltéséhez kattintson a frissítés most gombra.\n  Ekkor a program automatikusan letölti és megnyitja az új verziót.\n  Amennyiben később szeretné letölteni a frissítést, kattintson a frissítés elhalasztása gombra.\n  Az Önnek megfelelő időpontban futtassa újra a frissítés keresését a fenti módon, és válassza a frissítés most opciót.\n"
            ),
            (
                "Billentyűparancsok",
                "BILLENTYŰPARANCSOK LISTÁJA\n\n"
                "   1. A főablak billentyűparancsai:\n"
                "  Enter                 - Kijelölt könyv adatlapjának megnyitása\n"
                "  Ctrl + N              - Új könyv felvétele\n"
                "  Ctrl + E              - Kijelölt könyv szerkesztése\n"
                "  Ctrl + S              - Módosítások mentése (párbeszédablakokban)\n"
                "  Ctrl + A              - Összes elem kijelölése a listában\n"
                "  Ctrl + Shift + A      - Kijelölés törlése\n"
                "  Delete                - Kijelölt könyv(ek) törlése\n"
                "  Ctrl + Shift + E      - Egy vagy több könyvadatlap exportálása PDF fájlba\n"
                "  Ctrl + Shift + B      - Állományjegyzék betöltése JSON fájlból\n"
                "  Ctrl + Shift + M      - Állományjegyzék mentése JSON fájlba\n"
                "  Ctrl + K                - Katalóguslap mentése PDF fájlba\n"
                "  Ctrl + C            - Kijelölt könyv vágólapra másolása a látható oszlopokkal\n"
                "  Ctrl + F              - Élő keresősáv fókuszba helyezése\n"
                "  Ctrl + Shift + F      - Keresés a gyűjteményekben párbeszédablak megnyitása\n"
                "  Ctrl + T              - Állománystatisztika megnyitása\n"
                "  Ctrl + D              - Dezideráta-kezelő megnyitása\n"
                "  Ctrl + Shift + K      - KönyvTárnok kereső megnyitása\n"
                "  Ctrl + B              - Beállítások ablak megnyitása\n"
                "  Alt + C               - Rendezés cím szerint\n"
                "  Alt + S               - Rendezés összeállító szerint\n"
                "  Alt + K               - Rendezés kiadó szerint\n"
                "  Alt + E               - Rendezés a kiadás éve szerint\n"
                "  Alt + O               - Rendezés oldalszám szerint\n"
                "  Alt + M               - Rendezés méret szerint\n"
                "  Alt + D               - Rendezés bekerülés dátuma szerint\n"
                "  F1                    - Súgó megnyitása\n"
                "  Ctrl + Shift + S        - Billentyűparancsok megnyitása\n"
                "  Ctrl + Shift + U      - Újdonságok megjelenítése\n"
                "  Ctrl + Shift + N      - Névjegy megjelenítése\n"
                "  Ctrl + U      - Frissítések keresése\n"
                "  ESC                   - Párbeszédablakok bezárása\n"
                "  Ctrl + Z        - Utolsó művelet visszavonása.\n"
                "  Ctrl + Y        - Visszavont művelet ismételt végrehajtása.\n"
                "  Ctrl + W              - Ablak bezárása\n\n"
                "   2. A Dezideráta-kezelő billentyűparancsai:\n"
                "  Enter                 - Kijelölt tétel adatlapjának megnyitása\n"
                "  Ctrl + N              - Új tétel hozzáadása\n"
                "  Ctrl + E              - Kijelölt tétel szerkesztése\n"
                "  Ctrl + S              - Módosítások mentése (párbeszédablakokban)\n"
                "  Ctrl + A              - Összes tétel kijelölése\n"
                "  Ctrl + Shift + A      - Kijelölés törlése\n"
                "  Delete                - Kijelölt tétel(ek) törlése\n"
                "  Ctrl + F              - Kijelölt tétel(ek) felvétele a fő könyvállományba\n"
                "  Ctrl + K                - Katalóguslap mentése PDF fájlba\n"
                "  Ctrl + C            - Kijelölt könyv vágólapra másolása\n"
                "  Ctrl + Shift + B      - Dezideráta-jegyzék betöltése JSON fájlból\n"
                "  Ctrl + Shift + M      - Dezideráta-jegyzék mentése JSON fájlba\n"
                "  Ctrl + Z        - Utolsó művelet visszavonása.\n"
                "  Ctrl + Y        - Visszavont művelet ismételt végrehajtása.\n"
                "  Ctrl + Shift + F      - Keresés a gyűjteményekben párbeszédablak megnyitása\n"
                "  F1                    - Súgó megnyitása\n"
                "  Ctrl + W        - Ablak bezárása\n\n"
                "   3. A KönyvTárnok kereső billentyűparancsai:\n"
                "  Ctrl + O              - Adatbázis megnyitása\n"
                "  Enter a keresőmezőben - Találatok keresése és megjelenítése\n"
                "  Enter a találati listán - Helyi menü megnyitása\n"
                "  Ctrl + A              - Összes találat kijelölése\n"
                "  Ctrl + Shift + A      - Kijelölés törlése\n"
                "  Ctrl + C              - Kijelölt találat(ok) másolása a vágólapra\n"
                "  Ctrl + D              - Kijelölt találat(ok) felvétele a Dezideráta-jegyzékbe\n"
                "  Ctrl + F              - Kijelölt találat(ok) felvétele a fő könyvállományba\n"
                "  Alt + K               - Ugrás a keresendő kifejezés mezőjére\n"
                "  Alt + T               - Keresés törlése\n"
                "  Alt + R               - Keresés indítása\n"
                "  Alt + O               - Összes oszlop jelölőnégyzet\n"
                "  Alt + S               - Csak teljes szó\n"
                "  F1                    - Súgó megnyitása\n"
                "  Ctrl + W        - Ablak bezárása\n\n"
                "   4. A Keresés a gyűjteményekben ablak billentyűparancsai:\n"
                "  Enter a keresőmezőben - Keresés indítása\n"
                "  Enter a találati listán - Kijelölt tétel adatlapjának megnyitása\n"
                "  Ctrl + C              - Kijelölt találat másolása a vágólapra\n"
                "  Alt + H               - Keresés helye (Mindenhol, Dezideráta, Állomány)\n"
                "  Alt + S               - Csak teljes szó\n"
                "  Alt + K               - Ugrás a keresett kifejezés mezőjére\n"
                "  Alt + T               - Keresés törlése\n"
                "  Alt + R               - Keresés indítása\n"
                "  ESC                   - Ablak bezárása\n"
            )
        ]

        for tab_title, content in pages_data:
            page = wx.Panel(self.notebook)
            sizer = wx.BoxSizer(wx.VERTICAL)
            txt = wx.TextCtrl(page, style=wx.TE_MULTILINE | wx.TE_READONLY)
            txt.SetValue(content)
            sizer.Add(txt, 1, wx.EXPAND | wx.ALL, 5)
            page.SetSizer(sizer)
            self.notebook.AddPage(page, tab_title)

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)
        
        # --- Bezárás gomb (Escape támogatással) ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # A wx.ID_CANCEL azonosító automatikusan hozzárendeli az Escape gombot a dialog bezárásához
        btn_bezaras = wx.Button(self, wx.ID_CANCEL, label="Bezárás")
        btn_bezaras.SetDefault()
        btn_sizer.Add(btn_bezaras, 0)
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)
        
        # Téma beállítása
        apply_theme_from_settings(self)

        self.SetSizer(main_sizer)

def sugo_megnyitasa(parent, ful=0):
    dlg = HelpNotebookDialog(parent)
    dlg.notebook.SetSelection(ful)
    dlg.ShowModal()
    dlg.Destroy()
