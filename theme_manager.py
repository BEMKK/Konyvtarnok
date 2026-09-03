import wx

# A témák szótára és definíciói
THEMES = {
    "vilagos": {
        "name": "Világos (Hagyományos)",
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
        "name": "Sötét (Szemkímélő)",
        "panel_bg": wx.Colour(43, 43, 43),
        "text_fg": wx.Colour(220, 220, 220),
        "ctrl_bg": wx.Colour(60, 63, 65),
        "ctrl_fg": wx.Colour(220, 220, 220),
        "btn_bg": wx.Colour(75, 78, 80),
        "btn_fg": wx.Colour(240, 240, 240),
        "header_bg": wx.Colour(50, 53, 55),
        "header_fg": wx.Colour(230, 230, 230),
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
    }
}

def get_theme_names():
    """Visszaadja a témák belső kulcsait és megjelenítendő neveit a beállításokhoz."""
    return [(key, data["name"]) for key, data in THEMES.items()]

def apply_theme(window, theme_name="vilagos"):
    """Rekurzívan alkalmazza a kiválasztott témát az ablakra és elemeire."""
    theme = THEMES.get(theme_name, THEMES["vilagos"])
    
    # Ha a főablak/dialógus maga is színezhető
    if hasattr(window, "SetBackgroundColour"):
        window.SetBackgroundColour(theme["panel_bg"])

    for child in window.GetChildren():
        if isinstance(child, wx.Panel):
            child.SetBackgroundColour(theme["panel_bg"])
        elif isinstance(child, (wx.TextCtrl, wx.ComboBox, wx.ListBox)):
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
            except Exception:
                pass
                
        elif isinstance(child, wx.Button):
            child.SetBackgroundColour(theme["btn_bg"])
            child.SetForegroundColour(theme["btn_fg"])
        elif isinstance(child, wx.StaticText):
            child.SetForegroundColour(theme["text_fg"])
        
        # Rekurzió a gyermek elemek gyermekeire (pl. sizer-be ágyazott panelek, ablakok)
        if hasattr(child, "GetChildren") and child.GetChildren():
            apply_theme(child, theme_name)
            
    window.Refresh()
    window.Layout()
