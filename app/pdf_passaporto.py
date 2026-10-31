"""Generatore PDF del Passaporto cliente.

Foglio A4 con le 4 immagini in formato biglietto da visita (~85x54 mm),
titolo sotto ogni immagine e dati del documento.
"""
from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Image as RLImage
from PIL import Image as PILImage

from app.db import query
from config import Config

NAVY = colors.HexColor("#001C3A")
GOLD = colors.HexColor("#C9A24B")
GRAY = colors.HexColor("#39546B")

TIPI_DOC_LABEL = {
    "ci_fronte": "Carta d'identità - fronte",
    "ci_retro": "Carta d'identità - retro",
    "ts_fronte": "Tessera sanitaria/CF - fronte",
    "ts_retro": "Tessera sanitaria/CF - retro",
}
TIPI_DOC_ORDER = ["ci_fronte", "ci_retro", "ts_fronte", "ts_retro"]


def genera_pdf_passaporto(cliente_id: int) -> bytes | None:
    """Genera il PDF del Passaporto. Ritorna None se non completo."""
    cliente = query("SELECT * FROM clienti WHERE id = ?", (cliente_id,), one=True)
    if not cliente:
        return None
    docs = query("SELECT * FROM documenti_cliente WHERE cliente_id = ?", (cliente_id,))
    docs_per_tipo = {d["tipo"]: dict(d) for d in docs}
    if len(docs_per_tipo) < 4:
        return None

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, H - 20 * mm, "PASSAPORTO CLIENTE")
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, H - 26 * mm,
                 f"{cliente['cognome']} {cliente['nome']} — Cod. {cliente['codice_cliente']}")
    if cliente["codice_fiscale"]:
        c.drawString(20 * mm, H - 31 * mm, f"Codice fiscale: {cliente['codice_fiscale']}")

    card_w, card_h = 85 * mm, 54 * mm
    margin_x = (W - 2 * card_w - 10 * mm) / 2
    positions = [
        (margin_x, H - 70 * mm - card_h),
        (margin_x + card_w + 10 * mm, H - 70 * mm - card_h),
        (margin_x, H - 70 * mm - 2 * card_h - 25 * mm),
        (margin_x + card_w + 10 * mm, H - 70 * mm - 2 * card_h - 25 * mm),
    ]

    for i, tipo in enumerate(TIPI_DOC_ORDER):
        doc = docs_per_tipo.get(tipo)
        if not doc:
            continue
        x, y = positions[i]
        c.setStrokeColor(NAVY)
        c.setLineWidth(0.6)
        c.rect(x, y, card_w, card_h, stroke=1, fill=0)
        try:
            percorso = Config.FILES_DIR / doc["file_path"]
            if percorso.exists():
                img = PILImage.open(str(percorso))
                iw, ih = img.size
                target_w = 75 * mm
                target_h = 40 * mm
                ratio = min(target_w / iw, target_h / ih)
                draw_w = iw * ratio
                draw_h = ih * ratio
                img_x = x + (card_w - draw_w) / 2
                img_y = y + card_h - draw_h - 4 * mm
                tmp = io.BytesIO()
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(tmp, "JPEG", quality=80)
                tmp.seek(0)
                c.drawImage(tmp, img_x, img_y, draw_w, draw_h)
        except Exception as e:
            c.setFillColor(GRAY)
            c.setFont("Helvetica-Oblique", 8)
            c.drawCentredString(x + card_w / 2, y + card_h / 2, f"[immagine non disponibile: {e}]")

        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + 2 * mm, y + 9 * mm, TIPI_DOC_LABEL.get(tipo, tipo))
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 7)
        if doc.get("numero_codice"):
            c.drawString(x + 2 * mm, y + 5.5 * mm, f"Codice: {doc['numero_codice']}")
        if doc.get("data_scadenza"):
            c.drawString(x + 2 * mm, y + 3 * mm, f"Scadenza: {doc['data_scadenza']}")
        if doc.get("ente_emittente"):
            c.drawString(x + 2 * mm, y + 0.5 * mm, f"Emesso da: {doc['ente_emittente']}")

    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, 10 * mm,
                        "CSI - Centro Servizi Integrati — Documento generato dal sistema di front office")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
