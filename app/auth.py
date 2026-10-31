"""Sistema di autenticazione."""
from __future__ import annotations

import hashlib
import secrets
import time
from functools import wraps
from typing import Optional

from flask import session, request, redirect, url_for, flash, g

from app.db import get_db, query
from app.audit import log as audit_log
from config import Config


def _hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 100_000)
    return f"pbkdf2_sha256${salt.hex()}${h.hex()}"


def _verify_pin(pin: str, stored: str) -> bool:
    if not stored or not stored.startswith("pbkdf2_sha256$"):
        return False
    try:
        _, salt_hex, hash_hex = stored.split("$", 2)
        salt = bytes.fromhex(salt_hex)
        h = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 100_000)
        return secrets.compare_digest(h.hex(), hash_hex)
    except Exception:
        return False


hash_password = _hash_pin
verify_password = _verify_pin


def genera_password_casuale(length: int = 10) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789abcdefghijkmnpqrstuvwxyz"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def login_operatore(operatore_id: int, ip: str = "") -> None:
    session.clear()
    session["operatore_id"] = operatore_id
    session["login_time"] = time.time()
    session["last_activity"] = time.time()
    audit_log(operatore_id, "login", dettagli="Login operatore", ip=ip)


def logout_operatore() -> None:
    op_id = session.get("operatore_id")
    if op_id:
        audit_log(op_id, "logout", dettagli="Logout operatore", ip=request.remote_addr if request else "")
    session.clear()


def get_operatore_corrente():
    op_id = session.get("operatore_id")
    if not op_id:
        return None
    last = session.get("last_activity", 0)
    timeout = Config.SESSION_TIMEOUT_MINUTES * 60
    if time.time() - last > timeout:
        logout_operatore()
        return None
    op = query("SELECT * FROM operatori WHERE id = ? AND attivo = 1", (op_id,), one=True)
    if not op:
        session.clear()
        return None
    session["last_activity"] = time.time()
    return op


def is_amministratore() -> bool:
    op = get_operatore_corrente()
    return bool(op and op["ruolo"] == "amministratore")


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        op = get_operatore_corrente()
        if not op:
            if request.path.startswith("/api/"):
                return {"error": "non_autenticato"}, 401
            flash("Devi effettuare il login per accedere.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        g.operatore = op
        return fn(*args, **kwargs)
    return wrapper


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        op = get_operatore_corrente()
        if not op:
            flash("Devi effettuare il login per accedere.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if op["ruolo"] != "amministratore":
            flash("Accesso riservato all'amministratore.", "danger")
            return redirect(url_for("home.index"))
        g.operatore = op
        return fn(*args, **kwargs)
    return wrapper


def find_operatore_by_pin(pin: str):
    if not pin:
        return None
    operatori = query("SELECT * FROM operatori WHERE attivo = 1 AND pin_hash IS NOT NULL")
    for op in operatori:
        if _verify_pin(pin, op["pin_hash"]):
            return op
    return None


def find_operatore_by_email_password(email: str, password: str):
    if not email or not password:
        return None
    op = query("SELECT * FROM operatori WHERE attivo = 1 AND email = ? AND password_hash IS NOT NULL", (email.strip().lower(),), one=True)
    if op and _verify_pin(password, op["password_hash"]):
        return op
    return None


def imposta_password(operatore_id: int, password: str) -> bool:
    from app.db import execute
    execute("UPDATE operatori SET password_hash = ?, prima_login = 0 WHERE id = ?", (_hash_pin(password), operatore_id))
    return True
