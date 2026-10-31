"""Generatore PDF del modulo Privacy.

Approccio: PDF del modulo ufficiale come sfondo FISSO + overlay dati variabili
con coordinate OCR precise (vedi pdf_mandato.py per la metodologia).

Solo timbro; la firma di Cassano NON e inclusa (sara apposta al momento).
"""
from __future__ import annotations

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from app.db import query
from config import Config

NAVY = colors.HexColor("#001C3A")
GRAY = colors.HexColor("#39546B")

MODULO_OFFICIALE = Config.BASE_DIR / "moduli" / "Modulo_Privacy.pdf"


def _text(c: canvas.Canvas, x_pt: float, y_pt: float, text: str,
          font: str = "Helvetica", size: float = 9, color=NAVY):
    if not text:
        return
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x_pt, y_pt, str(text))


def _overlay_timbro(c: canvas.Canvas):
    """Solo timbro; la firma sara apposta al momento."""
    timbro_path = Config.FILES_DIR / "timbro.png"
    if timbro_path.exists():
        try:
            c.drawImage(str(timbro_path), 400, 110, 130, 80,
                        mask='auto', preserveAspectRatio=True)
        except Exception:
            pass


def genera_pdf_privacy(cliente_id: int) -> bytes | None:
    cliente = query("SELECT * FROM clienti WHERE id = ?", (cliente_id,), one=True)
    if not cliente:
        return None
    privacy = query(
        "SELECT * FROM privacy_consenso WHERE cliente_id = ? ORDER BY id DESC LIMIT 1",
        (cliente_id,), one=True)

    overlay = io.BytesIO()
    c = canvas.Canvas(overlay, pagesize=A4)

    if MODULO_OFFICIALE.exists():
        _text(c, 80, 682, cliente['sesso'] or "")
        _text(c, 200, 645, cliente['codice_fiscale'] or "")
        _text(c, 470, 645, cliente['cittadinanza'] or "")
        _text(c, 200, 670, f"{cliente['residenza_cap'] or ''} {cliente['residenza_provincia'] or ''}".strip())
        _text(c, 250, 657, f"{cliente['residenza_indirizzo'] or ''} {cliente['residenza_civico'] or ''}".strip())
        _text(c, 200, 700, f"{cliente['cognome']} {cliente['nome']}")

        if privacy:
            c1 = "SÌ" if privacy["consenso1"] == "S" else "NO"
            c2 = "SÌ" if privacy["consenso2"] == "S" else "NO"
            c3 = "SÌ" if privacy["consenso3"] == "S" else "NO"
            _text(c, 130, 180, c1, font="Helvetica-Bold", size=10)
            _text(c, 130, 114, c2, font="Helvetica-Bold", size=10)
            _text(c, 130, 50, c3, font="Helvetica-Bold", size=10)
            _text(c, 100, 503, privacy['data'] or "")

        _overlay_timbro(c)
    else:
        _fallback_pdf(c, cliente, privacy)

    c.showPage()
    c.save()
    overlay.seek(0)

    if MODULO_OFFICIALE.exists():
        try:
            from pypdf import PdfReader, PdfWriter
            base = PdfReader(str(MODULO_OFFICIALE))
            overlay_pdf = PdfReader(overlay)
            writer = PdfWriter()
            for i, page in enumerate(base.pages):
                if i < len(overlay_pdf.pages):
                    page.merge_page(overlay_pdf.pages[i])
                writer.add_page(page)
            out = io.BytesIO()
            writer.write(out)
            out.seek(0)
            return out.read()
        except Exception:
            overlay.seek(0)
            return overlay.read()
    return overlay.read()


def _fallback_pdf(c: canvas.Canvas, cliente, privacy):
    from reportlab.lib.pagesizes import A4
    W, H = A4
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, H - 50, "MODULO PRIVACY")
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 9)
    c.drawString(50, H - 62, "Patronato ACLI - Informativa ex art. 13 GDPR")

    y = H - 90
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Dati dell'interessato")
    y -= 18
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    for r in [
        f"Cognome e Nome: {cliente['cognome']} {cliente['nome']}",
        f"Codice Fiscale: {cliente['codice_fiscale'] or ''}",
        f"Sesso: {cliente['sesso'] or ''}    Cittadinanza: {cliente['cittadinanza'] or ''}",
        f"Residenza: {cliente['residenza_indirizzo'] or ''} {cliente['residenza_civico'] or ''} "
        f"{cliente['residenza_cap'] or ''} {cliente['residenza_provincia'] or ''}",
    ]:
        c.drawString(60, y, r)
        y -= 14

    y -= 12
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Consenso al trattamento dei dati")
    y -= 18
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    if privacy:
        c.drawString(60, y, f"1. Consenso al trattamento per finalita istituzionali: {'SI' if privacy['consenso1']=='S' else 'NO'}")
        y -= 14
        c.drawString(60, y, f"2. Consenso al trattamento per finalita statistiche: {'SI' if privacy['consenso2']=='S' else 'NO'}")
        y -= 14
        c.drawString(60, y, f"3. Consenso alla comunicazione a terzi: {'SI' if privacy['consenso3']=='S' else 'NO'}")
        y -= 20
        c.drawString(60, y, f"Data: {privacy['data'] or ''}    Sede: BARI")
    else:
        c.drawString(60, y, "(privacy non ancora registrata)")

    _overlay_timbro(c)
    c.setFillColor(GRAY)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(400, 95, "(firma del Presidente e rappresentante legale")
    c.drawString(400, 88, "da apporsi in presenza dell'interessato)")
