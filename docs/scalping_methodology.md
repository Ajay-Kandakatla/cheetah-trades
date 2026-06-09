# Scalping page — methodology & sources

Built 2026-06-09 from a vetted, adversarially-verified research pass. The user's
standing rule is *no assumptions*: every detector is tied to a named source, and
where the evidence is thin or a popular claim is folklore, we say so rather than
dress it up. **Educational, not advice.**

> **Bottom line, up front.** Exactly ONE of these has a defensible, reproduced,
> costs-modeled edge for retail — and even it nets only commissions, lives in a
> single 2016–23 bull regime, and runs a ~17% win rate carried by rare tails. The
> account-level evidence is blunt: **~80–99% of retail day-traders net LOSE after
> costs** (Taiwan: ~1–1.6% reliably profitable; Brazil: 97% of persistent day
> traders lost money). No backtest changes that base rate. The page therefore
> shows **gross signal beside net-of-cost reality** on every signal.

## Phase-1 detectors (what we built)

### 1. Stocks-in-Play 5-min Opening-Range Breakout — `detectors.stocks_in_play_orb`
- **Source:** Zarattini, Barbon & Aziz (2024), *A Profitable Day Trading Strategy
  For The U.S. Equity Market*, SSRN abstract_id=4729284 / Swiss Finance Institute
  Research Paper N°24-98. Independently re-coded by QuantConnect (research/18444).
- **Evidence:** strong on source rigor, **medium** on real-world net tradeability.
  Headline (verbatim from the paper): Sharpe **2.81**, >1,600% net, 36% alpha vs
  SPY's ~198%, 2016–2023; QuantConnect reproduced ~2.40 on a top-1000 subset.
- **Rules (as implemented):** universe = today's liquid movers; require
  **RelVol > 1.0** (the "stock in play" filter — the edge lives here); direction =
  sign of the 9:30–9:35 bar (skip dojis); buy-stop at the 5-min OR boundary; stop
  = `ORB_ATR_MULT` × **daily** ATR(14); primary exit = EOD flat or stop. We add a
  `MAX_EXT_PAST_TRIGGER_PCT = 3%` no-chase cap and a regime-alignment flag.
- **Honest demerits (why not "strong"):** author-published, not peer-reviewed; a
  single 2016–23 bull regime (QuantConnect shows it collapses pre-2016); ~17% win
  rate carried by rare 10R tails (operationally hard to hold); the paper nets
  $0.0035/share commission **but not slippage or short-borrow**. Treat 2.81 as an
  optimistic upper bound.

### 2. Volatility-normalized shock fade — `detectors.shock_fade`
- **Source:** Zawadowski, Andor & Kertész (2004), *Short-term market reaction
  after extreme price changes of liquid stocks*, arXiv cond-mat/0406696 (also
  Quantitative Finance 6:283–95, 2006).
- **Evidence:** **strong** for the effect's existence and microstructure honesty;
  net live edge **unproven** in modern markets. The paper is cost-honest in the
  exact way that matters: on NYSE the spread widened at the shock and *eliminated
  most of the profits*; the edge survived only where the spread stayed tight —
  which is why the **live spread gate is the kill-switch**, not a nicety.
- **Rules (as implemented):** a **pure-intraday** move (exclude opening gaps, the
  first 5 min, and the last 60 min) clearing **both** |move| ≥ 4% **and** ≥ 8× the
  name's own intraday σ; fade it; stop = 30% of the shock beyond entry; target =
  ~40% of the shock back; hard **60-min time-stop** (edge decays fast).
- **Documented limitation:** the paper's σ is a same-clock-window stdev over 60
  prior days; we approximate it from today's own 1-min returns. And it's a
  2000–2002 (pre-decimalization-tail, pre-HFT) event study — **gross opportunity,
  not a proven modern net return.**

### 3. Intraday-momentum regime gate — `regime.intraday_regime`
- **Source:** Gao, Han, Li & Zhou (2018), *Market Intraday Momentum*, Journal of
  Financial Economics 129(2):394–414, SSRN abstract_id=2440866.
- **Evidence:** **strong** — peer-reviewed, out-of-sample, robust to costs. BUT
  it is an **index/ETF timing effect** (SPY), R² ~1–2%, Sharpe ~1.08 — *not* a
  single-name scalp. We use only the **sign** of SPY's first-30-min return as a
  long-bias / short-bias / stand-aside **direction gate** feeding the detectors.
  Do **not** trade its magnitude on a single stock.

## The non-negotiable honesty layer (every signal wears this)
- **Relative volume (RVOL)** — the single most evidence-backed filter; no volume = noise.
- **ATR-normalized triggers** — never a raw % or fixed-cent move.
- **Live bid-ask spread kill-switch** — `nbbo.spread_gate`; Massive snapshot NBBO
  for the active set. Spread unknown → flagged, never assumed zero.
- **Time-of-day arming** — the first 5 min and **last 60 min** are excluded for
  the fade; the close is auction-dominated and hostile.
- **Regime/direction gate** — trend vs fade fire opposite signals and cancel
  without it.
- **Net-of-cost overlay** — `costs.py`: round-trip spread + slippage + commission
  + SEC/FINRA fees + borrow, and the **breakeven win rate** after costs, shown
  beside the gross R:R on every card.

## NOT built — folklore / inflated claims we deliberately rejected
The adversarial verify pass flagged these; do **not** add them as "validated":
- The VWAP 2-σ band-fade "63% win rate, QuantConnect 2022" stat — **fabricated**;
  it exists only on one vendor page with no methodology, and is absent from
  QuantConnect.
- The "target = 50% of the opening range" retail ORB framing sold as a validated
  edge (e.g. a vendor's "+108% in 6 months" — a tuned single-instrument backtest).
- Generic Bollinger / VWAP band-touch fades with quoted 60–78% win rates — no
  rigorous, cost-included, methodology-disclosed backtest exists.
- The TQQQ ~1,484% / ~2,300% "ORB returns" — a **3× leverage artifact**, not edge.
- Crabel "Stretch" ORB in-book win rates as validated *equity* edge — the only
  reproducible public backtest is on futures and the naïve version graded poorly.
- Warrior/Ross-Cameron Gap-and-Go — precisely documented, but **no** rigorous
  backtest; anecdotal.
- Any backtest treated as a base rate for *your* profitability — see the bottom
  line.

## Deferred to Phase 2 (offer with warnings, don't lead)
Single-instrument QQQ ORB (A/B baseline), End-of-Day Reversal (close-window
ranking overlay), generic ORB (baseline to beat), VWAP trend-pullback & Anchored
VWAP (clearly labeled practitioner/discretionary).

## Configured constants (NOT a book formula — tunable)
See `scalping/detectors.py`, `scalping/nbbo.py`, `scalping/costs.py`. The cost
defaults (commission $0.0035/share per Zarattini; 5 bps/side slippage; SEC §31 +
FINRA TAF; 2% short-borrow) are conservative retail assumptions, not gospel.

---

# SEPA-cross tape watch (added 2026-06-09) — candle wick/body reads at levels

The autonomous alert layer: holdings + buyable + at-pivot + leaderboard names,
each completed 5-min candle read at its levels (SEPA pivot, VWAP, opening-range
high, day high) → states (BREAKOUT_STRONG / BREAKOUT_WEAK / REJECTION /
BREAKDOWN / RECLAIM / STALL) → one push per (symbol, state, ET-day), each alert
self-graded against the +30-min tape. `scalping/candles.py` + `sepa_watch.py`.

## What the evidence actually says (adversarially verified 2026-06-09)

The candle measures we compute (body % of range, wick ratios, Chaikin
close-location-value, volume ratio) are DESCRIPTIVE arithmetic. The question is
whether candle PATTERNS predict — and the verified record is mostly null:

- **Duvinage, Mazza & Petitjean (2013)**, Quantitative Finance 13(7) — **the
  decisive study for this exact tool**: 5-MIN bars, 30 DJIA stocks, 83 candle
  rules. Some pre-cost predictive content, but **no rule beats buy-and-hold
  after costs plus data-snooping correction**. Our horizon, their null.
- **Marshall, Young & Rose (2006)**, J. Banking & Finance 30(8) — NULL: DJIA
  stocks 1992–2002, bootstrap test; candlestick strategies have no value.
- **Marshall, Young & Cahan (2008)**, RQFA 31(2) — NULL in candlesticks' home
  market (TSE 1975–2004): "not even consistently profitable before costs."
- **Horton (2009)**, QREF 49(2) — NULL on 349 US stocks; grounds our rule that
  a doji is a STATE label, never a reversal signal.
- **Fock, Klein & Zwergel (2005)**, J. Derivatives 13(1) — NULL on intraday
  DAX/Bund futures, alone or with momentum.
- Contested daily-bar positives exist — **Caginalp & Laurent (1998)** (S&P 500
  daily, out-of-sample positive; but their test "removes conditions on
  magnitudes", so NO body/wick size threshold has academic validation) and
  **Lu & Shiu (2012, 2016)** (Taiwan/DJIA daily) — cited to show the daily
  evidence is contested, not settled. None of it transfers to 5-min bars.
- **Engle (1982)**, Econometrica 50 — the ONE strong predictive claim we ship:
  volatility clustering means range compression/expansion forecasts more
  VOLATILITY, never direction. STALL is therefore "expect movement", direction
  unsaid.
- **Bulkowski (ThePatternSite)** — used ONLY for identification conventions
  (wick ≥ 2–3× body etc.). His own daily-bar stats are near-random (shooting
  star 59%, hammer 60%); never quoted as win rates here.

## Therefore: what this layer claims, and what it refuses to claim

- Verdicts are **descriptive** ("constructive" / "deteriorating") — who won the
  bar at the level, on what participation. Never "will go up".
- Thresholds (body ≥60%, doji <5%, wick dominance ≥2×, CLV ≥0.6, vol ≥1.5×,
  level band 0.3%) are **CONFIGURED** conventions, not validated formulas — per
  Caginalp & Laurent, no magnitude threshold has academic backing anywhere.
- **Self-scoring is the contract**: every alert is graded against the next 30
  minutes and the page shows the live per-state hit-rate; the historical
  tape-read backtest (`tape_backtest.py`) reports follow-through per state and
  says plainly that ~50% = the read is noise. If the record says the read adds
  nothing, believe the record over the read.
- Refused as folklore: fixed win-rates for hammer/shooting-star/engulfing,
  doji-as-reversal, any "this pattern means X% odds" claim.
