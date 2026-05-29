/**
 * Fund credibility tier list — curated by user 2026-05-28.
 *
 * EDIT THIS FILE to add/remove funds. Match is case-insensitive substring
 * on the 13F-filed holder name (e.g. "berkshire" matches "Berkshire
 * Hathaway Inc"). Keep substrings as short as possible without false
 * positives.
 *
 * HONESTY CAVEAT (shown in the modal tooltip):
 *   Tier S / A = the fund's historical reputation for active stock-
 *   picking. NOT a forward-looking prediction that they're right on
 *   THIS stock. Tier B = index giants whose flow is mandate-driven,
 *   not conviction.
 *
 * Order within each tier doesn't matter — first match wins. If two
 * substrings match (e.g. "vanguard" and "wellington" both on the same
 * name), the longer one is preferred to reduce false-positive risk.
 */

export type FundTier = 'S' | 'A' | 'B' | null;

export type FundTierInfo = {
  tier:    FundTier;
  match:   string;     // the substring that matched
  display: string;     // human-readable fund name
  manager?: string;    // who runs it (for the tooltip)
};

type Entry = { match: string; display: string; manager?: string };

/** Tier S — legendary stock-pickers, long alpha track record. */
const TIER_S: Entry[] = [
  { match: 'berkshire',       display: 'Berkshire Hathaway',  manager: 'Warren Buffett' },
  { match: 'pershing square', display: 'Pershing Square',     manager: 'Bill Ackman' },
  { match: 'greenlight',      display: 'Greenlight Capital',  manager: 'David Einhorn' },
  { match: 'scion',           display: 'Scion Asset Mgmt',    manager: 'Michael Burry' },
  { match: 'soros fund',      display: 'Soros Fund Mgmt',     manager: 'George Soros' },
  { match: 'renaissance',     display: 'Renaissance Tech',    manager: 'Medallion (Simons)' },
  { match: 'citadel',         display: 'Citadel',             manager: 'Ken Griffin' },
  { match: 'tiger global',    display: 'Tiger Global',        manager: 'Chase Coleman' },
  { match: 'coatue',          display: 'Coatue Mgmt',         manager: 'Philippe Laffont' },
  { match: 'lone pine',       display: 'Lone Pine',           manager: 'Stephen Mandel' },
  { match: 'viking global',   display: 'Viking Global',       manager: 'O. Andreas Halvorsen' },
  { match: 'maverick capital',display: 'Maverick Capital',    manager: 'Lee Ainslie' },
  { match: 'whale rock',      display: 'Whale Rock',          manager: 'Alex Sacerdote' },
  { match: 'glenview',        display: 'Glenview Capital',    manager: 'Larry Robbins' },
  { match: 'trian',           display: 'Trian Partners',      manager: 'Nelson Peltz' },
  { match: 'starboard',       display: 'Starboard Value',     manager: 'Jeffrey Smith' },
  { match: 'icahn',           display: 'Icahn Capital',       manager: 'Carl Icahn' },
  { match: 'valueact',        display: 'ValueAct',            manager: 'Mason Morfit' },
  { match: 'jana partners',   display: 'Jana Partners',       manager: 'Barry Rosenstein' },
  { match: 'pelican',         display: 'Pelican',             manager: '' },
  { match: 'altimeter',       display: 'Altimeter',           manager: 'Brad Gerstner' },
  { match: 'point72',         display: 'Point72',             manager: 'Steve Cohen' },
  { match: 'd.e. shaw',       display: 'D.E. Shaw',           manager: 'Quant' },
  { match: 'de shaw',         display: 'D.E. Shaw',           manager: 'Quant' },
  { match: 'two sigma',       display: 'Two Sigma',           manager: 'Quant' },
  { match: 'bridgewater',     display: 'Bridgewater',         manager: 'Ray Dalio (founder)' },
  { match: 'aqr',             display: 'AQR Capital',         manager: 'Cliff Asness' },
  { match: 'millennium',      display: 'Millennium Mgmt',     manager: 'Izzy Englander' },
];

/** Tier A — well-known active mutual-fund managers (alpha-seeking, not passive). */
const TIER_A: Entry[] = [
  { match: 'capital research', display: 'Capital Research',   manager: 'Capital Group' },
  { match: 'capital world',    display: 'Capital World Inv.', manager: 'Capital Group' },
  { match: 'wellington',       display: 'Wellington Mgmt' },
  { match: 'fidelity contrafund', display: 'Fidelity Contrafund', manager: 'Will Danoff' },
  { match: 't. rowe price',    display: 'T. Rowe Price',      manager: '(active funds)' },
  { match: 't rowe price',     display: 'T. Rowe Price',      manager: '(active funds)' },
  { match: 'baillie gifford',  display: 'Baillie Gifford',    manager: 'Scottish growth' },
  { match: 'sands capital',    display: 'Sands Capital' },
  { match: 'polen',            display: 'Polen Capital' },
  { match: 'dodge & cox',      display: 'Dodge & Cox' },
  { match: 'primecap',         display: 'Primecap' },
  { match: 'eagle capital',    display: 'Eagle Capital' },
  { match: 'ariel investments',display: 'Ariel Investments' },
];

/** Tier B — index giants (passive, mandate-driven, low signal). */
const TIER_B: Entry[] = [
  { match: 'vanguard',       display: 'Vanguard',       manager: 'mostly passive index' },
  { match: 'blackrock',      display: 'BlackRock',      manager: 'iShares ETFs' },
  { match: 'ishares',        display: 'BlackRock iShares' },
  { match: 'state street',   display: 'State Street',   manager: 'SPDR ETFs' },
  { match: 'spdr',           display: 'State Street SPDR' },
  { match: 'geode capital',  display: 'Geode Capital',  manager: 'Fidelity sub-advisor' },
  { match: 'northern trust', display: 'Northern Trust' },
  { match: 'bank of america',display: 'Bank of America' },
];

/** Tier-weight used in the composite score. Higher = more weight given
 *  to position size + concentration when sorting. Tier B is < 1 because
 *  index-giant flow is mostly mandate-driven, not conviction. */
export const TIER_WEIGHT: Record<NonNullable<FundTier>, number> = {
  S: 3.0,
  A: 2.0,
  B: 0.5,
};

/** Tier visual — emoji shown on the row. */
export const TIER_EMOJI: Record<NonNullable<FundTier>, string> = {
  S: '⭐⭐⭐',
  A: '⭐⭐',
  B: '🏛',
};

export const TIER_LABEL: Record<NonNullable<FundTier>, string> = {
  S: 'Legendary stock-picker',
  A: 'Active alpha-seeker',
  B: 'Index giant (mandate)',
};

/** Find which tier a 13F holder name belongs to. Returns null if not on
 *  the curated list. Match is case-insensitive substring; if multiple
 *  entries match, prefer the longest substring (cheap false-positive
 *  reduction). */
export function getFundTier(holderName: string): FundTierInfo | null {
  if (!holderName) return null;
  const lc = holderName.toLowerCase();
  let best: { tier: FundTier; entry: Entry } | null = null;
  const tryTier = (tier: NonNullable<FundTier>, list: Entry[]) => {
    for (const e of list) {
      if (lc.includes(e.match)) {
        if (!best || e.match.length > best.entry.match.length) {
          best = { tier, entry: e };
        }
      }
    }
  };
  tryTier('S', TIER_S);
  tryTier('A', TIER_A);
  tryTier('B', TIER_B);
  if (!best) return null;
  const b = best as { tier: NonNullable<FundTier>; entry: Entry };
  return {
    tier:    b.tier,
    match:   b.entry.match,
    display: b.entry.display,
    manager: b.entry.manager,
  };
}

/** Composite score for sorting / ranking funds within a buy or sell list.
 *
 *   score = tier_weight × log10(position_value_$ + 1) × (1 + pct_held)
 *
 *  - tier_weight: S=3.0, A=2.0, B=0.5, unknown=1.0
 *  - position_value: dollar value of the fund's position in this stock.
 *    log scale so $50B doesn't dwarf $50M by a factor of 1000.
 *  - pct_held: 0-1 (e.g. 0.025 = 2.5% of float). Concentration multiplier.
 *
 *  Returns 0 when value is missing (silent degradation — fund still
 *  renders, just at the bottom of the sort). */
export function fundScore(
  value:    number | null | undefined,
  pctHeld:  number | null | undefined,
  tier:     FundTier
): number {
  const v = value ?? 0;
  if (v <= 0) return 0;
  const tw = tier ? TIER_WEIGHT[tier] : 1.0;
  const sizeLog = Math.log10(v + 1);
  const conc = 1 + (pctHeld ?? 0);
  return tw * sizeLog * conc;
}

/** Format a dollar position size like 5_200_000_000 → "$5.2B". */
export function fmtPositionValue(v: number | null | undefined): string {
  if (v == null || !isFinite(v) || v <= 0) return '—';
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

/** Format pct_held — yfinance returns it like 0.025 (2.5%). */
export function fmtPctHeld(p: number | null | undefined): string {
  if (p == null || !isFinite(p) || p <= 0) return '—';
  // Some sources already give it as a percent (2.5), others as a ratio
  // (0.025). Detect by magnitude.
  const pct = p > 1 ? p : p * 100;
  return `${pct.toFixed(pct >= 10 ? 1 : 2)}%`;
}

/** Estimate how many dollars this fund actually deployed (bought or
 *  sold) last quarter — distinct from their current TOTAL position.
 *
 *  This is the number Ajay actually wants when he says "total volume
 *  of these investments". A +4292% increase on a $48M position is $47M
 *  of new buying; a +50% increase on $5B is $1.7B of new buying. The
 *  dollars-added view ranks the second one as a much bigger move,
 *  which is the truth.
 *
 *  Formula:  ΔPosition ≈ currentValue × pctChange / (1 + pctChange)
 *
 *  Derivation: if pctChange = (new − old) / old, then
 *  old = new / (1 + pctChange), and new − old = new × pctChange / (1 + pctChange).
 *
 *  Returns null when value is missing (backend hasn't shipped it yet)
 *  or when pctChange = -1 (sold-out, math blows up — handled by the
 *  caller as "fully exited").
 */
export function fundDollarsAdded(
  currentValue: number | null | undefined,
  pctChange:    number | null | undefined
): number | null {
  if (currentValue == null || !isFinite(currentValue) || currentValue <= 0) return null;
  if (pctChange == null || !isFinite(pctChange))                            return null;
  const denom = 1 + pctChange;
  if (denom === 0) return null;  // sold to zero
  return currentValue * pctChange / denom;
}

/** Format a signed dollar delta like 1_234_000_000 → "+$1.2B" or "−$1.2B".
 *  Returns "—" for null. Used for per-fund dollars-added + totals. */
export function fmtDeltaUSD(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return '—';
  const sign = v >= 0 ? '+' : '−';
  const abs = Math.abs(v);
  let s: string;
  if (abs >= 1e9)      s = `$${(abs / 1e9).toFixed(1)}B`;
  else if (abs >= 1e6) s = `$${(abs / 1e6).toFixed(1)}M`;
  else if (abs >= 1e3) s = `$${(abs / 1e3).toFixed(1)}K`;
  else                 s = `$${abs.toFixed(0)}`;
  return `${sign}${s}`;
}
