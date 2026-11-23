import '../test/ggCardWatchOff';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetRegShoCache } from '../hooks/useRegSho';
import { GG_TABLE_SUB } from '../lib/gajjala';
import type { GgVariantKey } from './ggVariant';

/* 🔒 Hard to borrow tag on the REAL Gajjala board (2026-11-22, spec htb §3.4 M1 / M2 / M3 / M3b, §4 fe).
 *
 * Ajay 2026-11-22: "Can you do something for me for reversal squeezes can you also tell me if something is under when
 * it's on our list.. add a tag to stocks tickers like short interest, name the tag " hard to borrow" threshold security"
 *
 * The real chip, label and fault read a stubbed GET /short-interest/reg-sho; the real 🩳 chip and label read the stubbed
 * /short-interest/map (neither is mocked). Boards are CLONES of the frozen 2026-10-13 hand fixture: FCHL = the 🎾 card,
 * PFAI = a bull_flag card. Every word is a stand-in for a served one. */

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
const SQ_CHIP = '🩳 SI 21.9% float · 1.0d · 10/15';
const BF_CHIP = '🩳 SI 4.2% float · 2.3d · 10/15';
const SI_TITLE = '🩳 Short interest — served title.';
const item = (sym: string, over: Record<string, unknown> = {}) => ({
  state: 'on', symbol: sym, market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: `🔒 Hard to borrow · threshold security · 11/20 ${sym}`, short: `🔒 Hard to borrow · 11/20 ${sym}`,
  label: `🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 ${sym}`, title: `served title ${sym}`, ...over,
});
const FAULT = '🔒 Hard to borrow tags may be missing or out of date: Nasdaq threshold list could not be read — last good list 11/19.';
const rs = (over: Record<string, unknown> = {}) => ({
  kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items: { [SQ]: item(SQ), [BF]: item(BF) },
  fault_text: null, refreshing: false, retry_after_sec: null, ...over,
});

let SI: Record<string, unknown> = {};
let RS: unknown = rs();
let rsMode: 'ok' | 'throw' = 'ok';
const siBlock = (sym: string, chip: string) => ({ symbol: sym, status: 'ok', chip, title: SI_TITLE, rows: [], extreme: null });

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
function stub(payload: any) {
  siCalls = [];
  rsCalls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/short-interest/reg-sho')) {
      rsCalls.push(String(url));
      if (rsMode === 'throw') throw new Error('down');
      return ok(RS);
    }
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

async function mount(payload: any, variant: GgVariantKey = 'gajjala', sub = 'reversal_squeeze') {
  stub(payload);
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps?tab=${variant}&sub=${sub}`]}>
      <GajjalaBoard variant={variant} />
    </MemoryRouter>,
  );
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  return r;
}
const settle = () => waitFor(() => expect(rsCalls.length).toBeGreaterThan(0)).then(() => new Promise((r) => setTimeout(r, 20)));

beforeEach(() => {
  _resetShortInterestCache();
  _resetRegShoCache();
  SI = { [SQ]: siBlock(SQ, SQ_CHIP), [BF]: siBlock(BF, BF_CHIP) };
  RS = rs();
  rsMode = 'ok';
});
afterEach(() => { vi.unstubAllGlobals(); _resetRegShoCache(); _resetShortInterestCache(); });

for (const variant of ['gajjala', 'gajjala_1m', 'gajjala_audited'] as const) {
  const pay = () => board((b) => { b.tab = variant; });

  describe(`🔒 on the card grid — ${variant}`, () => {
    it('M2: the 🎾 card shows the served label directly under the 🩳 label, and NO chip in its head row', async () => {
      await mount(pay(), variant);
      const el = await screen.findByTestId(`gg-htb-label-${SQ}`);
      const si = await screen.findByTestId(`gg-si-label-${SQ}`);
      expect(el.textContent).toBe(item(SQ).label);
      expect(el.getAttribute('title')).toBe(item(SQ).title);
      expect(el.className).toBe('cm-note gg-line gg-htb-label');
      expect(si.nextElementSibling).toBe(el);
      expect(within(screen.getByTestId(`gg-tile-${SQ}`)).getByTestId('gg-extras').contains(el)).toBe(true);
      expect(within(screen.getByTestId(`gg-chips-${SQ}`)).queryByTestId(`gg-htb-${SQ}`)).toBeNull();
      expect(screen.getByTestId(`gg-chips-${SQ}`).querySelector('.gg-htb')).toBeNull();
      /* ONE tag per card */
      expect(screen.getByTestId(`gg-tile-${SQ}`).querySelectorAll('.gg-htb, .gg-htb-label')).toHaveLength(1);
    });

    it('M1: a non-🎾 card shows the served chip in .cm-tile-chips right after the si-chip; no label', async () => {
      await mount(pay(), variant);
      const head = screen.getByTestId(`gg-chips-${BF}`);
      const chip = await within(head).findByTestId(`gg-htb-${BF}`);
      const si = await within(head).findByTestId('si-chip');
      expect(chip.textContent).toBe(item(BF).chip);
      expect(chip.getAttribute('title')).toBe(item(BF).title);
      expect(chip.className).toBe('cm-badge gg-htb');
      expect(si.nextElementSibling).toBe(chip);
      expect(chip.previousSibling!.textContent).toBe(' ');
      expect(screen.queryByTestId(`gg-htb-label-${BF}`)).toBeNull();
      expect(screen.getByTestId(`gg-tile-${BF}`).querySelectorAll('.gg-htb, .gg-htb-label')).toHaveLength(1);
    });

    it('ONE reg-sho GET for the whole board, and still ONE /short-interest/map GET', async () => {
      await mount(pay(), variant);
      await screen.findByTestId(`gg-htb-label-${SQ}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId(`gg-htb-${BF}`);
      await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
      expect(rsCalls).toHaveLength(1);
      expect(new URL(rsCalls[0], 'http://x').search).toBe('');
      expect(siCalls).toHaveLength(1);
    });
  });
}

describe('🔒 board — more positives', () => {
  it('a listed 🎾 name with NO SI record still shows the label (the tag is independent of the SI read)', async () => {
    SI = { [BF]: siBlock(BF, BF_CHIP) };
    await mount(board());
    const el = await screen.findByTestId(`gg-htb-label-${SQ}`);
    expect(el.textContent).toBe(item(SQ).label);
    expect(screen.queryByTestId(`gg-si-label-${SQ}`)).toBeNull();
  });

  it('M3: a served fault_text draws gg-htb-fault ONCE above the card grid, verbatim', async () => {
    RS = rs({ fault_text: FAULT });
    const { container } = await mount(board());
    const f = await screen.findByTestId('gg-htb-fault');
    expect(f.textContent).toBe(FAULT);
    expect(f.className).toBe('cm-note cm-note-err gg-htb-fault');
    expect(screen.getAllByTestId('gg-htb-fault')).toHaveLength(1);
    const grid = container.querySelector('.cm-grid')!;
    expect(grid).not.toBeNull();
    expect(grid.contains(f)).toBe(false);
    expect(f.compareDocumentPosition(grid) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(f.nextElementSibling).toBe(grid);
  });

  it('stale → gg-htb-stale and the served " · stale" text on the card label and chip', async () => {
    RS = rs({ items: { [SQ]: item(SQ, { stale: true, label: 'served label · stale' }), [BF]: item(BF, { stale: true, chip: 'served chip · stale' }) } });
    await mount(board());
    const l = await screen.findByTestId(`gg-htb-label-${SQ}`);
    expect(l.className).toContain('gg-htb-stale');
    expect(l.textContent).toBe('served label · stale');
    const c = await screen.findByTestId(`gg-htb-${BF}`);
    expect(c.className).toBe('cm-badge gg-htb gg-htb-stale');
  });
});

describe('🔒 board — NEGATIVES', () => {
  it('not on the list → no tag anywhere; the card head is byte-identical to a board with no reg-sho answer', async () => {
    RS = rs({ items: {} });
    const a = await mount(board());
    await settle();
    await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
    const htmlA = screen.getByTestId(`gg-tile-${BF}`).innerHTML;
    const sqA = screen.getByTestId(`gg-tile-${SQ}`).innerHTML;
    expect(a.container.querySelector('.gg-htb, .gg-htb-label, .gg-htb-fault')).toBeNull();
    a.unmount();
    _resetRegShoCache();
    _resetShortInterestCache();
    rsMode = 'throw';
    await mount(board());
    await settle();
    await within(screen.getByTestId(`gg-chips-${BF}`)).findByTestId('si-chip');
    expect(screen.getByTestId(`gg-tile-${BF}`).innerHTML).toBe(htmlA);
    expect(screen.getByTestId(`gg-tile-${SQ}`).innerHTML).toBe(sqA);
  });

  it('exact match: AKAN listed → an AKANW card shows nothing; ACONW listed → an ACON card shows nothing', async () => {
    RS = rs({ items: { AKAN: item('AKAN'), ACONW: item('ACONW') } });
    const pay = board((b) => { b.tiles[0].symbol = 'AKANW'; b.tiles[1].symbol = 'ACON'; });
    const { container } = await mount(pay);
    await settle();
    await screen.findByTestId('gg-tile-AKANW');
    expect(container.querySelector('.gg-htb, .gg-htb-label')).toBeNull();
  });

  it('unknown (complete: false, the names absent) → no tag; the payload did not say off', async () => {
    RS = rs({ complete: false, items: {} });
    const { container } = await mount(board());
    await settle();
    expect(container.querySelector('.gg-htb, .gg-htb-label')).toBeNull();
    expect(JSON.stringify(RS)).not.toContain('"off"');
  });

  it('a failed GET → no tag, no crash, NO fault line on the card grid', async () => {
    RS = rs({ fault_text: FAULT });
    rsMode = 'throw';
    const { container } = await mount(board());
    await settle();
    await screen.findByTestId(`gg-tile-${SQ}`);
    expect(container.querySelector('.gg-htb, .gg-htb-label, .gg-htb-fault')).toBeNull();
    expect(rsCalls).toHaveLength(1);
  });

  for (const [name, over] of [
    ['a clean payload', {}],
    ['fault_text null while refreshing', { refreshing: true, retry_after_sec: 20, fault_text: null }],
  ] as const) {
    it(`${name} → no gg-htb-fault above the card grid`, async () => {
      RS = rs(over);
      await mount(board());
      await screen.findByTestId(`gg-htb-label-${SQ}`).catch(() => null);
      await settle();
      expect(screen.queryByTestId('gg-htb-fault')).toBeNull();
    });
  }
});

/* ── the 📋 table sub (M3b): the same fault line, mounted in the board above GgAllTable ── */
const HEADS = [{ key: 'rank', label: 'served #' }, { key: 'symbol', label: 'served Ticker' }, { key: 'si', label: 'served SI' }];
const HEADS_OLD = HEADS.filter((h) => h.key !== 'si');
const ROW = (rank: number, sym: string, setup: string) => ({
  rank, tier: 3, tier_label: 'served tier', symbol: sym, setup, href: `/chart-maps?tab=gajjala&sub=${setup}&focus=${sym}`,
  in_watch: true, si_text: `served si ${sym}`, si_title: 't', si_stale: false,
});
function tableBoard(heads = HEADS): any {
  const b = clone(BOARDS.bull_flag);
  b.sub = GG_TABLE_SUB;
  b.tiles = [];
  b.empty_note = null;
  b.session = { ...b.session, refresh_sec: 0 };
  b.subs = [{ key: GG_TABLE_SUB, emoji: '\u{1F4CB}', label: 'All strategies', count: 2, title: null }, ...b.subs];
  b.table = { title: 'served table title', heads, order_text: 'served order', rows: [ROW(1, SQ, 'reversal_squeeze'), ROW(2, BF, 'bull_flag')],
    n: 2, fault_text: null, empty_text: null, si_head_title: 'served head', si_fault_text: null };
  return b;
}

describe('🔒 the 📋 table sub — the fault line above the table (M3b)', () => {
  for (const [name, heads] of [['with an si head', HEADS], ['without an si head', HEADS_OLD]] as const) {
    it(`${name}: a served fault_text draws gg-htb-fault right above the table, verbatim`, async () => {
      RS = rs({ fault_text: FAULT });
      await mount(tableBoard(heads), 'gajjala', GG_TABLE_SUB);
      const table = await screen.findByTestId('gg-all');
      const f = await screen.findByTestId('gg-htb-fault');
      expect(f.textContent).toBe(FAULT);
      expect(table.contains(f)).toBe(false);
      expect(f.nextElementSibling).toBe(table);
      expect(screen.getAllByTestId('gg-htb-fault')).toHaveLength(1);
      expect(rsCalls).toHaveLength(1);
    });
  }

  it('with an si head: the short chip prints in the si cell', async () => {
    await mount(tableBoard(), 'gajjala', GG_TABLE_SUB);
    const c = await screen.findByTestId(`gg-all-htb-${SQ}-reversal_squeeze`);
    expect(c.textContent).toBe(item(SQ).short);
  });

  it('NEGATIVE: a clean payload → no gg-htb-fault above the table', async () => {
    await mount(tableBoard(), 'gajjala', GG_TABLE_SUB);
    await screen.findByTestId(`gg-all-htb-${SQ}-reversal_squeeze`);
    expect(screen.queryByTestId('gg-htb-fault')).toBeNull();
  });

  it('NEGATIVE: a failed GET → no fault line and no chip on the table', async () => {
    RS = rs({ fault_text: FAULT });
    rsMode = 'throw';
    const { container } = await mount(tableBoard(), 'gajjala', GG_TABLE_SUB);
    await screen.findByTestId('gg-all');
    await settle();
    expect(container.querySelector('.gg-htb, .gg-htb-fault')).toBeNull();
  });
});

/* ── source guards ── */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('🔒 source guard — GajjalaBoard.tsx mounts', () => {
  it('the four mounts are present and the 11-08 🩳 mount strings are byte-for-byte unchanged', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    for (const m of [
      "import { GgShortInterestLabel } from './GgShortInterestLabel';",
      "read.setup === 'reversal_squeeze' ? <GgShortInterestLabel",
      "t.gajjala?.setup !== 'reversal_squeeze' ? <>{' '}<ShortInterestChip",
      "t.gajjala?.setup !== 'reversal_squeeze' ? <GgHardToBorrowChip symbol={t.symbol} testid={`gg-htb-${t.symbol}`} lead />",
      "read.setup === 'reversal_squeeze' ? <GgHardToBorrowLabel symbol={sym} testid={`gg-htb-label-${sym}`} />",
      '<GgAllTable',
    ]) expect(src).toContain(m);
    expect(src.match(/<GgHardToBorrowFault testid="gg-htb-fault" \/>/g) || []).toHaveLength(2);
    expect(src).not.toMatch(/Hard to borrow'|"Hard to borrow/);
  });
});
