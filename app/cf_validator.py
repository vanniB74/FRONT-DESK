"""Validazione codice fiscale."""
from __future__ import annotations

import re
from datetime import datetime

_VALORI = {
    'A':0,'B':1,'C':2,'D':3,'E':4,'F':5,'G':6,'H':7,'I':8,'J':9,'K':10,'L':11,'M':12,'N':13,'O':14,'P':15,'Q':16,'R':17,'S':18,'T':19,'U':20,'V':21,'W':22,'X':23,'Y':24,'Z':25,
    '0':0,'1':1,'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
}
_VALORI_DISPARI = {
    'A':1,'B':0,'C':5,'D':7,'E':9,'F':13,'G':15,'H':17,'I':19,'J':21,'K':2,'L':4,'M':18,'N':20,'O':11,'P':3,'Q':6,'R':8,'S':12,'T':14,'U':16,'V':10,'W':22,'X':25,'Y':24,'Z':23,
    '0':1,'1':0,'2':5,'3':7,'4':9,'5':13,'6':15,'7':17,'8':19,'9':21,
}
_CARATTERI_CONTROLLO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def valida_codice_fiscale(cf: str) -> tuple[bool, str]:
    if not cf:
        return False, "Codice fiscale vuoto"
    cf = cf.strip().upper().replace(" ", "")
    if len(cf) != 16:
        return False, "Il codice fiscale deve essere di 16 caratteri"
    if not re.match(r"^[A-Z0-9]+$", cf):
        return False, "Caratteri non validi nel codice fiscale"
    somma = 0
    for i, c in enumerate(cf[:15]):
        if i % 2 == 0:
            somma += _VALORI_DISPARI.get(c, 0)
        else:
            somma += _VALORI.get(c, 0)
    resto = somma % 26
    atteso = _CARATTERI_CONTROLLO[resto]
    if cf[15] != atteso:
        return False, f"Carattere di controllo non valido (atteso {atteso})"
    return True, ""


def estrai_da_cf(cf: str) -> dict:
    cf = (cf or "").strip().upper()
    if len(cf) != 16:
        return {}
    try:
        mese_map = {'A':1,'B':2,'C':3,'D':4,'E':5,'H':6,'L':7,'M':8,'P':9,'R':10,'S':11,'T':12}
        anno = int(cf[6:8])
        mese = mese_map.get(cf[8], 1)
        giorno = int(cf[9:11])
        sesso = 'M'
        if giorno > 31:
            sesso = 'F'
            giorno -= 40
        current_year = datetime.now().year
        secolo = 2000 if anno <= (current_year % 100) else 1900
        anno_full = secolo + anno
        from calendar import monthrange
        max_g = monthrange(anno_full, mese)[1]
        giorno = max(1, min(giorno, max_g))
        return {"sesso": sesso, "data_nascita": f"{anno_full:04d}-{mese:02d}-{giorno:02d}"}
    except Exception:
        return {}


def normalizza_cf(cf: str) -> str:
    return (cf or "").strip().upper().replace(" ", "")
