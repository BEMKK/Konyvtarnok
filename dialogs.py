import os
import sys
import logging
import wx
from constants import APP_NAME, APP_VERSION, APP_STAGE
from theme_manager import apply_theme_from_settings
from config_manager import load_settings, save_settings
from export_manager import export_konyv_pdf, get_biztonsagos_pdf_fajlnev

class NevjegyDialog(wx.Dialog):
    """Saját Névjegy párbeszédablak wx.Dialog alapokon."""
    def __init__(self, parent=None):
        super().__init__(parent, title="Névjegy", size=(420, 320), style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        
        sizer = wx.BoxSizer(wx.VERTICAL)

        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

        icon_path = os.path.join(base_dir, "ikon.ico")

        try:
            if os.path.exists(icon_path):
                img = wx.Image(icon_path, wx.BITMAP_TYPE_ANY)
                if img.IsOk():
                    img = img.Scale(80, 80, wx.IMAGE_QUALITY_HIGH)
                    bitmap = wx.Bitmap(img)
                    
                    icon_bitmap = wx.StaticBitmap(self, bitmap=bitmap)
                    sizer.Add(icon_bitmap, 0, wx.ALIGN_CENTER | wx.TOP, 15)
            else:
                logging.warning(f"Névjegy ikon nem található: {icon_path}")
        except Exception as e:
            logging.error(f"Névjegy ikon hiba: {e}")

        cim_label = wx.StaticText(self, label=APP_NAME)
        font = cim_label.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        font.SetPointSize(11)
        cim_label.SetFont(font)
        sizer.Add(cim_label, 0, wx.ALIGN_CENTER | wx.TOP, 20)
        
        verzio_label = wx.StaticText(self, label=f"v{APP_VERSION} {APP_STAGE}".strip())
        sizer.Add(verzio_label, 0, wx.ALIGN_CENTER | wx.TOP, 5)
        
        leiras_label = wx.StaticText(self, label="Akadálymentes könyvkatalógus-kezelő magángyűjtemények számára.")
        sizer.Add(leiras_label, 0, wx.ALIGN_CENTER | wx.ALL, 15)
        
        fejleszto_label = wx.StaticText(self, label="© 2026 KönyvTárnok")
        sizer.Add(fejleszto_label, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)
        
        ok_gomb = wx.Button(self, id=wx.ID_OK, label="OK")
        
        # Téma alkalmazása Realize/Hozzáadás után, de megjelenítés előtt
        apply_theme_from_settings(self)

        sizer.Add(ok_gomb, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)
        
        self.SetSizer(sizer)
        
        self.Centre()

class UjdonsagokDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Újdonságok", size=(460, 360), style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        cim_label = wx.StaticText(self, label="A verzió újdonságai:")
        font_cim = cim_label.GetFont()
        font_cim.SetWeight(wx.FONTWEIGHT_BOLD)
        font_cim.SetPointSize(12)
        cim_label.SetFont(font_cim)
        main_sizer.Add(cim_label, 0, wx.ALIGN_CENTER | wx.TOP, 15)
        
        verzio_label = wx.StaticText(self, label=f"v{APP_VERSION} {APP_STAGE}".strip())
        main_sizer.Add(verzio_label, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 5)        

        main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 15)
        
        ujdonsagok_lista = [
            "Kijelölés menüpont és gomb a KönyvTárnok-keresőben.",
            "Összes oszlop kijelölésére szolgáló jelölőnégyzet a KönyvTárnok-keresőben a kereséshez.",
            "Kijelölés törlése funkció mindhárom modulban."
        ]

        szoveg_box = wx.BoxSizer(wx.VERTICAL)
        bullet_cimkek = []
        for elem in ujdonsagok_lista:
            pont_sizer = wx.BoxSizer(wx.HORIZONTAL)
            bullet = wx.StaticText(self, label="• ")
            bullet_cimkek.append(bullet)
            
            txt = wx.StaticText(self, label=elem)
            txt.Wrap(380)
            
            pont_sizer.Add(bullet, 0, wx.TOP, 1)
            pont_sizer.Add(txt, 1, wx.EXPAND)
            szoveg_box.Add(pont_sizer, 0, wx.EXPAND | wx.BOTTOM, 8)

        main_sizer.Add(szoveg_box, 1, wx.EXPAND | wx.ALL, 20)

        # Gomb elhelyezése
        btn_sizer = wx.StdDialogButtonSizer()
        ok_gomb = wx.Button(self, id=wx.ID_OK, label="OK")
        ok_gomb.SetDefault()
        btn_sizer.AddButton(ok_gomb)
        
        btn_sizer.Realize()
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)
        
        self.SetSizer(main_sizer)

        # A témát az összes widget felépítése UTÁN, de a saját színezés ELŐTT
        # kell alkalmazni: az apply_theme minden StaticText előtérszínét
        # felülírja, így a korábban beállított egyedi színek hatástalanok voltak.
        apply_theme_from_settings(self)
        verzio_label.SetForegroundColour(wx.Colour(120, 120, 120))
        for bullet in bullet_cimkek:
            bullet.SetForegroundColour(wx.Colour(0, 120, 215))
        
        self.Centre()

class FajlutkozesDialog(wx.Dialog):
    def __init__(self, parent, fajlnev):
        super().__init__(parent, title="Fájlütközés", style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        msg = f"A(z) '{fajlnev}' fájl már létezik a célmappában.\nMit szeretne tenni?"
        lbl = wx.StaticText(self, label=msg)
        main_sizer.Add(lbl, 0, wx.ALL, 15)
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        btn_felulir = wx.Button(self, wx.ID_YES, "Felülírás")
        btn_mindent_felulir = wx.Button(self, wx.ID_YESTOALL, "Mindet felülír")
        btn_kihagy = wx.Button(self, wx.ID_NO, "Kihagyás")
        btn_osszes_kihagy = wx.Button(self, wx.ID_CANCEL, "Összes kihagyása")
        
        btn_sizer.Add(btn_felulir, 0, wx.RIGHT, 5)
        btn_sizer.Add(btn_mindent_felulir, 0, wx.RIGHT, 5)
        btn_sizer.Add(btn_kihagy, 0, wx.RIGHT, 5)
        btn_sizer.Add(btn_osszes_kihagy, 0)
        
        main_sizer.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 15)
        
        btn_felulir.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_YES))
        btn_mindent_felulir.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_YESTOALL))
        btn_kihagy.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_NO))
        btn_osszes_kihagy.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        
        apply_theme_from_settings(self)
        
        self.SetSizerAndFit(main_sizer)
        self.CentreOnParent()


def exportal_egy_konyv(szulo_ablak, konyv_adatok):
    """Egy könyv adatlapjának exportálása PDF-be (fájlmentés párbeszéddel).

    A szulo_ablak lehet a főablak vagy egy dialógus is, így a
    fájlválasztó és az üzenetek a hívó ablak fölött jelennek meg.
    Visszatérés: True, ha az exportálás sikeres volt.
    """
    config = load_settings()

    with wx.FileDialog(
        szulo_ablak,
        "Könyvadatlap exportálása",
        defaultDir=config.get("last_pdf_dir", ""),
        defaultFile=get_biztonsagos_pdf_fajlnev(konyv_adatok),
        wildcard="PDF fájl (*.pdf)|*.pdf",
        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
    ) as ment_dlg:
        if ment_dlg.ShowModal() != wx.ID_OK:
            return False
        fajlnev = ment_dlg.GetPath()

    config["last_pdf_dir"] = os.path.dirname(fajlnev)
    save_settings(config)

    try:
        export_konyv_pdf(konyv_adatok, fajlnev)
    except Exception as e:
        logging.error(f"Hiba történt exportálás közben: {e}")
        wx.MessageBox(f"Hiba történt exportálás közben:\n{e}", "Hiba",
                      wx.OK | wx.ICON_ERROR, szulo_ablak)
        return False

    wx.MessageBox("Exportálás sikeres!", "Exportálás",
                  wx.OK | wx.ICON_INFORMATION, szulo_ablak)
    return True
