import json
import locale
import logging
import os
import uuid
import webbrowser
import wx
from config_manager import load_settings, save_settings
from theme_manager import apply_theme_from_settings
from data_manager import (
    load_hmac_json,
    save_hmac_json,
    tetelek_egyeznek,
    additiv_lista_import,
    konyvek_tomeges_felvetele,
    kerj_tomeges_atemeles_megerositest,
    mutass_tomeges_atemeles_eredmenyt,
    DEZIDERATA_MEZO_ALIASOK,
    allomany_rekord_dezideratabol,
    is_same_book,
    MentesiHiba,
)
from konyvdialogs import (
    DEZIDERATA_MEZO_DEFINICIOK,
    DeziderataReszletekDialog,
    AddItemDialog,
    EditItemDialog,
)
from gyors_kereses import GyorsListaKereso, osszes_kijelolt_index
from export_manager import katalogus_mentese
from menu_bar import DeziderataMenuBar
from undo_manager import (
    UndoRegiszter, UndoKezelo, ListaTarolo, rekordlista_masolata, frissit_undo_menu,
)
# A magyar_rendezesi_kulcs és az alkalmazas_alapmappa az utils.py-ba
# kerültek át: tisztán szövegfeldolgozó, illetve az alkalmazás mappáját
# meghatározó, wx-től független logika (utóbbit korábban a
# config_manager.py, a data_manager.py, a deziderata.py és a main.py is
# egymástól függetlenül, szó szerint megegyező formában tartalmazta).
from utils import magyar_rendezesi_kulcs, alkalmazas_alapmappa, masolas_vagolapra_szoveg

# Magyar locale beállítása
try:
    locale.setlocale(locale.LC_ALL, "hu_HU.UTF-8")
except Exception:
    try:
        locale.setlocale(locale.LC_ALL, "hu_HU")
    except Exception as e:
        logging.debug(f"Magyar locale beállítása nem sikerült: {e}")

APP_NAME = "KönyvTárnok Dezideráta-kezelő"
BASE_DIR = alkalmazas_alapmappa()
DATA_FILE = os.path.join(BASE_DIR, "deziderata.json")

# A lista (és a katalóguslap) oszlopai: kulcsok sorrendben. A feliratok a
# DEZIDERATA_MEZO_DEFINICIOK-ból jönnek (lásd katalogus_oszlop_definiciok).
LISTA_OSZLOP_KULCSOK = [
    "cim", "szerzo", "egyeb_szemelyek", "kiado",
    "hely", "ev", "priority", "status",
]
# kulcs: (alap szélesség pixelben, kitöltési súly átméretezéskor).
# Ugyanazt a felépítést követi, mint a főlista constants.OSZLOP_DEFINICIOK /
# OSZLOP_SULYOK párosa: az alap szélesség az ablak oszlopainak kiindulási
# szélessége ÉS a PDF-katalóguslap oszlopainak aránya is (a katalogus_pdf
# a defs értékeit egymáshoz viszonyítva használja), a súly pedig azt adja
# meg, hogy az ablak átméretezésekor a többletszélességből mekkora részt kap.
LISTA_OSZLOP_ADATOK = {
    "cim":             (200, 3.0),
    "szerzo":          (130, 2.0),
    "egyeb_szemelyek": (120, 2.0),
    "kiado":           (140, 2.0),
    "hely":            (100, 1.0),
    "ev":              ( 80, 0.5),
    "priority":        ( 85, 0.8),
    "status":          (130, 1.5),
}
# A régi (angol kulcsos) rekordok kezelése
_REGI_KULCSOK = {"cim": "title", "szerzo": "author", "kiado": "publisher",
                 "hely": "place", "ev": "year"}


def katalogus_oszlop_definiciok():
    """{kulcs: (felirat, alap szélesség)} a katalogus_pdf számára (a főlista
    OSZLOP_DEFINICIOK-jával azonos alakban); a feliratok a
    DEZIDERATA_MEZO_DEFINICIOK-ból származnak (kettőspont nélkül)."""
    feliratok = dict(DEZIDERATA_MEZO_DEFINICIOK)
    return {k: (feliratok[k].rstrip(":"), LISTA_OSZLOP_ADATOK[k][0])
            for k in LISTA_OSZLOP_KULCSOK}


def lista_ertek(item, kulcs):
    """Egy tétel mezőjének megjelenítendő szövege (régi kulcsokra is visszaesve)."""
    return str(item.get(kulcs, item.get(_REGI_KULCSOK.get(kulcs, kulcs), "")) or "")

def uj_tetel_id():
    """Új, egyedi azonosító egy dezideráta-tételnek. A tételeket - a főlista
    könyveihez (KonyvListaCtrl.sor_id_terkep) hasonlóan - ez az "id" mező
    azonosítja, nem a listabeli sorindexük vagy a mezőik egyezése."""
    return str(uuid.uuid4())  # ugyanaz a formátum, mint a KonyvAdatbazis-ban


def tetelek_idjainak_potlasa(tetelek):
    """Minden dict tételnek egyedi "id"-t ad, ha még nincs neki (régi fájl,
    a KönyvTárnok-kereső által beszúrt tétel, JSON import), illetve ha az id
    egy korábbi tételével ütközik. True-t ad, ha módosított valamit."""
    latott = set()
    valtozott = False
    for item in tetelek:
        if not isinstance(item, dict):
            continue
        tetel_id = item.get("id")
        if not tetel_id or tetel_id in latott:
            tetel_id = uj_tetel_id()
            item["id"] = tetel_id
            valtozott = True
        latott.add(tetel_id)
    return valtozott


def deziderata_tetelek_hozzaadasa(lista, uj_tetelek):
    """Duplikátum-szűrten, egyedi id-vel hozzáfűzi az uj_tetelek elemeit a
    lista végéhez. Közös a nyitott Dezideráta-kezelő (Deziderata.
    tetelek_felvetele) és a KönyvTárnok-kereső zárt ablakos ága számára.

    Visszatérés: (sikeres_db, visszautasitott_db, felvett_tetelek). A cím
    nélküli tételeket szó nélkül kihagyja (sem sikeres, sem visszautasított)."""
    sikeres = 0
    visszautasitott = 0
    felvett = []
    for tetel in uj_tetelek:
        if not str(lista_ertek(tetel, "cim")).strip():
            continue
        if any(is_same_book(tetel, meglevo) for meglevo in lista
               if isinstance(meglevo, dict)):
            visszautasitott += 1
            continue
        uj = dict(tetel)
        uj["id"] = uj_tetel_id()
        lista.append(uj)
        felvett.append(uj)
        sikeres += 1
    return sikeres, visszautasitott, felvett


# ==============================================================================
# VISSZAVONÁS-TÁROLÓK (lásd undo_manager.py)
# ==============================================================================
class DeziderataTarolo(ListaTarolo):
    """A NYITOTT Dezideráta-ablak tétellistájának undo-tárolója."""

    def __init__(self, frame):
        self.frame = frame

    def lista(self):
        return self.frame.items

    def masolat(self):
        # Betöltési hiba miatt letiltott állapotban az items üres, a lemezen
        # lévő adat viszont nem: ilyenkor nem rögzítünk lépést.
        if self.frame._mentes_tiltva:
            return None
        return super().masolat()

    def mentes(self):
        return self.frame.save_data()

    def frissit(self, valtozas, kijelol):
        self.frame.refresh_list()
        if kijelol:
            self.frame._kijelol_idk(valtozas.erintett_idk())


class DeziderataFajlTarolo(ListaTarolo):
    """A ZÁRT Dezideráta-jegyzék undo-tárolója: a deziderata.json-t közvetlenül,
    HMAC-ellenőrzéssel olvassa és írja (ugyanúgy, mint a KönyvTárnok-kereső
    zárt ablakos átemelése)."""

    def __init__(self, frissito=None):
        self._frissito = frissito
        self._adat = None

    @staticmethod
    def _betolt():
        adat, ervenyes = load_hmac_json(DATA_FILE)
        if not ervenyes:
            raise ValueError("A dezideráta-fájl HMAC-aláírása érvénytelen.")
        return [x for x in adat if isinstance(x, dict)] if isinstance(adat, list) else []

    def masolat(self):
        try:
            lista = self._betolt()
        except Exception:
            logging.error("A dezideráta-fájl nem olvasható az undo-hoz.", exc_info=True)
            return None
        # A régi, id nélküli tételek id-it itt véglegesítjük, különben a
        # lépés előtti és utáni állapot id-ei nem lennének összevethetők.
        if tetelek_idjainak_potlasa(lista) and not save_hmac_json(DATA_FILE, lista):
            return None
        return rekordlista_masolata(lista)

    def lista(self):
        self._adat = self._betolt()
        tetelek_idjainak_potlasa(self._adat)
        return self._adat

    def mentes(self):
        return save_hmac_json(DATA_FILE, self._adat)

    def frissit(self, valtozas, kijelol):
        if self._frissito is not None:
            self._frissito()


# ==============================================================================
# FŐABLAK ÉS ALKALMAZÁS LOGIKA
# ==============================================================================


class Deziderata(wx.Frame):
    def __init__(self, parent=None):
        super().__init__(parent, title=f"{APP_NAME}", size=(1050, 500))

        # Adatmodell: a tételek listája (szótárakból álló listaként)
        self.items = []

        # sorindex -> tétel id (a főlista KonyvListaCtrl.sor_id_terkep-jének
        # megfelelője); a refresh_list építi újra minden frissítéskor.
        self.sor_id_terkep = {}

        # Visszavonás/mégis (lásd undo_manager.py). Ha a főablak gyermeke
        # vagyunk, annak adatbázisával közös regisztert használunk: az
        # állományba átemelés így EGY, mindkét oldalt érintő lépés, amely
        # bármelyik ablakból visszavonható. Önállóan futva saját regiszter.
        szulo_db = getattr(parent, "db", None)
        onallo = not hasattr(szulo_db, "undo_regiszter")
        regiszter = UndoRegiszter() if onallo else szulo_db.undo_regiszter
        self.undo_tarolo = DeziderataTarolo(self)
        if onallo:
            regiszter.tarolo_regisztral("deziderata", lambda: self.undo_tarolo)
        self.undo = UndoKezelo(regiszter, ["deziderata"], elsodleges=onallo)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # True, ha a deziderata.json betöltése nem sikerült (olvasási hiba,
        # ismeretlen formátum vagy érvénytelen HMAC-aláírás). Ilyenkor az
        # items üres, a lemezen viszont lehet (sérült, de megmenthető) adat,
        # ezért a szerkesztés és a mentés le van tiltva: különben az első
        # új tétel felvétele a fájl tartalmát az egyetlen új tétellel írná felül.
        self._mentes_tiltva = False

        self.statusbar = self.CreateStatusBar()

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # --- Gombok ---
        btn_box = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_add = wx.Button(panel, label="Új tétel")
        self.btn_edit = wx.Button(panel, label="Szerkesztés")
        self.btn_allomany = wx.Button(panel, label="Állományba vétel")
        self.btn_delete = wx.Button(panel, label="Törlés")
        self.btn_katalogus = wx.Button(panel, label="Katalógus export")

        btn_box.Add(self.btn_add, 0, wx.ALL, 5)
        btn_box.Add(self.btn_edit, 0, wx.ALL, 5)
        btn_box.Add(self.btn_allomany, 0, wx.ALL, 5)
        btn_box.Add(self.btn_delete, 0, wx.ALL, 5)
        btn_box.Add(self.btn_katalogus, 0, wx.ALL, 5)

        vbox.Add(btn_box, 0, wx.LEFT | wx.TOP, 5)

        # --- Lista (táblázat) ---
        self.list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN)

        # A táblázat oszlopfejléceit a konyvdialogs.DEZIDERATA_MEZO_DEFINICIOK
        # feliratkészletéből származtatjuk (a meződefiníció végén álló
        # kettőspontot levágva), ahelyett hogy itt egy második, kézzel
        # karbantartott listát tartanánk ugyanezekre a feliratokra - korábban
        # ez a két lista egymástól függetlenül létezett, ezért egy feliratot
        # csak az egyik helyen átnevezve a kettő csendben szétcsúszott volna.
        mezo_feliratok = dict(DEZIDERATA_MEZO_DEFINICIOK)
        columns = [mezo_feliratok[kulcs].rstrip(":") for kulcs in LISTA_OSZLOP_KULCSOK]

        for idx, (kulcs, col) in enumerate(zip(LISTA_OSZLOP_KULCSOK, columns)):
            self.list.InsertColumn(idx, col, width=LISTA_OSZLOP_ADATOK[kulcs][0])

        # Átméretezéskor a főlistához hasonlóan elosztjuk a többletszélességet
        self.list.Bind(wx.EVT_SIZE, self.on_lista_atmeretezes)

        vbox.Add(self.list, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(vbox)

        # --- Menüsor ---
        menusor = DeziderataMenuBar()
        self.menusor = menusor
        self.SetMenuBar(menusor)

        # --- Események ---
        self.Bind(wx.EVT_MENU, self.on_add, menusor.uj_tetel)
        self.Bind(wx.EVT_MENU, self.on_edit, menusor.szerk)
        self.Bind(wx.EVT_MENU, self.on_atemeles_allomanyba, menusor.allomanyba)
        self.Bind(wx.EVT_MENU, self.on_delete, menusor.torles)
        self.Bind(wx.EVT_MENU, self.on_import_json, menusor.json_import)
        self.Bind(wx.EVT_MENU, self.on_export_json, menusor.json_export)
        self.Bind(wx.EVT_MENU, self.on_katalogus_export, menusor.katalogus)
        self.Bind(wx.EVT_MENU, self.on_exit, menusor.kilepes)
        self.Bind(wx.EVT_MENU, self.OnMasolas, menusor.copy)
        self.Bind(wx.EVT_MENU, self.OnMindentKijelol, menusor.select_all)
        self.Bind(wx.EVT_MENU, self.OnEgyikSemKijelol, menusor.select_none)
        self.Bind(wx.EVT_MENU, self.OnVisszavonas, menusor.undo)
        self.Bind(wx.EVT_MENU, self.OnMegis, menusor.redo)
        self.Bind(wx.EVT_MENU_OPEN, self.OnMenuNyitas)

        self.btn_add.Bind(wx.EVT_BUTTON, self.on_add)
        self.btn_edit.Bind(wx.EVT_BUTTON, self.on_edit)
        self.btn_allomany.Bind(wx.EVT_BUTTON, self.on_atemeles_allomanyba)
        self.btn_delete.Bind(wx.EVT_BUTTON, self.on_delete)
        self.btn_katalogus.Bind(wx.EVT_BUTTON, self.on_katalogus_export)
        
        # Gyorskeresés (gépeléssel ugrás a listában)
        self.gyors_kereses = GyorsListaKereso()

        # Dupla kattintásra és Enter-re részletes nézet
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_reszletek)
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.list.Bind(wx.EVT_CHAR, self.on_char)
        self.list.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnListaJobbKlikk)

        self.list.SetFocus()

        # Adatok betöltése JSON-ból
        self.load_data()

        # Téma alkalmazása
        config = apply_theme_from_settings(self)
        self.current_theme = config.get("tema", "vilagos")

        self.Centre()
        self.Show()

    def rendez_listat(self):
        """A tételek ábécérendbe rendezése Cím szerint a magyar ábécé szabályai alapján."""
        def get_sort_key(item):
            val = item.get("cim", item.get("title", ""))
            return magyar_rendezesi_kulcs(val)

        self.items.sort(key=get_sort_key)

    # --- ID ALAPÚ AZONOSÍTÁS ---

    def _biztosit_idk(self):
        return tetelek_idjainak_potlasa(self.items)

    def GetKijeloltIdk(self):
        """A kijelölt sorok tétel-id-i (a lista sorrendjében)."""
        return [self.sor_id_terkep[i] for i in osszes_kijelolt_index(self.list)
                if i in self.sor_id_terkep]

    def _id_sorindexhez(self, sorindex):
        return self.sor_id_terkep.get(sorindex)

    def _sorindex_idhoz(self, tetel_id):
        """A tétel jelenlegi sora a listában (-1, ha nincs ilyen)."""
        if tetel_id is None:
            return -1
        for sorindex, azonosito in self.sor_id_terkep.items():
            if azonosito == tetel_id:
                return sorindex
        return -1

    def _tetel_idhoz(self, tetel_id):
        if tetel_id is None:
            return None
        for item in self.items:
            if isinstance(item, dict) and item.get("id") == tetel_id:
                return item
        return None

    def _pozicio_idhoz(self, tetel_id):
        """A tétel helye a self.items listában (-1, ha nincs ilyen)."""
        for pozicio, item in enumerate(self.items):
            if isinstance(item, dict) and item.get("id") == tetel_id:
                return pozicio
        return -1

    def GetTetelByRowIndex(self, sorindex):
        """A főlista GetKonyvByRowIndex-ének megfelelője."""
        return self._tetel_idhoz(self._id_sorindexhez(sorindex))

    def _torles_idk_alapjan(self, idk):
        torlendo = set(idk)
        self.items = [
            item for item in self.items
            if not (isinstance(item, dict) and item.get("id") in torlendo)
        ]

    # --- DUPLIKÁCIÓ ELLENŐRZŐ SEGÉDFÜGGVÉNY ---

    def is_duplicate(self, candidate, exclude_idx=None, exclude_id=None):
        """Megnézi, hogy a jelölt tétel létezik-e már a listában.

        A kihagyandó (épp szerkesztett) tételt id alapján azonosítjuk
        (exclude_id). Az exclude_idx (sorindex) paramétert a meglévő
        párbeszédablakok miatt még elfogadjuk, de itt azonnal id-re
        fordítjuk."""
        if exclude_id is None and exclude_idx is not None:
            exclude_id = self._id_sorindexhez(exclude_idx)
        for item in self.items:
            if exclude_id is not None and isinstance(item, dict) and item.get("id") == exclude_id:
                continue
            if is_same_book(candidate, item):
                return True
        return False

    # --- JSON KEZELŐ FÜGGVÉNYEK ---

    def load_data(self):
        self._mentes_tiltva = False
        try:
            betoltott_adat, ervenyes = load_hmac_json(DATA_FILE)
        except Exception as e:
            logging.error(f"Hiba a dezideráta-lista ({DATA_FILE}) betöltésekor: {e}", exc_info=True)
            self._mentes_tiltva = True
            wx.MessageBox(
                f"Hiba az adatok betöltésekor: {e}\n\n"
                "A fájl védelme érdekében a dezideráta szerkesztése le van tiltva.",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            self.items = []
            self.FrissitStatusBar()
            return

        if not ervenyes:
            logging.error(
                f"A dezideráta-lista ({DATA_FILE}) HMAC-aláírása érvénytelen: "
                "a fájl megsérült vagy jogosulatlanul módosították."
            )
            self._mentes_tiltva = True
            wx.MessageBox(
                "Az adatfájl integritás-ellenőrzése sikertelen: a fájl "
                "megsérülhetett, vagy valaki módosította a programon kívül.\n\n"
                "Az adatok betöltése biztonsági okból megszakadt, és a fájl "
                "védelme érdekében a dezideráta szerkesztése le van tiltva.",
                "Integritási hiba",
                wx.OK | wx.ICON_ERROR,
            )
            self.items = []
            self.FrissitStatusBar()
            return

        # Ellenőrizzük, hogy listát kaptunk-e, és rendeljük hozzá a self.items-hez!
        self.items = betoltott_adat if isinstance(betoltott_adat, list) else []

        # Lista frissítése a GUI-ban
        self.refresh_list()

    def _szerkesztes_engedelyezett(self):
        """False-t ad (és tájékoztat), ha a betöltés sikertelen volt, ezért a
        módosítás nem engedhető meg - lásd _mentes_tiltva."""
        if not self._mentes_tiltva:
            return True
        wx.MessageBox(
            "A dezideráta-jegyzék betöltése nem sikerült, ezért a szerkesztése "
            "le van tiltva: a program nem írja felül a meglévő (esetleg sérült) fájlt.\n\n"
            f"Fájl: {DATA_FILE}\n\n"
            "Ha a fájl sérült, állítsa vissza egy biztonsági másolatból, vagy "
            "nevezze át (pl. deziderata_serult.json), majd nyissa meg újra a "
            "Dezideráta-kezelőt.",
            "Szerkesztés letiltva",
            wx.OK | wx.ICON_WARNING,
            self,
        )
        return False

    def save_data(self):
        # Védőháló: a hívók (on_add stb.) már az elején ellenőrzik, de egy
        # betöltési hiba után semmiképp sem írhatjuk felül a fájlt.
        if self._mentes_tiltva:
            logging.error("A dezideráta mentése letiltva (sikertelen betöltés után).")
            return False
        # Régi (id nélküli) tételeknél az id itt kerül véglegesen a fájlba.
        self._biztosit_idk()
        if not save_hmac_json(DATA_FILE, self.items):
            wx.MessageBox(
                "Hiba az adatok mentésekor.",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return False

        # Ha a "KönyvTárnok kereső" ablak nyitva van, a találatai között
        # szereplő "Deziderátában" jelzések a most mentett változás miatt
        # elavulhattak (új tétel, törlés, szerkesztés, átemelés az
        # állományba) - ezért értesítjük a főablakon keresztül.
        szulo = self.GetParent()
        if szulo is not None and hasattr(szulo, "frissit_kereso_statuszokat"):
            szulo.frissit_kereso_statuszokat()
        return True

    def FrissitStatusBar(self):
        """Frissíti a status bar szövegét az elemek száma alapján."""
        if self._mentes_tiltva:
            self.statusbar.SetStatusText(
                "A dezideráta nem tölthető be, a szerkesztés le van tiltva."
            )
            return
        db_szam = self.list.GetItemCount()
        self.statusbar.SetStatusText(f"Dezideráta tételeinek száma: {db_szam}.")

    def OnMasolas(self, event=None):
        """Szerkesztés > Másolás (Ctrl+C): a kijelölt tételek a vágólapra.

        Soronként egy sor, az oszlopok tabulátorral elválasztva (minden
        oszlop látható ebben a listában).
        """
        indexek = sorted(osszes_kijelolt_index(self.list))
        if not indexek:
            return

        oszlopok_szama = self.list.GetColumnCount()
        sorok = []
        for sor_idx in indexek:
            cellak = [
                " ".join(self.list.GetItemText(sor_idx, col).split())
                for col in range(oszlopok_szama)
            ]
            sorok.append("\t".join(cellak))

        if not masolas_vagolapra_szoveg("\n".join(sorok)):
            wx.MessageBox("Nem sikerült megnyitni a vágólapot.", "Hiba", wx.OK | wx.ICON_ERROR)
            return
        self.statusbar.SetStatusText(f"{len(indexek)} tétel a vágólapra másolva.")

    def OnMindentKijelol(self, event=None):
        for i in range(self.list.GetItemCount()):
            self.list.Select(i, True)

    def OnEgyikSemKijelol(self, event=None):
        """Szerkesztés > Kijelölés > Egyik sem (Ctrl+Shift+A).

        Egyetlen hívással (-1 = minden elem) szünteti meg a kijelölést; a
        fókusz a helyén marad.
        """
        if self.list.GetItemCount() == 0 or self.list.GetSelectedItemCount() == 0:
            self.statusbar.SetStatusText("Nincs kijelölt tétel.")
            return
        self.list.SetItemState(-1, 0, wx.LIST_STATE_SELECTED)
        self.statusbar.SetStatusText("Kijelölés megszüntetve.")

    # --- VISSZAVONÁS / MÉGIS ---

    def on_close(self, event):
        # A saját vermek elvesznek; a főablakkal közös (kapcsolt) lépések a
        # főablak vermében megmaradnak, és zárt ablaknál a fájlra alkalmazódnak.
        self.undo.bezar()
        event.Skip()

    def OnMenuNyitas(self, event):
        frissit_undo_menu(self.menusor.undo, self.menusor.redo, self.undo)
        event.Skip()

    def OnVisszavonas(self, event=None):
        self._visszavonas_vagy_megis(ismet=False)

    def OnMegis(self, event=None):
        self._visszavonas_vagy_megis(ismet=True)

    def _visszavonas_vagy_megis(self, ismet):
        if not self._szerkesztes_engedelyezett():
            return
        leiras = self.undo.ismetlendo_leiras() if ismet else self.undo.visszavonando_leiras()
        if leiras is None:
            self.statusbar.SetStatusText(
                "Nincs mit újra alkalmazni." if ismet else "Nincs visszavonható művelet."
            )
            return

        # Kapcsolt lépésnél (pl. átemelés az állományba) a főablak
        # könyvlistáját is a regiszter frissíti.
        if not (self.undo.ismet() if ismet else self.undo.visszavon()):
            wx.MessageBox(
                "A művelet nem hajtható végre (a változás nem menthető), ezért "
                "az adatok a korábbi állapotukban maradtak.",
                "Mentési hiba", wx.OK | wx.ICON_ERROR, self,
            )
            self.list.SetFocus()
            return
        self.statusbar.SetStatusText(
            f"Újra alkalmazva: {leiras}." if ismet else f"Visszavonva: {leiras}."
        )

    def _kijelol_idk(self, idk):
        """A megadott id-jű tételek kijelölése (az elsőre fókuszálva)."""
        indexek = [self._sorindex_idhoz(i) for i in idk]
        indexek = [i for i in indexek if i != -1]
        for i in indexek:
            self.list.Select(i)
        if indexek:
            self.list.Focus(indexek[0])
            self.list.EnsureVisible(indexek[0])
        self.list.SetFocus()

    def on_lista_atmeretezes(self, event):
        event.Skip()
        self.IgazitOszlopSzelesseg()

    def IgazitOszlopSzelesseg(self):
        """Az oszlopok alap szélességéhez hozzáadja a lista szélességéből
        megmaradó helyet az oszlopok súlyának arányában (a főlista
        KonyvListaCtrl.IgazitOszlopSzelesseg-ével azonos módon). Ha a lista
        nem elég széles az alap szélességekhez, azok maradnak, és a lista
        vízszintesen görgethető."""
        szerel_szelesseg = (self.list.GetClientSize().width
                            - wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X))
        osszes_alap = sum(LISTA_OSZLOP_ADATOK[k][0] for k in LISTA_OSZLOP_KULCSOK)
        osszes_suly = sum(LISTA_OSZLOP_ADATOK[k][1] for k in LISTA_OSZLOP_KULCSOK)

        maradek_hely = max(szerel_szelesseg - osszes_alap, 0)
        for i, kulcs in enumerate(LISTA_OSZLOP_KULCSOK):
            alap, suly = LISTA_OSZLOP_ADATOK[kulcs]
            plusz = int(maradek_hely * (suly / osszes_suly))
            self.list.SetColumnWidth(i, alap + plusz)

    def refresh_list(self):
        """Frissíti a ListCtrl elemét a tételek ábécérendbe rendezése után."""
        self._biztosit_idk()
        self.rendez_listat()
        self.sor_id_terkep = {
            idx: item.get("id") for idx, item in enumerate(self.items)
            if isinstance(item, dict)
        }
        self.list.DeleteAllItems()
        for item in self.items:
            ertekek = [lista_ertek(item, k) for k in LISTA_OSZLOP_KULCSOK]
            index = self.list.InsertItem(self.list.GetItemCount(), ertekek[0])
            for oszlop, ertek in enumerate(ertekek[1:], start=1):
                self.list.SetItem(index, oszlop, ertek)

        # A görgetősáv megjelenése/eltűnése a hasznos szélességet módosíthatja
        self.IgazitOszlopSzelesseg()
        self.FrissitStatusBar()

    # --- ESEMÉNYKEZELŐK ---

    def _MegjelenitPopUpMenut(self):
        indexek = osszes_kijelolt_index(self.list)
        if not indexek:
            return

        popup_menu = wx.Menu()
        megtekint_item = popup_menu.Append(wx.ID_ANY, "Tétel részletei")
        szerkeszt_item = popup_menu.Append(wx.ID_ANY, "Tétel szerkesztése")
        popup_menu.AppendSeparator()
        torol_item = popup_menu.Append(wx.ID_ANY, f"Kijelölt tételek eltávolítása ({len(indexek)} db)")

        self.Bind(wx.EVT_MENU, self.on_reszletek, megtekint_item)
        self.Bind(wx.EVT_MENU, self.on_edit, szerkeszt_item)
        self.Bind(wx.EVT_MENU, self.on_delete, torol_item)

        self.PopupMenu(popup_menu)
        popup_menu.Destroy()

    def OnListaJobbKlikk(self, event):
        idx = event.GetIndex()
        if idx not in osszes_kijelolt_index(self.list):
            self.list.Select(idx)
        self._MegjelenitPopUpMenut()

    def on_reszletek(self, event):
        """Megnyitja a kijelölt tétel részletes adatlapját."""
        selected_idx = self.list.GetFirstSelected()
        if selected_idx == -1:
            wx.MessageBox(
                "Kérjük, válasszon ki egy tételt a listából!",
                "Nincs kijelölés",
                wx.OK | wx.ICON_INFORMATION
            )
            return

        selected_data = self.GetTetelByRowIndex(selected_idx)
        if selected_data is None:
            return
        dlg = DeziderataReszletekDialog(self, item_data=selected_data, index=selected_idx)
        dlg.ShowModal()
        dlg.Destroy()
        self.list.SetFocus()

    def tetel_modositasa(self, szerkesztett_id, updated_data, eredeti_sorindex=None):
        """Egy tétel adatainak lecserélése id alapján, mentés, újrarajzolás és
        a tétel újrakijelölése. A Deziderata.on_edit és a
        DeziderataReszletekDialog "Szerkesztés" gombja is ezt hívja, hogy a
        két útvonal viselkedése ne térjen el. True, ha a csere megtörtént."""
        if not self._szerkesztes_engedelyezett():
            return False
        pozicio = self._pozicio_idhoz(szerkesztett_id)
        if pozicio == -1:
            wx.MessageBox(
                "A szerkesztett tétel közben megváltozott vagy eltűnt a "
                "jegyzékből, ezért a módosítás nem menthető.",
                "Hiba", wx.OK | wx.ICON_ERROR, self,
            )
            return False
        # A párbeszédablak get_data()-ja nem adja vissza az id-t (és az
        # esetleges ismeretlen mezőket sem): a tétel azonosítóját megőrizzük.
        updated_data["id"] = szerkesztett_id
        with self.undo.muvelet("tétel módosítása"):
            self.items[pozicio] = updated_data
            self.save_data()
            self.refresh_list()

        target_idx = self._sorindex_idhoz(szerkesztett_id)
        if (target_idx == -1 and eredeti_sorindex is not None
                and self.list.GetItemCount() > 0):
            target_idx = min(eredeti_sorindex, self.list.GetItemCount() - 1)
        self.select_and_focus(target_idx)
        return True

    def tetelek_felvetele(self, uj_tetelek):
        """Új tételek felvétele kívülről (KönyvTárnok-kereső) a MEGNYITOTT
        ablak memóriabeli listájába: duplikátum-szűrés, id-k kiosztása,
        mentés és frissítés. Visszatérés: (sikeres, visszautasitott), vagy
        None, ha a szerkesztés le van tiltva / a mentés nem sikerült (utóbbi
        esetben a memóriabeli lista a művelet előtti állapotra áll vissza)."""
        if not self._szerkesztes_engedelyezett():
            return None
        with self.undo.muvelet("átemelés a deziderátába"):
            sikeres, visszautasitott, felvett = deziderata_tetelek_hozzaadasa(
                self.items, uj_tetelek
            )
            if sikeres:
                if not self.save_data():
                    self._torles_idk_alapjan([t["id"] for t in felvett])
                    self.refresh_list()
                    return None
                self.refresh_list()
        return sikeres, visszautasitott

    def on_add(self, event):
        if not self._szerkesztes_engedelyezett():
            return
        dlg = AddItemDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.get_data()
            data["id"] = uj_tetel_id()
            with self.undo.muvelet("új tétel felvétele"):
                self.items.append(data)
                self.save_data()
                self.refresh_list()
            target_idx = self._sorindex_idhoz(data["id"])

            if target_idx != -1:
                self.select_and_focus(target_idx)
            else:
                self.list.SetFocus()
        dlg.Destroy()

    def on_edit(self, event):
        if not self._szerkesztes_engedelyezett():
            return
        selected_idx = self.list.GetFirstSelected()
        if selected_idx == -1:
            wx.MessageBox(
                "Kérlek, válassz ki egy tételt a szerkesztéshez!",
                "Nincs kijelölve tétel",
                wx.OK | wx.ICON_INFORMATION
            )
            return

        selected_data = self.GetTetelByRowIndex(selected_idx)
        if selected_data is None:
            return
        szerkesztett_id = selected_data.get("id")
        dlg = EditItemDialog(self, selected_data, index=selected_idx)
        if dlg.ShowModal() == wx.ID_OK:
            self.tetel_modositasa(szerkesztett_id, dlg.get_data(),
                                  eredeti_sorindex=selected_idx)

        dlg.Destroy()

    def on_delete(self, event):
        """Kijelölt tétel(ek) törlése (tömeges törlés támogatásával)."""
        if not self._szerkesztes_engedelyezett():
            return
        selected_indices = osszes_kijelolt_index(self.list)
        selected_ids = self.GetKijeloltIdk()

        if not selected_indices:
            wx.MessageBox(
                "Kérlek, válassz ki legalább egy tételt a törléshez!",
                "Nincs kijelölve tétel",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        db = len(selected_indices)
        uzenet = (
            f"Biztosan törölni szeretné a kijelölt {db} db tételt?"
            if db > 1
            else "Biztosan törölni szeretné a kijelölt tételt?"
        )

        confirm = wx.MessageBox(
            uzenet,
            "Törlés megerősítése",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        )

        if confirm == wx.YES:
            with self.undo.muvelet(f"{db} tétel törlése" if db > 1 else "tétel törlése"):
                self._torles_idk_alapjan(selected_ids)
                self.save_data()
                self.refresh_list()
            osszesen = self.list.GetItemCount()
            if osszesen > 0:
                uj_idx = min(selected_indices[0], osszesen - 1)
                self.select_and_focus(uj_idx)
            else:
                self.list.SetFocus()

    def on_export_json(self, event):
        config = load_settings()
        default_dir = config.get("last_json_dir", "")

        fileDialog = wx.FileDialog(
            self,
            message="Jegyzék exportálása nyers JSON fájlba",
            defaultDir=default_dir,
            defaultFile="deziderata.json",
            wildcard="JSON fájlok (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )

        if fileDialog.ShowModal() == wx.ID_OK:
            pathname = fileDialog.GetPath()
            config["last_json_dir"] = os.path.dirname(pathname)
            save_settings(config)
            try:
                with open(pathname, "w", encoding="utf-8") as f:
                    json.dump(self.items, f, ensure_ascii=False, indent=4)
                    f.flush()  # Biztosítja, hogy az adatok azonnal kiírásra kerüljenek lemezre
                wx.MessageBox("Az adatok sikeresen exportálva!", "Siker", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Hiba történt az exportálás során: {e}", "Hiba", wx.OK | wx.ICON_ERROR)
        
        fileDialog.Destroy()

    def on_import_json(self, event):
        if not self._szerkesztes_engedelyezett():
            return
        config = load_settings()
        default_dir = config.get("last_json_dir", "")

        with wx.FileDialog(
            self,
            message="Jegyzék betöltése",
            defaultDir=default_dir,
            wildcard="JSON fájlok (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            pathname = fileDialog.GetPath()
            config["last_json_dir"] = os.path.dirname(pathname)
            save_settings(config)

            def _hozzaad(item):
                if not self.is_duplicate(item):
                    # Az importált fájl id-je egy másik gépről/állományból
                    # jöhet, és ütközhetne a meglévőkkel: mindig újat adunk.
                    if isinstance(item, dict):
                        item["id"] = uj_tetel_id()
                    self.items.append(item)
                    return True
                return False

            try:
                with self.undo.muvelet("JSON importálás"):
                    hozzaadva, kihagyva = additiv_lista_import(pathname, _hozzaad)
            except ValueError as e:
                wx.MessageBox(str(e), "Hiba", wx.OK | wx.ICON_ERROR)
                return
            except Exception as e:
                wx.MessageBox(f"Hiba történt az importálás során: {e}", "Hiba", wx.OK | wx.ICON_ERROR)
                return

            self.save_data()
            self.refresh_list()
            wx.MessageBox(
                f"Importálás befejeződött!\n\nHozzáadva: {hozzaadva} db\nKihagyva (már létező duplikátum): {kihagyva} db",
                "Siker",
                wx.OK | wx.ICON_INFORMATION
            )

    def on_katalogus_export(self, event):
        """A teljes dezideráta-lista exportálása katalóguslapként (PDF).
        Csak olvas, ezért betöltési hiba után sem kell letiltani."""
        sorok = [{k: lista_ertek(it, k) for k in LISTA_OSZLOP_KULCSOK}
                 for it in self.items]  # a self.items már rendezett
        katalogus_mentese(self, sorok, LISTA_OSZLOP_KULCSOK,
                          defs=katalogus_oszlop_definiciok(),
                          cim_szoveg="Dezideráta-lap",
                          alap_fajlnev="dezideratalap.pdf")

    def on_exit(self, event):
        self.Close()

    def on_atemeles_allomanyba(self, event=None):
        if not self._szerkesztes_engedelyezett():
            return
        if not self.GetParent() or not hasattr(self.GetParent(), "db"):
            wx.MessageBox(
                "Az átemelés nem lehetséges, mert a Dezideráta-kezelő önállóan fut!",
                "Hiba",
                wx.OK | wx.ICON_ERROR,
            )
            return

        kijelolt_indexek = osszes_kijelolt_index(self.list)
        kijelolt_idk = self.GetKijeloltIdk()

        if not kijelolt_indexek:
            wx.MessageBox(
                "Nincs kijelölve egyetlen elem sem!",
                "Figyelmeztetés",
                wx.OK | wx.ICON_WARNING,
            )
            return

        db = len(kijelolt_indexek)
        if not kerj_tomeges_atemeles_megerositest(self, db, "tételt", "az állományba"):
            return

        parent_frame = self.GetParent()

        # Az allomany_rekord_dezideratabol fehérlistás: id nélküli rekordot ad,
        # az állomány a felvételkor (uj_konyv_hozzaadasa) maga ad neki id-t,
        # amit a kapott dictbe vissza is ír - ezt használjuk lent.
        konyv_adatok = [
            allomany_rekord_dezideratabol(self._tetel_idhoz(tetel_id))
            for tetel_id in kijelolt_idk
        ]

        # A lista frissítését a főablak szűrés-megőrző segédmetódusára
        # bízzuk (ugyanaz, mint kézi felvitelnél, JSON importnál vagy a
        # KönyvTárnok-kereső átemelésénél), hogy egy esetlegesen aktív
        # szűrés/keresés ne sérüljön az átemelés után - egy sima
        # FeltoltLista() ugyanis figyelmen kívül hagyná az aktív szűrést, és
        # megtévesztő állapotot hagyna maga után (a szűrő-felirat és a
        # "Szűrés törlése" gomb aktív maradna, miközben a teljes, szűretlen
        # lista jelenne meg).
        def _frissites(uj_konyv_objektumok):
            if hasattr(parent_frame, "_uj_konyvek_utani_frissites"):
                parent_frame._uj_konyvek_utani_frissites(uj_konyv_objektumok)
            elif hasattr(parent_frame, "lista"):
                parent_frame.lista.FeltoltLista()
                if hasattr(parent_frame, "FrissitStatusBar"):
                    parent_frame.FrissitStatusBar()

        # A tényleges felvételi ciklust a data_manager.konyvek_tomeges_felvetele
        # közös segédfüggvénye végzi (ugyanaz, mint a KönyvTárnok-kereső
        # "Felvétel az állományba" műveleténél). Ha a mentés (lemezre írás)
        # meghiúsul, a data_manager.MentesiHiba kivételt kapjuk - ezt
        # szándékosan külön kezeljük, hogy ne keveredjen össze a
        # duplikátum miatti elutasítással (lásd data_manager.MentesiHiba).
        # Az átemelés EGY, kapcsolt visszavonási lépés: a könyvek felvétele
        # az állományban ÉS a tételek törlése innen. Bármelyik ablakból
        # visszavonva mindkét oldal visszaáll (lásd undo_manager.py).
        with self.undo.muvelet("átemelés az állományba", ["allomany", "deziderata"]):
            try:
                sikeres, visszautasitott, sikeres_relativ_indexek, _ = konyvek_tomeges_felvetele(
                    parent_frame.db, konyv_adatok, utani_frissites_fv=_frissites
                )
            except MentesiHiba as e:
                # A megszakadásig már felvett tételek az állományban maradnak, ezért
                # a dezideráta-jegyzékből is el kell távolítani őket (különben
                # duplikátumként ott maradnának). A felvett rekordok id-t kaptak.
                felvett_allomany_idk = {k.get("id") for k in parent_frame.db.konyvek}
                mar_felvett_idk = [
                    tetel_id for tetel_id, rekord in zip(kijelolt_idk, konyv_adatok)
                    if rekord.get("id") and rekord.get("id") in felvett_allomany_idk
                ]
                if mar_felvett_idk:
                    self._torles_idk_alapjan(mar_felvett_idk)
                    self.save_data()
                    self.refresh_list()
                wx.MessageBox(
                    f"Hiba történt az állományjegyzék mentése közben:\n{e}\n\n"
                    "A már sikeresen felvett tételek megmaradnak az állományban "
                    "(és kikerültek a dezideráta-jegyzékből), de a további "
                    "kijelölt tételek felvétele emiatt megszakadt.",
                    "Mentési hiba",
                    wx.OK | wx.ICON_ERROR,
                    self,
                )
                return

            if sikeres > 0:
                sikeres_idk = [kijelolt_idk[i] for i in sikeres_relativ_indexek]
                self._torles_idk_alapjan(sikeres_idk)
                self.save_data()
                self.refresh_list()

        mutass_tomeges_atemeles_eredmenyt(
            self, sikeres, visszautasitott, "az állományhoz", "az állományban"
        )

    def feldolgoz_kereso_karakter(self, karakter):
        """Kezeli a karakter hozzáadását a keresési pufferhez és a megfelelő
        sorra ugrást (lásd gyors_kereses.GyorsListaKereso)."""
        def kijeloles_beallitasa(talalt_idx):
            for i in range(self.list.GetItemCount()):
                self.list.Select(i, False)
            self.list.Select(talalt_idx, True)
            self.list.Focus(talalt_idx)
            self.list.EnsureVisible(talalt_idx)

        self.gyors_kereses.feldolgoz(
            karakter,
            total_lekero=self.list.GetItemCount,
            szoveg_lekero=self.list.GetItemText,
            kivalasztott_lekero=self.list.GetFirstSelected,
            kivalasztas_beallito=kijeloles_beallitasa,
        )

    def on_char(self, event):
        self.gyors_kereses.kezel_char_esemeny(event, self.feldolgoz_kereso_karakter)

    def on_key_down(self, event):
        keycode = event.GetKeyCode()

        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_reszletek(event)
        elif keycode == wx.WXK_SPACE:
            # A szóköz billentyű ne nyissa meg a részleteket, de adja hozzá a keresési pufferhez
            self.feldolgoz_kereso_karakter(' ')
        elif keycode == wx.WXK_WINDOWS_MENU or (keycode == wx.WXK_F10 and event.ShiftDown()):
            self._MegjelenitPopUpMenut()
        else:
            event.Skip()

    def select_and_focus(self, index):
        if 0 <= index < self.list.GetItemCount():
            self.list.Select(index)
            self.list.Focus(index)
            self.list.EnsureVisible(index)
        self.list.SetFocus()

class App(wx.App):
    def OnInit(self):
        Deziderata()
        return True

if __name__ == "__main__":
    app = App(False)
    app.MainLoop()