"""Sincronizzazione siti esterni."""
from __future__ import annotations

from datetime import date, timedelta

from app.db import query, transaction


def _log_sync(consulente_id, dettagli, stato="ok", errore=""):
    with transaction() as conn:
        conn.execute("INSERT INTO sync_log (tipo, direzione, consulente_id, dettagli, stato, errore) VALUES ('external', 'in', ?, ?, ?, ?)", (consulente_id, dettagli, stato, errore))


def sincronizza_tutti() -> None:
    siti = query("SELECT * FROM siti_esterni WHERE attivo = 1")
    for s in siti:
        try:
            sincronizza_sito(s)
        except Exception as e:
            _log_sync(None, f"sito={s['id']} {s['nome']}", "error", str(e))


def sincronizza_sito(sito) -> tuple[bool, str]:
    import requests
    url = sito["url"].rstrip("/")
    chiave = sito["chiave"]
    oggi = date.today().isoformat()
    tra_30 = (date.today() + timedelta(days=30)).isoformat()
    try:
        resp = requests.get(f"{url}/api/slot-occupati", params={"chiave": chiave, "da": oggi, "a": tra_30}, timeout=15)
        if resp.status_code != 200:
            with transaction() as conn:
                conn.execute("UPDATE siti_esterni SET last_sync = datetime('now') WHERE id = ?", (sito["id"],))
            _log_sync(None, f"sito={sito['id']} HTTP {resp.status_code}", "error", f"Status {resp.status_code}")
            return False, f"HTTP {resp.status_code}"
        dati = resp.json()
        n_importati = 0
        for ev in dati.get("eventi", []):
            consulente_id = ev.get("consulente_id")
            data_iso = ev.get("data")
            ora_inizio = ev.get("ora_inizio")
            ora_fine = ev.get("ora_fine")
            oggetto = ev.get("oggetto", "Prenotazione online")
            if not consulente_id or not data_iso or not ora_inizio:
                continue
            from app.slot_utils import time_to_slot_index
            try:
                slot_inizio = time_to_slot_index(ora_inizio)
                slot_fine = time_to_slot_index(ora_fine)
            except Exception:
                continue
            esiste = query("SELECT 1 FROM appuntamenti WHERE consulente_id = ? AND data = ? AND ora_inizio = ? AND provenienza = 'online' AND stato != 'annullato'", (consulente_id, data_iso, ora_inizio), one=True)
            if esiste:
                continue
            try:
                with transaction() as conn:
                    conn.execute("INSERT INTO appuntamenti (consulente_id, data, ora_inizio, ora_fine, slot_inizio, slot_fine, oggetto, stato, provenienza, sync_status) VALUES (?,?,?,?,?,?,?, 'prenotato','online','synced')", (consulente_id, data_iso, ora_inizio, ora_fine, slot_inizio, slot_fine, oggetto))
                    n_importati += 1
            except Exception:
                pass
        with transaction() as conn:
            conn.execute("UPDATE siti_esterni SET last_sync = datetime('now') WHERE id = ?", (sito["id"],))
        _log_sync(None, f"sito={sito['id']} {sito['nome']} importati={n_importati}", "ok")
        return True, f"Importati {n_importati}"
    except Exception as e:
        _log_sync(None, f"sito={sito['id']}", "error", str(e))
        return False, str(e)


def prova_connessione(sito_id: int) -> tuple[bool, str]:
    import requests
    sito = query("SELECT * FROM siti_esterni WHERE id = ?", (sito_id,), one=True)
    if not sito:
        return False, "Sito non trovato"
    try:
        resp = requests.get(sito["url"].rstrip("/") + "/api/ping", params={"chiave": sito["chiave"]}, timeout=10)
        if resp.status_code == 200:
            return True, "Connessione OK"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)
