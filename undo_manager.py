"""Visszavonás (undo) / Mégis (redo) kezelés, több adattárolóra kiterjedő
(kapcsolt) lépésekkel.

FELÉPÍTÉS
---------
* Tároló (ListaTarolo): egy rekordlista + annak tartósítása (állomány,
  dezideráta-ablak, dezideráta-fájl). A tárolókat név azonosítja
  ("allomany", "deziderata"); a nevet az UndoRegiszter oldja fel élő
  tárolóra, így pl. a dezideráta tárolója más, ha az ablak nyitva van
  (memória), és más, ha zárva (közvetlenül a fájl).
* Változás (Valtozas): egy lépés hatása egy tárolóra, REKORD-id alapú
  különbségként (eltávolított / hozzáadott / módosított rekordok). Ez nem
  teljes pillanatkép, ezért egy lépés visszavonása nem írja felül a közben,
  máshol történt (más rekordot érintő) módosításokat, és a lépés a másik
  ablakból is, sorrendtől függetlenül alkalmazható.
* Lépés (Lepes): egy logikai művelet (pl. 'átemelés az állományba') hatása
  egy vagy több tárolón. Ugyanaz a Lepes-objektum kerül az érintett ablakok
  (UndoKezelo) vermeibe, ezért bármelyikből visszavonva MINDKÉT oldal
  visszaáll, és a lépés mindkét veremből átkerül a mégis-verembe.
* UndoRegiszter: a tárolók feloldója és a lépések rögzítője/végrehajtója.

A modul nem függ a wx-től.
"""
import copy
import logging
from contextlib import contextmanager

_EGYSZERU_TIPUSOK = (str, int, float, bool, type(None))

ALAPERTELMEZETT_LIMIT = 30


# ==============================================================================
# REKORDOK ÉS VÁLTOZÁSOK
# ==============================================================================
def rekordlista_masolata(rekordok):
    """Gyors, rekordszinten független másolat (a lapos szótárakra dict(),
    összetett értékekre deepcopy)."""
    uj = []
    for rekord in rekordok:
        if isinstance(rekord, dict) and all(
            isinstance(ertek, _EGYSZERU_TIPUSOK) for ertek in rekord.values()
        ):
            uj.append(dict(rekord))
        else:
            uj.append(copy.deepcopy(rekord))
    return uj


class Valtozas:
    """Egy tárolóra gyakorolt hatás: a 'régi' állapotból az 'újba' vezető
    különbség. eltavolitott/hozzaadott: [(pozicio, rekord)], modositott:
    [(elotte, utana)]. A pozíció a rekord helye a megfelelő (régi illetve új)
    listában, csak a visszaillesztés pontosításához kell."""

    __slots__ = ("eltavolitott", "hozzaadott", "modositott")

    def __init__(self, eltavolitott=None, hozzaadott=None, modositott=None):
        self.eltavolitott = list(eltavolitott or [])
        self.hozzaadott = list(hozzaadott or [])
        self.modositott = list(modositott or [])

    def ures(self):
        return not (self.eltavolitott or self.hozzaadott or self.modositott)

    def fordit(self):
        """A fordított hatás (a visszavonás iránya)."""
        return Valtozas(
            self.hozzaadott,
            self.eltavolitott,
            [(utana, elotte) for elotte, utana in self.modositott],
        )

    def erintett_idk(self):
        """A változás után látható (újonnan megjelent vagy átírt) rekordok
        id-i - ezeket érdemes kijelölni."""
        idk = [r.get("id") for _, r in self.hozzaadott]
        idk += [utana.get("id") for _, utana in self.modositott]
        return [i for i in idk if i]


def _azonositott(lista):
    return {
        r["id"]: r for r in lista
        if isinstance(r, dict) and r.get("id")
    }


def valtozas_szamitasa(elotte, utana):
    """Két (független másolat) rekordlista különbsége id alapján. Az id nélküli
    rekordokat nem követi (a könyvek és a dezideráta-tételek mindig kapnak id-t)."""
    e_terkep = _azonositott(elotte)
    u_terkep = _azonositott(utana)
    eltavolitott = [
        (p, r) for p, r in enumerate(elotte)
        if isinstance(r, dict) and r.get("id") and r["id"] not in u_terkep
    ]
    hozzaadott = [
        (p, r) for p, r in enumerate(utana)
        if isinstance(r, dict) and r.get("id") and r["id"] not in e_terkep
    ]
    modositott = [
        (e_terkep[i], u_terkep[i]) for i in u_terkep
        if i in e_terkep and e_terkep[i] != u_terkep[i]
    ]
    return Valtozas(eltavolitott, hozzaadott, modositott)


def alkalmaz_listara(lista, valtozas):
    """A változást HELYBEN alkalmazza a listán, id alapján. Ellenálló a
    közben történt eltérésekkel szemben: a már hiányzó rekord törlését, a már
    meglévő rekord újbóli beszúrását és a hiányzó rekord módosítását kihagyja.
    A listába mindig másolat kerül, nem a változásban tárolt objektum."""
    torlendo = {r.get("id") for _, r in valtozas.eltavolitott}
    if torlendo:
        lista[:] = [
            r for r in lista
            if not (isinstance(r, dict) and r.get("id") in torlendo)
        ]

    atirasok = {elotte.get("id"): utana for elotte, utana in valtozas.modositott}
    if atirasok:
        for rekord in lista:
            if isinstance(rekord, dict) and rekord.get("id") in atirasok:
                uj_ertek = rekordlista_masolata([atirasok[rekord["id"]]])[0]
                rekord.clear()          # helyben: a mások által tartott
                rekord.update(uj_ertek)  # hivatkozások érvényben maradnak

    if valtozas.hozzaadott:
        meglevo = {r.get("id") for r in lista if isinstance(r, dict)}
        for poz, rekord in sorted(valtozas.hozzaadott, key=lambda x: x[0]):
            if rekord.get("id") in meglevo:
                continue
            lista.insert(min(poz, len(lista)), rekordlista_masolata([rekord])[0])
            meglevo.add(rekord.get("id"))


# ==============================================================================
# TÁROLÓK
# ==============================================================================
class ListaTarolo:
    """Egy rekordlista tárolója. Az alosztályok megadják az élő listát, a
    tartósítást és a nézet frissítését."""

    def lista(self):
        raise NotImplementedError

    def mentes(self):
        raise NotImplementedError

    def frissit(self, valtozas, kijelol):
        """A nézet újrarajzolása; kijelol=True esetén az érintett rekordok
        kijelölése is (csak abban az ablakban, ahonnan a visszavonás indult)."""

    def masolat(self):
        """Független másolat a pillanatképekhez; None, ha a tároló jelenleg
        nem rögzíthető (pl. letiltott, betöltési hibás állapot)."""
        return rekordlista_masolata(self.lista())

    def alkalmaz(self, valtozas, kijelol=True):
        """Alkalmazza a változást és tartósítja. Mentési hiba esetén a
        memóriát visszaállítja és False-t ad (a lépés nem történt meg)."""
        lista = self.lista()
        elozo = rekordlista_masolata(lista)
        alkalmaz_listara(lista, valtozas)
        if not self.mentes():
            lista[:] = elozo
            self.frissit(Valtozas(), False)
            return False
        self.frissit(valtozas, kijelol)
        return True


# ==============================================================================
# LÉPÉSEK, KEZELŐK, REGISZTER
# ==============================================================================
class Lepes:
    __slots__ = ("leiras", "reszek")

    def __init__(self, leiras, reszek):
        self.leiras = leiras
        self.reszek = reszek  # [(tarolo_nev, Valtozas), ...]


class UndoKezelo:
    """Egy ablak (nézet) visszavonási és mégis-verme.

    tarolok: azoknak a tárolóknak a nevei, amelyekhez az ablak tartozik; a
    rögzített lépés azokba a vermekbe kerül, amelyek tárolóját érinti.
    elsodleges: ha egy lépést egyetlen élő ablak sem birtokol (pl. a zárt
    dezideráta módosítása a KönyvTárnok-keresőből), ide kerül.
    """

    def __init__(self, regiszter, tarolok, elsodleges=False):
        self.regiszter = regiszter
        self.tarolok = frozenset(tarolok)
        self.elsodleges = elsodleges
        self._undo = []
        self._redo = []
        regiszter._kezelok.append(self)

    def bezar(self):
        """Az ablak bezárásakor: a saját vermek elvesznek, de a más
        ablakokkal közös (kapcsolt) lépések azok vermeiben megmaradnak."""
        if self in self.regiszter._kezelok:
            self.regiszter._kezelok.remove(self)
        self._undo.clear()
        self._redo.clear()

    def torol(self):
        self._redo_torlese()
        self._undo.clear()

    def muvelet(self, leiras, tarolok=None):
        """Visszavonható lépés (csoport) a megadott (alapból a saját)
        tárolókra. Egymásba ágyazható, a legkülső érvényes."""
        nevek = list(tarolok) if tarolok else sorted(self.tarolok)
        return self.regiszter.muvelet(leiras, nevek)

    def visszavonando_leiras(self):
        return self._undo[-1].leiras if self._undo else None

    def ismetlendo_leiras(self):
        return self._redo[-1].leiras if self._redo else None

    def visszavon(self):
        return self.regiszter.vegrehajt(self, ismet=False)

    def ismet(self):
        return self.regiszter.vegrehajt(self, ismet=True)

    # --- belső ---
    def _felvesz(self, lepes):
        self._redo_torlese()
        self._undo.append(lepes)
        while len(self._undo) > self.regiszter.limit:
            del self._undo[0]

    def _redo_torlese(self):
        # Az érvénytelenné vált mégis-lépés a többi ablak vermeiből is kikerül.
        for lepes in self._redo:
            for k in self.regiszter._kezelok:
                if k is not self and lepes in k._redo:
                    k._redo.remove(lepes)
        self._redo.clear()


class UndoRegiszter:
    def __init__(self, limit=ALAPERTELMEZETT_LIMIT):
        self.limit = limit
        self._feloldok = {}
        self._kezelok = []
        self._melyseg = 0
        self._csere_folyamatban = False

    def tarolo_regisztral(self, nev, feloldo):
        """feloldo(): az éppen érvényes tároló (ListaTarolo) vagy None."""
        self._feloldok[nev] = feloldo

    def _tarolo(self, nev):
        feloldo = self._feloldok.get(nev)
        if feloldo is None:
            return None
        try:
            return feloldo()
        except Exception:
            logging.error(f"Az undo-tároló ({nev}) feloldása sikertelen.", exc_info=True)
            return None

    def _masolat(self, nev):
        tarolo = self._tarolo(nev)
        if tarolo is None:
            return None
        try:
            return tarolo.masolat()
        except Exception:
            logging.error(f"Az undo-pillanatkép ({nev}) sikertelen.", exc_info=True)
            return None

    # --- rögzítés ---
    @contextmanager
    def muvelet(self, leiras, tarolo_nevek):
        """Egy visszavonható lépést fog közre. A legkülső hívás készít
        pillanatképet az érintett tárolókról, és a végén (akkor is, ha
        kivétel történt, de csak ha volt változás) rögzíti a különbséget."""
        if self._csere_folyamatban or self._melyseg > 0:
            self._melyseg += 1
            try:
                yield
            finally:
                self._melyseg -= 1
            return

        elotte = {}
        for nev in tarolo_nevek:
            masolat = self._masolat(nev)
            if masolat is not None:
                elotte[nev] = masolat
        self._melyseg = 1
        try:
            yield
        finally:
            self._melyseg = 0
            self._rogzit(leiras, elotte)

    def _rogzit(self, leiras, elotte):
        reszek = []
        for nev, regi in elotte.items():
            uj = self._masolat(nev)
            if uj is None:
                continue
            valtozas = valtozas_szamitasa(regi, uj)
            if not valtozas.ures():
                reszek.append((nev, valtozas))
        if not reszek:
            return

        lepes = Lepes(leiras, reszek)
        nevek = {nev for nev, _ in reszek}
        celok = [k for k in self._kezelok if k.tarolok & nevek]
        if not celok:
            celok = [k for k in self._kezelok if k.elsodleges][:1]
        for kezelo in celok:
            kezelo._felvesz(lepes)

    # --- végrehajtás ---
    def _alkalmaz(self, nev, valtozas, kijelol):
        tarolo = self._tarolo(nev)
        if tarolo is None:
            return False
        try:
            return bool(tarolo.alkalmaz(valtozas, kijelol))
        except Exception:
            logging.error(f"Az undo-lépés alkalmazása ({nev}) sikertelen.", exc_info=True)
            return False

    def vegrehajt(self, kezelo, ismet):
        """A kezelő legfelső lépésének visszavonása/újbóli alkalmazása MINDEN
        érintett tárolón. Ha bármelyik tároló nem tudja (pl. mentési hiba),
        a már alkalmazott részek visszaállnak, és False a visszatérés."""
        honnan = kezelo._redo if ismet else kezelo._undo
        if not honnan:
            return False
        lepes = honnan[-1]

        alkalmazott = []
        self._csere_folyamatban = True
        try:
            for nev, valtozas in lepes.reszek:
                irany = valtozas if ismet else valtozas.fordit()
                if not self._alkalmaz(nev, irany, nev in kezelo.tarolok):
                    for nev2, irany2 in reversed(alkalmazott):
                        self._alkalmaz(nev2, irany2.fordit(), False)
                    return False
                alkalmazott.append((nev, irany))
        finally:
            self._csere_folyamatban = False

        # A lépés minden olyan veremből átkerül, amelyben szerepelt.
        for k in list(self._kezelok):
            forras = k._redo if ismet else k._undo
            cel = k._undo if ismet else k._redo
            if lepes in forras:
                forras.remove(lepes)
                cel.append(lepes)
                while len(cel) > self.limit:
                    del cel[0]
        return True


# ==============================================================================
# SEGÉDEK A MENÜHÖZ ÉS A SZÖVEGMEZŐKHÖZ
# ==============================================================================
def frissit_undo_menu(undo_item, redo_item, kezelo, fokuszalt_ctrl=None):
    """A Visszavonás/Mégis menütételek feliratába beírja a soron következő
    lépés leírását (pl. 'Visszavonás: könyv törlése').

    A tételeket szándékosan nem tiltjuk le: a menü-gyorsbillentyűk
    engedélyezettségét Windowson csak a menü megnyitásakor frissíti a wx, így
    egy elavult 'letiltott' állapot elnyelné a Ctrl+Z-t. Ha nincs mit
    visszavonni, a kezelő a státuszsorban jelzi."""
    if fokuszalt_ctrl is not None and hasattr(fokuszalt_ctrl, "CanUndo"):
        undo_item.SetItemLabel("Visszavonás\tCtrl+Z")
        redo_item.SetItemLabel("Mégis\tCtrl+Y")
        return
    leiras = kezelo.visszavonando_leiras()
    undo_item.SetItemLabel(
        f"Visszavonás: {leiras}\tCtrl+Z" if leiras else "Visszavonás\tCtrl+Z"
    )
    leiras = kezelo.ismetlendo_leiras()
    redo_item.SetItemLabel(
        f"Mégis: {leiras}\tCtrl+Y" if leiras else "Mégis\tCtrl+Y"
    )


def szovegmezo_visszavonas(fokuszalt_ctrl, ismet=False):
    """Ha a fókusz szövegbeviteli mezőn van, annak saját visszavonását/mégisét
    végzi, és True-t ad (a hívó ilyenkor ne nyúljon az adatokhoz)."""
    if fokuszalt_ctrl is None or not hasattr(fokuszalt_ctrl, "CanUndo"):
        return False
    if ismet:
        if hasattr(fokuszalt_ctrl, "CanRedo") and fokuszalt_ctrl.CanRedo():
            fokuszalt_ctrl.Redo()
    elif fokuszalt_ctrl.CanUndo():
        fokuszalt_ctrl.Undo()
    return True
