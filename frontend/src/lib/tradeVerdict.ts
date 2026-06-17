/* tradeVerdict — composite BUY / WATCH / AVOID verdict for the SEPA detail
 * page's Analysis tab, combining TWO frameworks on data the scan payload
 * already carries (no extra fetch, no backend change):
 *
 *   1. Mark Minervini — SEPA / Trend Template
 *      ("Trade Like a Stock Market Wizard", Ch. on the Trend Template).
 *      The 8 price/MA/RS gates + an actionable pivot-breakout-on-volume.
 *
 *   2. Pradeep Bonde — Stockbee
 *      (Episodic Pivots, 2010; the 4% breakout scan; momentum bursts).
 *      Earnings/news gap-ups, 4% volume breakouts, momentum, group
 *      leadership — and the anti-thesis SELL signals (MA breach on volume,
 *      lower lows / climax after a Stage-2 advance).
 *
 * Composition rule (strict 3-state):
 *   - An ANTI-THESIS from either framework (Minervini structure broken, or a
 *     Bonde sell signal) forces AVOID — even if the other framework is a buy.
 *     This is the required edge case: Minervini passes but a Bonde sell signal
 *     fires → NOT a buy.
 *   - BUY requires BOTH frameworks to independently confirm an actionable buy.
 *   - Trend intact but no confirmed buy trigger → WATCH.
 *
 * Thresholds are the ones the two authors actually publish — they are NOT
 * invented here. See docs/sepa/trade_verdict_methodology.md for the cites.
 * Pure function: no I/O, no globals. Tested in tradeVerdict.test.ts.
 */

// ── Published thresholds ──────────────────────────────────────────────────
export const RS_MIN = 70; // Minervini Trend Template RS-rating minimum
export const RS_PREFERRED = 80; // Minervini's "preferably 80+"
export const BONDE_FOURPCT_GAIN = 4.0; // Stockbee "4% breakout" daily gain
export const BONDE_BREAKOUT_RVOL = 1.5; // "...on volume > 1.5× average"
export const BONDE_MOM_BURST_1W_PCT = 8.0; // momentum burst — 8/10/15%+ run
export const BONDE_MOM_BURST_1M_PCT = 15.0; // 1-month burst threshold
export const EXTENDED_DIST_200_PCT = 100.0; // far above 200-MA → extended, not a fresh entry

export type Verdict = 'buy' | 'watch' | 'avoid' | 'insufficient';

export interface VerdictCheck {
  label: string;
  /** true = pass, false = fail, null = data unavailable (shown as "—"). */
  ok: boolean | null;
  detail?: string;
}

export interface FrameworkResult {
  name: string;
  verdict: Exclude<Verdict, 'insufficient'>;
  checks: VerdictCheck[];
}

export interface TradeVerdict {
  verdict: Verdict;
  label: string; // BUY | WATCH | AVOID | NO DATA
  tone: string; // hex colour for the badge
  why: string; // short, cites which framework(s) drove the call
  minervini: FrameworkResult;
  bonde: FrameworkResult;
}

const TONE: Record<Verdict, string> = {
  buy: '#10b981',
  watch: '#eab308',
  avoid: '#f87171',
  insufficient: '#94a3b8',
};
const LABEL: Record<Verdict, string> = {
  buy: 'BUY',
  watch: 'WATCH',
  avoid: 'AVOID',
  insufficient: 'NO DATA',
};

const pct = (v: number | null | undefined): string =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${Math.round(v * 10) / 10}%`;

export interface TradeVerdictInput {
  /** Mirrors the SepaCandidate shape; loosely typed so we can read the
   *  v2 fields (sell_signals, dual_momentum, group_*) the FE type doesn't
   *  fully enumerate yet. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  row: any;
  /** Last earnings surprise %, if known (detail page passes data.catalyst). */
  catalystSurprisePct?: number | null;
}

export function computeTradeVerdict({ row, catalystSurprisePct }: TradeVerdictInput): TradeVerdict {
  const tc = row?.trend?.checks;
  const stage = row?.stage?.stage;

  // No trend template → we can't evaluate either framework.
  if (!tc || typeof tc !== 'object') {
    return {
      verdict: 'insufficient',
      label: LABEL.insufficient,
      tone: TONE.insufficient,
      why: 'Not enough data — no trend-template result for this name yet.',
      minervini: { name: 'Minervini SEPA', verdict: 'avoid', checks: [] },
      bonde: { name: 'Bonde / Stockbee', verdict: 'avoid', checks: [] },
    };
  }

  const rs: number | null = row?.rs_rank ?? null;
  const vol = row?.volume ?? {};
  const rvol = vol.avg_vol_50 ? (vol.last_vol ?? 0) / vol.avg_vol_50 : null;
  const dayChg: number | null = row?.day_change_pct ?? null;
  const dist200: number | null = row?.stage?.dist_200_pct ?? null;

  // ── Minervini SEPA / Trend Template ──────────────────────────────────────
  const stackOk = !!(tc.price_above_ma150_and_ma200 && tc.ma150_above_ma200 && tc.ma50_above_ma150_above_ma200);
  const rsOk = rs != null && rs >= RS_MIN;
  const buyTrigger = !!(vol.high_vol_breakout || vol.pocket_pivot) && row?.is_in_buy_zone !== false;
  const trendCore = !!(
    tc.price_above_ma150_and_ma200 &&
    tc.ma150_above_ma200 &&
    tc.ma50_above_ma150_above_ma200 &&
    tc.ma200_trending_up &&
    tc.at_least_30pct_above_52w_low &&
    tc.within_25pct_of_52w_high
  );
  const belowKeyMa = !tc.price_above_ma150_and_ma200;
  const minerviniBroken = belowKeyMa || (stage != null && stage > 2);

  const minerviniChecks: VerdictCheck[] = [
    { label: 'Price > 150-day & 200-day MA', ok: !!tc.price_above_ma150_and_ma200 },
    { label: '50 > 150 > 200-day MA stack', ok: stackOk },
    { label: '200-day MA trending up ≥1mo', ok: !!tc.ma200_trending_up },
    { label: '≥30% above 52-week low', ok: !!tc.at_least_30pct_above_52w_low },
    { label: 'Within 25% of 52-week high', ok: !!tc.within_25pct_of_52w_high },
    {
      label: `RS rating ≥${RS_MIN} (pref ≥${RS_PREFERRED})`,
      ok: rsOk,
      detail: rs == null ? '—' : `RS ${rs}${rs >= RS_PREFERRED ? ' ✓ preferred' : ''}`,
    },
    {
      label: 'Tight VCP / pivot breakout on volume',
      ok: buyTrigger,
      detail: vol.high_vol_breakout ? 'hi-vol breakout' : vol.pocket_pivot ? 'pocket pivot' : 'no active breakout',
    },
  ];

  let minerviniVerdict: FrameworkResult['verdict'];
  if (minerviniBroken) minerviniVerdict = 'avoid';
  else if (trendCore && rsOk && buyTrigger) minerviniVerdict = 'buy';
  else if (trendCore && rsOk) minerviniVerdict = 'watch';
  else minerviniVerdict = 'avoid';

  // ── Pradeep Bonde / Stockbee ─────────────────────────────────────────────
  const ss = row?.sell_signals ?? {};
  const sig = ss.signals ?? {};
  const hardSell = !!(
    sig.close_below_200ma ||
    sig.stop_loss_breached ||
    sig.close_below_50ma_on_high_vol ||
    sig.down_10pct_from_entry ||
    ss.action === 'SELL' ||
    (typeof ss.severity === 'number' && ss.severity >= 2)
  );
  const softSell = !!(
    ss.action === 'REDUCE' ||
    ss.severity === 1 ||
    sig.largest_1d_decline_since_stage2 ||
    sig.largest_1w_decline_since_stage2 ||
    sig.climax_run_25pct_in_3w ||
    vol.accumulation_strength === 'distributing' ||
    vol.cmf_signal === 'outflow'
  );

  const ret1w: number | null = ss?.today_1w_return_pct ?? null;
  const ret1m: number | null = row?.dual_momentum?.return_1m ?? null;
  const ep = !!(vol.high_vol_breakout && rvol != null && rvol >= BONDE_BREAKOUT_RVOL);
  const epEarningsDriven = ep && catalystSurprisePct != null;
  const fourPctBO = dayChg != null && dayChg >= BONDE_FOURPCT_GAIN && rvol != null && rvol > BONDE_BREAKOUT_RVOL;
  const momentumBurst =
    (ret1w != null && ret1w >= BONDE_MOM_BURST_1W_PCT) || (ret1m != null && ret1m >= BONDE_MOM_BURST_1M_PCT);
  const groupStrong = row?.group_leader === true || (row?.is_laggard === false && (row?.group_rs_rank ?? 99) <= 3);
  const bondeTrigger = ep || fourPctBO || momentumBurst;
  const notExtended = dist200 == null || dist200 < EXTENDED_DIST_200_PCT;

  const bondeChecks: VerdictCheck[] = [
    {
      label: 'Episodic Pivot (earnings gap on volume)',
      ok: ep,
      detail: rvol == null ? '—' : `RVOL ${(Math.round(rvol * 100) / 100).toFixed(2)}×${epEarningsDriven ? ', earnings-driven' : ''}`,
    },
    {
      label: `4% breakout (≥${BONDE_FOURPCT_GAIN}% on >${BONDE_BREAKOUT_RVOL}× vol)`,
      ok: fourPctBO,
      detail: `${pct(dayChg)} today${rvol != null ? `, RVOL ${(Math.round(rvol * 100) / 100).toFixed(2)}×` : ''}`,
    },
    {
      label: `Momentum burst (≥${BONDE_MOM_BURST_1W_PCT}% in a week)`,
      ok: momentumBurst,
      detail: `1w ${pct(ret1w)}, 1m ${pct(ret1m)}`,
    },
    {
      label: 'Constructive distance from MAs',
      ok: notExtended,
      detail: dist200 == null ? '—' : `${pct(dist200)} above 200-MA${notExtended ? '' : ' — extended'}`,
    },
    {
      label: 'Industry / sector strength (group leader)',
      ok: groupStrong,
      detail:
        row?.group_rs_rank != null
          ? `group RS #${row.group_rs_rank}/${row?.group_size ?? '?'}${row?.group_leader ? ' · leader' : ''}`
          : '—',
    },
    {
      label: 'No anti-thesis sell signal',
      ok: !hardSell && !softSell,
      detail: ss.action ? `action ${ss.action}, severity ${ss.severity ?? 0}` : '—',
    },
  ];

  let bondeVerdict: FrameworkResult['verdict'];
  if (hardSell) bondeVerdict = 'avoid';
  else if (bondeTrigger && groupStrong && !softSell) bondeVerdict = 'buy';
  else if ((bondeTrigger || groupStrong) && !softSell) bondeVerdict = 'watch';
  else if (softSell) bondeVerdict = 'watch';
  else bondeVerdict = 'avoid';

  // ── Composite ────────────────────────────────────────────────────────────
  // Anti-thesis (broken Minervini structure OR a Bonde sell signal) dominates.
  let verdict: Verdict;
  let why: string;
  if (minerviniBroken) {
    verdict = 'avoid';
    why = belowKeyMa
      ? 'Minervini: price below the 150/200-day MAs — trend template broken.'
      : `Minervini: Stage ${stage} (not a Stage-2 advance).`;
  } else if (hardSell) {
    verdict = 'avoid';
    const which = sig.close_below_200ma
      ? 'closed below the 200-day MA'
      : sig.stop_loss_breached
      ? 'stop-loss breached'
      : sig.close_below_50ma_on_high_vol
      ? 'broke the 50-day MA on high volume'
      : sig.down_10pct_from_entry
      ? 'down >10% from entry'
      : `sell action ${ss.action}`;
    why = `Bonde anti-thesis: ${which} — Minervini setup is overridden by the sell signal.`;
  } else if (minerviniVerdict === 'buy' && bondeVerdict === 'buy') {
    verdict = 'buy';
    const trig = epEarningsDriven
      ? 'Episodic Pivot'
      : fourPctBO
      ? '4% volume breakout'
      : momentumBurst
      ? 'momentum burst'
      : 'breakout';
    why = `Both frameworks confirm: Minervini trend template (RS ${rs}) + Bonde ${trig}${groupStrong ? ', group leader' : ''}.`;
  } else if (trendCore && rsOk) {
    verdict = 'watch';
    const miss = !buyTrigger ? 'no fresh pivot breakout yet' : !bondeTrigger ? 'no Bonde momentum trigger' : 'awaiting confirmation';
    why = `Minervini trend intact (RS ${rs}) but ${miss}${softSell ? ' — and a soft distribution caution is showing' : ''}.`;
  } else {
    verdict = 'avoid';
    why = 'Trend structure incomplete and no confirmed buy trigger.';
  }

  return {
    verdict,
    label: LABEL[verdict],
    tone: TONE[verdict],
    why,
    minervini: { name: 'Minervini SEPA', verdict: minerviniVerdict, checks: minerviniChecks },
    bonde: { name: 'Bonde / Stockbee', verdict: bondeVerdict, checks: bondeChecks },
  };
}
