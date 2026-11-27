"""💸 Borrow (Interactive Brokers' shortable-shares file) — the backend engine, route, ℹ️ fold and test guard (2026-11-22).

Ajay 2026-11-22, verbatim: "What is short borrow fee? Is that a real time value I saw AKAN has a high short borrow
fee" — offered a borrow fee + shares-available line next to the 🔒, he answered: "yes i need that please".

Spec: scratchpad borrow/spec.md §3.1-§3.2, §4 `be`. The fixture under tests/fixtures/ibkr_borrow/ is 24 VERBATIM rows of
IBKR's 2026-11-22 22:57:25 file with a rewritten `#EOF|24` trailer; every other body in this file is built here and
named SYNTHETIC.

Harness: an autouse fixture replaces the engine's ONE outside-call seam (`BR._ftp`) with a RECORDING refuser and
asserts at teardown it was never called; a test that wants an outside answer passes its own `ftp=` fake. The
in-memory collection implements exactly the three operations the engine may use and FAILS on any other (no delete).

The golden payload is REWRITTEN only with IBKR_BORROW_REGEN_GOLDEN=1; otherwise it is only compared.
"""
from __future__ import annotations

import ast
import copy
import ftplib
import hashlib
import json
import os
import re
import zlib
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from short_interest import api as SAPI
from short_interest import borrow as BR
from short_interest import client as SIC
from short_interest import read as SR
from short_interest import reg_sho as RS

BACKEND = Path(__file__).resolve().parents[1]
FIX = BACKEND / "tests" / "fixtures" / "ibkr_borrow"
BODY_PATH = FIX / "usa_2026-11-22_trimmed.txt"
MD5_PATH = FIX / "usa_2026-11-22_trimmed.txt.md5"
GOLDEN = BACKEND / "tests" / "fixtures" / "ibkr_borrow_payload_2026_11_22.json"
SRC = (BACKEND / "short_interest" / "borrow.py").read_text()
ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 22, 23, 4, tzinfo=ET)               # Sunday night, the planning clock
STAMP = "2026.11.22 22:57:25"
READ = "11/22 23:04 ET"
DEFAULT_MIN_ROWS = BR.BR_MIN_ROWS                            # captured before the harness lowers it
_SESSION = {}                                                # the conftest refuser, captured by the harness
GOLDEN_SYMS = ["DBGI", "LABT", "WETO", "AAPL", "AABB", "RZAI", "ADER", "AEMC", "AESG", "BRK-B", "PCG-PRB", "A",
               "AKAN", "DBGIW", "ATN"]
ITEM_KEYS = {"state", "symbol", "name", "chip", "short", "label", "title", "stale", "fee_pct", "rebate_pct",
             "available", "available_floor"}
ENVELOPE_KEYS = {"kind", "status", "stale", "items", "asked", "n", "max_symbols", "file", "note", "refreshing",
                 "retry_after_sec", "keep_sec"}
FORBIDDEN = re.compile(r"no shares|zero shares|cannot be borrowed|impossible|squeeze|bounce|fake|predict|"
                       r"will (rise|fall|drop)|\bhigh\b|\blow\b|expensive|cheap|elevated", re.I)
TAIL = " One broker's indicative rate — your broker sets its own fee when you borrow. A data label, not a signal. " \
       "UNMEASURED."

DBGI_TITLE = ("Interactive Brokers borrow fee for DBGI (IBKR's row: DIGITAL BRANDS GROUP INC): 196.23% a year (≈ 0.54% "
              "a day, the yearly rate ÷ 365), 100,000 shares available to borrow, IBKR file stamped 2026.11.22 "
              "22:57:25, read 11/22 23:04 ET." + TAIL)
AAPL_TITLE = ("Interactive Brokers borrow fee for AAPL (IBKR's row: APPLE INC): 0.25% a year, more than 10,000,000 "
              "shares available to borrow, IBKR file stamped 2026.11.22 22:57:25, read 11/22 23:04 ET." + TAIL)
PCG_TITLE = ("Interactive Brokers borrow fee for PCG-PRB (IBKR's row: PACIFIC GAS & ELEC CO: PCG PRB): 30.36% a year "
             "(≈ 0.08% a day, the yearly rate ÷ 365), 7,000 shares available to borrow, IBKR file stamped 2026.11.22 "
             "22:57:25, read 11/22 23:04 ET." + TAIL)
AESG_TITLE = ("Interactive Brokers lists AESG (IBKR's row: HARBOR ALPHAEDGE CAP GRW ETF) with 90 shares available to "
              "borrow and no fee rate (the file says NA), IBKR file stamped 2026.11.22 22:57:25, read 11/22 23:04 ET. "
              "One broker's indicative rate — your broker sets its own fee when you borrow. A data label, not a "
              "signal. UNMEASURED.")
AKAN_TITLE = ("AKAN is not in IBKR's borrow file stamped 2026.11.22 22:57:25 (read 11/22 23:04 ET, 22 US names). Not "
              "in the file is not a number — no count is shown. One broker's file — your own broker keeps its own "
              "list. A data label, not a signal. UNMEASURED.")
ZERO_ROW = "ZERO|USD|SYNTHETIC ZERO CO|1|X|-80.0000|85.0000|0|F|"
ZERO_TITLE = ("Interactive Brokers borrow fee for ZERO (IBKR's row: SYNTHETIC ZERO CO): 85.00% a year (≈ 0.23% a day, "
              "the yearly rate ÷ 365), 0 shares available to borrow, IBKR file stamped 2026.11.22 22:57:25, read "
              "11/22 23:04 ET." + TAIL)
RULES_DEFAULT = (
    "💸 Borrow = Interactive Brokers' public shortable-shares file: the yearly borrow fee rate and the shares it shows "
    "available to lend, per US ticker. Re-read at most once every 15 minutes while a Gajjala page is open; the hover "
    "carries IBKR's file stamp, the time it was read and the company name on IBKR's row, and the chip says how old the "
    "file is once it is more than 60 minutes old. A name that is not in the file reads '💸 not in IBKR's borrow file' "
    "on 🎾 cards only — never a zero. One broker's indicative rate — your broker sets its own fee when you borrow. Tags "
    "Gajjala cards and the 📋 All strategies table only; it gates, sorts and pushes nothing. UNMEASURED.")
SHORT_VOLUME_PICK = ("Short VOLUME — the daily share of trades marked short — is a different series and is not this "
                     "number.")


# ═════════════════════════════════════════════ fakes
class StandIn:
    """The engine's Mongo collection: find_one({"_id": …}), replace_one({"_id": …}, doc, upsert=True), create_index —
    and NOTHING else (no delete, no find, no sort)."""

    def __init__(self):
        self.docs = {}
        self.writes = []
        self.indexes = []
        self.fail_state_read = False
        self.fail_pre_write = False
        self.fail_final_state = False
        self.fail_snap = False
        self.fail_names = False

    def find_one(self, flt, *a, **k):
        assert not a and not k and isinstance(flt, dict) and set(flt) == {"_id"}, (flt, a, k)
        if self.fail_state_read and flt["_id"] == "state":
            raise RuntimeError("synthetic: the state read fails")
        return copy.deepcopy(self.docs.get(flt["_id"]))

    def replace_one(self, flt, doc, upsert=False):
        assert upsert is True and flt == {"_id": doc["_id"]}, (flt, upsert)
        kind = doc.get("kind")
        if kind == "state" and doc.get("result") == "running" and self.fail_pre_write:
            raise RuntimeError("synthetic: the pre-write fails")
        if kind == "state" and doc.get("result") != "running" and self.fail_final_state:
            raise RuntimeError("synthetic: the final state write fails")
        if kind == "snap" and self.fail_snap:
            raise RuntimeError("synthetic: the snapshot write fails")
        if kind == "names" and self.fail_names:
            raise RuntimeError("synthetic: the names write fails")
        self.docs[doc["_id"]] = copy.deepcopy(doc)
        self.writes.append(doc["_id"])

    def create_index(self, keys, **kw):
        self.indexes.append(keys)
        return "noop"

    def ids(self, kind):
        return sorted(k for k, d in self.docs.items() if d.get("kind") == kind)

    def __getattr__(self, name):
        raise AssertionError("borrow used a collection operation outside its three: %s" % name)


class FakeDB:
    def __init__(self, coll=None):
        self.coll = coll if coll is not None else StandIn()

    def __getitem__(self, name):
        assert name == BR.BR_COLL, name
        return self.coll


class FakeFTP:
    """The seam: records its keyword arguments, answers a LIST aligned with `names` (or raises)."""

    def __init__(self, answers=None, exc=None, on_call=None):
        self.answers = answers
        self.exc = exc
        self.on_call = on_call
        self.calls = []

    def __call__(self, **kw):
        self.calls.append(kw)
        if self.on_call:
            self.on_call(kw)
        if self.exc is not None:
            raise self.exc
        return list(self.answers)


class ReadTimeout(Exception):
    """SYNTHETIC stand-in for a socket timeout (the engine reads the class name)."""


# ═════════════════════════════════════════════ helpers
def fixture_body() -> bytes:
    return BODY_PATH.read_bytes()


def md5_lf(b: bytes) -> bytes:
    return hashlib.md5(b.replace(b"\r\n", b"\n")).hexdigest().encode()


def answers_for(b: bytes) -> list:
    return [md5_lf(b), b, md5_lf(b)]


def fixture_rows() -> list:
    lines = fixture_body().decode("ascii").split("\r\n")
    return [ln for ln in lines[2:] if ln and not ln.startswith("#EOF")]


def synth(rows=None, extra=(), stamp=("2026.11.22", "22:57:25"), eof=None, header=BR.BR_HEADER) -> bytes:
    """SYNTHETIC body: the fixture's BOF / header shape, `rows` (default the fixture rows) + `extra`, CRLF."""
    rows = list(fixture_rows() if rows is None else rows) + list(extra)
    n = len(rows) if eof is None else eof
    lines = ["#BOF|%s|%s" % stamp, header] + rows + ["#EOF|%d" % n]
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


def refreshed(coll=None, now=NOW, body=None, answers=None):
    coll = coll if coll is not None else StandIn()
    b = fixture_body() if body is None else body
    ftp = FakeFTP(answers if answers is not None else answers_for(b))
    state = BR.refresh(coll, now, ftp=ftp)
    return coll, ftp, state


def read(coll, syms, now=NOW):
    return BR.payload(syms, FakeDB(coll), now, kick=False)


def build_golden_payload():
    coll, _ftp, _st = refreshed()
    return BR.payload(list(GOLDEN_SYMS), FakeDB(coll), NOW, kick=False)


def served_strings(p) -> list:
    out = []
    for it in p["items"].values():
        out += [it[k] for k in ("chip", "short", "label", "title") if it[k]]
    if p.get("file"):
        out.append(p["file"]["text"])
    out.append(p["note"])
    return out


@pytest.fixture(autouse=True)
def outside_calls(monkeypatch):
    calls = []
    _SESSION.setdefault("ftp", BR._ftp)                       # the seam as the session fixture left it

    def recorder(*a, **k):
        calls.append(k)
        raise RuntimeError("IBKR borrow FTP sessions are refused in this file")
    monkeypatch.setattr(BR, "_ftp", recorder)
    monkeypatch.setattr(BR, "_bg", {"running": False, "last_start": None, "thread": None})
    monkeypatch.setattr(BR, "BR_MIN_ROWS", 5)
    BR._reset_cache()
    yield calls
    t = BR._bg.get("thread")
    if t is not None:
        t.join(5)
    BR._reset_cache()
    assert calls == [], "the engine reached the module seam: %s" % calls


# ═════════════════════════════════════════════ fixture + parse
def test_fixture_is_the_trimmed_crlf_file_with_its_trailer():
    b = fixture_body()
    assert len(b) == 2260 and b.count(b"\r\n") == 27 and b.endswith(b"#EOF|24\r\n")
    assert b.startswith(b"#BOF|2026.11.22|22:57:25\r\n" + BR.BR_HEADER.encode() + b"\r\n")


def test_parse_the_fixture_counts_stamp_rows_and_names():
    p = BR.parse_file(fixture_body())
    assert (p["n"], p["non_usd"], p["na"], p["floor"], p["zero"], p["skipped"], p["dups"]) == (22, 2, 2, 3, 0, 0, 0)
    assert p["stamp"] == STAMP and p["eof_n"] == 24
    assert p["rows"]["DBGI"] == (196.2308, -192.3508, 100000, False)
    assert p["rows"]["AAPL"] == (0.25, 3.63, 10000000, True)
    assert p["rows"]["AESG"] == (None, None, 90, False)
    assert p["rows"]["BRK.B"] == (0.25, 3.63, 9200000, False)
    assert p["names"]["DBGI"] == "DIGITAL BRANDS GROUP INC"
    assert p["names"]["PCG.PRB"] == "PACIFIC GAS & ELEC CO: PCG PRB"
    assert "ATN" not in p["rows"] and "3LI" not in p["rows"]                  # non-USD never served


@pytest.mark.parametrize("mangle", [
    lambda b: b.replace(b"#EOF|24\r\n", b""),                                 # no #EOF
    lambda b: b.replace(b"#EOF|24", b"#EOF|23"),                              # count off by one
    lambda b: b[:1000],                                                       # truncated
    lambda b: b.replace(b"#BOF|2026.11.22|22:57:25", b"#BOF|2026-11-22|22:57:25"),   # bad #BOF
    lambda b: b.replace(BR.BR_HEADER.encode(), BR.BR_HEADER.encode() + b"EXTRA|"),  # one more column
    lambda b: b"",
    lambda b: "not bytes",
], ids=["no_eof", "eof_23", "truncated", "bad_bof", "extra_column", "empty", "str"])
def test_NEGATIVE_a_mangled_file_is_malformed(mangle):
    with pytest.raises(RS.Malformed):
        BR.parse_file(mangle(fixture_body()))


def test_NEGATIVE_oversize_too_many_rows_and_the_default_min_rows(monkeypatch):
    b = fixture_body()
    monkeypatch.setattr(BR, "BR_MAX_BYTES", 2000)
    with pytest.raises(RS.Malformed, match="oversize"):
        BR.parse_file(b)
    monkeypatch.setattr(BR, "BR_MAX_BYTES", 8_000_000)
    monkeypatch.setattr(BR, "BR_MAX_ROWS", 10)
    with pytest.raises(RS.Malformed, match="too many rows"):
        BR.parse_file(b)
    monkeypatch.setattr(BR, "BR_MAX_ROWS", 60_000)
    assert DEFAULT_MIN_ROWS == 5000
    monkeypatch.setattr(BR, "BR_MIN_ROWS", DEFAULT_MIN_ROWS)
    with pytest.raises(RS.Malformed, match="too few rows"):
        BR.parse_file(b)


@pytest.mark.parametrize("bad", [
    "NINE|USD|SYNTHETIC|1|I|1.0|2.0|5|F",                                     # 9 cells
    "BADF|USD|SYNTHETIC|1|I|1.0|abc|5|F|",
    "NEGF|USD|SYNTHETIC|1|I|1.0|-1.0|5|F|",
    "NANF|USD|SYNTHETIC|1|I|1.0|nan|5|F|",
    "INFF|USD|SYNTHETIC|1|I|1.0|inf|5|F|",
    "LOTS|USD|SYNTHETIC|1|I|1.0|2.0|lots|F|",
    "lowr|USD|SYNTHETIC|1|I|1.0|2.0|5|F|",
], ids=["nine_cells", "fee_abc", "fee_negative", "fee_nan", "fee_inf", "avail_lots", "lower_case"])
def test_NEGATIVE_a_bad_row_is_skipped_and_counted_the_rest_kept(bad):
    p = BR.parse_file(synth(extra=[bad]))                                     # SYNTHETIC
    assert p["skipped"] == 1 and p["n"] == 22 and p["rows"]["DBGI"][0] == 196.2308
    assert bad.split("|")[0].upper() not in p["rows"]


def test_NEGATIVE_past_the_skipped_cap_the_file_is_malformed(monkeypatch):
    monkeypatch.setattr(BR, "BR_MAX_SKIPPED_ROWS", 2)
    bad = ["B%d|USD|SYNTHETIC|1|I|1.0|abc|5|F|" % i for i in range(3)]       # SYNTHETIC
    with pytest.raises(RS.Malformed, match="too many unreadable rows"):
        BR.parse_file(synth(extra=bad))
    assert BR.parse_file(synth(extra=bad[:2]))["skipped"] == 2


def test_NEGATIVE_a_duplicate_usd_symbol_is_unknown_and_its_name_dropped():
    dup = "DBGI|USD|SYNTHETIC DUPLICATE|1|I|-1.0000|9.0000|5|F|"             # SYNTHETIC
    b = synth(extra=[dup])
    p = BR.parse_file(b)
    assert p["dups"] == 1 and p["rows"]["DBGI"] is None and "DBGI" not in p["names"]
    coll, _f, _s = refreshed(body=b)
    out = read(coll, ["DBGI", "LABT"])
    assert "DBGI" not in out["items"] and out["items"]["LABT"]["state"] == "listed" and out["asked"] == 2


# ═════════════════════════════════════════════ [C5] line split
def test_a_form_feed_inside_a_name_cell_still_parses():
    orig = fixture_body()
    b = orig.replace(b"DIGITAL BRANDS GROUP INC", b"DIGITAL BRANDS\x0cGROUP INC")  # SYNTHETIC
    p = BR.parse_file(b)
    assert p["eof_n"] == 24 and p["n"] == 22 and p["skipped"] == 0
    assert p["names"]["DBGI"] == "DIGITAL BRANDS GROUP INC"
    # the proof the old rule would have rejected it: the str line splitter sees one line MORE
    assert len(b.decode("ascii").splitlines()) == len(orig.decode("ascii").splitlines()) + 1


def test_NEGATIVE_the_engine_never_uses_the_str_line_splitter():
    assert ".splitlines(" not in SRC


# ═════════════════════════════════════════════ [C6] clean_name
def test_clean_name_unescapes_and_cleans():
    assert BR.clean_name("PACIFIC GAS &amp; ELEC CO: PCG PRB") == "PACIFIC GAS & ELEC CO: PCG PRB"
    assert BR.clean_name("PFD DIGITALBRIDGE GRO BE&lt;") == "PFD DIGITALBRIDGE GRO BE<"
    assert BR.clean_name("A\x0cB  C|D") == "A B C D"
    assert len(BR.clean_name("X" * 80)) == 60 == BR.BR_NAME_MAX
    assert BR.clean_name("\x01\x02\x0c|") == ""


# ═════════════════════════════════════════════ [C2] zero shares = LISTED
@pytest.mark.parametrize("forms", [("label",), ("label", "chip", "short"), ("short",), (), ("label", "bogus")])
def test_a_zero_shares_row_is_listed_never_absent(monkeypatch, forms):
    monkeypatch.setattr(BR, "BR_ABSENT_FORMS", forms)
    b = synth(extra=[ZERO_ROW])                                               # SYNTHETIC
    assert BR.parse_file(b)["zero"] == 1
    coll, _f, _s = refreshed(body=b)
    it = read(coll, ["ZERO"])["items"]["ZERO"]
    assert it["state"] == "listed" and it["available"] == 0 and isinstance(it["available"], int)
    assert it["chip"] == "💸 Borrow 85% · 0 avail" and it["short"] == "💸 85%"
    assert it["label"] == "💸 Borrow 85% a year · 0 shares available · IBKR file 2026.11.22 22:57:25"
    assert it["title"] == ZERO_TITLE
    for s in (it["chip"], it["short"], it["label"], it["title"]):
        assert not FORBIDDEN.search(s), s


# ═════════════════════════════════════════════ md5 [C10]
def test_the_md5_file_is_the_md5_of_the_lf_form_never_the_raw_bytes():
    b, m = fixture_body(), MD5_PATH.read_bytes()
    assert m == b"68a63cd6a0f00138e4713cc5c72a2521" == md5_lf(b)
    assert hashlib.md5(b).hexdigest() == "4bbe54d074ae14073a4a13713afa2b90" != m.decode()
    assert BR.md5_ok(b, [m, None]) is True and BR.md5_ok(b, [hashlib.md5(b).hexdigest(), None]) is False


def test_the_seam_is_called_once_with_md5_before_and_after_the_file():
    _c, ftp, st = refreshed()
    assert len(ftp.calls) == 1 and ftp.calls[0]["names"] == ("usa.txt.md5", "usa.txt", "usa.txt.md5")
    assert st["result"] == "found"


WRONG = b"0" * 32


@pytest.mark.parametrize("before,after,want", [
    (WRONG, "right", ("found", True)),
    ("right", WRONG, ("found", True)),
    (WRONG, WRONG, ("error", "md5")),
    (WRONG, None, ("error", "md5")),
    (None, None, ("found", None)),
    (b"  68A63CD6A0F00138E4713CC5C72A2521\n", None, ("found", True)),
    (b"not an md5", None, ("found", None)),
])
def test_md5_before_and_after(before, after, want):
    b = fixture_body()
    pick = lambda v: md5_lf(b) if v == "right" else v                         # noqa: E731
    got = BR.fetch(FakeFTP([pick(before), b, pick(after)]))
    if want[0] == "found":
        assert got["result"] == "found" and got["md5_ok"] is want[1]
    else:
        assert got["result"] == "error" and got["error"] == want[1]


def test_NEGATIVE_both_md5_wrong_keeps_the_held_file():
    coll, _f, s1 = refreshed()
    b2 = synth(rows=[r.replace("196.2308", "199.0000") for r in fixture_rows()])   # SYNTHETIC changed row
    _c, _f2, s2 = refreshed(coll, NOW + timedelta(minutes=20), body=b2, answers=[WRONG, b2, WRONG])
    assert s2["result"] == "error" and s2["error"] == "md5" and s2["good_id"] == s1["good_id"]
    assert read(coll, ["DBGI"], NOW + timedelta(minutes=20))["items"]["DBGI"]["fee_pct"] == 196.2308


def test_both_md5_none_is_accepted_and_stored_as_none():
    b = fixture_body()
    coll, _f, s = refreshed(answers=[None, b, None])
    assert s["result"] == "found" and coll.docs[s["good_id"]]["md5_ok"] is None


# ═════════════════════════════════════════════ lower bound
def test_a_lower_bound_prints_with_its_mark():
    coll, _f, _s = refreshed()
    it = read(coll, ["AAPL"])["items"]["AAPL"]
    assert it["available"] == 10000000 and it["available_floor"] is True
    assert ">10M" in it["chip"] and "more than 10,000,000" in it["title"]
    assert "· 10M avail" not in it["chip"] and "· 10M shares" not in it["label"]           # NEGATIVE


# ═════════════════════════════════════════════ storage
def test_rows_and_names_roundtrip_and_the_digest_ignores_order():
    rows = BR.parse_file(fixture_body())["rows"]
    rows = dict(rows, DUPX=None)
    blob, dig = BR.encode_rows(rows)
    assert BR.decode_rows(blob) == rows
    _b2, dig2 = BR.encode_rows(dict(reversed(list(rows.items()))))
    assert dig == dig2
    names = BR.parse_file(fixture_body())["names"]
    nb, nd = BR.encode_names(names)
    assert BR.decode_names(nb) == names and BR.encode_names(dict(reversed(list(names.items()))))[1] == nd


def test_the_snap_blob_carries_no_name_and_the_names_blob_no_identifiers():
    coll, _f, s = refreshed()
    snap = zlib.decompress(coll.docs[s["good_id"]]["blob"])
    for w in (b"DIGITAL BRANDS", b"XXXXXXXN6067", b"BBG00S90Q1M3", b"904230898"):
        assert w not in snap, w
    names = zlib.decompress(coll.docs[s["names_id"]]["blob"])
    assert b"DBGI|DIGITAL BRANDS GROUP INC" in names
    for w in (b"XXXXXXXN6067", b"BBG00S90Q1M3", b"904230898"):
        assert w not in names, w
    snap_doc = coll.docs[s["good_id"]]
    assert set(snap_doc) == {"_id", "kind", "fetched_at", "stamp", "eof_n", "n", "skipped", "non_usd", "na", "floor",
                             "zero", "dups", "digest", "md5_ok", "names_id", "blob"}
    assert coll.indexes == [[("kind", 1), ("fetched_at", -1)]]


def test_names_doc_is_content_addressed():
    coll, _f, s1 = refreshed()
    refreshed(coll, NOW + timedelta(minutes=20))
    assert coll.ids("names") == [s1["names_id"]] and s1["names_id"].startswith("names|")
    assert coll.writes.count(s1["names_id"]) == 1                            # no second write of the same doc
    b3 = synth(rows=[r.replace("DIGITAL BRANDS GROUP INC", "DIGITAL BRANDS GROUP CORP") for r in fixture_rows()])
    _c, _f3, s3 = refreshed(coll, NOW + timedelta(minutes=40), body=b3)       # SYNTHETIC renamed row
    assert s3["result"] == "unchanged" and s3["names_id"] != s1["names_id"]
    assert set(coll.ids("names")) == {s1["names_id"], s3["names_id"]}
    assert "(IBKR's row: DIGITAL BRANDS GROUP CORP)" in read(coll, ["DBGI"], NOW + timedelta(minutes=40))[
        "items"]["DBGI"]["title"]


def test_a_missing_names_doc_drops_the_bracket_and_the_next_read_looks_again():
    coll, _f, s = refreshed()
    saved = coll.docs.pop(s["names_id"])
    p = read(coll, ["DBGI", "AKAN"])
    assert p["status"] == "ok"
    assert p["items"]["DBGI"]["title"].startswith("Interactive Brokers borrow fee for DBGI: 196.23% a year")
    assert p["items"]["DBGI"]["name"] is None and "IBKR's row" not in json.dumps(p, ensure_ascii=False)
    coll.docs[s["names_id"]] = saved
    assert read(coll, ["DBGI"])["items"]["DBGI"]["title"] == DBGI_TITLE
    coll.docs[s["names_id"]] = dict(saved, blob=b"not zlib")                 # does not unpack → no clause
    BR._reset_cache()
    assert read(coll, ["DBGI"])["items"]["DBGI"]["name"] is None


def test_a_names_write_that_raises_still_lands_found():
    coll = StandIn()
    coll.fail_names = True
    _c, _f, s = refreshed(coll)
    assert s["result"] == "found" and s.get("names_id") is None and coll.ids("names") == []
    p = read(coll, ["DBGI"])
    assert p["status"] == "ok" and "IBKR's row" not in p["items"]["DBGI"]["title"]


def test_NEGATIVE_the_stand_in_has_no_delete():
    with pytest.raises(AssertionError):
        StandIn().delete_one({"_id": "state"})
    for op in ("delete_one", "delete_many", "remove", "drop", "find", "update_one", "insert_one"):
        assert ".%s(" % op not in SRC, op


# ═════════════════════════════════════════════ [C7] snapshot id
def test_two_refreshes_at_the_same_moment_keep_two_snapshots():
    coll, _f, s1 = refreshed()
    b2 = synth(rows=[r.replace("346.8824", "350.0000") for r in fixture_rows()])   # SYNTHETIC
    _c, _f2, s2 = refreshed(coll, NOW, body=b2)
    assert s2["result"] == "found" and len(coll.ids("snap")) == 2
    a, b = s1["good_id"].split("|"), s2["good_id"].split("|")
    assert a[0] == b[0] == "snap" and a[1] == b[1] and a[2] != b[2] and len(a[2]) == 12
    assert s1["good_id"] in coll.docs


# ═════════════════════════════════════════════ host
def test_the_seam_gets_the_one_host_and_the_published_login():
    _c, ftp, _s = refreshed()
    kw = ftp.calls[0]
    assert kw["host"] == "ftp2.interactivebrokers.com" == BR.BR_FTP_HOST
    assert (kw["port"], kw["user"], kw["password"], kw["timeout"]) == (21, "shortstock", "", 25)
    assert (kw["max_bytes"], kw["budget_sec"]) == (BR.BR_MAX_BYTES, BR.BR_FETCH_BUDGET_SEC)
    assert set(kw) == {"host", "port", "user", "password", "names", "timeout", "max_bytes", "budget_sec"}


def test_NEGATIVE_no_second_host():
    assert "ftp3.interactivebrokers" not in SRC
    assert set(re.findall(r"[a-z0-9.\-]*interactivebrokers\.com", SRC)) == {"ftp2.interactivebrokers.com"}


def test_the_real_fetcher_reads_in_order_and_a_refused_md5_is_none(monkeypatch):
    log = []

    class FakeConn:                                                           # SYNTHETIC ftplib.FTP
        def connect(self, host, port, timeout=None):
            log.append(("connect", host, port, timeout))

        def login(self, user, password):
            log.append(("login", user, password))

        def retrbinary(self, cmd, cb):
            log.append(cmd)
            if cmd == "RETR usa.txt.md5" and log.count(cmd) == 2:
                raise ftplib.error_perm("550 synthetic")
            data = b"x" * 10 if cmd == "RETR usa.txt" else b"m"
            cb(data[:4])
            cb(data[4:])

        def close(self):
            log.append("close")
    monkeypatch.setattr(ftplib, "FTP", FakeConn)
    out = BR._ftp_fetch(host="h", port=21, user="u", password="", names=BR.BR_FETCH_NAMES, timeout=3,
                        max_bytes=100, budget_sec=60)
    assert out == [b"m", b"x" * 10, None]
    assert log == [("connect", "h", 21, 3), ("login", "u", ""), "RETR usa.txt.md5", "RETR usa.txt",
                   "RETR usa.txt.md5", "close"]
    log.clear()
    with pytest.raises(Exception):
        BR._ftp_fetch(host="h", port=21, user="u", password="", names=("usa.txt",), timeout=3, max_bytes=5,
                      budget_sec=60)
    assert log[-1] == "close"                                                 # closed in finally


# ═════════════════════════════════════════════ refresh [C3]
HELD_KEYS = ("good_id", "good_digest", "names_id", "stamp", "stamp_seen_at", "checked_at", "n", "skipped", "errors")


def test_the_running_pre_write_carries_every_held_key_and_reads_do_not_change():
    coll, _f, s1 = refreshed()
    later = NOW + timedelta(minutes=20)
    before = read(coll, ["DBGI", "AKAN", "AESG"], later)
    seen = {}

    def inside(kw):
        seen["doc"] = copy.deepcopy(coll.docs["state"])
        seen["read"] = read(coll, ["DBGI", "AKAN", "AESG"], later)
    b2 = synth(rows=[r.replace("196.2308", "199.0000") for r in fixture_rows()])   # SYNTHETIC
    BR.refresh(coll, later, ftp=FakeFTP(answers_for(b2), on_call=inside))
    doc = seen["doc"]
    assert doc["result"] == "running" and doc["error"] is None and doc["attempt_at"] == RS._utc_iso(later)
    for k in HELD_KEYS:
        assert doc.get(k) == s1.get(k), k
    assert seen["read"]["status"] == before["status"] == "ok"
    assert seen["read"]["items"] == before["items"]


def test_a_final_write_that_raises_leaves_the_held_file_served_and_waits():
    coll, _f, _s1 = refreshed()
    later = NOW + timedelta(minutes=20)
    before = read(coll, ["DBGI", "AKAN"], later)
    coll.fail_final_state = True
    b2 = synth(rows=[r.replace("196.2308", "199.0000") for r in fixture_rows()])   # SYNTHETIC
    BR.refresh(coll, later, ftp=FakeFTP(answers_for(b2)))
    disk = coll.docs["state"]
    assert disk["result"] == "running"
    assert read(coll, ["DBGI", "AKAN"], later)["items"] == before["items"]
    assert BR.is_due(disk, later + timedelta(minutes=14)) is False
    assert BR.is_due(disk, later + timedelta(minutes=15)) is True


def test_errors_reset_after_a_found_or_unchanged_round():
    coll, _f, _s = refreshed()
    t1 = NOW + timedelta(minutes=20)
    e1 = BR.refresh(coll, t1, ftp=FakeFTP(exc=RuntimeError("synthetic")))
    assert e1["result"] == "error" and e1["errors"] == 1
    _c, _f2, u = refreshed(coll, t1 + timedelta(minutes=5))
    assert u["result"] == "unchanged" and u["errors"] == 0
    BR.refresh(coll, t1 + timedelta(minutes=10), ftp=FakeFTP(exc=RuntimeError("synthetic")))
    b2 = synth(rows=[r.replace("196.2308", "199.0000") for r in fixture_rows()])   # SYNTHETIC
    _c, _f3, f = refreshed(coll, t1 + timedelta(minutes=15), body=b2)
    assert f["result"] == "found" and f["errors"] == 0


def test_unchanged_rows_and_stamp_moves():
    coll, _f, s1 = refreshed()
    t1 = NOW + timedelta(minutes=16)
    _c, _f2, s2 = refreshed(coll, t1)
    assert s2["result"] == "unchanged" and len(coll.ids("snap")) == 1
    assert s2["stamp_seen_at"] == s1["stamp_seen_at"] and s2["checked_at"] == RS._utc_iso(t1)
    b3 = synth(stamp=("2026.11.22", "23:13:02"))                              # same rows, the next stamp
    t2 = NOW + timedelta(minutes=32)
    _c, _f3, s3 = refreshed(coll, t2, body=b3)
    assert s3["result"] == "unchanged" and len(coll.ids("snap")) == 1
    assert s3["stamp"] == "2026.11.22 23:13:02" and s3["stamp_seen_at"] == RS._utc_iso(t2)
    b4 = synth(rows=[r.replace("196.2308", "199.0000") for r in fixture_rows()])   # SYNTHETIC
    _c, _f4, s4 = refreshed(coll, NOW + timedelta(minutes=48), body=b4)
    assert s4["result"] == "found" and len(coll.ids("snap")) == 2 and s1["good_id"] in coll.docs


def test_an_error_keeps_the_held_file_and_counts():
    coll, _f, s1 = refreshed()
    e = BR.refresh(coll, NOW + timedelta(minutes=20), ftp=FakeFTP(exc=RuntimeError("synthetic")))
    assert e["result"] == "error" and e["error"] == "exception" and e["errors"] == 1
    for k in HELD_KEYS[:-1]:
        assert e.get(k) == s1.get(k), k
    p = read(coll, ["DBGI"], NOW + timedelta(minutes=20))
    assert p["status"] == "ok" and p["items"]["DBGI"]["fee_pct"] == 196.2308       # status never reads result


def test_NEGATIVE_a_state_read_or_pre_write_that_raises_makes_no_seam_call():
    for flag in ("fail_state_read", "fail_pre_write"):
        coll = StandIn()
        setattr(coll, flag, True)
        ftp = FakeFTP(answers_for(fixture_body()))
        assert BR.refresh(coll, NOW, ftp=ftp) is None and ftp.calls == [], flag


def test_NEGATIVE_a_snap_write_that_raises_is_a_store_error_and_the_held_file_stays():
    coll, _f, s1 = refreshed()
    coll.fail_snap = True
    b2 = synth(rows=[r.replace("196.2308", "199.0000") for r in fixture_rows()])   # SYNTHETIC
    _c, _f2, s2 = refreshed(coll, NOW + timedelta(minutes=20), body=b2)
    assert s2["result"] == "error" and s2["error"] == "store" and s2["good_id"] == s1["good_id"]
    assert s2["errors"] == 1 and s2["checked_at"] == s1["checked_at"]
    first = BR.refresh(StandIn(), NOW, ftp=FakeFTP(answers_for(fixture_body())))
    assert first["result"] == "found"


@pytest.mark.parametrize("exc,err,detail", [
    (ReadTimeout("synthetic"), "timeout", "ReadTimeout"),
    (TimeoutError("synthetic"), "timeout", "TimeoutError"),
    (ftplib.error_temp("421 too many connections"), "exception", "error_temp"),
    (ConnectionRefusedError("synthetic"), "exception", "ConnectionRefusedError"),
])
def test_NEGATIVE_a_seam_that_raises_is_an_error_and_the_held_file_stays(exc, err, detail):
    assert BR.fetch(FakeFTP(exc=exc)) == {"result": "error", "error": err, "detail": detail}
    coll, _f, s1 = refreshed()
    t1 = NOW + timedelta(minutes=20)
    s2 = BR.refresh(coll, t1, ftp=FakeFTP(exc=exc))
    assert s2["result"] == "error" and s2["error"] == err and s2["good_id"] == s1["good_id"]
    assert BR.is_due(s2, t1 + timedelta(minutes=4)) is False
    assert BR.is_due(s2, t1 + timedelta(minutes=BR.BR_ERROR_RETRY_MIN)) is True


def test_NEGATIVE_an_empty_body_or_a_malformed_file_is_an_error():
    assert BR.fetch(FakeFTP([None, b"", None]))["error"] == "empty"
    assert BR.fetch(FakeFTP([None, b"garbage\r\n", None]))["error"] == "malformed"


# ═════════════════════════════════════════════ throttle + kick
def test_throttle():
    assert BR.is_due(None, NOW) is True
    ok = {"attempt_at": RS._utc_iso(NOW), "result": "found", "errors": 0}
    assert BR.is_due(ok, NOW + timedelta(minutes=14)) is False
    assert BR.is_due(ok, NOW + timedelta(minutes=BR.BR_REFRESH_MIN)) is True
    e1 = dict(ok, result="error", errors=1)
    assert BR.is_due(e1, NOW + timedelta(minutes=4)) is False and BR.is_due(e1, NOW + timedelta(minutes=5)) is True
    e2 = dict(ok, result="error", errors=BR.BR_ERROR_STRIKES)
    assert BR.is_due(e2, NOW + timedelta(minutes=5)) is False and BR.is_due(e2, NOW + timedelta(minutes=15)) is True
    dead = dict(ok, result="running")
    assert BR.is_due(dead, NOW + timedelta(minutes=14)) is False
    assert BR.is_due(dead, NOW + timedelta(minutes=15)) is True
    assert BR.is_due({"result": "found"}, NOW) is True                        # no attempt time


def test_kick_single_flight_floor_and_a_thread_that_cannot_start(monkeypatch):
    BR._bg["running"] = True
    assert BR.kick_refresh(StandIn(), NOW, ftp=FakeFTP([])) is False
    BR._bg.update({"running": False, "last_start": BR._mono()})
    assert BR.kick_refresh(StandIn(), NOW, ftp=FakeFTP([])) is False

    class NoThread:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")
    monkeypatch.setattr(BR.threading, "Thread", NoThread)
    BR._bg.update({"running": False, "last_start": None})
    assert BR.kick_refresh(StandIn(), NOW, ftp=FakeFTP([])) is False
    assert BR._bg["running"] is False and BR._bg["last_start"] is None


def test_kick_starts_one_named_worker():
    coll = StandIn()
    ftp = FakeFTP(answers_for(fixture_body()))
    assert BR.kick_refresh(coll, NOW, ftp=ftp) is True
    t = BR._bg["thread"]
    assert t.name == "ibkr-borrow-refresh" and t.daemon
    t.join(5)
    assert len(ftp.calls) == 1 and coll.docs["state"]["result"] == "found"
    assert BR.kick_refresh(coll, NOW, ftp=ftp) is False                       # the floor


def test_NEGATIVE_payload_with_kick_false_makes_no_call():
    ftp = FakeFTP(answers_for(fixture_body()))
    p = BR.payload(["DBGI"], FakeDB(), NOW, kick=False, ftp=ftp)
    assert ftp.calls == [] and BR._bg["thread"] is None and p["status"] == "pending" and p["refreshing"] is False


def test_a_kicked_read_with_no_ftp_reaches_only_the_module_seam(monkeypatch):
    hits = []

    def module_seam(**kw):
        hits.append(kw["host"])
        raise RuntimeError("synthetic: refused")
    monkeypatch.setattr(BR, "_ftp", module_seam)
    coll = StandIn()
    p = BR.payload(["DBGI"], FakeDB(coll), NOW, kick=True)
    assert p["refreshing"] is True and p["retry_after_sec"] == BR.BR_RETRY_AFTER_SEC
    BR._bg["thread"].join(5)
    assert hits == [BR.BR_FTP_HOST] and coll.docs["state"]["result"] == "error"


def test_conftest_installs_the_session_refuser():
    session_ftp = _SESSION["ftp"]
    assert callable(session_ftp)
    with pytest.raises(RuntimeError, match="tests/conftest.py"):
        session_ftp(host=BR.BR_FTP_HOST)
    src = (BACKEND / "tests" / "conftest.py").read_text()
    assert "BR._ftp = _refuse_ftp" in src and "BR._ftp = prior_br_ftp" in src


# ═════════════════════════════════════════════ payload
def test_golden_payload():
    p = build_golden_payload()
    got = json.loads(json.dumps(p, allow_nan=False))
    if os.environ.get("IBKR_BORROW_REGEN_GOLDEN") == "1":
        GOLDEN.write_text(json.dumps({"now": NOW.isoformat(), "symbols": GOLDEN_SYMS, "payload": got},
                                     ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    g = json.loads(GOLDEN.read_text())
    assert g["now"] == NOW.isoformat() and g["symbols"] == GOLDEN_SYMS
    assert got == g["payload"]


def test_worked_strings_exactly():
    p = build_golden_payload()
    it = p["items"]
    want = {
        "DBGI": ("💸 Borrow 196% · 100K avail", "💸 196%",
                 "💸 Borrow 196% a year · 100K shares available · IBKR file 2026.11.22 22:57:25"),
        "LABT": ("💸 Borrow 347% · 150K avail", "💸 347%",
                 "💸 Borrow 347% a year · 150K shares available · IBKR file 2026.11.22 22:57:25"),
        "WETO": ("💸 Borrow 10% · 350K avail", "💸 10%",
                 "💸 Borrow 10% a year · 350K shares available · IBKR file 2026.11.22 22:57:25"),
        "AAPL": ("💸 Borrow 0.25% · >10M avail", "💸 0.25%",
                 "💸 Borrow 0.25% a year · >10M shares available · IBKR file 2026.11.22 22:57:25"),
        "AESG": ("💸 Borrow fee n/a · 90 avail", None,
                 "💸 Borrow fee n/a · 90 shares available · IBKR file 2026.11.22 22:57:25"),
        "AKAN": (None, None, "💸 not in IBKR's borrow file"),
    }
    for sym, (chip, short, label) in want.items():
        assert (it[sym]["chip"], it[sym]["short"], it[sym]["label"]) == (chip, short, label), sym
    assert (it["RZAI"]["chip"], it["RZAI"]["short"]) == ("💸 Borrow 1,019% · 30K avail", "💸 1,019%")
    assert (it["ADER"]["chip"], it["ADER"]["short"]) == ("💸 Borrow 0% · 300K avail", "💸 0%")
    assert (it["BRK-B"]["chip"], it["BRK-B"]["short"]) == ("💸 Borrow 0.25% · 9.2M avail", "💸 0.25%")
    assert (it["PCG-PRB"]["chip"], it["PCG-PRB"]["short"]) == ("💸 Borrow 30% · 7K avail", "💸 30%")
    assert it["DBGI"]["title"] == DBGI_TITLE and it["AAPL"]["title"] == AAPL_TITLE
    assert it["PCG-PRB"]["title"] == PCG_TITLE and it["AESG"]["title"] == AESG_TITLE
    assert it["AKAN"]["title"] == AKAN_TITLE
    assert "(IBKR's row: 26 CAPITAL ACQUISITION COR-A)" in it["ADER"]["title"]
    assert it["DBGI"]["name"] == "DIGITAL BRANDS GROUP INC"
    assert p["file"]["text"] == ("Interactive Brokers borrow file stamped 2026.11.22 22:57:25 · read 11/22 23:04 ET · "
                                 "22 US names")
    assert p["note"] == BR.HONESTY_NOTE and p["keep_sec"] == 3600 and p["status"] == "ok"


def test_item_and_envelope_key_sets_and_asked():
    p = build_golden_payload()
    assert set(p) == ENVELOPE_KEYS and p["kind"] == "ibkr_borrow" and p["max_symbols"] == 200
    assert p["asked"] == 15 and p["n"] == len(p["items"]) == 15
    for sym, it in p["items"].items():
        assert set(it) == ITEM_KEYS and it["symbol"] == sym, sym
    assert set(p["file"]) == {"stamp", "first_read_at", "read_at", "age_min", "names", "skipped", "text"}
    assert p["file"]["names"] == 22 and p["file"]["stamp"] == STAMP and p["file"]["age_min"] == 0


@pytest.mark.parametrize("forms,want", [
    (("label",), (None, None, "💸 not in IBKR's borrow file")),
    (("label", "chip", "short"), ("💸 not in IBKR's file", "💸 not in file", "💸 not in IBKR's borrow file")),
    (("short",), (None, "💸 not in file", None)),
    ((), None),
    (("label", "bogus"), (None, None, "💸 not in IBKR's borrow file")),
], ids=["default", "everywhere", "short_only", "none", "bogus_ignored"])
def test_absent_forms_switch(monkeypatch, forms, want):
    monkeypatch.setattr(BR, "BR_ABSENT_FORMS", forms)
    coll, _f, _s = refreshed()
    p = read(coll, ["AKAN", "DBGI"])
    assert p["items"]["DBGI"]["state"] == "listed"
    if want is None:
        assert "AKAN" not in p["items"] and p["n"] == 1
    else:
        it = p["items"]["AKAN"]
        assert (it["chip"], it["short"], it["label"]) == want
        assert it["state"] == "absent" and it["fee_pct"] is None and it["available"] is None
        assert it["available"] != 0 and it["title"] == AKAN_TITLE
        for s in (it["chip"], it["short"], it["label"], it["title"]):
            assert s is None or (" 0 " not in s and "zero" not in s.lower()), s
        stale = read(coll, ["AKAN"], NOW + timedelta(minutes=195))["items"]["AKAN"]
        assert tuple(None if w is None else w + " · file 3h old" for w in want) == (
            stale["chip"], stale["short"], stale["label"])


def test_the_default_absent_forms_are_label_only():
    assert BR.BR_ABSENT_FORMS == ("label",) and BR.BR_FORMS == ("label", "chip", "short")


def test_stale_dbgi_worked_strings():
    coll, _f, _s = refreshed()
    p = read(coll, ["DBGI"], NOW + timedelta(minutes=195))
    it = p["items"]["DBGI"]
    assert p["status"] == "stale" and p["stale"] is True and it["stale"] is True
    assert it["chip"] == "💸 Borrow 196% · 100K avail · file 3h old"
    assert it["short"] == "💸 196% · file 3h old"
    assert it["label"] == "💸 Borrow 196% a year · 100K shares available · IBKR file 2026.11.22 22:57:25 · file 3h old"
    assert it["title"] == DBGI_TITLE + (" This is the file first read 11/22 23:04 ET (3h old) — a newer one could not "
                                        "be read or has not been published.")


@pytest.mark.parametrize("minutes,status,keep", [(0, "ok", 3600), (55, "ok", 300), (60, "ok", 1),
                                                 (61, "stale", 3600)])
def test_keep_sec(minutes, status, keep):
    coll, _f, _s = refreshed()
    p = read(coll, ["DBGI"], NOW + timedelta(minutes=minutes))
    assert (p["status"], p["keep_sec"]) == (status, keep)


def test_NEGATIVE_61_minutes_is_stale_on_every_string():
    coll, _f, _s = refreshed()
    p = read(coll, list(GOLDEN_SYMS), NOW + timedelta(minutes=61))
    assert p["status"] == "stale"
    for sym, it in p["items"].items():
        for k in ("chip", "short", "label"):
            if it[k] is not None:
                assert it[k].endswith(" · file 1h old"), (sym, k)
        assert "This is the file first read 11/22 23:04 ET (1h old)" in it["title"], sym


def test_NEGATIVE_pending_and_failed_serve_no_file_and_no_keep():
    p = read(StandIn(), ["DBGI", "AKAN"])
    assert p["status"] == "pending" and p["items"] == {} and p["file"] is None and p["keep_sec"] is None
    assert p["retry_after_sec"] == BR.BR_ERROR_RETRY_MIN * 60 and p["asked"] == 2
    coll = StandIn()
    BR.refresh(coll, NOW, ftp=FakeFTP(exc=RuntimeError("synthetic")))
    f = read(coll, ["DBGI", "AKAN"])
    assert f["status"] == "failed" and f["file"] is None and f["keep_sec"] is None
    assert set(f["items"]) == {"DBGI", "AKAN"}
    for sym, it in f["items"].items():
        assert it["state"] == "unread" and it["label"] == "💸 IBKR's borrow file could not be read"
        assert it["chip"] is None and it["short"] is None
        assert it["title"] == ("IBKR's borrow file could not be read — no fee and no share count is shown for %s. "
                               "One broker's file — your own broker keeps its own list. A data label, not a signal. "
                               "UNMEASURED." % sym)


def test_NEGATIVE_mongo_down_is_failed_and_equals_the_fault_payload():
    ftp = FakeFTP(answers_for(fixture_body()))
    syms = ["dbgi", "AKAN", "BRK-B"]
    down = BR.payload(syms, None, NOW, kick=True, ftp=ftp)
    assert ftp.calls == [] and BR._bg["thread"] is None
    assert down["status"] == "failed" and down["file"] is None and down["keep_sec"] is None
    assert BR.fault_payload(syms) == BR.payload(syms, db=None, kick=False) == down
    assert list(down["items"]) == ["DBGI", "AKAN", "BRK-B"]
    assert BR.fault_payload() == BR.payload([], db=None, kick=False)
    odd = BR.fault_payload([None, 5, "<x>", "a" * 40])
    assert odd["items"] == {} and odd["asked"] == 0 and set(odd) == ENVELOPE_KEYS
    assert BR.fault_payload("DBGI")["items"] == {}


def test_NEGATIVE_lookup_is_exact_match_only():
    coll, _f, _s = refreshed()
    p = read(coll, ["DBGI", "DBGIW", "DBG", "DBGIX", "ATN", "3LI", "PCG-PB", "brk b", "BRK.B", "BRK-B"])
    it = p["items"]
    assert it["DBGI"]["state"] == "listed"
    for sym in ("DBGIW", "DBG", "DBGIX", "ATN", "3LI"):
        assert it[sym]["state"] == "absent" and it[sym]["fee_pct"] is None, sym
    assert "PCG-PB" not in it and p["asked"] == 10 and p["n"] == 9               # unknown → OMITTED, never absent
    rows = [it[k] for k in ("BRK B", "BRK.B", "BRK-B")]
    assert all(r["fee_pct"] == 0.25 and r["available"] == 9200000 for r in rows)
    assert [r["symbol"] for r in rows] == ["BRK B", "BRK.B", "BRK-B"]
    assert BR.lookup("PCG-PB", {}) == ("unknown", None) and BR.lookup("AKAN", {}) == ("absent", None)
    assert BR.lookup("", {}) == ("unknown", None)


def test_every_state_serves_finite_json():
    coll, _f, _s = refreshed(body=synth(extra=[ZERO_ROW]))
    syms = list(GOLDEN_SYMS) + ["ZERO"]
    for p in (read(coll, syms), read(coll, syms, NOW + timedelta(minutes=61)), read(StandIn(), syms),
              BR.fault_payload(syms), BR.payload(syms, None, NOW, kick=False)):
        json.dumps(p, allow_nan=False)
        for it in p["items"].values():
            for k in ("fee_pct", "rebate_pct"):
                assert it[k] is None or (isinstance(it[k], float) and abs(it[k]) < 1e9), (k, it[k])


def test_NEGATIVE_cap_dedupe_blanks():
    many = ["S%03d" % i for i in range(250)]
    assert BR.clean_symbols(many) == many[:200] and len(BR.clean_symbols(many)) == BR.MAP_MAX_SYMBOLS
    assert BR.clean_symbols(["dbgi", " DBGI ", "", "   ", None, 5, "<x>", "a" * 40]) == ["DBGI"]
    assert BR.clean_symbols(None) == [] and BR.clean_symbols("DBGI") == [] and BR.clean_symbols({"A": 1}) == []
    assert "NONE" not in BR.clean_symbols([None])
    p = read(refreshed()[0], many)
    assert p["asked"] == 200 and p["n"] == 200


def test_NEGATIVE_no_served_string_carries_a_forbidden_word(monkeypatch):
    texts = []
    for forms in (("label",), ("label", "chip", "short")):
        monkeypatch.setattr(BR, "BR_ABSENT_FORMS", forms)
        coll, _f, _s = refreshed(body=synth(extra=[ZERO_ROW]))
        syms = list(GOLDEN_SYMS) + ["ZERO", "BRK B", "AAC U", "BF A", "BFIT.OLD", "GME", "AEMC", "ZZZOF"]
        for now in (NOW, NOW + timedelta(minutes=195), NOW + timedelta(days=3)):
            texts += served_strings(read(coll, syms, now))
        texts += served_strings(BR.fault_payload(syms))
        texts.append(BR.rules_pick())
    assert len(texts) > 100
    for t in texts:
        assert not FORBIDDEN.search(t), t
    names = BR.parse_file(fixture_body())["names"]
    assert len(names) == 22
    for n in names.values():
        assert not FORBIDDEN.search(n), n


# ═════════════════════════════════════════════ route
def _route_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(SAPI.router)
    return TestClient(app)


def test_route_cleans_lower_case_and_blank_symbols(monkeypatch):
    monkeypatch.setattr(SIC, "_get_db", lambda: None)
    r = _route_client().get("/short-interest/borrow?symbols=dbgi, akan ,,")
    assert r.status_code == 200
    j = r.json()
    assert j["kind"] == BR.KIND and list(j["items"]) == ["DBGI", "AKAN"] and j["asked"] == 2
    assert j == BR.fault_payload(["DBGI", "AKAN"])
    assert BR.API_PATH == "/short-interest/borrow"
    empty = _route_client().get("/short-interest/borrow").json()
    assert empty["items"] == {} and empty["asked"] == 0


def test_route_never_500s_a_raising_read_serves_the_fault_payload(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(BR, "payload", boom)
    r = _route_client().get("/short-interest/borrow?symbols=dbgi,AKAN")
    assert r.status_code == 200
    j = r.json()
    assert j == BR.fault_payload(["dbgi", "AKAN"])
    assert {k: v["state"] for k, v in j["items"].items()} == {"DBGI": "unread", "AKAN": "unread"}
    assert j["items"]["AKAN"]["label"] == "💸 IBKR's borrow file could not be read"


def test_the_route_runs_off_the_event_loop():
    import inspect
    src = inspect.getsource(SAPI.ibkr_borrow)
    assert "asyncio.to_thread" in src and "fault_payload(syms)" in src


def test_route_serves_a_held_read(monkeypatch):
    coll, _f, _s = refreshed()
    monkeypatch.setattr(SIC, "_get_db", lambda: FakeDB(coll))
    monkeypatch.setattr(BR, "is_due", lambda state, now: False)              # the real clock: never kick here
    j = _route_client().get("/short-interest/borrow?symbols=dbgi,akan").json()   # never asyncio.run: it unsets the loop
    assert j["items"]["DBGI"]["state"] == "listed" and j["items"]["AKAN"]["state"] == "absent"


# ═════════════════════════════════════════════ ℹ️
def test_rules_fold_into_the_short_volume_pick():
    picks = SR.rules_section()["picks"]
    assert len(picks) == 8 and picks[-1] == RS.rules_pick()
    # 2026-11-26 floatguard (spec §1.7 / §6, predicted): pick 1 ('% of float = ') now names EXTREME too
    assert picks[1].startswith("% of float = ") and "EXTREME" in picks[1]
    (ext,) = [p for p in picks if "EXTREME" in p and not p.startswith("% of float = ")]
    assert picks.index(ext) == 2
    assert picks[6].startswith("Short VOLUME") and picks[6].endswith(BR.rules_pick())
    assert picks[6] == SHORT_VOLUME_PICK + " " + RULES_DEFAULT
    assert BR.rules_pick() == RULES_DEFAULT


def test_rules_move_with_the_constants(monkeypatch):
    monkeypatch.setattr(BR, "BR_REFRESH_MIN", 20)
    monkeypatch.setattr(BR, "BR_STALE_MIN", 90)
    p6 = SR.rules_section()["picks"][6]
    assert "once every 20 minutes" in p6 and "more than 90 minutes old" in p6
    assert "every 15 minutes" not in p6 and "more than 60 minutes" not in p6
    monkeypatch.setattr(BR, "BR_ABSENT_FORMS", ("label", "chip", "short"))
    assert ("A name that is not in the file reads '💸 not in IBKR's borrow file' on 🎾 cards, the other Gajjala cards "
            "and the 📋 table — never a zero.") in SR.rules_section()["picks"][6]
    monkeypatch.setattr(BR, "BR_ABSENT_FORMS", ())
    assert "A name that is not in the file shows nothing — never a zero." in SR.rules_section()["picks"][6]
    monkeypatch.setattr(BR, "BR_ABSENT_FORMS", ("short",))
    assert "reads '💸 not in file' on the 📋 table only — never a zero." in BR.rules_pick()


def test_NEGATIVE_rules_name_the_table_not_the_watch():
    p = BR.rules_pick()
    assert "📋" in p and "Watch" not in p and "👀" not in p
    assert "Watch" not in BR.BR_SURFACES_TEXT


def test_NEGATIVE_a_raising_borrow_pick_leaves_pick_6_as_it_was(monkeypatch):
    monkeypatch.setattr(BR, "rules_pick", lambda: 1 / 0)
    picks = SR.rules_section()["picks"]
    assert len(picks) == 8 and picks[6] == SHORT_VOLUME_PICK and picks[-1] == RS.rules_pick()


# ═════════════════════════════════════════════ display only
def test_NEGATIVE_display_only_nothing_in_the_trading_paths_reads_it():
    hits = []
    for sub in ("chart_maps", "push", "trading"):
        for f in (BACKEND / sub).rglob("*.py"):
            t = f.read_text(errors="ignore")
            if "ibkr_borrow" in t or "short_interest.borrow" in t or "import borrow" in t:
                hits.append(str(f))
    assert hits == []
    assert "borrow" not in (BACKEND / "crontab").read_text().lower()


# ═════════════════════════════════════════════ [C10] Python 3.9
def test_python39_safe_source():
    tree = ast.parse(SRC)
    first = tree.body[0]
    assert isinstance(first, ast.ImportFrom) and first.module == "__future__"
    assert [a.name for a in first.names] == ["annotations"]
    assert not re.search(r"(?m)^\s*match\s+.+:\s*$", SRC)
    assert "strict=" not in SRC
