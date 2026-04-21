"""Cheetah Score dataset — edit here to refresh the Dashboard page.

Each stock has per-bucket scores (0-100). The final Cheetah Score is
computed live by `compute_score()` using FORMULA_WEIGHTS so you can tweak
the weights or any bucket and the "Rerun formulas" button on the dashboard
will pick it up.

Fields:
  ticker, name, sector, mcap (in $B), revGrowth (%), grossMargin (%),
  debtRev (ratio), peg, rs (0-99), perf3m (%),
  buckets: {growth, momentum, quality, stability, value}  each 0-100
  signals: [{label, type}]  type ∈ growth|momentum|quality|value|stability
  tier2: [ticker...]   # established rivals with meaningful share
  tier3: [ticker...]   # emerging / smaller / higher-risk challengers
  why: string
"""

FORMULA_WEIGHTS = {
    "growth": 0.30,
    "momentum": 0.20,
    "quality": 0.20,
    "stability": 0.15,
    "value": 0.15,
}


def compute_score(stock: dict) -> int:
    """Apply FORMULA_WEIGHTS to the stock's bucket scores. Returns 0-100."""
    b = stock.get("buckets") or {}
    total = 0.0
    for bucket, weight in FORMULA_WEIGHTS.items():
        total += (b.get(bucket) or 0) * weight
    return round(total)


def with_computed_scores(stocks: list[dict]) -> list[dict]:
    """Return copies of stocks with freshly computed `score` from buckets."""
    out = []
    for s in stocks:
        copy = dict(s)
        copy["score"] = compute_score(copy)
        out.append(copy)
    # Sort descending by score so the button actually visibly re-orders
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


CHEETAH_STOCKS = [
    {
        "ticker": "NVDA", "name": "Nvidia", "sector": "AI / Semis", "mcap": 3400,
        "revGrowth": 62, "grossMargin": 75, "debtRev": 0.06, "peg": 1.2, "rs": 94, "perf3m": 18,
        "buckets": {"growth": 98, "momentum": 94, "quality": 96, "stability": 92, "value": 70},
        "signals": [
            {"label": "Rev +62% YoY", "type": "growth"},
            {"label": "RS 94", "type": "momentum"},
            {"label": "GM 75%", "type": "quality"},
        ],
        "tier2": ["AMD", "AVGO"],
        "tier3": ["MRVL", "SMCI"],
        "why": "AI data center demand; Blackwell ramp; 63% projected FY26 revenue growth. CFRA target $270.",
    },
    {
        "ticker": "PLTR", "name": "Palantir Technologies", "sector": "AI / Software", "mcap": 280,
        "revGrowth": 60, "grossMargin": 80, "debtRev": 0.00, "peg": 2.8, "rs": 97, "perf3m": 22,
        "buckets": {"growth": 95, "momentum": 97, "quality": 92, "stability": 98, "value": 45},
        "signals": [
            {"label": "Rev +60% YoY", "type": "growth"},
            {"label": "RS 97", "type": "momentum"},
            {"label": "Zero Debt", "type": "stability"},
        ],
        "tier2": ["SNOW", "DDOG"],
        "tier3": ["AI", "BBAI"],
        "why": "60% projected FY26 rev growth; AIP adoption in US gov and enterprise; zero debt.",
    },
    {
        "ticker": "AVGO", "name": "Broadcom", "sector": "AI / Semis", "mcap": 950,
        "revGrowth": 47, "grossMargin": 76, "debtRev": 0.50, "peg": 1.4, "rs": 88, "perf3m": 12,
        "buckets": {"growth": 88, "momentum": 86, "quality": 90, "stability": 78, "value": 68},
        "signals": [
            {"label": "Rev +47% YoY", "type": "growth"},
            {"label": "GM 76%", "type": "quality"},
            {"label": "RS 88", "type": "momentum"},
        ],
        "tier2": ["MRVL", "AMD"],
        "tier3": ["QCOM", "NXPI"],
        "why": "47% 2026 rev growth expected; custom AI silicon with hyperscalers; VMware synergy.",
    },
    {
        "ticker": "CLS", "name": "Celestica", "sector": "AI Hardware", "mcap": 22,
        "revGrowth": 40, "grossMargin": 11, "debtRev": 0.25, "peg": 0.9, "rs": 92, "perf3m": 24,
        "buckets": {"growth": 88, "momentum": 93, "quality": 62, "stability": 80, "value": 92},
        "signals": [
            {"label": "Rev +40% YoY", "type": "growth"},
            {"label": "PEG 0.9", "type": "value"},
            {"label": "RS 92", "type": "momentum"},
        ],
        "tier2": ["FLEX", "JBL"],
        "tier3": ["SANM", "PLXS"],
        "why": "~40% revenue growth FY26 and FY27 on AI data center builds; attractive PEG.",
    },
    {
        "ticker": "VRT", "name": "Vertiv Holdings", "sector": "AI Infrastructure", "mcap": 55,
        "revGrowth": 28, "grossMargin": 37, "debtRev": 0.22, "peg": 1.3, "rs": 89, "perf3m": 15,
        "buckets": {"growth": 82, "momentum": 89, "quality": 75, "stability": 82, "value": 75},
        "signals": [
            {"label": "RS 89", "type": "momentum"},
            {"label": "Rev +28% YoY", "type": "growth"},
            {"label": "D/R 0.22", "type": "stability"},
        ],
        "tier2": ["ETN", "TT"],
        "tier3": ["GNRC", "PWR"],
        "why": "Data-center cooling/power; guided $13.5B 2026 sales (+28%); secular AI capex tailwind.",
    },
    {
        "ticker": "CRDO", "name": "Credo Technology", "sector": "AI Connectivity", "mcap": 28,
        "revGrowth": 201, "grossMargin": 65, "debtRev": 0.00, "peg": 1.8, "rs": 96, "perf3m": 28,
        "buckets": {"growth": 99, "momentum": 96, "quality": 85, "stability": 96, "value": 58},
        "signals": [
            {"label": "Rev +201% YoY", "type": "growth"},
            {"label": "RS 96", "type": "momentum"},
            {"label": "Zero Debt", "type": "stability"},
        ],
        "tier2": ["ALAB", "MRVL"],
        "tier3": ["POET", "SMTC"],
        "why": "AEC standard for AI datacenters; FY26 guide ~$1.3B; zero debt; TE settlement removed overhang.",
    },
    {
        "ticker": "ALAB", "name": "Astera Labs", "sector": "AI Connectivity", "mcap": 27,
        "revGrowth": 85, "grossMargin": 78, "debtRev": 0.00, "peg": 1.6, "rs": 91, "perf3m": 19,
        "buckets": {"growth": 94, "momentum": 91, "quality": 92, "stability": 98, "value": 55},
        "signals": [
            {"label": "Rev +85% YoY", "type": "growth"},
            {"label": "GM 78%", "type": "quality"},
            {"label": "Zero Debt", "type": "stability"},
        ],
        "tier2": ["CRDO", "MRVL"],
        "tier3": ["POET", "SMTC"],
        "why": "PCIe retimer leader; scale-up AI fabric adoption; fortress balance sheet.",
    },
    {
        "ticker": "LITE", "name": "Lumentum Holdings", "sector": "AI Optics", "mcap": 27,
        "revGrowth": 55, "grossMargin": 35, "debtRev": 0.60, "peg": 1.1, "rs": 98, "perf3m": 35,
        "buckets": {"growth": 84, "momentum": 98, "quality": 68, "stability": 65, "value": 78},
        "signals": [
            {"label": "3M +35%", "type": "momentum"},
            {"label": "RS 98", "type": "momentum"},
            {"label": "Rev +55% YoY", "type": "growth"},
        ],
        "tier2": ["COHR", "FN"],
        "tier3": ["AAOI", "APLD"],
        "why": "Up 402% in 52 weeks; AI optical transceivers ramping; Quant Strong Buy.",
    },
    {
        "ticker": "META", "name": "Meta Platforms", "sector": "Mega-cap Tech", "mcap": 1400,
        "revGrowth": 24, "grossMargin": 81, "debtRev": 0.18, "peg": 1.0, "rs": 82, "perf3m": 8,
        "buckets": {"growth": 75, "momentum": 80, "quality": 94, "stability": 86, "value": 82},
        "signals": [
            {"label": "GM 81%", "type": "quality"},
            {"label": "PEG 1.0", "type": "value"},
            {"label": "Rev +24% YoY", "type": "growth"},
        ],
        "tier2": ["GOOGL", "SNAP"],
        "tier3": ["PINS", "RDDT"],
        "why": "25% projected 2026 rev growth; AI ad monetization + Reels engagement; exceptional FCF.",
    },
    {
        "ticker": "LLY", "name": "Eli Lilly", "sector": "Pharma", "mcap": 850,
        "revGrowth": 43, "grossMargin": 81, "debtRev": 0.42, "peg": 1.4, "rs": 86, "perf3m": 9,
        "buckets": {"growth": 90, "momentum": 84, "quality": 90, "stability": 78, "value": 70},
        "signals": [
            {"label": "Rev +43% YoY", "type": "growth"},
            {"label": "GM 81%", "type": "quality"},
            {"label": "RS 86", "type": "momentum"},
        ],
        "tier2": ["NVO", "VKTX"],
        "tier3": ["ALT", "TERN"],
        "why": "Mounjaro +110%, Zepbound +123% YoY; 25.9% projected 2026 rev growth; GLP-1 dominance.",
    },
    {
        "ticker": "ABNB", "name": "Airbnb", "sector": "Consumer / Travel", "mcap": 95,
        "revGrowth": 14, "grossMargin": 83, "debtRev": 0.20, "peg": 1.8, "rs": 72, "perf3m": 6,
        "buckets": {"growth": 60, "momentum": 70, "quality": 90, "stability": 88, "value": 62},
        "signals": [
            {"label": "GM 83%", "type": "quality"},
            {"label": "FCF Margin 38%", "type": "quality"},
            {"label": "$11B Cash", "type": "stability"},
        ],
        "tier2": ["BKNG", "EXPE"],
        "tier3": ["TRIP", "TCOM"],
        "why": "38% FCF margin; $11B cash; international expansion + experiences relaunch.",
    },
    {
        "ticker": "NET", "name": "Cloudflare", "sector": "Cloud / Security", "mcap": 44,
        "revGrowth": 30, "grossMargin": 77, "debtRev": 0.95, "peg": 2.9, "rs": 84, "perf3m": 11,
        "buckets": {"growth": 80, "momentum": 82, "quality": 86, "stability": 60, "value": 42},
        "signals": [
            {"label": "Rev +30% YoY", "type": "growth"},
            {"label": "GM 77%", "type": "quality"},
            {"label": "RS 84", "type": "momentum"},
        ],
        "tier2": ["CRWD", "ZS"],
        "tier3": ["FSLY", "AKAM"],
        "why": "30% projected FY26 sales growth; AI inference at edge; Workers AI platform.",
    },
    {
        "ticker": "RKLB", "name": "Rocket Lab", "sector": "Space / Defense", "mcap": 14,
        "revGrowth": 78, "grossMargin": 27, "debtRev": 1.10, "peg": 2.5, "rs": 95, "perf3m": 32,
        "buckets": {"growth": 90, "momentum": 95, "quality": 55, "stability": 45, "value": 50},
        "signals": [
            {"label": "Rev +78% YoY", "type": "growth"},
            {"label": "RS 95", "type": "momentum"},
            {"label": "3M +32%", "type": "momentum"},
        ],
        "tier2": ["LUNR", "ASTS"],
        "tier3": ["BKSY", "ACHR"],
        "why": "Neutron rocket progress; space sector rotation; defense backlog expanding.",
    },
    {
        "ticker": "OKLO", "name": "Oklo Inc", "sector": "Nuclear / Energy", "mcap": 8,
        "revGrowth": 0, "grossMargin": 0, "debtRev": 0.00, "peg": 0, "rs": 93, "perf3m": 45,
        "buckets": {"growth": 40, "momentum": 96, "quality": 30, "stability": 80, "value": 35},
        "signals": [
            {"label": "3M +45%", "type": "momentum"},
            {"label": "RS 93", "type": "momentum"},
            {"label": "Zero Debt", "type": "stability"},
        ],
        "tier2": ["NNE", "SMR"],
        "tier3": ["LEU", "BWXT"],
        "why": "Small modular reactor momentum tied to AI power demand; pre-revenue — higher-risk cheetah.",
    },
    {
        "ticker": "SOFI", "name": "SoFi Technologies", "sector": "Fintech", "mcap": 22,
        "revGrowth": 26, "grossMargin": 85, "debtRev": 0.90, "peg": 1.7, "rs": 83, "perf3m": 14,
        "buckets": {"growth": 78, "momentum": 82, "quality": 84, "stability": 62, "value": 68},
        "signals": [
            {"label": "Rev +26% YoY", "type": "growth"},
            {"label": "RS 83", "type": "momentum"},
            {"label": "GM 85%", "type": "quality"},
        ],
        "tier2": ["UPST", "AFRM"],
        "tier3": ["LMND", "LC"],
        "why": "Member growth accelerating; Galileo platform; rate-cut tailwind for lending.",
    },
    {
        "ticker": "HIMS", "name": "Hims & Hers Health", "sector": "Telehealth", "mcap": 6,
        "revGrowth": 65, "grossMargin": 82, "debtRev": 0.05, "peg": 1.1, "rs": 90, "perf3m": 22,
        "buckets": {"growth": 92, "momentum": 90, "quality": 88, "stability": 92, "value": 74},
        "signals": [
            {"label": "Rev +65% YoY", "type": "growth"},
            {"label": "GM 82%", "type": "quality"},
            {"label": "D/R 0.05", "type": "stability"},
        ],
        "tier2": ["TDOC", "AMWL"],
        "tier3": ["LFMD", "GDRX"],
        "why": "GLP-1 compounding + weight-loss platform driving 65% rev growth; low debt.",
    },
    {
        "ticker": "SRPT", "name": "Sarepta Therapeutics", "sector": "Biotech", "mcap": 12,
        "revGrowth": 38, "grossMargin": 84, "debtRev": 0.70, "peg": 0.8, "rs": 85, "perf3m": 12,
        "buckets": {"growth": 85, "momentum": 82, "quality": 88, "stability": 60, "value": 92},
        "signals": [
            {"label": "PEG 0.8", "type": "value"},
            {"label": "Rev +38% YoY", "type": "growth"},
            {"label": "GM 84%", "type": "quality"},
        ],
        "tier2": ["CRSP", "BEAM"],
        "tier3": ["VERV", "EDIT"],
        "why": "Elevidys DMD gene therapy ramp; low PEG; pipeline reads in 2026.",
    },
    {
        "ticker": "HRMY", "name": "Harmony Biosciences", "sector": "Biotech", "mcap": 2.5,
        "revGrowth": 22, "grossMargin": 88, "debtRev": 0.35, "peg": 0.4, "rs": 76, "perf3m": 7,
        "buckets": {"growth": 72, "momentum": 74, "quality": 90, "stability": 72, "value": 96},
        "signals": [
            {"label": "PEG 0.4", "type": "value"},
            {"label": "GM 88%", "type": "quality"},
            {"label": "Rev +22% YoY", "type": "growth"},
        ],
        "tier2": ["JAZZ", "SUPN"],
        "tier3": ["AVXL", "XERS"],
        "why": "P/E 10, analysts see +42% upside; rare neuro-disorder niche; very cheap for growth rate.",
    },
]


# ---------------------------------------------------------------------------
# Growing peer groups — side-by-side competitor scout
# ---------------------------------------------------------------------------
# Each group is anchored on a cheetah ticker and lists its *growing* direct
# competitors in the same product space. Anchor metrics come from CHEETAH_STOCKS
# automatically; competitor metrics are here.
# ---------------------------------------------------------------------------

COMPETITOR_GROUPS = [
    {
        "anchor": "NVDA",
        "headline": "NVDA's growing direct competitors",
        "sub": (
            "AI accelerator silicon + the hyperscaler custom-ASIC challengers. "
            "All of these are growing double-digit YoY and have meaningful AI data-center exposure."
        ),
        "peers": [
            {
                "ticker": "AMD", "name": "Advanced Micro Devices",
                "overlap": "MI300 / MI325X data-center GPUs vs H100/B100",
                "revGrowth": 26, "grossMargin": 53, "peg": 1.3, "rs": 81, "perf3m": 10,
                "note": "MI300X at hyperscalers; ROCm software gap narrowing; EPYC CPU tailwind.",
                "status": "growing",
            },
            {
                "ticker": "AVGO", "name": "Broadcom",
                "overlap": "Custom AI ASICs for Google TPU, Meta MTIA; networking switches",
                "revGrowth": 47, "grossMargin": 76, "peg": 1.4, "rs": 88, "perf3m": 12,
                "note": "Custom silicon + Tomahawk/Jericho switches own the scale-out fabric.",
                "status": "growing",
            },
            {
                "ticker": "MRVL", "name": "Marvell Technology",
                "overlap": "Custom ASICs (Amazon Trainium), optical DSP",
                "revGrowth": 44, "grossMargin": 60, "peg": 1.6, "rs": 85, "perf3m": 14,
                "note": "Second custom-ASIC vendor after AVGO; optical transport to data-center.",
                "status": "growing",
            },
            {
                "ticker": "ARM", "name": "ARM Holdings",
                "overlap": "CPU IP inside Grace Hopper + every hyperscaler custom CPU",
                "revGrowth": 34, "grossMargin": 96, "peg": 2.4, "rs": 83, "perf3m": 11,
                "note": "Royalty model on Neoverse cores powering Grace, Graviton, Cobalt.",
                "status": "growing",
            },
            {
                "ticker": "TSM", "name": "Taiwan Semiconductor",
                "overlap": "Fabs every AI accelerator on CoWoS advanced packaging",
                "revGrowth": 37, "grossMargin": 58, "peg": 1.1, "rs": 87, "perf3m": 13,
                "note": "Not a rival — the enabler. CoWoS capacity is the industry bottleneck.",
                "status": "enabler",
            },
            {
                "ticker": "MU", "name": "Micron Technology",
                "overlap": "HBM3E memory stacked on Blackwell / MI300 / Trainium",
                "revGrowth": 84, "grossMargin": 38, "peg": 0.7, "rs": 84, "perf3m": 16,
                "note": "HBM3E sold out through 2026; memory intensity per AI chip rising.",
                "status": "growing",
            },
        ],
    },
    {
        "anchor": "CRDO",
        "headline": "CRDO's growing direct competitors",
        "sub": (
            "High-speed connectivity inside AI data-centers — AECs, PAM4 DSPs, "
            "PCIe/CXL retimers, and optical transceivers. All names here are "
            "riding the same AI-connect TAM curve."
        ),
        "peers": [
            {
                "ticker": "ALAB", "name": "Astera Labs",
                "overlap": "PCIe/CXL retimers + Scorpio fabric switches",
                "revGrowth": 85, "grossMargin": 78, "peg": 1.6, "rs": 91, "perf3m": 19,
                "note": "Closest pure-play; scale-up AI fabric standard for NVDA + hyperscalers.",
                "status": "growing",
            },
            {
                "ticker": "MRVL", "name": "Marvell Technology",
                "overlap": "800G / 1.6T optical DSP; AEC overlap",
                "revGrowth": 44, "grossMargin": 60, "peg": 1.6, "rs": 85, "perf3m": 14,
                "note": "Largest optical DSP vendor; incumbent CRDO has to displace in transceivers.",
                "status": "growing",
            },
            {
                "ticker": "AVGO", "name": "Broadcom",
                "overlap": "PAM4 DSPs + switch silicon that AECs plug into",
                "revGrowth": 47, "grossMargin": 76, "peg": 1.4, "rs": 88, "perf3m": 12,
                "note": "Tomahawk 5/6 + Bailly optical make AVGO the platform CRDO connects to and competes with.",
                "status": "growing",
            },
            {
                "ticker": "COHR", "name": "Coherent Corp",
                "overlap": "Optical transceiver modules (800G, 1.6T)",
                "revGrowth": 28, "grossMargin": 35, "peg": 1.2, "rs": 80, "perf3m": 11,
                "note": "Transceiver incumbent; AECs are the copper-alternative to short-reach optics.",
                "status": "growing",
            },
            {
                "ticker": "LITE", "name": "Lumentum Holdings",
                "overlap": "800G+ optical transceivers for AI",
                "revGrowth": 55, "grossMargin": 35, "peg": 1.1, "rs": 98, "perf3m": 35,
                "note": "Optical incumbent; AECs eat into short-reach TAM but long-reach still optical.",
                "status": "growing",
            },
            {
                "ticker": "SMTC", "name": "Semtech",
                "overlap": "FiberEdge PAM4 DSP + CopperEdge AEC line",
                "revGrowth": 18, "grossMargin": 51, "peg": 1.7, "rs": 68, "perf3m": 4,
                "note": "Smaller AEC challenger; CopperEdge family directly targets CRDO's core SKUs.",
                "status": "challenger",
            },
            {
                "ticker": "MTSI", "name": "MACOM Technology",
                "overlap": "Analog RF + optical driver ICs for 200G/lane",
                "revGrowth": 33, "grossMargin": 57, "peg": 1.8, "rs": 74, "perf3m": 6,
                "note": "Analog front-end plays into the same 200G/lane roadmap CRDO rides.",
                "status": "growing",
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Rapidly growing private unicorns (Tier 2 — not publicly tradable)
# ---------------------------------------------------------------------------
UNICORNS = [
    {
        "name": "OpenAI", "sector": "AI / Foundation Models",
        "valuation": 157, "revGrowth": 340, "arr": 3.7,
        "founders": "Sam Altman, Greg Brockman, Ilya Sutskever",
        "note": "ChatGPT + API; revenue tripled YoY. Competes with NVDA in reasoning compute demand, with MSFT on Copilot.",
        "indirectPublic": ["MSFT", "NVDA"],
    },
    {
        "name": "Anthropic", "sector": "AI / Foundation Models",
        "valuation": 60, "revGrowth": 1000, "arr": 1.0,
        "founders": "Dario Amodei, Daniela Amodei",
        "note": "Claude family on AWS Bedrock + GCP Vertex. AMZN/GOOGL strategic investors; ARR grew 10x in 12 months.",
        "indirectPublic": ["AMZN", "GOOGL"],
    },
    {
        "name": "xAI", "sector": "AI / Foundation Models",
        "valuation": 50, "revGrowth": 0, "arr": 0.1,
        "founders": "Elon Musk",
        "note": "Colossus supercluster (100k H100s), Grok models; tight coupling to X and Tesla data.",
        "indirectPublic": ["TSLA", "NVDA"],
    },
    {
        "name": "Databricks", "sector": "AI Data / Lakehouse",
        "valuation": 62, "revGrowth": 60, "arr": 3.0,
        "founders": "Ali Ghodsi + Spark creators",
        "note": "Lakehouse + Mosaic AI; path to IPO 2026-2027. Rival to SNOW + MSFT Fabric.",
        "indirectPublic": ["SNOW", "MSFT"],
    },
    {
        "name": "SpaceX", "sector": "Aerospace / Satellite",
        "valuation": 350, "revGrowth": 55, "arr": 13.0,
        "founders": "Elon Musk",
        "note": "Starlink crossed 4M subscribers; Starship enables new payload classes. Direct rival to RKLB.",
        "indirectPublic": ["RKLB", "IRDM"],
    },
    {
        "name": "Stripe", "sector": "Fintech / Payments",
        "valuation": 70, "revGrowth": 38, "arr": 21.0,
        "founders": "Patrick + John Collison",
        "note": "$1.4T TPV last year; Stripe Radar/Terminal expansion; IPO watch.",
        "indirectPublic": ["ADYEY", "PYPL"],
    },
    {
        "name": "Cerebras Systems", "sector": "AI Silicon",
        "valuation": 8, "revGrowth": 200, "arr": 0.4,
        "founders": "Andrew Feldman",
        "note": "Wafer-scale engine WSE-3; S-1 filed; direct NVDA training rival for large models.",
        "indirectPublic": ["NVDA", "AMD"],
    },
    {
        "name": "Groq", "sector": "AI Silicon / Inference",
        "valuation": 6, "revGrowth": 500, "arr": 0.15,
        "founders": "Jonathan Ross (ex-Google TPU)",
        "note": "LPU inference accelerators; claims 10× tokens/sec over GPUs; fastest-growing inference cloud.",
        "indirectPublic": ["NVDA", "AVGO"],
    },
    {
        "name": "Figure AI", "sector": "Humanoid Robotics",
        "valuation": 39, "revGrowth": 0, "arr": 0.05,
        "founders": "Brett Adcock",
        "note": "Figure 02 robots in BMW pilot; OpenAI partnership for vision-language-action models.",
        "indirectPublic": ["TSLA", "ISRG"],
    },
    {
        "name": "Anduril Industries", "sector": "Defense / Autonomy",
        "valuation": 14, "revGrowth": 100, "arr": 1.0,
        "founders": "Palmer Luckey",
        "note": "Lattice AI-native defense OS; Collaborative Combat Aircraft win; software-led defense disruption.",
        "indirectPublic": ["LMT", "PLTR"],
    },
    {
        "name": "Perplexity AI", "sector": "AI / Search",
        "valuation": 9, "revGrowth": 900, "arr": 0.12,
        "founders": "Aravind Srinivas, Denis Yarats",
        "note": "Answer engine; search disruption layer; partnerships with publishers for revenue share.",
        "indirectPublic": ["GOOGL", "MSFT"],
    },
    {
        "name": "Scale AI", "sector": "AI Data / Labeling",
        "valuation": 14, "revGrowth": 70, "arr": 1.0,
        "founders": "Alexandr Wang",
        "note": "RLHF + defense data; MSFT + Meta + US DoD customers; pick-and-shovel of the AI stack.",
        "indirectPublic": ["PLTR", "NVDA"],
    },
]

# ---------------------------------------------------------------------------
# Thematic / sector ETFs growing on the same tailwinds as the Cheetahs
# ---------------------------------------------------------------------------
ETFS = [
    {
        "ticker": "SMH", "name": "VanEck Semiconductor ETF",
        "theme": "Semiconductors", "expense": 0.35,
        "topHoldings": ["NVDA", "TSM", "AVGO", "AMD", "QCOM"],
        "ytd": 24, "oneYear": 45,
        "note": "25-stock cap-weighted; cleanest direct AI silicon exposure; lower single-name risk than owning NVDA alone.",
    },
    {
        "ticker": "SOXX", "name": "iShares Semiconductor ETF",
        "theme": "Semiconductors", "expense": 0.35,
        "topHoldings": ["AVGO", "NVDA", "AMD", "QCOM", "TXN"],
        "ytd": 20, "oneYear": 40,
        "note": "30-stock equal-ish weight; broader than SMH — includes QCOM, TXN heavier.",
    },
    {
        "ticker": "QQQM", "name": "Invesco NASDAQ-100 ETF",
        "theme": "Mega-cap tech", "expense": 0.15,
        "topHoldings": ["AAPL", "NVDA", "MSFT", "AMZN", "META"],
        "ytd": 17, "oneYear": 32,
        "note": "Cheapest Nasdaq-100 wrapper; 50%+ AI-linked mega caps.",
    },
    {
        "ticker": "IGV", "name": "iShares Expanded Tech-Software ETF",
        "theme": "Software / SaaS", "expense": 0.41,
        "topHoldings": ["MSFT", "CRM", "ORCL", "NOW", "PLTR"],
        "ytd": 15, "oneYear": 28,
        "note": "Pure-play software; benefits from AI-agent revenue cycle; PLTR + NOW upweighted.",
    },
    {
        "ticker": "BOTZ", "name": "Global X Robotics & AI ETF",
        "theme": "Robotics / AI", "expense": 0.68,
        "topHoldings": ["NVDA", "ISRG", "ABB", "KEYS", "FANUY"],
        "ytd": 18, "oneYear": 36,
        "note": "Narrower robotics exposure; good for humanoid-robotics + industrial automation theme.",
    },
    {
        "ticker": "WCLD", "name": "WisdomTree Cloud Computing ETF",
        "theme": "Cloud / SaaS", "expense": 0.45,
        "topHoldings": ["CRWD", "ZS", "NET", "MDB", "DDOG"],
        "ytd": 14, "oneYear": 26,
        "note": "Pure-play SaaS exposure; includes NET (Cheetah) + infrastructure software.",
    },
    {
        "ticker": "IBIT", "name": "iShares Bitcoin Trust",
        "theme": "Crypto / Digital assets", "expense": 0.25,
        "topHoldings": ["BTC spot"],
        "ytd": 28, "oneYear": 70,
        "note": "Non-correlated digital asset exposure; liquid BTC proxy for portfolios without custody.",
    },
    {
        "ticker": "ARKW", "name": "ARK Next Generation Internet ETF",
        "theme": "Disruptive internet", "expense": 0.75,
        "topHoldings": ["TSLA", "COIN", "ROBLOX", "PLTR", "RBLX"],
        "ytd": 21, "oneYear": 38,
        "note": "High-beta disruption play; concentrated; overlaps with PLTR + TSLA cheetahs.",
    },
    {
        "ticker": "ITA", "name": "iShares US Aerospace & Defense",
        "theme": "Aerospace / Defense", "expense": 0.40,
        "topHoldings": ["GE", "RTX", "LMT", "BA", "NOC"],
        "ytd": 16, "oneYear": 30,
        "note": "Defense budget tailwind; pairs with RKLB for space exposure.",
    },
    {
        "ticker": "URNM", "name": "Sprott Uranium Miners ETF",
        "theme": "Nuclear / Uranium", "expense": 0.75,
        "topHoldings": ["CCJ", "NXE", "SRUUF", "PDN", "DNN"],
        "ytd": 33, "oneYear": 58,
        "note": "AI-power demand → nuclear revival → uranium; pairs with OKLO cheetah thesis.",
    },
    {
        "ticker": "XBI", "name": "SPDR S&P Biotech",
        "theme": "Biotech", "expense": 0.35,
        "topHoldings": ["VRTX", "MRNA", "GILD", "REGN", "SRPT"],
        "ytd": 9, "oneYear": 18,
        "note": "Equal-weight biotech; less concentration risk than IBB; includes SRPT.",
    },
    {
        "ticker": "TAN", "name": "Invesco Solar ETF",
        "theme": "Solar / Clean energy", "expense": 0.67,
        "topHoldings": ["FSLR", "ENPH", "SEDG", "NXT", "ARRY"],
        "ytd": 12, "oneYear": 22,
        "note": "Data-center power demand + IRA incentives; clean-energy complement to nuclear (URNM).",
    },
]


def get_competitor_groups() -> list[dict]:
    """Enrich each group with anchor metrics from CHEETAH_STOCKS."""
    idx = {s["ticker"]: s for s in with_computed_scores(CHEETAH_STOCKS)}
    out = []
    for g in COMPETITOR_GROUPS:
        anchor = idx.get(g["anchor"])
        copy = dict(g)
        copy["anchorStock"] = (
            {
                "ticker": anchor["ticker"], "name": anchor["name"],
                "revGrowth": anchor["revGrowth"], "grossMargin": anchor["grossMargin"],
                "peg": anchor["peg"], "rs": anchor["rs"], "perf3m": anchor["perf3m"],
                "score": anchor["score"],
            }
            if anchor else None
        )
        out.append(copy)
    return out
