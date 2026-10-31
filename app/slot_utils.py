"""Utility per slot, disponibilità e calendario."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from config import Config


def slot_minutes() -> int:
    return Config.SLOT_MINUTES


def parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def hhmm_from_minutes(mins: int) -> str:
    h = mins // 60
    m = mins % 60
    return f"{h:02d}:{m:02d}"


def office_bounds() -> tuple[int, int]:
    return parse_hhmm(Config.OFFICE_START), parse_hhmm(Config.OFFICE_END)


def slots_per_day() -> int:
    start, end = office_bounds()
    return (end - start) // slot_minutes()


def slot_index_to_time(slot: int) -> str:
    start, _ = office_bounds()
    return hhmm_from_minutes(start + slot * slot_minutes())


def time_to_slot_index(hhmm: str) -> int:
    start, _ = office_bounds()
    return (parse_hhmm(hhmm) - start) // slot_minutes()


def slot_index_to_minutes(slot: int) -> int:
    start, _ = office_bounds()
    return start + slot * slot_minutes()


def daily_slots():
    out = []
    n = slots_per_day()
    for i in range(n):
        start_min = slot_index_to_minutes(i)
        end_min = start_min + slot_minutes()
        out.append({"index": i, "start": hhmm_from_minutes(start_min), "end": hhmm_from_minutes(end_min)})
    return out


def weekday_it(d: date):
    return ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"][d.weekday()]


def weekdays_it():
    return ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
