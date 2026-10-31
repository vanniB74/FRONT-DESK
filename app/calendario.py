"""Calendario e logica appuntamenti."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.db import query, transaction
from app.slot_utils import daily_slots, time_to_slot_index


def _utente_has_availability(consulente_id: int, data_iso: str, slot_inizio: int, slot_fine: int) -> bool:
    # controllo disponibilità settimanale
    d = datetime.strptime(data_iso, "%Y-%m-%d").date()
    day = d.weekday()
    rows = query(
        "SELECT ora_inizio, ora_fine FROM disponibilita_settimanale WHERE consulente_id = ? AND giorno_settimana = ? ORDER BY ora_inizio",
        (consulente_id, day),
    )
    if not rows:
        return False
    for r in rows:
        start = time_to_slot_index(r["ora_inizio"])
        end = time_to_slot_index(r["ora_fine"])
        if slot_inizio >= start and slot_fine <= end:
            return True
    return False


def slot_disponibili_consulente(consulente_id: int, data_iso: str):
    slots = []
    for slot in daily_slots():
        start = slot["index"]
        end = start + 1
        ok = _utente_has_availability(consulente_id, data_iso, start, end)
        if not ok:
            continue
        if query(
            "SELECT 1 FROM appuntamenti WHERE consulente_id = ? AND data = ? AND slot_inizio < ? AND slot_fine > ? AND stato != 'annullato' LIMIT 1",
            (consulente_id, data_iso, end, start),
            one=True,
        ):
            continue
        slots.append({"index": start, "start": slot["start"], "end": slot["end"], "libero": True})
    return {"slots": slots}


def verifica_slot_prenotabile(consulente_id: int, data_iso: str, slot_inizio: int, slot_fine: int):
    if not _utente_has_availability(consulente_id, data_iso, slot_inizio, slot_fine):
        return False, "Slot non disponibile per il consulente"
    if query(
        "SELECT 1 FROM appuntamenti WHERE consulente_id = ? AND data = ? AND slot_inizio < ? AND slot_fine > ? AND stato != 'annullato' LIMIT 1",
        (consulente_id, data_iso, slot_fine, slot_inizio),
        one=True,
    ):
        return False, "Slot già occupato"
    return True, ""


def crea_appuntamento(consulente_id: int, data_iso: str, slot_inizio: int, slot_fine: int, oggetto: str,
                     cliente_id: int | None = None, operatore_id: int | None = None, provenienza: str = "sportello",
                     note: str = "", di_prova: int = 0):
    ok, msg = verifica_slot_prenotabile(consulente_id, data_iso, slot_inizio, slot_fine)
    if not ok:
        return False, msg, None
    start = daily_slots()[slot_inizio]["start"]
    end = daily_slots()[slot_fine - 1]["end"] if slot_fine > slot_inizio else daily_slots()[slot_inizio]["end"]
    try:
        with transaction() as conn:
            cur = conn.execute(
                "INSERT INTO appuntamenti (consulente_id, cliente_id, data, ora_inizio, ora_fine, slot_inizio, slot_fine, oggetto, stato, provenienza, operatore_id, note, di_prova) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (consulente_id, cliente_id, data_iso, start, end, slot_inizio, slot_fine, oggetto, "prenotato", provenienza, operatore_id, note, di_prova),
            )
            app_id = cur.lastrowid
        return True, "OK", app_id
    except Exception as exc:
        return False, str(exc), None


def cambia_stato_appuntamento(app_id: int, nuovo_stato: str, operatore_id: int | None = None):
    with transaction() as conn:
        conn.execute(
            "UPDATE appuntamenti SET stato = ?, updated_at = datetime('now') WHERE id = ?",
            (nuovo_stato, app_id),
        )
    return True
