"""Dati di prova."""
from __future__ import annotations

import random
import shutil
from datetime import date, timedelta

from app.codice_cliente import genera_codice_cliente
from app.calendario import crea_appuntamento
from app.db import query, transaction
from config import Config

NOMI = ["Mario","Luigi","Giuseppe","Giovanni","Anna","Maria","Rosa","Lucrezia","Francesco","Antonio","Carmela","Vito","Donato","Angela","Paola"]
COGNOMI = ["Rossi","Bianchi","Esposito","Conti","Ferrari","Gallo","Greco","Lombardi","Marino","Ricci","De Luca","Romano","Colombo","Costa","Fontana","Moretti"]
OGGETTI = ["Dichiarazione 730","Permesso di soggiorno","Visura camerale","Calcolo pensione","Assunzione colf","Apertura Partita IVA","Contratto di locazione","Successione","Cessione del quinto","Attivazione SPID"]


def genera_dati_prova(operatore_id: int) -> int:
    n = 0
    consulenti_creati = []
    with transaction() as conn:
        for i, (nome, cognome) in enumerate([("Marco","Esposito"),("Lucia","Rinaldi"),("Paolo","Greco"),("Sara","Fontana")]):
            cur = conn.execute("INSERT INTO consulenti (nome, cognome, email, colore, attivo) VALUES (?,?,?,?,1)", (nome, cognome, f"{nome.lower()}.{cognome.lower()}@example.com", ["#39546B","#5A8AB8","#7BA9C9","#C9A24B"][i]))
            consulenti_creati.append(cur.lastrowid)
            n += 1
            for g in range(5):
                conn.execute("INSERT INTO disponibilita_settimanale (consulente_id, giorno_settimana, ora_inizio, ora_fine) VALUES (?,?,?,?)", (cur.lastrowid, g, "09:00", "13:00"))
                conn.execute("INSERT INTO disponibilita_settimanale (consulente_id, giorno_settimana, ora_inizio, ora_fine) VALUES (?,?,?,?)", (cur.lastrowid, g, "14:00", "18:00"))
    today = date.today()
    for _ in range(20):
        nome = random.choice(NOMI)
        cognome = random.choice(COGNOMI)
        codice = genera_codice_cliente()
        try:
            with transaction() as conn:
                cur = conn.execute("INSERT INTO clienti (codice_cliente, cognome, nome, luogo_nascita, data_nascita, sesso, codice_fiscale, residenza_indirizzo, residenza_cap, residenza_provincia, telefono, email, registrato_da, di_prova, privacy_firmata, mandato_firmato, passaporto_completo) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,1,1,0)", (codice, cognome, nome, "Bari", f"{random.randint(1950,2000)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}", random.choice(["M","F"]), "RSSMRA80A01A789X", "Via Roma", "70129", "BA", f"340{random.randint(1000000,9999999)}", f"{nome.lower()}.{cognome.lower()}@example.com", operatore_id))
                cid = cur.lastrowid
            n += 1
            for _ in range(random.randint(0, 2)):
                delta = random.randint(0, 6)
                data_iso = (today + timedelta(days=delta)).isoformat()
                slot_inizio = random.randint(0, 15)
                slot_durata = random.choice([1, 2])
                slot_fine = slot_inizio + slot_durata
                consulente_id = random.choice(consulenti_creati)
                ok, _, _ = crea_appuntamento(consulente_id=consulente_id, data_iso=data_iso, slot_inizio=slot_inizio, slot_fine=slot_fine, oggetto=random.choice(OGGETTI), cliente_id=cid, operatore_id=operatore_id, di_prova=1)
                if ok:
                    n += 1
        except Exception:
            pass
    return n


def cancella_dati_prova() -> int:
    n = 0
    with transaction() as conn:
        cur = conn.execute("DELETE FROM appuntamenti WHERE di_prova = 1")
        n += cur.rowcount
        cur = conn.execute("DELETE FROM clienti WHERE di_prova = 1")
        n += cur.rowcount
        cur = conn.execute("DELETE FROM consulenti WHERE email LIKE '%@example.com'")
        n += cur.rowcount
    for d in Config.FILES_DIR.glob("cliente_*"):
        try:
            shutil.rmtree(d)
        except Exception:
            pass
    return n
