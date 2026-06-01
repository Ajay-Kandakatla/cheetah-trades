"""Contracts for Massive API-key routing (``backend/massive_keys.py``).

Locks in the 2026-06-01 fix that split the single ``MASSIVE_API_KEY`` into
product-specific keys (stocks / options / crypto), each a DISTINCT Massive
entitlement. Guards against three regressions that have real money behind them:

  1. The var-name landmine — code reading the bare ``MASSIVE_API_KEY`` while
     ``.env`` defines ``MASSIVE_API_KEY_STOCKS``. On a container restart every
     stock call silently resolved to ``None`` and fell back to yfinance.
  2. Options modules using the stocks key — a stocks key returns HTTP 403
     ("not entitled") on options endpoints, so SOIR sentiment would die.
  3. The fallback chain breaking for older single-key deployments.
"""
from __future__ import annotations

import pathlib

import massive_keys

_ALL = (
    "MASSIVE_API_KEY",
    "MASSIVE_API_KEY_STOCKS",
    "MASSIVE_API_KEY_OPTIONS",
    "MASSIVE_API_KEY_CRYPTO",
)


def _set(monkeypatch, **kv):
    for k in _ALL:
        monkeypatch.delenv(k, raising=False)
    for k, v in kv.items():
        monkeypatch.setenv(k, v)


def test_stocks_key_prefers_product_var(monkeypatch):
    _set(monkeypatch, MASSIVE_API_KEY_STOCKS="S", MASSIVE_API_KEY="LEGACY")
    assert massive_keys.stocks_key() == "S"


def test_options_key_prefers_product_var(monkeypatch):
    _set(monkeypatch, MASSIVE_API_KEY_OPTIONS="O", MASSIVE_API_KEY="LEGACY")
    assert massive_keys.options_key() == "O"


def test_crypto_key_prefers_product_var(monkeypatch):
    _set(monkeypatch, MASSIVE_API_KEY_CRYPTO="C", MASSIVE_API_KEY="LEGACY")
    assert massive_keys.crypto_key() == "C"


def test_legacy_fallback(monkeypatch):
    _set(monkeypatch, MASSIVE_API_KEY="LEGACY")
    assert massive_keys.stocks_key() == "LEGACY"
    assert massive_keys.options_key() == "LEGACY"
    assert massive_keys.crypto_key() == "LEGACY"


def test_options_does_not_fall_back_to_stocks(monkeypatch):
    # A stocks key 403s on options — it must NOT masquerade as the options key.
    # With only the stocks var set, options_key() resolves empty (clean "no key"
    # signal that makes SOIR fall back to yfinance, not emit confusing 403s).
    _set(monkeypatch, MASSIVE_API_KEY_STOCKS="S")
    assert massive_keys.options_key() == ""


def test_unset_is_empty_not_none(monkeypatch):
    _set(monkeypatch)
    assert massive_keys.stocks_key() == ""
    assert massive_keys.options_key() == ""
    assert massive_keys.crypto_key() == ""


def test_whitespace_is_stripped(monkeypatch):
    _set(monkeypatch, MASSIVE_API_KEY_STOCKS="  S  ")
    assert massive_keys.stocks_key() == "S"


# ── Static guards over the whole backend tree ────────────────────────────

_BARE_READS = (
    'os.getenv("MASSIVE_API_KEY")',
    "os.getenv('MASSIVE_API_KEY')",
    'os.environ.get("MASSIVE_API_KEY")',
    'os.environ["MASSIVE_API_KEY"]',
)
_BACKEND = pathlib.Path(__file__).resolve().parent.parent


def _py_files():
    for p in _BACKEND.rglob("*.py"):
        sp = str(p)
        if ".venv" in sp or f"{pathlib.os.sep}tests{pathlib.os.sep}" in sp:
            continue
        if p.name == "massive_keys.py":
            continue
        yield p


def test_no_module_reads_the_bare_key():
    """The landmine guard: routing MUST go through ``massive_keys.*`` so the
    .env's product-specific names resolve. Nobody reads the bare var directly."""
    offenders = []
    for p in _py_files():
        t = p.read_text()
        if any(pat in t for pat in _BARE_READS):
            offenders.append(str(p.relative_to(_BACKEND)))
    assert not offenders, (
        "These modules read the deprecated bare MASSIVE_API_KEY — route them "
        f"through massive_keys.stocks_key()/options_key(): {offenders}"
    )


def test_options_modules_use_options_key():
    for rel in ("options/soir.py", "options/scanner.py"):
        t = (_BACKEND / rel).read_text()
        assert "options_key()" in t, f"{rel} must read the OPTIONS key"
        assert "stocks_key()" not in t, f"{rel} must NOT read the stocks key"
