"""chart_maps/gajjala/store.py — the tab's Mongo storage (spec §3.1.6), against an in-memory collection.

`FakeColl` here is the stand-in the other Gajjala test files import (tests/conftest.py refuses a real MongoClient).
"""
from __future__ import annotations

import copy
import re
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST

S = date(2026, 10, 13)
NOW = datetime(2026, 10, 13, 14, 1, tzinfo=timezone.utc)


# ── in-memory collection ──────────────────────────────────────────────────────────────────────────────────────
def _get(doc, path):
    cur = doc
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None, False
        cur = cur[p]
    return cur, True


def _cmp(a, b):
    if isinstance(a, datetime) and isinstance(b, datetime):
        a = a if a.tzinfo else a.replace(tzinfo=timezone.utc)
        b = b if b.tzinfo else b.replace(tzinfo=timezone.utc)
    return a, b


def _match_val(v, cond, present) -> bool:
    if isinstance(cond, dict) and any(k.startswith("$") for k in cond):
        for op, arg in cond.items():
            if op == "$in" and v not in arg:
                return False
            if op == "$ne" and v == arg:
                return False
            if op == "$exists" and bool(present) != bool(arg):
                return False
            if op == "$lte":
                if v is None:
                    return False
                a, b = _cmp(v, arg)
                if not a <= b:
                    return False
            if op == "$gte":
                if v is None:
                    return False
                a, b = _cmp(v, arg)
                if not a >= b:
                    return False
        return True
    return v == cond


def match(doc, q) -> bool:
    for k, cond in (q or {}).items():
        if k == "$or":
            if not any(match(doc, sub) for sub in cond):
                return False
        elif k == "$and":
            if not all(match(doc, sub) for sub in cond):
                return False
        else:
            v, present = _get(doc, k)
            if not _match_val(v, cond, present):
                return False
    return True


def _set_path(doc, path, value):
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = copy.deepcopy(value)


class FakeColl:
    def __init__(self, docs=None, fail=False):
        self.docs = {d["_id"]: copy.deepcopy(d) for d in docs or []}
        self.indexes = []
        self.fail = fail
        self.writes = 0

    def _guard(self):
        if self.fail:
            raise RuntimeError("mongo down")

    def find(self, q=None, projection=None):
        self._guard()
        return [copy.deepcopy(d) for d in self.docs.values() if match(d, q or {})]

    def find_one(self, q=None, projection=None):
        self._guard()
        for d in self.docs.values():
            if match(d, q or {}):
                return copy.deepcopy(d)
        return None

    def distinct(self, field):
        self._guard()
        return sorted({d.get(field) for d in self.docs.values() if d.get(field) is not None})

    def _apply(self, doc, upd, inserting):
        for op, fields in upd.items():
            if op == "$set" or (op == "$setOnInsert" and inserting):
                for k, v in fields.items():
                    _set_path(doc, k, v)
            elif op == "$setOnInsert":
                continue
            elif op == "$inc":
                for k, v in fields.items():
                    cur, _ = _get(doc, k)
                    _set_path(doc, k, (cur or 0) + v)
            elif op == "$max":
                for k, v in fields.items():
                    cur, _ = _get(doc, k)
                    _set_path(doc, k, v if cur is None else max(cur, v))
            else:
                raise NotImplementedError(op)

    def update_one(self, q, upd, upsert=False):
        self._guard()
        self.writes += 1
        for d in self.docs.values():
            if match(d, q):
                self._apply(d, upd, False)
                return SimpleNamespace(upserted_id=None, matched_count=1)
        if not upsert:
            return SimpleNamespace(upserted_id=None, matched_count=0)
        new = {k: v for k, v in q.items() if not k.startswith("$") and not isinstance(v, dict)}
        self._apply(new, upd, True)
        self.docs[new["_id"]] = new
        return SimpleNamespace(upserted_id=new["_id"], matched_count=0)

    def replace_one(self, q, doc, upsert=False):
        self._guard()
        self.writes += 1
        self.docs[q["_id"]] = copy.deepcopy(dict(doc, _id=q["_id"]))

    def find_one_and_update(self, q, upd, upsert=False):
        self._guard()
        for d in self.docs.values():
            if match(d, q):
                before = copy.deepcopy(d)
                self._apply(d, upd, False)
                return before
        if upsert:
            from pymongo.errors import DuplicateKeyError
            if q.get("_id") in self.docs:
                raise DuplicateKeyError("dup")
            new = {"_id": q["_id"]}
            self._apply(new, upd, True)
            self.docs[new["_id"]] = new
        return None

    def create_index(self, spec, **kw):
        self.indexes.append((tuple(spec), kw))


def fake_store(**over) -> ST.GajjalaStore:
    colls = {n: FakeColl() for n in ST.ALL}
    colls.update(over)
    return ST.GajjalaStore(colls=colls)


def _row(sym, change=30.0, **kw):
    return dict({"symbol": sym, "price": 1.3, "prev_close": 1.0, "change_pct": change, "volume": 2e6}, **kw)


# ── tests ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_ensure_indexes_ttl_per_spec_and_idempotent():
    st = fake_store()
    st.ensure_indexes()
    st.ensure_indexes()
    ttl = {n: [kw.get("expireAfterSeconds") for spec, kw in st.coll(n).indexes if spec == (("at", 1),)]
           for n in ST.ALL}
    assert ttl[ST.READS][0] == GC.READS_TTL_DAYS * 86400 == 14 * 86400
    for n in (ST.SCAN, ST.AH_CARRY, ST.POST, ST.PASSES, ST.DAILY):
        assert ttl[n][0] == GC.LEDGER_TTL_DAYS * 86400 == 30 * 86400
    # WIDENED 2026-10-15 — 🧠 gajjala_potentials joins the KEPT ledgers (the study's data spine, HIS CALL P7)
    # WIDENED 2026-10-16 — 🏁 gajjala_ledger joins the kept ledgers
    # WIDENED 2026-10-16 (night): DECISIONS11 D4 — ⏪ gajjala_replay joins the kept ledgers (P21)
    for n in (ST.ALERTS, ST.HALTS, ST.STATE, ST.POTENTIALS, ST.LEDGER, ST.REPLAY):      # ledgers kept
        assert ttl[n] == []
    assert ST.POTENTIALS not in ST.TTL_DAYS and ST.LEDGER not in ST.TTL_DAYS
    assert ST.REPLAY not in ST.TTL_DAYS
    idx = [spec for spec, _kw in st.coll(ST.POTENTIALS).indexes]
    assert (("date", 1), ("symbol", 1)) in idx and (("symbol", 1), ("date", -1)) in idx


def test_record_qualifiers_returns_only_new_and_accumulates():
    st = fake_store()
    assert st.record_qualifiers(S, NOW, [_row("AAA"), _row("BBB")], "premarket") == {"AAA", "BBB"}
    later = NOW + timedelta(minutes=5)
    assert st.record_qualifiers(S, later, [_row("AAA", 80.0), _row("CCC")], "rth") == {"CCC"}
    doc = st.coll(ST.SCAN).docs["2026-10-13|AAA"]
    assert doc["n_passes"] == 2 and doc["max_change_pct"] == 80.0
    assert doc["sessions"] == {"premarket": True, "rth": True}
    assert doc["first_qualified_at"] == NOW and doc["last_qualified_at"] == later
    assert doc["date"] == "2026-10-13" and doc["symbol"] == "AAA" and doc["at"] == later


def test_NEGATIVE_max_change_never_decreases():
    st = fake_store()
    st.record_qualifiers(S, NOW, [_row("AAA", 90.0)], "rth")
    st.record_qualifiers(S, NOW, [_row("AAA", 30.0)], "rth")
    assert st.coll(ST.SCAN).docs["2026-10-13|AAA"]["max_change_pct"] == 90.0


def test_split_checks_and_held_names_excluded_from_scan_docs():
    st = fake_store()
    st.record_qualifiers(S, NOW, [_row("AAA")], "rth")
    st.set_split_check(S, "AAA", "ok", now=NOW)
    st.set_split_check(S, "RSPL", "held", now=NOW, held=True)
    assert st.split_checks(S) == {"AAA": "ok", "RSPL": "held"}
    assert st.qualified_symbols(S) == {"AAA"}


def test_replace_ah_carry_replaces_wholesale():
    st = fake_store()
    st.replace_ah_carry(S, NOW, [_row("AAA", ah_move_pct=12.0, day_c=1.0), _row("BBB", ah_move_pct=11.0, day_c=2.0)])
    st.replace_ah_carry(S, NOW + timedelta(hours=1), [_row("BBB", ah_move_pct=15.0, day_c=2.0)])
    doc = st.ah_carry(S)
    assert set(doc["names"]) == {"BBB"}
    assert doc["names"]["BBB"] == {"ah_move_pct": 15.0, "ah_last": 1.3, "reg_close": 2.0}
    assert doc["pass_at"] == NOW + timedelta(hours=1)


def test_NEGATIVE_ah_carry_missing_is_none():
    assert fake_store().ah_carry(S) is None


def test_record_pass_writes_the_pass_and_latest():
    st = fake_store()
    st.record_pass(S, NOW, {"status": "ok", "counts": {"rows": 3}})
    # WIDENED 2026-10-15 — 🔄 scan on open (AMENDMENTS5 A10): a cron pass also moves the cron-only "latest_cron" pointer
    assert set(st.coll(ST.PASSES).docs) == {"2026-10-13|10:01", "latest", "latest_cron"}
    assert st.latest_cron_pass()["pass_id"] == "2026-10-13|10:01"
    assert st.latest_pass()["pass_id"] == "2026-10-13|10:01"
    assert [p["_id"] for p in st.passes(S)] == ["2026-10-13|10:01"]


class _ProjSpy(FakeColl):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.finds = []

    def find(self, q=None, projection=None):
        self.finds.append((q, projection))
        return super().find(q, projection)


def test_recent_passes_reads_only_the_window_projected_and_never_latest():
    """🧠 2026-10-15 D9 join rule: the previous-pass read is a windowed, projected find (finding LOW 5)."""
    spy = _ProjSpy()
    st = fake_store(**{ST.PASSES: spy})
    for m in (41, 51, 56):
        st.record_pass(S, NOW.replace(minute=m) - timedelta(hours=1), {"status": "ok", "potential": {"pushed": 0}})
    st.record_pass(S, NOW, {"status": "ok"})
    docs = st.recent_passes(S, NOW - timedelta(minutes=10), NOW - timedelta(minutes=4))
    assert sorted(d["_id"] for d in docs) == ["2026-10-13|09:51", "2026-10-13|09:56"]
    q, proj = spy.finds[-1]
    assert proj == {"at": 1, "potential": 1} and q["_id"] == {"$ne": "latest"} and q["date"] == "2026-10-13"


def test_NEGATIVE_recent_passes_is_none_on_a_read_fault_and_empty_when_none_on_file():
    assert fake_store(**{ST.PASSES: FakeColl(fail=True)}).recent_passes(S, NOW - timedelta(minutes=10), NOW) is None
    assert fake_store().recent_passes(S, NOW - timedelta(minutes=10), NOW) == []
    st = fake_store()
    st.record_pass(S, NOW - timedelta(hours=3), {"status": "ok", "potential": {}})
    assert st.recent_passes(S, NOW - timedelta(minutes=10), NOW) == []          # outside the window
    assert st.recent_passes(date(2026, 10, 12), NOW - timedelta(hours=4), NOW) == []   # another session


def test_reads_post_daily_halts_roundtrip():
    st = fake_store()
    st.upsert_read(S, "aaa", {"setups": {"bull_flag": {"state": "forming"}}}, now=NOW)
    assert st.get_read(S, "AAA")["setups"]["bull_flag"]["state"] == "forming"
    assert [r["symbol"] for r in st.reads(S)] == ["AAA"]
    st.upsert_post(S, "AAA", {"close_pos": 0.9}, now=NOW)
    assert st.post_docs(S)[0]["close_pos"] == 0.9
    st.upsert_daily(S, "AAA", {"float": {"shares": 3.1e6}}, now=NOW)
    assert st.get_daily(S, "AAA")["float"]["shares"] == 3.1e6
    st.upsert_halt(S, "AAA", {"n_halts": 2, "source": "live"})
    st.upsert_halt(date(2026, 10, 9), "AAA", {"n_halts": 1, "source": "history"})
    assert st.halt_dates("aaa") == {"2026-10-13", "2026-10-09"}
    assert st.halt_sessions() == {"2026-10-13", "2026-10-09"}


def test_lease_claim_then_held_then_released_then_min_gap():
    st = fake_store()
    # WIDENED 2026-10-15 — 🔄 scan on open: claim_lease returns a LeaseClaim (truthy), releases carry the holder's token
    c = st.claim_lease(NOW)
    assert bool(c) and c.why == "claimed"
    held = st.claim_lease(NOW + timedelta(seconds=10))
    assert not held and held.why == "held"                               # held
    st.release_lease(NOW + timedelta(seconds=60), c.token)
    gap = st.claim_lease(NOW + timedelta(seconds=GC.LEASE_MIN_GAP_SEC - 1))
    assert not gap and gap.why == "gap"                                  # inside the min gap
    assert bool(st.claim_lease(NOW + timedelta(seconds=GC.LEASE_MIN_GAP_SEC)))


def test_NEGATIVE_a_stuck_lease_expires_after_lease_sec():
    st = fake_store()
    # WIDENED 2026-10-15 — 🔄 scan on open: claim_lease returns a LeaseClaim (truthy), releases carry the holder's token
    assert bool(st.claim_lease(NOW))
    assert bool(st.claim_lease(NOW + timedelta(seconds=GC.LEASE_SEC)))


def test_types_map_roundtrip():
    st = fake_store()
    assert st.types_map() == {}
    st.set_types_map({"as_of": "2026-10-13", "pairs": [["AAA", "CS"]]})
    assert st.types_map()["pairs"] == [["AAA", "CS"]]


def test_NEGATIVE_no_mongo_is_the_documented_none_path():
    st = ST.GajjalaStore(colls={n: None for n in ST.ALL})
    st.ensure_indexes()
    assert st.record_qualifiers(S, NOW, [_row("AAA")], "rth") == {"AAA"}
    st.replace_ah_carry(S, NOW, [_row("AAA")])
    assert st.ah_carry(S) is None and st.reads(S) == [] and st.latest_pass() is None
    assert st.get_state("lease") == {} and st.halt_sessions() == set()
    # WIDENED 2026-10-15 — 🔄 scan on open: claim_lease returns a LeaseClaim (truthy), releases carry the holder's token
    c = st.claim_lease(NOW)
    assert c.ok and c.why == "no_store"                                  # the documented no-mongo answer


def test_NEGATIVE_a_failing_collection_never_raises():
    st = fake_store(**{n: FakeColl(fail=True) for n in ST.ALL})
    st.ensure_indexes()
    assert st.record_qualifiers(S, NOW, [_row("AAA")], "rth") == {"AAA"}
    st.set_split_check(S, "AAA", "ok")
    st.replace_ah_carry(S, NOW, [_row("AAA")])
    st.record_pass(S, NOW, {"status": "ok"})
    assert st.reads(S) == [] and st.ah_carry(S) is None and st.split_checks(S) == {}
    # WIDENED 2026-10-15 — 🔄 scan on open: claim_lease returns a LeaseClaim (truthy), releases carry the holder's token
    c = st.claim_lease(NOW)
    assert not c and c.why == "error"


def test_module_level_functions_delegate_to_the_default_store(monkeypatch):
    fake = fake_store()
    monkeypatch.setattr(ST, "_DEFAULT", fake)
    ST.replace_ah_carry(S, NOW, [_row("AAA", ah_move_pct=12.0, day_c=1.0)])
    assert set(ST.ah_carry(S)["names"]) == {"AAA"}
    assert ST.coll(ST.SCAN) is fake.coll(ST.SCAN)


def test_key_shape():
    assert ST.key(S, "brk-b") == "2026-10-13|BRK-B"
    assert ST.key("2026-10-13", "AAA") == "2026-10-13|AAA"


@pytest.mark.parametrize("mod", ["store", "scanner", "bars", "constants"])
def test_NEGATIVE_no_gate_modules_imported(mod):
    """Not another board's gates: the data spine imports price / calendar / bar engines only."""
    import ast
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "chart_maps" / "gajjala" / f"{mod}.py").read_text()
    banned = ("sepa.scan", "sepa.trend", "sepa.vcp", "sepa.bonde", "bonde", "sepa.api", "sepa.candidates")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
            for n in names:
                assert not any(n == b or n.startswith(b + ".") for b in banned), (mod, n)
    assert "is_candidate" not in src and "Minervini" not in src and "Bonde" not in src



# ── 🧠 gajjala_potentials (2026-10-15) — guarded writes only ─────────────────────────────────────────────────────────
PID = "2026-10-13|AAA|bull_flag"


def _pot_store():
    st = fake_store()
    assert st.upsert_potential(PID, {"date": "2026-10-13", "symbol": "AAA", "setup": "bull_flag"},
                               {"last": {"state": "forming"}, "at": NOW})
    return st


def test_potential_key_and_reads():
    st = _pot_store()
    assert ST.potential_key(S, "aaa", "bull_flag") == PID
    assert st.get_potential(S, "AAA", "bull_flag")["symbol"] == "AAA"
    assert [d["_id"] for d in st.potentials(S)] == [PID] and st.count_potentials(S) == 1
    assert [d["_id"] for d in st.potential_docs_for_symbol("aaa")] == [PID]
    assert st.count_potentials(date(2026, 10, 12)) == 0


def test_claim_is_claimed_then_taken_and_error_on_a_fault():
    st = _pot_store()
    assert st.claim_potential_push(PID, {"state": "claimed"}) == "claimed"
    assert st.claim_potential_push(PID, {"state": "claimed", "at_et": "10:06"}) == "taken"
    assert st.get_potential(S, "AAA", "bull_flag")["push"] == {"state": "claimed"}
    assert st.claim_potential_push("2026-10-13|ZZZ|bull_flag", {"state": "claimed"}) == "taken"   # no doc
    assert fake_store(**{ST.POTENTIALS: FakeColl(fail=True)}).claim_potential_push(PID, {}) == "error"
    assert ST.GajjalaStore(colls={n: None for n in ST.ALL}).claim_potential_push(PID, {}) == "error"


def test_NEGATIVE_hold_never_lands_on_a_claimed_doc():
    st = _pot_store()
    assert st.hold_potential(PID, [{"at_et": "09:36", "reason": "muted"}]) is True
    st.claim_potential_push(PID, {"state": "claimed"})
    before = copy.deepcopy(st.coll(ST.POTENTIALS).docs[PID])
    assert st.hold_potential(PID, [{"at_et": "09:41", "reason": "stale_tape"}]) is False
    assert st.coll(ST.POTENTIALS).docs[PID] == before


def test_settle_sets_the_dotted_push_fields_only():
    st = _pot_store()
    st.claim_potential_push(PID, {"state": "claimed", "at": "x", "kind_at_push": "armed"})
    assert st.settle_potential_push(PID, {"state": "pushed", "result": {"sent": 1}, "at_et": "10:06",
                                          "kind_at_push": "IGNORED", "at": "IGNORED"}) is True
    push = st.get_potential(S, "AAA", "bull_flag")["push"]
    assert push == {"state": "pushed", "at": "x", "kind_at_push": "armed", "result": {"sent": 1}, "at_et": "10:06"}


def test_NEGATIVE_settle_never_creates_a_push_on_an_unclaimed_doc():
    st = _pot_store()
    assert st.settle_potential_push(PID, {"state": "pushed"}) is False
    assert "push" not in st.get_potential(S, "AAA", "bull_flag")


def test_NEGATIVE_graveyard_marks_once():
    st = _pot_store()
    assert st.mark_potential_graveyard(PID, S, [{"state": "graveyard"}]) is True
    assert st.mark_potential_graveyard(PID, date(2026, 10, 14), [{"state": "graveyard"}, {"state": "graveyard"}]) \
        is False
    doc = st.get_potential(S, "AAA", "bull_flag")
    assert doc["graveyard_on"] == "2026-10-13" and doc["state_path"] == [{"state": "graveyard"}]


def test_NEGATIVE_upsert_refuses_a_clash_or_a_guarded_field():
    st = fake_store()
    assert st.upsert_potential(PID, {"a": 1}, {"a": 2}) is False
    for banned in ("push", "held", "graveyard_on"):
        assert st.upsert_potential(PID, {}, {banned: 1}) is False
        assert st.upsert_potential(PID, {banned: 1}, {"x": 1}) is False
    assert st.coll(ST.POTENTIALS).docs == {}


def test_NEGATIVE_there_is_no_whole_doc_potential_writer():
    assert not hasattr(ST.GajjalaStore, "put_potential") and not hasattr(ST, "put_potential")
    import inspect
    for name in ("upsert_potential", "hold_potential", "claim_potential_push", "settle_potential_push",
                 "mark_potential_graveyard", "_guarded_set"):
        assert "replace_one" not in inspect.getsource(getattr(ST.GajjalaStore, name)), name


def test_NEGATIVE_a_failing_potentials_coll_answers_its_soft_values():
    st = fake_store(**{ST.POTENTIALS: FakeColl(fail=True)})
    assert st.potentials(S) is None and st.get_potential(S, "AAA", "bull_flag") is None   # None, not []: 2026-10-15
    assert st.count_potentials(S) == 0 and st.potential_docs_for_symbol("AAA") == []
    assert st.upsert_potential(PID, {"a": 1}, {"b": 2}) is False
    assert st.hold_potential(PID, []) is False and st.settle_potential_push(PID, {"state": "x"}) is False
    assert st.mark_potential_graveyard(PID, S, []) is False and st.claim_potential_push(PID, {}) == "error"


def test_potential_module_delegates(monkeypatch):
    fake = _pot_store()
    monkeypatch.setattr(ST, "_DEFAULT", fake)
    assert ST.count_potentials(S) == 1 and ST.get_potential(S, "AAA", "bull_flag")["_id"] == PID


# ── final critic 2026-10-15: an unreadable tracker is not an empty one ───────────────────────────────────────────
def test_potentials_is_an_empty_list_when_nothing_is_on_file_and_None_on_a_read_fault():
    assert fake_store().potentials(S) == []
    assert fake_store(**{ST.POTENTIALS: FakeColl(fail=True)}).potentials(S) is None
    dead = ST.GajjalaStore(colls={n: None for n in ST.ALL})
    assert dead.potentials(S) is None and dead.count_potentials(S) == 0


def test_NEGATIVE_the_claim_never_lands_on_a_joined_doc_and_still_lands_on_a_normal_or_pre_build_doc():
    """D9's second guard: `first_seen_mode: joined` is never claimable even with `push` absent; a `normal` doc and a doc
    from before this build (no `first_seen_mode` at all) claim as before."""
    from chart_maps.gajjala import potential as PT
    assert ST.JOINED_MODE == PT.FIRST_SEEN_MODES[1]
    joined = {"_id": "2026-10-13|JJJ|bull_flag", "date": S.isoformat(), "symbol": "JJJ", "setup": "bull_flag",
              "first_seen_mode": "joined"}
    normal = {"_id": "2026-10-13|NNN|bull_flag", "date": S.isoformat(), "symbol": "NNN", "setup": "bull_flag",
              "first_seen_mode": "normal"}
    old = {"_id": "2026-10-13|OOO|bull_flag", "date": S.isoformat(), "symbol": "OOO", "setup": "bull_flag"}
    st = fake_store(**{ST.POTENTIALS: FakeColl([joined, normal, old])})
    assert st.claim_potential_push(joined["_id"], {"state": "claimed"}) == "taken"
    assert "push" not in st.get_potential(S, "JJJ", "bull_flag")
    assert st.claim_potential_push(normal["_id"], {"state": "claimed"}) == "claimed"
    assert st.claim_potential_push(old["_id"], {"state": "claimed"}) == "claimed"
    assert st.claim_potential_push(joined["_id"], {"state": "claimed"}) == "taken"       # still, on a second try


# ── 🔄 the split lease (2026-10-15 — DECISIONS5 C1, AMENDMENTS5 A5–A10) ──────────────────────────────────────────────
# Ajay 2026-10-15: "When ever I open Gajjala's intiate a new scan of stocks.  In that moment and if there are any
# enterable stocks on the top which I see in potential i guess". An open never makes a cron tick skip or refuse.
CRON, OD = ST.LEASE_CRON, ST.LEASE_ON_DEMAND


def _ago(s):
    return NOW - timedelta(seconds=s)


def _lease(st):
    return st.coll(ST.STATE).docs.get(ST.LEASE_ID)


def _put_lease(st, **doc):
    st.coll(ST.STATE).docs[ST.LEASE_ID] = dict(doc, _id=ST.LEASE_ID)


def test_a_cron_claim_carries_its_token_holder_and_the_tick_clock():
    st = fake_store()
    c = st.claim_lease(NOW)
    assert c.ok and c.why == "claimed" and isinstance(c.token, str) and len(c.token) == 32
    d = _lease(st)
    assert d["held_by"] == CRON and d["token"] == c.token and d["status"] == "running"
    assert d["claimed_at"] == d["started_at"] == d["last_cron_started_at"] == NOW
    assert "od_started_at" not in d


def test_A6_a_cron_claim_after_a_wait_stamps_the_gap_with_the_tick_clock():
    st = fake_store()
    later = NOW + timedelta(seconds=GC.CRON_WAIT_ON_DEMAND_SEC)
    c = st.claim_lease(later, source=CRON, cron_start=NOW)
    d = _lease(st)
    assert c.ok and d["claimed_at"] == later and d["last_cron_started_at"] == d["started_at"] == NOW


def test_C1_an_on_open_claim_skips_the_cron_gap_and_never_moves_it():
    st = fake_store()
    c = st.claim_lease(NOW)
    st.release_lease(NOW + timedelta(seconds=30), c.token)
    o = st.claim_lease(NOW + timedelta(seconds=60), source=OD)          # inside the 240 s cron gap
    d = _lease(st)
    assert o.ok and o.why == "claimed" and o.token != c.token
    assert d["held_by"] == OD and d["od_started_at"] == NOW + timedelta(seconds=60)
    assert d["last_cron_started_at"] == NOW                               # C1: the cron gap clock unchanged
    assert d["started_at"] == NOW                                         # NEGATIVE A9: started_at never written by an open


def test_NEGATIVE_A9_an_on_open_claim_on_a_fresh_store_never_writes_started_at():
    st = fake_store()
    assert st.claim_lease(NOW, source=OD).ok
    assert "started_at" not in _lease(st) and "last_cron_started_at" not in _lease(st)


@pytest.mark.parametrize("holder,source,why", [(CRON, OD, "held"), (OD, OD, "held"), (OD, CRON, "held_on_demand"),
                                               (CRON, CRON, "held")])
def test_NEGATIVE_a_held_lease_refuses_with_its_reason(holder, source, why):
    st = fake_store()
    first = st.claim_lease(_ago(300), source=holder)
    assert first.ok
    _lease(st)["claimed_at"] = _ago(10)                                   # held, fresh
    r = st.claim_lease(NOW, source=source)
    assert not r and r.why == why and r.held_by == holder and r.token is None
    assert _lease(st)["token"] == first.token                             # nothing overwritten


def test_NEGATIVE_a_cron_inside_its_gap_meeting_an_on_open_holder_is_gap_never_a_wait():
    st = fake_store()
    _put_lease(st, status="running", held_by=OD, token="od", claimed_at=_ago(5), last_cron_started_at=_ago(100))
    r = st.claim_lease(NOW, source=CRON)
    assert not r and r.why == "gap"
    assert not st.claim_lease(NOW, source=CRON, take_over=True)           # a take-over never skips the gap


def test_take_over_replaces_an_on_open_holder_and_its_release_then_does_nothing():
    st = fake_store()
    o = st.claim_lease(_ago(20), source=OD)
    t = st.claim_lease(NOW, source=CRON, take_over=True)
    assert t.ok and t.why == "taken_over" and t.token != o.token
    d = _lease(st)
    assert d["held_by"] == CRON and d["token"] == t.token and d["last_cron_started_at"] == NOW
    assert st.release_lease(NOW + timedelta(seconds=1), o.token) is False      # NEGATIVE: the old holder frees nothing
    assert _lease(st)["status"] == "running" and _lease(st)["held_by"] == CRON
    assert st.release_lease(NOW + timedelta(seconds=2), t.token) is True
    assert _lease(st)["status"] == "done"


def test_NEGATIVE_take_over_never_takes_a_cron_holder():
    st = fake_store()
    _put_lease(st, status="running", held_by=CRON, token="c", claimed_at=_ago(5), last_cron_started_at=_ago(300))
    r = st.claim_lease(NOW, source=CRON, take_over=True)
    assert not r and r.why == "held" and _lease(st)["token"] == "c"


def test_take_over_of_a_free_lease_is_a_plain_claim():
    st = fake_store()
    assert st.claim_lease(NOW, source=CRON, take_over=True).why == "claimed"


def test_NEGATIVE_a_tokenless_release_never_frees_a_tokened_lease():
    st = fake_store()
    c = st.claim_lease(NOW)
    assert st.release_lease(NOW + timedelta(seconds=1)) is False
    assert st.release_lease(NOW + timedelta(seconds=1), "not-the-token") is False
    assert _lease(st)["status"] == "running" and _lease(st)["token"] == c.token
    _put_lease(st, status="running", claimed_at=NOW, started_at=NOW)     # a legacy (pre-split) lease has no token
    assert st.release_lease(NOW + timedelta(seconds=1)) is True and _lease(st)["status"] == "done"


@pytest.mark.parametrize("source", [CRON, OD])
def test_a_stale_lease_frees_itself_for_both_sources(source):
    st = fake_store()
    _put_lease(st, status="running", held_by=OD if source == CRON else CRON, token="x",
               claimed_at=_ago(GC.LEASE_SEC), last_cron_started_at=_ago(GC.LEASE_SEC))
    c = st.claim_lease(NOW, source=source)
    assert c.ok and c.why == "claimed" and _lease(st)["held_by"] == source


def test_legacy_medical_shape_lease_gaps_on_its_started_at():
    st = fake_store()
    _put_lease(st, status="done", claimed_at=_ago(100), started_at=_ago(100), pid=1)
    r = st.claim_lease(NOW)
    assert not r and r.why == "gap"
    assert st.claim_lease(NOW, source=OD).ok                              # an open needs only "not held"
    st2 = fake_store()
    _put_lease(st2, status="done", claimed_at=_ago(GC.LEASE_MIN_GAP_SEC), started_at=_ago(GC.LEASE_MIN_GAP_SEC))
    assert st2.claim_lease(NOW).why == "claimed"


@pytest.mark.parametrize("source", [CRON, OD])
def test_NEGATIVE_a_legacy_running_fresh_lease_is_held_for_both(source):
    st = fake_store()
    _put_lease(st, status="running", claimed_at=_ago(10), started_at=_ago(10), pid=1)
    r = st.claim_lease(NOW, source=source)
    assert not r and r.why in ("held", "gap") and r.held_by in (CRON, None)
    if source == OD:
        assert r.why == "held" and r.held_by == CRON


def test_lease_state_reads_held_holder_and_stamps():
    st = fake_store()
    assert st.lease_state(NOW) == {"held": False, "held_by": None, "holder_started_at": None, "claimed_at": None,
                                   "started_at": None, "od_started_at": None, "last_cron_started_at": None,
                                   "status": None, "done_at": None}      # WIDENED 2026-10-16: status + done_at (reuse)
    st.claim_lease(_ago(10), source=OD)
    s = st.lease_state(NOW)
    assert s["held"] is True and s["held_by"] == OD and s["holder_started_at"] == _ago(10) == s["od_started_at"]
    assert s["started_at"] is None
    s = st.lease_state(NOW + timedelta(seconds=GC.LEASE_SEC))             # NEGATIVE: a stale holder is not "held"
    assert s["held"] is False and s["holder_started_at"] is None
    c = fake_store()
    c.claim_lease(NOW)
    s = c.lease_state(NOW + timedelta(seconds=1))
    assert s["held"] and s["held_by"] == CRON and s["holder_started_at"] == NOW == s["last_cron_started_at"]


def test_NEGATIVE_lease_state_is_empty_on_no_handle_or_a_read_fault():
    assert ST.GajjalaStore(colls={n: None for n in ST.ALL}).lease_state(NOW) == {}
    assert fake_store(**{ST.STATE: FakeColl(fail=True)}).lease_state(NOW) == {}


def test_A5_naive_mongo_stamps_never_break_a_comparison():
    """The live MongoClient is not tz-aware: stamps come back NAIVE (UTC). Every read-back goes through _utc first."""
    naive = lambda dt: dt.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: E731
    st = fake_store()
    _put_lease(st, status="running", held_by=OD, token="od", claimed_at=naive(_ago(5)),
               od_started_at=naive(_ago(5)), last_cron_started_at=naive(_ago(300)))
    r = st.claim_lease(NOW, source=CRON)
    assert not r and r.why == "held_on_demand"                            # never "error"
    s = st.lease_state(NOW)
    assert s["held"] is True and s["held_by"] == OD and s["holder_started_at"].tzinfo is not None
    t = st.claim_lease(NOW, source=CRON, take_over=True)
    assert t.ok and t.why == "taken_over"
    assert ST.lease_free({"status": "running", "claimed_at": naive(_ago(GC.LEASE_SEC))}, NOW) is True
    assert ST.lease_gap_ok({"last_cron_started_at": naive(_ago(10))}, NOW) is False


class _RacyColl(FakeColl):
    """The holder releases between the claim's attempt (DuplicateKeyError) and its classify read."""
    def find_one(self, q=None, projection=None):
        d = self.docs.get(ST.LEASE_ID)
        if d is not None:
            d["status"] = "done"
        return super().find_one(q, projection)


def test_NEGATIVE_a_release_between_the_attempt_and_the_read_is_error_never_a_false_held():
    st = fake_store(**{ST.STATE: _RacyColl()})
    _put_lease(st, status="running", held_by=OD, token="od", claimed_at=_ago(5), last_cron_started_at=_ago(300))
    r = st.claim_lease(NOW, source=CRON)
    assert not r and r.why == "error"
    assert st.claim_lease(NOW, source=CRON).ok                            # the retry claims (A7)


def test_lease_owner_is_reads_the_token():
    st = fake_store()
    c = st.claim_lease(NOW, source=OD)
    assert st.lease_owner_is(c.token) is True
    assert st.lease_owner_is("someone-else") is False and st.lease_owner_is(None) is False
    t = st.claim_lease(NOW + timedelta(seconds=GC.CRON_WAIT_ON_DEMAND_SEC), source=CRON, take_over=True)
    assert st.lease_owner_is(c.token) is False and st.lease_owner_is(t.token) is True
    assert fake_store(**{ST.STATE: FakeColl(fail=True)}).lease_owner_is(c.token) is False   # fail closed
    assert ST.GajjalaStore(colls={n: None for n in ST.ALL}).lease_owner_is("x") is True
    assert fake_store().lease_owner_is("x") is True                     # no lease doc on file: nobody took it over


# the FakeColl verdict of lease_query == the python helpers, on a table of lease docs (query and classifier never drift)
_N = lambda dt: dt.astimezone(timezone.utc).replace(tzinfo=None)         # noqa: E731
LEASE_TABLE = [
    {},
    {"status": "done"},
    {"status": "done", "held_by": CRON, "last_cron_started_at": _ago(10), "started_at": _ago(10)},
    {"status": "done", "held_by": CRON, "last_cron_started_at": _ago(300), "started_at": _ago(300)},
    {"status": "done", "held_by": OD, "od_started_at": _ago(5), "last_cron_started_at": _ago(100)},
    {"status": "running", "held_by": CRON, "claimed_at": _ago(10), "last_cron_started_at": _ago(10)},
    {"status": "running", "held_by": CRON, "claimed_at": _ago(GC.LEASE_SEC), "last_cron_started_at": _ago(GC.LEASE_SEC)},
    {"status": "running", "held_by": OD, "claimed_at": _ago(5), "last_cron_started_at": _ago(300)},
    {"status": "running", "held_by": OD, "claimed_at": _ago(5), "last_cron_started_at": _ago(100)},
    {"status": "running", "held_by": OD, "claimed_at": _ago(5)},
    {"status": "running", "held_by": OD, "claimed_at": _ago(GC.LEASE_SEC + 5), "last_cron_started_at": _ago(100)},
    {"status": "done", "claimed_at": _ago(100), "started_at": _ago(100)},
    {"status": "done", "claimed_at": _ago(300), "started_at": _ago(300)},
    {"status": "running", "claimed_at": _ago(10), "started_at": _ago(10)},
    {"status": "running", "held_by": OD, "claimed_at": _N(_ago(5)), "last_cron_started_at": _N(_ago(300))},
    {"status": "done", "last_cron_started_at": None},
    {"status": "done", "last_cron_started_at": _ago(100), "started_at": _ago(300)},
]
MODES = [(CRON, False), (OD, False), (CRON, True)]


@pytest.mark.parametrize("i", range(len(LEASE_TABLE)))
@pytest.mark.parametrize("source,take", MODES)
def test_the_lease_query_and_the_python_classifier_agree(i, source, take):
    doc = dict(LEASE_TABLE[i], _id=ST.LEASE_ID)
    hit = FakeColl([doc]).find_one(ST.lease_query(NOW, source, take_over=take)) is not None
    assert hit == ST.lease_claimable(doc, NOW, source, take_over=take), (doc, source, take)


def test_the_lease_table_exercises_both_verdicts_in_every_mode():
    for source, take in MODES:
        vs = {ST.lease_claimable(dict(d, _id=ST.LEASE_ID), NOW, source, take_over=take) for d in LEASE_TABLE}
        assert vs == {True, False}, (source, take)


def test_NEGATIVE_the_lease_query_uses_only_the_operators_the_fake_and_mongo_share():
    import json
    for source, take in MODES:
        ops = set(re.findall(r'"(\$[a-zA-Z]+)"', json.dumps(ST.lease_query(NOW, source, take_over=take), default=str)))
        assert ops <= {"$or", "$and", "$ne", "$lte", "$exists"}, ops


# ── A10 two pointers / C5 the on-open pass doc ──────────────────────────────────────────────────────────────────
def test_A10_an_on_open_pass_moves_latest_never_latest_cron():
    st = fake_store()
    st.record_pass(S, NOW, {"status": "ok"})
    od_at = NOW + timedelta(seconds=40)
    st.record_pass(S, od_at, {"status": "ok", "on_demand": True}, hhmm="10:01:40|open", source=OD, latest_if_newer=True)
    assert set(st.coll(ST.PASSES).docs) == {"2026-10-13|10:01", "2026-10-13|10:01:40|open", "latest", "latest_cron"}
    assert st.latest_pass()["pass_id"] == "2026-10-13|10:01:40|open" and st.latest_pass()["on_demand"] is True
    assert st.latest_cron_pass()["pass_id"] == "2026-10-13|10:01"
    assert [p["_id"] for p in sorted(st.passes(S), key=lambda d: d["_id"])] == ["2026-10-13|10:01",
                                                                               "2026-10-13|10:01:40|open"]


def test_NEGATIVE_latest_if_newer_never_moves_latest_back():
    st = fake_store()
    st.record_pass(S, NOW, {"status": "ok"})                              # a cron pass that started later, recorded first
    st.record_pass(S, NOW - timedelta(seconds=30), {"status": "ok"}, hhmm="10:00:30|open", source=OD,
                   latest_if_newer=True)
    assert st.latest_pass()["pass_id"] == "2026-10-13|10:01"
    assert "2026-10-13|10:00:30|open" in st.coll(ST.PASSES).docs          # its own doc is still written
    st.coll(ST.PASSES).docs["latest"]["at"] = (NOW - timedelta(minutes=5)).replace(tzinfo=None)   # naive, older
    st.record_pass(S, NOW - timedelta(seconds=30), {"status": "ok"}, hhmm="10:00:30|open", source=OD,
                   latest_if_newer=True)
    assert st.latest_pass()["pass_id"] == "2026-10-13|10:00:30|open"    # older stored latest → replaced


def test_NEGATIVE_move_latest_false_writes_the_pass_doc_only():
    st = fake_store()
    st.record_pass(S, NOW, {"status": "ok"})
    st.record_pass(S, NOW + timedelta(seconds=40), {"status": "ok"}, hhmm="10:01:40|open", source=OD,
                   latest_if_newer=True, move_latest=False)
    assert st.latest_pass()["pass_id"] == "2026-10-13|10:01" and "2026-10-13|10:01:40|open" in st.coll(ST.PASSES).docs


def test_NEGATIVE_recent_passes_never_returns_the_latest_cron_pointer():
    st = fake_store()
    st.record_pass(S, NOW - timedelta(minutes=5), {"status": "ok", "potential": {}})
    docs = st.recent_passes(S, NOW - timedelta(minutes=10), NOW)
    assert [d["_id"] for d in docs] == ["2026-10-13|09:56"]


def test_the_new_lease_and_pointer_reads_delegate(monkeypatch):
    fake = fake_store()
    monkeypatch.setattr(ST, "_DEFAULT", fake)
    c = ST.claim_lease(NOW, source=OD)
    assert ST.lease_state(NOW)["held_by"] == OD and ST.lease_owner_is(c.token) is True
    ST.record_pass(S, NOW, {"status": "ok"})
    assert ST.latest_cron_pass()["pass_id"] == ST.latest_pass()["pass_id"]


# ── 🏁 gajjala_ledger (the Track record, 2026-10-16 — BUILD_SPEC9 §3.2) ─────────────────────────────────────────────
D16 = date(2026, 10, 16)


def _pot(sym, d=D16, state="pushed"):
    return {"_id": ST.potential_key(d, sym, "bull_flag"), "date": d.isoformat(), "symbol": sym, "setup": "bull_flag",
            "push": {"state": state, "at": "2026-10-16T14:00:00+00:00"}}


def test_ledger_is_a_kept_collection_with_the_read_indexes():
    st = fake_store()
    assert ST.LEDGER == "gajjala_ledger" and ST.LEDGER in ST.ALL
    st.ensure_indexes()
    idx = [spec for spec, _kw in st.coll(ST.LEDGER).indexes]
    assert (("date", 1), ("symbol", 1)) in idx and (("symbol", 1), ("date", -1)) in idx
    assert not [kw for spec, kw in st.coll(ST.LEDGER).indexes if kw.get("expireAfterSeconds")]


def test_potential_pushes_reads_only_rung_pushes_of_the_sessions():
    st = fake_store(**{ST.POTENTIALS: FakeColl([_pot("AAA"), _pot("BBB", state="no_target"),
                                                _pot("OLD", d=date(2026, 10, 9)),
                                                {"_id": "x", "date": "2026-10-16", "symbol": "NOP"}])})
    assert [d["symbol"] for d in st.potential_pushes([D16])] == ["AAA"]
    assert st.potential_pushes([]) == []


def test_alert_rows_reads_shadow_and_pushed_only():
    docs = [{"_id": "SHADOW:GG:2026-10-16|PMI|bull_flag", "date": "2026-10-16", "state": "shadow"},
            {"_id": "GG:2026-10-16|PMI|bull_flag#late", "date": "2026-10-16", "state": "late"},
            {"_id": "GG:2026-10-16|TGL|bull_flag", "date": "2026-10-16", "state": "pushed"},
            {"_id": "GG:2026-10-16|HCAI|bull_flag", "date": "2026-10-16", "state": "claimed"}]
    st = fake_store(**{ST.ALERTS: FakeColl(docs)})
    assert sorted(d["_id"] for d in st.alert_rows([D16])) == ["GG:2026-10-16|TGL|bull_flag",
                                                              "SHADOW:GG:2026-10-16|PMI|bull_flag"]


def test_upsert_ledger_then_ledger_docs_and_dates():
    st = fake_store()
    assert st.upsert_ledger("2026-10-16|AAA|bull_flag|potential", {"date": "2026-10-16", "symbol": "AAA",
                                                                   "same": {"outcome": "win"}, "version": 1})
    assert st.upsert_ledger("2026-10-16|AAA|bull_flag|potential", {"next": {"outcome": "win"}})
    (doc,) = st.ledger_docs([D16])
    assert doc["same"] == {"outcome": "win"} and doc["next"] == {"outcome": "win"}     # a next never rewrites same
    assert st.ledger_dates() == ["2026-10-16"] and st.ledger_docs([date(2026, 10, 15)]) == []
    assert set(st.coll(ST.LEDGER).docs) == {"2026-10-16|AAA|bull_flag|potential"}
    assert all(st.coll(n).writes == 0 for n in ST.ALL if n != ST.LEDGER)               # never another collection


@pytest.mark.parametrize("bad", [{"push": {}}, {"date": "2026-10-16", "held": True}, {}])
def test_NEGATIVE_upsert_ledger_refuses_a_key_outside_ledger_keys(bad):
    st = fake_store()
    assert st.upsert_ledger("2026-10-16|AAA|bull_flag|potential", bad) is False
    assert st.coll(ST.LEDGER).writes == 0


def test_alert_dates_is_the_union_of_the_rows_own_dates():
    st = fake_store(**{ST.POTENTIALS: FakeColl([_pot("AAA"), _pot("OLD", d=date(2026, 10, 9)),
                                                _pot("NT", d=date(2026, 10, 8), state="no_target")]),
                       ST.ALERTS: FakeColl([{"_id": "SHADOW:GG:2026-10-13|PMI|bull_flag", "date": "2026-10-13",
                                             "state": "shadow"}])})
    assert st.alert_dates() == ["2026-10-09", "2026-10-13", "2026-10-16"]


@pytest.mark.parametrize("which", [ST.POTENTIALS, ST.ALERTS, ST.LEDGER])
def test_NEGATIVE_every_ledger_read_is_none_on_a_failing_coll(which):
    st = fake_store(**{which: FakeColl(fail=True)})
    reads = {ST.POTENTIALS: [st.potential_pushes([D16]), st.alert_dates()],
             ST.ALERTS: [st.alert_rows([D16]), st.alert_dates()],
             ST.LEDGER: [st.ledger_docs([D16]), st.ledger_dates()]}[which]
    assert reads == [None, None]
    if which == ST.LEDGER:
        assert st.upsert_ledger("2026-10-16|AAA|bull_flag|potential", {"date": "2026-10-16"}) is False


def test_NEGATIVE_no_handle_reads_none_and_writes_false():
    st = ST.GajjalaStore(colls={n: None for n in ST.ALL})
    assert (st.potential_pushes([D16]), st.alert_rows([D16]), st.ledger_docs([D16]), st.ledger_dates(),
            st.alert_dates()) == (None, None, None, None, None)
    assert st.upsert_ledger("2026-10-16|AAA|bull_flag|potential", {"date": "2026-10-16"}) is False
