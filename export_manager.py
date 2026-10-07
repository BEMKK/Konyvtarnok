import os
import logging
import wx
from datetime import date
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from konyv_lista import KonyvListaCtrl
from config_manager import load_settings, save_settings

# A mezők sorrendjét és feliratait a constants.py-ból importáljuk, hogy
# ugyanaz az egyetlen forrás írja le őket, mint a konyvdialogs.py-beli
# adatlap/szerkesztő dialógusokét - lásd a constants.py megjegyzését.
from constants import BIBLIOGRAFIAI_MEZO_DEFINICIOK, PELDANY_MEZO_DEFINICIOK

# Betöltjük az Arial betűtípust a PDF-hez, hogy az összes magyar ékezet (ő, ű is) működjön
try:
    pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
    PDF_FONT = 'Arial'
except Exception as e:
    logging.warning(f"Nem sikerült betölteni az Arial betűtípust, visszatérés Helveticára: {e}")
    PDF_FONT = 'Helvetica'

# A "Példány rövid leírása" mező felirata is a constants.py PELDANY_MEZO_DEFINICIOK
# listájából származik, nem szabad kézzel megismételni: így egy átnevezés után sem
# veszik el a kétsoros megjelenítés az export_konyv_pdf-ben.
ROVID_LEIRAS_FELIRAT = dict(PELDANY_MEZO_DEFINICIOK).get("rovid_leiras", "Példány rövid leírása:")


def katalogus_pdf(utvonal, konyvek, oszlopok, defs=None, cim_szoveg="Katalóguslap"):
    """Katalóguslap (táblázatos PDF) készítése.

    defs: {oszlopkulcs: (felirat, szélességi súly)}; alapértelmezés szerint a
    főlista KonyvListaCtrl.OSZLOP_DEFINICIOK-ja. Más listák (pl. a dezideráta)
    a saját definíciókészletüket adhatják át.
    """
    if defs is None:
        defs = KonyvListaCtrl.OSZLOP_DEFINICIOK
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
        os.startfile(utvonal)

def export_konyv_pdf(konyv, fajlnev):
    """PDF export a könyv címe alapján, ékezetes tartalommal."""
    sablon = general_sablon(konyv)
    
    c = canvas.Canvas(fajlnev, pagesize=A4)
    c.setFont(PDF_FONT, 11)

    y = 800
    for sor in sablon.splitlines():
        if sor.startswith(ROVID_LEIRAS_FELIRAT) and len(sor) > len(ROVID_LEIRAS_FELIRAT):
            felirat = ROVID_LEIRAS_FELIRAT
            ertek = sor[len(ROVID_LEIRAS_FELIRAT):].strip()
            
            c.drawString(50, y, felirat)
            y -= 18
            
            c.drawString(50, y, ertek)
            y -= 18
        else:
            c.drawString(50, y, sor)
            y -= 18
            
        if y < 50:
            c.showPage()
            c.setFont(PDF_FONT, 11)
            y = 800

    c.save()
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
    """Statisztikai jelentés exportálása PDF fájlba."""
    c = canvas.Canvas(fajlnev, pagesize=A4)
    c.setFont(PDF_FONT, 10)

    y = 800
    for sor in szoveg.splitlines():
        # Monospace/tabulált elrendezés szimulálása
        c.drawString(50, y, sor)
        y -= 15
        if y < 50:
            c.showPage()
            c.setFont(PDF_FONT, 10)
            y = 800

    c.save()

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

def tomeges_export_pdf(konyvek_listaja, mentesi_utvonal, fajl_letezik_callback=None):
    sikeres = 0
    mindent_felulir = False

    for konyv in konyvek_listaja:
        if not konyv.get('cim'):
            continue

        fajlnev = get_biztonsagos_pdf_fajlnev(konyv)
        fajl_utvonal = os.path.join(mentesi_utvonal, fajlnev)

        if os.path.exists(fajl_utvonal) and not mindent_felulir and fajl_letezik_callback:
            valasz = fajl_letezik_callback(fajlnev)
            
            if valasz == "KIHAGYAS":
                continue
            elif valasz == "MINDET_FELULIR":
                mindent_felulir = True
            elif valasz == "OSSZES_KIHAGYASA":
                break

        try:
            export_konyv_pdf(konyv, fajl_utvonal)
            sikeres += 1
        except Exception as e:
            logging.error(f"Hiba a(z) {konyv.get('cim')} exportálásakor", exc_info=True)

    return sikeres
