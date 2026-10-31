"""Loader servizi CSV."""
from __future__ import annotations

import csv
from pathlib import Path

from app.db import query, transaction
from config import Config


def conta_servizi() -> tuple[int, int]:
    gruppi = query("SELECT COUNT(*) AS c FROM servizi_gruppi", one=True)["c"]
    servizi = query("SELECT COUNT(*) AS c FROM servizi", one=True)["c"]
    return gruppi, servizi


def lista_gruppi_e_servizi():
    gruppi = query("SELECT * FROM servizi_gruppi ORDER BY ordine, nome")
    out = []
    for g in gruppi:
        servizi = query("SELECT * FROM servizi WHERE gruppo_id = ? ORDER BY ordine, nome", (g["id"],))
        out.append({"gruppo": dict(g), "servizi": [dict(s) for s in servizi]})
    return out


def importa_servizi_csv(csv_path: str | None = None):
    path = Path(csv_path) if csv_path else Config.SERVICES_CSV
    if not path.exists():
        return 0, 0
    gruppi = {}
    servizi = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gruppo_codice = (row.get("gruppo_codice") or row.get("codice_gruppo") or "").strip()
            gruppo_nome = (row.get("gruppo_nome") or row.get("nome_gruppo") or "Altro").strip()
            servizio_nome = (row.get("servizio") or row.get("nome") or "").strip()
            if not gruppo_codice and not gruppo_nome and not servizio_nome:
                continue
            if gruppo_codice not in gruppi:
                gruppi[gruppo_codice] = {"codice": gruppo_codice, "nome": gruppo_nome or "Altro"}
            if servizio_nome:
                servizi.append((gruppo_codice, servizio_nome))
    with transaction() as conn:
        for idx, (codice, data) in enumerate(gruppi.items()):
            existing = conn.execute("SELECT id FROM servizi_gruppi WHERE codice = ?", (codice,)).fetchone()
            if not existing:
                conn.execute("INSERT INTO servizi_gruppi (codice, nome, ordine) VALUES (?, ?, ?)", (codice or f"G{idx}", data["nome"], idx))
            else:
                conn.execute("UPDATE servizi_gruppi SET nome = ?, ordine = ? WHERE id = ?", (data["nome"], idx, existing["id"]))
        for idx, (codice, nome) in enumerate(servizi):
            gruppo = conn.execute("SELECT id FROM servizi_gruppi WHERE codice = ?", (codice or "",)).fetchone()
            if not gruppo:
                continue
            conn.execute("INSERT OR IGNORE INTO servizi (gruppo_id, nome, ordine) VALUES (?, ?, ?)", (gruppo["id"], nome, idx))
    return conta_servizi()
