"""Scanning universe — tickers we run SEPA against.

Three modes, selected via the `SEPA_UNIVERSE_MODE` env var or argument:

  - "curated"  (default) — the hand-picked ~130-name list below. Fast scans,
                           biased toward growth-friendly sectors.
  - "sp500"    — full S&P 500 (~503 names) fetched from Wikipedia (with an
                 explicit User-Agent — see fetch_sp500) or the datahub CSV
                 mirror, cached 30 days under ~/.cheetah/universe/sp500.txt.
  - "russell1000" — Russell 1000 holdings (~1000 names) fetched from iShares
                    IWB ETF holdings CSV. Cached 30 days.
  - "russell3000" — Russell 3000 holdings (~3000 names) fetched from iShares
                    IWV ETF holdings CSV. Cached 30 days. Opt-in only —
                    set SEPA_UNIVERSE_MODE=russell3000.
  - "expanded" — curated ∪ sp500 union (deduped).

You can also point SEPA_UNIVERSE_FILE at any text file (one ticker per line)
or set SEPA_UNIVERSE to a comma-separated override.
"""
from __future__ import annotations

import functools
import logging
import os
from massive_keys import stocks_key
import time
from pathlib import Path

log = logging.getLogger("sepa.universe")
UNIV_CACHE_DIR = Path.home() / ".cheetah" / "universe"
UNIV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
UNIV_CACHE_TTL_SEC = 30 * 24 * 3600  # 30 days

# Liquid growth + momentum names. Edit freely.
# Index ETFs carried in every universe for RS math ONLY — never tradeable rows.
# They are NOT in the SEPA scan's results, so a consumer that filters ETFs by
# the scan's own `is_etf` flag will silently let these three through: that is
# exactly how SPY/QQQ/IWM reached the pattern sweep on 2026-09-10 when it
# widened to load_universe("full"). Filter against THIS, not against a scan row.
RS_ANCHORS: tuple[str, ...] = ("SPY", "QQQ", "IWM")

UNIVERSE: list[str] = [
    # Mega-cap tech
    "NVDA", "MSFT", "AAPL", "META", "GOOGL", "AMZN", "TSLA", "AVGO", "ORCL", "NFLX",
    # Semis / AI infra
    "AMD", "ASML", "TSM", "MU", "ARM", "MRVL", "LRCX", "AMAT", "KLAC", "SMCI",
    "CRDO", "ALAB", "ANET", "CRWV", "NBIS",
    # Software / cloud
    "CRM", "NOW", "SNOW", "DDOG", "NET", "CRWD", "PANW", "ZS", "MDB", "PLTR",
    # NTSK added 2026-09-10. Ajay holds it AND watches it, and it named itself
    # in his security-sector ask — but it reached NO index layer, so it was
    # scanning nowhere: no SEPA card, no zone_store doc, and therefore no
    # demand / bounce / supply-break alert and no paper entry. A 2025 IPO is
    # exactly what this curated list exists to carry. NOTE this is the ONLY
    # thing that makes a ticker scannable: supply_demand/sectors.py sp_tickers
    # is display-only and shares no code path with this file.
    "NTSK",
    # Crypto EQUITIES, curated 2026-09-12. Ajay: "there are so many Crypto
    # related stocks are missin gin ours like IREN, Mining stocks like bit coind
    # related". Said alongside "Ignore Crypo" — and both hold: the TOKENS stay
    # out (BNB/ETH/XRP are refused outright), the listed companies come in.
    #
    # Only the names that were NOT already carried by an index layer are listed
    # here; IREN, MARA, RIOT, CLSK, CIFR, WULF, HUT, BTDR, CORZ, BTBT, APLD,
    # COIN, HOOD, GLXY and MSTR already reach `full` on their own.
    #
    # EVERY ONE PRICE-VALIDATED against production data before it went in.
    # GREE (7 bars) and SDIG (acquired by Bitfarms, stopped printing) FAILED
    # that check and are deliberately absent.
    # 2026-09-29 dead-ticker cleanup (sepa/symbols.py): BITF -> KEEL (rename,
    # 2026-04-06); SMLR delisted 2026-01-20, dropped.
    "KEEL", "HIVE", "CAN", "SLNH", "ARBK", "BKKT", "DFDV", "UPXI",
    # Crypto ETFs — they CHART AND SCAN BUT NEVER ALERT, the same deal he
    # accepted for the robotics funds: the provider reports AUM for a fund and
    # never a market cap, and zone_store keeps only a KNOWN cap over MIN_CAP_USD,
    # so no ETF can ever get zone bands or fire a demand push.
    "IBIT", "FBTC", "BITO", "BLOK", "WGMI", "BITQ", "DAPP",

    # AXTI added 2026-09-11 — the SAME invisibility, found while building the
    # growth tracker. Ajay named AXTI as the shape he wants ("I want real
    # growing stocks like AXTI and SABR with genuine sales") and it screens at
    # sales +145.9% YoY on a growing prior quarter, quarterly EPS +185.0%, cap
    # $3.95B. It sits in Russell 3000, so it reaches the `broad` universe
    # (3,703) that only the 16:30 fast-scan runs — but NOT `full` (2,651),
    # which is what the hourly scan, zone_store, every board and every alert
    # actually use. Net effect: zero zone_store docs, so AXTI could never fire
    # a demand alert no matter how good the setup. Curating it fixes that.
    "AXTI",
    # UMAC, CLYM, LWLG, WYFI added 2026-09-12 — Ajay pointed his own watchlist
    # at the app ("Can you check if these companies are in our scans?") and four
    # of twelve came back blind. Two failure modes, both already seen:
    #
    #   UMAC, CLYM — the AXTI case exactly: in `broad` (3,703) and therefore
    #       fast-scanned at 16:30, but NOT in `full` (2,652), which is what the
    #       hourly scan, zone_store, every board and every alert run on. Both
    #       had ZERO zone_store docs, so neither could ever fire a demand alert
    #       however good the setup looked.
    #   LWLG, WYFI — worse: not in `companies` at all, in no universe, never
    #       scanned. LWLG (Lightwave Logic) is a photonics name and `optical`
    #       was his #1 theme that week at +9.29%; WYFI (WhiteFiber) is Bit
    #       Digital's 2025 AI-infrastructure spin-out, and BTBT was already
    #       carried while its spin-out was not.
    #
    # All four verified priceable before being added, via the REAL fetchers and
    # not by hand: companies.store.get(force=True) filed each one, and
    # sepa.prices.load_prices returned 276-504 bars apiece through 2026-09-11.
    # NOTE their GICS tags are the provider's, not a guess, and one is a
    # surprise: LWLG files as Basic Materials / Specialty Chemicals, so it
    # would never have shown up under optical on a GICS-grouped board anyway.
    "UMAC", "CLYM", "LWLG", "WYFI",
    # Robotics ETFs, 2026-09-12 — Ajay: "Can you find robotics stocks and ETFs
    # please", then chose "charts and scans only" once the limit below surfaced.
    #
    # THE LIMIT, stated here because it is invisible otherwise: the provider
    # reports NO market cap for an ETF, only AUM (BOTZ $3.44B, ROBO $2.06B,
    # ARKQ $1.92B, ROBT $0.79B, KOID $0.33B). `zone_store.big_cap_universe`
    # keeps only a KNOWN cap >= MIN_CAP_USD, so every one of these is excluded
    # from the zone store and CAN NEVER FIRE A DEMAND ALERT. They chart, they
    # scan, they appear on boards; they do not alert.
    #
    # Deliberately NOT fixed by falling back to AUM: MIN_CAP_USD is shared with
    # trading/safety_floor.py, where it is a MANIPULATION-SAFETY floor that
    # blocks real buys. AUM is not market cap, and conflating them would change
    # what that number means on the entry path. His call, offered as option 2
    # and declined.
    "KOID", "BOTZ", "ROBO", "ARKQ", "ROBT",
    # CFLT + SMAR removed 2026-08-25 — both delisted (see sepa.symbols.DELISTED)
    "SHOP", "TEAM", "WDAY", "HUBS", "TOST",
    # Consumer growth
    "ABNB", "UBER", "DASH", "BKNG", "CMG", "LULU", "DECK", "COST", "WMT",
    # Health / biotech leaders
    "LLY", "UNH", "ISRG", "VRTX", "REGN", "BMRN", "RMD", "BSX",
    # Fintech / payments
    "V", "MA", "PYPL", "AXP", "COIN", "HOOD", "XYZ", "SOFI", "NU", "MELI",
    # Energy / industrials / materials
    "CEG", "VST", "GEV", "ETN", "PH", "CAT", "DE", "FSLR", "ENPH",
    # China ADR growth
    "BABA", "PDD", "JD", "NIO", "LI", "XPEV",
    # Canada (US-listed) — Canadian companies are excluded from the US Russell
    # indices, so they only reach the scan via this curated list.
    "BB", "AEM", "BMO", "BN", "BNS", "BTE", "CCJ", "CM", "CNI", "CNQ",
    "CP", "CVE", "DOO", "ENB", "FNV", "GIB", "IMO", "KGC", "LSPD", "MFC",
    "NTR", "OGI", "OTEX", "RY", "SLF", "SU", "TD", "TECK", "TLRY", "TRI",
    "TRP", "WCN", "WPM",
    # Foreign tech / semis (US-listed ADRs) — ASML / TSM / ARM are above.
    "SAP", "SE", "STM", "UMC", "ASX", "HIMX", "SONY", "INFY", "WIT",
    "BIDU", "NTES", "TCOM", "GRAB",
    # Small/mid momentum movers (edit freely)
    "RKLB", "ACHR", "JOBY", "SERV", "OKLO", "LUNR", "ASTS", "AEHR", "IONQ",
    "RGTI", "QBTS", "BBAI", "SOUN", "TEM", "HIMS", "DUOL", "RBLX", "DKNG",
    # RXT added 2026-09-18 on Ajay's approval ("yes go"). DOCN's closest direct
    # hosting peer — Rackspace sells the same thing one rung down the stack —
    # and it was reaching NO index layer: `broad` only, which is not a scanning
    # universe. Measured that day against production data before it went in:
    #   companies doc  Rackspace Technology, Inc. / Software - Infrastructure / NMS
    #   bars           502, first 2024-09-17, last 2026-09-17 (validated by the
    #                  LAST BAR DATE, never by bar count — the SDIG trap)
    #   liquidity      $41.06M/day on a 50-bar average
    #   market cap     $1,876,645,504 (shares_cache) — clears
    #                  supply_demand.zone_store.MIN_CAP_USD $700M, and 502 bars
    #                  clear MIN_BARS 120, so it finally gets zone bands. It had
    #                  ZERO zone_store docs, so it could never alert.
    #   price          $3.92 — which clears trading.safety_floor.MIN_SHARE_PRICE
    #                  $2.00 and safety_floor.MIN_CAP_USD $700M. SAY THIS OUT
    #                  LOUD: adding it here does not just make it visible, it
    #                  makes it push- and paper-entry eligible through the
    #                  UNCHANGED gates. No gate is loosened by this line; the
    #                  population those gates run over grows by one.
    # It sits with the small/mid movers, not in the `# Software / cloud` group
    # above — that group is the mega/large-cap software block and this is a
    # $1.9B, $3.92 name. It is ALSO a `cloud_infra` theme member below, the same
    # way the crypto names are carried in both places, so a later roster edit
    # can never silently drop it back out of `full`.
    "SPOT", "RDDT", "APP", "APPN", "PATH", "BILL", "DOCN", "RXT",
    # Anchor / benchmarks (not traded but used for RS math)
    *RS_ANCHORS,
]


# ---------------------------------------------------------------------------
# Theme rosters — the 2025-26 build-out names the S&P indices cannot hold.
#
# Ajay 2026-08-15: "make sure the new companies like Quantum based and Power
# based and robotics based and then Semis all are considered."
#
# WHY THIS EXISTS AS A SEPARATE LIST. S&P's index committee requires positive
# GAAP earnings and US domicile, so no quantum name is in any S&P tier, OKLO /
# SMR / NNE are pre-revenue, and ARM is a UK-domiciled ADR — structurally
# excluded from every S&P *and* Russell list. Measured 2026-08-15: sp1500
# resolves to 1,506 names and misses 12 of the 22 theme tickers Ajay named.
# That is not a bug in the fetchers to be fixed; it is what an index IS. So
# the names arrive by hand, tagged with the theme that earned them a slot.
#
# These are riskier than the index layers by construction — pre-profit, thin,
# high-beta. Nothing here bypasses a gate: they enter the same trend, knife and
# liquidity filters as every other name. This list only decides who gets LOOKED
# at, never who passes.
# ---------------------------------------------------------------------------
# Ajay 2026-08-16: "I do want us to give priority to Space technology, Quantum,
# Semis" and "Fiber optics, and Robotic components or any potential bottlenecks
# for AI that are going to be the next big thing.. after Semis and HBM."
#
# Every ticker below was probed against our own price feed before it was added
# (260 daily bars + 50-day dollar volume). Nothing here is from memory or a
# list off the internet. Names that resolved but are too thin to chart or trade
# were dropped on purpose, and the floor is noted per roster.
THEME_UNIVERSE: dict[str, list[str]] = {
    # Space technology — launch, satellites, imagery, satcom. Deliberately NOT
    # the defence primes (LMT/NOC/RTX/BA): they are conglomerates where space is
    # a segment, so tagging them "space" would put a defence budget story at the
    # top of the board. Dropped: SPCE ($3.32), MNTS ($4.84) — broken businesses;
    # SPIR ($17M/day) — too thin to chart honestly; ATRO/TDG/HEI — aerostructures
    # and aftermarket parts, not space technology.
    "space":     ["RKLB", "ASTS", "LUNR", "RDW", "PL", "BKSY",
                  "IRDM", "GSAT", "SATS", "VSAT",
                  # VOYG 2026-08-28: record bookings + Starlab; +54% in the
                  # early-Aug space rally
                  "VOYG",
                  # FLY 2026-08-28 (more-like-LPTH sweep): +659% rev, $1.5B
                  # backlog, below IPO price — lumpiest name on the roster
                  "FLY"],
    "quantum":   ["IONQ", "RGTI", "QBTS", "QUBT", "ARQQ"],
    # Crypto EQUITIES — Ajay 2026-09-12, looking at the 🔥 Hottest board:
    # "Where is Robitics and crypto here?"
    #
    # WHAT IS AND IS NOT HERE, because the answer is not obvious. The big
    # miners he would expect first — IREN, MARA, RIOT, CIFR, WULF, HUT, BTDR,
    # CORZ, APLD and GLXY — are ALREADY TRACKED, under `ai_power`, and they
    # stay there. Themes are a strict partition (`_assert_themes_disjoint`
    # raises at import), and those ten sit in ai_power because that is the
    # actual trade: they are power-constrained datacenter operators converting
    # contracted megawatts into AI/HPC hosting, which is why several were in
    # the universe on their own merits before any crypto roster existed.
    # Moving them here would disturb a roster he already watches AND would tell
    # him the wrong story about what drives them.
    #
    # So this theme is the half that had NO theme at all: the pure miners, the
    # exchanges and brokers, and the treasury holders.
    #
    # A TREASURY HOLDER IS A LEVERED COIN PROXY, not an operating business —
    # MSTR, DFDV, UPXI, BTCS and SBET move with the coin and with
    # their own issuance, and their "earnings" are mark-to-market. Read them
    # that way.
    #
    # NO SUPPLY GAP IS CLAIMED. Hashrate expands to meet price and difficulty
    # adjusts it away, so there is no bottleneck to own; the edge, where it
    # exists, is cheap contracted power. And the COINS stay out entirely —
    # BNB/ETH/XRP are not scannable US equities.
    #
    # The 23-name roster in supply_demand/sectors.py has no partition
    # constraint and still holds all of them; it renders on /supply-demand,
    # which he does not use. This is the Chart Maps copy.
    # 2026-09-29 dead-ticker cleanup (sepa/symbols.py): BITF -> KEEL (rename,
    # 2026-04-06); SMLR (delisted 2026-01-20) and CEP (delisted) dropped.
    "crypto":    ["CLSK", "BTBT", "KEEL", "HIVE", "CAN", "SLNH", "ARBK",
                  "COIN", "HOOD", "BKKT",
                  "MSTR", "DFDV", "UPXI", "BTCS", "SBET"],
    # Ajay 2026-09-11: "there are companies like SNDK but for raw material for
    # Semis" -> "yes add that". Then, correcting me: "i dont use supply deman
    # page at all.. I only been using chart maps". The sector I first added to
    # supply_demand/sectors.py only renders on /supply-demand, which he never
    # opens; the Chart Maps 🔥 Hot-sectors strip ranks THEMES, and themes come
    # from HERE. So the roster lives in both places, on purpose.
    #
    # THE LAYER UNDER THE CHIP. ai_semis below already holds the designers, the
    # four equipment giants and the HBM/storage names, plus ONTO/NVMI/CAMT. This
    # roster is the CONSUMABLES, sub-fab parts, test, probe and packaging step —
    # paid per wafer and per die rather than per tool, so it tracks fab
    # utilisation instead of the lumpy capex cycle.
    #
    # THEMES ARE A STRICT PARTITION — _assert_themes_disjoint() raises at import
    # on any ticker in two themes. I first wrote this roster with all 17 names
    # and the assert caught five of them: FORM, ICHR, ONTO and UCTT already sit
    # in ai_semis, and TER sits in robotics. They stay where they are rather
    # than being moved, so a roster he already watches is not disturbed; this
    # theme is the 12 that had no theme at all. The full 17-name roster lives in
    # supply_demand/sectors.py, which has no such constraint.
    #
    # READ BEFORE TRADING IT (measured 2026-09-11, same 6-month window): being
    # upstream is NOT the edge. ASML +26%, KLAC +27%, AMAT +34%, LIN -6%,
    # APD +1% against AEHR +166%, COHU +110%, MTRN +89%, ONTO +48%, VECO +45%.
    # Size mattered far more than position in the stack.
    "semi_materials": ["ENTG", "MTRN", "CBT", "ROG", "ACMR", "AEHR", "COHU",
                       "AMKR", "KLIC", "ACLS", "VECO", "PLAB"],
    # Semis incl. the HBM/storage layer Ajay named. MU is the HBM name; SNDK,
    # WDC and STX are the AI-storage bottleneck; ONTO/NVMI/CAMT are the
    # metrology tools that gate HBM stacking yield.
    "ai_semis":  ["ARM", "ALAB", "CRDO", "NVDA", "AVGO", "AMD", "MU", "MRVL",
                  "TSM", "LRCX", "AMAT", "KLAC",
                  "SNDK", "WDC", "STX", "ONTO", "NVMI", "CAMT",
                  # semicap suppliers riding the AI-WFE upcycle (2026-08-28:
                  # UCTT +191% YTD, ICHR +242% 1yr, FORM cryo/test for both
                  # semis AND quantum, MKSI lasers/vacuum)
                  "UCTT", "ICHR", "FORM", "MKSI"],
    # Fibre optics / optical interconnect — the bottleneck once compute is no
    # longer the constraint. Transceivers and lasers (COHR/LITE/AAOI/FN/POET),
    # optical networking (CIEN/MTSI), the fibre and glass itself (GLW), and the
    # connectors that carry it (APH/TEL). Contract manufacturers went to
    # ai_infra instead — they assemble the racks, they do not make the optics.
    # LPTH added 2026-08-28 (Ajay named it; +109% rev, $97.8M defense-optics
    # backlog, Russell 2000 only — outside every index layer we scan). VIAV
    # was already in the universe via sp400 but untagged (+149% YTD on AI-DC
    # optical test).
    "optical":   ["COHR", "LITE", "AAOI", "CIEN", "FN", "GLW", "MTSI", "POET",
                  "APH", "TEL", "LPTH", "VIAV"],
    # Robotic components / physical AI. Beyond the platform names: machine
    # vision (CGNX), perception (MBLY, OUST), motion and precision dispensing
    # (EMR, AME, NDSN, HON), and TSLA for humanoid/physical AI. Dropped as too
    # thin to chart: LAZR $18M, ATS $5M, KRNT $4M, INVZ $2M ($0.37 a share).
    "robotics":  ["SERV", "RR", "SYM", "TER", "ROK", "PATH", "ISRG",
                  "CGNX", "MBLY", "OUST", "EMR", "AME", "NDSN", "HON", "TSLA",
                  # 2026-08-28: INDI (Ajay named it — ADAS radar/vision semis,
                  # the MBLY precedent; Russell 2000 only), AMBA (edge-AI
                  # vision, 15+ robotics design wins), ALNT (motion, 1.31x
                  # book-to-bill — thinnest add, ~$10M/day), NOVT (precision
                  # motion for humanoids)
                  "INDI", "AMBA", "ALNT", "NOVT"],
    # Power FOR AI — the compute hosts whose real constraint is megawatts, plus
    # the generation sold to them. Ajay 2026-08-16: "energy is super important
    # now with AI lot of folks are investing in to Nuclear and Hyperscalers that
    # are power efficient like green energy like IREN for example."
    #
    # APLD/CRWV/NBIS moved here from ai_infra: they are power-constrained
    # datacenter operators, not rack hardware. BE/FSLR/NXT are the generation
    # side of the same trade. Residential solar (ENPH/RUN/ARRY/SEDG, -39% to
    # -58% since June) is a DIFFERENT thesis and is deliberately not here.
    "ai_power":  ["IREN", "CIFR", "CORZ", "WULF", "APLD", "CRWV", "NBIS",
                  "HUT", "RIOT", "MARA", "BTDR", "GLXY", "BE", "FSLR", "NXT",
                  # 2026-08-28: AGX (gas-plant EPC, $2.8B backlog for AI load),
                  # FRMI (Ajay named it — Amarillo 17GW AI campus; pre-revenue,
                  # $5 vs $37 high — the tag is a category, not an endorsement)
                  "AGX", "FRMI",
                  # 2026-08-28 more-like-LPTH sweep — storage/grid names whose
                  # backlog dwarfs the cap: EOSE +351% rev/$807M backlog,
                  # FLNC $6.4B backlog at 0.76x sales, AMSC backlog +40%
                  "EOSE", "FLNC", "AMSC"],
    "nuclear":   ["OKLO", "SMR", "NNE", "LEU", "BWXT", "TLN", "VST", "CEG",
                  # MIR 2026-08-28: radiation detection — picks-and-shovels on
                  # every SMR/restart, net income +145%
                  "MIR",
                  # 2026-09-21, Ajay: "can you add x energy and then other
                  # small energy companies in to our list please". XE is
                  # X-Energy Inc — the SMR/TRISO-fuel name that listed
                  # 2026-04-24, so it carries only ~103 daily bars and every
                  # window longer than that reads as unknown, not as flat.
                  # The rest is the FUEL CYCLE behind the reactors he already
                  # tracks: CCJ is the largest Western producer and was in
                  # supply_demand/sectors.py's uranium roster but never in this
                  # one, so it could not be tagged. Each name validated
                  # 2026-09-21 in the api container: resolves, a bar on
                  # 2026-09-19 or later, and a 50-day median dollar volume
                  # printed in docs/sepa/energy_universe_2026_09_21.md.
                  "XE", "CCJ", "UEC", "DNN", "NXE", "URG", "EU",
                  # Sub-$500M nuclear-fuel technology, thinner than the rest
                  # ($5.0M and $13.7M/day) but above the boards' own tradeable
                  # floor: LTBR (metallic fuel), ASPI (isotope enrichment).
                  "LTBR", "ASPI"],
    # Traditional energy. Added 2026-08-16 because the rotation measurement put
    # it first on base formation (45.5% VCP rate, 2.0x the market) and refiners
    # at +39.6% median since June. Excluded as DEAD tickers whose last bar
    # predates the window and would read as a flat 0%: MRO (last bar
    # 2024-11-21, acquired by COP), HES (2025-07-17, acquired by CVX),
    # CTRA (2026-05-06).
    "energy":    ["DK", "MPC", "VLO", "PSX", "LNG", "OKE", "COP", "XOM", "CVX",
                  "TRGP", "EOG", "FANG", "KMI", "WMB", "OXY", "DVN", "SLB",
                  "BKR", "PR",
                  # MTRX 2026-08-28 (more-like-LPTH sweep): LNG/ammonia tank
                  # EPC, backlog ~2x the cap, inflecting losses -> profit
                  "MTRX",
                  # 2026-09-21, Ajay: "other small energy companies". Every
                  # name above this line is a mega-cap major, refiner or
                  # midstream — the roster had no small end at all, so a
                  # small-cap energy move could never tag as energy. These are
                  # E&P / offshore names from $362M to $8.4B, each validated
                  # 2026-09-21 the same way as the nuclear additions.
                  # EXCLUDED and why (the MRO/HES/CTRA rule above): VTLE (last
                  # bar 2025-12-12), CIVI (2026-01-29) and BRY (2025-12-17) are
                  # dead in the price cache and would read as a flat 0%;
                  # AMPY ($2.6M/day), KGEI ($0.7M/day) and NPWR ($1.1M/day) are
                  # below the tradeable floor; SRUUF is a physical trust, not an
                  # operating company.
                  "SM", "MGY", "CRGY", "GPOR", "NOG", "TALO", "REPX",
                  "VTS", "EGY", "WTI", "REI"],
    # The people who BUILD the data centre, as opposed to the people who make
    # what goes inside it (Ajay 2026-09-09: "robotics, energy and optic fiber,
    # constructipn like for data centers add these").
    #
    # Why this is separate from ai_infra and from the Engineering &
    # Construction industry cohort. ai_infra is hardware — racks, cooling,
    # transmission gear — a different business with a different cycle. The
    # `Engineering & Construction` industry row (31 names) is the right grain
    # for "construction" but the wrong one for "for data centers": it is half
    # highways, water and environmental work (ROAD, GVA, ACM, J, TTEK), whose
    # driver is federal spending, not AI capex. These ten are the mechanical,
    # electrical and site contractors whose backlog moves with the build-out.
    #
    # PWR (Quanta) and DY (Dycom) belong here on the business and are LEFT in
    # ai_infra, because themes must stay disjoint and quietly restructuring his
    # existing rosters is not mine to do — say the word and they move.
    # Deliberately excluded: TT / JCI / CARR / LII (diversified HVAC majors,
    # data centres are a minority of revenue) and the civil names above.
    "datacenter_build": ["EME", "FIX", "IESC", "STRL", "MTZ", "MYRG", "PRIM",
                         "APG", "FLR", "LGN"],
    # Cloud infrastructure — the rented capacity, added 2026-09-18 on Ajay's
    # approval ("yes go") to "create a cloud / SaaS theme so that class can
    # reach the 🔥 Hot Sectors strip". Before this, NONE of the 16 themes was
    # cloud/SaaS/devtools and `infosec` was the only software roster at all.
    #
    # NAMING GUARD — READ THIS BEFORE EDITING EITHER ROSTER. `ai_infra` below is
    # the PHYSICAL BOX: racks, cooling, power distribution, transmission gear.
    # `cloud_infra` is the RENTED CAPACITY that runs on top of it. Two different
    # businesses on two different cycles; they will be confused within a month
    # if this paragraph is deleted.
    # `data_infra` (2026-09-28) is the DATA LAYER that runs on this capacity —
    # database, warehouse, observability, search. Three rosters, three
    # businesses.
    #
    # THE CUT RULE. Re-runnable, so the roster can be argued with instead of
    # taken on trust. STEPS 1-4 ARE MECHANICAL AND REPRODUCIBLE.
    # STEP 5 IS JUDGMENT — IT IS MINE, NOT A RULE, AND IT IS LABELLED AS SUCH.
    #
    #   1. SOURCE   Mongo `companies` where industry == "Software - Infrastructure"
    #               — the PROVIDER'S OWN TAG, not my taste and not a list off the
    #               internet. 106 docs on 2026-09-17.
    #               db.companies.find({industry:"Software - Infrastructure"},
    #                                 {symbol:1,_id:0})
    #   2. PARTITION  drop any ticker already in another THEME_UNIVERSE roster
    #               (20 names). THEMES ARE A STRICT PARTITION —
    #               _assert_themes_disjoint() raises at import.
    #   3. LIVENESS   last cached bar must be the freshest session (2026-09-17).
    #               VALIDATED BY DATE, NEVER BY BAR COUNT (the SDIG trap — a dead
    #               ticker keeps its history). Drops 6.
    #   4. LIQUIDITY  50-bar average dollar volume >= 20_000_000 — reused BY NAME
    #               from rotation.tracker.build(min_dollar_vol=20_000_000.0),
    #               the floor the very board this row renders on already applies
    #               to every sector row. NO price floor is invented here: 26 of
    #               the 235 existing theme members trade under $10.
    #               -> 52 names survive steps 1-4.
    #   5. THESIS (JUDGMENT — 52 -> 18, drops 34). The test, stated so it can be
    #               argued with: "Is the PRODUCT ITSELF hosted capacity that
    #               someone else's software or data runs on / is stored in —
    #               compute, storage, edge/CDN, DNS, database, developer
    #               platform, application delivery, communications transport?"
    #               IN by that test even though they are sold as SaaS:
    #                 DBX, BOX  the product IS the hosted storage tier; the
    #                           customer's DATA lives in it and is served from
    #                           it. Who owns the metal underneath is not the test.
    #                 TDC       a data platform others run workloads on.
    #                           On-prem-heavy today, which is a DELIVERY-MODEL
    #                           objection, not a product objection.
    #                           MOVED to data_infra 2026-09-28 (Ajay's data-
    #                           sector ask; a ticker lives in one roster). MDB
    #                           moved the same day.
    #                 TWLO,BAND communications transport; the product is the pipe.
    #               OUT by the same test, and the line that separates them:
    #                 AVPT      governance/backup TOOLING that manages data
    #                           living in Microsoft 365. The capacity is
    #                           Microsoft's; AVPT sells the management layer on
    #                           top. Compare DBX: the bytes are IN Dropbox. THAT
    #                           IS THE DISCRIMINATOR.
    #                 FIVN, APPN, AI, RZLV, ZETA, RAMP, YEXT — applications. The
    #                           product is the app.
    #                 payments, telematics, lidar, EDA, IT services, travel GDS
    #                           — not software capacity.
    #               Same line `infosec` drew at "pure-play security only" below.
    #
    # EXCLUSIONS, recorded so the roster is auditable:
    #   20 PARTITION HOLDS (they stay where they are, nothing is restructured):
    #     PANW CRWD ZS S OKTA FTNT TENB QLYS VRNS RPD SAIL NTSK RBRK GEN OSPN
    #     (infosec) · ARQQ (quantum) · BKKT (crypto) · CORZ CRWV (ai_power) ·
    #     PATH (robotics).
    #   MSFT ($13.25B/day), ORCL ($4.50B/day), PLTR ($5.76B/day) — conglomerates
    #     and application platforms where cloud is a SEGMENT. Same call `space`
    #     made on LMT/NOC/RTX/BA above. HIS CALL, flagged in the wrap-up.
    #     PLTR is in data_infra since 2026-09-28 (it passes THAT roster's
    #     thesis test); ORCL and MSFT stay out of both on this same SEGMENT
    #     rule — HIS CALL.
    #   SNOW, DDOG, DT, ESTC — the obvious cloud-data/observability names,
    #     excluded ONLY because the provider files them under
    #     "Software - Application", which step 1 does not read. HIS CALL.
    #     RESOLVED 2026-09-28: all four are in data_infra.
    #   PAYMENTS filed under Software-Infrastructure by the provider:
    #     XYZ TOST FOUR CPAY WEX RELY STNE PAGS PAYO PGY EEFT ACIW FLYW MQ EVTC
    #     IIIV IMXI PAYS PRTH RPAY PSFE — a fintech index wearing a cloud label.
    #   NOT HOSTED CAPACITY (step-5 test): AVPT (see the discriminator above) ·
    #     SNPS (EDA, provider mis-tag) · IOT (telematics) · CALX (broadband
    #     hardware) · AEVA (lidar) · NN (PNT) · BB (IoT/QNX) · GCT (B2B
    #     marketplace) · ZETA RAMP (martech) · FIVN (contact-centre SaaS) ·
    #     APPN (low-code apps) · DOX (telecom BSS) · NTCT (network monitoring) ·
    #     AI RZLV (AI applications) · BLSH (crypto exchange) · PRGS (mixed
    #     infrastructure-software portfolio) · SABR (travel GDS) · TCX YEXT
    #     AIOT CCSI.
    #   STALE — VALIDATED BY DATE, NOT BAR COUNT: INFQ (last bar 2026-09-11, and
    #     it carries 144 bars — bar count would have let it in) · XNDU
    #     (2026-08-25, 104 bars) · LIDR (2026-09-15) · OLB (2026-09-16) · KPLT
    #     (2026-09-14) · SQ (2026-09-14, superseded by RENAMES["SQ"] -> XYZ).
    #   BELOW THE $20M/day FLOOR: GRRR 15.0M · MQ 15.4M · EVTC 12.1M · IIIV 8.3M
    #     · PAYS 8.4M · IMXI 7.5M · CCSI 5.8M · TCX 1.1M · VHC 0.7M, and every
    #     sub-$1M name (REKR USIO AISP AUID CSAI FATN AIFA AIFC XBP). If the
    #     floor ever moves, GRRR and MQ come in FIRST — said here so a later
    #     session does not "discover" them.
    #   DELISTED, NEVER RE-ADD: CFLT (last bar 2026-03-16) and SMAR
    #     (2025-01-21) are in sepa.symbols.DELISTED; GREE and SDIG likewise.
    #     No companies doc at all: WIX FROG PSTG INFA MNDY.
    #   THE SEVEN HANDED NAMES THAT FAILED THE THESIS TEST: PDYN (robotics) ·
    #     LIDR (lidar, stale) · ZENA (drones) · OLB (payments, stale) · TLS
    #     (security — it would belong in infosec) · VERI (AI applications) ·
    #     GRRR (mixed, and under the floor). BLZE was the one of the eight that
    #     passed, and it is in.
    #
    # NET-NEW TO `full`: RXT and BLZE only — measured 2689 -> 2691 in the api
    # container. Everything else already reaches `full` via sp1500/russell3000/
    # curated, which is normal: a theme roster is a MEASUREMENT COHORT for the
    # rotation board's median, not a coverage mechanism (infosec: 15 of 15
    # already reach `full`; biotech 31 of 32).
    #
    # NO EDGE IS CLAIMED. Sector/industry heat measured NULL for demand
    # outcomes on 2026-09-09 (-0.57pp, CI spans zero; cold beat hot at 5
    # sessions). This row is context. It gates nothing and it must never borrow
    # infosec's +8.00pp morning.
    #
    # 16 names (MDB and TDC moved to data_infra 2026-09-28) leaves 8 of
    # headroom over rotation.tracker.MIN_COHORT_N (8) before the row prints
    # `· thin`.
    "cloud_infra": ["NET", "NTAP", "TWLO", "AKAM", "DOCN", "FFIV",
                    "VRSN", "GTLB", "GDDY", "NTNX", "DBX", "BOX",
                    "BAND", "BLZE", "RXT", "ATEN"],
    # Data infrastructure — the DATA LAYER, added 2026-09-28 on Ajay's ask,
    # verbatim: "Can you create a new sector for DATA driven companies like
    # DATA DOG, Mongo DB and Snow flake in to the add them accross board where
    # we have sectors".
    #
    # NAMING: `ai_infra` = the box (racks, cooling, power). `cloud_infra` = the
    # rented capacity (compute, storage, edge, DNS, delivery, comms).
    # `data_infra` = the DATA LAYER running on that capacity (database,
    # warehouse / data cloud, observability, search, event analytics).
    #
    # THE CUT RULE:
    #   1. ANCHORS    his three: DDOG, MDB, SNOW.
    #   2. THESIS (JUDGMENT — MINE, NOT A RULE): "Is the PRODUCT ITSELF the
    #               layer where a customer's data is stored, queried, searched
    #               or observed — database, data warehouse / data cloud,
    #               observability telemetry, search, event analytics,
    #               data-integration platform?"
    #   3. SEGMENT    a conglomerate where the data layer is one segment of the
    #               business is OUT. cloud_infra's own rule as it applies to
    #               the conglomerates MSFT and ORCL (the SEGMENT line above),
    #               reused, not reinvented; IBM is the same case. PLTR is NOT
    #               under this rule here: its product IS the data platform
    #               (see "PLTR IS IN" below). HIS CALL.
    #   4. PARTITION  _assert_themes_disjoint() — a ticker lives in ONE roster.
    #               MDB and TDC MOVED from cloud_infra; nothing else moved.
    #   5. LIVENESS   last cached bar == the freshest session 2026-09-28.
    #               VALIDATED BY DATE, NEVER BY BAR COUNT (the SDIG trap).
    #   6. LIQUIDITY  50-bar average dollar volume >= 20_000_000, reused BY NAME
    #               from rotation.tracker.build(min_dollar_vol=20_000_000.0) and
    #               trading.safety_floor.MIN_DOLLAR_VOL. No new number.
    #
    # EXCLUSIONS, each with its reason:
    #   SEGMENT: ORCL ($4.3B/day), IBM ($1.5B/day, owns Db2 and Confluent),
    #     MSFT — the data layer is one segment of a conglomerate. Same call as
    #     cloud_infra made on ORCL/MSFT above. HIS CALL.
    #   DOMO: last bar 2026-09-23 (stale) and $7.2M/day (under the floor).
    #   CFLT: in sepa.symbols.DELISTED (acquired by IBM) — never re-add.
    #   BASE: last bar 2025-09-23. FROG, KVYO: 2026-08-31. CWAN: 2026-06-24.
    #   INFA, SWI, PSTG: no cached bars.
    #   PD: an incident-response workflow APP, not a data layer. It also sits
    #     under the 50-bar floor ($18.8M) but clears the 20-day median ($21.7M),
    #     so the metric does not decide it; the thesis does.
    #   PRGS: mixed infrastructure-software portfolio.
    #   Data vendors SPGI ICE MSCI FDS VRSK: they SELL their own data; the
    #     customer's data does not live in them. HIS CALL.
    #   Storage hardware P (Everpure) and QMCO; backup CVLT (its peer RBRK is
    #     in infosec). HIS CALL.
    #   Apps IOT, AI, AVPT, BRZE, RAMP, ZETA, OTEX, INOD, NTCT; edge FSLY.
    #   PARTITION holds NTAP NTNX GTLB DBX BOX — they stay in cloud_infra.
    #
    # PLTR IS IN ON THE THESIS TEST, NOT THE COUNT: its product is the
    # data-integration / analytics platform over the customer's data. The
    # consequence: 8 names = exactly MIN_COHORT_N, zero headroom. A member
    # drops from `n` only after more than MAX_STALE_DAYS (10) calendar days
    # without a bar, and one such member prints `· thin`. Without PLTR: 7,
    # `· thin`. With ORCL too: 9. HIS CALL: PLTR and/or ORCL.
    #
    # NET-NEW TO `full`: 0 (2730 -> 2730), measured in the api container. A
    # measurement cohort, not coverage.
    #
    # NO EDGE IS CLAIMED (sector heat measured NULL 2026-09-09). Gates nothing.
    "data_infra": ["SNOW", "DDOG", "MDB", "DT", "ESTC", "TDC", "AMPL", "PLTR"],
    # Racks, cooling, transmission hardware.
    "ai_infra":  ["VRT", "MOD", "SMCI", "ANET", "ETN", "PWR", "GEV", "NVT",
                  "HUBB", "POWL", "AAON", "CLS", "FLEX",
                  # 2026-08-28 buildout suppliers: SPXC (DC cooling +23%), AZZ
                  # (grid coatings), VICR (800VDC rack power, +274% 1yr), DY
                  # (fiber/DC construction, +38% rev), PENG (AI/HPC clusters)
                  "SPXC", "AZZ", "VICR", "DY", "PENG",
                  # 2026-08-28 more-like-LPTH sweep: CECO (DC air/thermal,
                  # $1.8B backlog), SANM (bought AMD's ZT rack manufacturing,
                  # +70-102% quarters at ~14x earnings)
                  "CECO", "SANM"],
    # Defense tech / drones (Ajay 2026-08-28: "the ones Trump has been
    # announcing" — the $150B shipbuilding/Golden Dome/drone cycle). Small/mid
    # caps with 2026 contract traction, not the primes: ONDS 13x rev + $757M
    # backlog, RCAT +520% rev on Army SRR, BBAI $282M backlog, KRMN $1.3B
    # backlog, KTOS (CCA jets — nearly large-cap but the category anchor).
    # LASR 2026-08-28: directed-energy lasers (HELSI-2, JLWS ~$607M ceiling),
    # A&D revenue +41% while the stock halved.
    "defense":   ["ONDS", "RCAT", "BBAI", "KTOS", "KRMN", "LASR"],
    # Rare earth / critical minerals (the 2026 Section 232 + July EO trade):
    # MP the anchor, USAR mine-to-magnet, UUUU first US heavy-REE production
    # (Mar 2026), METC Brook Mine optionality on met-coal revenue.
    "rare_earth": ["MP", "USAR", "UUUU", "METC"],
    # Information security (Ajay 2026-09-14, watching the AI dump: "Where is
    # information security? Like NTSK and other companies").
    #
    # WHY IT EARNED A ROSTER ON THAT DAY: on 2026-09-14 the 15 names below ran
    # a median +7.80% while ai_semis ran -6.95% on the same tape — +8.00pp
    # against RSP, with all 15 green. The Technology SECTOR read only +1.15
    # because it averages collapsing semis against ripping software, so the
    # rotation was invisible at every grain the app had.
    #
    # Pure-play security only. NET, DDOG, AKAM and CHKP are deliberately OUT:
    # the first three are CDN/observability businesses that carry a security
    # line, and a roster that admits them stops measuring this thesis.
    #
    # VALIDATED LIVE 2026-09-14 by LAST BAR DATE, not bar count (the SDIG trap
    # — a dead ticker keeps its history). Three names failed and must not be
    # re-added without re-checking: CYBR (last bar 2026-02-10), JAMF
    # (2026-01-29), MIME (no data — taken private 2022).
    "infosec":   ["CRWD", "PANW", "ZS", "S", "OKTA", "FTNT", "TENB", "QLYS",
                  "VRNS", "RPD", "SAIL", "NTSK", "RBRK", "GEN", "OSPN"],
    # 2026-09-14 — Ajay, with a watchlist screenshot of green biotech against a
    # red tape: "Do we have any bio and theraputics stocks especially these a
    # bunch of them are gaining momentun in this down trend market whcih is
    # mostly red". We did not: all 15 existing themes were AI, hardware, energy,
    # defence, crypto or infosec, and nothing covered drug developers.
    #
    # He was right about the tape. Measured that afternoon: XLV +1.40%,
    # ARKG +3.01%, XBI +1.00% against SMH -4.75% and QQQ -0.66% — a six-point
    # spread on the day. The Healthcare SECTOR grain only read +2.81% over 21
    # days, because a 642-name sector dilutes a biotech move exactly the way
    # "Technology" once hid a 33-point semis-vs-software spread (2026-09-09).
    # That dilution is the whole reason this is a theme and not a sector read.
    #
    # THERAPEUTICS ONLY — the line is "does its value sit in a drug pipeline".
    # Deliberately NOT here, including two from his own screenshot:
    #   ACHC  behavioural-health FACILITIES — a hospital operator
    #   EL    Estee Lauder, cosmetics — not healthcare at all
    #   NTRA VCYT   diagnostics, and TWST synthetic-DNA tools — they sell to
    #               drug developers, they do not develop drugs
    #   GANX  real therapeutics but ~$1M/day; it would swing the median on noise
    # Validated by LAST BAR DATE, not bar count (the infosec lesson from the
    # same morning). Nine candidates were dropped as dead despite carrying years
    # of history: APLS (last bar 2026-05-13), CRNX (08-31), FOLD (04-24),
    # SAVA (03-10), DVAX (02-09), BPMC (2025-07-17), SWTX (2025-06-30),
    # ITCI (2025-04-01), BGNE (2024-12-31).
    # 2026-09-21, Ajay: "Do we have critical minerals in our list?" and "Also
    # greenland minerals or greenland related mineral companies". The answer
    # before this line existed was: barely. `rare_earth` carried four names and
    # nothing covered lithium, copper, titanium or antimony, so a critical-
    # minerals move could not tag at all. supply_demand/sectors.py has lithium
    # / copper / rare_earths NARRATIVES, but their sp_tickers (TSLA, F, GM,
    # ALB, FCX) are a dependency read, not a roster — none of them was tagged.
    #
    # rare_earth is left exactly as it is: MP / USAR / UUUU / METC really are
    # rare earths. This roster is the wider complex around it.
    #
    # GREENLAND, measured rather than assumed: CRML (Critical Metals Corp,
    # $1.3B, $38M/day) is the Tanbreez rare-earth project and is the ONLY
    # liquid US-listed Greenland name. Amaroq (AMRQ/AMQ), Bluejay (BLUJ),
    # Eclipse (EGDFF) and TANB return no US bars at all — they list in London
    # or Toronto and this app cannot price them. GLND is named "Greenland
    # Energy Co" but is a $52M shell at $1.0M/day, under the tradeable floor,
    # and is deliberately NOT here. UUUU stays in rare_earth; it is the third
    # name in the Greenland headline cohort on the POTUS tab, and a ticker
    # lives in exactly one roster.
    #
    # Every name validated 2026-09-21 in the api container: resolves, not
    # delisted, a bar on 2026-09-19 or later, 50-day median dollar volume
    # recorded in docs/sepa/energy_universe_2026_09_21.md. EXCLUDED and why —
    # dead price history: TMRC (last bar 2026-08-10), PLL (2025-08-29), LITM
    # (2026-03-13), ARMN (2026-02-18); under the floor: KRO ($2.7M/day), USAU
    # ($2.9M), WWR ($0.4M), GPHOF ($0.1M), GLND ($1.0M).
    #
    # NAK is a permitting story with no production (Pebble). It is here because
    # this roster is a MEASUREMENT COHORT and the tag is a category, not an
    # endorsement — the same rule the FRMI line in ai_power states.
    "critical_minerals": ["CRML", "ALB", "SQM", "LAC", "SGML", "ABAT",
                          "FCX", "SCCO", "TECK", "HBM", "ERO", "IE", "NAK",
                          "PPTA", "UAMY", "TROX", "IPX", "NB", "IDR"],
    "biotech":   ["AMGN", "GILD", "VRTX", "REGN", "BIIB", "MRNA", "BNTX",
                  "ALNY", "NBIX", "SRPT", "BMRN", "INCY", "EXEL", "HALO",
                  "AXSM", "PTGX", "LQDA", "VERA", "DYN", "RYTM", "KRYS",
                  "SMMT", "IOVA", "RARE", "IONS", "UTHR", "MDGL", "TGTX",
                  "ARWR", "PCVX", "RVMD", "JAZZ"],
}

# Ordering BETWEEN themes, most-wanted first — Ajay's stated priority, then the
# bottlenecks he expects to matter next. Before this, every theme scored the
# same and the board could only answer "theme or not", never "which theme".
# A theme missing from this map sorts last but still ahead of untagged names.
THEME_PRIORITY: dict[str, int] = {
    "space":     0,
    "quantum":   1,
    "ai_semis":  2,
    # 2026-09-11 — right behind the chips it feeds, because it is the SAME story
    # one layer down: fabs cannot ship without the consumables, the probe cards
    # and the packaging step. Everything below shifts one rank; relative order
    # is unchanged.
    "semi_materials": 3,
    # The power thesis, kept together and ranked right behind Ajay's stated
    # three: AI is megawatt-constrained, so the compute hosts, the reactors and
    # the barrels are one story, not three.
    "ai_power":  4,
    "nuclear":   5,
    "energy":    6,
    "optical":   7,
    "robotics":  8,
    "ai_infra":  9,
    # Right behind the hardware it houses — same build-out, different half.
    "datacenter_build": 10,
    # 2026-09-18 — directly behind datacenter_build because it is the layer the
    # build-out SELLS: the datacenters get poured and wired, the racks go in,
    # and this is the capacity rented off them. THE RANK IS MINE, NOT HIS — he
    # asked for a cloud theme, he did not ask for this placement, exactly as
    # with semi_materials and datacenter_build. Everything below shifts one
    # rank; relative order is unchanged.
    "cloud_infra": 11,
    # 2026-09-28 — directly behind cloud_infra because it is the same software
    # story one layer up: cloud_infra rents the capacity, data_infra is the data
    # layer running on it. THE RANK IS MINE, NOT HIS — he asked for the sector,
    # not for this placement, exactly as with semi_materials, datacenter_build,
    # cloud_infra and critical_minerals. Everything below shifts one rank;
    # relative order is unchanged.
    "data_infra": 12,
    "defense":   13,
    "rare_earth": 14,
    # 2026-09-21 — directly behind rare_earth because it is the SAME story one
    # layer wider: the reactors, batteries and grid above all bottleneck on
    # these inputs. THE RANK IS MINE, NOT HIS — he asked for the names, not for
    # the placement, exactly as with semi_materials, datacenter_build and
    # cloud_infra. Everything below shifts one rank; relative order is
    # unchanged.
    "critical_minerals": 15,
    # 2026-09-14 — ahead of crypto, behind the AI build-out. It is an
    # AI-ecosystem story (agent and model security is the new attack surface)
    # but an indirect one, so it does not outrank the hardware.
    "infosec":   16,
    # Last on purpose: it is the only roster here with no AI-ecosystem thesis,
    # and his standing rule puts AI-ecosystem winners on top of every list.
    "crypto":    17,
    # 2026-09-14 — ranked BELOW every AI theme and below crypto, deliberately.
    # It is the one theme here that is not an AI story at all, and his standing
    # rule is that AI-ecosystem winners lead any list. This tag decides which
    # label a name carries when it sits in two themes; it does not decide where
    # a theme ranks on a board — the rotation grain ranks on measured return.
    "biotech":   18,
}

# Rank used for a tagged theme that is not in THEME_PRIORITY — still ahead of
# every untagged name, which is what UNTAGGED_RANK guarantees.
UNKNOWN_THEME_RANK = 50
UNTAGGED_RANK = 99

# Reverse map, built once — a linear scan over the rosters per ticker is fine
# for a card and wasteful for a 1,500-row board.
#
# A ticker must live in exactly ONE roster: this dict is last-wins, so a
# duplicate would silently retag the name and change its priority. NVDA is the
# obvious temptation (it is the physical-AI platform as much as it is a semi) —
# it stays in ai_semis. `_assert_themes_disjoint()` below makes the rule fail
# loudly at import instead of quietly at sort time.
THEME_BY_TICKER: dict[str, str] = {
    t: theme for theme, names in THEME_UNIVERSE.items() for t in names
}


def _assert_themes_disjoint() -> None:
    seen: dict[str, str] = {}
    dupes: list[str] = []
    for theme, names in THEME_UNIVERSE.items():
        for t in names:
            if t in seen:
                dupes.append(f"{t} in both {seen[t]} and {theme}")
            seen[t] = theme
    if dupes:
        raise ValueError("THEME_UNIVERSE tickers must be unique: " + "; ".join(dupes))


_assert_themes_disjoint()


def theme_for(symbol: str) -> str | None:
    """Which build-out theme a ticker belongs to, or None. PURE."""
    if not isinstance(symbol, str):
        return None
    return THEME_BY_TICKER.get(symbol.strip().upper())


def theme_rank(theme: str | None) -> int:
    """Sort rank for a theme — lower leads. Untagged names sort last. PURE."""
    if not theme:
        return UNTAGGED_RANK
    return THEME_PRIORITY.get(theme, UNKNOWN_THEME_RANK)


def fetch_themes() -> list[str]:
    """Every theme name, deduped, order-stable. No network — hand-curated."""
    out: list[str] = []
    seen: set[str] = set()
    for names in THEME_UNIVERSE.values():
        for t in names:
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


# ---------------------------------------------------------------------------
# Remote-list fetchers (cached to disk for 30 days)
# ---------------------------------------------------------------------------
# 2026-09-29 (round 2): the iShares lists' cache FILES are versioned. The
# caches the old May-xls loader wrote hold no holdings date and would keep
# serving that vintage for up to 30 days after the deploy; a new file name
# stops them matching, and every file under the new name is written with its
# holdings-date sidecar (`_cache_as_of_path`). Keyed by the LIST name so every
# caller (`_read_cached`, `_cache_age_days`, universe_changes._expire_cache)
# follows without change.
_CACHE_KEY_VERSIONS: dict[str, str] = {
    "russell1000": "russell1000_v2",
    "russell3000": "russell3000_v2",
    "microcap": "microcap_v2",
}


def _cache_path(name: str) -> Path:
    return UNIV_CACHE_DIR / f"{_CACHE_KEY_VERSIONS.get(name, name)}.txt"


def _cache_as_of_path(name: str) -> Path:
    """Sidecar holding the SOURCE's own list date for a cached list
    (``<key>.as_of``, one ISO date). Written beside the list, so a cache hit
    carries the date the holdings are from, not just when we fetched them."""
    p = _cache_path(name)
    return p.with_name(p.stem + ".as_of")


def _read_cached_as_of(name: str) -> str | None:
    """The sidecar date for `name`'s cache, or None (absent / unreadable)."""
    try:
        raw = _cache_as_of_path(name).read_text().strip()
    except Exception:
        return None
    try:
        from datetime import date as _date
        return _date.fromisoformat(raw).isoformat()
    except ValueError:
        return None


def _write_cached_as_of(name: str, as_of: str | None) -> None:
    """Write (or, when the source stated no date, REMOVE) the sidecar, so a
    stale date can never outlive the list it described."""
    p = _cache_as_of_path(name)
    try:
        if as_of:
            p.write_text(as_of)
        elif p.exists():
            p.unlink()
    except Exception as exc:                            # noqa: BLE001
        log.warning("universe: could not write %s: %s", p.name, exc)


def _read_cached(name: str) -> list[str] | None:
    path = _cache_path(name)
    if not path.exists():
        return None
    if (time.time() - path.stat().st_mtime) >= UNIV_CACHE_TTL_SEC:
        return None
    return [ln.strip().upper() for ln in path.read_text().splitlines() if ln.strip()]


def _read_cached_stale(name: str) -> list[str] | None:
    """Read a cached list IGNORING the TTL. Only for use as a last-resort
    fallback when the live fetch fails — an out-of-date real index beats a
    fresh list of the wrong universe. Returns None if no file exists."""
    path = _cache_path(name)
    if not path.exists():
        return None
    syms = [ln.strip().upper() for ln in path.read_text().splitlines() if ln.strip()]
    return syms or None


def _file_age_days(path: Path) -> float | None:
    """Age of a file on disk in days, or None when it is not there. Used to
    stamp provenance for the manually-downloaded iShares exports, whose
    freshness is a human's refresh cadence, not a TTL."""
    try:
        if not path.exists():
            return None
        return (time.time() - path.stat().st_mtime) / 86400.0
    except Exception:
        return None


def _cache_age_days(name: str) -> float | None:
    path = _cache_path(name)
    if not path.exists():
        return None
    return (time.time() - path.stat().st_mtime) / 86400.0


def _write_cached(name: str, syms: list[str]) -> None:
    _cache_path(name).write_text("\n".join(syms))


# ---------------------------------------------------------------------------
# HTTP with an explicit User-Agent (2026-08-13)
# ---------------------------------------------------------------------------
# Wikipedia answers HTTP 403 to the default urllib/pandas user-agent — which
# is what `pandas.read_html(url)` sends when you hand it a URL, because pandas
# fetches the page itself via urllib. Verified inside the api container:
#
#   default urllib UA                 -> HTTP 403  (126 bytes, error page)
#   any descriptive/browser UA        -> HTTP 200  (568 KB, the real article)
#
# So we never let pandas do the fetching. We fetch with `requests` + a
# descriptive UA (Wikimedia's UA policy asks for an identifiable agent with a
# contact URL) and hand pandas the HTML text. Same trick applies to any other
# HTML/CSV source that filters on UA.
_HTTP_UA = "cheetah-market-app/1.0 (+https://pounce.ajaykandakatla.dev)"


def _fetch_text(url: str, *, timeout: int = 20) -> str:
    """GET `url` with our descriptive User-Agent; raise on non-2xx."""
    import requests
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": _HTTP_UA})
    resp.raise_for_status()
    return resp.text


def _read_html_ua(url: str, *, timeout: int = 20):
    """`pandas.read_html`, but over HTML we fetched ourselves with a real UA.

    Never pass a URL straight to pandas.read_html — it fetches with the
    default urllib UA and Wikipedia 403s that.
    """
    import io
    import pandas as pd
    return pd.read_html(io.StringIO(_fetch_text(url, timeout=timeout)))


# --- source provenance ------------------------------------------------------
# Which source each list actually came from on the last resolve, so callers
# can tell "the real, fresh index" from "a 76-day-old snapshot" from "the
# wrong universe entirely". Without this, a stale list looks identical to a
# fresh one at the call site and degrades silently — exactly the failure this
# module hit between 2026-05-29 and 2026-08-13.
_LAST_SOURCE: dict[str, dict] = {}


def _record(name: str, source: str, syms: list[str], *,
            age_days: float | None = None,
            as_of: str | None = None) -> list[str]:
    rec = {"source": source, "n": len(syms), "age_days": age_days}
    # `as_of` is the date the SOURCE says its list is from (the iShares
    # "Fund Holdings as of" line). Only the iShares paths know it, so the key
    # is only present when it is — every other record keeps its old shape.
    if as_of is not None:
        rec["as_of"] = as_of
    _LAST_SOURCE[name] = rec
    return syms


def last_source(name: str) -> dict | None:
    """How `name` was resolved on its last fetch, or None if never fetched.

    Returns ``{"source": str, "n": int, "age_days": float | None}`` where
    source is one of: ``cache`` (fresh, within TTL), ``wikipedia``,
    ``datahub``, ``stale-cache`` (expired but real), ``curated`` (WRONG
    universe — last-resort only), ``empty``; and for the iShares lists
    ``ishares-network`` (live holdings CSV), ``ishares-snapshot`` (the
    committed fallback file — the live fetch FAILED) and ``ishares-local``
    (an IWM export dropped on disk). iShares records also carry ``as_of``.
    """
    rec = _LAST_SOURCE.get(name)
    return dict(rec) if rec else None


def is_stale(name: str) -> bool:
    """True when `name` last resolved to an expired cache — a real index
    snapshot, but one that has stopped tracking membership changes."""
    rec = _LAST_SOURCE.get(name)
    return bool(rec and rec["source"] == "stale-cache")


# --- constituent-count sanity gates -----------------------------------------
# A parse that silently returns 12 names (table shape changed, column renamed,
# an interstitial page that happens to contain a table) must NOT be cached and
# must NOT be served as "the S&P 500". Falling through to a stale-but-real
# snapshot is strictly better than scanning a truncated list. Bounds are wide
# enough to survive normal index drift — the S&P 500 carries ~503 share
# classes (a few issuers have two), the S&P 400 ~400.
# Sane size band per list. Ajay 2026-08-16: "add a count checks for returned
# values for all the tickers API like Russel 3000 and S&P 500 as well."
#
# Every band below is anchored on a MEASURED count taken 2026-08-16 (shown in
# the comment), widened to absorb legitimate index churn and dual-class adds.
# A list that lands outside its band is not a smaller universe — it is a parse
# that silently changed meaning, which is exactly how the scan came to run on
# 158 names while reporting "S&P 1500".
_EXPECTED_COUNTS: dict[str, tuple[int, int]] = {
    "sp500": (450, 530),          # measured 503
    "sp400": (350, 430),          # measured 400
    "sp600": (540, 650),          # measured 603
    # The Nasdaq-100 holds 100 companies but slightly more SYMBOLS, because a
    # few constituents have two share classes in the index (GOOG/GOOGL,
    # FOX/FOXA). Range, not equality, so a legitimate dual-class add does not
    # look like a parse failure.
    "nasdaq100": (95, 115),       # measured 102
    # Every Nasdaq PRIMARY listing among active US common stocks. Wide band:
    # this tracks real listings and delistings, and the whole point of the
    # guard is to catch the exchange filter silently matching nothing (0) or
    # nothing at all (the full 5,300 major-exchange list leaking through).
    "nasdaq_listed": (1500, 4500),
    "sp1500": (1350, 1700),       # measured 1506 (500+400+600 layered)
    "russell1000": (900, 1150),   # measured 1001
    # Deliberately floored ABOVE the ~1030-name clean fallback (curated ∪ sp500
    # ∪ sp400). If the iShares file is missing we fall back to a list that is a
    # perfectly good universe but is NOT the Russell 3000 — and the whole point
    # of this band is to say so out loud rather than mislabel it.
    "russell3000": (1800, 3200),  # measured 2559
    # microcap is an optional layer (IWC holdings file); absent is legitimate,
    # so there is no lower bound HERE — only an upper one to catch a bad parse.
    # A truncated LIVE parse is caught instead by the snapshot-anchored floor
    # ISHARES_LIVE_MIN_SNAPSHOT_FRACTION in `_resolve_ishares` (2026-09-29).
    "microcap": (0, 2500),        # measured 1278 (live 2026-09-28: 1,353)
    "etf": (150, 600),            # measured 373
    "themes": (20, 300),          # measured 298 (2026-09-28), hand-curated
    # ZERO IS LEGITIMATE here and nowhere else in this table: on day one nothing
    # has been curated in from the tracked traders, and the default band starts
    # at 1 — which would fail an empty list and log it as a broken parse. The
    # upper bound is the real guard: it catches a curator regression that starts
    # yielding names by the hundred (traders/curate.py caps a single run at 12).
    "traders": (0, 200),
    # Same reasoning for the promo-circuit curation lane (2026-09-21): zero is
    # the legitimate starting state, and the upper bound is the real guard.
    # Steady state is MAX_ADDS_PER_RUN (12) x the 14-day candidate window = 168.
    "promo": (0, 200),
    "broad": (1800, 6000),        # measured 3707
    "massive": (3000, 7000),      # ~5300 per the fetcher's own docstring
}

# Last observed size per list, for the health check. name -> dict.
LAST_COUNTS: dict[str, dict] = {}


def _count_ok(name: str, syms: list[str]) -> bool:
    lo, hi = _EXPECTED_COUNTS.get(name, (1, 10**9))
    if lo <= len(syms) <= hi:
        return True
    log.warning("universe: %s parse returned %d names, outside the sane range "
                "%d-%d — rejecting this source", name, len(syms), lo, hi)
    return False


def _record_count(name: str, syms: list[str]) -> list[str]:
    """Observe a fetcher's result size. Returns `syms` unchanged.

    Distinct from `_count_ok`, which REJECTS a source mid-fallback-chain. This
    one runs at the boundary, where rejecting would leave the caller with
    nothing — so it logs loudly and records for `universe_counts()` instead.
    """
    n = len(syms or [])
    lo, hi = _EXPECTED_COUNTS.get(name, (1, 10**9))
    ok = lo <= n <= hi
    LAST_COUNTS[name] = {"count": n, "expected": [lo, hi], "ok": ok}
    if not ok:
        log.error("universe: %s returned %d names, OUTSIDE the sane range %d-%d "
                  "— the scan is running on the wrong universe", name, n, lo, hi)
    return syms


def _count_guarded(name: str, fn):
    """Wrap a public fetcher so every return path is size-checked at source.

    Applied by name after the definitions rather than at each `return`: these
    fetchers have up to six exit points each (cache hit, local file, network,
    mirror, stale cache, clean fallback) and guarding one of them is how the
    fallback paths escaped the check in the first place.
    """
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        return _record_count(name, fn(*args, **kwargs))
    return inner


def universe_counts(names: list[str] | None = None) -> dict:
    """Call each list fetcher and report its size against its sane band.

    Used by the health audit and safe to call ad hoc — every fetcher is disk
    cached for 30 days, so this is cheap after the first pass.
    """
    import collections
    fetchers: "collections.OrderedDict[str, object]" = collections.OrderedDict((
        ("sp500", fetch_sp500), ("sp400", fetch_sp400), ("sp600", fetch_sp600),
        ("nasdaq100", fetch_nasdaq100), ("sp1500", fetch_sp1500),
        ("russell1000", fetch_russell1000), ("russell3000", fetch_russell3000),
        ("microcap", fetch_microcap), ("etf", fetch_etf_universe),
        ("themes", fetch_themes), ("broad", fetch_broad),
        ("traders", fetch_trader_adds), ("promo", fetch_promo_adds),
    ))
    out: dict = {}
    for name, fn in fetchers.items():
        if names and name not in names:
            continue
        lo, hi = _EXPECTED_COUNTS.get(name, (1, 10**9))
        try:
            n = len(fn())
            out[name] = {"count": n, "expected": [lo, hi], "ok": lo <= n <= hi,
                         "age_days": _cache_age_days(name)}
        except Exception as exc:
            out[name] = {"count": None, "expected": [lo, hi], "ok": False,
                         "error": f"{type(exc).__name__}: {exc}"[:160]}
    out["_failing"] = sorted(k for k, v in out.items()
                             if isinstance(v, dict) and not v.get("ok"))
    # iShares provenance (2026-09-29). A list can be the right SIZE and still
    # be months old: it resolved from the committed snapshot because the live
    # holdings CSV failed. Say where each came from, and name every list that
    # is being SERVED from a snapshot older than ISHARES_SNAPSHOT_STALE_DAYS.
    #
    # Round 2: `_snapshot_served` names EVERY list the snapshot served, at any
    # age — a served snapshot means the live fetch failed, which the health
    # audit reports with the holdings date. `_stale` stays the stricter subset.
    stale: list[str] = []
    served: list[str] = []
    try:
        snaps = ishares_snapshot_status()
    except Exception:                                   # noqa: BLE001
        snaps = {}
    for name, snap in snaps.items():
        entry = out.get(name)
        if not isinstance(entry, dict):
            continue
        rec = last_source(name) or {}
        entry["source"] = rec.get("source")
        entry["as_of"] = rec.get("as_of")
        entry["snapshot"] = snap
        if snap.get("served"):
            served.append(name)
            if snap.get("stale"):
                stale.append(name)
    out["_stale"] = sorted(stale)
    out["_snapshot_served"] = sorted(served)
    return out


def _dedup_symbols(raw) -> list[str]:
    """Uppercase, dot→dash (BRK.B → BRK-B), drop blanks/NaN, dedup in order."""
    seen, out = set(), []
    for s in raw:
        sym = str(s).strip().replace(".", "-").upper()
        if not sym or sym == "NAN" or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


# Independent-transport mirror of the same S&P 500 constituent table, served
# as a plain CSV from GitHub raw by the `datasets` org. Honest caveat: this is
# DERIVED from the same Wikipedia table, so it is not an independent *source
# of truth* — but it is an independent *delivery path*, which is precisely the
# failure mode that took Wikipedia out (UA filtering at the edge). If
# Wikipedia blocks or reshapes its table again, this keeps the list fresh.
_DATAHUB_SP500_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
    "main/data/constituents.csv"
)


def _sp500_from_wikipedia() -> list[str]:
    tables = _read_html_ua("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    return _dedup_symbols(tables[0]["Symbol"].tolist())


def _sp500_from_datahub() -> list[str]:
    import csv
    import io
    rows = csv.DictReader(io.StringIO(_fetch_text(_DATAHUB_SP500_URL)))
    return _dedup_symbols(r.get("Symbol", "") for r in rows)


def _sp400_from_wikipedia() -> list[str]:
    tables = _read_html_ua("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies")
    # The constituents table isn't always tables[0] on this page — find the
    # one that actually has a Symbol/Ticker column.
    for tb in tables:
        col = next((c for c in tb.columns
                    if str(c).lower() in ("symbol", "ticker")), None)
        if col is not None:
            return _dedup_symbols(tb[col].tolist())
    return []


def _sp600_from_wikipedia() -> list[str]:
    tables = _read_html_ua("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies")
    for tb in tables:
        col = next((c for c in tb.columns
                    if str(c).lower() in ("symbol", "ticker")), None)
        if col is not None:
            return _dedup_symbols(tb[col].tolist())
    return []


def _resolve_index(name: str, loaders: list[tuple[str, object]],
                   *, on_exhausted: str) -> list[str]:
    """Shared resolve ladder for the S&P constituent lists.

        fresh cache → each live loader in order → stale cache → last resort

    A live loader only wins if it parses AND passes the count sanity gate;
    otherwise we keep walking. Every outcome is recorded via `_record` so
    callers can see whether they got the real, fresh index or a fallback.

    `on_exhausted` is "curated" (return the curated list — WRONG universe,
    sp500's historical behaviour, kept only so a scan still runs) or "empty".
    """
    cached = _read_cached(name)
    if cached:
        return _record(name, "cache", cached, age_days=_cache_age_days(name))

    failures: list[str] = []
    for label, loader in loaders:
        try:
            out = loader()
        except Exception as exc:
            failures.append(f"{label}: {exc}")
            continue
        if out and _count_ok(name, out):
            _write_cached(name, out)
            log.info("universe: fetched %d %s components from %s",
                     len(out), name, label)
            return _record(name, label, out, age_days=0.0)
        failures.append(f"{label}: rejected ({len(out)} names)")

    why = "; ".join(failures) or "no loaders"
    stale = _read_cached_stale(name)
    if stale:
        age = _cache_age_days(name) or 0.0
        log.warning("universe: %s live fetch failed (%s) — using STALE cached "
                    "list (%d names, %.0fd old)", name, why, len(stale), age)
        return _record(name, "stale-cache", stale, age_days=age)

    if on_exhausted == "curated":
        log.warning("universe: %s fetch failed (%s) and no cache exists — "
                    "falling back to the CURATED list, which is NOT %s",
                    name, why, name)
        return _record(name, "curated", list(UNIVERSE))
    log.warning("universe: %s fetch failed (%s) and no cache exists — "
                "skipping this layer", name, why)
    return _record(name, "empty", [])


def fetch_sp500() -> list[str]:
    """Return S&P 500 components, cached 30 days.

    Resolve order: fresh cache → Wikipedia → datahub CSV mirror → stale
    cache → curated.

    WIKIPEDIA 403 (2026-08-13): Wikipedia rejects the default urllib UA that
    `pandas.read_html(url)` sends, so the live fetch failed on every call and
    the cache aged out. The fix is `_read_html_ua` — fetch with requests + a
    descriptive User-Agent, then parse. Verified in-container: default UA
    403s, descriptive UA returns the full article.

    Two layers of protection remain behind that, because a scan that claims
    "S&P 500" while holding some other list is wrong data, not degraded data:

      - `datahub` is a second delivery path for the same table (GitHub raw
        CSV), so a repeat of the UA block doesn't re-freeze the list.
      - the STALE cache beats the curated list. Index membership turns over
        only a few names a quarter, so an expired snapshot is ~99% right,
        while the 158-name curated list is a different universe entirely
        (mega-caps + momentum movers). Curated is the true last resort and
        is reported as such via `last_source("sp500")`.
    """
    return _resolve_index(
        "sp500",
        [("wikipedia", _sp500_from_wikipedia), ("datahub", _sp500_from_datahub)],
        on_exhausted="curated",
    )


def fetch_sp400() -> list[str]:
    """Return S&P 400 MidCap components, cached 30 days.

    Mirror of fetch_sp500 against Wikipedia's S&P 400 list, and it hit the
    same 403 (sp400.txt had aged to 76 days alongside sp500.txt) — so it goes
    through the same UA'd fetch.

    These names are almost all already inside the Russell 3000, so this is
    belt-and-suspenders coverage. It falls back to the stale cache but NEVER
    to curated: returning large-caps here would pollute the mid-cap layer of
    a union, so the last resort is [].
    """
    return _resolve_index(
        "sp400",
        [("wikipedia", _sp400_from_wikipedia)],
        on_exhausted="empty",
    )


def fetch_sp600() -> list[str]:
    """Return S&P 600 SmallCap components, cached 30 days.

    Added 2026-08-13 (Ajay: "expand the scan to best companies beyond S and p
    500 increase in to 1000 others"). S&P 400 + S&P 600 together are ~1,000
    names OUTSIDE the S&P 500, and unlike a raw Russell slice they clear S&P's
    index-committee bar — including a positive-earnings requirement — so
    "best companies beyond the S&P 500" is a fair description of them.

    Same ladder and the same never-fall-back-to-curated rule as sp400: a
    large-cap list leaking into the small-cap layer would corrupt any union.
    """
    return _resolve_index(
        "sp600",
        [("wikipedia", _sp600_from_wikipedia)],
        on_exhausted="empty",
    )


def _nasdaq100_from_wikipedia() -> list[str]:
    """Nasdaq-100 constituents.

    NOTE the URL: the components table lives on the SEPARATE
    "List_of_NASDAQ-100_companies" page, not on the "Nasdaq-100" article — that
    one now carries only index history (milestones, yearly closes) and links
    out. Verified 2026-08-16: the article yields 0 tickers, the list page
    yields 102 across columns Ticker / Company / ICB Industry / ICB Subsector.

    The components table is identified by carrying BOTH a ticker column and a
    company/industry column, which the navbox and history tables do not.
    """
    tables = _read_html_ua("https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies")
    best: list[str] = []
    for tb in tables:
        cols = {str(c).lower() for c in tb.columns}
        tick = next((c for c in tb.columns
                     if str(c).lower() in ("symbol", "ticker")), None)
        if tick is None:
            continue
        if not any(k in c for c in cols
                   for k in ("company", "name", "industry", "sector")):
            continue
        syms = _dedup_symbols(tb[tick].tolist())
        if len(syms) > len(best):
            best = syms
    return best


def fetch_nasdaq100() -> list[str]:
    """Nasdaq-100 — the large-cap non-financial Nasdaq names.

    Added 2026-08-16 (Ajay: "Latest tickers as they change like getting added
    to SP 500 or Russel 3000 and Nasdaq"). Nasdaq was the one index family the
    app tracked nowhere: the S&P ladders cover the NYSE/Nasdaq blend by market
    cap and the Russell lists are broad-market, but neither tells you when a
    name JOINS the Nasdaq-100 — which is its own liquidity and flow event.

    Never falls back to curated: a large-cap growth list leaking in as
    "Nasdaq-100" would corrupt any membership diff built on top of it.
    """
    return _resolve_index(
        "nasdaq100",
        [("wikipedia", _nasdaq100_from_wikipedia)],
        on_exhausted="empty",
    )


def fetch_sp1500() -> list[str]:
    """S&P Composite 1500 = S&P 500 + S&P 400 MidCap + S&P 600 SmallCap.

    Deduped, order-stable (large -> mid -> small). Layers that fail resolve to
    [] rather than to curated, so a partial outage shrinks the universe instead
    of silently mixing in the wrong names — `last_source` reports each layer.
    """
    out: list[str] = []
    seen: set[str] = set()
    for part in (fetch_sp500(), fetch_sp400(), fetch_sp600()):
        for sym in part:
            if sym and sym not in seen:
                seen.add(sym)
                out.append(sym)
    return out


# ============================================================================
# iShares CSV cleanup (added 2026-05-21)
# ----------------------------------------------------------------------------
# Two recurring sources of garbage in the raw iShares IWB CSV that the
# original ticker-shape regex didn't catch:
#
# 1. Class-share tickers come through with NO separator. iShares writes
#    "BRKB" (not "BRK.B" or "BRK-B"). yfinance only accepts "BRK-B" — so
#    these silently 404'd until we mapped them explicitly. The map below
#    covers every Russell 1000 / S&P 500 multi-class issuer as of 2026-05;
#    add new entries when iShares adds new dual-class IPOs.
#
# 2. Futures contracts used by the ETF for cash management — "ESM6"
#    (S&P 500 E-mini June 2026), "FAM6", "UBFUT", "XTSLA", etc. pass the
#    basic ticker regex but aren't equities. They're held inside the ETF
#    as cash-equivalent collateral, not as real holdings. Filter via
#    explicit blocklist + a futures-contract regex (single letter month
#    code H/M/U/Z + single digit year). Both layers — blocklist catches
#    named oddities, regex catches the next-year-future variants without
#    a code change.
# ============================================================================

# Real ticker → yfinance ticker remap for class-share names. Keys are the
# raw symbols iShares emits; values are the yfinance-accepted form.
_CLASS_SHARE_REMAP: dict[str, str] = {
    "BRKA":   "BRK-A",   # Berkshire Hathaway A
    "BRKB":   "BRK-B",   # Berkshire Hathaway B
    "BFA":    "BF-A",    # Brown-Forman A
    "BFB":    "BF-B",    # Brown-Forman B
    "CWENA":  "CWEN-A",  # Clearway Energy A
    "HEIA":   "HEI-A",   # HEICO A
    "LENB":   "LEN-B",   # Lennar B
    "UHALB":  "UHAL-B",  # U-Haul B
    "MOGA":   "MOG-A",   # Moog A
    "GEFB":   "GEF-B",   # Greif B
    "CRDA":   "CRD-A",   # Crawford A
    "CRDB":   "CRD-B",   # Crawford B
    "FCNCA":  "FCNCA",   # First Citizens — yfinance accepts as-is
    "JWA":    "JW-A",    # John Wiley A
    "JWB":    "JW-B",    # John Wiley B
    "RUSHA":  "RUSHA",   # Rush Enterprises A — yfinance accepts as-is
    "RUSHB":  "RUSHB",   # Rush Enterprises B — yfinance accepts as-is
}

# Hardcoded blocklist of non-equity symbols seen leaking through. These
# are futures contracts / ETF internal accounting placeholders that
# happen to have valid-looking ticker shapes. Lowercase comparison; we
# normalize incoming symbols to upper.
_NON_EQUITY_BLOCKLIST: set[str] = {
    "XTSLA",     # iShares internal Tesla proxy / not a real ticker
    "UBFUT",     # Ultra T-Bond futures collateral
    "MGEH",      # Common iShares cash-equivalent placeholder
    # Futures contracts seen in Q2 2026:
    "ESM6", "ESU6", "ESZ6", "ESH7",   # S&P 500 E-mini contracts
    "FAM6", "FAU6", "FAZ6",            # Russell 2000 mini futures
    "NQM6", "NQU6",                    # Nasdaq 100 E-mini
    "VXM6", "VXU6",                    # VIX futures
    "USD", "EUR", "JPY", "GBP",        # FX placeholders
    "MARGIN_USD", "CASH",              # iShares accounting rows
}

# Futures-contract pattern: ROOT (2-4 letters) + MONTH (H/M/U/Z) + YEAR (1 digit).
# Catches ESM6, FAM6, NQU7, etc. without needing a code update each year.
# Real equity tickers don't follow this pattern (only edge case: companies
# whose ticker ends in [HMUZ][0-9], which doesn't currently exist in Russell
# 1000 — checked 2026-05-21).
import re as _re
_FUTURES_PATTERN = _re.compile(r"^[A-Z]{1,3}[HMUZ][0-9]$")
# A class share written with a space, as the live iShares CSV does: "BRK B".
_CLASS_SHARE_SPACE = _re.compile(r"^[A-Z]{1,5} [A-Z]$")


def _normalize_ishares_ticker(raw: str) -> str | None:
    """Convert an iShares-emitted ticker to the yfinance form, or None
    if the symbol should be excluded from the equity universe.

    Order of operations:
      1. Drop known non-equity placeholders (XTSLA, UBFUT, CASH, etc.).
      2. Drop futures-contract patterns (ESM6, NQU7, etc.).
      3. Apply class-share remap (BRKB → BRK-B, BFA → BF-A, etc.).
      4. Convert any legacy dot notation (BRK.B → BRK-B).
      5. Final shape check — only allow ticker-like strings through.
    """
    s = (raw or "").strip().upper()
    if not s or s in {"-", "CASH"}:
        return None
    if s in _NON_EQUITY_BLOCKLIST:
        return None
    if _FUTURES_PATTERN.match(s):
        return None
    # 2026-09-29: the live latest-holdings.csv writes class shares with a
    # SPACE ("BRK B", "HEI A", "UHAL B") where the old export wrote "BRKB".
    # The shape check below rejected the space silently — HEI-A ($69M/day),
    # BF-A, GEF-B, LEN-B and UHAL-B would have left `full`. The joined form
    # goes through the SAME remap table first (so "RUSH A" would stay RUSHA,
    # as the curated entry says); anything else becomes the dash form.
    if _CLASS_SHARE_SPACE.match(s):
        joined = s.replace(" ", "")
        if joined in _CLASS_SHARE_REMAP:
            return _CLASS_SHARE_REMAP[joined]
        return s.replace(" ", "-")
    # Class-share remap takes precedence over dot-to-dash because
    # iShares typically emits the joined form (BRKB) not the dotted form.
    if s in _CLASS_SHARE_REMAP:
        return _CLASS_SHARE_REMAP[s]
    if "." in s:
        s = s.replace(".", "-")
    # Final shape check.
    if not _re.match(r"^[A-Z][A-Z0-9\-]{0,9}$", s):
        return None
    return s


# MIC codes. XNAS is Nasdaq's primary-listing code — the thing that makes a
# stock "a Nasdaq stock" rather than merely quoted there.
MIC_NASDAQ = "XNAS"
MAJOR_EXCHANGES = frozenset({"XNYS", "XNAS", "ARCX", "BATS", "XASE"})


def fetch_massive_universe(limit: int | None = None,
                           keep_exchanges: frozenset = MAJOR_EXCHANGES,
                           cache_name: str = "massive_universe") -> list[str]:
    """Return all active US common stocks via Massive's reference endpoint.

    Used as a fallback when iShares blocks CSV downloads (their site
    sporadically serves HTML instead of CSV for IWB/IWV ETF holdings).
    Cached 30 days under 'massive_universe.txt'. Paginates through the
    /v3/reference/tickers endpoint until exhausted — typically 5-6 pages
    for ~5,300 active common stocks.

    Args:
        limit: optional cap on number of tickers returned (preserves
               alphabetical order from Massive). None returns the full list.
    """
    cached = _read_cached(cache_name)
    if cached:
        return cached[:limit] if limit else cached

    api_key = stocks_key()
    if not api_key:
        log.warning("universe: MASSIVE_API_KEY not set; cannot fetch Massive universe")
        return []
    try:
        import requests
    except ImportError:
        return []

    all_tickers: list[str] = []
    url = "https://api.massive.com/v3/reference/tickers"
    params: dict = {
        "market":  "stocks",
        "type":    "CS",       # Common Stock — drop preferreds, units, warrants
        "active":  "true",
        "limit":   1000,
        "apiKey":  api_key,
    }
    page = 1
    next_url = url
    next_params = params
    try:
        while next_url and page <= 10:  # safety: cap at 10 pages = 10,000 tickers
            r = requests.get(
                next_url,
                params=next_params if page == 1 else {"apiKey": api_key},
                timeout=20,
            )
            if r.status_code != 200:
                log.warning("universe: Massive tickers page %d returned HTTP %s",
                            page, r.status_code)
                break
            data = r.json()
            for entry in (data.get("results") or []):
                t = (entry.get("ticker") or "").upper().strip()
                if not t:
                    continue
                # Filter weird-shape tickers (units, warrants leak through with
                # suffixes like ABC.U, ABC.W). Allow [A-Z][A-Z0-9-]{0,9}.
                if not _re.match(r"^[A-Z][A-Z0-9\-]{0,9}$", t):
                    continue
                # Keep only the requested exchanges; drop OTC/PINK.
                exch = (entry.get("primary_exchange") or "").upper()
                if exch and exch not in keep_exchanges:
                    continue
                # A blank primary_exchange cannot be proven to be on the
                # requested venue, so a SPECIFIC request drops it while the
                # broad "major exchanges" request keeps it — unchanged
                # behaviour for every existing caller.
                if not exch and keep_exchanges != MAJOR_EXCHANGES:
                    continue
                all_tickers.append(t)
            next_url = data.get("next_url")
            page += 1
        # Dedup preserving order
        seen, out = set(), []
        for t in all_tickers:
            if t not in seen:
                seen.add(t)
                out.append(t)
        if not out:
            return []
        _write_cached(cache_name, out)
        log.info("universe: %s cached — %d active US common stocks", cache_name, len(out))
        return out[:limit] if limit else out
    except Exception as exc:
        log.warning("universe: Massive universe fetch failed (%s)", exc)
        return []


# --- iShares holdings: live CSV first, committed snapshot second ---------
#
# HISTORY. 2026-05-29: the old `1467271812596.ajax?fileType=csv` endpoint
# started serving HTML, so Ajay downloaded the "Download Holdings" .xls
# exports by hand and they became the PRIMARY source. Nobody refreshed them:
# on 2026-09-29 `full` was still built from "Fund Holdings as of May 28, 2026"
# — before the June 26 reconstitution and the Sep 21 Q3 IPO adds — and the
# weekly `universe_changes` job re-read the same file and reported "no change"
# every Sunday.
#
# 2026-09-29 (diagnosed read-only in the api container): iShares redesigned
# its product pages. The old ajax URL answers HTTP 200 `text/csv` with 1.45 MB
# of product-page HTML (not a TLS / Cloudflare block — curl_cffi Chrome
# impersonation gets the same HTML). The page now links
# `/us/products/<id>/<slug>/latest-holdings.csv`, which returns the real CSV
# to plain `requests` with our UA: a ~9-line metadata block, then the
# `Ticker,Name,Sector,Asset Class,...,Price,Location,Exchange,...` table.
#
# So the order is now:
#   1. live `latest-holdings.csv`                     -> ``ishares-network``
#   2. the committed snapshot in ``backend/sepa/data`` -> ``ishares-snapshot``
#      (a WARNING when the live fetch fails; a second WARNING past
#      ISHARES_SNAPSHOT_STALE_DAYS; `universe_counts()["_snapshot_served"]`
#      names it at ANY age for the health audit — no silent staleness)
#   3. the old clean fallback (curated ∪ S&P 500 ∪ S&P 400), or [] for microcap
# The snapshot is NOT written to the 30-day disk cache: a cached snapshot would
# read back as plain ``cache`` and hide that the live fetch failed, and it
# would keep serving the fallback for a month after iShares recovers.
# Round 2 (2026-09-29): a failed live fetch is memoised for
# ISHARES_LIVE_FAILURE_MEMO_SEC (the outage is one download per hour, not per
# call); the cache files are versioned (`_CACHE_KEY_VERSIONS`) and carry the
# holdings date in a sidecar, so a cache hit keeps its `as_of`.

_DATA_DIR = Path(__file__).parent / "data"
# Committed snapshots of the live CSV (same format the network path parses).
# Refreshed 2026-09-29 from "Fund Holdings as of Sep 28, 2026". Re-save them
# from the same URL (ISHARES_HOLDINGS_URL) whenever the health audit says a
# snapshot is being served and is stale.
_LOCAL_IWB_PATH = _DATA_DIR / "iShares-Russell-1000-ETF_holdings.csv"
_LOCAL_IWV_PATH = _DATA_DIR / "iShares-Russell-3000-ETF_holdings.csv"
# Micro-cap extension ("beyond Russell 3000", user 2026-05-30). The Russell
# 3000 ≈ Russell 1000 + Russell 2000, so true small/micro names below it come
# from the iShares Micro-Cap ETF (IWC) holdings. Optional — if neither the live
# CSV nor the file is available, the micro-cap layer is just skipped (the
# broad mode still returns R3000 ∪ ETFs).
_LOCAL_IWC_PATH = _DATA_DIR / "iShares-Micro-Cap-ETF_holdings.csv"
# The Russell 2000 (IWM). Ajay 2026-09-18: "Yes add it." ABSENT today — until
# he drops the "Download Holdings" export here, `fetch_russell2000` derives the
# list from FTSE's own definition (Russell 3000 minus Russell 1000) and says
# so on every surface. See `russell2000_coverage`. A live IWM fetch is now
# possible (same URL shape) but is NOT wired: that is a construction change of
# the Russell 2000 list and his call.
_LOCAL_IWM_PATH = _DATA_DIR / "iShares-Russell-2000-ETF_fund.xls"

# The live holdings link, per fund. Verified 2026-09-29 for IWB, IWV, IWC
# (and IWM 239710 / ishares-russell-2000-etf, not wired).
ISHARES_HOLDINGS_URL = ("https://www.ishares.com/us/products/{pid}/{slug}/"
                        "latest-holdings.csv")
_ISHARES_FUNDS: dict[str, tuple[str, str, str]] = {
    # list name     (fund, product id, slug)
    "russell1000": ("IWB", "239707", "ishares-russell-1000-etf"),
    "russell3000": ("IWV", "239714", "ishares-russell-3000-etf"),
    "microcap":    ("IWC", "239716", "ishares-microcap-etf"),
}

# Provenance labels for the iShares ladder, so `last_source()` can tell a real
# export from a derivation. Named constants, never retyped strings — the
# change-log's source-flip re-baseline (sepa/universe_changes.refresh_one)
# compares them.
SRC_ISHARES_LOCAL = "ishares-local"
SRC_ISHARES_NETWORK = "ishares-network"
# The committed snapshot, served because the live fetch failed. NOT live data:
# universe_changes refuses to diff it (it would compare a file against itself).
SRC_ISHARES_SNAPSHOT = "ishares-snapshot"
SRC_DERIVED_R2000 = "derived-r3000-minus-r1000"

# How old a served snapshot may be before it is called STALE. Not a new
# number: it is the 120-day age warning the old local-xls loader already
# carried ("refresh from iShares.com 'Download Holdings'"), now named.
ISHARES_SNAPSHOT_STALE_DAYS = 120

# 2026-09-29 (round 2) — an iShares OUTAGE must not re-download on every
# `load_universe` call. A failed (or rejected) live fetch is remembered per
# fund for this long; until it expires the ladder goes straight to the
# snapshot. One hour, as the fix round specified. universe_changes' forced
# weekly refresh clears it (`forget_ishares_memos`) so that job always asks.
ISHARES_LIVE_FAILURE_MEMO_SEC = 60 * 60

# 2026-09-29 (round 2) — a live parse SMALLER than this share of the committed
# snapshot's own count is a truncated download, not a smaller fund, and is
# rejected for the snapshot. Anchored on the snapshot so it needs no absolute
# number; it is the only lower bound microcap has (its `_EXPECTED_COUNTS`
# floor is 0 because an absent layer is legitimate). 60% as the fix round
# specified. Applied to all three iShares lists: for russell1000/3000 their
# static floors (900 / 1800) are already higher, so it never loosens them.
ISHARES_LIVE_MIN_SNAPSHOT_FRACTION = 0.60

# The fund's OWN categorical marks for a residual line that is not a tradeable
# listing: HOLX "NO MARKET (E.G. UNLISTED)" at $0.01, VUECF / P5N994
# "Non-Nms Quotation Service". Prefix match, upper-cased. Together with a
# Price of exactly 0 (THRD, SBT, PDLI, GTXI) this drops the dead rows iShares
# still lists as Equity — no threshold involved.
_ISHARES_RESIDUAL_EXCHANGE_PREFIXES = ("NO MARKET", "NON-NMS")

# SpreadsheetML 2003 namespace — iShares' old Holdings.xls export uses this.
_SS_NS = "{urn:schemas-microsoft-com:office:spreadsheet}"

_AS_OF_FORMATS = ("%b %d, %Y", "%m/%d/%Y", "%d-%b-%Y", "%Y-%m-%d", "%B %d, %Y")


def _parse_as_of(raw: str) -> str | None:
    """'Sep 28, 2026' / '05/28/2026' / … -> '2026-09-28', else None."""
    from datetime import datetime as _dt
    s = (raw or "").strip().strip('"').strip()
    for fmt in _AS_OF_FORMATS:
        try:
            return _dt.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _ishares_csv_records(text: str, *, source_label: str) -> tuple[list[dict], str | None]:
    """Split an iShares holdings CSV into row dicts + its "as of" date.

    Works on the live `latest-holdings.csv` and on the pre-2026 ajax CSV: both
    carry a metadata block of drifting length above a header row whose first
    field is ``Ticker``. Raises RuntimeError on anything else — notably the
    HTML product page the old URL now returns with a `text/csv` header.
    """
    import csv
    import io
    if not text or not text.strip():
        raise RuntimeError(f"{source_label}: iShares CSV is empty")
    lines = text.lstrip("﻿").splitlines()
    as_of = None
    header_idx = None
    for i, ln in enumerate(lines[:50]):
        stripped = ln.lstrip()
        if as_of is None and stripped.lower().startswith(("fund holdings as of",
                                                           '"fund holdings as of')):
            parts = next(csv.reader([stripped]), [])
            if len(parts) > 1:
                as_of = _parse_as_of(parts[1])
        # Header row has "Ticker" as first field (with or without quotes).
        if stripped.startswith(("Ticker,", '"Ticker"')):
            header_idx = i
            break
    if header_idx is None:
        head = (lines[0] if lines else "")[:60]
        raise RuntimeError(f"iShares CSV: header row with 'Ticker' not found "
                           f"({source_label}; first line {head!r})")
    records = [dict(r) for r in csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))]
    return records, as_of


def _ishares_xls_records(path: Path, *, source_label: str) -> tuple[list[dict], str | None]:
    """Row dicts + as-of date from an old "Download Holdings" .xls
    (SpreadsheetML XML). Raises RuntimeError on a parse failure."""
    from lxml import etree
    # iShares files have occasional malformed bits; recover=True
    # lets lxml skip them rather than aborting the whole parse.
    parser = etree.XMLParser(recover=True)
    tree = etree.parse(str(path), parser)
    root = tree.getroot()

    holdings_ws = None
    for ws in root.findall(f"{_SS_NS}Worksheet"):
        if ws.get(f"{_SS_NS}Name") == "Holdings":
            holdings_ws = ws
            break
    if holdings_ws is None:
        raise RuntimeError(f"{source_label}: 'Holdings' worksheet not found in {path.name}")

    rows = holdings_ws.findall(f".//{_SS_NS}Row")

    def _cell_strings(row) -> list[str]:
        out = []
        for cell in row.findall(f"{_SS_NS}Cell"):
            data = cell.find(f"{_SS_NS}Data")
            out.append(data.text if data is not None and data.text else "")
        return out

    # iShares puts ~7 rows of fund metadata above the header; that count
    # drifts so detect, don't hardcode.
    as_of = None
    header = None
    header_idx = None
    for i, r in enumerate(rows[:50]):
        cells = _cell_strings(r)
        if cells and cells[0].strip().lower() == "fund holdings as of" and len(cells) > 1:
            as_of = _parse_as_of(cells[1])
        if cells and cells[0].strip() == "Ticker":
            header_idx = i
            header = [h.strip() for h in cells]
            break
    if header_idx is None:
        raise RuntimeError(f"{source_label}: header row with 'Ticker' not found in {path.name}")
    records = []
    for r in rows[header_idx + 1:]:
        cells = _cell_strings(r)
        if cells:
            records.append({h: (cells[j] if j < len(cells) else "")
                            for j, h in enumerate(header)})
    return records, as_of


def _clean_ishares_records(records: list[dict], *, source_label: str) -> list[str]:
    """The ONE cleanup both formats go through, so they cannot drift apart
    again (the network branch used to have no Asset Class filter at all).

      1. Asset Class must be Equity (drops Futures / Cash / Money Market).
      2. Drop the fund's residual lines: Exchange starting "NO MARKET" or
         "Non-Nms", or a Price of exactly 0 (dead names iShares still lists).
      3. `_normalize_ishares_ticker` (blocklist, futures, class shares incl.
         the new space form, shape check); dedup in order.
    """
    def _get(rec: dict, name: str) -> str:
        for k, v in rec.items():
            if k is not None and str(k).strip().lower() == name:
                return "" if v is None else str(v).strip()
        return ""

    has = lambda name: any(k is not None and str(k).strip().lower() == name  # noqa: E731
                           for rec in records[:1] for k in rec)
    has_ac, has_px, has_ex = has("asset class"), has("price"), has("exchange")

    n_non_equity_row = n_residual = n_zero_price = 0
    n_dropped_non_equity = n_dropped_shape = n_remapped_class = 0
    seen, out = set(), []
    for rec in records:
        raw = _get(rec, "ticker")
        if not raw:
            continue
        if has_ac:
            ac = _get(rec, "asset class").lower()
            if ac and ac != "equity":
                n_non_equity_row += 1
                continue
        if has_ex:
            ex = _get(rec, "exchange").upper()
            if ex.startswith(_ISHARES_RESIDUAL_EXCHANGE_PREFIXES):
                n_residual += 1
                continue
        if has_px:
            px_raw = _get(rec, "price").replace(",", "")
            try:
                if float(px_raw) == 0.0:
                    n_zero_price += 1
                    continue
            except ValueError:
                pass                       # "-" or blank: not evidence of death
        r_up = raw.strip().upper()
        norm = _normalize_ishares_ticker(raw)
        if norm is None:
            if r_up in _NON_EQUITY_BLOCKLIST or _FUTURES_PATTERN.match(r_up):
                n_dropped_non_equity += 1
            else:
                n_dropped_shape += 1
            continue
        if norm != r_up:
            n_remapped_class += 1
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    log.info(
        "universe: %s iShares holdings cleaned — kept=%d  class_share_remapped=%d  "
        "skipped_non_equity_row=%d  skipped_residual_exchange=%d  "
        "skipped_zero_price=%d  dropped_non_equity_norm=%d  dropped_shape=%d",
        source_label, len(out), n_remapped_class, n_non_equity_row, n_residual,
        n_zero_price, n_dropped_non_equity, n_dropped_shape,
    )
    return out


def _parse_ishares_csv(text: str, *, source_label: str) -> list[str]:
    """Holdings CSV text -> clean equity tickers. Raises on HTML / no rows."""
    records, _as_of = _ishares_csv_records(text, source_label=source_label)
    out = _clean_ishares_records(records, source_label=source_label)
    if not out:
        raise RuntimeError(f"{source_label}: iShares CSV parsed to zero equities")
    return out


def _load_ishares_file(path: Path, *, source_label: str) -> tuple[list[str], str | None]:
    """A holdings file on disk (.csv snapshot or old .xls export) ->
    (clean tickers, as-of ISO date or None).

    Raises FileNotFoundError if the file isn't present, RuntimeError on a
    parse failure.
    """
    if not path.exists():
        raise FileNotFoundError(f"iShares local file missing: {path}")
    if path.suffix.lower() == ".csv":
        records, as_of = _ishares_csv_records(
            path.read_text(encoding="utf-8", errors="replace"),
            source_label=source_label)
    else:
        records, as_of = _ishares_xls_records(path, source_label=source_label)
    out = _clean_ishares_records(records, source_label=source_label)
    age = _snapshot_age_days(path, as_of)
    if age is not None and age > ISHARES_SNAPSHOT_STALE_DAYS:
        log.warning(
            "universe: %s local iShares file %s is STALE — holdings as of %s, "
            "%.0f days old (> %d). Re-save it from %s",
            source_label, path.name, as_of or "unknown (file mtime)", age,
            ISHARES_SNAPSHOT_STALE_DAYS, ISHARES_HOLDINGS_URL,
        )
    return out, as_of


def _load_ishares_local_xls(path: Path, *, source_label: str) -> list[str]:
    """Back-compat wrapper (the IWM drop-in path and its tests): the tickers
    only. Same cleanup as the live CSV."""
    out, _as_of = _load_ishares_file(path, source_label=source_label)
    return out


def ishares_snapshot_as_of(path: Path) -> str | None:
    """The "Fund Holdings as of" date written INSIDE a snapshot file, or None.

    The file's mtime is NOT the holdings date — in the image it is the build
    or checkout time — so staleness is measured from the content first.
    """
    try:
        if not path.exists():
            return None
        if path.suffix.lower() == ".csv":
            head = path.read_text(encoding="utf-8", errors="replace")[:4000]
            import csv
            for ln in head.splitlines()[:50]:
                s = ln.lstrip("﻿").lstrip()
                if s.lower().startswith(("fund holdings as of", '"fund holdings as of')):
                    parts = next(csv.reader([s]), [])
                    return _parse_as_of(parts[1]) if len(parts) > 1 else None
            return None
        _recs, as_of = _ishares_xls_records(path, source_label=path.name)
        return as_of
    except Exception:
        return None


def _days_since(as_of: str | None, today=None) -> float | None:
    """Whole days from an ISO date to `today` (default: the local date)."""
    from datetime import date as _date
    if not as_of:
        return None
    try:
        return float(((today or _date.today()) - _date.fromisoformat(as_of)).days)
    except (TypeError, ValueError):
        return None


def _snapshot_age_days(path: Path, as_of: str | None = None,
                       today=None) -> float | None:
    """Days since the snapshot's holdings date; the file mtime only when the
    file carries no date. None when there is no file."""
    age = _days_since(as_of or ishares_snapshot_as_of(path), today)
    return age if age is not None else _file_age_days(path)


def _fetch_ishares_live(name: str) -> tuple[list[str], str | None]:
    """The live latest-holdings.csv for one tracked fund -> (tickers, as_of).
    Raises on any failure, including the HTML product page."""
    _fund, pid, slug = _ISHARES_FUNDS[name]
    text = _fetch_text(ISHARES_HOLDINGS_URL.format(pid=pid, slug=slug), timeout=20)
    records, as_of = _ishares_csv_records(text, source_label=name)
    out = _clean_ishares_records(records, source_label=name)
    if not out:
        raise RuntimeError(f"{name}: iShares CSV parsed to zero equities")
    return out, as_of


# In-process memos for the iShares ladder (2026-09-29, round 2).
#   _ISHARES_FAILED    (list, cache dir) -> (failed_at, why). The cache dir is
#                      part of the key so a test's tmp cache never inherits a
#                      production failure (and vice versa); in the app it is
#                      constant, so this is "per fund".
#   _ISHARES_RESOLVED  list -> (cache generation, (syms, as_of)). A generation
#                      is the cache file's + sidecar's (path, mtime_ns, size):
#                      a rewrite, an expiry or universe_changes deleting the
#                      file all change it, so a memo can never outlive its file.
#   _ISHARES_SNAPSHOT  list -> (snapshot file generation, (syms, as_of)), so an
#                      outage parses the committed file once, not per call.
_ISHARES_FAILED: dict[tuple[str, str], tuple[float, str]] = {}
_ISHARES_RESOLVED: dict[str, tuple[tuple, tuple]] = {}
_ISHARES_SNAPSHOT: dict[str, tuple[tuple, tuple]] = {}


def _clock() -> float:
    """Wall clock for the failure memo (a seam tests replace)."""
    return time.time()


def _file_generation(path: Path) -> tuple | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return (str(path), st.st_mtime_ns, st.st_size)


def _cache_generation(name: str) -> tuple | None:
    """Identity of `name`'s FRESH cache (list + sidecar), None when there is
    no cache or it is past UNIV_CACHE_TTL_SEC — same rule as `_read_cached`."""
    path = _cache_path(name)
    gen = _file_generation(path)
    if gen is None:
        return None
    if (time.time() - path.stat().st_mtime) >= UNIV_CACHE_TTL_SEC:
        return None
    return gen + (_file_generation(_cache_as_of_path(name)),)


def forget_ishares_memos(name: str | None = None) -> None:
    """Drop the in-process memos for one list (or all). universe_changes calls
    this with its forced refresh: that job exists to ASK the source."""
    for key in list(_ISHARES_FAILED):
        if name is None or key[0] == name:
            _ISHARES_FAILED.pop(key, None)
    for memo in (_ISHARES_RESOLVED, _ISHARES_SNAPSHOT):
        if name is None:
            memo.clear()
        else:
            memo.pop(name, None)


def _load_ishares_snapshot(name: str, snapshot: Path) -> tuple[list[str], str | None]:
    """`_load_ishares_file`, memoised on the file's generation. Raises as it
    does (FileNotFoundError / RuntimeError); a failure is never memoised."""
    gen = _file_generation(snapshot)
    hit = _ISHARES_SNAPSHOT.get(name)
    if gen is not None and hit and hit[0] == gen:
        syms, as_of = hit[1]
        return list(syms), as_of
    out, as_of = _load_ishares_file(snapshot, source_label=name)
    if gen is not None:
        _ISHARES_SNAPSHOT[name] = (gen, (tuple(out), as_of))
    return out, as_of


def _ishares_live_floor(name: str, snapshot: Path) -> int:
    """Smallest live list accepted: ISHARES_LIVE_MIN_SNAPSHOT_FRACTION of the
    snapshot's own count (0 when there is no readable snapshot)."""
    import math
    try:
        snap, _ = _load_ishares_snapshot(name, snapshot)
    except Exception:                                   # noqa: BLE001
        return 0
    return int(math.ceil(ISHARES_LIVE_MIN_SNAPSHOT_FRACTION * len(snap)))


def _resolve_ishares(name: str, snapshot: Path) -> tuple | None:
    """fresh cache -> live CSV -> committed snapshot.

    Returns ``(syms, source, age_days, as_of)`` for the caller to `_record`
    (the provenance call stays visible in each public fetcher), or None when
    all three fail — the caller owns the last resort. A cache hit carries the
    holdings date from its sidecar, so staleness survives the cache.

    A failed or rejected live fetch is remembered for
    ISHARES_LIVE_FAILURE_MEMO_SEC: until then the ladder skips the network and
    serves the snapshot (an outage costs one download per hour, not one per
    `load_universe` call).
    """
    gen = _cache_generation(name)
    if gen is not None:
        hit = _ISHARES_RESOLVED.get(name)
        if hit and hit[0] == gen:
            syms, as_of = hit[1]
            return list(syms), "cache", _cache_age_days(name), as_of
        cached = _read_cached(name)
        if cached:
            as_of = _read_cached_as_of(name)
            _ISHARES_RESOLVED[name] = (gen, (tuple(cached), as_of))
            return cached, "cache", _cache_age_days(name), as_of

    fkey = (name, str(UNIV_CACHE_DIR))
    now = _clock()
    failed = _ISHARES_FAILED.get(fkey)
    memo_hit = bool(failed and (now - failed[0]) < ISHARES_LIVE_FAILURE_MEMO_SEC)
    if memo_hit:
        why = (f"live fetch failed {now - failed[0]:.0f}s ago: {failed[1]} — "
               f"not retried for {ISHARES_LIVE_FAILURE_MEMO_SEC}s")
    else:
        why = ""
        try:
            out, as_of = _fetch_ishares_live(name)
            floor = _ishares_live_floor(name, snapshot)
            if _count_ok(name, out) and len(out) >= floor:
                _write_cached(name, out)
                _write_cached_as_of(name, as_of)
                _ISHARES_FAILED.pop(fkey, None)
                gen2 = _cache_generation(name)
                if gen2 is not None:
                    _ISHARES_RESOLVED[name] = (gen2, (tuple(out), as_of))
                log.info("universe: %s live iShares holdings — %d names, as of %s",
                         name, len(out), as_of)
                age = _days_since(as_of)
                return out, SRC_ISHARES_NETWORK, (age if age is not None else 0.0), as_of
            if len(out) < floor:
                log.warning("universe: %s live iShares list has %d names, under "
                            "%.0f%% of the snapshot's count (floor %d) — a "
                            "truncated download, rejected", name, len(out),
                            ISHARES_LIVE_MIN_SNAPSHOT_FRACTION * 100, floor)
            why = f"rejected ({len(out)} names)"
        except Exception as exc:
            why = str(exc)[:200]
        _ISHARES_FAILED[fkey] = (now, why)

    try:
        out, as_of = _load_ishares_snapshot(name, snapshot)
    except FileNotFoundError:
        log.warning("universe: %s live iShares fetch failed (%s) and the "
                    "snapshot %s is absent", name, why, snapshot.name)
        return None
    except Exception as exc:
        log.warning("universe: %s live iShares fetch failed (%s) and the "
                    "snapshot %s did not parse (%s)", name, why, snapshot.name, exc)
        return None
    if not (out and _count_ok(name, out)):
        return None
    age = _snapshot_age_days(snapshot, as_of)
    # WARNING on the call that actually failed; INFO while the memo holds, so
    # an outage is one loud line per hour, not one per call. The health audit
    # (`universe_counts()["_snapshot_served"]`) still sees every served list.
    log.log(
        logging.INFO if memo_hit else logging.WARNING,
        "universe: %s live iShares fetch failed (%s) — serving the committed "
        "snapshot %s (holdings as of %s, %s days old). NOT cached; the live "
        "list is retried once the %ds failure memo expires", name, why,
        snapshot.name, as_of, "?" if age is None else f"{age:.0f}",
        ISHARES_LIVE_FAILURE_MEMO_SEC,
    )
    return out, SRC_ISHARES_SNAPSHOT, age, as_of


def ishares_snapshot_status(today=None) -> dict:
    """Per iShares list: the committed snapshot's holdings date and age, and
    whether the LAST resolve actually served it. Read by `universe_counts`
    (and so by the health audit). PURE apart from reading the files."""
    out: dict = {}
    for name, path in (("russell1000", _LOCAL_IWB_PATH),
                       ("russell3000", _LOCAL_IWV_PATH),
                       ("microcap", _LOCAL_IWC_PATH)):
        as_of = ishares_snapshot_as_of(path)
        age = _snapshot_age_days(path, as_of, today=today) if path.exists() else None
        served = (last_source(name) or {}).get("source") == SRC_ISHARES_SNAPSHOT
        out[name] = {
            "file": path.name,
            "exists": path.exists(),
            "as_of": as_of,
            "age_days": None if age is None else round(age, 1),
            "stale": bool(age is None or age > ISHARES_SNAPSHOT_STALE_DAYS),
            "stale_after_days": ISHARES_SNAPSHOT_STALE_DAYS,
            "served": served,
        }
    return out


def fetch_nasdaq_listed(limit: int | None = None) -> list[str]:
    """Every active US common stock whose PRIMARY listing is Nasdaq.

    Ajay 2026-08-20: "I want QQQ stocks and SPY stocks and Nasdaq stocks."

    QQQ is the Nasdaq-100 (`fetch_nasdaq100`, 102 symbols) and SPY is the
    S&P 500 (`fetch_sp500`, 503). This is the third thing he asked for and the
    only one that did not already exist: the whole Nasdaq listing.

    It costs no new data source. `primary_exchange` already arrives on every
    row of the Massive reference endpoint and was already being read — it was
    just used to DROP OTC and then thrown away. This keeps `XNAS` instead, so
    the list comes from the same fetch, the same paging and the same cache
    machinery as `fetch_massive_universe`, cached separately.

    PRIMARY listing, deliberately. A stock is "a Nasdaq stock" because Nasdaq
    is where it is listed, not because it can be traded there — nearly
    everything can. Anything looser would return most of the market and the
    word would stop meaning anything.
    """
    return fetch_massive_universe(limit=limit,
                                  keep_exchanges=frozenset({MIC_NASDAQ}),
                                  cache_name="nasdaq_listed")


def _russell_clean_fallback(name: str) -> list[str]:
    """Deterministic, no-404 last resort: curated leaders + S&P 500 (large) +
    S&P 400 (mid). ~1030 strict names from Wikipedia — a good universe that is
    NOT the Russell list, so the caller records it as ``curated`` (and the
    count band says so out loud for russell3000)."""
    try:
        sp500 = fetch_sp500()
        try:
            sp400 = fetch_sp400()
        except Exception:
            sp400 = []
        merged = list(dict.fromkeys(list(UNIVERSE) + sp500 + sp400))
        log.info("universe: %s via curated+sp500+sp400 = %d names", name, len(merged))
        return merged
    except Exception as exc2:
        log.warning("universe: Wikipedia fallback also failed (%s) — using S&P 500 only", exc2)
        return fetch_sp500()


def fetch_russell1000() -> list[str]:
    """Return Russell 1000 components (iShares IWB holdings), cached 30 days.

    Source priority (2026-09-29 — see the section comment above _DATA_DIR):
      1. live ``latest-holdings.csv`` for IWB           -> ``ishares-network``
      2. committed snapshot ``_LOCAL_IWB_PATH``         -> ``ishares-snapshot``
      3. clean fallback: curated ∪ S&P 500 ∪ S&P 400    -> ``curated``
    """
    got = _resolve_ishares("russell1000", _LOCAL_IWB_PATH)
    if got:
        syms, src, age, as_of = got
        return _record("russell1000", src, syms, age_days=age, as_of=as_of)
    log.warning("universe: russell1000 — live list and snapshot both failed; "
                "falling back to curated ∪ S&P 500 ∪ S&P 400 MidCap")
    return _record("russell1000", "curated", _russell_clean_fallback("russell1000"))


def fetch_russell3000() -> list[str]:
    """Return Russell 3000 components (iShares IWV holdings), cached 30 days.

    Same ladder as fetch_russell1000. IWV is a SAMPLED fund (2,587 names on
    2026-09-28 against ~2,992 for IWB ∪ IWM) — widening to IWB ∪ IWM is a
    construction change and HIS call, not done here.
    """
    got = _resolve_ishares("russell3000", _LOCAL_IWV_PATH)
    if got:
        syms, src, age, as_of = got
        return _record("russell3000", src, syms, age_days=age, as_of=as_of)
    log.warning("universe: russell3000 — live list and snapshot both failed; "
                "falling back to curated ∪ S&P 500 ∪ S&P 400 MidCap")
    return _record("russell3000", "curated", _russell_clean_fallback("russell3000"))


def fetch_russell2000() -> list[str]:
    """Russell 2000 by FTSE's own definition: Russell 3000 minus Russell 1000.

    Ajay 2026-09-18: "Yes add it" — he asked for the Russell 2000 alongside the
    1000 and 3000 in the membership tracker.

    Source priority:
      1. ``backend/sepa/data/iShares-Russell-2000-ETF_fund.xls`` (IWM) — the
         REAL list, the same manually-downloaded SpreadsheetML export the IWB
         and IWV paths read. Absent today. -> source ``ishares-local``.
      2. DERIVED: ``set(fetch_russell3000()) - set(fetch_russell1000())``,
         order preserved from the Russell 3000 list so the result is
         deterministic. -> source ``derived-r3000-minus-r1000``.
      3. ``[]`` -> source ``empty``.

    There is deliberately NO curated fallback. The curated list is large-cap
    leaders — the exact opposite population of a small-cap index — and serving
    it under this name would invent membership.

    THE DERIVED LIST INHERITS ITS PARENTS' SHORTFALL. Measured 2026-09-18: the
    IWV export on disk listed 2,559 tradeable holdings and the IWB export
    1,001, so the derivation was 1,560 names, not ~2,000 (live 2026-09-28:
    2,587 - 1,022 ≈ 1,565 — IWV is a sampled fund). Never present it as a
    complete Russell 2000 — call `russell2000_coverage()` and serve what it
    says.
    """
    # The DERIVED branch below writes no disk cache, deliberately: the only
    # thing that can have written this file is the local-xls branch, so a cache
    # hit here is unambiguous provenance rather than an inference. A derivation
    # re-runs from the parents' own caches and is two set operations.
    cached = _read_cached("russell2000")
    if cached:
        return _record("russell2000", SRC_ISHARES_LOCAL, cached,
                       age_days=_cache_age_days("russell2000"))

    # --- (1) the real thing, if Ajay has dropped an IWM export in ----
    try:
        out = _load_ishares_local_xls(_LOCAL_IWM_PATH, source_label="russell2000")
        if out:
            _write_cached("russell2000", out)
            return _record("russell2000", SRC_ISHARES_LOCAL, out,
                           age_days=_file_age_days(_LOCAL_IWM_PATH))
    except FileNotFoundError:
        log.info("universe: russell2000 local xls absent — deriving from "
                 "russell3000 minus russell1000")
    except Exception as exc:
        log.warning("universe: russell2000 local-xls parse failed (%s) — "
                    "deriving from russell3000 minus russell1000", exc)

    # --- (2) the derivation ------------------------------------------
    # No network path is wired for IWM. Since 2026-09-29 one exists (the same
    # latest-holdings.csv the parents use), but switching the Russell 2000
    # from a derivation to the real 1,970-name list is a CONSTRUCTION change
    # (universe_changes re-baselines on it) and his call. The derivation IS
    # the index's own definition, which is why it is second, not a fallback.
    try:
        big = fetch_russell1000()
    except Exception as exc:
        log.warning("universe: russell2000 — russell1000 parent failed (%s)", exc)
        big = []
    try:
        broad = fetch_russell3000()
    except Exception as exc:
        log.warning("universe: russell2000 — russell3000 parent failed (%s)", exc)
        broad = []
    # THE PARENTS MUST BOTH BE REAL (added 2026-09-18, before ship).
    # A derived list is only as honest as what it is derived FROM. If either
    # parent fell back to `curated` — the WRONG universe, a last resort — the
    # subtraction still produces a plausible-looking list, and because both runs
    # report the same source string ("derived-…") the change tracker sees no
    # source flip and publishes the delta as REAL index events.
    #
    # Measured on live data the day this was written: r1000=1001 r3000=2559
    # derive to 1,560. With russell1000 fallen back to curated (903) the
    # derivation gives 1,669 — a diff of 204 additions and 95 removals, churn
    # 299 against a sane-window of 546, so `is_sane_churn` waves it through.
    # The weekly cron would have said "russell1000 could not be refreshed
    # (curated)" and "204 additions to the Russell 2000" in the SAME run.
    # Ajay reads that log for real corporate events. Fail empty instead.
    _BAD_PARENT = ("curated", "empty", "stale-cache")
    for _parent in ("russell1000", "russell3000"):
        _src = (last_source(_parent) or {}).get("source")
        if _src in _BAD_PARENT:
            log.warning("universe: russell2000 NOT derived — parent %s resolved "
                        "from %s, which is not that index; a subtraction off it "
                        "would publish corporate events that did not happen",
                        _parent, _src)
            return _record("russell2000", "empty", [])

    big_set = {str(s).strip().upper() for s in (big or []) if str(s).strip()}
    seen, out = set(), []
    for s in (broad or []):
        u = str(s).strip().upper()
        if not u or u in big_set or u in seen:
            continue
        seen.add(u)
        out.append(u)
    if out:
        log.info("universe: russell2000 derived — %d names "
                 "(russell3000 %d - russell1000 %d)",
                 len(out), len(broad or []), len(big or []))
        # NOT cached: see the note on the cache read above.
        return _record("russell2000", SRC_DERIVED_R2000, out)

    log.warning("universe: russell2000 could not be derived — both parents "
                "resolved empty; serving nothing rather than a wrong universe")
    return _record("russell2000", "empty", [])


def russell2000_coverage() -> dict:
    """What the russell2000 list we serve actually IS. Every number measured.

    A derived list is definitionally correct and materially incomplete, and the
    two facts have to travel together or the surface reading it will quote a
    partial index as the index. Nothing in here is a literal: the counts are
    read off the parents at call time, including the label.

    Keys:
      ``n``                    names in the list we would serve
      ``source``               ``ishares-local`` | ``derived-r3000-minus-r1000``
                               | ``empty``
      ``complete``             True ONLY when an IWM export supplied the list
      ``attributable``         False for a derived list — a name leaving it may
                               have entered the Russell 1000 or may simply have
                               moved in one parent export and not the other
      ``derived_from``         the two parent counts
      ``parents_not_contained``names in the Russell 1000 that are NOT in the
                               Russell 3000. FTSE guarantees containment, so any
                               name here is proof the two exports are out of step
      ``label``                a one-line qualifier built from those counts
      ``note``                 the plain-English version, including the exact
                               file drop that upgrades it
    """
    syms = fetch_russell2000()
    src = (last_source("russell2000") or {}).get("source")
    complete = src == SRC_ISHARES_LOCAL
    n = len(syms or [])
    out: dict = {
        "index": "russell2000",
        "n": n,
        "source": src,
        "complete": bool(complete),
        "attributable": bool(complete),
    }
    if complete:
        out["derived_from"] = None
        out["parents_not_contained"] = []
        out["label"] = "russell2000 (iShares IWM export, %d names)" % n
        out["note"] = (
            "Read from the iShares Russell 2000 (IWM) holdings export on disk "
            "at %s. This is the real membership list, not a derivation."
            % _LOCAL_IWM_PATH
        )
        return out

    try:
        big = fetch_russell1000() or []
    except Exception:
        big = []
    try:
        broad = fetch_russell3000() or []
    except Exception:
        broad = []
    n_big, n_broad = len(set(big)), len(set(broad))
    not_contained = sorted({str(s).upper() for s in big} - {str(s).upper() for s in broad})
    out["derived_from"] = {"russell3000": n_broad, "russell1000": n_big}
    out["parents_not_contained"] = not_contained
    out["label"] = ("russell2000 (derived: russell3000 %d - russell1000 %d = %d)"
                    % (n_broad, n_big, n))
    out["note"] = (
        "Derived as Russell 3000 minus Russell 1000, which is FTSE's own "
        "definition of the Russell 2000. It holds {n} names; the index is "
        "named for about two thousand. The shortfall is inherited: the iShares "
        "Russell 3000 holdings list {r3000} tradeable names and the "
        "Russell 1000 holdings list {r1000}. The names it is missing are small "
        "caps — exactly this list's population. Treat it as part of the "
        "Russell 2000, not as the Russell 2000. A change on this list cannot "
        "be attributed to a parent: a name leaving here may have entered the "
        "Russell 1000 or may only have moved in one export and not the other. "
        "Drop an iShares IWM holdings export at {path} and this becomes the "
        "real list with no code change."
    ).format(n=n, r3000=n_broad, r1000=n_big, path=_LOCAL_IWM_PATH)
    return out


def fetch_microcap() -> list[str]:
    """Micro-cap names below the Russell 3000: the iShares Micro-Cap ETF (IWC)
    holdings — live CSV first, then the committed snapshot. Returns [] (not
    an error) when both fail — the broad universe is still valid without it.

    Cached 30 days like the other Russell sources.
    """
    got = _resolve_ishares("microcap", _LOCAL_IWC_PATH)
    if got:
        syms, src, age, as_of = got
        return _record("microcap", src, syms, age_days=age, as_of=as_of)
    log.info("universe: microcap — no live IWC list and no snapshot — "
             "skipping micro-cap layer")
    return _record("microcap", "empty", [])


def fetch_etf_universe() -> list[str]:
    """Broad list of liquid US-listed ETFs (see sepa/etf_universe.py).

    SEPA's liquidity gate + trend template filter downstream, so this list is
    intentionally over-inclusive. Static (no network), so no caching needed.
    """
    try:
        from .etf_universe import etf_universe as _etfs
        return _etfs()
    except Exception as exc:
        log.warning("universe: ETF universe import failed (%s)", exc)
        return []


def fetch_broad() -> list[str]:
    """Widest equity + ETF net (user 2026-05-30: "expand beyond Russell 3000
    alongside ETFs"):

        curated  ∪  Russell 3000  ∪  micro-caps (IWC, if present)  ∪  ETFs

    `curated` goes FIRST and is non-negotiable: the iShares Russell holdings
    are US-domiciled only, so foreign ADRs Ajay actively trades — ARM, ASML,
    TSM, SHOP, BABA, … — are NOT Russell constituents and silently vanished
    from `broad` (ARM dropped 2026-05-30: "it was in the list till
    yesterday"). The hand-picked curated list carries those names plus the
    mega-cap leaders, so unioning it back guarantees they're always scanned
    AND pre-warms them early. Dedup keeps first-seen order.
    """
    curated = list(UNIVERSE)
    # S&P 500 + 400 explicit union — almost entirely a subset of Russell 3000
    # already (so net-new is ~0), but it guarantees full S&P coverage even if
    # the quarterly iShares snapshot is stale on a recent index add, and it
    # restores the old fallback universe (curated ∪ sp500 ∪ sp400) the user
    # asked to preserve. Both fall back gracefully (sp500→curated, sp400→[]).
    sp500 = fetch_sp500()
    sp400 = fetch_sp400()
    # Build-out themes, for the same reason curated is here: the quantum /
    # SMR-nuclear / robotics names are pre-profit and several are foreign ADRs,
    # so they are in no S&P tier and the US-domiciled-only Russell holdings miss
    # the ADRs too. Measured 2026-08-15: 40 of the 42 theme names already
    # arrived via curated ∪ russell1000, but ARQQ and SYM reached NO layer, so
    # the Strong VCP board could never show them. Unioning the rosters closes
    # that without touching SEPA_UNIVERSE_MODE.
    themes = fetch_themes()
    equities = fetch_russell3000()
    micro = fetch_microcap()
    etfs = fetch_etf_universe()
    merged = list(dict.fromkeys(
        curated + themes + sp500 + sp400 + equities + micro + etfs
    ))
    log.info(
        "universe: broad mode = %d curated + %d themes + %d sp500 + %d sp400 "
        "+ %d R3000 + %d micro + %d ETF -> %d unique",
        len(curated), len(themes), len(sp500), len(sp400), len(equities),
        len(micro), len(etfs), len(merged),
    )
    return merged


# Orthogonal universe building blocks → fetcher. Used by the multi-select
# path in load_universe: the user picks any combination and we union + dedup
# (overlaps removed). Defined here, after every fetcher, so the direct
# function references resolve.
# Named aliases that expand to a set of components. Keep the membership here,
# next to the component map, so a page that offers "S&P 1500 + themes" cannot
# drift from what that phrase actually resolves to.
_UNIVERSE_ALIASES: dict[str, tuple[str, ...]] = {
    "sp1500_plus": ("sp1500", "curated", "themes"),
    # The SEPA scan's own net (Ajay 2026-08-25: "for our demand and supply all
    # the chart maps i would like the full universe scan which includes SP1500
    # too"). russell1000 alone was the mode until then, which structurally
    # misses every S&P 600 small cap — the demand board scanned 1,551 names
    # while the scanner feeding the SEPA page and Strong VCP tab saw 1,001.
    # Union, not replacement: Russell keeps the not-yet-in-S&P large caps
    # (recent IPOs), sp1500 adds the small-cap tier, curated + themes carry
    # the pre-profit / ADR names no index will hold.
    # Ajay 2026-09-07: "Yes please add 3000, I wanna be able to scan more..
    # becuz there is so much growth to small cap." Was russell1000 (1,751 names
    # measured that day); the Russell 3000 layer adds ~900 small caps and every
    # consumer of "full" (scan, zone_store, demand boards, quick-bounce study)
    # widens with it. A raw `russell3000` mode would have DROPPED 95 names that
    # only curated / themes / sp1500 carry — hence the layered alias.
    # `promo` joined 2026-09-21 (Ajay: "add them to our list as they come
    # through"): names the promo-circuit board tagged that survived the
    # curation gate in catalysts/promo_curate.py. Being tagged is the INPUT,
    # never the test — and an add means the app can SEE the name, nothing more.
    "full": ("russell3000", "sp1500", "curated", "themes", "traders", "promo"),
}


# The one place a component name maps to a fetcher. `load_universe` resolves
# single keys through the SAME map, so a name that works in a comma-separated
# multi-select cannot silently fail as a standalone mode — which is precisely
# how "sp1500" resolved to the curated 158.
_COMPONENT_FETCHERS: dict = {
    "curated":     lambda: list(UNIVERSE),
    "sp500":       lambda: fetch_sp500(),
    "sp400":       lambda: fetch_sp400(),
    # sp600/sp1500 existed as fetchers but were absent from this map, so
    # SEPA_UNIVERSE_MODE="curated,sp1500" silently resolved to the curated
    # ~158 names with only a log line. Registered 2026-08-15.
    "sp600":       lambda: fetch_sp600(),
    "sp1500":      lambda: fetch_sp1500(),
    "nasdaq100":   lambda: fetch_nasdaq100(),
    # Keyed `nasdaq_listed` to match its size band and its guard name — a
    # component with no band in _EXPECTED_COUNTS silently gets (1, 1e9),
    # i.e. no guard at all, which `test_every_component_has_a_size_band`
    # exists to catch. It caught this one.
    "nasdaq_listed": lambda: fetch_nasdaq_listed(),
    "themes":      lambda: fetch_themes(),
    # Tickers the tracked public traders named that resolved to a real company
    # with real price history (traders/curate.py). Mongo-backed BECAUSE the
    # curated list above is a Python literal baked into the image: a cron
    # cannot edit it, and the edit would vanish on the next deploy anyway.
    # Every row carries who said it and which post, so an add is auditable and
    # flipping its status removes it from the next scan with no code change.
    "traders":     lambda: fetch_trader_adds(),
    # Tickers the promo-circuit roster tagged that survived the curation gate
    # (catalysts/promo_curate.py): a real common stock on a listing exchange,
    # real price history, over the $2 and $5M-median-dollar-volume floors.
    # Mongo-backed for the same reason `traders` is.
    "promo":       lambda: fetch_promo_adds(),
    "russell1000": lambda: fetch_russell1000(),
    "russell3000": lambda: fetch_russell3000(),
    "micro":       lambda: fetch_microcap(),
    "microcap":    lambda: fetch_microcap(),
    "etf":         lambda: fetch_etf_universe(),
    "etfs":        lambda: fetch_etf_universe(),
    "broad":       lambda: fetch_broad(),
}

# Late-bound via lambdas above so the _count_guarded wrappers installed at the
# bottom of this module are the ones actually called.
_KNOWN_COMPONENTS = frozenset(_COMPONENT_FETCHERS)


def fetch_trader_adds() -> list[str]:
    """Names curated in from the tracked traders' posts. [] on any failure.

    Fails EMPTY, never raising: this component sits inside `full`, and a Mongo
    blip must cost the handful of curated adds, never the 2,661-name universe
    every scan and board runs on."""
    try:
        from traders.curate import added_symbols
        out = added_symbols()
        if out:
            log.info("universe: %d trader-curated add(s)", len(out))
        return out
    except Exception as exc:                                   # noqa: BLE001
        log.warning("universe: trader adds unavailable: %s", exc)
        return []


def fetch_promo_adds() -> list[str]:
    """Names curated in from the promo-circuit board. [] on any failure.

    Fails EMPTY, never raising, for exactly the reason `fetch_trader_adds`
    does: this component sits inside `full`, and a Mongo blip must cost the
    handful of curated adds, never the whole universe every scan and board
    runs on."""
    try:
        from catalysts.promo_curate import added_symbols
        out = added_symbols()
        if out:
            log.info("universe: %d promo-curated add(s)", len(out))
        return out
    except Exception as exc:                                   # noqa: BLE001
        log.warning("universe: promo adds unavailable: %s", exc)
        return []


def _fetch_component(name: str) -> list[str]:
    fetchers = _COMPONENT_FETCHERS
    fn = fetchers.get(name)
    if fn is None:
        log.warning("universe: unknown component '%s' — skipping", name)
        return []
    try:
        return fn()
    except Exception as exc:
        log.warning("universe: component '%s' failed (%s) — skipping", name, exc)
        return []


def load_universe(mode: str | None = None) -> list[str]:
    """Resolve the active universe.

    Priority:
    1. `mode` argument (explicit caller choice)
    2. SEPA_UNIVERSE_FILE env var (path to one-ticker-per-line text file)
    3. SEPA_UNIVERSE env var (comma-separated literal)
    4. SEPA_UNIVERSE_MODE env var (one of: curated / sp500 / russell1000 /
       russell3000 / broad / all_us / expanded)
    5. Default: curated

    `broad` = Russell 3000 ∪ micro-caps (IWC, if present) ∪ broad ETF list —
    the widest net, equities + ETFs together.

    Always preserves dedup + insertion order. Always appends benchmarks
    (SPY/QQQ/IWM) so RS math has anchors.
    """
    file_path = os.getenv("SEPA_UNIVERSE_FILE")
    if file_path and Path(file_path).exists():
        syms = [ln.strip().upper() for ln in Path(file_path).read_text().splitlines() if ln.strip()]
        return _with_benchmarks(syms)

    env = os.getenv("SEPA_UNIVERSE")
    if env:
        syms = [s.strip().upper() for s in env.split(",") if s.strip()]
        return _with_benchmarks(syms)

    selected = (mode or os.getenv("SEPA_UNIVERSE_MODE") or "curated").lower()

    # Multi-select: a comma-separated list of components (e.g.
    # "russell3000,etf,micro"). Union each + dedup so overlaps are removed.
    # The frontend already strips subset-covered components, but the set
    # union here makes dedup correct regardless of what's sent.
    if "," in selected:
        combined: list[str] = []
        seen_parts: set[str] = set()
        for part in (p.strip() for p in selected.split(",")):
            if part and part not in seen_parts:
                seen_parts.add(part)
                combined.extend(_fetch_component(part))
        log.info("universe: multi-select [%s] -> %d unique (pre-benchmark)",
                 selected, len(dict.fromkeys(combined)))
        return _with_benchmarks(combined)

    # sp500 / russell1000 / russell3000 / broad used to have their own explicit
    # branches here, duplicating _COMPONENT_FETCHERS. That duplication IS the
    # bug this function shipped: the branch list and the component map drifted,
    # and every key present in one but not the other (sp1500, sp400, sp600,
    # nasdaq100, themes) fell through to curated. One map now, one lookup.
    if selected in ("russell3000_etf", "max"):
        # Widest net — Russell 3000 ∪ micro-caps ∪ broad ETF list. SEPA's
        # liquidity gate handles the small-cap / thin-ETF noise floor.
        selected = "broad"
    if selected == "all_us":
        # All active US common stocks via Massive (~5,300 names). Scans
        # take 8-10 minutes with the bulk-snapshot pre-warm — SEPA's
        # built-in liquidity gate handles the small-cap noise floor.
        return _with_benchmarks(fetch_massive_universe())
    if selected == "expanded":
        # Curated ∪ S&P 500 (curated wins on ordering)
        merged = list(dict.fromkeys(list(UNIVERSE) + fetch_sp500()))
        return _with_benchmarks(merged)

    # Named aliases that expand to a component set. `sp1500_plus` is the Chart
    # Maps and demand-reentry default, and it MUST include the themes — the
    # whole reason the rosters exist is that the S&P tiers structurally cannot
    # hold them.
    if selected in _UNIVERSE_ALIASES:
        parts = _UNIVERSE_ALIASES[selected]
        combined = []
        for part in parts:
            combined.extend(_fetch_component(part))
        log.info("universe: alias %s -> [%s] -> %d unique (pre-benchmark)",
                 selected, ",".join(parts), len(dict.fromkeys(combined)))
        return _with_benchmarks(combined)

    # Any single component name we actually know how to fetch. Before
    # 2026-08-16 this branch did not exist: `sp1500`, `sp400`, `sp600`,
    # `nasdaq100` and `themes` all fell through to the curated 158 SILENTLY,
    # identical to what a garbage key returned, so /supply-demand ran a
    # 158-name scan while its own UI said "S&P 1500".
    if selected in _KNOWN_COMPONENTS:
        return _with_benchmarks(_fetch_component(selected))

    if selected != "curated":
        log.error("universe: unknown mode %r — falling back to the curated %d "
                  "names. This is NOT the universe that was asked for.",
                  selected, len(UNIVERSE))
    return _with_benchmarks(list(dict.fromkeys(UNIVERSE)))


def _resolve_fates(syms: list[str]) -> list[str]:
    """Map renamed tickers to their live symbol, drop verified delistings.

    Every load_universe path funnels through here (via _with_benchmarks), which
    matters because most components are 30-day-cached fetches: a rename or
    delisting sits in those caches long after the fact (SMAR was dead in the
    universe for 19 months). Applying sepa.symbols at the chokepoint heals
    every path — cached, fetched, curated, env-var — the day the curated map
    learns the fate. Also dedups old+new pairs (IAC and PPLI were both
    present; resolve() collapses them to one PPLI).
    """
    from . import symbols as S
    out, seen = [], set()
    for s in syms:
        cur = S.resolve(s)
        if S.is_delisted(cur) or cur in seen:
            continue
        seen.add(cur)
        out.append(cur)
    return out


def _with_benchmarks(syms: list[str]) -> list[str]:
    """Resolve symbol fates, then append the RS anchors (for RS math).

    Reads RS_ANCHORS rather than its own tuple: this function is what PUTS the
    anchors into every universe, and `patterns.scan` is what has to keep them
    off a stock-pattern board. A fourth benchmark added here and not there
    would ship an index ETF straight onto the board.
    """
    out = _resolve_fates(syms)
    for b in RS_ANCHORS:
        if b not in out:
            out.append(b)
    return out


# ---------------------------------------------------------------------------
# Size guards, installed last so every fetcher is defined.
#
# Ajay 2026-08-16: "add a count checks for returned values for all the tickers
# API like Russel 3000 and S&P 500 as well."
#
# `_count_ok` already guarded the four lists that route through
# `_resolve_with_fallbacks`. Everything else — Russell 1000/3000, sp1500,
# microcap, ETFs, broad — had bespoke cache/fallback chains with up to six exit
# points each and no check on any of them. Wrapping by name covers every path,
# including the stale-cache and clean-fallback returns that are exactly where a
# list quietly becomes a different universe.
# ---------------------------------------------------------------------------
fetch_sp500 = _count_guarded("sp500", fetch_sp500)
fetch_sp400 = _count_guarded("sp400", fetch_sp400)
fetch_sp600 = _count_guarded("sp600", fetch_sp600)
fetch_nasdaq100 = _count_guarded("nasdaq100", fetch_nasdaq100)
fetch_sp1500 = _count_guarded("sp1500", fetch_sp1500)
fetch_russell1000 = _count_guarded("russell1000", fetch_russell1000)
fetch_russell3000 = _count_guarded("russell3000", fetch_russell3000)
fetch_microcap = _count_guarded("microcap", fetch_microcap)
fetch_etf_universe = _count_guarded("etf", fetch_etf_universe)
fetch_themes = _count_guarded("themes", fetch_themes)
fetch_broad = _count_guarded("broad", fetch_broad)
fetch_massive_universe = _count_guarded("massive", fetch_massive_universe)
fetch_nasdaq_listed = _count_guarded("nasdaq_listed", fetch_nasdaq_listed)
# The two Mongo-backed curation components were declared with a (0, 200) band
# and then never wrapped — so `LAST_COUNTS["traders"]` was never written and the
# band was documentation, not enforcement (found 2026-09-21). `_record_count`
# records and logs loudly; it never REJECTS, so the fail-EMPTY contract and the
# universe size are unchanged. Observability only.
fetch_trader_adds = _count_guarded("traders", fetch_trader_adds)
fetch_promo_adds = _count_guarded("promo", fetch_promo_adds)


BENCHMARK = "SPY"
