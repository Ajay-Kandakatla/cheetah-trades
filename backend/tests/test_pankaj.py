"""Pankaj picks — data integrity + pure status logic.

No IO: every test drives the pure functions in ``sepa.pankaj_picks`` with
synthetic prices. The alert cron (``sepa.pankaj_alerts``) was removed
2026-09-08 (Ajay: "Remove all of Pankaj's alerts") — the guard at the bottom
keeps it out."""
import inspect
import pathlib

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


# ── the alert cron is gone (Ajay 2026-09-08: "Remove all of Pankaj's alerts") ──
ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_pankaj_alert_cron_is_gone_everywhere():
    """6,378 `pankaj_alert` rows (1 ever delivered) re-fired every 5 minutes into
    push_history and dominated the /alerts page once it opened on every push.
    Nothing computes, registers or labels the kind any more; the /pankaj page
    keeps his picks and levels."""
    assert not (ROOT / "backend" / "sepa" / "pankaj_alerts.py").exists()
    from sepa import cli
    src = inspect.getsource(cli)
    assert "pankaj_alerts" not in src and "check_pankaj_alerts" not in src
    assert not hasattr(pk, "alert_events") and not hasattr(pk, "CLOSE_WINDOW_ET")
    for gone in ("_confirm_text", "_stops_text", "_targets_text", "_in_close_window"):
        assert not hasattr(pk, gone), gone
    from market_hours import gate
    assert "pankaj_alert" not in gate.MARKET_ALERT_KINDS and "pankaj_alert" not in gate.PERSONAL_KINDS
    assert "pankaj" not in (ROOT / "backend" / "crontab").read_text().lower()
    fe = (ROOT / "frontend" / "src" / "lib" / "alertKinds.ts").read_text()
    assert "pankaj_alert" not in fe
    # the page's own pure reads stay
    assert pk.setup_status(_pick("VG")["setups"][0], 13.40)["state"] in {"triggered", "approaching", "below", "in_zone", "above_zone", "below_zone"}
