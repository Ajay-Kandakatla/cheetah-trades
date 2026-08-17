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
  /** Bars back to the OLDEST swing in the cluster. The chart window is sized
   *  from this so a band's own defining touches are never off the left edge. */
  oldest_touch_bars?: number;
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
  /* Falling-knife guard — replaced the Minervini trend template 2026-08-13.
   * `structure.trend` is the direction of the swing lows. */
  structure?: { trend: 'rising' | 'falling' | 'unclear'; swing_lows: number[];
                last_two: number[] | null; ma50_rising?: boolean | null };
  is_knife?: boolean;
  trend_ok: boolean;
  zone_quality_ok: boolean;
  entry_zone: Zone | null;
  plan: Plan | null;
  resolution?: 'fine' | 'swing' | null;
  liquidity?: Liquidity | null;
  venues?: Venues | null;
  retail?: Retail | null;
  breakeven_win_pct?: number | null;
  /** o/h/l/volume added 2026-08-16 for the candlestick chart; a payload cached
   *  before that carries date + close only. See lib/zoneChart.ts. */
  series?: { date: string; open?: number | null; high?: number | null;
             low?: number | null; close: number; volume?: number | null }[];
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

/** "$335–$344" — the band as a price range.
 *
 *  Falls back to cents when both ends round to the same string: a very thin
 *  band otherwise renders as "$230–$230", which reads as a rendering bug
 *  rather than as the (real, but narrow) band it is. */
export function bandLabel(z: Zone | null | undefined): string {
  if (!z) return '—';
  const lo = money(z.lo), hi = money(z.hi);
  return lo === hi ? `${level(z.lo)}–${level(z.hi)}` : `${lo}–${hi}`;
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
  if (!p.trend_ok || p.is_knife) {
    const lows = p.structure?.last_two;
    const detail = lows ? ` (${lows[0]} → ${lows[1]})` : '';
    return `In the band, but the swing lows are stepping DOWN${detail} with a falling 50-day — falling knife, not a demand zone.`;
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

export type Liquidity = {
  avg_vol_50: number | null; avg_dollar_vol_50: number | null;
  /* Today's figures. Mid-session these come from the LIVE TAPE, not the daily
   * bar — the bar is a stale snapshot (measured 1.5-2.6x understated). Rows
   * without a tape pull report today_source 'pending' and no rvol. */
  today_vol?: number | null; today_dollar_vol?: number | null;
  rvol?: number | null;
  rvol_state?: 'surging' | 'active' | 'quiet' | 'dead' | null;
  rvol_partial?: boolean; today_source?: 'tape' | 'daily_bar' | 'pending' | null;
  session_pct?: number | null; last_close?: number | null;
  tier: 'deep' | 'ok' | 'thin' | 'illiquid' | null; tradeable: boolean | null;
};

export type DarkBlock = { time: string; price: number; size: number; dollars: number };

export type Venues = {
  available?: boolean; dark_pct?: number | null;
  /** Board rows carry a COUNT; the detail view carries the blocks themselves. */
  blocks?: number | DarkBlock[] | null;
  rating?: 'heavy' | 'normal' | 'light' | null;
  read?: string; disclaimer?: string;
  dark_shares?: number; total_shares?: number; dark_trades?: number;
};

/** Block COUNT, whatever shape the payload used. The board sends a number
 *  (cheap); the detail view sends the blocks themselves. */
export function blockCount(v: Venues | null | undefined): number | null {
  if (!v || v.blocks == null) return null;
  return Array.isArray(v.blocks) ? v.blocks.length : v.blocks;
}

/** Blocks as a list, whatever shape the payload used. */
export function blockList(v: Venues | null | undefined): DarkBlock[] {
  return Array.isArray(v?.blocks) ? (v!.blocks as DarkBlock[]) : [];
}

/** Blocks that printed INSIDE a band — the ones that say something about
 *  that level specifically, rather than about the session in general. */
export function blocksInBand(blocks: DarkBlock[], z: Zone | null | undefined): DarkBlock[] {
  if (!z) return [];
  return blocks.filter((b) => b.price >= z.lo && b.price <= z.hi);
}

/** Break-even win rate for a given R:R — the number that makes R:R concrete.
 *  At 3.8R you can be wrong 4 times in 5; at 0.03R you'd need to be right 97%
 *  of the time. Ajay 2026-08-13 asked for this on every row. */
export function breakEvenWinPct(rr: number | null | undefined): number | null {
  if (rr == null || !Number.isFinite(rr) || rr <= 0) return null;
  return Number((100 / (1 + rr)).toFixed(0));
}

/** Compact dollar volume: 3075500000 -> "$3.1B/day". */
export function volLabel(dollars: number | null | undefined): string {
  if (dollars == null || !Number.isFinite(dollars)) return '—';
  if (dollars >= 1e9) return `$${(dollars / 1e9).toFixed(1)}B/day`;
  if (dollars >= 1e6) return `$${(dollars / 1e6).toFixed(0)}M/day`;
  return `$${(dollars / 1e3).toFixed(0)}K/day`;
}

/** Can you actually get filled here? A great R:R on untradeable tape is not a
 *  trade — the spread eats the edge before the setup gets a chance. */
export function liquidityView(l: Liquidity | null | undefined):
  { label: string; color: string; warn: boolean } {
  const tier = l?.tier;
  if (!tier) return { label: '—', color: '#8595ad', warn: false };
  if (tier === 'deep') return { label: 'deep', color: '#22c55e', warn: false };
  if (tier === 'ok') return { label: 'ok', color: '#cbd5e1', warn: false };
  if (tier === 'thin') return { label: 'thin', color: '#d97706', warn: true };
  return { label: 'illiquid', color: '#ef4444', warn: true };
}

/** Off-exchange share. Venue fact, NOT proof of institutional intent — the
 *  bucket mixes dark-pool crossing with retail internalisation. */
export function venueView(v: Venues | null | undefined):
  { label: string; color: string; title: string } {
  if (!v || v.dark_pct == null) {
    return { label: '—', color: '#8595ad',
             title: 'No tape pulled for this row (only the top rows by R:R get venue detail).' };
  }
  const blocks = Array.isArray(v.blocks) ? v.blocks.length : (v.blocks ?? 0);
  const base = `${v.dark_pct}% of volume printed off-exchange; ${blocks} large off-exchange block${blocks === 1 ? '' : 's'}. `
    + 'Mixes dark-pool crossing with retail internalisation — a venue fact, not proof of who traded.';
  if (v.rating === 'heavy') return { label: `${v.dark_pct}%`, color: '#a78bfa', title: `Unusually dark. ${base}` };
  if (v.rating === 'light') return { label: `${v.dark_pct}%`, color: '#8595ad', title: `Lightly dark. ${base}` };
  return { label: `${v.dark_pct}%`, color: '#cbd5e1', title: base };
}

export type Retail = {
  available?: boolean; signed?: boolean;
  retail_trades?: number; retail_shares?: number;
  retail_pct_of_volume?: number | null;
  imbalance_pct?: number | null;
  lean?: 'buying' | 'selling' | 'balanced' | null;
  read?: string; disclaimer?: string;
  divergence?: { retail_lean: string; block_count: number; block_dollars: number; note: string } | null;
};

/** Retail lean, coloured. Unsigned reads are shown as unknown rather than
 *  neutral — "we could not sign these" is not "retail is balanced". */
export function retailView(r: Retail | null | undefined):
  { label: string; color: string; title: string } {
  if (!r?.available) {
    return { label: '—', color: '#8595ad',
             title: 'No tape pulled for this row (only the top rows by R:R get retail detail).' };
  }
  if (!r.signed || r.imbalance_pct == null) {
    return { label: `${r.retail_pct_of_volume ?? '—'}%`, color: '#8595ad',
             title: r.read || 'Retail prints identified but unsigned — no NBBO for this session.' };
  }
  const base = `${r.read ?? ''} Identified by sub-penny price improvement on off-exchange prints `
    + '(Boehmer et al. 2021) and signed on the quote midpoint (Barber et al. 2024 — the original '
    + 'sub-penny signing mis-signs 28% of trades). Catches roughly a third of retail activity, so '
    + 'it is a sample, not a census.';
  if (r.lean === 'buying') return { label: `+${r.imbalance_pct}%`, color: '#22c55e', title: base };
  if (r.lean === 'selling') return { label: `${r.imbalance_pct}%`, color: '#ef4444', title: base };
  return { label: `${r.imbalance_pct}%`, color: '#cbd5e1', title: base };
}

export type LabelItem = {
  /** Ideal vertical position, in SVG user units. */
  y: number;
  text: string;
  color: string;
  bold?: boolean;
  /** Higher wins a collision. BUY/STOP/TARGET/NOW are 2; band labels are 1. */
  priority: number;
};

/** Stack the right-hand labels so they never overlap.
 *
 * When price, the entry band and the stop sit within a couple of percent of
 * each other — exactly the case this feature is built for — their labels land
 * on the same pixels and become unreadable. High-priority labels (the plan:
 * BUY / STOP / TARGET / NOW) keep their position and push others away; a
 * low-priority band label that cannot find a free slot within `maxShift` is
 * DROPPED rather than drawn on top of the plan.
 */
export function layoutLabels(
  items: LabelItem[],
  opts: { minGap?: number; top?: number; bottom?: number; maxShift?: number } = {},
): LabelItem[] {
  const minGap = opts.minGap ?? 11;
  const top = opts.top ?? 0;
  const bottom = opts.bottom ?? Number.POSITIVE_INFINITY;
  const maxShift = opts.maxShift ?? 26;

  const ordered = [...items].sort((a, b) => (b.priority - a.priority) || (a.y - b.y));
  const placed: LabelItem[] = [];

  const clashes = (y: number) =>
    y < top || y > bottom || placed.some((p) => Math.abs(p.y - y) < minGap);

  for (const item of ordered) {
    let y: number | null = null;
    for (let shift = 0; shift <= maxShift; shift += 1) {
      if (!clashes(item.y + shift)) { y = item.y + shift; break; }
      if (shift && !clashes(item.y - shift)) { y = item.y - shift; break; }
    }
    if (y == null) {
      if (item.priority >= 2) y = item.y;   // never drop the plan
      else continue;                        // drop a colliding band label
    }
    placed.push({ ...item, y });
  }
  return placed.sort((a, b) => a.y - b.y);
}

/** Keep only bands that intersect the visible domain, clipped to it, so we
 *  never draw a rectangle off-canvas or a zero-height sliver. */
export function visibleBands(bands: Zone[], domain: { lo: number; hi: number }): Zone[] {
  return bands
    .filter((z) => z && z.hi > domain.lo && z.lo < domain.hi)
    .map((z) => ({ ...z, lo: Math.max(z.lo, domain.lo), hi: Math.min(z.hi, domain.hi) }))
    .filter((z) => z.hi > z.lo);
}
