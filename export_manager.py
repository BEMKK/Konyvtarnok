import os
import logging
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sablon import general_sablon

# Betöltjük az Arial betűtípust a PDF-hez, hogy az összes magyar ékezet (ő, ű is) működjön
try:
    pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
    PDF_FONT = 'Arial'
except Exception as e:
    logging.warning(f"Nem sikerült betölteni az Arial betűtípust, visszatérés Helveticára: {e}")
    PDF_FONT = 'Helvetica'

def export_konyv_pdf(konyv, fajlnev):
    """PDF export a könyv címe alapján, ékezetes tartalommal."""
    sablon = general_sablon(konyv)
    
    c = canvas.Canvas(fajlnev, pagesize=A4)
    c.setFont(PDF_FONT, 11)

    y = 800
    for sor in sablon.splitlines():
        if sor.startswith("Példány rövid leírása:") and len(sor) > len("Példány rövid leírása:"):
            felirat = "Példány rövid leírása:"
            ertek = sor[len("Példány rövid leírása:"):].strip()
            
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

# export_manager.py

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

        try:
            export_konyv_pdf(konyv, fajl_utvonal)
            sikeres += 1
        except Exception as e:
            logging.error(f"Hiba a(z) {konyv.get('cim')} exportálásakor", exc_info=True)

    return sikeres
