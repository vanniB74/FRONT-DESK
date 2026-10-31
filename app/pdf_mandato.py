"""Generatore PDF del Mandato di Assistenza e Rappresentanza.

Approccio: usa il PDF del modulo ufficiale come sfondo FISSO e
sovrappone i dati variabili nelle posizioni esatte con pypdf.

Le coordinate sono state ricavate via OCR (tesseract) sull'immagine
del modulo a 120 DPI (993x1404 px) e convertite in punti PDF (595x842).
Formula: x_pdf = x_img * (595/993), y_pdf = 842 - y_img * (842/1404) - 6.

La firma di Cassano NON viene inclusa (sara apposta al momento);
viene sovrapposto solo il TIMBRO dell'associazione.
"""
from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from app.db import query
from config import Config

NAVY = colors.HexColor("#001C3A")
GRAY = colors.HexColor("#39546B")

MODULO_OFFICIALE = Config.BASE_DIR / "moduli" / "Mandato_di_Assistenza_e_Rappresentanza.pdf"


def _text(c: canvas.Canvas, x_pt: float, y_pt: float, text: str,
          font: str = "Helvetica", size: float = 9, color=NAVY):
    """Scrive testo in coordinate PDF (punti, origine bottom-left)."""
    if not text:
        return
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x_pt, y_pt, str(text))


def _overlay_timbro(c: canvas.Canvas):
    """Sovrappone SOLO il timbro (la firma di Cassano sara apposta al momento)."""
    timbro_path = Config.FILES_DIR / "timbro.png"
    if timbro_path.exists():
        try:
            c.drawImage(str(timbro_path), 400, 110, 130, 80,
                        mask='auto', preserveAspectRatio=True)
        except Exception:
            pass


def genera_pdf_mandato(cliente_id: int) -> bytes | None:
    """Genera il PDF del mandato per il cliente."""
    cliente = query("SELECT * FROM clienti WHERE id = ?", (cliente_id,), one=True)
    if not cliente:
        return None
    mandato = query(
        "SELECT * FROM mandati WHERE cliente_id = ? AND attivo = 1 ORDER BY id DESC LIMIT 1",
        (cliente_id,), one=True)
    servizi = []
    if mandato:
        servizi = query(
            """SELECT s.nome, g.nome AS gruppo_nome, g.codice
               FROM mandato_servizi ms
               JOIN servizi s ON s.id = ms.servizio_id
               JOIN servizi_gruppi g ON g.id = s.gruppo_id
               WHERE ms.mandato_id = ?
               ORDER BY g.ordine, s.ordine""", (mandato["id"],))

    overlay = io.BytesIO()
    c = canvas.Canvas(overlay, pagesize=A4)

    if MODULO_OFFICIALE.exists():
        _text(c, 114, 686, f"{cliente['cognome']} {cliente['nome']}")
        _text(c, 200, 671, cliente['luogo_nascita'] or "")
        _text(c, 410, 671, (cliente['data_nascita'] or ""))
        _text(c, 80, 656, (cliente['sesso'] or ""))
        _text(c, 410, 656, cliente['codice_fiscale'] or "")
        _text(c, 130, 645, cliente['cittadinanza'] or "")
        cap_prov = f"{cliente['residenza_cap'] or ''} {cliente['residenza_provincia'] or ''}".strip()
        _text(c, 410, 641, cap_prov)
        _text(c, 130, 629, f"{cliente['residenza_cap'] or ''} {cliente['residenza_provincia'] or ''}".strip())
        indirizzo = f"{cliente['residenza_indirizzo'] or ''} {cliente['residenza_civico'] or ''}".strip()
        _text(c, 200, 617, indirizzo)

        if mandato:
            _text(c, 200, 546, mandato['istituto_ente'] or "")
            _text(c, 200, 532, mandato['istituto_paese'] or "")
            collab = mandato['collaboratore_volontario'] or ""
            _text(c, 180, 416, collab)
            _text(c, 560, 387, mandato['data_firma'] if mandato['data_firma'] else "")
            _text(c, 640, 387, "BARI")
            if mandato['consenso_p1']:
                _text(c, 60, 230, "X", font="Helvetica-Bold", size=11)
            if mandato['consenso_p2']:
                _text(c, 60, 169, "X", font="Helvetica-Bold", size=11)
            _text(c, 100, 140, mandato['data_firma'] or "")
        _overlay_timbro(c)
    else:
        _fallback_pdf(c, cliente, mandato, servizi)

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


def _fallback_pdf(c: canvas.Canvas, cliente, mandato, servizi):
    """PDF da zero quando il modulo ufficiale non e disponibile."""
    from reportlab.lib.pagesizes import A4
    W, H = A4
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, H - 50, "MANDATO DI ASSISTENZA E RAPPRESENTANZA")
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 9)
    c.drawString(50, H - 62, "Patronato ACLI - Sezione Ceglie del Campo - Sede di BARI")

    y = H - 90
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "1. DATI ANAGRAFICI DELL'ASSISTITO/A")
    y -= 18
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    for r in [
        f"Cognome e Nome: {cliente['cognome']} {cliente['nome']}",
        f"Luogo di Nascita: {cliente['luogo_nascita'] or ''}    Data: {cliente['data_nascita'] or ''}",
        f"Sesso: {cliente['sesso'] or ''}    Codice Fiscale: {cliente['codice_fiscale'] or ''}",
        f"Cittadinanza: {cliente['cittadinanza'] or ''}    CAP/Prov: {cliente['residenza_cap'] or ''} {cliente['residenza_provincia'] or ''}",
        f"Residenza: {cliente['residenza_indirizzo'] or ''} {cliente['residenza_civico'] or ''}",
    ]:
        c.drawString(60, y, r)
        y -= 14

    y -= 10
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "2. OGGETTO DEL MANDATO")
    y -= 18
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    if mandato:
        c.drawString(60, y, f"Istituto/Ente: {mandato['istituto_ente'] or ''}")
        y -= 14
        c.drawString(60, y, f"Paese: {mandato['istituto_paese'] or ''}")
        y -= 18

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "Pratica relativa a:")
    y -= 14
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    if servizi:
        from collections import OrderedDict
        gruppi = OrderedDict()
        for s in servizi:
            gruppi.setdefault(s["gruppo_nome"], []).append(s["nome"])
        for g_nome, ss in gruppi.items():
            c.setFont("Helvetica-Bold", 9)
            c.drawString(70, y, g_nome)
            y -= 12
            c.setFont("Helvetica", 8)
            for sname in ss:
                c.drawString(80, y, f"- {sname}")
                y -= 10
            y -= 4
            if y < 200:
                c.showPage()
                y = H - 50
                c.setFont("Helvetica", 9)
    else:
        c.drawString(70, y, "(nessun servizio selezionato)")
        y -= 14

    if y < 200:
        c.showPage()
        y = H - 50

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "3. ATTESTAZIONE OPERATIVA E VALIDAZIONE SEDE")
    y -= 18
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    if mandato:
        c.drawString(60, y, f"Collaboratore volontario: {mandato['collaboratore_volontario'] or ''}")
        y -= 14
        c.drawString(60, y, f"Operatore / Sede: BARI    Data: {mandato['data_firma'] or ''}")
        y -= 14

    y -= 10
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "4. INFORMATIVA GDPR - CONSENSI")
    y -= 18
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    p1 = "SÌ" if (mandato and mandato["consenso_p1"]) else "NO"
    p2 = "SÌ" if (mandato and mandato["consenso_p2"]) else "NO"
    c.drawString(60, y, f"Punto 1 (obbligatorio) - Consenso al trattamento: {p1}")
    y -= 14
    c.drawString(60, y, f"Punto 2 (facoltativo) - Consenso ulteriore: {p2}")
    y -= 20
    if mandato:
        c.drawString(60, y, f"Data: {mandato['data_firma'] or ''}    Sede: BARI")

    _overlay_timbro(c)
    c.setFillColor(GRAY)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(400, 95, "(firma del Presidente e rappresentante legale")
    c.drawString(400, 88, "da apporsi in presenza dell'assistito)")
