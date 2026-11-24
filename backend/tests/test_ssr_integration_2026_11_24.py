"""⛔ SSR tag — integration: the REAL exchange files and the REAL Massive bodies through the REAL modules (2026-11-24).

Ajay 2026-11-23, verbatim: "No shorting at the bid (SEC short-sale restriction)

Can we check or this for other stocks too?"

Spec rev 2 §4 main-session item 3. Nothing here is a stand-in for a module: the four files under tests/fixtures/ssr/
go through `ssr_lists.refresh_one` → `fetch` → `parse_nasdaq` / `parse_nyse` (biff_rows), the two bodies under
tests/fixtures/ssr_corp/ go through `ssr_corp.refresh_due`, both land in ONE in-memory collection, and
`ssr.payload(...)` reads it with `lists=None, corp=None` — the real `ssr_lists` and `ssr_corp`. Only the computed
half's docs (trig / day / judged) are written here, in the shape `ssr.record_pass` writes, with the §1.3 measured
numbers (GP 13:43 minute low 2.50 vs 2.81; PXED snapshot day low 17.39 vs 19.66). Names starting ZZ are SYNTHETIC.

Harness: every outside-call seam (`ssr_lists._http`, `sepa.prices._http`) is a RECORDING refuser asserted empty at
teardown; the Massive key resolver returns a synthetic key.
"""
from __future__ import annotations

import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from short_interest import ssr as SSR
from short_interest import ssr_corp as CA
from short_interest import ssr_lists as SL

BACKEND = Path(__file__).resolve().parents[1]
FIX = BACKEND / "tests" / "fixtures" / "ssr"
CFIX = BACKEND / "tests" / "fixtures" / "ssr_corp"
ET = ZoneInfo("America/New_York")
D20, D23, D24, D25 = date(2026, 11, 20), date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25)
KEY = "SYNTHKEYintegration"
DIV_URL = CA.BASE_URL + CA.DIVIDENDS_PATH
SPL_URL = CA.BASE_URL + CA.SPLITS_PATH


def et(d: date, h: int, m: int, s: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, s, tzinfo=ET)


def utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


MON_2209 = et(D23, 22, 9)          # the evening he asked
MON_1000 = et(D23, 10, 0)


# ═════════════════════════════════════════════ the ONE collection (every operation the three modules use)
class Coll:
    def __init__(self):
        self.docs = {}

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
                for k, v in (projection or {}).items():
                    if v == 0:
                        d.pop(k, None)
                out.append(d)
        return out

    def find_one(self, flt, *a, **k):
        for d in self.docs.values():
            if self._match(d, flt):
                return copy.deepcopy(d)
        return None

    def replace_one(self, flt, doc, upsert=False):
        assert set(flt) == {"_id"} and upsert is True
        self.docs[flt["_id"]] = copy.deepcopy(doc)

    def update_one(self, flt, upd, upsert=False):
        raise AssertionError("the read wrote: %s" % flt)

    def insert_many(self, docs, ordered=True):
        raise AssertionError("the read wrote")

    def create_index(self, keys, **kw):
        return "noop"


class DB:
    def __init__(self, coll):
        self.coll = coll

    def __getitem__(self, name):
        assert name == SL.SSR_COLL == "ssr_rule_201", name
        return self.coll


class Resp:
    def __init__(self, status_code, content=b"", headers=None, body=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self._body = body

    def json(self):
        return copy.deepcopy(self._body)


class FileHTTP:
    """requests.get-shaped: serves the fixture FILES by URL (ssr_lists.fetch)."""

    def __init__(self, answers):
        self.answers = answers
        self.urls = []

    def __call__(self, url, **kw):
        self.urls.append(url)
        return self.answers[url]


class BodySession:
    """Session-shaped: serves the two REAL Massive bodies by URL (ssr_corp._read_all)."""

    def __init__(self):
        self.calls = []
        self.answers = {DIV_URL: json.loads((CFIX / "massive_dividends_20261123.json").read_text(encoding="utf-8")),
                        SPL_URL: json.loads((CFIX / "massive_splits_20261123.json").read_text(encoding="utf-8"))}

    def get(self, url, **kw):
        self.calls.append((url, kw.get("params")))
        return Resp(200, body=self.answers[url])


# VERBATIM headers of the captures (ssr/*.hdr, 2026-11-23) — the same as test_ssr_lists_2026_11_24.py
FILES = {
    ("nasdaq", D20): ("nasdaq_shorthalts20261120.txt",
                      {"ETag": '"cfebd2633679dd1:0"', "Last-Modified": "Fri, 20 Nov 2026 21:30:40 GMT"}),
    ("nasdaq", D23): ("nasdaq_shorthalts20261123_preopen.txt",
                      {"ETag": '"8ae4a42c2b7bdd1:0"', "Last-Modified": "Mon, 23 Nov 2026 09:15:25 GMT"}),
    ("nyse", D20): ("nyse_ssr20261120.xls",
                    {"ETag": '"6b00ff90-fa00"', "Last-Modified": "Sat, 21 Nov 2026 02:18:56 GMT"}),
    ("nyse", D23): ("nyse_ssr20261123.xls",
                    {"ETag": '"6b04e32e-6600"', "Last-Modified": "Tue, 24 Nov 2026 01:06:54 GMT"}),
}


def hold_lists(coll, keys, now):
    """The real files through the real refresh_one → fetch → parse_* path."""
    answers = {}
    for k, d in keys:
        name, hdr = FILES[(k, d)]
        answers[SL.source_url(SL.source(k), d)] = Resp(200, (FIX / name).read_bytes(), hdr)
    http = FileHTTP(answers)
    for k, d in keys:
        st = SL.refresh_one(SL.source(k), d, coll, now, http=http)
        assert st["result"] == "found", (k, d, st)
    assert len(http.urls) == len(keys)
    return coll


def hold_corp(coll, now):
    s = BodySession()
    out = CA.refresh_due(coll, [D23], now, http=s)
    assert out["results"] == {"2026-11-23": "found"} and out["calls"] == 2
    return coll


# the computed half — the shape ssr.record_pass writes; numbers = spec §1.3 measured, ZZ = SYNTHETIC
def trig(T, sym, basis="snapshot", **kw):
    d = {"_id": "trig|%s|%s" % (T.isoformat(), sym), "kind": "trig", "date": T.isoformat(), "symbol": sym,
         "basis": basis, "created_at": utc_iso(et(T, 13, 45))}
    d.update(kw)
    return d


def entry(s, at, why=None, by="minute", pc=None, lo=None):
    return {"s": s, "why": why, "by": by, "pc": pc, "lo": lo, "mlo": lo, "drop_pct": None, "at": utc_iso(at)}


GP_TRIG_1123 = trig(D23, "GP", "minute_bar", at="13:43", low=2.50, drop_pct=-11.0, prev_close=2.81)
PXED_TRIG_1123 = trig(D23, "PXED", seen_at="10:05", prev_close=19.66, low=17.39, drop_pct=-11.5)


def computed_docs_evening():
    last = et(D23, 20, 0)
    day = {"_id": "day|2026-11-23", "kind": "day", "date": "2026-11-23", "last_ok_at": utc_iso(last),
           "n_rows": 12800, "n_usable": 12650, "n_trig": 2, "final": True,
           "names": {"GP": entry("on", last, pc=2.81, lo=2.50)}}
    judged = {"_id": "judged|2026-11-23", "kind": "judged", "date": "2026-11-23", "at": utc_iso(et(D23, 16, 5)),
              "off": "AAPL ZZOF", "unjudged": {"ZZLP": "late_print"}, "n_off": 2, "n_unjudged": 1}
    return [GP_TRIG_1123, PXED_TRIG_1123, day, judged]


def put(coll, docs):
    for d in docs:
        coll.docs[d["_id"]] = copy.deepcopy(d)
    return coll


def evening_coll(with_corp=True):
    coll = hold_lists(Coll(), [("nasdaq", D20), ("nasdaq", D23), ("nyse", D20), ("nyse", D23)], MON_2209)
    if with_corp:
        hold_corp(coll, MON_2209)
    return put(coll, computed_docs_evening())


EVENING_SYMS = ["GP", "AGL", "TOPP", "PXED", "ZZLP", "ZZNW", "AAPL"]


def read(coll, syms, now, **kw):
    SSR._reset_cache()
    SL._reset_cache()
    CA._reset_cache()
    return SSR.payload(syms, db=DB(coll), now=now, **kw)          # lists=None, corp=None → the REAL modules


@pytest.fixture(autouse=True)
def harness(monkeypatch):
    import massive_keys
    from sepa import prices
    calls = []

    def refuse_get(u=None, *a, **k):
        calls.append(("ssr_lists", u))
        raise RuntimeError("outside calls are refused in this file")

    class RefuseSession:
        def get(self, url, **kw):
            calls.append(("massive", url))
            raise RuntimeError("outside calls are refused in this file")

    monkeypatch.setattr(SL, "_http", refuse_get)
    monkeypatch.setattr(SL, "_bg", {"running": False, "last_start": None, "thread": None})
    monkeypatch.setattr(prices, "_http", lambda: RefuseSession())
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: KEY)
    for m in (SSR, SL, CA):
        m._reset_cache()
    yield calls
    t = SL._bg.get("thread")
    if t is not None:
        t.join(5)
    for m in (SSR, SL, CA):
        m._reset_cache()
    assert calls == [], "an outside call reached a seam: %s" % calls


# ═════════════════════════════════════════════ 2026-11-23 22:09 ET — the evening he asked
def test_evening_the_stored_shapes_came_from_the_real_files():
    coll = evening_coll()
    assert coll.docs["list|nasdaq|2026-11-23"]["stamp"] == "20261123041515"        # the 04:15 trap edition
    assert coll.docs["list|nasdaq|2026-11-23"]["final"] is False
    assert coll.docs["list|nasdaq|2026-11-20"]["final"] is True
    assert coll.docs["list|nyse|2026-11-23"]["n"] == 114
    assert coll.docs["corp|2026-11-23"]["n_div"] == 198 and coll.docs["corp|2026-11-23"]["n_split"] == 15
    assert KEY not in json.dumps(coll.docs)


def test_evening_states_and_whys():
    p = read(evening_coll(), EVENING_SYMS, MON_2209)
    assert p["status"] == "ok"
    assert p["session"]["in_play"] == ["2026-11-23"]
    assert p["states"] == {"GP": "on", "AGL": "on", "TOPP": "on", "PXED": "unknown", "ZZLP": "unknown",
                           "ZZNW": "unknown", "AAPL": "off"}
    assert p["whys"] == {"PXED": "corp_action", "ZZLP": "late_print", "ZZNW": "no_final_read"}
    assert p["refreshing"] is False


def test_evening_gp_is_computed_because_nasdaq_is_not_complete_for_1123():
    coll = evening_coll()
    loaded = SL.load(coll, MON_2209)
    assert SL.complete_for(loaded, D23) is False                                 # file(11/24) not held
    it = read(coll, ["GP"], MON_2209)["items"]["GP"]
    assert it["source"] == "computed" and it["time_basis"] == "minute_bar" and it["triggered_at_et"] == "13:43"
    assert it["triggered_on"] == "2026-11-23" and it["through"] == "2026-11-24"
    assert it["chip"] == "⛔ SSR · no shorting at the bid · thru Tue 11/24 · computed"
    assert it["short"] == "⛔ SSR thru 11/24 · computed"
    assert it["corp_checked"] is True and it["retriggered"] is False


def test_evening_agl_official_nyse_through_tue_and_the_exchange_deactivation_agrees():
    it = read(evening_coll(), ["AGL"], MON_2209)["items"]["AGL"]
    assert it["source"] == "official" and it["exchange"] == "NYSE"
    assert it["triggered_on"] == "2026-11-23" and it["triggered_at_et"] == "09:37:47"
    assert it["through"] == "2026-11-24" and it["off_from"] == "2026-11-25"
    assert it["chip"] == "⛔ SSR · no shorting at the bid · thru Tue 11/24"
    assert it["label"] == "⛔ SSR on · no shorting at the bid · through Tue 11/24 · NYSE list"
    rows, _sk = SL.parse_nyse((FIX / "nyse_ssr20261123.xls").read_bytes(), D23)
    agl = [r for r in rows if r[0] == "AGL"]
    assert agl and agl[0][4] == it["off_from"]                                 # Anticipated Deactivation Date


def test_evening_topp_official_nyse_american_a_split_never_voids_an_official_row():
    coll = evening_coll()
    assert CA.actions(CA.load(coll, [D23]), D23)["TOPP"] == "split"              # the real split row
    it = read(coll, ["TOPP"], MON_2209)["items"]["TOPP"]
    assert it["state"] == "on" and it["source"] == "official" and it["exchange"] == "NYSE American"
    assert it["triggered_at_et"] == "09:30:00" and it["through"] == "2026-11-24"
    assert "computed" not in it["chip"]


def test_NEGATIVE_evening_pxed_snapshot_trig_with_the_real_dividend_is_unknown_corp_action_no_chip():
    coll = evening_coll()
    assert CA.actions(CA.load(coll, [D23]), D23)["PXED"] == "dividend"           # the real 2.36 row
    p = read(coll, ["PXED"], MON_2209)
    assert p["states"]["PXED"] == "unknown" and p["whys"]["PXED"] == "corp_action"
    it = p["items"]["PXED"]
    assert it["chip"] is None and it["short"] is None and it["label"] == "⛔ SSR not read"
    assert "dividend or a split took effect on Mon 11/23" in it["title"]


def test_NEGATIVE_evening_pxed_without_the_corp_read_would_wear_a_computed_tag():
    """The contrast: the SAME trig with no corporate-action day read → on · computed, corp_checked false."""
    p = read(evening_coll(with_corp=False), ["PXED"], MON_2209, kick=False)   # a due corp day would kick the worker
    it = p["items"]["PXED"]
    assert p["states"]["PXED"] == "on" and it["source"] == "computed" and it["corp_checked"] is False


def test_NEGATIVE_evening_a_name_in_judged_unjudged_is_unknown_with_that_why():
    p = read(evening_coll(), ["ZZLP"], MON_2209)
    assert p["states"]["ZZLP"] == "unknown" and p["whys"]["ZZLP"] == "late_print"
    it = p["items"]["ZZLP"]
    assert it["chip"] is None and it["short"] is None and it["label"] == "⛔ SSR not read"


def test_NEGATIVE_evening_a_name_on_neither_list_and_in_neither_judged_set_is_unknown_never_off():
    p = read(evening_coll(), ["ZZNW", "AAPL"], MON_2209)
    assert p["states"]["ZZNW"] == "unknown" and p["whys"]["ZZNW"] == "no_final_read"
    assert p["items"]["ZZNW"]["chip"] is None
    assert p["states"]["AAPL"] == "off" and "AAPL" not in p["items"]            # only judged.off proves off


def test_evening_sources_rows_read_the_real_editions():
    p = read(evening_coll(), ["GP"], MON_2209)
    by = {s["key"]: s for s in p["sources"]}
    assert set(by) == {"nasdaq", "nyse", "corp_actions"}
    assert by["nasdaq"]["edition_et"] == "04:15" and by["nasdaq"]["final"] is False
    assert by["nasdaq"]["text"] == ("Nasdaq short sale list for 11/23 · edition 04:15 ET · 1092 rows"
                                    " (today's triggers not in it yet)")
    assert by["nyse"]["text"] == "NYSE Group short sale list for 11/23 · edition 20:06 ET · 114 rows"
    assert by["corp_actions"]["text"] == "dividends and splits of 11/23 read · 209 names"
    assert p["computed"]["final"] is True


# ═════════════════════════════════════════════ 2026-11-23 10:00 ET — GP's Friday trigger, official
def morning_coll():
    coll = hold_lists(Coll(), [("nasdaq", D20), ("nasdaq", D23), ("nyse", D20)], MON_1000)
    at = et(D23, 9, 55)
    return put(coll, [{"_id": "day|2026-11-23", "kind": "day", "date": "2026-11-23", "last_ok_at": utc_iso(at),
                       "n_rows": 12800, "n_usable": 12650, "n_trig": 0,
                       "names": {"GP": entry("off", at, pc=2.81, lo=2.70)}}])


def test_morning_gp_on_official_triggered_fri_0945_through_mon():
    p = read(morning_coll(), ["GP"], MON_1000, kick=False)                    # 10:00: the corp day is due → no worker here
    assert p["session"]["in_play"] == ["2026-11-23", "2026-11-20"]
    it = p["items"]["GP"]
    assert p["states"]["GP"] == "on" and it["source"] == "official" and it["exchange"] == "Nasdaq"
    assert it["triggered_on"] == "2026-11-20" and it["triggered_at_et"] == "09:45:36"
    assert it["through"] == "2026-11-23" and it["off_from"] == "2026-11-24"
    assert it["chip"] == "⛔ SSR · no shorting at the bid · thru Mon 11/23"
    assert "file stamped 11/23 04:15:15 ET" in it["title"]                     # the newest file's copy of the row


def test_NEGATIVE_morning_agl_is_not_on_before_nyse_publishes_its_1123_file():
    p = read(morning_coll(), ["AGL"], MON_1000, kick=False)
    assert p["states"]["AGL"] != "on" and "AGL" not in {k for k, v in p["items"].items() if v.get("state") == "on"}


# ═════════════════════════════════════════════ C4 — Nasdaq completes T only with file(next T)
def test_C4_the_1630_edition_never_completes_its_own_day_the_next_pre_open_file_does():
    coll = hold_lists(Coll(), [("nasdaq", D20), ("nyse", D20)], MON_1000)
    assert coll.docs["list|nasdaq|2026-11-20"]["stamp"] == "20261120163031"
    assert coll.docs["list|nasdaq|2026-11-20"]["final"] is True                # final ≠ complete
    assert SL.complete_for(SL.load(coll, MON_1000), D20) is False
    hold_lists(coll, [("nasdaq", D23)], MON_1000)
    SL._reset_cache()
    assert SL.complete_for(SL.load(coll, MON_1000), D20) is True


def test_NEGATIVE_C4_the_next_nasdaq_file_without_nyses_file_is_not_complete():
    coll = hold_lists(Coll(), [("nasdaq", D20), ("nasdaq", D23)], MON_1000)
    assert SL.complete_for(SL.load(coll, MON_1000), D20) is False
