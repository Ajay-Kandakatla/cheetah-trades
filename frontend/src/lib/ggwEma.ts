/* 👀 Gajjala's Watch LIVE — the 9 / 21 EMA step on the forming bar (2026-11-16, watch-live spec §3.4, WP-C).
 *
 * Ajay 2026-11-16: "Realtime updates.. Like the 1 min chart I need it to be live live.. per sec change".
 *
 * The ONE EMA is the backend's `orderflow.signals.ema` = pandas `ewm(span, adjust=False).mean()`. This file re-states
 * THAT recursion (never lib/ema's SMA-seeded 2/(period+1) chart EMA): alpha from pandas' com → alpha conversion, the
 * normalised step, and pandas' equal-value guard (when the close equals the running value the value is kept as is).
 * It is NOT bit-identical to the server in the raw double — pandas' compiled kernel fuses the multiply-add on the
 * server's CPU and JS cannot (spec §1.5: ≤ 1 ulp) — and it equals the server at the server's own 6-dp precision
 * (bars._masked_ema rounds to 6). Pinned two-sided against backend/tests/fixtures/gajjala/ema_step_golden_2026_11_16.json.
 * Display only, and drawn only when GGW_LIVE_EMA_TIP is on (HIS CALL #1 — ON since 11-16). Composes no word. */

/** pandas' alpha for a span: com = (span − 1) / 2, alpha = 1 / (1 + com). */
export function ggwEmaAlpha(span: number): number {
  return 1 / (1 + (span - 1) / 2);
}

/** One adjust=False step: the normalised weighted mean of the running value and the close; the running value itself
 *  when the close equals it (pandas' `if weighted != cur` guard). */
export function ggwEmaStep(prev: number, close: number, span: number): number {
  if (prev === close) return prev;
  const a = ggwEmaAlpha(span);
  return ((1 - a) * prev + a * close) / ((1 - a) + a);
}

/** 6 dp — the precision the server serves its curves at (bars._masked_ema). */
export function ggwRound6(x: number): number {
  return Number.isFinite(x) ? Number(x.toFixed(6)) : x;
}

/** The chain from the served UNROUNDED tail over the FE-held closes (closed-by-FE bars, then the forming one): each
 *  step chains from the previous UNROUNDED value; each output is rounded to 6 dp for display. */
export function ggwEmaTips(tail: number, closes: ReadonlyArray<number>, span: number): number[] {
  const out: number[] = [];
  let t = tail;
  for (const c of closes) {
    t = ggwEmaStep(t, c, span);
    out.push(ggwRound6(t));
  }
  return out;
}
