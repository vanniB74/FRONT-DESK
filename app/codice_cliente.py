"""Generatore codice cliente."""
from __future__ import annotations

from datetime import date

from app.db import get_db, query
from config import Config


def genera_codice_cliente() -> str:
    today = date.today()
    aamm = f"{today.strftime('%y')}{today.strftime('%m')}"
    prefix = Config.CODICE_PREFIX
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT codice_cliente FROM clienti WHERE codice_cliente LIKE ? || '-%' ORDER BY codice_cliente DESC LIMIT 1",
            (prefix,),
        ).fetchone()
        next_n = 1
        if row:
            try:
                next_n = int(row["codice_cliente"].split("-")[-1]) + 1
            except Exception:
                pass
        codice = f"{prefix}-{aamm}-{next_n:04d}"
        while True:
            esiste = conn.execute("SELECT 1 FROM clienti WHERE codice_cliente = ?", (codice,)).fetchone()
            if not esiste:
                break
            next_n += 1
            codice = f"{prefix}-{aamm}-{next_n:04d}"
        return codice
    finally:
        conn.close()


def normalizza_codice_ricerca(s: str) -> str:
    if not s:
        return ""
    s = s.strip().upper().replace(" ", "").replace("-", "")
    if len(s) >= 10 and s.startswith(Config.CODICE_PREFIX):
        prefix_len = len(Config.CODICE_PREFIX)
        body = s[prefix_len:]
        if len(body) == 8:
            return f"{Config.CODICE_PREFIX}-{body[:4]}-{body[4:]}"
    return s


def cerca_cliente_codice(s: str):
    codice = normalizza_codice_ricerca(s)
    row = query("SELECT * FROM clienti WHERE codice_cliente = ?", (codice,), one=True)
    if row:
        return row
    like = "%" + s.strip().upper().replace(" ", "").replace("-", "") + "%"
    return query(
        "SELECT * FROM clienti WHERE REPLACE(REPLACE(UPPER(codice_cliente), ' ', ''), '-', '') LIKE ?",
        (like,),
        one=True,
    )
