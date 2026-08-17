/* zoneChart — pure helpers for the candlestick zone map.
 *
 * Ajay 2026-08-16: *"is there any way we can use trading view charts? ... I
 * wanna be able to hover on the pricing at for some points"* and, a moment
 * later, *"can you also add volume please"*.
 *
 * The answer was lightweight-charts — the engine TradingView open-sourced,
 * already a dependency here. This file holds every number the chart derives, so
 * the component stays a thin wrapper around the library and the arithmetic is
 * testable without a canvas. Same split PatternChart.tsx argues for in its
 * header: "every number drawn here comes from pure, tested functions".
 *
 * Backend: GET /supply-demand/zone-map/{symbol} (supply_demand/demand_reentry.py).
 * Configured price-structure read — NOT a book method, NOT advice.
 */
import type { Plan, Zone, ZoneMapPayload } from './zonePlan';

/** One bar as the backend sends it. `open/high/low/volume` were added
 *  2026-08-16; a payload cached before that has only `date` + `close`. */
export type SeriesBar = {
  date: string;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close: number;
  volume?: number | null;
};

export type Candle = {
  time: string;
  open: number; high: number; low: number; close: number;
};

export type VolumeBar = { time: string; value: number; color: string };

const ok = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/** Bars → candlesticks, in the order lightweight-charts wants them.
 *
 *  A bar missing open/high/low degenerates to a doji at the close rather than
 *  being dropped: a hole would shift every later bar and silently mis-place the
 *  bands against the price. That is the failure mode worth avoiding — a flat
 *  candle is visibly odd, a shifted chart is not.
 */
export function toCandles(series: SeriesBar[] | undefined | null): Candle[] {
  if (!Array.isArray(series)) return [];
  const out: Candle[] = [];
  let prevTime = '';
  for (const b of series) {
    if (!b || typeof b.date !== 'string' || !b.date || !ok(b.close)) continue;
    // The library requires strictly ascending, unique times.
    if (b.date <= prevTime) continue;
    prevTime = b.date;
    const close = b.close;
    const open = ok(b.open) ? b.open : close;
    const hi = ok(b.high) ? b.high : Math.max(open, close);
    const lo = ok(b.low) ? b.low : Math.min(open, close);
    out.push({
      time: b.date,
      open,
      close,
      // Clamp rather than trust: a high below the body draws an inverted wick.
      high: Math.max(hi, open, close),
      low: Math.min(lo, open, close),
    });
  }
  return out;
}

export const VOL_UP = 'rgba(34,197,94,0.38)';
export const VOL_DOWN = 'rgba(239,68,68,0.38)';

/** Volume histogram, coloured by the bar's own direction.
 *
 *  Bars with no volume are omitted, not zeroed — a zero column reads as "nobody
 *  traded", which is a claim we cannot make from a missing field.
 */
export function toVolumeBars(series: SeriesBar[] | undefined | null): VolumeBar[] {
  if (!Array.isArray(series)) return [];
  const out: VolumeBar[] = [];
  let prevTime = '';
  for (const b of series) {
    if (!b || typeof b.date !== 'string' || !b.date || b.date <= prevTime) continue;
    if (!ok(b.close)) continue;
    prevTime = b.date;
    if (!ok(b.volume) || b.volume <= 0) continue;
    const open = ok(b.open) ? b.open : b.close;
    out.push({ time: b.date, value: b.volume, color: b.close >= open ? VOL_UP : VOL_DOWN });
  }
  return out;
}

/** True when this payload predates the OHLCV change and can only draw a line. */
export function hasOhlc(series: SeriesBar[] | undefined | null): boolean {
  if (!Array.isArray(series) || !series.length) return false;
  return series.some((b) => ok(b?.open) && ok(b?.high) && ok(b?.low));
}

export function hasVolume(series: SeriesBar[] | undefined | null): boolean {
  if (!Array.isArray(series)) return false;
  return series.some((b) => ok(b?.volume) && (b.volume as number) > 0);
}

/* ── the hover readout ───────────────────────────────────────────────────── */

export type HoverRow = {
  date: string;
  open: string; high: string; low: string; close: string;
  volume: string;
  changePct: string | null;
  up: boolean;
};

function px(v: number): string {
  return `$${v.toFixed(Math.abs(v) >= 1000 ? 0 : 2)}`;
}

/** Compact volume: 1.2M, 531K. Volume is a count — never given cents. */
export function vol(v: number | null | undefined): string {
  if (!ok(v) || v < 0) return '—';
  if (v >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return String(Math.round(v));
}

/** What the tooltip shows for one hovered bar. `prevClose` drives the % change,
 *  which is the number he actually reads; without it the field is omitted
 *  rather than computed against the bar's own open, which would be a different
 *  statistic wearing the same label. */
export function hoverRow(bar: Candle | null | undefined,
                        volume?: number | null,
                        prevClose?: number | null): HoverRow | null {
  if (!bar || !ok(bar.close)) return null;
  const chg = ok(prevClose) && prevClose !== 0
    ? ((bar.close - prevClose) / prevClose) * 100
    : null;
  return {
    date: bar.time,
    open: px(bar.open), high: px(bar.high), low: px(bar.low), close: px(bar.close),
    volume: vol(volume),
    changePct: chg == null ? null : `${chg > 0 ? '+' : ''}${chg.toFixed(2)}%`,
    up: bar.close >= bar.open,
  };
}

/* ── the plan drawn as price lines ───────────────────────────────────────── */

export const SUPPLY = '#ef4444';
export const DEMAND = '#22c55e';
export const NEUTRAL = '#cbd5e1';

export type PriceLineSpec = {
  price: number;
  color: string;
  title: string;
  dashed: boolean;
  bold: boolean;
};

const lvl = (v: number) => `$${v.toFixed(2)}`;

/** The BUY band, STOP, TARGET and NOW as labelled price lines.
 *
 *  These are the levels he would type into a broker, so they carry cents
 *  regardless of the stock's price — `money()` rounds $98.50 to "$99", which
 *  would be a different order.
 *
 *  ONE buy line, not two (Ajay 2026-08-17: *"There are two different buys in the
 *  NBIX stock one on chart"*). Labelling both band edges `BUY $x` printed two
 *  different prices under the same word, which reads as two competing entries
 *  rather than one range. The band's own outline already shows both edges — the
 *  price line exists for its axis LABEL, and one label carries the whole range.
 *
 *  A BROKEN band never says BUY. Same for a stop the market has already run:
 *  labelling it `STOP` implies it is still ahead of price.
 */
export function planLines(data: Pick<ZoneMapPayload,
                                     'plan' | 'entry_zone' | 'last_price' | 'zone_broken'>
                          | null | undefined): PriceLineSpec[] {
  if (!data) return [];
  const plan: Plan | null = data.plan ?? null;
  const out: PriceLineSpec[] = [];
  const broken = data.zone_broken === true;

  const ez = data.entry_zone;
  if (ez && ok(ez.lo) && ok(ez.hi)) {
    // Anchored at the band TOP, not the floor: the floor sits ~1.5% from the
    // stop and the two axis labels would land on the same pixels.
    out.push({
      price: ez.hi,
      color: broken ? NEUTRAL : DEMAND,
      title: `${broken ? 'BROKEN' : 'BUY'} ${lvl(ez.lo)}–${lvl(ez.hi)}`,
      dashed: broken,
      bold: true,
    });
  }
  if (plan && ok(plan.stop)) {
    const hit = plan.stop_recently_hit === true;
    out.push({ price: plan.stop, color: SUPPLY,
               title: `${hit ? 'STOP HIT' : 'STOP'} ${lvl(plan.stop)}`,
               dashed: true, bold: true });
  }
  if (plan && ok(plan.target)) {
    out.push({ price: plan.target as number, color: DEMAND,
               title: `TARGET ${lvl(plan.target as number)}`, dashed: true, bold: true });
  }
  if (ok(data.last_price)) {
    out.push({ price: data.last_price, color: NEUTRAL,
               title: `NOW ${lvl(data.last_price)}`, dashed: true, bold: false });
  }
  return out;
}

/* ── the bands, as the primitive wants them ──────────────────────────────── */

export type BandSpec = {
  lo: number; hi: number;
  kind: 'supply' | 'demand';
  isEntry: boolean;
};

/** Is this the band the plan actually points at?
 *
 *  The SVG version compared CLIPPED band edges by float tolerance, which made
 *  the BUY highlight a numeric coincidence. Nothing is clipped on a real price
 *  scale, so the comparison is against the entry zone's own edges.
 */
function sameBand(z: Zone, ez: Zone | null | undefined): boolean {
  if (!ez) return false;
  return Math.abs(z.lo - ez.lo) < 0.005 && Math.abs(z.hi - ez.hi) < 0.005;
}

/** Every band worth drawing, entry band marked. Zero-height and non-finite
 *  bands are dropped — they render as a hairline that reads like a price level
 *  rather than a zone.
 *
 *  A BROKEN band is not marked as the entry band. `isEntry` is what gives a band
 *  the strong fill and the outline on both edges — the visual claim "this is the
 *  plan". It still draws as demand, because it still is one; it just stops being
 *  advertised. The `BROKEN $lo–$hi` price line from `planLines` names it.
 */
export function bandsFor(data: Pick<ZoneMapPayload,
                                    'supply_zones' | 'demand_zones' | 'entry_zone' | 'zone_broken'>
                         | null | undefined): BandSpec[] {
  if (!data) return [];
  const ez = data.zone_broken === true ? null : data.entry_zone;
  const take = (zones: Zone[] | undefined, kind: 'supply' | 'demand'): BandSpec[] =>
    (zones || [])
      .filter((z) => z && ok(z.lo) && ok(z.hi) && z.hi > z.lo)
      .map((z) => ({ lo: z.lo, hi: z.hi, kind, isEntry: kind === 'demand' && sameBand(z, ez) }));
  return [...take(data.supply_zones, 'supply'), ...take(data.demand_zones, 'demand')];
}

/** Off-exchange block prints, as price markers. Kept here so the component
 *  never does arithmetic on notionals. */
export function blockRadius(dollars: number, maxDollars: number): number {
  if (!ok(dollars) || !ok(maxDollars) || maxDollars <= 0) return 0;
  return 2.2 + 3.6 * Math.sqrt(Math.max(0, dollars) / maxDollars);
}
