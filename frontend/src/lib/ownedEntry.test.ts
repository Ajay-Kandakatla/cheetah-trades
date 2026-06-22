import { describe, it, expect } from 'vitest';
import { resolveOwnedEntry } from './ownedEntry';

/* resolveOwnedEntry — per-share entry for the on-card hold/sell verdict.
   Drives whether a SEPA card shows PositionSignal for a name you own. */

describe('resolveOwnedEntry', () => {
  it('prefers broker/Plaid avg_cost when present', () => {
    expect(resolveOwnedEntry({ avg_cost: 445.43, entry: 400, cost_basis: 9000, quantity: 20 }))
      .toBe(445.43);
  });

  it('falls back to the user-typed entry when avg_cost is missing', () => {
    expect(resolveOwnedEntry({ avg_cost: null, entry: 445.43, cost_basis: null, quantity: null }))
      .toBe(445.43);
  });

  it('derives from cost_basis ÷ quantity when neither avg_cost nor entry is set', () => {
    // ARM-like: cost basis $20,111.16 over 45.15 shares → ~$445.43/share
    const v = resolveOwnedEntry({ avg_cost: null, entry: null, cost_basis: 20111.16, quantity: 45.15 });
    expect(v).toBeCloseTo(445.43, 2);
  });

  // ── negative / edge ────────────────────────────────────────────────────
  it('returns null for a null/undefined holding (non-owned card → renders nothing)', () => {
    expect(resolveOwnedEntry(null)).toBeNull();
    expect(resolveOwnedEntry(undefined)).toBeNull();
  });

  it('returns null when there is no usable cost basis', () => {
    expect(resolveOwnedEntry({ avg_cost: null, entry: null, cost_basis: null, quantity: null }))
      .toBeNull();
  });

  it('ignores zero / non-positive values rather than emitting a bogus entry', () => {
    expect(resolveOwnedEntry({ avg_cost: 0, entry: 0, cost_basis: 0, quantity: 10 })).toBeNull();
    // cost_basis present but zero shares must not divide-by-zero
    expect(resolveOwnedEntry({ avg_cost: null, entry: null, cost_basis: 5000, quantity: 0 })).toBeNull();
  });
});
