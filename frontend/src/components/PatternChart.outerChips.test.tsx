import { describe, it, expect, afterEach } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { EnterableChip } from './EnterableChip';
import { ExplosiveChip } from './ExplosiveChip';
import { SignalWatchButton } from './SignalWatchButton';
import { SUPPORT_OUTER_CHIPS } from './SupportLevels';
import { POTUS_OUTER_CHIPS } from './PotusBoard';
import { EMA_OUTER_CHIPS } from './EmaFramesBoard';
import type { OuterChip } from '../lib/cardLadder';
import { outerChipsFor } from '../lib/outerChips';
import { VOYA } from '../lib/__fixtures__/cardLadder.tiles';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';

/* 📋 D8 (2026-09-25): three wrappers print chips in their own head beside the
 * tile — the Support tab's sl-head (🚀 🎪 🧨 🎯), the POTUS pb-tile head
 * (🚀 🎪 🧨 🎯 + Signals) and the 9 EMA strip (🚀 🧨 🎯). The tile skips
 * exactly those, so each prints ONCE on the card. The wrapper's own chip is
 * drawn here the way the wrapper draws it, off the same read. */

const EXPLOSIVE = { room: { state: 'ROOM', room_pct: 7.2 }, floor: 'held', measured: { status: 'no_signal' } } as any;
const TILE = { ...VOYA, explosive: EXPLOSIVE };

/* The wrapper draws its own 🎯 / 🧨 off ITS read (the room endpoint); the
 * list the tile skips is outerChipsFor(base, tile, wrapperReads) — exactly
 * what SupportLevels / PotusBoard / EmaFramesBoard pass. */
type Reads = { enterable?: any; explosive?: any };
const card = (base: ReadonlyArray<OuterChip> | undefined, withWatch = false,
              reads: Reads = { enterable: TILE.enterable, explosive: TILE.explosive }) => render(
  <MemoryRouter>
    <div className="wrapper-head">
      <ExplosiveChip read={reads.explosive} />
      <EnterableChip read={reads.enterable} />
      {withWatch ? <SignalWatchButton symbol={TILE.symbol} /> : null}
    </div>
    <PatternChart tile={TILE}
                  outerChips={base ? outerChipsFor(base, TILE, { ...reads, outerStudy: null, tileStudy: null }) : undefined} />
  </MemoryRouter>,
);

const count = (re: RegExp) => screen.queryAllByText(re).length;

describe('outerChips — each wrapper chip prints once on the card', () => {
  afterEach(() => { cleanup(); _resetSignalWatchlist(); });

  it('Support: 🎯 and 🧨 once each', () => {
    expect(SUPPORT_OUTER_CHIPS).toEqual(['growth', 'promo', 'explosive', 'enterable']);
    card(SUPPORT_OUTER_CHIPS);
    expect(count(/^🎯 READY$/)).toBe(1);
    expect(count(/^🧨/)).toBe(1);
  });

  it('POTUS: 🎯, 🧨 and + Signals once each; the tile keeps TV ↗', () => {
    expect(POTUS_OUTER_CHIPS).toEqual(['growth', 'promo', 'explosive', 'enterable', 'watch']);
    card(POTUS_OUTER_CHIPS, true);
    expect(count(/^🎯 READY$/)).toBe(1);
    expect(count(/^🧨/)).toBe(1);
    expect(screen.getAllByRole('button', { name: /VOYA (to|from) Signals/ })).toHaveLength(1);
    expect(screen.getByRole('button', { name: /VOYA in TradingView/ })).toBeInTheDocument();
  });

  it('9 EMA: 🎯 and 🧨 once each; 🪜 stays on the tile (the strip has none)', () => {
    expect(EMA_OUTER_CHIPS).toEqual(['growth', 'explosive', 'enterable']);
    const { container } = card(EMA_OUTER_CHIPS);
    expect(count(/^🎯 READY$/)).toBe(1);
    expect(count(/^🧨/)).toBe(1);
    expect(container.textContent).toContain('🪜 ceiling 2.7% wide');
  });

  it('NEGATIVE: with no outerChips (the Chart Maps grid) the tile prints its own — twice beside a wrapper chip', () => {
    card(undefined);
    expect(count(/^🎯 READY$/)).toBe(2);
    expect(count(/^🧨/)).toBe(2);
  });

  /* Repair 2026-09-25: the head's 🎯 / 🧨 come from a DIFFERENT endpoint than
   * the tile's. Skip the tile's copy only when the two chip strings are equal. */
  it('NEGATIVE: wrapper read absent (room loading / failed) → the tile keeps its 🎯 and 🧨', () => {
    for (const base of [SUPPORT_OUTER_CHIPS, POTUS_OUTER_CHIPS, EMA_OUTER_CHIPS]) {
      card(base, false, {});
      expect(count(/^🎯 READY$/)).toBe(1);
      expect(count(/^🧨/)).toBe(1);
      cleanup();
    }
  });

  it('NEGATIVE: wrapper 🎯 text differs from the tile\'s → both print (dedupe only on equality)', () => {
    const other = { ...TILE.enterable, verdict: 'WATCH', reason_short: ['down day'] };
    card(SUPPORT_OUTER_CHIPS, false, { enterable: other, explosive: TILE.explosive });
    expect(count(/^🎯 READY$/)).toBe(1);                   // the tile's own
    expect(count(/^🎯 WATCH · down day$/)).toBe(1);        // the head's
    expect(count(/^🧨/)).toBe(1);                          // equal → once
  });

  it('outerChipsFor: equal reads hand back the SAME array (PatternChart memo holds); unequal drop only that chip', () => {
    const same = outerChipsFor(POTUS_OUTER_CHIPS, TILE, { enterable: TILE.enterable, explosive: TILE.explosive });
    expect(same).toBe(POTUS_OUTER_CHIPS);
    const a = outerChipsFor(POTUS_OUTER_CHIPS, TILE, { explosive: TILE.explosive });
    expect(a).toEqual(['growth', 'promo', 'explosive', 'watch']);
    expect(outerChipsFor(POTUS_OUTER_CHIPS, TILE, { explosive: TILE.explosive })).toBe(a);
    expect(outerChipsFor(EMA_OUTER_CHIPS, TILE, {})).toEqual(['growth']);
    /* No read on either side → nothing to print twice → skip stands. */
    expect(outerChipsFor(EMA_OUTER_CHIPS, { enterable: null, explosive: null }, {})).toBe(EMA_OUTER_CHIPS);
  });
});
