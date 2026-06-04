/* researchContent — expert interpretation + adversarial validation of the
   bullish/bearish patterns, authored by a multi-agent pass (2026-06-04) and
   reviewed against the code. The /research page merges this narrative with the
   LIVE prevalence numbers from /research/patterns (keyed by pattern key). */
export type PatternNote = {
  key: string; label: string; plain_english: string;
  why?: string; confidence: 'high' | 'medium' | 'low'; caveat?: string;
};
export type ResearchContent = {
  thesis_verdict: string; watch_summary: string;
  bullish: PatternNote[]; bearish: PatternNote[];
  overlaps: string[]; key_caveats: string[];
};

export const RESEARCH_CONTENT: ResearchContent = {
  "thesis_verdict": "The insider thesis is partly true in a way that inverts its own conclusion. Bullish names genuinely show far more insider FILING ACTIVITY — 75% had at least one Form 4 in the last 30 days versus 25% of falling names, a clean 3x gap. But \"activity\" is not \"buying.\" The any-Form-4 metric (form4_count_30d) is EDGAR full-text-search metadata that only means an insider filed SOMETHING, and on a stock that already ran up that something is overwhelmingly the bearish-leaning kind: vested grants, option exercises, and sells as insiders harvest the move. The conviction tell the thesis actually cares about — an officer or director putting their own cash in via an open-market purchase (Section-16 code P, acquired) — was 0% in the bullish cohort and slightly HIGHER at 8.3% in the falling cohort, which is textbook insider dip-buying. So the literal claim \"bullish stocks all have insiders, falling ones don't\" fails twice over: it wasn't all (75%, not 100%), the falling cohort wasn't empty (25%), and the one metric that means insiders are bullish-by-wallet leaned the other way. The detection logic itself is sound — insider.py excludes grants/exercises/tax-withholding from buys (only code P + acquired sets is_buy, line 218) and the cluster gate requires >=2 distinct officer/director open-market buyers — so the activity-vs-buying split is a real property of the data, not a measurement artifact. Honest read: insider filing volume tracks the recent move (more paperwork where price already ran), but insider buying does not confirm these particular up-moves and if anything showed up more in the names that fell. Confidence is medium and the buy-side numbers are directional only: at 12 names per cohort, 0% vs 8.3% is one name flipping, and rate-limiting in _fetch_form4_detail (returns None on any throttled non-200 response, line 274) can only MISS real buys never invent them, so both buy rates are floors that a clean re-run could move.",
  "watch_summary": "For new leadership, watch trajectory not just today's level: a stealth riser that sat at the bottom or off the qualifier board entirely for most of the last ~45 days and shot into the top ranks only in the final week or two is where the next leg of relative strength tends to come from, before the crowd prices it as a leader. Confirm any candidate with accelerating rank (the climb curving upward, not a steady grind) plus durable day-to-day persistence near the top, and screen out round-trip head-fakes that spiked mid-window and faded. Use the clean Minervini triggers — a fresh high-volume breakout and a 70+ SEPA score — as the real entry filter, since both were nearly absent here (about 2 of 35 winners each), meaning this scan caught momentum that already extended rather than fresh setups; treat the headline bullish flags as confirmation a name is already in an uptrend, not proof it will keep outperforming.",
  "bullish": [
    {
      "key": "rs_strong",
      "label": "Top-tier relative-strength leader (RS 80+)",
      "plain_english": "About half the winners are top-tier relative-strength leaders while zero losers are, making it one of the cleanest leadership separators in the set.",
      "why": "Relative strength rank is a ranking of trailing price performance, so the best 3-month performers cluster at RS 80+ and laggards cannot be there; RS leadership is also one of the most robust Minervini filters that holds up outside this sample.",
      "confidence": "high",
      "caveat": "Partly circular: RS is built from the same trailing return used to split the cohorts, and the bear 0% rests on zero names so the 49-point lift cannot get smaller. It is also ambiguous whether RS is ranked versus the broad market or versus this semiconductor-tilted 105-name basket, which changes its meaning. Treat the separation as definitional confirmation, but RS leadership remains genuinely predictive in general."
    },
    {
      "key": "trend_strong",
      "label": "Passes 7-8 of 8 trend-template checks",
      "plain_english": "Winners usually pass at least 7 of Minervini's 8 trend-template checks while losers rarely do.",
      "why": "The trend template aggregates price-above-MA, MA alignment, and distance-from-high into one score, capturing the whole uptrend gestalt that sustained winners satisfy and laggards fail.",
      "confidence": "high",
      "caveat": "The template is a composite built from price-vs-MA and 52-week-high proximity, all functions of trailing return, so it partially restates the cohort definition and double-counts the same uptrend already captured by above_200dma, ma_stacked, and near_high. Its lift is not independent evidence, and it still misclassifies a notable share of winners. A confirming descriptor, not a forward predictor."
    },
    {
      "key": "above_200dma",
      "label": "Trading above the 200-day moving average",
      "plain_english": "Almost every winner trades above its 200-day moving average and almost no loser does.",
      "why": "Price above the 200-day line is the basic definition of a long-term uptrend, and stocks that ran up are above it while stocks down 6-35% over three months have usually fallen below it.",
      "confidence": "high",
      "caveat": "Near-tautological with the cohort definition and the most circular flag in the set: a stock cannot post a big trailing 3-month gain and still sit below a slow 200-day average, so the 88-point lift restates 'this stock went up' rather than predicting it. The bear side rests on roughly one name. Zero forward-looking content; useful only as a baseline trend filter, not an edge."
    },
    {
      "key": "ma_stacked",
      "label": "Moving averages stacked 50 > 150 > 200",
      "plain_english": "Winners more often have their moving averages stacked in bullish order with the 50-day above the 150-day above the 200-day.",
      "why": "Proper MA stacking is the signature of a sustained Stage 2 uptrend where every timeframe agrees, which a multi-month winner produces and a faller breaks.",
      "confidence": "high",
      "caveat": "A lagged, smoothed restatement of 'price has been rising for months,' which is the cohort sort variable. The 46-point lift overlaps heavily with above_200dma and trend_strong (they fire on the same names) so it adds little independent signal. Confirming, not predictive."
    },
    {
      "key": "near_high",
      "label": "Within ~25% of the 52-week high",
      "plain_english": "Winners are sitting close to their 52-week high while losers are well off theirs.",
      "why": "A stock making fresh highs has buyers in control and no overhead supply of trapped sellers, the textbook condition for continued advance, whereas a falling stock is by definition far below its high.",
      "confidence": "high",
      "caveat": "Circular with the sort variable: being within 25% of the high is almost a deterministic consequence of a strongly positive trailing return, so a stock up +54% median is near its high by construction. It tells you a name that already went up is near its high, not that a near-high name will outperform from here."
    },
    {
      "key": "rank_persistent_leader",
      "label": "Persistent top-rank leader (held the top, low rank volatility)",
      "plain_english": "A stock that has stayed in the top ranks almost every single day of the window, with low rank volatility, is a durable leader the market keeps re-confirming.",
      "why": "This is the bullish counterpart to the volatility-as-bear-tell the study already found: a name with persistence near 100%, low rank-stdev, and best and current rank both in the top tercile is one the market re-confirms daily, and in a momentum sample the median +54% bull cohort is dominated by names that simply never leave the top of the board.",
      "confidence": "medium",
      "caveat": "Untested proposal at high risk of being tautological: rank is derived from the SEPA score, the cohort is derived from 3-month return, and in this curated tech universe the top-ranked and top-return names are largely the same, so a big lift may just restate 'leaders led.' Persistence is also inflated for any stock that was merely a qualifier every day regardless of where it ranked, so pair persistence% with an actual top-tercile rank threshold. Treat as confirmation, not edge."
    },
    {
      "key": "stage2",
      "label": "Confirmed Stage 2 advance",
      "plain_english": "Winners are more likely to be in a confirmed Stage 2 advance, the only stage where institutional accumulation drives price steadily higher.",
      "why": "Stage 2 is where sustained winners live because price rises on accumulation above rising moving averages, while falling stocks have rolled into Stage 3 or 4.",
      "confidence": "medium",
      "caveat": "Stage 2 is defined by an established uptrend (price above rising MAs), which is mechanically what the bullish-return cohort exhibits, so the 31-point lift is largely a relabeling and overlaps with trend_strong, ma_stacked, and above_200dma. Only 37% of even the winners are flagged Stage 2 on n=35, so it separates well but is far from present in all winners — confirming, not necessary, and fragile at this sample size."
    },
    {
      "key": "rank_stealth_riser",
      "label": "Stealth riser (bottom/absent for ~45d, then top ranks in last 1-2 weeks)",
      "plain_english": "A stock that sat at the bottom of the rankings or wasn't even a qualifier for most of the last ~45 days and then shot into the top ranks in just the last week or two.",
      "why": "The cohort study only sees a name's current 3-month return, but a stock whose rank went from absent or deep-worst to top-decile in the final stretch is one the crowd hasn't yet priced as a leader, and in a momentum tape these late igniters are where the next leg of relative-strength expansion comes from before they show up on everyone's already-a-leader screens.",
      "confidence": "medium",
      "caveat": "Untested proposal and the headline bullish idea, but forward-looking by nature: the cohort study labels by TRAILING return, so a name that only just moved may still sit in the middle or bear tercile today and may not even land in the bullish cohort, meaning it is better validated by forward outcomes than by the current split. Definition is fragile — a true stealth riser spends early days as rank=None (not a qualifier), and rank_history.py confirms None days are genuine gaps, so you must decide whether None is 'worse than worst rank' or excluded; the two choices give different stocks. With ~45 daily points on a fluctuating qualifier base, the count of genuine stealth risers per scan may be low single digits and noisy."
    },
    {
      "key": "rank_acceleration",
      "label": "Accelerating rank (climb curving upward, not linear)",
      "plain_english": "A stock whose rank is not just improving but improving faster each week, so the climb curves upward rather than grinding in a straight line.",
      "why": "This separates explosive emerging leaders from slow-and-steady names: a steady climber improves linearly while an accelerating one shows second-derivative improvement, and Minervini-style power plays and the +286% tail of the bull cohort tend to come from acceleration rather than gradual drift.",
      "confidence": "medium",
      "caveat": "Untested proposal. Second derivatives are very noisy on rank data that is integer-valued, capped at the fluctuating qualifier count, and gappy with None days. Acceleration is also mechanically bounded near the top — a stock already at rank 1-3 cannot accelerate further, so the metric mislabels established leaders as 'not accelerating' — and it needs a minimum of roughly 15 non-None points or it fires on noise."
    },
    {
      "key": "rank_fresh_top_entry",
      "label": "Fresh top-10 entry (first-ever crossing into the leaderboard)",
      "plain_english": "A stock that broke into the top ranks for the very first time in the window within the last few days is a brand-new entrant to the leaderboard.",
      "why": "A lighter, more tradable cousin of the stealth riser built on a crisp testable event — first-ever crossing of a fixed rank threshold with no prior point ever there — and new leadership entries are where fresh institutional sponsorship shows up; it maps directly onto the app's existing became_buyable edge concept in rank_history.py, which fires once rather than describing a level.",
      "confidence": "medium",
      "caveat": "Untested proposal and threshold-sensitive: a fixed top-10 cutoff means different percentiles on different days because rank_history.py confirms the denominator is only the trend.pass_all qualifiers, which fluctuates scan to scan and is not fixed at 105, so consider a percentile threshold instead. Like the stealth riser it is forward-looking and may post a weaker measured lift than its predictive value, since it may not align with the trailing-return cohort labels."
    },
    {
      "key": "accumulation",
      "label": "Up/down volume ratio above 1.3",
      "plain_english": "Winners show somewhat more up-volume than down-volume, a sign big buyers are stepping in.",
      "why": "An up/down volume ratio above 1.3 means accumulation days outweigh distribution days, the footprint of institutions building positions that fuels an advance.",
      "confidence": "low",
      "caveat": "Weak and overlapping: volume follows price in advances so this partially restates the cohort, the gap is a modest 23 points (43% vs 20%) driven by roughly 15 vs 7 names on n=35 (within sampling noise), and accumulation still appears in a fifth of losers. Not a clean separator; useful only alongside the trend signals."
    },
    {
      "key": "hi_vol_breakout",
      "label": "Recent high-volume breakout (the actual Minervini buy trigger)",
      "plain_english": "Very few winners show a recent high-volume breakout, but the handful that do are all winners and no losers carry it.",
      "why": "A fresh breakout on heavy volume marks a brand-new advance and is the actual Minervini buy trigger, but most names in this cohort broke out months ago and are already extended, so only a couple show a recent one.",
      "confidence": "low",
      "caveat": "Statistically meaningless at this sample size: about 2 of 35 winners (5.7%) versus 0 of 35 losers, so the 6-point lift is one or two stocks and one name flipping moves it ~3 points. Its near-total absence across the universe (about 2 of 105) is itself the key tell — the scan caught momentum that already extended, not fresh breakouts — so use a real high-volume breakout as an entry filter rather than reading anything into this lift."
    },
    {
      "key": "score_high",
      "label": "SEPA composite score 70+",
      "plain_english": "Almost no stocks in either cohort clear a SEPA score of 70, but the few that do are winners.",
      "why": "A 70+ composite SEPA score demands fundamentals and technicals to line up at once, a high bar most names in a fast-moving momentum sample do not meet even when price is rising.",
      "confidence": "low",
      "caveat": "Statistically meaningless and internally contradictory: only about 2 of 35 winners (5.7%) clear 70 and 0 losers, so the proprietary score barely separates the cohorts (+6 lift) even though its own components — trend, RS, stage — individually show 30-50 point lifts. Either the threshold is mis-calibrated for this universe or the components are being diluted. Decision-useless at n=2, but a genuine 70+ remains a sensible entry gate."
    }
  ],
  "bearish": [
    {
      "key": "trend_weak",
      "label": "Fails most of the 8-point trend template (score <=3)",
      "plain_english": "Stocks that failed most of Minervini's 8-point trend template clustered hard in the losers.",
      "why": "The trend template checks that price and moving averages are stacked in bullish order with the stock near its highs, so failing it means the stock lacks the structural uptrend institutions buy into and tends to keep lagging.",
      "confidence": "high",
      "caveat": "Composite of price-below-MA and far-from-high criteria, i.e. a restatement of negative trailing return (the cohort sort), so the -46 lift is largely circular and redundant with below_200dma and rs_weak. It also misclassifies over a third of winners (bull 37%), so even as a descriptor it is noisy on n=35."
    },
    {
      "key": "rs_weak",
      "label": "Relative-strength rank 40 or below",
      "plain_english": "Laggards with a relative-strength rank of 40 or below were three times more common in the bottom cohort than the top.",
      "why": "Relative strength is trailing outperformance versus the market and leadership tends to persist, so weak RS today usually means the stock keeps underperforming as money keeps flowing to the leaders instead.",
      "confidence": "high",
      "caveat": "Circular: RS rank <=40 is low trailing relative strength, essentially the variable the cohorts were sorted by, so the -43 lift is definitional. Same broad-market-vs-basket ranking ambiguity as the bullish RS flag — in this tilted universe it may measure rank within the basket rather than versus the market."
    },
    {
      "key": "below_200dma",
      "label": "Trading below the 200-day moving average",
      "plain_english": "Stocks trading under their 200-day moving average were almost all in the worst-performing third of the list.",
      "why": "The 200-day line divides long-term uptrends from downtrends, and price below it means supply is in control and the stock is in a Stage 4 decline or basing — the opposite of the institutional accumulation that drives winners.",
      "confidence": "high",
      "caveat": "Near-mechanical and the inverse of above_200dma: a stock cannot post a big positive 3-month return and still be below a slow 200-day average, so the -88 lift is the cohort definition restated, not a predictor. The bull side rests on roughly three names."
    },
    {
      "key": "far_below_high",
      "label": "More than 40% below the 52-week high",
      "plain_english": "Stocks sitting more than 40% below their 52-week high were heavily concentrated in the worst performers.",
      "why": "A deep drawdown means the stock is buried under trapped overhead supply where every prior buyer is underwater and sells into rallies, which caps upside and is the signature of a broken leader rather than a setup.",
      "confidence": "high",
      "caveat": "Circular with the sort variable and the inverse of near_high: being >40% below the high is a mechanical consequence of a deeply negative 3-month return, so the -32 lift restates the cohort rather than predicting it."
    },
    {
      "key": "rank_falling_knife_collapse",
      "label": "Falling knife (former top leader in a sustained rank downtrend)",
      "plain_english": "A stock that was a top-ranked leader earlier in the window and has been falling through the ranks fast and steadily ever since.",
      "why": "This is the bearish trajectory analogue to the stealth riser and a cleaner bear tell than a single-day low rank: a name whose rank deteriorated monotonically from a top-tercile best to a bottom-tercile current is losing relative strength in real time, classic Stage 3-into-Stage 4 rolling-over behavior, and unlike a static rs_weak flag it catches former leaders mid-breakdown before trailing return fully reflects it.",
      "confidence": "medium",
      "caveat": "Untested proposal. In a strong bull sample like this one (bear cohort is only -35% to -6%, i.e. mild) there may be very few genuine top-to-bottom rank collapses, so the bearish count could be too small for a meaningful lift. Rank collapse also frequently ends with the stock dropping out of qualifiers entirely (rank goes to None, which rank_history.py confirms is a real gap), truncating the trajectory, so you must decide how to score a knife that falls off the board or you will systematically miss the worst cases."
    },
    {
      "key": "distribution",
      "label": "Distribution (down/up volume ratio below 0.9)",
      "plain_english": "Stocks showing distribution, with more volume on down days than up days, were over-represented among the losers.",
      "why": "An up/down volume ratio below 0.9 means institutions are selling into the stock more aggressively than buying it, and sustained big-money selling is what turns a stock into a laggard and keeps it there.",
      "confidence": "medium",
      "caveat": "Partially circular and noisy: down/up volume below 0.9 tends to accompany falling prices so it co-moves with the negative-return cohort definition, the -26 lift comes from roughly 13 vs 4 names on n=35, and the winner cohort still shows 11% distribution. A supporting tell, not a standalone reason to avoid a name."
    },
    {
      "key": "stage4",
      "label": "Stage 4 decline",
      "plain_english": "Stocks classified as being in a Stage 4 decline were about three times more common in the bottom cohort.",
      "why": "Stage 4 is the markdown phase where the stock is rolling over below a falling 200-day average, so by definition these are the names being actively distributed and trending down, which is exactly what produces poor trailing returns.",
      "confidence": "medium",
      "caveat": "Stage 4 is defined as a sustained downtrend, which is what the bear cohort is by construction, so the flag is circular and overlaps heavily with below_200dma and trend_weak. Magnitude is also small and fragile: bull 8.6% vs bear 28.6% is roughly 3 vs 10 names on n=35, so a handful of reclassifications would move the -20 lift materially."
    },
    {
      "key": "rank_round_trip_pump_fade",
      "label": "Round-trip pump-fade (spiked mid-window, gave it all back)",
      "plain_english": "A stock that spiked up into good ranks mid-window and then gave it all back, ending roughly where it started or worse.",
      "why": "This tests trajectory SHAPE rather than start-vs-end level, which no existing pattern does: a name whose rank peaked in the middle third and has since faded is showing a failed-breakout or distribution signature, and it catches the exact false positive the stealth-riser idea is most exposed to — a head-fake that rose then rolled rather than a name still rising at the end.",
      "confidence": "low",
      "caveat": "Untested proposal and the weakest of the set: distinguishing a mid-window peak from end-window strength on ~45 noisy integer points is fragile, and in a momentum bull tape these round-trips are rare so cohort counts will be small. Mainly valuable as a NEGATIVE filter to subtract from stealth-riser and fresh-top-entry candidates rather than as a standalone bull/bear tell."
    },
    {
      "key": "low_vol",
      "label": "Lowest daily price swings (sample artifact)",
      "plain_english": "Stocks with the lowest daily price swings showed up more often among the losers, but only because this market's winners happened to be the wild semiconductor movers.",
      "why": "In this momentum-led tech sample the biggest gainers like AMD and ARM are inherently high-volatility names, so calm low-volatility stocks landed in the bottom by contrast — the low volatility isn't causing the underperformance, it's just correlated with which sector led.",
      "confidence": "low",
      "caveat": "SAMPLE ARTIFACT, not a general rule and the mirror of the high-volatility bullish artifact: the -31 lift (bear 40% vs bull 8.6%) is regime- and sector-conditional, and in a normal or risk-off market low volatility is typically protective or neutral. Do not trade off this signal."
    },
    {
      "key": "late_base",
      "label": "Late-stage base (4th or later)",
      "plain_english": "Late-stage bases leaned slightly toward the losers, but the tilt is weak and nearly a coin flip.",
      "why": "Minervini warns that by the 4th base a move is widely recognized and prone to failure as late buyers get shaken out, which can drag forward returns, but base count is about future failure risk rather than past return so the link to trailing performance is loose.",
      "confidence": "low",
      "caveat": "Effectively non-discriminating: bull 45.7% vs bear 54.3% is a -9 lift, roughly 16 vs 19 names, well inside noise on n=35, so both cohorts are about half late-stage bases. Treat as a yellow flag for future failure risk, not evidence the stock is a current laggard."
    }
  ],
  "overlaps": [
    "Institutional liquidity (liquid): 100% in BOTH cohorts, lift 0 — this is a pre-filter applied to the entire 105-name universe before the split, so it cannot separate anything by construction. It was a fixed entry criterion, not something that was tested; do not read its presence as a discriminating signal.",
    "Early base, 1st-2nd stage (early_base): bull 37.1% vs bear 34.3%, +3 lift (roughly 13 vs 12 names) — pure noise on n=35 with zero discriminating power. Its 'base stage' label should not imply otherwise.",
    "VCP base present (vcp_base): 0% in both cohorts, but this is MISSING DATA, not absence — VCP was never computed in this fast scan. Listing it as zero-lift invites the false reading that VCP doesn't matter or isn't present, when in fact the single most important Minervini setup pattern was simply never evaluated. It requires a deep scan before any inference and must be excluded, not treated as informative.",
    "Power Play (power_play): 0% in both cohorts for the same reason — not computed in the fast scan. This is absent data masquerading as a null result, not evidence that Power Plays are irrelevant or nonexistent in the sample. Mark unavailable and re-run a deep scan to evaluate it.",
    "Late-stage base (late_base) borders on non-discriminating too: at a -9 lift with a 46% vs 54% split it is barely better than random and is listed under bearish only as a weak risk flag, not a reliable separator."
  ],
  "key_caveats": [
    "Momentum-universe / regime artifact: the entire sample is a curated, semiconductor-heavy tech basket in a bull tape, so several flags invert their normal meaning. High volatility and deep >40% bases show up as 'bullish' here ONLY because high-beta chips draw down hard then rip +50% to +286%; in Minervini's actual method a base deeper than ~40% is a RED FLAG and high volatility associates with risk and drawdowns, not leadership. Do not read 'buy deep bases' or 'chase volatility' from this — that is the opposite of the book and the opposite of what holds in a normal or risk-off market.",
    "Circularity with the cohort definition: the cohorts were split by trailing 3-month return, so the biggest-lift flags — above_200dma (88 pts), near_high, RS rank, MA-stacking, trend template, Stage 2 — are near-tautological restatements of 'this stock already went up,' not predictions that it will keep going up. Several bear-side mirrors (below_200dma, rs_weak, far_below_high) are the same circularity inverted. Use these to confirm a name is in an uptrend, never as standalone evidence of an edge.",
    "Small sample throughout: 35 names per cohort for the pattern table and only 12 per cohort for the insider analysis. The genuinely tradable Minervini setups — high-volume breakout (about 2 of 35 winners) and SEPA score 70+ (about 2 of 35 winners) — and several bear flags (Stage 4 ~3 vs 10, distribution ~13 vs 4) rest on a handful of names where one stock flipping moves the lift by ~3 points. The proposed rank-trajectory patterns are all UNTESTED against the cohorts and noisier still on ~45 integer, gappy daily points.",
    "Insider rate-limiting is asymmetric: open-market BUY and cluster detection require fetching and parsing each Form 4 XML, and insider.py's _fetch_form4_detail silently returns None on any throttled non-200 response (line 274), so real buys can only be MISSED, never invented. Both cohorts' buy rates (0% bullish, 8.3% bearish) are therefore FLOORS that a clean un-throttled re-run could move, and the 0% vs 8.3% gap is one or zero names — directional only, not statistically distinguishable. The any-Form-4 ACTIVITY count does not depend on the XML parse and is reliable.",
    "No timing or causality test anywhere: cohorts were labeled by CURRENT trailing return, then every signal — technical flags, rank state, and insider state — was read after the fact. This sample cannot separate 'the signal predicted the move' from 'the move produced the signal,' which is why the rank-trajectory and stealth-riser patterns are better validated by forward outcomes than by the current bull/bear split, and why insider filing volume clustering on already-risen names proves nothing about predictive edge."
  ]
};

const _byKey: Record<string, PatternNote> = {};
for (const p of [...RESEARCH_CONTENT.bullish, ...RESEARCH_CONTENT.bearish]) _byKey[p.key] = p;
export function noteFor(key: string): PatternNote | undefined { return _byKey[key]; }