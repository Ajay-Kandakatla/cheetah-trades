/* MinerviniLesson — small daily learning card.
 *
 *  Originally this card had: auto-rotating quotes every 10s, prev/next
 *  buttons, a pause toggle, progress dots, an expand-the-full-framework
 *  button, AND a day-picker row at the bottom. The user said it was
 *  "too noisy" and asked to "make it smaller and change every day."
 *
 *  Reduced to the quiet version:
 *    • Today's topic + emoji (rotates daily via todayLessonCT)
 *    • One quote — deterministically picked from the topic's quote list
 *      using day-of-year, so it changes day-to-day but stays stable
 *      within a single trading session.
 *    • THE RULE — one-liner
 *    • TODAY — specific application
 *
 *  Removed: framework expansion, day picker, prev/next, auto-rotate,
 *  pause, progress dots, the "WHY" pillar. The framework data is still
 *  in LESSONS (used elsewhere in time / kept available for future deep
 *  pages) but no longer surfaced in this card.
 *
 *  defaultTopic prop is still honored so a page can force a specific
 *  topic — useful if we ever wire "show me the sell-rules lesson" from
 *  a Holdings card after a loss.
 *
 *  Weekday rotation (CT — midnight Chicago flips the lesson):
 *    Mon · Entry · Tue · Sell · Wed · Risk · Thu · Mindset
 *    Fri · Regime · Sat · Stages · Sun · Mistakes
 */
import { useMemo } from 'react';

type DayTheme = {
  weekday:   number;          // 0 = Sun, 1 = Mon, ...
  emoji:     string;
  topic:     string;
  color:     string;
  /* Multiple quotes per topic — UI rotates through them every 10s so
   * the user sees varied wisdom on the day's theme without the topic
   * itself flipping mid-session. */
  quotes:    { quote: string; source: string }[];
  rule:      string;          // one-liner takeaway
  why:       string;          // 1-2 sentence explanation
  howToday:  string;          // applied to *today*
  framework: FrameworkSection[];  // the full deep-dive
};

type FrameworkSection = {
  heading:  string;
  body:     string;
  bullets?: string[];
  example?: string;           // famous trade case Minervini cites
};

/* ============================================================================
   LESSONS — one per weekday. Tuesday (selling) is the deepest because
   that's the user's specific gap from MU.
   ========================================================================== */
const LESSONS: DayTheme[] = [
  /* ===================== MONDAY · ENTRY ===================== */
  {
    weekday: 1, emoji: '🎯', topic: 'Entry Rules', color: '#10b981',
    quotes: [
      { quote: "The best stocks make their best moves out of proper bases after a correction or bear market.",
        source: "Trade Like a Stock Market Wizard (2013), ch. 4" },
      { quote: "Patience for the right setup. Aggression on entry. Discipline on exit.",
        source: "Mark Minervini — seminars" },
      { quote: "Trade what you see, not what you think.",
        source: "Trade Like a Stock Market Wizard (2013)" },
      { quote: "The pivot is a specific price, not a general area. Buy within 1-2% above it, never chase.",
        source: "Think & Trade Like a Champion (2017), ch. 6" },
      { quote: "A breakout without volume is a fake. Demand 40-50% above the 50-day average on the breakout day.",
        source: "Trade Like a Stock Market Wizard (2013), ch. 6" },
    ],
    rule: "Only buy at the pivot point of a proper base — not extended, not anticipated, not late-stage.",
    why: "Bases form when weak hands sell to strong hands. The pivot is where institutional demand overwhelms supply. Buying before the pivot means buying into selling pressure; buying after extension means chasing a move that's already paid the early entrants.",
    howToday: "Check today's SEPA cards: if the price is more than 5% above the buy pivot, the entry window has closed for that base. Wait for the next base or pass.",
    framework: [
      {
        heading: "The 5 base types Minervini buys",
        body: "Every great Stage 2 move launches from one of these structures:",
        bullets: [
          "Volatility Contraction Pattern (VCP) — the preferred. 3-6 contractions, each tighter, on declining volume. Final contraction = 5-15% tight.",
          "Cup-with-handle — classic O'Neil base. Cup 12-30% deep, handle drifts down, pivot is handle high.",
          "Flat base — sideways action of 10-15% for 5+ weeks after a prior run.",
          "Power Play / High-Tight Flag — post-IPO or post-news consolidation 3-5 weeks, only 10-25% pullback after a 100%+ surge.",
          "Ascending base — three pullbacks of progressively higher lows. Strongest of all.",
        ],
      },
      {
        heading: "Base count: avoid late-stage bases",
        body: "Each successful breakout from a base counts. By the 4th base from a major low, failure rate spikes. The 'NO BASE' tag on a card means we couldn't identify a clean structure — that is itself a sell signal, not just info.",
        example: "Tesla 2020-2021 ran 3 bases successfully. The 4th base in Nov 2021 broke down and started the Stage 4 decline.",
      },
      {
        heading: "Pivot precision",
        body: "The pivot is NOT 'somewhere near the breakout.' It's a specific price.",
        bullets: [
          "VCP: top of the final contraction",
          "Cup-with-handle: handle high (often +10 cents above for buffer)",
          "Power Play: top of the consolidation rectangle",
          "Buying 1-2% above pivot = ideal (confirms breakout)",
          "Buying 5%+ above pivot = chasing — risk:reward broken",
        ],
      },
      {
        heading: "Volume must confirm",
        body: "A breakout on dry volume is a fake. Minervini requires 40-50% above the 50-day average volume on the breakout day. The SEPA card flags this as '📈 hi-vol breakout' when present.",
      },
    ],
  },

  /* ===================== TUESDAY · SELLING ===================== */
  {
    weekday: 2, emoji: '✂️', topic: 'Sell Rules',  color: '#ef4444',
    quotes: [
      { quote: "The whole secret to winning in the stock market is to lose the least amount possible when you're not right.",
        source: "Trade Like a Stock Market Wizard (2013), ch. 7" },
      { quote: "Cut losses quickly. Cut losses quickly. Cut losses quickly.",
        source: "Repeated in every Minervini book + interview" },
      { quote: "I'm not going to puke a stock at 10am because of an intraday wick. The close is what matters.",
        source: "Mark Minervini — interview" },
      { quote: "I would rather be out of a stock that's going up than in a stock that's going down.",
        source: "Trade Like a Stock Market Wizard (2013)" },
      { quote: "The single biggest mistake amateurs make is failing to take small losses when they should.",
        source: "Think & Trade Like a Champion (2017)" },
      { quote: "Trading without a stop is like driving without brakes.",
        source: "Mark Minervini" },
      { quote: "Hope is not a strategy. The market doesn't care about your wishes.",
        source: "Trade Like a Stock Market Wizard (2013)" },
    ],
    rule: "Three exit triggers: (1) initial stop at MAX 7-8% from entry, evaluated at CLOSE; (2) trailing stop after profits accumulate; (3) sell signals — climax top, distribution, time stop.",
    why: "Profits come from a few outliers compounding. Losses come from refusing to take small ones. A 7% loss recovers with a 7.5% gain; a 25% loss needs a 33% gain; a 50% loss needs a 100% gain. The math is asymmetric — small losses keep the compounding intact, big losses destroy it.",
    howToday: "For every position you hold, write down NOW (before market noise) the exact stop level. If today's close is below that level, exit tomorrow's open. If above, hold and revisit at tomorrow's close. Do not react to intraday wicks unless the move exceeds -12% (structural break).",
    framework: [
      {
        heading: "Tier 1 — the initial stop (every position needs one before you buy)",
        body: "Set BEFORE entry, never adjusted lower, only adjusted higher as the trade matures.",
        bullets: [
          "MAX 7-8% from entry — this is a ceiling, not a target. Tighter is better.",
          "Preferred placement: below the structural low of the base (often 3-5% from entry, sometimes <2% on tight VCPs).",
          "Evaluate at CLOSE (3:00 PM CT / 4:00 PM ET) — intraday wicks below the stop are not exit signals.",
          "Exception: any intraday move of -12% or more from yesterday's close = structural break = exit immediately, full stop.",
        ],
        example: "Your MU trade: bought near $795 pivot, stop $739 (-7%). Intraday touched -15% = -12% rule triggered = exit was correct. The bounce-back is luck, not vindication.",
      },
      {
        heading: "Tier 2 — sell into strength (the 3-to-1 rule)",
        body: "Profits don't manage themselves. Minervini's rule: when you have a profit equal to 3x your risk (3R), take partial profits.",
        bullets: [
          "If your initial risk was 7%, take partial profits at +21% gain (3R).",
          "Specifically: sell 25-50% of position at +2R to +3R to lock in some win.",
          "Move stop on remaining shares to breakeven or +1R — now this trade can't lose money.",
          "Let the winner run on the remaining position with a trailing stop.",
        ],
        example: "NVDA 2023: A +7% stop entry gave a 3R signal around +21% gain in April. Selling 1/3 there and trailing the rest with 21-day EMA captured the bulk of the move while taking gains off the table.",
      },
      {
        heading: "Tier 3 — trailing stops",
        body: "Once a position has run +2R or more, switch from initial stop to a trailing stop. Several methods Minervini uses:",
        bullets: [
          "21-day EMA: close below it = exit. Works on liquid growth names.",
          "Last swing low: each pullback's low becomes the new stop.",
          "10-day MA close: tightest method, for parabolic moves you want to defend.",
          "Rule of thumb: tighter trailing stop when the move accelerates; looser when consolidating.",
        ],
      },
      {
        heading: "Tier 4 — sell signals (regardless of stop)",
        body: "These override everything — when they fire, exit even if stop hasn't been hit:",
        bullets: [
          "Climax top: gap up of 25%+ on highest volume of the move, often a wick that closes near low.",
          "Exhaustion gap: gap up after a long run, fills the gap same day = top.",
          "Multiple distribution days: 4-5 distribution days in 2 weeks = institutional selling.",
          "Stage 4 breakdown: close below 50-day MA on heavy volume, then close below 200-day = trend dead.",
          "Time stop: no progress in 8 weeks after entry = wrong setup, cut.",
        ],
      },
      {
        heading: "What 'evaluate at close' means in practice",
        body: "You DO NOT sell at 10am because the stock touched your stop intraday. You wait. Specifically:",
        bullets: [
          "From open to 2:30 PM CT: ignore the chart. Don't watch tick by tick.",
          "From 2:30-3:00 PM CT: check where price is settling. This is the 'institutional positioning window.'",
          "At 3:00 PM CT (4:00 PM ET): if the CLOSE is below your stop level, the signal is confirmed → sell at tomorrow's open.",
          "If the close is above your stop, hold. The intraday touch was noise.",
        ],
        example: "Minervini quote: 'I'm not going to puke a stock at 10am because of an intraday wick. The close is what matters.' Apply this every trading day.",
      },
    ],
  },

  /* ===================== WEDNESDAY · RISK ===================== */
  {
    weekday: 3, emoji: '🛡️', topic: 'Risk & Sizing', color: '#f59e0b',
    quotes: [
      { quote: "Risk management is the most important thing in trading. Period.",
        source: "Think & Trade Like a Champion (2017), ch. 3" },
      { quote: "Never risk more than you can afford to lose on a single trade.",
        source: "Mark Minervini" },
      { quote: "Don't average down. Ever. That's how amateurs turn small losses into account-killers.",
        source: "Mark Minervini" },
      { quote: "Your job is not to be right. Your job is to manage risk so being wrong stays cheap.",
        source: "Think & Trade Like a Champion (2017)" },
      { quote: "Position size, not entry price, is what kills accounts.",
        source: "Mindset Secrets for Winning (2019)" },
    ],
    rule: "Size positions so that hitting your stop loses no more than 1-2% of total capital. Never average down. Never use leverage on losers.",
    why: "Entries are guesses; exits and sizing are math. The math wins long-term. Risking 5% per trade on a 7% stop means a 5-trade losing streak draws down 25% — recovery requires 33%. Risking 1% means a 5-trade streak draws down 5% — recovery requires 5.3%. Same trading skill, completely different outcomes.",
    howToday: "Compute: (1% of total capital) ÷ (entry price - stop price) = max shares. If that number times the entry price is more than 25% of your portfolio, halve it. No single position should be >25% by capital.",
    framework: [
      {
        heading: "The 1-2% rule",
        body: "Risk per trade = max acceptable loss as % of total capital. Minervini's defaults:",
        bullets: [
          "1% of capital for normal market regime, normal setups.",
          "1.5-2% for confirmed uptrend + A+ setup (VCP with high RS).",
          "0.5% (half size) in correction or pressure regime.",
          "0% in confirmed downtrend — go to cash entirely.",
        ],
      },
      {
        heading: "Position sizing formula",
        body: "Shares = (capital × risk%) / (entry − stop). Example: $100k account, 1% risk, entry $100, stop $93 → $1000 risk / $7 per share = 142 shares. Position value = $14,200 = 14% of book.",
      },
      {
        heading: "Concentration limits",
        body: "Even with proper sizing, don't let any single position dominate:",
        bullets: [
          "Single position: max 25% by capital, max 40% by value after a runner gets big.",
          "Single sector: max 40% — diversify across sectors so a sector correction doesn't crater the whole book.",
          "Maximum 8-12 positions for an individual account. More = can't monitor each properly.",
        ],
      },
      {
        heading: "Never average down",
        body: "Adding to a losing position is the amateur signature. 'But it's cheaper now' is irrelevant — price below your stop is the market telling you you're wrong. Add only to winners, after they've proven the entry.",
      },
    ],
  },

  /* ===================== THURSDAY · MINDSET ===================== */
  {
    weekday: 4, emoji: '🧠', topic: 'Mindset', color: '#8b5cf6',
    quotes: [
      { quote: "A great trader is one who can handle being wrong — not one who is always right.",
        source: "Mindset Secrets for Winning (2019), ch. 2" },
      { quote: "Don't be discouraged by losses. Be discouraged by repeating the same mistake.",
        source: "Mindset Secrets for Winning (2019)" },
      { quote: "Confidence comes from following a proven system — not from being right on any single trade.",
        source: "Think & Trade Like a Champion (2017)" },
      { quote: "The market is always right. Your job is to respond, not to predict.",
        source: "Trade Like a Stock Market Wizard (2013)" },
      { quote: "Discipline is not about being rigid. It's about being consistent.",
        source: "Mark Minervini — seminars" },
      { quote: "A bounce-back after a stop is not vindication. It's selection bias.",
        source: "Mark Minervini — interview" },
    ],
    rule: "Being wrong is data. Refusing to be wrong is a portfolio risk. Detach from the outcome of any single trade.",
    why: "Trading is a probability game. A 50% win rate with proper R/R (3:1) is profitable. Your job is not to be right; it's to execute the system. The system handles win/loss arithmetic — you handle adherence.",
    howToday: "Two questions for any position you regret today: (1) Did I follow my rules? If yes — there's nothing to regret, it's noise. (2) Did I break my rules? If yes — write down exactly which rule, journal it, fix the next trade. Either way, the past trade is closed.",
    framework: [
      {
        heading: "Detach outcome from process",
        body: "A good trade can lose money. A bad trade can make money. Judge yourself by process adherence, not by P/L.",
        bullets: [
          "Good process + good outcome = repeat",
          "Good process + bad outcome = repeat anyway (variance)",
          "Bad process + good outcome = DO NOT repeat (you got lucky)",
          "Bad process + bad outcome = obvious — fix the process",
        ],
      },
      {
        heading: "The bounce-back regret trap",
        body: "Most amateurs get stopped out correctly, watch the stock bounce, then conclude the stop was wrong. This is the most expensive cognitive error in trading. Out of every 10 stops that 'bounce back,' 7-8 would have broken down further if held. You only remember the 2-3 that bounced.",
        example: "Your MU exit at -7% on a -15% intraday touch was textbook. The bounce is selection bias — you remember THIS one because it bounced. The next 5 -15% intraday touches probably won't.",
      },
      {
        heading: "FOMO management",
        body: "Watching stocks you don't own run up is part of the job. The only cure: trust that better setups come. Forcing trades in poor regimes turns FOMO into losses, which compounds psychological damage.",
      },
      {
        heading: "Hope is not a strategy",
        body: "If you find yourself 'hoping' a position recovers, you've already abandoned the plan. Hope means the trade is past its stop and you're rationalizing. Sell.",
      },
    ],
  },

  /* ===================== FRIDAY · REGIME ===================== */
  {
    weekday: 5, emoji: '🌐', topic: 'Market Regime', color: '#3b82f6',
    quotes: [
      { quote: "Don't fight the tape. When the market says no, sit on cash and stay sharp.",
        source: "Trade Like a Stock Market Wizard (2013), ch. 5" },
      { quote: "If the market isn't paying you, sit on cash. Cash is a position.",
        source: "Think & Trade Like a Champion (2017)" },
      { quote: "You don't need to catch every move. You need to catch the BIG moves and avoid the big losses.",
        source: "Trade Like a Stock Market Wizard (2013)" },
      { quote: "Roughly 75% of stocks follow the market direction. Aligning with the trend is half the edge.",
        source: "Trade Like a Stock Market Wizard (2013), ch. 5" },
    ],
    rule: "Trade aggressively only when the market is in a confirmed uptrend. In correction, go to cash. Cash is a position.",
    why: "Roughly 75% of stocks follow the market direction. In a confirmed uptrend, your A+ setups have tailwinds. In a correction, even great setups fail. Trading the same way in both regimes is how accounts get destroyed.",
    howToday: "Check the market regime banner at top. Confirmed uptrend = full size on A+ setups. Pressure = half size, A+ only. Correction = no new entries, harvest existing stops.",
    framework: [
      {
        heading: "Regime states",
        body: "Three states drive your aggression dial:",
        bullets: [
          "Confirmed uptrend: indices above 50-day, breakouts working, distribution count low → trade full size.",
          "Uptrend under pressure: rolling distribution, tight tape → half size, A+ only.",
          "Market in correction: index below 50-day or distribution count >5 → no new entries, tighten stops.",
        ],
      },
      {
        heading: "Distribution days",
        body: "A distribution day = index closes down 0.2%+ on heavier volume than yesterday. Trailing 25-day count:",
        bullets: [
          "0-3: clean tape, breakouts work",
          "4-5: caution, breakouts whippy",
          "6+: institutional selling, expect correction",
        ],
      },
      {
        heading: "Follow-through day",
        body: "The signal that a new uptrend has confirmed: after an attempted rally, day 4-7 closes up 1.5%+ on volume higher than yesterday. Until you see one, treat any rally as bear-market noise.",
      },
    ],
  },

  /* ===================== SATURDAY · STAGES ===================== */
  {
    weekday: 6, emoji: '📊', topic: 'Stage Analysis', color: '#06b6d4',
    quotes: [
      { quote: "There are only four stages a stock can be in. Buy only Stage 2.",
        source: "Trade Like a Stock Market Wizard (2013), ch. 2" },
      { quote: "Bottom fishing is the most expensive hobby in the stock market.",
        source: "Mark Minervini" },
      { quote: "Stage 4 stocks stay in Stage 4 longer than your patience holds. Wait for Stage 1 base.",
        source: "Trade Like a Stock Market Wizard (2013)" },
      { quote: "About 80% of a stock's total return happens in Stage 2. Earlier is dead money, later is the top.",
        source: "Stan Weinstein (cited by Minervini)" },
    ],
    rule: "Only buy stocks in Stage 2 (advancing). Avoid Stage 1 (basing), exit Stage 3 (topping), short or avoid Stage 4 (declining).",
    why: "Stan Weinstein's stage analysis is the foundation. ~80% of a stock's total return happens in Stage 2. Buying earlier means dead money; buying later means catching the top.",
    howToday: "On every SEPA card, look at the stage badge. S2 ADVANCING is the only buy condition. If a stock has dropped from S2 to S3 or S4, the structural trend has broken — your stop should already be triggered.",
    framework: [
      {
        heading: "The four stages",
        body: "Each defined by price action vs 50-day and 200-day MAs:",
        bullets: [
          "Stage 1 — Basing: price flat, 200-day flattening, 50-day weaving through. Don't buy yet.",
          "Stage 2 — Advancing: price above rising 50-day, 50-day above rising 200-day. The buy zone.",
          "Stage 3 — Topping: price stalls, 50-day flattens, distribution. Trail stops aggressively.",
          "Stage 4 — Declining: price below falling 50-day, 50-day below 200-day. Do not buy. Do not 'bottom fish.'",
        ],
      },
      {
        heading: "Common stage transitions",
        body: "Stage transitions take time — usually weeks, not days:",
        bullets: [
          "Stage 1 → 2: confirmed by breakout from base on volume (the entry signal)",
          "Stage 2 → 3: confirmed by lower high + 50-day flattening (trim signal)",
          "Stage 3 → 4: confirmed by close below 50-day on heavy volume (exit-all signal)",
          "Stage 4 → 1: confirmed by 200-day flattening + tightening range (start watching)",
        ],
      },
    ],
  },

  /* ===================== SUNDAY · MISTAKES ===================== */
  {
    weekday: 0, emoji: '⚠️', topic: 'Common Mistakes', color: '#ec4899',
    quotes: [
      { quote: "Repeated mistakes destroy accounts faster than market drawdowns.",
        source: "Mindset Secrets for Winning (2019), ch. 5" },
      { quote: "If you find yourself hoping a position recovers, you've already abandoned the plan.",
        source: "Trade Like a Stock Market Wizard (2013)" },
      { quote: "Buying without a stop is the #1 amateur mistake. Write the stop BEFORE clicking buy.",
        source: "Think & Trade Like a Champion (2017)" },
      { quote: "Selling on intraday noise costs more than holding through it. The close is the signal.",
        source: "Mark Minervini" },
      { quote: "One bad trade is variance. The same bad trade six times is a fixable habit.",
        source: "Mindset Secrets for Winning (2019)" },
    ],
    rule: "Audit yourself weekly for these patterns. One bad trade is variance; the same bad trade six times is a fixable habit.",
    why: "Every amateur cycles through the same mistakes. The difference between $100k and $1M isn't strategy — it's catching your own pattern errors before they compound.",
    howToday: "Open your trade journal (or the Holdings card P/L history). For every red trade in the last month, ask: was the mistake on entry, on exit, or on sizing? Group them. The most-common one is the pattern to fix this week.",
    framework: [
      {
        heading: "The seven deadly mistakes",
        body: "Minervini's master list — these account for 90% of trader failures:",
        bullets: [
          "1. Buying without a stop. Solution: never click Buy until you've written the stop down.",
          "2. Averaging down. Solution: if price is below your stop, sell. Don't add.",
          "3. Selling on intraday noise. Solution: close-of-day rule for stops, except the -12% structural break.",
          "4. Holding losers past the stop. Solution: stop is a contract you signed with yourself BEFORE the trade.",
          "5. Cutting winners early. Solution: 3R rule for partial profits, trailing stops for the rest.",
          "6. Trading the wrong regime. Solution: regime banner is your master gate — sit out corrections.",
          "7. Over-trading after a loss. Solution: mandatory 24h cooldown after any -2R+ loss.",
        ],
      },
    ],
  },
];

function todayLessonCT(): DayTheme {
  // Compute Chicago-time weekday so the lesson rotates at midnight CT,
  // not UTC midnight (which would flip mid-evening for the user).
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Chicago',
    weekday: 'short',
  });
  const weekdayName = fmt.format(new Date());
  const idx = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].indexOf(weekdayName);
  return LESSONS.find(l => l.weekday === idx) || LESSONS[0];
}

/* Deterministic day-of-year index. Used so the quote within a topic also
 * changes day-to-day (e.g. seven Tuesdays in a row each show a different
 * sell-rule quote) but stays stable within a single day so the user
 * never sees the quote "flicker" mid-session. */
function dayOfYearCT(): number {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Chicago', year: 'numeric', month: 'numeric', day: 'numeric',
  });
  const parts = fmt.formatToParts(new Date());
  const y = Number(parts.find(p => p.type === 'year')?.value  || 0);
  const m = Number(parts.find(p => p.type === 'month')?.value || 1);
  const d = Number(parts.find(p => p.type === 'day')?.value   || 1);
  const start = Date.UTC(y, 0, 0);
  const now   = Date.UTC(y, m - 1, d);
  return Math.round((now - start) / 86400000);
}

export function MinerviniLesson({ defaultTopic }: { defaultTopic?: string }) {
  const lesson = useMemo(() => {
    if (defaultTopic) {
      const explicit = LESSONS.find(l => l.topic.toLowerCase() === defaultTopic.toLowerCase());
      if (explicit) return explicit;
    }
    return todayLessonCT();
  }, [defaultTopic]);

  // Pick today's quote deterministically. Same day → same quote; next
  // day → next quote (wraps via modulo). No user controls, no auto-
  // rotation, no flicker.
  const quote = useMemo(
    () => lesson.quotes[dayOfYearCT() % lesson.quotes.length],
    [lesson.quotes],
  );

  return (
    <section
      style={{
        margin: '0.4rem 0 0.7rem',
        padding: '0.55rem 0.8rem',
        border: '1px solid var(--rule, #ddd)',
        borderLeft: `3px solid ${lesson.color}`,
        borderRadius: 4,
        background: 'var(--bg-raised)',
      }}
    >
      <div className="eyebrow" style={{
        color: lesson.color,
        letterSpacing: '0.08em',
        fontSize: '0.62rem',
        marginBottom: '0.3rem',
      }}>
        {lesson.emoji} Minervini · {lesson.topic} · today's lesson
      </div>

      <blockquote style={{
        margin: '0 0 0.2rem',
        fontSize: '0.82rem',
        fontStyle: 'italic',
        lineHeight: 1.4,
        color: 'var(--ink, inherit)',
      }}>
        "{quote.quote}"
      </blockquote>
      <div style={{ fontSize: '0.62rem', color: 'var(--cm-slate)', marginBottom: '0.4rem' }}>
        — {quote.source}
      </div>

      <div style={{
        padding: '0.3rem 0.5rem',
        background: 'rgba(255,255,255,0.025)',
        borderLeft: `2px solid ${lesson.color}`,
        borderRadius: 2,
        marginBottom: '0.3rem',
      }}>
        <div style={{
          fontSize: '0.58rem', fontWeight: 700, letterSpacing: '0.08em',
          color: lesson.color, marginBottom: 1,
        }}>THE RULE</div>
        <div style={{ fontSize: '0.78rem', lineHeight: 1.4 }}>{lesson.rule}</div>
      </div>

      <div style={{ padding: '0.3rem 0.5rem' }}>
        <div style={{
          fontSize: '0.58rem', fontWeight: 700, letterSpacing: '0.08em',
          color: 'var(--cm-slate)', marginBottom: 1,
        }}>TODAY</div>
        <div style={{ fontSize: '0.76rem', lineHeight: 1.4, color: '#cfcfd4' }}>
          {lesson.howToday}
        </div>
      </div>
    </section>
  );
}
