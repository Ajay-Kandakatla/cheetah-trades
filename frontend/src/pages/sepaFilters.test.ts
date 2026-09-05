/* passesSepaFilters — the 🪃 Bouncing off Demand gate (Ajay 2026-09-05: "#1
 * for Sepa stocks that is bouncing off of Demand zone").
 *
 * The gate chain is one module-level function shared by the main list and the
 * setup tabs; this pins the ONE clause added on 2026-09-05 with its negatives:
 * chip on hides covered-not-bouncing, pending, unavailable and absent rows
 * (the count line, not a blank list, says how much is covered); chip off
 * gates nothing; the lookup is by UPPER symbol. Every other gate is opened so
 * a failure here is this clause and nothing else. */
import { describe, it, expect } from 'vitest';
import { passesSepaFilters, type SepaFilterDeps } from './Sepa';
import type { SepaFilters } from '../components/SepaFilterBar';
import type { SepaCandidate } from '../hooks/useSepa';
import type { BounceRoomRow } from '../lib/bounceRoom';

const OPEN: SepaFilters = {
  rating: 'ALL', setup: 'ALL', decision: 'ALL', rsMin: 0, search: '', showAll: true,
  dmEligibleOnly: false, type: 'all', pioneerOnly: false, stage: 'ALL', moatMin: 0,
  hideDistributing: false, volX15Only: false, hideEarningsSoon: false, whalesAccumOnly: false,
  hedgeFundTopBuyer: false, potusFamilyOnly: false, usGovOnly: false, insiderClusterBuy: false,
  momentumLeaderOnly: false, bounceDemandOnly: false, weekly21SmaPass: false, atrPctMax: 0, adxMin: 0,
  sortBy: 'score',
};

const row = (symbol: string): SepaCandidate =>
  ({ symbol, score: 80, rs_rank: 90, stage: { stage: 2, label: 'Stage 2', dist_200_pct: 10 } } as unknown as SepaCandidate);

const BOUNCING: BounceRoomRow = {
  symbol: 'AVGO', coverage: 'store', print: 99, fresh: true,
  bounce: { band: { kind: 'demand', lo: 90, hi: 92, touches: 2, strength: 50 }, role: 'demand',
            touch_low: 91, touch_date: '2026-09-04', sessions_ago: 0, bounce_pct: 8.8, floor_pct: 3,
            strong: true, atr_x: 4 },
  room: { state: 'CLEAR', room_pct: null, atr_days: null, band: null, at_highs: false },
};
const FLAT: BounceRoomRow = { ...BOUNCING, symbol: 'FLAT', bounce: null };
const PENDING: BounceRoomRow = { symbol: 'PEND', coverage: 'pending' };
const UNAVAILABLE: BounceRoomRow = { symbol: 'GONE', coverage: 'unavailable', error: 'no print in snapshot' };

const deps = (rows: BounceRoomRow[]): SepaFilterDeps => ({
  earningsMap: new Map(),
  whalesFlow: new Map(),
  bounceRoom: new Map(rows.map((r) => [r.symbol, r])),
});

describe('passesSepaFilters — 🪃 bounceDemandOnly', () => {
  const D = deps([BOUNCING, FLAT, PENDING, UNAVAILABLE]);
  const ON: SepaFilters = { ...OPEN, bounceDemandOnly: true };

  it('chip on: a bouncing row passes', () => {
    expect(passesSepaFilters(row('AVGO'), ON, D)).toBe(true);
  });

  it('chip on: covered-but-not-bouncing, pending, unavailable and absent rows are hidden (negatives)', () => {
    expect(passesSepaFilters(row('FLAT'), ON, D)).toBe(false);
    expect(passesSepaFilters(row('PEND'), ON, D)).toBe(false);
    expect(passesSepaFilters(row('GONE'), ON, D)).toBe(false);
    expect(passesSepaFilters(row('NOPE'), ON, D)).toBe(false);
    expect(passesSepaFilters(row('AVGO'), ON, deps([]))).toBe(false);   // read not loaded yet
  });

  it('chip off: the clause gates nothing — every row passes regardless of the read', () => {
    for (const s of ['AVGO', 'FLAT', 'PEND', 'GONE', 'NOPE']) {
      expect(passesSepaFilters(row(s), OPEN, D)).toBe(true);
    }
    expect(passesSepaFilters(row('AVGO'), OPEN, deps([]))).toBe(true);
  });

  it('looks the row up by UPPER symbol — a lower-case candidate still matches the map key', () => {
    expect(passesSepaFilters(row('avgo'), ON, D)).toBe(true);
    expect(passesSepaFilters(row('flat'), ON, D)).toBe(false);
  });
});
