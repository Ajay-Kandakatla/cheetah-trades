"""chart_maps/gajjala/store.py — the tab's Mongo storage (spec §3.1.6), against an in-memory collection.

`FakeColl` here is the stand-in the other Gajjala test files import (tests/conftest.py refuses a real MongoClient).
"""
from __future__ import annotations

import copy
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
    for n in (ST.ALERTS, ST.HALTS, ST.STATE):                     # ledgers kept
        assert ttl[n] == []


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
    assert set(st.coll(ST.PASSES).docs) == {"2026-10-13|10:01", "latest"}
    assert st.latest_pass()["pass_id"] == "2026-10-13|10:01"
    assert [p["_id"] for p in st.passes(S)] == ["2026-10-13|10:01"]


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
    assert st.claim_lease(NOW) is True
    assert st.claim_lease(NOW + timedelta(seconds=10)) is False          # held
    st.release_lease(NOW + timedelta(seconds=60))
    assert st.claim_lease(NOW + timedelta(seconds=GC.LEASE_MIN_GAP_SEC - 1)) is False   # inside the min gap
    assert st.claim_lease(NOW + timedelta(seconds=GC.LEASE_MIN_GAP_SEC)) is True


def test_NEGATIVE_a_stuck_lease_expires_after_lease_sec():
    st = fake_store()
    assert st.claim_lease(NOW) is True
    assert st.claim_lease(NOW + timedelta(seconds=GC.LEASE_SEC)) is True


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
    assert st.claim_lease(NOW) is True                                    # the medical helper's no-mongo answer


def test_NEGATIVE_a_failing_collection_never_raises():
    st = fake_store(**{n: FakeColl(fail=True) for n in ST.ALL})
    st.ensure_indexes()
    assert st.record_qualifiers(S, NOW, [_row("AAA")], "rth") == {"AAA"}
    st.set_split_check(S, "AAA", "ok")
    st.replace_ah_carry(S, NOW, [_row("AAA")])
    st.record_pass(S, NOW, {"status": "ok"})
    assert st.reads(S) == [] and st.ah_carry(S) is None and st.split_checks(S) == {}
    assert st.claim_lease(NOW) is False


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
