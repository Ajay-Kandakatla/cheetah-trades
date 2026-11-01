# Martin Luk (@martinlukkt): deep read of the public playbook

Read 2026-11-01. Everything below carries the URL I actually read. Tags used:
- **[NUM]**: Luk states it himself, with a number.
- **[QUAL]**: Luk states it himself, with no number.
- **[INFERRED]**: my reading, or a third party's.
- **[NOT FREE]**: only in a paid product. Nothing like this was found.

Verbatim quotes come from YouTube auto-captions, so a few words are mangled ("3 hour" = 3R, "ankle free web" = anchored VWAP).

## 0. Verdict
- **Access: free-complete.** His X bio, read through the fxtwitter API (https://api.fxtwitter.com/martinlukkt), says: "Trader | +969% in US Investing Championship 2025 / NO PAID SUBSCRIPTIONS OR SERVICES / Streams and recordings: youtube.com/@martinlukkt". No course, newsletter or Discord is for sale. The full method is in free sources: a free Substack guest post, two free TraderLion YouTube interviews (about 4h09m and about 2h10m) and near-daily free live streams.
- **The gaps are discretionary, not hidden.** In his own words, the stock picking and the selling are discretionary ("Selling is really hard. I don't have a hard rule."). The mechanical skeleton (universe, trigger, stop, size, trim, trail) is published with numbers.

## 1. USIC record (verified)
| Year | Division | Result | Source |
|---|---|---|---|
| 2024 | USIC $20,000+ Accounts, Stock Division | **6th, +283.1%** ("Martin Luk + 283.1%") | https://financial-competitions.com/previousstandings/2025/2/12/december-final-standings-2024 |
| 2025 | USIC $20,000+ Accounts, Stock Division | **1st, +969.8%** (579 entrants overall; 2nd Rajnus Capital +382%) | https://financial-competitions.com/previousstandings/2026/1/24/december-standings-2025 |
| 2026 (through 30 Sep) | $20,000+ Stock | **1st, +785.8%** (712 entrants; 2nd Victor M +363%) | https://financial-competitions.com/previousstandings/2026/10/24/september-standings-2026 |

CTE research sheet (https://completetradersedge.com/wp-content/uploads/2026/09/CTE-Research-Sheet-US-Investing-Championship-2.pdf, read from the saved text in dl-cte/cte.txt):
- His 2025 peak was +1,358.2% in November, against +969.8% final (a 388.4-point give-back).
- Highest year-end $20k+ return on record, "passing Oliver Kell's +941.1% (2020)".
- Two-year compound for 2024-25 of +3,998% (the organiser's figure).

His own numbers:
- 2025: 209 winners and 731 losers, a 22% win rate, and a 26% drawdown in December 2025. Source: VKNEJA5r8zw at 0:23, 20:20, 24:56 and 46:22.
- 2024: a 25% win rate, an 18-trade losing streak and a 30% drawdown from June to August. Source: the Substack post.

## 2. Primary sources read
1. **Guest post in his own words**, 2025-02-01, read in full: https://tradingresourcehub.substack.com/p/martin-luk-283-usic-2024-key-lessons
2. **TraderLion podcast, 2026-01-31**, "+969% Return in 1 Year: The Pullback Strategy of a Trading Champion" (4h09m), FULL transcript read: https://www.youtube.com/watch?v=VKNEJA5r8zw. I pulled the transcript from YouTube's own "Show transcript" panel in the built-in browser; captions are auto-generated. The description (TraderLion's text) also says "risking 0.5% per trade while running up to 280% margin exposure" and "46% of trades were avoidable mistakes".
3. **TraderLion podcast, 2025-04-06**, "283% Gain in 1 Year": https://www.youtube.com/watch?v=lS9zbnLi1Gg. I read the description and chapter list only; the transcript request returned HTTP 400 three times. Chapters include "Adopting a tighter stop strategy", "Ideal entry tactics: Inside days, ORH, and prior day highs", "Sell strategies: Into strength vs. trailing stops" and "Martin's scanning system: Pre-market, daily, and leaders".
4. **His own live streams** on https://www.youtube.com/@martinlukkt (RSS feed lists 15 streams from 2026-09-14 to 2026-10-28). I read four transcripts directly to spot-check the fan Q&A:
   - iMBI3ZcQ6sU (28 Oct 2026), 1:15-1:22: screener settings discussion.
   - 297D7gVsLY4 (27 Apr 2026), 1:02-1:05: QQQ extension.
   - tx321OQ8iD0 (24 Jun 2026), 1:45-1:50: stop below the breakout-bar low, 5/15-minute entry.
   - yvaMXQfOEWI (26 May 2026), 1:00-1:03 and 2:12-2:15: 0.3% risk, chasing gap-ups.
5. **Fan reference site martinluk.com** ("Not by Martin. Built by a fan"). Its answers are edited from the stream captions and timestamped. I read the Screeners page in full (https://martinluk.com/screeners/index.html), plus the FAQ (https://martinluk.com/faq/index.html) and the Q&A of 109 answers. The four answers I checked against the original captions were faithful. I also checked the three screener screenshots (frames from his stream, iMBI3ZcQ6sU at about 1:17:44 to 1:18:27) visually, at https://martinluk.com/assets/screeners/{premarket,leader,potent}.png.
6. **Kyna Kosling, "Martin Luk's Low-Friction Study Process"**, 2026-01-10, free: https://tradingresourcehub.substack.com/p/martin-luk-study-process. It is a short-side case study with first-person quotes from Luk.
7. **X**: https://x.com/martinlukkt/status/1871449484066160646 (2024-12-24) reads "US Investing Championship 2024 +150.2% YTD til 30Nov". In VKNEJA5r8zw at 1:00:20 he says he wrote an X post in May 2025 on his pullback entry tactics. I did NOT find or read that post: the web-search budget was exhausted and the syndication endpoint was rate-limited. **This is a gap to close.**
8. **Independent backtest (secondary)**: https://github.com/rootchunhe/martin-luk-backtesting, README and specs.py read in full.

## 3. Rule set (his words, with URL and tag)

### 3a. Universe and scans
- [NUM] "I mainly trade stocks with >5% ADR ... but this isn't a hard rule." (Substack)
- [NUM] "I spend around 30 minutes a day scanning for the previous day's high performers ('potent scan') and pre-market gap-ups ('pre-market scan'). On weekends, I also scan for the biggest movers of the past 30 days ('leader scan')." (Substack)
- [NUM] Watchlists: "Lead: 9 EMA > 21 EMA > 50 EMA. Mediocre: 9 EMA > 21 EMA < 50 EMA or 9 EMA < 21 EMA > 50 EMA. Lag: 9 EMA < 21 EMA < 50 EMA." He also keeps a small-cap list for "<$5B market cap". (Substack)
- [QUAL] Theme rule: "When several stocks within the same sector newly appear on my scans ... or 'upgrade' to a stronger watchlist, I pay more attention to them." (Substack; repeated in VKNEJA5r8zw at 2:31-2:33)
- [NUM] TradingView screens as shown on his stream, iMBI3ZcQ6sU (28 Oct 2026). I verified them against the screenshot frames.
  - **Premarket**: US; Mkt cap > 100M USD; Avg vol 10D > 500K; Price×vol > 50M USD; Volatility 1W > 3.5%; sorted by Pre-mkt chg % descending.
  - **Leader**: US; Mkt cap > 100M USD; Avg vol 10D > 500K; Price×vol 1W > 300M USD; sorted by Perf % 1M descending.
  - **Potent**: US; Price > EMA 50; Price > EMA 21 (the fan site says ≥); Mkt cap > 100M USD; Volatility 1W > 3.5%; Price×vol > 50M USD; Industry selection (99+, list not visible); Chg from open outside -0.5% to 0.5%; sorted by Chg % descending.
  - Transcript at 1:17:58: "Maybe I'm I will like trying to change this like this dollar volume to like 100 million"; at 1:18:23: "I filter some bioteex out on my potent watch list"; at 1:18:34, he added a filter to "exclude the buyouts or the merger".
- [NUM] "I want to focus only fast moving stocks in the [hot sector]." (VKNEJA5r8zw at 18:45) To pick within a theme: relative strength first, then tightness over the 1-3 days before the breakout, then "I would prioritize trading the one with the highest dollar volume". (VKNEJA5r8zw at 3:16:37-3:18:44)
- [NUM, fan-paraphrased, not checked by me] "perhaps those trading at least $500 million in daily volume or having at least a $10 billion market cap." (20 May 2026 stream, via https://martinluk.com/faq/index.html; original 603RKPXwd3Y at t=7674s)
- [NUM, fan-paraphrased] "Generally, I won't take a stock within five days of earnings, I think 95% of the time." (26 Oct 2026 stream via the fan Q&A)

### 3b. Setup: where to buy
- [NUM] "generally when I'm trading the pullbacks, I'm going to wait at least on the daily 9 [EMA]" (VKNEJA5r8zw at 49:58)
- [QUAL] "the best timing for you to buy in pullback will be the first pullback into the supports level" (1:17:34). "the really the good one would be the first pullback within a base the really the base with some higher lows" (2:04:13). The highest-edge spots are where levels coincide: 9/21/50/150 EMA, anchored VWAP, prior swing high and unfilled gap (1:10:01-1:10:32).
- [NUM] A pullback to the daily 9 EMA has "the lowest win rate"; slower EMAs have the highest. (3:19:26)
- [QUAL] "if the stock is like basing below the angle VWAP or the basing below the EMAs then it's not good very good spots like to take the long entries" (1:31:08)
- [QUAL] AVWAP anchor: "I prefer to put it in the swing high or the swing lows of a base" (1:08:15); also on huge gap-up or gap-down days (1:11:40, 1:47:10). He uses daily anchors about 80-90% of the time (1:07:24).
- [QUAL] "I really love the stock that is gapping up and then reverses or just the stock is um opening lower and then just go just go down and just um falling into the support level ... V-shaped recovery" (1:25:54-1:26:44)

### 3c. Entry trigger
- [NUM] "normally I would look for a really really really fast flush to the downside into the supports level which is on the hourly 9 and the 21 EMA ... I will look at the 1 minute or the 5 minute or the 15 minute candle for the first breakout of the previous bar high" (VKNEJA5r8zw at 1:56:39-1:57:03)
- [NUM] "for the first 15 minute ... I'm using the one minute candle breakout, for 15 minutes to maybe the 60 minute after the market open I'm using the five minute candle breakout ... it's all about the intraday breakout of the previous bar high" (1:57:23-1:58:11)
- [NUM] He does not chase: "if it's up for more than 3% from the low of day then I'm I'm just avoiding it" (24:37)
- [QUAL] "Generally, I wait for the five minute or the 15 minute candle breakouts after the stock uh find support at the support level. So I generally won't uh buy the dip on the way down." (tx321OQ8iD0, 24 Jun 2026 at 1:49:06-1:49:27)
- [NUM, fan-paraphrased] Timing: "most of my trades are still made within the first hour, or maybe the first two hours." "About 90% of the time I use market orders for entries." (23 Oct and 14 Jul 2026 streams via the fan Q&A)
- [QUAL] Breakouts and EPs are still traded: inside-day, previous-day-high and opening-range-high breakouts (BBAI, HOOD, FUTU, RGTI in VKNEJA5r8zw at 2:26-3:13). In 2026 he also chases gap-ups when he has a profit cushion: "I would rather like take like maybe one to two% uh risk" of profit, with the stop at the low of day (yvaMXQfOEWI at 1:02:57-1:03:35).

### 3d. Initial stop
- [NUM] "I tightened my stops to 1–5% (mostly), and avoided exceeding half of the stock's average daily range (ADR) — so, no more than a 2.5% stop for a 5% ADR stock ... Over 80% of my trades in 2024 used stops of <3.5%." (Substack)
- [NUM] "I limit my stops at the less than 50% of these stocks average [daily range] so maximum will be 5% ... I rarely would set my stop wider than 3% or even 2.5%" (VKNEJA5r8zw at 18:10-18:39). "I set my stop really tight. So really mostly under 2.5%." (30:50)
- [NUM] "I'm going to set the stop either at the low of day. I think maybe 60 to 70% at the low of day. But sometimes the stop may be too wide ... Then I may set it to the low of the breakout bar or the low of the previous bar." (1:58:18-1:58:39)
- [QUAL] Hard stop: "I define my stop before entering a trade, and place a hard stop as soon as I'm filled" (Substack). Stops are market orders, never stop-limits (fan Q&A, 14 Jul 2026).
- [NUM] Shorts (mirror image): "I place my stop loss at the high of the day or at the high of the breakdown candle, with a typical range of 1.5–5%." (Kyna study-process post)

### 3e. Position sizing and exposure
- [NUM] "my portfolio risk per trade is around 0.5%" (VKNEJA5r8zw at 16:09). In 2024 it was "account risk at 0.5–1% per trade" (Substack). In 2026: "now I'm using like [0.]3% risk per trade ... even if I'm losing 10 trades in a row, I would get a 3% draw down" (yvaMXQfOEWI at 2:13:26). After the December 2025 drawdown he cut to about 0.3%, 0.25% or 0.2% (fan Q&A, 8 May 2026).
- [NUM] Position size: "most positions are around 25 to 30%" with a 35% cap in 2024; micro-caps "around maybe 20%"; slow names can go over 35%, "But still I'm going to limit the risk per trade to [0.]5%" (16:45-18:10).
- [NUM] Worked example: "$10,000 account ... risking .5% ... 50 bucks ... divided by 2.5% ... $2,000 position ... 20% position size" (3:03:50-3:04:26).
- [NUM] Exposure: "at most it is 280% long" (41:14-41:30). Positions: "normally ... three to four positions ... up to maybe six or seven ... 11 positions" at peak margin (43:49-44:31). Exposure is built progressively and only while new trades work (41:47-42:44).
- [QUAL] Risk control: never increase risk in a drawdown (yvaMXQfOEWI at 2:14:33-2:14:56). Size down below $5 (Substack).

### 3f. Exits and trailing
- [NUM] "I actually don't have a very strict sell rule. I would sell partial into strength when it's up 3 [R] or 5 [R] ... generally I would sell into strength when I think it's really extended on the lower time frame especially the 1 hour" (VKNEJA5r8zw at 2:27:34-2:28:24)
- [NUM] "I trim my position at around 15% each. So every time I think this stock is extended I sell 15% ... then I closed this trade on the first close below the 9 EMA." (2:29:05-2:29:24) First sell into strength is 15-20%: "Yep. Correct." (2:56:11-2:56:20)
- [NUM] The 2024 trailing rule is the "9 EMA trailing stop sell rule" (Substack). Now he puts a hard stop slightly below the 9 EMA or the candle low, because he cannot watch the close from Hong Kong (2:53:56-2:54:26). In 2026 he often sells into strength before a 9 EMA close: "Selling is really hard. I don't have a hard rule." (fan FAQ, 27 Oct 2026)
- [NUM] Holding periods: shorts "only maybe two to three days" (25:31). Longs are sometimes trailed "two or three weeks before the first trim" (3:36:59-3:37:07).
- [NUM] Shorts: "Trim ~15% when up over 3R"; exit "if the hourly bar closes above the 50 EMA" (Kyna study-process post).

### 3g. Market filter
- [QUAL] He ranks three inputs: "your own trade feedback is the most important one"; then "I look at the Q's and IWM every day ... if the Q is really kind of extending ... that's not the right place to really ... be really aggressive ... the best time to be aggressive would be during the pullbacks of the Q's"; then watchlist breadth, meaning the number of names in the Lead versus Lag lists. (VKNEJA5r8zw at 3:47:19-3:50:49)
- [NUM, an example rather than a hard threshold] "for now is almost 2% above the 9 EMA. So it's not close to any of the EMAs ... I'm not going to like be very aggressive on the long side ... I'm not going to chase the breakouts right here." (297D7gVsLY4, 27 Apr 2026 at 1:02:41-1:03:20)
- [QUAL] Choppy market: "trade less"; scale down when the equity curve makes lower highs (iMBI3ZcQ6sU at 1:16:45). He finds that after 2008, QQQ fell 15% only when IWM was the lagging index (3:57:43-4:00:16).
- [INFERRED] The repo's "QQQ 9 EMA > 21 EMA, no new longs otherwise" is the repo author's codification. **Luk never states it as a numeric rule.**

## 4. Data the strategy needs
Daily OHLCV for US common stocks, with:
- daily EMAs 9/21/50/150 and weekly EMAs 9/21
- 20-day ADR%
- dollar volume (daily, and 1-week sum against $300M)
- 1-week volatility above 3.5%
- 1-month performance rank
- market cap above $100M, and a $5B small-cap split
- 10-day average share volume above 500K

Also:
- **Pre-market** % change and gap (the premarket screen).
- **Intraday bars** at 1-minute (first 15 minutes) and 5-minute (15-60 minutes), plus 15-minute and hourly for the 9/21/50 EMA support and the entry trigger, the low of day and breakout-bar stops, and the 3% no-chase rule.
- **Anchored VWAP** on daily and hourly bars, anchored at the base swing high or low and at gap days.
- **Earnings calendar** for the 5-day blackout.
- **QQQ and IWM** daily EMAs, for distance from the 9 EMA.
- **Sector or industry labels**, for theme clustering and Lead/Mediocre/Lag upgrades.
- For shorts: borrow availability and inverse or leveraged ETFs.

He ignores volume at entry: "I don't watch volume when I'm entering a position." (fan Q&A, 27 Oct 2026)

## 5. Similarity to Gajjala (GG)
**Shared:**
- Both are scanner-driven, with a pre-market gap-up scan and a scan of yesterday's top movers.
- Both trigger on an intraday break of the previous 1- or 5-minute bar high or the opening-range high, with a low-of-day or breakout-bar stop.
- Both use very tight stops (mostly under 2.5-3%), accept low win rates (22-25%) and chase high-R winners.
- Both trade momentum and theme names and publish explicit numbers.

**Different:**
- Luk is a swing trader: days to weeks for longs, 2-3 days for shorts. He trails the daily 9 EMA and trims about 15% at 3-5R. GG is intraday.
- Luk's core 2025 setup is the **pullback** into rising daily/hourly EMAs and anchored VWAP after a fast morning flush. It is a reversal-then-breakout of the previous bar high, not a first-candle gap breakout.
- Luk demands liquidity (cap above $100M, $50M+ dollar volume, moving towards $100M; prefers $500M+). GG's lane favours low float.
- Luk uses 0.3-0.5% risk per trade with 20-30% positions and up to 280% gross on margin.
- Luk trades shorts and inverse ETFs too.
- Luk's stock picking and selling are partly discretionary by his own admission.

**Overall: moderately-high similarity (about 6/10).** The gap-up scan, the 1/5-minute previous-bar-high trigger, the low-of-day stop and the explicit numbers map straight onto a GG-style scanner. The added layer is daily EMA and anchored-VWAP context, plus multi-day holding.

## 6. Independent evidence (secondary)
rootchunhe/martin-luk-backtesting codifies his rules on CRSP and TAQ data from 2016 to 2026-08:
- The `full` run makes CAGR 12.1%, Sharpe 0.83, max drawdown -13%, 29% win rate, 27 trades a year.
- **His literal morning 1/5-minute entry shows no edge after spreads**: 13% winners, CAGR -2.2%.
- The edge in that sample comes from the daily touch-and-reclaim of the 9 EMA, using a 15:55 close-confirm proxy entry.
- The result is regime-bound (2020 and 2023-25) and sits on a sharp 9 EMA peak; the 5 and 13 EMA variants are weaker.
- The 30% run-up filter and the 250-day-high anchored-VWAP anchor are the author's or third parties' choices, not Luk's.

## 7. Open items and caveats
- His May 2025 X post on pullback entry tactics was not located (search budget exhausted). It is the one primary source still unread.
- I could not read the 2025 TraderLion transcript (lS9zbnLi1Gg; HTTP 400). Its numbers are covered by the Substack post from the same period.
- At VKNEJA5r8zw 33:42 the auto-caption says "risking 5% of my account" with a 1.5% stop giving about 20% size. That arithmetic is inconsistent and is almost certainly ".5%". The clean worked example at 3:03:50 (0.5% risk, 2.5% stop, 20% position) and the TraderLion description ("risking 0.5% per trade") settle it.
- Fan-site answers are the fan's edited paraphrases. I checked four against the original captions and they were faithful, but treat the rest as secondary.
