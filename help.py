import wx
from config_manager import load_settings
from theme_manager import apply_theme

class HelpNotebookDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent, 
            title="Súgó", 
            size=(700, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self.init_ui()
        self.CentreOnParent()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        notebook = wx.Notebook(self)
        
        # --- 1. Lap: Használati útmutató ---
        page1 = wx.Panel(notebook)
        sizer1 = wx.BoxSizer(wx.VERTICAL)
        txt1 = wx.TextCtrl(page1, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        txt1.SetValue(
            "HASZNÁLATI ÚTMUTATÓ\n\n"
            "1. Új könyv felvétele:\n"
            "  Új könyv felvételéhez kattintson az 'Új könyv' gombra a lista feletti gombsorban, vagy nyomja meg a Ctrl+N billentyűkombinációt. A megnyíló ablakban töltse ki a mezőket, majd kattintson a Mentés gombra, vagy nyomja meg a Ctrl + S billentyűket.\n\n"
            "2. Keresés és Szűrés:\n"
            "  A lista felett lévő keresőmezővel a teljes állományban kereshet. A kereső gépelés közben folyamatosan szűri a listát a beírt szöveg alapján. A keresés törléséhez és a teljes lista visszaállításához használja a Szűrés törlése gombot, mely szűrt lista esetén automatikusan aktívvá válik.\n\n"
            "3. Exportálás:\n"
            "   A kijelölt könyvekről PDF adatlapot hozhat létre a Fájl menü Exportálás menüpontban, vagy a Ctrl + Shift + E billentyűkombinációval.\n"
        )
        sizer1.Add(txt1, 1, wx.EXPAND | wx.ALL, 5)
        page1.SetSizer(sizer1)
        notebook.AddPage(page1, "Az alkalmazás használata")
        
        # --- 2. Lap: Billentyűparancsok ---
        page2 = wx.Panel(notebook)
        sizer2 = wx.BoxSizer(wx.VERTICAL)
        txt2 = wx.TextCtrl(page2, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        txt2.SetValue(
            "BILLENTYŰPARANCSOK LISTÁJA\n\n"
            "   1. A főablak billentyűparancsai:\n"
            "  Enter       - Könyvadatlap megnyitása\n"
        "  Ctrl + N    - Új könyv felvétele\n"
            "  Ctrl + E    - Kijelölt könyv szerkesztése\n"
            "  Ctrl + S    - Módosítások mentése az új könyv felvétele vagy kijelölt könyv szerkesztése dialogok-ban\n"
            "  Ctrl + A    - Összes elem kijelölése a listában\n"
            "  Delete      - Kijelölt könyv(ek) törlése\n"
            "  Ctrl + Shift + I    - Egy vagy több könyvadatlap importálása PDF-ből\n"
            "  Ctrl + Shift + E    - Egy vagy több könyvadatlap exportálása PDF fájlba\n"
            "  Ctrl + Shift + B    - Állományjegyzék betöltése titkosítás nélküli JSON fájlból\n"
            "  Ctrl + Shift + M    - Állományjegyzék mentése JSON fájlba, titkosítás nélkül\n"
            "  Ctrl + F    - Élő keresősáv fókuszba helyezése\n"
            "  Ctrl + K    - Keresés és szűrés dialog megnyitása\n"
            "  Ctrl + B    - Beállítások ablak megnyitása\n"
            "  Ctrl + Shift + K    - A KönyvTárnok kereső megnyitása a külső excel fájl adatainak keresésére\n"
            "  Ctrl + D    - Dezideráta-kezelő megnyitása\n"
            "  F1          - Súgó megnyitása\n"
            "  ESC         - Párbeszédablakok bezárása\n"
            "  Ctrl + W    - Ablak bezárása\n\n"
        "   2. A Dezideráta-kezelő billentyűparancsai:\n"
        "  Enter    - Könyvadatlap megnyitása\n"
        "  Ctrl + N    - Új tétel hozzáadása\n"
        "  Ctrl + E    - Kijelölt tétel szerkesztése\n"
            "  Ctrl + S    - Módosítások mentése az új tétel hozzáadása vagy kijelölt tétel szerkesztése dialogok-ban\n"
        "  Ctrl + A    - Összes tétel kijelölése\n"
        "  Delete    - Kijelölt tétel(ek) törlése\n"
        "  Ctrl + F    - Kijelölt tétel(ek) felvétele az állományba\n"
            "  Ctrl + Shift + B    - Dezideráta-jegyzék betöltése titkosítás nélküli JSON fájlból\n"
            "  Ctrl + Shift + M    - Dezideráta-jegyzék mentése JSON fájlba, titkosítás nélkül\n"
            "  Ctrl + W    - Ablak bezárása\n\n"
        "   3. A KönyvTárnok kereső billentyűparancsai:\n"
        "  Enter a keresőmezőben    - Találatok megjelenítése\n"
        "  Enter a kijelölt találaton    - Helyi menü megnyitása\n"
        "  Ctrl + A    - Összes találat kijelölése\n"
        "  Ctrl + C    - Kijelölt találat(ok) másolása a vágólapra\n"
        "  Ctrl + D    - Kijelölt találat(ok) felvétele a Dezideráta-jegyzékbe\n"
        "  Ctrl + F    - Kijelölt találat(ok) felvétele az állományba\n"
            "  Ctrl + W    - Ablak bezárása\n"
        )
        sizer2.Add(txt2, 1, wx.EXPAND | wx.ALL, 5)
        page2.SetSizer(sizer2)
        notebook.AddPage(page2, "Billentyűparancsok")
        
        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 10)
        
        # --- Bezárás gomb (Escape támogatással) ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # A wx.ID_CANCEL azonosító automatikusan hozzárendeli az Escape gombot a dialog bezárásához
        btn_bezaras = wx.Button(self, wx.ID_CANCEL, label="Bezárás")
        btn_bezaras.SetDefault()
        btn_sizer.Add(btn_bezaras, 0)
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)
        
        # Téma beállítása
        config = load_settings()
        apply_theme(self, config.get("tema", "vilagos"))
        
        self.SetSizer(main_sizer)
