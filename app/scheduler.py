"""Scheduler interno."""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler


def avvia_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.start()
    app.extensions["scheduler"] = scheduler
    return scheduler
