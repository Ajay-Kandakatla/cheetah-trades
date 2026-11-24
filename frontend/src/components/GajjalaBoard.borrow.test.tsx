import '../test/ggCardWatchOff';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetRegShoCache } from '../hooks/useRegSho';
import { _resetBorrowCache } from '../hooks/useBorrow';
import type { GgVariantKey } from './ggVariant';

/* 💸 Borrow read on the REAL Gajjala board (2026-11-22, spec borrow §3.4 / §4 fe part B).
 *
 * Ajay 2026-11-22: "What is short borrow fee? Is that a real time value I saw AKAN has a high short borrow fee" — "yes i
 * need that please".
 *
 * The real 💸 chip / label read a stubbed GET /short-interest/borrow?symbols=…; the real 🔒 and 🩳 pieces read their own
 * stubbed routes (none is mocked). Boards are CLONES of the frozen 2026-10-13 hand fixture: FCHL = the 🎾 card, PFAI = a
 * bull_flag card. Order on a surface: 🩳 → 🔒 → 💸. Every word is a stand-in for a served one. */

vi.mock('./PatternChart', () => ({
  PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} />,
}));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => {} }));

import GajjalaBoard from './GajjalaBoard';

const BOARDS: Record<string, any> = (fixture as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const SQ = 'FCHL';
const BF = 'PFAI';
const SI_TITLE = '🩳 Short interest — served title.';
const siBlock = (sym: string) => ({ symbol: sym, status: 'ok', chip: `🩳 served si chip ${sym}`, title: SI_TITLE, rows: [], extreme: null });
const htb = (sym: string) => ({
  state: 'on', symbol: sym, market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: `served 🔒 chip ${sym}`, short: `served 🔒 short ${sym}`, label: `served 🔒 label ${sym}`, title: `served 🔒 title ${sym}`,
});
const rs = (items: Record<string, unknown>) => ({
  kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items, fault_text: null, refreshing: false, retry_after_sec: null,
});
const listed = (sym: string, over: Record<string, unknown> = {}) => ({
  state: 'listed', symbol: sym, name: `SERVED CO ${sym}`, chip: `💸 served chip ${sym}`, short: `💸 served short ${sym}`,
  label: `💸 served label ${sym}`, title: `served 💸 title ${sym}`, stale: false,
  fee_pct: 196.2308, rebate_pct: -192.3508, available: 100000, available_floor: false, ...over,
});
const absent = (sym: string, over: Record<string, unknown> = {}) => ({
  state: 'absent', symbol: sym, name: null, chip: null, short: null, label: `💸 served absent label ${sym}`,
  title: `served absent title ${sym}`, stale: false, fee_pct: null, rebate_pct: null, available: null, available_floor: false, ...over,
});
const br = (items: Record<string, unknown>, over: Record<string, unknown> = {}) => ({
  kind: 'ibkr_borrow', status: 'ok', stale: false, items, asked: 2, n: Object.keys(items).length, max_symbols: 200,
  refreshing: false, retry_after_sec: null, keep_sec: 3600, ...over,
});

let SI: Record<string, unknown> = {};
let RS: unknown = rs({});
let BR: unknown = br({});
let brMode: 'ok' | 'throw' = 'ok';

function board(patch: (b: any) => void = () => {}): any {
  const b = clone(BOARDS.reversal_squeeze);
  b.session = { ...b.session, refresh_sec: 0 };
  b.tiles = [clone(BOARDS.reversal_squeeze.tiles[0]), clone(BOARDS.bull_flag.tiles[0])];
  b.tiles[0].gajjala.plan_text = 'Entry above 3.42 · stop 3.18 · risk 7.0%';
  b.tiles[1].gajjala.plan_text = 'Entry above 4.12 · stop 3.95 · risk 4.1%';
  patch(b);
  return b;
}

let siCalls: string[] = [];
let rsCalls: string[] = [];
let brCalls: string[] = [];
function stub(payload: any) {
  siCalls = [];
  rsCalls = [];
  brCalls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/short-interest/borrow')) {
      brCalls.push(String(url));
      if (brMode === 'throw') throw new Error('down');
      return ok(BR);
    }
    if (u.pathname.endsWith('/short-interest/reg-sho')) { rsCalls.push(String(url)); return ok(RS); }
    if (u.pathname.endsWith('/short-interest/map')) {
      siCalls.push(String(url));
      const q = (u.searchParams.get('symbols') || '').split(',');
      const items: Record<string, unknown> = {};
      for (const s of q) if (SI[s]) items[s] = SI[s];
      return ok({ items, n: Object.keys(items).length, max_symbols: 200 });
    }
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.endsWith('/chart-maps/live')) return ok({});
    if (u.pathname.includes('/chart-maps/gajjala')) return ok(payload);
    return ok({});
  }));
}

const tree = (variant: GgVariantKey, sub: string) => (
  <MemoryRouter initialEntries={[`/chart-maps?tab=${variant}&sub=${sub}`]}>
    <GajjalaBoard variant={variant} />
  </MemoryRouter>
);
async function mount(payload: any, variant: GgVariantKey = 'gajjala', sub = 'reversal_squeeze') {
  stub(payload);
  const r = render(tree(variant, sub));
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  return r;
}
const settle = () => waitFor(() => expect(brCalls.length).toBeGreaterThan(0)).then(() => new Promise((r) => setTimeout(r, 20)));
const asked = (url: string) => (new URL(url, 'http://x').searchParams.get('symbols') || '').split(',').sort();

beforeEach(() => {
  _resetShortInterestCache();
  _resetRegShoCache();
  _resetBorrowCache();
  SI = { [SQ]: siBlock(SQ), [BF]: siBlock(BF) };
  RS = rs({ [SQ]: htb(SQ), [BF]: htb(BF) });
  BR = br({ [SQ]: listed(SQ), [BF]: listed(BF) });
  brMode = 'ok';
});
afterEach(() => { vi.unstubAllGlobals(); _resetBorrowCache(); _resetRegShoCache(); _resetShortInterestCache(); });

for (const variant of ['gajjala', 'gajjala_audited'] as const) {
  const pay = () => board((b) => { b.tab = variant; });

  describe(`💸 on the card grid — ${variant}`, () => {
    it('the 🎾 card prints the served label as the next sibling of the 🔒 label; no 💸 chip in its head row', async () => {
      await mount(pay(), variant);
      const el = await screen.findByTestId(`gg-brw-label-${SQ}`);
      const lock = await screen.findByTestId(`gg-htb-label-${SQ}`);
      expect(el.textContent).toBe(listed(SQ).label);
      expect(el.getAttribute('title')).toBe(listed(SQ).title);
      expect(el.className).toBe('cm-note gg-line gg-brw-label');
      expect(el.getAttribute('data-brw-state')).toBe('listed');
      expect(lock.nextElementSibling).toBe(el);
      expect(within(screen.getByTestId(`gg-tile-${SQ}`)).getByTestId('gg-extras').contains(el)).toBe(true);
      expect(screen.getByTestId(`gg-chips-${SQ}`).querySelector('.gg-brw')).toBeNull();
      expect(screen.getByTestId(`gg-tile-${SQ}`).querySelectorAll('.gg-brw, .gg-brw-label')).toHaveLength(1);
    });

    it('a non-🎾 card prints the served chip right after the 🔒 chip; no label', async () => {
      await mount(pay(), variant);
      const head = screen.getByTestId(`gg-chips-${BF}`);
      const chip = await within(head).findByTestId(`gg-brw-${BF}`);
      const lock = await within(head).findByTestId(`gg-htb-${BF}`);
      expect(chip.textContent).toBe(listed(BF).chip);
      expect(chip.getAttribute('title')).toBe(listed(BF).title);
      expect(chip.className).toBe('cm-badge gg-brw');
      expect(lock.nextElementSibling).toBe(chip);
      expect(chip.previousSibling!.textContent).toBe(' ');
      expect(screen.queryByTestId(`gg-brw-label-${BF}`)).toBeNull();
      expect(screen.getByTestId(`gg-tile-${BF}`).querySelectorAll('.gg-brw, .gg-brw-label')).toHaveLength(1);
    });

    it('ONE borrow GET carrying both symbols; still ONE reg-sho GET and ONE map GET', async () => {
      await mount(pay(), variant);
      await screen.findByTestId(`gg-brw-label-${SQ}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-brw-${BF}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-htb-${BF}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
      expect(brCalls).toHaveLength(1);
      expect(asked(brCalls[0])).toEqual([BF, SQ].sort());
      expect(rsCalls).toHaveLength(1);
      expect(siCalls).toHaveLength(1);
    });

    it('[C9] a second and a third render of the same board make no further borrow GET', async () => {
      const r = await mount(pay(), variant);
      await screen.findByTestId(`gg-brw-label-${SQ}`);
      expect(brCalls).toHaveLength(1);
      r.rerender(tree(variant, 'reversal_squeeze'));
      await new Promise((res) => setTimeout(res, 20));
      r.rerender(tree(variant, 'reversal_squeeze'));
      await new Promise((res) => setTimeout(res, 20));
      expect(screen.getByTestId(`gg-brw-label-${SQ}`).textContent).toBe(listed(SQ).label);
      expect(brCalls).toHaveLength(1);
    });
  });
}

describe('💸 board — more positives', () => {
  it('no 🔒 on either name: the 🎾 label sits directly under the 🩳 label, the chip right after the si-chip', async () => {
    RS = rs({});
    await mount(board());
    const el = await screen.findByTestId(`gg-brw-label-${SQ}`);
    expect((await screen.findByTestId(`gg-si-label-${SQ}`)).nextElementSibling).toBe(el);
    const head = screen.getByTestId(`gg-chips-${BF}`);
    const chip = await within(head).findByTestId(`gg-brw-${BF}`);
    expect((await within(head).findByTestId('si-chip')).nextElementSibling).toBe(chip);
    expect(head.querySelector('.gg-htb')).toBeNull();
  });

  it('[C1] an absent name served WITH a chip → that chip on a non-🎾 card (the server switch, no FE change)', async () => {
    BR = br({ [SQ]: absent(SQ), [BF]: absent(BF, { chip: `💸 served absent chip ${BF}` }) });
    await mount(board());
    const chip = await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-brw-${BF}`);
    expect(chip.textContent).toBe(`💸 served absent chip ${BF}`);
    expect(chip.getAttribute('data-brw-state')).toBe('absent');
    expect((await screen.findByTestId(`gg-brw-label-${SQ}`)).textContent).toBe(absent(SQ).label);
  });

  it('stale → gg-brw-stale on the label and the chip, the served text verbatim', async () => {
    BR = br({ [SQ]: listed(SQ, { stale: true, label: 'served label · file 3h old' }), [BF]: listed(BF, { stale: true, chip: 'served chip · file 3h old' }) });
    await mount(board());
    const l = await screen.findByTestId(`gg-brw-label-${SQ}`);
    expect(l.className).toBe('cm-note gg-line gg-brw-label gg-brw-stale');
    expect(l.textContent).toBe('served label · file 3h old');
    expect((await screen.findByTestId(`gg-brw-${BF}`)).className).toBe('cm-badge gg-brw gg-brw-stale');
  });
});

describe('💸 board — NEGATIVES', () => {
  it('an absent name served label-only → the label on the 🎾 card, NOTHING on a non-🎾 card', async () => {
    BR = br({ [SQ]: absent(SQ), [BF]: absent(BF) });
    await mount(board());
    expect((await screen.findByTestId(`gg-brw-label-${SQ}`)).textContent).toBe(absent(SQ).label);
    await settle();
    await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-htb-${BF}`);
    expect(screen.queryByTestId(`gg-brw-${BF}`)).toBeNull();
    expect(screen.getByTestId(`gg-tile-${BF}`).querySelector('.gg-brw, .gg-brw-label')).toBeNull();
  });

  for (const [name, setup] of [
    ['a failed GET', () => { brMode = 'throw'; }],
    ['a foreign body (the 🔒 payload)', () => { BR = rs({ [SQ]: htb(SQ), [BF]: htb(BF) }); }],
    ['a foreign body ({})', () => { BR = {}; }],
  ] as const) {
    it(`${name} → each tile's innerHTML equals a board with no borrow answer`, async () => {
      BR = br({});
      const a = await mount(board());
      await settle();
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-htb-${BF}`);
      await screen.findByTestId(`gg-htb-label-${SQ}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
      await screen.findByTestId(`gg-si-label-${SQ}`);
      const bfA = screen.getByTestId(`gg-tile-${BF}`).innerHTML;
      const sqA = screen.getByTestId(`gg-tile-${SQ}`).innerHTML;
      expect(a.container.querySelector('.gg-brw, .gg-brw-label')).toBeNull();
      a.unmount();
      _resetBorrowCache();
      _resetRegShoCache();
      _resetShortInterestCache();
      setup();
      const b = await mount(board());
      await settle();
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-htb-${BF}`);
      await screen.findByTestId(`gg-htb-label-${SQ}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
      await screen.findByTestId(`gg-si-label-${SQ}`);
      expect(screen.getByTestId(`gg-tile-${BF}`).innerHTML).toBe(bfA);
      expect(screen.getByTestId(`gg-tile-${SQ}`).innerHTML).toBe(sqA);
      expect(b.container.querySelector('.gg-brw, .gg-brw-label')).toBeNull();
      expect(brCalls).toHaveLength(1);
    });
  }

  it('exact match: DBGI served → a DBGIW card and a DBG card show nothing', async () => {
    BR = br({ DBGI: listed('DBGI') });
    const pay = board((b) => { b.tiles[0].symbol = 'DBGIW'; b.tiles[1].symbol = 'DBG'; });
    const { container } = await mount(pay);
    await settle();
    await screen.findByTestId('gg-tile-DBGIW');
    expect(container.querySelector('.gg-brw, .gg-brw-label')).toBeNull();
  });
});

/* ── source guard ── */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('💸 source guard — GajjalaBoard.tsx mounts', () => {
  const PAIRS: Array<[string, string]> = [
    ["import { GgHardToBorrowChip, GgHardToBorrowFault, GgHardToBorrowLabel } from './GgHardToBorrow';",
      "import { GgBorrowChip, GgBorrowLabel } from './GgBorrow';"],
    ["{t.gajjala?.setup !== 'reversal_squeeze' ? <GgHardToBorrowChip symbol={t.symbol} testid={`gg-htb-${t.symbol}`} lead /> : null}",
      "{t.gajjala?.setup !== 'reversal_squeeze' ? <GgBorrowChip symbol={t.symbol} testid={`gg-brw-${t.symbol}`} lead /> : null}"],
    ["{read.setup === 'reversal_squeeze' ? <GgHardToBorrowLabel symbol={sym} testid={`gg-htb-label-${sym}`} /> : null}",
      "{read.setup === 'reversal_squeeze' ? <GgBorrowLabel symbol={sym} testid={`gg-brw-label-${sym}`} /> : null}"],
  ];

  it('each 💸 line sits directly after its 🔒 line; the 🔒 and 🩳 mount strings are byte-for-byte unchanged', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    const lines = src.split('\n').map((l) => l.trim());
    for (const [lock, brw] of PAIRS) {
      const i = lines.indexOf(lock);
      expect(i, lock).toBeGreaterThan(-1);
      expect(lines[i + 1], brw).toBe(brw);
      expect(lines.filter((l) => l === brw), brw).toHaveLength(1);
    }
    for (const m of [
      "import { GgShortInterestLabel } from './GgShortInterestLabel';",
      "read.setup === 'reversal_squeeze' ? <GgShortInterestLabel",
      "t.gajjala?.setup !== 'reversal_squeeze' ? <>{' '}<ShortInterestChip",
    ]) expect(src).toContain(m);
    expect(src.match(/<GgHardToBorrowFault testid="gg-htb-fault" \/>/g) || []).toHaveLength(2);
    expect(src.match(/<GgBorrowChip /g) || []).toHaveLength(1);
    expect(src.match(/<GgBorrowLabel /g) || []).toHaveLength(1);
    expect(src).not.toMatch(/GgBorrowFault|useBorrow/);
  });

  it('NEGATIVE: the adjacency check fails when the 💸 line drifts away from its 🔒 line', () => {
    const [lock, brw] = PAIRS[1];
    const lines = [lock, '{/* a comment between */}', brw];
    expect(lines[lines.indexOf(lock) + 1]).not.toBe(brw);
  });
});
