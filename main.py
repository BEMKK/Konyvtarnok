import os
import sys
import traceback
import logging
import wx
from pathlib import Path
from data_manager import KonyvAdatbazis
from main_frame import KonyvtarApp

def get_resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path

# Segédfüggvény az EXE MELLET lévő mappához (hibanapló, adatbázisok)
def get_exe_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

# =========================================================
# HIBAKEZELŐ BEÁLLÍTÁSA
# =========================================================
# Alapértelmezett beállítás fájlnév nélkül (nem hoz létre fájlt indításkor)
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def custom_excepthook(exctype, value, tb):
    # 1. Csak most, a hiba pillanatában adjuk hozzá a fájlba író handlert!
    log_file = get_exe_dir() / 'hibanaplo.log'
    file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)

    # 2. A teljes hibaleírást stringgé alakítjuk
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    
    # 3. Beírjuk a log fájlba (ekkor jön létre a fájl, ha még nem létezett)
    logging.error("Váratlan hiba történt:\n" + error_msg)
    
    # 4. Eltávolítjuk a handlert, hogy esetleges későbbi hibáknál ne duplázódjon
    logging.getLogger().removeHandler(file_handler)
    file_handler.close()
    
    # Ha a wx felület már fut, felugró ablak a felhasználónak
    if wx.GetApp():
        wx.MessageBox(
            f"Váratlan hiba történt:\n{value}\n\nA hiba részleteit a 'hibanaplo.log' fájlban találja.", 
            "Programhiba", 
            wx.OK | wx.ICON_ERROR
        )

# Regisztráljuk a hibaelkapót
sys.excepthook = custom_excepthook


# =========================================================
# PROGRAM INDÍTÁSA
# =========================================================
if __name__ == '__main__':
    app = wx.App()
    
    # 1. Létrehozzuk az adatbázis objektumot
    adatbazis = KonyvAdatbazis()
    
    # 2. Átadjuk az adatbázist a grafikus felületnek
    frame = KonyvtarApp(adatbazis)
    
    icon_path = get_resource_path("ikon.ico")
    if icon_path.exists():
        icon = wx.Icon(str(icon_path), wx.BITMAP_TYPE_ICO)
        frame.SetIcon(icon)
    else:
        # Hibakereséshez: ha nem találja, kiírja a pontos utat
        logging.warning(f"Az ikon nem található ezen az útvonalon: {icon_path}")

    frame.Show()
    app.MainLoop()