"""🔗 Leveraged-ETF map (sepa/levered_etf.py) — the parser, the Mongo-cached
map, the refresh, the claim and the served words (2026-10-14).

Ajay 2026-10-14, verbatim: "Can you add a short tag on these stocks for their
Leverage equivalents like IRE for IREN, VSTL for VST".

Both of his examples resolve from DATA (the planner's read-only Massive probe,
tests/fixtures/levered_etf_reference_2026_10_14.json: 49 real funds, 22 real
stocks, the 10-14 grouped prints): IRE is "Defiance Daily Target 2X Long IREN
ETF", filed as type ETS — an ETF-only pull misses it (pinned below) — and VSTL
is "Defiance Daily Target 2X Long VST ETF". No ticker is typed in the module.
Hermetic: every HTTP call and every Mongo call goes to a double here.
"""
from __future__ import annotations

import ast
import copy
import json
import logging
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from sepa import levered_etf as LE

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
FIXTURE = BACKEND / "tests" / "fixtures" / "levered_etf_reference_2026_10_14.json"
MODULE = BACKEND / "sepa" / "levered_etf.py"
NOW = datetime(2026, 10, 15, 10, 0, tzinfo=ET)           # Thursday; last closed session 10-14
KEY = "SeCrEtKeY_123-abc"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    LE._reset_for_tests()
    spawned = []
    monkeypatch.setattr(LE, "_spawn", lambda target, name: spawned.append((target, name)))
    yield spawned
    LE._reset_for_tests()


def _fx() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _built(**kw):
    f = _fx()
    return LE.build_rows(kw.get("funds", f["funds"]), LE.stocks_from(f["stocks"]), kw.get("grouped", f["grouped"]))


def _by(rows):
    return LE.by_underlying(rows)


# --------------------------------------------------------------------------
# doubles
# --------------------------------------------------------------------------
def _match(doc: dict, flt: dict) -> bool:
    for k, v in flt.items():
        if k == "$or":
            if not any(_match(doc, f) for f in v):
                return False
            continue
        if isinstance(v, dict):
            for op, x in v.items():
                if op == "$ne" and doc.get(k) == x:
                    return False
                if op == "$exists" and (k in doc) is not x:
                    return False
                if op == "$lt" and not (k in doc and doc[k] < x):
                    return False
        elif doc.get(k) != v:
            return False
    return True


class _Coll:
    def __init__(self, doc=None, *, raise_on=None):
        self.docs = {} if doc is None else {doc["_id"]: copy.deepcopy(doc)}
        self.writes = []
        self.raise_on = raise_on or set()

    def _maybe(self, op):
        if op in self.raise_on:
            raise RuntimeError(f"mongo {op} down")

    def find_one(self, flt, proj=None):
        self._maybe("find_one")
        d = self.docs.get(flt.get("_id"))
        return copy.deepcopy(d) if d is not None else None

    def replace_one(self, flt, doc, upsert=False):
        self._maybe("replace_one")
        self.writes.append(("replace_one", copy.deepcopy(doc)))
        self.docs[flt["_id"]] = copy.deepcopy(doc)

    def update_one(self, flt, upd, upsert=False):
        self._maybe("update_one")
        self.writes.append(("update_one", copy.deepcopy(upd)))
        d = self.docs.get(flt["_id"])
        if d is not None and _match(d, flt):
            d.update(copy.deepcopy(upd.get("$set") or {}))
            return SimpleNamespace(modified_count=1)
        if d is None and upsert:
            self.docs[flt["_id"]] = {"_id": flt["_id"], **copy.deepcopy(upd.get("$set") or {})}
        return SimpleNamespace(modified_count=0)

    def insert_one(self, doc):
        from pymongo.errors import DuplicateKeyError
        self.writes.append(("insert_one", copy.deepcopy(doc)))
        if doc["_id"] in self.docs:
            raise DuplicateKeyError("E11000 duplicate key")
        self.docs[doc["_id"]] = copy.deepcopy(doc)


class _DB:
    def __init__(self, coll=None):
        self.coll = coll or _Coll()
        self.names = []

    def __getitem__(self, name):
        self.names.append(name)
        return self.coll


class _Resp:
    def __init__(self, code, body=None):
        self.status_code, self._body = code, body or {}

    def json(self):
        return self._body


class _Http:
    """The Massive reference + grouped endpoints over the fixture: each type in
    pages of `per_page` with a `next_url` cursor; `fail` = {"ETF:1": 500 |
    Exception} breaks one page, {"grouped": …} the grouped read."""

    def __init__(self, fx=None, *, per_page=10, fail=None):
        fx = fx or _fx()
        self.by_type = {}
        for r in fx["funds"] + fx["stocks"]:
            self.by_type.setdefault(r["type"], []).append({**r, "active": True})
        self.grouped = fx["grouped"]
        self.per_page, self.fail, self.calls = per_page, fail or {}, []

    def _fail(self, k, url):
        f = self.fail.get(k)
        if isinstance(f, Exception):
            raise type(f)(f"{f} {url}?apiKey={KEY} (key {KEY})")
        return _Resp(f) if f else None

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if url.startswith(LE.GROUPED_URL_FMT.split("{")[0]):
            bad = self._fail("grouped", url)
            if bad:
                return bad
            return _Resp(200, {"results": [{"T": t, "v": g[0], "vw": g[1], "c": g[2]}
                                           for t, g in self.grouped.items()]})
        if "cursor=" in url:
            t, i = url.split("cursor=")[1].split(":")
            i = int(i)
        else:
            t, i = params["type"], 0
        bad = self._fail(f"{t}:{i}", url)
        if bad:
            return bad
        rows = self.by_type.get(t, [])
        page = rows[i * self.per_page:(i + 1) * self.per_page]
        more = (i + 1) * self.per_page < len(rows)
        return _Resp(200, {"results": page,
                           "next_url": f"{LE.REF_URL}?cursor={t}:{i + 1}" if more else None})


def _doc(as_of="2026-10-15", grouped_day="2026-10-14", **kw):
    rows, counts = _built()
    d = {"_id": LE.DOC_ID, "as_of": as_of, "grouped_day": grouped_day, "complete": True, "rows": rows,
         "counts": counts, "attempted_on": as_of, "attempted_at": 1.0}
    d.update(kw)
    return d


# --------------------------------------------------------------------------
# 1 — fixture parity (his two examples resolve by DATA)
# --------------------------------------------------------------------------
def test_01_fixture_parity_iren_vst_nbis_tsla_and_totals():
    rows, c = _built()
    by = _by(rows)
    assert [x["etf"] for x in by["IREN"]] == ["IRE", "IREX", "IREG", "IREZ"]
    ire = next(x for x in rows if x["etf"] == "IRE")
    assert ire["type"] == "ETS" and ire["factor"] == 2.0 and ire["direction"] == "long"
    assert [x["etf"] for x in by["VST"]] == ["VSTL"]
    assert [x["etf"] for x in by["NBIS"]] == ["NBIL", "NBIG", "NEBX", "NBIZ"]
    assert len(by["TSLA"]) == 8
    assert c["tagged"] == 31 and c["underlyings"] == 14 and c["funds_read"] == 49
    assert c["by_ticker"] + c["by_name"] == c["tagged"]
    assert set(c) == set(LE.COUNT_KEYS)


def test_01b_NEG_an_etf_only_pull_misses_IRE_the_trap_that_hid_it(monkeypatch):
    monkeypatch.setattr(LE, "FUND_TYPES", ("ETF",))
    rows, _c = _built()
    assert "IRE" not in {x["etf"] for x in rows}
    assert [x["etf"] for x in _by(rows)["IREN"]] == ["IREX", "IREG", "IREZ"]


def test_01c_NEG_no_ticker_is_typed_in_the_module_the_map_is_data():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    consts = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for t in ("IRE", "IREX", "IREG", "IREZ", "IREC", "VSTL", "NBIL", "NBIG", "NEBX", "NBIZ", "TSLL"):
        assert t not in consts, t
    # the CLI prints his names' lines but never maps them
    assert not any(isinstance(n, ast.Dict) and any(isinstance(k, ast.Constant) and k.value in ("IREN", "VST")
                                                   for k in n.keys) for n in ast.walk(tree))


def test_01d_NEG_the_computed_task_example_appears_nowhere():
    bad = "IR" + "NX"
    assert bad not in MODULE.read_text(encoding="utf-8")
    assert bad not in FIXTURE.read_text(encoding="utf-8")
    rows, _c = _built()
    assert bad not in {x["etf"] for x in rows}


# --------------------------------------------------------------------------
# 2 — an unknown pattern never produces a tag (each reason counted)
# --------------------------------------------------------------------------
def _one(name, stocks, *, etf="ZZZX", grouped=None, type_="ETF"):
    rows, c = LE.build_rows([{"ticker": etf, "name": name, "type": type_}], stocks,
                            {etf: [1000, 10.0, 10.0]} if grouped is None else grouped)
    return rows, c


@pytest.mark.parametrize("name,stocks,reason", [
    ("Corgi IREN 2x Daily ETF", {"IREN": "IREN Limited Ordinary Shares"}, "no_direction"),
    ("T-Rex 2X Long Bitcoin Daily Target ETF", {"ABTC": "American Bitcoin Corp. Class A Common Stock"},
     "no_us_underlying"),
    ("21Shares 2x Long Sui ETF", {"SUIG": "Sui Group Holdings Limited Common Stock"}, "no_us_underlying"),
    ("T-Rex 2X Long Alphabet Daily Target ETF", {"GOOG": "Alphabet Inc. Class C Capital Stock",
                                                 "GOOGL": "Alphabet Inc. Class A Common Stock"}, "ambiguous_name"),
    ("Direxion Daily AMD Bear 1X ETF", {"AMD": "Advanced Micro Devices"}, "one_x"),
    ("MicroSectors U.S. Big Banks -3x Inverse Leveraged ETNs", {"BAC": "Bank of America Corp"}, "no_slot"),
    ("Direxion Daily BRKB Bull 2X", {"BRK.B": "BERKSHIRE HATHAWAY Class B"}, "no_us_underlying"),
    ("Tradr 2X Long IREN Short NBIS Daily ETF", {"IREN": "IREN Limited", "NBIS": "Nebius Group N.V."},
     "both_directions"),
    ("Acme 2x and 3x Long IREN Daily ETF", {"IREN": "IREN Limited"}, "multi_factor"),
    ("Acme 2X Long IREN NBIS Bull ETF", {"IREN": "IREN Limited", "NBIS": "Nebius Group N.V."},
     "ambiguous_ticker"),
    ("Direxion Daily S&P 500 Bull 3X Shares", {"S": "SentinelOne", "SPY": "x"}, "no_us_underlying"),
    ("Direxion Daily S&P 500 Bear 3X Shares", {"S": "SentinelOne", "SPY": "x"}, "no_us_underlying"),
])
def test_02_NEG_unknown_patterns_are_counted_never_tagged(name, stocks, reason):
    rows, c = _one(name, stocks)
    assert rows == [] and c["tagged"] == 0
    assert c[reason] == 1 and sum(c[k] for k in LE.SKIP_REASONS) == 1


def test_02b_NEG_a_non_leveraged_fund_never_gets_a_row_or_a_count():
    rows, c = _one("Acme Momentum ETF", {"ACME": "Acme Inc."})
    assert rows == [] and c["funds_read"] == 1 and c["with_factor"] == 0
    assert sum(c[k] for k in LE.SKIP_REASONS) == 0
    assert LE.parse_name("SPY", "SPDR S&P 500 ETF Trust", {}, {})[0] == "no_factor"


def test_02c_NEG_an_all_caps_name_never_reads_its_words_as_tickers():
    # UGLD trap: "GOLD" would be Gold.com's ticker beside "BULL"
    rows, c = _one("DIREXION DAILY GOLD BULL 2X ETF", {"GOLD": "Gold.com, Inc."}, etf="UGLD")
    assert rows == [] and c["no_us_underlying"] == 1


def test_02d_NEG_grammar_words_never_match_a_symbol():
    # real word-like tickers (ETF-ish words) never match outside the direction slot
    stocks = {"ETF": "Etf Corp", "AND": "And Inc", "DAILY": "Daily Inc", "LONG": "Long Corp",
              "TARGET": "Target Corp", "BULL": "Webull Corporation Class A Ordinary Shares"}
    for name in ("Acme 2X Long Daily ETF", "Defiance Daily Target 2X Long ETF", "Acme ETF and 2x Long Fund",
                 "Acme 2X Long AND Daily ETF", "Acme 2X Short TARGET Daily ETF", "Acme 2X Inverse LONG ETF"):
        rows, _c = _one(name, stocks)
        assert rows == [], name
    # … while word-like tickers that ARE stocks still tag in the slot (BULL = Webull -> BULG, real 10-14)
    rows, _c = _built()
    assert {(x["etf"], x["underlying"]) for x in rows} >= {("BULG", "BULL"), ("ETNG", "ETN"), ("PUL", "P"),
                                                           ("UNX", "U")}
    assert LE.parse_name("SPCL", "Defiance Daily 2X Space ETF", {"SPCX": "Space Exploration"}, {})[1] is None


# 2026-10-14 review: each coin fund name below mapped to a real US stock on the
# 10-14 CS/ADRC list before COIN_SYMBOLS (ticker slot, then name slot).
COIN_CASES = [
    ("T-REX 2X Long LINK Daily Target ETF", {"LINK": "Interlink Electronics, Inc. Common Stock"}),
    ("T-Rex 2X Long TRX Daily Target ETF", {"TRX": "TRX Gold Corporation Common Shares"}),
    ("21Shares 2x Long SUI ETF", {"SUI": "Sun Communities, Inc. Common Stock"}),
    ("Defiance Daily Target 2X Long LTC ETF", {"LTC": "LTC Properties, Inc. Common Stock"}),
    ("Defiance Daily Target 2X Long SEI ETF", {"SEI": "Solaris Energy Infrastructure, Inc. Class A"}),
    ("21Shares 2x Long ATOM ETF", {"ATOM": "Atomera Incorporated Common Stock"}),
    ("21Shares 2x Long APT ETF", {"APT": "Alpha Pro Tech, Ltd. Common Stock"}),
    ("T-Rex 2X Long Tron Daily Target ETF", {"TRON": "Tron Inc. Common Stock"}),
    ("T-Rex 2X Long Bonk Daily Target ETF", {"BNKK": "Bonk, Inc. Common Stock"}),
    ("21Shares 2x Short LINK ETF", {"LINK": "Interlink Electronics, Inc. Common Stock"}),
]


@pytest.mark.parametrize("name,stocks", COIN_CASES)
def test_02h_NEG_a_coin_fund_never_tags_the_stock_sharing_its_symbol(name, stocks):
    rows, c = _one(name, stocks)
    assert rows == [] and c["tagged"] == 0 and c["no_us_underlying"] == 1, name


def test_02h_NEG_coin_set_is_closed_and_covers_every_case():
    assert LE.COIN_SYMBOLS == frozenset({"LINK", "TRX", "SUI", "LTC", "SEI", "ATOM", "APT", "TRON", "BONK"})
    assert not (LE.COIN_SYMBOLS & LE.NEVER_TICKER_WORDS)
    # control: the same shape on a non-coin ticker still tags (the block is the coin set, not the shape)
    rows, _c = _one("T-REX 2X Long IREN Daily Target ETF", {"IREN": "IREN Limited Ordinary Shares"})
    assert [(x["underlying"], x["factor"], x["direction"]) for x in rows] == [("IREN", 2.0, "long")]


def test_02i_the_ready_line_parts_sum_to_every_untagged_fund():
    c = {k: 0 for k in LE.COUNT_KEYS}
    c.update(with_factor=365 + 312, tagged=365, underlyings=200, no_direction=157, one_x=23,
             no_us_underlying=119, no_slot=12, ambiguous_name=1)
    assert sum(c[k] for k in LE.SKIP_REASONS) == c["with_factor"] - c["tagged"]
    assert LE.untagged_other(c) == 132
    line = LE.status_block({"state": "ready", "counts": c, "as_of": "2026-10-14", "grouped_day": "2026-10-13"},
                           n_on=1, listed=2)["line"]
    assert "157 with no direction" in line and "23 1× inverse" in line and "132 index, sector" in line
    assert 157 + 23 + 132 == c["with_factor"] - c["tagged"]
    # every skip reason not printed alone folds in; nothing is double-counted or dropped
    for k in LE.SKIP_REASONS:
        one = {**{x: 0 for x in LE.COUNT_KEYS}, k: 1}
        assert LE.untagged_other(one) == (0 if k in LE.LINE_SPLIT else 1), k
    assert LE.untagged_other(None) == 0 and LE.untagged_other({"no_slot": None}) == 0


def test_02i_NEG_built_fixture_line_tally_equals_with_factor_minus_tagged():
    rows, c = _built()
    printed = c["no_direction"] + c["one_x"] + LE.untagged_other(c)
    assert printed == c["with_factor"] - c["tagged"]


def test_02e_NEG_a_fund_naming_its_own_ticker_is_never_self_mapped():
    rows, c = _one("Tradr 2X Long XYZL Daily ETF", {"XYZL": "Xyzl Inc."}, etf="XYZL")
    assert rows == [] and c["no_us_underlying"] == 1


@pytest.mark.parametrize("grouped", [{}, {"ZZZX": [0, 10.0, 10.0]}, {"ZZZX": [None, None, None]}])
def test_02f_NEG_no_print_on_the_last_session_is_counted_not_served(grouped):
    rows, c = _one("Tradr 2X Long IREN Daily ETF", {"IREN": "IREN Limited"}, grouped=grouped)
    assert rows == [] and c["no_print"] == 1 and c["tagged"] == 0


def test_02g_NEG_corgi_no_direction_is_untagged_by_default_in_the_fixture():
    rows, c = _built()
    assert "IREC" not in {x["etf"] for x in rows} and "NBIC" not in {x["etf"] for x in rows}
    assert c["no_direction"] == 5 and c["one_x"] == 2                 # AMDD + TSLS


# --------------------------------------------------------------------------
# 3 — positive edges, one per issuer pattern
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name,stocks,want", [
    ("Tradr 2X Long IREN Daily ETF", {"IREN": "IREN Limited Ordinary Shares"}, ("IREN", 2.0, "long", "ticker")),
    ("Leverage Shares 2X Long IREN Daily ETF", {"IREN": "IREN Limited"}, ("IREN", 2.0, "long", "ticker")),
    ("GraniteShares 2x Long NBIS Daily ETF", {"NBIS": "Nebius Group N.V."}, ("NBIS", 2.0, "long", "ticker")),
    ("Defiance Daily Target 2X Long VST ETF", {"VST": "Vistra Corp."}, ("VST", 2.0, "long", "ticker")),
    ("Direxion Daily SOFI Bull 2X ETF", {"SOFI": "SoFi Technologies, Inc."}, ("SOFI", 2.0, "long", "ticker")),
    ("Tradr 2X Short IREN Daily ETF", {"IREN": "IREN Limited"}, ("IREN", 2.0, "short", "ticker")),
    ("T-REX 2X Long Tesla Daily Target ETF", {"TSLA": "Tesla, Inc. Common Stock"}, ("TSLA", 2.0, "long", "name")),
    ("T-Rex 2X Long NVIDIA Daily Target ETF", {"NVDA": "Nvidia Corp"}, ("NVDA", 2.0, "long", "name")),
    ("T-Rex 2X Inverse NVIDIA Daily Target ETF", {"NVDA": "Nvidia Corp"}, ("NVDA", 2.0, "short", "name")),
    ("GraniteShares 1.25x Long TSLA  Daily ETF", {"TSLA": "Tesla, Inc."}, ("TSLA", 1.25, "long", "ticker")),
    ("Acme -3x Inverse TSLA Daily ETN", {"TSLA": "Tesla, Inc."}, ("TSLA", 3.0, "short", "ticker")),
    ("Tradr 2X Long U Daily ETF", {"U": "Unity Software Inc."}, ("U", 2.0, "long", "ticker")),
    ("GraniteShares 2x Long P Daily ETF", {"P": "Everpure, Inc."}, ("P", 2.0, "long", "ticker")),
])
def test_03_issuer_patterns_tag_the_stock(name, stocks, want):
    rows, c = _one(name, stocks)
    assert len(rows) == 1 and c["tagged"] == 1
    r = rows[0]
    assert (r["underlying"], r["factor"], r["direction"], r["rule"]) == want
    assert r["etf"] == "ZZZX" and r["dollar_vol"] == 10000


def test_03b_an_ets_fund_is_read_and_a_class_share_maps_to_the_dash_form():
    rows, _c = _one("Direxion Daily ADBE Bull 2X ETF", {"ADBE": "Adobe Inc."}, type_="ETS")
    assert rows[0]["underlying"] == "ADBE" and rows[0]["type"] == "ETS"
    rows, _c = _one("Direxion Daily BRK.B Bull 2X ETF", {"BRK.B": "BERKSHIRE HATHAWAY Class B"})
    assert rows[0]["underlying"] == "BRK-B"


def test_03c_corgi_as_his_call_tags_IREC_long(monkeypatch):
    monkeypatch.setattr(LE, "NO_DIRECTION_LONG_ISSUERS", ("Corgi",))
    rows, _c = _built()
    irec = next(x for x in rows if x["etf"] == "IREC")
    assert irec["underlying"] == "IREN" and irec["direction"] == "long" and irec["factor"] == 2.0


def test_03d_core_name_strips_trailing_corporate_forms_only():
    assert LE.core_name("Nvidia Corp") == "nvidia"
    assert LE.core_name("Tesla, Inc. Common Stock") == "tesla"
    assert LE.core_name("American Bitcoin Corp. Class A Common Stock") == "american bitcoin"
    assert LE.core_name("Sui Group Holdings Limited Common Stock") == "sui group holdings"


# --------------------------------------------------------------------------
# 4 — order and the chip
# --------------------------------------------------------------------------
def _it(etf, f=2.0, d="long", dv=0, name=None):
    return {"etf": etf, "factor": f, "direction": d, "dollar_vol": dv, **({"name": name} if name else {})}


def test_04_order_long_first_factor_desc_dollars_desc_then_ticker():
    items = [_it("S1", 2.0, "short", 9e9), _it("B", 2.0, "long", 5), _it("A", 2.0, "long", 5),
             _it("L3", 3.0, "long", 1), _it("BIG", 2.0, "long", 9e8)]
    assert [x["etf"] for x in LE.order(items)] == ["L3", "BIG", "A", "B", "S1"]


def test_04b_chip_texts_for_1_3_4_and_9_items():
    rows, _c = _built()
    by = _by(rows)
    assert LE.chip(by["VST"])["text"] == "\U0001F517 2× VSTL"
    c = LE.chip(by["IREN"])
    assert c["text"] == "\U0001F517 2× IRE · IREX · IREG +1"
    assert c["shown"] == ["IRE", "IREX", "IREG"] and c["more"] == 1 and c["rest"] == "IREZ −2×"
    assert c["parts"][-1] == {"text": " +1", "title": "IREZ −2×"}
    assert next(p for p in c["parts"] if p.get("etf") == "IRE")["title"] == "Defiance Daily Target 2X Long IREN ETF"
    assert LE.chip(by["NBIS"])["text"] == "\U0001F517 2× NBIL · NBIG · NEBX +1"
    assert LE.chip(by["TSLA"])["text"] == "\U0001F517 2× TSLL · TSLG · TSLT +5"
    three = LE.chip([_it("A"), _it("B"), _it("C")])
    assert three["text"] == "\U0001F517 2× A · B · C" and three["more"] == 0 and three["rest"] is None
    nine = LE.chip([_it(f"X{i}") for i in range(9)])
    assert nine["text"].endswith(" +6") and nine["more"] == 6 and len(nine["rest"].split(" · ")) == 6
    for ch in (c, three, nine):
        assert "".join(p.get("text", p.get("etf")) for p in ch["parts"]) == ch["text"]


def test_04c_mixed_factors_and_shorts_only():
    c = LE.chip([_it("A", 2.0), _it("B", 1.25), _it("C", 2.0, "short")])
    assert c["text"] == "\U0001F517 2× A · 1.25× B · −2× C"
    assert LE.chip([_it("XXXX", 2.0, "short")])["text"] == "\U0001F517 −2× XXXX"
    assert LE.factor_text(2.0, "short") == "−2×" and LE.factor_text(1.25) == "1.25×"
    assert LE._MINUS == "−"


def test_04d_NEG_include_shorts_off_drops_shorts_everywhere(monkeypatch):
    rows, _c = _built()
    monkeypatch.setattr(LE, "INCLUDE_SHORTS", False)
    c = LE.chip(_by(rows)["IREN"])
    assert c["text"] == "\U0001F517 2× IRE · IREX · IREG" and c["more"] == 0 and c["rest"] is None
    assert "IREZ" not in LE.stat_value(_by(rows)["IREN"])
    assert LE.chip([_it("XXXX", 2.0, "short")]) is None


def test_04e_NEG_no_items_no_chip_no_stat():
    assert LE.chip([]) is None and LE.chip(None) is None and LE.stat_value([]) is None
    assert LE.chip([{"factor": 2.0}]) is None                                  # no etf = no item
    rows, _c = _built()
    assert LE.stat_value(_by(rows)["IREN"]) == "IRE 2× · IREX 2× · IREG 2× · IREZ −2×"


# --------------------------------------------------------------------------
# 5 — load states (never raise, never fetch)
# --------------------------------------------------------------------------
def test_05_age_7_is_ready_and_8_is_stale():
    db = _DB(_Coll(_doc(as_of="2026-10-08")))
    s = LE.load(now=NOW, db=db, ensure=False)
    assert s["state"] == "ready" and s["age_days"] == 7
    assert [x["etf"] for x in LE.for_symbol(s, "IREN")] == ["IRE", "IREX", "IREG", "IREZ"]
    assert LE.for_symbol(s, "iren")[0] == {"etf": "IRE", "factor": 2.0, "direction": "long"}
    blk = LE.status_block(s, n_on=2, listed=10)
    assert blk["line"].startswith("\U0001F517 Leveraged-ETF tags: 2 of these 10 names") and blk["legend"]
    assert "31 funds on 14 stocks" in blk["line"] and "as of 10-08" in blk["line"]
    db = _DB(_Coll(_doc(as_of="2026-10-07")))
    s = LE.load(now=NOW, db=db, ensure=False)
    assert s["state"] == "stale" and s["age_days"] == 8
    assert LE.for_symbol(s, "IREN") == [] and LE.items_for(s, "IREN") == []
    blk = LE.status_block(s, n_on=5, listed=10)
    assert blk["n_on"] == 0 and blk["legend"] is None
    assert "hidden" in blk["line"] and "8 days ago" in blk["line"] and f"past {LE.STALE_DAYS} days" in blk["line"]


def test_05b_NEG_missing_error_and_no_database_never_raise_and_tag_nothing(monkeypatch):
    s = LE.load(now=NOW, db=_DB(), ensure=False)
    assert s["state"] == "missing" and LE.for_symbol(s, "IREN") == []
    assert LE.status_block(s, n_on=0, listed=3)["line"] == LE.LINE_MISSING
    s = LE.load(now=NOW, db=_DB(_Coll(raise_on={"find_one"})), ensure=False)
    assert s["state"] == "error" and LE.for_symbol(s, "IREN") == []
    assert "could not be read (mongo find_one down)" in LE.status_block(s, n_on=0, listed=3)["line"]
    monkeypatch.setattr(LE, "_db", lambda db=None: None)
    s = LE.load(now=NOW)
    assert s["state"] == "missing" and s["reason"] == LE.NO_DB_REASON
    assert "could not be read (no database)" in LE.status_block(s, n_on=0, listed=3)["line"]
    assert LE.status_block(None, n_on=1, listed=1)["state"] == "error"
    assert LE.status_block({"state": "ready", "counts": "junk"}, n_on=1, listed=1)["line"]


def test_05c_NEG_the_default_db_under_the_hermetic_stub_is_missing_and_starts_no_thread(_clean):
    s = LE.load(now=NOW)
    assert s["state"] == "missing" and _clean == []


def test_05d_load_memoises_the_default_database_read(monkeypatch):
    db = _DB(_Coll(_doc()))
    monkeypatch.setattr(LE, "_db", lambda d=None: d if d is not None else db)
    LE.load(now=NOW)
    LE.load(now=NOW)
    assert db.names.count(LE.COLL) == 1
    LE._reset_for_tests()
    LE.load(now=NOW)
    assert db.names.count(LE.COLL) == 2


def test_05e_NEG_load_never_fetches_it_starts_one_thread_for_an_old_map(monkeypatch, _clean):
    def boom(*a, **k):
        raise AssertionError("load fetched Massive")
    monkeypatch.setattr(LE, "fetch_reference", boom)
    monkeypatch.setattr(LE, "fetch_grouped", boom)
    db = _DB(_Coll(_doc(as_of="2026-10-14")))
    s = LE.load(now=NOW, db=db)
    assert s["state"] == "ready" and len(_clean) == 1                       # spawned, not run
    s2 = LE.load(now=NOW, db=db)
    assert s2["state"] == "ready" and len(_clean) == 1                      # one refresh, never two


# --------------------------------------------------------------------------
# 6 — refresh
# --------------------------------------------------------------------------
def test_06_a_complete_read_replaces_the_doc():
    db = _DB(_Coll(_doc(as_of="2026-10-10", rows=[{"etf": "OLD", "underlying": "OLDX"}])))
    http = _Http()
    res = LE.refresh(now=NOW, db=db, http=http, key=KEY)
    assert res["ok"] is True and res["complete"] is True and res["as_of"] == "2026-10-15"
    assert res["counts"]["tagged"] == 31 and res["calls"] == len(http.calls)
    d = db.coll.docs[LE.DOC_ID]
    assert d["as_of"] == "2026-10-15" and d["grouped_day"] == "2026-10-14" and d["complete"] is True
    assert "OLD" not in {r["etf"] for r in d["rows"]} and len(d["rows"]) == 31
    assert any("/2026-10-14" in u for u, _p in http.calls)                   # the last closed session
    first = [p for u, p in http.calls if u == LE.REF_URL]
    assert {p["type"] for p in first} == set(LE.FUND_TYPES + LE.STOCK_TYPES)
    assert all(p["limit"] == LE.PAGE_LIMIT and p["active"] == "true" for p in first)
    nexts = [p for u, p in http.calls if "cursor=" in u]
    assert nexts and all(p == {"apiKey": KEY} for p in nexts)               # the key re-sent alone


@pytest.mark.parametrize("fail,budget", [({"ETF:1": 500}, None), ({"CS:0": RuntimeError("conn reset")}, None),
                                         ({"grouped": 500}, None), ({}, -1)])
def test_06b_NEG_a_partial_read_keeps_the_old_map(monkeypatch, fail, budget):
    if budget is not None:
        monkeypatch.setattr(LE, "REFRESH_BUDGET_SEC", budget)
    old = _doc(as_of="2026-10-12")
    db = _DB(_Coll(old))
    res = LE.refresh(now=NOW, db=db, http=_Http(fail=fail), key=KEY)
    assert res["complete"] is False and res["ok"] is False and res["as_of"] == "2026-10-12"
    d = db.coll.docs[LE.DOC_ID]
    assert d["as_of"] == "2026-10-12" and d["rows"] == old["rows"]
    assert d["last_error_at"] and isinstance(d["last_partial"], dict)
    assert not any(op == "replace_one" for op, _x in db.coll.writes)


def test_06c_NEG_the_key_never_reaches_a_log_an_exception_or_the_doc(caplog):
    caplog.set_level(logging.DEBUG)
    db = _DB(_Coll(_doc(as_of="2026-10-12")))
    fail = {"ETF:0": ConnectionError("boom"), "grouped": ConnectionError("boom")}
    res = LE.refresh(now=NOW, db=db, http=_Http(fail=fail), key=KEY)
    assert KEY not in caplog.text and "<redacted>" in caplog.text
    assert KEY not in json.dumps(res, default=str) and KEY not in json.dumps(db.coll.docs, default=str)
    db2 = _DB()
    LE.refresh(now=NOW, db=db2, http=_Http(), key=KEY)
    assert KEY not in json.dumps(db2.coll.docs, default=str)


def test_06d_dry_run_writes_nothing_and_returns_the_would_be_doc():
    db = _DB(_Coll(_doc(as_of="2026-10-12")))
    res = LE.refresh(now=NOW, db=db, http=_Http(), key=KEY, dry_run=True)
    assert res["complete"] is True and db.coll.writes == [] and db.names == []
    assert res["doc"]["as_of"] == "2026-10-15" and len(res["doc"]["rows"]) == 31


def test_06e_NEG_no_key_or_no_database_never_raises():
    res = LE.refresh(now=NOW, db=_DB(), http=_Http(), key="")
    assert res["complete"] is False and res["calls"] == 0
    assert LE.fetch_reference("ETF", http=_Http(), key="") == ([], False, 0)


def test_06f_refresh_clears_the_load_memo(monkeypatch):
    db = _DB(_Coll(_doc(as_of="2026-10-12")))
    monkeypatch.setattr(LE, "_db", lambda d=None: d if d is not None else db)
    assert LE.load(now=NOW, ensure=False)["as_of"] == "2026-10-12"
    LE.refresh(now=NOW, http=_Http(), key=KEY)
    assert LE.load(now=NOW, ensure=False)["as_of"] == "2026-10-15"


# --------------------------------------------------------------------------
# 7 — claim / ensure_async
# --------------------------------------------------------------------------
def test_07_two_calls_start_one_refresh_and_a_claim_holds_across_processes(_clean):
    db = _DB(_Coll(_doc(as_of="2026-10-14", attempted_at=0.0)))
    assert LE.ensure_async(now=NOW, db=db) is True
    assert LE.ensure_async(now=NOW, db=db) is False
    assert len(_clean) == 1
    LE._reset_for_tests()                                                    # another process: no flag
    assert LE.ensure_async(now=NOW, db=db) is False and len(_clean) == 1      # Mongo's claim holds


def test_07b_NEG_within_retry_sec_after_a_failure_no_second_fetch():
    import time as _t
    db = _DB(_Coll(_doc(as_of="2026-10-12", attempted_at=0.0)))
    now_ts = _t.time()
    assert LE.claim(db, today_iso="2026-10-15", now_ts=now_ts) is True
    assert LE.claim(db, today_iso="2026-10-15", now_ts=now_ts + LE.RETRY_SEC - 1) is False
    assert LE.claim(db, today_iso="2026-10-15", now_ts=now_ts + LE.RETRY_SEC + 1) is True


def test_07c_no_doc_inserts_once_and_a_lost_race_is_false():
    db = _DB()
    assert LE.claim(db, today_iso="2026-10-15", now_ts=1e9) is True
    assert LE.claim(db, today_iso="2026-10-15", now_ts=1e9) is False
    assert db.coll.docs[LE.DOC_ID]["rows"] == []


def test_07d_NEG_todays_map_or_no_database_starts_nothing(_clean, monkeypatch):
    db = _DB(_Coll(_doc(as_of="2026-10-15")))
    assert LE.ensure_async(now=NOW, db=db) is False
    monkeypatch.setattr(LE, "_db", lambda d=None: d)
    assert LE.ensure_async(now=NOW) is False
    assert _clean == []


def test_07e_the_spawned_work_refreshes_and_clears_the_flag(_clean, monkeypatch):
    db = _DB(_Coll(_doc(as_of="2026-10-12", attempted_at=0.0)))
    seen = []
    monkeypatch.setattr(LE, "refresh", lambda **k: seen.append(k) or {})
    assert LE.ensure_async(now=NOW, db=db) is True
    _clean[0][0]()
    assert seen and seen[0]["db"] is db and LE._refreshing["on"] is False


# --------------------------------------------------------------------------
# 8 — pins, wording, import guard, CLI
# --------------------------------------------------------------------------
def test_08_transport_pins_and_his_type():
    from chart_maps.gajjala import constants as GC
    from chart_maps import high_beta_tab as HB
    assert set(LE.STOCK_TYPES) == set(GC.SCAN_INSTRUMENT_TYPES)
    assert LE.PAGE_LIMIT == GC.TYPES_PAGE_LIMIT
    assert "ETS" in LE.FUND_TYPES and "ETF" in LE.FUND_TYPES
    assert LE._MINUS == HB._MINUS
    assert LE.MARK == "\U0001F517" and LE.MARK not in ("⚡", "\U0001F53B")


def test_09_NEG_wording_guard_over_every_string_constant():
    from chart_maps import high_beta_tab as HB
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    words = " ".join(n.value for n in ast.walk(tree)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)).lower()
    for w in HB.FORBIDDEN_WORDS:
        assert w not in words, w
    assert "not advice" in words


def test_10_NEG_trading_and_push_never_import_the_map():
    for sub in ("trading", "push"):
        for p in (BACKEND / sub).rglob("*.py"):
            assert "levered_etf" not in p.read_text(errors="ignore"), p


def test_11_cli_dry_run_prints_counts_and_his_lines_never_the_key(monkeypatch, capsys, tmp_path):
    real = LE.refresh
    monkeypatch.setattr(LE, "refresh", lambda **k: real(now=NOW, http=_Http(), key=KEY, **k))
    out = tmp_path / "lev.json"
    rc = LE.main(["refresh", "--dry-run", "--json", str(out)])
    txt = capsys.readouterr().out
    assert rc == 0 and '"tagged": 31' in txt
    assert "IREN \U0001F517 2× IRE · IREX · IREG +1" in txt and "VST \U0001F517 2× VSTL" in txt
    assert KEY not in txt and KEY not in out.read_text()


# ---------------------------------------------------------------------------
# 2026-10-14 late: the "missing" state must never be memoised — the first map of the
# day was hidden for MAP_MEMO_SEC per worker on the live api
# ---------------------------------------------------------------------------
class _FakeColl:
    def __init__(self):
        self.doc = None

    def find_one(self, q):
        return self.doc


class _FakeDb(dict):
    pass


def test_NEG_a_missing_map_is_not_memoised_and_the_next_load_sees_the_doc(monkeypatch):
    LE._reset_for_tests()
    coll = _FakeColl()
    db = _FakeDb({LE.COLL: coll})
    monkeypatch.setattr(LE, "_db", lambda d=None: db)
    monkeypatch.setattr(LE, "ensure_async", lambda **kw: None)
    first = LE.load(now=None)
    assert first["state"] == "missing"
    assert not LE._memo.get("v"), "a missing read must not be pinned for MAP_MEMO_SEC"
    coll.doc = {"_id": LE.DOC_ID, "as_of": LE._et_today(None).isoformat(),
                "rows": [{"etf": "IREX", "underlying": "IREN", "factor": 2.0, "direction": "long",
                          "name": "Tradr 2X Long IREN Daily ETF"}], "complete": True}
    second = LE.load(now=None)
    assert second["state"] == "ready" and second["as_of"] == coll.doc["as_of"]
    assert LE._memo.get("v") and LE._memo["v"]["val"]["state"] == "ready"
    LE._reset_for_tests()
