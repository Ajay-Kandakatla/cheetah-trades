"""Locks the EDGAR insider fix (sepa/insider) — CIK-scoped, issuer-stripped.

Bug (2026-06-03): the old code did a free-text phrase search for the ticker
string (`q="ST"`). For the 2-letter ticker ST (Sensata) that matched the
letters "ST" anywhere and returned 1,767 unrelated Form 4s (Apax, TotalEnergies,
PennyMac…) instead of Sensata's real 15 — and falsely tripped "cluster insider
buying" with 47 phantom insiders.

The fix resolves ticker -> issuer CIK, queries scoped to that CIK, and strips
the issuer's own name from each filing's party list. These tests pin both
behaviours offline (no network).
"""
import asyncio

import sepa.insider as ins


# ── issuer stripping ────────────────────────────────────────────────────────

def test_owner_names_strips_issuer():
    names = [
        "SIEDEL RICHARD W. JR.  (CIK 0001661082)",
        "Sensata Technologies Holding plc  (CIK 0001477294)",
    ]
    owners = ins._owner_names(names, "0001477294")
    assert owners == ["SIEDEL RICHARD W. JR.  (CIK 0001661082)"]
    assert all("Sensata" not in o for o in owners)


def test_owner_names_keeps_multiple_reporting_owners():
    names = [
        "Apax Guernsey (Holdco) PCC Ltd  (CIK 0001469807)",
        "Ignition Acquisition Holdings LP  (CIK 0001816556)",
        "Acme Corp  (CIK 0000000123)",
    ]
    owners = ins._owner_names(names, "0000000123")
    assert len(owners) == 2
    assert "Acme Corp  (CIK 0000000123)" not in owners


def test_owner_names_handles_empty():
    assert ins._owner_names([], "0001477294") == []
    assert ins._owner_names(None, "0001477294") == []


# ── unknown ticker returns zeros, never free-text garbage ────────────────────

def test_unknown_ticker_returns_empty(monkeypatch):
    async def fake_cik(_sym):
        return None

    # If this fires the test fails — an unknown ticker must NOT hit FTS.
    async def boom(*a, **k):
        raise AssertionError("must not run a filing search for an unknown ticker")

    monkeypatch.setattr(ins, "_ticker_to_cik", fake_cik)
    monkeypatch.setattr(ins, "_fts_search", boom)

    r = asyncio.run(ins.insider_activity("ZZZZ"))
    assert r["resolved_cik"] is None
    assert r["form4_count_30d"] == 0
    assert r["form4_unique_insiders_30d"] == 0
    assert r["form4_cluster_buy"] is False
    assert r["recent_filings"] == {"form4": [], "13d": [], "13g": []}


# ── end-to-end counting with a stubbed (offline) filing feed ─────────────────

def test_insider_activity_counts_real_owners(monkeypatch):
    async def fake_cik(_sym):
        return "0001477294"

    # 3 distinct Sensata insiders inside 30d (issuer already stripped here,
    # mirroring _fts_search's output).
    form4 = [
        {"form": "4", "filed": "2026-06-03", "display_names": ["SIEDEL RICHARD W. JR.  (CIK 0001661082)"]},
        {"form": "4", "filed": "2026-05-22", "display_names": ["Stott David K  (CIK 0001947385)"]},
        {"form": "4", "filed": "2026-05-08", "display_names": ["Caljouw Lynne J  (CIK 0001818333)"]},
        {"form": "4", "filed": "2026-04-09", "display_names": ["Caljouw Lynne J  (CIK 0001818333)"]},
    ]

    async def fake_fts(cik, form, days=60):
        assert cik == "0001477294"          # scoped to the issuer, not free text
        if form == "4":
            return list(form4)
        return []                           # no 13D/13G

    monkeypatch.setattr(ins, "_ticker_to_cik", fake_cik)
    monkeypatch.setattr(ins, "_fts_search", fake_fts)

    # Freeze "now" so the 30-day cutoff is deterministic.
    import datetime as _dt

    class _FrozenDT(_dt.datetime):
        @classmethod
        def utcnow(cls):
            return cls(2026, 6, 3)

    monkeypatch.setattr(ins, "datetime", _FrozenDT)

    r = asyncio.run(ins.insider_activity("ST"))
    assert r["resolved_cik"] == "0001477294"
    assert r["form4_count_60d"] == 4
    # 30d cutoff is 2026-05-04 → Apr 9 falls outside; Jun 3 / May 22 / May 8 in.
    assert r["form4_count_30d"] == 3
    assert r["form4_unique_insiders_30d"] == 3   # Siedel, Stott, Caljouw
    assert r["form4_cluster_buy"] is True
    assert r["sc13d_180d"] == 0 and r["sc13g_180d"] == 0
    # Far below the 1,767-hit free-text contamination the bug produced.
    assert r["form4_count_30d"] < 50
