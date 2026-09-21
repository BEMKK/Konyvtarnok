import sys
import os
import subprocess
import platform
import traceback
import logging
import wx
from pathlib import Path
from data_manager import KonyvAdatbazis
from main_frame import Konyvtarnok

# Segédfüggvény az EXE MELLET lévő mappához (hibanapló, adatbázisok)
def get_exe_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


# =========================================================
# EGYÉNI HIBAABLAK (vágólapra másolás / napló megnyitása gombokkal)
# =========================================================
class HibaAblak(wx.Dialog):
    def __init__(self, parent, message, log_path):
        super().__init__(
            parent, title="Programhiba",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.message = message
        self.log_path = log_path

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Ikon + rövid szöveg felül
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        icon = wx.StaticBitmap(
            panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_ERROR, wx.ART_MESSAGE_BOX)
        )
        top_sizer.Add(icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        top_sizer.Add(
            wx.StaticText(panel, label="Váratlan hiba történt:"),
            0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10
        )
        vbox.Add(top_sizer, 0)

        # A hiba részletes szövege (görgethető, csak olvasható)
        text_ctrl = wx.TextCtrl(
            panel, value=message,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
            size=(500, 200)
        )
        vbox.Add(text_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Gombsor
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        copy_btn = wx.Button(panel, label="Hibaüzenet másolása")
        open_btn = wx.Button(panel, label="Napló megnyitása")
        ok_btn = wx.Button(panel, wx.ID_OK, label="OK")

        copy_btn.Bind(wx.EVT_BUTTON, self.on_copy)
        open_btn.Bind(wx.EVT_BUTTON, self.on_open)

        btn_sizer.Add(copy_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(open_btn, 0, wx.RIGHT, 5)
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(ok_btn, 0)

        vbox.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(vbox)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)
        self.SetSize((550, 400))
        ok_btn.SetDefault()

    def on_copy(self, event):
        sikeres = False
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self.message))
            wx.TheClipboard.Flush()  # Biztosítja, hogy az adatok a program bezárása után is a rendszer-vágólapon maradjanak
            wx.TheClipboard.Close()
            sikeres = True
        else:
            sikeres = self._masolas_win32_vagolapra(self.message)

        if sikeres:
            copy_btn = event.GetEventObject()
            eredeti = copy_btn.GetLabel()
            copy_btn.SetLabel("Kimásolva a vágólapra")
            
            def reset_label():
                try:
                    if copy_btn and bool(copy_btn):
                        copy_btn.SetLabel(eredeti)
                except (RuntimeError, Exception):
                    pass

            wx.CallLater(1500, reset_label)
        else:
            wx.MessageBox(
                "Nem sikerült megnyitni a vágólapot.",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )

    def _masolas_win32_vagolapra(self, szoveg):
        """Windows API segítségével másol a vágólapra (biztonsági tartalék)."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            GMEM_MOVEABLE = 0x0002
            CF_UNICODETEXT = 13

            if user32.OpenClipboard(None):
                user32.EmptyClipboard()
                encoded = szoveg.encode('utf-16le') + b'\x00\x00'
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
                if h_mem:
                    p_mem = kernel32.GlobalLock(h_mem)
                    ctypes.memmove(p_mem, encoded, len(encoded))
                    kernel32.GlobalUnlock(h_mem)
                    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                user32.CloseClipboard()
                return True
        except Exception as e:
            logging.error(f"Win32 vágólap másolási hiba: {e}")
        return False

    def on_open(self, event):
        try:
            rendszer = platform.system()
            if rendszer == 'Windows':
                os.startfile(str(self.log_path))
            elif rendszer == 'Darwin':
                subprocess.run(['open', str(self.log_path)], check=True)
            else:
                subprocess.run(['xdg-open', str(self.log_path)], check=True)
        except Exception as e:
            wx.MessageBox(
                f"Nem sikerült megnyitni a napló fájlt:\n{e}",
                "Hiba", wx.OK | wx.ICON_ERROR
            )

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
    logging.error("Váratlan hiba történt.\n" + error_msg)
    
    # 4. Eltávolítjuk a handlert, hogy esetleges későbbi hibáknál ne duplázódjon
    logging.getLogger().removeHandler(file_handler)
    file_handler.close()
    
    # Ha a wx felület már fut, felugró ablak a felhasználónak
    if wx.GetApp():
        dlg = HibaAblak(None, error_msg, log_file)
        dlg.ShowModal()
        dlg.Destroy()

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
    frame = Konyvtarnok(adatbazis)

    # Engedélyezd az alábbi sorokat a logging teszteléséhez:
    # try:
        # 1 / 0
    # except Exception:
        # sys.excepthook(*sys.exc_info())
    frame.Show()
    app.MainLoop()