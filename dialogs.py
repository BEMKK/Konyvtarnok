import os
import sys
import json
import logging
from collections import namedtuple
import wx
from config_manager import load_settings, save_settings
from constants import APP_NAME, APP_VERSION
from export_manager import export_konyv_pdf, get_biztonsagos_pdf_fajlnev
from theme_manager import apply_theme_from_settings

def eroforras_utvonal(fajlnev):
    """Csomagolt (PyInstaller) és forrásból futtatott környezetben is megkeresi a fájlt."""
    helyek = [
        getattr(sys, '_MEIPASS', None),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] else None,
    ]
    for hely in helyek:
        if hely:
            ut = os.path.join(hely, fajlnev)
            if os.path.exists(ut):
                return ut
    return None


class LicencDialog(wx.Dialog):
    """Licencinformációk megjelenítése görgethető, csak olvasható mezőben."""
    def __init__(self, parent, szoveg):
        super().__init__(parent, title="Licencszerződés",
                         size=(600, 450),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP)
        self.SetMinSize((420, 300))
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.szoveg_mezo = wx.TextCtrl(self, value=szoveg,
                                       style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(self.szoveg_mezo, 1, wx.EXPAND | wx.ALL, 10)
        ok = wx.Button(self, wx.ID_OK, "&OK")
        ok.SetDefault()
        sizer.Add(ok, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
        self.SetSizer(sizer)
        apply_theme_from_settings(self)
        self.CentreOnParent()
        self.szoveg_mezo.SetFocus()

def licenc_megjelenitese(parent):
    """Betölti a license.txt-t és megjeleníti a licencablakot.
    Névjegy gombból és menüből is ez hívandó."""
    licenc_ut = eroforras_utvonal("license.txt")
    szoveg = None
    if licenc_ut:
        try:
            with open(licenc_ut, "r", encoding="utf-8") as f:
                szoveg = f.read()
        except OSError as e:
            logging.error(f"Licencfájl nem olvasható: {e}")
    else:
        logging.warning("A license.txt nem található.")
    if not szoveg:
        szoveg = ("A licencfájl nem található.\n\n"
                  "A GNU Általános Nyilvános Licenc 3. verziójának teljes szövege itt olvasható:\n"
                  "https://www.gnu.org/licenses/gpl-3.0.html")
    with LicencDialog(parent, szoveg) as dlg:
        dlg.ShowModal()

class NevjegyDialog(wx.Dialog):
    """Saját Névjegy párbeszédablak wx.Dialog alapokon."""
    def __init__(self, parent=None):
        super().__init__(parent, title="Névjegy", size=(420, 320), style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        
        sizer = wx.BoxSizer(wx.VERTICAL)

        icon_path = eroforras_utvonal("ikon.ico")

        try:
            if icon_path:
                img = wx.Image(icon_path, wx.BITMAP_TYPE_ANY)
                if img.IsOk():
                    img = img.Scale(80, 80, wx.IMAGE_QUALITY_HIGH)
                    bitmap = wx.Bitmap(img)
                    
                    icon_bitmap = wx.StaticBitmap(self, bitmap=bitmap)
                    sizer.Add(icon_bitmap, 0, wx.ALIGN_CENTER | wx.TOP, 15)
            else:
                logging.warning("Névjegy ikon nem található: ikon.ico")
        except Exception as e:
            logging.error(f"Névjegy ikon hiba: {e}")

        cim_label = wx.StaticText(self, label=APP_NAME)
        font = cim_label.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        font.SetPointSize(11)
        cim_label.SetFont(font)
        sizer.Add(cim_label, 0, wx.ALIGN_CENTER | wx.TOP, 20)
        
        leiras_label = wx.StaticText(self, label="Akadálymentes könyvkatalógus-kezelő magángyűjtemények számára.")
        sizer.Add(leiras_label, 0, wx.ALIGN_CENTER | wx.ALL, 15)

        verzio_label = wx.StaticText(self, label=f"Verzió: {APP_VERSION}".strip())
        sizer.Add(verzio_label, 0, wx.ALIGN_CENTER | wx.TOP, 15)
                
        fejleszto_label = wx.StaticText(self, label="© 2026 Bemkk")
        sizer.Add(fejleszto_label, 0, wx.ALIGN_CENTER | wx.BOTTOM, 4)
        
        licenc_label = wx.StaticText(
            self,
            label=("A KönyvTárnok nyílt forráskódú szoftver, a Free Software Foundation által "
                   "közzétett GNU General Public License 3.0 feltételei "
                   "szerint terjeszthető és módosítható. A program szavatosság nélkül "
                   "kerül terjesztésre.")
        )
        licenc_label.Wrap(380)
        sizer.Add(licenc_label, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        ok_gomb = wx.Button(self, id=wx.ID_OK, label="&OK")
        ok_gomb.SetDefault()
        licenc_gomb = wx.Button(self, label="&Licencszerződés")
        licenc_gomb.Bind(wx.EVT_BUTTON, self.on_licenc)

        gomb_sizer = wx.BoxSizer(wx.HORIZONTAL)
        gomb_sizer.Add(ok_gomb, 0, wx.RIGHT, 8)
        gomb_sizer.Add(licenc_gomb, 0)
        sizer.Add(gomb_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 20)

        # Téma alkalmazása a widgetek felépítése után, de megjelenítés előtt
        apply_theme_from_settings(self)

        self.SetSizerAndFit(sizer)
        self.Centre()

    def on_licenc(self, event):
        licenc_megjelenitese(self)

class UjdonsagokDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Újdonságok", size=(480, 1), style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        cim_label = wx.StaticText(self, label="A verzió főbb újdonságai:")
        font_cim = cim_label.GetFont()
        font_cim.SetWeight(wx.FONTWEIGHT_BOLD)
        font_cim.SetPointSize(12)
        cim_label.SetFont(font_cim)
        main_sizer.Add(cim_label, 0, wx.ALIGN_CENTER | wx.TOP, 15)
        
        verzio_label = wx.StaticText(self, label=F"{APP_VERSION}".strip())
        main_sizer.Add(verzio_label, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 5)        

        main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 15)
        
        ujdonsagok_lista = [
            "A KönyvTárnok-keresőben javítva a lista címkéjének felolvasási hibája szűrés esetén.",
            "Ugyanitt egységesítve és javítva a státuszsor szövege.",
            "Kisebb kódjavítások, nem használt importok és kódok, függőségek törlése.",
            "Frissítés a súgóban és a readme.md fájlban."
        ]

        szoveg_box = wx.BoxSizer(wx.VERTICAL)
        bullet_cimkek = []
        for elem in ujdonsagok_lista:
            pont_sizer = wx.BoxSizer(wx.HORIZONTAL)
            bullet = wx.StaticText(self, label="• ")
            bullet_cimkek.append(bullet)
            
            txt = wx.StaticText(self, label=elem)
            txt.Wrap(400)
            
            pont_sizer.Add(bullet, 0, wx.TOP, 1)
            pont_sizer.Add(txt, 1, wx.EXPAND)
            szoveg_box.Add(pont_sizer, 0, wx.EXPAND | wx.BOTTOM, 8)

        main_sizer.Add(szoveg_box, 1, wx.EXPAND | wx.ALL, 20)

        # Gomb elhelyezése
        btn_sizer = wx.StdDialogButtonSizer()
        ok_gomb = wx.Button(self, id=wx.ID_OK, label="&OK")
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
        main_sizer.Fit(self)
        self.Centre()

class FajlutkozesDialog(wx.Dialog):
    def __init__(self, parent, fajlnev, hatralevo_utkozesek=1, osszes_utkozes=1):
        super().__init__(parent, title="Fájlütközés", style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        msg = f"A(z) '{fajlnev}' fájl már létezik a célmappában.\nMit szeretne tenni?"
        lbl = wx.StaticText(self, label=msg)
        main_sizer.Add(lbl, 0, wx.ALL, 15)
        
        if hatralevo_utkozesek > 1:
            if hatralevo_utkozesek == osszes_utkozes:
                cb_label = f"Legyen érvényes az összes ütközésnél (összesen {osszes_utkozes} db)"
            else:
                cb_label = f"Legyen érvényes az összes hátralévő ütközésnél (még {hatralevo_utkozesek} db)"
        else:
            cb_label = "Legyen érvényes az összes ütközésnél (1 db)"

        self.chk_mindre = wx.CheckBox(self, label=cb_label)
        main_sizer.Add(self.chk_mindre, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        btn_felulir = wx.Button(self, wx.ID_YES, "Felülírás")
        btn_kihagy = wx.Button(self, wx.ID_NO, "Kihagyás")
        btn_megse = wx.Button(self, wx.ID_CANCEL, "Mégse")
        
        btn_sizer.Add(btn_felulir, 0, wx.RIGHT, 8)
        btn_sizer.Add(btn_kihagy, 0, wx.RIGHT, 8)
        btn_sizer.Add(btn_megse, 0)
        
        main_sizer.Add(btn_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 15)
        
        btn_felulir.Bind(wx.EVT_BUTTON, self._on_felulir)
        btn_kihagy.Bind(wx.EVT_BUTTON, self._on_kihagy)
        btn_megse.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        self.Bind(wx.EVT_CLOSE, lambda e: self.EndModal(wx.ID_CANCEL))
        self.SetEscapeId(wx.ID_CANCEL)
        
        apply_theme_from_settings(self)
        
        self.SetSizerAndFit(main_sizer)
        self.CentreOnParent()

    def _on_felulir(self, event):
        if self.chk_mindre.GetValue():
            self.EndModal(wx.ID_YESTOALL)
        else:
            self.EndModal(wx.ID_YES)

    def _on_kihagy(self, event):
        if self.chk_mindre.GetValue():
            self.EndModal(wx.ID_NOTOALL)
        else:
            self.EndModal(wx.ID_NO)


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


class JsonImportValasztoDialog(wx.Dialog):
    """Párbeszédablak a JSON fájlból importálandó könyvek/tételek kiválasztásához
    és a hiányzó adatok összefésüléséhez."""

    def __init__(
        self,
        parent,
        uj_tetelek=None,
        kiegeszitheto_tetelek=None,
        cim="Importálandó könyvek kiválasztása",
        fejlec="Válassza ki az új vagy kiegészítendő köteteket az importáláshoz:",
        muvelet_uj="Új könyv",
    ):
        super().__init__(
            parent,
            title=cim,
            size=(850, 520),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP,
        )
        self.SetMinSize((650, 380))

        self.uj_tetelek = uj_tetelek or []
        self.kiegeszitheto_tetelek = kiegeszitheto_tetelek or []
        self.muvelet_uj = muvelet_uj

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Magyarázó fejléc
        info_label = wx.StaticText(
            self,
            label=fejlec,
        )
        main_sizer.Add(info_label, 0, wx.ALL, 12)

        # Gyorsgombok
        btn_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_mindent = wx.Button(self, label="Mindet kijelöl")
        self.btn_semmit = wx.Button(self, label="Kijelölés törlése")
        btn_box.Add(self.btn_mindent, 0, wx.RIGHT, 6)
        btn_box.Add(self.btn_semmit, 0, wx.RIGHT, 10)

        self.btn_csak_ujak = None
        self.btn_csak_kieg = None
        if self.uj_tetelek and self.kiegeszitheto_tetelek:
            uj_felirat = f"Csak új tételek ({len(self.uj_tetelek)})" if muvelet_uj != "Új könyv" else f"Csak új könyvek ({len(self.uj_tetelek)})"
            self.btn_csak_ujak = wx.Button(self, label=uj_felirat)
            self.btn_csak_kieg = wx.Button(self, label=f"Csak adatpótlások ({len(self.kiegeszitheto_tetelek)})")
            btn_box.Add(self.btn_csak_ujak, 0, wx.RIGHT, 6)
            btn_box.Add(self.btn_csak_kieg, 0)

        main_sizer.Add(btn_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Lista vezérlő
        self.lista = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SINGLE_SEL | wx.LC_HRULES | wx.LC_VRULES
        )
        self.lista.EnableCheckBoxes()

        self.lista.InsertColumn(0, "Cím", width=250)
        self.lista.InsertColumn(1, "Szerző", width=170)
        self.lista.InsertColumn(2, "Művelet", width=130)
        self.lista.InsertColumn(3, "Részletek / Új adatok", width=260)

        # Elemek feltöltése:
        self.uj_sorok = {}  # list_row_idx -> uj_tetelek index
        self.kiegeszitheto_sorok = {}  # list_row_idx -> kiegeszitheto_tetelek index

        sor_idx = 0

        # 1. Új könyvek / tételek
        for idx, ujkonyv in enumerate(self.uj_tetelek):
            cim_str = str(ujkonyv.get("cim", "") or "")
            szerzo = str(ujkonyv.get("szerzo", "") or "")
            kiado = str(ujkonyv.get("kiado", "") or "")
            ev = str(ujkonyv.get("ev", "") or "")
            reszlet = f"{kiado} ({ev})".strip(" ()") if (kiado or ev) else ""

            row = self.lista.InsertItem(sor_idx, cim_str)
            self.lista.SetItem(row, 1, szerzo)
            self.lista.SetItem(row, 2, self.muvelet_uj)
            self.lista.SetItem(row, 3, reszlet)
            self.lista.CheckItem(row, True)

            self.uj_sorok[row] = idx
            sor_idx += 1

        # 2. Kiegészíthető könyvek
        for idx, kieg in enumerate(self.kiegeszitheto_tetelek):
            meglevo = kieg["meglevo"]
            cim = str(meglevo.get("cim", "") or "")
            szerzo = str(meglevo.get("szerzo", "") or "")
            leiras = kieg.get("leiras", "")

            row = self.lista.InsertItem(sor_idx, cim)
            self.lista.SetItem(row, 1, szerzo)
            self.lista.SetItem(row, 2, "Adatpótlás")
            self.lista.SetItem(row, 3, leiras)
            self.lista.CheckItem(row, True)

            self.kiegeszitheto_sorok[row] = idx
            sor_idx += 1

        main_sizer.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Alsó gombok (Importálás, Mégse)
        alsogombok_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_import = wx.Button(self, wx.ID_OK, label="Importálás")
        self.btn_import.SetDefault()
        self.btn_megse = wx.Button(self, wx.ID_CANCEL, label="Mégse")

        alsogombok_sizer.Add(self.btn_import, 0, wx.RIGHT, 10)
        alsogombok_sizer.Add(self.btn_megse, 0)

        main_sizer.Add(alsogombok_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 12)

        self.SetSizer(main_sizer)

        # Eseménykezelők
        self.btn_mindent.Bind(wx.EVT_BUTTON, self.on_mindent_kijelol)
        self.btn_semmit.Bind(wx.EVT_BUTTON, self.on_kijeloles_torlese)
        if self.btn_csak_ujak:
            self.btn_csak_ujak.Bind(wx.EVT_BUTTON, self.on_csak_ujak)
        if self.btn_csak_kieg:
            self.btn_csak_kieg.Bind(wx.EVT_BUTTON, self.on_csak_kieg)
        self.btn_import.Bind(wx.EVT_BUTTON, self.on_import)

        apply_theme_from_settings(self)
        self.CentreOnParent()

        # Fókusz azonnali áthelyezése a listára
        self.lista.SetFocus()
        wx.CallAfter(self.lista.SetFocus)

    def on_mindent_kijelol(self, event):
        for i in range(self.lista.GetItemCount()):
            self.lista.CheckItem(i, True)

    def on_kijeloles_torlese(self, event):
        for i in range(self.lista.GetItemCount()):
            self.lista.CheckItem(i, False)

    def on_csak_ujak(self, event):
        for i in range(self.lista.GetItemCount()):
            self.lista.CheckItem(i, i in self.uj_sorok)

    def on_csak_kieg(self, event):
        for i in range(self.lista.GetItemCount()):
            self.lista.CheckItem(i, i in self.kiegeszitheto_sorok)

    def on_import(self, event):
        ujak = self.get_kivalasztott_uj_konyvek()
        kieg = self.get_kivalasztott_kiegeszitesek()
        if not ujak and not kieg:
            wx.MessageBox(
                "Nincs kijelölve egyetlen tétel sem az importáláshoz vagy adatpótláshoz!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return
        self.EndModal(wx.ID_OK)

    def get_kivalasztott_uj_konyvek(self):
        valasztott = []
        for row_idx, tetel_idx in self.uj_sorok.items():
            if self.lista.IsItemChecked(row_idx):
                valasztott.append(self.uj_tetelek[tetel_idx])
        return valasztott

    def get_kivalasztott_kiegeszitesek(self):
        valasztott = []
        for row_idx, tetel_idx in self.kiegeszitheto_sorok.items():
            if self.lista.IsItemChecked(row_idx):
                valasztott.append(self.kiegeszitheto_tetelek[tetel_idx])
        return valasztott


# ==============================================================================
# KÖZÖS "JSON IMPORT" ELŐKÉSZÍTÉS (főablak és Dezideráta-kezelő)
# ==============================================================================
# A fájlválasztás, a beolvasás, a "lista-e" ellenőrzés, az üres eredmény
# üzenete és a választó párbeszédablak felépítése korábban a főablak
# OnJsonImport és a Dezideráta-kezelő on_import_json függvényében
# egymástól függetlenül, szinte szó szerint megegyező formában szerepelt.
# A tényleges felvétel/kiegészítés a két helyen eltér, ezért az itt marad.
def json_lista_betoltese(parent, konfig_kulcs, ablakcim):
    """JSON fájl kiválasztása és beolvasása (listát vár).

    konfig_kulcs: a beállításokban az utoljára használt mappa kulcsa.
    A hibákat maga jeleníti meg. Megszakításnál vagy hibánál None-t ad.
    """
    config = load_settings()
    with wx.FileDialog(
        parent,
        message=ablakcim,
        defaultDir=config.get(konfig_kulcs, ""),
        wildcard="JSON fájl (*.json)|*.json",
        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
    ) as megnyit_dlg:
        if megnyit_dlg.ShowModal() != wx.ID_OK:
            return None
        utvonal = megnyit_dlg.GetPath()

    config[konfig_kulcs] = os.path.dirname(utvonal)
    save_settings(config)

    try:
        with open(utvonal, "r", encoding="utf-8") as f:
            importalt_adatok = json.load(f)
    except Exception as e:
        wx.MessageBox(
            f"Hiba a JSON fájl beolvasásakor vagy értelmezésekor:\n{e}",
            "Fájl olvasási hiba",
            wx.OK | wx.ICON_ERROR,
            parent,
        )
        return None

    if not isinstance(importalt_adatok, list):
        wx.MessageBox(
            "A kiválasztott JSON fájl formátuma nem megfelelő (listát várunk)!",
            "Hiba",
            wx.OK | wx.ICON_ERROR,
            parent,
        )
        return None
    return importalt_adatok


ImportValasztas = namedtuple("ImportValasztas", "uj_tetelek kiegeszitesek osszes_kihagyva")


def json_import_valasztas(
    parent, uj_tetelek, kiegeszitheto_tetelek, kihagyott_duplum_db, nincs_uzenet,
    **dialog_kwargs,
):
    """Az elemez_json_import eredményének megjelenítése és a felhasználó
    választásának bekérése.

    nincs_uzenet: az üzenet, ha nincs sem új, sem kiegészíthető tétel.
    dialog_kwargs: a JsonImportValasztoDialog további paraméterei (cim,
    fejlec, muvelet_uj).

    None-t ad, ha nincs mit importálni, a felhasználó megszakította, vagy
    semmit sem választott ki. Egyébként ImportValasztas(uj_tetelek,
    kiegeszitesek, osszes_kihagyva): a kiválasztott új tételek, a
    kiválasztott kiegészítések, és a kihagyott tételek eddigi száma (a
    nem kiválasztottak és a már létező duplikátumok).
    """
    if not uj_tetelek and not kiegeszitheto_tetelek:
        uzenet = nincs_uzenet
        if kihagyott_duplum_db > 0:
            uzenet += f"\n\nKihagyva (már létező duplikátum): {kihagyott_duplum_db} db"
        wx.MessageBox(uzenet, "Importálás", wx.OK | wx.ICON_INFORMATION, parent)
        return None

    dlg = JsonImportValasztoDialog(
        parent,
        uj_tetelek=uj_tetelek,
        kiegeszitheto_tetelek=kiegeszitheto_tetelek,
        **dialog_kwargs,
    )
    try:
        if dlg.ShowModal() != wx.ID_OK:
            return None
        kivalasztott_ujak = dlg.get_kivalasztott_uj_konyvek()
        kivalasztott_kiegeszitesek = dlg.get_kivalasztott_kiegeszitesek()
    finally:
        dlg.Destroy()

    if not kivalasztott_ujak and not kivalasztott_kiegeszitesek:
        return None

    osszes_kihagyva = (
        (len(uj_tetelek) - len(kivalasztott_ujak))
        + (len(kiegeszitheto_tetelek) - len(kivalasztott_kiegeszitesek))
        + kihagyott_duplum_db
    )
    return ImportValasztas(kivalasztott_ujak, kivalasztott_kiegeszitesek, osszes_kihagyva)
