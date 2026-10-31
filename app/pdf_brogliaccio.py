"""Generatore PDF del Brogliaccio unico.

Ordine:
1. Copertina: data, giorno e ora appuntamento, consulente, oggetto,
   codice cliente, numero pratica, primo appuntamento richiesto, operatore.
2. Modulo privacy compilato + modulo mandato compilato (con servizi omnibus,
   timbro e firma).
3. Pagina A4 del Passaporto.
"""
from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from pypdf import PdfWriter

from app.db import query

NAVY = colors.HexColor("#001C3A")
GOLD = colors.HexColor("#C9A24B")
GRAY = colors.HexColor("#39546B")


def genera_pdf_brogliaccio(app_id: int) -> bytes | None:
    """Genera il PDF unico del brogliaccio."""
    app = query(
        """SELECT a.*, c.cognome || ' ' || c.nome AS consulente_nome,
                  cl.cognome || ' ' || cl.nome AS cliente_nome, cl.id AS cliente_id,
                  cl.codice_cliente, cl.numero_pratica, cl.data_nascita, cl.luogo_nascita,
                  cl.codice_fiscale,
                  o.nome || ' ' || o.cognome AS operatore_nome
           FROM appuntamenti a
           LEFT JOIN consulenti c ON c.id = a.consulente_id
           LEFT JOIN clienti cl ON cl.id = a.cliente_id
           LEFT JOIN operatori o ON o.id = a.operatore_id
           WHERE a.id = ?""",
        (app_id,),
        one=True,
    )
    if not app:
        return None

    writer = PdfWriter()

    # --- Pagina 1: Copertina ---
    copertina = _genera_copertina(app)
    writer.append(io.BytesIO(copertina))

    # --- Pagine 2-3: Privacy + Mandato ---
    if app["cliente_id"]:
        from app.pdf_privacy import genera_pdf_privacy
        from app.pdf_mandato import genera_pdf_mandato

        pdf_priv = genera_pdf_privacy(app["cliente_id"])
        pdf_mand = genera_pdf_mandato(app["cliente_id"])
        if pdf_priv:
            writer.append(io.BytesIO(pdf_priv))
        if pdf_mand:
            writer.append(io.BytesIO(pdf_mand))

        # --- Pagina Passaporto ---
        from app.pdf_passaporto import genera_pdf_passaporto

        pdf_pass = genera_pdf_passaporto(app["cliente_id"])
        if pdf_pass:
            writer.append(io.BytesIO(pdf_pass))

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


def _genera_copertina(app) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    # Banda navy in alto
    c.setFillColor(NAVY)
    c.rect(0, H - 50 * mm, W, 50 * mm, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(20 * mm, H - 25 * mm, "BROGLIACCIO")
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, H - 35 * mm, "CSI - Centro Servizi Integrati")
    c.drawString(20 * mm, H - 41 * mm, "Patronato ACLI — Sede di BARI")

    # Box dati appuntamento
    y = H - 65 * mm
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(20 * mm, y, "Dati appuntamento")
    y -= 8 * mm
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 11)

    try:
        d = datetime.strptime(app["data"], "%Y-%m-%d").date()
        weekday = [
            "Lunedì",
            "Martedì",
            "Mercoledì",
            "Giovedì",
            "Venerdì",
            "Sabato",
            "Domenica",
        ][d.weekday()]
        data_str = f"{weekday} {d.strftime('%d/%m/%Y')}"
    except Exception:
        data_str = app["data"]

    righe = [
        ("Data", data_str),
        ("Ora", f"{app['ora_inizio']} - {app['ora_fine']}"),
        ("Consulente", app["consulente_nome"] or ""),
        ("Oggetto", app["oggetto"] or ""),
        ("Cliente", f"{app['cliente_nome'] or ''} ({app['codice_cliente'] or ''})"),
        ("Codice fiscale", app["codice_fiscale"] or ""),
        ("Data di nascita", f"{app['data_nascita'] or ''} a {app['luogo_nascita'] or ''}"),
        ("Numero pratica", app["numero_pratica"] or ""),
        ("Operatore", app["operatore_nome"] or ""),
        ("Provenienza", app["provenienza"] or ""),
        ("Stato", app["stato"] or ""),
    ]
    for label, val in righe:
        c.setFillColor(GRAY)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(20 * mm, y, label + ":")
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 10)
        c.drawString(60 * mm, y, val)
        y -= 7 * mm

    # Primo appuntamento richiesto
    y -= 6 * mm
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "Primo appuntamento richiesto:")
    y -= 6 * mm
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawString(25 * mm, y, app["oggetto"] or "(vedi oggetto sopra)")

    # Mandato omnibus: sezione outline servizi
    y -= 10 * mm
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "Mandato omnibus — servizi di interesse")
    y -= 6 * mm
    if app["cliente_id"]:
        servizi = query(
            """SELECT s.nome, g.nome AS gruppo_nome, g.codice
               FROM cliente_servizi_interesse csi
               JOIN servizi s ON s.id = csi.servizio_id
               JOIN servizi_gruppi g ON g.id = s.gruppo_id
               WHERE csi.cliente_id = ?
               ORDER BY g.ordine, s.ordine LIMIT 60""",
            (app["cliente_id"],),
        )
        from collections import OrderedDict

        gruppi = OrderedDict()
        for s in servizi:
            gruppi.setdefault(s["gruppo_nome"], []).append(s["nome"])
        if gruppi:
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(NAVY)
            for g_nome, ss in gruppi.items():
                c.drawString(25 * mm, y, g_nome)
                y -= 4.5 * mm
                c.setFont("Helvetica", 8)
                c.setFillColor(colors.black)
                for sname in ss:
                    c.drawString(30 * mm, y, f"• {sname}")
                    y -= 4 * mm
                    if y < 30 * mm:
                        break
                c.setFont("Helvetica-Bold", 9)
                c.setFillColor(NAVY)
                y -= 1 * mm
                if y < 30 * mm:
                    break
        else:
            c.setFillColor(GRAY)
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(25 * mm, y, "(nessun servizio di interesse registrato)")

    # Footer
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawCentredString(
        W / 2,
        10 * mm,
        "CSI Front Office — Brogliaccio generato il " + datetime.now().strftime("%d/%m/%Y %H:%M"),
    )

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
