"""Utility di crittografia Fernet."""
from __future__ import annotations

from config import Config

_cached_fernet = None


def _get_fernet():
    global _cached_fernet
    if _cached_fernet is not None:
        return _cached_fernet
    key = Config.FERNET_KEY
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        _cached_fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return _cached_fernet
    except Exception:
        return None


def encrypt(plaintext: str) -> str:
    f = _get_fernet()
    if f is None:
        return f"PLAIN:{plaintext}"
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    if ciphertext.startswith("PLAIN:"):
        return ciphertext[6:]
    f = _get_fernet()
    if f is None:
        return ""
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""
