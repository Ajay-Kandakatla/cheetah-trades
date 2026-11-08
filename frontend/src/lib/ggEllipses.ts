/* 🎾 GG's chart circles on the Reversal Squeeze card (spec gg-squeeze 2026-11-08, WP fe-ellipse).
 *
 * Ajay 2026-11-08, with GG's annotated TPST 5-minute chart attached: "I need something like this but
 * that big of circle for reversal squeen mainly on the cart itself also increase the width of the
 * reversal sqeeze chart to show more bars" · "This is from Gajjals".
 *
 * The server (chart_maps/gajjala/squeeze_marks.py) sends `tile.ellipses`: one item per structure the
 * detector already found — {kind, from_t, to_t, lo, hi, label, note, tone}. This module is the pure
 * geometry: it joins the two stamps to the served bars by the FULL stamp (an intraday card's bars are
 * "%Y-%m-%d %H:%M"), and turns the bar span + price span into one ellipse in viewBox units.
 * Display only — nothing sorts, filters, gates or pushes on it. UNMEASURED.
 *
 * The drawing constants below are MINE (pixels, not trading numbers). */
import { barWidth, xFor, yFor, type CmBar, type CmEllipse } from './chartMaps';

type Domain = { lo: number; hi: number };

/** drawing constant (MINE): horizontal padding past the outer bars, in bar widths. */
export const ELLIPSE_PAD_X_BARS = 0.6;
/** drawing constant (MINE): vertical padding above the high / below the low, viewBox units. */
export const ELLIPSE_PAD_Y = 3;
/** drawing constant (MINE): the smallest radius, so a one-bar entry circle stays visible. */
export const ELLIPSE_MIN_R = 5;
/** drawing constant (MINE): the chart label's font size, viewBox units. */
export const ELLIPSE_LABEL_FS = 8;
/** GG's own pens: magenta for the structure he circles, the house green for the entry.
 *  There is NO red tone — "CLOSE OR ADD OPPORTUNITY" is his discretion (HIS CALL #1). */
export const ELLIPSE_STROKE: Record<string, string> = {
  structure: '#e879f9' /* GG's magenta pen */,
  entry: 'var(--positive, #22c55e)',
};

/** The kinds whose label sits UNDER the ellipse (the run up and the base at the top);
 *  every other kind is labelled above it. */
const LABEL_BELOW = new Set(['run', 'base']);

/** A served tone the chart knows, else 'structure' — an unknown tone never invents a colour. */
export function ellipseTone(tone: string | null | undefined): string {
  return tone && Object.prototype.hasOwnProperty.call(ELLIPSE_STROKE, tone) ? tone : 'structure';
}

export function ellipseStroke(tone: string | null | undefined): string {
  return ELLIPSE_STROKE[ellipseTone(tone)];
}

/** FULL-stamp join (b.t === t); -1 when absent. A date-only key never matches an intraday bar. */
export function stampIndex(bars: CmBar[], t: string): number {
  if (!t || !bars || !bars.length) return -1;
  return bars.findIndex((b) => b.t === t);
}

export type EllipseGeom = {
  cx: number; cy: number; rx: number; ry: number;
  labelX: number; labelY: number; above: boolean;
};

/** One served structure → one ellipse around its bars and its price range.
 *  null when either stamp is off the served bars or lo/hi is not a finite number. */
export function ellipseGeom(
  e: CmEllipse, bars: CmBar[], domain: Domain, H: number, padY: number, W: number, padR: number,
): EllipseGeom | null {
  if (!e || !bars || !bars.length) return null;
  const a = stampIndex(bars, e.from_t);
  const b = stampIndex(bars, e.to_t);
  if (a < 0 || b < 0) return null;
  const lo = typeof e.lo === 'number' ? e.lo : NaN;
  const hi = typeof e.hi === 'number' ? e.hi : NaN;
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return null;
  const i0 = Math.min(a, b);
  const i1 = Math.max(a, b);
  const n = bars.length;
  const bw = barWidth(n, W, padR);
  const x0 = xFor(i0, n, W, padR);
  const x1 = xFor(i1, n, W, padR);
  const yTop = yFor(Math.max(lo, hi), domain, H, padY);
  const yBot = yFor(Math.min(lo, hi), domain, H, padY);
  const cx = (x0 + x1) / 2;
  const cy = (yTop + yBot) / 2;
  const rx = Math.max((x1 - x0) / 2 + bw * (0.5 + ELLIPSE_PAD_X_BARS), ELLIPSE_MIN_R);
  const ry = Math.max((yBot - yTop) / 2 + ELLIPSE_PAD_Y, ELLIPSE_MIN_R);
  const above = !LABEL_BELOW.has(String(e.kind));
  const rawY = above ? cy - ry - 2 : cy + ry + 8;
  const labelY = Math.min(Math.max(rawY, padY + 7), H - padY - 2);
  const len = String(e.label || '').length;
  const plotW = Math.max(W - padR, 1);
  const half = len * 2.3;
  const labelX = half * 2 >= plotW ? plotW / 2 : Math.min(Math.max(cx, half), plotW - half);
  return { cx, cy, rx, ry, labelX, labelY, above };
}

/** The hover <title>: "label · HH:MM–HH:MM · note" — the clock only when both stamps share a date,
 *  else the full stamps. The note (GG's own words, quoted) lives HERE only, never on the chart face. */
export function ellipseTitle(e: CmEllipse): string {
  const from = String(e.from_t || '');
  const to = String(e.to_t || '');
  const same = from.length > 10 && from.slice(0, 10) === to.slice(0, 10);
  const span = same ? `${from.slice(11, 16)}–${to.slice(11, 16)}` : `${from}–${to}`;
  return [e.label || e.kind, span, e.note].filter((s) => s != null && String(s) !== '').join(' · ');
}
