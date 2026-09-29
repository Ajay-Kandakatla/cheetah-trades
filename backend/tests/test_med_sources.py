"""🧬 Medical catalysts — sources (catalysts/medical/sources.py, spec §3.5).

Real captured payloads (tests/fixtures/medical/, key-scrubbed); every network
call is an injected async stub. NEGATIVES: undated dropped, a `related` story
that never names the company dropped, a partner tag never becomes the issuer,
a non-healthcare SIC dropped, a boilerplate-only 8-K (no EX-99.1) skipped, the
python-requests UA 404 returns nothing without raising, and a key inside an
exception text is never stored.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts.medical import sources as SRC   # noqa: E402

ET = ZoneInfo("America/New_York")
FX = Path(__file__).resolve().parent / "fixtures" / "medical"


def load(name):
    p = FX / name
    return json.loads(p.read_text()) if p.suffix == ".json" else p.read_text()


def resp(status=200, body=None, text=None):
    return SimpleNamespace(status_code=status, json=lambda: body, text=text if text is not None else "")


def run(coro):
    return asyncio.run(coro)


def rows_fetch(rows):
    async def f(_sym, _days):
        return rows
    return f


# ── Finnhub ─────────────────────────────────────────────────────────────────
def test_finnhub_KOD_fixture_becomes_articles_keyed_and_dated():
    counts = {}
    arts = run(SRC.finnhub_articles("KOD", company="Kodiak Sciences Inc.", fetch=rows_fetch(load("finnhub_KOD.json")),
                                    counts=counts))
    first = [a for a in arts if a["key"] == "fh:142466027"][0]
    assert first["title"].startswith("Kodiak Sciences Says Phase 3 DAYBREAK Study Met Primary Endpoints")
    assert first["provider"] == "finnhub" and first["ticker"] == "KOD" and first["source"] == "Benzinga"
    assert datetime.fromtimestamp(first["published"], timezone.utc).astimezone(ET).strftime("%H:%M") == "02:34"
    assert len(first["context"]) <= SRC.EXHIBIT_LEAD_CHARS
    # the 06:30 PR copy never names the company in its TITLE -> dropped by the title rule
    assert not [a for a in arts if a["key"] == "fh:142465362"]
    assert counts["irrelevant_dropped"] >= 1


def test_NEGATIVE_undated_rows_are_dropped_never_stamped_now():
    rows = load("finnhub_KOD.json")[:2]
    rows[0] = dict(rows[0], datetime=0)
    rows[1] = dict(rows[1], datetime=None)
    counts = {}
    arts = run(SRC.finnhub_articles("KOD", company="Kodiak Sciences Inc.", fetch=rows_fetch(rows), counts=counts))
    assert arts == [] and counts["undated_dropped"] == 2


def test_NEGATIVE_a_related_story_that_never_names_the_company_is_dropped():
    """Finnhub's `related` is the ASKED ticker even on others' stories."""
    rows = load("finnhub_MRNA_subset.json")
    arts = run(SRC.finnhub_articles("MRNA", company="Moderna, Inc.", fetch=rows_fetch(rows)))
    titles = [a["title"] for a in arts]
    assert not any(t.startswith("Tempus AI") for t in titles)
    assert not any(t.startswith("AMD Hits $1 Trillion") for t in titles)
    assert any(t.startswith("Moderna Announces Late-Breaking Data") for t in titles)


def test_a_fetch_that_raises_is_counted_and_its_key_redacted(caplog):
    async def boom(_s, _d):
        raise RuntimeError("GET https://finnhub.io/api/v1/company-news?symbol=KOD&token=SECRET123")
    counts = {}
    with caplog.at_level(logging.WARNING, logger="catalysts.medical.sources"):
        assert run(SRC.finnhub_articles("KOD", company="Kodiak", fetch=boom, counts=counts)) == []
    assert counts["errors"] == 1
    assert "SECRET123" not in caplog.text and "token=<redacted>" in caplog.text


def test_redact_exc_covers_token_and_apiKey():
    t = SRC.redact_exc(ValueError("x?apiKey=AAA&token=BBB"))
    assert "AAA" not in t and "BBB" not in t and t.startswith("ValueError: ")


# ── Massive issuer ──────────────────────────────────────────────────────────
NAMES = {"HCM": "HUTCHMED (China) Ltd", "AZN": "ASTRAZENECA PLC", "RLAY": "Relay Therapeutics, Inc.",
         "SAN": "Banco Santander, S.A.", "MNOV": "MediciNova, Inc.", "ARVN": "Arvinas, Inc.",
         "PFE": "Pfizer Inc.", "RIGL": "Rigel Pharmaceuticals, Inc.", "FTAI": "FTAI Aviation Ltd.",
         "FTAIM": "FTAI Aviation Ltd.", "MSLE": "Satellos Bioscience Inc.", "LLY": "Eli Lilly and Company",
         "TAK": "Takeda Pharmaceutical Company Limited", "GSK": "GSK plc"}


def forms_for(t):
    from catalysts.medical.classify import name_forms
    return name_forms(t, NAMES.get(t))


def _massive_items():
    async def get(url, params=None, headers=None):
        assert url == SRC.MASSIVE_NEWS_URL and params["apiKey"] == "K" and params["limit"] == 1000
        return resp(200, load("massive_med_subset.json"))
    return run(SRC.massive_marketwide(datetime(2026, 9, 21, tzinfo=timezone.utc), get=get, key="K"))


def test_massive_issuer_is_the_tagged_name_in_the_title_never_a_partner_or_a_single_tag():
    by = {a["title"][:30]: a for a in _massive_items()}
    hcm = [a for t, a in by.items() if t.startswith("HUTCHMED Announces Submission")][0]
    assert hcm["tickers_tagged"] == ["HCM", "AZN"]
    assert SRC.resolve_issuer_massive(hcm["title"], hcm["tickers_tagged"], forms_for) == "HCM"
    elevar = [a for t, a in by.items() if t.startswith("Elevar")][0]
    assert elevar["tickers_tagged"] == ["RLAY"]
    assert SRC.resolve_issuer_massive(elevar["title"], ["RLAY"], forms_for) is None
    oak = [a for t, a in by.items() if t.startswith("Live Oak")][0]
    assert SRC.resolve_issuer_massive(oak["title"], ["SAN"], forms_for) is None
    arvn = [a for t, a in by.items() if t.startswith("Arvinas")][0]
    assert SRC.resolve_issuer_massive(arvn["title"], arvn["tickers_tagged"], forms_for) == "ARVN"


def test_massive_articles_keep_source_url_and_published():
    arts = _massive_items()
    assert all(a["key"].startswith("mv:") and a["url"] and a["published"] for a in arts)
    assert {a["source"] for a in arts} == {"GlobeNewswire Inc."}


def test_NEGATIVE_massive_without_a_key_or_on_an_error_returns_nothing():
    async def get(url, params=None, headers=None):
        return resp(403, {})
    assert run(SRC.massive_marketwide(datetime(2026, 9, 21, tzinfo=timezone.utc), get=get, key="")) == []
    assert run(SRC.massive_marketwide(datetime(2026, 9, 21, tzinfo=timezone.utc), get=get, key="K")) == []


# ── EDGAR ───────────────────────────────────────────────────────────────────
def _efts_get(fixture):
    async def get(url, params=None, headers=None):
        assert params["forms"] == "8-K" and params["dateRange"] == "custom"
        return resp(200, load(fixture))
    return get


def test_edgar_hits_are_healthcare_only_and_one_per_accession():
    counts = {}
    hits = run(SRC.edgar_8k_hits("2026-09-21", "2026-09-28", get=_efts_get("efts_topline_8k.json"),
                                 queries=('"topline"',), counts=counts))
    tick = {h["ticker"] for h in hits}
    assert "KOD" in tick and "MIRM" in tick
    assert not tick & {"IDT", "THO"}, "NEGATIVE: non-healthcare SIC dropped"
    assert counts["non_healthcare_sic"] >= 1
    kod = [h for h in hits if h["ticker"] == "KOD"][0]
    assert kod["adsh"] == "0001193125-26-403481" and kod["sic"] == "2836"


def test_display_name_with_two_tickers_is_the_first():
    counts = {}
    hits = run(SRC.edgar_8k_hits("2026-09-21", "2026-09-28", get=_efts_get("efts_clinical_hold_8k.json"),
                                 queries=('"clinical hold"',), counts=counts))
    assert "CLDI" in {h["ticker"] for h in hits}
    assert SRC.ticker_from_display("Calidi Biotherapeutics, Inc.  (CLDI, CLDWW)  (CIK 0001855485)") == "CLDI"
    assert len({h["adsh"] for h in hits}) == len(hits)


def test_a_boilerplate_only_8K_with_no_EX_99_1_is_skipped_for_good():
    """VKTX 1.01/2.03 credit agreement: FTS hit 'clinical hold' in ex1-1 boilerplate."""
    async def get(url, params=None, headers=None):
        return resp(200, {"directory": {"item": [{"name": "vktx-ex1_1.htm"}, {"name": "vktx-8k.htm"}]}})
    assert run(SRC.edgar_exhibit_lead("0001607678", "0001193125-26-405580", get=get)) == ""


def test_a_failed_index_fetch_is_None_so_the_routine_retries():
    async def get(url, params=None, headers=None):
        return None
    assert run(SRC.edgar_exhibit_lead("0001468748", "0001193125-26-403481", get=get)) is None


def test_kod_exhibit_lead_is_the_press_release_and_stops_at_the_boilerplate():
    html = "<html><body><p>" + load("kod_ex991.txt").replace(
        "Forward-Looking Statements", "Forward-Looking Statements The FDA may place a clinical hold on") + "</p></body></html>"
    seen = []

    async def get(url, params=None, headers=None):
        seen.append(url)
        if url.endswith("index.json"):
            return resp(200, load("kod_8k_index.json"))
        return resp(200, None, text=html)
    lead = run(SRC.edgar_exhibit_lead("0001468748", "0001193125-26-403481", get=get))
    assert seen[0] == "https://www.sec.gov/Archives/edgar/data/1468748/000119312526403481/index.json"
    assert seen[1].endswith("d185059dex991.htm")
    assert 0 < len(lead) <= SRC.EXHIBIT_LEAD_CHARS
    assert lead.startswith("Zenkuda and tabirafusp-ted Meet Primary Endpoints in Pivotal DAYBREAK Trial")
    assert "clinical hold" not in lead.lower() and "forward-looking" not in lead.lower()
    head, rest = SRC.split_headline(lead)
    assert head.startswith("Zenkuda and tabirafusp-ted Meet Primary Endpoints") and "•" not in head
    assert "biologics license application (BLA) planned" in rest


def test_acceptance_time_is_utc_and_reads_08_53_56_ET():
    async def get(url, params=None, headers=None):
        assert url == "https://data.sec.gov/submissions/CIK0001468748.json"
        return resp(200, load("sec_submissions_KOD_subset.json"))
    acc = run(SRC.edgar_acceptance("0001468748", "0001193125-26-403481", get=get))
    assert acc == datetime(2026, 9, 28, 12, 53, 56, tzinfo=timezone.utc)
    assert acc.astimezone(ET).strftime("%H:%M:%S") == "08:53:56"   # EDGAR index: "Accepted 2026-09-28 08:53:56"
    assert run(SRC.edgar_acceptance("0001468748", "0000000000-00-000000", get=get)) is None


def test_edgar_article_shape_and_NEGATIVE_undated_is_None():
    hit = {"adsh": "0001193125-26-403481", "cik": "0001468748", "ticker": "KOD", "sic": "2836"}
    a = SRC.edgar_article(hit, "Headline Here • bullet one", datetime(2026, 9, 28, 8, 53, 56, tzinfo=timezone.utc))
    assert a["key"] == "sec:0001193125-26-403481" and a["title"] == "Headline Here"
    assert a["ticker"] == "KOD" and a["text_basis"] == "exhibit_99_1"
    assert SRC.edgar_article(hit, "Headline", None) is None
    assert SRC.edgar_article(hit, "", datetime.now(timezone.utc)) is None


def test_sec_company_titles():
    async def get(url, params=None, headers=None):
        return resp(200, {"0": {"ticker": "HCM", "title": "HUTCHMED (China) Ltd"}, "1": {"ticker": "LLY", "title": "ELI LILLY & Co"}})
    assert run(SRC.sec_company_titles(get=get)) == {"HCM": "HUTCHMED (China) Ltd", "LLY": "ELI LILLY & Co"}


# ── FDA RSS ─────────────────────────────────────────────────────────────────
def test_fda_rss_sends_the_browser_UA_and_parses_items():
    hdrs = []

    async def get(url, params=None, headers=None):
        hdrs.append(headers)
        if url == SRC.FDA_PRESS_RSS:
            return resp(200, None, text=load("fda_press_rss.xml"))
        return resp(200, None, text="<p>Approval of Emcitate was granted to Egetis Therapeutics AB.</p>")
    arts = run(SRC.fda_press_releases(get=get, want_page=lambda it: "MCT8" in it["title"]))
    assert hdrs[0] == {"User-Agent": SRC.FDA_RSS_UA} and "Mozilla" in SRC.FDA_RSS_UA
    mct8 = [a for a in arts if "MCT8" in a["title"]][0]
    assert mct8["company"] == "Egetis Therapeutics"
    assert datetime.fromtimestamp(mct8["published"], timezone.utc).astimezone(ET).strftime("%m-%d %H:%M") == "09-28 17:43"
    assert mct8["key"].startswith("fda:http")
    assert len(hdrs) == 2, "one page fetch for the one wanted item"


def test_NEGATIVE_the_python_requests_UA_404_is_zero_items_and_no_raise():
    async def get(url, params=None, headers=None):
        return resp(404, None, text="Not Found")
    assert run(SRC.fda_press_releases(get=get)) == []

    async def boom(url, params=None, headers=None):
        raise OSError("connect failed")
    counts = {}
    assert run(SRC.fda_press_releases(get=boom, counts=counts)) == [] and counts["errors"] == 1


def test_fda_page_company_rule_and_the_sec_title_match():
    assert SRC.fda_company_from_page("<p>approved to Egetis Therapeutics AB for MCT8</p>") == "Egetis Therapeutics"
    assert SRC.fda_company_from_page("<p>no company here</p>") is None
    titles = {"LLY": "ELI LILLY & Co", "EGTX": "Egetis Therapeutics AB"}
    assert SRC.match_company_title("Egetis Therapeutics", titles) == "EGTX"
    assert SRC.match_company_title("Nobody Inc", titles) is None
    assert SRC.norm_company("Merck & Co., Inc.") == "Merck"
    assert SRC.norm_company("HUTCHMED (China) Ltd") == "HUTCHMED"


def test_article_key_fallback_is_title_and_minute():
    k = SRC.article_key({"provider": "x", "title": "A B!", "published": 1_790_000_000.0})
    assert k.startswith("t:ab:") and len(k.split(":")[-1]) == 12
