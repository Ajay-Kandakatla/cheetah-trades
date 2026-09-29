"""🧬 Medical catalysts routine (catalysts/medical/routine.py, spec §3.9).

A whole pass over REAL captured payloads (KOD 2026-09-28 Finnhub + SEC 8-K
EX-99.1, Massive market-wide, FDA RSS, prod price-cache frames) with every
fetcher injected and in-memory collections. Pins: KOD -> ONE event from three
sources that rings once; the medical gate drops FTAI's aircraft deal and the
SAN-tagged SPAC IPO; the budget cuts a hung fetcher; the baseline never rings.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts.medical import routine as RT    # noqa: E402
from catalysts.medical import store as S       # noqa: E402
from catalysts.medical import sources as SRC   # noqa: E402
from tests.test_med_store import FakeColl, fake_colls   # noqa: E402

ET = ZoneInfo("America/New_York")
FX = Path(__file__).resolve().parent / "fixtures" / "medical"
NOW = datetime(2026, 9, 28, 7, 30, tzinfo=ET)          # Monday pre-market, the KOD morning

NAMES = {"KOD": "Kodiak Sciences Inc.", "MRNA": "Moderna, Inc.", "MIRM": "Mirum Pharmaceuticals, Inc.",
         "MNOV": "MediciNova, Inc.", "HUMA": "Humacyte, Inc.", "HCM": None, "AZN": None,
         "ARVN": "Arvinas, Inc.", "MSLE": None, "RLAY": "Relay Therapeutics, Inc.", "SAN": None,
         "FTAI": "FTAI Aviation Ltd.", "UNH": "UnitedHealth Group Incorporated", "AAPL": "Apple Inc."}
SEC_TITLES = {"HCM": "HUTCHMED (China) Ltd", "AZN": "ASTRAZENECA PLC", "SAN": "Banco Santander, S.A.",
              "MSLE": "Satellos Bioscience Inc."}
COMPANIES = {
    "KOD": {"sector": "Healthcare", "industry": "Biotechnology"},
    "MIRM": {"sector": "Healthcare", "industry": "Biotechnology"},
    "MNOV": {"sector": "Healthcare", "industry": "Biotechnology"},
    "HUMA": {"sector": "Healthcare", "industry": "Biotechnology"},
    "MRNA": {"sector": "Healthcare", "industry": "Biotechnology"},
    "UNH": {"sector": "Healthcare", "industry": "Healthcare Plans"},
    "AAPL": {"sector": "Technology", "industry": "Consumer Electronics"},
}


def load(name):
    p = FX / name
    return json.loads(p.read_text()) if p.suffix == ".json" else p.read_text()


def resp(status=200, body=None, text=""):
    return SimpleNamespace(status_code=status, json=lambda: body, text=text)


def frames():
    out = {}
    for sym, rows in load("frames_KOD_MIRM_MNOV_HUMA.json")["frames"].items():
        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
        df.index = pd.to_datetime(df.pop("date"))
        out[sym] = df
    return out


class Sender:
    def __init__(self):
        self.calls = []

    def __call__(self, owner, msg, kind):
        self.calls.append((owner, msg, kind))
        return {"sent": 1, "failed": 0, "total_targets": 1}


def fetchers(now=NOW, **over):
    cut = now.timestamp()
    fh = {"KOD": load("finnhub_KOD.json"), "MRNA": load("finnhub_MRNA_subset.json")}
    calls = {"finnhub": [], "snapshot": 0, "edgar": [], "http": []}

    async def finnhub(sym, days):
        calls["finnhub"].append(sym)
        return [r for r in fh.get(sym, []) if r["datetime"] <= cut]      # a replay never sees the future

    html = "<p>" + load("kod_ex991.txt") + "</p>"

    async def edgar_get(url, params=None, headers=None):
        calls["edgar"].append(url)
        from sepa.insider import EDGAR_FTS
        if url == EDGAR_FTS:
            return resp(200, load("efts_topline_8k.json"))
        if url == SRC.SEC_TICKERS_URL:
            return resp(200, {str(i): {"ticker": t, "title": v} for i, (t, v) in enumerate(SEC_TITLES.items())})
        if url.endswith("/1468748/000119312526403481/index.json"):
            return resp(200, load("kod_8k_index.json"))
        if url.endswith("d185059dex991.htm"):
            return resp(200, None, text=html)
        if url.endswith("index.json"):
            return resp(200, {"directory": {"item": [{"name": "x-8k.htm"}]}})
        if "submissions/CIK0001468748" in url:
            return resp(200, load("sec_submissions_KOD_subset.json"))
        return resp(404, None)

    async def http_get(url, params=None, headers=None):
        calls["http"].append(url)
        if url == SRC.MASSIVE_NEWS_URL:
            body = load("massive_med_subset.json")
            body["results"] = [r for r in body["results"]
                               if datetime.fromisoformat(r["published_utc"].replace("Z", "+00:00")).timestamp() <= cut]
            return resp(200, body)
        if url == SRC.FDA_PRESS_RSS:
            return resp(200, None, text=load("fda_press_rss.xml"))
        return resp(200, None, text="<p>nothing</p>")

    def snapshot(syms):
        calls["snapshot"] += 1
        return {"KOD": {"price": 32.35, "last_trade_price": 55.64, "prev_day_close": 32.35, "volume": 3.1e6,
                        "last_trade_ts_ms": datetime(2026, 9, 28, 7, 24, tzinfo=ET).timestamp() * 1000}}

    fx = {"finnhub": finnhub, "finnhub_cached": lambda s: False, "edgar_get": edgar_get, "http_get": http_get,
          "massive_key": "K", "universe": lambda: ["KOD", "MRNA", "MIRM", "MNOV", "HUMA", "UNH", "AAPL"],
          "companies": lambda syms: {s: COMPANIES[s] for s in syms if s in COMPANIES},
          "healthcare": lambda: {"KOD", "MRNA", "MIRM", "MNOV", "HUMA", "UNH", "HCM", "ARVN", "MSLE"},
          "biotech": lambda: ["MRNA"], "scope": lambda owner: {"KOD"}, "name_for": NAMES.get,
          "snapshot": snapshot, "frames": lambda syms: {s: f for s, f in frames().items() if s in syms},
          "load_prices": lambda s: None, "caps": lambda syms, last: {}, "pace_sec": 0, "sender": Sender()}
    fx.update(over)
    return fx, calls


def seeded(now=NOW, lap=True, names=("KOD", "MRNA", "MIRM", "MNOV", "HUMA")):
    """State of a routine that has been running: lap complete, feeds seen."""
    c = fake_colls()
    st = c[S.STATE]
    utc = now.astimezone(timezone.utc)
    st.docs["baseline"] = {"_id": "baseline", "started_at": utc - timedelta(days=3),
                           "lap_complete_at": (utc - timedelta(days=2)) if lap else None,
                           "names_done": list(names)}
    st.docs["edgar_seen"] = {"_id": "edgar_seen", "adsh": ["0000000000-00-000000"]}
    st.docs["massive_hwm"] = {"_id": "massive_hwm", "published_utc": utc - timedelta(hours=RT.LOOKBACK_H)}
    st.docs["fda_seen"] = {"_id": "fda_seen", "first_run_at": utc - timedelta(days=3)}
    return c


def tick(c, fx, now=NOW, **kw):
    kw.setdefault("owner", "o@x.com")
    return RT.run_tick(now=now, fetchers=fx, colls=c, **kw)


# ── the KOD morning ─────────────────────────────────────────────────────────
def test_kod_three_sources_become_ONE_event_that_rings_once():
    # 09:00 ET: after the 8-K (accepted 08:53:56 ET — EDGAR index), before the open
    now = NOW.replace(hour=9, minute=0)
    c = seeded(now=now)
    fx, calls = fetchers(now=now)
    out = tick(c, fx, now=now)
    assert out["ran"] is True, out
    ev = c[S.EVENTS].docs["KOD|topline_positive|2026-09-28"]
    provs = [s["provider"] for s in ev["sources"]]
    assert "sec" in provs and provs.count("finnhub") >= 2 and len(provs) >= 3
    assert ev["published_at"].astimezone(ET).strftime("%H:%M") == "02:34"
    assert ev["phase"] == "3" and "DAYBREAK" in ev["trials"] and "ophthalmology" in ev["areas"]
    assert not [k for k in c[S.EVENTS].docs if k.startswith("KOD|") and k != "KOD|topline_positive|2026-09-28"
                and k.split("|")[1].startswith("topline")], "every KOD topline re-report merged"
    liq = ev["reaction"]["liquidity"]
    assert liq["base_close"] == 32.35 and liq["base_basis"] == "frame" and round(liq["adv50_usd"] / 1e6, 1) == 22.7
    assert ev["reaction"]["at_close"] is None, "09:00 — the 09-28 bar is not closed"
    sends = fx["sender"].calls
    kod_msgs = [m for _o, m, _k in sends if m.get("ticker") == "KOD"]
    assert len(kod_msgs) == 1
    assert kod_msgs[0]["title"] == "🧬 KOD · Phase 3 topline positive · ophthalmology · +72% · UNMEASURED, not a buy signal"
    assert ev["push"]["state"] == "pushed"
    assert c["alert_pass_latest"].docs["med_catalyst"]["counts"]["pushed"] >= 1
    assert c[S.STATE].docs["lease"]["status"] == "done"
    # a second pass five minutes later: nothing rings again, nothing duplicates
    fx2, _ = fetchers(now=now, sender=Sender())            # same feed content, the next tick
    out2 = tick(c, fx2, now=now + timedelta(minutes=5))
    assert out2["ran"] and fx2["sender"].calls == []
    assert out2["counts"]["articles_new"] == 0 and out2["counts"]["articles_dup"] > 0


def test_the_medical_gate_drops_the_aircraft_deal_and_the_SAN_tagged_SPAC():
    c = seeded()
    fx, _ = fetchers()
    out = tick(c, fx)
    assert out["counts"]["non_medical_dropped"] >= 2
    tick_ = {e.get("ticker") for e in c[S.EVENTS].docs.values()}
    assert not tick_ & {"FTAI", "FTAIM", "SAN", "RLAY"}, "NEGATIVE: no partner / non-medical issuer"
    heads = " ".join(a["title"] for a in c[S.ARTICLES].docs.values())
    assert "Boeing 737" not in heads and "Live Oak" not in heads


def test_first_ever_pass_is_baseline_and_rings_nothing():
    c = fake_colls()
    fx, _ = fetchers()
    out = tick(c, fx)
    assert out["ran"] and fx["sender"].calls == []
    kod = c[S.EVENTS].docs["KOD|topline_positive|2026-09-28"]
    assert kod["baseline"] is True and kod["push"]["state"] == "baseline"
    assert c[S.STATE].docs["baseline"]["lap_complete_at"] is not None, "the whole 3-name roster was read"


def test_a_new_roster_name_first_fetch_is_baseline_after_the_lap():
    c = seeded(names=("MRNA", "MIRM", "MNOV", "HUMA"))                   # KOD never fetched before
    c[S.STATE].docs["edgar_seen"]["adsh"] = ["0001193125-26-403481"]     # the SEC copy already seen
    fx, _ = fetchers()
    tick(c, fx)
    kod = c[S.EVENTS].docs["KOD|topline_positive|2026-09-28"]
    assert kod["push"]["state"] == "baseline" and fx["sender"].calls == []


def test_roster_is_the_medical_industries_plus_the_biotech_theme_holdings_first():
    fx, _ = fetchers(scope=lambda owner: {"MNOV"}, biotech=lambda: ["MRNA", "ZZZZ"])
    r = RT.roster("o@x.com", fetchers=fx)
    assert r[0] == "MNOV" and r[1:3] == ["MRNA", "ZZZZ"], "tier 0 holdings, tier 1 biotech theme"
    assert "UNH" not in r and "AAPL" not in r, "Healthcare Plans / non-healthcare excluded"
    assert set(r) == {"KOD", "MRNA", "MIRM", "MNOV", "HUMA", "ZZZZ"}
    assert RT.MEDICAL_INDUSTRIES == ("Biotechnology", "Medical Devices", "Drug Manufacturers - Specialty & Generic",
                                     "Diagnostics & Research", "Medical Instruments & Supplies",
                                     "Drug Manufacturers - General")


def test_roster_includes_all_32_biotech_theme_names():
    from sepa.universe import THEME_UNIVERSE
    fx, _ = fetchers(biotech=RT._default_biotech)
    r = RT.roster(None, fetchers=fx)
    assert len(THEME_UNIVERSE["biotech"]) == 32 and set(THEME_UNIVERSE["biotech"]) <= set(r)


# ── clock, lease, window ────────────────────────────────────────────────────
def test_outside_the_window_does_not_run():
    fx, calls = fetchers()
    for t in (datetime(2026, 9, 28, 3, 59, tzinfo=ET), datetime(2026, 9, 28, 20, 0, tzinfo=ET)):
        out = RT.run_tick(now=t, fetchers=fx, colls=fake_colls())
        assert out == {"ran": False, "reason": "outside 04:00-20:00 ET"}
    assert calls["finnhub"] == [] and calls["edgar"] == []


def test_a_held_lease_skips_and_an_expired_one_is_reclaimed():
    c = seeded()
    utc = NOW.astimezone(timezone.utc)
    c[S.STATE].docs["lease"] = {"_id": "lease", "status": "running", "claimed_at": utc - timedelta(seconds=60),
                                "started_at": utc - timedelta(seconds=60), "pid": 1}
    fx, calls = fetchers()
    assert tick(c, fx) == {"ran": False, "reason": "lease held"} and calls["finnhub"] == []
    c[S.STATE].docs["lease"]["claimed_at"] = utc - timedelta(seconds=RT.LEASE_SEC + 1)
    c[S.STATE].docs["lease"]["started_at"] = utc - timedelta(seconds=RT.LEASE_SEC + 1)
    assert tick(c, fx)["ran"] is True


def test_min_gap_between_two_starts():
    c = seeded()
    fx, _ = fetchers()
    assert tick(c, fx)["ran"]
    fx2, _ = fetchers()
    assert tick(c, fx2, now=NOW + timedelta(seconds=RT.MIN_GAP_SEC - 30))["reason"] == "lease held"


# ── budget ──────────────────────────────────────────────────────────────────
def test_a_hung_fetcher_is_cut_and_its_leg_stops(monkeypatch):
    monkeypatch.setattr(RT, "CALL_CAP_SEC", 0.5)
    monkeypatch.setattr(RT, "CALL_MIN_SEC", 0.1)

    async def hang(sym, days):
        await asyncio.sleep(3600)
    fx, _ = fetchers(finnhub=hang)
    t0 = time.monotonic()
    out = tick(seeded(), fx, budget_sec=1.0)
    assert time.monotonic() - t0 < 3.0
    assert out["counts"]["call_timeouts"] >= 1 and out["counts"]["finnhub_stopped"] == 1
    assert out["counts"]["sliced"] == 0


def test_with_less_than_CALL_MIN_left_no_fetcher_is_ever_invoked():
    fx, calls = fetchers()
    out = tick(seeded(), fx, budget_sec=RT.CALL_MIN_SEC - 1)
    assert calls["finnhub"] == [] and calls["edgar"] == [] and calls["http"] == []
    assert out["counts"]["budget_exhausted"] >= 1


def test_the_cursor_advances_only_by_names_actually_fetched():
    clock = {"t": 0.0}

    async def slow(sym, days):
        clock["t"] += 4.0
        return []
    fx, calls = fetchers(finnhub=slow)
    c = seeded()
    out = tick(c, fx, budget_sec=10.0, clock=lambda: clock["t"])
    assert out["counts"]["sliced"] == 2 and out["counts"]["budget_exhausted"] >= 1
    assert c[S.STATE].docs["cursor"]["i"] == 2


def test_with_less_than_SYNC_RESERVE_left_the_snapshot_is_never_called():
    fx, calls = fetchers()
    c = seeded()
    tick(c, fx, budget_sec=RT.SYNC_RESERVE_SEC - 5)
    assert calls["snapshot"] == 0
    ev = c[S.EVENTS].docs.get("KOD|topline_positive|2026-09-28")
    if ev is not None:
        assert ev["reaction"]["liquidity"]["base_close"] == 32.35, "the Mongo frame still gives the base"


def test_the_cursor_resets_at_the_first_run_of_an_ET_day():
    c = seeded()
    c[S.STATE].docs["cursor"] = {"_id": "cursor", "i": 3, "day": "2026-09-25"}
    fx, calls = fetchers()
    tick(c, fx)
    assert calls["finnhub"][0] == "KOD", "tier 0 first on the morning sweep"


def test_dry_run_writes_no_pass_doc_and_sends_nothing():
    c = seeded()
    fx, _ = fetchers()
    out = tick(c, fx, dry_run=True)
    assert out["ran"] and fx["sender"].calls == []
    assert "med_catalyst" not in c["alert_pass_latest"].docs
    assert c[S.EVENTS].docs["KOD|topline_positive|2026-09-28"]["push"]["state"] == "pending"
    assert out["messages"] and out["messages"][0]["title"].startswith("🧬 KOD ·")


def test_no_push_keeps_events_pending_but_records_the_pass():
    c = seeded()
    fx, _ = fetchers()
    tick(c, fx, push=False)
    assert fx["sender"].calls == [] and "med_catalyst" in c["alert_pass_latest"].docs


def test_a_crash_inside_the_pass_is_redacted_and_the_lease_released():
    def boom():
        raise RuntimeError("https://api.massive.com/x?apiKey=SEKRET")
    fx, _ = fetchers(universe=boom)
    c = seeded()
    out = tick(c, fx)
    assert out["ran"] and "SEKRET" not in out["reason"] and out["counts"]["errors"] == 1
    assert c[S.STATE].docs["lease"]["status"] == "done"


def test_explain_prints_the_would_be_title_and_the_gate_reason():
    c = seeded()
    fx, _ = fetchers()
    tick(c, fx, push=False)
    ex = RT.explain("KOD", now=datetime(2026, 9, 28, 13, 0, tzinfo=ET), colls=c)
    top = [e for e in ex if e["event_key"] == "KOD|topline_positive|2026-09-28"][0]
    assert top["reason"] == "stale" and top["title"].startswith("🧬 KOD · Phase 3 topline positive")


def test_NEGATIVE_the_crontab_has_no_line_for_the_routine():
    tab = (Path(__file__).resolve().parents[1] / "crontab").read_text().splitlines()
    live = [ln for ln in tab if ln.strip() and not ln.lstrip().startswith("#")]
    assert not [ln for ln in live if "catalysts.medical" in ln]
    assert len([ln for ln in live if "catalysts.promo_live" in ln]) == 1


# ── critic 2026-09-29: the CLI installs log redaction (httpx logs keyed URLs at INFO) ──
def test_cli_main_installs_redaction(monkeypatch, capsys):
    import logging as _logging
    from observability.logsetup import RedactFilter
    root = _logging.getLogger()

    def reset():
        for h in [root] + list(root.handlers):
            for f in [f for f in h.filters if isinstance(f, RedactFilter)]:
                h.removeFilter(f)
        _logging.getLogger("httpx").setLevel(_logging.NOTSET)
    reset()
    try:
        monkeypatch.setattr(RT, "run_tick", lambda **kw: {"ran": False, "reason": "stub"})
        assert _logging.getLogger("httpx").level == _logging.NOTSET
        assert RT.main(["--dry-run"]) == 0
        assert _logging.getLogger("httpx").level >= _logging.WARNING
        assert any(isinstance(f, RedactFilter) for f in root.filters)
    finally:
        reset()


# ── critic 2026-09-29 #4: the OLDEST article creates the event (session date) ──
def test_the_oldest_article_keys_the_session_even_when_the_feed_is_newest_first():
    now = datetime(2026, 9, 29, 7, 30, tzinfo=ET)
    older = datetime(2026, 9, 28, 4, 2, tzinfo=ET).timestamp()        # Mon pre-market -> session 09-28
    newer = datetime(2026, 9, 28, 17, 30, tzinfo=ET).timestamp()      # Mon after the bell -> session 09-29
    rows = [  # Finnhub returns newest first
        {"category": "company", "datetime": int(newer), "headline": "Mirum Pharmaceuticals Receives FDA Approval "
         "of Atebrioz for Fibrodysplasia Ossificans Progressiva", "id": 902, "related": "MIRM",
         "source": "Benzinga", "summary": "", "url": "https://example.test/b"},
        {"category": "company", "datetime": int(older), "headline": "FDA Approves Mirum's Atebrioz for "
         "Fibrodysplasia Ossificans Progressiva", "id": 901, "related": "MIRM", "source": "Reuters",
         "summary": "", "url": "https://example.test/a"}]

    async def finnhub(sym, days):
        return rows if sym == "MIRM" else []
    c = seeded(now=now)
    fx, _ = fetchers(now=now, finnhub=finnhub)
    out = tick(c, fx, now=now, push=False)
    assert out["ran"], out
    mirm = {k: v for k, v in c[S.EVENTS].docs.items() if k.startswith("MIRM|fda_approval")}
    assert list(mirm) == ["MIRM|fda_approval|2026-09-28"], mirm.keys()
    ev = mirm["MIRM|fda_approval|2026-09-28"]
    assert ev["session_date"] == "2026-09-28" and len(ev["sources"]) == 2
    assert ev["published_at"].astimezone(ET).strftime("%m-%d %H:%M") == "09-28 04:02"


def test_event_doc_carries_congress_and_partial_for_the_labels():
    art = {"published": datetime(2026, 9, 28, 6, 0, tzinfo=ET).timestamp(), "title": "t", "provider": "finnhub",
           "key": "fh:1"}
    conf = RT._ev_doc({"event_type": "conference_data", "subtype": "upcoming", "congress": "ESMO"}, art,
                      {"modality": ["mrna"], "areas": ["oncology"]}, ticker="MRNA", company="Moderna",
                      now_utc=datetime(2026, 9, 28, 11, 0, tzinfo=timezone.utc), baseline=False)
    assert conf["congress"] == "ESMO" and conf["label"] == "ESMO data (upcoming)"
    hold = RT._ev_doc({"event_type": "clinical_hold", "subtype": "placed", "partial": True}, art, {},
                      ticker="ABC", company="ABC", now_utc=datetime(2026, 9, 28, 11, 0, tzinfo=timezone.utc),
                      baseline=False)
    assert hold["label"] == "Partial clinical hold placed" and hold["impact"] == "high"
