/* volumePane — the shared volume read for every chart (2026-10-13).
 *
 * Ajay: "show me volume on our charts please thats missing I wanna see it
 * like green and red volume ... Which means there is a sudden demand in the
 * stock that is easily visible like this." His call: a bar is green when the
 * close is at or above the open, red otherwise (the candle above it), plus a
 * thin 50-bar simple average of volume — on EVERY chart.
 *
 * Four surfaces draw volume: the Chart Maps SVG tile (PatternChart), the live
 * lightweight-charts candles (LiveCandlesChart), the zone chart (ZoneChart
 * via lib/zoneChart) and the day-trading / scalping SVG (IntradayChart). They all read their colour, their average and its length
 * from here, so a bar can never be green on one chart and red on another.
 *
 * Display only. The average is a reference line for the eye — no gate, no
 * alert and no board reads it.
 */

/** Up / down volume. 0.7 alpha so a column reads at tile size; the old 0.38
 *  sat so far into the background that a demand bar did not stand out. */
export const VOL_UP = 'rgba(34,197,94,0.7)';
export const VOL_DOWN = 'rgba(239,68,68,0.7)';

/** His number: the 50-bar simple average of volume (2026-10-13). */
export const VOLUME_SMA_LEN = 50;

/** Grey-white, thin — the thinkorswim VolumeAvg look. Neither green nor red,
 *  so the line is never mistaken for a bar. */
export const VOLUME_SMA_COLOR = 'rgba(226,232,240,0.85)';

/** The share of an SVG tile the volume pane takes, bottom of the chart. */
export const VOL_PANE_FRAC = 0.22;

/** Units between the lowest candle and the tallest volume column. */
const VOL_PANE_GAP = 4;

const fin = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);

/** The bar's colour: green when close >= open (a doji is green, exactly like
 *  the candle body above it), red otherwise. null when either price is not a
 *  finite number — the caller draws nothing rather than guessing a side. */
export function volumeColor(open: number | null | undefined,
                            close: number | null | undefined): string | null {
  if (!fin(open) || !fin(close)) return null;
  return close >= open ? VOL_UP : VOL_DOWN;
}

/** Simple moving average of volume over `n` bars.
 *
 *  One output per input. The first n-1 positions are null — the warm-up, NOT
 *  zero: a zero average would draw a line along the floor claiming nobody
 *  traded. A window holding any missing / negative / non-finite value is null
 *  too, so a hole in the data is a gap in the line, never a dip. A zero volume
 *  is a real number and counts as zero. */
export function volumeSma(values: ReadonlyArray<number | null | undefined>,
                          n: number = VOLUME_SMA_LEN): (number | null)[] {
  const vals = Array.isArray(values) ? values : [];
  const out: (number | null)[] = new Array(vals.length).fill(null);
  if (!Number.isInteger(n) || n < 1) return out;
  for (let i = n - 1; i < vals.length; i++) {
    let sum = 0;
    let ok = true;
    for (let j = i - n + 1; j <= i; j++) {
      const v = vals[j];
      if (!fin(v) || v < 0) { ok = false; break; }
      sum += v;
    }
    if (ok) out[i] = sum / n;
  }
  return out;
}

/** The window the tile actually uses: 50, or every bar it has when it has
 *  fewer (an intraday frame, a fresh IPO). */
export function volumeSmaWindow(nBars: number): number {
  return Math.max(1, Math.min(VOLUME_SMA_LEN, Math.floor(nBars) || 0));
}

/** What the average line says it is — the short-window case says so. */
export function volumeSmaTitle(win: number, nBars: number): string {
  return win < VOLUME_SMA_LEN
    ? `average volume over ${win} bars (only ${nBars} bars on this chart; ${VOLUME_SMA_LEN} wanted)`
    : `${VOLUME_SMA_LEN}-bar simple average volume`;
}

export type VolumePaneLayout = {
  /** The height the PRICE mapping uses (yFor / priceAt / priceTicks). */
  priceH: number;
  /** Top and bottom of the volume columns, in viewBox units. */
  volTop: number;
  volBot: number;
};

/** Split an SVG tile into price (top) and volume (bottom). With no volume the
 *  price pane keeps the whole height, so a tile without `v` draws exactly as
 *  it did before this change. The volume pane sits inside the bottom padding
 *  line, above the month row. */
export function volumePaneLayout(height: number, padY: number, hasVolume: boolean): VolumePaneLayout {
  if (!hasVolume || !fin(height) || height <= 0) {
    return { priceH: height, volTop: height - padY, volBot: height - padY };
  }
  const volBot = height - padY;
  const volTop = volBot - Math.round(height * VOL_PANE_FRAC);
  return { priceH: volTop - VOL_PANE_GAP + padY, volTop, volBot };
}
