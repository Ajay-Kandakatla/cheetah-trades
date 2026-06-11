"""Pankaj picks — data integrity + pure status/alert logic.

No IO: every test drives the pure functions in ``sepa.pankaj_picks`` with
synthetic prices. The alert cron (``sepa.pankaj_alerts``) is just dedup + delivery
on top of these, so locking the pure logic locks the behaviour."""
from sepa import pankaj_picks as pk


def _pick(sym):
    return next(p for p in pk.load_picks() if p["symbol"] == sym)


# ── Data integrity ─────────────────────────────────────────────────────────
def test_picks_shape():
    picks = pk.load_picks()
    assert {p["symbol"] for p in picks} >= {"VG", "OKE", "MRVL"}
    for p in picks:
        assert p["symbol"] and p["name"] and p["analyst"] == "Pankaj"
        assert p["setups"], f"{p['symbol']} has no setups"
        for s in p["setups"]:
            assert s["id"] and s["kind"] in ("breakout", "pullback")
            stops = s.get("stops") or {}
            assert "aggressive" in stops and "conservative" in stops, s
            if s["kind"] == "breakout":
                assert isinstance(s["trigger"], (int, float))
                assert s["confirm"]["conservative"] and s["confirm"]["aggressive"]
            else:
                assert s["zone"]["lo"] < s["zone"]["hi"]


def test_levels_match_pankaj_notes():
    """Lock the verbatim levels so a careless edit can't silently drift them."""
    vg = _pick("VG")
    bo = next(s for s in vg["setups"] if s["kind"] == "breakout")
    assert bo["trigger"] == 13.35
    assert bo["stops"] == {"aggressive": 11.90, "conservative": 11.00}
    pbk = next(s for s in vg["setups"] if s["kind"] == "pullback")
    assert (pbk["zone"]["lo"], pbk["zone"]["hi"]) == (11.00, 11.50)

    oke = _pick("OKE")
    assert next(s for s in oke["setups"] if s["kind"] == "breakout")["trigger"] == 90.0

    mrvl = _pick("MRVL")
    mz = mrvl["setups"][0]
    assert (mz["zone"]["lo"], mz["zone"]["hi"]) == (195.0, 210.0)
    assert mz.get("extreme") is True


# ── setup_status (drives the page badge) ───────────────────────────────────
def test_status_breakout():
    bo = next(s for s in _pick("VG")["setups"] if s["kind"] == "breakout")
    assert pk.setup_status(bo, None)["state"] == "unknown"
    assert pk.setup_status(bo, 13.40)["state"] == "triggered"
    assert pk.setup_status(bo, 13.20)["state"] == "approaching"   # within 1.5% below 13.35
    assert pk.setup_status(bo, 12.50)["state"] == "below"


def test_status_pullback():
    pbk = next(s for s in _pick("VG")["setups"] if s["kind"] == "pullback")
    assert pk.setup_status(pbk, 11.30)["state"] == "in_zone"
    assert pk.setup_status(pbk, 12.00)["state"] == "above_zone"
    assert pk.setup_status(pbk, 10.50)["state"] == "below_zone"


# ── alert_events (drives the cron) ─────────────────────────────────────────
def _events(sym, price, now_hm=None):
    return {e["event"] for e in pk.alert_events(_pick(sym), price, now_hm)}


def test_breakout_trigger_and_close_confirm():
    # Intraday tag of the trigger → TRIGGER, but no close-confirm outside the window.
    assert "TRIGGER" in _events("VG", 13.40)
    assert "CLOSE_CONFIRM" not in _events("VG", 13.40)
    assert "CLOSE_CONFIRM" not in _events("VG", 13.40, "11:00")
    # In the close window, above the trigger → both fire.
    ev = _events("VG", 13.40, "16:00")
    assert "TRIGGER" in ev and "CLOSE_CONFIRM" in ev


def test_breakout_approach_and_quiet():
    assert "APPROACH" in _events("VG", 13.20)        # 1.1% below 13.35
    assert _events("VG", 12.50) == set()             # too far below the trigger / zone → silent


def test_pullback_zone_event():
    assert "ZONE" in _events("VG", 11.30)
    assert "ZONE" in _events("MRVL", 200.0)
    assert _events("MRVL", 288.0) == set()           # nowhere near the 195-210 zone


def test_events_have_attribution_and_levels():
    ev = pk.alert_events(_pick("VG"), 13.40, "16:00")
    for e in ev:
        assert "not advice" in e["body"].lower()
        assert e["emoji"] and e["title"] and e["setup_id"]


def test_titles_lead_with_brand_then_ticker():
    # Ajay 2026-06-10: notifications must read "Pankaj Swing Alert" then the
    # actual ticker, so the source is unmistakable on a phone lock screen.
    for sym, price in (("VG", 13.40), ("VG", 13.20), ("VG", 11.30), ("MRVL", 200.0)):
        for e in pk.alert_events(_pick(sym), price, "16:00"):
            assert e["title"].startswith(f"Pankaj Swing Alert · {sym}"), e["title"]
