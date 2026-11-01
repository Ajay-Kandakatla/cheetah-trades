"""chart_maps/luk/store.py — 🥇 Luk's store (spec §3.4): a GajjalaStore subclass over `luk_*` only, refusing every other
GG collection, on Luk's own lease numbers."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as GS
from chart_maps.luk import constants as LC
from chart_maps.luk import store as LS
from tests.test_gajjala_store import FakeColl

S = date(2026, 11, 3)
NOW = datetime(2026, 11, 3, 14, 36, tzinfo=timezone.utc)


def fake_luk(**over) -> LS.LukStore:
    colls = {n: FakeColl() for n in LS.LOGICAL}
    colls[LS.SCREENS_KEY] = FakeColl()
    colls.update(over)
    return LS.LukStore(colls=colls)


@pytest.fixture
def mongo_names(monkeypatch):
    """GS._coll replaced: records every physical name the store resolves, hands back a FakeColl."""
    seen: dict = {}

    def _coll(name):
        seen.setdefault(name, FakeColl())
        return seen[name]

    monkeypatch.setattr(GS, "_coll", _coll)
    return seen


def test_physical_names_are_all_luk():
    assert set(LS.LOGICAL.values()) == {"luk_passes", "luk_reads", "luk_alerts", "luk_state", "luk_ledger",
                                        "luk_daily"}
    assert LS.SCREENS == "luk_screens"
    assert all(p.startswith("luk_") for p in LS.PHYSICAL)
    st = LS.LukStore(colls={})
    for logical, phys in LS.LOGICAL.items():
        assert st.physical(logical) == phys
    assert set(LS.REFUSED) | set(LS.LOGICAL) == set(GS.ALL) and not set(LS.REFUSED) & set(LS.LOGICAL)


def test_every_used_method_resolves_to_a_luk_collection(mongo_names):
    st = LS.LukStore()
    st.record_pass(S, NOW, {"n_read": 1})
    st.upsert_read(S, "aaa", {"setups": {}}, now=NOW)
    st.set_state(LC.LUK_STATE_BARS_THROUGH, {"session": S.isoformat()})
    st.upsert_daily(S, "aaa", {"facts": {"close": 1.0}}, now=NOW)
    st.upsert_screens(S, NOW, {"premarket": []})
    st.alerts_coll().update_one({"_id": "x"}, {"$set": {"date": S.isoformat()}}, upsert=True)
    st.upsert_ledger("2026-11-03|AAA|pullback_reversal|aplus", {"date": S.isoformat(), "symbol": "AAA"})
    st.claim_lease(NOW)
    assert st.get_read(S, "AAA")["symbol"] == "AAA"
    assert st.get_daily(S, "AAA")["facts"] == {"close": 1.0}
    assert st.latest_screens(S)["premarket"] == []
    assert mongo_names, "something was resolved"
    assert all(n.startswith("luk_") for n in mongo_names), sorted(mongo_names)
    assert not any(n.startswith("gajjala") for n in mongo_names)


def test_dry_store_records_writes_on_luk_names_only():
    real = fake_luk()
    dry = LS.dry_store(real)
    assert dry.dry is True and dry.writes == []
    dry.record_pass(S, NOW, {"n_read": 0})
    dry.upsert_read(S, "AAA", {"setups": {}}, now=NOW)
    dry.set_state(LC.LUK_STATE_BARS_THROUGH, {"t1": None})
    dry.upsert_daily(S, "AAA", {"facts": {}}, now=NOW)
    dry.upsert_screens(S, NOW, {"potent": []})
    dry.claim_lease(NOW)
    names = {n for n, _op in dry.writes}
    assert names == {"luk_passes", "luk_reads", "luk_state", "luk_daily", "luk_screens"}
    assert all(real.coll(n).docs == {} for n in LS.LOGICAL), "NEGATIVE: nothing landed on the real store"
    assert real.screens.docs == {}


@pytest.mark.parametrize("name", LS.REFUSED)
def test_NEGATIVE_a_refused_gg_collection_raises(name):
    st = fake_luk()
    with pytest.raises(RuntimeError, match="Luk never touches"):
        st.coll(name)


def test_NEGATIVE_scan_raises_even_when_injected_and_stub_refuses_any_attr():
    st = LS.LukStore(colls={GS.SCAN: FakeColl()})
    with pytest.raises(RuntimeError):
        st.coll(GS.SCAN)
    stub = LS._Refusing(GS.HALTS)
    with pytest.raises(RuntimeError, match="gajjala_halts"):
        stub.find({})


def test_lease_numbers_are_luks():
    st = fake_luk()
    assert st._lease_nums() == (LC.LUK_LEASE_SEC, LC.LUK_LEASE_MIN_GAP_SEC)
    assert st._lease_nums() != (GC.GG1M_LEASE_SEC, GC.GG1M_LEASE_MIN_GAP_SEC), \
        "NEGATIVE: the GG base hands any non-GG5 variant the 1-minute page's numbers"


def test_lease_gap_runs_on_luks_gap():
    st = fake_luk()
    assert st.claim_lease(NOW)
    st.release_lease(NOW, st.coll(GS.STATE).docs[GS.LEASE_ID]["token"])
    gap = LC.LUK_LEASE_MIN_GAP_SEC
    inside = st.claim_lease(NOW + timedelta(seconds=gap - 1))
    assert not inside and inside.why == "gap"
    assert st.claim_lease(NOW + timedelta(seconds=gap))


def test_ensure_indexes_luk_only_and_ttl(mongo_names):
    st = LS.LukStore()
    st.ensure_indexes()
    st.ensure_indexes()
    assert set(mongo_names) == set(LS.PHYSICAL)
    assert "luk_overlay" not in mongo_names and "luk_scan" not in mongo_names
    ttl = {n: [kw.get("expireAfterSeconds") for spec, kw in c.indexes if spec == (("at", 1),)]
           for n, c in mongo_names.items()}
    assert ttl["luk_reads"][0] == GC.READS_TTL_DAYS * 86400
    for n in ("luk_passes", "luk_daily", "luk_screens"):
        assert ttl[n][0] == GC.LEDGER_TTL_DAYS * 86400
    for n in ("luk_alerts", "luk_state", "luk_ledger"):
        assert ttl[n] == [], f"{n} is kept (no TTL)"
    idx = [spec for spec, _kw in mongo_names["luk_daily"].indexes]
    assert (("date", 1), ("symbol", 1)) in idx


def test_screens_roundtrip_one_doc_per_session():
    st = fake_luk()
    st.upsert_screens(S, NOW, {"premarket": [{"symbol": "AAA"}]})
    st.upsert_screens(S, NOW, {"premarket": []})
    assert list(st.screens.docs) == [S.isoformat()]
    doc = st.latest_screens(S)
    assert doc["premarket"] == [] and doc["date"] == S.isoformat()
    assert st.latest_screens(date(2026, 11, 4)) is None


def test_ledger_open_lists_rows_without_an_exit():
    led = FakeColl([{"_id": "a", "walk": {"exit": None}}, {"_id": "b", "walk": {"exit": "stop"}},
                    {"_id": "c", "walk": {"exit": "ema9_close"}}, {"_id": "d"}])
    st = fake_luk(**{GS.LEDGER: led})
    assert sorted(d["_id"] for d in st.ledger_open()) == ["a", "d"]
    assert fake_luk(**{GS.LEDGER: FakeColl(fail=True)}).ledger_open() == []


def test_default_is_one_object_and_a_lukstore(mongo_names, monkeypatch):
    monkeypatch.setattr(LS, "_DEFAULT", None)
    a = LS.default()
    assert a is LS.default() and isinstance(a, LS.LukStore) and a.variant.key == "luk"
