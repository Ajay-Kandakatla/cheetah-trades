"""✨ board_arrival — the arrivals push for 📈 Bonde and 🚀 Explosive Growth.

Ajay 2026-09-20: *"Default on for any change of todays features Bondes or
Potus or explosive growth or Earnings I wanna see all of them."*

The whole point of this kind is that it rings ONCE, for a name a board really
placed, and NEVER for the first cohort a ledger sees. So the negatives carry
the weight here: the first pass, a stale arrival, a `rejected` row, a name
that left and came back, a raise in transport, a closed day, and the six S/D
`skipped_*` counter names the /alerts page aggregates (a counter borrowing one
would silently move a number on a page he reads).
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from sepa import board_arrival as BA

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 21, 17, 42, tzinfo=ET)          # a Monday, the Bonde slot
LABOR_DAY = datetime(2026, 9, 7, 17, 42, tzinfo=ET)     # in market_hours.reminder.ALL_HOLIDAYS
NOW_UTC = NOW.astimezone(timezone.utc).isoformat()      # "2026-09-21T21:42:00+00:00"
# The baseline is stamped in the SAME clock the two ledgers write — UTC. The
# ET spelling of this moment is "2026-09-20T17:42:00-04:00", which sorts BELOW
# every same-day UTC ledger stamp; see test_a_ledger_stamp_from_the_1740_run_
# is_not_after_the_1742_baseline.
BASELINE = "2026-09-20T21:42:00+00:00"
ARRIVED = "2026-09-21T09:00:00+00:00"                   # strictly after BASELINE
OLD = "2026-09-19T09:00:00+00:00"                       # before it


# ─────────────────────────────────────────────────────────────── fakes
class Coll:
    """pymongo-shaped (copied from test_alerts_review_fixes_2026_09_14.Coll):
    `$setOnInsert` only on an insert, update_one reports upserted_id /
    matched_count, find by `_id $in`."""

    def __init__(self, docs=None):
        self.docs = dict(docs or {})
        self.calls = []

    def find_one(self, q, projection=None):
        self.calls.append("find_one")
        return self.docs.get(q["_id"])

    def find(self, q, projection=None):
        self.calls.append("find")
        for k in q["_id"]["$in"]:
            if k in self.docs:
                yield dict(self.docs[k])

    def update_one(self, q, u, upsert=False):
        self.calls.append("update_one")
        existed = q["_id"] in self.docs
        d = self.docs.setdefault(q["_id"], {"_id": q["_id"]})
        if not existed:
            d.update(u.get("$setOnInsert", {}))
        d.update(u.get("$set", {}))
        return SimpleNamespace(matched_count=1 if existed else 0,
                               upserted_id=None if existed else q["_id"])

    def delete_one(self, q):
        self.calls.append("delete_one")
        self.docs.pop(q["_id"], None)
        return SimpleNamespace(deleted_count=1)


def seeded(**docs) -> Coll:
    """A collection whose baseline is already stamped — i.e. NOT a first pass."""
    return Coll({BA.META_ID: {"_id": BA.META_ID, "tracking_since": BASELINE}, **docs})


class Sender:
    def __init__(self, result=None, raises=False):
        self.calls = []
        self.result = result if result is not None else {"sent": 1, "failed": 0, "total_targets": 1}
        self.raises = raises

    def send_to_user(self, email, payload, kind=None):
        self.calls.append((email, payload, kind))
        if self.raises:
            raise RuntimeError("transport down")
        return self.result


@pytest.fixture
def sender(monkeypatch):
    from push import sender as S
    spy = Sender()
    monkeypatch.setattr(S, "send_to_user", spy.send_to_user)
    return spy


@pytest.fixture(autouse=True)
def _no_status_write(monkeypatch):
    """Every test that is not ABOUT the status row stubs the write."""
    from supply_demand import alert_status as AS
    monkeypatch.setattr(AS, "record_result", lambda *a, **k: True)


@pytest.fixture(autouse=True)
def _no_mongo(monkeypatch):
    monkeypatch.setattr(BA, "_growth_db", lambda: None)


# ─────────────────────────────────────────────────────────────── fixtures
VERDICT = "MEASURED 2026-09-13 AND THIS BOARD’S OWN THESIS IS INVERTED"


@pytest.fixture(autouse=True)
def _served_verdict(monkeypatch):
    """The verdict is read from the SERVING module, never retyped in the push."""
    from sepa import bonde
    monkeypatch.setattr(bonde, "measured_verdict",
                        lambda: {"headline": VERDICT, "body": "x"})


def brow(sym, **kw):
    r = {"symbol": sym, "tier": "explosive", "growth_yoy_pct": 131.4,
         "prior_yoy_pct": 88.0, "accelerating": True, "pivot": None,
         "period_ok": True, "is_new": True, "first_seen": ARRIVED}
    r.update(kw)
    return r


def bpayload(**sections):
    base = {k: [] for k in ("pivot", "explosive", "strong", "steady", "rejected")}
    base.update(sections)
    return {"sections": base}


def grow(sym, **kw):
    r = {"symbol": sym, "sales_growth_pct": 212.0, "q_eps_growth_pct": 140.0,
         "sales_prior_pct": 96.0, "warnings": []}
    r.update(kw)
    return r


def item(board, sym, first_seen=ARRIVED, **kw):
    maker = brow if board == "bonde" else grow
    return {"board": board, "symbol": sym, "first_seen": first_seen,
            "row": maker(sym, **kw)}


# ═══════════════════════════════════════════════════════════ positives
def test_a_bonde_arrival_rings_once_with_the_served_verdict(sender):
    coll = seeded()
    out = BA.run("bonde", now=NOW, coll=coll, items=[item("bonde", "ABCD")])

    assert out["first_pass"] is False
    assert (out["rows"], out["since_tracking"], out["fresh"]) == (1, 1, 1)
    assert (out["individual"], out["digest"]) == (1, 0)
    assert len(sender.calls) == 1
    email, payload, kind = sender.calls[0]
    assert email == BA.OWNER and kind == "board_arrival"
    assert payload["title"] == "✨ New on 📈 Bonde — ABCD (explosive · sales +131% YoY)"
    assert "arrived 2026-09-21" in payload["body"]
    assert VERDICT in payload["body"]
    assert "not a recommendation" in payload["body"]
    assert payload["tickers"] == ["ABCD"] and payload["ticker"] == "ABCD"
    assert payload["url"] == "/chart-maps?tab=bonde&symbol=ABCD"
    assert payload["kind"] == "board_arrival"
    assert payload["data"]["board"] == "bonde"
    assert payload["data"]["url"] == payload["url"]
    # the claim is a (board, symbol) key with no day in it
    assert "bonde|ABCD" in coll.docs
    assert coll.docs["bonde|ABCD"]["source"] == BA.SOURCE


def test_a_bonde_body_says_the_pivot_and_the_pair_mark():
    m = BA.message(item("bonde", "EFGH", pivot={"gap_pct": 9.1}, period_ok=False))
    assert "⚡ Episodic Pivot on the tape" in m["body"]
    assert BA.PAIR_WITHHELD in m["body"]
    assert "prior quarter +88%" in m["body"]
    assert "accelerating" in m["body"]

    m2 = BA.message(item("bonde", "EFGH", period_ok=None))
    assert BA.PAIR_UNVERIFIED in m2["body"]
    assert BA.PAIR_WITHHELD not in m2["body"]


def test_a_growth_arrival_carries_every_warning_verbatim_and_the_honesty_line(sender):
    warns = ["⛔ under the $2 price floor — the engine will refuse to buy it",
             "⛔ under the $700M cap floor"]
    coll = seeded()
    BA.run("growth", now=NOW, coll=coll,
           items=[item("growth", "WXYZ", warnings=warns)])
    _, payload, _ = sender.calls[0]
    assert payload["title"] == "✨ New on 🚀 Explosive Growth — WXYZ (sales +212%, qEPS +140%)"
    for w in warns:
        assert w in payload["body"]
    assert BA.NOT_BACKTESTED in payload["body"]
    assert "prior quarter sales +96%" in payload["body"]
    assert payload["url"] == "/chart-maps?tab=growth&symbol=WXYZ"
    assert "growth|WXYZ" in coll.docs


def test_bonde_rows_walk_pivot_then_the_tiers_and_dedupe_first_placement():
    payload = bpayload(
        pivot=[brow("PIV", tier=None, pivot={"gap_pct": 9.0})],
        explosive=[brow("PIV"), brow("EXP")],          # PIV placed twice — first wins
        strong=[brow("STR", tier="strong")],
        steady=[brow("STE", tier="steady")],
    )
    got = BA.bonde_rows(payload)
    assert [i["symbol"] for i in got] == ["PIV", "EXP", "STR", "STE"]
    assert got[0]["row"]["pivot"] == {"gap_pct": 9.0}   # the PIVOT row, not the explosive one
    assert all(i["board"] == "bonde" for i in got)


def test_six_arrivals_ring_four_singles_then_one_digest_in_body_order(sender):
    syms = ["AA", "BB", "CC", "DD", "EE", "FF"]
    coll = seeded()
    out = BA.run("bonde", now=NOW, coll=coll,
                 items=[item("bonde", s) for s in syms])
    assert (out["individual"], out["digest"]) == (BA.MAX_INDIVIDUAL, 2)
    assert len(sender.calls) == BA.MAX_INDIVIDUAL + 1
    singles = [c[1]["ticker"] for c in sender.calls[:BA.MAX_INDIVIDUAL]]
    assert singles == syms[:BA.MAX_INDIVIDUAL]
    dig = sender.calls[-1][1]
    assert dig["title"] == "✨ 2 new on 📈 Bonde"
    assert dig["tickers"] == ["EE", "FF"]
    assert dig["ticker"] is None
    assert dig["url"] == "/chart-maps?tab=bonde"
    assert dig["body"].startswith("EE (explosive), FF (explosive) · ")
    assert VERDICT in dig["body"]
    # the chips and the text can never disagree
    assert [t for t in dig["tickers"]] == [p.split(" (")[0] for p in
                                           dig["body"].split(" · ")[0].split(", ")]
    assert all(k in coll.docs for k in ("bonde|EE", "bonde|FF"))
    assert coll.docs["bonde|FF"]["digest"] is True


def test_a_growth_digest_tail_is_the_not_backtested_line(sender):
    syms = ["A1", "B2", "C3", "D4", "E5"]
    BA.run("growth", now=NOW, coll=seeded(), items=[item("growth", s) for s in syms])
    dig = sender.calls[-1][1]
    assert dig["title"] == "✨ 1 new on 🚀 Explosive Growth"
    assert dig["body"] == "E5 (sales +212%) · " + BA.NOT_BACKTESTED


def test_a_wet_pass_records_its_result_under_the_board_scoped_kind(monkeypatch, sender):
    from supply_demand import alert_status as AS
    seen = []
    monkeypatch.setattr(AS, "record_result",
                        lambda kind, res, now=None, **k: seen.append((kind, res)))
    out = BA.run("bonde", now=NOW, coll=seeded(), items=[item("bonde", "ABCD")])
    assert [k for k, _ in seen] == ["board_arrival:bonde"]
    assert seen[0][1] is out


def test_growth_rows_keep_served_order_and_read_first_seen_from_the_ledger():
    doc = {"rows": [grow("ZZ"), grow("AA"), grow("MM")]}
    got = BA.growth_rows(doc, new={"MM", "ZZ"},
                         seen={"ZZ": ARRIVED, "MM": OLD})
    assert [i["symbol"] for i in got] == ["ZZ", "MM"]        # served order, not sorted
    assert [i["first_seen"] for i in got] == [ARRIVED, OLD]
    assert BA.select(got, BASELINE) == [got[0]]              # only the one after the baseline


# ═══════════════════════════════════════════════════════════ negatives
def test_the_first_pass_stamps_the_baseline_and_sends_nothing(sender):
    coll = Coll()                                            # empty — never tracked before
    out = BA.run("bonde", now=NOW, coll=coll,
                 items=[item("bonde", "AAA"), item("bonde", "BBB", first_seen=OLD)])
    assert out["first_pass"] is True
    assert out["tracking_since"] == NOW_UTC
    assert (out["since_tracking"], out["fresh"], out["individual"], out["digest"]) == (0, 0, 0, 0)
    assert sender.calls == []
    assert coll.docs[BA.META_ID]["tracking_since"] == NOW_UTC
    assert [k for k in coll.docs if k != BA.META_ID] == []


def test_a_ledger_stamp_from_the_1740_run_is_not_after_the_1742_baseline(sender):
    """THE first-pass trap. `sepa.bonde show` runs at 17:40 ET and stamps
    `first_seen` in UTC — "2026-09-21T21:40:00+00:00". This pass starts two
    minutes LATER, at 17:42 ET. If the baseline were stamped in ET
    ("2026-09-21T17:42:00-04:00") the lexical compare in `select()` would read
    "21:40" as AFTER "17:42" and the very first run would push the whole
    board — every name the ledger has ever held."""
    ledger = "2026-09-21T21:40:00+00:00"                     # 17:40 ET, the show run
    coll = Coll()                                            # empty — the first pass
    out = BA.run("bonde", now=NOW, coll=coll,
                 items=[item("bonde", "AAA", first_seen=ledger)])

    assert out["tracking_since"] == NOW_UTC == "2026-09-21T21:42:00+00:00"
    assert ledger < out["tracking_since"]                     # the lexical compare, explicitly
    assert out["first_pass"] is True
    assert (out["since_tracking"], out["fresh"], out["individual"]) == (0, 0, 0)
    assert sender.calls == []
    assert [k for k in coll.docs if k != BA.META_ID] == []


def test_the_baseline_is_stamped_in_utc_not_the_et_wall_clock():
    assert BA.tracking_since(None, NOW) == NOW_UTC
    assert BA.tracking_since(None, NOW) != NOW.isoformat()
    assert BA.tracking_since(Coll(), NOW).endswith("+00:00")


def test_a_baseline_stored_in_another_offset_is_compared_in_utc(sender):
    """A `__meta__` doc written by an older build carries the ET spelling. It
    must still be read as the MOMENT it names, not as the string it is."""
    et_doc = Coll({BA.META_ID: {"_id": BA.META_ID,
                                "tracking_since": "2026-09-21T17:42:00-04:00"}})
    assert BA.tracking_since(et_doc, NOW) == NOW_UTC
    out = BA.run("bonde", now=NOW, coll=et_doc,
                 items=[item("bonde", "AAA", first_seen="2026-09-21T21:40:00+00:00")])
    assert (out["since_tracking"], out["individual"]) == (0, 0)
    assert sender.calls == []


def test_the_claim_doc_keeps_a_human_et_stamp_while_the_baseline_is_utc(sender):
    coll = seeded()
    BA.run("bonde", now=NOW, coll=coll, items=[item("bonde", "ABCD")])
    assert coll.docs["bonde|ABCD"]["at"] == NOW.isoformat()   # ET — nothing compares it
    assert coll.docs[BA.META_ID]["tracking_since"] == BASELINE


def test_the_baseline_is_written_once_and_a_later_pass_reads_it_back(sender):
    coll = Coll()
    BA.run("bonde", now=NOW, coll=coll, items=[])
    later = datetime(2026, 9, 22, 17, 42, tzinfo=ET)
    out = BA.run("bonde", now=later, coll=coll, items=[])
    assert out["first_pass"] is False
    assert out["tracking_since"] == NOW_UTC           # $setOnInsert, never refreshed


def test_an_arrival_at_or_before_tracking_since_never_pushes(sender):
    coll = seeded()
    out = BA.run("bonde", now=NOW, coll=coll,
                 items=[item("bonde", "OLD1", first_seen=OLD),
                        item("bonde", "SAME", first_seen=BASELINE)])   # strict >, so equal is out
    assert (out["rows"], out["since_tracking"], out["fresh"]) == (2, 0, 0)
    assert sender.calls == []
    assert [k for k in coll.docs if k != BA.META_ID] == []


def test_an_arrival_with_no_first_seen_stamp_never_pushes(sender):
    out = BA.run("bonde", now=NOW, coll=seeded(),
                 items=[item("bonde", "NOFS", first_seen=None)])
    assert out["since_tracking"] == 0 and sender.calls == []


def test_is_new_false_rows_never_push():
    payload = bpayload(explosive=[brow("NEWY"), brow("OLDY", is_new=False),
                                  brow("NOSTAMP", first_seen=None)])
    assert [i["symbol"] for i in BA.bonde_rows(payload)] == ["NEWY"]


def test_an_arrival_the_section_cap_pushed_off_the_board_never_rings():
    """DESIGNED, and the limitation is in the doc (2026-09-20).

    `bonde.board()` stamps `is_new` on the rows that SURVIVED the per-section
    cap, so a name that arrived into a full tier is counted in `n_new` but is
    not in `sections` — and this pass rings only what the board DRAWS. On a day
    where every arrival is capped out, `n_new` is non-zero and nothing rings.
    Reading the pre-cap `arrived` set instead would ring names his screen does
    not show; that is a Bonde-tab change and HIS call, so the behaviour is
    pinned here rather than quietly widened.
    """
    payload = bpayload(explosive=[brow("SHOWN")])
    payload["n_new"] = 3                      # three arrivals, one of them drawn
    assert [i["symbol"] for i in BA.bonde_rows(payload)] == ["SHOWN"]

    capped = bpayload()                        # every arrival capped off the board
    capped["n_new"] = 3
    assert BA.bonde_rows(capped) == []


def test_the_rejected_section_never_pushes():
    payload = bpayload(explosive=[brow("KEEP")],
                       rejected=[brow("REJ", is_new=True)])
    got = [i["symbol"] for i in BA.bonde_rows(payload)]
    assert got == ["KEEP"] and "REJ" not in got


def test_a_second_run_the_same_day_is_fresh_zero(sender):
    coll = seeded()
    first = BA.run("bonde", now=NOW, coll=coll, items=[item("bonde", "ABCD")])
    again = BA.run("bonde", now=NOW, coll=coll, items=[item("bonde", "ABCD")])
    assert first["fresh"] == 1 and again["fresh"] == 0
    assert again["since_tracking"] == 1                      # still a candidate, already rung
    assert len(sender.calls) == 1


def test_a_name_that_left_and_returned_is_never_rung_again(sender):
    """[C8] No TTL on the state, and the ledger's first_seen is $setOnInsert
    forever — so a return carries its ORIGINAL arrival date and is silent.
    Designed behaviour; the re-arrival window is his call."""
    coll = seeded()
    BA.run("bonde", now=NOW, coll=coll, items=[item("bonde", "GONE")])
    assert len(sender.calls) == 1
    months_later = datetime(2027, 3, 1, 17, 42, tzinfo=ET)
    out = BA.run("bonde", now=months_later, coll=coll,
                 items=[item("bonde", "GONE")])               # same first_seen, back on the board
    assert (out["since_tracking"], out["fresh"]) == (1, 0)
    assert len(sender.calls) == 1


def test_the_two_boards_keep_separate_claims(sender):
    coll = seeded()
    BA.run("bonde", now=NOW, coll=coll, items=[item("bonde", "DUAL")])
    out = BA.run("growth", now=NOW, coll=coll, items=[item("growth", "DUAL")])
    assert out["fresh"] == 1
    assert {"bonde|DUAL", "growth|DUAL"} <= set(coll.docs)


def test_a_transport_raise_releases_the_key(monkeypatch):
    from push import sender as S
    spy = Sender(raises=True)
    monkeypatch.setattr(S, "send_to_user", spy.send_to_user)
    coll = seeded()
    out = BA.run("bonde", now=NOW, coll=coll, items=[item("bonde", "BOOM")])
    assert out["individual"] == 0
    assert "bonde|BOOM" not in coll.docs                      # released, retried next pass


def test_a_non_terminal_send_releases_the_key(monkeypatch):
    from push import sender as S
    spy = Sender(result={"sent": 0, "failed": 1, "total_targets": 1})
    monkeypatch.setattr(S, "send_to_user", spy.send_to_user)
    coll = seeded()
    out = BA.run("bonde", now=NOW, coll=coll, items=[item("bonde", "SOFT")])
    assert out["individual"] == 0 and "bonde|SOFT" not in coll.docs


def test_nobody_targeted_is_terminal_and_keeps_the_key(monkeypatch):
    from push import sender as S
    spy = Sender(result={"sent": 0, "failed": 0, "total_targets": 0})
    monkeypatch.setattr(S, "send_to_user", spy.send_to_user)
    coll = seeded()
    out = BA.run("bonde", now=NOW, coll=coll, items=[item("bonde", "MUTE")])
    assert out["individual"] == 1 and "bonde|MUTE" in coll.docs


def test_a_digest_raise_releases_every_digest_key(monkeypatch):
    from push import sender as S
    calls = []

    def flaky(email, payload, kind=None):
        calls.append(payload)
        if payload.get("ticker") is None:                     # the digest
            raise RuntimeError("transport down")
        return {"sent": 1, "failed": 0, "total_targets": 1}

    monkeypatch.setattr(S, "send_to_user", flaky)
    coll = seeded()
    syms = ["AA", "BB", "CC", "DD", "EE", "FF"]
    out = BA.run("bonde", now=NOW, coll=coll, items=[item("bonde", s) for s in syms])
    assert out["individual"] == 4 and out["digest"] == 0
    assert "bonde|EE" not in coll.docs and "bonde|FF" not in coll.docs
    assert "bonde|AA" in coll.docs                            # the singles terminated, they keep


def test_a_dry_run_reads_state_but_writes_nothing(monkeypatch):
    from push import sender as S
    from supply_demand import alert_status as AS
    monkeypatch.setattr(S, "send_to_user",
                        lambda *a, **k: pytest.fail("a dry run must not send"))
    monkeypatch.setattr(AS, "record_result",
                        lambda *a, **k: pytest.fail("a dry run must not record"))
    coll = seeded(**{"bonde|RUNG": {"_id": "bonde|RUNG"}})
    out = BA.run("bonde", dry_run=True, now=NOW, coll=coll,
                 items=[item("bonde", "RUNG"), item("bonde", "NEW1")])
    assert out["dry_run"] is True
    assert (out["since_tracking"], out["fresh"]) == (2, 1)    # the rung key read as seen
    assert out["individual"] == 1 and out["digest"] == 0      # what a wet pass WOULD send
    assert "find" in coll.calls                               # the state READ happened
    assert set(coll.docs) == {BA.META_ID, "bonde|RUNG"}       # no new claim


def test_a_closed_day_is_dropped_by_the_sender_and_the_claim_released(monkeypatch):
    """The crontab wrapper exits first; this pins the SECOND line of defence —
    and that the permanent claim is RELEASED, so a holiday cannot mute a name
    forever on the strength of a push that never left the building."""
    from market_hours import gate
    from push import subs
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    monkeypatch.setattr(gate, "closed_reason", lambda now=None: "holiday 2026-09-07")
    monkeypatch.setattr(subs, "list_subscriptions",
                        lambda **k: pytest.fail("a closed day must not touch a device"))
    coll = seeded()
    out = BA.run("bonde", now=LABOR_DAY, coll=coll, items=[item("bonde", "SHUT")])
    assert out["individual"] == 0
    assert "bonde|SHUT" not in coll.docs                      # a drop is not a delivery


def test_a_skipped_result_is_never_terminal():
    assert BA._terminal({"sent": 0, "failed": 0, "total_targets": 0,
                         "skipped": "holiday 2026-09-07"}) is False
    assert BA._terminal({"sent": 0, "failed": 0, "total_targets": 0}) is True


def test_the_kind_is_registered_on_by_default_and_is_a_market_kind():
    from push import subs
    from market_hours import gate
    assert subs.default_prefs()[BA.KIND] is True
    assert subs.owner_prefs()[BA.KIND] is True
    assert BA.KIND in subs.OWNER_KEEP_SET
    assert BA.KIND not in subs.DISABLED_ALERT_KINDS
    assert BA.KIND in gate.MARKET_ALERT_KINDS
    assert BA.KIND not in gate.PERSONAL_KINDS
    assert gate.should_drop_kind(BA.KIND, LABOR_DAY) == "holiday 2026-09-07"
    assert gate.should_drop_kind(BA.KIND, NOW) is None        # a Monday delivers


def test_a_subscription_is_targeted_only_once_the_pref_is_True(monkeypatch):
    from push import subs

    class FakeSubs:
        def __init__(self, rows): self.rows = rows
        def find(self, q):
            def ok(r):
                for k, v in q.items():
                    if k == "kind":
                        continue
                    cur = r
                    for part in k.split("."):
                        cur = (cur or {}).get(part) if isinstance(cur, dict) else None
                    if cur != v:
                        return False
                return True
            return [r for r in self.rows if ok(r)]

    rows = [{"user_email": "a@x", "prefs": {BA.KIND: False}},
            {"user_email": "b@x", "prefs": {}},
            {"user_email": "c@x", "prefs": {BA.KIND: True}}]
    db = type("DB", (), {"push_subscriptions": FakeSubs(rows)})()
    monkeypatch.setattr(subs, "_get_db", lambda: db)
    monkeypatch.setattr(subs, "_backfill", lambda _db: None)
    got = subs.list_subscriptions(filter_kind=BA.KIND, honor_quiet_hours=False)
    assert [r["user_email"] for r in got] == ["c@x"]


SRC = Path(BA.__file__).read_text(encoding="utf-8")


def test_the_owner_and_the_spill_come_from_growth_alerts_and_the_source_has_no_at():
    from growth import alerts as GA
    assert BA.OWNER is GA.OWNER and BA.MAX_INDIVIDUAL == GA.MAX_INDIVIDUAL
    assert "@" not in SRC                                     # never the admin email in the tree


def test_no_surface_this_kind_writes_says_bounce():
    bodies = [BA.message(item("bonde", "AAA")), BA.message(item("growth", "BBB")),
              BA.digest_message("bonde", [item("bonde", "CC")]),
              BA.digest_message("growth", [item("growth", "DD")])]
    for m in bodies:
        assert "bounce" not in m["title"].lower()
        assert "bounce" not in m["body"].lower()


def test_the_module_never_writes_to_either_board_ledger():
    """It READS arrivals; the boards own their ledgers. Checked on the parsed
    tree, so the docstring may name `growth_seen` while the code may not."""
    import ast
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in ("bonde_seen", "growth_seen"), node.value
        if isinstance(node, ast.Attribute):
            assert node.attr not in ("record", "_record_seen"), node.attr
    assert "_record_seen" not in SRC
    # the growth ledger is reached by NAME (tracker.SEEN_COLL) and read-only
    assert "FS.first_seen_map(T.SEEN_COLL" in SRC


def test_the_summary_never_borrows_an_sd_skip_counter(sender):
    """[C11] Alerts.tsx sums these six over EVERY recorded pass — a counter
    named like one of them would silently move the S/D gate aggregate."""
    sd = {"skipped_room", "skipped_proximity", "skipped_direction",
          "skipped_knife", "skipped_mood", "skipped_floor"}
    wet = BA.run("bonde", now=NOW, coll=seeded(), items=[item("bonde", "ABCD")])
    dry = BA.run("growth", dry_run=True, now=NOW, coll=seeded(),
                 items=[item("growth", "WXYZ")])
    assert set(wet) & sd == set()
    assert set(dry) & sd == set()
    assert set(wet) == {"kind", "board", "ran", "date", "first_pass", "tracking_since",
                        "rows", "since_tracking", "fresh", "individual", "digest",
                        "claimed_elsewhere", "dry_run"}


def test_importing_the_module_never_loads_the_board_stack():
    """[C9] alert_status / rules_info import this module for SLOTS_ET; the S/D
    rules page must not drag in the SEPA board stack."""
    for name in ("from sepa import bonde", "from growth import tracker", "import sepa.bonde"):
        for line in SRC.splitlines():
            if line.startswith(name):
                pytest.fail("module-level board import: %r" % line)
    code = ("import sepa.board_arrival, sys; "
            "assert 'sepa.bonde' not in sys.modules, 'sepa.bonde'; "
            "assert 'growth.tracker' not in sys.modules, 'growth.tracker'")
    r = subprocess.run([sys.executable, "-c", code],
                       cwd=str(Path(BA.__file__).resolve().parents[1]),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_an_unknown_board_is_refused():
    with pytest.raises(ValueError):
        BA.run("pankaj", now=NOW, coll=seeded(), items=[])
    assert BA.main(["pankaj"]) == 2
    assert BA.main([]) == 2


def test_the_slots_are_the_crontab_minutes_in_one_place():
    assert BA.SLOTS_ET == {"bonde": "17:42", "growth": "08:08"}
    assert set(BA.BOARDS) == set(BA.SLOTS_ET) == set(BA.TAB_URL) == set(BA.LABEL)
