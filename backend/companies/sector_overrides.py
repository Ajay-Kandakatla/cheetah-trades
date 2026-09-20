"""Curated sector/industry corrections for names the provider misfiles.

Ajay 2026-09-19, on a screenshot of WULF: *"They are all wrongle categorizerd
OKLO is nuclear power, IREN is mining.."*

He was right, and the breadth is the point. Audited all 253 themed names against
the provider label the app actually serves:

    ai_power (20)   Technology 7 · FINANCIAL SERVICES 6 · Industrials 4 · Utilities 1
    nuclear  (9)    Industrials 4 · Utilities 4 · Energy 1
    crypto   (17)   FINANCIAL SERVICES 10 · Technology 3 · Comm Services 1 · none 3

Sixteen names arrived as sector "Financial Services", industry "Capital
Markets" — the peer group for brokers, dealers and exchanges. Only COIN and
HOOD belong there.

WHERE THE BAD LABEL COMES FROM
------------------------------
Not from a careless provider. TeraWulf's own EDGAR filer header carries
**SIC 6199 "Finance Services", CF Office 09 Crypto Assets** — a filing-routing
code, not a business descriptor. Every data vendor that maps SIC -> sector
inherits it, which is why a bitcoin miner and a GPU-cloud landlord both land in
Capital Markets. GICS does not agree: it places miners in Sector 45
INFORMATION TECHNOLOGY (45103010 Application Software), and the 2026-07-17
S&P DJI / MSCI consultation proposes moving them to 45102030 Internet Services
& Infrastructure — still Information Technology, never Financials.

The provider itself already ignores the SIC for some of these (APLD, CIFR and
CORZ are correctly Technology despite the same SIC 6199 trap), so this table
makes the treatment consistent rather than inventing a new taxonomy.

WHAT THIS BREAKS WHEN IT IS WRONG
---------------------------------
Two surfaces rank PEER-RELATIVE and both read this label:

  * ``/sepa/longterm/{symbol}`` scored WULF **19.6 against 406 "Financial
    Services" peers** — a loss-making data-center build-out graded against
    banks and asset managers on ROCE, ROE and D/E.
  * the rotation grid takes sector and industry MEDIANS, so a cohort of miners
    sitting inside Capital Markets moves a number he reads as a rotation
    signal. WULF's served heat badge was "cold Capital Markets -2.5% vs RSP".

THE BAR FOR A ROW HERE
----------------------
Every entry names the filing or standard that grounds it, and the test file
asserts that none is empty. A label is corrected only when the provider's
string MISSTATES THE BUSINESS — never for tidiness, and never to make a theme
look coherent. The app's curated themes (``universe.THEME_BY_TICKER``) are a
SEPARATE axis and are deliberately not mirrored here: a diversified industrial
that also makes robots is genuinely Industrials, and forcing it to "robotics"
would be the same error in the other direction.

NOT A GATE. This changes a LABEL and therefore a PEER GROUP. It gates no
alert, sizes no position, enters no lane and moves no S&D rule, threshold or
band. A name's zones, verdict and enterable read are byte-identical before and
after — pinned in tests.

Deliberately NOT decided here, because they are judgement calls the owner
must make rather than facts a filing settles:

  BTCS · SBET · DFDV   crypto TREASURY vehicles. Their P&L is a levered coin
                       proxy, not an operating business. "Financial Services"
                       is arguably RIGHT for a balance-sheet vehicle, and the
                       industry string is the real question.
  FRMI                 pre-revenue with a REIT election (SIC 6798) — the
                       election argues Real Estate, the intended business
                       argues data centres, and there is no revenue to test.
  NNE                  pre-revenue reactor developer; the provider is already
                       right, and at $214K of nine-month revenue a
                       peer-relative score is noise whatever the label.

Those stay on the provider's label until he says otherwise.
"""
from __future__ import annotations

from typing import Optional

# ticker -> (sector, industry, basis)
#
# `basis` is the citation, in the provider's own vocabulary. It is printed in
# the API payload beside the corrected label so a reader can see WHY a name was
# moved — a silent relabel is how a wrong one survives.
SECTOR_OVERRIDES: dict[str, tuple[str, str, str]] = {
    # ── the SIC 6199 cohort: miners and AI/HPC data-centre operators that the
    # "Finance Services" filing code drags into Capital Markets ─────────────
    "WULF": ("Technology", "Information Technology Services",
             "Q2 2026 10-Q: two reportable segments, HPC Leasing ($31.9M, "
             "71.3% of revenue) and Digital Asset Mining ($12.8M). No "
             "financial-services revenue. SIC 6199 is the CF Office 09 "
             "crypto-assets routing code, not a business descriptor."),
    "IREN": ("Technology", "Information Technology Services",
             "Revenue majority is GPU cloud compute with the mining business "
             "being wound down; an AI cloud provider, not a broker. GICS "
             "places miners in Sector 45 Information Technology (45103010), "
             "never Financials."),
    "MARA": ("Technology", "Information Technology Services",
             "Essentially all revenue is selling hashrate to the bitcoin "
             "network. No brokerage, underwriting, asset-management or "
             "exchange activity exists to justify Capital Markets. GICS "
             "45103010, Sector 45 Information Technology."),
    "RIOT": ("Technology", "Information Technology Services",
             "All three reported segments are mining, electrical engineering "
             "or data-centre leasing — none is a capital-markets business. "
             "SIC 6199 is the crypto filing-routing code; GICS 45103010."),
    "HUT":  ("Technology", "Information Technology Services",
             "Reported segments are compute, data-centre infrastructure and "
             "power generation: an energy-and-compute operator, not a "
             "securities business. GICS 45103010, Sector 45 IT."),
    "CLSK": ("Technology", "Information Technology Services",
             "Fiscal Q3 2026 10-Q: $138M revenue, essentially all bitcoin "
             "mining, plus a signed 175MW triple-net data-centre lease. No "
             "brokerage, exchange or asset-management revenue."),
    "HIVE": ("Technology", "Information Technology Services",
             "Both reported revenue lines are compute — hashrate and GPU "
             "hosting — with nothing resembling a capital-markets activity. "
             "GICS 45103010, Sector 45 IT."),
    "ARBK": ("Technology", "Information Technology Services",
             "Single-business bitcoin miner; has never had financial-services "
             "revenue. SIC 6199 routing code only; GICS 45103010."),
    "BTBT": ("Technology", "Information Technology Services",
             "~90% of revenue is AI cloud and colocation hosting. RE-CHECK "
             "if the announced 'pure play ETH staking' transition completes — "
             "that would make it a treasury vehicle, a different question."),
    "SLNH": ("Technology", "Information Technology Services",
             "Majority segment is data-centre hosting attached to owned "
             "renewable generation. The minority wind/demand-response lines "
             "argue Utilities at most, never Capital Markets."),

    # ── the nuclear cohort: a PRE-REVENUE developer is not an operating
    # utility. Ajay's own example. VST, CEG and TLN keep their IPP label —
    # they were never the defect; OKLO sitting beside them was ────────────────
    "OKLO": ("Industrials", "Specialty Industrial Machinery",
             "Pre-revenue reactor developer selling no electricity. Ranking "
             "it against VST (~44,000 MW) and CEG ($7.50B of Q2 2026 revenue) "
             "compares it to companies it shares no financial structure with. "
             "Lands with SMR, the other reactor-module vendor."),
    "MIR":  ("Technology", "Scientific & Technical Instruments",
             "Radiation-measurement instrument maker with ~$1B of recurring "
             "revenue — not industrial machinery and not a power producer; "
             "its peer set is instruments, not capital equipment."),

    # ── manufacturers mislabelled as the thing they supply ──────────────────
    "FLNC": ("Industrials", "Electrical Equipment & Parts",
             "Q3 FY2026 10-Q: ONE reportable segment; sells battery-storage "
             "hardware and software, generates no electricity. Gross profit "
             "$33.2M on $649.8M (5.1%) — a thin-margin equipment maker being "
             "ranked against regulated utilities on payout and rate base. "
             "SIC 3690, the same code the provider already maps to "
             "Industrials / Electrical Equipment & Parts for EOSE."),
    "NXT":  ("Industrials", "Electrical Equipment & Parts",
             "GICS splits solar by what is made: semiconductor module makers "
             "(FSLR) stay in Information Technology, balance-of-system "
             "hardware makers do not. NXT is the latter, so its peer set is "
             "electrical equipment."),

    # ── a stale name from a divested business ───────────────────────────────
    "NBIS": ("Technology", "Software - Infrastructure",
             "Q2 2026 6-K: AI cloud revenue $574.9M of $582.3M group revenue "
             "(98.7%). 'Internet Content & Information' is the stale Yandex "
             "search-portal tag from before the Russian business was "
             "divested; direct peer CRWV is already Software - Infrastructure."),
}

# Names deliberately LEFT on the provider's label, with the reason. Kept in
# code so a future pass does not "discover" them again and quietly override
# something that was considered and declined.
REVIEWED_NO_CHANGE: dict[str, str] = {
    "COIN": "Genuinely operates an exchange and brokerage — Financial Data & "
            "Stock Exchanges is the right peer set.",
    "HOOD": "A broker-dealer by registration and by revenue mix.",
    "GLXY": "A licensed trading, lending and asset-management franchise; "
            "SIC 6211 and the revenue mix both match Capital Markets.",
    "SMR":  "Early-revenue reactor MODULE vendor, correctly in the "
            "capital-equipment bucket rather than the utility bucket.",
    "LEU":  "Operating nuclear-FUEL supplier with real product revenue.",
    "BWXT": "Profitable operating defence manufacturer; revenue majority is "
            "naval nuclear propulsion, not power generation.",
    "CEG":  "Operating power producer at multi-billion quarterly scale — the "
            "peer group OKLO was corrupting.",
    "TLN":  "Cash-generating IPP selling electricity from an operating "
            "13.1 GW fleet.",
    "VST":  "The canonical cash-generating IPP. The defect was never VST's "
            "label; it was OKLO being placed beside it.",
    "AGX":  "Builds power plants under fixed-price EPC contracts, owns no "
            "generation, sells no electricity.",
    "APLD": "Owns and operates data centres; no REIT election in the 10-K.",
    "BE":   "Manufactures and services onsite power equipment rather than "
            "owning generation.",
    "CIFR": "Provider already correctly ignores the SIC 6199 trap here.",
    "CORZ": "Data-centre colocation operator, correctly in Information "
            "Technology.",
    "BTDR": "Sector is right; the industry string faithfully renders the "
            "miner's GICS sub-industry.",
    "NNE":  "Pre-revenue reactor developer — provider is already right, and "
            "at $214K of nine-month revenue a peer score is noise anyway.",
}


def sector_for(symbol: str) -> Optional[tuple[str, str, str]]:
    """The corrected ``(sector, industry, basis)`` for a symbol, or None.

    None means "use whatever the provider said" — the overwhelming majority of
    names, and the only safe default.
    """
    return SECTOR_OVERRIDES.get((symbol or "").upper().strip())


def apply(doc: Optional[dict]) -> Optional[dict]:
    """Heal one company doc in place-safe fashion, returning it.

    Never raises and never invents: a doc with no symbol, or a symbol with no
    override, comes back untouched. The ORIGINAL provider strings are kept
    under ``sector_provider`` / ``industry_provider`` so nothing is destroyed
    and a reader can always see what was corrected — the same courtesy
    ``sepa.symbols`` pays a renamed ticker.
    """
    if not isinstance(doc, dict):
        return doc
    fix = sector_for(doc.get("symbol") or "")
    if not fix:
        return doc
    sector, industry, basis = fix
    # Idempotent: applying twice must not shuffle the provider strings out of
    # reach. get_many_cached() and get() can both touch the same doc.
    if "sector_provider" not in doc:
        doc["sector_provider"] = doc.get("sector")
        doc["industry_provider"] = doc.get("industry")
    doc["sector"] = sector
    doc["industry"] = industry
    doc["sector_override"] = True
    doc["sector_override_basis"] = basis
    return doc
