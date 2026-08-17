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


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------
# Found 2026-08-16 while verifying the ticker-rename fix: httpx logs every
# request at INFO with the FULL URL, and Finnhub takes its key as a query
# param. The result was 493 lines of
#
#     INFO HTTP Request: GET https://finnhub.io/api/v1/...&token=<the real key>
#
# sitting in cheetah.log on the shared `cheetah-scans` volume, readable from
# both the api and cron containers. sepa/prices.py already had `_scrub_key` for
# exactly this on the Massive key ("leaked once, 2026-06-11; rotated") — but
# that only covers exception text it formats itself, not what a third-party
# library logs.
#
# Two layers, because either alone is a single point of failure:
#   1. Quiet the libraries that log full URLs.
#   2. Redact anything that still gets through, on every handler.
import re as _re

# The lookbehind matters: without it `key` matches inside `monkey=1` and the
# filter mangles ordinary log lines. Over-redaction is safe but it makes logs
# untrustworthy, which is its own cost.
_SECRET_RE = _re.compile(
    r"(?<![A-Za-z0-9_])"
    r"((?:token|apikey|api_key|access_token|key|secret|password)=)[^&\s\"']+",
    _re.IGNORECASE)

# Libraries that log a full request URL at INFO. WARNING keeps the failures.
_CHATTY_URL_LOGGERS = ("httpx", "httpcore", "urllib3.connectionpool", "yfinance")


def redact(text: str) -> str:
    """Replace the VALUE of any secret-looking query param. PURE."""
    if not text:
        return text
    return _SECRET_RE.sub(r"\1<redacted>", text)


class RedactFilter(logging.Filter):
    """Scrub secrets from a record before any handler formats it.

    Rewrites `msg` and `args` rather than the formatted string, because a
    handler may format it more than once (stdout + file) and because
    `record.getMessage()` is what every formatter ultimately calls.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str) and "=" in record.msg:
                record.msg = redact(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: (redact(v) if isinstance(v, str) else v)
                                   for k, v in record.args.items()}
                elif isinstance(record.args, tuple):
                    record.args = tuple(redact(a) if isinstance(a, str) else a
                                        for a in record.args)
        except Exception:
            pass                      # a logging filter must never raise
        return True


def install_redaction() -> None:
    """Silence full-URL loggers and scrub whatever still leaks. Idempotent."""
    try:
        for name in _CHATTY_URL_LOGGERS:
            lg = logging.getLogger(name)
            if lg.level < logging.WARNING:
                lg.setLevel(logging.WARNING)
        root = logging.getLogger()
        if not any(isinstance(f, RedactFilter) for f in root.filters):
            root.addFilter(RedactFilter())
        # Root filters do NOT apply to records logged via child loggers, so the
        # handlers need it too — that is where every record converges.
        for h in root.handlers:
            if not any(isinstance(f, RedactFilter) for f in h.filters):
                h.addFilter(RedactFilter())
    except Exception:
        pass
