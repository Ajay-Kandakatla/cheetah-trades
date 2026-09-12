"""Secrets must never reach a log line.

Found 2026-08-16 while verifying the ticker-rename fix. httpx logs every request
at INFO with the FULL URL, and Finnhub takes its API key as a query parameter,
so `cheetah.log` on the shared `cheetah-scans` volume held **493 lines**
containing the live key in plaintext — readable from both the api and the cron
container.

`sepa/prices.py` already had `_scrub_key` for exactly this on the Massive key
("leaked once, 2026-06-11; rotated"). That only covers exception text we format
ourselves; it cannot touch what a third-party library logs.

Two layers here, because either alone is a single point of failure:
  1. Quiet the libraries that log full URLs (WARNING keeps the failures).
  2. Redact anything that still gets through, on every handler.

All synthetic. No network, no files.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from observability import logsetup as L  # noqa: E402


# ---------------------------------------------------------------------------
# redact
# ---------------------------------------------------------------------------
def test_the_real_leak_is_redacted():
    """The exact shape that filled the log file."""
    line = ("HTTP Request: GET https://finnhub.io/api/v1/stock/profile2"
            "?symbol=ECHO&token=d7j4kb1r01qp3g1rpc1g \"HTTP/1.1 200 OK\"")
    out = L.redact(line)
    assert "d7j4kb1r01qp3g1rpc1g" not in out
    assert "token=<redacted>" in out
    assert "symbol=ECHO" in out, "the useful part of the URL must survive"


@pytest.mark.parametrize("param", [
    "token", "apiKey", "api_key", "access_token", "key", "secret", "password",
])
def test_every_secret_shaped_param_is_caught(param):
    assert "SUPERSECRET" not in L.redact(f"https://x.test/a?{param}=SUPERSECRET")


def test_it_is_case_insensitive():
    assert "abc123" not in L.redact("?APIKEY=abc123")
    assert "abc123" not in L.redact("?ApiKey=abc123")


def test_it_stops_at_the_next_parameter():
    out = L.redact("?token=SECRET&symbol=NVDA&interval=1d")
    assert "symbol=NVDA" in out and "interval=1d" in out
    assert "SECRET" not in out


def test_it_redacts_more_than_one_secret_in_a_line():
    out = L.redact("?token=AAA and later ?apiKey=BBB")
    assert "AAA" not in out and "BBB" not in out


def test_the_massive_style_url_is_covered_too():
    out = L.redact("https://api.massive.com/v2/aggs/ticker/NVDA?adjusted=true&apiKey=MKEY")
    assert "MKEY" not in out
    assert "adjusted=true" in out


# --- negatives ---
def test_ordinary_text_is_untouched():
    for s in ("scan complete: 506 symbols", "rvol=2.4 close=42.12", ""):
        assert L.redact(s) == s


def test_it_does_not_eat_a_word_ending_in_key():
    """`monkey=1` is not a secret. The pattern must match the whole param name."""
    assert L.redact("?monkey=1") == "?monkey=1"


def test_none_and_empty_do_not_explode():
    assert L.redact("") == ""
    assert L.redact(None) is None


# ---------------------------------------------------------------------------
# The filter, as logging actually uses it
# ---------------------------------------------------------------------------
class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines: list = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def test_the_filter_scrubs_a_real_log_record():
    lg = logging.getLogger("test.redaction.record")
    lg.propagate = False
    lg.setLevel(logging.INFO)
    cap = Capture()
    cap.addFilter(L.RedactFilter())
    lg.addHandler(cap)
    try:
        lg.info("GET https://finnhub.io/quote?symbol=NVDA&token=LIVEKEY123")
        assert "LIVEKEY123" not in cap.lines[0]
        assert "<redacted>" in cap.lines[0]
    finally:
        lg.removeHandler(cap)


def test_the_filter_scrubs_LAZY_arguments():
    """`log.info("fetch %s", url)` never puts the URL in `msg` — it is in
    `args`, and a filter that only rewrites `msg` would miss every one."""
    lg = logging.getLogger("test.redaction.args")
    lg.propagate = False
    lg.setLevel(logging.INFO)
    cap = Capture()
    cap.addFilter(L.RedactFilter())
    lg.addHandler(cap)
    try:
        lg.info("fetching %s", "https://x.test/a?token=LEAKED")
        assert "LEAKED" not in cap.lines[0]
    finally:
        lg.removeHandler(cap)


def test_the_filter_handles_dict_args():
    lg = logging.getLogger("test.redaction.dict")
    lg.propagate = False
    lg.setLevel(logging.INFO)
    cap = Capture()
    cap.addFilter(L.RedactFilter())
    lg.addHandler(cap)
    try:
        lg.info("%(u)s", {"u": "https://x.test?token=LEAKED"})
        assert "LEAKED" not in cap.lines[0]
    finally:
        lg.removeHandler(cap)


def test_the_filter_never_drops_a_record():
    """It is a scrubber, not a gate. Returning False would silently delete logs."""
    rec = logging.LogRecord("n", logging.INFO, __file__, 1, "?token=X", None, None)
    assert L.RedactFilter().filter(rec) is True


def test_the_filter_never_raises_on_a_weird_record():
    rec = logging.LogRecord("n", logging.INFO, __file__, 1, object(), None, None)
    assert L.RedactFilter().filter(rec) is True


# ---------------------------------------------------------------------------
# install_redaction
# ---------------------------------------------------------------------------
def test_the_url_logging_libraries_are_quieted():
    """This is the layer that stops the leak at source — httpx logs the full
    URL at INFO on EVERY request."""
    L.install_redaction()
    for name in ("httpx", "httpcore"):
        assert logging.getLogger(name).level >= logging.WARNING


def test_install_is_idempotent():
    L.install_redaction()
    L.install_redaction()
    root = logging.getLogger()
    assert sum(isinstance(f, L.RedactFilter) for f in root.filters) == 1


def test_handlers_get_the_filter_too():
    """Root FILTERS do not apply to records emitted through child loggers —
    only root HANDLERS see those. Filtering in one place only would leak
    everything logged by a named logger, which is all of it."""
    root = logging.getLogger()
    cap = Capture()
    root.addHandler(cap)
    try:
        L.install_redaction()
        assert any(isinstance(f, L.RedactFilter) for f in cap.filters)
    finally:
        root.removeHandler(cap)


# ---------------------------------------------------------------------------
# Exception ARGS (2026-09-12) — the 5th credential exposure
# ---------------------------------------------------------------------------
# The 2026-08-16 layer redacted `str` args only. `log.warning("failed: %s", exc)`
# hands the filter an EXCEPTION, not a string, so it sailed straight through —
# and `requests` puts the full request URL inside its ConnectTimeout text, with
# the Massive key riding in that URL as `apiKey=`. One network blip during the
# 2026-09-12 qoq backfill printed the live key in plaintext.
LEAKY = ("HTTPSConnectionPool(host='api.massive.com', port=443): Max retries "
         "exceeded with url: /vX/reference/financials?ticker=ESNT&limit=8"
         "&timeframe=quarterly&apiKey=SUPERSECRETKEYVALUE123 (Caused by "
         "ConnectTimeoutError(...))")


def _emit(logger_name, *args):
    import io
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.addFilter(L.RedactFilter())
    lg = logging.getLogger(logger_name)
    lg.handlers = [h]
    lg.propagate = False
    lg.setLevel(logging.INFO)
    lg.warning(*args)
    return buf.getvalue()


def test_THE_LEAK_an_EXCEPTION_arg_is_redacted_not_just_a_string():
    out = _emit("t.exc", "fetch failed for %s: %s", "ESNT", RuntimeError(LEAKY))
    assert "SUPERSECRETKEYVALUE123" not in out
    assert "<redacted>" in out


def test_a_plain_string_arg_is_still_redacted():
    out = _emit("t.str", "fetch failed: %s", LEAKY)
    assert "SUPERSECRETKEYVALUE123" not in out


def test_NEGATIVE_a_clean_non_string_arg_keeps_its_type_and_its_formatting():
    """Blanket-stringifying every arg would break `%d` / `%.2f` on every other
    log line in the app. Only args whose TEXT actually matches are touched."""
    out = _emit("t.num", "scanned %d names in %.2fs", 2840, 1.5)
    assert "scanned 2840 names in 1.50s" in out


def test_NEGATIVE_the_exception_MESSAGE_survives_minus_the_secret():
    """A redacted log line still has to be debuggable — the host, the path and
    the failing ticker must all remain."""
    out = _emit("t.keep", "fetch failed for %s: %s", "ESNT", RuntimeError(LEAKY))
    for keep in ("api.massive.com", "ESNT", "ConnectTimeoutError", "reference/financials"):
        assert keep in out


def test_the_module_that_KNOWS_the_key_is_in_the_url_scrubs_it_itself():
    """Defence in depth: `canslim` builds the keyed URL, so it must not depend
    on a downstream filter being installed in whatever process is running."""
    from sepa.canslim import _scrub
    assert "SUPERSECRETKEYVALUE123" not in _scrub(RuntimeError(LEAKY))


def test_the_backfill_CLI_installs_redaction_because_it_has_no_app_startup():
    import inspect
    from sepa import qoq
    assert "install_redaction" in inspect.getsource(qoq._main)
