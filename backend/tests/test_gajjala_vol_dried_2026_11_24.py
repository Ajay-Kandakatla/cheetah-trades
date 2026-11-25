"""💧 "Armed, volume dried" — the push, the forward tracker, the nightly grade, the count line (2026-11-24).

Ajay, verbatim (2026-11-24): "Can you track something for me how many times have the stocks bumped right after volume
dried up.. I noticed that the best entries so far have been after volume dried up.. after all the other rules. Can you
send me notification of volume dried please.."

Pins chart_maps/gajjala/vol_dried.py (SPEC voldry REV 2 §3.2), its run.py / nightly / tab / rules_info wiring
(§3.3–§3.6) and scripts/gajjala_vol_dried_count.py (§4 be-engine step 4). Every positive sets the mode EXPLICITLY (one
test pins the shipped default "live" with his words). NEGATIVES are the point: a push he did not ask for — a second
ring, a held one ringing late, a ledger leak — is the failure.
"""
from __future__ import annotations

import inspect
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import entry_marks as EM
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import nightly as NG
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala import vol_dried as VD
from tests.test_gajjala_store import FakeColl, fake_store

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")
UTC = timezone.utc
S = date(2026, 11, 24)                                           # a Tuesday, NYSE open
WED = date(2026, 11, 25)
THANKSGIVING = date(2026, 11, 26)                                # NYSE closed
HALF = date(2026, 11, 27)                                        # NYSE half day (extended close 17:00)
SATURDAY = date(2026, 11, 28)
OWNER = "owner-local-part" + chr(64) + "example.com"
SYM = "ABC"
LIVE, OFF = GC.VOL_DRIED_PUSH_MODES[1], GC.VOL_DRIED_PUSH_MODES[0]
HIS_WORDS = "Can you send me notification of volume dried please.."
K3 = {"key": D.K3_VOL_KEY, "label": "K3 volume dried up on the pullback", "ok": True, "value": "busiest bar 40k",
      "need": "every bar at most half the run up's average"}


def at(hh, mm, d=S, ss=30, us=0):
    return datetime(d.year, d.month, d.day, hh, mm, ss, us, tzinfo=ET)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setattr(GC, "VOL_DRIED_PUSH_MODE", LIVE)


class Spy:
    def __init__(self, result=None, raise_=None, on_call=None):
        self.calls, self.raise_, self.on_call = [], raise_, on_call
        self.result = result if result is not None else {"sent": 1, "failed": 0, "total_targets": 1}

    def __call__(self, owner, payload):
        self.calls.append((owner, payload))
        if self.on_call:
            self.on_call()
        if self.raise_:
            raise self.raise_
        return self.result


def read(setup="bull_flag", *, state="forming", ready=True, base=2, crit=None, trigger=10.5, stop=10.0, **kw):
    r = {"setup": setup, "state": state, "ready": ready, "base": {"bars": base} if base is not None else None,
         "criteria": [dict(K3)] if crit is None else crit, "trigger": trigger, "stop": stop, "risk_pct": 4.8,
         "as_of_bar_t": "2026-11-24 10:25", "frame": "5m"}
    r.update(kw)
    return r


def frame_at(now, px=10.4, *, age_min=1):
    stamp = (now.astimezone(ET) - timedelta(minutes=age_min)).strftime("%Y-%m-%d %H:%M")
    return SimpleNamespace(as_of_bar_t={"5m": stamp, "15m": stamp}, f5=SimpleNamespace(c=[px]))


def entry(when, state="forming", kind="armed"):
    return {"at": PT._utc(when).isoformat(), "at_et": PT._hhmm(when), "state": state, "kind": kind}


def tracker(st, path, *, sym=SYM, setup="bull_flag", d=S, mode="normal", push=None):
    _id = ST.potential_key(d, sym, setup)
    doc = {"_id": _id, "date": d.isoformat(), "symbol": sym, "setup": setup, "first_seen_mode": mode,
           "state_path": list(path)}
    if push is not None:
        doc["push"] = push
    st.coll(ST.POTENTIALS).docs[_id] = doc
    return doc


def go(st, now, reads=None, *, session=None, vol=2_000_000, send=None, dry=False, frames=None, ctx=None, age_min=1):
    reads = reads if reads is not None else {SYM: {"bull_flag": read()}}
    send = send if send is not None else Spy()
    frames = frames if frames is not None else {s: frame_at(now, age_min=age_min) for s in reads}
    c = VD.run_step(st, reads, frames, now, session or now.astimezone(ET).date(),
                    volume={s: vol for s in reads}, ctx=ctx, owner=OWNER, send=send, dry=dry)
    return c, send


def gg_docs(st):
    return {k: v for k, v in st.alerts_coll().docs.items() if k.startswith("GGD:")}


# ── the constants and the shipped mode ───────────────────────────────────────────────────────────────────────────
def test_the_constants_his_words_and_the_shipped_default_is_live():
    assert GC.VOL_DRIED_PUSH_KIND == "gajjala_vol_dried" == VD.KIND
    assert GC.VOL_DRIED_PUSH_MODES == GC.FADE_CROSS_PUSH_MODES == ("off", "live")
    assert GC.VOL_DRIED_CLAIM_PREFIX == "GGD"
    src = (ROOT / "chart_maps" / "gajjala" / "constants.py").read_text(encoding="utf-8")
    line = next(ln for ln in src.splitlines() if ln.startswith("VOL_DRIED_PUSH_MODE = "))
    assert line.split("#")[0].strip() == 'VOL_DRIED_PUSH_MODE = "live"' and HIS_WORDS in line
    for p in ("GG", "GGX", "GGS", "GGW", GC.HIGH_SI_CROSS_CLAIM_PREFIX):
        assert GC.VOL_DRIED_CLAIM_PREFIX != p


@pytest.mark.parametrize("junk", ["shadow", "LIVE", "", None, 1, True])
def test_NEGATIVE_a_junk_mode_fails_closed_to_off(monkeypatch, junk):
    monkeypatch.setattr(GC, "VOL_DRIED_PUSH_MODE", junk)
    assert VD.mode() == OFF


def test_states_never_a_ledger_word_and_never_a_cross_word():
    assert not set(VD.STATES) & set(ST.LEDGER_ALERT_STATES)
    assert not set(VD.STATES) & set(AL.FADE_CROSS_STATES)
    assert all(s.startswith("dried_") for s in VD.STATES)
    assert VD.RECORDED == VD.STATES[1:] and "dried_claimed" not in VD.RECORDED and VD.RANG == ("dried_pushed",)


# ── the positives ────────────────────────────────────────────────────────────────────────────────────────────────
def test_building_then_armed_this_pass_rings_once_through_the_real_tracker():
    """The 🧠 gate and the 💧 step on the SAME `now`: 10:31 building (no ring), 10:36 armed (ONE ring), 10:41 still
    armed (steady)."""
    st = fake_store()
    tracker(st, [entry(at(4, 6))], sym="SEED", setup="kiss_fly")             # the D9 join rule stays out
    send, pot = Spy(), Spy()

    def both(now, r):
        reads = {SYM: {"bull_flag": r}}
        frames = {SYM: frame_at(now)}
        PT.run_pass(reads, frames, now, S, store=st, ctx={SYM: {}}, rows={SYM: {"volume": 2e6}}, send=pot,
                    owner=OWNER)
        return VD.run_step(st, reads, frames, now, S, volume={SYM: 2_000_000}, ctx={}, owner=OWNER, send=send)
    c1 = both(at(10, 31), read(ready=False))
    assert c1["armed"] == 0 and send.calls == []
    c2 = both(at(10, 36), read())
    assert c2["pushed"] == 1 and len(send.calls) == 1
    c3 = both(at(10, 41), read())
    assert c3["steady"] == 1 and c3["pushed"] == 0 and len(send.calls) == 1
    doc = gg_docs(st)[VD.claim_key(S, SYM, "bull_flag")]
    assert doc["state"] == "dried_pushed" and doc["transition_at"] == PT._utc(at(10, 36)).isoformat()


def test_the_payload_title_body_tag_url_kind_and_no_items():
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(at(10, 26), kind="building"), entry(now)])
    c, send = go(st, now)
    assert c["pushed"] == 1 and c["armed"] == 1
    owner, p = send.calls[0]
    e, label = PT._setup_meta("bull_flag")
    assert owner == OWNER and p["title"] == f"💧 Armed, volume dried · {SYM} · {e} {label}"
    r = read()
    assert p["body"] == " · ".join([f"trigger {GT._px(10.5)}", f"stop {GT._px(10.0)}{PT._risk_bit(r)}",
                                    f"{K3['label']} ({K3['value']})", PT.TAIL])
    assert p["tag"] == f"gg-dry-bull_flag-{SYM}" and not p["tag"].startswith("gg-pot")
    assert p["url"] == PT.deep_link(SYM, "bull_flag") and p["kind"] == GC.VOL_DRIED_PUSH_KIND and p["ticker"] == SYM
    assert "items" not in p
    assert "b" + "ounce" not in json.dumps(p, ensure_ascii=False).lower()
    doc = gg_docs(st)[VD.claim_key(S, SYM, "bull_flag")]
    assert doc["state"] == "dried_pushed" and doc["mode"] == LIVE and doc["kind"] == GC.VOL_DRIED_PUSH_KIND
    assert (doc["trigger"], doc["stop"], doc["price"], doc["risk_pct"]) == (10.5, 10.0, 10.4, 4.8)
    assert doc["at"] == PT._utc(now).isoformat() and doc["at_et"] == "10:31" and doc["bar_t"] == "2026-11-24 10:25"
    assert doc["vol_row"] == {k: K3[k] for k in ("label", "value", "need")}
    assert doc["result"] == {"sent": 1, "failed": 0, "total_targets": 1, "skipped": None}
    assert "trader" not in doc and "promo" not in doc


def test_tags_ride_the_body_and_the_claim_only_when_tagged():
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    ctx = {SYM: {"trader": "algo", "trader_text": "📌 algo", "promo": True, "promo_text": "🎪 promo"}}
    c, send = go(st, now, ctx=ctx)
    body = send.calls[0][1]["body"]
    assert "📌 algo · 🎪 promo · " + PT.TAIL in body
    doc = gg_docs(st)[VD.claim_key(S, SYM, "bull_flag")]
    assert doc["trader"] == "algo" and doc["promo"] is True and doc["promo_text"] == "🎪 promo"


def test_the_claim_lands_BEFORE_the_send_and_a_raising_send_settles_dried_failed():
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    seen = []
    key = VD.claim_key(S, SYM, "bull_flag")
    send = Spy(raise_=RuntimeError("push down"),
               on_call=lambda: seen.append((st.alerts_coll().docs.get(key) or {}).get("state")))
    c, _ = go(st, now, send=send)
    assert seen == ["dried_claimed"]                                          # on file at the moment of the send
    assert c["failed"] == 1 and gg_docs(st)[key]["state"] == "dried_failed"
    assert gg_docs(st)[key]["result"] == {"error": "RuntimeError"}


@pytest.mark.parametrize("res,state,ckey", [({"sent": 0, "total_targets": 0}, "dried_no_target", "no_target"),
                                            ({"sent": 0, "total_targets": 2}, "dried_failed", "failed")])
def test_no_target_and_failed_sends_stay_in_the_record(res, state, ckey):
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    c, _ = go(st, now, send=Spy(result=res))
    assert c[ckey] == 1 and gg_docs(st)[VD.claim_key(S, SYM, "bull_flag")]["state"] == state


def test_a_first_sighting_already_armed_rings():
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])                                                 # first entry, normal mode
    c, send = go(st, now)
    assert c["pushed"] == 1 and len(send.calls) == 1


def test_the_second_setup_of_a_name_rings_too_HIS_CALL_12():
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)], setup="bull_flag")
    tracker(st, [entry(now)], setup="intraday_vcp")
    reads = {SYM: {"intraday_vcp": read("intraday_vcp"), "bull_flag": read()}}
    c, send = go(st, now, reads)
    assert c["pushed"] == 2 and [p["tag"] for _o, p in send.calls] == [f"gg-dry-bull_flag-{SYM}",
                                                                       f"gg-dry-intraday_vcp-{SYM}"]   # SETUPS order


def test_shadow_mode_records_dried_shadow_and_NEVER_calls_the_sender(monkeypatch):
    monkeypatch.setattr(GC, "VOL_DRIED_PUSH_MODE", OFF)
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    c, send = go(st, now)
    assert c["shadow"] == 1 and c["pushed"] == 0 and send.calls == []
    doc = gg_docs(st)[VD.claim_key(S, SYM, "bull_flag")]
    assert doc["state"] == "dried_shadow" and doc["mode"] == OFF
    assert (doc["trigger"], doc["stop"], doc["price"]) == (10.5, 10.0, 10.4) and doc["at"] == PT._utc(now).isoformat()
    later = at(10, 41)                                                        # a re-arm the same session
    tracker(st, [entry(now), entry(at(10, 36), kind="building"), entry(later)])
    c2, send2 = go(st, later)
    assert c2["claimed_before"] == 1 and send2.calls == []


# ── NEGATIVE: another rule fails ─────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("r", [
    read(state="partial"),                                                    # a hard row False
    read(ready=False),                                                        # building (pending)
    read(variant="near_kiss"),                                                # a near-kiss variant
    read("intraday_vcp", grade="B"),                                          # a VCP "B"
    read(state="aplus"), read(state="triggered"),                             # A+ / triggered
    read(base=0),                                                             # no sideways bar yet
])
def test_NEGATIVE_a_read_that_is_not_trigger_armed_never_rings(r):
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)], setup=r["setup"])
    c, send = go(st, now, {SYM: {r["setup"]: r}})
    assert send.calls == [] and gg_docs(st) == {} and c["armed"] == 0
    assert sum(c.values()) == 0                                               # skipped, uncounted


def test_NEGATIVE_a_read_missing_from_the_pass_never_rings():
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    c, send = go(st, now, {"OTHER": {"bull_flag": read()}})
    assert send.calls == [] and gg_docs(st) == {}


@pytest.mark.parametrize("crit", [[], [dict(K3, ok=False)], [dict(K3, ok=None)], [dict(K3, key="k3_other")]])
def test_NEGATIVE_an_armed_read_without_a_met_vol_row_is_no_vol_row(crit):
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    c, send = go(st, now, {SYM: {"bull_flag": read(crit=crit)}})
    assert c["armed"] == 1 and c["no_vol_row"] == 1 and send.calls == [] and gg_docs(st) == {}


# ── NEGATIVE: already in state at the prior sighting / the transition ───────────────────────────────────────────
def test_NEGATIVE_armed_since_the_previous_pass_is_steady():
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(at(10, 26))])
    c, send = go(st, now)
    assert c["steady"] == 1 and send.calls == [] and gg_docs(st) == {}


def test_turned_now_is_a_datetime_compare():
    now = at(10, 31, us=123456)
    assert VD.turned_now({"state_path": [entry(now)]}, now) is True
    assert VD.turned_now({"state_path": [entry(now, kind="building")]}, now) is False          # ready_since None
    assert VD.turned_now(None, now) is False and VD.turned_now({"state_path": []}, now) is False
    off = dict(entry(now), at=PT._utc(now + timedelta(microseconds=1)).isoformat())
    assert VD.turned_now({"state_path": [off]}, now) is False                                   # one µs off
    naive = dict(entry(now), at=PT._utc(now).replace(tzinfo=None))                             # naive UTC datetime
    assert VD.turned_now({"state_path": [naive]}, now) is True
    assert VD.turned_now({"state_path": [entry(now)], "first_seen_mode": "joined"}, now) is False


def test_NEGATIVE_a_joined_docs_first_entry_is_steady_but_its_later_rearm_rings():
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)], mode="joined")
    c, send = go(st, now)
    assert c["steady"] == 1 and send.calls == []
    later = at(10, 41)
    tracker(st, [entry(now), entry(at(10, 36), kind="building"), entry(later)], mode="joined")
    c2, send2 = go(st, later)
    assert c2["pushed"] == 1 and len(send2.calls) == 1


def test_NEGATIVE_no_second_ring_the_same_session():
    st = fake_store()
    send = Spy()
    t1 = at(10, 31)
    tracker(st, [entry(t1)])
    go(st, t1, send=send)
    t3 = at(10, 41)
    tracker(st, [entry(t1), entry(at(10, 36), kind="building"), entry(t3)])
    c, _ = go(st, t3, send=send)
    assert c["claimed_before"] == 1 and len(send.calls) == 1


def test_NEGATIVE_the_tracker_read_fault_is_no_tracker_never_a_send(monkeypatch):
    st = fake_store()
    monkeypatch.setattr(st, "potentials", lambda session: None)
    c, send = go(st, at(10, 31))
    assert c["no_tracker"] == 1 and c["armed"] == 1 and send.calls == [] and gg_docs(st) == {}


def test_NEGATIVE_no_tracker_doc_for_the_pair_is_no_tracker():
    st = fake_store()
    tracker(st, [entry(at(10, 31))], setup="kiss_fly")
    c, send = go(st, at(10, 31))
    assert c["no_tracker"] == 1 and send.calls == []


# ── NEGATIVE: the day, the window, the tape, the floor, the plan ─────────────────────────────────────────────────
@pytest.mark.parametrize("now,want", [(at(10, 31, d=SATURDAY), "closed_day"), (at(10, 31, d=THANKSGIVING), "closed_day"),
                                      (at(17, 1, d=HALF), "outside_hours"), (at(3, 59), "outside_hours"),
                                      (at(20, 1), "outside_hours"), (at(9, 36), "muted"), (at(9, 44), "muted")])
def test_NEGATIVE_closed_days_the_window_and_the_mute(now, want):
    st = fake_store()
    d = now.astimezone(ET).date()
    tracker(st, [entry(now)], d=d)
    c, send = go(st, now)
    assert c[want] == 1 and send.calls == [] and gg_docs(st) == {}


@pytest.mark.parametrize("now", [at(16, 59, d=HALF), at(9, 46)])
def test_the_half_day_1659_and_the_0946_pass_ring(now):
    st = fake_store()
    tracker(st, [entry(now)], d=now.astimezone(ET).date())
    c, send = go(st, now)
    assert c["pushed"] == 1 and len(send.calls) == 1


def test_NEGATIVE_a_refusal_never_consumes_the_claim():
    st = fake_store()
    send = Spy()
    t1 = at(9, 36)
    tracker(st, [entry(t1)])
    c, _ = go(st, t1, send=send)
    assert c["muted"] == 1 and gg_docs(st) == {}                              # no GGD doc on file
    t3 = at(10, 31)
    tracker(st, [entry(t1), entry(at(9, 41), kind="building"), entry(t3)])
    c2, _ = go(st, t3, send=send)
    assert c2["pushed"] == 1 and len(send.calls) == 1


@pytest.mark.parametrize("vol", [None, float("nan"), True, "1e6", 999_999, float("inf")])
def test_NEGATIVE_under_or_unknown_session_volume_is_held(vol):
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    c, send = go(st, now, vol=vol)
    assert c["under_floor"] == 1 and send.calls == [] and gg_docs(st) == {}


def test_the_floor_itself_rings():
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    c, send = go(st, now, vol=GC.K11_MIN_SESSION_VOLUME)
    assert GC.K11_MIN_SESSION_VOLUME == 1_000_000 and c["pushed"] == 1


@pytest.mark.parametrize("trig,stop", [(10.0, 10.0), (float("nan"), 10.0), (10.0, 10.5), (None, 10.0)])
def test_NEGATIVE_no_plan_is_no_risk(trig, stop):
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    c, send = go(st, now, {SYM: {"bull_flag": read(trigger=trig, stop=stop)}})
    assert c["no_risk"] == 1 and send.calls == []


def test_NEGATIVE_a_stale_tape_is_held():
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    c, send = go(st, now, age_min=AL.MAX_ENTRY_AGE_SEC // 60 + 2)
    assert c["stale_tape"] == 1 and send.calls == []


def test_NEGATIVE_dry_writes_and_sends_nothing_and_no_store_is_no_store(monkeypatch):
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    c, send = go(st, now, dry=True)
    assert c["dry"] == 1 and send.calls == [] and gg_docs(st) == {}
    monkeypatch.setattr(st, "alerts_coll", lambda: None)
    c2, send2 = go(st, now)
    assert c2["no_store"] == 1 and send2.calls == []


def test_NEGATIVE_a_junk_mode_shadows_and_never_sends(monkeypatch):
    monkeypatch.setattr(GC, "VOL_DRIED_PUSH_MODE", "loud")
    st = fake_store()
    now = at(10, 31)
    tracker(st, [entry(now)])
    c, send = go(st, now)
    assert c["shadow"] == 1 and send.calls == []


def test_NEGATIVE_a_claim_write_fault_fails_open_for_ONE_send_only_C6():
    """demand_alerts.claim_key reads True on a write error: that pass sends ONCE, unrecorded. The next pass with the
    same tracker reads `steady` — no second send."""
    st = fake_store(**{ST.ALERTS: FakeColl(fail=True)})
    send = Spy()
    now = at(10, 31)
    tracker(st, [entry(now)])
    c, _ = go(st, now, send=send)
    assert c["pushed"] == 1 and len(send.calls) == 1 and st.alerts_coll().docs == {}
    c2, _ = go(st, at(10, 36), send=send)
    assert c2["steady"] == 1 and len(send.calls) == 1


@pytest.mark.parametrize("variant", [V.GG1, V.GGA])
def test_NEGATIVE_a_non_gg5_store_returns_zero_counts_and_never_imports_the_sender(monkeypatch, variant):
    monkeypatch.setattr(VD, "_send", lambda *a, **k: (_ for _ in ()).throw(AssertionError("imported")))
    st = ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=variant)
    monkeypatch.setattr(st, "potentials", lambda s: (_ for _ in ()).throw(AssertionError("read")))
    c = VD.run_step(st, {SYM: {"bull_flag": read()}}, {SYM: frame_at(at(10, 31))}, at(10, 31), S,
                    volume={SYM: 2e6}, owner=OWNER)
    assert c == {k: 0 for k in VD.COUNT_KEYS}


# ── run.py wiring ────────────────────────────────────────────────────────────────────────────────────────────────
class Rec:
    def __init__(self, exc=None, order=None, tag="vd"):
        self.calls, self.exc, self.order, self.tag = [], exc, order, tag

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        if self.order is not None:
            self.order.append(self.tag)
        if self.exc:
            raise self.exc
        return {"armed": 1}


def _pass_deps(**kw):
    from tests.test_gajjala_run import make_deps
    deps, _snap, _send, _status = make_deps()
    for k, v in kw.items():
        setattr(deps, k, v)
    return deps


def test_the_deps_default_none_and_the_cron_deps_carry_it():
    assert RUN.Deps().vol_dried is None and RUN.dry_deps().vol_dried is None
    assert RUN._cron_deps().vol_dried is VD.run_step


def test_the_pass_calls_the_step_after_the_potential_step_with_the_SAME_now_and_sv(monkeypatch):
    from tests.test_gajjala_run import NOW as RNOW
    order, pot_now = [], []
    real = PT.run_pass

    def pot(*a, **k):
        order.append("pot")
        pot_now.append(a[2])
        return real(*a, **k)
    monkeypatch.setattr(PT, "run_pass", pot)
    base = RUN.run_pass(RNOW, store=fake_store(), deps=_pass_deps())
    st = fake_store()
    step = Rec(order=order)
    xc = Rec(order=order, tag="xc")
    out = RUN.run_pass(RNOW, store=st, deps=_pass_deps(vol_dried=step, fade_cross=xc))
    (a, k), = step.calls
    assert a[0] is st and a[3] is pot_now[-1] and a[4] == date(2026, 10, 13)
    assert isinstance(a[1], dict) and a[1] and isinstance(a[2], dict)
    assert set(k) == {"volume", "ctx", "owner"} and isinstance(k["volume"], dict) and k["volume"]
    assert all(v == 3_000_000 for v in k["volume"].values())                # sv = the number K11 reads
    assert order[-3:] == ["pot", "vd", "xc"]                                 # after 🧠, before 🔀
    assert out == base and "vol_dried" not in json.dumps(sorted(out))


def test_NEGATIVE_not_on_an_open_a_dry_run_or_a_potential_gate_that_did_not_complete(monkeypatch):
    from tests.test_gajjala_run import NOW as RNOW
    step = Rec()
    RUN.run_pass(RNOW, store=RUN.dry_store(fake_store()), deps=_pass_deps(vol_dried=step), dry=True)
    RUN.run_on_demand(RNOW, store=fake_store(), deps=_pass_deps(vol_dried=step))
    assert step.calls == []
    monkeypatch.setattr(PT, "run_pass", lambda *a, **k: {"potential": 1})   # no tracked_today = a read fault
    RUN.run_pass(RNOW, store=fake_store(), deps=_pass_deps(vol_dried=step))
    monkeypatch.setattr(PT, "run_pass", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("gate down")))
    RUN.run_pass(RNOW, store=fake_store(), deps=_pass_deps(vol_dried=step))
    assert step.calls == []


def test_NEGATIVE_a_raising_step_never_reaches_errors_or_a_key_of_out():
    from tests.test_gajjala_run import NOW as RNOW
    base = RUN.run_pass(RNOW, store=fake_store(), deps=_pass_deps())
    out = RUN.run_pass(RNOW, store=fake_store(), deps=_pass_deps(vol_dried=Rec(exc=RuntimeError("boom"))))
    assert out["errors"] == [] and out == base


def test_the_real_step_on_a_real_pass_rings_the_fixture_days_armed_flag():
    """tests/test_gajjala_run's day: GGA forms a Bull Flag at 10:31 — the 🧠 rings it armed, and so does 💧, once."""
    from tests.test_gajjala_run import T1, T2, at as rat, snap_row
    from tests.test_gajjala_run import make_deps
    st = fake_store()
    tracker(st, [entry(rat(4, 6))], sym="SEED", setup="kiss_fly", d=date(2026, 10, 13))
    send = Spy()
    hook = (lambda *a, **k: VD.run_step(*a, **k, send=send))
    for now in (T1, T2):
        deps, _s, _x, _y = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=rat(10, 30))})
        deps.vol_dried = hook
        out = RUN.run_pass(now, store=st, deps=deps)
        assert out["errors"] == []
    docs = gg_docs(st)
    assert len(send.calls) == 1 and len(docs) == 1, docs
    p = send.calls[0][1]
    assert p["ticker"] == "GGA" and p["kind"] == GC.VOL_DRIED_PUSH_KIND
    (doc,) = docs.values()
    assert doc["state"] == "dried_pushed" and doc["at"] == PT._utc(T1).isoformat()


# ── ISOLATION ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_ISOLATION_a_ggd_doc_is_never_a_ledger_row():
    st = fake_store()
    coll = st.alerts_coll()
    for state in ("dried_pushed", "dried_shadow"):
        coll.docs[f"GGD:{S.isoformat()}|{SYM}|{state}"] = {"_id": f"GGD:{S.isoformat()}|{SYM}|{state}",
                                                           "date": S.isoformat(), "symbol": SYM, "setup": "bull_flag",
                                                           "state": state, "at": PT._utc(at(10, 31)).isoformat(),
                                                           "trigger": 10.5, "stop": 10.0}
    assert st.alert_rows([S]) == []
    assert LG.rows_for([S], st) == []


def test_ISOLATION_the_lane_and_the_stream_never_name_the_kind_or_the_prefix():
    for rel in ("trading/gajjala_entry.py", "trading/gajjala_stream.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "gajjala_vol_dried" not in src and "GGD" not in src and "vol_dried" not in src, rel


# ── INVARIANT: on GG5, a "trigger armed" read has met K3 ─────────────────────────────────────────────────────────
def _sweep():
    from tests.fixtures.gajjala import detector_frames as FX
    frames = {
        "bull_flag": [FX.frame(FX.bf_bars(entry=None)), FX.frame(FX.bf_bars(FX.flat_pull(4), entry=None)),
                      FX.bf_aplus(), FX.frame(FX.bf_bars([FX.P1, FX.P2, FX.P3], entry=None))],
        "kiss_fly": [FX.kf_frame(), FX.kf_frame(kiss_above_pct=0.6, entry=False), FX.kf_frame(n_pull=5)],
        "horizontal_fade": [FX.hf_frame(tf="5m"), FX.hf_frame(FX.HF_BASE[:5], entry=None, tf="5m"),
                            FX.hf_frame(entry=None, tf="5m")],
        "intraday_vcp": [FX.vcp_frame(), FX.vcp_frame(entry=None)],
        "reversal_squeeze": [FX.rs_frame(), FX.rs_frame(entry=None)],
    }
    out = []
    for setup, Fs in frames.items():
        for F in Fs:
            for k in range(F.today.start, len(F.c)):
                G = FX.prefix(F, k)
                if setup == "bull_flag":
                    r = D.bull_flag(G)
                elif setup == "kiss_fly":
                    r = D.kiss_fly(G)
                elif setup == "horizontal_fade":
                    r = D.horizontal_fade(None, G)
                elif setup == "intraday_vcp":
                    r = D.intraday_vcp(G)
                else:
                    r = D.reversal_squeeze(G, float_read=FX.float_read(5e6))
                out.append((setup, r))
    return out


def test_INVARIANT_every_gg5_forming_ready_read_has_k3_vol_met():
    reads = _sweep()
    ready = [(s, r) for s, r in reads if r.get("state") == "forming" and r.get("ready") is True]
    assert len({s for s, _r in ready}) >= 4 and len(ready) >= 8                 # the sweep is not vacuous
    for s, r in ready:
        row = next((c for c in r.get("criteria") or [] if c.get("key") == D.K3_VOL_KEY), None)
        assert row is not None and row.get("ok") is True, (s, r.get("criteria"))


def test_INVARIANT_NEGATIVE_a_k3_miss_is_partial_never_armed():
    from tests.fixtures.gajjala import detector_frames as FX
    heavy = (FX.P1[0], FX.P1[1], FX.P1[2], FX.P1[3], 900_000)                  # far over the K3 cap
    r = D.bull_flag(FX.frame(FX.bf_bars([heavy, FX.P2], entry=None)))
    assert r["state"] == "partial" and D.K3_VOL_KEY in r["missed"]
    assert PT.potential_kind(r) is None and not VD.in_state(r)


# ── grade_row (pure) ─────────────────────────────────────────────────────────────────────────────────────────────
RING = at(10, 31)


def bar(hh, mm, o, h, lo, c, d=S):
    return (datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).astimezone(UTC), o, h, lo, c)


def gdoc(at_=RING, d=S, trigger=10.5, stop=10.0, price=10.2, **kw):
    doc = {"_id": f"GGD:{d.isoformat()}|{SYM}|bull_flag", "date": d.isoformat(), "symbol": SYM, "setup": "bull_flag",
           "state": "dried_pushed", "at": PT._utc(at_).isoformat(), "trigger": trigger, "stop": stop, "price": price}
    doc.update(kw)
    return doc


def gr(bars, doc=None):
    doc = doc or gdoc()
    return VD.grade_row(doc, bars, LG.session_bounds(doc["date"], LG._parse_at(doc["at"])))


def test_grade_row_filled_then_win_and_then_loss():
    g = gr([bar(10, 46, 10.4, 10.6, 10.3, 10.5), bar(10, 50, 10.6, 11.1, 10.6, 11.0)])
    assert g["triggered"] is True and g["won"] is True and g["outcome"] == "win" and g["stop_first"] is False
    assert g["max_high"] == 11.1 and g["version"] == VD.GRADE_VERSION
    g = gr([bar(10, 46, 10.4, 10.6, 10.3, 10.5), bar(10, 50, 10.4, 10.45, 9.9, 10.0), bar(11, 0, 10, 12, 10, 12)])
    assert g["triggered"] is True and g["won"] is False and g["outcome"] == "loss" and g["stop_first"] is False
    assert g["max_high"] == 10.6                                              # capped before the 10:50 stop minute


def test_grade_row_never_filled_stop_first_by_touch():
    g = gr([bar(10, 40, 10.2, 10.3, 9.9, 10.0)])
    assert g["triggered"] is False and g["won"] is False and g["stop_first"] is True and g["entry"] == "no_entry"
    g = gr([bar(10, 40, 10.2, 10.3, 10.1, 10.2)])
    assert g["stop_first"] is False and g["stop_t"] is None


def test_grade_row_stop_then_fill_and_the_same_minute_fill_and_stop():
    g = gr([bar(10, 40, 10.2, 10.3, 9.9, 10.0), bar(10, 50, 10.4, 10.6, 10.3, 10.5)])
    assert g["triggered"] is True and g["stop_first"] is True
    g = gr([bar(10, 46, 10.4, 10.6, 9.9, 10.0)])
    assert g["outcome"] == "loss" and g["reason"] == "stop_fill_minute" and g["stop_first"] is False


def test_grade_row_C5_no_high_after_or_inside_the_first_stop_minute_counts():
    g = gr([bar(10, 35, 10.2, 10.3, 10.1, 10.2), bar(10, 40, 10.2, 10.45, 9.9, 10.0), bar(10, 50, 10.4, 12.0, 10.3, 11.9)])
    assert g["max_high"] == 10.3
    assert g["max_vs_ring_pct"] == round((10.3 / 10.2 - 1) * 100, 2)
    assert g["max_vs_trigger_pct"] == round((10.3 / 10.5 - 1) * 100, 2)
    assert g["r_max"] == pytest.approx(LG.r_past(10.5, 10.0, 10.3)) == pytest.approx(-0.4)
    g = gr([bar(10, 35, 10.2, 10.9, 9.9, 10.0), bar(10, 40, 10.2, 12.0, 10.1, 11.9)])
    assert g["max_high"] is None and g["r_max"] is None and g["max_vs_ring_pct"] is None


@pytest.mark.parametrize("price", [None, float("nan"), 0, "x"])
def test_NEGATIVE_a_bad_ring_price_is_none_never_nan(price):
    g = gr([bar(10, 35, 10.2, 10.3, 10.1, 10.2)], gdoc(price=price))
    assert g["max_vs_ring_pct"] is None and g["max_high"] == 10.3
    json.dumps(g, allow_nan=False)


def test_NEGATIVE_the_ring_minute_and_before_never_count():
    g = gr([bar(10, 30, 10.2, 13.0, 9.0, 10.2), bar(10, 35, 10.2, 10.3, 10.1, 10.2)])
    assert g["max_high"] == 10.3 and g["stop_first"] is False


# ── grade_step ───────────────────────────────────────────────────────────────────────────────────────────────────
NIGHT = at(20, 15)
WED_NIGHT = at(20, 15, d=WED)


class Loader:
    def __init__(self, by=None, fail=()):
        self.by, self.fail, self.calls = by or {}, set(fail), []

    def __call__(self, sym, day):
        self.calls.append((sym, day))
        if day in self.fail:
            return None, True
        return list(self.by.get(day, [])), False


def store_with(*docs, alerts=None):
    st = fake_store(**({ST.ALERTS: alerts} if alerts is not None else {}))
    for d in docs:
        st.alerts_coll().docs[d["_id"]] = dict(d)
    return st


def gs(st, now=NIGHT, **kw):
    kw.setdefault("load_day", Loader({S: [bar(10, 46, 10.4, 10.6, 10.3, 10.5)]}))
    kw.setdefault("split_lookup", lambda *a: False)
    return VD.grade_step(st, now, **kw)


def test_grade_step_grades_a_due_row_once_and_writes_it():
    st = store_with(gdoc())
    out = gs(st)
    assert out["rows"] == 1 and out["graded"] == 1 and out["written"] == 1 and out["read_fault"] is False
    g = st.alerts_coll().docs[gdoc()["_id"]]["grade"]
    assert g["triggered"] is True and g["version"] == VD.GRADE_VERSION
    again = gs(st)
    assert again["already"] == 1 and again["graded"] == 0


def test_NEGATIVE_not_due_before_close_plus_settle_and_the_cap_defers():
    st = store_with(gdoc())
    assert gs(st, at(16, 0, ss=10))["not_due"] == 1
    out = gs(st, max_loads=0)
    assert out["deferred_cap"] == 1 and "grade" not in st.alerts_coll().docs[gdoc()["_id"]]


def test_NEGATIVE_a_failed_load_is_retried_never_written():
    st = store_with(gdoc())
    out = gs(st, load_day=Loader(fail=[S]))
    assert out["load_failed"] == 1 and out["written"] == 0 and "grade" not in st.alerts_coll().docs[gdoc()["_id"]]
    out = gs(st, load_day=Loader({}))
    assert out["no_bars"] == 1 and "grade" not in st.alerts_coll().docs[gdoc()["_id"]]


def test_C8_an_after_close_ring_loads_the_ring_evening_and_counts_its_stop():
    doc = gdoc(at_=at(17, 0))
    st = store_with(doc)
    ld = Loader({S: [bar(17, 30, 10.4, 10.8, 9.9, 10.0)],                      # evening: stop touch AND a high > trigger
                 WED: [bar(10, 0, 10.0, 10.2, 10.0, 10.1)]})
    out = gs(st, WED_NIGHT, load_day=ld)
    assert out["written"] == 1 and sorted(d for _s, d in ld.calls) == [S, WED]
    g = st.alerts_coll().docs[doc["_id"]]["grade"]
    assert g["stop_first"] is True and g["triggered"] is False                # 17:30 is never a fill minute
    assert g["max_high"] is None                                              # the stop is the first eligible minute


def test_C8_a_pre_close_ring_loads_one_day_only_and_an_after_close_failure_of_either_day_retries():
    ld = Loader({S: [bar(10, 46, 10.4, 10.6, 10.3, 10.5)]})
    gs(store_with(gdoc()), load_day=ld)
    assert ld.calls == [(SYM, S)]
    st = store_with(gdoc(at_=at(17, 0)))
    assert gs(st, WED_NIGHT, load_day=Loader({WED: [bar(10, 0, 10, 10.2, 10, 10.1)]}, fail=[S]))["load_failed"] == 1
    assert gs(st, WED_NIGHT, load_day=Loader({S: []}, fail=[WED]))["load_failed"] == 1
    out = gs(st, WED_NIGHT, load_day=Loader({WED: [bar(10, 0, 10, 10.2, 10, 10.1)]}))   # a quiet evening is no fault
    assert out["written"] == 1


def test_an_after_close_ring_split_and_an_unread_split_check():
    st = store_with(gdoc(at_=at(17, 0)))
    out = gs(st, WED_NIGHT, split_lookup=lambda *a: None)
    assert out["split_check_failed"] == 1 and "grade" not in st.alerts_coll().docs[gdoc()["_id"]]
    out = gs(st, WED_NIGHT, split_lookup=lambda *a: "2026-11-25")
    assert out["split"] == 1 and st.alerts_coll().docs[gdoc()["_id"]]["grade"]["reason"] == "split"


def test_every_recorded_state_is_graded_but_never_the_in_flight_claim():
    docs = [gdoc(_id=f"GGD:{S.isoformat()}|S{i}|bull_flag", symbol=f"S{i}", state=s)
            for i, s in enumerate(VD.STATES)]
    st = store_with(*docs, {"_id": "GG:2026-11-24|X|bull_flag", "date": S.isoformat(), "state": "dried_pushed"})
    out = gs(st, load_day=lambda sym, day: ([bar(10, 46, 10.4, 10.6, 10.3, 10.5)], False))
    assert out["rows"] == len(VD.RECORDED) == 4 and out["written"] == 4
    assert "grade" not in st.alerts_coll().docs[docs[0]["_id"]]               # dried_claimed — in flight
    assert "grade" not in st.alerts_coll().docs["GG:2026-11-24|X|bull_flag"]  # NEGATIVE: never a non-GGD id


def test_NEGATIVE_dry_writes_nothing_and_a_read_fault_is_read_fault():
    st = store_with(gdoc())
    out = gs(st, dry=True)
    assert out["graded"] == 1 and out["written"] == 0 and "grade" not in st.alerts_coll().docs[gdoc()["_id"]]
    assert gs(store_with(alerts=FakeColl(fail=True)))["read_fault"] is True


def test_grade_night_never_raises(monkeypatch):
    monkeypatch.setattr(ST, "default", lambda: (_ for _ in ()).throw(RuntimeError("no mongo")))
    assert VD.grade_night(NIGHT) == {"error": "grade: RuntimeError"}
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    assert "grade" in VD.grade_night(NIGHT)


def test_nightly_main_carries_the_vol_dried_grade_after_the_divergence_fenced(monkeypatch, capsys):
    from chart_maps.gajjala import divergence as DV
    order: list = []
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    monkeypatch.setattr(NG, "run", lambda *a, **k: order.append("gg5") or {"errors": []})
    monkeypatch.setattr(NG, "grade_1m", lambda now, **k: order.append("gg1") or {"grade": {}})
    monkeypatch.setattr(NG, "grade_audited", lambda now, **k: order.append("gga") or {"grade": {}})
    monkeypatch.setattr(DV, "grade_divergence", lambda now, **k: order.append("dv") or {"grade": {}})
    monkeypatch.setattr(VD, "grade_night", lambda now: order.append("vd") or {"error": "grade: RuntimeError"})
    assert NG.main([]) == 0                                                   # a 💧 failure never moves the exit code
    assert order == ["gg5", "gg1", "gga", "dv", "vd"]
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["gajjala_vol_dried"] == {"error": "grade: RuntimeError"} and out["errors"] == []
    order.clear()
    assert NG.main(["--steps", "floats"]) == 0 and "vd" not in order         # NEGATIVE: no grade step → no grade
    assert NG.STEPS == ("floats", "halts", "history", "bases", "grade")


def test_NEGATIVE_nightly_main_fences_the_vol_dried_import_and_a_raising_grade(monkeypatch, capsys):
    import sys
    import chart_maps.gajjala as PKG
    from chart_maps.gajjala import divergence as DV
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    monkeypatch.setattr(NG, "run", lambda *a, **k: {"errors": []})
    monkeypatch.setattr(NG, "grade_1m", lambda now, **k: {"grade": {}})
    monkeypatch.setattr(NG, "grade_audited", lambda now, **k: {"grade": {}})
    monkeypatch.setattr(DV, "grade_divergence", lambda now, **k: {"grade": {}})
    monkeypatch.setattr(VD, "grade_night", lambda now: (_ for _ in ()).throw(RuntimeError("boom")))
    assert NG.main([]) == 0                                                   # a raising grade never moves the exit code
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["gajjala_vol_dried"] == {"error": "grade: RuntimeError"} and out["errors"] == []
    monkeypatch.delattr(PKG, "vol_dried")                                     # the module cannot be imported at all
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala.vol_dried", None)
    assert NG.main([]) == 0                                                   # a broken import never moves the exit code
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["gajjala_vol_dried"] == {"error": "grade: ModuleNotFoundError"} and out["errors"] == []
    assert out["gajjala_divergence"] == {"grade": {}}                        # the 🧨 grade before it still lands


# ── count_block + the board ──────────────────────────────────────────────────────────────────────────────────────
def cdoc(i, state="dried_pushed", grade=None, d=S):
    doc = {"_id": f"GGD:{d.isoformat()}|S{i}|bull_flag", "date": d.isoformat(), "symbol": f"S{i}", "state": state}
    if grade is not None:
        doc["grade"] = dict(grade, version=grade.get("version", VD.GRADE_VERSION))
    return doc


def test_count_block_none_text():
    b = VD.count_block(fake_store(), S)
    assert b == {"mode": LIVE, "text": "💧 Volume dried: none in the last 10 sessions · UNMEASURED"}


def test_count_block_counts_and_the_recorded_split_only_when_it_differs():
    st = store_with(cdoc(1, grade={"triggered": True, "won": True, "stop_first": False}),
                    cdoc(2, grade={"triggered": False, "won": False, "stop_first": True}),
                    cdoc(3, state="dried_no_target"), cdoc(4, state="dried_claimed"))
    b = VD.count_block(st, S)
    assert b["text"] == ("💧 3 recorded · 2 rang · 1 triggered · 1 hit +1R · 1 stop-first — last 10 sessions · "
                         "1 not graded yet · UNMEASURED")
    st2 = store_with(cdoc(1, grade={"triggered": True, "won": False, "stop_first": False}))
    assert VD.count_block(st2, S)["text"] == ("💧 1 rang · 1 triggered · 0 hit +1R · 0 stop-first — last 10 sessions"
                                              " · UNMEASURED")


def test_count_block_off_tail_and_the_R_multiple_from_the_constant(monkeypatch):
    monkeypatch.setattr(GC, "VOL_DRIED_PUSH_MODE", OFF)
    monkeypatch.setattr(GC, "LEDGER_R_MULT", 2.0)
    st = store_with(cdoc(1, state="dried_shadow", grade={"triggered": True, "won": True, "stop_first": False}))
    b = VD.count_block(st, S)
    assert b["mode"] == OFF and "hit +2R" in b["text"] and b["text"].endswith(VD.OFF_TAIL + " · UNMEASURED")
    assert b["text"].startswith("💧 1 recorded · 0 rang")
    assert VD.count_block(fake_store(), S)["text"] == ("💧 Volume dried: none in the last 10 sessions"
                                                       + VD.OFF_TAIL + " · UNMEASURED")


@pytest.mark.parametrize("junk", [float("nan"), "yes", 1, None])
def test_NEGATIVE_a_junk_stored_grade_never_counts(junk):
    st = store_with(cdoc(1, grade={"triggered": junk, "won": junk, "stop_first": junk}))
    b = VD.count_block(st, S)
    assert "0 triggered · 0 hit +1R · 0 stop-first" in b["text"]
    json.dumps(b, allow_nan=False)


def test_NEGATIVE_count_block_ignores_other_dates_and_a_read_fault_raises(monkeypatch):
    old = date(2026, 10, 1)
    st = store_with(cdoc(1, d=old))
    assert "none" in VD.count_block(st, S)["text"]
    with pytest.raises(Exception):
        VD.count_block(store_with(alerts=FakeColl(fail=True)), S)
    monkeypatch.setattr(st, "alerts_coll", lambda: None)
    with pytest.raises(RuntimeError):
        VD.count_block(st, S)


def test_the_board_serves_push_vol_dried_on_gg5_only(monkeypatch):
    now = at(10, 42)
    b = GT.build("bull_flag", now=now, store=fake_store(), owner=True)
    assert b["push_vol_dried"] == VD.count_block(fake_store(), S)
    json.dumps(b["push_vol_dried"], allow_nan=False)
    for v in (V.GGA, V.GG1):
        st = ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=v)
        assert "push_vol_dried" not in GT.build("bull_flag", now=now, store=st, owner=True), v
    monkeypatch.setattr(VD, "count_block", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    assert GT.build("bull_flag", now=now, store=fake_store(), owner=True)["push_vol_dried"] is None


def test_the_board_golden_carries_the_none_line():
    doc = json.loads((ROOT / "tests" / "fixtures" / "gajjala" / "gg5_board_2026_10_27.json").read_text("utf-8"))
    for mode in ("live", "shadow"):
        for k, b in doc[mode].items():
            assert b["push_vol_dried"] == {"mode": "live",
                                           "text": "💧 Volume dried: none in the last 10 sessions · UNMEASURED"}, k


# ── rules_line + the ℹ️ note ─────────────────────────────────────────────────────────────────────────────────────
def test_rules_line_is_built_from_the_constants_at_call_time(monkeypatch):
    line = VD.rules_line()
    assert "(gajjala_vol_dried, mode live)" in line and "at most half the run-up" in line
    assert "1,000,000-share" in line and "hit +1R" in line and "20:15 ET" in line and "from 09:45 ET" in line
    assert "04:00–20:00 ET" in line and "09:30–09:45" in line and line.endswith("UNMEASURED — a description, not an entry.")
    monkeypatch.setattr(GC, "K3_VOL_FRAC", 0.7)
    monkeypatch.setattr(GC, "K11_MIN_SESSION_VOLUME", 2_500_000)
    monkeypatch.setattr(GC, "VOL_DRIED_PUSH_MODE", OFF)
    line = VD.rules_line()
    assert "at most 70% of the run-up" in line and "2,500,000-share" in line and "mode off" in line
    assert "b" + "ounce" not in line.lower()


def test_the_rules_note_carries_the_line_after_the_fade_cross_clause(monkeypatch):
    from supply_demand import rules_info as RI
    note = RI._gajjala_section()["note"]
    fade = AL.fade_cross_rules_line()
    assert VD.rules_line() in note and note.index(fade) < note.index(VD.rules_line())
    monkeypatch.setattr(VD, "rules_line", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    assert RI._gg_vol_dried_clause() == ""
    assert "💧 Armed, volume dried" not in RI._gajjala_section()["note"]


# ── the count script (UPPER bound) ──────────────────────────────────────────────────────────────────────────────
def test_the_count_script_uses_ready_since_on_each_prefix(monkeypatch):
    import scripts.gajjala_vol_dried_count as C
    assert "UPPER bound" in C.HEADER and "EM.ready_since(dict(doc, state_path=path[:i + 1]))" in inspect.getsource(C.turns)
    doc = {"state_path": [entry(at(9, 36)), entry(at(9, 41), kind="building"), entry(at(10, 31)),
                          entry(at(10, 36), state="aplus", kind=None)],
           "push": {"at": PT._utc(at(10, 31)).isoformat()}}
    assert C.turns(doc) == [PT._utc(at(9, 36)), PT._utc(at(10, 31))]
    c = C.count_doc(doc, S)
    assert c == {"first_band": "muted", "would_ring": PT._utc(at(10, 31)), "same_pass": True}
    seen = []
    real = EM.ready_since
    monkeypatch.setattr(EM, "ready_since", lambda d: seen.append(len(d["state_path"])) or real(d))
    C.turns(doc)
    assert seen == [1, 2, 3, 4]


def test_NEGATIVE_the_count_script_drops_a_joined_first_entry_and_bands_the_clock():
    import scripts.gajjala_vol_dried_count as C
    assert C.count_doc({"state_path": [entry(at(10, 31))], "first_seen_mode": "joined"}, S)["first_band"] is None
    assert C.band(PT._utc(at(9, 0)), S) == "pre" and C.band(PT._utc(at(15, 59)), S) == "rth"
    assert C.band(PT._utc(at(16, 0)), S) == "after_close" and C.band(PT._utc(at(13, 0, d=HALF)), HALF) == "after_close"
    row = C.count_session([{"state_path": [entry(at(20, 1))]}, {"state_path": []}], S)
    assert row["first_arms"] == 1 and row["would_ring"] == 0 and row["bands"]["after_close"] == 1


def test_the_count_script_run_reads_only(monkeypatch):
    import scripts.gajjala_vol_dried_count as C
    st = fake_store()
    tracker(st, [entry(at(10, 31))])
    coll = st.coll(ST.POTENTIALS)
    before = coll.writes
    res = C.run(st, 8)
    assert res["header"] == C.HEADER and res["sessions"][S.isoformat()]["would_ring"] == 1
    assert coll.writes == before
    json.dumps(res, default=str)


# ── source guards ────────────────────────────────────────────────────────────────────────────────────────────────
def test_SOURCE_the_hook_is_its_own_try_never_errors_never_a_key_of_out():
    import ast
    src = inspect.getsource(RUN.run_pass)
    i = src.index("deps.vol_dried(")
    assert src.index("PT.run_pass(") < i < src.index("deps.fade_cross(")
    tree = ast.parse((ROOT / "chart_maps" / "gajjala" / "run.py").read_text(encoding="utf-8"))
    hooks = [n for n in ast.walk(tree) if isinstance(n, ast.If) and "deps.vol_dried is not None" in ast.unparse(n.test)]
    assert len(hooks) == 1
    test, body = ast.unparse(hooks[0].test), ast.unparse(hooks[0])
    assert "not push_dry" in test and "'tracked_today' in" in test
    assert "errors" not in body and "out[" not in body and isinstance(hooks[0].body[0], ast.Try)


def test_SOURCE_no_number_typed_in_the_engine():
    src = (ROOT / "chart_maps" / "gajjala" / "vol_dried.py").read_text(encoding="utf-8")
    for lit in ("1_000_000", "1000000", "0.5", "20:15", "09:45", "LEDGER_R_MULT = "):
        assert lit not in src, lit
    assert "b" + "ounce" not in src.lower()
    assert math.isfinite(GC.LEDGER_R_MULT)
