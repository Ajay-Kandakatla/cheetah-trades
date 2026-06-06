"""Persistent app logging — a rotating file handler on the shared volume.

`logging.basicConfig` in main.py / cli.py only writes to stdout, which Docker
keeps for a while but is awkward to audit. This adds a rotating FILE handler so
every WARNING/ERROR (and the health-audit summaries) lands in one place the
audit can scan AND any external log agent (Datadog / Splunk / Vector / Promtail)
can tail:

    ~/.cheetah/logs/cheetah.log   (10 MB × 5 rotations)

It lives on the `cheetah-scans` volume (mounted into both `api` and `cron`), so
the API and every cron job append to the same trail. Idempotent + never raises —
logging setup must not be able to break the app.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(os.getenv("CHEETAH_LOG_DIR", str(Path.home() / ".cheetah" / "logs")))
LOG_PATH = LOG_DIR / "cheetah.log"

_installed = False


def install_file_handler(level: int = logging.INFO) -> None:
    """Attach a rotating file handler to the root logger (once)."""
    global _installed
    if _installed:
        return
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        root = logging.getLogger()
        already = any(
            isinstance(h, RotatingFileHandler)
            and getattr(h, "baseFilename", "") == str(LOG_PATH)
            for h in root.handlers
        )
        if not already:
            h = RotatingFileHandler(
                LOG_PATH, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            h.setLevel(level)
            h.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"))
            root.addHandler(h)
            if root.level > level:
                root.setLevel(level)
        _installed = True
    except Exception:
        # Never let logging setup break startup.
        pass
