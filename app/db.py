"""Database SQLite per CSI Front Office."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from config import Config

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS operatori (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cognome TEXT NOT NULL,
    email TEXT,
    pin_hash TEXT,
    password_hash TEXT,
    ruolo TEXT NOT NULL CHECK (ruolo IN ('operatore','amministratore')),
    attivo INTEGER NOT NULL DEFAULT 1,
    prima_login INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operatore_id INTEGER,
    azione TEXT NOT NULL,
    record_tipo TEXT,
    record_id TEXT,
    dettagli TEXT,
    data_ora TEXT NOT NULL DEFAULT (datetime('now')),
    ip TEXT,
    FOREIGN KEY (operatore_id) REFERENCES operatori(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_data ON audit_log(data_ora);
CREATE INDEX IF NOT EXISTS idx_audit_op ON audit_log(operatore_id);

CREATE TABLE IF NOT EXISTS servizi_gruppi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    ordine INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS servizi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gruppo_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    ordine INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (gruppo_id) REFERENCES servizi_gruppi(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_servizi_gruppo ON servizi(gruppo_id);

CREATE TABLE IF NOT EXISTS consulenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cognome TEXT NOT NULL,
    email TEXT,
    colore TEXT NOT NULL DEFAULT '#39546B',
    attivo INTEGER NOT NULL DEFAULT 1,
    google_calendar_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS consulente_gruppi (
    consulente_id INTEGER NOT NULL,
    gruppo_id INTEGER NOT NULL,
    PRIMARY KEY (consulente_id, gruppo_id),
    FOREIGN KEY (consulente_id) REFERENCES consulenti(id) ON DELETE CASCADE,
    FOREIGN KEY (gruppo_id) REFERENCES servizi_gruppi(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS disponibilita_settimanale (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consulente_id INTEGER NOT NULL,
    giorno_settimana INTEGER NOT NULL CHECK (giorno_settimana BETWEEN 0 AND 6),
    ora_inizio TEXT NOT NULL,
    ora_fine TEXT NOT NULL,
    FOREIGN KEY (consulente_id) REFERENCES consulenti(id) ON DELETE CASCADE,
    UNIQUE (consulente_id, giorno_settimana, ora_inizio)
);
CREATE TABLE IF NOT EXISTS disponibilita_eccezioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consulente_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    ora_inizio TEXT,
    ora_fine TEXT,
    tipo TEXT NOT NULL CHECK (tipo IN ('bloccato','disponibile')),
    motivo TEXT,
    FOREIGN KEY (consulente_id) REFERENCES consulenti(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS chiusure_totali (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL UNIQUE,
    motivo TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by) REFERENCES operatori(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS clienti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice_cliente TEXT NOT NULL UNIQUE,
    cognome TEXT NOT NULL,
    nome TEXT NOT NULL,
    luogo_nascita TEXT,
    data_nascita TEXT,
    sesso TEXT CHECK (sesso IN ('M','F','') OR sesso IS NULL),
    codice_fiscale TEXT,
    cittadinanza TEXT,
    residenza_indirizzo TEXT,
    residenza_civico TEXT,
    residenza_cap TEXT,
    residenza_provincia TEXT,
    telefono TEXT,
    email TEXT,
    note TEXT,
    numero_pratica TEXT,
    attivo INTEGER NOT NULL DEFAULT 1,
    archiviato INTEGER NOT NULL DEFAULT 0,
    data_registrazione TEXT NOT NULL DEFAULT (datetime('now')),
    registrato_da INTEGER,
    di_prova INTEGER NOT NULL DEFAULT 0,
    privacy_firmata INTEGER NOT NULL DEFAULT 0,
    mandato_firmato INTEGER NOT NULL DEFAULT 0,
    passaporto_completo INTEGER NOT NULL DEFAULT 0,
    data_firma_mandato TEXT,
    data_scadenza_mandato TEXT,
    FOREIGN KEY (registrato_da) REFERENCES operatori(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS documenti_cliente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('ci_fronte','ci_retro','ts_fronte','ts_retro')),
    file_path TEXT NOT NULL,
    numero_codice TEXT,
    data_scadenza TEXT,
    ente_emittente TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (cliente_id) REFERENCES clienti(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS cliente_servizi_interesse (
    cliente_id INTEGER NOT NULL,
    servizio_id INTEGER NOT NULL,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (cliente_id, servizio_id),
    FOREIGN KEY (cliente_id) REFERENCES clienti(id) ON DELETE CASCADE,
    FOREIGN KEY (servizio_id) REFERENCES servizi(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS appuntamenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consulente_id INTEGER NOT NULL,
    cliente_id INTEGER,
    data TEXT NOT NULL,
    ora_inizio TEXT NOT NULL,
    ora_fine TEXT NOT NULL,
    slot_inizio INTEGER NOT NULL,
    slot_fine INTEGER NOT NULL,
    oggetto TEXT NOT NULL,
    stato TEXT NOT NULL DEFAULT 'prenotato' CHECK (stato IN ('prenotato','arrivato','in corso','concluso','assente','annullato')),
    provenienza TEXT NOT NULL DEFAULT 'sportello' CHECK (provenienza IN ('sportello','online')),
    operatore_id INTEGER,
    note TEXT,
    google_event_id TEXT,
    sync_status TEXT NOT NULL DEFAULT 'pending' CHECK (sync_status IN ('pending','synced','error','local_only')),
    di_prova INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (consulente_id) REFERENCES consulenti(id) ON DELETE CASCADE,
    FOREIGN KEY (cliente_id) REFERENCES clienti(id) ON DELETE SET NULL,
    FOREIGN KEY (operatore_id) REFERENCES operatori(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_appuntamento_slot ON appuntamenti(consulente_id, data, slot_inizio, slot_fine) WHERE stato != 'annullato';
CREATE TABLE IF NOT EXISTS mandati (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    data_firma TEXT NOT NULL,
    data_scadenza TEXT NOT NULL,
    istituto_ente TEXT,
    istituto_paese TEXT,
    collaboratore_volontario TEXT,
    operatore_id INTEGER,
    operatore_sede TEXT NOT NULL DEFAULT 'BARI',
    consenso_p1 INTEGER NOT NULL DEFAULT 1,
    consenso_p2 INTEGER NOT NULL DEFAULT 0,
    attivo INTEGER NOT NULL DEFAULT 1,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (cliente_id) REFERENCES clienti(id) ON DELETE CASCADE,
    FOREIGN KEY (operatore_id) REFERENCES operatori(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS mandato_servizi (
    mandato_id INTEGER NOT NULL,
    servizio_id INTEGER NOT NULL,
    PRIMARY KEY (mandato_id, servizio_id),
    FOREIGN KEY (mandato_id) REFERENCES mandati(id) ON DELETE CASCADE,
    FOREIGN KEY (servizio_id) REFERENCES servizi(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS privacy_consenso (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    consenso1 TEXT NOT NULL CHECK (consenso1 IN ('S','N')),
    consenso2 TEXT NOT NULL CHECK (consenso2 IN ('S','N')),
    consenso3 TEXT NOT NULL CHECK (consenso3 IN ('S','N')),
    operatore_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (cliente_id) REFERENCES clienti(id) ON DELETE CASCADE,
    FOREIGN KEY (operatore_id) REFERENCES operatori(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS email_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    operatore_id INTEGER,
    destinatario TEXT NOT NULL,
    oggetto TEXT NOT NULL,
    corpo TEXT,
    allegati TEXT,
    data_ora TEXT NOT NULL DEFAULT (datetime('now')),
    stato TEXT NOT NULL DEFAULT 'inviata' CHECK (stato IN ('inviata','errore','coda')),
    errore TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clienti(id) ON DELETE SET NULL,
    FOREIGN KEY (operatore_id) REFERENCES operatori(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS email_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    oggetto TEXT NOT NULL,
    corpo TEXT NOT NULL,
    modificabile INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK (tipo IN ('google','external')),
    direzione TEXT NOT NULL CHECK (direzione IN ('in','out')),
    consulente_id INTEGER,
    dettagli TEXT,
    stato TEXT NOT NULL CHECK (stato IN ('ok','error','warning')),
    errore TEXT,
    data_ora TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (consulente_id) REFERENCES consulenti(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS siti_esterni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    url TEXT NOT NULL,
    chiave TEXT NOT NULL,
    frequenza_minuti INTEGER NOT NULL DEFAULT 15,
    attivo INTEGER NOT NULL DEFAULT 1,
    last_sync TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS backup_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK (tipo IN ('auto','manual','restore')),
    file_path TEXT NOT NULL,
    dimensione INTEGER,
    data_ora TEXT NOT NULL DEFAULT (datetime('now')),
    stato TEXT NOT NULL CHECK (stato IN ('ok','error')),
    errore TEXT
);
CREATE TABLE IF NOT EXISTS reminder_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    mandato_id INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('scadenza_30g','scadenza_7g')),
    data_invio TEXT NOT NULL DEFAULT (datetime('now')),
    stato TEXT NOT NULL DEFAULT 'inviata' CHECK (stato IN ('inviata','errore')),
    FOREIGN KEY (cliente_id) REFERENCES clienti(id) ON DELETE CASCADE,
    FOREIGN KEY (mandato_id) REFERENCES mandati(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS impostazioni (
    chiave TEXT PRIMARY KEY,
    valore TEXT
);
"""


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(Config.DB_PATH, isolation_level=None, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = get_db()
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def query(sql: str, params: tuple = (), one: bool = False):
    conn = get_db()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def execute(sql: str, params: tuple = ()):
    with transaction() as conn:
        cur = conn.execute(sql, params)
        return cur.rowcount


def init_db() -> None:
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database inizializzato: {Config.DB_PATH}")
