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
        notebook = wx.Notebook(self)

        pages_data = [
            (
                "Állománykezelés",
                "FŐABLAK ÉS ÁLLOMÁNYKEZELÉS\n\n"
                "1. Új könyv felvétele:\n"
                "  Új könyv felvételéhez kattintson az 'Új könyv' gombra a lista feletti eszköztárban, nyomja meg a Ctrl + N billentyűkombinációt, vagy válassza a Fájl menü Új könyv felvétele menüpontját. A megnyíló ablakban töltse ki a könyv adatait (Cím, Alcím, Összeállító, Egyéb személyek, Kiadó, Kiadás helye és éve, Oldalszám, Méret, Kötés típusa, Rövid cím, Bekerülés dátuma, Példány forrása, Státusz és Rövid leírás). A mentéshez kattintson a Mentés gombra vagy nyomja meg a Ctrl + S billentyűket. Fontos: a könyv címét minden esetben kötelező kitölteni!\n\n"
                "2. Könyv megtekintése és szerkesztése:\n"
                "  A listában lévő könyv részletes adatlapjának megtekintéséhez nyomja meg az Enter billentyűt a kijelölt elemen, kattintson rá duplán, vagy válassza a helyi menü 'Könyvadatlap megtekintése' pontját. A könyv adatainak módosításához kattintson a 'Kijelölt könyv szerkesztése' gombra, nyomja meg a Ctrl + E billentyűkombinációt, vagy válassza a Fájl -> Könyv szerkesztése menüpontot. Ha végzett a könyv adatainak szerkesztésével, kattintson a Mentés gombra, vagy nyomja meg a Ctrl+S billentyűkombinációt.\n\n"
                "3. Könyvek eltávolítása:\n"
                "  Egy vagy több könyv állományból való törléséhez jelölje ki a kívánt tételeket a listában, majd nyomja meg a Delete billentyűt, kattintson a 'Kijelöltek törlése' gombra, vagy válassza a Fájl -> Könyv(ek) eltávolítása menüpontot. A rendszer a törlés előtt megerősítést kér.\n\n"
                "4. Összes elem kijelölése:\n"
                "  A főlista összes kötetének egyidejű kijelöléséhez nyomja meg a Ctrl + A billentyűkombinációt.\n\n"
                "5. Gyorskeresés a listában:\n"
                "  Amikor a könyvlista fókuszban van, a kezdőbetű vagy szótag begépelésével is kijelölheti a kívánt kötetet.\n"
            ),
            (
                "Keresés és statisztika",
                "KERESÉS, SZŰRÉS, RENDEZÉS ÉS ÁLLOMÁNYSTATISZTIKA\n\n"
                "1. Élő keresősáv a főablakban:\n"
                "  A főablak felső részén található keresőmezővel (Ctrl + F) gépelés közben azonnal szűrheti az állományt. A rendszer a könyvek minden adatmezőjében (cím, szerző, kiadó, év stb.) keres.\n\n"
                "2. Részletes keresés párbeszédablak:\n"
                "  Az Eszközök -> Keresés az állományban menüponttal vagy a Ctrl + K billentyűkombinációval megnyitható keresőablakban pontos vagy részleges egyezésre is kereshet a teljes adatbázisban.\n\n"
                "3. Szűrés törlése:\n"
                "  Aktív szűrés vagy keresés esetén a lista feletti 'Szűrés törlése' gomb aktívvá válik, rákattintva visszaállíthatja a teljes könyvállomány megjelenítését.\n\n"
                "4. Állománystatisztika készítése:\n"
                "  Az Eszközök -> Állománystatisztika menüpontban (Ctrl + T) részletes kimutatásokat készíthet az állományról. Kiválaszthatja a statisztika alapját (pl. Kiadó, Kiadás éve, Kiadás évszázada, Kiadás évtizede, Kötés típusa, Példány forrása, Státusz stb.), majd szűrhet egy adott értékre vagy a hiányzó adatokra (\"Nincs kitöltve\"). A találatokat lehetősége van cím, szűrési szempont vagy az állomány aktuális rendezési szempontja szerint rendezni, valamint azokra fő listát leszűrni.\n\n"
                "5. Állomány rendezése:\n"
                "  A Rendezés menüpontban vagy az Alt billentyűparancsokkal (lásd a billentyűparancsok listáját) tetszőlegesen sorba rendezheti a könyveket. Fontos, hogy ez csak ideiglenes rendezés, mely a program bezárásakor törlődik. A lista alapértelmezett rendezését a beállítások Téma és rendezés fülén választhatja ki.\n"
            ),
                (
                "Adatmentés",
                "PDF ÉS JSON FÁJLOK KEZELÉSE\n\n"
                "1. Könyvadatlap exportálása PDF fájlba:\n"
                "  A kijelölt könyv(ek)ről nyomtatható PDF adatlapot generálhat a Fájl -> Könyvadatlap(ok) exportálása PDF-ként... menüpontban vagy a Ctrl + Shift + E billentyűkombinációval. Egyetlen könyv esetén egyedi fájlnevet adhat meg, több könyv kijelölése esetén pedig egy kiválasztott mappába tömegesen exportálhatja az adatlapokat. A program alapértelmezetten a könyv címét és kiadásának évét használja a pdf fájlneveként egyedi és tömeges exportnál is. Ha a könyv kiadási éve nincs kitöltve, a zárójelben a \"nincs_ev_megadva\" felirat szerepel.\n\n"
                "2. Állományjegyzék mentése JSON-ba (Biztonsági mentés):\n"
                "  A teljes állományjegyzék exportálható szerkeszthető, SHA integritásvédelem nélküli JSON fájlba a Fájl -> Állományjegyzék mentése JSON fájlba... menüpontban (Ctrl + Shift + M). Ez kiválóan alkalmas biztonsági mentésre. A JSON fájl alapértelmezetten az \"allomanyjegyzek.json\" nevet kapja.\n\n"
                "3. Állományjegyzék betöltése JSON-ból:\n"
                "  Egy korábban elmentett JSON állományjegyzék beolvasásához használja a Fájl -> Állományjegyzék betöltése JSON fájlból... menüpontot (Ctrl + Shift + B). A mentett JSON fájlból csak azok a könyvek kerülnek felvételre, amelyek még nem szerepelnek a listában.\n\nFONTOS: nyers, azaz SHA aláírás nélküli, exportált JSON-t soha ne helyezzen a program mappájába! A program ugyanis az ilyen fájlokat nem tölti be és nem kezeli! Amennyiben az állományjegyzék vagy a dezideráta csak nyers formátumban áll rendelkezésére, használja a megfelelő modul JSON importálás funkcióját a fenti módon.\n"
            ),
                        (
                "Dezideráta-kezelő",
                "A DEZIDERÁTA-KEZELŐ HASZNÁLATA\n\n"
                "1. A Dezideráta-kezelő megnyitása:\n"
                "  A beszerzendő vagy hiányzó könyvek nyilvántartására szolgáló modult az Eszközök -> Dezideráta-kezelő menüpontból vagy a Ctrl + D billentyűkombinációval nyithatja meg.\n\n"
                "2. Új tétel hozzáadása:\n"
                "  Új beszerzendő könyv felvételéhez nyomja meg az 'Új tétel' gombot vagy a Ctrl + N billentyűket. A megnyíló ablakban töltse ki a könyv aadatait. Az alapadatok (cím, összeállító, egyéb személyek, kiadó, kiadás helye és éve) mellett megadhatja a tétel prioritását, státuszát (kapható/nem kapható). Kapható státusz esetén megjelenik három további mező, ahol a megvásárolható tétel lelőhelyét, jelenlegi vagy becsült árát és webes hivatkozását (link) is rögzítheti. Ha a könyv státuszát Nem kapható-ra állítja, az utóbbi három mező eltűnik, és tartalmuk törlődik a könyv adatlapjáról. Amikor végzett az adatok kitöltésével, kattintson a Mentés gombra, vagy nyomja meg a Ctrl+S billentyűt.\n\n"
                "3. Tételek megtekintése és szerkesztése:\n"
                "  A kijelölt tétel részleteit az Enter billentyűvel vagy dupla kattintással tekintheti meg. Ha a tétel kapható, és van megadva link, az adatlapon rákattintva a program megnyitja a weboldalt az Ön alapértelmezett böngészőjében. Tétel szerkesztéséhez használja a 'Kijelölt tétel szerkesztése' gombot vagy a Ctrl + E billentyűparancsot. Az adatok módosítása után kattintson a Mentés gombra, vagy nyomja meg a Ctrl+S billentyűt.\n\n"
                "4. Tételek törlése:\n"
                "  A már nem kívánt tételeket a Delete billentyűvel vagy a törlés gombbal távolíthatja el.\n\n"
                "5. Tétel felvétele a fő könyvállományba:\n"
                "  Ha egy beszerzendő könyvet sikerült megvásárolni/megszerezni, a kijelölt tételt a Ctrl + F billentyűkombinációval vagy a 'Felvétel az állományba' gombbal közvetlenül átemelheti a fő katalógusba. Átemeléskor a program megkérdezi, hogy biztosan át szeretné e emelni a tételt. Amennyiben ezt szeretné, kattintson az Igen gombra.\n\n"
                "6. Dezideráta adatok mentése és betöltése:\n"
                "  A dezideráta jegyzék exportálhstó szerkeszthető, azaz SHA integritásvédelem nélküli JSON fájlba (Ctrl + Shift + M) és bármikor visszatölthető (Ctrl + Shift + B) a Tételek menüből. JSON fájl betöltése esetén csak azok a kötetek kerülnek importálásra, amelyek még nem szerepelnek a jegyzékben. Mentéskor a fájl neve alapértelmezetten \"deziderata.json\"\n"
            ),
            (
                "KönyvTárnok kereső",
                "A KÖNYVTÁRNOK KERESŐ HASZNÁLATA\n\n"
                "1. A KönyvTárnok-kereső megnyitása:\n"
                "  A külső énekeskönyv adatbázisban való kereséshez válassza az Eszközök -> KönyvTárnok-kereső menüpontot, vagy nyomja meg a Ctrl + Shift + K billentyűkombinációt.\n\n"
                "2. Keresés:\n"
                "  Írja be a keresendő szót vagy kifejezést a keresőmezőbe, majd nyomja meg az Enter billentyűt a találatok kilistázásához. A mező melletti jelölőnégyzetekkel kiválaszthatja, mely oszlopokban szeretne keresni (cím, összeállító, kiadó, kiadás helye, kiadás éve, megjegyzés).\n\n"
                "3. Találatok kijelölése és másolása:\n"
                "  Az összes találatot kijelölheti a Ctrl + A billentyűparancsal. A kijelölt sorok adatait a Ctrl + C gombokkal másolhatja a vágólapra.\n\n"
                "4. Találat átemelése a Deziderátába vagy az Állományba:\n"
                "  A kiválasztott találat(ok)at a Ctrl + D billentyűkombinációval felveheti a Dezideráta-jegyzékbe, a Ctrl + F billentyűkombinációval pedig a fő könyvállományba.\n"
            ),
            (
                "Beállítások",
                "BEÁLLÍTÁSOK ÉS TESTRESZABÁS\n\n"
                "1. A Beállítások ablak megnyitása:\n"
                "  Az alkalmazás testreszabásához válassza az Eszközök -> Beállítások menüpontot vagy nyomja meg a Ctrl + B billentyűkombinációt.\n\n"
                "2. Vizuális téma váltása:\n"
                "  Beállíthatja az alkalmazás megjelenési témáját (pl. Világos vagy Sötét téma), amely azonnal érvényesül a főablakon, a párbeszédablakokon és a segédmodulokon is. Ehhez vállassza ki a kívánt témát, majd kattintson a mentés gombra.\n\n"
                "3. Alapértelmezett rendezés:\n"
                "  Kiválaszthatja, hogy a program indításakor a könyvlista milyen mező szerint legyen automatikusan sorba rendezve. A Rendezés-menüben kiválasztott szempont csupán ideiglenesen, a program bezárásáig érvényes.\n\n"
                "4. Látható oszlopok beállítása:\n"
                "  A beállítások ablakban kiválaszthatja, hogy a főablak könyvlistájában mely oszlopok (alcím, összeállító, kiadó, kiadás éve, méret, kötés, forrás, státusz stb.) jelenjenek meg. A Cím oszlop mindig aktív, és a jelölőnégyzete le van tiltva.\n\n"
                "5. Mappák automatikus megjegyzése:\n"
                "  A program automatikusan megjegyzi a legutóbb használt PDF export és JSON mentési/betöltési könyvtárakat, így nem kell minden alkalommal kikeresni azokat. Az alkalmazás első használatakor ezeket manuálisan is megadhatja a beállítások ablak ezen fülén.\n"
                "6. Frissítések keresése:\n"
                "  A Beállítások ablak frissítések fülén megadhatja, hogy a program keressen e automatikusan frissítéseket. Ehhez jelölje be a frissítések automatikus ellenőrzése jelölőnégyzetet.\n"
                "  Ha a négyzet be van jelölve, megjelenik egy kombinált listamező, ahol kiválaszthatja a frissítések ellenőrzésének gyakoriságát (minden indításkor, naponta, hetente, havonta).\n"
                "  A beállítás mentéséhez kattintson a mentés gombra.\n"
            ),
            (
                "Frissítés",
                "FRISSÍTÉSEK KERESÉSE\n\n"
                "  Új verzió ellenőrzéséhez használja a Súgó menü Frissítések keresése menüpontját, vagy nyomja meg a Ctrl+Shift+F billentyűkombinációt.\n"
                "  Ha van elérhető új verzió, a felugró ablakban megjelenik annak leírása, valamint a GitHub kiadási oldal megnyitására, és a frissítés elhalasztására szolgáló gombok. Az új verzió futtatható fájlját Önnek kell a megnyíló GitHub oldalról letölteni, és a régi fájlt manuálisan lecserélni az újra. Fontos, hogy az új verzió abba a mappába kerüljön,  ahol a régi volt, különben a program nem fogja megtalálni az állomány- és dezideráta-jegyzéket, valamint az Ön beállításait tartalmazó JSON fájlt.\n"
                "  Ha nincs új verzió, a program felugró ablakban tájékoztat erről.\n"
                "  A program alapértelmezés szerint minden indításkor ellenőrzi a frissítéseket, ezt a beállítások ablakban módosíthatja.\n"
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
                "  Delete                - Kijelölt könyv(ek) törlése\n"
                "  Ctrl + Shift + E      - Egy vagy több könyvadatlap exportálása PDF fájlba\n"
                "  Ctrl + Shift + B      - Állományjegyzék betöltése JSON fájlból\n"
                "  Ctrl + Shift + M      - Állományjegyzék mentése JSON fájlba\n"
                "  Ctrl + F              - Élő keresősáv fókuszba helyezése\n"
                "  Ctrl + K              - Keresés az állományban párbeszédablak megnyitása\n"
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
                "  F1                    - Súgó és billentyűparancsok megnyitása\n"
                "  Ctrl + Shift + U      - Újdonságok megjelenítése\n"
                "  Ctrl + Shift + N      - Névjegy megjelenítése\n"
                "  Ctrl + Shift + F      - Frissítések keresése\n"
                "  ESC                   - Párbeszédablakok bezárása\n"
                "  Ctrl + W              - Ablak bezárása\n\n"
                "   2. A Dezideráta-kezelő billentyűparancsai:\n"
                "  Enter                 - Kijelölt tétel adatlapjának megnyitása\n"
                "  Ctrl + N              - Új tétel hozzáadása\n"
                "  Ctrl + E              - Kijelölt tétel szerkesztése\n"
                "  Ctrl + S              - Módosítások mentése (párbeszédablakokban)\n"
                "  Ctrl + A              - Összes tétel kijelölése\n"
                "  Delete                - Kijelölt tétel(ek) törlése\n"
                "  Ctrl + F              - Kijelölt tétel(ek) felvétele a fő könyvállományba\n"
                "  Ctrl + Shift + B      - Dezideráta-jegyzék betöltése JSON fájlból\n"
                "  Ctrl + Shift + M      - Dezideráta-jegyzék mentése JSON fájlba\n"
                "  Ctrl + W        - Ablak bezárása\n\n"
                "   3. A KönyvTárnok kereső billentyűparancsai:\n"
                "  Enter a keresőmezőben - Találatok keresése és megjelenítése\n"
                "  Enter a találati listán - Helyi menü megnyitása\n"
                "  Ctrl + A              - Összes találat kijelölése\n"
                "  Ctrl + C              - Kijelölt találat(ok) másolása a vágólapra\n"
                "  Ctrl + D              - Kijelölt találat(ok) felvétele a Dezideráta-jegyzékbe\n"
                "  Ctrl + F              - Kijelölt találat(ok) felvétele a fő könyvállományba\n"
                "  Ctrl + W        - Ablak bezárása\n"
            )
        ]

        for tab_title, content in pages_data:
            page = wx.Panel(notebook)
            sizer = wx.BoxSizer(wx.VERTICAL)
            txt = wx.TextCtrl(page, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
            txt.SetValue(content)
            sizer.Add(txt, 1, wx.EXPAND | wx.ALL, 5)
            page.SetSizer(sizer)
            notebook.AddPage(page, tab_title)

        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 10)
        
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
