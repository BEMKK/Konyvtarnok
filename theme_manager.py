import wx
import logging

from config_manager import load_settings

# A témák szótára és definíciói
THEMES = {
    "rendszer": {
        # Helyőrző: a színeket a _rendszer_tema() állítja elő a Windows
        # aktuális (akár magas kontrasztos) beállításaiból.
        "name": "Rendszer (Windows színek)",
    },
    "vilagos": {
        "name": "Világos",
        "panel_bg": wx.Colour(240, 240, 240),
        "text_fg": wx.Colour(0, 0, 0),
        "ctrl_bg": wx.Colour(255, 255, 255),
        "ctrl_fg": wx.Colour(0, 0, 0),
        "btn_bg": wx.Colour(240, 240, 240),
        "btn_fg": wx.Colour(0, 0, 0),
        "header_bg": wx.Colour(240, 240, 240),
        "header_fg": wx.Colour(0, 0, 0),
    },
    "sotet": {
        "name": "Sötét",
        "panel_bg": wx.Colour(43, 43, 43),
        "text_fg": wx.Colour(220, 220, 220),
        "ctrl_bg": wx.Colour(60, 63, 65),
        "ctrl_fg": wx.Colour(220, 220, 220),
        "btn_bg": wx.Colour(75, 78, 80),
        "btn_fg": wx.Colour(240, 240, 240),
        "header_bg": wx.Colour(50, 53, 55),
        "header_fg": wx.Colour(230, 230, 230),
    },
    "magas_kontraszt": {
        "name": "Magas kontraszt",
        "panel_bg": wx.Colour(0, 0, 0),          # Tiszta fekete
        "text_fg": wx.Colour(255, 255, 255),    # Tiszta fehér
        "ctrl_bg": wx.Colour(20, 20, 20),
        "ctrl_fg": wx.Colour(255, 255, 0),      # Kiemelt sárga szöveg a mezőkben
        "btn_bg": wx.Colour(40, 40, 40),
        "btn_fg": wx.Colour(255, 255, 255),
        "header_bg": wx.Colour(30, 30, 30),
        "header_fg": wx.Colour(255, 255, 255),
    },
    "szepia": {
        "name": "Szépia (Papír)",
        "panel_bg": wx.Colour(245, 238, 220),    # Meleg, krémszínű papírháttér
        "text_fg": wx.Colour(60, 45, 30),        # Mély kávébarna szöveg
        "ctrl_bg": wx.Colour(252, 248, 235),     # Világosabb krém a beviteli mezőknek
        "ctrl_fg": wx.Colour(50, 35, 20),
        "btn_bg": wx.Colour(230, 220, 200),
        "btn_fg": wx.Colour(50, 35, 20),
        "header_bg": wx.Colour(235, 225, 205),
        "header_fg": wx.Colour(50, 35, 20),
    },
    "zsalya": {
        "name": "Zsálya zöld",
        "panel_bg": wx.Colour(232, 240, 235),
        "text_fg": wx.Colour(30, 50, 40),
        "ctrl_bg": wx.Colour(242, 248, 244),
        "ctrl_fg": wx.Colour(20, 40, 30),
        "btn_bg": wx.Colour(210, 225, 215),
        "btn_fg": wx.Colour(20, 40, 30),
        "header_bg": wx.Colour(220, 235, 225),
        "header_fg": wx.Colour(25, 45, 35),
    },
    "pastel_kek": {
        "name": "Pasztell kék",
        "panel_bg": wx.Colour(230, 240, 250),
        "text_fg": wx.Colour(20, 40, 60),
        "ctrl_bg": wx.Colour(215, 230, 245),
        "ctrl_fg": wx.Colour(10, 20, 30),
        "btn_bg": wx.Colour(200, 220, 240),
        "btn_fg": wx.Colour(10, 20, 30),
        "header_bg": wx.Colour(210, 230, 245),
        "header_fg": wx.Colour(15, 30, 50),
    },
    "rozsaszin": {
        "name": "Rózsaszín",
        "panel_bg": wx.Colour(253, 238, 242),
        "text_fg": wx.Colour(60, 20, 35),
        "ctrl_bg": wx.Colour(255, 245, 248),
        "ctrl_fg": wx.Colour(40, 10, 25),
        "btn_bg": wx.Colour(248, 215, 225),
        "btn_fg": wx.Colour(50, 15, 30),
        "header_bg": wx.Colour(250, 225, 232),
        "header_fg": wx.Colour(60, 20, 35),
    },
    "sotet_kek": {
        "name": "Sötét kék",
        "panel_bg": wx.Colour(20, 28, 40),
        "text_fg": wx.Colour(230, 238, 248),
        "ctrl_bg": wx.Colour(32, 44, 62),
        "ctrl_fg": wx.Colour(230, 238, 248),
        "btn_bg": wx.Colour(45, 60, 82),
        "btn_fg": wx.Colour(245, 248, 255),
        "header_bg": wx.Colour(26, 36, 52),
        "header_fg": wx.Colour(220, 230, 242),
    },
"homok": {
        "name": "Homok",
        "panel_bg": wx.Colour(240, 232, 218),
        "text_fg": wx.Colour(55, 42, 30),
        "ctrl_bg": wx.Colour(250, 245, 235),
        "ctrl_fg": wx.Colour(45, 32, 20),
        "btn_bg": wx.Colour(225, 212, 192),
        "btn_fg": wx.Colour(45, 32, 20),
        "header_bg": wx.Colour(230, 220, 203),
        "header_fg": wx.Colour(50, 38, 25),
    },
    "barack": {
        "name": "Barack",
        "panel_bg": wx.Colour(253, 236, 224),
        "text_fg": wx.Colour(70, 35, 20),
        "ctrl_bg": wx.Colour(255, 246, 240),
        "ctrl_fg": wx.Colour(55, 25, 10),
        "btn_bg": wx.Colour(247, 215, 195),
        "btn_fg": wx.Colour(60, 28, 12),
        "header_bg": wx.Colour(250, 224, 208),
        "header_fg": wx.Colour(65, 30, 15),
    },
    "mez": {
        "name": "Méz (halványsárga)",
        "panel_bg": wx.Colour(255, 248, 205),
        "text_fg": wx.Colour(40, 30, 10),
        "ctrl_bg": wx.Colour(255, 252, 230),
        "ctrl_fg": wx.Colour(35, 25, 5),
        "btn_bg": wx.Colour(245, 232, 170),
        "btn_fg": wx.Colour(40, 30, 10),
        "header_bg": wx.Colour(250, 240, 185),
        "header_fg": wx.Colour(40, 30, 10),
    },
    "terrakotta": {
        "name": "Terrakotta (pasztell)",
        "panel_bg": wx.Colour(246, 228, 218),
        "text_fg": wx.Colour(75, 32, 20),
        "ctrl_bg": wx.Colour(252, 240, 233),
        "ctrl_fg": wx.Colour(60, 25, 12),
        "btn_bg": wx.Colour(236, 200, 185),
        "btn_fg": wx.Colour(60, 25, 12),
        "header_bg": wx.Colour(240, 214, 202),
        "header_fg": wx.Colour(70, 30, 18),
    },
    "borostyan": {
        "name": "Borostyán feketén",
        "panel_bg": wx.Colour(0, 0, 0),
        "text_fg": wx.Colour(255, 176, 0),
        "ctrl_bg": wx.Colour(22, 14, 0),
        "ctrl_fg": wx.Colour(255, 190, 40),
        "btn_bg": wx.Colour(48, 32, 0),
        "btn_fg": wx.Colour(255, 176, 0),
        "header_bg": wx.Colour(36, 24, 0),
        "header_fg": wx.Colour(255, 176, 0),
    },
    "sarga_kek": {
        "name": "Sárga kéken",
        "panel_bg": wx.Colour(0, 0, 128),
        "text_fg": wx.Colour(255, 255, 0),
        "ctrl_bg": wx.Colour(0, 0, 160),
        "ctrl_fg": wx.Colour(255, 255, 0),
        "btn_bg": wx.Colour(30, 30, 175),
        "btn_fg": wx.Colour(255, 255, 0),
        "header_bg": wx.Colour(0, 0, 100),
        "header_fg": wx.Colour(255, 255, 0),
    },
    "sarga_fekete": {
        "name": "Sárga feketén",
        "panel_bg": wx.Colour(0, 0, 0),
        "text_fg": wx.Colour(255, 255, 0),
        "ctrl_bg": wx.Colour(30, 30, 30),
        "ctrl_fg": wx.Colour(255, 255, 0),
        "btn_bg": wx.Colour(50, 50, 50),
        "btn_fg": wx.Colour(255, 255, 0),
        "header_bg": wx.Colour(38, 38, 38),
        "header_fg": wx.Colour(255, 255, 0),
    },
    "tompitett_szurke": {
        "name": "Tompított szürke",
        "panel_bg": wx.Colour(70, 70, 70),
        "text_fg": wx.Colour(225, 225, 225),
        "ctrl_bg": wx.Colour(88, 88, 88),
        "ctrl_fg": wx.Colour(240, 240, 240),
        "btn_bg": wx.Colour(100, 100, 100),
        "btn_fg": wx.Colour(245, 245, 245),
        "header_bg": wx.Colour(80, 80, 80),
        "header_fg": wx.Colour(235, 235, 235),
    },

    # ---------- Esztétikai témák ----------
    "grafit": {
        "name": "Grafit",
        "panel_bg": wx.Colour(46, 52, 64),
        "text_fg": wx.Colour(236, 239, 244),
        "ctrl_bg": wx.Colour(59, 66, 82),
        "ctrl_fg": wx.Colour(236, 239, 244),
        "btn_bg": wx.Colour(67, 76, 94),
        "btn_fg": wx.Colour(236, 239, 244),
        "header_bg": wx.Colour(52, 60, 74),
        "header_fg": wx.Colour(216, 222, 233),
    },
    "levendula": {
        "name": "Levendula",
        "panel_bg": wx.Colour(240, 236, 250),
        "text_fg": wx.Colour(40, 30, 70),
        "ctrl_bg": wx.Colour(248, 246, 255),
        "ctrl_fg": wx.Colour(30, 20, 60),
        "btn_bg": wx.Colour(224, 216, 244),
        "btn_fg": wx.Colour(30, 20, 60),
        "header_bg": wx.Colour(232, 226, 248),
        "header_fg": wx.Colour(35, 25, 65),
    },
}


def _rendszer_tema():
    """A Windows aktuális színeiből állítja elő a témát (magas kontrasztos
    módot is követ). Futásidőben hívódik, mert a wx.SystemSettings csak a
    wx.App létrejötte után megbízhatóan használható."""
    def sc(index):
        return wx.SystemSettings.GetColour(index)

    return {
        "name": "Rendszer (Windows színek)",
        "panel_bg": sc(wx.SYS_COLOUR_BTNFACE),
        "text_fg": sc(wx.SYS_COLOUR_WINDOWTEXT),
        "ctrl_bg": sc(wx.SYS_COLOUR_WINDOW),
        "ctrl_fg": sc(wx.SYS_COLOUR_WINDOWTEXT),
        "btn_bg": sc(wx.SYS_COLOUR_BTNFACE),
        "btn_fg": sc(wx.SYS_COLOUR_BTNTEXT),
        "header_bg": sc(wx.SYS_COLOUR_BTNFACE),
        "header_fg": sc(wx.SYS_COLOUR_BTNTEXT),
    }


def _get_theme(theme_name):
    """Visszaadja a téma szótárát; a 'rendszer' témát futásidőben állítja elő."""
    if theme_name == "rendszer":
        return _rendszer_tema()
    return THEMES.get(theme_name, THEMES["vilagos"])


def get_theme_names():
    """Visszaadja a témák belső kulcsait és megjelenítendő neveit a beállításokhoz."""
    return [(key, data["name"]) for key, data in THEMES.items()]

def apply_theme(window, theme_name="vilagos"):
    """Rekurzívan alkalmazza a kiválasztott témát az ablakra és elemeire.

    A színezés közben az ablak le van fagyasztva (Freeze/Thaw), az újrarajzolás
    és az elrendezés-számítás (Refresh/Layout) pedig csak egyszer, a legfelső
    szinten fut le. Korábban minden rekurziós szinten külön lefutott, ami
    beágyazott panelek esetén sokszoros, észrevehető késlekedést okozott.
    """
    theme = _get_theme(theme_name)
    window.Freeze()
    try:
        _apply_theme_rekurziv(window, theme)
    finally:
        window.Thaw()
    window.Refresh()
    window.Layout()


def _apply_theme_rekurziv(window, theme):
    """Az apply_theme belső, rekurzív része (Refresh/Layout nélkül)."""
    # Ha a főablak/dialógus maga is színezhető
    if hasattr(window, "SetBackgroundColour"):
        window.SetBackgroundColour(theme["panel_bg"])

    for child in window.GetChildren():
        # A wx.ScrolledWindow NEM wx.Panel leszármazott, ezért enélkül a
        # kifejezett kezelés nélkül a görgethető területek (pl. a
        # BeallitasokDialog oszlopválasztó füle, a KonyvSzerkesztoDialog
        # mezőrácsa) mindig az alapértelmezett (világos) hátteret tartották
        # meg, míg a bennük lévő vezérlők már a téma színét kapták - foltos,
        # a témával inkonzisztens megjelenést eredményezve.
        if isinstance(child, (wx.Panel, wx.ScrolledWindow)):
            child.SetBackgroundColour(theme["panel_bg"])
        elif isinstance(child, (wx.TextCtrl, wx.ComboBox, wx.ListBox, wx.Choice, wx.SearchCtrl)):
            child.SetBackgroundColour(theme["ctrl_bg"])
            child.SetForegroundColour(theme["ctrl_fg"])
        elif isinstance(child, wx.ListCtrl):
            child.SetBackgroundColour(theme["ctrl_bg"])
            child.SetForegroundColour(theme["ctrl_fg"])
            
            # Oszlopfejlécek (HeaderCtrl) színezése Windows/wxPython alatt
            try:
                header = child.GetMainWindow().GetParent() if hasattr(child, 'GetMainWindow') else None
                if not header:
                    header = child.GetChildren()[0] if child.GetChildren() else None
                
                if header and isinstance(header, wx.Window):
                    header.SetBackgroundColour(theme["header_bg"])
                    header.SetForegroundColour(theme["header_fg"])
                    header.Refresh()
            except Exception as e:
                logging.debug(f"Fejléc színezési hiba (nem kritikus): {e}")
                
        elif isinstance(child, wx.Button):
            child.SetBackgroundColour(theme["btn_bg"])
            child.SetForegroundColour(theme["btn_fg"])
        elif isinstance(child, wx.StaticText):
            child.SetForegroundColour(theme["text_fg"])
        elif isinstance(child, (wx.CheckBox, wx.RadioButton)):
            # Szándékosan NEM állítunk rajta színt. Az explicit szín Windows
            # alatt owner-drawn (saját rajzolású) vezérlővé alakíthatja az
            # elemet, amit a képernyőolvasók (NVDA) nyomógombként olvasnak
            # fel: elvész a jelölőnégyzet/rádiógomb szerepkör és a
            # "bejelölve" állapot. A natív vezérlő a szülő (panel) háttérszínét
            # örökli, ezért a háttér így is a témához igazodik.
            pass
        
        # Rekurzió a gyermek elemek gyermekeire (pl. sizer-be ágyazott panelek, ablakok)
        if hasattr(child, "GetChildren") and child.GetChildren():
            _apply_theme_rekurziv(child, theme)


def apply_theme_from_settings(window):
    """Betölti a mentett beállításokat, és alkalmazza a bennük tárolt témát
    az ablakra/dialógusra.

    Kényelmi függvény azoknak a - jellemzően dialógus - hívóknak, akiknek
    nincs már betöltött beállítás-szótáruk, és a témát a mentett
    beállításokból kell alkalmazniuk. Korábban ezt a két sort:

        config = load_settings()
        apply_theme(self, config.get("tema", "vilagos"))

    számos dialógus (KonyvReszletekDialog, KonyvSzerkesztoDialog,
    StatisztikaDialog, KeresoDialog, NevjegyDialog, UjdonsagokDialog,
    FajlutkozesDialog, DeziderataReszletekDialog, BaseItemDialog stb.)
    egymástól függetlenül megismételte.

    A betöltött beállítás-szótárral tér vissza, hogy azok a hívók is
    használhassák, akiknek a témán kívül más beállításra (pl. a téma
    kulcsának későbbi eltárolására) is szükségük van.
    """
    config = load_settings()
    apply_theme(window, config.get("tema", "vilagos"))
    return config
