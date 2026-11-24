import '../test/ggCardWatchOff';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetRegShoCache } from '../hooks/useRegSho';
import { _resetBorrowCache } from '../hooks/useBorrow';
import { _resetSsrCache } from '../hooks/useSsr';
import type { GgVariantKey } from './ggVariant';

/* ⛔ SSR tag on the REAL Gajjala board (2026-11-23, spec ssr §3.10 / §4 W4).
 *
 * Ajay 2026-11-23: "No shorting at the bid (SEC short-sale restriction)
 * Can we check or this for other stocks too?"
 *
 * The real ⛔ chip / label / fault read a stubbed GET /short-interest/ssr?symbols=…; the real 🩳, 🔒 and 💸 pieces read
 * their own stubbed routes (none is mocked). Boards are CLONES of the frozen 2026-10-13 hand fixture: FCHL = the 🎾 card,
 * PFAI = a bull_flag card. Order on a surface: 🩳 → 🔒 → 💸 → ⛔. Every word is a stand-in for a served one. */

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
const siBlock = (sym: string) => ({ symbol: sym, status: 'ok', chip: `🩳 served si chip ${sym}`, title: 'served si title', rows: [], extreme: null });
const htb = (sym: string) => ({
  state: 'on', symbol: sym, market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: `served 🔒 chip ${sym}`, short: `served 🔒 short ${sym}`, label: `served 🔒 label ${sym}`, title: `served 🔒 title ${sym}`,
});
const rs = (items: Record<string, unknown>) => ({
  kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items, fault_text: null, refreshing: false, retry_after_sec: null,
});
const listed = (sym: string) => ({
  state: 'listed', symbol: sym, name: `SERVED CO ${sym}`, chip: `💸 served chip ${sym}`, short: `💸 served short ${sym}`,
  label: `💸 served label ${sym}`, title: `served 💸 title ${sym}`, stale: false,
});
const br = (items: Record<string, unknown>) => ({
  kind: 'ibkr_borrow', status: 'ok', stale: false, items, asked: 2, n: Object.keys(items).length, max_symbols: 200,
  refreshing: false, retry_after_sec: null, keep_sec: 3600,
});
const on = (sym: string, over: Record<string, unknown> = {}) => ({
  state: 'on', symbol: sym, source: 'official', chip: `⛔ served chip ${sym}`, short: `⛔ served short ${sym}`,
  label: `⛔ served label ${sym}`, title: `served ⛔ title ${sym}`, ...over,
});
const unknown = (sym: string) => ({ state: 'unknown', symbol: sym, why: 'corp_action', chip: null, short: null, label: `⛔ served unknown label ${sym}`, title: `served unknown title ${sym}` });
const ssr = (items: Record<string, unknown>, over: Record<string, unknown> = {}) => ({
  kind: 'ssr_rule_201', status: 'ok', items, states: {}, whys: {}, asked: 2, n: Object.keys(items).length, max_symbols: 200,
  fault_text: null, refreshing: false, retry_after_sec: null, keep_sec: 300, ...over,
});

let SI: Record<string, unknown> = {};
let RS: unknown = rs({});
let BR: unknown = br({});
let SSR: unknown = ssr({});
let ssrMode: 'ok' | 'throw' = 'ok';

function board(patch: (b: any) => void = () => {}): any {
  const b = clone(BOARDS.reversal_squeeze);
  b.session = { ...b.session, refresh_sec: 0 };
  b.tiles = [clone(BOARDS.reversal_squeeze.tiles[0]), clone(BOARDS.bull_flag.tiles[0])];
  b.tiles[0].gajjala.plan_text = 'Entry above 3.42 · stop 3.18 · risk 7.0%';
  b.tiles[1].gajjala.plan_text = 'Entry above 4.12 · stop 3.95 · risk 4.1%';
  patch(b);
  return b;
}

let ssrCalls: string[] = [];
let brCalls: string[] = [];
function stub(payload: any) {
  ssrCalls = [];
  brCalls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/short-interest/ssr')) {
      ssrCalls.push(String(url));
      if (ssrMode === 'throw') throw new Error('down');
      return ok(SSR);
    }
    if (u.pathname.endsWith('/short-interest/borrow')) { brCalls.push(String(url)); return ok(BR); }
    if (u.pathname.endsWith('/short-interest/reg-sho')) return ok(RS);
    if (u.pathname.endsWith('/short-interest/map')) {
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
const settle = () => waitFor(() => expect(ssrCalls.length).toBeGreaterThan(0)).then(() => new Promise((r) => setTimeout(r, 20)));
const asked = (url: string) => (new URL(url, 'http://x').searchParams.get('symbols') || '').split(',').sort();
const resetAll = () => { _resetSsrCache(); _resetBorrowCache(); _resetRegShoCache(); _resetShortInterestCache(); };

beforeEach(() => {
  resetAll();
  SI = { [SQ]: siBlock(SQ), [BF]: siBlock(BF) };
  RS = rs({ [SQ]: htb(SQ), [BF]: htb(BF) });
  BR = br({ [SQ]: listed(SQ), [BF]: listed(BF) });
  SSR = ssr({ [SQ]: on(SQ), [BF]: on(BF) });
  ssrMode = 'ok';
});
afterEach(() => { vi.unstubAllGlobals(); resetAll(); });

for (const variant of ['gajjala', 'gajjala_audited'] as const) {
  const pay = () => board((b) => { b.tab = variant; });

  describe(`⛔ on the card grid — ${variant}`, () => {
    it('the 🎾 card prints the served label as the next sibling of the 💸 label; NO ⛔ chip in its head row', async () => {
      await mount(pay(), variant);
      const el = await screen.findByTestId(`gg-ssr-label-${SQ}`);
      const brw = await screen.findByTestId(`gg-brw-label-${SQ}`);
      expect(el.textContent).toBe(on(SQ).label);
      expect(el.getAttribute('title')).toBe(on(SQ).title);
      expect(el.className).toBe('cm-note gg-line gg-ssr-label');
      expect(el.getAttribute('data-ssr-state')).toBe('on');
      expect(brw.nextElementSibling).toBe(el);
      expect(within(screen.getByTestId(`gg-tile-${SQ}`)).getByTestId('gg-extras').contains(el)).toBe(true);
      expect(screen.getByTestId(`gg-chips-${SQ}`).querySelector('.gg-ssr')).toBeNull();
      expect(screen.queryByTestId(`gg-ssr-${SQ}`)).toBeNull();
      expect(screen.getByTestId(`gg-tile-${SQ}`).querySelectorAll('.gg-ssr, .gg-ssr-label')).toHaveLength(1);
    });

    it('a non-🎾 card prints the served chip right after the 💸 chip (one leading space); no label', async () => {
      await mount(pay(), variant);
      const head = screen.getByTestId(`gg-chips-${BF}`);
      const chip = await within(head).findByTestId(`gg-ssr-${BF}`);
      const brw = await within(head).findByTestId(`gg-brw-${BF}`);
      expect(chip.textContent).toBe(on(BF).chip);
      expect(chip.getAttribute('title')).toBe(on(BF).title);
      expect(chip.className).toBe('cm-badge gg-ssr');
      expect(brw.nextElementSibling).toBe(chip);
      expect(chip.previousSibling!.textContent).toBe(' ');
      expect(screen.queryByTestId(`gg-ssr-label-${BF}`)).toBeNull();
      expect(screen.getByTestId(`gg-tile-${BF}`).querySelectorAll('.gg-ssr, .gg-ssr-label')).toHaveLength(1);
    });

    it('ONE ssr GET carrying both symbols; still ONE borrow GET', async () => {
      await mount(pay(), variant);
      await screen.findByTestId(`gg-ssr-label-${SQ}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-ssr-${BF}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-brw-${BF}`);
      expect(ssrCalls).toHaveLength(1);
      expect(asked(ssrCalls[0])).toEqual([BF, SQ].sort());
      expect(brCalls).toHaveLength(1);
    });

    it('the served fault line prints once above the grid when served', async () => {
      SSR = ssr({ [SQ]: on(SQ), [BF]: on(BF) }, { fault_text: '⛔ served fault line' });
      await mount(pay(), variant);
      const f = await screen.findByTestId('gg-ssr-fault');
      expect(f.textContent).toBe('⛔ served fault line');
      expect(f.className).toBe('cm-note cm-note-err gg-ssr-fault');
      expect(screen.getAllByTestId('gg-ssr-fault')).toHaveLength(1);
    });
  });
}

describe('⛔ board — positives', () => {
  it('no 🔒 and no 💸 on either name: the 🎾 label sits directly under the 🩳 label, the chip right after the si-chip', async () => {
    RS = rs({});
    BR = br({});
    await mount(board());
    const el = await screen.findByTestId(`gg-ssr-label-${SQ}`);
    expect((await screen.findByTestId(`gg-si-label-${SQ}`)).nextElementSibling).toBe(el);
    const head = screen.getByTestId(`gg-chips-${BF}`);
    const chip = await within(head).findByTestId(`gg-ssr-${BF}`);
    expect((await within(head).findByTestId('si-chip')).nextElementSibling).toBe(chip);
  });

  it('an unknown with a served label → the label on the 🎾 card, NOTHING on a non-🎾 card', async () => {
    SSR = ssr({ [SQ]: unknown(SQ), [BF]: unknown(BF) });
    await mount(board());
    const l = await screen.findByTestId(`gg-ssr-label-${SQ}`);
    expect(l.textContent).toBe(unknown(SQ).label);
    expect(l.getAttribute('data-ssr-state')).toBe('unknown');
    await settle();
    await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-brw-${BF}`);
    expect(screen.queryByTestId(`gg-ssr-${BF}`)).toBeNull();
    expect(screen.getByTestId(`gg-tile-${BF}`).querySelector('.gg-ssr, .gg-ssr-label')).toBeNull();
  });
});

describe('⛔ board — NEGATIVES', () => {
  it('no fault_text served → no gg-ssr-fault node', async () => {
    await mount(board());
    await screen.findByTestId(`gg-ssr-label-${SQ}`);
    expect(screen.queryByTestId('gg-ssr-fault')).toBeNull();
  });

  it('off (no item) → nothing on either card', async () => {
    SSR = ssr({}, { states: { [SQ]: 'off', [BF]: 'off' } });
    const { container } = await mount(board());
    await settle();
    await screen.findByTestId(`gg-brw-label-${SQ}`);
    expect(container.querySelector('.gg-ssr, .gg-ssr-label, .gg-ssr-fault')).toBeNull();
  });

  for (const [name, setup] of [
    ['a failed GET', () => { ssrMode = 'throw'; }],
    ['a foreign body (the 💸 payload)', () => { SSR = br({ [SQ]: listed(SQ), [BF]: listed(BF) }); }],
    ['a foreign body ({})', () => { SSR = {}; }],
  ] as const) {
    it(`the card order, the sort and every other chip are unchanged with and without the payload (${name})`, async () => {
      const a = await mount(board());
      await settle();
      const chipA = await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-ssr-${BF}`);
      const labelA = await screen.findByTestId(`gg-ssr-label-${SQ}`);
      await screen.findByTestId(`gg-brw-label-${SQ}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');   // 2026-11-24 verify: wait for every async chip before the byte capture
      const orderA = Array.from(a.container.querySelectorAll('[data-testid^="gg-tile-"]')).map((n) => n.getAttribute('data-testid'));
      const headA = screen.getByTestId(`gg-chips-${BF}`).innerHTML.replace(` ${chipA.outerHTML}`, '');
      const sqA = screen.getByTestId(`gg-tile-${SQ}`).innerHTML.replace(labelA.outerHTML, '');
      const bfA = screen.getByTestId(`gg-tile-${BF}`).innerHTML.replace(` ${chipA.outerHTML}`, '');
      a.unmount();
      resetAll();
      setup();
      const b = await mount(board());
      await settle();
      await screen.findByTestId(`gg-brw-label-${SQ}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-brw-${BF}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
      const orderB = Array.from(b.container.querySelectorAll('[data-testid^="gg-tile-"]')).map((n) => n.getAttribute('data-testid'));
      expect(orderB).toEqual(orderA);
      expect(screen.getByTestId(`gg-chips-${BF}`).innerHTML).toBe(headA);
      expect(screen.getByTestId(`gg-tile-${SQ}`).innerHTML).toBe(sqA);
      expect(screen.getByTestId(`gg-tile-${BF}`).innerHTML).toBe(bfA);
      expect(b.container.querySelector('.gg-ssr, .gg-ssr-label, .gg-ssr-fault')).toBeNull();
      expect(ssrCalls).toHaveLength(1);
    });
  }

  it('exact match: AKAN served → an AKANW card and an AKA card show nothing', async () => {
    SSR = ssr({ AKAN: on('AKAN') });
    const pay = board((b) => { b.tiles[0].symbol = 'AKANW'; b.tiles[1].symbol = 'AKA'; });
    const { container } = await mount(pay);
    await settle();
    await screen.findByTestId('gg-tile-AKANW');
    expect(container.querySelector('.gg-ssr, .gg-ssr-label')).toBeNull();
  });
});

/* ── source guard ── */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('⛔ source guard — GajjalaBoard.tsx mounts', () => {
  const PAIRS: Array<[string, string]> = [
    ["import { GgBorrowChip, GgBorrowLabel } from './GgBorrow';", "import { GgSsrChip, GgSsrFault, GgSsrLabel } from './GgSsr';"],
    ['<GgHardToBorrowFault testid="gg-htb-fault" />', '<GgSsrFault testid="gg-ssr-fault" />'],
    ["{t.gajjala?.setup !== 'reversal_squeeze' ? <GgBorrowChip symbol={t.symbol} testid={`gg-brw-${t.symbol}`} lead /> : null}",
      "{t.gajjala?.setup !== 'reversal_squeeze' ? <GgSsrChip symbol={t.symbol} testid={`gg-ssr-${t.symbol}`} lead /> : null}"],
    ["{read.setup === 'reversal_squeeze' ? <GgBorrowLabel symbol={sym} testid={`gg-brw-label-${sym}`} /> : null}",
      "{read.setup === 'reversal_squeeze' ? <GgSsrLabel symbol={sym} testid={`gg-ssr-label-${sym}`} /> : null}"],
  ];

  it('each ⛔ line sits directly after its 💸 / 🔒 line; mounted exactly once each; never on the 📋 table', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    const lines = src.split('\n').map((l) => l.trim());
    for (const [prev, mine] of PAIRS) {
      const idx = lines.map((l, i) => (l === prev ? i : -1)).filter((i) => i >= 0);
      expect(idx.length, prev).toBeGreaterThan(0);
      expect(idx.some((i) => lines[i + 1] === mine), mine).toBe(true);
      expect(lines.filter((l) => l === mine), mine).toHaveLength(1);
    }
    expect(src.match(/<GgSsrChip /g) || []).toHaveLength(1);
    expect(src.match(/<GgSsrLabel /g) || []).toHaveLength(1);
    expect(src.match(/<GgSsrFault /g) || []).toHaveLength(1);
    expect(src).not.toMatch(/useSsr/);
    const table = src.indexOf('<GgAllTable');
    const fault = src.indexOf('<GgSsrFault');
    const tableFault = src.lastIndexOf('<GgHardToBorrowFault testid="gg-htb-fault" />', table);
    expect(src.slice(tableFault, table)).not.toMatch(/GgSsr/);
    expect(fault).toBeGreaterThan(table);
  });

  it('NEGATIVE: the adjacency check fails when the ⛔ line drifts away from its 💸 line', () => {
    const [prev, mine] = PAIRS[2];
    const lines = [prev, '{/* a comment between */}', mine];
    expect(lines[lines.indexOf(prev) + 1]).not.toBe(mine);
  });
});
