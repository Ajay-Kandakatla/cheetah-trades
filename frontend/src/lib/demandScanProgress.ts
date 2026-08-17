/* demandScanProgress — every number the Back in Demand progress panel shows.
 *
 * Ajay 2026-08-17, looking at the tab mid-scan:
 *   "I am looking at this and its hard to tell if its scanning or now"
 *
 * The page said `0 in demand · 0/0 scanned` for the whole ~2-3 minutes of a
 * cold S&P 1500 pass, because those counters only exist in the FINAL payload.
 * A static "scanning in the background…" sentence is indistinguishable from a
 * hung request.
 *
 * This is NOT the SEPA scan stream (lib/../hooks/useSepaScanStream). That one
 * watches /sepa/scan/stream — a different scan over a different universe, which
 * is why the Chart Maps panel could not simply be reused here. The Back in
 * Demand board runs its own pass and publishes its own counter.
 *
 * Backend: GET /supply-demand/demand-reentry/progress
 *          (supply_demand/demand_reentry.py :: progress_for)
 *
 * Pure so the arithmetic is testable without a DOM or a network.
 */

/** Phases the backend publishes, in order. `idle` means nothing is running. */
export type DemandScanPhase =
  | 'idle' | 'universe' | 'scanning' | 'enriching' | 'done' | 'failed';

export type DemandScanProgress = {
  universe_key?: string;
  universe_label?: string | null;
  phase: DemandScanPhase;
  running?: boolean;
  current?: number;
  total?: number;
  hits?: number;
  errors?: number;
  scanned?: number;
  symbol?: string | null;
  elapsed_sec?: number | null;
  eta_sec?: number | null;
  pct?: number | null;
  took_sec?: number | null;
  error?: string | null;
};

const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/** "1m 40s" / "12s". Coarse on purpose: a scan ETA that reads "1m 39.4s"
 *  implies a precision the projection does not have. */
export function fmtEta(sec: number | null | undefined): string | null {
  if (!num(sec) || sec < 0) return null;
  if (sec < 10) return 'a few seconds';
  if (sec < 60) return `${Math.round(sec / 5) * 5}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round((sec - m * 60) / 10) * 10;
  return s > 0 && s < 60 ? `${m}m ${s}s` : `${m}m`;
}

const PHASE_LABEL: Record<DemandScanPhase, string> = {
  idle: 'idle',
  universe: 'loading names',
  scanning: 'scanning',
  enriching: 'enriching',
  done: 'done',
  failed: 'failed',
};

/* The CSS lives in styles.css under .sepa-progress__phase--*. Only a few
 * modifiers are defined there, so phases map onto the ones that exist rather
 * than inventing class names with no rule behind them. */
const PHASE_CLASS: Record<DemandScanPhase, string> = {
  idle: 'scanning',
  universe: 'warming_names',
  scanning: 'scanning',
  enriching: 'enriching',
  done: 'done',
  failed: 'error',
};

export type ProgressView = {
  /** Should the panel render at all? */
  visible: boolean;
  phase: DemandScanPhase;
  phaseLabel: string;
  phaseClass: string;
  /** 0-100, clamped. Null when the total is not known yet — the bar then shows
   *  an indeterminate state rather than a confident 0%. */
  pct: number | null;
  /** "412 / 1,500 names" */
  countLabel: string | null;
  /** The ticker being analysed right now. */
  symbol: string | null;
  hits: number;
  /** "~1m 40s left" */
  etaLabel: string | null;
  elapsedLabel: string | null;
  /** The one-line status sentence. */
  message: string;
  isError: boolean;
  isDone: boolean;
};

/** Everything the panel renders, derived once.
 *
 *  `universeLabel` is passed in rather than trusted from the payload alone: the
 *  backend only knows the label AFTER the constituent lists resolve, and the
 *  first seconds of a cold scan are exactly when the page most needs to name
 *  what it is doing.
 */
export function progressView(p: DemandScanProgress | null | undefined,
                             universeLabel?: string | null,
                             opts: { running?: boolean } = {}): ProgressView {
  // `running` is what the BOARD says (its `warming` flag) and it is the more
  // reliable of the two: the board payload arrives with the page, while the
  // first progress poll is up to a poll-interval behind it and may never land
  // at all if that endpoint is unhappy. Without this the panel renders nothing
  // for the first second and a half of every scan — silence, which is the
  // precise complaint being fixed.
  const raw: DemandScanPhase = (p?.phase && p.phase in PHASE_LABEL)
    ? p.phase : 'idle';
  const phase: DemandScanPhase =
    (raw === 'idle' && opts.running) ? 'universe' : raw;
  const total = num(p?.total) ? (p!.total as number) : 0;
  const current = num(p?.current) ? (p!.current as number) : 0;
  const hits = num(p?.hits) ? (p!.hits as number) : 0;
  const name = p?.universe_label || universeLabel || 'the universe';

  // Only claim a percentage once the denominator is real. During `universe` the
  // constituent lists are still being fetched and total is genuinely unknown —
  // showing 0% there reads as "stuck at zero", the exact impression to avoid.
  const pct = total > 0
    ? Math.max(0, Math.min(100, Math.round((current / total) * 1000) / 10))
    : null;

  const eta = fmtEta(p?.eta_sec);
  const isError = phase === 'failed';
  const isDone = phase === 'done';

  let message: string;
  if (isError) {
    message = `Scan of ${name} failed${p?.error ? ` — ${p.error}` : ''}.`;
  } else if (isDone) {
    const secs = num(p?.took_sec) ? ` in ${p!.took_sec}s` : '';
    message = `Scanned ${name}${secs} — ${hits} in demand.`;
  } else if (phase === 'universe') {
    message = `Loading the ${name} constituent list…`;
  } else if (phase === 'enriching') {
    message = `Pulling tape for the top rows — ${hits} in demand.`;
  } else {
    message = `Scanning ${name} for demand-zone pullbacks…`;
  }

  return {
    visible: phase !== 'idle',
    phase,
    phaseLabel: PHASE_LABEL[phase],
    phaseClass: PHASE_CLASS[phase],
    pct,
    countLabel: total > 0
      ? `${current.toLocaleString('en-US')} / ${total.toLocaleString('en-US')}`
      : null,
    symbol: p?.symbol || null,
    hits,
    etaLabel: (!isDone && !isError && eta) ? `~${eta} left` : null,
    elapsedLabel: num(p?.elapsed_sec) ? `${Math.round(p!.elapsed_sec as number)}s elapsed` : null,
    message,
    isError,
    isDone,
  };
}
