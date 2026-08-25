/* ema — exponential moving averages for chart overlays.
 *
 * Ajay 2026-08-24: "We need EMA to be there ... so that I can do Intraday and
 * do more deterministic trading" — 9/21 EMAs as the trend/context layer over
 * the supply-demand zones ("only Supply demand based zones are not enough").
 *
 * The backend already computes an EMA read per scan (orderflow/signals.py
 * intraday_ema_read, 5-min closes); THIS is the chart-line version, computed
 * from the exact bars the chart is already drawing so the two can never show
 * different candles than they average.
 *
 * Convention (standard, matches the backend): seed with the SMA of the first
 * `period` values, then EMA_t = α·close_t + (1−α)·EMA_{t−1}, α = 2/(period+1).
 * Values before the seed are null — a line drawn from bar 0 would be an SMA
 * pretending to be an EMA precisely where the chart has least data.
 */

export const EMA_FAST = 9;
export const EMA_SLOW = 21;

export function emaAlpha(period: number): number {
  return 2 / (period + 1);
}

/** EMA over `values`; null until the seed SMA is complete. PURE.
 *  Non-finite inputs poison an average silently, so they are rejected loudly —
 *  a chart fed a NaN close has a data bug upstream that must not be smoothed
 *  over by the smoothing function. */
export function emaSeries(values: number[], period: number): (number | null)[] {
  if (!Number.isInteger(period) || period < 1) {
    throw new Error(`ema period must be a positive integer, got ${period}`);
  }
  const out: (number | null)[] = new Array(values.length).fill(null);
  if (values.length < period) return out;

  const a = emaAlpha(period);
  let acc = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (!Number.isFinite(v)) throw new Error(`non-finite value at index ${i}`);
    if (i < period) {
      acc += v;
      if (i === period - 1) out[i] = acc / period;   // SMA seed
      continue;
    }
    out[i] = a * v + (1 - a) * (out[i - 1] as number);
  }
  return out;
}

/** One incremental step: the EMA if the CURRENT bar's close were `price`,
 *  given the previous bar's EMA. Used to tick the last point live without
 *  recomputing the series on every SSE price. PURE. */
export function emaStep(prevEma: number, price: number, period: number): number {
  const a = emaAlpha(period);
  return a * price + (1 - a) * prevEma;
}
