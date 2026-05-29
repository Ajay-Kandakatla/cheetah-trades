/* SignalDrillModal — generic drill-in for SEPA card signal chips.
 *
 *  Used when the user taps a chip ("🚀 hi-vol breakout", "🪙 Pocket pivot",
 *  "💪 Strong accum", etc.) on a SEPA candidate card. The modal explains:
 *
 *    1. What the signal measures (formula)
 *    2. THIS ticker's actual numbers for the signal (grounded data)
 *    3. Minervini's framework — when to act on it
 *    4. Common pitfalls / fake-positive failure modes
 *    5. Where the data comes from (backend reference)
 *
 *  The map of signal kinds → spec lives at module scope so adding
 *  another clickable chip is a one-entry edit, not a new component.
 *
 *  Pattern matches the existing WhalesFlowModal / MacroContextModal /
 *  ChatterMomentumDrillModal — close on Escape, click-outside, portal
 *  to escape any parent overflow:hidden.
 */
import { useEffect } from 'react';
import { createPortal } from 'react-dom';

export type SignalKind =
  // Volume signals (originally added)
  | 'hi_vol_breakout'
  | 'pocket_pivot'
  | 'accum_strong'
  | 'accum_accumulating'
  | 'accum_distributing'
  | 'cmf_outflow'
  | 'cmf_inflow'
  | 'dist_days_warning'
  | 'dual_momentum_12m'
  | 'stage_vol_disagreement'
  | 'rank_trend_history'
  | 'conviction'
  | 'political_disclosure'
  // Score / ranking components (added 2026-05-22 — user asked for
  // ranking transparency: "I want to see why · what actually helped
  // the ranking"). Each kind drills into one piece of the SEPA score.
  | 'score_breakdown'
  | 'trend_template'
  | 'rs_rank'
  | 'stage'
  | 'adr'
  | 'base_count_late'
  | 'base_count_none'
  | 'setup_vcp'
  | 'setup_power_play';

/** Live ticker numbers we ground the explanation in. Optional fields —
 *  the modal degrades gracefully when a metric isn't available for this
 *  particular ticker (older cached scans, missing volume data, etc). */
export type SignalData = {
  symbol:                string;
  // Volume metrics — sepa/volume.py
  last_vol?:             number | null;
  avg_vol_50?:           number | null;
  vol_ratio?:            number | null;   // last_vol / avg_vol_50
  up_down_vol_ratio?:    number | null;
  recent_21d_high?:      number | null;
  last_close?:           number | null;
  // Volume v2 fields
  accumulation_strength?: string | null;
  pocket_pivot_detail?:  {
    today_vol?: number;
    max_down_vol_lookback?: number;
    strength_x?: number | null;
    reason?: string;
  } | null;
  cmf_20?:               number | null;
  distribution_days_25?: number | null;
  accumulation_days_25?: number | null;
  // Score-component fields (added 2026-05-22 for ranking transparency)
  score?:                number | null;
  rating?:               string | null;
  trend_passed?:         number | null;   // 0..8
  trend_checks?:         Record<string, boolean> | null;
  rs_rank?:              number | null;
  stage_num?:            number | null;   // 1..4
  stage_label?:          string | null;
  fundamentals_passed?:  number | null;   // 0..3
  adr_pct?:              number | null;
  base_count_n?:         number | null;
  base_count_is_late?:   boolean | null;
  setup_type?:           string | null;
  setup_pivot?:          number | null;
  setup_stop?:           number | null;
  liquidity_liquid?:     boolean | null;
  // Volume flags relevant to the score-breakdown view
  high_vol_breakout?:    boolean | null;
  pocket_pivot?:         boolean | null;
  cmf_signal?:           string | null;
  // Dollar flows — added 2026-05-29 so drill modals show actual $
  // accumulation instead of just abstract ratios.
  up_dollar_vol_50?:     number | null;   // sum of (close × vol) on up days, 50d
  dn_dollar_vol_50?:     number | null;   // sum of (close × vol) on down days, 50d
  net_dollar_vol_50?:    number | null;   // up_dollar - dn_dollar
  cmf_dollar_flow_20?:   number | null;   // CMF money-flow-volume × close, summed 20d
  // Dual momentum (Antonacci) — drives the dual_momentum_12m spec.
  // Each return is a percentage (e.g. 178.1 means +178.1%).
  return_1m?:            number | null;
  return_3m?:            number | null;
  return_6m?:            number | null;
  return_12m?:           number | null;
  abs_mom_pass?:         boolean | null;
  beats_spy?:            boolean | null;
  // Stage classifier volume-disagreement (added 2026-05-28). When MA
  // geometry says Stage 2 but volume tape disagrees, stage.classify()
  // downgrades to Stage 3 and includes a reason string. Surfaced in
  // the stage_vol_disagreement drill modal so the user can see exactly
  // which volume condition (distributing accumulation, CMF outflow)
  // triggered the downgrade.
  stage_volume_reason?:  string | null;
  // Rank-trend trajectory — full timeline of (date, score, rank) over
  // the last 30 days. Built by SepaCandidateCard from the symbol-history
  // API (/sepa/history/{symbol}?days=30). Empty array when the symbol
  // has no prior snapshots (new entrant). Powers the rank_trend_history
  // drill chart.
  trend_history?:        Array<{
    date_et:   string;
    generated_at: number;
    score:     number | null;
    rank:      number | null;
    stage_label?: string | null;
  }> | null;
  /** Date string for the "yesterday" anchor on the trend chart. */
  trend_yesterday_date?: string | null;
  /** Date string for the "~5 trading days ago" anchor. */
  trend_week_ago_date?:  string | null;
  // Conviction (Whales + Volume composite) — feeds the conviction drill.
  // Computed in SepaConvictionChip; passed verbatim so the modal renders
  // the same numbers the chip-tooltip shows.
  conviction_tier?:        string | null;     // ConvictionTier value
  conviction_label?:       string | null;
  conviction_combined?:    number | null;
  conviction_whale_score?: number | null;
  conviction_vol_score?:   number | null;
  conviction_whale_reason?: string | null;
  conviction_vol_reason?:   string | null;
  conviction_summary?:     string | null;
  conviction_disagrees?:   boolean | null;
  // Political-disclosure context for the political_disclosure drill —
  // passed from SepaCandidateCard, looked up from politicalDisclosures.ts.
  political_categories?:   string[] | null;
  political_band?:         string | null;
  political_company?:      string | null;
  political_sector?:       string | null;
  political_notes?:        string | null;
  political_is_inferred?:  boolean | null;
};

type Field = { label: string; value: string; tone?: 'good' | 'bad' | 'neutral' };
type Pitfall = { title: string; body: string };
type SignalSpec = {
  emoji:    string;
  title:    string;
  oneLine:  string;
  formula:  string;
  buildFields: (data: SignalData) => Field[];
  framework: string[];
  pitfalls:  Pitfall[];
  source:    string;
};


function fmtVol(n: number | null | undefined): string {
  if (n == null) return '—';
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return Math.round(n).toLocaleString();
}

// Signed dollar formatter — e.g. +$1.2B, −$340M. Used by the volume +
// CMF drill modals to display actual dollar flow numbers added 2026-05-29.
function fmtSignedUSD(n: number | null | undefined): string {
  if (n == null || !isFinite(n)) return '—';
  const sign = n >= 0 ? '+' : '−';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${Math.round(abs).toLocaleString()}`;
}

/* ============================================================================
 * Score weights — MUST mirror backend/sepa/scanner.py SCORE_WEIGHTS.
 * If these drift, the breakdown view will misreport contributions.
 * The backend is the source of truth; this is a frontend recompute.
 * ============================================================================ */
const WEIGHTS = {
  trend_template: 30,
  rs_rank:        25,
  stage_2:        10,
  setup:          15,
  fundamentals:   10,
  volume:          5,
  liquidity_adr:   5,
};

/** Decompose the final score into per-component contributions.
 *  Returns components in display order — first row is the biggest
 *  weight, last row is the smallest. Returns NUMBER (signed) for
 *  each component so penalties (late base) show as negative. */
export type ScoreComponent = {
  label:   string;
  weight:  number;          // max possible
  earned:  number;          // signed actual contribution
  detail:  string;          // why this number
};

export function computeScoreBreakdown(d: SignalData): ScoreComponent[] {
  const out: ScoreComponent[] = [];

  // Trend template — 30 × (passed / 8)
  const passed = d.trend_passed ?? 0;
  out.push({
    label:  'Trend Template',
    weight: WEIGHTS.trend_template,
    earned: WEIGHTS.trend_template * (passed / 8),
    detail: `passed ${passed} of 8 Minervini price/MA gates`,
  });

  // RS rank — 25 × (rs / 99), but ONLY counts if rs >= 70
  const rs = d.rs_rank ?? 0;
  out.push({
    label:  'Relative Strength',
    weight: WEIGHTS.rs_rank,
    earned: rs >= 70 ? WEIGHTS.rs_rank * (Math.min(rs, 99) / 99) : 0,
    detail: rs >= 70
      ? `RS ${rs} → ${(WEIGHTS.rs_rank * (Math.min(rs, 99) / 99)).toFixed(1)} pts (gate ≥70 passed)`
      : `RS ${rs} below the ≥70 gate → 0 pts`,
  });

  // Stage 2 — flat 10
  const stg = d.stage_num;
  out.push({
    label:  'Stage 2 Advancing',
    weight: WEIGHTS.stage_2,
    earned: stg === 2 ? WEIGHTS.stage_2 : 0,
    detail: stg === 2 ? 'In Stage 2 — full credit' :
            stg ? `Stage ${stg} — no Stage-2 credit` :
            'no stage detected',
  });

  // Setup — VCP = 15, Power Play = 15 × 0.85 = 12.75
  const setupType = (d.setup_type || '').toUpperCase().replace(/_/g, '');
  let setupEarned = 0;
  let setupDetail = 'no VCP or Power Play setup detected';
  if (setupType === 'VCP') {
    setupEarned = WEIGHTS.setup;
    setupDetail = 'VCP base detected — full 15 pts';
  } else if (setupType === 'POWERPLAY') {
    setupEarned = WEIGHTS.setup * 0.85;
    setupDetail = 'Power Play setup — 85% of base credit';
  }
  out.push({
    label:  'Base / Setup',
    weight: WEIGHTS.setup,
    earned: setupEarned,
    detail: setupDetail,
  });

  // Fundamentals — 10 × (passed / 3)
  const fp = d.fundamentals_passed ?? 0;
  out.push({
    label:  'Fundamentals (CANSLIM)',
    weight: WEIGHTS.fundamentals,
    earned: WEIGHTS.fundamentals * (fp / 3),
    detail: `passed ${fp}/3 CANSLIM C·A·I gates`,
  });

  // Volume — graded across 4 inputs (strong/pocket-pivot/breakout/cmf)
  let volEarned = 0;
  const volReasons: string[] = [];
  if (d.accumulation_strength === 'strong') {
    volEarned += WEIGHTS.volume * 0.4;
    volReasons.push('strong (+2.0)');
  } else if (d.accumulation_strength === 'accumulating') {
    volEarned += WEIGHTS.volume * 0.2;
    volReasons.push('accumulating (+1.0)');
  } else if (d.accumulation_strength === 'distributing') {
    volEarned -= WEIGHTS.volume * 0.2;
    volReasons.push('distributing (-1.0)');
  }
  if (d.pocket_pivot)       { volEarned += WEIGHTS.volume * 0.2; volReasons.push('pocket pivot (+1.0)'); }
  if (d.high_vol_breakout)  { volEarned += WEIGHTS.volume * 0.2; volReasons.push('hi-vol breakout (+1.0)'); }
  if (d.cmf_signal === 'inflow') { volEarned += WEIGHTS.volume * 0.2; volReasons.push('CMF inflow (+1.0)'); }
  out.push({
    label:  'Volume signals',
    weight: WEIGHTS.volume,
    earned: volEarned,
    detail: volReasons.length ? volReasons.join(' · ') : 'no qualifying volume signals',
  });

  // Liquidity / ADR — 0.4 if liquid + 0.6 if ADR ≥ 4
  let liqEarned = 0;
  const liqBits: string[] = [];
  if (d.liquidity_liquid) {
    liqEarned += WEIGHTS.liquidity_adr * 0.4;
    liqBits.push('liquid (+2.0)');
  }
  if (d.adr_pct != null && d.adr_pct >= 4) {
    liqEarned += WEIGHTS.liquidity_adr * 0.6;
    liqBits.push(`ADR ${d.adr_pct}% ≥4 (+3.0)`);
  } else if (d.adr_pct != null) {
    liqBits.push(`ADR ${d.adr_pct}% < 4 (no bonus)`);
  }
  out.push({
    label:  'Liquidity + ADR',
    weight: WEIGHTS.liquidity_adr,
    earned: liqEarned,
    detail: liqBits.length ? liqBits.join(' · ') : 'no liquidity data',
  });

  // Late-stage base penalty — -8 if late stage
  if (d.base_count_is_late) {
    out.push({
      label:  'Late-base penalty',
      weight: -8,
      earned: -8,
      detail: `base #${d.base_count_n ?? '?'} — failure rate climbs sharply by base 4+`,
    });
  }

  return out;
}


const SIGNAL_SPECS: Record<SignalKind, SignalSpec> = {
  hi_vol_breakout: {
    emoji:   '🚀',
    title:   'High-volume breakout',
    oneLine: "Today's volume ≥ 1.5× the 50-day average AND price closed above the recent 21-day high. Classic Minervini pivot-buy signal.",
    formula: 'breakout = (last_vol > 1.5 × avg_vol_50) AND (close > max(high, last 21 days))',
    buildFields: (d) => {
      const vol_ratio = (d.last_vol && d.avg_vol_50)
        ? (d.last_vol / d.avg_vol_50)
        : null;
      const above_21d = (d.last_close != null && d.recent_21d_high != null)
        ? d.last_close > d.recent_21d_high
        : null;
      const above_pct = (d.last_close != null && d.recent_21d_high && d.recent_21d_high > 0)
        ? ((d.last_close - d.recent_21d_high) / d.recent_21d_high) * 100
        : null;
      return [
        {
          label: "Today's volume",
          value: fmtVol(d.last_vol),
          tone:  'neutral',
        },
        {
          label: '50-day avg volume',
          value: fmtVol(d.avg_vol_50),
          tone:  'neutral',
        },
        {
          label: 'Volume ratio',
          value: vol_ratio != null ? `${vol_ratio.toFixed(2)}× avg` : '—',
          tone:  vol_ratio != null && vol_ratio >= 1.5 ? 'good' : 'neutral',
        },
        {
          label: 'Last close',
          value: d.last_close != null ? `$${d.last_close.toFixed(2)}` : '—',
          tone:  'neutral',
        },
        {
          label: '21-day high',
          value: d.recent_21d_high != null ? `$${d.recent_21d_high.toFixed(2)}` : '—',
          tone:  'neutral',
        },
        {
          label: 'Above pivot?',
          value: above_21d == null ? '—'
                : above_21d ? `YES · +${(above_pct ?? 0).toFixed(2)}% above`
                : 'NO',
          tone:  above_21d ? 'good' : above_21d === false ? 'bad' : 'neutral',
        },
      ];
    },
    framework: [
      "Minervini's pivot-buy rule: enter on the day the stock breaks out of a proper base, on volume ≥ 1.5× average (he prefers 1.7-2.0× when available). Buy within 1-2% above the pivot price — chasing past 5% breaks the risk-to-stop math.",
      "Stop placement: just under the breakout day's LOW. If the breakout day stays the swing low, you're typically risking 5-8% — perfect for the 1% capital risk rule.",
      "Combine with: pocket pivot history (institutional accumulation BEFORE breakout = higher conviction), Stage 2 confirmation (S1 → S2 transition is the cleanest), VCP base or Power Play setup beneath the breakout.",
    ],
    pitfalls: [
      {
        title:   "Breakout from a deep base = often fake",
        body:    "If the prior pullback was >25% deep, the base is 'too deep' — breakouts from these tend to fail within 1-2 weeks. Check vcp.base_depth_pct on the candidate. Under 15% is ideal.",
      },
      {
        title:   "Late-stage base + breakout = climax risk",
        body:    "By the 4th base from a major low, breakouts have a 60% failure rate (Minervini's published data). The LATE BASE #4 badge on the card = treat the breakout with extra caution; tight stop.",
      },
      {
        title:   "Volume from a fund unloading looks like a breakout",
        body:    "1.5× volume can be institutional BUYING or institutional SELLING. The close-above-pivot filter screens out most distribution, but cross-check with CMF 20-day. If CMF is negative the same day, the move is suspect.",
      },
      {
        title:   "Gap-up breakouts have different rules",
        body:    "If the breakout is a gap-up (today's open > yesterday's close × 1.03), Minervini's PEG framework applies, not the standard pivot rule. See the PEG setup on /setups for the gap-day-high entry trigger.",
      },
    ],
    source: 'backend/sepa/volume.py · analyze() · high_vol_breakout',
  },

  pocket_pivot: {
    emoji:   '🪙',
    title:   'Pocket pivot',
    oneLine: "Today's UP-volume exceeded the MAX down-day volume of the last 10 sessions. Minervini's pre-breakout institutional footprint signal.",
    formula: "pp = (today.close > prior.close) AND (today.volume > max(down_day_volumes, last 10 sessions))",
    buildFields: (d) => {
      const pp = d.pocket_pivot_detail || {};
      return [
        { label: "Today's up-volume",  value: fmtVol(pp.today_vol),               tone: 'neutral' },
        { label: "Max down-day vol (10d)", value: fmtVol(pp.max_down_vol_lookback), tone: 'neutral' },
        { label: 'Strength',            value: pp.strength_x != null ? `${pp.strength_x}× max down-vol` : '—',
                                         tone: pp.strength_x && pp.strength_x >= 1.3 ? 'good' : 'neutral' },
        { label: 'Notes',               value: pp.reason || '—', tone: 'neutral' },
      ];
    },
    framework: [
      "From 'Trade Like a Stock Market Wizard' Ch.8. The pocket pivot fires 1-5 days BEFORE the textbook breakout — it's the institutional footprint that precedes the confirmed move.",
      "Use as a SUB-BASE BUY: enter a partial position when the pocket pivot fires within a constructive base (VCP or Power Play forming). Add on the confirmed breakout.",
      "Best when: the stock has been consolidating, volume drying up, then ONE day where up-volume spikes past anything the sellers did in the prior 2 weeks. That's institutions starting to accumulate.",
    ],
    pitfalls: [
      {
        title:   "Pocket pivot in Stage 3 / late base = trap",
        body:    "Pocket pivots only work in Stage 1→2 transitions or early Stage 2 advances. By Stage 3, they're often a single mutual fund rebalancing — not initiation of a position.",
      },
      {
        title:   "No down-days in the lookback = trivially true",
        body:    "If the stock has been ripping with no down-days, the 'max down-day volume' = 0 and any up-day technically qualifies. The chip still fires but the signal is weak. Check the detail panel — if 'reason' says 'no down-days in lookback', treat as confirmation of strength, not a fresh institutional buy.",
      },
    ],
    source: 'backend/sepa/volume.py · _pocket_pivot()',
  },

  accum_strong: {
    emoji:   '💪',
    title:   'Strong accumulation',
    oneLine: "All three confirmations align: up/down ratio ≥ 1.5, CMF inflow, ≤ 1 distribution day in 25.",
    formula: "strong = (up_down_vol_ratio ≥ 1.5) AND (cmf_20 ≥ 0.10) AND (distribution_days_25 ≤ 1)",
    buildFields: (d) => [
      { label: 'Up/down vol ratio (50d)', value: d.up_down_vol_ratio != null ? `${d.up_down_vol_ratio.toFixed(2)}×` : '—',
                                          tone: d.up_down_vol_ratio && d.up_down_vol_ratio >= 1.5 ? 'good' : 'neutral' },
      { label: 'CMF 20-period',          value: d.cmf_20 != null ? d.cmf_20.toFixed(3) : '—',
                                          tone: d.cmf_20 != null && d.cmf_20 >= 0.10 ? 'good' : 'neutral' },
      { label: 'Distribution days (25)',  value: d.distribution_days_25 != null ? String(d.distribution_days_25) : '—',
                                          tone: d.distribution_days_25 != null && d.distribution_days_25 <= 1 ? 'good' : 'bad' },
      { label: 'Accumulation days (25)',  value: d.accumulation_days_25 != null ? String(d.accumulation_days_25) : '—',
                                          tone: d.accumulation_days_25 != null && d.accumulation_days_25 >= 8 ? 'good' : 'neutral' },
      // Actual dollar amounts — added 2026-05-29 so users see real
      // money flow not just abstract ratios.
      { label: '$ on up days (50d)',       value: `$${fmtVol(d.up_dollar_vol_50)}`,    tone: 'good' },
      { label: '$ on down days (50d)',     value: `$${fmtVol(d.dn_dollar_vol_50)}`,    tone: 'neutral' },
      { label: 'Net $ accumulation (50d)', value: fmtSignedUSD(d.net_dollar_vol_50),
                                           tone: d.net_dollar_vol_50 != null && d.net_dollar_vol_50 > 0 ? 'good' : 'bad' },
    ],
    framework: [
      "Rare — about 5% of the universe trips all three gates. When you see this on a Stage 2 leader with a clean base forming, it's the highest-conviction long setup in the framework.",
      "Pairs with: pocket pivot (pre-breakout institutional footprint), VCP base (tight setup), RS rank ≥ 90 (leadership).",
    ],
    pitfalls: [
      {
        title:   "Strong + extended = late-cycle warning",
        body:    "Strong accumulation that fires on a name already 50%+ above its 200-day MA is often distribution disguised as buying (institutions exiting into retail strength). Watch the distribution-day count — if it ticks up to 3+ over the next 2 weeks, exit.",
      },
    ],
    source: 'backend/sepa/volume.py · _strength_label()',
  },

  accum_accumulating: {
    emoji:   '📈',
    title:   'Accumulating',
    oneLine: "Up/down volume ratio ≥ 1.3 over 50 days. Real institutional bias toward buying — tighter than the old binary ≥1.0 threshold (which tripped 49% of universe).",
    formula: "accumulating = (up_down_vol_ratio ≥ 1.3) AND not (cmf_outflow OR ≥ 4 dist days)",
    buildFields: (d) => [
      { label: 'Up/down vol ratio',      value: d.up_down_vol_ratio != null ? `${d.up_down_vol_ratio.toFixed(2)}×` : '—',
                                          tone: 'good' },
      { label: 'CMF 20-period',           value: d.cmf_20 != null ? d.cmf_20.toFixed(3) : '—',
                                          tone: d.cmf_20 != null && d.cmf_20 >= 0 ? 'good' : 'neutral' },
      { label: 'Distribution days (25)',  value: d.distribution_days_25 != null ? String(d.distribution_days_25) : '—',
                                          tone: d.distribution_days_25 != null && d.distribution_days_25 < 4 ? 'neutral' : 'bad' },
      { label: '$ on up days (50d)',       value: `$${fmtVol(d.up_dollar_vol_50)}`,    tone: 'good' },
      { label: '$ on down days (50d)',     value: `$${fmtVol(d.dn_dollar_vol_50)}`,    tone: 'neutral' },
      { label: 'Net $ accumulation (50d)', value: fmtSignedUSD(d.net_dollar_vol_50),
                                           tone: d.net_dollar_vol_50 != null && d.net_dollar_vol_50 > 0 ? 'good' : 'bad' },
    ],
    framework: [
      "Meaningful but not maxed — the stock is being net-bought but doesn't qualify for 'strong' (needs all three confirmations). About 12% of universe trips this.",
      "Take action: combine with a base setup before entering. Accumulating + VCP = entry; accumulating alone = watchlist.",
    ],
    pitfalls: [
      {
        title:   "Accumulating but extended = wait for pullback",
        body:    "If the stock is already 15%+ above its 50-day MA, the accumulation has already happened and the buy zone has closed. Wait for a pullback to the 21-day EMA before acting on this signal.",
      },
    ],
    source: 'backend/sepa/volume.py · _strength_label()',
  },

  accum_distributing: {
    emoji:   '📉',
    title:   'Distributing',
    oneLine: "Institutional selling. Trips when up/down ratio ≤ 0.7, OR CMF outflow, OR ≥ 4 distribution days in 25.",
    formula: "distributing = (ratio ≤ 0.7) OR (cmf_20 ≤ -0.10) OR (distribution_days_25 ≥ 4)",
    buildFields: (d) => [
      { label: 'Up/down vol ratio',      value: d.up_down_vol_ratio != null ? `${d.up_down_vol_ratio.toFixed(2)}×` : '—',
                                          tone: d.up_down_vol_ratio != null && d.up_down_vol_ratio <= 0.7 ? 'bad' : 'neutral' },
      { label: 'CMF 20-period',           value: d.cmf_20 != null ? d.cmf_20.toFixed(3) : '—',
                                          tone: d.cmf_20 != null && d.cmf_20 <= -0.10 ? 'bad' : 'neutral' },
      { label: 'Distribution days (25)',  value: d.distribution_days_25 != null ? String(d.distribution_days_25) : '—',
                                          tone: d.distribution_days_25 != null && d.distribution_days_25 >= 4 ? 'bad' : 'neutral' },
      { label: '$ on up days (50d)',       value: `$${fmtVol(d.up_dollar_vol_50)}`,    tone: 'neutral' },
      { label: '$ on down days (50d)',     value: `$${fmtVol(d.dn_dollar_vol_50)}`,    tone: 'bad' },
      { label: 'Net $ distribution (50d)', value: fmtSignedUSD(d.net_dollar_vol_50),
                                           tone: d.net_dollar_vol_50 != null && d.net_dollar_vol_50 < 0 ? 'bad' : 'neutral' },
    ],
    framework: [
      "Per Minervini Ch.5: 4-5 distribution days in 25 = institutional selling. Trim or exit. Don't fight the tape on a single ticker showing this signal even if the broader market is rallying.",
      "Action: if you hold this position, TRIM. If you don't, do not enter — even on a 'breakout', the institutional supply is heavier than retail demand.",
    ],
    pitfalls: [
      {
        title:   "Distributing AT the 200-day MA = high-conviction sell",
        body:    "When distribution shows up as price approaches the rising 200-day MA, institutions are exiting in size before the structural support breaks. Stronger sell signal than a random distribution flag.",
      },
    ],
    source: 'backend/sepa/volume.py · _strength_label()',
  },

  cmf_outflow: {
    emoji:   '💸',
    title:   'Money outflow',
    oneLine: "Chaikin Money Flow ≤ -0.10. Independent confirmation of selling that the bare up/down ratio can miss.",
    formula: "CMF = sum(money_flow_volume, 20) / sum(volume, 20); money_flow_volume weights each day by close position within range.",
    buildFields: (d) => [
      { label: 'CMF 20-period', value: d.cmf_20 != null ? d.cmf_20.toFixed(3) : '—', tone: 'bad' },
      { label: 'Net $ outflow (20d, CMF-weighted)',
                                  value: fmtSignedUSD(d.cmf_dollar_flow_20),
                                  tone: d.cmf_dollar_flow_20 != null && d.cmf_dollar_flow_20 < 0 ? 'bad' : 'neutral' },
      { label: 'Up/down vol ratio', value: d.up_down_vol_ratio != null ? `${d.up_down_vol_ratio.toFixed(2)}×` : '—', tone: 'neutral' },
    ],
    framework: [
      "The OGN trap: a stock can have up/down ratio 3.5× (looks bullish) but CMF -0.23 (real outflow). The high ratio comes from low-volume up-days; the close-within-range data tells the real story.",
      "When CMF and up/down ratio disagree, CMF wins. The close-position-weighted-by-volume approach is harder to fake.",
    ],
    pitfalls: [
      {
        title:   "CMF outflow on a fresh breakout = fade the breakout",
        body:    "A hi-vol breakout chip + a money-outflow chip on the same ticker is a 'don't buy' signal. The breakout day printed on volume but closed off its highs — institutions sold into retail enthusiasm.",
      },
    ],
    source: 'backend/sepa/volume.py · _chaikin_money_flow()',
  },

  cmf_inflow: {
    emoji:   '💰',
    title:   'Money inflow',
    oneLine: "Chaikin Money Flow ≥ +0.10. Independent confirmation of buying — closes are skewed toward the highs of the daily range, weighted by volume.",
    formula: "CMF = sum(money_flow_volume, 20) / sum(volume, 20); inflow when CMF ≥ +0.10 sustained.",
    buildFields: (d) => [
      { label: 'CMF 20-period',     value: d.cmf_20 != null ? d.cmf_20.toFixed(3) : '—', tone: 'good' },
      { label: 'Net $ inflow (20d, CMF-weighted)',
                                     value: fmtSignedUSD(d.cmf_dollar_flow_20),
                                     tone: d.cmf_dollar_flow_20 != null && d.cmf_dollar_flow_20 > 0 ? 'good' : 'neutral' },
      { label: 'Up/down vol ratio', value: d.up_down_vol_ratio != null ? `${d.up_down_vol_ratio.toFixed(2)}×` : '—', tone: 'neutral' },
    ],
    framework: [
      "Inflow + accumulation is the cleanest 'institutional support' read. Money flowing in while the up/down ratio is also bullish means the bid is real, not a low-volume bounce.",
      "When CMF inflow disagrees with a weak up/down ratio, trust CMF — close-position-weighted-by-volume is harder to fake than raw volume direction.",
    ],
    pitfalls: [
      {
        title:   "Inflow alone doesn't make it a buy",
        body:    "Inflow is a tape confirmation, not an entry signal. Combine with a setup (VCP / Power Play) + Trend Template + Stage 2 before acting.",
      },
    ],
    source: 'backend/sepa/volume.py · _chaikin_money_flow()',
  },

  dual_momentum_12m: {
    emoji:   '📈',
    title:   '12-month Dual Momentum (Antonacci)',
    oneLine: "Two gates — absolute momentum (12m return > 0) AND relative momentum (12m return beats SPY). Both pass = ✓ Dual Momentum trend confirmation.",
    formula: "absolute_momentum = (return_12m > 0); relative_momentum = (return_12m > spy_return_12m); dual_momentum = absolute_momentum AND relative_momentum",
    buildFields: (d) => [
      { label: '1-month return',  value: d.return_1m  != null ? `${d.return_1m > 0 ? '+' : ''}${d.return_1m.toFixed(1)}%`  : '—', tone: d.return_1m  != null && d.return_1m  > 0 ? 'good' : 'neutral' },
      { label: '3-month return',  value: d.return_3m  != null ? `${d.return_3m > 0 ? '+' : ''}${d.return_3m.toFixed(1)}%`  : '—', tone: d.return_3m  != null && d.return_3m  > 0 ? 'good' : 'neutral' },
      { label: '6-month return',  value: d.return_6m  != null ? `${d.return_6m > 0 ? '+' : ''}${d.return_6m.toFixed(1)}%`  : '—', tone: d.return_6m  != null && d.return_6m  > 0 ? 'good' : 'neutral' },
      { label: '12-month return', value: d.return_12m != null ? `${d.return_12m > 0 ? '+' : ''}${d.return_12m.toFixed(1)}%` : '—', tone: d.return_12m != null && d.return_12m > 0 ? 'good' : 'bad' },
      { label: 'Absolute momentum (12m > 0)', value: d.abs_mom_pass == null ? '—' : d.abs_mom_pass ? '✓ pass' : '✗ fail', tone: d.abs_mom_pass ? 'good' : 'bad' },
      { label: 'Relative momentum (beats SPY)', value: d.beats_spy == null ? '—' : d.beats_spy ? '✓ pass' : '✗ fail', tone: d.beats_spy ? 'good' : 'bad' },
    ],
    framework: [
      "Gary Antonacci's Dual Momentum (2014) — absolute momentum filters out bear markets, relative momentum keeps the strongest leaders. Combined they have historically reduced max-drawdown vs SPY by ~50%.",
      "Why 12 months? It smooths out noise from short-term swings while still being short enough to rotate when leadership changes. Shorter windows (1m / 3m) catch reversals but also produce more whipsaws.",
      "When both gates pass, the stock is in a confirmed up-trend that's also outperforming the index — the kind of stock Minervini wants you in. When only absolute passes, the stock is rising but lagging — there's a better leader to be holding.",
    ],
    pitfalls: [
      {
        title:   "Don't lean on 12m return alone",
        body:    "A stock can have a great trailing 12m number after a parabolic move that's already exhausted. Combine with stage analysis (Stage 2 = good, Stage 3 = warning, Stage 4 = exit) and base count (early base = good, late base = exhaustion).",
      },
      {
        title:   "Beats-SPY is the gate that often fails first",
        body:    "When SPY itself is ripping (e.g. AI rally), individual stocks need to rip harder to clear relative momentum. A 12m return of +35% looks great but if SPY did +40%, relative momentum fails.",
      },
    ],
    source: 'backend/sepa/dual_momentum.py · compute_dual_momentum() + scanner row.dual_momentum',
  },

  stage_vol_disagreement: {
    emoji:   '⚠️',
    title:   'Stage 3 — geometry says 2, volume disagrees',
    oneLine: "The MA stack (price > MA50 > MA150 > MA200, 200DMA rising) is textbook Stage 2 advancing — but the volume tape is distributing or has CMF outflow. Per Minervini, distribution is a Stage 3 (topping) characteristic, not Stage 2.",
    formula: "stage 2 geometry (p.71-72) AND (accumulation_strength = 'distributing' OR cmf_signal = 'outflow') → downgrade 2 → 3 (Topping, p.74-76)",
    buildFields: (d) => [
      { label: 'Reported stage',          value: d.stage_label ?? '—',                          tone: 'neutral' },
      { label: 'Accumulation strength',   value: d.accumulation_strength ?? '—',                tone: d.accumulation_strength === 'distributing' ? 'bad' : 'neutral' },
      { label: 'CMF signal',              value: d.cmf_signal ?? '—',                           tone: d.cmf_signal === 'outflow' ? 'bad' : 'neutral' },
      { label: 'CMF 20-period',           value: d.cmf_20 != null ? d.cmf_20.toFixed(3) : '—',  tone: d.cmf_20 != null && d.cmf_20 <= -0.10 ? 'bad' : 'neutral' },
    ],
    framework: [
      "Minervini p.71-72 (Stage 2): \"Volume spikes on big up days and big up weeks are contrasted by volume contractions during normal price pullbacks. There are more up days and up weeks on above-average volume than down days and down weeks on above-average volume.\" Accumulation, not distribution.",
      "Minervini p.74-76 (Stage 3 topping): distribution shows up as more down days/weeks on above-average volume than up. The stock can still look strong on the daily chart — price hasn't broken down yet — but the tape is telling you institutions are stepping out.",
      "Pre-2026-05-28, the classifier was geometry-only, so distributing names with perfect MA stacks (e.g. ANTX) came back as Stage 2 'Advancing' and made the buyable list. The fix consults volume tape and downgrades these to Stage 3 — Topping = not buyable.",
    ],
    pitfalls: [
      {
        title:   "Don't buy a name flagged here even if everything else looks good",
        body:    "Trend Template can pass, RS can be ≥70, ADR can be ≥4%, but if the volume disagreement chip is showing, institutions are distributing. The pivot may still trigger, the breakout may still print, but the follow-through usually fails. Wait for re-accumulation.",
      },
      {
        title:   "Some names recover — watch for re-accumulation",
        body:    "A Stage 3 downgrade isn't permanent. If accumulation_strength flips back to accumulating or strong AND CMF moves above zero on the next scan, the stock is back in Stage 2 candidacy. Stalk it on the watchlist; don't write it off.",
      },
    ],
    source: 'backend/sepa/stage.py · classify() volume-disagreement branch · added 2026-05-28',
  },

  rank_trend_history: {
    emoji:   '📈',
    title:   'Score & rank trajectory',
    oneLine: "How this stock's SEPA score AND its leaderboard rank have changed over the last few weeks. Lets you see at a glance whether it's strengthening, fading, or just bouncing around the same tier.",
    formula: "Δ score = current_score − historical_score; Δ rank = historical_rank − current_rank (positive Δ rank means climbed). Rank is derived client-side by sorting each scan's candidates by score descending — does NOT modify ranking logic.",
    buildFields: (d) => {
      const hist = d.trend_history ?? [];
      // Find anchor points to display in the table view.
      const yda = hist.find(p => p.date_et === d.trend_yesterday_date);
      const wka = hist.find(p => p.date_et === d.trend_week_ago_date);
      const oldest = hist.length > 0 ? hist[hist.length - 1] : null;
      const fields: Field[] = [];
      if (yda) {
        fields.push(
          { label: `Score on ${yda.date_et}`,
            value: yda.score != null ? yda.score.toFixed(1) : '—',
            tone:  'neutral' },
          { label: `Rank on ${yda.date_et}`,
            value: yda.rank != null ? `#${yda.rank}` : '—',
            tone:  'neutral' },
        );
      }
      if (wka && wka.date_et !== yda?.date_et) {
        fields.push(
          { label: `Score on ${wka.date_et}`,
            value: wka.score != null ? wka.score.toFixed(1) : '—',
            tone:  'neutral' },
          { label: `Rank on ${wka.date_et}`,
            value: wka.rank != null ? `#${wka.rank}` : '—',
            tone:  'neutral' },
        );
      }
      if (oldest && oldest.date_et !== wka?.date_et && oldest.date_et !== yda?.date_et) {
        fields.push(
          { label: `Earliest snapshot — ${oldest.date_et}`,
            value: oldest.score != null ? `score ${oldest.score.toFixed(1)}` : '—',
            tone:  'neutral' },
        );
      }
      fields.push(
        { label: 'Snapshots available',
          value: String(hist.length),
          tone:  hist.length >= 5 ? 'good' : 'neutral' },
      );
      return fields;
    },
    framework: [
      "Score trend > rank trend for fundamental conviction. A rising score means real Minervini gates are activating (Trend Template gaining checks, RS climbing, base setup detected, volume confirming). A rising rank with flat score might just be tie-breakers shifting around — less meaningful.",
      "Rank trend > score trend for intraday positioning. Within a tight scoring band (e.g. 70-74), rank can swing wildly because day-move and live-quote drift are the tie-breakers. Use rank movement to identify rotation among similarly-scored leaders.",
      "Dropping score AND dropping rank = real exit signal. The methodology is telling you this stock is weakening on multiple gates simultaneously. Cross-reference with the Trend Template breakdown and Stage classifier — usually one specific gate has flipped (RS dropped below 70, Stage 2 → 3, etc).",
      "Climbing score from a low base (e.g. 50 → 72 over 7 days) is the bullish setup pattern. The stock has just qualified onto the leaderboard and is gaining gates. Often coincides with a fresh VCP or Power Play base completing.",
    ],
    pitfalls: [
      {
        title:   "Don't confuse intraday rank slips with real weakening",
        body:    "Rank drops of 5-10 spots within a day are usually just live-quote drift through a tight scoring tier. The Minervini gates compute off MAs and base structure — those don't shift minute-to-minute. Score Δ over multiple days is the honest signal.",
      },
      {
        title:   "New-to-list ≠ buyable",
        body:    "A '🆕 NEW today' chip means the stock just qualified onto the leaderboard. That's a heads-up, not an entry signal. Verify the volume tape, base structure, and Stage 2 confirmation before sizing in. Fresh qualifiers often have unstable scores for the first 1-2 days.",
      },
      {
        title:   "Weekends + holidays gap the chart",
        body:    "Cron only runs on trading days, so a 'Δ vs yesterday' chip on Monday compares to Friday — not Sunday. The tooltip date is what's being compared. If the gap looks unusually large, check whether you're spanning a holiday.",
      },
    ],
    source: 'frontend/src/components/SepaTrendContext.tsx + /sepa/history/runs + /sepa/history/date/{date_et} — pure FE, no ranking logic touched',
  },

  conviction: {
    emoji:   '🎯',
    title:   'Whales + Volume — combined conviction',
    oneLine: "Your two decision signals on one line. When 13F whales (lagging, quarterly) and volume tape (live, daily) agree, conviction is high. When they disagree, one of them is wrong — wait.",
    formula: "combined = whale_score + volume_score\n  whale_score: accumulating +2, distributing −2, balanced 0\n  volume_score: strong accum +3, accumulating +2, distributing −2; CMF inflow +1 / outflow −2; pocket pivot +1; hi-vol breakout +1; ≥4 dist days −1\n\nWARNING tier triggers when both |scores| ≥ 2 AND signs oppose (the ANTX class).",
    buildFields: (d) => {
      const tier = d.conviction_tier ?? '—';
      const label = d.conviction_label ?? '—';
      const whaleScore = d.conviction_whale_score ?? 0;
      const volScore = d.conviction_vol_score ?? 0;
      const combined = d.conviction_combined ?? 0;
      const disagrees = !!d.conviction_disagrees;
      return [
        { label: 'Tier',                  value: `${tier} — ${label}`,                          tone: disagrees ? 'bad' : (combined >= 2 ? 'good' : combined <= -2 ? 'bad' : 'neutral') },
        { label: '🐋 Whales score (13F)', value: `${whaleScore >= 0 ? '+' : ''}${whaleScore}`,  tone: whaleScore > 0 ? 'good' : whaleScore < 0 ? 'bad' : 'neutral' },
        { label: '🐋 Whales detail',      value: d.conviction_whale_reason ?? '—',              tone: 'neutral' },
        { label: '📊 Volume score',       value: `${volScore >= 0 ? '+' : ''}${volScore}`,      tone: volScore > 0 ? 'good' : volScore < 0 ? 'bad' : 'neutral' },
        { label: '📊 Volume detail',      value: d.conviction_vol_reason ?? '—',                tone: 'neutral' },
        { label: 'Combined score',        value: `${combined >= 0 ? '+' : ''}${combined}`,      tone: combined >= 2 ? 'good' : combined <= -2 ? 'bad' : 'neutral' },
        { label: 'Signals disagree?',     value: disagrees ? 'YES — wait for resolution' : 'no — signals aligned', tone: disagrees ? 'bad' : 'good' },
      ];
    },
    framework: [
      "Whales = slow signal. 13F filings disclose institutional positions at the end of each quarter, filed within 45 days. By the time you see them, the actual buying happened 1-4 months ago. But it's high-quality: real funds, real money, real disclosure obligations. Use it to see WHO has committed.",
      "Volume = fast signal. CMF + accumulation strength + pivot detection use this week's tape. Updates daily. Noisier per indicator but together they tell you what's happening RIGHT NOW. Use it to see WHEN to act.",
      "Both bullish (🟢🟢 strong tier) is the highest-confidence setup. Institutions are committed AND the tape is still confirming. This is when conviction position-sizing makes sense.",
      "Signal disagreement (🔴 warning tier) is the ANTX class. Whales accumulated last quarter, but CMF says they're now distributing. Either the institutions are wrong (rare) or the tape is wrong (more common — could be a temporary shakeout). Either way, wait — you have no edge yet.",
    ],
    pitfalls: [
      {
        title:   "Don't trust whales alone in a fast-moving tape",
        body:    "13F data is 45-90 days old. In a stock that's run hard since the filing, the institutions you're following may have already trimmed. Always cross-reference with current volume — that's why this chip combines them.",
      },
      {
        title:   "Don't trust volume alone over multi-week views",
        body:    "Volume signals can flicker on a single big day. Strong accumulation on a Friday earnings beat doesn't mean institutional commitment. The 13F whale layer gives you the months-long context that filters noise from real positioning.",
      },
      {
        title:   "Disagreement = wait, not sell",
        body:    "🔴 warning is not a sell signal on its own — it's a 'don't buy yet' signal. If you already hold, look at the broader Stage classifier and Trend Template before exiting. The disagreement might resolve in the bullish direction within 1-2 weeks.",
      },
      {
        title:   "Missing whales data is common for new IPOs and tiny floats",
        body:    "13F coverage requires the fund to hold ≥ a million shares. Newly-IPO'd names and microcap floats often don't show up in 13F data yet. The chip degrades to 📊 'volume-only' for those — treat it as one signal, not two.",
      },
    ],
    source: 'frontend/src/components/SepaConvictionChip.tsx · computeConviction()',
  },

  political_disclosure: {
    emoji:   '🏛️',
    title:   'Political-disclosure context',
    oneLine: "This ticker appears on the curated list of stocks with disclosed POTUS-family positions or direct U.S. government involvement. Informational only — disclosed positions don't predict outcomes.",
    formula: "Curated list lookup in src/lib/politicalDisclosures.ts. Two distinct chip types: POTUS Family (gold) for disclosed personal/family positions per OGE filings + news reporting; Govt Investment / Contractor (blue) for U.S. govt equity stakes (CHIPS Act) and major contractors. Inferred subset uses dashed border + dim color.",
    buildFields: (d) => {
      const cats = (d.political_categories ?? []).join(' · ');
      const fields: Field[] = [
        { label: 'Company',             value: d.political_company ?? '—',                 tone: 'neutral' },
        { label: 'Sector',              value: d.political_sector ?? '—',                  tone: 'neutral' },
        { label: 'Category',            value: cats || '—',                                tone: 'neutral' },
      ];
      if (d.political_band) {
        fields.push({ label: 'Disclosed band',  value: d.political_band,                   tone: 'neutral' });
      }
      if (d.political_notes) {
        fields.push({ label: 'Source note',     value: d.political_notes,                  tone: 'neutral' });
      }
      fields.push({
        label: 'Confidence',
        value: d.political_is_inferred ? 'Inferred (not directly disclosed)' : 'Directly disclosed / sourced',
        tone:  d.political_is_inferred ? 'neutral' : 'good',
      });
      return fields;
    },
    framework: [
      "What this chip IS: a context flag that this stock has been touched by political-disclosure reporting. It surfaces things you'd want to be aware of when evaluating the name — disclosed positions, govt equity stakes, contractor / program relationships. Use it like a sector tag.",
      "What this chip is NOT: a buy or sell signal. Disclosed positions don't predict outcomes — there's no statistical edge in following them, and even if there were, the disclosure lag (often 30-45 days) usually erases it. Trade the chart, not the headline.",
      "Two-chip design reflects the two-signal nature: POTUS Family disclosures are about personal financial behavior; Govt Investment / Contractor is about institutional capital flows. They mean different things — multiple chips on one card means multiple distinct context layers, not 'more bullish'.",
      "The Inferred subset (dashed chips) is for tickers scan-classified into the political-signal cluster but not directly disclosed. These have lower confidence — treat them as soft context, not as evidence.",
    ],
    pitfalls: [
      {
        title:   "Don't trade because a politician owns it",
        body:    "There's no consistent edge in copying disclosed political positions. By the time you see the filing, the position has already been held for weeks-to-months, and other market participants have priced in any disclosure premium. Treat the chip as background context — your buy decision should still come from Trend Template + Stage 2 + volume + setup.",
      },
      {
        title:   "Disclosed band ≠ current position",
        body:    "OGE forms show position bands as of the reporting date, which lags by 30-45 days minimum. The actual position may have been added to, trimmed, or fully exited since then. Don't infer current conviction from a stale disclosure band.",
      },
      {
        title:   "List freshness is manual",
        body:    "This list is curated and only updates when src/lib/politicalDisclosures.ts is edited. Sources (OGE.gov + reputable news) update on their own schedule. If you've seen a relevant disclosure in the news that's not in this list, add it to the file — there's no automated refresh.",
      },
      {
        title:   "Inferred ≠ verified",
        body:    "The dashed 'Inferred' chips are for tickers grouped with the political-signal cluster but lacking direct disclosure. Be more skeptical of these — they may be guilt-by-association rather than actual disclosed holdings.",
      },
    ],
    source: 'frontend/src/lib/politicalDisclosures.ts — curated from OGE.gov disclosures + reputable news reporting (NYT, Bloomberg, WSJ). User-editable.',
  },

  dist_days_warning: {
    emoji:   '⚠️',
    title:   'Distribution day cluster',
    oneLine: "3+ distribution days in last 25. Below the 4-day institutional-selling threshold but worth watching closely.",
    formula: "dist_day = (close down ≥ 0.2%) AND (volume > yesterday's volume)",
    buildFields: (d) => [
      { label: 'Distribution days (25)',  value: d.distribution_days_25 != null ? String(d.distribution_days_25) : '—',
                                          tone: d.distribution_days_25 != null && d.distribution_days_25 >= 4 ? 'bad' : 'neutral' },
      { label: 'Accumulation days (25)',  value: d.accumulation_days_25 != null ? String(d.accumulation_days_25) : '—',
                                          tone: 'neutral' },
    ],
    framework: [
      "Watch but don't act yet. At 4-5, switch to active trimming. At 6+, full exit. Track the trend — if dist days are clustering in the last 5 sessions (vs spread over 25), the signal is more acute.",
    ],
    pitfalls: [
      {
        title:   "Distribution days during earnings runs are often noise",
        body:    "Earnings-day volatility can produce 'distribution days' that aren't institutional selling, just intraday volatility. Check if any of the dist days coincided with earnings; if so, weight the signal lower.",
      },
    ],
    source: 'backend/sepa/volume.py · _count_accum_dist_days()',
  },

  /* ============================ SCORE COMPONENTS ============================
   * These specs cover the trend / RS / stage / setup / ADR / base count
   * drill-ins. The score_breakdown kind uses a custom renderer (see
   * renderScoreBreakdown below) instead of the generic Field grid.
   * ========================================================================= */
  score_breakdown: {
    emoji:   '📊',
    title:   'Score breakdown — what drove the ranking',
    oneLine: "The SEPA score (0-100) is a weighted sum of 7 components. This tab shows EXACTLY how much each one contributed to this ticker's score.",
    formula: "score = Σ(weight_i × completion_i) − late_base_penalty",
    buildFields: () => [],  // unused — custom renderer below replaces this
    framework: [
      "Trend Template (30 pts) is the largest single contributor — Minervini's 8 price/MA gates. A perfect 8/8 = full 30 pts; 6/8 = 22.5 pts.",
      "RS Rank (25 pts) ONLY counts if RS ≥ 70. Below the gate it's 0 pts. The point of the gate is to filter out non-leaders entirely — partial credit would dilute the screen.",
      "Setup (15 pts) — VCP gets full 15, Power Play gets 12.75 (85%). NO BASE is 0 pts. Most current-environment candidates have 0 here.",
      "Fundamentals (10 pts) is graded — 1/3 CANSLIM = 3.3, 2/3 = 6.7, 3/3 = 10. ETFs skip this entirely.",
      "Volume (5 pts) is the v2 graded model — strong/pocket-pivot/breakout/CMF inflow each add 0.2× the weight. Distributing subtracts.",
      "Late-base penalty (-8) trips on base #4+. By that point in an uptrend, institutional buying is mostly done; failure rates climb sharply.",
    ],
    pitfalls: [
      {
        title:   "Score is mechanical — it's a screen, not a forecast",
        body:    "Two stocks with score 75 can have wildly different prospects depending on which components contributed. A 75 from trend+RS+stage is high-conviction; a 75 from breakout+volume+late-base is fragile. The breakdown reveals the difference.",
      },
      {
        title:   "Caps the max — high scores aren't 'better'",
        body:    "Score is capped at 100. Once a candidate hits all weights, more confirmation doesn't push the score higher. Use the score to RANK; use the components to UNDERSTAND.",
      },
    ],
    source: 'backend/sepa/scanner.py · SCORE_WEIGHTS + _score()',
  },

  trend_template: {
    emoji:   '📈',
    title:   'Trend Template',
    oneLine: "Minervini's 8 price/MA gates. Every gate is binary (pass/fail). The score component is 30 × (passed / 8).",
    formula: "trend_score = 30 × (gates_passed / 8)",
    buildFields: (d) => {
      const checks = d.trend_checks || {};
      // Render each known gate as a separate field — green if true, red if false.
      // Falls through gracefully if backend renames a check key.
      const keys = Object.keys(checks);
      if (keys.length === 0) {
        return [{ label: 'Gates passed', value: `${d.trend_passed ?? 0} / 8`, tone: 'neutral' }];
      }
      return keys.map((k) => ({
        label: k.replace(/_/g, ' '),
        value: checks[k] ? '✓ pass' : '✗ fail',
        tone:  (checks[k] ? 'good' : 'bad') as 'good' | 'bad',
      }));
    },
    framework: [
      "All 8 gates passed = full credit and a Stage-2 confirmation. Even 6/8 leaves the ticker eligible if RS is strong.",
      "Key gates: (1) price > 200-day MA, (2) 200-day rising 1+ months, (3) 50-day > 150-day > 200-day, (4) price > 50-day, (5) price ≥ 30% above 52-week low, (6) price within 25% of 52-week high.",
      "Gate failures often cluster — a stock failing 4+ gates is in transition (S1→S2 or S2→S3) and is NOT yet investable.",
    ],
    pitfalls: [
      {
        title:   "Gates can pass while the trend is actually rolling over",
        body:    "The 8 gates are LAGGING. A stock can pass all 8 today but be in the early stages of distribution. Cross-check with the distribution-day count + accumulation strength chips.",
      },
    ],
    source: 'backend/sepa/trend_template.py',
  },

  rs_rank: {
    emoji:   '⚡',
    title:   'Relative Strength Rank',
    oneLine: "IBD-style 1-99 percentile rank of 12-month total return vs every other US stock. The most cited single metric in Minervini's framework.",
    formula: "rs_score = (rs >= 70) ? 25 × (min(rs, 99) / 99) : 0",
    buildFields: (d) => [
      { label: 'RS rank',           value: d.rs_rank != null ? String(d.rs_rank) : '—',
                                     tone: d.rs_rank != null && d.rs_rank >= 80 ? 'good'
                                         : d.rs_rank != null && d.rs_rank >= 70 ? 'neutral'
                                         : 'bad' },
      { label: 'Above ≥70 gate?',   value: (d.rs_rank ?? 0) >= 70 ? 'YES' : 'NO',
                                     tone: (d.rs_rank ?? 0) >= 70 ? 'good' : 'bad' },
      { label: 'Score contribution', value: ((d.rs_rank ?? 0) >= 70
                                              ? (25 * Math.min(d.rs_rank ?? 0, 99) / 99).toFixed(1)
                                              : '0.0') + ' / 25 pts', tone: 'neutral' },
    ],
    framework: [
      "Minervini's hard gate: RS ≥ 70 to even be in the universe. Below that, the stock has been UNDER-performing the market — leadership is mathematically elsewhere.",
      "≥ 80 = top quintile, strong candidate. ≥ 90 = top decile, leaders only. The chart leaders (NVDA, MU at certain windows, etc.) live at 98-99.",
      "RS is RELATIVE — a 99 in a bear market still means the stock is the BEST in a falling tape, not a guaranteed winner.",
    ],
    pitfalls: [
      {
        title:   "RS leaders can crash hard at cycle tops",
        body:    "The highest-RS names lead going UP and lead going DOWN. RS is symmetric. Don't confuse 'highest RS' with 'safest'. Combine with stage analysis and distribution count.",
      },
    ],
    source: 'backend/sepa/rs_rank.py',
  },

  stage: {
    emoji:   '🪜',
    title:   "Weinstein's stage analysis",
    oneLine: "Every stock is in one of four stages. Minervini only buys Stage 2. The stage_2 score component is 10 pts flat — no partial credit.",
    formula: "stage_score = (stage == 2) ? 10 : 0",
    buildFields: (d) => [
      { label: 'Current stage', value: d.stage_label || (d.stage_num ? `Stage ${d.stage_num}` : '—'),
                                tone: d.stage_num === 2 ? 'good' : d.stage_num && d.stage_num > 2 ? 'bad' : 'neutral' },
      { label: 'Score contribution', value: (d.stage_num === 2 ? '10' : '0') + ' / 10 pts',
                                tone: 'neutral' },
    ],
    framework: [
      "Stage 1 (Basing) — sideways accumulation after a downtrend. NOT a buy zone. Watch for the 200-day flattening + tightening range as the early signal.",
      "Stage 2 (Advancing) — price > 50-day > 150-day > 200-day, all rising. THE ONLY BUY STAGE per Minervini. 80% of all gains in a stock's lifetime happen here.",
      "Stage 3 (Topping) — 50-day flattens, price loses 50-day support but stays above 200. Distribution phase; trim positions.",
      "Stage 4 (Declining) — price < 50 < 150 < 200, 200-day falling. Exit signal. Do NOT bottom-fish.",
    ],
    pitfalls: [
      {
        title:   "Stage transitions take weeks, not days",
        body:    "A single bar's price doesn't change the stage. The 50/150/200-day MA relationships have to actually flip. Don't pre-empt the transition.",
      },
    ],
    source: "backend/sepa/stage.py (Weinstein's 4 stages)",
  },

  adr: {
    emoji:   '〰️',
    title:   'Average Daily Range (ADR)',
    oneLine: "Average % move per day over the last 20 sessions. Proxies for how much room you have to work with on a swing trade.",
    formula: "adr_score = liquid ? 2.0 : 0 + (adr_pct >= 4 ? 3.0 : 0)  // max 5 pts",
    buildFields: (d) => [
      { label: 'ADR %',                  value: d.adr_pct != null ? `${d.adr_pct}%` : '—',
                                          tone: d.adr_pct != null && d.adr_pct >= 4 ? 'good' : 'neutral' },
      { label: 'Above ≥4% leader gate?',  value: (d.adr_pct ?? 0) >= 4 ? 'YES' : 'NO',
                                          tone: (d.adr_pct ?? 0) >= 4 ? 'good' : 'neutral' },
      { label: 'Liquid?',                 value: d.liquidity_liquid ? 'YES' : 'NO',
                                          tone: d.liquidity_liquid ? 'good' : 'bad' },
    ],
    framework: [
      "ADR ≥ 4% = leader-grade volatility. The stock moves enough each day that a 1-2% stop has real room without being noise.",
      "ADR < 2% = slow-moving name. Tighter stops are required (the ATR is too small for normal stop placement) and R-multiples per swing are smaller.",
      "Combine: high ADR + Stage 2 + RS ≥ 90 = textbook Minervini hyper-growth candidate. High ADR alone = volatile junk.",
    ],
    pitfalls: [
      {
        title:   "ADR is a TRAILING metric",
        body:    "20-day ADR doesn't reflect today's regime. After a series of gap-up earnings, ADR will spike; after a calm consolidation, it drops. Use it as one input, not gospel.",
      },
    ],
    source: 'backend/sepa/adr.py',
  },

  base_count_late: {
    emoji:   '⚠️',
    title:   'Late-stage base',
    oneLine: "This stock is on base #4+ from its current Stage-1 starting point. By this point in an uptrend, institutional buying is largely complete and failure rates climb sharply.",
    formula: "late_base_penalty = is_late_stage ? -8 : 0",
    buildFields: (d) => [
      { label: 'Base count',          value: d.base_count_n != null ? `#${d.base_count_n}` : '#4+', tone: 'bad' },
      { label: 'Penalty applied',      value: '-8 pts',                                              tone: 'bad' },
    ],
    framework: [
      "From 'Trade Like a Stock Market Wizard' Ch.11: the 1st and 2nd base off a Stage 1 bottom are the prime entries. By base #4+, the trend is mature; new entries face institutional EXITS, not entries.",
      "Tradeable but lower conviction: tighten stops (4-5% instead of 7-8%), smaller position size (0.5% capital risk instead of 1%), faster exits on weakness.",
      "Watch for: failed breakouts from late bases — within 2-3 days they reverse below the pivot. That's the textbook late-base failure pattern.",
    ],
    pitfalls: [
      {
        title:   "Late bases can rip if the broader narrative reignites",
        body:    "Periodic news catalysts (earnings beats, AI announcements, etc.) can sometimes restart institutional accumulation on late bases. The -8 penalty isn't a hard sell — it's a 'be careful' tag.",
      },
    ],
    source: 'backend/sepa/base_count.py',
  },

  base_count_none: {
    emoji:   '🚫',
    title:   'No base',
    oneLine: "No clean VCP or Power Play base detected. This is normal in late-stage markets where everything is extended — but it means the 15 pts of base/setup score didn't contribute.",
    formula: "setup_score = vcp ? 15 : (powerplay ? 12.75 : 0)",
    buildFields: (d) => [
      { label: 'Setup type',              value: d.setup_type || 'none',         tone: 'neutral' },
      { label: 'Score contribution',      value: '0 / 15 pts',                   tone: 'bad' },
    ],
    framework: [
      "Bases form during CONSOLIDATION (sideways action). In runaway uptrends every name is extending — no clean bases exist. That's market regime, not a bug.",
      "Without a base, you can't use the standard Minervini pivot-buy. Alternative entries: PEG (Power Earnings Gap), ORB (Opening Range Breakout), Inside-Day breakout — all on /setups.",
      "When the market consolidates (typically late summer / late winter), bases re-form across sectors. Patient money waits.",
    ],
    pitfalls: [
      {
        title:   "Buying without a base is buying without a stop",
        body:    "If there's no clean base, there's no defined low for stop placement. ATR-based stops are wider and looser. Sizing must shrink to compensate.",
      },
    ],
    source: 'backend/sepa/vcp.py + power_play.py',
  },

  setup_vcp: {
    emoji:   '🎯',
    title:   'Volatility Contraction Pattern (VCP)',
    oneLine: "Minervini's archetypal base. 2-6 successive pullbacks each ~half the previous, with a tight (≤10%) right side. Full 15 pts of setup credit.",
    formula: "vcp_score = 15 (+2 if ideal depth + good contraction count)",
    buildFields: (d) => [
      { label: 'Pivot',                value: d.setup_pivot != null ? `$${d.setup_pivot.toFixed(2)}` : '—',  tone: 'neutral' },
      { label: 'Suggested stop',        value: d.setup_stop != null ? `$${d.setup_stop.toFixed(2)}` : '—',   tone: 'neutral' },
      { label: 'Risk to stop',          value: (d.setup_pivot && d.setup_stop)
                                                ? `${(((d.setup_pivot - d.setup_stop) / d.setup_pivot) * 100).toFixed(2)}%`
                                                : '—',
                                          tone: 'neutral' },
    ],
    framework: [
      "Buy WITHIN 1-2% of the pivot — chasing past 5% breaks the risk-to-stop math.",
      "Volume should be DRYING UP during the final contraction (right side) and SPIKING on the breakout day. That's institutional rotation in.",
      "Tight VCPs (≤ 8% final contraction) historically work the best. > 15% final contraction = base is too deep, lower conviction.",
    ],
    pitfalls: [
      {
        title:   "Not all VCPs are equal",
        body:    "Pivot quality varies. Look at pivot_quality_ok flag and prior-advance % — a VCP forming after a 100%+ run is a Power Play. A VCP after a flat 6 months is a stage-1-to-stage-2 transition; different setup entirely.",
      },
    ],
    source: 'backend/sepa/vcp.py · detect()',
  },

  setup_power_play: {
    emoji:   '🚀',
    title:   'Power Play / High-Tight Flag',
    oneLine: "Explosive multi-week run-up of ≥100% in any 40-day window followed by tight consolidation. The 'second-chance' entry into a leader.",
    formula: "powerplay_score = 15 × 0.85 = 12.75",
    buildFields: (d) => [
      { label: 'Pivot',                value: d.setup_pivot != null ? `$${d.setup_pivot.toFixed(2)}` : '—', tone: 'neutral' },
      { label: 'Suggested stop',        value: d.setup_stop != null ? `$${d.setup_stop.toFixed(2)}` : '—',  tone: 'neutral' },
      { label: 'Score contribution',    value: '12.75 / 15 pts (85% of full base credit)',                  tone: 'neutral' },
    ],
    framework: [
      "Looser pattern criteria than VCP — only 85% of full setup credit. Reflects that the entry zone is less precise.",
      "Best Power Plays come from IPOs or post-news leaders where institutional accumulation drove the initial 100%+ move. Watch for tight 10-25% pullback during consolidation.",
      "Stop placement: low of the consolidation rectangle. Risk often 8-12% — wider than a VCP but the explosive upside justifies it.",
    ],
    pitfalls: [
      {
        title:   "Pump-and-dump can mimic Power Play setup",
        body:    "Penny stocks with retail-driven 100%+ moves create 'Power Play' patterns that have no institutional sponsorship. Cross-check: float size, dollar volume, RS rank. Real Power Plays have RS ≥ 95 and meaningful institutional ownership.",
      },
    ],
    source: 'backend/sepa/power_play.py · detect()',
  },
};


function ToneStyle(tone?: 'good' | 'bad' | 'neutral'): React.CSSProperties {
  if (tone === 'good') return { color: '#22c55e' };
  if (tone === 'bad')  return { color: '#ef4444' };
  return { color: '#cfcfd4' };
}


export function SignalDrillModal({ kind, data, onClose }: {
  kind: SignalKind;
  data: SignalData;
  onClose: () => void;
}) {
  const spec = SIGNAL_SPECS[kind];

  // Esc to close.
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onEsc);
    return () => window.removeEventListener('keydown', onEsc);
  }, [onClose]);

  const fields = spec.buildFields(data);

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${spec.title} for ${data.symbol}`}
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '1rem', zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#141416', color: '#e6e6e6',
          width: 'min(640px, calc(100vw - 2rem))',
          maxHeight: 'calc(100vh - 2rem)', overflowY: 'auto',
          border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12,
          padding: '1.1rem 1.2rem 1rem',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'baseline',
          justifyContent: 'space-between', gap: '0.5rem',
          marginBottom: '0.6rem',
        }}>
          <div>
            <div className="eyebrow" style={{ fontSize: '0.66rem', color: '#9aa8c8' }}>
              Signal drill-in · {data.symbol}
            </div>
            <h2 style={{
              margin: '0.1rem 0 0', fontSize: '1.15rem',
              fontFamily: '"Times New Roman", Georgia, serif',
              fontStyle: 'italic',
            }}>
              {spec.emoji} {spec.title}
            </h2>
          </div>
          <button
            onClick={onClose} aria-label="Close"
            style={{
              background: 'none', border: '1px solid rgba(255,255,255,0.15)',
              color: '#cfcfd4', padding: '4px 10px', borderRadius: 4,
              cursor: 'pointer', fontSize: '0.85rem', fontFamily: 'inherit',
            }}
          >✕</button>
        </div>

        {/* One-liner */}
        <div style={{
          padding: '0.55rem 0.75rem',
          background: 'rgba(154, 168, 200, 0.06)',
          border: '1px solid rgba(154, 168, 200, 0.22)',
          borderRadius: 6,
          fontSize: '0.84rem',
          lineHeight: 1.55,
          marginBottom: '0.7rem',
        }}>
          {spec.oneLine}
        </div>

        {/* Formula */}
        <div style={{ marginBottom: '0.8rem' }}>
          <div className="eyebrow" style={{ fontSize: '0.62rem', marginBottom: 4 }}>
            Formula
          </div>
          <code style={{
            display: 'block', padding: '0.4rem 0.6rem',
            background: 'rgba(0,0,0,0.35)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 4,
            fontFamily: 'ui-monospace, monospace',
            fontSize: '0.74rem',
            lineHeight: 1.5,
            color: '#cfcfd4',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}>
            {spec.formula}
          </code>
        </div>

        {/* THIS ticker's numbers — score_breakdown uses a custom renderer
            with weighted bars; everything else uses the generic field grid. */}
        {kind === 'score_breakdown' ? (
          <ScoreBreakdownPanel data={data} />
        ) : (
          <div style={{ marginBottom: '0.9rem' }}>
            <div className="eyebrow" style={{ fontSize: '0.62rem', marginBottom: 4 }}>
              {data.symbol} · live numbers
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
              gap: '0.4rem',
            }}>
              {fields.map((f, i) => (
                <div key={i} style={{
                  padding: '0.4rem 0.6rem',
                  background: 'rgba(20,20,22,0.5)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: 4,
                }}>
                  <div style={{
                    fontSize: '0.6rem', color: '#9a9aa3',
                    letterSpacing: '0.06em', textTransform: 'uppercase',
                    marginBottom: 1,
                  }}>{f.label}</div>
                  <div className="mono" style={{
                    fontSize: '0.92rem', fontWeight: 700,
                    ...ToneStyle(f.tone),
                  }}>{f.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Minervini framework */}
        <div style={{ marginBottom: '0.8rem' }}>
          <div className="eyebrow" style={{ fontSize: '0.62rem', marginBottom: 4 }}>
            How to act on it
          </div>
          <ul style={{
            margin: 0, padding: '0 0 0 1.1rem',
            fontSize: '0.82rem', lineHeight: 1.55, color: '#cfcfd4',
          }}>
            {spec.framework.map((p, i) => <li key={i} style={{ marginBottom: 4 }}>{p}</li>)}
          </ul>
        </div>

        {/* Pitfalls */}
        <div style={{ marginBottom: '0.6rem' }}>
          <div className="eyebrow" style={{ fontSize: '0.62rem', marginBottom: 4 }}>
            Common ways this misleads
          </div>
          {spec.pitfalls.map((p, i) => (
            <div key={i} style={{
              padding: '0.45rem 0.65rem',
              background: 'rgba(239,68,68,0.05)',
              borderLeft: '2px solid #ef4444',
              borderRadius: 3,
              marginBottom: 4,
            }}>
              <div style={{ fontWeight: 700, fontSize: '0.8rem', marginBottom: 2 }}>
                ⚠️ {p.title}
              </div>
              <div style={{ fontSize: '0.76rem', lineHeight: 1.5, color: '#cfcfd4' }}>
                {p.body}
              </div>
            </div>
          ))}
        </div>

        <div style={{ fontSize: '0.62rem', color: '#6a6a72', marginTop: 6 }}>
          Source: <code style={{ fontFamily: 'ui-monospace, monospace' }}>{spec.source}</code>
        </div>
      </div>
    </div>,
    document.body,
  );
}


/* ============================================================================
 * ScoreBreakdownPanel — custom renderer for the score_breakdown kind.
 * Shows each component as a row with:
 *   - label
 *   - filled bar (earned / weight)
 *   - "earned / max" text in mono
 *   - detail line explaining the number
 * Sums to the final score and compares against the row's stored score
 * to catch any drift between frontend recompute and backend value.
 * ============================================================================ */
function ScoreBreakdownPanel({ data }: { data: SignalData }) {
  const components = computeScoreBreakdown(data);
  const totalEarned = components.reduce((s, c) => s + c.earned, 0);
  const totalMax = components
    .filter((c) => c.weight > 0)
    .reduce((s, c) => s + c.weight, 0);
  const storedScore = data.score ?? null;
  const drift = storedScore != null ? totalEarned - storedScore : null;

  return (
    <div style={{ marginBottom: '0.9rem' }}>
      <div style={{
        display: 'flex', alignItems: 'baseline',
        justifyContent: 'space-between', marginBottom: 6,
      }}>
        <div className="eyebrow" style={{ fontSize: '0.62rem' }}>
          {data.symbol} · score components
        </div>
        <div className="mono" style={{ fontSize: '0.74rem', color: '#cfcfd4' }}>
          {totalEarned.toFixed(1)} <span style={{ opacity: 0.5 }}>/ {totalMax}</span>
          {storedScore != null && (
            <span style={{ marginLeft: 8, color: '#6a6a72' }}>
              (stored: {storedScore.toFixed(1)}
              {drift != null && Math.abs(drift) >= 1 ? ` · Δ ${drift > 0 ? '+' : ''}${drift.toFixed(1)}` : ''})
            </span>
          )}
        </div>
      </div>

      {components.map((c, i) => {
        const isPenalty = c.earned < 0;
        const isPartial = c.earned > 0 && c.earned < c.weight;
        const isFull = c.earned >= c.weight && c.weight > 0;
        const isZero = c.earned === 0 && c.weight > 0;
        // Bar width is earned/weight clamped 0-100. For penalty rows
        // (weight < 0), we render a red bar at 100% of the row.
        const fillPct = c.weight > 0
          ? Math.max(0, Math.min(100, (c.earned / c.weight) * 100))
          : 100;
        const fillColor = isPenalty ? '#ef4444'
          : isFull ? '#22c55e'
          : isPartial ? '#d4af37'
          : '#6a6a72';
        return (
          <div key={i} style={{
            padding: '0.4rem 0.55rem',
            background: 'rgba(20,20,22,0.5)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderLeft: `3px solid ${fillColor}`,
            borderRadius: 4,
            marginBottom: 3,
          }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              alignItems: 'baseline', marginBottom: 3,
            }}>
              <span style={{ fontSize: '0.84rem', fontWeight: 600 }}>
                {isFull ? '✓ ' : isZero ? '✗ ' : isPenalty ? '⚠ ' : '◐ '}
                {c.label}
              </span>
              <span className="mono" style={{
                fontSize: '0.78rem', fontWeight: 700,
                color: fillColor,
              }}>
                {c.earned > 0 ? '+' : ''}{c.earned.toFixed(1)}
                <span style={{ opacity: 0.4, fontSize: '0.86em' }}>
                  {' '}/ {c.weight > 0 ? c.weight : c.weight}
                </span>
              </span>
            </div>
            <div style={{
              height: 4, background: 'rgba(255,255,255,0.05)',
              borderRadius: 2, overflow: 'hidden',
            }}>
              <div style={{
                height: '100%',
                width: `${fillPct}%`,
                background: fillColor,
                opacity: 0.7,
                transition: 'width 200ms',
              }} />
            </div>
            <div style={{
              fontSize: '0.7rem', color: '#9a9aa3',
              marginTop: 3, lineHeight: 1.4,
            }}>
              {c.detail}
            </div>
          </div>
        );
      })}

      {/* Rating tier reminder so the user can see which threshold the
          score crossed (STRONG_BUY ≥ 75, BUY ≥ 60, WATCH ≥ 50). */}
      {storedScore != null && (
        <div style={{
          marginTop: 6, padding: '0.35rem 0.55rem',
          background: 'rgba(154,168,200,0.06)',
          borderRadius: 4,
          fontSize: '0.72rem', color: '#9aa8c8', lineHeight: 1.45,
        }}>
          <strong style={{ color: '#cfcfd4' }}>{data.rating || '—'}</strong>{' '}
          tier · thresholds: STRONG_BUY ≥ 75, BUY ≥ 60, WATCH ≥ 50.
          {storedScore < 50 && ' Below WATCH threshold — wouldn\'t typically appear in the list.'}
        </div>
      )}
    </div>
  );
}
