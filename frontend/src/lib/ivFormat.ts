/* ivFormat — pure formatting for the implied-volatility read, shared by the
 * nav IvBadge and the /market-gauge IV card (Ajay 2026-09-06). */
import type { MarketIv } from '../hooks/useMarketIv';

/** 1 → "1st", 2 → "2nd", 11 → "11th", 22 → "22nd", 100 → "100th". */
export function ordinal(n: number): string {
  const v = Math.round(n);
  const mod100 = Math.abs(v) % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${v}th`;
  switch (Math.abs(v) % 10) {
    case 1: return `${v}st`;
    case 2: return `${v}nd`;
    case 3: return `${v}rd`;
    default: return `${v}th`;
  }
}

/** "▲0.2" / "▼1.3" once the day change is at least a tenth of a point; '' below. */
export function ivArrow(chg: number | null | undefined): string {
  if (chg == null || !Number.isFinite(chg) || Math.abs(chg) < 0.1) return '';
  return `${chg > 0 ? '▲' : '▼'}${Math.abs(chg).toFixed(1)}`;
}

/** The regime word — the backend label first, else the key capitalised. */
export function ivRegimeWord(iv: Pick<MarketIv, 'regime' | 'regime_label'>): string {
  if (iv.regime_label) return iv.regime_label;
  if (!iv.regime) return '';
  return iv.regime.charAt(0).toUpperCase() + iv.regime.slice(1);
}

/** "Fri" for a YYYY-MM-DD as-of (local-date parse so it never rolls a day). */
export function asOfDay(asOf: string | null | undefined): string {
  if (!asOf) return '';
  const d = new Date(`${asOf}T00:00:00`);
  if (Number.isNaN(d.getTime())) return asOf;
  return d.toLocaleDateString('en-US', { weekday: 'short' });
}

export function fmtRatio(v: number | null | undefined): string {
  return v == null || !Number.isFinite(v) ? '—' : v.toFixed(2);
}

/** The full one-line read for the badge title / aria-label:
 *  "VIX 14.5 (▲0.2) · Calm · 5th pct of the year · 9D/30D 1.16 ·
 *   30D/3M 0.71 contango · VVIX 84 · as of Fri — <read>" */
export function ivTitle(iv: MarketIv): string {
  const parts: string[] = [];
  if (iv.vix != null) {
    const arrow = ivArrow(iv.chg);
    parts.push(`VIX ${iv.vix.toFixed(1)}${arrow ? ` (${arrow})` : ''}`);
  }
  const word = ivRegimeWord(iv);
  if (word) parts.push(word);
  if (iv.pct_252 != null) parts.push(`${ordinal(iv.pct_252)} pct of the year`);
  const t = iv.term;
  if (t && t.ratio_9d_30d != null) parts.push(`9D/30D ${t.ratio_9d_30d.toFixed(2)}`);
  if (t && t.ratio_30d_3m != null) {
    parts.push(`30D/3M ${t.ratio_30d_3m.toFixed(2)}${t.shape ? ` ${t.shape}` : ''}`);
  }
  if (iv.vvix != null) parts.push(`VVIX ${Math.round(iv.vvix)}`);
  const day = asOfDay(iv.as_of);
  if (day) parts.push(`as of ${day}`);
  const head = parts.join(' · ');
  return iv.read ? `${head} — ${iv.read}` : head;
}
