/* The units and the sentences the review round found wrong (2026-09-23).
 *
 * The 2026-09-22 change made every intraday frame read its OWN bars. Four
 * reviewers then measured what that did to the wording built on top of the
 * old assumption that a bar is a trading session and that the daily zoom is
 * where every number came from. Measured live 2026-09-22 from the branch
 * worktree, PTGX at 145.07 on `?tf=5m_today`:
 *
 *   supports: []            standing_in 144.50-145.96, bars_since_test 6
 *   overhead: 145.53-147.71, bars_since_test 5
 *   window_label: "6 months"   board demand 139.46-144.43
 *
 * which the surface rendered as "tested 6 sessions ago" for a band touched
 * half an hour earlier, and "No band below price in the last 6 months" over a
 * chart built from 79 five-minute bars — while PTGX's actual 6-month read
 * holds a band at 142.43-144.15 and the board's band is printed on the same
 * page. Every helper here takes the unit or the scope as a SERVED argument.
 */
import { describe, expect, it } from 'vitest';
import {
  barDomain, offDomainBands, type CmBand,
} from './chartMaps';
import {
  emptySupportNote, headline, recencyLabel, recentWindowLabel,
  type SupportLevel, type SupportPayload,
} from './supportLevels';

const lvl = (over: Partial<SupportLevel> = {}): SupportLevel => ({
  lo: 144.50, hi: 145.96, mid: 145.23, origin: 'demand', touches: 13,
  strength: 60, bars_since_test: 6, oldest_touch_bars: 70, recent: true,
  tested: true, distance_pct: 0.4, ...over,
});

/* ── recency, in the unit the bars were counted in ───────────────────────── */

describe('recencyLabel — the unit is served, never assumed', () => {
  it('keeps the session wording on the daily frame', () => {
    expect(recencyLabel(lvl({ bars_since_test: 0 }), 'daily')).toBe('tested today');
    expect(recencyLabel(lvl({ bars_since_test: 1 }), 'daily')).toBe('tested yesterday');
    expect(recencyLabel(lvl({ bars_since_test: 6 }), 'daily')).toBe('tested 6 sessions ago');
  });

  it('a five-minute bar is NOT a trading session', () => {
    // The regression, verbatim: 6 x 5-minute bars is half an hour, and the
    // surface called it six trading days.
    expect(recencyLabel(lvl({ bars_since_test: 6 }), '5-minute'))
      .toBe('tested 6 × 5-minute bars ago');
    expect(recencyLabel(lvl({ bars_since_test: 1 }), '5-minute'))
      .toBe('tested 1 5-minute bar ago');
    expect(recencyLabel(lvl({ bars_since_test: 0 }), '5-minute'))
      .toBe('tested on the last bar');
    expect(recencyLabel(lvl({ bars_since_test: 34 }), '15-minute'))
      .toBe('tested 34 × 15-minute bars ago');
  });

  it('NEGATIVE: an intraday unit never says "sessions", "today" or "yesterday"', () => {
    for (const n of [0, 1, 2, 9, 34]) {
      const s = recencyLabel(lvl({ bars_since_test: n }), '5-minute');
      expect(s).not.toMatch(/session/);
      expect(s).not.toMatch(/yesterday/);
      expect(s).not.toBe('tested today');
    }
  });

  it('an unserved unit falls back to the wording every payload had before', () => {
    // A payload served before 2026-09-23 carries no `levels_bar_label`; it was
    // always a daily read on the surfaces that print this, so nothing moves.
    expect(recencyLabel(lvl({ bars_since_test: 6 }))).toBe('tested 6 sessions ago');
    expect(recencyLabel(lvl({ bars_since_test: 6 }), '')).toBe('tested 6 sessions ago');
  });

  it('says nothing at all when the server sent no count', () => {
    expect(recencyLabel(lvl({ bars_since_test: undefined }), '5-minute'))
      .toBe('not tested in this window');
    expect(recencyLabel(null, '5-minute')).toBe('not tested in this window');
  });
});

describe('recentWindowLabel — RECENT_BARS is a bar count', () => {
  it('21 bars is 21 sessions on the daily frame', () => {
    expect(recentWindowLabel(21, 'daily')).toBe('21 sessions');
    expect(recentWindowLabel(21)).toBe('21 sessions');
  });
  it('21 bars is NOT 21 sessions on a five-minute chart', () => {
    expect(recentWindowLabel(21, '5-minute')).toBe('21 × 5-minute bars');
    expect(recentWindowLabel(21, '5-minute')).not.toMatch(/session/);
  });
});

describe('headline — carries the served unit into its recency clause', () => {
  it('names the drawn band in the frame’s own unit', () => {
    const p = {
      standing_in: lvl(), supports: [], overhead: [], last_price: 145.07,
      levels_bar_label: '5-minute',
    } as unknown as SupportPayload;
    expect(headline(p)).toContain('tested 6 × 5-minute bars ago');
    expect(headline(p)).not.toMatch(/session/);
  });
  it('and keeps sessions when the levels came off daily bars', () => {
    const p = {
      standing_in: lvl(), supports: [], overhead: [], last_price: 145.07,
      levels_bar_label: 'daily',
    } as unknown as SupportPayload;
    expect(headline(p)).toContain('tested 6 sessions ago');
  });
});

/* ── the empty "Support below" sentence ──────────────────────────────────── */

const EMPTY_ENTRY_FRAME = {
  window_label: '6 months',
  levels_scope: '79 x 5-minute bars',
  levels_bar_label: '5-minute',
  last_price: 145.07,
  supports: [],
  overhead: [lvl({ lo: 145.53, hi: 147.71, origin: 'supply' })],
  standing_in: lvl(),
  board: { demand: { lo: 139.46, hi: 144.43, touches: 1, distance_pct: 0.44 },
           supply: null },
} as unknown as SupportPayload;

describe('emptySupportNote — names the frame, not the pinned daily zoom', () => {
  it('states the window the emptiness actually came from', () => {
    const s = emptySupportNote(EMPTY_ENTRY_FRAME,
                               { zoomApplies: false, longerFrameLabel: 'The big picture' });
    expect(s).toContain('79 x 5-minute bars');
    // THE REGRESSION: it claimed six months, and the six-month read is not
    // empty — its own band is printed on the same page.
    expect(s).not.toContain('6 months');
  });

  it('drops "Try a longer zoom" where the zoom control does not render', () => {
    const s = emptySupportNote(EMPTY_ENTRY_FRAME,
                               { zoomApplies: false, longerFrameLabel: 'The big picture' });
    expect(s).not.toContain('Try a longer zoom');
    // …and points at a chart that IS in the dropdown
    expect(s).toContain('The big picture');
  });

  it('keeps the zoom hint on the one frame that has a zoom', () => {
    const s = emptySupportNote({ ...EMPTY_ENTRY_FRAME, levels_scope: '6 months' },
                               { zoomApplies: true });
    expect(s).toContain('Try a longer zoom');
    expect(s).not.toContain('The big picture');
  });

  it('says what IS known: the band price stands in, and the board’s band below', () => {
    const s = emptySupportNote(EMPTY_ENTRY_FRAME, { zoomApplies: false });
    expect(s).toContain('$144.50 – $145.96');
    expect(s).toContain('$139.46 – $144.43');
    expect(s).toMatch(/BOARD/);
    // labelled as the OTHER reading, never as this chart's
    expect(s).toMatch(/alert gate and the paper lanes use/);
  });

  it('NEGATIVE: never claims a board band that is not below price', () => {
    const above = {
      ...EMPTY_ENTRY_FRAME,
      board: { demand: { lo: 150.0, hi: 152.0 }, supply: null },
    } as unknown as SupportPayload;
    expect(emptySupportNote(above, { zoomApplies: false })).not.toContain('$150.00');
  });

  it('NEGATIVE: says nothing about a band price is not standing in', () => {
    const out = { ...EMPTY_ENTRY_FRAME, standing_in: null } as unknown as SupportPayload;
    expect(emptySupportNote(out, { zoomApplies: false })).not.toContain('standing INSIDE');
  });

  it('degrades to the served zoom when no scope was sent', () => {
    const old = { window_label: '6 months', supports: [] } as unknown as SupportPayload;
    expect(emptySupportNote(old, { zoomApplies: true }))
      .toBe('No band below price in 6 months — nothing here to place a stop '
            + 'under. Try a longer zoom.');
  });
});

/* ── the board band that is not on the chart ─────────────────────────────── */

describe('offDomainBands — a band the plot dropped', () => {
  /* Measured 2026-09-22, NVDA on the 24-hour frame: candles 225.56-229.44,
   * board demand 212.19-216.82. `barDomain`'s stretch guard ignores any edge
   * more than one chart-height away and `clipBands` then discards it, so the
   * dashed rectangle the served note points at is simply not drawn. */
  const bars = [
    { t: '2026-09-22 09:30', o: 226, h: 229.44, l: 225.56, c: 228.5, v: 1 },
    { t: '2026-09-22 09:35', o: 228.5, h: 229.2, l: 226.1, c: 228.56, v: 1 },
  ];
  const board: CmBand = { kind: 'board_demand', lo: 212.19, hi: 216.82,
                          label: 'board demand · 4× tested' } as CmBand;

  it('reports the board band as BELOW this chart', () => {
    const d = barDomain(bars as any, [board], [], 6, []);
    expect(board.hi).toBeLessThan(d.lo);            // the premise
    const off = offDomainBands([board], d);
    expect(off).toHaveLength(1);
    expect(off[0].side).toBe('below');
    expect(off[0].band.lo).toBe(212.19);
  });

  it('reports one above, and says which side', () => {
    const d = barDomain(bars as any, [], [], 6, []);
    const up: CmBand = { kind: 'board_supply', lo: 300, hi: 305 } as CmBand;
    const off = offDomainBands([up], d);
    expect(off).toEqual([{ band: up, side: 'above' }]);
  });

  it('NEGATIVE: a band inside or overlapping the plot is not reported', () => {
    const d = barDomain(bars as any, [], [], 6, []);
    const inside: CmBand = { kind: 'demand', lo: 226, hi: 227 } as CmBand;
    const straddling: CmBand = { kind: 'demand', lo: 200, hi: 227 } as CmBand;
    expect(offDomainBands([inside, straddling], d)).toEqual([]);
  });

  it('NEGATIVE: a band with no numbers is skipped, never reported at NaN', () => {
    const d = barDomain(bars as any, [], [], 6, []);
    expect(offDomainBands([{ kind: 'demand' } as any,
                           { kind: 'demand', lo: 1, hi: NaN } as any], d)).toEqual([]);
  });
});
