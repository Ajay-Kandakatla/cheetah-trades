"""Locks the EDGAR insider fix (sepa/insider) — CIK-scoped, issuer-stripped,
and transaction-aware.

Bug (2026-06-03): the old code did a free-text phrase search for the ticker
string (`q="ST"`). For the 2-letter ticker ST (Sensata) that matched the
letters "ST" anywhere and returned 1,767 unrelated Form 4s instead of Sensata's
real 15 — and falsely tripped "cluster insider buying" with 47 phantom insiders.

Phase 2 (same day): even scoped correctly, "cluster buying" must mean OFFICERS/
DIRECTORS making OPEN-MARKET PURCHASES (code P), not grants/sells/tax-withholding.
We parse each Form 4's relationship + transaction codes to tell them apart.

All tests run offline (no network).
"""
import asyncio

import sepa.insider as ins


# ── issuer stripping ────────────────────────────────────────────────────────

def test_owner_names_strips_issuer():
    names = [
        "SIEDEL RICHARD W. JR.  (CIK 0001661082)",
        "Sensata Technologies Holding plc  (CIK 0001477294)",
    ]
    owners = ins._owner_names(names, "0001477294")
    assert owners == ["SIEDEL RICHARD W. JR.  (CIK 0001661082)"]
    assert all("Sensata" not in o for o in owners)


def test_owner_names_handles_empty():
    assert ins._owner_names([], "0001477294") == []
    assert ins._owner_names(None, "0001477294") == []


# ── Form 4 XML parsing: relationship + transaction classification ────────────

def _f4(owner, *, director=0, officer=0, ten=0, title="", code="P", ad="A",
        shares="1000", price="50"):
    return f"""<ownershipDocument>
      <issuer><issuerName>Acme</issuerName><issuerTradingSymbol>AC</issuerTradingSymbol></issuer>
      <reportingOwner><reportingOwnerId><rptOwnerName>{owner}</rptOwnerName></reportingOwnerId>
      <reportingOwnerRelationship>
        <isDirector>{director}</isDirector><isOfficer>{officer}</isOfficer>
        <isTenPercentOwner>{ten}</isTenPercentOwner><officerTitle>{title}</officerTitle>
      </reportingOwnerRelationship></reportingOwner>
      <nonDerivativeTable><nonDerivativeTransaction>
        <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
        <transactionAmounts>
          <transactionShares><value>{shares}</value></transactionShares>
          <transactionPricePerShare><value>{price}</value></transactionPricePerShare>
          <transactionAcquiredDisposedCode><value>{ad}</value></transactionAcquiredDisposedCode>
        </transactionAmounts>
      </nonDerivativeTransaction></nonDerivativeTable>
    </ownershipDocument>"""


def test_parse_open_market_buy_by_director():
    r = ins._parse_form4_xml(_f4("DOE JANE", director=1, code="P", ad="A",
                                 shares="2000", price="48.50"))
    assert r["owner"] == "DOE JANE"
    assert r["relationship"] == "Director"
    assert r["is_insider"] is True
    assert r["is_buy"] is True
    assert r["buy_shares"] == 2000.0 and r["buy_value"] == 97000.0
    assert "Buy" in r["txn"]


def test_parse_tax_withholding_is_not_a_buy():
    # The real ST/Siedel case: code F, disposed.
    r = ins._parse_form4_xml(_f4("SIEDEL RICHARD", officer=1,
                                 title="Chief Accounting Officer",
                                 code="F", ad="D", shares="374", price="49.29"))
    assert r["relationship"] == "Officer"
    assert r["is_buy"] is False and r["is_sell"] is False
    assert r["txn"] == "Tax withholding"


def test_parse_sell_and_grant():
    sell = ins._parse_form4_xml(_f4("X", officer=1, code="S", ad="D", shares="500"))
    assert sell["is_sell"] is True and sell["is_buy"] is False
    grant = ins._parse_form4_xml(_f4("Y", director=1, code="A", ad="A", shares="100"))
    assert grant["is_buy"] is False and grant["txn"] == "Grant"


def test_parse_ten_percent_owner_is_entity_holder_not_insider():
    r = ins._parse_form4_xml(_f4("Apax Guernsey PCC Ltd", ten=1, code="P", ad="A"))
    assert r["relationship"] == "10% owner"
    assert r["is_insider"] is False          # not officer/director
    assert r["is_entity_holder"] is True


# ── unknown ticker returns zeros, never free-text garbage ────────────────────

def test_unknown_ticker_returns_empty(monkeypatch):
    async def fake_cik(_sym):
        return None

    async def boom(*a, **k):
        raise AssertionError("must not run a filing search for an unknown ticker")

    monkeypatch.setattr(ins, "_ticker_to_cik", fake_cik)
    monkeypatch.setattr(ins, "_fts_search", boom)

    r = asyncio.run(ins.insider_activity("ZZZZ"))
    assert r["resolved_cik"] is None
    assert r["form4_cluster_buy"] is False
    assert r["recent_filings"] == {"form4": [], "13d": [], "13g": []}


# ── end-to-end: cluster_buy requires real open-market insider purchases ──────

def _stub(monkeypatch, form4_details):
    """form4_details: list of (filed, owner, detail_dict|None)."""
    async def fake_cik(_sym):
        return "0001477294"

    async def fake_fts(cik, form, days=60):
        assert cik == "0001477294"           # scoped to issuer, not free text
        if form != "4":
            return []
        return [{"filed": fd, "owner": ow, "display_names": [ow],
                 "accession": f"acc-{i}", "doc": "d.xml"}
                for i, (fd, ow, _det) in enumerate(form4_details)]

    detail_by_acc = {f"acc-{i}": det for i, (_fd, _ow, det) in enumerate(form4_details)}

    async def fake_detail(cik, accession, doc, sem):
        return detail_by_acc.get(accession)

    monkeypatch.setattr(ins, "_ticker_to_cik", fake_cik)
    monkeypatch.setattr(ins, "_fts_search", fake_fts)
    monkeypatch.setattr(ins, "_fetch_form4_detail", fake_detail)

    import datetime as _dt

    class _FrozenDT(_dt.datetime):
        @classmethod
        def utcnow(cls):
            return cls(2026, 6, 3)

    monkeypatch.setattr(ins, "datetime", _FrozenDT)


def _buy(owner, insider=True):
    return {"owner": owner, "relationship": "Director" if insider else "10% owner",
            "title": None, "is_insider": insider, "is_entity_holder": not insider,
            "is_buy": True, "is_sell": False, "txn": "Buy 1,000 sh @ $50",
            "buy_shares": 1000.0, "buy_value": 50000.0}


def _noise(owner, txn="Grant"):
    return {"owner": owner, "relationship": "Officer", "title": "CFO",
            "is_insider": True, "is_entity_holder": False,
            "is_buy": False, "is_sell": txn == "Sell", "txn": txn,
            "buy_shares": 0.0, "buy_value": 0.0}


def test_grants_and_sells_do_not_count_as_cluster_buying(monkeypatch):
    # The real ST/NUE shape: officer tax-withholding / sells / director grants.
    _stub(monkeypatch, [
        ("2026-06-03", "SIEDEL RICHARD", _noise("SIEDEL RICHARD", "Tax withholding")),
        ("2026-05-22", "Stott David",    _noise("Stott David", "Sell")),
        ("2026-05-08", "Caljouw Lynne",  _noise("Caljouw Lynne", "Option exercise")),
    ])
    r = asyncio.run(ins.insider_activity("ST"))
    assert r["form4_count_30d"] == 3
    assert r["form4_buy_count_30d"] == 0
    assert r["form4_insider_buyers_30d"] == 0
    assert r["form4_cluster_buy"] is False     # the key fix — no phantom cluster


def test_two_distinct_insider_buyers_trip_cluster(monkeypatch):
    _stub(monkeypatch, [
        ("2026-06-02", "DOE JANE",  _buy("DOE JANE")),
        ("2026-05-30", "ROE JOHN",  _buy("ROE JOHN")),
        ("2026-05-20", "Big Fund LP", _buy("Big Fund LP", insider=False)),  # 10% owner: ignored
    ])
    r = asyncio.run(ins.insider_activity("AC"))
    assert r["form4_buy_count_30d"] == 3
    assert r["form4_insider_buyers_30d"] == 2   # the fund is not an officer/director
    assert r["form4_cluster_buy"] is True


def test_single_insider_buyer_is_not_a_cluster(monkeypatch):
    _stub(monkeypatch, [
        ("2026-06-02", "DOE JANE", _buy("DOE JANE")),
        ("2026-05-30", "DOE JANE", _buy("DOE JANE")),  # same person twice
    ])
    r = asyncio.run(ins.insider_activity("AC"))
    assert r["form4_insider_buyers_30d"] == 1
    assert r["form4_cluster_buy"] is False
