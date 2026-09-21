"""🗓️ "Coming up" drill-in — `chart_maps.ipo_upcoming` + its route.

Ajay 2026-09-20: *"Can you gather similar info about these please like the
ticket and make them clicable the onesin IPO tab that are future"*.

What these tests exist to stop:

  * **A failure becoming a fact.** An unreachable EDGAR, a name EDGAR cannot
    confirm and a filing block that carries a `parse_note` must all leave
    `resolved_at` exactly where it was. Cache any of them and a 30-second blip
    serves `cached: true` for a day, on a sheet he reads before a listing.
  * **A number escaping the prospectus.** Revenue and net loss are SENTENCES,
    carried with the units and period header of THEIR OWN table — the two
    quotes come from two different tables on Amaero and print two different
    units lines. `test_wire_no_number_from_the_filing` walks the payload.
  * **The symbol's own full stop.** The cover prints `“AMRO.”` — the stop sits
    inside the closing quote. Compare it unstripped and every name-only match
    looks like a different company and gets hidden.
  * **A lowercase "underwriters" opening the bank list.** On Amaero's cover
    the running text says "…between us and the underwriters…" 2,000 characters
    before Stifel and Baird. The segment anchors are case-SENSITIVE.
  * **A second EDGAR client.** Every GET goes through
    `sepa.insider._edgar_get`, bound BARE at import — `insider._edgar_get(...)`
    would silently defeat every stub below and send these tests at live EDGAR.
  * **lxml.** It is in the api container and NOT in `backend/.venv`; this
    suite passing locally is the proof that `html.parser` is the only parser.

Nothing here touches the network: every EDGAR leg, the news engine and Mongo
are fakes.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import sepa.insider as INSIDER
from chart_maps import ipo as IPO
from chart_maps import ipo_upcoming as IU
from news_search import core
from tests.fixtures import ipo_upcoming_excerpts as FX


NOW = 1_789_800_000.0          # pinned; nothing below reads the wall clock
DAY = 24 * 3600.0

MODULE_SRC = Path(IU.__file__).read_text(encoding="utf-8")

ROW = {"symbol": "AMRO", "name": "Amaero Inc.", "date": "2026-09-23",
       "exchange": "NASDAQ Global Select", "price": "7.06",
       "numberOfShares": 7456500, "totalSharesValue": 60539323.5,
       "status": "expected"}


def _run(coro):
    return asyncio.run(coro)


# ── fakes ───────────────────────────────────────────────────────────────────
class FakeResp:
    def __init__(self, status=200, payload=None, text="", body_len=None):
        self.status_code = status
        self._payload = payload
        self.text = text
        self.content = _Body(body_len if body_len is not None else len(text))

    def json(self):
        if self._payload is None:
            raise ValueError("no json body")
        return self._payload


class _Body:
    def __init__(self, n):
        self._n = n

    def __len__(self):
        return self._n


class FakeColl:
    """An in-memory stand-in for `ipo_upcoming_cache`."""

    def __init__(self, doc=None):
        self.docs = {doc["_id"]: dict(doc)} if doc else {}
        self.writes = 0

    def find_one(self, flt):
        got = self.docs.get(flt.get("_id"))
        return dict(got) if got else None

    def replace_one(self, flt, doc, upsert=False):
        self.writes += 1
        self.docs[flt.get("_id")] = dict(doc)


def _hit(ciks, displays, form="S-1/A", filed="2026-09-18"):
    return {"_source": {"form": form, "file_date": filed,
                        "ciks": list(ciks), "display_names": list(displays)}}


def _fts_body(hits):
    return {"hits": {"hits": list(hits)}}


AMAERO_HITS = [_hit(["0002141616"], ["Amaero Inc.  (CIK 0002141616)"])]

SUB = {
    "cik": "2141616", "name": "Amaero Inc.", "sic": "3390",
    "sicDescription": "Miscellaneous Primary Metal Products",
    "stateOfIncorporation": "DE", "fiscalYearEnd": "1231",
    "tickers": [], "exchanges": [],
    "filings": {"recent": {
        "accessionNumber": ["0001193125-26-395150", "0001193125-26-300000"],
        "filingDate": ["2026-09-18", "2026-06-02"],
        "form": ["S-1/A", "S-1"],
        "primaryDocument": ["project_alchemy_-_s-1a_2.htm", "s1.htm"],
        "size": [12449161, 9000000],
    }},
}

PROSPECTUS_HTML = ("<html><head><style>b{}</style></head><body><script>x=1</script>"
                   "<p>" + FX.AMAERO_EXCERPTS + "</p></body></html>")


class EdgarRecorder:
    """Every EDGAR GET the module makes, in order."""

    def __init__(self, *, fts=None, sub=None, doc_html=PROSPECTUS_HTML,
                 fts_status=200, doc_status=200, doc_len=None, raises=False):
        self.calls = []
        self._fts = _fts_body(AMAERO_HITS if fts is None else fts)
        self._sub = SUB if sub is None else sub
        self._doc_html = doc_html
        self._fts_status = fts_status
        self._doc_status = doc_status
        self._doc_len = doc_len
        self._raises = raises

    async def __call__(self, url, *, params=None, timeout=15):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if self._raises:
            raise RuntimeError("socket is gone")
        if url == IU.EDGAR_FTS:
            if self._fts_status != 200:
                return FakeResp(status=self._fts_status)
            return FakeResp(payload=self._fts)
        if "data.sec.gov/submissions" in url:
            if self._sub is None:
                return None
            return FakeResp(payload=self._sub)
        return FakeResp(status=self._doc_status, text=self._doc_html,
                        body_len=self._doc_len)

    @property
    def fts_calls(self):
        return [c for c in self.calls if c["url"] == IU.EDGAR_FTS]

    @property
    def doc_calls(self):
        return [c for c in self.calls if "Archives/edgar/data" in c["url"]]


async def _no_headlines(symbol, name, *, now=None):
    return [], {}


def _wire(coll, monkeypatch, edgar, *, now=NOW, row=None):
    monkeypatch.setattr(IU, "_coll", lambda: coll)
    monkeypatch.setattr(IU, "_edgar_get", edgar)
    monkeypatch.setattr(IU, "headlines", _no_headlines)
    return _run(IU.lookup("AMRO", row or ROW, now=now))


# ═══════════════════════════════════════════════════════════════════════════
# the ONE engines
# ═══════════════════════════════════════════════════════════════════════════
def test_edgar_get_is_insiders_before_patching():
    """The bare-name import is the whole reason a stub can stop the network."""
    assert IU._edgar_get is INSIDER._edgar_get
    assert IU.EDGAR_FTS is INSIDER.EDGAR_FTS
    assert IU.SEC_HEADERS is INSIDER.SEC_HEADERS
    assert "from sepa.insider import _edgar_get" in MODULE_SRC


def test_every_edgar_get_goes_through_insider_edgar_get_with_the_SEC_UA(monkeypatch):
    rec = EdgarRecorder()
    _wire(FakeColl(), monkeypatch, rec)
    assert rec.calls, "the cold path must hit EDGAR"
    for call in rec.calls:
        assert re.match(r"https://(efts|data|www)\.sec\.gov/", call["url"]), call["url"]
    assert "@" in INSIDER.SEC_HEADERS["User-Agent"]
    assert "httpx." not in MODULE_SRC and "requests." not in MODULE_SRC
    assert "import httpx" not in MODULE_SRC


def test_NEGATIVE_no_llm_import():
    for banned in ("anthropic", "openai", "ollama", "lm_studio", "llm_client"):
        assert banned not in MODULE_SRC.lower(), banned


def test_NEGATIVE_board_build_never_imports_ipo_upcoming():
    """A cold open costs 3-4 paced EDGAR GETs and a multi-MB download. The
    board may never pay that per row."""
    for mod in (IPO, __import__("chart_maps.board", fromlist=["board"])):
        assert "ipo_upcoming" not in Path(mod.__file__).read_text(encoding="utf-8")


def test_html_to_text_uses_html_parser_and_runs_in_the_venv():
    assert IU.HTML_PARSER == "html.parser"
    # lxml is named in prose (to say why it is NOT used) and nowhere else: it
    # is never a string literal, never imported, and the ONE BeautifulSoup
    # call names HTML_PARSER. A `"lxml"` literal here would break this suite
    # with FeatureNotFound, because lxml is absent from backend/.venv.
    assert '"lxml"' not in MODULE_SRC and "'lxml'" not in MODULE_SRC
    assert "import lxml" not in MODULE_SRC
    assert re.search(r"BeautifulSoup\([^)]*HTML_PARSER", MODULE_SRC)
    assert len(re.findall(r"BeautifulSoup\(", MODULE_SRC)) == 1
    got = IU._html_to_text(
        "<html><style>p{}</style><script>var a=1</script>"
        "<p>Total\xa0 revenues  $ 6,305</p></html>")
    assert got == "Total revenues $ 6,305"
    assert "var a" not in got and "p{}" not in got


def test_note_says_not_measured_not_signal_dates_move():
    low = IU.NOTE.lower()
    assert "measured" in low and "signal" in low
    assert "dates move" in low and "withdrawn" in low


# ═══════════════════════════════════════════════════════════════════════════
# short_name
# ═══════════════════════════════════════════════════════════════════════════
def test_short_name_one_rule():
    assert IU.short_name("Bamboo Insurance Services, Inc.") == "Bamboo Insurance Services"
    assert IU.short_name("Amaero Inc.") == "Amaero"
    assert IU.short_name("Foo Holdings, Inc.") == "Foo"
    assert IU.short_name("Foo Holdings Inc") == "Foo"
    assert IU.short_name("SIYATA PTT") == "SIYATA PTT"
    # NEGATIVE — dropping both would leave nothing, so nothing is dropped.
    assert IU.short_name("Holdings Inc") == "Holdings Inc"
    assert IU.short_name("") == ""


# ═══════════════════════════════════════════════════════════════════════════
# pick_hit — which CIK is this company
# ═══════════════════════════════════════════════════════════════════════════
def test_pick_hit_ticker_tag_beats_name_only():
    hits = [
        _hit(["0000111111"], ["PTT Global Chemical  (CIK 0000111111)"],
             filed="2026-09-19"),
        _hit(["0002110025"], ["SIYATA PTT  (PTT)  (CIK 0002110025)"],
             form="F-1/A", filed="2026-09-18"),
    ]
    got, reason = IU.pick_hit(hits, symbol="PTT", name="SIYATA PTT")
    assert reason is None
    assert got["cik"] == "0002110025" and got["method"] == "ticker_tag"
    assert got["form"] == "F-1/A" and got["file_date"] == "2026-09-18"


def test_pick_hit_name_similarity_accepts_the_amaero_shape():
    """Amaero's hits carry NO ticker tag — the name is all there is."""
    got, reason = IU.pick_hit(AMAERO_HITS, symbol="AMRO", name="Amaero Inc.")
    assert reason is None
    assert got["cik"] == "0002141616" and got["method"] == "name"


def test_pick_hit_ties_go_to_the_newest_file_date():
    hits = [
        _hit(["0002141616"], ["Amaero Inc.  (CIK 0002141616)"], form="S-1",
             filed="2026-06-02"),
        _hit(["0002141616"], ["Amaero Inc.  (CIK 0002141616)"], form="S-1/A",
             filed="2026-09-18"),
    ]
    got, _ = IU.pick_hit(hits, symbol="AMRO", name="Amaero Inc.")
    assert got["file_date"] == "2026-09-18"


def test_pick_hit_NEGATIVE_unrelated_names_are_a_miss_not_the_top_hit():
    hits = [_hit(["0000999999"], ["Bumble Bee Foods LLC  (BUMB)  (CIK 0000999999)"])]
    got, reason = IU.pick_hit(hits, symbol="AMRO", name="Amaero Inc.")
    assert got is None
    assert reason == "no registration filing found for this name"


def test_pick_hit_NEGATIVE_zero_hits_is_a_sentence_no_exception():
    got, reason = IU.pick_hit([], symbol="AMRO", name="Amaero Inc.")
    assert got is None and isinstance(reason, str) and reason


def test_pick_hit_NEGATIVE_co_registrant_tag_confirms_only_its_own_cik():
    """`ciks` and `display_names` are PARALLEL. A tag printed on the
    co-registrant's line confirms the CO-REGISTRANT, never the other filer."""
    hits = [_hit(["0000000AAA", "0000000BBB"],
                 ["Other Co  (PTT)  (CIK 0000000AAA)",
                  "SIYATA PTT  (CIK 0000000BBB)"])]
    got, _ = IU.pick_hit(hits, symbol="PTT", name="Nothing Like This Inc.")
    assert got["cik"] == "0000000AAA" and got["method"] == "ticker_tag"
    assert got["display_name"].startswith("Other Co")


def test_pick_hit_NEGATIVE_malformed_parallel_lists_are_skipped():
    hits = [_hit(["0002141616", "0009999999"], ["Amaero Inc.  (CIK 0002141616)"])]
    got, reason = IU.pick_hit(hits, symbol="AMRO", name="Amaero Inc.")
    assert got is None and reason


def test_display_name_parts():
    assert IU.display_name_parts("SIYATA PTT  (PTT)  (CIK 0002110025)") == \
        ("SIYATA PTT", "PTT", "0002110025")
    assert IU.display_name_parts("Amaero Inc.  (CIK 0002141616)") == \
        ("Amaero Inc.", None, "0002141616")


# ═══════════════════════════════════════════════════════════════════════════
# full-text search
# ═══════════════════════════════════════════════════════════════════════════
def test_fts_retries_once_with_the_short_name_on_zero_hits(monkeypatch):
    rec = EdgarRecorder(fts=[])
    monkeypatch.setattr(IU, "_edgar_get", rec)
    hits, url = _run(IU.fts_search("Bamboo Insurance Services, Inc.",
                                   today=date(2026, 9, 20)))
    assert hits == []                       # EDGAR answered — with nothing
    assert len(rec.fts_calls) == 2, "two queries, never a third"
    assert rec.fts_calls[0]["params"]["q"] == '"Bamboo Insurance Services, Inc."'
    assert rec.fts_calls[1]["params"]["q"] == '"Bamboo Insurance Services"'
    assert rec.fts_calls[0]["params"]["forms"] == IU.FTS_FORMS
    assert rec.fts_calls[0]["params"]["dateRange"] == "custom"
    assert rec.fts_calls[0]["params"]["startdt"] == "2025-09-20"
    assert rec.fts_calls[0]["params"]["enddt"] == "2026-09-20"
    assert url.startswith(IU.EDGAR_FTS + "?")


def test_fts_NEGATIVE_edgar_down_is_None_not_an_empty_list(monkeypatch):
    """`None` = could not be reached, `[]` = answered with nothing. `lookup`
    says a different sentence for each, so they can never collapse."""
    async def _down(url, *, params=None, timeout=15):
        return None
    monkeypatch.setattr(IU, "_edgar_get", _down)
    hits, _url = _run(IU.fts_search("Amaero Inc.", today=date(2026, 9, 20)))
    assert hits is None


def test_fts_NEGATIVE_an_exception_never_escapes(monkeypatch):
    async def _boom(url, *, params=None, timeout=15):
        raise RuntimeError("dns")
    monkeypatch.setattr(IU, "_edgar_get", _boom)
    hits, _url = _run(IU.fts_search("Amaero Inc.", today=date(2026, 9, 20)))
    assert hits is None


# ═══════════════════════════════════════════════════════════════════════════
# submissions → the newest registration document
# ═══════════════════════════════════════════════════════════════════════════
def test_company_block_is_edgars_own_record_all_strings():
    got = IU.company_block(SUB)
    assert got == {"name": "Amaero Inc.", "cik": "0002141616", "sic": "3390",
                   "sic_description": "Miscellaneous Primary Metal Products",
                   "state": "DE", "fiscal_year_end": "1231"}
    assert all(v is None or isinstance(v, str) for v in got.values())


def test_latest_prospectus_424B4_outranks_a_newer_S1A():
    sub = {"cik": "2141616", "filings": {"recent": {
        "accessionNumber": ["0001-26-1", "0001-26-2"],
        "filingDate": ["2026-09-18", "2026-09-10"],
        "form": ["S-1/A", "424B4"],
        "primaryDocument": ["a.htm", "b.htm"], "size": [1, 2]}}}
    got = IU.latest_prospectus(sub)
    assert got["form"] == "424B4" and got["filed"] == "2026-09-10"
    assert got["url"] == ("https://www.sec.gov/Archives/edgar/data/2141616/"
                          "0001262/b.htm")


def test_latest_prospectus_amendment_outranks_the_original():
    got = IU.latest_prospectus(SUB)
    assert got["form"] == "S-1/A"
    assert got["accession"] == "0001193125-26-395150"
    assert got["primary_document"] == "project_alchemy_-_s-1a_2.htm"
    assert got["url"] == ("https://www.sec.gov/Archives/edgar/data/2141616/"
                          "000119312526395150/project_alchemy_-_s-1a_2.htm")


def test_latest_prospectus_none_when_no_registration_form():
    sub = {"cik": "2141616", "filings": {"recent": {
        "accessionNumber": ["0001-26-1"], "filingDate": ["2026-09-18"],
        "form": ["8-K"], "primaryDocument": ["a.htm"], "size": [1]}}}
    assert IU.latest_prospectus(sub) is None


def test_fetch_prospectus_NEGATIVE_reasons(monkeypatch):
    async def _big(url, *, params=None, timeout=15):
        return FakeResp(text="x", body_len=IU.PROSPECTUS_MAX_BYTES + 1)
    monkeypatch.setattr(IU, "_edgar_get", _big)
    assert _run(IU.fetch_prospectus_html("u")) == \
        (None, "prospectus larger than 15 MB; not parsed")

    async def _503(url, *, params=None, timeout=15):
        return FakeResp(status=503)
    monkeypatch.setattr(IU, "_edgar_get", _503)
    assert _run(IU.fetch_prospectus_html("u")) == (None, "EDGAR answered 503")

    async def _none(url, *, params=None, timeout=15):
        return None
    monkeypatch.setattr(IU, "_edgar_get", _none)
    assert _run(IU.fetch_prospectus_html("u")) == (None, "EDGAR could not be reached")


# ═══════════════════════════════════════════════════════════════════════════
# extract — every value is a printed string
# ═══════════════════════════════════════════════════════════════════════════
def test_extract_amaero_overview_symbol_shares_price_underwriters_revenue_net_loss():
    got = IU.extract(FX.AMAERO_EXCERPTS, symbol="AMRO")
    assert got["overview"].startswith(
        "We are a leading U.S.-based producer of high-value refractory and "
        "titanium alloy spherical metal powders")
    assert got["overview"].endswith(".")
    assert got["proposed_symbol_line"] == (
        "We have applied to list our common stock on the Nasdaq Global Select "
        "Market (the “Nasdaq”) under the symbol “AMRO.”")
    assert got["shares_offered_line"] == \
        "We are selling 7,456,500 shares of our common stock."
    assert got["price_line"].startswith(
        "The initial public offering price of our common stock will be "
        "determined through negotiations")
    assert got["underwriters"] == ["Stifel", "Baird", "Lake Street"]
    assert got["revenue_line"] == \
        "Total revenues from contracts with customers $ 6,305 $ 1,317 $ 4,988 379 %"
    assert got["net_loss_line"] == (
        "Net loss attributable to stockholders (1) $ (18,378 ) $ (12,725 ) "
        "$ (13,433 ) $ (8,731 )")


def test_extract_symbol_capture_strips_the_full_stop():
    """The cover prints `“AMRO.”` — the stop is INSIDE the closing quote."""
    got = IU.extract(FX.AMAERO_EXCERPTS, symbol="AMRO")
    assert got["symbol_in_filing"] == "AMRO"
    assert got["symbol_in_filing"] != "AMRO."
    assert "AMRO" in got["proposed_symbol_line"]
    assert "3DA" not in got["proposed_symbol_line"], "the ASX line is not ours"


def test_extract_range_cover_finds_the_between_sentence_and_three_banks():
    got = IU.extract(FX.RANGE_COVER, symbol="XXX")
    assert got["price_line"] == (
        "We currently estimate that the initial public offering price will be "
        "between $18.00 and $20.00 per share.")
    assert got["underwriters"] == ["Goldman Sachs", "J.P. Morgan", "Roth Capital"]
    assert "Roth" not in [u for u in got["underwriters"] if u == "Roth"]


def test_extract_per_quote_units_and_periods_amaero():
    """The two quotes come from two DIFFERENT tables. One shared units line
    would print the wrong unit under one of them."""
    got = IU.extract(FX.AMAERO_EXCERPTS, symbol="AMRO")
    assert got["revenue_units_line"] == "(in thousands)"
    assert got["revenue_period_line"] == "Year ended December 31, 2025"
    assert got["net_loss_units_line"] == \
        "in thousands, except share and per share data"
    assert got["net_loss_period_line"] == "Six Months ended June 30, 2025"
    assert got["revenue_units_line"] != got["net_loss_units_line"]
    assert got["revenue_period_line"] != got["net_loss_period_line"]


def test_extract_per_quote_units_and_periods_synthetic_present():
    """One table, both quotes, "Ended" capitalised and two years joined by
    "and" — the `[Ee]nded` case and the multi-year tail."""
    got = IU.extract(FX.HEADER_TABLE, symbol="XXX")
    assert got["revenue_line"] == "Net revenues $ 1,234 $ 987"
    assert got["net_loss_line"] == "Net loss $ (156 ) $ (278 )"
    for key in ("revenue_units_line", "net_loss_units_line"):
        assert got[key] == "(in millions, except per share data)"
    for key in ("revenue_period_line", "net_loss_period_line"):
        assert got[key] == "Fiscal Years Ended January 31, 2026 and 2025"


def test_extract_NEGATIVE_units_and_periods_None_when_absent():
    text = "Net revenues $ 1,234 $ 987 and nothing else was printed here."
    got = IU.extract(text, symbol="XXX")
    assert got["revenue_line"] == "Net revenues $ 1,234 $ 987"
    assert got["revenue_units_line"] is None
    assert got["revenue_period_line"] is None


def test_extract_NEGATIVE_misses_are_None_never_empty_or_zero():
    got = IU.extract(FX.NOTHING, symbol="AMRO")
    for key in IU.EXTRACT_KEYS:
        if key in ("underwriters", "extracted_at"):
            continue
        assert got[key] is None, f"{key} must be None, got {got[key]!r}"
    assert got["underwriters"] == []           # the one list
    assert isinstance(got["extracted_at"], str)


def test_extract_NEGATIVE_underwriters_only_from_the_cover():
    """A bank named past `COVER_CHARS` is not on the cover and is not listed."""
    filler = "Filler sentence about nothing at all. " * 900
    assert len(filler) > IU.COVER_CHARS
    text = filler + "Joint Bookrunning Managers Goldman Sachs Prospectus dated , 2026"
    assert IU.extract(text, symbol="XXX")["underwriters"] == []
    # and the same tail INSIDE the cover window is found, so the negative is
    # about the boundary and not about the regex.
    assert IU.extract(text[-200:], symbol="XXX")["underwriters"] == ["Goldman Sachs"]


def test_extract_NEGATIVE_lowercase_underwriters_sentence_does_not_open_the_segment():
    got = IU.extract(FX.LOWER_UNDERWRITERS_COVER, symbol="XXX")
    assert got["underwriters"] == ["Stifel", "Baird"]


def test_extract_NEGATIVE_a_label_with_no_figures_is_not_a_quote():
    text = ("Revenue recognition is described in Note 2. Our revenues are "
            "discussed below in detail (1) and nowhere else.")
    got = IU.extract(text, symbol="XXX")
    assert got["revenue_line"] is None


def test_parse_filing_is_strip_plus_extract():
    got = IU.parse_filing(PROSPECTUS_HTML, symbol="AMRO")
    assert got["symbol_in_filing"] == "AMRO"
    assert got["underwriters"] == ["Stifel", "Baird", "Lake Street"]


# ═══════════════════════════════════════════════════════════════════════════
# headlines
# ═══════════════════════════════════════════════════════════════════════════
def test_headlines_use_the_one_news_engine_7d_window_audit_tag_and_relevance(monkeypatch):
    seen = {}

    async def _search(**kw):
        seen.update(kw)
        return {"items": [
            {"title": "Amaero prices IPO at $7.06", "url": "u1",
             "source": "Reuters", "published": 1789700000},
            {"title": "Dollar rallies on rate bets", "url": "u2",
             "source": "WSJ", "published": 1789700001},
        ], "query": 'Amaero', "counts": {}, "window_hours": 168}

    monkeypatch.setattr(core, "search", _search)
    items, meta = _run(IU.headlines("AMRO", "Amaero Inc.", now=NOW))
    assert seen["keyword"] == '"Amaero"'
    assert seen["window_hours"] == 168 == IU.HEADLINES_WINDOW_HOURS
    assert seen["audit"] == "ipo_upcoming" == IU.AUDIT_TAG
    assert [i["title"] for i in items] == ["Amaero prices IPO at $7.06"]
    assert items[0]["published"] == 1789700000
    assert meta["window_hours"] == 168


def test_headlines_NEGATIVE_a_dead_provider_is_an_empty_list(monkeypatch):
    async def _boom(**kw):
        raise RuntimeError("provider down")
    monkeypatch.setattr(core, "search", _boom)
    assert _run(IU.headlines("AMRO", "Amaero Inc.")) == ([], {})


# ═══════════════════════════════════════════════════════════════════════════
# lookup — the cache rule
# ═══════════════════════════════════════════════════════════════════════════
def _fresh_doc(**over):
    doc = {"_id": "AMRO", "name": "Amaero Inc.", "resolved_at": NOW - 10,
           "headlines_at": NOW - 10, "error": None,
           "resolution": {"method": "name", "query": '"Amaero Inc."',
                          "hits": 6, "reason": None},
           "company": IU.company_block(SUB),
           "filing": dict(IU._filing_head(IU.latest_prospectus(SUB)),
                          parse_note=None,
                          **{k: None for k in IU.EXTRACT_KEYS}),
           "headlines": [], "sources": dict(IU._EMPTY_SOURCES)}
    doc["filing"]["underwriters"] = []
    doc["filing"]["symbol_in_filing"] = "AMRO"
    doc.update(over)
    return doc


def test_lookup_cache_is_read_before_any_network(monkeypatch):
    coll = FakeColl(_fresh_doc())

    async def _explode(*a, **k):
        raise AssertionError("the warm path must not touch the network")

    monkeypatch.setattr(IU, "_coll", lambda: coll)
    monkeypatch.setattr(IU, "_edgar_get", _explode)
    monkeypatch.setattr(core, "search", _explode)
    got = _run(IU.lookup("AMRO", ROW, now=NOW))
    assert got["cached"] is True
    assert got["ok"] is True and got["symbol"] == "AMRO"
    assert got["calendar_row"] == ROW
    assert got["note"] == IU.NOTE
    assert coll.writes == 0


def test_lookup_new_accession_re_extracts_same_accession_reuses(monkeypatch):
    coll = FakeColl()
    rec = EdgarRecorder()
    first = _wire(coll, monkeypatch, rec, now=NOW)
    assert first["cached"] is False
    assert first["filing"]["accession"] == "0001193125-26-395150"
    assert first["filing"]["underwriters"] == ["Stifel", "Baird", "Lake Street"]
    assert len(rec.doc_calls) == 1

    # a day later: stale resolve, same accession, the block parsed cleanly
    rec2 = EdgarRecorder()
    second = _wire(coll, monkeypatch, rec2, now=NOW + DAY + 1)
    assert second["cached"] is False
    assert len(rec2.doc_calls) == 0, "a clean block keyed by accession is kept"
    assert second["filing"]["revenue_line"] == first["filing"]["revenue_line"]

    # a NEW accession re-extracts
    newer = json.loads(json.dumps(SUB))
    newer["filings"]["recent"]["accessionNumber"][0] = "0001193125-26-499999"
    rec3 = EdgarRecorder(sub=newer)
    third = _wire(coll, monkeypatch, rec3, now=NOW + 2 * DAY + 2)
    assert len(rec3.doc_calls) == 1
    assert third["filing"]["accession"] == "0001193125-26-499999"


def test_lookup_stale_headlines_refresh_without_refetching_the_prospectus(monkeypatch):
    coll = FakeColl(_fresh_doc(headlines_at=NOW - DAY - 5))
    rec = EdgarRecorder()
    calls = []

    async def _heads(symbol, name, *, now=None):
        calls.append(symbol)
        return [{"title": "Amaero files amendment", "url": "u", "source": "SEC",
                 "published": 1789700000}], {}

    monkeypatch.setattr(IU, "_coll", lambda: coll)
    monkeypatch.setattr(IU, "_edgar_get", rec)
    monkeypatch.setattr(IU, "headlines", _heads)
    got = _run(IU.lookup("AMRO", ROW, now=NOW))
    assert calls == ["AMRO"]
    assert rec.calls == [], "a fresh resolve costs no EDGAR GET"
    assert got["cached"] is False
    assert got["headlines"][0]["title"] == "Amaero files amendment"
    assert got["filing"]["accession"] == "0001193125-26-395150"


def test_lookup_NEGATIVE_edgar_down_serves_calendar_row_filing_None_error_sentence(monkeypatch):
    coll = FakeColl()

    async def _down(url, *, params=None, timeout=15):
        return None

    monkeypatch.setattr(IU, "_coll", lambda: coll)
    monkeypatch.setattr(IU, "_edgar_get", _down)
    monkeypatch.setattr(IU, "headlines", _no_headlines)
    got = _run(IU.lookup("AMRO", ROW, now=NOW))
    assert got["filing"] is None and got["company"] is None
    assert got["calendar_row"] == ROW
    assert got["error"].startswith("EDGAR could not be reached")
    assert got["cached"] is False
    assert got["resolved_at"] is None, "a failure never advances the clock"
    assert coll.docs["AMRO"]["resolved_at"] is None

    # the SECOND call re-hits EDGAR — a 30 s blip is a 30 s blip, never a day
    rec = EdgarRecorder()
    monkeypatch.setattr(IU, "_edgar_get", rec)
    again = _run(IU.lookup("AMRO", ROW, now=NOW + 60))
    assert rec.fts_calls, "the next click must ask EDGAR again"
    assert again["cached"] is False
    assert again["filing"]["accession"] == "0001193125-26-395150"


def test_lookup_NEGATIVE_edgar_raising_is_the_same_sentence(monkeypatch):
    coll = FakeColl()
    rec = EdgarRecorder(raises=True)
    got = _wire(coll, monkeypatch, rec)
    assert got["error"].startswith("EDGAR could not be reached")
    assert got["resolved_at"] is None


def test_lookup_NEGATIVE_no_hit_is_not_cached(monkeypatch):
    coll = FakeColl()
    rec = EdgarRecorder(fts=[])
    first = _wire(coll, monkeypatch, rec, now=NOW)
    assert first["filing"] is None
    assert first["error"] == IU.NO_HIT_ERROR
    assert first["resolution"]["reason"] == "no registration filing found for this name"
    assert first["resolution"]["hits"] == 0
    assert first["resolved_at"] is None

    rec2 = EdgarRecorder(fts=[])
    second = _wire(coll, monkeypatch, rec2, now=NOW + 60)
    assert len(rec2.fts_calls) == 2, "the next click asks EDGAR again"
    assert second["error"] == IU.NO_HIT_ERROR
    assert second["cached"] is False


def test_lookup_NEGATIVE_filing_block_with_a_parse_note_is_refetched_on_the_next_resolve(monkeypatch):
    stale = _fresh_doc(resolved_at=NOW - DAY - 5)
    stale["filing"]["parse_note"] = "EDGAR answered 503"
    coll = FakeColl(stale)
    rec = EdgarRecorder()
    got = _wire(coll, monkeypatch, rec, now=NOW)
    assert len(rec.doc_calls) == 1, "a block carrying a parse_note is not a fact"
    assert got["filing"]["parse_note"] is None
    assert got["filing"]["underwriters"] == ["Stifel", "Baird", "Lake Street"]

    # now that it parsed cleanly, the SAME accession is reused
    rec2 = EdgarRecorder()
    _wire(coll, monkeypatch, rec2, now=NOW + DAY + 10)
    assert len(rec2.doc_calls) == 0


def test_lookup_NEGATIVE_prospectus_over_15MB_serves_link_and_parse_note(monkeypatch):
    coll = FakeColl()
    rec = EdgarRecorder(doc_len=IU.PROSPECTUS_MAX_BYTES + 1)
    got = _wire(coll, monkeypatch, rec, now=NOW)
    f = got["filing"]
    assert f["parse_note"] == "prospectus larger than 15 MB; not parsed"
    assert f["url"].endswith("project_alchemy_-_s-1a_2.htm")
    assert f["overview"] is None and f["revenue_line"] is None
    assert f["underwriters"] == []
    # the RESOLVE succeeded — only the parse did not.
    assert got["resolved_at"] == IU._iso(NOW)
    # and the block re-fetches next time, because parse_note is set.
    rec2 = EdgarRecorder()
    _wire(coll, monkeypatch, rec2, now=NOW + DAY + 10)
    assert len(rec2.doc_calls) == 1


def test_lookup_NEGATIVE_name_only_hit_whose_filing_names_another_symbol_is_hidden(monkeypatch):
    coll = FakeColl()
    rec = EdgarRecorder()
    row = dict(ROW, symbol="ZZZZ")
    monkeypatch.setattr(IU, "_coll", lambda: coll)
    monkeypatch.setattr(IU, "_edgar_get", rec)
    monkeypatch.setattr(IU, "headlines", _no_headlines)
    got = _run(IU.lookup("ZZZZ", row, now=NOW))
    assert got["resolution"]["method"] == "name"
    assert got["filing"] is None
    assert got["error"] == ("the registration filing found for this name names "
                            "the symbol AMRO, not ZZZZ; not shown")
    # the filing WAS read, so the mismatch is a fact and the clock advances
    assert got["resolved_at"] == IU._iso(NOW)


def test_lookup_name_only_hit_with_a_trailing_stop_is_NOT_hidden(monkeypatch):
    """The Amaero shape: the cover prints `“AMRO.”` and the calendar says AMRO."""
    coll = FakeColl()
    got = _wire(coll, monkeypatch, EdgarRecorder(), now=NOW)
    assert got["resolution"]["method"] == "name"
    assert got["filing"] is not None, "the full stop is stripped at capture"
    assert got["filing"]["symbol_in_filing"] == "AMRO"
    assert got["error"] is None


def test_lookup_edgar_down_with_a_clean_stale_filing_serves_it_with_the_cached_sentence(monkeypatch):
    stale = _fresh_doc(resolved_at=NOW - DAY - 5)
    stale["filing"]["revenue_line"] = "Total revenues $ 6,305"
    coll = FakeColl(stale)

    async def _down(url, *, params=None, timeout=15):
        return None

    monkeypatch.setattr(IU, "_coll", lambda: coll)
    monkeypatch.setattr(IU, "_edgar_get", _down)
    monkeypatch.setattr(IU, "headlines", _no_headlines)
    got = _run(IU.lookup("AMRO", ROW, now=NOW))
    assert got["filing"]["revenue_line"] == "Total revenues $ 6,305"
    assert got["error"].startswith("EDGAR could not be reached; showing the "
                                   "filing cached ")
    assert got["cached"] is False, "a stale serve is never `cached`"
    assert got["resolved_at"] == IU._iso(NOW - DAY - 5), "the clock stands still"


def test_lookup_NEGATIVE_edgar_down_with_a_parse_noted_stale_filing_is_not_served(monkeypatch):
    stale = _fresh_doc(resolved_at=NOW - DAY - 5)
    stale["filing"]["parse_note"] = "EDGAR answered 503"
    coll = FakeColl(stale)

    async def _down(url, *, params=None, timeout=15):
        return None

    monkeypatch.setattr(IU, "_coll", lambda: coll)
    monkeypatch.setattr(IU, "_edgar_get", _down)
    monkeypatch.setattr(IU, "headlines", _no_headlines)
    got = _run(IU.lookup("AMRO", ROW, now=NOW))
    assert got["filing"] is None, "a failed block is never served as a fact"
    assert got["error"] == ("EDGAR could not be reached: the full-text search "
                            "did not answer")


def test_lookup_NEGATIVE_mongo_down_still_answers(monkeypatch):
    monkeypatch.setattr(IU, "_coll", lambda: None)
    monkeypatch.setattr(IU, "_edgar_get", EdgarRecorder())
    monkeypatch.setattr(IU, "headlines", _no_headlines)
    got = _run(IU.lookup("AMRO", ROW, now=NOW))
    assert got["ok"] is True and got["cached"] is False
    assert got["filing"]["accession"] == "0001193125-26-395150"


def test_lookup_timestamps_are_epoch_in_mongo_iso_on_the_wire(monkeypatch):
    coll = FakeColl()
    got = _wire(coll, monkeypatch, EdgarRecorder(), now=NOW)
    doc = coll.docs["AMRO"]
    assert isinstance(doc["resolved_at"], float) and doc["resolved_at"] == NOW
    assert isinstance(doc["headlines_at"], float)
    stamp = datetime.fromtimestamp(NOW, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert stamp == "2026-09-19T06:40:00Z"
    assert got["resolved_at"] == stamp
    assert got["headlines_at"] == stamp
    assert IU._iso(None) is None


def test_lookup_parses_in_a_thread(monkeypatch):
    """The ONLY thing that leaves the event loop is the CPU-bound parse."""
    seen = []
    real = asyncio.to_thread

    async def _record(fn, *a, **kw):
        seen.append(fn)
        return await real(fn, *a, **kw)

    monkeypatch.setattr(IU.asyncio, "to_thread", _record)
    _wire(FakeColl(), monkeypatch, EdgarRecorder(), now=NOW)
    assert seen == [IU.parse_filing]


def test_wire_no_number_from_the_filing(monkeypatch):
    got = _wire(FakeColl(), monkeypatch, EdgarRecorder(), now=NOW)

    def _walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                _walk(v, f"{path}[{i}]")
        else:
            assert not isinstance(node, (int, float)) or isinstance(node, bool), \
                f"{path} carries a number from the filing: {node!r}"

    _walk(got["filing"], "filing")
    _walk(got["company"], "company")
    assert isinstance(got["filing"]["revenue_line"], str)
    assert isinstance(got["company"]["cik"], str) and len(got["company"]["cik"]) == 10
    assert "size" not in got["filing"]
    # the numbers that ARE allowed live only on the calendar row and the counts
    assert got["calendar_row"]["numberOfShares"] == 7456500
    assert got["headlines_window_days"] == 7
    assert isinstance(got["resolution"]["hits"], int)


def test_wire_shape_is_the_contract(monkeypatch):
    got = _wire(FakeColl(), monkeypatch, EdgarRecorder(), now=NOW)
    assert set(got) == {
        "ok", "symbol", "calendar_row", "company", "filing", "headlines",
        "headlines_window_days", "headlines_at", "resolution", "error",
        "cached", "resolved_at", "sources", "note"}
    assert set(got["filing"]) == {
        "form", "filed", "accession", "primary_document", "url", "parse_note",
        *IU.EXTRACT_KEYS}
    assert set(got["sources"]) == {"edgar_search_url", "submissions_url",
                                   "filing_url"}
    assert got["sources"]["filing_url"].startswith(
        "https://www.sec.gov/Archives/edgar/data/")
    assert got["sources"]["submissions_url"] == \
        "https://data.sec.gov/submissions/CIK0002141616.json"


# ═══════════════════════════════════════════════════════════════════════════
# the route
# ═══════════════════════════════════════════════════════════════════════════
def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps.api import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_200_404_503(monkeypatch):
    c = _client()

    async def _lookup(sym, row, *, now=None):
        return {"ok": True, "symbol": sym, "calendar_row": row, "note": IU.NOTE}

    monkeypatch.setattr(IU, "calendar_row", lambda s: (ROW, True, None))
    monkeypatch.setattr(IU, "lookup", _lookup)
    r = c.get("/chart-maps/ipo/upcoming/amro")
    assert r.status_code == 200
    assert r.json()["symbol"] == "AMRO", "the path symbol is upper-cased"

    monkeypatch.setattr(IU, "calendar_row", lambda s: (None, True, None))
    r = c.get("/chart-maps/ipo/upcoming/ZZZZ")
    assert r.status_code == 404
    assert str(IPO.FORWARD_DAYS) in r.json()["detail"]
    assert "ZZZZ" in r.json()["detail"]

    monkeypatch.setattr(IU, "calendar_row", lambda s: (None, False, "finnhub 5xx"))
    r = c.get("/chart-maps/ipo/upcoming/AMRO")
    assert r.status_code == 503
    assert "finnhub 5xx" in r.json()["detail"]


def test_calendar_row_finds_the_expected_row(monkeypatch):
    rows = [dict(ROW), dict(ROW, symbol="BMB", name="Bamboo Insurance Services, Inc.")]
    monkeypatch.setattr(IU.ipo, "calendar",
                        lambda a, b: {"ok": True, "rows": rows, "reason": None})
    monkeypatch.setattr(IU.ipo, "upcoming", lambda r, t: rows)
    row, ok, reason = IU.calendar_row("bmb")
    assert ok is True and reason is None and row["symbol"] == "BMB"
    # NEGATIVE — a symbol the calendar does not carry
    row, ok, _ = IU.calendar_row("ZZZZ")
    assert row is None and ok is True


def test_calendar_row_NEGATIVE_unreadable_calendar_reports_not_ok(monkeypatch):
    monkeypatch.setattr(IU.ipo, "calendar",
                        lambda a, b: {"ok": False, "rows": [], "reason": "finnhub 5xx"})
    row, ok, reason = IU.calendar_row("AMRO")
    assert row is None and ok is False and reason == "finnhub 5xx"


def test_lookup_NEGATIVE_a_zero_hit_answer_never_erases_a_clean_cached_filing(monkeypatch):
    """Verify miss 2026-09-20: FTS answering with ZERO hits used to write
    `filing: None` over a block that had parsed cleanly, so the next call with
    EDGAR down served nothing and the accession reuse was gone.

    Wire: the zero-hit call still says `filing: None` + the no-hit sentence
    (a failure is never served as a fact). Store: the clean block survives.
    Then EDGAR goes down: the stale clean block is what gets shown.
    """
    coll = FakeColl()
    first = _wire(coll, monkeypatch, EdgarRecorder(), now=NOW)
    assert first["filing"]["accession"] == "0001193125-26-395150"
    assert coll.docs["AMRO"]["filing"]["parse_note"] is None

    # a day later EDGAR answers, with nothing
    second = _wire(coll, monkeypatch, EdgarRecorder(fts=[]), now=NOW + DAY + 1)
    assert second["filing"] is None
    assert second["error"] == IU.NO_HIT_ERROR
    assert coll.docs["AMRO"]["filing"]["accession"] == "0001193125-26-395150", \
        "the clean block must survive a zero-hit answer in the store"

    # then EDGAR does not answer at all: the stale clean block is shown
    third = _wire(coll, monkeypatch, EdgarRecorder(raises=True), now=NOW + 2 * DAY + 2)
    assert third["filing"] is not None
    assert third["filing"]["accession"] == "0001193125-26-395150"
    assert third["error"], "an EDGAR-down answer carries its sentence"


def test_lookup_NEGATIVE_a_parse_failure_block_is_still_never_kept_as_a_fact(monkeypatch):
    """The keep-rule is for CLEAN blocks only: a block carrying `parse_note`
    is a failure, and a zero-hit answer after it stores nothing in its place."""
    coll = FakeColl()
    bad = _wire(coll, monkeypatch, EdgarRecorder(doc_status=500), now=NOW)
    assert bad["filing"] is not None and bad["filing"].get("parse_note")
    _wire(coll, monkeypatch, EdgarRecorder(fts=[]), now=NOW + DAY + 1)
    assert coll.docs["AMRO"].get("filing") is None
