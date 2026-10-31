"""Sincronizzazione Google Calendar (bidirezionale).

STRUTTURA: l'integrazione reale richiede OAuth2 con Google Cloud.
Questa implementazione fornisce:
- Collegamento account Google (avvio OAuth flow).
- Creazione eventi sul calendario del consulente (solo titolo, ora, oggetto;
  MAI dati sensibili).
- Lettura eventi esterni (prenotazioni online) e blocco slot.
- Registro scambi ed errori.

Per ambiente di test/demo le chiamate reali a Google sono stubbed
e registrano nel sync_log.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from app.db import query, transaction
from app.audit import log as audit_log
from config import Config


def is_google_configured() -> bool:
    return bool(Config.GOOGLE_CREDENTIALS_FILE) and bool(Config.GOOGLE_CREDENTIALS_FILE.strip())


def _log_sync(tipo: str, direzione: str, consulente_id: Optional[int],
              dettagli: str, stato: str = "ok", errore: str = "") -> None:
    with transaction() as conn:
        conn.execute(
            """INSERT INTO sync_log (tipo, direzione, consulente_id, dettagli, stato, errore)
               VALUES (?,?,?,?,?,?)""",
            (tipo, direzione, consulente_id, dettagli, stato, errore),
        )


def get_google_service():
    """Restituisce il servizio Google Calendar autenticato (o None se non configurato)."""
    if not is_google_configured():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import os

        SCOPES = ["https://www.googleapis.com/auth/calendar"]
        creds = None
        if Config.GOOGLE_TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(Config.GOOGLE_TOKEN_FILE), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    Config.GOOGLE_CREDENTIALS_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)
            Config.GOOGLE_TOKEN_FILE.write_text(creds.to_json())
        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        _log_sync("google", "in", None, "get_service", "error", str(e))
        return None


def push_appuntamento_google(app_id: int) -> tuple[bool, str]:
    """Crea/aggiorna l'evento Google per un appuntamento locale.
    Solo titolo, ora e oggetto; MAI dati sensibili.
    """
    app = query("SELECT * FROM appuntamenti WHERE id = ?", (app_id,), one=True)
    if not app:
        return False, "Appuntamento non trovato"
    consulente = query("SELECT * FROM consulenti WHERE id = ?", (app["consulente_id"],), one=True)
    if not consulente or not consulente["google_calendar_id"]:
        return False, "Consulente senza calendario Google abbinato"
    service = get_google_service()
    if service is None:
        with transaction() as conn:
            conn.execute(
                "UPDATE appuntamenti SET sync_status = 'local_only' WHERE id = ?",
                (app_id,),
            )
        _log_sync("google", "out", app["consulente_id"],
                  f"app={app_id} stub (google non configurato)", "warning")
        return True, "Stub (Google non configurato)"
    try:
        d = app["data"]
        start_dt = datetime.fromisoformat(f"{d}T{app['ora_inizio']}:00")
        end_dt = datetime.fromisoformat(f"{d}T{app['ora_fine']}:00")
        event = {
            "summary": f"Appuntamento - {app['oggetto']}",
            "description": f"Oggetto: {app['oggetto']}",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Rome"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Rome"},
        }
        if app["google_event_id"]:
            event = service.events().update(
                calendarId=consulente["google_calendar_id"],
                eventId=app["google_event_id"],
                body=event,
            ).execute()
        else:
            event = service.events().insert(
                calendarId=consulente["google_calendar_id"],
                body=event,
            ).execute()
            with transaction() as conn:
                conn.execute(
                    "UPDATE appuntamenti SET google_event_id = ?, sync_status = 'synced' WHERE id = ?",
                    (event["id"], app_id),
                )
        _log_sync("google", "out", app["consulente_id"],
                  f"app={app_id} event={event.get('id')}", "ok")
        return True, "Sincronizzato"
    except Exception as e:
        with transaction() as conn:
            conn.execute(
                "UPDATE appuntamenti SET sync_status = 'error' WHERE id = ?",
                (app_id,),
            )
        _log_sync("google", "out", app["consulente_id"],
                  f"app={app_id}", "error", str(e))
        return False, str(e)


def pull_eventi_google(consulente_id: int, data_iso: str) -> int:
    """Legge eventi Google per un consulente in una data e blocca slot locali.
    Ritorna il numero di eventi importati.
    """
    consulente = query("SELECT * FROM consulenti WHERE id = ?", (consulente_id,), one=True)
    if not consulente or not consulente["google_calendar_id"]:
        return 0
    service = get_google_service()
    if service is None:
        return 0
    try:
        from datetime import datetime as dt

        time_min = dt.fromisoformat(f"{data_iso}T00:00:00")
        time_max = dt.fromisoformat(f"{data_iso}T23:59:59")
        events_result = service.events().list(
            calendarId=consulente["google_calendar_id"],
            timeMin=time_min.isoformat() + "+02:00",
            timeMax=time_max.isoformat() + "+02:00",
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])
        n = 0
        for ev in events:
            summary = ev.get("summary", "Evento esterno")
            start = ev.get("start", {}).get("dateTime", "")[:16]
            end = ev.get("end", {}).get("dateTime", "")[:16]
            if not start or not end:
                continue
            ora_inizio = start[11:16]
            ora_fine = end[11:16]
            esiste = query(
                """SELECT 1 FROM appuntamenti WHERE consulente_id = ? AND data = ?
                   AND ora_inizio = ? AND google_event_id = ?""",
                (consulente_id, data_iso, ora_inizio, ev["id"]),
                one=True,
            )
            if esiste:
                continue
            try:
                from app.slot_utils import time_to_slot_index

                slot_inizio = time_to_slot_index(ora_inizio)
                slot_fine = time_to_slot_index(ora_fine)
            except Exception:
                continue
            with transaction() as conn:
                try:
                    conn.execute(
                        """INSERT INTO appuntamenti
                           (consulente_id, data, ora_inizio, ora_fine, slot_inizio, slot_fine,
                            oggetto, stato, provenienza, sync_status, google_event_id)
                           VALUES (?,?,?,?,?,?,?,?, 'prenotato', 'online','synced', ?)""",
                        (
                            consulente_id,
                            data_iso,
                            ora_inizio,
                            ora_fine,
                            slot_inizio,
                            slot_fine,
                            summary,
                            ev["id"],
                        ),
                    )
                    n += 1
                except Exception:
                    pass
        _log_sync("google", "in", consulente_id, f"data={data_iso} eventi={n}", "ok")
        return n
    except Exception as e:
        _log_sync("google", "in", consulente_id, f"data={data_iso}", "error", str(e))
        return 0
