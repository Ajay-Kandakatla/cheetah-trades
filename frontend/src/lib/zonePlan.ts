/* zonePlan — pure helpers for the supply/demand zone map + trade plan.
 *
 * Ajay 2026-08-13: "I would like to see the supply and demand zones drawn out
 * and the entry and exit written on these."
 *
 * Backend: supply_demand/demand_reentry.py (GET /supply-demand/zone-map/{sym},
 * GET /supply-demand/demand-reentry). Everything here is pure so the drawing
 * component stays dumb and the numbers are testable.
 *
 * NOT a book method and NOT advice — a configured price-structure read.
 */

export type Zone = {
  kind: 'supply' | 'demand';
  lo: number; hi: number; mid: number;
  touches: number; volume: number;
  bars_since_test: number;
  strength: number;
  in_price?: boolean;
};

export type Plan = {
  entry_low: number; entry_high: number; entry_ref: number;
  stop: number; risk_pct: number | null;
  target: number | null; reward_pct: number | null;
  rr: number | null;
  risk_exceeds_max: boolean;
  max_stop_pct: number;
};

export type ZoneMapPayload = {
  symbol: string;
  name?: string;
  last_price: number;
  supply_zones: Zone[];
  demand_zones: Zone[];
  nearest_resistance: Zone | null;
  nearest_support: Zone | null;
  in_demand_band: boolean;
  is_reentry: boolean;
  fell_from_pct: number | null;
  bars_since_above: number | null;
  trend_passed: number | null;
  trend_ok: boolean;
  zone_quality_ok: boolean;
  entry_zone: Zone | null;
  plan: Plan | null;
  series?: { date: string; close: number }[];
  error?: string;
};

/** Money with sane precision for both $4 and $1,500 stocks. */
export function money(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  if (Math.abs(v) >= 1000) return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  if (Math.abs(v) >= 20) return `$${v.toFixed(0)}`;
  return `$${v.toFixed(2)}`;
}

/** An ACTIONABLE price level — a stop or target he would type into a broker.
 *  Always keeps cents: `money()` rounds $98.50 to "$99", which would show a
 *  tighter stop than the one actually computed. Never round a risk level. */
export function level(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** "$335–$344" — the band as a price range. */
export function bandLabel(z: Zone | null | undefined): string {
  if (!z) return '—';
  return `${money(z.lo)}–${money(z.hi)}`;
}

/** How wide the band is, in % of its floor. Zones thinner than ~1% are lines,
 *  not zones — the UI dims those so they aren't read as tradeable support. */
export function bandWidthPct(z: Zone | null | undefined): number | null {
  if (!z || !z.lo || !z.hi || z.hi <= z.lo) return null;
  return Number((((z.hi / z.lo) - 1) * 100).toFixed(1));
}

/** Reward:risk quality bands — house convention, mirrors how the Trading page
 *  talks about R. Below 1 the trade risks more than the first target pays. */
export function rrBand(rr: number | null | undefined): {
  label: string; tone: 'good' | 'ok' | 'poor' | 'none';
} {
  if (rr == null || !Number.isFinite(rr)) return { label: 'no target above', tone: 'none' };
  if (rr >= 3) return { label: `${rr.toFixed(1)}R — strong`, tone: 'good' };
  if (rr >= 1.5) return { label: `${rr.toFixed(1)}R — workable`, tone: 'ok' };
  return { label: `${rr.toFixed(1)}R — thin`, tone: 'poor' };
}

/** "back in today" / "back in 3 days ago" — how fresh the re-entry is. */
export function freshnessLabel(barsSinceAbove: number | null | undefined): string {
  if (barsSinceAbove == null) return 'in the band';
  if (barsSinceAbove <= 0) return 'dropped in today';
  if (barsSinceAbove === 1) return 'back in yesterday';
  return `back in ${barsSinceAbove} days ago`;
}

/** The one-line trade plan the zone chart writes onto the bands. */
export function planLine(plan: Plan | null | undefined): string {
  if (!plan) return 'No demand band below price — no defined entry here.';
  const parts = [`Buy ${level(plan.entry_low)}–${level(plan.entry_high)}`];
  parts.push(`Stop ${level(plan.stop)}${plan.risk_pct != null ? ` (−${plan.risk_pct}%)` : ''}`);
  if (plan.target != null) {
    parts.push(`Target ${level(plan.target)}${plan.reward_pct != null ? ` (+${plan.reward_pct}%)` : ''}`);
  } else {
    parts.push('Target — none (no overhead supply in range)');
  }
  return parts.join(' · ');
}

/** Plain-English why-this-qualified (or didn't). Keeps the list auditable
 *  instead of asking him to trust a boolean. */
export function reentryReason(p: ZoneMapPayload): string {
  if (!p.entry_zone) return 'No demand band under price.';
  if (!p.in_demand_band) return `Price is above the ${bandLabel(p.entry_zone)} band, not in it.`;
  if (!p.trend_ok) {
    return `In the band, but the trend template only passes ${p.trend_passed ?? 0}/8 — pullback in a weak trend.`;
  }
  if (!p.zone_quality_ok) {
    return `In the band, but it is only tested ${p.entry_zone.touches}× (weak support).`;
  }
  if (p.is_reentry) {
    const fell = p.fell_from_pct != null ? ` after running +${p.fell_from_pct}% above it` : '';
    return `Pulled back into a ${p.entry_zone.touches}×-tested demand band${fell} — ${freshnessLabel(p.bars_since_above)}.`;
  }
  return 'Sitting in the band, but it never left it — not a re-entry.';
}

/** Y-domain for the chart: the price series, widened just enough to show the
 *  bands that matter (entry zone + first target) WITHOUT letting a far-away
 *  band squash the price line into a flat streak. */
export function chartDomain(
  closes: number[],
  bands: (Zone | null | undefined)[],
  padPct = 4,
): { lo: number; hi: number } {
  const vals = closes.filter((c) => Number.isFinite(c));
  if (!vals.length) return { lo: 0, hi: 1 };
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  for (const b of bands) {
    if (!b) continue;
    // Only stretch for a band that is within one series-height of the data —
    // beyond that it is context, not something worth rescaling for.
    const height = hi - lo || 1;
    if (b.lo >= lo - height && b.lo <= hi + height) lo = Math.min(lo, b.lo);
    if (b.hi >= lo - height && b.hi <= hi + height) hi = Math.max(hi, b.hi);
  }
  const pad = ((hi - lo) || hi || 1) * (padPct / 100);
  return { lo: lo - pad, hi: hi + pad };
}

/** Keep only bands that intersect the visible domain, clipped to it, so we
 *  never draw a rectangle off-canvas or a zero-height sliver. */
export function visibleBands(bands: Zone[], domain: { lo: number; hi: number }): Zone[] {
  return bands
    .filter((z) => z && z.hi > domain.lo && z.lo < domain.hi)
    .map((z) => ({ ...z, lo: Math.max(z.lo, domain.lo), hi: Math.min(z.hi, domain.hi) }))
    .filter((z) => z.hi > z.lo);
}
