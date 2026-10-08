import wx

class MenuBar(wx.MenuBar):
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
        self.katalogus = exportalas_menu.Append(wx.ID_ANY, "Katalóguslap\tCtrl+Shift+C", "A látható lista exportálása pdf fájlba")
        fajl_menu.AppendSubMenu(exportalas_menu, '&Exportálás')
        fajl_menu.AppendSeparator()
        self.json_import = fajl_menu.Append(wx.ID_ANY, 'Betöltés JSON fájlból\tCtrl+Shift+B', 'Teljes állományjegyzék megnyitása JSON-ból')
        self.json_export = fajl_menu.Append(wx.ID_ANY, 'Állományjegyzék mentése JSON fájlba\tCtrl+Shift+M', 'Teljes állományjegyzék mentése JSON-ba')
        fajl_menu.AppendSeparator()
        self.kilepes = fajl_menu.Append(wx.ID_EXIT, '&Kilépés\tCtrl+W', 'Program bezárása')
        
        self.Append(fajl_menu, '&Fájl')

        view_menu = wx.Menu()
        ord_menu = wx.Menu()
        self.cim = ord_menu.Append(wx.ID_ANY, '&Cím szerint\tALT+C', 'Rendezés cím szerint')
        self.szerzo = ord_menu.Append(wx.ID_ANY, '&Összeállító szerint\tALT+S', 'Rendezés összeállító szerint')
        self.kiado = ord_menu.Append(wx.ID_ANY, '&Kiadó szerint\tALT+K', 'Rendezés kiadó szerint')
        self.ev = ord_menu.Append(wx.ID_ANY, '&Kiadás éve szerint\tALT+E', 'Rendezés a kiadás éve szerint')
        self.oldalszam = ord_menu.Append(wx.ID_ANY, '&Oldalszám szerint\tALT+O', 'Rendezés oldalszám szerint')
        self.meretek = ord_menu.Append(wx.ID_ANY, '&Méret szerint\tALT+M', 'Rendezés a könyv magassága szerint')
        self.bekerult = ord_menu.Append(wx.ID_ANY, '&Bekerülés dátuma szerint\tALT+D', 'Rendezés a bekerülés dátuma szerint')
        view_menu.AppendSubMenu(ord_menu, '&Rendezés')
        self.Append(view_menu, '&Nézet')

        set_menu = wx.Menu()
        self.find = set_menu.Append(wx.ID_ANY, '&Keresés és szűrés\tCTRL+K', 'Keresés')
        self.statisztika = set_menu.Append(wx.ID_ANY, '&Állománystatisztika\tCTRL+T', 'Statisztika készítése feltételek alapján')
        set_menu.AppendSeparator()
        self.deziderata = set_menu.Append(wx.ID_ANY, '&Dezideráta-kezelő\tCTRL+D', 'Dezideráta jegyzék kezelése')
        self.konyvtarnok_kereso_item = set_menu.Append(wx.ID_ANY, '&KönyvTárnok-kereső\tCTRL+SHIFT+K', 'KönyvTárnok kereső')
        set_menu.AppendSeparator()
        self.set = set_menu.Append(wx.ID_ANY, '&Beállítások\tCTRL+B', 'Beállítások')

        self.Append(set_menu, '&Eszközök')

        help_menu = wx.Menu()
        self.help = help_menu.Append(wx.ID_ANY, '&Súgó és billentyűparancsok\tF1', 'Az alkalmazás súgója és billentyűparancsai')
        self.frissites = help_menu.Append(wx.ID_ANY, '&Frissítés ellenőrzése...\tCTRL+SHIFT+F', 'Új verzió keresése a GitHub-on')
        help_menu.AppendSeparator()
        self.Ujdonsagok = help_menu.Append(wx.ID_ANY, '&Újdonságok\tCTRL+SHIFT+U', 'Megjeleníti az aktuális verzió újdonságait')
        self.nevjegy = help_menu.Append(wx.ID_ABOUT, '&Névjegy\tCTRL+SHIFT+N', 'Megjeleníti a névjegy ablakot')

        self.Append(help_menu, '&Súgó')

class DeziderataMenuBar(wx.MenuBar):
    def __init__(self):
        super().__init__()

        fajl_menu = wx.Menu()
        self.uj_tetel = fajl_menu.Append(wx.ID_NEW, "Új tétel\tCTRL+N")
        fajl_menu.AppendSeparator()
        self.szerk = fajl_menu.Append(wx.ID_EDIT, "Szerkesztés\tCTRL+E")
        self.allomanyba = fajl_menu.Append(wx.ID_ANY, "Felvétel az állományba\tCTRL+F")
        self.torles = fajl_menu.Append(wx.ID_DELETE, "Törlés\tDelete")
        fajl_menu.AppendSeparator()
        self.katalogus = fajl_menu.Append(wx.ID_ANY, "Katalóguslap exportálása\tCtrl+Shift+C")
        self.json_import = fajl_menu.Append(wx.ID_ANY, "Betöltés JSON fájlból\tCtrl+SHIFT+B")
        self.json_export = fajl_menu.Append(wx.ID_ANY, "Jegyzék mentése JSON fájlba\tCtrl+SHIFT+M")
        fajl_menu.AppendSeparator()
        self.kilepes = fajl_menu.Append(wx.ID_EXIT, "Kilépés\tCtrl+W")

        self.Append(fajl_menu, "Fájl")
