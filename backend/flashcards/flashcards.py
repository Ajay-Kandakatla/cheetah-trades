"""Flash-card bank + dispatcher — hourly trading education.

Three-slot scheduling (2026-05-20) → hourly scheduling (2026-05-21):
user asked for more cadence + broader topics beyond Minervini's
methodology. The card bank is now organized by TOPIC, and each hour
of the day routes to one topic so the rhythm stays predictable
(morning = entry prep, lunch = trader history fun fact, etc.) while
the specific card rotates within the topic.

Topics
------
  * entry            — Minervini entry rules, base quality, pivots
  * risk             — sizing, stops, the math of asymmetric losses
  * sell_rules       — Minervini exit framework, -12% rule, partials
  * psychology       — mindset, bounce-back trap, hope-is-not-a-strategy
  * review           — common mistakes, journal prompts
  * fundamentals     — EPS / FCF / ROIC / book value / equity types
                       (the user asked about "company equity vs shareholder equity")
  * market_structure — T+1, dark pools, LULD bands, NBBO, Greeks intuition
  * history          — famous trades, traders, crashes, blowups
                       (the user asked for "fun facts that get people stoked")
  * edge_math        — expectancy, Kelly, drawdown math, compounding

Hourly schedule (ET, weekdays only)
-----------------------------------
  8  fundamentals    13 sell_rules         18 edge_math
  9  entry           14 psychology         19 history
 10  market_structure 15 entry             20 psychology
 11  risk            16 review
 12  history         17 fundamentals

Selection: deterministic on (day_of_year, hour). Cards within a topic
cycle by day. With 8-12 cards per topic and 1-2 hours per topic per
day, each card surfaces every ~10-14 days — variety without amnesia.

Card schema
-----------
  {
    "topic":  "fundamentals"                          # routing tag
    "title":  "📚 Equity types · stockholder vs co.", # ≤ 80 chars with emoji
    "body":   "Stockholders' equity = what's left ...", # ≤ 180 chars
    "source": "Investopedia / SEC EDGAR primer",     # cited; shown in body
    "url":    "/sepa"                                 # tap-route (optional)
  }

Push kind: ``minervini_flashcards`` (kept as-is so the existing pref
toggle on /notifications keeps working). User mutes by toggling that
single pref off — covers all topics, not just Minervini ones now.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger("flashcards")


# ===========================================================================
# CARD POOLS — by topic
# ===========================================================================
# Each card is short on purpose. Push notifications truncate aggressively
# on iOS (~180-200 chars body) so the line that gets cut shouldn't be
# the lesson itself. Cite the source so the curious user can look up
# the full context.

# ---------- Minervini entry rules ----------
ENTRY_CARDS: list[dict] = [
    {"topic": "entry", "title": "🎯 Entry · Pivot precision",
     "body":  "The pivot is a SPECIFIC PRICE, not a zone. Buy within 1-2% above. 5%+ above = chasing — risk-to-stop is broken.",
     "source": "Think & Trade Like a Champion · ch.6"},
    {"topic": "entry", "title": "🎯 Entry · Volume confirmation",
     "body":  "A breakout on dry volume is a fake. Demand 40-50%+ above the 50-day average on the breakout day.",
     "source": "Trade Like a Stock Market Wizard · ch.6"},
    {"topic": "entry", "title": "🎯 Entry · Base quality first",
     "body":  "Only buy from a PROPER BASE. 5 types: VCP, cup-and-handle, flat, Power Play, ascending. No base = no buy.",
     "source": "Trade Like a Stock Market Wizard · ch.4"},
    {"topic": "entry", "title": "🎯 Entry · Base count",
     "body":  "By the 4th base from a major low, failure rate spikes. Late-stage bases break — don't buy them.",
     "source": "Mark Minervini · seminars"},
    {"topic": "entry", "title": "🎯 Setup · VCP signature",
     "body":  "3-6 contractions, each tighter than the last, on DECLINING volume. Final contraction tight 5-15%. That's the spring loading.",
     "source": "Trade Like a Stock Market Wizard"},
    {"topic": "entry", "title": "🎯 Quality · Stage 2 only",
     "body":  "Buy only Stage 2 (advancing). Stage 1 = dead money. Stage 3 = trim. Stage 4 = do not buy ever.",
     "source": "Stan Weinstein (cited by Minervini)"},
    {"topic": "entry", "title": "🎯 Entry · Patience over aggression",
     "body":  "Patience for the right setup. Aggression on entry. Discipline on exit. Don't reverse the order.",
     "source": "Mark Minervini · seminars"},
    {"topic": "entry", "title": "🎯 Entry · What you SEE",
     "body":  "Trade what you see, not what you think. Charts tell you what's happening; opinions tell you what should happen.",
     "source": "Trade Like a Stock Market Wizard"},
    {"topic": "entry", "title": "🎯 Setup · Power Play",
     "body":  "Post-IPO ran 100%+ then consolidates 3-5 weeks with only a 10-25% pullback. Break of the consolidation high = high-tight-flag.",
     "source": "Mark Minervini"},
    {"topic": "entry", "title": "🎯 RS Rank gate",
     "body":  "Don't buy below 80 RS rank. Top 20% of the market is where the leaders live. Everything else is a coin flip.",
     "source": "Trade Like a Stock Market Wizard"},
    {"topic": "entry", "title": "🌐 Regime · Follow-through day",
     "body":  "After a correction, day 4-7 closing +1.5%+ on heavier volume = new uptrend confirmed. Until then, every rally is suspect.",
     "source": "Trade Like a Stock Market Wizard · ch.5"},
    {"topic": "entry", "title": "🌐 Regime · Tape pays you",
     "body":  "Don't fight the tape. ~75% of stocks follow the market. Cash is a position when the market says no.",
     "source": "Think & Trade Like a Champion"},
]

# ---------- Risk / sizing ----------
RISK_CARDS: list[dict] = [
    {"topic": "risk", "title": "🛡️ Risk · The 1% rule",
     "body":  "Size positions so that hitting your stop loses ≤1% of total capital. 1.5-2% only in confirmed uptrend + A+ setup.",
     "source": "Think & Trade Like a Champion · ch.3"},
    {"topic": "risk", "title": "🛡️ Risk · Stop placement",
     "body":  "MAX 7-8% from entry. Tighter is better — below the structural low of the base. Evaluated at CLOSE, not intraday.",
     "source": "Trade Like a Stock Market Wizard · ch.7"},
    {"topic": "risk", "title": "🛡️ Risk · The asymmetry",
     "body":  "A 7% loss recovers with 7.5% gain. A 50% loss needs 100% gain. Small losses keep compounding intact; big losses destroy it.",
     "source": "Trade Like a Stock Market Wizard"},
    {"topic": "risk", "title": "🛡️ Risk · Never average down",
     "body":  "Adding to a losing position is the amateur signature. Add only to WINNERS after they've proven the entry.",
     "source": "Think & Trade Like a Champion"},
    {"topic": "risk", "title": "🛡️ Sizing · Position formula",
     "body":  "Shares = (capital × risk%) / (entry − stop). $100k × 1% / ($100 − $93) = 142 shares.",
     "source": "Think & Trade Like a Champion"},
    {"topic": "risk", "title": "🛡️ Risk · Concentration caps",
     "body":  "Single position ≤25% of book. Single sector ≤40%. 8-12 positions total. More = can't monitor each.",
     "source": "Mark Minervini"},
    {"topic": "risk", "title": "🛡️ Risk · Trail with 21-EMA",
     "body":  "Once a position runs +2R, switch from initial stop to trailing. 21-day EMA close-below works on liquid leaders.",
     "source": "Trade Like a Stock Market Wizard"},
    {"topic": "risk", "title": "🛡️ Position · Defend the wins",
     "body":  "Tighter trailing stop when the move accelerates. Looser when consolidating. Give a winner room — but not unlimited.",
     "source": "Trade Like a Stock Market Wizard"},
]

# ---------- Sell rules ----------
SELL_RULES_CARDS: list[dict] = [
    {"topic": "sell_rules", "title": "✂️ Sell · The -12% rule",
     "body":  "Intraday move of -12% or more from yesterday's close = STRUCTURAL BREAK. Exit immediately. No discretion.",
     "source": "Mark Minervini · interviews"},
    {"topic": "sell_rules", "title": "✂️ Sell · Take partials at 3R",
     "body":  "When profit = 3× your risk, sell 25-50%. Move remaining stop to breakeven. Now the trade can't lose money.",
     "source": "Trade Like a Stock Market Wizard · ch.8"},
    {"topic": "sell_rules", "title": "✂️ Sell · Close-of-day rule",
     "body":  "Don't puke a stock at 10am on a wick. Wait for the 3:00 PM CT close. If close is below stop → sell tomorrow's open.",
     "source": "Mark Minervini · interview"},
    {"topic": "sell_rules", "title": "✂️ Sell · The signals",
     "body":  "Climax top, exhaustion gap, 4-5 distribution days in 2 weeks, close below 50DMA on volume, 8 weeks no progress.",
     "source": "Trade Like a Stock Market Wizard · ch.7"},
    {"topic": "sell_rules", "title": "✂️ Sell · Climax top",
     "body":  "Gap up 25%+ on highest volume of the move, wick that closes near the low = blow-off top. Sell into strength.",
     "source": "Trade Like a Stock Market Wizard"},
    {"topic": "sell_rules", "title": "✂️ Sell · Time stop",
     "body":  "Position made no progress in 8 weeks after entry? Setup was wrong. Cut, free up capital, find a working name.",
     "source": "Trade Like a Stock Market Wizard"},
    {"topic": "sell_rules", "title": "✂️ Sell · Distribution count",
     "body":  "Index distribution day = down 0.2%+ on heavier volume. 4-5 in 25 days = institutions selling. Trim leaders.",
     "source": "Trade Like a Stock Market Wizard · ch.5"},
    {"topic": "sell_rules", "title": "✂️ Sell · Stage 2 → 3",
     "body":  "Lower high + 50-day flattens = topping. Don't wait for confirmation — TRIM into the rolling-over phase.",
     "source": "Stan Weinstein"},
]

# ---------- Psychology / mindset ----------
PSYCHOLOGY_CARDS: list[dict] = [
    {"topic": "psychology", "title": "🧠 Mindset · Process > outcome",
     "body":  "Good process + bad outcome = REPEAT (variance). Bad process + good outcome = DO NOT repeat (you got lucky).",
     "source": "Mindset Secrets for Winning · ch.2"},
    {"topic": "psychology", "title": "🧠 Mindset · Bounce-back trap",
     "body":  "You got stopped CORRECTLY, watched the bounce, concluded the stop was wrong. Selection bias. 7/10 don't bounce.",
     "source": "Mark Minervini · interview"},
    {"topic": "psychology", "title": "🧠 Mindset · Hope is not a strategy",
     "body":  "If you find yourself HOPING a position recovers, you've already abandoned the plan. Hope means past stop. Sell.",
     "source": "Trade Like a Stock Market Wizard"},
    {"topic": "psychology", "title": "🧠 Mindset · Detach from any single trade",
     "body":  "A good trade can lose money. A bad trade can make money. Judge yourself by process adherence, not P/L.",
     "source": "Mindset Secrets for Winning"},
    {"topic": "psychology", "title": "🧠 Mindset · Confidence",
     "body":  "Confidence comes from following a proven system — not from being right on any single trade.",
     "source": "Think & Trade Like a Champion"},
    {"topic": "psychology", "title": "🧠 Mindset · 24h cooldown",
     "body":  "After any -2R+ loss, mandatory 24h cooldown. Over-trading after a loss compounds psychological damage into financial damage.",
     "source": "Mindset Secrets for Winning"},
    {"topic": "psychology", "title": "🧠 Mindset · The market is right",
     "body":  "The market doesn't care about your wishes. Your job is to RESPOND, not predict. Adjust faster than you defend.",
     "source": "Mark Minervini"},
    {"topic": "psychology", "title": "🧠 Mindset · FOMO management",
     "body":  "Watching stocks you don't own run is part of the job. Better setups come. Forcing trades in poor regimes ≠ catching up.",
     "source": "Trade Like a Stock Market Wizard"},
]

# ---------- Review / common mistakes ----------
REVIEW_CARDS: list[dict] = [
    {"topic": "review", "title": "⚠️ Mistake · No stop = no trade",
     "body":  "Buying without a stop is the #1 amateur mistake. WRITE THE STOP DOWN before clicking buy. Every time.",
     "source": "Think & Trade Like a Champion"},
    {"topic": "review", "title": "⚠️ Mistake · The 7 deadly sins",
     "body":  "No stop · averaging down · selling on noise · holding losers · cutting winners · wrong regime · over-trading after loss.",
     "source": "Mark Minervini · seminars"},
    {"topic": "review", "title": "⚠️ Mistake · One bad trade vs six",
     "body":  "One bad trade is variance. The SAME bad trade six times is a fixable habit. Journal it. Find the pattern.",
     "source": "Mindset Secrets for Winning"},
    {"topic": "review", "title": "⚠️ Mistake · Bottom fishing",
     "body":  "Bottom fishing is the most expensive hobby in the stock market. Stage 4 stays Stage 4 longer than your patience.",
     "source": "Mark Minervini"},
    {"topic": "review", "title": "📊 Stage transitions take TIME",
     "body":  "S1→S2 = breakout on volume. S2→S3 = lower high + 50DMA flattens. S3→S4 = close below 50DMA on heavy volume.",
     "source": "Stan Weinstein"},
    {"topic": "review", "title": "📊 Stage 4 = don't buy",
     "body":  "Stage 4 = price below falling 50DMA, 50 < 200. Do NOT bottom-fish. Wait for Stage 1 base before even watching.",
     "source": "Stan Weinstein"},
]

# ---------- Fundamentals / accounting basics ----------
# The user explicitly asked about "company equity vs shareholder equity"
# in this batch — covering that gap plus the rest of the financial-
# statement vocabulary that trips up self-taught traders.
FUNDAMENTALS_CARDS: list[dict] = [
    {"topic": "fundamentals", "title": "📚 Equity types · stockholder vs company",
     "body":  "Stockholders' equity = Assets − Liabilities. It's what shareholders 'own' on paper. 'Company equity' usually means the SAME thing. Market cap is what the market thinks it's worth — different number.",
     "source": "Investopedia"},
    {"topic": "fundamentals", "title": "📚 Book value vs market value",
     "body":  "Book value = stockholders' equity ÷ shares outstanding. Market value = price × shares. Tech stocks trade 5-20× book; banks closer to 1×.",
     "source": "SEC EDGAR · Form 10-K notes"},
    {"topic": "fundamentals", "title": "📚 EPS · diluted vs basic",
     "body":  "Basic EPS = net income / shares. Diluted = adds in options + RSUs + convertibles. Always use DILUTED — it's the worst case.",
     "source": "GAAP definitions"},
    {"topic": "fundamentals", "title": "📚 P/E vs PEG",
     "body":  "P/E = price ÷ EPS. PEG = P/E ÷ earnings growth %. P/E of 30 looks expensive until growth is 40% → PEG 0.75 = cheap.",
     "source": "Peter Lynch · One Up On Wall Street"},
    {"topic": "fundamentals", "title": "📚 Free cash flow ≠ earnings",
     "body":  "Earnings can be juiced via depreciation, accruals, stock comp. FCF = cash from ops − capex. Harder to fake. Watch FCF, not just EPS.",
     "source": "Berkshire Hathaway letters"},
    {"topic": "fundamentals", "title": "📚 ROIC · what 'good' looks like",
     "body":  "Return on Invested Capital. >15% = healthy moat. >25% = compounder. <10% = struggling. Easier comp than ROE (no leverage games).",
     "source": "Joel Greenblatt · The Little Book"},
    {"topic": "fundamentals", "title": "📚 Margins · gross / op / net",
     "body":  "Gross = revenue − COGS. Operating = gross − SG&A − R&D. Net = after tax + interest. Software gross can be 70%+, retail 20-30%.",
     "source": "Standard accounting"},
    {"topic": "fundamentals", "title": "📚 Buybacks · sneaky EPS lever",
     "body":  "Buying back stock shrinks share count → EPS rises even if profit is flat. Always check share count YoY before celebrating EPS growth.",
     "source": "Aswath Damodaran"},
    {"topic": "fundamentals", "title": "📚 Stock-based comp eats returns",
     "body":  "Tech firms 'report' SBC as a non-cash expense but it dilutes you. Adjusted earnings that add back SBC = misleading. Look at SBC ÷ revenue.",
     "source": "Damodaran · NYU Stern"},
    {"topic": "fundamentals", "title": "📚 Goodwill · what it really is",
     "body":  "When Co A buys Co B for more than B's book value, the difference is 'goodwill' on A's balance sheet. Big goodwill = M&A-driven growth.",
     "source": "GAAP / IFRS basics"},
    {"topic": "fundamentals", "title": "📚 Enterprise value vs market cap",
     "body":  "EV = market cap + debt − cash. EV is what an acquirer would pay. Compare EV/EBITDA instead of P/E for capital-heavy businesses.",
     "source": "Damodaran"},
    {"topic": "fundamentals", "title": "📚 Working capital basics",
     "body":  "Working capital = current assets − current liabilities. Negative isn't always bad (Amazon thrives on it). Sudden swings = warning.",
     "source": "Buffett's annual letters"},
]

# ---------- Market structure ----------
MARKET_STRUCTURE_CARDS: list[dict] = [
    {"topic": "market_structure", "title": "🏛️ T+1 settlement (US, May 2024)",
     "body":  "US stocks settle one trading day after the trade. You CAN sell what you just bought intraday but the cash isn't really yours until T+1.",
     "source": "SEC Rule 15c6-1"},
    {"topic": "market_structure", "title": "🏛️ Dark pools · ~40% of US volume",
     "body":  "Off-exchange venues where institutions trade to avoid moving the public tape. Prints land on the consolidated tape with a venue flag.",
     "source": "FINRA TRF data"},
    {"topic": "market_structure", "title": "🏛️ NBBO · what you actually buy at",
     "body":  "National Best Bid & Offer. Your market order gets the BEST available bid/ask across ALL exchanges at that instant. Reg NMS protects this.",
     "source": "SEC Reg NMS"},
    {"topic": "market_structure", "title": "🏛️ Halts · LULD bands",
     "body":  "Limit Up/Limit Down. If a stock moves outside its 5% band (10% for under $3) in 5min, it halts 5 minutes. Resumes via auction.",
     "source": "NYSE / NASDAQ rules"},
    {"topic": "market_structure", "title": "🏛️ Circuit breakers · SPX -7/-13/-20",
     "body":  "S&P 500 down 7% = 15-min halt. -13% = another 15-min. -20% = market closes for the day. Levels reset daily.",
     "source": "SEC Rule 80B"},
    {"topic": "market_structure", "title": "🏛️ Short interest + days to cover",
     "body":  "Short interest = shares shorted ÷ float. Days to cover = SI ÷ avg daily volume. Squeeze risk lives at >20% SI and >5 days to cover.",
     "source": "FINRA bi-monthly data"},
    {"topic": "market_structure", "title": "🏛️ PDT rule (>$25k frees you)",
     "body":  "Pattern Day Trader: 4+ day trades in 5 biz days. Triggers margin requirements unless equity > $25k. Cash accts not affected.",
     "source": "FINRA Rule 4210"},
    {"topic": "market_structure", "title": "🏛️ Greeks · delta intuition",
     "body":  "Delta = how much the option moves per $1 in the stock. 0.50 = at-the-money. 0.90 = deep ITM (basically owns the stock). 0.10 = lottery ticket.",
     "source": "Black-Scholes basics"},
    {"topic": "market_structure", "title": "🏛️ Greeks · theta is rent",
     "body":  "Theta = $ value the option loses per day from time decay alone. Long options pay theta; short options collect it. Weekends still count.",
     "source": "Options trading basics"},
    {"topic": "market_structure", "title": "🏛️ Block trades · who's institutional",
     "body":  "≥10,000 shares OR ≥$200k notional. Often print off-exchange (TRF/ADF). Clusters of blocks at the same price = institutional accumulation.",
     "source": "FINRA definitions"},
    {"topic": "market_structure", "title": "🏛️ After-hours · why spreads widen",
     "body":  "RTH: market makers required to quote tight. AH: most MMs go home. Spreads can be 2-5%. Limit orders only — never market AH.",
     "source": "Standard practice"},
    {"topic": "market_structure", "title": "🏛️ Earnings · BMO vs AMC",
     "body":  "BMO = before market open (gap reaction overnight). AMC = after market close (overnight gap). Trade the morning after either.",
     "source": "Earnings calendar convention"},
]

# ---------- History / fun facts ----------
HISTORY_CARDS: list[dict] = [
    {"topic": "history", "title": "📖 Livermore · short the 1929 crash",
     "body":  "Jesse Livermore made $100M (~$1.7B today) shorting the 1929 crash. He famously sold the SHIPPING stocks days before the panic peak.",
     "source": "Reminiscences of a Stock Operator"},
    {"topic": "history", "title": "📖 Buffett's first stock · age 11",
     "body":  "Bought 3 shares of Cities Service Preferred at $38. Watched it fall to $27 (held), sold at $40 (small gain), then it ran to $200. Lifelong lesson on patience.",
     "source": "The Snowball biography"},
    {"topic": "history", "title": "📖 Druckenmiller breaks the Bank of England",
     "body":  "1992: with Soros, shorted £10B betting BoE would devalue. They were right. Made $1B in a day. Druck did the analysis; Soros sized it.",
     "source": "Soros bio + Druck interviews"},
    {"topic": "history", "title": "📖 Black Monday · 1987",
     "body":  "Oct 19, 1987: Dow -22.6% in ONE day — still the largest % drop ever. Triggered by portfolio insurance feedback loops + program trading.",
     "source": "Brady Commission report"},
    {"topic": "history", "title": "📖 The flash crash · 2010",
     "body":  "May 6, 2010 · 2:32pm: Dow lost 1000 pts in 5 min, recovered 700 in another 5. Triggered by a single fat-finger sell of E-mini S&P futures.",
     "source": "SEC/CFTC report"},
    {"topic": "history", "title": "📖 LTCM · 1998 blowup",
     "body":  "Long-Term Capital — 2 Nobel laureates on staff — leveraged 25:1, lost $4.6B in months when Russia defaulted. Genius doesn't survive leverage.",
     "source": "When Genius Failed"},
    {"topic": "history", "title": "📖 Volkswagen · briefly the world's most valuable",
     "body":  "Oct 2008: Porsche revealed it had cornered 74% of VW. Short squeeze ran VW from €200 to €1000 in 2 days. Briefly biggest company on Earth.",
     "source": "FT archives"},
    {"topic": "history", "title": "📖 Archegos · biggest single trader loss ever",
     "body":  "Bill Hwang, March 2021: $20B family office, levered 5-8× via swaps on US tech/media. One bad day = total loss. Six banks took $10B in losses.",
     "source": "DOJ filings"},
    {"topic": "history", "title": "📖 GameStop · January 2021",
     "body":  "WSB retail vs Melvin Capital. GME ran from $20 → $483 in 3 weeks. Melvin lost $6.8B and eventually closed. The first viral short squeeze.",
     "source": "House Financial Services hearings"},
    {"topic": "history", "title": "📖 Nick Leeson · sank Barings",
     "body":  "1995: rogue Singapore trader bet $1.3B on Nikkei futures, lost it after the Kobe earthquake. 233-year-old Barings Bank sold for £1.",
     "source": "Rogue Trader memoir"},
    {"topic": "history", "title": "📖 Soros · 1969 Quantum Fund · 35%/yr",
     "body":  "Soros's Quantum returned ~35%/yr for 30 years — turning $1k → $4M. Reflexivity: prices INFLUENCE fundamentals, not just reflect them.",
     "source": "The Alchemy of Finance"},
    {"topic": "history", "title": "📖 Buffett · the 20-punch card",
     "body":  "Buffett's rule: imagine you have a card with 20 trade punches FOR LIFE. You'd think harder. Most traders take 20 trades in a week.",
     "source": "1987 Berkshire annual meeting"},
    {"topic": "history", "title": "📖 Paul Tudor Jones · predicted '87",
     "body":  "PTJ overlaid 1987 chart on 1929. Same pattern. He shorted into Black Monday, +200% that year. Documentary that birthed the legend got pulled.",
     "source": "Trader (1987 film)"},
    {"topic": "history", "title": "📖 1929 didn't happen on one day",
     "body":  "The crash was 4 days: Oct 24 (Thurs) -11%, Oct 28 (Mon) -13%, Oct 29 (Tues) -12%. Bottom didn't come until 1932 — Dow -89% peak-to-trough.",
     "source": "Federal Reserve historical data"},
]

# ---------- Edge math ----------
EDGE_MATH_CARDS: list[dict] = [
    {"topic": "edge_math", "title": "🧮 Expectancy · the only formula",
     "body":  "Expectancy = (win% × avg win) − (loss% × avg loss). Positive = play forever. Negative = stop. 50% win × 3R win − 50% × 1R loss = +1R/trade.",
     "source": "Van Tharp · Trade Your Way"},
    {"topic": "edge_math", "title": "🧮 Kelly criterion · half Kelly is plenty",
     "body":  "Optimal bet size = (win% / loss) − (loss% / win). Full Kelly maximizes growth but has wild drawdowns. HALF Kelly = ~75% of growth, half the pain.",
     "source": "Kelly 1956 · Edward Thorp"},
    {"topic": "edge_math", "title": "🧮 Drawdown math is brutal",
     "body":  "20% drawdown needs 25% gain to recover. 50% needs 100%. 80% needs 400%. Why Minervini says small losses are SACRED.",
     "source": "Standard math"},
    {"topic": "edge_math", "title": "🧮 Sharpe vs Sortino",
     "body":  "Sharpe penalizes ALL volatility — including upside. Sortino only penalizes DOWNSIDE volatility. Most traders should report Sortino.",
     "source": "Sortino 1994"},
    {"topic": "edge_math", "title": "🧮 Survivorship bias",
     "body":  "Backtests on the CURRENT S&P 500 miss every name that got delisted. Real returns are 2-4% lower than the headline backtest says.",
     "source": "Damodaran · academic finance"},
    {"topic": "edge_math", "title": "🧮 Compounding · the 72 rule",
     "body":  "72 ÷ rate = years to double. 10%/yr → 7.2yr. 20%/yr → 3.6yr. 30%/yr → 2.4yr. Every extra % matters disproportionately.",
     "source": "Folk math · accurate enough"},
    {"topic": "edge_math", "title": "🧮 The 10 best days problem",
     "body":  "S&P 500 1990-2020: full return was 7.7%/yr. MISS the 10 best days → 4.0%/yr. Miss the 20 best → 1.4%/yr. Timing destroys returns.",
     "source": "Hartford Funds study"},
    {"topic": "edge_math", "title": "🧮 Win rate is overrated",
     "body":  "A 30% win rate at 5R is more profitable than 70% at 1R. Trend-followers win 30-40% of the time and crush. R-multiple > win rate.",
     "source": "Van Tharp"},
    {"topic": "edge_math", "title": "🧮 Standard deviation · 1σ = 68%",
     "body":  "Stock returns aren't normal, but rough rule: 1σ around the mean covers ~68% of outcomes. 2σ covers ~95%. 3σ events happen monthly.",
     "source": "Stats basics + fat tails"},
    {"topic": "edge_math", "title": "🧮 R-multiple framework",
     "body":  "R = your initial risk per trade. A +3R win is 3× your stop loss. Track every trade in R. Decouples lessons from absolute $ size.",
     "source": "Van Tharp"},
]


# ===========================================================================
# HOUR → TOPIC routing
# ── CHART PATTERNS — Bulkowski geometry + the WHY (supply/demand mechanics) ──
# Added 2026-06-09 (Ajay: "I want to understand the why behind the chart
# pattern"). Sources verified in this repo's adversarial evidence passes (see
# docs/scalping_methodology.md → Patterns): Bulkowski quoted only in permitted
# framings; the WHY is Minervini's overhead-supply mechanics (TLSMW pp.204-206).
CHART_PATTERN_CARDS: list[dict] = [
    {"topic": "chart_patterns", "title": "🗺️ The master key — every base is ONE story",
     "body":  "VCP, cup-handle, double bottom, flat base — the same story in different shapes: price returns to a resistance level, each visit absorbs more overhead supply, sellers exhaust, then modest demand pops it through. The pattern doesn't predict the breakout — the BEHAVIOR at resistance does.",
     "source": "Minervini TLSMW pp.204-206 · curriculum wk.2"},
    {"topic": "chart_patterns", "title": "🗺️ Why resistance exists — trapped buyers",
     "body":  "Who sells at the old high? (1) Trapped buyers who bought there, sat through the drawdown, and 'just want out even.' (2) Bottom-fishers nailing down quick profit. Their selling IS the resistance. A base is the time it takes to exhaust them.",
     "source": "Minervini TLSMW pp.204-205"},
    {"topic": "chart_patterns", "title": "W Double bottom — the anatomy",
     "body":  "Two near-equal lows, weeks apart (most form in 2-7 weeks), with a ≥10% peak between them. The BUY POINT is that middle peak — not the lows. Bulkowski: the pattern only EXISTS once price closes above that peak.",
     "source": "Bulkowski ThePatternSite (eedb) · LMW 2000"},
    {"topic": "chart_patterns", "title": "W Double bottom — WHY the second low matters",
     "body":  "The second trip to the low is a TEST: does new selling show up at the old price? When it holds (or briefly undercuts then snaps back), the weak holders who were going to sell already have. The undercut flushes the last stops — fewer sellers left for the move up.",
     "source": "O'Neil HTMMIS · Minervini shakeout concept"},
    {"topic": "chart_patterns", "title": "W Unconfirmed = NOT a pattern",
     "body":  "Bulkowski's verified number: unconfirmed double bottoms continue LOWER 48% of the time — a coin flip. The W shape means nothing until a daily CLOSE above the middle peak. Before that it's a shape you watch, never a signal you act on.",
     "source": "Bulkowski ThePatternSite, verified 2026-06-09"},
    {"topic": "chart_patterns", "title": "W Adam vs Eve bottoms",
     "body":  "Bulkowski names bottoms by shape: ADAM = narrow, V-shaped, single-spike low (panic). EVE = wide, rounded, choppy low (gradual exhaustion). Eve&Eve is his best double-bottom variant (12% break-even failure in his hindsight database; caveats apply).",
     "source": "Bulkowski, Encyclopedia of Chart Patterns"},
    {"topic": "chart_patterns", "title": "👤 Inverse H&S — the anatomy",
     "body":  "Three lows: the middle (head) lowest, the two shoulders near-equal (within ~1.5% in the academic definition). Neckline through the two interim peaks. Confirmation = close above the neckline. Target convention: head-to-neckline height added above.",
     "source": "Lo-Mamaysky-Wang 2000 Def.1 · Bulkowski hsb"},
    {"topic": "chart_patterns", "title": "👤 Inverse H&S — WHY it works when it works",
     "body":  "The head is the panic low. The right shoulder makes a HIGHER low — sellers couldn't push it back down. That failed retest + shorts covering through the neckline is the demand that fuels the breakout. The best-studied reversal: two peer-reviewed predictive results (FX & US indices) — both short of standalone profitability.",
     "source": "Chang & Osler 1999 · Savin et al. 2007"},
    {"topic": "chart_patterns", "title": "☕ Cup-with-handle — why the handle exists",
     "body":  "The cup works through most of the overhead supply; the handle is the FINAL shakeout — a quiet downward drift in the upper half of the cup that clears the last weak hands. A handle that forms in the LOWER half or wedges upward = supply still in control. Buy through the handle high.",
     "source": "O'Neil HTMMIS · Bulkowski cup.html"},
    {"topic": "chart_patterns", "title": "📏 Flat base — boring is bullish",
     "body":  "A shallow (≤15%) sideways shelf after a run-up. Why it's strong: holders REFUSE to sell despite weeks of chop — no supply. Often stacks on a prior base ('base on base'). Tight weekly closes + RS line at highs = institutions sitting on the bid.",
     "source": "O'Neil HTMMIS · IBD base reading"},
    {"topic": "chart_patterns", "title": "🚩 Bull flag — continuation, NOT a bounce",
     "body":  "A flag needs a POLE: a sharp prior advance, then a light-volume drift against it. It's a rest in a trend, not a bottom — don't confuse it with reversal patterns. Red flag: the flag retraces >50% of the pole.",
     "source": "Bulkowski flags.html · curriculum wk.3"},
    {"topic": "chart_patterns", "title": "📐 The measure rule is a convention",
     "body":  "Target = pattern height added to the breakout. Even in Bulkowski's hindsight-perfect data it's met only ~65-73% of the time. Use it to judge whether the trade's reward justifies the risk BEFORE entry — never as a prediction.",
     "source": "Bulkowski, Encyclopedia of Chart Patterns"},
    {"topic": "chart_patterns", "title": "↩️ Throwbacks — don't panic on the retest",
     "body":  "After ~65% of inverse-H&S breakouts, price THROWS BACK to the neckline before continuing. The retest of a broken level is normal — old resistance becoming support. Panic-selling the throwback is how breakout buyers turn winners into losers.",
     "source": "Bulkowski hsb.html, verified 2026-06-09"},
    {"topic": "chart_patterns", "title": "⚖️ What the science actually says",
     "body":  "Lo-Mamaysky-Wang (J. Finance 2000): algorithmically-detected patterns carry INFORMATION — return distributions differ — but that's not a profit guarantee, and the double bottom was a null on NYSE/AMEX. Patterns are context for entries with defined risk, not crystal balls.",
     "source": "Lo, Mamaysky & Wang 2000 · see docs/scalping_methodology.md"},
]

# ── CANDLE READS — wick/body anatomy as a supply/demand scoreboard ───────────
# The vocabulary the scalp_tape (SEPA Watch) alerts speak. Honest per the
# verified record: candle patterns standalone are weak-to-null; the read only
# means something AT a level WITH volume.
CANDLE_READ_CARDS: list[dict] = [
    {"topic": "candle_reads", "title": "🕯 Candle anatomy — the bar's scoreboard",
     "body":  "Every candle answers one question: who won the bar? Body% of range = control (≥60% one side dominated). Wicks = rejected prices. Close-location (CLV): close at the high = +1, at the low = -1. That's the whole vocabulary — everything else is combinations.",
     "source": "Chaikin CLV · scalping/candles.py"},
    {"topic": "candle_reads", "title": "🕯 Strong body = control",
     "body":  "A ≥60%-body bar closing near its extreme means one side controlled the auction start to finish. THROUGH a level on volume, that's the read you want (it's exactly your BREAKOUT_STRONG alert). The same bar in the middle of nowhere means little.",
     "source": "scalping/candles.py thresholds (CONFIGURED)"},
    {"topic": "candle_reads", "title": "🕯 Upper-wick rejection — supply showed up",
     "body":  "A long upper wick (2-3× the body, Bulkowski's shooting-star convention) AT a breakout level says: buyers pushed through, sellers slammed it back. That's distribution at the level — your REJECTION alert. Same wick in open air = noise.",
     "source": "Bulkowski ID convention — never quoted as a win rate"},
    {"topic": "candle_reads", "title": "🕯 Hammer honesty",
     "body":  "The hammer (long lower wick = dip-buying) is one of the most-taught candles — and Bulkowski's own database ranks it near-random (~60%, rank 65/103). The LOCATION (at support, after a flush, on volume) carries the information; the candle alone doesn't.",
     "source": "Bulkowski thepatternsite.com/Hammer.html"},
    {"topic": "candle_reads", "title": "🕯 Doji = undecided, NOT reversal",
     "body":  "A doji (body <5% of range — open≈close) means the auction ended where it started: nobody won. Academic check on 349 US stocks found dojis carry little predictive value. Treat it as a state label ('unresolved at the level'), never a signal.",
     "source": "Horton 2009, QREF — null result"},
    {"topic": "candle_reads", "title": "🕯 Engulfing = body dominance",
     "body":  "Bulkowski's engulfing convention: today's BODY swallows yesterday's body — ignore the shadows. The read: the new bar completely repriced the prior bar's auction. Direction + level + volume decide whether it matters.",
     "source": "Bulkowski ID convention"},
    {"topic": "candle_reads", "title": "🕯 No volume, no read",
     "body":  "A candle read at a level only counts WITH participation — ≥1.5× the average bar volume. A breakout bar on dry volume is the CVGI-class fake: the shape without the demand. This is why your tape-watch alerts carry the volume ratio on every read.",
     "source": "Minervini TLSMW p.203 (expanding volume)"},
    {"topic": "candle_reads", "title": "🕯 Compression forecasts volatility, not direction",
     "body":  "Tight ranges and dojis at a level (your STALL state) mean energy is building — volatility clustering is one of the most robust findings in finance (Engle 1982). But compression says MOVE COMING, never which way. Wait for the resolving bar.",
     "source": "Engle 1982, Econometrica"},
    {"topic": "candle_reads", "title": "🕯 The null that keeps you honest",
     "body":  "The decisive study at the 5-minute horizon (83 candle rules, DJIA stocks): NO rule beat buy-and-hold after costs and data-snooping correction. Candles are a context layer for reads at levels — never a standalone system.",
     "source": "Duvinage, Mazza & Petitjean 2013, Quantitative Finance"},
    {"topic": "candle_reads", "title": "🕯 Your alerts speak this language",
     "body":  "The SEPA Watch pushes ARE candle reads at levels: BREAKOUT_STRONG (big body + close-at-highs + volume through the pivot), REJECTION (upper wick at the level), BREAKDOWN/RECLAIM (strong body losing/retaking VWAP), STALL (doji at the line). Every alert self-grades vs the next 30 min on /scalping.",
     "source": "scalping/sepa_watch.py · /scalping"},
]


# ===========================================================================
# Each hour of the day (24h, server local TZ = America/New_York) maps to
# one TOPIC; the specific card within a topic cycles by day-of-year.
#
# Coverage extended to 0-23 on 2026-05-21 — user asked for cards EVERY
# hour. Overnight slots stay light (history / edge_math / psychology)
# to give the late-night reader something interesting rather than a
# strict trading rule when markets are closed. Quiet hours (per-user
# pref in /notifications) gate delivery, so the default 22:00-08:00
# mute window suppresses these for users who don't want night pings.
HOURLY_TOPIC: dict[int, str] = {
    0:  "history",            # midnight — fun fact
    1:  "edge_math",
    2:  "psychology",
    3:  "chart_patterns",     # 2026-06-09: Bulkowski patterns + the why
    4:  "fundamentals",       # premarket starts ~4 AM ET
    5:  "market_structure",
    6:  "candle_reads",       # 2026-06-09: wick/body anatomy at levels
    7:  "edge_math",
    8:  "chart_patterns",     # pre-open pattern rep (was a 3rd fundamentals slot)
    9:  "entry",              # 9:30 ET regular session open
    10: "market_structure",
    11: "risk",
    12: "chart_patterns",     # midday pattern rep
    13: "sell_rules",
    14: "psychology",
    15: "entry",
    16: "review",             # 16:00 ET close
    17: "fundamentals",
    18: "edge_math",
    19: "candle_reads",       # evening candle rep
    20: "psychology",
    21: "review",
    22: "edge_math",
    23: "history",
}

TOPIC_POOLS: dict[str, list[dict]] = {
    "entry":            ENTRY_CARDS,
    "risk":             RISK_CARDS,
    "sell_rules":       SELL_RULES_CARDS,
    "psychology":       PSYCHOLOGY_CARDS,
    "review":           REVIEW_CARDS,
    "fundamentals":     FUNDAMENTALS_CARDS,
    "market_structure": MARKET_STRUCTURE_CARDS,
    "history":          HISTORY_CARDS,
    "edge_math":        EDGE_MATH_CARDS,
    "chart_patterns":   CHART_PATTERN_CARDS,
    "candle_reads":     CANDLE_READ_CARDS,
}

# Convenience flat list — used by tests and the count line in admin diagnostics.
ALL_CARDS: list[dict] = [c for pool in TOPIC_POOLS.values() for c in pool]


def _now_et() -> datetime:
    """Current time in US Eastern. Used to decide both day-of-year and
    hour-of-day so card rotation matches the user's local rhythm."""
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-5)))


def _day_of_year_et() -> int:
    return _now_et().timetuple().tm_yday


def pick_for_topic(topic: str, day_of_year: int | None = None) -> dict | None:
    """Deterministic card pick from a topic pool keyed on day-of-year."""
    pool = TOPIC_POOLS.get(topic)
    if not pool:
        log.warning("flashcards: unknown topic %r", topic)
        return None
    day = day_of_year if day_of_year is not None else _day_of_year_et()
    return pool[day % len(pool)]


def pick_for_hour(hour: int, day_of_year: int | None = None) -> dict | None:
    """Resolve hour → topic → card. The topic mapping is HOURLY_TOPIC;
    cards within a topic cycle by day so consecutive days never repeat
    the same card at the same hour."""
    topic = HOURLY_TOPIC.get(hour)
    if not topic:
        return None
    return pick_for_topic(topic, day_of_year)


# Backward-compat aliases for the previous 3-slot scheduling. Cron used
# to fire `python -m flashcards.flashcards morning` etc.; keep these so
# rolling deploys don't error during the transition.
def pick_for_slot(slot: str, day_of_year: int | None = None) -> dict | None:
    """Legacy alias: maps morning/midday/close to the new hourly topic
    map at a representative hour for that slot."""
    slot_to_hour = {"morning": 9, "midday": 12, "close": 16}
    return pick_for_hour(slot_to_hour.get(slot, 9), day_of_year)


def _fire(card: dict, tag_suffix: str) -> dict:
    """Shared push-send path. Returns {ok, slot/hour, title, sent, failed, total_targets}."""
    body = card["body"]
    source = card.get("source")
    if source:
        body = f"{body}\n— {source}"
    # Route flashcards to the dedicated /learn module instead of /sepa.
    # The user (2026-05-22) wanted pushes to land in their topic context
    # rather than the trading list. /learn reads the ?topic= query and
    # renders the full pool for that topic with the just-pushed card
    # highlighted. ?from=alert tells the page to show a back-to-alerts
    # link so the user can return to the notification feed.
    topic = card.get("topic") or "entry"
    default_url = f"/learn?topic={topic}&from=alert"
    payload = {
        "title":  card["title"],
        "body":   body[:300],
        "tag":    f"flashcard-{tag_suffix}",
        "url":    card.get("url", default_url),
        "kind":   "minervini_flashcards",
    }
    try:
        from push import sender
        result = sender.send_to_all(payload, kind="minervini_flashcards")
    except Exception as exc:
        log.warning("flashcard fire failed: %s", exc)
        return {"ok": False, "reason": str(exc)}
    log.info("flashcard fired: tag=%s topic=%s title=%r sent=%d failed=%d",
             tag_suffix, card.get("topic"), card["title"],
             result.get("sent", 0), result.get("failed", 0))
    return {"ok": True, "tag": tag_suffix, "topic": card.get("topic"),
            "title": card["title"], **result}


def fire_hourly() -> dict:
    """Fire the card mapped to the current hour (ET). No-op outside the
    populated HOURLY_TOPIC window so the cron can use a single wide
    range without worrying about misfiring at midnight."""
    now = _now_et()
    hour = now.hour
    card = pick_for_hour(hour)
    if card is None:
        log.info("flashcards: no card mapped for hour=%d ET — skipping", hour)
        return {"ok": False, "reason": f"no topic for hour {hour}", "hour": hour}
    return _fire(card, tag_suffix=f"h{hour}-{_day_of_year_et()}")


def fire_flashcard(slot_or_topic: str) -> dict:
    """Legacy entrypoint kept for backward compat with the 3-slot cron
    (`python -m flashcards.flashcards morning`).

    Also accepts a TOPIC name directly (`python -m flashcards.flashcards
    fundamentals`) for manual testing of any individual topic."""
    # First try the legacy slot names (morning/midday/close).
    if slot_or_topic in ("morning", "midday", "close"):
        card = pick_for_slot(slot_or_topic)
        if card is None:
            return {"ok": False, "reason": f"no card for slot {slot_or_topic}"}
        return _fire(card, tag_suffix=f"{slot_or_topic}-{_day_of_year_et()}")
    # Then accept a direct topic name for ad-hoc testing.
    if slot_or_topic in TOPIC_POOLS:
        card = pick_for_topic(slot_or_topic)
        if card is None:
            return {"ok": False, "reason": f"empty pool for topic {slot_or_topic}"}
        return _fire(card, tag_suffix=f"topic-{slot_or_topic}-{_day_of_year_et()}")
    # Finally accept "hourly" as the new canonical entrypoint name.
    if slot_or_topic == "hourly":
        return fire_hourly()
    return {"ok": False, "reason": f"unknown arg: {slot_or_topic}"}


if __name__ == "__main__":
    # CLI for cron + manual testing:
    #   python -m flashcards.flashcards hourly         # picks topic from current hour ET
    #   python -m flashcards.flashcards fundamentals   # force a specific topic
    #   python -m flashcards.flashcards morning        # legacy slot alias
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else "hourly"
    print(fire_flashcard(arg))
