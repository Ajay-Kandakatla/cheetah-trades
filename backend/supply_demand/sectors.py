"""Curated sector list for supply/demand tracking.

Each sector has:
  - id, label, narrative
  - etf:        primary ETF that proxies sector exposure
  - commodity:  underlying commodity ticker (yfinance) if applicable
  - keywords:   for news search
  - sp_tickers: S&P names whose business is heavily dependent on this sector
  - thesis:     current supply/demand thesis we're tracking

The "gap_index" computed in tracker.py runs from -100 (oversupplied) to +100
(supply-constrained). Updated daily via cron + cached 6 hours.
"""
from __future__ import annotations

from typing import TypedDict


class Sector(TypedDict, total=False):
    id: str
    label: str
    narrative: str
    etf: str
    commodity: str
    keywords: list[str]
    sp_tickers: list[str]
    thesis: str
    gap_economics: dict


SECTORS: list[Sector] = [
    {
        "id": "ai_chips",
        "label": "AI Chips / GPUs",
        "narrative": "Cutting-edge accelerator silicon for AI training/inference. The biggest 'gap' story of 2024-2026.",
        "etf": "SMH",
        "commodity": "",
        "keywords": ["AI chip shortage", "GPU shortage", "H200", "Blackwell", "MI300", "data center GPU", "TSMC capacity", "advanced packaging"],
        "sp_tickers": ["NVDA", "AMD", "AVGO", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "MRVL"],
        "thesis": "Demand far exceeds supply through 2026 due to TSMC CoWoS packaging bottleneck. Hyperscaler capex runs at ~$300B/yr.",
        "gap_economics": {
            "demand_usd_bn": 200,
            "supply_usd_bn": 130,
            "unit": "annual revenue, AI accelerator silicon",
            "capex_to_close_usd_bn": 80,
            "years_to_close": "3–5",
            "key_constraint": "TSMC CoWoS-S advanced packaging capacity (~30k wafers/mo, growing 30%/yr)",
            "notes": "Each new $20B fab takes 3–5 yrs to bring online. ASML EUV tools have 18-month lead times. Even TSMC running flat-out, gap persists into 2027.",
            "as_of": "2024-Q4",
            "sources": ["NVDA 10-K FY25", "TSMC Q4'24 earnings", "Gartner WW Semi forecast"],
        },
    },
    {
        "id": "memory_hbm",
        "label": "Memory / HBM",
        "narrative": "High-bandwidth memory used in AI accelerators (HBM3E, HBM4). Sold out at every major DRAM maker.",
        "etf": "",
        "commodity": "",
        "keywords": ["HBM3E", "HBM4", "Micron HBM", "SK Hynix HBM", "DRAM shortage"],
        "sp_tickers": ["MU", "WDC", "SNDK"],
        "thesis": "Micron HBM3E sold out through end of 2025. NAND/SSD pricing recovering after 2023 trough.",
        "gap_economics": {
            "demand_usd_bn": 50,
            "supply_usd_bn": 32,
            "unit": "annual revenue, HBM specifically (subset of DRAM)",
            "capex_to_close_usd_bn": 25,
            "years_to_close": "2–3",
            "key_constraint": "TSV (through-silicon via) bonding capacity at SK Hynix, Samsung, Micron",
            "notes": "Each HBM3E line costs ~$10B and takes 18-24 months. SK Hynix has 2-quarter tech lead in 12-Hi stacks.",
            "as_of": "2024-Q4",
            "sources": ["Micron Q4'24", "SK Hynix earnings", "TrendForce"],
        },
    },
    {
        "id": "lithium",
        "label": "Lithium / EV Battery",
        "narrative": "Lithium hydroxide for EV batteries. Spot prices crashed 75% from 2022 highs but supply rationalizing.",
        "etf": "LIT",
        "commodity": "",
        "keywords": ["lithium price", "lithium hydroxide", "battery materials", "EV demand", "Albemarle"],
        "sp_tickers": ["TSLA", "ALB", "F", "GM"],
        "thesis": "Severe oversupply 2023-2024 absorbing slowly. EV demand growth offset by Chinese capacity additions.",
        "gap_economics": {
            "demand_usd_bn": 28,
            "supply_usd_bn": 38,
            "unit": "annual revenue, lithium chemicals at battery grade",
            "capex_to_close_usd_bn": -12,
            "years_to_close": "1–2",
            "key_constraint": "Inverse problem — supply is ~$10B too HIGH; capacity needs to come offline (or demand to catch up)",
            "notes": "Spot prices crashed 75% from 2022 peak. Chinese producers running below cash cost. Re-balance comes from EV demand growth + miners idling capacity.",
            "as_of": "2024-Q4",
            "sources": ["Albemarle Q4'24", "S&P Platts", "Benchmark Mineral Intelligence"],
        },
    },
    {
        "id": "copper",
        "label": "Copper",
        "narrative": "Critical for electrification, EVs, AI data centers (60-80kg copper per EV vs 20kg ICE).",
        "etf": "COPX",
        "commodity": "HG=F",
        "keywords": ["copper price", "copper supply", "Chile copper", "smelter shutdown"],
        "sp_tickers": ["FCX", "TSLA"],
        "thesis": "Long-term structural deficit projected. Codelco production declining. Greenfield mines take 8+ years.",
        "gap_economics": {
            "demand_usd_bn": 230,
            "supply_usd_bn": 220,
            "unit": "annual revenue, refined copper at $4.50/lb",
            "capex_to_close_usd_bn": 150,
            "years_to_close": "8–12",
            "key_constraint": "Greenfield mine permitting + ore grade decline at existing mines (Chuquicamata, Grasberg)",
            "notes": "BHP forecast ~10Mt deficit by 2035. Each new tier-1 mine costs $5-10B and takes 8+ yrs to first ore. AI data centers + EV grid build add ~3Mt/yr demand on top of baseline growth.",
            "as_of": "2024-Q4",
            "sources": ["BHP", "Wood Mackenzie", "Codelco production reports"],
        },
    },
    {
        "id": "rare_earths",
        "label": "Rare Earths",
        "narrative": "Neodymium, dysprosium for permanent magnets in EV motors, wind turbines, F-35 missiles.",
        "etf": "REMX",
        "commodity": "",
        "keywords": ["rare earth", "neodymium", "China rare earth export", "dysprosium", "MP Materials"],
        "sp_tickers": ["MP", "GM", "TSLA"],
        "thesis": "China controls 85%+ refined supply. US re-shoring via MP Materials Mountain Pass + Phase 2 magnet plant.",
        "gap_economics": {
            "demand_usd_bn": 12,
            "supply_usd_bn": 11,
            "unit": "annual revenue, refined rare-earth oxides + magnets",
            "capex_to_close_usd_bn": 8,
            "years_to_close": "5–7",
            "key_constraint": "Refining + magnet manufacturing — China holds 85% refined supply, 92% of magnet production",
            "notes": "True 'gap' is strategic, not absolute volumes. US needs ~$8B for full domestic refining + magnet supply chain. MP Phase 2 magnet plant ($1B) is just the start.",
            "as_of": "2024-Q4",
            "sources": ["USGS Mineral Commodity Summaries", "MP Materials 10-K", "DoE critical materials"],
        },
    },
    {
        "id": "oil_gas",
        "label": "Oil & Gas",
        "narrative": "Crude oil + natural gas. OPEC+ production cuts vs US shale + global demand.",
        "etf": "XLE",
        "commodity": "CL=F",
        "keywords": ["oil price", "OPEC+", "Brent", "WTI", "shale", "rig count"],
        "sp_tickers": ["XOM", "CVX", "OXY", "SLB"],
        "thesis": "Range-bound $70-85 WTI. Saudi spare capacity capping upside; demand growth slowing in China.",
        "gap_economics": {
            "demand_usd_bn": 2700,
            "supply_usd_bn": 2750,
            "unit": "annual revenue, global crude + condensate at ~$75/bbl",
            "capex_to_close_usd_bn": 0,
            "years_to_close": "balanced",
            "key_constraint": "OPEC+ has ~6 mb/d spare capacity (~$165B/yr in idle production) capping price upside",
            "notes": "Market is functionally balanced at $70-85 WTI. Saudi spare capacity is the price ceiling; US shale break-even is the floor. No structural gap to close — just price band.",
            "as_of": "2024-Q4",
            "sources": ["EIA STEO", "IEA Oil Market Report", "OPEC monthly report"],
        },
    },
    {
        "id": "uranium",
        "label": "Uranium / Nuclear Fuel",
        "narrative": "U3O8 spot rallying as data centers sign nuclear PPAs and SMRs gain commercial traction.",
        "etf": "URA",
        "commodity": "",
        "keywords": ["uranium price", "U3O8", "SMR", "small modular reactor", "nuclear PPA", "Cameco"],
        "sp_tickers": ["CCJ", "CEG", "VST", "MSFT"],
        "thesis": "Severe long-term deficit. Russian sanctions removed enrichment supply; data center demand new bid.",
        "gap_economics": {
            "demand_usd_bn": 14,
            "supply_usd_bn": 11,
            "unit": "annual revenue, U3O8 + enrichment + fuel fab at $80/lb",
            "capex_to_close_usd_bn": 15,
            "years_to_close": "5–8",
            "key_constraint": "Primary mine production + Western enrichment (post-Russian-ban). Conversion is the tightest sub-market.",
            "notes": "190M lb/yr demand vs ~140M lb primary supply (gap covered by inventories + secondaries which are running down). New mines $1-2B each + 5+ yrs. SMR demand adds optionality on top.",
            "as_of": "2024-Q4",
            "sources": ["WNA", "UxC", "Cameco Q4'24"],
        },
    },
    {
        "id": "steel",
        "label": "Steel",
        "narrative": "Hot-rolled coil prices, scrap. Affected by China demand + tariffs.",
        "etf": "SLX",
        "commodity": "",
        "keywords": ["steel price", "hot-rolled coil", "China steel", "Section 232 tariff"],
        "sp_tickers": [],
        "thesis": "Weak China demand pressuring global prices. US tariffs supporting domestic mills (NUE, STLD).",
        "gap_economics": {
            "demand_usd_bn": 1300,
            "supply_usd_bn": 1450,
            "unit": "annual revenue, global crude steel at ~$680/t",
            "capex_to_close_usd_bn": -50,
            "years_to_close": "structural oversupply",
            "key_constraint": "Inverse — China overcapacity (~250Mt of idle/excess EAF). Re-balancing requires Chinese capacity closures.",
            "notes": "Global capacity 2.4 Bt vs production 1.9 Bt. China still 55% of global supply. US tariffs help domestic mills but global oversupply persists.",
            "as_of": "2024-Q4",
            "sources": ["World Steel Association", "Platts SBB", "MEPS International"],
        },
    },
    {
        "id": "ag_grains",
        "label": "Agriculture / Grains",
        "narrative": "Corn, soybeans, wheat. Affected by weather, fertilizer prices, China imports.",
        "etf": "DBA",
        "commodity": "ZC=F",
        "keywords": ["corn price", "soybean price", "wheat", "USDA WASDE", "fertilizer"],
        "sp_tickers": ["ADM", "BG"],
        "thesis": "Bearish 2024-2025 cycle on strong harvests; bullish weather/geopolitical optionality.",
        "gap_economics": {
            "demand_usd_bn": 480,
            "supply_usd_bn": 500,
            "unit": "annual revenue, corn + soy + wheat trade at current prices",
            "capex_to_close_usd_bn": 0,
            "years_to_close": "annual cycle",
            "key_constraint": "Weather (La Niña, drought) is the year-to-year swing factor; structural supply is healthy",
            "notes": "Strong 2024 US corn/soy harvests pushing prices to multi-year lows. Bullish optionality from any La Niña / Black Sea disruption.",
            "as_of": "2024-Q4",
            "sources": ["USDA WASDE", "FAO", "ADM/BG earnings"],
        },
    },
    {
        "id": "healthcare_pharma",
        "label": "Healthcare / Pharma",
        "narrative": "GLP-1 weight-loss drugs in critical supply shortage. Manufacturing capacity ramping.",
        "etf": "XLV",
        "commodity": "",
        "keywords": ["GLP-1 shortage", "Mounjaro", "Wegovy", "obesity drug supply", "drug shortage", "FDA approval"],
        "sp_tickers": ["LLY", "PFE", "MRK", "JNJ", "UNH", "ISRG", "NVO"],
        "thesis": "GLP-1 demand vastly exceeds supply through 2026. CDMO fill-finish capacity is the binding constraint.",
        "gap_economics": {
            "demand_usd_bn": 75,
            "supply_usd_bn": 50,
            "unit": "annual revenue, GLP-1 obesity drugs (tirzepatide + semaglutide)",
            "capex_to_close_usd_bn": 12,
            "years_to_close": "3–5",
            "key_constraint": "Sterile fill-finish CDMO capacity. Active pharmaceutical ingredient (API) is plentiful; injection device + filling lines are the bottleneck.",
            "notes": "LLY building $9B in new capacity (Concord NC, Lebanon IN). Novo CapEx of ~$6B. Each fill-finish plant runs $1.5-2.5B + 3-5 yrs build. TAM by 2030 estimated $200B+ — gap likely WIDENS even as capacity expands.",
            "as_of": "2024-Q4",
            "sources": ["LLY 10-K FY24", "NVO Q4'24 earnings", "ISI Evercore obesity model"],
        },
    },
    {
        "id": "defense",
        "label": "Defense / Munitions",
        "narrative": "Backlog at multi-decade highs. 155mm shells, missile interceptors, naval shipbuilding all constrained.",
        "etf": "ITA",
        "commodity": "",
        "keywords": ["defense budget", "munitions", "155mm", "missile production", "Pentagon contract", "FY2026 defense"],
        "sp_tickers": ["LMT", "RTX", "NOC", "GD"],
        "thesis": "Supply-constrained across most product lines. Industrial base bottleneck — labor, foundries, primer cord.",
        "gap_economics": {
            "demand_usd_bn": 950,
            "supply_usd_bn": 880,
            "unit": "annual revenue, US + allied defense procurement",
            "capex_to_close_usd_bn": 60,
            "years_to_close": "5–7",
            "key_constraint": "Industrial base — skilled labor, foundries (steel + aluminum forgings), specialty chemicals (TNT, RDX, primer cord). Re-shoring takes years.",
            "notes": "155mm shell production: 14k/mo → goal 100k/mo by 2026 needs $3B+ capex. PAC-3 missile production: 500/yr → 1100/yr by 2027. Each scaled production line $200M-1B + 2-4 yrs.",
            "as_of": "2024-Q4",
            "sources": ["DoD FY25 budget", "GAO industrial base reports", "RTX/LMT earnings"],
        },
    },
    {
        "id": "shipping",
        "label": "Shipping / Logistics",
        "narrative": "Container freight rates + tanker rates. Red Sea reroute + Panama Canal drought lifted rates.",
        "etf": "SEA",
        "commodity": "",
        "keywords": ["freight rates", "shipping containers", "Red Sea", "Suez", "tanker rates", "BDIY"],
        "sp_tickers": [],
        "thesis": "Spot rates normalizing as Red Sea risk premium fades. Long-haul oversupply on container side.",
        "gap_economics": {
            "demand_usd_bn": 320,
            "supply_usd_bn": 360,
            "unit": "annual revenue, container freight at spot rates",
            "capex_to_close_usd_bn": -80,
            "years_to_close": "structural oversupply 2024-2026",
            "key_constraint": "Inverse — fleet orderbook is ~25% of fleet size, far above demand growth. Re-balance via vessel scrapping + slow-steaming.",
            "notes": "Container fleet adding 8% capacity 2024-2025 vs 3% trade volume growth. Red Sea reroute absorbed some but re-balance comes when transit normalizes.",
            "as_of": "2024-Q4",
            "sources": ["Drewry", "BIMCO", "Clarksons Research"],
        },
    },
    {
        "id": "datacenter_power",
        "label": "Data Center Power",
        "narrative": "Power capacity is the new bottleneck for AI training. Hyperscalers signing decade-long PPAs.",
        "etf": "XLU",
        "commodity": "",
        "keywords": ["data center power", "AI power demand", "PPA", "grid capacity", "Three Mile Island"],
        "sp_tickers": ["VST", "CEG", "NRG", "MSFT", "GOOGL", "AMZN"],
        "thesis": "Demand is growing faster than utilities can permit/build new capacity. Old nuclear restarts trading at premium.",
        "gap_economics": {
            "demand_usd_bn": 100,
            "supply_usd_bn": 60,
            "unit": "annual data-center power purchases (US, $40-60/MWh × ~150 TWh)",
            "capex_to_close_usd_bn": 250,
            "years_to_close": "7–12",
            "key_constraint": "Permitting + transmission. Generation is technically buildable but interconnect queues are 4-7 yrs and HV transmission lines take 10+ yrs to permit.",
            "notes": "Hyperscaler AI demand growing 20-30%/yr. New nameplate capacity needs ~$5B/GW (gas + transmission) or ~$7-15B/GW (nuclear). Need 50+ GW new capacity by 2030 = $250B+ capex.",
            "as_of": "2024-Q4",
            "sources": ["EIA Annual Energy Outlook", "FERC interconnect queue", "MSFT/GOOGL/AMZN PPA announcements"],
        },
    },
    {
        "id": "cloud_infra",
        "label": "Cloud Infrastructure",
        "narrative": "Hyperscaler capex pulled forward by AI; ~$300B+ aggregate spend 2025.",
        "etf": "IGV",
        "commodity": "",
        "keywords": ["hyperscaler capex", "AWS revenue", "Azure", "Google Cloud", "AI infrastructure spend"],
        "sp_tickers": ["MSFT", "AMZN", "GOOGL", "META", "ORCL", "NVDA"],
        "thesis": "Capex remains supply-constrained on the input side (chips, power) — gates revenue growth.",
        "gap_economics": {
            "demand_usd_bn": 700,
            "supply_usd_bn": 580,
            "unit": "annual revenue, IaaS + PaaS cloud (AWS, Azure, GCP, OCI, Tencent)",
            "capex_to_close_usd_bn": 300,
            "years_to_close": "1–2 (capex cycle)",
            "key_constraint": "Three-stage cascade: NVIDIA GPUs → power → data-center floor space. Currently chip-bound, but 2026+ likely power-bound.",
            "notes": "MSFT $80B FY25 capex, GOOGL $75B, AMZN $100B+, META $40B = ~$300B aggregate hyperscaler capex. Most of this maps to chip purchases (NVDA) + DC build.",
            "as_of": "2024-Q4",
            "sources": ["MSFT/AMZN/GOOGL/META Q4'24 capex guidance", "Synergy Research"],
        },
    },
    {
        "id": "robotics",
        "label": "Robotics / Automation",
        "narrative": "Surgical robotics, industrial automation, warehouse fulfillment. Long-term growth thesis.",
        "etf": "ROBO",
        "commodity": "",
        "keywords": ["surgical robot", "Da Vinci", "industrial automation", "Amazon robotics", "humanoid"],
        "sp_tickers": ["ISRG", "AMZN", "TSLA"],
        "thesis": "Surgical robotics in scarce-supply regime (multi-month wait at hospitals); humanoid still pre-revenue.",
        "gap_economics": {
            "demand_usd_bn": 80,
            "supply_usd_bn": 65,
            "unit": "annual revenue, surgical + industrial robotics (excludes humanoid)",
            "capex_to_close_usd_bn": 10,
            "years_to_close": "2–4",
            "key_constraint": "ISRG Da Vinci 5 production capacity — multi-month hospital waitlist. Industrial robotics gated by precision-machining + harmonic drive supply.",
            "notes": "ISRG ~2k Da Vinci 5 placements/yr capacity vs ~3k+ demand. Each manufacturing expansion ~$300M-1B + 18-24 months. Humanoid robotics ($XB optionality) still pre-revenue, excluded from gap.",
            "as_of": "2024-Q4",
            "sources": ["ISRG Q4'24 earnings", "ABB/FANUC reports", "International Federation of Robotics"],
        },
    },
]


SECTOR_BY_ID: dict[str, Sector] = {s["id"]: s for s in SECTORS}


def sectors_for_ticker(ticker: str) -> list[Sector]:
    """Sectors that include this ticker in their sp_tickers roster."""
    t = ticker.upper()
    return [s for s in SECTORS if t in (s.get("sp_tickers") or [])]
