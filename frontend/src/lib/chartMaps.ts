/* chartMaps — pure helpers for the Chart Maps study board (/chart-maps).
 *
 * Ajay 2026-08-15: "I need just maps that you are pulling show… look at
 * patterns and learn them day by day."
 *
 * Backend: backend/chart_maps/board.py (GET /chart-maps?tab=…). The server
 * returns ONE tile shape for all three tabs; everything here is geometry and
 * formatting, so the drawing component stays dumb and the numbers are testable.
 *
 * NOT advice — a study surface over scans that already exist.
 */
import { layoutLabels, type LabelItem } from './zonePlan';
import type { DemandScanProgress } from './demandScanProgress';
import type { ExplosiveRead, ExplosiveStudy } from './bounceRoom';
import type { BandStructureRead, BandStructureStudy } from './bandStructure';
import type { EnterableKind, EnterableRead, EnterableStudy } from './enterable';

export type CmTab = 'bonde' | 'keltner' | 'amd' | 'holdings' | 'vcp' | 'topping' | 'zones' | 'supply' | 'ict' | 'deep_demand' | 'quick_bounce' | 'breaking' | 'session' | 'gabbar' | 'undervalue' | 'support' | 'zero_dte' | 'winners' | 'earnings' | 'overnight' | 'signals' | 'catalysts' | 'hot_pullback' | 'hot_sectors' | 'growth' | 'patterns' | 'gnt';
// Order = MOST-USED FIRST (Ajay 2026-09-06: "Move most used tabs to the
// beginning of the list"). Nothing had ever recorded which tab was open —
// page views log the pathname only, the API keeps no access log — so this
// first cut is the evidence at hand: every S/D push (demand, bounce, supply
// break) lands on Back in Demand / Deep Demand, Quick Bounce was asked for
// the same day, Session and Signals are the intraday reads of those names,
// Catalysts was moved in on 2026-09-05 with Overnight as its movers twin,
// Gabbar carries its own alerts. The SEPA slices (Strong VCP, S3 Topping)
// sit behind them because that scan is read on the SEPA page, ICT measured
// no edge (2026-09-04) and is a study board, and the rest are occasional.
// From this change on every tab open is counted (tabUsageKey → Mongo
// usage_stats `feature:chart-maps:tab:<tab>`), so the next cut is measured.
// Adjacencies kept: `deep_demand` → `quick_bounce` → `session` → `signals`
// (session READS the two demand boards; signals is the other intraday read),
// `catalysts` beside `overnight` (both movers boards), `topping` beside `vcp`
// (two slices of one SEPA scan file), `support` — the only per-ticker tool —
// closes the level boards before the option / ledger tabs. `supply` stays in
// the CmTab union so TAB_META keeps its copy and an old ?tab=supply deep link
// still renders (→ `ict`, see parseTab); it is not in CM_TABS.
// `hot_pullback` (2026-09-09) sits after `breaking`: it is the other side of
// the same demand structure — `breaking` is price leaving a lid, this is price
// flushing into a band and turning. It must NOT split `quick_bounce` from
// `breaking`, whose adjacency a frontend contract pins.
// `breaking` (2026-09-06, Ajay: "change the deep demand to be like In Demand
// with charts and cards") is the zone-edge 🚀 list that used to sit as ~200
// text rows on top of Deep Demand, now its own card board right after the
// demand cluster; Deep Demand is cards only, like Back in Demand.
// `patterns` (2026-09-09, Ajay: "Can you move chart patterns in to the
// Chartmaps page please and show the winning charts") mounts the Patterns
// page body; /patterns redirects here, the Catalysts precedent. `winners`
// deliberately STAYS at the end with the other ledger tabs — that grouping is
// its own tested rule — so "show the winning charts" is served by a link out
// of the patterns board instead: one at the top, one on every card, each
// filtered to that pattern. A link from the thing you are looking at beats a
// tab two seats over.
export const CM_TABS: CmTab[] = ['zones', 'deep_demand', 'quick_bounce', 'breaking', 'hot_pullback', 'patterns',
  // 🌀 Turning Bullish (Ajay 2026-09-13: "I need two tabs in chart maps
  // for me to look at where stocks are bullish in the recent 6 months
  // where they are turning bullish"). Placed mid-pack rather than at the
  // front on purpose: the order is supposed to be MEASURED, and a brand
  // new tab has no usage yet. `tabUsageKey` counts them from the first
  // open, so the next re-cut moves them on evidence.
  'keltner', 'amd',
  // 📁 My holdings (Ajay 2026-09-14: "about the new portfolio stocks I want
  // to run these against them" — the AMD / KC / supply-demand reads on the
  // names he actually owns, with his cost on every chart). Beside the two
  // study tabs it runs; no usage yet, so mid-pack like them.
  'holdings',
  // Bonde (Ajay 2026-09-13: "create me a Bonde tab ... I wanna see his
  // stocks"). Beside the growth boards it belongs with, not at the front —
  // same measured-order rule as the two above.
  'bonde',
  'session', 'signals', 'hot_sectors', 'growth', 'gnt', 'catalysts', 'overnight', 'gabbar', 'vcp', 'topping', 'ict', 'undervalue', 'support', 'zero_dte', 'earnings', 'winners'];

/** The tab a bare /chart-maps (and any unknown ?tab=) opens on — the FIRST,
 *  most-used tab, so the landing board follows the order itself. */
export const DEFAULT_TAB: CmTab = CM_TABS[0];

/* 🎯 ENTERABLE_KIND — which read each tab's rows get (2026-09-15). CONFIG, not
 * a rule: it mirrors backend/supply_demand/enterable.py::KIND_BY_TAB and is
 * pinned against the same fixture both suites read
 * (backend/tests/fixtures/enterable_mirror_2026_09_15.json). The SERVED
 * `enterable_kind` wins wherever the payload carries it; this map is the
 * fallback before the first response lands.
 *
 *   `demand`       — the rows are demand reversals, the read and the filter apply;
 *   `supply_break` — 🚀 Breaking: room to the NEXT lid is the read;
 *   `n/a`          — the rows are pivots / highs / lids / events / options /
 *                    value, never demand reversals, so a demand read would blank
 *                    the tab by construction. The filter is inert there and the
 *                    chip says why. Which tabs sit in which bucket is HIS CALL
 *                    (spec §7.16) — the hide rate per tab is measured on the
 *                    live payload and handed to him.
 *
 * `supply` (the legacy tab replaced by `ict` on 2026-09-03, still in CmTab for
 * old bookmarks but never returned by parseTab and not in CM_TABS) is absent
 * here on purpose: the map is the backend's map, key for key. */
export const ENTERABLE_KIND = {
  zones: 'demand', deep_demand: 'demand', quick_bounce: 'demand', hot_pullback: 'demand',
  session: 'demand', signals: 'demand', overnight: 'demand', patterns: 'demand',
  bonde: 'demand', growth: 'demand', gnt: 'demand', catalysts: 'demand', hot_sectors: 'demand',
  keltner: 'demand', amd: 'demand', gabbar: 'demand', ict: 'demand',
  breaking: 'supply_break',
  // chip only — the FE never hides these (contract: a position is never hidden,
  // and the Support tab answers one symbol).
  holdings: 'demand', support: 'demand',
  vcp: 'n/a', winners: 'n/a', topping: 'n/a', earnings: 'n/a', zero_dte: 'n/a', undervalue: 'n/a',
} as Record<CmTab, EnterableKind>;

/** usage/track key for one tab open (landing or click). Read back from Mongo
 *  `usage_stats` as `feature:chart-maps:tab:<tab>` (count + weekday/hour
 *  buckets) to re-cut CM_TABS from measured use. */
export function tabUsageKey(t: CmTab): string {
  return `chart-maps:tab:${t}`;
}

/** Tabs driven by a scan. `support` answers one ticker on request, so the
 *  board loader, the sort/tier controls and the tile grid are all skipped for
 *  it — asking /chart-maps for an unknown tab silently returns the VCP board. */
export function isBoardTab(t: CmTab): boolean {
  // `session` joins `support` as a non-board tab: it has its own endpoint
  // (/supply-demand/session-board) and its own row renderer, so the tile grid
  // and the sort/tier controls are skipped for it too.
  // `catalysts` (2026-09-05) mounts the Catalysts page body — its own scan
  // endpoints and sub-tabs, nothing from /chart-maps.
  return t !== 'support' && t !== 'session' && t !== 'overnight' && t !== 'signals'
    && t !== 'catalysts' && t !== 'hot_pullback' && t !== 'patterns'
    && t !== 'hot_sectors'
    // `holdings` (2026-09-14) is one /chart-maps/support call per name he
    // owns — his portfolio is not a universe pass.
    && t !== 'holdings'
    // Bonde is a sectioned table off /bonde/board, not a tile grid.
    && t !== 'bonde'
    && t !== 'growth'
    && t !== 'gnt';
}

export const TAB_META: Record<CmTab, { label: string; blurb: string }> = {
  gnt: {
    label: '\uD83D\uDCCC GnT',
    blurb: 'Tito Adhikary (@GnT_Trades) \u2014 what he is posting, with this app\u2019s own read beside it. Ajay 2026-09-12: "I wanna track his stocks for investing". HE WON THE 2025 US INVESTING CHAMPIONSHIP, $20k+ Enhanced Growth division, +2,115.1% \u2014 a CITED claim quoted from @USICOfficial on his own pinned post, not a number this app measured, and not a transferable track record: those divisions permit concentration and leverage this app\u2019s own risk rules forbid. THE BOARD SHOWS SENTENCES, NOT A TICKER LIST, and that is deliberate. He does not post a portfolio: his timeline mixes forward ideas ("$SPCX reclaiming 150 into the close. Definitely on watch next week") with past-tense recaps of CLOSED trades, several of them PUTS ("Great day on $QQQ puts, +$12K") and some from 2022 naming stocks that no longer exist. A bare cashtag list inverts him. So every row leads with his actual words and its age, and NO row claims a direction \u2014 one of his own posts reads "caught the upside on $FSLR and downside on $META $TSLA", one sentence carrying both, so the chips are WORDS FOUND IN THE POST rather than a reading of it. Index tickers are dropped from the roster because "$SPY $QQQ weak" is him describing the tape, not naming a stock. The overlay columns are ours: whether the name is even in the scan universe (his freshest idea, SPCX, is NOT \u2014 invisible to every board and alert here), the demand-band read, and the 100/100 growth screen. Fetched twice a day, 07:40 and 17:40 CT, weekends included because his weekend wrap is where the next week\u2019s watchlist shows up. His calls, NOT advice. Nothing here gates a scan, an alert or a lane.',
  },
  growth: {
    label: '\uD83D\uDE80 Explosive Growth',
    blurb: 'Sales up 100%+ AND quarterly EPS up 100%+ year-over-year on the latest reported quarter \u2014 with the quarter BEFORE it also growing, which is the leg that separates a real ramp from an easy year-ago base. Ajay 2026-09-11: "I want real growing stocks like AXTI and SABR with genuine sales". THIS BOARD HAS NO MARKET-CAP FLOOR \u2014 your call ("remove the 700M rule for this page") \u2014 so it can show a name before it is big. Every other board in the app filters to $700M+, and so does the trading engine: a row the engine will REFUSE to buy (under $2 a share, or a known cap under $700M) says exactly that in its own warnings rather than looking buyable. \u26A0\uFE0F also flags a thin tape and a promo-tagged name. The \uD83E\uDDF2 demand column is the one gate that measured \u2014 the band floor never pierced (+8.6pp win rate over 31,861 events); an order block rides along as a DISPLAY flag only, because the ICT study measured +0.03R over 6,004 signals, i.e. nothing. Rebuilt Sundays after the weekly research refresh, so new Russell entrants join on their own. NOTHING HERE IS BACKTESTED: the 100/100 screen has never been measured forward. It is a discovery list, not a buy signal.',
  },
  hot_sectors: {
    label: '\uD83D\uDD25 Hottest',
    blurb: 'Every sector ranked, opening into its industries and then its names, with the sales block on each row \u2014 built to surface names you are NOT already tracking. Three legs: today, 5 days and 21 days, each against RSP (equal-weight), so a name is measured against the average stock rather than the mega-caps. ALL ELEVEN sectors are listed, not just the hot end, deliberately: a strong name often sits in a cold sector \u2014 ANDE, the name that prompted this board, is 2nd of Consumer Defensive\u2019s 76 over 21 days while the sector itself is 8th of 11, so a hot-sectors-only list could never find it. Sector and industry heat is the rotation grid\u2019s sampled median (the SAME number the Hot-sectors strip prints, reused so the two can never disagree); name rows are the FULL membership, which is what makes those names reachable. Industries too small for a ranked row still show inside their sector, flagged \u2014 a 6-name median is not a 25-name one. Names are ranked by the return legs, NOT by traction: traction measures acceleration, and it ranks ANDE 23rd of 76 while the 5-day ranks it 3rd. This is a DISCOVERY list off trailing returns \u2014 nothing here is backtested and none of it is a buy signal. Sales, EPS and margin come from the weekly research cache, so they can be up to a week behind a fresh print; a blank is printed as \u2014 and never as a zero.',
  },
  hot_pullback: {
    label: '\uD83D\uDD25 Hot Pullback',
    blurb: 'A stock that has been HOT takes one hard flush into a demand band and turns the same day \u2014 the DYN 2026-09-08 shape: gapped from 24.28 to a 17.00 low that landed inside a 4-touch demand band, then closed 20.31, +19.5% off that low and 21% under the 21-day line. All four parts are required: hot before the drop (prior close at least 30% above its own 52-week low), the day\u2019s low at least 12% under the prior 10-day high AND the close at least 10% under the 21-day line, that low inside a TESTED demand band, and the close at least 8% off the low in the top 30% of the day\u2019s range. MEASURED over 2 years (65 events, 56 names, no lookahead): entering at the NEXT OPEN returned a median +2.40% by the next close and +2.85% by day two, 66% up, against a placebo of +0.05% / +0.19%. The demand band is what carries it \u2014 the identical reversal NOT in a band measured nothing (p=0.461). The edge is GONE by day five (p=0.450), so this is a one-to-three session trade, not a hold, and the worst three-day in the sample was \u221236%. A study board with a measured horizon, not a buy button. Not advice.',
  },
  signals: {
    label: '\u26A1 Signals',
    blurb: 'Your own tickers on 1-minute candles with BUY / SELL tags \u2014 opening-range breaks, liquidity sweeps and BOS/CHoCH structure composed into the five-step entry (stop at the trap wick, 2R target). Closed bars only; signals never repaint. Same board as the Signal Lab page.',
  },
  // 🌀 Turning Bullish, two tabs (Ajay 2026-09-13: "I need two tabs in chart
  // maps for me to look at where stocks are bullish in the recent 6 months
  // where they are turning bullish"). Both read the SAME modules the chart
  // overlays draw from, through supply_demand/turning_bullish.py, so a name on
  // the board and that name's chart can never disagree about its state.
  holdings: {
    label: '\u{1F4C1} My holdings',
    blurb: 'Every name on your Portfolio page, drawn the way the Support tab draws it: the tested demand and supply bands at the zoom you pick, the swings that MADE each band marked on the bars, the SMC order blocks, and — when you tick them — the AMD phases (A on the base, M on the raid bar, D on the markup, ✗ where the base failed), the Keltner channel with its squeeze dots, Fibonacci and mean reversion. Ajay 2026-09-14: "about the new portfolio stocks I want to run these against them." YOUR COST is the pink line on each chart; YOUR STOP appears in blue only when you have typed a stop on the Portfolio page — the app never invents one. Worst position first. The DASHED band on each chart is the demand BOARD\u2019s own band \u2014 the one Back in Demand, Deep Demand, the alert gate and the paper lanes use (swing 5 \u00b7 merge 4% \u00b7 252 bars); the solid bands are the Support tab\u2019s finer levels at this zoom. Both study reads MEASURED INVERTED on 2026-09-13 and again on 2026-09-14 on ~3,700 names (see the two \u{1F300} tabs): they describe the tape, they do not predict it, and nothing here gates, alerts or trades. Not advice.',
  },
  bonde: {
    label: '\ud83d\udcc8 Bonde',
    blurb: 'MEASURED 2026-09-13 AND THIS BOARD\u2019S OWN THESIS IS INVERTED \u2014 read this before the rules. The tab shipped on the idea that Bonde\u2019s SALES screen is the universe and the EPISODIC PIVOT is the entry, so the intersection is the selection. Two passes measured it \u2014 the second an independent audit with its own code, its own fetch and roughly twice the panel \u2014 and that intersection is the WORST cell either pass found. On 780 Episodic Pivots reconstructed from CLOSED bars (2024-09-13 \u2192 2026-09-11, the rule validated 62/63 against the stored setup docs, 0 of 780 using a quarter filed after its bar), the 376 that ALSO passed his sales gate ran a 21-day median \u22123.22% with a 39.8% win rate, against \u22120.11% and 49.6% for date-matched non-Pivot names \u2014 a lift of \u22123.11pp, 95% CI \u22125.28 to \u22121.16 symbol-clustered and \u22125.19 to \u22121.13 date-clustered. It holds under a $1M liquidity cut, under entry at the next open (worse, \u22124.76pp) and in all four point-in-time fundamentals variants. His sales gate ON ITS OWN separated nothing at any horizon (\u22120.40pp, CI \u22121.40 to +0.61): it passes 48.2% of Pivot events and 46.0% of matched non-Pivot draws, so it carries no information about the pivot. Expectancy on the setup\u2019s own bracket is \u22120.92% and the sales gate moves it by \u22120.06pp \u2014 and the 58% target-before-stop rate is bracket geometry, not a win rate (target 6.00% away, stop a median 13.71% away). THIS IS NOT A LICENCE TO SHORT: that cohort\u2019s 21-day MEAN is \u22122.18% with a CI including zero. The finding is \u201cthese bleed at the median and win less than half the time\u201d. THE TIERS DO NOT SEPARATE EITHER: over 45,425 symbol-bars in 24 monthly cross-sections the \u2265100% and \u226525% tiers beat the scored universe by a MEDIAN of +0.45pp and +0.37pp at 21 days, both CIs including zero, win rates level with the market; the average lift is the right tail and falls to +0.26pp once the top 5% of returns are dropped. So the board never sorts on the 0-100 sales score, and no tier number prints without its median, its win rate and its placebo. THE ONE FINDING THAT SURVIVED EVERY ATTACK is about the cohort his gate THROWS AWAY: among names clearing his 5% floor, the character clause (accelerating OR \u22652 consecutive growth quarters) measures BACKWARDS \u2014 the rejected names won 56.8% of the next 21 sessions against 51.2% for the ones the gate accepts (+5.64pp, CI +3.91 to +7.52), and clause by clause it is the CONSISTENCY half (\u22652 consecutive quarters costs 3.31pp of win rate, CI \u22124.68 to \u22121.83; accelerating is a null, not a negative). His gate is NOT edited \u2014 it is his, and this tab exists to show his screen \u2014 so the discarded cohort is shown beside it in the \ud83d\udd0e section, labelled as not on his screen. WHAT WAS STRUCK on re-measurement and is said nowhere: that Pivot+PASS also loses to Pivot+FAIL (\u22122.42pp, CI \u22124.88 to +0.30), that BOTH character clauses are inverted, and the first pass\u2019s \u201ccoverage is 46%\u201d limitation \u2014 that was its own no-retry fetcher losing half its requests. \u2728 NEW still marks names that ARRIVED on his screen, which was your ask; the ledger refuses to badge the first cohort it ever sees, and it never lights on a \ud83d\udd0e row. WHOSE NUMBERS ARE WHOSE: the 5% floor / 25% preferred / 100% explosive tiers are Bonde\u2019s own (docs/sepa/sales_confidence_methodology.md, which also lists the figures widely attributed to him that FAILED source verification); the Pivot\u2019s 8% gap on 5\u00d7 volume are THIS APP\u2019S owner settings, stricter than its PEG cousin because it has no earnings-calendar filter \u2014 he never published them. A ranking guard of this app\u2019s own: a percentage measured off a NEGATIVE or sub-$1M year-ago quarter is a sign flip or a ratio, not growth (DBRG reads +15,961% off MINUS $3.2M, QUBT +9,000% off $61,000), so those names still show with their dollars but never outrank a real base. LIMITS: delisting survivorship is unmeasured, the tier panel is 24 cross-sections inside ONE bull regime, 24.3% of quarterly rows carry no filing date and are assumed available at quarter-end + 90 days, 24.6% of pivots are unclassifiable and the dropout is structural (recent IPOs and de-SPACs), and all returns are gross of commissions, slippage and borrow. Scripts, re-runnable verbatim: backend/scripts/bonde_audit/. Nothing on this tab gates a scan, fires an alert, or buys in any lane. Not advice.',
  },
  keltner: {
    label: '\u{1F300} KC Coiled',
    blurb: 'RE-MEASURED 2026-09-14 ON 3,704 NAMES AND THE CLAIM IS STILL INVERTED \u2014 harder than on 2026-09-13; read this before the rules. Over 1,662,135 closed daily bars (two years to 2026-09-14) a coiled bar returned LESS than every other bar of the same names: 21-day median lift \u22120.55pp (95% CI \u22120.72 to \u22120.37), 10d \u22120.30pp (\u22120.40 to \u22120.20), 5d \u22120.22pp (\u22120.27 to \u22120.17); win rate 48.3% vs 50.7% at 5 days. And the one thing a coil is supposed to do it does LESS often: a coiled name closes above its upper Keltner band within 21 sessions 38.6% of the time (CI 37.8\u201339.6) against 55.4% (54.9\u201355.9) for a name in the SAME upper half of the channel with the SAME rising 20-EMA and no squeeze \u2014 the squeeze makes that break 16.2pp LESS likely. Against that one-clause control the squeeze itself now subtracts (21d \u22120.25pp, CI \u22120.47 to \u22120.06), so the compression is not neutral, it is a drag. THE ONE POSITIVE CELL OF 2026-09-13 \u2014 a coil of 21+ bars, +1.34pp on 2,660 names \u2014 did not survive the wider list: +0.23pp (CI \u22120.44 to +0.88) over 752 names, a null. The board still sorts LONGEST COIL FIRST, as an order, not a measured ranking. Script: backend/scripts/turning_bullish_keltner_study.py, re-runnable verbatim. WHAT THE BOARD IS: the Bollinger band inside a 1.5\u00d7 Keltner channel (the squeeze) or released on the last bar, price in the upper half of the 2\u00d7 channel, and the 20-day EMA midline higher than 20 bars ago \u2014 all three, or it grades \u201cupper half\u201d and is context. Fires on 5.5% of bars; on the 2026-09-14 nightly sweep this board carried 154 of the 2,686 names it draws from. The channel is drawn as a CURVE, not three flat lines: an EMA plus an ATR multiple moves every bar, and the flat draw claimed the band sat at its latest value across the whole window (your MU catch \u2014 the midline was 921.60 sixty bars back against 960.61 now). HOW IT DIFFERS FROM STRONG VCP: that board is the book\u2019s own cited contraction with a pivot and a stop; this is Carter\u2019s TTM compression test over Raschke\u2019s EMA+ATR channel \u2014 no cited source in your library, and now measured negative. A squeeze is COMPRESSION, NOT A DIRECTION. Nothing here pushes, gates a scan, or buys in any lane. Not advice.',
  },
  amd: {
    label: '\u{1F300} AMD Raided',
    blurb: 'RE-MEASURED 2026-09-14 WITH THE FAILED PHASE, ON 3,712 NAMES, AND THE CLAIM IS STILL INVERTED \u2014 smaller than on 2026-09-13, not gone. The old detector never ended a cycle on a close through the raided edge, so bars in an already-broken base kept counting as raids \u2014 237,802 of them, as many as the real fires \u2014 which is where most of the \u22128.9pp came from. On 1,592,057 evaluated bars the state fires on 15.1% of bars. Forward returns against every other bar of the same names: 5d \u22120.36% (95% CI \u22120.77 to \u22120.06), 10d \u22120.48% (\u22121.07 to \u22120.02), 21d \u22120.41% (\u22121.11 to +0.15). The one claim this read makes \u2014 a fresh raid precedes a close above the base top within 21 sessions \u2014 against a like-for-like bar sitting INSIDE its own live base at the same distance below the top: 51.9% vs 56.1%, \u22124.2pp (CI \u22126.9 to \u22121.9), negative in all seven distance buckets. This board\u2019s own cut (raid 0\u20133 sessions ago) is worse: 48.9% vs 54.4%, \u22125.6pp (CI \u22129.0 to \u22122.7). Against that same bar the forward returns are negative too (5d \u22120.34%, CI \u22120.63 to \u22120.09; 10d \u22120.42%, \u22120.81 to \u22120.07). Raid recency separates nothing on returns (0\u20133 vs 4\u201310: every CI spans zero), so the 3-session bound is a BOARD-SIZE cut, never an accuracy gain. Script: backend/scripts/turning_bullish_amd_study.py, staged, re-runnable verbatim. WHAT THE BOARD IS: a base of 8+ bars whose whole range fits inside 3\u00d7 its own median true range had its LOW traded through and the bar CLOSED BACK INSIDE it \u2014 the stops under the base are gone and the markup through the top has not happened. A close BEYOND the edge is a breakout and means the opposite thing, so the close is the whole test; a close back THROUGH the raided edge ends the cycle as FAILED (\u2717 on the bar), and a base that re-forms after a failure reads as basing, not as a months-old failure. It fires on 15.1% of all bars; on the 2026-09-14 nightly sweep this board carried 459 of the 2,686 names it draws from (17%), still a description of the tape rather than a selection. Longest base first, because a longer base is a level more people are watching \u2014 an ORDER, not a measured ranking. This app measured AMD\u2019s nearest relative, the ICT tab, at +0.03R over 6,004 signals against placebo; this one is worse than that null. Nothing here pushes, gates or buys. Not advice.',
  },
  vcp: {
    label: 'Strong VCP',
    blurb: 'Bases whose contractions have tightened — the volatility squeeze before a breakout. Green box is the base, dashed lines the pivot and the stop.',
  },
  zones: {
    label: 'Back in Demand',
    blurb: 'Names that left a demand zone and have pulled back into it. Green band is the zone, with the buy / stop / target written on. Order (2026-09-03): the approaching boards rank closest to the level first; money flow (CMF) breaks ties within a 0.5% distance bucket; Back in Demand keeps reward:risk first. \ud83e\uddf2 marks dealer gamma from last night\'s close (same read as the GEX Board): helps = dealers dampen dips at your entry, hurts = they amplify moves; \ud83d\udee1\ufe0f/\ud83e\uddf1 flags a put/call wall sitting ON the drawn band. No chip just means the name is outside the nightly ~200-name gamma snapshot. 🧭 SPY and QQQ are pinned above this board (2026-09-16) as a strip with a CHART each — every stored band drawn on it, at two resolutions you can flip between (Fine, the finer geometry; Board, the very set the demand engine and the tiles below are drawn with) — plus the full level ladder folded underneath. Computed overnight from closed daily bars, never filtered or ordered by the controls here, and context only: they gate nothing and claim nothing.',
  },
  earnings: {
    label: 'Earnings Flow',
    blurb: "Today only. Names that reported today and were BOUGHT — big volume, closing near the day's high — plus names reporting after today's close that institutions are already accumulating into. Amber badge means the print has not happened yet.",
  },
  // Not in CM_TABS since 2026-09-03 (the slot went to `ict`). Kept so an old
  // ?tab=supply bookmark still has copy to render if it ever reaches a page
  // that indexes TAB_META directly — parseTab sends it to `ict`.
  supply: {
    label: 'Into Supply',
    blurb: 'The inverse of Back in Demand: names that have rallied INTO a tested band of overhead supply, or are about to. Red band is the ceiling, green the next support beneath it. Not a short list — it is where an advance is most likely to stall, so check it before you buy and watch it if you hold. "Room up:down" under 1.00 means more air below than above. \ud83e\uddf2 marks dealer gamma from last night\'s close (same read as the GEX Board): helps = dealers dampen dips at your entry, hurts = they amplify moves; \ud83d\udee1\ufe0f/\ud83e\uddf1 flags a put/call wall sitting ON the drawn band. No chip just means the name is outside the nightly ~200-name gamma snapshot.',
  },
  // Ajay 2026-09-03 (late): "create a new chart maps tab for ICT Strategy,
  // replace supply tab with this new tab." The concepts are his own spec +
  // Jesse Rogers' video (ICT_SOURCE); everything numeric that the video does
  // not give is an OWNER setting the backend echoes in `params`, listed under
  // the board. Purely price action — no moving averages anywhere in it, and
  // nothing from the SEPA book (that is a different strategy's authority).
  ict: {
    label: 'ICT',
    blurb: 'Purely price action, two clocks. The daily chart sets the key levels — the last swing highs and lows (3-candle fractals) and the fair value gaps still open — and the 60-minute loop stays asleep until price actually taps one of them. Then it looks for the manipulation: a wick through a key low (or the accumulation range’s lows) that fails to close through it — no displacement. Confirmation is an energetic push the other way that leaves a new fair value gap AND closes past the last swing point (the market structure shift, MSS). Entry is the inverted FVG — an old bearish gap a candle closed firmly above — or the new gap itself; the stop sits under the manipulation wick and the target is the next daily swing point (external liquidity), mirrored for the bearish side. Tiles carry State → Grade → R:R so the ones with every step in place read first. The rules are Ajay’s spec plus Jesse Rogers’ walkthrough; every threshold the video does not give (how tight a consolidation, how many bars, the tap tolerance, the stop buffer) is an owner setting shown under the board, not a claim from the source. Not advice. Backtested 2026-09-04 (200 names, 6 months, walk-forward): no edge over its own placebo — median +0.03R vs 0.00R over 6,004 signals — so read it as a study board, not a trade list.',
  },
  topping: {
    label: 'S3 Topping · Shorts',
    blurb: 'The short-side slice of the SEPA scan: Stage 3 topping or Stage 4 decline (TLSW pp.73-76) with at least two independent distribution reads — more down days on above-average volume (p.76), CMF outflow, the largest drop since the Stage 2 advance (p.90), a close below the 50-day on heavy volume, climax runs, churning and high-volume reversals (TTLAC §9). Below the 200-day is Minervini\'s own Stage 4 short trigger (TTLAC §6). Ranked by how aggressive the selling reads; declining Bonde sales shown as confirmation only, because fundamentals lag at tops. Nothing here is backtested and shorting risk is unlimited — this is a study list, not an inverted buy button.',
  },
  // Ajay 2026-09-16, verbatim: "For the deep demand stocks I need the logic to
  // be, the stocks that crosses the first level of support and lying in second
  // or third level of support. Like CRDO dropped after the earning it crossed
  // multiple support level." And, with a screenshot of a tile: "there are two
  // level of support in this chart and the price is at the second level of
  // support." So the read walks the served bands instead of the fixed first
  // pair, and the tile DRAWS every level already crossed plus the one price is
  // standing in. Depth is NOT an edge: the 2026-09-16 band-structure study
  // measured no_signal on the adjacent claim and a BIGGER first support band
  // measured harmful — so this copy describes the geometry and never ranks on it.
  deep_demand: {
    label: 'Deep Demand',
    blurb: 'Penalized price, intact business. Names that crossed one or more demand bands and are arriving at the next level down — the 2nd, the 3rd or the 4th — kept only when Pradeep Bonde\'s sales tiers (his 5% YoY floor) say revenue is still growing, so a falling knife with a dying top line never shows. These fail the trend gate by design: the market has already punished them. Red bands are the levels already crossed, each labelled 1st / 2nd / 3rd, green is the level being entered; the tile names the count once more than one was crossed. Four is as deep as this window goes: the board is served the four bands nearest the price, so three crossed levels is the arithmetic ceiling, not a preference. The 2nd \u00b7 3rd \u00b7 4th chips filter the board to the arrival levels you want \u2014 all three on is the whole board, and turning every one off means all of them rather than nothing; each chip carries how many names that level would show right now. Depth is not a measured edge \u2014 the filter narrows, it never ranks: a 4th- or 3rd-level name is not placed above a closer 2nd-level one. 💰 marks money flowing back IN while price sits at the band — CMF-20 plus up/down volume-day counts (Minervini p.71-76) — and it decides ties. Order (2026-09-03, unchanged): names inside their arrival band first, then the nearest approaching names; within a distance bucket money flow (CMF) ranks — supersedes the 2026-08-26 CMF-first order; 🔻 means sellers are still in control, shown so you know why it ranks last. \ud83e\uddf2 marks dealer gamma from last night\'s close (same read as the GEX Board): helps = dealers dampen dips at your entry, hurts = they amplify moves; \ud83d\udee1\ufe0f/\ud83e\uddf1 flags a put/call wall sitting ON the drawn band. No chip just means the name is outside the nightly ~200-name gamma snapshot.',
  },
  quick_bounce: {
    label: '\u{1FA83} Quick Reversal',
    blurb: 'Names that historically turned at a demand band THE SAME DAY — the close lifted at least 3% (or one ATR) off the low on one of the first three touch days — or gapped up 2%+ the next morning (the KLAC 09-04 shape), measured over two years of daily bars with the bands recomputed monthly on prior bars only. A name makes the list with 3+ visits and a quick rate of 50%+, and shows only while it sits inside a proven demand band or within 5% above it with 5%+ room to the first proven lid, nearest to the band first. Each rate is printed next to the name\u2019s own any-day base rate, and the study\u2019s first-half \u2192 second-half persistence sits under the board, because the 2026-08-14 study found per-name same-day-reversal rankings did not carry over. A screen for where to stand with a limit order, not a forecast. Not advice.',
  },
  breaking: {
    label: '\u{1F680} Breaking',
    blurb: 'Breaking resistance, as cards (2026-09-06). Every name of the last zone-edge pass — $1B+ names within 1% under the ceiling of their LAST supply band (nothing overhead, or the band sits at the 52-week high) or through it today by up to 3% — drawn like the demand boards: red band is the ceiling being tested, the dashed line its top, a second band the next proven lid, and Room \u2265 5% hides names with a lid straight overhead (open sky passes). Broke-today names first, then new highs, then nearest to the ceiling; prints and distances are the pass\u2019s own and its stamp sits under this line. The pass runs every minute in session and is the same read your \u{1F680} pushes come from (pushes want 2+ touches). Until 2026-09-06 this was the text list on top of Deep Demand; Deep Demand is cards only now. A structure read, not advice.',
  },
  undervalue: {
    label: 'Under Value',
    blurb: 'Incredible sales, lagging price tag (2026-08-28). The whole universe screened for Bonde strong/explosive revenue (+25% / +100% YoY floors), kept only when price-to-sales divided by growth (PSG) is \u2264 0.15 — calibrated on LightPath at ~12x sales with +109% growth. Cheapest-for-growth ranks first, zones drawn per name so the entry is a level, not a feeling. Backlogs and contracts are not machine-readable: the screen finds the divergence, you check the story. Missing revenue or share data excludes a name — nothing here is estimated.',
  },
  session: {
    label: 'Session',
    blurb: 'After the open, for entries. Every name on Back in Demand and Deep Demand, re-read on intraday bars: market mood (bullish / bearish), where price sits against the opening range, unfilled fair-value gaps with the ones left by THIS session called out, and the complete Smart-Money sequence (liquidity sweep \u2192 BOS \u2192 order block \u2192 FVG) where one exists. The daily boards pick the names; this says whether the session is confirming the daily band that listed them \u2014 "at the daily band" plus a completed setup is the entry this tab exists to find. Mood, gaps and the SMC sequence are convention, not book methods, and the ranking is this app\'s own; the opening range says "forming" until its full window has printed. Not advice.',
  },
  overnight: {
    label: 'Overnight',
    blurb: 'The overnight movers board, in Chart Maps where the rest of the scan lives. Move = the headline change (chipped PM/AH/O\u2044N only when it IS the extended-hours move); O\u2044N drift = the actual extended-session change vs the last regular close; $ Vol avg = 50-day average liquidity for context; O\u2044N $ Vol = the dollars that actually traded in tonight\u2019s extended session (top names only \u2014 that is the real overnight volume). RelVol \u22651.5\u00d7 = elevated interest, <1\u00d7 = thin tape. Same data as the Day Trading page\u2019s scan. Not advice.',
  },
  // Ajay 2026-09-05: "also move catalyst tab in to Chart maps ... for
  // catalyst same deal make sure you sort stocks by bigger gaps in to supply
  // like EOSE stock and CLYM as an example they have bigger gap and room to
  // grow." Room and bounce come from the same configured zone engine as the
  // Demand board (owner settings) — nothing from the SEPA book here.
  catalysts: {
    label: '\u{1F5DE}️ Catalysts',
    blurb: 'Microcaps and sub-$20 names moving on a fresh catalyst or social chatter, scored on two axes — chatter (Stocktwits + Reddit) against evidence (SEC filings, news, insider trades) — so a real setup reads apart from a pump where the crowd is loud and the paperwork is silent. Moved here from its own page on 2026-09-05; /catalysts links land on this tab. Cards now lead with room to the first supply band overhead: open sky (nothing overhead in the 1-year frame) first, then the biggest gap — the EOSE / CLYM shape — and 🪃 flags a name reversing off a demand band or a broken-supply shelf within the last 5 sessions. Room and the reversal read are a configured price-structure read (owner settings, shared with the Demand board), not advice; a name whose zones are still being built says "room pending" and sorts last rather than disappearing.',
  },
  gabbar: {
    label: 'Gabbar Levels',
    blurb: 'Hand-curated buy zones from Gabbar\'s Price Levels (veerenj on TradingView) — expert judgment stored as numbers, not a computation. Names touching or within 3% of a band sort first, and 🛡️ marks one at its CONSERVATIVE band — the author\'s deeper discount level — which leads its group over an aggressive-band touch; each tile\'s Conserv. stat shows where that deeper entry sits. The Bonde sales read still runs: a covered name with declining revenue wears a 📉 chip and ranks last in its group — a hand-drawn level under a shrinking business is the knife, so it is flagged, not hidden. Check the snapshot date in the note — old levels describe an old chart.',
  },
  support: {
    label: 'Support Levels',
    blurb: 'Any ticker, on demand. The zoom changes the answer on purpose — a 1-month read finds the level this week\'s trade is standing on, a 1-year read finds the structural floor. Green bands are support below, red overhead; a ● marks a level price has actually tested recently.',
  },
  zero_dte: {
    label: '0DTE Options',
    blurb: 'Same-day expiry, calls and puts. "0.4x" means the underlying needs four tenths of today\'s expected move for the contract to double — the only figure comparable across names, since a 1% day is a crash in SPY and a Tuesday in TSLA. Read the badge first: PINNED means dealers suppress movement and you are fighting them, AMPLIFYING means they push it along. Theta on a 0DTE routinely exceeds the entire premium in a day. Every suggestion here is recorded and graded, because nothing about it has been backtested — there is no intraday option history to backtest against.',
  },
  patterns: {
    label: '\u{1F4D0} Chart Patterns',
    blurb: 'Named bullish reversal patterns on the daily frame \u2014 cup-with-handle, double bottom, triple bottom, inverse head-and-shoulders \u2014 with the confirmation line, the measure-rule target and the stop on every card. Moved here from its own page on 2026-09-09; /patterns links land on this tab. SAID PLAINLY: in your own ledger, across 669 resolved observations, not one of these beats a 50% placebo (cup-with-handle 45% over 434, double bottom 43% over 248, triple bottom 37% over 68, inverse head-and-shoulders 10% over 10), and flat_top is excluded outright because it fired on 120 of 120 random names. Each pattern links straight to \u{1F3C6} Past Winners filtered to itself \u2014 the charts from your ledger that actually reached target before stop \u2014 which is the honest way to use this board: to learn what a working base looked like, not as a signal. Phone pushes for these are gated on the name also being IN a demand zone or reversing off one. Not advice.',
  },
  winners: {
    label: '\u{1F3C6} Past Winners',
    blurb: 'Setups from your own ledger that reached their measure-rule target before their stop. The dotted line is the confirmation bar — study what the base looked like BEFORE it.',
  },
};

export type CmQuickBouncePersistence = {
  split_date?: string; names?: number; quartile?: number;
  top_q_first_half_pct?: number; top_q_second_half_pct?: number;
  bottom_q_second_half_pct?: number; gap_pts?: number; rank_corr?: number | null; note?: string;
};
export type CmQuickBounceStudy = {
  as_of?: string; universe?: number; studied?: number; events?: number; quick?: number;
  same_day?: number; gap_up?: number; quick_rate_pct?: number | null;
  first_day_rate_pct?: number | null; placebo_rate_pct?: number | null; edge_pts?: number | null;
  qualifying?: number; persistence?: CmQuickBouncePersistence | null;
  params?: Record<string, number> | null;
};

/** One-line read of the Quick Bounce study for the strip under the board.
 *  Pure so the wording is testable; '' when there is no study yet. */
export function quickBounceStudyText(s?: CmQuickBounceStudy | null): string {
  if (!s || s.events == null) return '';
  const pct = (v?: number | null) => (v == null ? '—' : `${Math.round(v)}%`);
  const parts = [
    `${s.studied ?? '—'} names · ${s.events} band visits`,
    `quick ${pct(s.quick_rate_pct)} vs ${pct(s.placebo_rate_pct)} on any day` +
      (s.edge_pts == null ? '' : ` (${s.edge_pts >= 0 ? '+' : ''}${Math.round(s.edge_pts)} pts)`),
    `first-day ${pct(s.first_day_rate_pct)}`,
    `${s.qualifying ?? 0} on the list`,
  ];
  return parts.join(' · ');
}

/** The persistence verdict in words: does a high quick rate carry over? */
export function quickBouncePersistenceText(p?: CmQuickBouncePersistence | null): string {
  if (!p || p.gap_pts == null || p.top_q_second_half_pct == null || p.bottom_q_second_half_pct == null) {
    return p?.note ? `Persistence: ${p.note}.` : '';
  }
  const carry = p.gap_pts >= 10 ? 'carries over' : p.gap_pts >= 5 ? 'carries over weakly' : 'does not carry over';
  const rho = p.rank_corr == null ? '' : `, rank corr ${p.rank_corr.toFixed(2)}`;
  return `Persistence: names ranked in the top quarter by their first-half quick rate ran ${Math.round(p.top_q_second_half_pct)}% in the second half vs ${Math.round(p.bottom_q_second_half_pct)}% for the bottom quarter (${p.gap_pts >= 0 ? '+' : ''}${Math.round(p.gap_pts)} pts${rho}) — the ranking ${carry}.`;
}

/** `s` marks an extended-hours bar ('pre' | 'ah') on the live frame so the
 *  chart can shade it; absent on regular-hours and daily bars. */
export type CmBar = { t: string; o: number; h: number; l: number; c: number; v: number; s?: string };
// `neutral` is a range that is neither a floor nor a lid — the 0DTE gamma
// walls, which bracket where dealer hedging is expected to contain the tape.
// Colouring it green or red would imply a direction it does not have.
export type CmBand = { kind: 'base' | 'demand' | 'supply' | 'neutral' | 'board_demand' | 'board_supply'; lo: number; hi: number; label?: string };
// The last four are the 2026-09-12 study overlays. They were missing from
// this union, so `toneColor` and `TONE_PRIORITY` had no case for them and
// every study line rendered grid-grey with a droppable label.
export type CmLineTone = 'buy' | 'stop' | 'target' | 'now' | 'neutral'
  | 'amd' | 'fib' | 'meanrev' | 'keltner'
  // 2026-09-14: the two lines the 📁 My holdings tab adds on a name he owns —
  // his cost, and the stop he typed on the Portfolio page. Their own tones
  // so the `trade` checkbox (BUY / STOP / TARGET of a plan) never hides them.
  | 'cost' | 'ownstop';
/** `quiet` (2026-09-14): the backend flags BOS / swept / ORB lines it wants
 *  drawn but not fought over — the label yields to the plan labels under
 *  pressure (priority 0) while the line itself still draws. The flag was sent
 *  for weeks with no consumer; "BOS 211.50" carried a STOP tone at priority 3
 *  and could push the real support label off the gutter. */
export type CmLine = { price: number; label: string; tone: CmLineTone; quiet?: boolean };
export type CmTapeSession = 'premarket' | 'rth' | 'afterhours' | 'closed';
export type CmMarker = { date: string; label?: string; kind?: string; price?: number };
export type CmStat = { k: string; v: string };
export type CmBadge = {
  text: string; tone: 'good' | 'warn' | 'muted';
  /** Overlay family this badge belongs to, when it belongs to one. Present on
   *  the study verdicts (`keltner`, `amd`) so `filterTile` can drop the
   *  SENTENCE along with that family's bands and lines — one checkbox governs
   *  the drawing and the words together. A badge with no group is a board
   *  badge (Setup ready, Vol drying) and is never filtered. */
  group?: string;
};

/** A per-bar overlay: one value per tile bar, `null` where there is none.
 *
 *  Ajay 2026-09-13 (MU): "I was hoping to see the KC bands like this but it
 *  should flat horizontal." A `CmLine` is ONE price and renders as a
 *  horizontal level, which is right for a pivot, a stop or a band edge and
 *  wrong for a Keltner channel — an EMA plus an ATR multiple moves every bar.
 *  `values` is aligned 1:1 with `tile.bars`; a null is a GAP in the drawn
 *  path, never a point joined through. */
export type CmCurve = { tone: CmLineTone; label: string; values: (number | null)[] };

export type CmTile = {
  symbol: string;
  name?: string | null;
  href: string;
  bars: CmBar[];
  bands: CmBand[];
  lines: CmLine[];
  markers: CmMarker[];
  stats: CmStat[];
  why: string;
  theme?: string | null;
  badges?: CmBadge[];
  curves?: CmCurve[];
  pattern?: string | null;
  /** 🧨 The explosive read for this name (chart_maps/board.attach_explosive,
   *  2026-09-15) — served on every tile board request whatever the sort, so the
   *  chip never costs a second fetch. null = no demand band under the print, a
   *  legacy doc, or no read yet; the chip then renders nothing and the tile
   *  sorts LAST under the explosive sort. */
  explosive?: ExplosiveRead | null;
  /** 🎯 The enterable read for this name (chart_maps/board.attach_enterable,
   *  2026-09-15) — taken on the SAME live snapshot the now-line uses, so the
   *  tile chip and the phone read the same print. null = no read (a legacy
   *  doc, a dead store, a tile the fan-out missed); the chip then renders
   *  nothing and the filter NEVER hides it. */
  enterable?: EnterableRead | null;
  /** 🪜 The band-structure read for this name (chart_maps/board
   *  .attach_band_structure, 2026-09-16) — the ceiling above the print and the
   *  floor under it, served on every tile board request whatever the sort, and
   *  keyed on the SAME live snapshot the now-line uses (a ceiling "0.5% up"
   *  measured off yesterday's close is the wrong number for a name that has
   *  already traded into the band this morning). null = no doc, no bands, or a
   *  name the fan-out missed; the chip then renders nothing and the tile sorts
   *  LAST under the band-structure sort. `applicable: false` = a tab whose rows
   *  are not price-structure bands at all. */
  band_structure?: BandStructureRead | null;
  /** 🩹 Deep Demand only (chart_maps/board.deep_demand_tiles, 2026-09-16): how
   *  many demand levels price has already crossed on its way to the band it is
   *  standing in — 1 for a 2nd-level arrival, 2 for a 3rd. The arrival level
   *  itself is `levels_broken + 1`, which is what the badge and the band labels
   *  say, so the FE never computes an ordinal of its own. Absent on every other
   *  tab and on a Deep Demand row served from a cache written before this
   *  shipped; read it as 1 there, never as 0 — the board has always required at
   *  least one crossed band. It orders NOTHING: depth is unmeasured (the
   *  2026-09-16 band-structure study read no_signal on the adjacent claim). */
  levels_broken?: number;
};

/** 🪜 The tile path's coverage block (chart_maps/board.py
 *  ::band_structure_coverage, 2026-09-16). Counts, plus the one SERVED
 *  sentence to print when not one shown tile came back with a read — the same
 *  string the ten row boards already print
 *  (`bounce_room.BAND_STRUCTURE_NO_READ`), so "no band read" is worded once for
 *  the whole app. `note` is null whenever anything DID read, and on an n/a tab,
 *  whose own n/a sentence is the right one there. */
export type BandStructureCoverage = {
  tiles_with_read?: number;
  tiles_without_read?: number;
  note?: string | null;
};

export type CmPatternRecord = {
  pattern: string; label: string;
  wins: number; losses: number; n: number; win_pct: number | null;
};

export type CmSort = { key: string; label: string };

export type CmLidBreak = {
  as_of?: string | null;
  events?: number | null;
  names?: number | null;
  universe?: number | null;
  hit_52w_21_pct?: number | null;
  hit_52w_21_n?: number | null;
  hit_52w_63_pct?: number | null;
  hit_52w_63_n?: number | null;
  placebo_any_21_pct?: number | null;
  placebo_up_21_pct?: number | null;
  placebo_any_63_pct?: number | null;
  placebo_up_63_pct?: number | null;
  failed_21_pct?: number | null;
  median_days_to_52w_63?: number | null;
  median_runup_21_pct?: number | null;
  median_runup_63_pct?: number | null;
  proven_hit_52w_21_pct?: number | null;
  proven_n?: number | null;
  single_hit_52w_21_pct?: number | null;
  single_n?: number | null;
  volc_hit_52w_21_pct?: number | null;
  volc_n?: number | null;
  dist?: Record<string, { pct?: number | null; n?: number | null }> | null;
  persistence?: CmQuickBounceStudy['persistence'];
  disclaimer?: string | null;
};

/* ── 🧭 SPY / QQQ index zones (2026-09-16) ───────────────────────────────────
 *
 * Ajay, verbatim: "Can you create a SPY demand and supply zone please for me?
 * and also QQQ supply and demand zone and keep them always in the in demand
 * zone page. I need everything calculation overnight."
 *
 * Served by backend/supply_demand/index_zones.py off the 04:05 ET zone_store
 * warm and STORED — the page reads one doc a night and re-derives no band. The
 * shape below is the contract both sides code against; the frontend adds
 * nothing to it and computes no level of its own.
 *
 * TWO BASES, IN TWO SETS OF KEYS. `close` / `bands` / `ceiling` / `floor` /
 * `room_pct` / `drop_pct` / `sentence` are all read off the CLOSED bars of
 * `as_of`. The `live_*` keys are the live-print overlay applied at read time
 * by index_zones.with_live(); they say where price is standing and never move
 * a band. A read built at 04:20 and the same read at 15:00 carry identical
 * stored keys — that is the whole point of the split.
 */
export type CmIndexZoneBand = {
  kind: 'supply' | 'demand';
  lo: number; hi: number; mid?: number;
  touches?: number; strength?: number;
  /** Where the CLOSED-bar close sits relative to this band. */
  side?: 'above' | 'below' | 'in';
  dist_pct?: number | null;
};

/** The nearest band above (`ceiling`) or below (`floor`) — ANY kind, because
 *  broken support is resistance. Both null when the stored structure has none
 *  on that side.
 *
 *  `kind` (2026-09-16) is the band's ORIGIN, and it is printed: Ajay's note
 *  from Pankaj Kenjale says "when a demand zone is broken, it becomes a supply
 *  zone and similarly when a supply zone is broken, it becomes a demand zone",
 *  which is already how the engine picks these two — nearest on each side,
 *  whatever it started as. A ceiling that reads "demand" is support price has
 *  gone under, and that fact is invisible if only the colour carries it. */
export type CmIndexZoneEdge = {
  lo: number; hi: number; dist_pct?: number | null;
  kind?: 'supply' | 'demand' | null;
};

/** ONE geometry's worth of a read. The backend serves two under
 *  `CmIndexZoneRead.resolutions` (2026-09-16), on Ajay's "I wanna see charts
 *  with multiple zones":
 *    board — demand_reentry.zone_geom(), the geometry the demand engine and
 *            every tile on the Chart Maps grid already draw with (7 bands on
 *            each index, median band ~3% wide).
 *    fine  — the price_zones module's own defaults (14 bands on SPY, 13 on
 *            QQQ, median band ~1.1% wide).
 *  Both are EXISTING settings; neither number was invented for this strip, and
 *  neither was taken off a hand-drawn note (gabbar_backtest_2026_08_31: hand
 *  levels are contaminated as a measurement). Same closed bars behind both. */
export type CmIndexZoneResolution = {
  bands?: CmIndexZoneBand[];
  in_band?: CmIndexZoneBand | null;
  ceiling?: CmIndexZoneEdge | null;
  floor?: CmIndexZoneEdge | null;
  room_pct?: number | null;
  drop_pct?: number | null;
  sentence?: string | null;
  /* THE LIVE OVERLAY IS PER RESOLUTION (2026-09-16 review). `with_live`
   * recurses into each set, because where the print sits depends on which
   * bands you are looking at: a print that is INSIDE a ~3%-wide board band is
   * routinely BETWEEN two ~1.1%-wide fine bands. The strip reads these off the
   * set it is drawing (izLiveSource); reading the flat keys under a fine chart
   * named a band that was on no visible surface. */
  live_px?: number | null;
  live_side?: 'above' | 'below' | 'in' | 'between' | null;
  live_in_band?: CmIndexZoneBand | null;
  live_dist_pct?: number | null;
  live_chg_pct?: number | null;
  price_basis?: string | null;
};

export type CmIndexZoneRead = {
  symbol: string;
  name?: string | null;
  /** The CLOSED-bar date the bands were drawn from. Every stored number on the
   *  read is on this session; the page prints it over them. */
  as_of?: string | null;
  close?: number | null;
  atr14?: number | null;
  high_252?: number | null;
  /** High → low, the backend's order. Never re-sorted on the page. */
  bands?: CmIndexZoneBand[];
  in_band?: CmIndexZoneBand | null;
  ceiling?: CmIndexZoneEdge | null;
  floor?: CmIndexZoneEdge | null;
  room_pct?: number | null;
  drop_pct?: number | null;
  /** ONE plain line naming where price sits, built by the backend from the
   *  numbers. Never a verdict and never advice. */
  sentence?: string | null;
  source?: string | null;
  /** The two geometries, keyed `board` / `fine` (2026-09-16). The flat keys
   *  above stay populated for a doc written before this shipped, and the strip
   *  falls back to them — a legacy doc renders a full card and no toggle. */
  resolutions?: Record<string, CmIndexZoneResolution | null | undefined> | null;
  /** Which resolution to open on. The backend sends 'fine'. */
  default_resolution?: string | null;
  /** CLOSED daily bars, windowed by the backend to hold every band in either
   *  resolution — the chart the strip draws (Ajay 2026-09-16: "I wanna see
   *  charts with multiple zones"). Never carries today's partial bar, and a
   *  live print is never appended to it. */
  bars?: CmBar[];
  /* The live overlay — its own keys, applied at read time, never merged over
   * the stored ones above. */
  live_px?: number | null;
  live_dist_pct?: number | null;
  live_in_band?: CmIndexZoneBand | null;
  /** Measured against the WHOLE stored structure: 'in' a band, 'above' every
   *  band, 'below' every band, or 'between' two of them and inside none. The
   *  last one is the open-air case, and it is emitted. */
  live_side?: 'above' | 'below' | 'in' | 'between' | null;
  /** The backend's own label for what the live number is. Printed verbatim. */
  price_basis?: string | null;
};

export type CmIndexZones = {
  /** The stored day. */
  date?: string | null;
  indexes?: Record<string, CmIndexZoneRead | null | undefined> | null;
  /** CALENDAR days since the stored day — NOT sessions. A Friday doc read on
   *  Monday is 3 calendar days and 1 session old, and printing the 3 beside the
   *  word "session" is a different number wearing the wrong word. Printed, and
   *  only ever as calendar days. */
  stale_days?: number | null;
  /** TRADING sessions since the stored day (2026-09-16). This is the one the
   *  header prints as "N sessions old". Printed, never a gate. */
  stale_sessions?: number | null;
  /** Which resolution the strip opens on. The backend names it at the PAYLOAD
   *  level, not per read — reading it off a read was always undefined on the
   *  wire, and the page only opened on fine because a local fallback said so
   *  (2026-09-16 review). */
  default_resolution?: string | null;
  note?: string | null;
};

export type CmBoard = {
  tab: CmTab;
  count: number;
  /** The sort actually applied. The winners tabs read a ledger with no live
   *  volume, so the backend answers `theme` there and sends an empty `sorts`. */
  sort?: string;
  sorts?: CmSort[];
  /** Liquidity floor by 50-day average $ volume, same tiers as Back in Demand. */
  min_tier?: string;
  tiers?: CmSort[];
  /** How many names the floor removed. Shown so a shrunken board is explained
   *  rather than just smaller. */
  dropped_thin?: number;
  /** Demand boards only — names hidden because price already ran >= bounce_done_pct
   *  off the band top (Ajay 2026-09-03: the arrival is over). */
  dropped_bounced?: number;
  bounce_done_pct?: number;
  /** Demand boards only (2026-09-05) — the room floor the server applied on the
   *  LIVE print (% to the first unbroken band overhead; ALERT_MIN_ROOM_PCT,
   *  owner setting) and how many tiles it hid. Ajay: "stocks that have more
   *  room atleast >5%". 0 = floor off. */
  min_room?: number;
  /** The HOUSE floor the server would have used had the board not asked for
   *  one (`board._room_meta` → `room_floor.MIN_ROOM_DEFAULT`, 2026-09-17). It
   *  is what "default" means in the toolbar, served rather than retyped, so a
   *  change to the owner setting reaches the page without a frontend edit.
   *  Absent on a cache written before this shipped; the page falls back to its
   *  own mirror (DEFAULT_MIN_ROOM). */
  min_room_default?: number;
  hidden_low_room?: number;
  /** 🩹 Deep Demand only (2026-09-16) — the arrival-level filter, echoed back.
   *  `"all"` (the default) or the normalised ascending comma list the server
   *  actually applied, e.g. `"3,4"`. Absent on every other tab and on a cache
   *  written before this shipped; the page then reads it as "all". */
  levels?: string;
  /** 🩹 Deep Demand only (2026-09-16) — how many tiles EACH arrival level would
   *  show under the CURRENT phase / room / sales settings but with the level
   *  filter OFF, keyed by level ("2" | "3" | "4"). This is what the chips
   *  display, so it is deliberately NOT computed after the filter: a chip whose
   *  count changed because it is switched off would be a lie about the board. */
  level_counts?: Record<string, number>;
  /** 🩹 Deep Demand only (2026-09-16) — how many tiles the level filter hid on
   *  THIS call. 0 / absent when every level is selected. */
  hidden_by_level?: number;
  /** 🌀 AMD / Keltner (2026-09-17): which grades this payload IS, every grade
   *  it could be, and how many names sit at each in the whole sweep. The chips
   *  render from `grades_all` so the choices come from the backend's enforcing
   *  tuple, and the counts are taken with the filter OFF — a count that moved
   *  because a chip is unselected would be a lie about the board. */
  grades?: string[];
  grades_all?: string[];
  grade_counts?: Record<string, number>;
  /** 🔻 AMD in flight (2026-09-17): which live states this payload is filtered
   *  to, every state there is, and how many names sit in each RIGHT NOW. The
   *  counts are read live and are unconfirmed until the close. */
  flight?: string[];
  flight_states?: string[];
  flight_counts?: Record<string, number>;
  /** 🚀 Breaking (2026-09-06): the zone-edge pass the cards were drawn from. */
  pass_as_of?: string | null;
  pass_date?: string | null;
  in_session?: boolean;
  reason?: string | null;
  edge_counts?: Record<string, number> | null;
  /** Every tab (2026-09-08, Ajay: "show real time premarket and extended hours
   *  trading info as well in all the chart maps") — the clock the board was
   *  read on. Outside RTH every tile's `now` line already sits on the live
   *  print (tagged `now · pre` / `now · AH`); the board says so once. */
  tape_session?: CmTapeSession | null;
  /** Quick Bounce only (2026-09-06) — the weekly study's universe numbers and
   *  its persistence check, printed under the board so the list is read
   *  against its own evidence. */
  study?: CmQuickBounceStudy | null;
  /** \u{1F680} Breaking only (2026-09-07) — the weekly last-lid-break study, pooled
   *  (supply_demand/lid_break.board_meta): does breaking the LAST supply band carry
   *  price to the prior 52-week high? Printed under the pass line. */
  lid_break?: CmLidBreak | null;
  qualifying?: number;
  no_band?: number;
  no_print?: number;
  store_date?: string | null;
  /** 0DTE only — the same-day expiry these chains are read from. */
  expiry?: string;
  /** 0DTE only — where in the trading day this read happened. After the close
   *  on expiry day the chain has SETTLED, and a board that is nearly empty is
   *  correct rather than broken. The banner says which. */
  session?: { state: string; label: string; actionable: boolean } | null;
  /** 0DTE only — names with a same-day chain, and how many of those carry any
   *  contract clearing the cost floors. The gap between them is the point. */
  with_chain?: number;
  with_contract?: number;
  cached_age_sec?: number;
  /** Sorts that need an intraday tape pull, and how far it got. */
  tape_sorts?: string[];
  tape_pool?: number;
  tape_enriched?: number;
  /** Set when the chosen sort's column came back empty for every row — the
   *  board is showing its default order and says so. */
  sort_unavailable?: string | null;
  /** The explosive study's served verdict (2026-09-15), rendered in the
   *  coverage strip. Numbers live in backend/supply_demand/explosive.py::MEASURED
   *  and are never typed into a board. */
  explosive_study?: ExplosiveStudy | null;
  /** 🎯 Which read this tab's rows get (chart_maps/board, 2026-09-15) — the
   *  SERVED mirror of enterable.KIND_BY_TAB. The page prefers it over the
   *  local ENTERABLE_KIND map so moving a tab between `demand` and `n/a` is a
   *  backend change, not a frontend deploy. */
  enterable_kind?: EnterableKind | string | null;
  /** 🎯 The entry-trigger study's served verdict (2026-09-15), rendered in the
   *  coverage strip. Every number lives in
   *  backend/supply_demand/enterable.py::MEASURED and is never typed here. */
  enterable_study?: EnterableStudy | null;
  /** 🪜 Which read this tab's rows get (chart_maps/board, 2026-09-16) — the
   *  SERVED mirror of enterable.KIND_BY_TAB via band_structure.kind_for_tab, so
   *  moving a tab between `demand` and `n/a` is a backend change, not a
   *  frontend deploy. */
  band_structure_kind?: string | null;
  /** 🪜 The n/a sentence at the PAYLOAD level, for a tab whose kind is `n/a`.
   *  The per-tile `band_structure.na_text` is the usual carrier; this one is
   *  what a board with ZERO tiles can still say (0DTE outside the session),
   *  where taking the sentence off the first tile said nothing at all.
   *  Optional: when it is absent the page falls back to the pinned mirror of
   *  band_structure.NA_TEXT rather than going silent. */
  band_structure_na_text?: string | null;
  /** 🪜 The band-structure study's served verdict (2026-09-16), rendered in the
   *  coverage strip. Every number lives in
   *  backend/supply_demand/band_structure.py::MEASURED and is never typed here.
   *  It reads `no_signal`: the study ran, nothing separated, so the ordering
   *  ships DESCRIPTIVE and the banner says so. */
  band_structure_study?: BandStructureStudy | null;
  /** 🪜 Who came back with a read, and the SERVED sentence to print when NOT
   *  ONE of the shown tiles did (chart_maps/board.py::band_structure_coverage,
   *  2026-09-16). The tile path had no such note: a name the $1B zone store has
   *  not warmed drew a tile with no Bands line and NO REASON, while the ten row
   *  boards — which build the doc on demand — served the read for the same name
   *  on the same day (BTBT, one of his own positions). The sentence is the row
   *  boards' own (`bounce_room.BAND_STRUCTURE_NO_READ`), served rather than
   *  typed here so the two surfaces cannot word one fact two ways; `note` is
   *  null on an n/a tab, which carries `band_structure_na_text` instead. */
  band_structure_coverage?: BandStructureCoverage | null;
  /** 🪜 What the ordering could actually reach (band_structure.BOARD_SCOPE_NOTE)
   *  — set ONLY when the band-structure sort ran and worked. The sort is applied
   *  after the board was cut to `limit`, so it ranks the page rather than the
   *  universe behind it, and the page says that out loud instead of letting
   *  "thinnest ceiling first" quietly mean "first among the default top N".
   *  null when the sort was not chosen, or when it could not run (the reason is
   *  then in `sort_unavailable`). */
  band_structure_scope?: string | null;
  /** 🧭 SPY / QQQ, pinned to the Back in Demand tab (2026-09-16). Computed
   *  overnight and stored; the strip renders in EVERY state of the board and
   *  is never filtered, ordered or gated by the controls above it. Absent on
   *  every other tab, and absent here until the nightly job has run — the
   *  strip draws its own placeholder rather than vanishing. */
  index_zones?: CmIndexZones | null;
  tiles: CmTile[];
  disclaimer?: string;
  note?: string;
  warming?: boolean;
  /* The demand tab's live scan counter. Same scan the Back in Demand tab on
   * /supply-demand watches — both tabs read one demand_reentry cache, so they
   * must show one progress reading (Ajay 2026-08-17). */
  progress?: DemandScanProgress | null;
  matched?: number;
  /** gabbar tab: the band-type lens the server measured against, its menu,
   *  and how many covered names had no band of that type. */
  level?: string;
  level_choices?: string[];
  without_level?: number;
  touching_only?: boolean;
  away_hidden?: number;
  scanned?: number;
  universe_key?: string;
  universe_label?: string;
  /** The universes the SERVER offers. Preferred over the frontend's
   *  fallback list so adding one backend-side needs no FE deploy. */
  universe_choices?: { key: string; label: string }[];
  generated_at?: string | number | null;
  scan_generated_at?: string | number | null;
  /** ict tab (2026-09-03): when the engine last scanned, how far the dormant
   *  loop got (macro pass → tapped names → micro runs), every owner constant
   *  with its value, and the source the rules are cited to. `params` is
   *  rendered verbatim under the board so a changed threshold is visible
   *  without a frontend deploy. */
  as_of?: string | null;
  counts?: { macro_n?: number; tapped_n?: number; micro_n?: number } | null;
  /** The backend (ict/engine.py params()) sends a LIST of {key, value,
   *  from_video, note} so the two values the video actually states are never
   *  listed as house rules; a flat {key: value} map is accepted too. */
  params?: IctParamIn[] | Record<string, number | string | boolean | null> | null;
  source?: {
    video?: string | null;
    /** Plain stamps ("02:39") or {at, rule} objects — ictSource() renders both. */
    timestamps?: (string | { at?: string | null; rule?: string | null } | null)[] | null;
  } | null;
  patterns?: string[];
  excluded_already_past_target?: number;
  record?: {
    overall: { wins: number; losses: number; n: number; win_pct: number | null };
    by_pattern: CmPatternRecord[];
    caveat: string;
  };
};

/* ── tab plumbing ─────────────────────────────────────────────────────────── */

/** Coerce a `?tab=` value. An unknown tab lands on the first one rather than
 *  rendering an empty board — a mistyped deep link should still show charts. */
export function parseTab(raw: string | null | undefined): CmTab {
  const t = (raw || '').trim().toLowerCase();
  // The Into Supply slot was replaced by ICT on 2026-09-03 (Ajay: "replace
  // supply tab with this new tab"). An old ?tab=supply bookmark lands on the
  // tab that took its place rather than falling back to the first tab — same slot,
  // same neighbourhood, and the backend still resolves "supply" on its side.
  if (t === 'supply') return 'ict';
  return (CM_TABS as string[]).includes(t) ? (t as CmTab) : DEFAULT_TAB;
}

/* ── ICT tab (Ajay 2026-09-03) ────────────────────────────────────────────── */

/** Where the rules come from — Ajay's own spec plus this walkthrough. The
 *  timestamps are the ones cited in backend/ict/ for each rule; the backend
 *  echoes the same URL in the board's `source`, this copy is for the blurb
 *  link when the board has not loaded yet. */
export const ICT_SOURCE = {
  label: 'Jesse Rogers',
  url: 'https://www.youtube.com/watch?v=Q7Ryv1M7CvI',
  timestamps: [
    { at: '02:39', rule: 'manipulation = a sweep with no displacement' },
    { at: '03:57', rule: 'stacked consolidations on the way to a higher-timeframe FVG' },
    { at: '05:30', rule: 'Power of 3 — accumulation range first, then the manipulation below it' },
  ],
} as const;

export type IctBias = 'all' | 'bullish' | 'bearish';
export type IctMicro = '60m' | '15m';

/** Server defaults — kept OUT of the query string when unchanged so the
 *  common URL stays clean and one cache key serves the default board. */
export const DEFAULT_ICT_BIAS: IctBias = 'all';
export const DEFAULT_ICT_MICRO: IctMicro = '60m';

export const ICT_BIASES: { key: IctBias; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'bullish', label: 'Bullish' },
  { key: 'bearish', label: 'Bearish' },
];

/** The trigger timeframe. 60m is the video's "micro" clock; 15m is offered
 *  because the same frame_for() resample serves it — nothing else changes. */
export const ICT_MICROS: { key: IctMicro; label: string }[] = [
  { key: '60m', label: '60m' },
  { key: '15m', label: '15m' },
];

/* ── room floor (Ajay 2026-09-05) ─────────────────────────────────────────── */

/** The two boards the floor applies to. Their tiles are demand arrivals; a
 *  tile 0.3% under a supply band (TRU, 2026-09-05) is not one worth showing.
 *  The other tabs have no room read and never receive the param. */
export const ROOM_TABS: CmTab[] = ['zones', 'deep_demand', 'quick_bounce', 'breaking'];

/** Frontend mirror of ALERT_MIN_ROOM_PCT (backend/supply_demand/alert_gates.py,
 *  owner setting) — the phone's gate and now the demand boards' floor. Same
 *  constant as lib/bounceRoom.ts ROOM_MIN_PCT; re-declared here so this file
 *  stays dependency-free (it is imported by the chart primitives). */
export const DEFAULT_MIN_ROOM = 5;

/** `?room=` → the floor. Two values only: `any` (or `0`) turns it off, every
 *  other value — including a typed number Ajay never chose — is the floor. */
export function parseMinRoom(raw: string | null | undefined): 5 | 0 {
  if (raw === 'any' || raw === '0') return 0;
  return DEFAULT_MIN_ROOM;
}

/* ── 🩹 Deep Demand arrival level (Ajay 2026-09-16: "can you do level 4 and
 *     give me filters for that") ──────────────────────────────────────────── */

/** The arrival levels the SERVED window can express. Price is standing in the
 *  2nd, 3rd or 4th demand band; anything deeper is not a policy choice, it is
 *  arithmetic — the board is served `price_zones.nearest_first(...)[:4]`, so at
 *  most three bands can sit above the arrival band (backend mirror:
 *  deep_demand.MAX_LEVELS_BROKEN = PZ.MAX_ZONES_PER_SIDE - 1).
 *
 *  It is a FILTER, never an ordering: depth is unmeasured (the 2026-09-16
 *  band-structure study read `no_signal` on the adjacent claim), so a 4th-level
 *  name must never outrank a closer 2nd-level one. */
export const DEEP_LEVELS: readonly number[] = [2, 3, 4];

/** The ordinal the chips and the tile badges say. Read from here rather than
 *  built with a suffix rule, so "1st/2nd/3rd" is worded once. */
export const DEEP_LEVEL_LABEL: Record<number, string> = { 2: '2nd', 3: '3rd', 4: '4th' };

/** The AMD / Keltner grades in Ajay's vocabulary (2026-09-17).
 *
 *  The KEYS stay the backend's (`turning_bullish.AMD_GRADES` /
 *  `KELTNER_GRADES`) so a label can never become a second definition of a
 *  grade; only the wording is ours. A grade the server adds that this map has
 *  not caught up with renders as its own key rather than vanishing from the
 *  filter — a missing chip would hide names, which is the one thing a filter
 *  must never do quietly. */
export const AMD_GRADE_LABEL: Record<string, string> = {
  raided: '\u{1F300} Manipulated',
  basing: '\u{1F7E6} Accumulating',
  marked_up: '\u{1F4C8} Distributed',
  failed: '\u2717 Base failed',
  stale: '\u23F3 Stale raid',
  breaking_up: '\u2197 Breaking up',
  coiled_up: '\u{1FA22} Coiled',
  upper_half: '\u25B2 Upper half',
  lower_half: '\u25BC Lower half',
};

/** The AMD cycle IN FLIGHT (2026-09-17) — where a name is against its base
 *  edge RIGHT NOW, before tonight's close confirms anything.
 *
 *  Ajay: "Today its not granular we do not show potentially or in the flight
 *  mani pulation i wanna see those". The stored detector only fires on a
 *  COMPLETE raid, so a sweep in progress is invisible until the sweep re-runs.
 *  Keys are the backend's `AMD_FLIGHT_STATES`; only the wording is ours. */
export const AMD_FLIGHT_LABEL: Record<string, string> = {
  sweeping: '\u{1F53B} Sweeping now',
  reclaimed: '\u{1F504} Reclaimed today',
  holding: '\u{1F6E1}\uFE0F Holding the edge',
};

/** The flight states a URL asks for. Same fail-open rule as the grades. */
export function parseFlight(raw: string | null | undefined): Set<string> {
  const out = new Set<string>();
  for (const part of String(raw || '').split(',')) {
    const k = part.trim().toLowerCase();
    if (k) out.add(k);
  }
  return out;
}

/** The `flight=` value for a selection, or null when every state is on (which
 *  is the same board as no filter, so it must not ride). */
export function flightParam(sel: Set<string>, all?: string[]): string | null {
  if (!sel.size) return null;
  if (all && all.length && all.every((g) => sel.has(g))) return null;
  return Array.from(sel).sort().join(',');
}

/** `?levels=` → the selected arrival levels. FAILS OPEN exactly like the
 *  backend's `deep_demand.parse_levels`: empty, `all`, garbage, a level outside
 *  the window, or a spec that selects nothing all mean EVERY level. A filter
 *  that can silently serve an empty board is a filter that eats the tab. */
export function parseLevels(raw: string | null | undefined): Set<number> {
  const all = new Set<number>(DEEP_LEVELS);
  const v = (raw || '').trim().toLowerCase();
  if (!v || v === 'all') return all;
  const picked = new Set<number>();
  for (const part of v.split(',')) {
    const n = Number(part.trim());
    if (Number.isInteger(n) && DEEP_LEVELS.includes(n)) picked.add(n);
  }
  return picked.size ? picked : all;
}

/** The selection as the wire/URL value, normalised ascending — `null` when it
 *  is every level, which is the DEFAULT and therefore written nowhere (same
 *  rule `phase` and `room` follow, so a plain tab URL stays clean). Selecting
 *  none is meaningless and normalises to null too, so the page can never ask
 *  for an empty board. */
export function levelsParam(sel: Iterable<number>): string | null {
  const want = new Set<number>(sel);
  const picked = DEEP_LEVELS.filter((n) => want.has(n));
  if (!picked.length || picked.length === DEEP_LEVELS.length) return null;
  return picked.join(',');
}

/* ── 🎯 Un-hide by reason (Ajay 2026-09-17: "Can you give me a toggle for the
 *     room too? I am not seeing all stocks on the selected filter due to this
 *     now") ──────────────────────────────────────────────────────────────────
 *
 * A VIEW filter over the SERVED verdict, and nothing else. The codes are the
 * backend's own `enterable.reasons` entries; this file never holds a list of
 * them, because a list here would be a second definition of a reason.
 *
 * It is NOT the `?room=` floor. That one runs on the SERVER (drop_low_room,
 * ROOM_TABS) and decides which tiles are returned at all; this one decides
 * which of the returned tiles are drawn. On a ROOM_TABS tab both have to be
 * relaxed to see every room-blocked name. */
export const UNHIDE_PARAM = 'unhide';

/** `?unhide=` → the served reason codes this view un-hides.
 *
 *  FAILS CLOSED (empty) on empty or garbage input — the opposite of
 *  `parseLevels`, deliberately: an un-hide ADDS BLOCKED rows to his view, so an
 *  unreadable URL must land on the shipped filter, never on "show everything".
 *  No allow-list: the codes come from the payload, and a token no row carries
 *  is simply inert. Never throws. */
export function parseUnhide(raw: string | null | undefined): Set<string> {
  const out = new Set<string>();
  for (const part of String(raw || '').split(',')) {
    const k = part.trim().toLowerCase();
    if (/^[a-z0-9_]{1,40}$/.test(k)) out.add(k);
  }
  return out;
}

/** The selection as the URL value, deduped and sorted ascending. `null` when
 *  empty — that is the DEFAULT and is therefore written nowhere, the same rule
 *  `phase`, `room` and `levels` follow. */
export function unhideParam(sel: Iterable<string>): string | null {
  const picked = Array.from(new Set(Array.from(sel, (c) => String(c).trim().toLowerCase())))
    .filter((c) => /^[a-z0-9_]{1,40}$/.test(c))
    .sort();
  return picked.length ? picked.join(',') : null;
}

export function parseBias(raw: string | null | undefined): IctBias {
  const v = (raw || '').trim().toLowerCase();
  return v === 'bullish' || v === 'bearish' ? v : DEFAULT_ICT_BIAS;
}

export function parseMicro(raw: string | null | undefined): IctMicro {
  const v = (raw || '').trim().toLowerCase();
  return v === '15m' ? '15m' : DEFAULT_ICT_MICRO;
}

/** Plain-language names for the owner constants the backend echoes in
 *  `params`. Every one of these is a house value — "owner rule, not from the
 *  video" — which is exactly why they are listed under the board instead of
 *  buried in code. Keys are matched case-insensitively so the backend is free
 *  to spell them either way; a key not listed here still renders, by name, so
 *  a new constant can never be hidden by an out-of-date frontend map. */
export const ICT_PARAM_LABELS: Record<string, string> = {
  fractal_window: 'swing point: bars each side (1 = 3-candle fractal)',
  stack_min: 'stacked consolidations: min count',
  atr_period: 'ATR period (the range unit every ATR rule uses)',
  consol_min_bars: 'consolidation: min bars',
  consol_max_atr: 'consolidation: max span (× ATR14)',
  displace_max_atr: 'manipulation: max close-through (× ATR, 0 = must close back above)',
  displace_min_atr: 'displacement: min body (× ATR)',
  confirm_max_bars: 'displacement: within N bars of the sweep',
  mss_fvg_within_bars: 'MSS: new gap within N bars of the close',
  stack_lookback_bars: 'stacked consolidations: bars searched',
  n_swings: 'daily swings kept as key levels',
  tap_lookback: 'tap window (daily sessions)',
  tap_tol_pct: 'tap tolerance (% of level)',
  entry_tol_pct: 'entry: within % of the zone',
  stop_buffer_atr: 'stop buffer under the wick (× micro ATR)',
  micro_max: 'micro runs per scan (cap)',
  budget_sec: 'scan budget (seconds)',
  ict_ttl_sec: 'cache TTL before a background re-scan (seconds)',
  keep_days: 'dated scans kept (days)',
  macro_min_bars: 'daily frame: min bars to read',
  micro_min_bars: 'micro frame: min bars to read',
  macro_fvg_lookback: 'daily gaps: bars searched',
  macro_fvg_keep: 'daily gaps: newest kept',
  liq_window: 'liquidity: avg $ volume window (days)',
  grade_manipulation: 'grade: manipulation found',
  grade_displacement: 'grade: opposite displacement',
  grade_mss: 'grade: market structure shift',
  grade_entry: 'grade: at the entry zone',
};

/** One entry of the backend's `params` list (ict/engine.py params()). */
export type IctParamIn = {
  key?: string | null; value?: unknown; from_video?: boolean | null; note?: string | null;
};

export type IctParamRow = { key: string; label: string; value: string; fromVideo: boolean };

/** `params` → rows for the settings list: known constants first in the
 *  order the rules are applied (levels → tap → consolidation → manipulation →
 *  displacement → entry → plan → ops), then anything unlisted, by name. A
 *  missing or malformed payload gives [] — the list simply does not draw.
 *
 *  Two shapes are accepted. The backend contract is a LIST of
 *  {key, value, from_video, note} — `from_video` is what lets the page keep
 *  the two values the video states (3-candle fractal, "two or more"
 *  consolidations) out of the "not from the video" group. A flat
 *  {key: value} map still works and counts every entry as an owner rule. */
export function ictParamRows(params: CmBoard['params']): IctParamRow[] {
  if (!params || typeof params !== 'object') return [];
  const order = Object.keys(ICT_PARAM_LABELS);
  const rows: IctParamRow[] = [];
  const push = (k: unknown, v: unknown, fromVideo: boolean) => {
    if (v === null || v === undefined) return;
    if (typeof v === 'object') return;                    // nested → not a constant
    const key = typeof k === 'string' ? k.trim() : '';
    if (!key) return;
    const norm = key.toLowerCase();
    rows.push({ key, label: ICT_PARAM_LABELS[norm] || key, value: String(v), fromVideo });
  };
  if (Array.isArray(params)) {
    for (const p of params) {
      if (!p || typeof p !== 'object' || Array.isArray(p)) continue;
      push(p.key, p.value, p.from_video === true);
    }
  } else {
    for (const [k, v] of Object.entries(params)) push(k, v, false);
  }
  rows.sort((a, b) => {
    const ia = order.indexOf(a.key.toLowerCase());
    const ib = order.indexOf(b.key.toLowerCase());
    if (ia >= 0 && ib >= 0) return ia - ib;
    if (ia >= 0) return -1;
    if (ib >= 0) return 1;
    return a.key.localeCompare(b.key);
  });
  return rows;
}

/** Tile legend for the ICT board. Mirrors what chart_maps/board.py ict_tiles
 *  draws and what PatternChart does with each kind: bands by kind, lines by
 *  tone, markers by kind (sweep / bos = small glyphs, buy / sell = candle
 *  tags). Written here rather than in the page so it is a fixed list the
 *  tests can hold to the backend contract. */
export const ICT_LEGEND: { glyph: string; label: string; hint: string }[] = [
  { glyph: '▭', label: 'accumulation', hint: 'the Power-of-3 range the manipulation dips below (grey box)' },
  { glyph: '🟩', label: 'FVG ↑', hint: 'active bullish fair value gap (Low[i+2] > High[i]) — support' },
  { glyph: '🟥', label: 'FVG ↓', hint: 'active bearish fair value gap (High[i+2] < Low[i]) — resistance' },
  { glyph: '▦', label: 'IFVG', hint: 'inverted gap: a candle CLOSED through the far edge, so it flips role (neutral box)' },
  { glyph: '🎯', label: 'entry', hint: 'the IFVG or the new gap — the zone the plan buys / sells in' },
  { glyph: '┈', label: 'key low / key high', hint: 'the daily swing levels the 60m loop is watching' },
  { glyph: '⤵', label: 'MANIP', hint: 'the sweep bar — wick through the level, close back inside (no displacement)' },
  { glyph: '↗', label: 'MSS', hint: 'market structure shift — close past the last opposing swing with a new FVG' },
  { glyph: '▲▼', label: 'IFVG tag', hint: 'the entry bar, tagged under (bullish) or over (bearish) the candle' },
  { glyph: '— —', label: 'STOP / TARGET', hint: 'stop = manipulation extreme ± buffer; target = the next daily swing (external liquidity)' },
];

/** The source line under the ICT board. The backend echoes `source` as
 *  {video, timestamps}; the stamps may arrive as plain strings ("02:39") or as
 *  {at, rule} objects (the ICT_SOURCE.timestamps shape) — both render as the
 *  bare stamps and anything else is dropped rather than printed as
 *  "[object Object]". A missing or non-http video URL falls back to the
 *  frontend copy so the name is always a working link. */
export function ictSource(source: CmBoard['source']): { url: string; stamps: string } {
  const video = source && typeof source === 'object' ? source.video : null;
  const url = typeof video === 'string' && /^https?:\/\//i.test(video.trim())
    ? video.trim() : ICT_SOURCE.url;
  const raw = source && typeof source === 'object' && Array.isArray(source.timestamps)
    ? source.timestamps : [];
  const stamps: string[] = [];
  for (const t of raw) {
    if (typeof t === 'string') { if (t.trim()) stamps.push(t.trim()); continue; }
    if (t && typeof t === 'object' && typeof t.at === 'string' && t.at.trim()) stamps.push(t.at.trim());
  }
  const shown = stamps.length ? stamps : ICT_SOURCE.timestamps.map((t) => t.at);
  return { url, stamps: shown.join(' · ') };
}

/** Deep link to a ticker's SEPA detail page. Default 'supply' (Ajay
 *  2026-09-03: "go Supply and Demand tab in all pages"; was 'setup' since
 *  2026-08-17). SepaCandidate silently falls back to Supply / Demand on an
 *  unknown value, so a typo here is invisible — hence the test.
 *  NOTE: dead at runtime — the live tiles take `href` from the backend
 *  (chart_maps/board.py _href, also defaulting to supply). Kept as the
 *  frontend statement of the same rule; tests only. */
export function sepaHref(symbol: string, tab: 'setup' | 'supply' | 'breakout' = 'supply'): string {
  return `/sepa/${encodeURIComponent((symbol || '').toUpperCase())}?tab=${tab}`;
}

/** Which ledger the Past Winners tab reads. Ajay 2026-08-16: "In the past
 *  winners tab I wanna see the deman zones that were successful as well." */
export type WinnerSource = 'pattern' | 'zone';

export const WINNER_SOURCES: { key: WinnerSource; label: string }[] = [
  { key: 'pattern', label: 'Chart patterns' },
  { key: 'zone', label: 'Demand zones' },
];

export function parseSource(v: string | null | undefined): WinnerSource {
  return v === 'zone' ? 'zone' : 'pattern';
}

/** Matches board.DEFAULT_SORT — the tab's own score (base tightness for VCP,
 *  R:R for demand), NOT a metric. Kept out of the query string when unchanged so
 *  a shared URL stays short and the default stays the default.
 *
 *  Was 'theme' / "🤖 AI sectors (default)" until 2026-08-17, which bundled two
 *  claims into one entry: the theme LEAD is the checkbox, this is the ordering
 *  used when no metric is chosen. Ajay: "Remove default themes checked and AI
 *  sector from drop down". */
export const DEFAULT_SORT = 'default';

/** Matches board.THEMES_FIRST_DEFAULT. The AI-ecosystem lead is now opt-in. */
export const THEMES_FIRST_DEFAULT = false;

/** Matches board.DEFAULT_MIN_TIER — "comfortably tradeable in retail size"
 *  ($10M/day). Ajay 2026-08-17: "we want to make that average turn over is high
 *  for these". A study board that teaches the shape of a $1.5M/day base is
 *  teaching a pattern he cannot actually trade. */
export const DEFAULT_MIN_TIER = 'ok';

export function parseTier(raw: string | null | undefined): string {
  const v = (raw || '').trim();
  return v || DEFAULT_MIN_TIER;
}

/** A sort the backend actually offers, or the default. The board advertises its
 *  own options, so a key retired server-side degrades instead of 404ing. */
export function parseSort(raw: string | null | undefined,
                          offered?: CmSort[] | null): string {
  const v = (raw || '').trim();
  if (!v) return DEFAULT_SORT;
  if (offered && offered.length) {
    return offered.some((o) => o.key === v) ? v : DEFAULT_SORT;
  }
  return v;
}

/** The AMD/Keltner grade chips a URL asks for. Empty / junk -> an empty set,
 *  which the caller normalises to "the server default" (the turning grade
 *  alone) rather than to an empty board. Order is not preserved; the chips
 *  render in the backend's own `grades_all` order. */
export function parseGrades(raw: string | null | undefined): Set<string> {
  const out = new Set<string>();
  for (const part of String(raw || '').split(',')) {
    const k = part.trim().toLowerCase();
    if (k) out.add(k);
  }
  return out;
}

/** The `grades=` value for a selection, or null when it should not ride:
 *  nothing selected (normalise to the default) or everything selected but the
 *  caller passed no universe to compare against. */
export function gradesParam(sel: Set<string>, all?: string[]): string | null {
  if (!sel.size) return null;
  if (all && all.length && all.every((g) => sel.has(g))) return 'all';
  return Array.from(sel).sort().join(',');
}

export function boardQuery(p: {
  tab: CmTab; limit?: number; days?: number;
  universe?: string; themesFirst?: boolean; pattern?: string | null;
  source?: WinnerSource; minerviniOnly?: boolean; sort?: string;
  minTier?: string; gabbarLevel?: string; gabbarTouchingOnly?: boolean;
  phase?: string; target?: string;
  bias?: string; micro?: string;
  minRoom?: number;
  levels?: string;
  grades?: string;
  flight?: string;
}): string {
  const q = new URLSearchParams({ tab: p.tab });
  // Reaching vs already reached (Ajay 2026-08-31, extended same day to "all
  // the tabs possible"). Demand boards: default reached, only 'approaching'
  // rides on the URL. Lens tabs (undervalue, gabbar): default ALL, so both
  // explicit phases ride. Zones alone takes the level flavour (order_block),
  // on either phase — reached+order_block = IN the block on first touch.
  if ((p.tab === 'zones' || p.tab === 'deep_demand') && p.phase === 'approaching') {
    q.set('phase', 'approaching');
  }
  if ((p.tab === 'undervalue' || p.tab === 'gabbar')
      && (p.phase === 'approaching' || p.phase === 'reached')) {
    q.set('phase', p.phase);
  }
  if (p.tab === 'zones' && p.target === 'order_block') {
    q.set('target', 'order_block');
  }
  // Room floor (Ajay 2026-09-05: "same logic in Demand and deep demand
  // zone ... more room atleast >5%"). Sent EXPLICITLY — 5 and 0 alike — so the
  // request says which floor the board was asked for, and only on the two
  // demand boards; nothing else has a room read. Omitted when the caller did
  // not decide (older call sites), leaving their query byte for byte.
  if (ROOM_TABS.includes(p.tab) && p.minRoom != null && Number.isFinite(p.minRoom)) {
    q.set('min_room', String(p.minRoom));
  }
  // 🩹 Arrival-level filter (Ajay 2026-09-16: "can you do level 4 and give me
  // filters for that"). Deep Demand alone has an arrival level; `all` is the
  // server default and rides nowhere. NOT the gabbar tab's `level` (singular),
  // which is a band-TYPE lens on a different board — two params, two names.
  if (p.tab === 'deep_demand' && p.levels && p.levels !== 'all') {
    q.set('levels', p.levels);
  }
  // 🌀 AMD / Keltner grade filter (Ajay 2026-09-17: "I wanna see all AMD and
  // also filterable AMD"). Only a selection that DIFFERS from the server's
  // default rides — an empty param means "the turning grade only", which is
  // the board this tab has always opened on.
  if ((p.tab === 'amd' || p.tab === 'keltner') && p.grades) {
    q.set('grades', p.grades);
  }
  // 🔻 The live state filter — AMD only, and only when it NARROWS.
  if (p.tab === 'amd' && p.flight) q.set('flight', p.flight);
  if (p.limit) q.set('limit', String(p.limit));
  if (p.days) q.set('days', String(p.days));
  // Both demand boards read ONE demand_reentry cache, so the universe
  // choice governs both or the two tabs would describe different scans.
  if ((p.tab === 'zones' || p.tab === 'supply') && p.universe) {
    q.set('universe', p.universe);
  }
  // Gabbar band-type lens (2026-08-25). Only sent when it narrows something —
  // 'all' is the server default and would just noise up the common URL.
  if (p.tab === 'gabbar' && p.gabbarLevel && p.gabbarLevel !== 'all') {
    q.set('level', p.gabbarLevel);
  }
  // Touching-only became the opt-IN (2026-08-27: "just show me all of them
  // there") — only the narrowing value rides on the URL.
  if (p.tab === 'gabbar' && p.gabbarTouchingOnly === true) {
    q.set('touching_only', 'true');
  }
  // ICT (2026-09-03): bias narrows the board to one side of the sweep, micro
  // picks the trigger timeframe. Both are server defaults when omitted, and
  // both are ict-only — the other boards have no sweep side and no second
  // clock, so a leaked param would just split their cache keys.
  if (p.tab === 'ict' && p.bias && p.bias !== DEFAULT_ICT_BIAS) {
    q.set('bias', p.bias);
  }
  if (p.tab === 'ict' && p.micro && p.micro !== DEFAULT_ICT_MICRO) {
    q.set('micro', p.micro);
  }
  // Only sent when it differs from the shared default, so the common URL stays
  // clean. That default flipped to OFF on 2026-08-17, so this now sends `true`
  // rather than `false` — keeping it on `false` would have put the parameter on
  // every request while silently never sending the one that changes anything.
  if (p.themesFirst !== undefined && p.themesFirst !== THEMES_FIRST_DEFAULT) {
    q.set('themes_first', String(p.themesFirst));
  }
  // Sent to the BACKEND on purpose. board._finish ranks and caps before it
  // fetches bars for only the tiles it will show, so sorting in the browser
  // would reorder the ~24 tiles theme priority already chose — "highest
  // volume" would silently mean "highest volume among those 24".
  if (p.sort && p.sort !== DEFAULT_SORT) q.set('sort', p.sort);
  if (p.minTier && p.minTier !== DEFAULT_MIN_TIER) q.set('min_tier', p.minTier);
  // Winners-only params. `pattern` is meaningless for the zone ledger — zone
  // re-entries have no chart-pattern name — so it is dropped there rather than
  // sent and silently ignored.
  if (p.tab === 'winners' && p.source === 'zone') q.set('source', 'zone');
  if (p.tab === 'winners' && p.source !== 'zone' && p.pattern) q.set('pattern', p.pattern);
  if (p.tab === 'winners' && p.source !== 'zone' && p.minerviniOnly) {
    q.set('minervini_only', 'true');
  }
  return q.toString();
}

/* ── chart geometry ───────────────────────────────────────────────────────── */

export type Domain = { lo: number; hi: number };

/** Y-domain over candle highs/lows, widened for nearby bands and lines.
 *
 * The nearness guard is the same idea as zonePlan.chartDomain: a target sitting
 * 40% above the last bar is context, and stretching to it flattens the price
 * action into a streak — which defeats the whole point of a study chart. Only
 * levels within one series-height of the data pull the domain.
 */
export function barDomain(
  bars: CmBar[],
  bands: CmBand[] = [],
  lines: CmLine[] = [],
  padPct = 6,
  curves: CmCurve[] = [],
): Domain {
  const highs = bars.map((b) => b.h).filter((n) => Number.isFinite(n));
  const lows = bars.map((b) => b.l).filter((n) => Number.isFinite(n));
  if (!highs.length || !lows.length) return { lo: 0, hi: 1 };
  let lo = Math.min(...lows);
  let hi = Math.max(...highs);
  const height = hi - lo || 1;

  const stretch = (v: number | null | undefined) => {
    if (v == null || !Number.isFinite(v)) return;
    if (v >= lo - height && v <= hi + height) {
      lo = Math.min(lo, v);
      hi = Math.max(hi, v);
    }
  };
  for (const b of bands) { stretch(b.lo); stretch(b.hi); }
  for (const l of lines) stretch(l.price);
  // A curve is drawn across the whole tile, so a channel that runs wider than
  // the candles would be CLIPPED at the top or bottom of the plot without
  // this. Same `stretch` guard as every other overlay: a value more than one
  // chart-height away is an outlier and never squashes the candles to fit it.
  for (const c of curves) for (const v of c.values || []) stretch(v);

  const pad = ((hi - lo) || hi || 1) * (padPct / 100);
  return { lo: lo - pad, hi: hi + pad };
}

/** Price → SVG y. Inverted (high price = small y). */
export function yFor(price: number, d: Domain, height: number, padY = 8): number {
  const span = d.hi - d.lo || 1e-9;
  const t = (price - d.lo) / span;
  return padY + (1 - t) * (height - 2 * padY);
}

/** Index → SVG x for the centre of bar `i`. */
export function xFor(i: number, n: number, width: number, padR: number): number {
  const w = Math.max(width - padR, 1);
  const bw = w / Math.max(n, 1);
  return i * bw + bw / 2;
}

export function barWidth(n: number, width: number, padR: number): number {
  return Math.max(width - padR, 1) / Math.max(n, 1);
}

/** Clip bands to the visible domain, dropping any that fall outside it, so we
 *  never draw an off-canvas rectangle or a zero-height sliver. */
export function clipBands(bands: CmBand[], d: Domain): CmBand[] {
  const out: CmBand[] = [];
  for (const b of bands) {
    if (!Number.isFinite(b.lo) || !Number.isFinite(b.hi)) continue;
    const lo = Math.max(Math.min(b.lo, b.hi), d.lo);
    const hi = Math.min(Math.max(b.lo, b.hi), d.hi);
    if (hi <= lo) continue;                    // entirely outside the view
    out.push({ ...b, lo, hi });
  }
  return out;
}

// HIGHER wins: layoutLabels sorts descending and pins anything >= 2 to its
// exact y. `neutral` is the earnings tiles' prior-close reference, so it sits
// at 1 — it may be nudged or dropped when the plan lines need the pixels,
// which is right, because the gap it marks is already written in the stats.
const TONE_PRIORITY: Record<CmLineTone, number> = {
  buy: 3, stop: 3, target: 2, now: 2, neutral: 1,
  // Priority 1 for the study overlays, deliberately. `layoutLabels` hunts the
  // whole chart height for anything >= 2 and DROPS a 1 that cannot fit — which
  // is the behaviour we want here: sixteen study labels must never shove the
  // BUY / STOP / TARGET plan off the chart. The coloured line still draws;
  // only its right-edge text yields.
  amd: 1, fib: 1, meanrev: 1, keltner: 1,
  // His own numbers on his own chart are never dropped for a study label.
  cost: 3, ownstop: 3,
};

/** Right-edge labels for the plan lines, de-collided. Reuses zonePlan's
 *  layoutLabels so the two chart surfaces cannot drift apart. */
/** The now line's label carries the live price (Ajay 2026-09-08: "add the now
 *  price here please from current market") — "now 4.17", "now · pre 52.41",
 *  "LAST · AH 75.94". Sub-dollar names keep a third decimal. */
export function nowLabelText(label: string, price: number): string {
  if (!Number.isFinite(price)) return label;
  const px = Math.abs(price) < 1 ? price.toFixed(3) : price.toFixed(2);
  return `${label || 'now'} ${px}`;
}

/** A curve's gutter label — its value at the LAST bar it has one.
 *
 *  The number in the gutter always means "where this overlay is now", which
 *  for a flat level is the level itself and for a bending channel is its
 *  right-hand end. Returned as pseudo-lines so `lineLabels` lays them out in
 *  the same collision pass as everything else: a channel label that overlapped
 *  a stop label would be the 2026-09-08 overlap bug again, on a new family. */
export function curveLabels(curves: CmCurve[] = []): CmLine[] {
  const out: CmLine[] = [];
  for (const c of curves || []) {
    const vals = c.values || [];
    for (let i = vals.length - 1; i >= 0; i -= 1) {
      const v = vals[i];
      if (v != null && Number.isFinite(v)) {
        out.push({ price: v, tone: c.tone, label: `${c.label} ${v.toFixed(2)}` });
        break;
      }
    }
  }
  return out;
}

export function lineLabels(
  lines: CmLine[], d: Domain, height: number, padY = 8, fontSize = 9.5,
): LabelItem[] {
  const items: LabelItem[] = lines
    .filter((l) => Number.isFinite(l.price) && l.price >= d.lo && l.price <= d.hi)
    .map((l) => ({
      y: yFor(l.price, d, height, padY),
      text: l.tone === 'now' ? nowLabelText(l.label, l.price) : l.label,
      color: toneColor(l.tone),
      bold: l.tone === 'buy' || l.tone === 'cost',
      priority: l.quiet ? 0 : (TONE_PRIORITY[l.tone] ?? 2),
    }));
  // The gap follows the type size: a 10-unit gap under 9.5-unit text let two
  // labels touch, and a plan label that could not fit within maxShift used to
  // be pinned onto its neighbour (Ajay 2026-09-08: "These overlap"). Now it
  // travels further and a pointer leads back to its level.
  return layoutLabels(items, { minGap: fontSize + 2, top: 6, bottom: height - 4, maxShift: 22 });
}

/* ── price axis (2026-08-19) ──────────────────────────────────────────────────
 * Ajay: "can you add the #s to these graphs please?"
 *
 * Until now the ONLY numbers on a tile were the plan-line labels. A demand band
 * could be drawn as a green box with no way to read what price it sat at —
 * which is most of the point on the Support Levels tab, where the band IS the
 * answer.
 *
 * The axis goes in the SAME right gutter the plan labels already use, never
 * over the candles. Ajay 2026-08-18: "they are all clumsy and its hard to look
 * at the bars" — that complaint was about text on the price action, and this
 * must not re-create it.
 */

/** Steps a human reads without thinking, per decade. */
const STEP_MULTS = [1, 2, 2.5, 5];

/** Pick the step whose tick count lands closest to `target`.
 *
 * The naive `niceStep(span / target)` rounds UP through a 5→10 gap, which on a
 * real chart is the difference between a usable scale and a broken one: META
 * over a year spans ~$300, `300/5 = 60` rounds to 100, and the axis came back
 * 600 / 700 / 800 — while price was at 539, so every tick sat above the entire
 * lower half of the chart (measured 2026-08-19). Searching the ladder either
 * side of the estimate picks 50 instead, and the scale covers the candles.
 *
 * Ties go to the LARGER step: fewer gridlines for the same coverage.
 */
function chooseStep(span: number, target: number): number {
  if (!Number.isFinite(span) || span <= 0) return 1;
  const exp = Math.floor(Math.log10(span / Math.max(target, 1)));
  let best = Math.pow(10, exp);
  let bestScore = Infinity;
  for (const e of [exp - 1, exp, exp + 1]) {
    for (const m of STEP_MULTS) {
      const step = m * Math.pow(10, e);
      if (!Number.isFinite(step) || step <= 0) continue;
      const count = Math.floor(span / step);
      if (count < 2 || count > MAX_TICKS) continue;
      const score = Math.abs(count - target);
      if (score < bestScore || (score === bestScore && step > best)) {
        best = step;
        bestScore = score;
      }
    }
  }
  return best;
}

/** Ceiling on gridlines. Past this the chart is graph paper, not a chart. */
const MAX_TICKS = 10;

/** Roughly how many ticks to aim for. Six rather than four because some are
 *  spent on collisions with the plan labels — BRKR at the 1-month zoom lost two
 *  of four that way and the scale stopped being readable. */
const TARGET_TICKS = 6;

/** Decimals needed to print the step EXACTLY, capped at 2.
 *
 * Not derived from the step's magnitude — that was wrong, and wrong in the way
 * that matters. `-floor(log10(2.5))` is 0, so a 2.5 step printed BRKR's
 * gridlines at 52.5 and 57.5 as "53" and "58" (measured 2026-08-19): the number
 * claimed a price the line was not drawn at. An axis that misreports its own
 * position is worse than no axis, because a stop gets placed off it.
 *
 * So: the smallest decimal count that represents the step without rounding.
 * 50 → 0, 2.5 → 1, 0.25 → 2.
 */
export function tickDecimals(step: number): number {
  if (!Number.isFinite(step) || step <= 0) return 2;
  for (let d = 0; d <= 2; d++) {
    const scaled = step * Math.pow(10, d);
    if (Math.abs(scaled - Math.round(scaled)) < 1e-9) return d;
  }
  return 2;
}

export type PriceTick = { price: number; y: number; text: string };

/** Horizontal price ticks across the visible domain.
 *
 * Stepping by index rather than accumulating `p += step` keeps float error out
 * of the label text — otherwise a 0.1 step prints "1.3000000000000003".
 */
export function priceTicks(
  d: Domain, height: number, padY = 8, target = TARGET_TICKS,
): PriceTick[] {
  const span = d.hi - d.lo;
  if (!Number.isFinite(span) || span <= 0 || !Number.isFinite(height)) return [];
  const step = chooseStep(span, target);
  const dp = tickDecimals(step);
  const first = Math.ceil(d.lo / step) * step;
  const out: PriceTick[] = [];
  for (let i = 0; i <= MAX_TICKS * 2; i++) {
    const price = first + i * step;
    if (price > d.hi) break;
    const y = yFor(price, d, height, padY);
    // Keep the top and bottom labels off the chart's own edges, where they
    // would sit half-clipped or collide with the month row.
    if (y < padY + 2 || y > height - padY - 2) continue;
    out.push({ price, y, text: price.toFixed(dp) });
  }
  return out;
}

/** Which ticks may print their NUMBER. The gridline is always drawn.
 *
 * The plan labels win the text: buy / stop / target / now are the decision
 * numbers, and they are more precise than the round tick they sit next to. But
 * suppressing the whole tick left visible holes in an evenly spaced grid —
 * BRKR kept 2 of 4 — which reads as a rendering bug rather than as deference.
 * So the LINE stays and only the number yields; at that height there is still a
 * number on screen, just a better one.
 */
export function dropCollidingTicks(
  ticks: PriceTick[], labels: { y: number }[], minGap = 11,
): PriceTick[] {
  if (!labels?.length) return ticks;
  return ticks.filter((t) => !labels.some((l) => Math.abs(l.y - t.y) < minGap));
}

/* ── right gutter + hover readout (2026-08-19) ────────────────────────────────
 * Ajay, with a screenshot: the META tile rendered "overhead 553" and
 * "support 527." — both cut off at the SVG's right edge. PAD_R was a fixed 62
 * units in a 620-unit viewBox, and "overhead 553.67" needs ~78. The tab that
 * exposed it is the one where the label IS the answer.
 *
 * And: "can you give me same features like hover over prices at the level".
 */

/** Approximate advance width of a string, in viewBox units, without measuring.
 *
 * getComputedTextLength needs a laid-out DOM node, which the geometry layer
 * deliberately does not have — every number on this chart comes from a pure
 * function so it can be tested. Per-class advances for a UI sans are close
 * enough for a gutter that gets clamped anyway.
 */
export function textWidth(text: string, fontSize: number): number {
  let em = 0;
  for (const ch of text || '') {
    // DIGITS FIRST. UI sans faces ship tabular figures by default — every
    // digit carries the same advance so columns of numbers line up — so '1'
    // is NOT a narrow glyph here. Lumping it in with 'il!' under-measured
    // every label holding a 1, which is most stock prices, and let
    // "overhead 151.87" overflow the gutter it had just been widened for.
    if (ch >= '0' && ch <= '9') em += 0.55;
    else if (ch === ' ') em += 0.28;
    else if ('.,:;\'`|'.includes(ch)) em += 0.28;
    else if ('il!'.includes(ch)) em += 0.30;
    else if ('mwMW'.includes(ch)) em += 0.85;
    else if (ch >= 'A' && ch <= 'Z') em += 0.66;
    else em += 0.55;
  }
  return em * fontSize;
}

export const GUTTER_MIN = 56;
export const GUTTER_MAX = 118;

/** Width the right gutter needs so no label is clipped.
 *
 * Dynamic rather than a constant: a board tile labelled "BUY 152.30" should not
 * pay for the Support tab's "overhead 553.67". Clamped at both ends so one
 * pathological label cannot eat the plot.
 */
export function gutterWidth(
  texts: string[], fontSize = 9.5, pad = 12,
): number {
  // `pad` is real breathing room, not decoration. `textWidth` is an ESTIMATE —
  // the actual face, its kerning and the user's zoom all move the true advance
  // — so the margin has to absorb being wrong by a few percent. At pad 8 a
  // deliberately cruder estimate already overflowed the viewBox by 0.4 units,
  // which is exactly the clipped label this function exists to prevent.
  const widest = (texts || []).reduce(
    (m, t) => Math.max(m, textWidth(t, fontSize)), 0);
  return Math.min(GUTTER_MAX, Math.max(GUTTER_MIN, Math.ceil(widest + pad)));
}

/** Inverse of `yFor` — the price at a pixel row. Used by the hover crosshair. */
export function priceAt(y: number, d: Domain, height: number, padY = 8): number {
  const usable = height - 2 * padY || 1;
  const t = 1 - (y - padY) / usable;
  return d.lo + t * (d.hi - d.lo);
}

/** Inverse of `xFor` — which bar sits under a pixel column, clamped to the
 *  series so a cursor in the gutter still reads the last bar rather than
 *  falling off the end. */
export function barIndexAt(
  x: number, n: number, width: number, padR: number,
): number {
  if (!n) return -1;
  const w = Math.max(width - padR, 1);
  const bw = w / n;
  return Math.min(n - 1, Math.max(0, Math.floor(x / bw)));
}

/** The band a price falls inside, if any. Hovering a zone should name it —
 *  that is the "hover over prices at the level" ask. */
export function bandAt(price: number, bands: CmBand[]): CmBand | null {
  if (!Number.isFinite(price)) return null;
  for (const b of bands || []) {
    const lo = Math.min(b.lo, b.hi);
    const hi = Math.max(b.lo, b.hi);
    if (price >= lo && price <= hi) return b;
  }
  return null;
}

/** Compact volume — 12.4M, 903K. A raw 18011648 in a tooltip is unreadable. */
export function shortVol(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v) || v < 0) return '—';
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${Math.round(v / 1e3)}K`;
  return String(Math.round(v));
}

/** Keep a tooltip box inside the chart, flipping it rather than clipping it.
 *  A readout that runs off the right edge is the same defect as the labels
 *  this change was opened to fix. */
export function tooltipPos(
  x: number, y: number, boxW: number, boxH: number,
  width: number, height: number, gap = 10,
): { x: number; y: number } {
  const px = x + gap + boxW > width ? Math.max(2, x - gap - boxW) : x + gap;
  const py = Math.min(Math.max(2, y - boxH / 2), Math.max(2, height - boxH - 2));
  return { x: px, y: py };
}

/** The lines of the hover readout for one bar. Pure so the text is testable. */
export function hoverLines(bar: CmBar | null | undefined): string[] {
  if (!bar) return [];
  const f = (n: number) => (Number.isFinite(n) ? n.toFixed(2) : '—');
  // The extended-hours bar carries the AH / pre-market print as its close and
  // widened high/low (prices.with_today_bar); say so, or the readout claims an
  // official close the session never printed (2026-09-14).
  const tape = bar.s === 'ah' ? ' · AH' : bar.s === 'pre' ? ' · pre' : '';
  return [
    `${bar.t}${tape}`,
    `O ${f(bar.o)}   H ${f(bar.h)}`,
    `L ${f(bar.l)}   C ${f(bar.c)}`,
    `Vol ${shortVol(bar.v)}`,
  ];
}

export function toneColor(tone: CmLineTone): string {
  if (tone === 'buy') return 'var(--positive, #22c55e)';
  if (tone === 'stop') return 'var(--negative, #ef4444)';
  if (tone === 'target') return 'var(--gold, #c9a227)';
  // The 2026-09-12 study overlays. They shipped WITHOUT these and every one of
  // them fell through to the muted grey below — drawn, but the same colour as
  // the grid, which is why Ajay reported "Non of these are showing up".
  // Each colour is the one its checkbox shows in the ledger, so the swatch and
  // the line agree.
  if (tone === 'amd') return 'var(--cm-violet, #8b5cf6)';
  if (tone === 'fib') return 'var(--cm-teal, #14b8a6)';
  if (tone === 'meanrev') return 'var(--cm-slate, #64748b)';
  if (tone === 'keltner') return 'var(--cm-amberlt, #f59e0b)';
  // The now line draws in the ink its legend swatch shows (it fell to the
  // grid grey below, so the swatch and the line disagreed — 2026-09-14).
  if (tone === 'now') return 'var(--ink, #e7e7e7)';
  // 📁 My holdings: his cost in the position pink, his typed stop in the
  // info blue — neither borrows a plan tone, so a "STOP" the engine drew and
  // the stop HE set can never look like the same line.
  if (tone === 'cost') return 'var(--cm-pink, #ec4899)';
  if (tone === 'ownstop') return 'var(--info, #38bdf8)';
  return 'var(--text-muted, #94a3b8)';
}

/** Sparse x-axis ticks — first bar of each new month, as {i, label}. A dense
 *  daily axis is unreadable at tile size; month boundaries are what you
 *  actually navigate by. */
/** Axis ticks for whichever bars these are: intraday bars (HH:MM stamps)
 *  get session ticks — the date at each new day, 09:30 and 16:00 in between
 *  — so a two-session live chart reads "Sep 1 · 09:30 · 16:00 · Sep 2 …"
 *  instead of a single "Sep". Daily bars keep the month ticks. */
export function timeTicks(bars: CmBar[], max = 8): { i: number; label: string }[] {
  if (!bars.length || (bars[0].t || '').length <= 10) return monthTicks(bars, max);
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const ticks: { i: number; label: string; major: boolean }[] = [];
  let prevDay = '';
  let openTicked = true;
  bars.forEach((b, i) => {
    const day = b.t.slice(0, 10);
    const hm = b.t.slice(11, 16);
    if (day !== prevDay) {
      prevDay = day;
      openTicked = false;
      const m = Number(day.slice(5, 7)); const d = Number(day.slice(8, 10));
      ticks.push({ i, label: `${MON[m - 1] || ''} ${d}`, major: true });
      return;
    }
    // Bars are RIGHT-labelled by the resampler, so no bar is ever stamped
    // exactly 09:30 — the first RTH bar of the day carries 09:35/09:45/10:00.
    // Tick the first bar at or after the bell instead (and, on the live
    // frame, the first bar that is not extended-hours).
    if (!openTicked && hm >= '09:30' && !b.s) {
      openTicked = true;
      ticks.push({ i, label: 'open', major: false });
    } else if (hm === '16:00') {
      ticks.push({ i, label: '16:00', major: false });
    }
  });
  if (ticks.length <= max) return ticks.map(({ i, label }) => ({ i, label }));
  const majors = ticks.filter((t) => t.major);
  const minors = ticks.filter((t) => !t.major);
  // Day boundaries are thinned too when there are more of them than fit —
  // a 47-session hourly frame produced 48 labels smeared along the axis
  // (review 2026-09-02). Minors are dropped first, then majors are stepped.
  if (majors.length >= max) {
    const step = Math.ceil(majors.length / max);
    return majors.filter((_, k) => k % step === 0).map(({ i, label }) => ({ i, label }));
  }
  const room = max - majors.length;
  const step = room > 0 ? Math.ceil(minors.length / room) : 0;
  const kept = step > 0 ? minors.filter((_, k) => k % step === 0) : [];
  return [...majors, ...kept].sort((a, b) => a.i - b.i)
    .map(({ i, label }) => ({ i, label }));
}

export function monthTicks(bars: CmBar[], max = 6): { i: number; label: string }[] {
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const ticks: { i: number; label: string; year: string }[] = [];
  let prev = '';
  bars.forEach((b, i) => {
    const mo = (b.t || '').slice(0, 7);
    if (mo && mo !== prev) {
      prev = mo;
      const m = Number(mo.slice(5, 7));
      if (m >= 1 && m <= 12) ticks.push({ i, label: MON[m - 1], year: mo.slice(0, 4) });
    }
  });
  const shown = ticks.length <= max
    ? ticks
    : ticks.filter((_, i) => i % Math.ceil(ticks.length / max) === 0);
  // Years on the SHOWN set, decided after thinning: the first tick and every
  // year change carry theirs ("Aug '25 … Feb '26"). A year-long window reading
  // "Aug Nov Feb May Aug" left which-Aug-is-which to guesswork (Ajay
  // 2026-09-01: "add years to the calendar months at the bottom").
  let prevYear = '';
  return shown.map((t) => {
    const label = t.year && t.year !== prevYear
      ? `${t.label} '${t.year.slice(2)}` : t.label;
    prevYear = t.year || prevYear;
    return { i: t.i, label };
  });
}

/** Index of a dated marker within the bar window, or -1.
 *  Joined by DATE, never by index — the ledger's indices are offsets into the
 *  full cached frame, not into the window drawn here. */
export function markerIndex(bars: CmBar[], date: string): number {
  const d = (date || '').slice(0, 10);
  if (!d) return -1;
  return bars.findIndex((b) => b.t === d);
}

/* ── formatting ───────────────────────────────────────────────────────────── */

/* Order here mirrors backend THEME_PRIORITY (sepa/universe.py) — Ajay's stated
 * priority, most-wanted first. The board already sorts by it; keeping the same
 * order here means the legend and the tiles tell the same story. */
export const THEME_LABEL: Record<string, string> = {
  space: '🛰 Space',
  quantum: '⚛ Quantum',
  ai_semis: '🔲 AI semis',
  optical: '💡 Optical',
  robotics: '🦾 Robotics',
  ai_infra: '⚡ AI infra',
  nuclear: '☢ Nuclear',
  defense: '🎖 Defense',
  rare_earth: '⛏ Rare earth',
  // 2026-09-11 — the layer under the chip: consumables, test and packaging.
  semi_materials: '🧪 Semi materials',
};

export function themeLabel(theme: string | null | undefined): string | null {
  if (!theme) return null;
  return THEME_LABEL[theme] || theme.replace(/_/g, ' ');
}

/** One honest line about a pattern's record.
 *
 * Always states the loss side and the sample size. Never compares patterns to
 * each other — their stop brackets differ ~2x, which is exactly the broken
 * comparison the 2026-07-10 pattern audit found. */
export function recordLine(r: CmPatternRecord | null | undefined): string {
  if (!r || !r.n) return 'no resolved observations yet';
  const pct = r.win_pct == null ? '—' : `${r.win_pct}%`;
  return `${r.wins} hit target · ${r.losses} stopped out · ${pct} of ${r.n}`;
}

/** Small-sample guard. Under this many resolved observations a win rate is a
 *  number, not a finding. */
export const MIN_SAMPLE = 20;

export function isThinSample(n: number | null | undefined): boolean {
  return !n || n < MIN_SAMPLE;
}

/* ── scan freshness ───────────────────────────────────────────────────────── */

/** Parse a backend scan timestamp — ISO string (demand `as_of`) or epoch
 *  seconds/ms (older caches) — to epoch ms, or null. */
export function parseScanTs(raw: string | number | null | undefined): number | null {
  if (raw == null) return null;
  if (typeof raw === 'number') {
    if (!Number.isFinite(raw) || raw <= 0) return null;
    return raw < 1e12 ? raw * 1000 : raw;
  }
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}

/** "Scanned just now" / "Scanned 4m ago" / "Scanned 3h ago" / "Scanned 2d ago".
 *  Null when the backend sent no timestamp — the stamp then simply doesn't
 *  render; a made-up "just now" is exactly the false reassurance this exists
 *  to prevent (Ajay 2026-08-25: same tiles two days running looked stale, and
 *  the board carried nothing that could prove otherwise). */
export function scanStamp(raw: string | number | null | undefined, nowMs: number): string | null {
  const ts = parseScanTs(raw);
  if (ts == null) return null;
  const sec = Math.max(0, (nowMs - ts) / 1000); // clock skew → clamp, not lie
  if (sec < 90) return 'Scanned just now';
  const min = Math.round(sec / 60);
  if (min < 90) return `Scanned ${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 36) return `Scanned ${hr}h ago`;
  return `Scanned ${Math.round(hr / 24)}d ago`;
}

/** "data through Aug 25" — the newest bar date any tile on the board carries.
 *  This is the half a wall-clock stamp can't answer: a scan run five minutes
 *  ago over week-old bars is still stale. Null when no tile has bars. */
export function dataThrough(tiles: { bars?: CmBar[] }[] | null | undefined): string | null {
  let best = '';
  for (const t of tiles || []) {
    const last = t.bars?.[t.bars.length - 1];
    if (last?.t && last.t > best) best = last.t;
  }
  if (!best) return null;
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const m = Number(best.slice(5, 7));
  const d = Number(best.slice(8, 10));
  if (!(m >= 1 && m <= 12) || !d) return null;
  return `data through ${MON[m - 1]} ${d}`;
}

/** The 🚀 Breaking board's stamp line (2026-09-06) — the same facts the
 *  zone-edge list said above Deep Demand: which pass the cards are, whether
 *  it is live, and the backend's own reason when it is not. The stamp is
 *  already ET with its offset, so the clock is a substring, never a
 *  timezone conversion (same rule as ZoneEdgeBoard.hhmm). */
/** The lid-break study line under the \u{1F680} Breaking pass line (2026-09-07). Every
 *  rate next to its placebo and n; null when the study has not run yet. */
export function lidBreakStudyText(m: CmLidBreak | null | undefined): string | null {
  if (!m || !m.events) return null;
  const pct = (v: number | null | undefined) => (v == null ? '\u2014' : `${Math.round(v)}%`);
  const n = (v: number | null | undefined) => (v == null ? '' : ` (n=${v})`);
  const parts: string[] = [];
  parts.push(`${m.events} breaks of the last lid across ${m.names ?? '?'} names`);
  parts.push(`${pct(m.hit_52w_21_pct)} reached the prior 52-week high within 21 sessions${n(m.hit_52w_21_n)} vs ${pct(m.placebo_any_21_pct)} from any day / ${pct(m.placebo_up_21_pct)} from any up-day`);
  parts.push(`${pct(m.hit_52w_63_pct)} within 63${n(m.hit_52w_63_n)} vs ${pct(m.placebo_any_63_pct)} / ${pct(m.placebo_up_63_pct)}`);
  if (m.median_days_to_52w_63 != null) parts.push(`median ${m.median_days_to_52w_63} sessions to get there`);
  parts.push(`${pct(m.failed_21_pct)} closed back under the lid within 21`);
  if (m.median_runup_21_pct != null) parts.push(`median best run +${m.median_runup_21_pct}% in 21 / +${m.median_runup_63_pct ?? '\u2014'}% in 63`);
  if (m.proven_hit_52w_21_pct != null || m.single_hit_52w_21_pct != null) {
    parts.push(`proven lids ${pct(m.proven_hit_52w_21_pct)}${n(m.proven_n)} vs single-touch ${pct(m.single_hit_52w_21_pct)}${n(m.single_n)}`);
  }
  if (m.volc_hit_52w_21_pct != null) parts.push(`volume-confirmed breaks ${pct(m.volc_hit_52w_21_pct)}${n(m.volc_n)}`);
  const d = m.dist || {};
  const dparts = Object.keys(d).filter(k => d[k] && d[k]!.pct != null).map(k => `${k} away ${pct(d[k]!.pct)}${n(d[k]!.n)}`);
  if (dparts.length) parts.push(`by distance to that high: ${dparts.join(', ')}`);
  return parts.join(' \u00b7 ');
}

export function breakingPassText(b: Pick<CmBoard, 'pass_as_of' | 'in_session' | 'reason' | 'tape_session'>): string {
  const iso = b.pass_as_of ? String(b.pass_as_of) : '';
  const hhmm = iso.length >= 16 && iso[10] === 'T' ? iso.slice(11, 16) : '';
  const why = b.reason && b.reason !== 'no pass yet' ? b.reason : '';
  if (!hhmm) return why ? `no pass yet today \u2014 ${why}` : 'no pass yet today';
  if (b.in_session && (b.tape_session === 'premarket' || b.tape_session === 'afterhours')) {
    // 2026-09-08: the pass AND the phone run 4:00–20:00 ET (Ajay: "Make phone push also pre and post market").
    const tape = b.tape_session === 'premarket' ? 'pre-market' : 'after-hours';
    return `${tape} pass as of ${hhmm} ET \u00b7 thin tape, pushes on 4:00\u201320:00 ET; these cards refresh every 5`;
  }
  if (b.in_session) return `as of ${hhmm} ET \u00b7 the pass runs every minute in session; these cards refresh every 5`;
  if (why) return `${why} (${hhmm} ET)`;
  return `market closed \u2014 last pass ${hhmm} ET`;
}

/** One line under any board read outside regular hours (2026-09-08): where the
 *  `now` lines came from. Empty in RTH / closed — nothing to explain. */
export function sessionNoteText(session: CmTapeSession | null | undefined): string {
  if (session === 'premarket') return '\u{1F305} pre-market prints: every now line sits on the last pre-market trade (now \u00b7 pre) \u2014 thin tape; phone pushes are on from 4:00 ET';
  if (session === 'afterhours') return '\u{1F319} after-hours prints: every now line sits on the last after-hours trade (now \u00b7 AH) \u2014 thin tape; phone pushes stay on until 20:00 ET';
  return '';
}
