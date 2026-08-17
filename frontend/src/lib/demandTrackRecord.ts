/* Back in Demand — reading the live track record.
 *
 * Ajay 2026-08-17: "Can you maintain history of our In deman page please.. I
 * think its working out.. I saw CIEN you recommended is bouncing out of the
 * zone now.. I would imagine the same with other stocks. Want you to track it"
 *
 * The pure half of the surface, so the honesty rules are testable without a
 * DOM. Two of them do the real work:
 *
 *   1. An empty ledger must SAY it is empty. Recording began 2026-08-17, so
 *      for the first weeks there is nothing graded — and "0.0% win rate" is a
 *      claim, not a blank. `verdict` returns 'empty' rather than a number.
 *   2. Excess-vs-SPY leads, never the win rate. Everything measured about this
 *      board says a dip-buying rule in a rising tape shows profit with or
 *      without skill, and that bracket geometry makes raw win% unreadable
 *      across trades (the 2026-07-10 pattern audit).
 */

export type TrackRecord = {
  ok?: boolean;
  since?: string | null;
  through?: string | null;
  symbols?: number;
  open?: number;
  never_filled?: number;
  raced?: number;
  wins?: number;
  losses?: number;
  expired?: number;
  win_pct?: number | null;
  expectancy_pct?: number | null;
  excess_vs_spy_pct?: number | null;
  beat_spy_pct?: number | null;
  median_rr?: number | null;
  median_bars_held?: number | null;
  runs?: BoardRun[];
};

export type BoardRun = {
  et_date: string;
  n: number;
  universe?: string;
  symbols?: string[];
  entered?: string[];
  dropped?: string[];
};

/** Below this the numbers are anecdote. The board produces ~10-20 names a day
 *  but an episode can run 60 bars, so a usable sample is months away — saying
 *  so is the point. */
export const THIN_SAMPLE = 20;

export type Verdict = 'empty' | 'thin' | 'ready';

export function verdict(t: TrackRecord | null | undefined): Verdict {
  const raced = t?.raced ?? 0;
  if (!t?.ok || raced <= 0) return 'empty';
  return raced < THIN_SAMPLE ? 'thin' : 'ready';
}

/** A signed percentage, or an em dash. Never "0.0%" for a missing value —
 *  that reads as a measurement that came back flat. */
export function pct(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${v > 0 ? '+' : ''}${v.toFixed(digits)}%`;
}

export function tone(v: number | null | undefined): 'good' | 'bad' | 'flat' {
  if (v === null || v === undefined || Number.isNaN(v)) return 'flat';
  return v > 0 ? 'good' : v < 0 ? 'bad' : 'flat';
}

/** The one-line answer to "is it working". Deliberately leads with excess. */
export function headline(t: TrackRecord | null | undefined): string {
  const v = verdict(t);
  if (v === 'empty') {
    const runs = t?.runs?.length ?? 0;
    return runs > 0
      ? `Recording since ${t?.since ?? t?.runs?.[runs - 1]?.et_date ?? '—'} — no episode has finished racing yet`
      : 'Recording starts with the next scan — nothing graded yet';
  }
  const ex = t?.excess_vs_spy_pct;
  const verb = ex === null || ex === undefined ? 'unmeasured against'
    : ex > 0 ? 'ahead of' : ex < 0 ? 'behind' : 'level with';
  const lead = `${pct(ex)} vs SPY over the same days (${verb} the benchmark)`;
  return v === 'thin' ? `${lead} — only ${t?.raced} finished, too few to lean on` : lead;
}

/** Names the board is still holding an opinion on, newest board first, so
 *  "what did we say about CIEN" is answerable without a per-symbol fetch. */
export function latestBoard(t: TrackRecord | null | undefined): BoardRun | null {
  const runs = t?.runs ?? [];
  return runs.length ? runs[0] : null;
}

/** Churn worth reading: the days something actually changed. A board that
 *  repeats yesterday's list tells you nothing and should not take up a row. */
export function churnRuns(t: TrackRecord | null | undefined, limit = 10): BoardRun[] {
  return (t?.runs ?? [])
    .filter((r) => (r.entered?.length ?? 0) > 0 || (r.dropped?.length ?? 0) > 0)
    .slice(0, limit);
}
