# Independent backtests, replications and critiques of US Investing Championship (USIC) winners' public strategies
Label: backtests-critiques. Compiled 2026-11-01. Every claim carries the URL that was actually read (or is marked SNIPPET-ONLY).
Web-search budget for the run ran out near the end, so some threads were not followed (see "Gaps" at the bottom).
Reddit could not be searched or read: the search tool refuses reddit.com. X/Twitter posts return 402/451; nitter is down (cease-and-desist notice); threadreaderapp had no unroll.

## TL;DR
- **Gajjala: nobody has published a backtest of his rules.** The only "modification" source is F4VS's free Substack series (May–Aug 2024). It is a faithful summary of GG's free Momentum Access masterclass. The author adds opinions (invalid examples, "a base breakout before the setup is more favourable", "combining setups may raise the hit rate") and **no numbers**.
- **GG's own stats (as reported by TraderLion, SNIPPET-ONLY) do not reproduce his return mechanically.** 750 trades, 31% win rate, +8.55% average win, −4.06% average loss. My arithmetic: the expectancy is **−0.15% per trade** (about −0.04R), and the breakeven win rate at a 2.1 payoff is 32.2%. A fixed-fractional replay of those stats loses money, so the +805% came from variable sizing and fat-tail outliers (e.g., TPST, held through a 1,000% intraday move) that a mechanical rule set will not capture. This is an inference from the reported stats, not a published test.
- **GG himself reported decay** (X, 2024-10-11, read via search snippet): his setups were absent "for very extended periods", the probability of them working was "drastically reduced", he overtraded into a drawdown, YTD returns were only double digits, and he is trading almost nothing. Earlier a note on F4VS's Substack (2024-06-03) said GG announced he would discontinue services for health reasons.
- **Gajjala's 2023 path was violent.** April +65.3%, May +47%, then **June −44.4%** after **17 straight losers** (revenge trading). He was absent from the June–August USIC boards, reappeared at +266.5% after nine months, and finished at +805.1%.
- **Oliver Kell: one large independent test exists.** The Premarket Brief, 2026-10-31, tested 66,314 MA reclaims on the S&P 500+600 over 2010–2026. The full Wedge Pop scored +0.222R per trade (37.3% win), which is *worse* than any reclaim with no pattern (+0.246R). Dropping the capitulation step improved it to +0.343R. **Kell's prescribed exit (close below the 20-day) cut expectancy to +0.064R, removing 71% of the edge.** The only component that helped was an unfilled breakaway gap.
- **Martin Luk (2025, +969.8%) is the one champion with two independent, coded, public replications. They disagree.**
  - rootchunhe (CRSP+TAQ, point-in-time, after costs): CAGR 12.1%, Sharpe 0.83 (equal to QQQ's), max DD −13%. Nearly all the edge is in the pullback *timing*; his morning-breakout entry loses after spreads.
  - zongfan2/TradingAgents (all three setups, 5-minute SIP data): −58.3% total, −87.6% max DD, −0.009R per trade.
  - A third, paid replication (Signal&Moat) claims +1,450% at 3× leverage. It is commercially motivated and internally inconsistent.
- **Minervini-style VCP / O'Neil cup-and-handle (Premarket Brief).** Progressive contraction added only +0.023R over its own control across 74,500 breakouts. The textbook 5-rule cup-and-handle was the *weakest* version (+0.181R, t=1.83). Relative strength versus the index was the only checklist item that helped.
- **The contest itself.** Only 8% (2022, 26 of 316) and 17% (H1 2026, 115 of 688) of entrants reported profits. The published table is the right tail. Monthly listing is optional, late entry starts the scoring clock, and returns are time-weighted, statement-checked and not audited. Peak-to-final giveback is large (Luk peaked at +1,358% in November and finished at +969.8%).

---

## 1. Gajjala (Goverdhan "GG" Gajjala, 2023 $20k+ Stock Division, +805.1%)

### 1a. Primary-ish rule sources (free)
- **GG's X post "Here is how I scan for stocks"** (status 1756337327780364324, decoded 2024-02-10). SNIPPET-ONLY: https://x.com/gov_gajjala/status/1756337327780364324
  - He used a free YouTube scanner (Zendoo premarket live) plus a custom thinkorswim premarket scan for **volume ≥ 1M and up ≥ 25% since the prior close**. Watchlists are built from gradual volume increases and slow pullbacks. A catalyst (earnings, FDA, partnership) is required.
- **Business Insider (Japan edition, by Laila Maidan; first published 2024-02-12).** READ: https://www.businessinsider.jp/article/how-to-get-805-percent-return-small-caps-c/
  - Premarket scan: stocks moving more than 25%. Intraday scan: small caps priced $0.50–$100 with volume over 1M shares. The two scans yield 5–8 stocks a day.
  - 5-minute charts and five patterns. The main one is the bull-flag pullback. He takes the 1st and 2nd flags and avoids the 3rd. Entry is the first pullback high or the first green candle. Stop is the most recent pullback low or the last flag candle.
  - Zadeh puts his win rate at about 30%.
  - **Position-size examples:** 5,000 shares for about $12,000, and 20,000 shares at $5.18 (= $103,700). That is evidence the account was not tiny, though the account size itself is undisclosed.
  - The record is "statistically very significant" because of the trade count (Zadeh).
- **F4VS, "A Retail Trader's Repository" (Substack, free, 7 posts from 2024-05-17 to 2024-08-21).** READ:
  - Part 1: https://retailtradersrepository.substack.com/p/goverdhan-gajjala-a-deep-dive-into
    - Risk 0.25% of account per trade, moved with monthly performance (progressive exposure).
    - The stop is almost always the low of the prior bar. Sell partials and trail.
    - Focus on small caps. Scanners named: TOS "Small Cap Volatility Scan", premarket, Zendoo.
  - 2A Bull Flag: https://retailtradersrepository.substack.com/p/bull-flag-breakout-pullback-setup
  - 2B EMA Kiss & Fly: https://retailtradersrepository.substack.com/p/goverdhan-gajjala-ema-kiss-and-fly-setup. Carries the note: "GG announced he was going to discontinue services due to health issues", undated, in a post dated 2024-06-03.
  - 2C Horizontal Fade: https://retailtradersrepository.substack.com/p/goverdhan-gajjala-horizontal-fade
  - 2D Intraday VCP: https://retailtradersrepository.substack.com/p/goverdhan-gajjala-intraday-vcp
  - 2E Reversal Squeeze: https://retailtradersrepository.substack.com/p/goverdhan-gajjala-reversal-squeeze
  - Part 3 Q&A: https://retailtradersrepository.substack.com/p/goverdhan-gajjala-question-and-answer
    - About 20 tickers a day on scans, 10 watchable, 5 very good.
    - 90% of trades on the 5-minute chart, 10% on the 15-minute.
    - SPY/QQQ is ignored ("focus is small caps").
    - Float: "lower the better", but momentum magnitude matters most.
    - Target moves: 20/50/100%.

### 1b. "Modifications" by others: OPINION ONLY, no measured tests found
F4VS (all opinion, no stats):
- 2A: a breakout from a base followed by the bull flag is "more favorable". Open-market demand and a premarket uptrend may matter more than mid-day news moves. Gradual vs violent moves is his reading. He labels RKDA, NVCT and OCX invalid (no clear uptrend, a single green bar, an excessive volume jump). He warns against overfitting patterns to charts.
- 2C: Horizontal Fade, EMA Kiss & Fly and Bull Flag are **timeframe variants of one momentum trade** (30–15m, 5–15m and 5m respectively). The main failure mode is an impatient early entry.
- 2D: the first leg must "flow" into the consolidation. A choppy or violent first leg, or a too-high volume spike, makes the setup invalid (LQR, BE, MNRA, AYLA).
- 2E: Reversal Squeeze combined with another setup (HUDI plus Horizontal Fade, POL plus Kiss & Fly) "can improve the hit rate". This is unmeasured. Too-violent spikes are invalid (SNES, SASI, SGD).
- 2B: uses the high of the highest pullback bar as a "safer" entry. The first pullback bar need not hold. After about 3 bases a climax and gradual pullback are typical.

No backtest, Pine script, TradingView indicator, GitHub repo or Reddit study of GG's rules turned up in any search. TradingView and GitHub searches for "Gajjala" returned nothing relevant. tradingqna.com thread: https://tradingqna.com/t/us-investing-champion-2023-805-annual-return/159847. READ. Only a video link and chapter list; no tests or critique.

### 1c. GG's reported stats (MEASURED by GG / TraderLion; not independently verified)
- TraderLion profile: https://traderlion.com/investing-champions/2023-us-investing-champion/. Fetch returned 403, so these figures are **SNIPPET-ONLY** from search:
  - 750 trades in 2023, 31% win rate, average win +8.55%, average loss −4.06%.
  - Last six months: about 165 trades, 28% win rate, average win about 13% (fewer trades, bigger winners).
- TraderLion podcast 2024-01-24 (chapters only, no numbers): https://www.listennotes.com/podcasts/the-traderlion/805-trading-champion-of-2023-bWsG9zPaOJq/. READ. Chapters cover "Trading Stats of 2023", "Rules Around Drawdowns", "Adapting the Strategy to Account Size", "TPST 1,000% Move" and "Biggest Losers".
- TraderLion X (2026-05-13): GG held TPST through a move of over 1,000% in a single session. SNIPPET-ONLY: https://x.com/TraderLion/status/2054524681265225839
- A podcast summary says he had a 50% drawdown in 2021 after tripling his account. SNIPPET-ONLY, via search summary; source not opened.
- **My arithmetic on the snippet stats (not a source claim):**
  - Expectancy is 0.31×8.55 − 0.69×4.06 = **−0.15% per trade**.
  - Payoff is 2.11, so the breakeven win rate is 32.2%.
  - In R (1R = average loss) that is about **−0.04R**.
  - Compounding 750 trades to 9.05× needs a mean of about +0.29% of account per trade. At 0.25% risk that is about +1.2R per trade.
  - So the published stats cannot generate +805% under fixed-fractional sizing. The result depends on discretionary sizing (progressive exposure, adds, "up to double") and on tail trades (TPST).
  - Implication: a mechanical GG clone should be expected to be roughly breakeven before costs unless it captures the sizing and tail behaviour.

### 1d. Critiques / disputes / decay
- **Elite Trader thread** (January 2024, page 1 of 4 read): https://www.elitetrader.com/et/threads/a-software-consultant-who-day-trades-stocks-gained-805-in-2023.378008/. READ.
  - Reposts BI: monthly statements were viewed by Insider and vetted by Zadeh. April +65.3% (2nd place), May +47%, **June −44.4% after 17 straight losers driven by revenge trading**. Early on he risked $20 per trade.
  - Posters' critiques (OPINION):
    - "gambler" (SunTrader, citing the 17-loss streak).
    - "everyone's a genius in a bull market" (vanzandt).
    - The article omits his Nov 2021–Oct 2022 bear-market performance (nitrene).
    - The edge's sustainability is questionable (Jzwu2017).
- **CTE Research Sheet** (Louw van Riet, compiled 2026-09-07; PDF read via pdftotext): https://completetradersedge.com/wp-content/uploads/2026/09/CTE-Research-Sheet-US-Investing-Championship-2.pdf
  - "Goverdhan Gajjala is absent from the June, July and August boards, reappears at nine months on +266.5%, and finishes on +805.1%."
  - The 2023 field was 352 entrants.
  - The sheet confirms GG won the **$20k+ Stock board** (the $1m+ Stock board went to Tanmay Khandelwal, +129%).
- **GG's own decay report.** X post 1844811275412627921, decoded **2024-10-11**: https://x.com/gov_gajjala/status/1844811275412627921. The direct fetch returned 402, so this is SNIPPET-ONLY via search.
  - His setups did not appear for very extended periods, and the probability of them working dropped drastically.
  - He overtraded with forced trades, causing a drawdown.
  - YTD returns were positive but only double digits.
  - He is trading "very less, almost none" and shifting to learning rather than teaching.
  - Consistent with the project memory note that GG published nothing new after 2024-10-18.
- **Small-account question:** the contest scores sub-minimum accounts by dividing profit by the $20,000 minimum, so small accounts cannot inflate the percentage (completetradersedge.com page and the Kagels review). GG's position examples ($12k and $103.7k) indicate a mid-five- to six-figure account. Account size is undisclosed.

### 1e. Base-rate evidence relevant to a 25%-gap long scanner (MEASURED by third parties, not GG-specific)
- **SmallCapLab research page** (READ): https://www.smallcaplab.com/research
  - Universe: premarket gap-ups ≥45%, US common stock, price ≥$0.30. About 3,000–3,500 events, 2022–2026. No p-values.
  - **67.7% close below the RTH open** and 75.0% close below VWAP. The premarket-high break rate is 44.6%. Median HOD is +35.2% from the open.
  - **HOD timing:** 50% by 9:45 and 85%+ by 10:30 (internally inconsistent with another figure of 46.6% in the first 15 minutes). 63% of HODs come before 9:55.
  - Fade rate by gap size is flat at about 70% across 45–150%.
  - The fade rate rises with premarket volume, from 58.9% (<5M) to 70.6% (60M+).
  - Only 26% continue the next session.
  - SPY/VIX regime barely moves the fade rate (64–65%).
  - Exploratory vendor data, with some inconsistent numbers. **Implication (my inference, not the source's): long-side gap-up trades have their window in the first 15–60 minutes. After 10:30 the base rate is a fade.** A rule like "only trade the first 30–60 minutes" is consistent with this, but nobody has tested it on GG's patterns.
- **FennEdge gapper glossary.** SNIPPET-ONLY; two fetch attempts were reset: https://fennedge.ai/glossary/gapper
  - 671 stocks that opened ≥20% above the prior close, 2026-07-01 to 2026-10-02: **65.3% closed below their open**.
- **Zarattini, Barbon & Aziz (2024), "Stocks in Play" 5-minute opening-range breakout (SSRN 4729284; SSRN returned 403).** QuantConnect recreation thread READ: https://quantconnect.com/forum/discussion/18444/Opening+Range+Breakout+for+Stocks+in+Play/p0/comment-37562
  - This is the closest *measured* analogue to "trade the gappers early".
  - Rules: top 20 stocks by first-5-minute relative volume. Long above the opening-range high if the first bar is green; short below the low if it is red. ATR stop, 1% risk, flat at the close.
  - Recreation for 2016: Sharpe 2.396 versus SPY 0.836. 17 of 25 parameter combinations (5–25-minute OR, 500–1,500-name universe) beat the benchmark.
  - Poster critiques (opinion and anecdote): "results look poor in other years / overfit?" (Angus Li). Costs consume about 25% of returns (Jack Pizza). The strategy collapsed in the dot-com era and large-cap-only versions fail. The win rate is low (17% per one poster). 1–2-minute ORs plus a 2,000-name universe improved results (Lars Klawitter).
  - Note: this universe is liquid names ≥$5, not GG's $0.50 low floats.

---

## 2. Oliver Kell (2020 $20k+ Stock, +941.1%; 124 entrants per the CTE sheet)

- **The Premarket Brief, "The Wedge Pop's own exit rule threw away most of its edge"** (Saturday Study, 2026-10-31, no named author; full text visible). READ: https://premarketbrief.substack.com/p/the-wedge-pops-own-exit-rule-threw
  - Universe and period: S&P 500 and S&P 600, 2010–2026. 66,314 MA reclaims, of which 32,533 were full Wedge Pops.
  - Exit: 3R target or a time limit (length not given). Before costs. Survivorship handling and out-of-sample testing not reported.
  - **MEASURED results (R per trade):**

    | Variant | R per trade | Win rate |
    |---|---|---|
    | Full pattern | +0.222 | 37.3% |
    | Any reclaim, no pattern | +0.246 | 39.0% |
    | Reclaims in stocks that **never capitulated** | +0.343 | 41.4% |

  - Component tests:
    - Quiet-period convergence: +0.009R.
    - Volume on the pop *hurt*: +0.219R with it vs +0.255R without.
    - Unfilled breakaway gap *helped*: +0.276R with it vs +0.224R without. It was the only component that helped.
  - **Kell's prescribed exit (close below the 20-day): +0.064R, 29.5% win rate. It removed 71% of the expectancy.**
  - Author's conclusion: as defined, the setup is not worth trading. Test exits as hard as entries, because MA-noise exits kill winners.
  - Proposed changes implied by the data: drop the capitulation requirement, require or add the breakaway gap, and replace the 20-day close exit.
- **No other quantitative Kell test was found.**
  - TradingView "Oliver Kell Cycle of Price Action" (vishnuv, protected source): https://in.tradingview.com/script/xHyBTcMq-Oliver-Kell-Cycle-of-Price-Action/ (snippet). Indicator only; the author says rules were rebuilt from the masterclass and changed between versions.
  - GitHub scanners only, no results: https://github.com/arjunbchavan1989-AB/nse-kell-price-cycle and https://github.com/passiontrader/oliver-kell-price-action-rulebook/tree/main (snippets).
- **Kell's own statements** (Rayner Teo interview, page updated 2024-07-09; READ, first 100k characters): https://www.tradingwithrayner.com/the-stock-trader-who-made-941-1-in-a-year-with-oliver-kell/
  - No 2020 stats. Admits he gets stopped out "more than I do get it right". Uses margin. His largest position is usually the runner.
- **Third-party leverage estimates (SNIPPET-ONLY, opinion):**
  - FinancialWisdomTV: positions of about 190%, i.e. just under 2:1 margin.
  - EBC: top ideas 25–35% of capital, total exposure 120–150%, and +242.6% by the end of June 2020.
- Kell's site calls the result a "941.10% annualized return". The wording is inconsistent with the contest's calendar-year return (search summary).

---

## 3. Martin Luk (2025 $20k+ Stock, +969.8%, a record; 2024 6th at +283.1%; 2026 2nd at +868.6% through July)

Luk-attributed rules: pullback to the 9/21 EMA or anchored VWAP in a 9>21>50 EMA leader, stop at the low of day (≤2.5–3%), 0.5% risk, partial at 3R, trail on the 9 EMA, trade only when QQQ is above its 50-day EMA.

- **rootchunhe/martin-luk-backtesting** (GitHub, 3 commits; READ): https://github.com/rootchunhe/martin-luk-backtesting
  - Data and setup: CRSP daily plus TAQ minute/NBBO, 2016-01 to 2026-08, point-in-time. Common stocks ≥$5 with ≥$50M a day of dollar volume. Leaders have ADR ≥5%, a 9>21>50 EMA stack, price above the AVWAP anchored at the 250-day high, and a ≥30% run-up.
  - Entry is a 15:54 close-confirm with a fill at 15:55. Stop at the low of day (2–5%). 0.5% risk, 15% partial at 3R, exit on a close below the 9 EMA, max hold 15 days.
  - Costs: NBBO half-spread, fees, and margin at T-bill +1.5%.
  - **MEASURED (after costs):**

    | Variant | CAGR | Sharpe | Max DD | Trades/yr | Win | Avg win / loss | PF |
    |---|---|---|---|---|---|---|---|
    | Full | 12.1% | 0.83 | −13% | 27 | 29% | +14.3% / −2.9% | 1.98 |
    | QQQ, same pool | 19.9% | 0.83 | −35% | | | | |
    | **no_timing** (buy strong stocks near the 9 EMA without the pullback timing) | 7.1% | 0.30 | −62% | | | | 1.07 |
    | **no_avwap** | 18.2% | 0.87 | −27% | 74 | | | 1.55 |
    | risk_1pct | 17.4% | 0.84 | | | | | |
    | exit_ema21 | 11.1% | 0.70 | | | | | |
    | support EMA 5 | | 0.40 | | | | | |
    | support EMA 13 | | 0.37 | | | | | |

  - **Luk's morning-breakout entry: 166 trades/yr, 13% win, CAGR −2.2%, max DD −59% after spreads.**
  - Concentration: the 10 largest trades are 111% of net P&L, CDTX alone is 32%, and 2025 alone is about 1/3 of P&L. 2016–2019 was a small net loss on about 20 trades.
  - Author's notes: no clean out-of-sample period, because the 30% run-up and 15:55 entry were chosen with the data in view. The AVWAP filter mainly reduces trade count. The 9 EMA level is fragile. The README says nothing in the data approaches Luk's reported returns.
- **zongfan2/TradingAgents PR #4** (opened 2026-10-14, merged 2026-10-15; READ): https://github.com/zongfan2/TradingAgents/pull/4
  - Setups: EP (≥10% gap plus first-bar volume), breakout, and pullback to the 9/21 EMA. Leaders are the top 5% by relative strength with a ≥30% move.
  - 5-minute SIP data, 2017-01 to 2026-10, $5M ADV and $3 price floors, 10 bps slippage, parameters set a priori. Survivorship coverage is only partial.
  - **MEASURED:**

    | Variant | Total | Max DD | R per trade |
    |---|---|---|---|
    | Baseline | **−58.3%** | −87.6% | −0.009 |
    | Breakouts only | +18.9% | −67.6% | +0.075 (rests on one GME trade) |
    | Contract exits (2R / 10 days) | −36.3% | | |
    | SPY buy-and-hold | +248.1% | −34.2% | |

  - Win rate 28%, average loss −3.9%, payoff about 2.5× (Luk's reported payoff is about 5×). About 40% of trades stopped out on the entry day.
  - Lost money in 2024–2025, Luk's best years. Luk-style trailing exits did *not* beat fixed contract exits.
  - Author's verdict: "Not as a mechanical strategy."
- **Signal&Moat / mistakesoninvesting Substack** (Alberto Taiana, 2026-10-23; **PAID post, paid code**; READ the free portion): https://mistakesoninvesting.substack.com/p/decoding-martin-luks-record-969-championship
  - Reverse-engineered Luk replication, 2010–2025, 3× leverage: +1,450% total, "CAGR 15–18%" (inconsistent: +1,450% over 15 years is about 20%), max DD 19.8%, PF 2.28, win rate 38.5%.
  - Luk stats per the author: win rate 22–38%, average loss about 2%, average win about 14%.
  - Commercial product, so treat as marketing.
- CTE sheet: Luk's 2025 path peaked at +1,358.2% in November and finished at +969.8%, giving back 388 points. The organiser's two-year 2024–25 compound is +3,998%.

---

## 4. Minervini (USIC 1997 +155% on $250k; 2021 $1m+ Stock +334.8%) and O'Neil/David Ryan-style patterns

- **The Premarket Brief, "The contraction in the contraction pattern added 0.023R"** (2026-10-24; READ): https://premarketbrief.substack.com/p/the-contraction-in-the-contraction
  - VCP-style test (Minervini is not named). S&P 500+600, 2010–2026, 74,500 base breakouts, before costs.
  - **MEASURED:**

    | Group | Trades | Win | R per trade |
    |---|---|---|---|
    | Progressively shallower pullbacks | 20,955 | 44.2% | +0.181 |
    | Control | 53,545 | 46.9% | +0.158 |

  - The edge is +0.023R. There is no gradient by shrinkage, and the "final pullback 2× the first" group had the highest win rate (50.6%).
  - Checklist items:
    - **RS vs the index helped** (+0.176R vs +0.133R).
    - Prior uptrend ≥30% hurt (+0.156R vs +0.178R).
    - Breakout volume >1.4× hurt slightly.
    - All six checks passing gave +0.150R; five checks gave +0.186R.
- **The Premarket Brief, "The Textbook Cup and Handle Was the Weakest Version"** (2026-10-17; READ): https://premarketbrief.substack.com/p/the-textbook-cup-and-handle-was-the
  - S&P 500, 2010–2026, 5,565 breakouts, entry at the next open, before costs.
  - **MEASURED:**
    - The full 5-rule pattern scored +0.181R (n=238, t=1.83, not significant). Passing exactly 1 check scored +0.303R.
    - A V-bottom beat a rounded cup.
    - **A handle in the upper half is the only useful rule** (+0.337R vs +0.209R), and it weakened after 2019 (+0.393R before vs +0.221R after).
    - Handle volume drying up made no difference. Expanding breakout volume hurt slightly.
- **julioffernandez/TrendTemplate-Backtesting** (GitHub; READ): https://github.com/julioffernandez/TrendTemplate-Backtesting
  - SEPA-style rules, 2020-04 to 2026-06. The example uses 8 current mega-caps, so it carries survivorship and selection bias.
  - The README gives only drawdown: about 14–17% vs QQQ −35.1%. It lags in 2023–25 from cash drag and whipsaws. A 6.5% stop is called "optimal". **Weak evidence.**
- **paperswithbacktest Minervini page** (READ): https://paperswithbacktest.com/strategies/mark-minervini
  - No SEPA backtest; the example code uses random signals. Not usable evidence.
- Survivorship caveat seen in a public PR (SNIPPET-ONLY): xang1234/stock-screener PR #705 replays Minervini picks point-in-time but admits the universe is survivor-biased. https://github.com/xang1234/stock-screener/pull/705

---

## 5. Contest-level critiques: small accounts, verification, disputes
- **completetradersedge.com USIC page** (READ): https://completetradersedge.com/us-investing-championship/
  - Two bands, $20k+ (USIC) and $1m+ (MMVR). Sub-minimum accounts have their profit divided by the minimum. Returns are time-weighted.
  - Checked against statements, with live walkthroughs at the organiser's discretion. Not a GIPS composite.
  - The 1998 SEC cease-and-desist against Zadeh/Prime Advisors covered unregistered securities and books-and-records failures.
  - Minervini's 1997 +155% on $250k is the only firm original-era anchor.
- **CTE Research Sheet PDF** (READ via pdftotext): https://completetradersedge.com/wp-content/uploads/2026/09/CTE-Research-Sheet-US-Investing-Championship-2.pdf
  - Denominators: **2022: 26 of 316 profitable (8%)**. **H1 2026: 115 of 688 (17%)** while the S&P 500 gained 10.2%.
  - Entrant counts: 2019 96, 2020 124, 2021 338, 2022 326, 2023 352, 2024 451, 2025 579.
  - Monthly listing is optional. **Late entry: scoring starts from the close on the day a competitor joins.**
  - Leaders who vanished: Y. Chiu at +779.9% in July 2025; Dr Terry Potter at +1,678.8% in Q1 2026, then absent.
  - David Ryan's 1987 two-year result was **$43,000 → $295,000**, a small account.
  - Persistence: Sean Ryan was profitable 7 of 7 years (2019–2025) for +6,232%, the best "skill" signal on record.
  - The entry fee is $475; published results once carried a phone number used to solicit fund investors.
- **Kagels Trading review** (Karsten Kagels, updated 2026-10-09; READ): https://kagels-trading.com/blog/us-investing-championship/
  - Single-year ranking rewards risk and luck. The standings hide drawdowns and position sizes. Self-checking by the organiser is weaker than partner-broker reporting.
  - Wants multi-year results. Small accounts are penalised by the divisor ($10k example: shows 25% instead of 50%). Optional reporting creates survivorship.
  - No independent strategy tests are discussed.
- Larry Williams 1987 (futures, Robbins World Cup, not USIC): $10k grew to about $1.1M. A secondary source reports a 62% intra-contest drawdown, and an NFA-quoted forum post questions the composite. SNIPPET-ONLY: https://completetradersedge.com/larry-williams-11376-percent-trading-record/

---

## Measured vs opinion: quick ledger

| Claim | Type | Source |
|---|---|---|
| Wedge Pop +0.222R vs plain reclaim +0.246R; Kell exit kills 71% | MEASURED | premarketbrief, 2026-10-31 |
| VCP contraction +0.023R over control; RS is the only helpful filter | MEASURED | premarketbrief, 2026-10-24 |
| Textbook cup-and-handle weakest (+0.181R, ns); upper-half handle helps | MEASURED | premarketbrief, 2026-10-17 |
| Luk pullback: 12.1% CAGR, Sharpe 0.83 = QQQ; morning breakout −2.2% CAGR after spreads | MEASURED | rootchunhe GitHub |
| Luk all-setups replica −58.3%, −0.009R | MEASURED | zongfan2 PR #4 |
| Luk replica +1,450% at 3× | MEASURED but paid, commercial, inconsistent | Signal&Moat |
| ≥45% gappers: 67.7% close below open; HOD 85% by 10:30 | MEASURED (vendor, no p-values) | smallcaplab |
| ≥20% openers: 65.3% close below open (n=671, 3 months) | MEASURED (vendor) | fennedge (SNIPPET-ONLY) |
| Stocks-in-play 5-minute ORB Sharpe 2.4 (2016 recreation) | MEASURED | QuantConnect forum |
| GG: 750 trades, 31% win, +8.55% / −4.06% | SELF-REPORTED stats | TraderLion (SNIPPET-ONLY) |
| GG stats imply about −0.15% per trade fixed-size | MY ARITHMETIC | derived from the above |
| GG setups decayed in 2024 | SELF-REPORTED | GG X post 2024-10-11 (SNIPPET-ONLY) |
| "Base breakout first is better", "combined setups raise hit rate", invalid examples | OPINION | F4VS Substack |
| "Gambler", "bull-market genius", omitted bear year | OPINION | Elite Trader posters |
| One-year rank rewards luck; need multi-year | OPINION, with optional-reporting facts | Kagels; CTE |

## Gaps (not followed because the search budget ran out, or blocked)
- Reddit (r/algotrading, r/Daytrading, r/RealDayTrading): the tool refuses reddit.com. Not covered.
- The TraderLion GG profile page (403), so the stats are SNIPPET-ONLY. The TraderLion podcast numbers at the 37:27 chapter are not transcribed.
- The SSRN 4729284 abstract (403). The paper's own Sharpe and period were not read.
- Kell's post-2020 repeat performance was not searched (the search budget ended).
- Leif Soreide, Pavel Sterba, Afzal Lokhandwala, Judy Lai, Tanmay Khandelwal, J Law, Tom Doub, Sean Ryan: no public rule sets or tests were found (Lokhandwala, Lai and Doub were searched; nothing on method).
