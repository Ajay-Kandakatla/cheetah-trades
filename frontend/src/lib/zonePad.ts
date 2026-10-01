/* zonePad — the 🧱 1% pad under demand floors and support key levels, as the
 * charts and the card ladder draw it (Ajay 2026-09-30).
 *
 * His ask, verbatim: "Also increase our Demand zone and key levels sizes by 1%.
 * becuz Generally we are missing this, I been noticing if the demand zone or key
 * level is 133, it holding at 132. My theory is MMs know stoplosses are beyond
 * 133."
 *
 * The pad is SERVED: backend/supply_demand/level_pad.py (the one number is
 * sd_liquidity.STOP_SHELF_PCT) puts `pad_lo` on a padded demand band and
 * `pad_price` on a padded support-low key line. The drawn edge never moves; the
 * pad is the lighter strip UNDER it. This file does NO arithmetic on prices —
 * comparisons only. A missing, non-finite, non-number or not-below-the-edge pad
 * draws nothing, never a guessed one. UNMEASURED: his rule, display only.
 */

/** Band kinds the backend pads (level_pad.PAD_BAND_KINDS = demand; the chart
 *  tiles serve the board's own band as `board_demand`). Anything else — supply,
 *  board_supply, fvg, base — never draws a pad even if a key leaks through. */
export const PAD_KINDS: ReadonlyArray<string> = ['demand', 'board_demand'];

/** Key-line tones that can carry a served pad (🔑 key / key_broken). */
export const KEY_PAD_TONES: ReadonlyArray<string> = ['key', 'key_broken'];

export type PadStrip = { lo: number; hi: number };

const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/** The pad strip under a demand band: {lo: pad_lo, hi: the drawn lo}, or null.
 *  Only for a padded kind, a finite served `pad_lo` strictly below a finite
 *  positive `lo`. */
export function padStrip(
  b: { kind?: unknown; lo?: unknown; hi?: unknown; pad_lo?: unknown } | null | undefined,
): PadStrip | null {
  if (!b || typeof b !== 'object') return null;
  if (!PAD_KINDS.includes(String(b.kind ?? ''))) return null;
  const lo = b.lo;
  const pad = b.pad_lo;
  if (!num(lo) || !num(pad)) return null;
  if (!(pad > 0) || !(pad < lo)) return null;
  return { lo: pad, hi: lo };
}

/** The pad strip under a 🔑 support-low line: {lo: pad_price, hi: price}, or
 *  null. The backend serves `pad_price` only on a padded support low; a pad
 *  above the level (never served) or on a non-key tone draws nothing. */
export function keyPadStrip(
  l: { tone?: unknown; price?: unknown; pad_price?: unknown } | null | undefined,
): PadStrip | null {
  if (!l || typeof l !== 'object') return null;
  if (!KEY_PAD_TONES.includes(String(l.tone ?? ''))) return null;
  const price = l.price;
  const pad = l.pad_price;
  if (!num(price) || !num(pad)) return null;
  if (!(pad > 0) || !(pad < price)) return null;
  return { lo: pad, hi: price };
}

/** A strip clipped to the drawn price domain (comparisons only), or null when
 *  none of it is on the chart. */
export function clipStrip(
  s: PadStrip | null | undefined, d: { lo: number; hi: number } | null | undefined,
): PadStrip | null {
  if (!s || !d || !num(d.lo) || !num(d.hi)) return null;
  const lo = s.lo > d.lo ? s.lo : d.lo;
  const hi = s.hi < d.hi ? s.hi : d.hi;
  return hi > lo ? { lo, hi } : null;
}

/** "1%" from the served `pad_pct`, or '' when it is not served — never typed. */
export function padPctText(pct: unknown): string {
  return num(pct) && pct > 0 ? `${pct}%` : '';
}

/** The strip's hover/screen-reader title:
 *  "Support pad 131.67–133.00 — 1% under the drawn edge, where stops sit". */
export function padTitle(
  name: string, strip: PadStrip, pct?: unknown,
): string {
  const p = padPctText(pct);
  return `${name} pad ${strip.lo.toFixed(2)}–${strip.hi.toFixed(2)} — `
    + `${p ? `${p} ` : ''}under the drawn edge, where stops sit`;
}
