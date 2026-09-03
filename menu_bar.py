import wx

class KonyvtarMenuBar(wx.MenuBar):
    def __init__(self):
        super().__init__()
        
        fajl_menu = wx.Menu()
        self.uj_konyv = fajl_menu.Append(wx.ID_NEW, '&Új könyv felvétele\tCtrl+N', 'Új könyv hozzáadása')
        fajl_menu.AppendSeparator()
        self.szerk = fajl_menu.Append(wx.ID_EDIT, '&Könyv szerkesztése\tCtrl+E', 'Kijelölt könyv szerkesztése')
        self.torles = fajl_menu.Append(wx.ID_DELETE, '&Könyv(ek) eltávolítása\tDelete', 'Kijelölt könyvek törlése')
        fajl_menu.AppendSeparator()
        self.import_elem = fajl_menu.Append(wx.ID_ANY, '&Könyvadatlap(ok) importálása PDF-ből...\tCtrl+Shift+I', 'Könyvek importálása')
        self.export_elem = fajl_menu.Append(wx.ID_ANY, '&Könyvadatlap(ok) exportálása PDF-ként...\tCtrl+Shift+E', 'Kijelöltek exportálása PDF-be')
        fajl_menu.AppendSeparator()
        self.json_import = fajl_menu.Append(wx.ID_ANY, 'Állományjegyzék betöltése JSON fájlból...\tCtrl+Shift+B', 'Teljes állományjegyzék betöltése JSON-ból')
        self.json_export = fajl_menu.Append(wx.ID_ANY, 'Állományjegyzék mentése titkosítás nélküli JSON fájlba...\tCtrl+Shift+M', 'Teljes állományjegyzék kimentése JSON-ba')
        fajl_menu.AppendSeparator()
        self.kilepes = fajl_menu.Append(wx.ID_EXIT, '&Kilépés\tCtrl+W', 'Program bezárása')
        
        self.Append(fajl_menu, '&Fájl')

        ord_menu = wx.Menu()
        self.cim = ord_menu.Append(wx.ID_ANY, '&Cím szerint\tALT+C', 'Rendezés cím szerint')
        self.szerzo = ord_menu.Append(wx.ID_ANY, '&Összeállító szerint\tALT+S', 'Rendezés összeállító szerint')
        self.kiado = ord_menu.Append(wx.ID_ANY, '&Kiadó szerint\tALT+K', 'Rendezés kiadó szerint')
        self.ev = ord_menu.Append(wx.ID_ANY, '&Kiadás éve szerint\tALT+E', 'Rendezés a kiadás éve szerint')
        self.oldalszam = ord_menu.Append(wx.ID_ANY, '&Oldalszám szerint\tALT+O', 'Rendezés oldalszám szerint')
        self.meretek = ord_menu.Append(wx.ID_ANY, '&Méret szerint\tALT+M', 'Rendezés a könyv magassága szerint')
        self.bekerult = ord_menu.Append(wx.ID_ANY, '&Bekerülés dátuma szerint\tALT+D', 'Rendezés a bekerülés dátuma szerint')
        self.Append(ord_menu, '&Rendezés')

        set_menu = wx.Menu()
        self.deziderata = set_menu.Append(wx.ID_ANY, '&Dezideráta-kezelő\tCTRL+D', 'Dezideráta jegyzék kezelése')
        set_menu.AppendSeparator()
        self.find = set_menu.Append(wx.ID_ANY, '&Keresés az állományban\tCTRL+K', 'Keresés')
        self.konyvtarnok_kereso_item = set_menu.Append(wx.ID_ANY, '&Keresés az adatbázisban\tCTRL+SHIFT+K', 'KönyvTárnok kereső')
        self.statisztika = set_menu.Append(wx.ID_ANY, '&Állománystatisztika\tCTRL+T', 'Statisztika készítése feltételek alapján')
        set_menu.AppendSeparator()
        self.set = set_menu.Append(wx.ID_ANY, '&Beállítások\tCTRL+B', 'Beállítások')

        self.Append(set_menu, '&Eszközök')

        help_menu = wx.Menu()
        self.help = help_menu.Append(wx.ID_ANY, '&Súgó és billentyűparancsok\tF1', 'Az alkalmazás súgója és billentyűparancsai')
        self.Ujdonsagok = help_menu.Append(wx.ID_ANY, '&Újdonságok\tCTRL+SHIFT+U', 'Megjeleníti az aktuális verzió újdonságait')
        self.nevjegy = help_menu.Append(wx.ID_ABOUT, '&Névjegy\tCTRL+SHIFT+N', 'Megjeleníti a névjegy ablakot')

        self.Append(help_menu, '&Súgó')