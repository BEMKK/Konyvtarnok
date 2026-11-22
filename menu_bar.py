import wx


class NezetMenuBar(wx.MenuBar):
    """Közös ősosztály a három ablak menüsorához: a Nézet menü rádiócsoportjainak
    (rendezés, szűrések) jelölését végző segédek. Az utódok a kulcs -> menüelem
    szótárakat (rendezes_elemek, prioritas_elemek, statusz_elemek) töltik fel."""

    @staticmethod
    def RadioJelolese(elemek, kulcs):
        """Egy rádiócsoportban a megadott kulcsú elemet jelöli be (ha még nem
        az), hogy a képernyőolvasó mindig a valódi állapotot mondja be."""
        elem = elemek.get(kulcs)
        if elem is not None and not elem.IsChecked():
            elem.Check(True)

    def RendezesJelolese(self, kulcs):
        """A Nézet > Rendezés rádiócsoportban a megadott kulcsú elemet jelöli be."""
        self.RadioJelolese(self.rendezes_elemek, kulcs)

    def PrioritasJelolese(self, kulcs):
        """A Nézet > Szűrés > Prioritás rádiócsoport jelölése (Dezideráta)."""
        self.RadioJelolese(self.prioritas_elemek, kulcs)

    def StatuszJelolese(self, kulcs):
        """A Nézet > Státusz (Szűrés > Státusz) rádiócsoport jelölése."""
        self.RadioJelolese(self.statusz_elemek, kulcs)


class MenuBar(NezetMenuBar):
    def __init__(self):
        super().__init__()
        
        fajl_menu = wx.Menu()
        self.uj_konyv = fajl_menu.Append(wx.ID_NEW, '&Új könyv\tCtrl+N', 'Új könyv hozzáadása')
        fajl_menu.AppendSeparator()
        self.szerk = fajl_menu.Append(wx.ID_EDIT, '&Szerkesztés\tCtrl+E', 'Kijelölt könyv szerkesztése')
        self.torles = fajl_menu.Append(wx.ID_DELETE, '&Törlés\tDelete', 'Kijelölt könyvek törlése')
        fajl_menu.AppendSeparator()
        exportalas_menu = wx.Menu()
        self.export_elem = exportalas_menu.Append(wx.ID_ANY, '&Könyvadatlap\tCtrl+Shift+E', 'Kijelöltek exportálása PDF-be')
        self.katalogus = exportalas_menu.Append(wx.ID_ANY, "&Katalóguslap\tCtrl+K", "A látható lista exportálása pdf fájlba")
        fajl_menu.AppendSubMenu(exportalas_menu, '&Exportálás')
        fajl_menu.AppendSeparator()
        self.json_import = fajl_menu.Append(wx.ID_ANY, 'Betöltés JSON fájlból\tCtrl+Shift+B', 'Teljes állományjegyzék megnyitása JSON-ból')
        self.json_export = fajl_menu.Append(wx.ID_ANY, 'Állományjegyzék mentése JSON fájlba\tCtrl+Shift+M', 'Teljes állományjegyzék mentése JSON-ba')
        fajl_menu.AppendSeparator()
        self.kilepes = fajl_menu.Append(wx.ID_EXIT, '&Kilépés\tCtrl+W', 'Program bezárása')
        
        self.Append(fajl_menu, '&Fájl')

        edit_menu = wx.Menu()
        self.undo = edit_menu.Append(wx.ID_ANY, "Visszavonás\tCtrl+Z", "Utolsó művelet visszavonása")
        self.redo = edit_menu.Append(wx.ID_ANY, "Mégis\tCtrl+Y", "Visszavont művelet ismételt alkalmazása")
        self.copy = edit_menu.Append(wx.ID_ANY, "Másolás\tCtrl+C", "Kijelölt elemek vágólapra másolása")
        select_menu = wx.Menu()
        self.select_all = select_menu.Append(wx.ID_ANY, "Összes elem\tCtrl+A", "Összes elem kijelölése a listában")
        self.select_none = select_menu.Append(wx.ID_ANY, "Egyik sem\tCtrl+Shift+A")
        edit_menu.AppendSubMenu(select_menu, '&Kijelölés')

        self.Append(edit_menu, "S&zerkesztés")

        view_menu = wx.Menu()
        ord_menu = wx.Menu()
        self.cim = ord_menu.AppendRadioItem(wx.ID_ANY, '&Cím szerint\tALT+C', 'Rendezés cím szerint')
        self.szerzo = ord_menu.AppendRadioItem(wx.ID_ANY, '&Összeállító szerint\tALT+S', 'Rendezés összeállító szerint')
        self.kiado = ord_menu.AppendRadioItem(wx.ID_ANY, '&Kiadó szerint\tALT+K', 'Rendezés kiadó szerint')
        self.ev = ord_menu.AppendRadioItem(wx.ID_ANY, '&Kiadás éve szerint\tALT+E', 'Rendezés a kiadás éve szerint')
        self.oldalszam = ord_menu.AppendRadioItem(wx.ID_ANY, '&Oldalszám szerint\tALT+O', 'Rendezés oldalszám szerint')
        self.meretek = ord_menu.AppendRadioItem(wx.ID_ANY, '&Méret szerint\tALT+M', 'Rendezés a könyv magassága szerint')
        self.bekerult = ord_menu.AppendRadioItem(wx.ID_ANY, '&Bekerülés dátuma szerint\tALT+D', 'Rendezés a bekerülés dátuma szerint')
        view_menu.AppendSubMenu(ord_menu, '&Rendezés')
        self.Append(view_menu, '&Nézet')

        # A rendezési mező kulcsa -> menüelem. A rádiócsoport jelölésének
        # szinkronizálásához kell (lásd RendezesJelolese).
        self.rendezes_elemek = {
            "cim": self.cim,
            "szerzo": self.szerzo,
            "kiado": self.kiado,
            "ev": self.ev,
            "oldalszam": self.oldalszam,
            "meretek": self.meretek,
            "bekerult": self.bekerult,
        }

        set_menu = wx.Menu()
        self.find = set_menu.Append(wx.ID_ANY, '&Keresés a gyűjteményekben\tCTRL+Shift+F', 'Közös keresés az állományban és a deziderátában')
        self.statisztika = set_menu.Append(wx.ID_ANY, '&Állománystatisztika\tCTRL+T', 'Statisztika készítése feltételek alapján')
        set_menu.AppendSeparator()
        self.deziderata = set_menu.Append(wx.ID_ANY, '&Dezideráta-kezelő\tCTRL+D', 'Dezideráta jegyzék kezelése')
        self.konyvtarnok_kereso_item = set_menu.Append(wx.ID_ANY, '&KönyvTárnok-kereső\tCTRL+SHIFT+K', 'KönyvTárnok kereső')
        set_menu.AppendSeparator()
        self.set = set_menu.Append(wx.ID_ANY, '&Beállítások\tCTRL+B', 'Beállítások')

        self.Append(set_menu, '&Eszközök')

        help_menu = wx.Menu()
        self.help = help_menu.Append(wx.ID_ANY, '&Súgó\tF1', 'Az alkalmazás súgója')
        self.billentyu = help_menu.Append(wx.ID_ANY, '&Billentyűparancsok\tCtrl+Shift+S', 'Az alkalmazás billentyűparancsainak listája')
        self.frissites = help_menu.Append(wx.ID_ANY, '&Frissítés ellenőrzése...\tCTRL+U', 'Új verzió keresése a GitHub-on')
        help_menu.AppendSeparator()
        self.Ujdonsagok = help_menu.Append(wx.ID_ANY, '&Újdonságok\tCTRL+SHIFT+U', 'Megjeleníti az aktuális verzió újdonságait')
        self.licenc = help_menu.Append(wx.ID_ANY, '&Licencszerződés', 'Megjeleníti a program licencfeltételeit')
        self.nevjegy = help_menu.Append(wx.ID_ABOUT, '&Névjegy\tCTRL+SHIFT+N', 'Megjeleníti a névjegy ablakot')

        self.Append(help_menu, '&Súgó')

class DeziderataMenuBar(NezetMenuBar):
    def __init__(self):
        super().__init__()

        fajl_menu = wx.Menu()
        self.uj_tetel = fajl_menu.Append(wx.ID_NEW, "Új tétel\tCTRL+N")
        fajl_menu.AppendSeparator()
        self.szerk = fajl_menu.Append(wx.ID_EDIT, "Szerkesztés\tCTRL+E")
        self.allomanyba = fajl_menu.Append(wx.ID_ANY, "Felvétel az állományba\tCTRL+F")
        self.torles = fajl_menu.Append(wx.ID_DELETE, "Törlés\tDelete")
        fajl_menu.AppendSeparator()
        self.katalogus = fajl_menu.Append(wx.ID_ANY, "Katalóguslap exportálása\tCtrl+K")
        self.json_import = fajl_menu.Append(wx.ID_ANY, "Betöltés JSON fájlból\tCtrl+SHIFT+B")
        self.json_export = fajl_menu.Append(wx.ID_ANY, "Jegyzék mentése JSON fájlba\tCtrl+SHIFT+M")
        fajl_menu.AppendSeparator()
        self.kilepes = fajl_menu.Append(wx.ID_EXIT, "Kilépés\tCtrl+W")

        self.Append(fajl_menu, "Fájl")

        edit_menu = wx.Menu()
        self.undo = edit_menu.Append(wx.ID_ANY, "Visszavonás\tCtrl+Z", "Utolsó művelet visszavonása")
        self.redo = edit_menu.Append(wx.ID_ANY, "Mégis\tCtrl+Y", "Visszavont művelet ismételt alkalmazása")
        self.copy = edit_menu.Append(wx.ID_ANY, "Másolás\tCtrl+C", "Kijelölt elemek vágólapra másolása")
        select_menu = wx.Menu()
        self.select_all = select_menu.Append(wx.ID_ANY, "Összes elem\tCtrl+A", "Összes elem kijelölése a listában")
        self.select_none = select_menu.Append(wx.ID_ANY, "Egyik sem\tCtrl+Shift+A")
        edit_menu.AppendSubMenu(select_menu, '&Kijelölés')
        edit_menu.AppendSeparator()

        self.Append(edit_menu, "S&zerkesztés")

        view_menu = wx.Menu()
        ord_menu = wx.Menu()
        self.cim = ord_menu.AppendRadioItem(wx.ID_ANY, '&Cím szerint\tALT+C', 'Rendezés cím szerint')
        self.szerzo = ord_menu.AppendRadioItem(wx.ID_ANY, '&Összeállító szerint\tALT+S', 'Rendezés összeállító szerint')
        self.kiado = ord_menu.AppendRadioItem(wx.ID_ANY, '&Kiadó szerint\tALT+K', 'Rendezés kiadó szerint')
        self.ev = ord_menu.AppendRadioItem(wx.ID_ANY, '&Kiadás éve szerint\tALT+E', 'Rendezés a kiadás éve szerint')
        view_menu.AppendSubMenu(ord_menu, '&Rendezés')
        szures_menu = wx.Menu()
        priority_menu = wx.Menu()
        self.prioritas_mind = priority_menu.AppendRadioItem(wx.ID_ANY, '&Összes')
        self.elsodleges = priority_menu.AppendRadioItem(wx.ID_ANY, 'Elsődleges')
        self.masodlagos = priority_menu.AppendRadioItem(wx.ID_ANY, 'Másodlagos')
        szures_menu.AppendSubMenu(priority_menu, '&Prioritás')
        status_menu = wx.Menu()
        self.statusz_mind = status_menu.AppendRadioItem(wx.ID_ANY, '&Összes')
        self.beszerzes = status_menu.AppendRadioItem(wx.ID_ANY, 'Beszerzés alatt')
        self.kaphato = status_menu.AppendRadioItem(wx.ID_ANY, 'Jelenleg kapható')
        self.nemkaphato = status_menu.AppendRadioItem(wx.ID_ANY, 'Jelenleg nem kapható')
        szures_menu.AppendSubMenu(status_menu, '&Státusz')
        view_menu.AppendSubMenu(szures_menu, '&Szűrés')

        self.Append(view_menu, '&Nézet')

        # A rendezési mező / szűrési érték kulcsa -> menüelem. A rádiócsoportok
        # jelölésének szinkronizálásához kellenek (lásd NezetMenuBar).
        self.rendezes_elemek = {
            "cim": self.cim,
            "szerzo": self.szerzo,
            "kiado": self.kiado,
            "ev": self.ev,
        }
        self.prioritas_elemek = {
            "mind": self.prioritas_mind,
            "elsodleges": self.elsodleges,
            "masodlagos": self.masodlagos,
        }
        self.statusz_elemek = {
            "mind": self.statusz_mind,
            "beszerzes": self.beszerzes,
            "kaphato": self.kaphato,
            "nemkaphato": self.nemkaphato,
        }

        set_menu = wx.Menu()
        self.find = set_menu.Append(wx.ID_ANY, '&Keresés a gyűjteményekben\tCTRL+Shift+F', 'Közös keresés az állományban és a deziderátában')
        self.konyvtarnok_kereso_item = set_menu.Append(wx.ID_ANY, '&KönyvTárnok-kereső\tCTRL+SHIFT+K', 'KönyvTárnok kereső')
        set_menu.AppendSeparator()
        self.beallitasok = set_menu.Append(wx.ID_ANY, '&Beállítások\tCTRL+B', 'Beállítások')

        self.Append(set_menu, '&Eszközök')

        help_menu = wx.Menu()
        self.help = help_menu.Append(wx.ID_ANY, "Súgó\tF1")

        self.Append(help_menu, "Súgó")

class KeresoMenuBar(NezetMenuBar):
    def __init__(self):
        super().__init__()
        
        fajl_menu = wx.Menu()
        self.megnyitas = fajl_menu.Append(wx.ID_ANY, "Adatbázis megnyitása...\tCtrl+O", "Keresési adatbázis (JSON) megnyitása")
        fajl_menu.AppendSeparator()
        self.deziderata = fajl_menu.Append(wx.ID_ANY, "Átemelés a Deziderátába\tCtrl+Shift+D")
        self.allomany = fajl_menu.Append(wx.ID_ANY, "Átemelés az állományba\tCtrl+F")
        self.kilepes = fajl_menu.Append(wx.ID_EXIT, "Kilépés\tCtrl+W")

        self.Append(fajl_menu, "Fájl")

        edit_menu = wx.Menu()
        self.undo = edit_menu.Append(wx.ID_ANY, "Visszavonás\tCtrl+Z", "A kereső utolsó átemelésének visszavonása")
        self.redo = edit_menu.Append(wx.ID_ANY, "Mégis\tCtrl+Y", "Visszavont átemelés ismételt alkalmazása")
        self.copy = edit_menu.Append(wx.ID_ANY, "Másolás\tCtrl+C")
        select_menu = wx.Menu()
        self.select_all = select_menu.Append(wx.ID_ANY, "Összes elem\tCtrl+A", "Összes elem kijelölése a listában")
        self.select_none = select_menu.Append(wx.ID_ANY, "Egyik sem\tCtrl+Shift+A")
        edit_menu.AppendSubMenu(select_menu, '&Kijelölés')

        self.Append(edit_menu, "S&zerkesztés")

        view_menu = wx.Menu()
        ord_menu = wx.Menu()
        self.cim = ord_menu.AppendRadioItem(wx.ID_ANY, '&Cím szerint\tALT+C', 'Rendezés cím szerint')
        self.szerzo = ord_menu.AppendRadioItem(wx.ID_ANY, '&Összeállító szerint\tALT+S', 'Rendezés összeállító szerint')
        self.kiado = ord_menu.AppendRadioItem(wx.ID_ANY, '&Kiadó szerint\tALT+K', 'Rendezés kiadó szerint')
        self.ev = ord_menu.AppendRadioItem(wx.ID_ANY, '&Kiadás éve szerint\tALT+E', 'Rendezés a kiadás éve szerint')
        view_menu.AppendSubMenu(ord_menu, '&Rendezés')
        status_menu = wx.Menu()
        self.osszes = status_menu.AppendRadioItem(wx.ID_ANY, '&Összes')
        self.allomanyban = status_menu.AppendRadioItem(wx.ID_ANY, 'Állományban')
        self.deziderataban = status_menu.AppendRadioItem(wx.ID_ANY, 'Deziderátában')
        view_menu.AppendSubMenu(status_menu, '&Státusz')
        self.Append(view_menu, '&Nézet')

        # A rendezési mező / szűrési érték kulcsa -> menüelem. A rádiócsoportok
        # jelölésének szinkronizálásához kellenek (lásd NezetMenuBar).
        self.rendezes_elemek = {
            "cim": self.cim,
            "szerzo": self.szerzo,
            "kiado": self.kiado,
            "ev": self.ev,
        }
        self.statusz_elemek = {
            "osszes": self.osszes,
            "allomanyban": self.allomanyban,
            "deziderataban": self.deziderataban,
        }

        set_menu = wx.Menu()
        self.deziderata_kezelo = set_menu.Append(wx.ID_ANY, '&Dezideráta-kezelő\tCTRL+D', 'Dezideráta jegyzék kezelése')
        set_menu.AppendSeparator()
        self.beallitasok = set_menu.Append(wx.ID_ANY, '&Beállítások\tCTRL+B', 'Beállítások')

        self.Append(set_menu, '&Eszközök')

        help_menu = wx.Menu()
        self.help = help_menu.Append(wx.ID_ANY, '&Súgó\tF1', 'Az alkalmazás súgója és billentyűparancsai')

        self.Append(help_menu, "Súgó")
