import os
import logging
from enum import Enum
import wx
from datetime import date
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from utils import fajl_megnyitasa
from config_manager import load_settings, save_settings

# A mezők sorrendjét és feliratait a constants.py-ból importáljuk, hogy
# ugyanaz az egyetlen forrás írja le őket, mint a konyvdialogs.py-beli
# adatlap/szerkesztő dialógusokét - lásd a constants.py megjegyzését.
from constants import BIBLIOGRAFIAI_MEZO_DEFINICIOK, PELDANY_MEZO_DEFINICIOK, OSZLOP_DEFINICIOK

# Betöltjük az Arial betűtípust a PDF-hez, hogy az összes magyar ékezet (ő, ű is) működjön
try:
    pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
    PDF_FONT = 'Arial'
except Exception as e:
    logging.warning(f"Nem sikerült betölteni az Arial betűtípust, visszatérés Helveticára: {e}")
    PDF_FONT = 'Helvetica'


def _monospace_betutipus_regisztralasa():
    """Egyenközű (monospace) betűtípust regisztrál a statisztikai jelentéshez.

    Sorrendben: Courier New (Windows), DejaVu Sans Mono, Consolas. Mindhárom
    tartalmazza az ő/ű betűket. Ha egyik sem érhető el, a beépített Courier a
    tartalék - az igazítás ekkor is megmarad, de az ő/ű nem jelenik meg helyesen.
    """
    for nev, fajl in (("CourierNew", "cour.ttf"),
                      ("DejaVuSansMono", "DejaVuSansMono.ttf"),
                      ("Consolas", "consola.ttf")):
        try:
            pdfmetrics.registerFont(TTFont(nev, fajl))
            return nev
        except Exception:
            continue
    logging.warning("Nem található egyenközű TTF betűtípus, visszatérés Courier-re "
                    "(az ő/ű betűk hibásan jelenhetnek meg a statisztikai PDF-ben).")
    return 'Courier'


PDF_MONO_FONT = _monospace_betutipus_regisztralasa()

# A "Példány rövid leírása" mező felirata is a constants.py PELDANY_MEZO_DEFINICIOK
# listájából származik, nem szabad kézzel megismételni: így egy átnevezés után sem
# veszik el a kétsoros megjelenítés az export_konyv_pdf-ben.
ROVID_LEIRAS_FELIRAT = dict(PELDANY_MEZO_DEFINICIOK).get("rovid_leiras", "Példány rövid leírása:")


def katalogus_pdf(utvonal, konyvek, oszlopok, defs=None, cim_szoveg="Katalóguslap"):
    """Katalóguslap (táblázatos PDF) készítése.

    defs: {oszlopkulcs: (felirat, szélességi súly)}; alapértelmezés szerint a
    főlista constants.OSZLOP_DEFINICIOK-ja. Más listák (pl. a dezideráta)
    a saját definíciókészletüket adhatják át.
    """
    if defs is None:
        defs = OSZLOP_DEFINICIOK
    oszlopok = [k for k in oszlopok if k in defs]

    # Sok oszlopnál automatikusan kisebb betű, hogy ne kelljen a felhasználóra bízni
    n = len(oszlopok)
    meret = 8 if n <= 7 else 7 if n <= 10 else 6

    cella = ParagraphStyle("cella", fontName=PDF_FONT, fontSize=meret, leading=meret + 2)
    fejlec = ParagraphStyle("fejlec", parent=cella, textColor=colors.white)
    cim = ParagraphStyle("cim", fontName=PDF_FONT, fontSize=12, leading=15)

    adat = [[Paragraph(escape(defs[k][0]), fejlec) for k in oszlopok]]
    for kv in konyvek:
        adat.append([Paragraph(escape(str(kv.get(k) or "")), cella) for k in oszlopok])

    doc = SimpleDocTemplate(utvonal, pagesize=landscape(A4), title=cim_szoveg,
                            leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=40)
    suly = [defs[k][1] for k in oszlopok]
    szelessegek = [doc.width * s / sum(suly) for s in suly]

    tabla = Table(adat, colWidths=szelessegek, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#444444")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
    ]))

    def oldalszam(canvas, doc):
        canvas.setFont(PDF_FONT, 8)
        canvas.drawRightString(doc.pagesize[0] - 30, 20, f"{doc.page}. oldal")

    fejsor = Paragraph(
        f"{escape(cim_szoveg)} – {len(konyvek)} tétel – {date.today():%Y.%m.%d.}", cim)
    doc.build([fejsor, Spacer(1, 8), tabla],
              onFirstPage=oldalszam, onLaterPages=oldalszam)


def katalogus_mentese(szulo, sorok, oszlopok, defs=None,
                      cim_szoveg="Katalóguslap", alap_fajlnev="katalogus.pdf"):
    """Fájlnevet kér, elkészíti a katalóguslapot, majd felajánlja a megnyitását.

    A főablak és a dezideráta-kezelő is ezt használja, hogy a mentési folyamat
    (fájldialógus, utolsó mappa megjegyzése, hibakezelés) egy helyen éljen.
    """
    if not sorok or not oszlopok:
        wx.MessageBox(
            "A katalóguslapot nem lehet exportálni: a lista vagy az oszlopkészlet üres.",
            cim_szoveg, wx.OK | wx.ICON_WARNING, szulo)
        return

    config = load_settings()
    with wx.FileDialog(
        szulo, f"{cim_szoveg} mentése PDF-be",
        defaultDir=config.get("last_json_dir", ""),
        defaultFile=alap_fajlnev,
        wildcard="PDF fájl (*.pdf)|*.pdf",
        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
    ) as dlg:
        if dlg.ShowModal() != wx.ID_OK:
            return
        utvonal = dlg.GetPath()

    config["last_json_dir"] = os.path.dirname(utvonal)
    save_settings(config)

    try:
        with wx.BusyCursor():
            katalogus_pdf(utvonal, sorok, oszlopok, defs=defs, cim_szoveg=cim_szoveg)
    except Exception as e:
        logging.error(f"Hiba a(z) {cim_szoveg} készítésekor", exc_info=True)
        wx.MessageBox(f"Hiba történt a PDF készítésekor:\n{e}", "Hiba",
                      wx.OK | wx.ICON_ERROR, szulo)
        return

    if wx.MessageBox(f"A(z) {cim_szoveg} elkészült. Megnyitja most?", cim_szoveg,
                     wx.YES_NO | wx.ICON_QUESTION, szulo) == wx.YES:
        try:
            fajl_megnyitasa(utvonal)
        except Exception as e:
            logging.error(f"Nem sikerült megnyitni: {utvonal}", exc_info=True)
            wx.MessageBox(f"Nem sikerült megnyitni a fájlt:\n{e}", "Hiba",
                          wx.OK | wx.ICON_ERROR, szulo)

# Az egyszerű (canvas-alapú) PDF-ek oldalbeállításai
_PDF_BAL_MARGO = 50
_PDF_ALSO_MARGO = 50
_PDF_FELSO_Y = 800


def _tordelt_sorok(sor, betutipus, meret, max_szelesseg):
    """Egy szövegsort a megadott szélességhez igazítva több sorra tör.

    - Ami elfér, azt változatlanul adja vissza (a soron belüli szóközök,
      igazítások megmaradnak, pl. a statisztikai jelentésben).
    - A sor eleji behúzást a tördelt sorok is megkapják.
    - Szóközök mentén tör; ha egyetlen szó (pl. hosszú URL) önmagában is
      szélesebb a megengedettnél, karakterenként vágja.
    """
    if not sor.strip():
        return [""]
    if pdfmetrics.stringWidth(sor, betutipus, meret) <= max_szelesseg:
        return [sor]

    behuzas = sor[:len(sor) - len(sor.lstrip(" "))]
    hely = max(max_szelesseg - pdfmetrics.stringWidth(behuzas, betutipus, meret), 50)

    eredmeny = []
    for resz in simpleSplit(sor.strip(), betutipus, meret, hely):
        while pdfmetrics.stringWidth(resz, betutipus, meret) > hely and len(resz) > 1:
            n = len(resz)
            while n > 1 and pdfmetrics.stringWidth(resz[:n], betutipus, meret) > hely:
                n -= 1
            eredmeny.append(behuzas + resz[:n])
            resz = resz[n:]
        eredmeny.append(behuzas + resz)
    return eredmeny


def _sorok_pdf_be(sorok, fajlnev, meret, sorkoz, betutipus=None):
    """Szöveges sorokat ír A4-es PDF-be: tördeli a hosszú sorokat, és
    szükség szerint új oldalt kezd. A betűtípus alapértelmezése a PDF_FONT."""
    betutipus = betutipus or PDF_FONT
    c = canvas.Canvas(fajlnev, pagesize=A4)
    max_szelesseg = A4[0] - 2 * _PDF_BAL_MARGO
    c.setFont(betutipus, meret)
    y = _PDF_FELSO_Y

    for sor in sorok:
        for resz in _tordelt_sorok(sor, betutipus, meret, max_szelesseg):
            if y < _PDF_ALSO_MARGO:
                c.showPage()
                c.setFont(betutipus, meret)
                y = _PDF_FELSO_Y
            c.drawString(_PDF_BAL_MARGO, y, resz)
            y -= sorkoz

    c.save()


def export_konyv_pdf(konyv, fajlnev):
    """PDF export a könyv címe alapján, ékezetes tartalommal."""
    sorok = []
    for sor in general_sablon(konyv).splitlines():
        if sor.startswith(ROVID_LEIRAS_FELIRAT) and len(sor) > len(ROVID_LEIRAS_FELIRAT):
            # A hosszú leírás a felirat alatt, külön sorban (és tördelve) jelenik meg
            sorok.append(ROVID_LEIRAS_FELIRAT)
            sorok.append(sor[len(ROVID_LEIRAS_FELIRAT):].strip())
        else:
            sorok.append(sor)

    _sorok_pdf_be(sorok, fajlnev, meret=11, sorkoz=18)
    logging.info(f"PDF mentve: {fajlnev}")

def general_sablon(konyv):
    """Visszaadja a sablon szövegét a könyv adataival kitöltve.

    A mezők sorrendjét és feliratait a constants.py-beli
    BIBLIOGRAFIAI_MEZO_DEFINICIOK / PELDANY_MEZO_DEFINICIOK listák adják -
    ugyanaz az egyetlen forrás, amit a konyvdialogs.py-beli adatlap- és
    szerkesztő dialógusok (MEZO_DEFINICIOK) is használnak -, hogy a
    PDF-exportban szereplő mezők/feliratok sose térjenek el csendben azoktól.
    """
    sorok = ["Bibliográfiai adatok"]
    for kulcs, felirat in BIBLIOGRAFIAI_MEZO_DEFINICIOK:
        sorok.append(f"{felirat} {konyv.get(kulcs, '')}")

    sorok.append("")
    sorok.append("Példány adatai")
    for kulcs, felirat in PELDANY_MEZO_DEFINICIOK:
        sorok.append(f"{felirat} {konyv.get(kulcs, '')}")

    return "\n".join(sorok)

def export_statisztika_pdf(szoveg, fajlnev):
    """Statisztikai jelentés exportálása PDF fájlba.

    Egyenközű betűtípussal készül, hogy a szóközökkel/tabulátorral igazított
    oszlopok a PDF-ben is egymás alá kerüljenek. A tabulátorokat 8 karakteres
    tabulátorpozíciókra bontja szóközökké (a TTF betűtípusok nem rajzolnak
    tabulátor-karaktert).
    """
    sorok = [sor.expandtabs(8) for sor in szoveg.splitlines()]
    _sorok_pdf_be(sorok, fajlnev, meret=9, sorkoz=13, betutipus=PDF_MONO_FONT)

def get_biztonsagos_pdf_fajlnev(konyv):
    cim = konyv.get('cim', '')
    biztonsagos_cim = "".join([c for c in cim if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
    if not biztonsagos_cim:
        biztonsagos_cim = "konyv"

    ev = str(konyv.get('ev', '')).strip()
    biztonsagos_ev = "".join([c for c in ev if c.isalnum() or c in ('-', '_')]).rstrip()

    if biztonsagos_ev:
        return f"{biztonsagos_cim} ({biztonsagos_ev}).pdf"
    return f"{biztonsagos_cim} (nincs_ev_megadva).pdf"

class FajlUtkozesValasz(str, Enum):
    """A tomeges_export_pdf fajl_letezik_callback-jének lehetséges válaszai.

    A str-öröklés miatt a korábbi szöveges értékek ("KIHAGYAS", "MINDET_FELULIR",
    "OSSZES_KIHAGYASA") egyenlők a megfelelő taggal, így a régi, szöveget
    visszaadó callbackek is működnek. Új kódban a tagokat érdemes használni.
    """
    FELULIR = "FELULIR"
    KIHAGYAS = "KIHAGYAS"
    MINDET_FELULIR = "MINDET_FELULIR"
    OSSZES_KIHAGYASA = "OSSZES_KIHAGYASA"


class ExportEredmeny(int):
    """A tömeges export eredménye.

    Visszafelé kompatibilis: egész számként viselkedik, értéke a sikeresen
    exportált fájlok száma (mint korábban), de a további adatok is elérhetők:

      .sikeres       - sikeresen exportált fájlok száma
      .hibak         - a hibás fájlok listája: [(könyvcím, hibaüzenet), ...]
      .hibas         - a hibás fájlok száma
      .kihagyott     - a kihagyott könyvek száma (cím nélküli, vagy a
                       felhasználó által kihagyott)
    """
    def __new__(cls, sikeres, hibak, kihagyott):
        peldany = super().__new__(cls, sikeres)
        peldany.sikeres = sikeres
        peldany.hibak = list(hibak)
        peldany.kihagyott = kihagyott
        return peldany

    @property
    def hibas(self):
        return len(self.hibak)


def tomeges_export_pdf(konyvek_listaja, mentesi_utvonal, fajl_letezik_callback=None):
    """Több könyv exportálása PDF-be a megadott mappába.

    fajl_letezik_callback(fajlnev) egy már létező fájlnál hívódik, és egy
    FajlUtkozesValasz tagot ad vissza (FELULIR / KIHAGYAS / MINDET_FELULIR /
    OSSZES_KIHAGYASA). Más (pl. None) válasz felülírást jelent.

    Visszatérés: ExportEredmeny (egészként a sikeres fájlok száma).
    """
    sikeres = 0
    kihagyott = 0
    hibak = []
    mindent_felulir = False
    konyvek = list(konyvek_listaja)

    for sorszam, konyv in enumerate(konyvek):
        if not konyv.get('cim'):
            kihagyott += 1
            continue

        fajlnev = get_biztonsagos_pdf_fajlnev(konyv)
        fajl_utvonal = os.path.join(mentesi_utvonal, fajlnev)

        if os.path.exists(fajl_utvonal) and not mindent_felulir and fajl_letezik_callback:
            valasz = fajl_letezik_callback(fajlnev)

            if valasz == FajlUtkozesValasz.KIHAGYAS:
                kihagyott += 1
                continue
            elif valasz == FajlUtkozesValasz.MINDET_FELULIR:
                mindent_felulir = True
            elif valasz == FajlUtkozesValasz.OSSZES_KIHAGYASA:
                # Ez a könyv és az összes hátralévő kihagyottnak számít
                kihagyott += len(konyvek) - sorszam
                break

        try:
            export_konyv_pdf(konyv, fajl_utvonal)
            sikeres += 1
        except Exception as e:
            logging.error(f"Hiba a(z) {konyv.get('cim')} exportálásakor", exc_info=True)
            hibak.append((konyv.get('cim'), str(e)))

    return ExportEredmeny(sikeres, hibak, kihagyott)
