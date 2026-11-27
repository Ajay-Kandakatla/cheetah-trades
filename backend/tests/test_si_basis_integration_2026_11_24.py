"""🩳 % of float — dilution, splits, filings: integration over the REAL captured inputs (2026-11-24).

Ajay 2026-11-24, verbatim, in order: "Yeah please" · "Make sure we are looking for Dilution.." · "Also split related
events and filing so we flag them in the right way".

Spec `sidilute` rev 2 §4 probe-docs. Nothing here stands in for a module: the REAL `share_basis.refresh_symbol`
(its SEC reads, its Massive reference read, `drop10_tab.fetch_splits_strict` for the splits) writes into ONE
in-memory Mongo, the REAL `read.si_map` joins it through the REAL `share_basis.load`, and the REAL `basis_math`
judges it. The fake HTTP answers ONLY from `tests/fixtures/si_share_basis_2026_11_24.json` — 12 names captured
11-24 from Massive and data.sec.gov (no synthetic SEC answer in the fixture; the accession numbers the submissions
body needs are derived from the row index here, since the capture kept none). Each test mutates a deep copy only.

Harness: every outside call goes through `FakeHTTP` (records host + path, never the key); the Massive key resolver
answers a synthetic key; the SEC pacer is a no-op (its spacing is pinned in test_si_share_basis_2026_11_24.py).
"""
from __future__ import annotations

import copy
import json
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from short_interest import basis_math as BM
from short_interest import client as SIC
from short_interest import read as SR
from short_interest import share_basis as SB
from scripts import si_share_basis_probe as PR

BACKEND = Path(__file__).resolve().parents[1]
FIXTURE = BACKEND / "tests" / "fixtures" / "si_share_basis_2026_11_24.json"
FX = json.loads(FIXTURE.read_text(encoding="utf-8"))
NAMES = list(FX["names"])
TODAY = date(2026, 11, 24)
NOW1 = datetime(2026, 11, 24, 19, 30, tzinfo=timezone.utc)                      # after the last capture (19:05Z)
NOW2 = NOW1 + timedelta(minutes=SB.SB_ERROR_RETRY_MIN + 1)
KEY = "SYNTHKEYsibasis"
# 2026-11-26 sishares §3.3 / §5.5 (C12): the share-basis family also reaches efts.sec.gov (the 6-K full-text search,
# sec_fts.py through share_basis._sec_get) — the contracts host pin is amended the same way; www.sec.gov never.
ALLOWED_HOSTS = {"data.sec.gov", "api.massive.com", "efts.sec.gov"}
# 2026-11-26 sitrack A4: the provider's 1.0 with no ADV on the record is FINRA's floor → '≤1d'
SMTK_CHIP = "🩳 SI 8.9% shs out · ≤1d · 10/30 · ⚠️ float stale · ✂️ split 11/23 · 📄 S-4 11/13"
MOVED = {"SMTK", "LABT", "KITT", "SMX"}                 # spec §7 #1 (C): the four that lose the % of float
# 2026-11-24 later ("Is GMEX float accurate?") — the names whose captured Yahoo row holds a NEWER, different float than the
# SI record: basis_math.newer_float makes it the one divided by (the splits read is held for all of them); the dilution
# checks keep the replaced float's date and count, so LABT / KITT stay refused as diluted.
FLOAT_UPDATED = {"LABT", "KITT", "WETO", "JELD", "SMX"}


# ═════════════════════════════════════════════ the in-memory Mongo (every operation the three modules use)
class Coll:
    def __init__(self, name):
        self.name = name
        self.docs = {}
        self.writes = 0

    @staticmethod
    def _match(doc, flt):
        for k, v in (flt or {}).items():
            if isinstance(v, dict) and "$in" in v:
                if doc.get(k) not in v["$in"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def find(self, flt=None, projection=None):
        out = []
        for d in self.docs.values():
            if self._match(d, flt):
                d = copy.deepcopy(d)
                if projection:
                    keep = {k for k, v in projection.items() if v}
                    if keep:
                        d = {k: v for k, v in d.items() if k in keep or k == "_id"}
                out.append(d)
        return out

    def find_one(self, flt=None, *a, **k):
        got = self.find(flt)
        return got[0] if got else None

    def replace_one(self, flt, doc, upsert=False):
        assert set(flt) == {"_id"} and upsert is True
        self.writes += 1
        self.docs[flt["_id"]] = copy.deepcopy(doc)

    def update_one(self, flt, upd, upsert=False):
        self.writes += 1
        d = self.docs.get(flt["_id"]) or {"_id": flt["_id"]}
        d.update(copy.deepcopy(upd.get("$set") or {}))
        self.docs[flt["_id"]] = d

    def create_index(self, *a, **k):
        return "noop"


class DB:
    def __init__(self):
        self.colls = {}

    def __getitem__(self, name):
        if name not in self.colls:
            self.colls[name] = Coll(name)
        return self.colls[name]


def _epoch(iso: str) -> float:
    d = date.fromisoformat(iso)
    return datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc).timestamp()


def make_db(fx) -> DB:
    db = DB()
    for sym, n in fx["names"].items():
        db[SIC.SI_COLL].docs[sym] = dict(n["si_record"], _id=sym, symbol=sym)
        y = n["yahoo_now"]
        db["shares_cache"].docs[sym] = {"_id": sym, "float_shares": y["float_shares"],
                                        "shares_outstanding": y["shares_outstanding"], "as_of": _epoch(y["as_of"])}
    return db


# ═════════════════════════════════════════════ the fake outside world (answers from the fixture only)
class Resp:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        return copy.deepcopy(self._body)

    @property
    def text(self):
        return json.dumps(self._body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("http %d" % self.status_code)


class FakeHTTP:
    """requests.get-shaped AND session-shaped. `fail(host)` → raise a Timeout for that call."""

    def __init__(self, fx, fail=None):
        self.fx = fx
        self.fail = fail or (lambda host: False)
        self.calls = []
        self.by_cik = {n["ref"]["cik"]: s for s, n in fx["names"].items() if n["ref"].get("cik")}

    def __call__(self, url, params=None, headers=None, timeout=None, **kw):
        return self.get(url, params=params, headers=headers, timeout=timeout, **kw)

    def get(self, url, params=None, headers=None, timeout=None, **kw):
        u = urllib.parse.urlsplit(str(url))
        q = dict(urllib.parse.parse_qsl(u.query))
        q.update(params or {})
        q.pop("apiKey", None)
        self.calls.append((u.netloc, u.path, tuple(sorted((k, str(v)) for k, v in q.items()))))
        if self.fail(u.netloc):
            raise requests.Timeout("synthetic timeout")
        if u.netloc == "api.massive.com":
            return self._massive(u.path, q)
        if u.netloc == "data.sec.gov":
            return self._sec(u.path)
        return Resp(599, {})

    def _massive(self, path, q):
        if path.startswith("/v3/reference/tickers/"):
            n = self.fx["names"].get(path.rsplit("/", 1)[-1].upper())
            if n is None or n["ref"]["http"] != 200:
                return Resp(404, {"status": "NOT_FOUND"})
            r = n["ref"]
            return Resp(200, {"status": "OK", "results": {
                "ticker": path.rsplit("/", 1)[-1], "cik": r["cik"], "type": r["type"],
                "weighted_shares_outstanding": r["weighted_shares_outstanding"],
                "share_class_shares_outstanding": r["share_class_shares_outstanding"]}})
        if path == "/v3/reference/splits":
            n = self.fx["names"].get(str(q.get("ticker") or "").upper())
            gte = q.get("execution_date.gte") or ""
            rows = [] if n is None else [dict(x, ticker=q.get("ticker")) for x in n["splits"]["rows"]
                                         if x["execution_date"] >= gte]
            return Resp(200, {"status": "OK", "results": rows})
        return Resp(404, {})

    def _sec(self, path):
        cik = path.split("CIK", 1)[-1][:10] if "CIK" in path else ""
        sym = self.by_cik.get(cik)
        n = self.fx["names"].get(sym) if sym else None
        if n is None:
            return Resp(404, {})
        sec = n["sec"]
        if "/companyconcept/" in path:
            if sec["concept_http"] != 200:
                return Resp(404, {})
            return Resp(200, {"cik": int(cik), "taxonomy": "dei", "tag": "EntityCommonStockSharesOutstanding",
                              "units": {"shares": [{"end": c["as_of"], "val": c["shares"], "form": c["form"],
                                                    "filed": c["filed"], "accn": "FX-%s-c%d" % (sym, i)}
                                                   for i, c in enumerate(sec["covers"])]}})
        if path.startswith("/submissions/"):
            if sec["sub_http"] != 200:
                return Resp(404, {})
            f = sec["filings"]
            return Resp(200, {"cik": cik, "name": sec.get("entity"), "filings": {"recent": {
                "accessionNumber": ["FX-%s-f%d" % (sym, i) for i in range(len(f))],
                "filingDate": [x["filed"] for x in f], "form": [x["form"] for x in f],
                "items": [x["items"] for x in f]}}})
        return Resp(404, {})

    def hosts(self):
        return {c[0] for c in self.calls}


@pytest.fixture(autouse=True)
def _harness(monkeypatch):
    import massive_keys
    from sepa import prices
    monkeypatch.setattr(massive_keys, "stocks_key", lambda *a, **k: KEY)
    monkeypatch.setattr(SB, "_sec_wait", lambda *a, **k: None)
    monkeypatch.setitem(SB._sec_stop, "until", None)
    monkeypatch.setattr(SB, "_http", None)
    holder = {}
    monkeypatch.setattr(prices, "_http", lambda *a, **k: holder["http"])
    monkeypatch.setattr(BM, "FLOAT_STALE_WHEN", "added_exceeds_float")
    return holder


def refresh_all(db, http, holder, now, names=NAMES):
    holder["http"] = http
    return {s: SB.refresh_symbol(s, db, now, http=http) for s in names}


def blocks(db, names=NAMES):
    return SR.si_map(list(names), db=db, today=TODAY)


def flags(b):
    return [f.get("key") for f in ((b.get("basis") or {}).get("flags") or [])]


def shorts(b):
    return [f.get("short") for f in ((b.get("basis") or {}).get("flags") or [])]


def refused(b):
    return (b.get("basis") or {}).get("float_refused")


def _run(fx=None, fail=None, names=NAMES, *, holder):
    fx = fx or copy.deepcopy(FX)
    db = make_db(fx)
    old = blocks(db, names)
    http = FakeHTTP(fx, fail=fail)
    docs = refresh_all(db, http, holder, NOW1, names)
    return db, http, old, blocks(db, names), docs


# ═════════════════════════════════════════════ the §7 #2 moves under the built mode
def test_fixture_is_real_captures_only():
    assert set(NAMES) == {"SMTK", "LABT", "KITT", "SMX", "WETO", "JELD", "MEDS", "JZ", "INLF", "BENF", "NXAT", "CLRO"}
    labels = {s: n["label"] for s, n in FX["names"].items()}
    assert labels["WETO"] == "20-F filer, covers older than the anchor"
    assert labels["BENF"] == "no cover fact (404)"
    assert labels["NXAT"] == "count fell, no split row"
    assert labels["JZ"] == "ADR, split due"
    for s, n in FX["names"].items():
        assert n["captured_at"]["sec"].startswith("2026-11-24T") and n["captured_at"]["si_yahoo_ref_splits"]
    smtk = [(r["execution_date"], r["split_from"], r["split_to"]) for r in FX["names"]["SMTK"]["splits"]["rows"]]
    assert smtk == [("2026-08-21", 50, 1), ("2026-11-23", 5, 1)]
    assert FX["names"]["BENF"]["sec"]["concept_http"] == 404 and FX["names"]["BENF"]["sec"]["covers"] == []


def test_no_basis_doc_is_served_as_before(_harness):
    db = make_db(copy.deepcopy(FX))
    for s, b in blocks(db).items():
        assert "basis" not in b
        assert b == SR.si_block(dict(db[SIC.SI_COLL].docs[s]), TODAY)


def test_the_moves_under_the_built_mode(_harness):
    db, http, old, new, docs = _run(holder=_harness)
    assert http.hosts() <= ALLOWED_HOSTS and "data.sec.gov" in http.hosts()
    assert {s for s, b in new.items() if refused(b)} == MOVED
    for s in MOVED:
        assert new[s]["pct_of_float"] is None and new[s]["tier"] is None, s
    # SMTK — the acceptance case, frozen fixture: the exact chip IS pinned here (spec §5 step 2)
    sm = new["SMTK"]
    assert sm["chip"] == SMTK_CHIP
    assert refused(sm) == "diluted" and flags(sm)[:3] == ["float_stale", "split", "filing"]
    assert sm["shares_outstanding"] == 4859369 and sm["shares_asof"] == "2026-11-11"
    assert sm["shares_source"].startswith("SEC") and sm["pct_of_shares_out"] == 8.9
    assert "4.7×" in sm["title"] and "8.6×" in sm["title"] and "86,463 of today's shares" in sm["title"]
    assert PR.smtk_check(sm) == []
    # LABT / KITT / SMX
    assert refused(new["LABT"]) == "diluted" and new["LABT"]["pct_of_shares_out"] == 1.71
    # 2026-11-24 later — KITT's newer Yahoo float (11-23) is on the count's side of the 9/25 split, so the split
    # refusal goes; the dilution since the REPLACED float's date (09-03) still refuses it (was: split + diluted)
    assert refused(new["KITT"]) == "diluted" and new["KITT"]["basis"]["refused_reasons"] == ["diluted"]
    assert new["KITT"]["pct_of_shares_out"] == 7.71 and "2.1×" in new["KITT"]["title"]
    assert refused(new["SMX"]) == "split" and new["SMX"]["pct_of_shares_out"] is None    # newer float post-split, SI pre
    # 2026-11-24 later — every newer float carries the flag first; the dilution flags stay
    assert {s for s, b in new.items() if "float_updated" in flags(b)} == FLOAT_UPDATED
    for s in FLOAT_UPDATED:
        assert flags(new[s])[0] == "float_updated" and "⚠️ float updated" in new[s]["chip"], s
        assert new[s]["float_source"] == SR.YAHOO_LIVE_FLOAT_SOURCE, s
    assert "float_stale" in flags(new["LABT"]) and "float_stale" in flags(new["KITT"])
    assert "3,201,536 (Yahoo 11/18) replaced 847,661 (11/9)" in new["LABT"]["title"]
    # WETO — the replaced float was suspect (shares-headed path): Yahoo's later count still raises ⚠️ shares up 14×;
    # the newer float (14,735,015 on its own row's 14,897,999) is the one divided by
    we = new["WETO"]
    assert refused(we) is None and we["pct_of_float"] == 1.64 and we["float_suspect"] is None
    assert "count_stale" in flags(we) and "⚠️ shares up 14×" in we["chip"]
    # NXAT — the count fell 21× with no split row: a flag, never a refusal
    nx = new["NXAT"]
    assert nx["pct_of_float"] == old["NXAT"]["pct_of_float"] == 1.59 and nx["tier"] == old["NXAT"]["tier"]
    assert "count_fell" in flags(nx) and "❔ shares fell 21×" in nx["chip"] and nx["basis"]["status"] == "partial"
    # CLRO — EXTREME 44.0% float unchanged; the chip gains ONLY the filing mark
    cl = new["CLRO"]
    assert cl["pct_of_float"] == 44.05 and cl["tier"] == old["CLRO"]["tier"] and cl["extreme"] is not None
    assert cl["chip"] == old["CLRO"]["chip"] + " · 📄 S-1/A 11/24 +1"
    assert set(cl["extreme"]) == set(old["CLRO"]["extreme"])
    # JELD — ×1.0001: nothing refused; the only mark is the newer float (10.03% either way)
    assert new["JELD"]["chip"] == old["JELD"]["chip"] + " · ⚠️ float updated" and flags(new["JELD"]) == ["float_updated"]
    # JZ — an ADR: its SEC cover is never compared; the upcoming split is a mark only
    jz = new["JZ"]
    assert refused(jz) is None and jz["pct_of_float"] == old["JZ"]["pct_of_float"]
    assert jz["extreme"]["short"].endswith(" · ✂️ split due 12/24") and len(jz["extreme"]) == 4
    assert jz["basis"]["sources"]["sec"] == "units"
    # BENF — no cover fact: never a SEC flag; MEDS / INLF keep their float under the built mode
    assert docs["BENF"]["sec"]["status"] == "none" and "unchecked" not in flags(new["BENF"])
    for s in ("BENF", "MEDS", "INLF"):
        assert refused(new[s]) is None and new[s]["pct_of_float"] == old[s]["pct_of_float"], s
    json.dumps(new, allow_nan=False)


def test_every_mode_over_the_same_inputs(_harness):
    db, http, old, new, docs = _run(holder=_harness)
    by = {}
    for m in BM.FLOAT_STALE_MODES:
        with PR._mode(BM, m):
            by[m] = {s for s, b in blocks(db).items() if refused(b)}
    assert by["added_exceeds_float"] == MOVED
    assert "MEDS" in by["any_increase"] and "MEDS" in by["tier_moves"]
    assert "JELD" in by["any_increase"] and "JELD" not in by["tier_moves"]
    assert MOVED <= by["tier_moves"] <= by["any_increase"] | MOVED
    assert BM.FLOAT_STALE_WHEN == "added_exceeds_float"


# ═════════════════════════════════════════════ C1 — failures never un-refuse, never pass silently
def test_every_sec_call_fails_on_the_first_pass(_harness):
    db, http, old, new, docs = _run(fail=lambda h: h == "data.sec.gov", holder=_harness)
    for s, b in new.items():
        assert docs[s]["sec"]["status"] == "failed" and docs[s]["ref"]["cik"], s
        assert "❔ share count unchecked" in b["chip"] or (b["extreme"] or {}).get("short", "").endswith(
            "❔ share count unchecked"), s
        assert b["basis"]["status"] == "partial", s
        assert not str(b.get("shares_source") or "").startswith("SEC"), s
    # the error is the TYPE, never its text
    assert {docs[s]["sec"]["error"] for s in docs} == {"Timeout"}


def test_every_sec_and_splits_call_fails_on_the_first_pass_no_pct_changes(_harness):
    """Nothing is refused, rebased or replaced unless the splits were read (spec §3.3 step 0): with the SEC and the
    splits read both failing on the first pass, no % moves and every name says the check did not run."""
    def fail(host):
        return host == "data.sec.gov"
    fx = copy.deepcopy(FX)
    db = make_db(fx)
    old = blocks(db)
    http = FakeHTTP(fx, fail=fail)
    _harness["http"] = FakeHTTP(fx, fail=lambda h: True)          # the splits read (prices._http) fails too
    docs = {s: SB.refresh_symbol(s, db, NOW1, http=http) for s in NAMES}
    new = blocks(db)
    for s in NAMES:
        assert docs[s]["splits"]["status"] == "failed", s
        for k in ("pct_of_float", "pct_of_shares_out", "tier", "shares_outstanding", "si_change_pct"):
            assert new[s][k] == old[s][k], (s, k)
        assert refused(new[s]) is None and "unchecked" in flags(new[s]), s
        assert "❔ share count unchecked" in shorts(new[s]), s


def test_a_good_pass_then_every_call_fails(_harness):
    db, http, old, first, docs1 = _run(holder=_harness)
    bad = FakeHTTP(copy.deepcopy(FX), fail=lambda h: True)
    docs2 = refresh_all(db, bad, _harness, NOW2)
    second = blocks(db)
    for s in NAMES:
        assert refused(second[s]) == refused(first[s]), s
        assert second[s]["pct_of_float"] == first[s]["pct_of_float"], s
        assert second[s]["pct_of_shares_out"] == first[s]["pct_of_shares_out"], s
        assert second[s]["chip"].startswith(first[s]["chip"]) and second[s]["chip"].endswith("❔ last check failed"), s
        for k in ("sec", "splits"):
            sub = docs2[s][k]
            assert sub["status"] == docs1[s][k]["status"] and sub["read_at"] == docs1[s][k]["read_at"], (s, k)
            assert sub["error"] == "Timeout" and sub["strikes"] == 1, (s, k)
        assert docs2[s]["ref"] == docs1[s]["ref"]                   # a fresh ref is reused, never re-asked
    assert {c[0] for c in bad.calls} <= ALLOWED_HOSTS
    assert not any(c[1].startswith("/v3/reference/tickers/") for c in bad.calls)
    assert PR.smtk_check(second["SMTK"]) == []


# ═════════════════════════════════════════════ no CIK · an ETF · an ADR
def test_a_name_with_no_cik(_harness):
    fx = copy.deepcopy(FX)
    fx["names"]["SMTK"]["ref"]["http"] = 404
    db, http, old, new, docs = _run(fx=fx, names=["SMTK"], holder=_harness)
    assert docs["SMTK"]["ref"]["status"] == "absent" and docs["SMTK"]["sec"]["status"] == "no_cik"
    assert "data.sec.gov" not in http.hosts()
    sm = new["SMTK"]
    assert refused(sm) == "diluted"                               # Yahoo's later count still shows the dilution
    assert not sm["shares_source"].startswith("SEC") and "unchecked" not in flags(sm)
    assert "8.6×" not in sm["title"]


def test_an_etf_type_is_not_compared_to_a_sec_cover(_harness):
    fx = copy.deepcopy(FX)
    fx["names"]["SMTK"]["ref"]["type"] = "ETF"
    db, http, old, new, docs = _run(fx=fx, names=["SMTK"], holder=_harness)
    sm = new["SMTK"]
    assert sm["basis"]["sources"]["sec"] == "units"
    assert not sm["shares_source"].startswith("SEC") and "8.6×" not in sm["title"]


def test_an_adr_type_is_not_compared_and_the_same_doc_as_cs_is(_harness):
    fx = copy.deepcopy(FX)
    fx["names"]["SMTK"]["ref"]["type"] = "ADRC"
    db, http, old, new, docs = _run(fx=fx, names=["SMTK"], holder=_harness)
    assert new["SMTK"]["basis"]["sources"]["sec"] == "units"
    assert not new["SMTK"]["shares_source"].startswith("SEC")
    db2, http2, old2, new2, docs2 = _run(names=["SMTK"], holder=_harness)
    assert new2["SMTK"]["shares_source"].startswith("SEC")


def test_no_host_but_sec_and_massive_and_no_key_in_a_stored_doc(_harness):
    db, http, old, new, docs = _run(holder=_harness)
    assert http.hosts() == ALLOWED_HOSTS and "www.sec.gov" not in http.hosts()
    text = json.dumps(db[SB.SB_COLL].docs, default=str)
    assert KEY not in text and "apiKey" not in text


# ═════════════════════════════════════════════ the probe body over the same world
def test_the_probe_holds_on_the_fixture_and_writes_nothing(_harness):
    fx = copy.deepcopy(FX)
    db = make_db(fx)
    _harness["http"] = http = FakeHTTP(fx)
    out = PR.run(NAMES, db=db, now=NOW1, today=TODAY,
                 refresh=lambda s, d, n, store: SB.refresh_symbol(s, d, n, http=http, store=store))
    assert out["smtk_failures"] == []
    assert set(out["by_mode"]["added_exceeds_float"]["refused"]) == MOVED
    assert db[SB.SB_COLL].writes == 0 and db[SB.SB_COLL].docs == {}
    assert len(out["lines"]) == len(NAMES) and out["lines"][0].startswith("SMTK | ")
    assert {c["name"] for c in out["payload"]["cases"]} >= {"smtk_basis", "smtk_no_basis"}
    json.dumps(out["payload"], allow_nan=False)


def test_the_probe_seed_carries_the_check_across_a_rewarm(_harness):
    """The 11-13 settlement re-warms SMTK with today's shares_cache pair (546,875 @ 11-18, 4,859,369 @ 11-18): with no
    seed the check finds nothing (exit 1); the 11-24 seed row (the captured record's own pairing) carries it."""
    fx = copy.deepcopy(FX)
    rec = fx["names"]["SMTK"]["si_record"]
    seed = {"rows": {"SMTK": {k: rec[k] for k in ("float_shares", "float_asof", "shares_outstanding", "shares_asof")}}}
    rec.update({"settlement_date": "2026-11-13", "short_interest": 440000, "float_asof": "2026-11-18",
                "shares_outstanding": 4859369, "shares_asof": "2026-11-18",
                "prev_settlement_date": "2026-10-30", "prev_short_interest": 432313})
    db = make_db(fx)
    _harness["http"] = http = FakeHTTP(fx)
    ref = (lambda s, d, n, store: SB.refresh_symbol(s, d, n, http=http, store=store))
    bare = PR.run(["SMTK"], db=db, now=NOW1, today=TODAY, refresh=ref)
    assert bare["smtk_failures"] != []
    seeded = PR.run(["SMTK"], db=db, now=NOW1, today=TODAY, refresh=ref, seed=seed)
    assert seeded["seeded"] == ["SMTK"] and seeded["smtk_failures"] == []
    assert db[SB.SB_COLL].writes == 0


def test_the_probe_seed_is_refused_when_the_float_differs(_harness):
    fx = copy.deepcopy(FX)
    db = make_db(fx)
    seed = {"rows": {"SMTK": {"float_shares": 546874, "float_asof": "2026-11-02",
                              "shares_outstanding": 1035799, "shares_asof": "2026-11-02"}}}
    assert PR.seed_tracks(seed, ["SMTK"], db) == {}
    assert db[SB.SB_COLL].writes == 0


def test_the_structural_check_refuses_a_wrong_block(_harness):
    db, http, old, new, docs = _run(names=["SMTK"], holder=_harness)
    good = new["SMTK"]
    assert PR.smtk_check(good) == []
    assert PR.smtk_check(old["SMTK"]) != []                       # the block before the check: a float %, a tier
    assert PR.smtk_check(None) == ["no block"]
    for mutate in (lambda b: b.update(pct_of_float=79.05), lambda b: b.update(tier="extreme"),
                   lambda b: b["basis"].update(float_refused=None), lambda b: b["basis"].update(flags=[]),
                   lambda b: b.update(shares_source="yfinance sharesOutstanding"),
                   lambda b: b.update(pct_of_shares_out=8.91), lambda b: b.update(shares_outstanding=4859368)):
        b = copy.deepcopy(good)
        mutate(b)
        assert PR.smtk_check(b) != [], b
    later = copy.deepcopy(good)                                    # past the split's side no count is pinned
    later.update(settlement_date="2026-11-28", shares_outstanding=971874,
                 pct_of_shares_out=round(later["si_shares"] / 971874 * 100, 2))
    assert PR.smtk_check(later) == []


def test_the_probe_blocks_writes_before_any_read():
    src = (BACKEND / "scripts" / "si_share_basis_probe.py").read_text(encoding="utf-8")
    body = src[src.index("def main("):]
    assert body.index("block_writes()") < body.index("_get_db()") < body.index("run(")
    assert "www.sec.gov" not in src.split('"""', 2)[2]
