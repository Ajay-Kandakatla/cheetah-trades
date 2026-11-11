import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import type { GgVariantKey } from './ggVariant';

/* 🎾 short-interest label + 🧪 entry-zone card line on the REAL board (2026-11-08, spec gg-zones WP fe-card).
 *
 * Ajay 2026-11-07: "Also for the reversal squeeze I need short interest to be show on all the 3 of his tab as a label."
 * and "add entry signal on the chart please like a small zone".
 *
 * This file does NOT mock ./ShortInterestChip (19 other board tests do): the real chip and the real label both read the
 * stubbed /short-interest/map, so the 🎾-only chip skip [C7] is observable — the SI text prints exactly ONCE per 🎾
 * card while a bull_flag card on the same board keeps its muted head-row chip. The zone line prints the band's served
 * `note` [C1], never its short `label`. Boards are CLONES of the frozen 2026-10-13 hand fixture. */

const chartProps: any[] = [];
vi.mock('./PatternChart', () => ({
  PatternChart: (props: any) => { chartProps.push(props); return <div data-testid={`chart-${props.tile.symbol}`} />; },
}));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => {} }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const BOARDS: Record<string, any> = (fixture as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const SQ = 'FCHL';
const BF = 'PFAI';
const SQ_CHIP = '🩳 SI 21.9% float · 1.0d · 10/15';
const BF_CHIP = '🩳 SI 4.2% float · 2.3d · 10/15';
const TITLE = '🩳 Short interest — FINRA settlement 2026-10-15 (published ~2026-10-24). A count of open short positions — not a forecast.';
const NOTE = 'imminent — trigger armed, volume dry, no more than 3 red closes in a row · UNMEASURED';
const LABEL = 'entry zone';

let SI: Record<string, unknown> = {};
const siOk = (sym: string, chip: string, status = 'ok') => ({ symbol: sym, status, chip, title: TITLE, rows: [] });

/** A 🎾 board carrying the squeeze tile FCHL AND the bull_flag tile PFAI (both clones), no timers. */
function board(patch: (b: any) => void = () => {}): any {
  const b = clone(BOARDS.reversal_squeeze);
  b.session = { ...b.session, refresh_sec: 0 };
  b.tiles = [clone(BOARDS.reversal_squeeze.tiles[0]), clone(BOARDS.bull_flag.tiles[0])];
  // ⚡ 2026-11-11 (entry spec §3.2, predicted pin): the plan line is the SERVED plan_text — the hand fixture predates it.
  b.tiles[0].gajjala.plan_text = 'Entry above 3.42 · stop 3.18 · risk 7.0%';
  b.tiles[1].gajjala.plan_text = 'Entry above 4.12 · stop 3.95 · risk 4.1%';
  patch(b);
  return b;
}
const zone = (extra: Record<string, unknown> = {}) => ({ kind: 'gg_entry', lo: 3.18, hi: 3.42, label: LABEL, note: NOTE, ...extra });

let siCalls: string[] = [];
let boardCalls: string[] = [];
function stub(payload: any, siFails = false) {
  siCalls = [];
  boardCalls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/short-interest/map')) {
      siCalls.push(String(url));
      if (siFails) throw new Error('down');
      const q = (u.searchParams.get('symbols') || '').split(',');
      const items: Record<string, unknown> = {};
      for (const s of q) if (SI[s]) items[s] = SI[s];
      return ok({ items, n: Object.keys(items).length, max_symbols: 200 });
    }
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.includes('/chart-maps/gajjala')) { boardCalls.push(u.pathname); return ok(payload); }
    return ok({});
  }));
}

async function mount(payload: any, variant: GgVariantKey = 'gajjala', siFails = false) {
  stub(payload, siFails);
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps?tab=${variant}&sub=reversal_squeeze`]}>
      <GajjalaBoard variant={variant} />
    </MemoryRouter>,
  );
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  await screen.findByTestId(`gg-tile-${SQ}`);
  return r;
}
/** Wait for the bulk SI GET to answer (the flush is debounced) and the listeners to re-render. */
const settleSi = () => waitFor(() => expect(siCalls.length).toBeGreaterThan(0)).then(() => new Promise((r) => setTimeout(r, 20)));
const count = (hay: string, needle: string) => hay.split(needle).length - 1;

describe('🎾 short-interest label on a Reversal Squeeze card', () => {
  beforeEach(() => {
    _resetShortInterestCache();
    chartProps.length = 0;
    SI = { [SQ]: siOk(SQ, SQ_CHIP), [BF]: siOk(BF, BF_CHIP) };
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('prints the SERVED chip text with the SERVED title under the plan, inside the card extras', async () => {
    await mount(board());
    const el = await screen.findByTestId(`gg-si-label-${SQ}`);
    expect(el.textContent).toBe(SQ_CHIP);
    expect(el.getAttribute('title')).toBe(TITLE);
    expect(el.className).toContain('gg-si-label');
    const extras = within(screen.getByTestId(`gg-tile-${SQ}`)).getByTestId('gg-extras');
    expect(extras.contains(el)).toBe(true);
    expect(within(extras).getByTestId('gg-plan').nextElementSibling).toBe(el);
  });

  it('[C7] the SI text prints exactly ONCE on the 🎾 card — no muted chip in its head row', async () => {
    await mount(board());
    await screen.findByTestId(`gg-si-label-${SQ}`);
    const head = screen.getByTestId(`gg-chips-${SQ}`);
    expect(within(head).queryByTestId('si-chip')).toBeNull();
    expect(head.textContent).not.toContain('🩳');
    expect(count(screen.getByTestId(`gg-tile-${SQ}`).textContent || '', SQ_CHIP)).toBe(1);
    const sq = chartProps.filter((p) => p.tile.symbol === SQ).pop();
    expect(sq.outerChips).toContain('short');            // PatternChart still skips its own copy
  });

  it('[C7] NEGATIVE: the bull_flag card on the same board keeps its muted chip and gets no label', async () => {
    await mount(board());
    const head = screen.getByTestId(`gg-chips-${BF}`);
    const chip = await within(head).findByTestId('si-chip');
    expect(chip.textContent).toBe(BF_CHIP);
    expect(chip.className).toBe('cm-badge cm-badge-muted');
    expect(screen.queryByTestId(`gg-si-label-${BF}`)).toBeNull();
    expect(count(screen.getByTestId(`gg-tile-${BF}`).textContent || '', BF_CHIP)).toBe(1);
  });

  it('the board issues ONE /short-interest/map GET for the whole grid (label + chip share the hook)', async () => {
    await mount(board());
    await screen.findByTestId(`gg-si-label-${SQ}`);
    await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
    expect(siCalls).toHaveLength(1);
    const syms = new URL(siCalls[0], 'http://x').searchParams.get('symbols')!.split(',').sort();
    expect(syms).toEqual([BF, SQ].sort());
  });

  it('a stale read carries gg-si-stale and the served stale word', async () => {
    SI[SQ] = siOk(SQ, '🩳 SI 30.6% shs out · 5.0d · 8/31 · stale', 'stale');
    await mount(board());
    const el = await screen.findByTestId(`gg-si-label-${SQ}`);
    expect(el.className).toContain('gg-si-stale');
    expect(el.textContent).toMatch(/· stale$/);
  });

  for (const v of ['gajjala_1m', 'gajjala_audited'] as const) {
    it(`the label appears on the ${v} board too (all three tabs), from that page's GET`, async () => {
      await mount(board((b) => { b.tab = v; }), v);
      expect((await screen.findByTestId(`gg-si-label-${SQ}`)).textContent).toBe(SQ_CHIP);
      expect(boardCalls.every((p) => p.endsWith(v === 'gajjala_1m' ? '/chart-maps/gajjala-1m' : '/chart-maps/gajjala-audited'))).toBe(true);
      expect(within(screen.getByTestId(`gg-chips-${SQ}`)).queryByTestId('si-chip')).toBeNull();
    });
  }

  it('a 🧠-style tile whose primary read is the squeeze gets the label on another sub', async () => {
    await mount(board((b) => { b.sub = 'potential'; }));
    expect(await screen.findByTestId(`gg-si-label-${SQ}`)).toBeTruthy();
  });

  it('NEGATIVE: a no_record block → no label and no chip anywhere on the 🎾 card', async () => {
    SI[SQ] = { symbol: SQ, status: 'no_record', chip: null, title: 'no FINRA record — not read.', rows: [] };
    await mount(board());
    await settleSi();
    await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
    expect(screen.queryByTestId(`gg-si-label-${SQ}`)).toBeNull();
    expect(screen.getByTestId(`gg-tile-${SQ}`).textContent).not.toContain('🩳');
  });

  it('NEGATIVE: an absent symbol → no label, never a 0', async () => {
    delete SI[SQ];
    await mount(board());
    await settleSi();
    await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
    expect(screen.queryByTestId(`gg-si-label-${SQ}`)).toBeNull();
    expect(screen.getByTestId(`gg-tile-${SQ}`).textContent).not.toMatch(/SI 0|0\.0%/);
  });

  it('NEGATIVE: a failed SI fetch → no label, no chip, the board still draws', async () => {
    await mount(board(), 'gajjala', true);
    await settleSi();
    expect(screen.queryByTestId(`gg-si-label-${SQ}`)).toBeNull();
    expect(screen.queryAllByTestId('si-chip')).toHaveLength(0);
    expect(screen.getByTestId(`gg-tile-${BF}`)).toBeTruthy();
  });

  it('NEGATIVE: a squeeze card whose read is another setup (bull_flag) keeps the chip and gets no label', async () => {
    await mount(board((b) => { b.tiles[0].gajjala.setup = 'bull_flag'; }));
    const chip = await within(screen.getByTestId(`gg-chips-${SQ}`)).findByTestId('si-chip');
    expect(chip.textContent).toBe(SQ_CHIP);
    expect(screen.queryByTestId(`gg-si-label-${SQ}`)).toBeNull();
  });

  it('NEGATIVE: a tile with no gajjala read keeps the chip and gets no label', async () => {
    await mount(board((b) => { delete b.tiles[0].gajjala; }));
    expect(await within(screen.getByTestId(`gg-chips-${SQ}`)).findByTestId('si-chip')).toBeTruthy();
    expect(screen.queryByTestId(`gg-si-label-${SQ}`)).toBeNull();
  });
});

describe('🧪 entry-zone card line — prints the served band note [C1]', () => {
  beforeEach(() => {
    _resetShortInterestCache();
    chartProps.length = 0;
    SI = {};
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('prints bands[0].note verbatim and NOT the short label; the chart still gets the band', async () => {
    await mount(board((b) => { b.tiles[0].bands = [zone()]; }), 'gajjala_1m');
    const el = screen.getByTestId(`gg-zone-${SQ}`);
    expect(el.textContent).toBe(NOTE);
    expect(el.textContent).not.toContain(LABEL);
    expect(el.className).toBe('cm-note gg-line gg-zone');
    const sq = chartProps.filter((p) => p.tile.symbol === SQ).pop();
    expect(sq.tile.bands).toEqual([zone()]);
    expect(screen.getAllByTestId(/^gg-zone-/)).toHaveLength(1);
  });

  it('the line sits under the chart, above the card extras', async () => {
    await mount(board((b) => { b.tiles[0].bands = [zone()]; }), 'gajjala_audited');
    const el = screen.getByTestId(`gg-zone-${SQ}`);
    expect(el.previousElementSibling).toBe(screen.getByTestId(`chart-${SQ}`));
    expect(el.nextElementSibling?.getAttribute('data-testid')).toBe('gg-extras');
  });

  it('NEGATIVE: bands [] (the GG5 payload) → no zone line', async () => {
    await mount(board());
    expect(screen.queryAllByTestId(/^gg-zone-/)).toHaveLength(0);
  });

  it('NEGATIVE: a gg_entry band WITHOUT a note, with a blank note or a non-string note → no line', async () => {
    const { unmount } = await mount(board((b) => {
      const { note: _n, ...noNote } = zone();
      b.tiles[0].bands = [noNote];
      b.tiles[1].bands = [zone({ note: '   ' })];
    }));
    expect(screen.queryAllByTestId(/^gg-zone-/)).toHaveLength(0);
    unmount();
    _resetShortInterestCache();
    await mount(board((b) => { b.tiles[0].bands = [zone({ note: 98765 })]; }));
    expect(screen.queryAllByTestId(/^gg-zone-/)).toHaveLength(0);
    expect(screen.getByTestId(`gg-tile-${SQ}`).textContent).not.toContain('98765');
  });

  it('NEGATIVE: a band of another kind carrying a note → no zone line', async () => {
    await mount(board((b) => {
      b.tiles[0].bands = [{ kind: 'demand', lo: 3.0, hi: 3.1, label: 'demand', note: 'not a zone sentence' }];
    }));
    expect(screen.queryAllByTestId(/^gg-zone-/)).toHaveLength(0);
    expect(screen.getByTestId(`gg-tile-${SQ}`).textContent).not.toContain('not a zone sentence');
  });

  it('NEGATIVE: absent bands key (an older API) → no line, no throw', async () => {
    await mount(board((b) => { delete b.tiles[0].bands; }));
    expect(screen.queryAllByTestId(/^gg-zone-/)).toHaveLength(0);
  });
});
