"""Audit log."""
from __future__ import annotations

from typing import Optional

from app.db import get_db


def log(operatore_id: Optional[int], azione: str, record_tipo: str = "",
        record_id: str = "", dettagli: str = "", ip: str = "") -> None:
    try:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO audit_log (operatore_id, azione, record_tipo, record_id, dettagli, ip) VALUES (?, ?, ?, ?, ?, ?)",
                (operatore_id, azione, record_tipo, str(record_id), dettagli, ip),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
