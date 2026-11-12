import { cleanup, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import gg1 from './__fixtures__/gajjala_1m_board_2026_10_27.json';
import golden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';

/* ⏸ No-breakout line through the REAL GajjalaBoard (2026-11-12, no-breakout spec §3.3 / FE package).
 *
 * Ajay 2026-11-12: "Most of our potentials are not having breakout, please write that on them that.. I need for an
 * additonal break out from the triggers Usually after that run up to tirgger point they are mostly just sitting there"
 *
 * Boards: in-file DEEP COPIES of the real goldens (the fixture files are NOT edited); any `breakout` a regenerated golden
 * carries is stripped first, then one block is injected (test data standing in for breakout_state.py's served words).
 * Card: the line sits immediately after the plan line and before the criteria / 🔴 live line. 📈 row: the word sits
 * after the ⚡ slot and before the timeline. NEGATIVES: a tile / row without `breakout` gets no line / word;
 * yesterday's block never prints one it was not served; the card element carries `gg-line` (the 430 px wrap rule). */

vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: null, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({ PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <span data-testid={`short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const clone = (x: any) => JSON.parse(JSON.stringify(x));
const GG1: Record<string, any> = (gg1 as any).boards;
const GOLD: Record<string, any> = (golden as any).boards;

/* ---- served blocks (test data, the §3.1 shape) ---- */
const BROKE = {
  state: 'broke_vol',
  head: '🔊 broke out on the 11:05 bar — volume louder than the base\'s busiest bar',
  detail: ' · closed above 0.452, the high since the trigger · volume 1.2M vs 310.0K (the base\'s busiest bar) · last close 0.46 (+3.3% vs the trigger 0.4451) · 20 min since the trigger bar (10:45)',
  text: '🔊 broke out on the 11:05 bar — volume louder than the base\'s busiest bar · closed above 0.452, the high since the trigger · volume 1.2M vs 310.0K (the base\'s busiest bar) · last close 0.46 (+3.3% vs the trigger 0.4451) · 20 min since the trigger bar (10:45)',
  hint: 'served hint — display only, UNMEASURED',
};
const YET = {
  state: 'no_break_yet',
  head: '⏸ no breakout yet',
  detail: ' · last close 0.44 (-1.1% vs the trigger 0.4451) · 40 min since first seen (10:05 bar)',
  text: '⏸ no breakout yet · last close 0.44 (-1.1% vs the trigger 0.4451) · 40 min since first seen (10:05 bar)',
  hint: 'served 🧠 hint',
};
const NOBRK = { state: 'no_break', head: '⏸ no breakout over 0.4451', detail: '', text: '⏸ no breakout over 0.4451', hint: 'served row hint' };

/** Deep copy with every served `breakout` stripped (tiles + both 📈 blocks), then the named injections. */
function withBreakout(board: any, tiles: Record<string, any>, rows: Record<string, any> = {}, brk: Record<string, string> = {}): any {
  const b = clone(board);
  b.session = { ...(b.session || {}), refresh_sec: 0 };
  b.tiles = (b.tiles || []).map((t: any) => {
    if (!t.gajjala) return t;
    const g = { ...t.gajjala };
    delete g.breakout;
    if (tiles[t.symbol]) g.breakout = clone(tiles[t.symbol]);
    return { ...t, gajjala: g };
  });
  for (const k of ['today', 'yesterday']) {
    const blk = b.track?.[k];
    if (!blk?.rows) continue;
    blk.rows = blk.rows.map((r: any) => {
      const x = { ...r };
      delete x.breakout;
      const id = `${r.symbol}-${r.setup}`;
      if (k === 'today' && rows[id]) x.breakout = clone(rows[id]);
      if (k === 'today' && brk[id]) x.brk_text = brk[id];
      return x;
    });
  }
  return b;
}

let board: (u: URL) => any = () => ({});
function stub() {
  const spy = vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.endsWith('/entry-tape')) return ok({ id: 'x', bars: [], rules: [], lite: true });
    if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) return ok(board(u));
    if (u.pathname.endsWith('/supply-demand/rules')) return ok({ sections: {} });
    return ok({});
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const mount = (q: string, variant?: 'gajjala' | 'gajjala_1m' | 'gajjala_audited') => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}>
    {variant ? <GajjalaBoard variant={variant} /> : <GajjalaBoard />}
  </MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
const precedes = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

beforeEach(() => { board = () => ({}); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('⏸ the card line on the real 1-minute board (deep-copied golden)', () => {
  it('the A+ card: line right after gg-plan, before criteria and any 🔴 live line; served words verbatim', async () => {
    const aplus = GG1.bull_flag.tiles.find((t: any) => t.gajjala?.state === 'aplus');
    expect(aplus).toBeTruthy();
    const sym = aplus.symbol;
    board = (u) => withBreakout(GG1[u.searchParams.get('sub') || 'bull_flag'] || GG1.bull_flag, { [sym]: BROKE });
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(container);
    expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala_1m');
    const el = container.querySelector(`[data-testid="gg-brk-${sym}"]`) as HTMLElement;
    expect(el).not.toBeNull();
    expect(el.textContent).toBe(BROKE.text);
    expect(el.querySelector('strong')?.textContent).toBe(BROKE.head);
    expect(el.getAttribute('title')).toBe(BROKE.hint);
    expect(el.className).toBe('cm-note gg-line gg-brk gg-brk-broke_vol');
    const extras = el.closest('[data-testid="gg-extras"]') as HTMLElement;
    const plan = extras.querySelector('[data-testid="gg-plan"]') as HTMLElement;
    expect(plan).not.toBeNull();
    expect(plan.nextElementSibling).toBe(el);
    const criteria = extras.querySelector('[data-testid="gg-criteria"]');
    expect(criteria).not.toBeNull();
    expect(precedes(el, criteria!)).toBe(true);
    const live = extras.querySelector(`[data-testid="gg-live-${sym}"]`);
    if (live) expect(precedes(el, live)).toBe(true);
    const stages = extras.querySelector(`[data-testid="gg-stages-${sym}"]`);
    if (stages) expect(precedes(el, stages)).toBe(true);
  });

  it('NEGATIVE: the other tile (no breakout served) has no line; exactly one line on the board', async () => {
    const aplus = GG1.bull_flag.tiles.find((t: any) => t.gajjala?.state === 'aplus');
    const other = GG1.bull_flag.tiles.find((t: any) => t.gajjala && t.symbol !== aplus.symbol);
    expect(other).toBeTruthy();
    board = (u) => withBreakout(GG1[u.searchParams.get('sub') || 'bull_flag'] || GG1.bull_flag, { [aplus.symbol]: BROKE });
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(container);
    expect(container.querySelector(`[data-testid="gg-brk-${other.symbol}"]`)).toBeNull();
    expect(container.querySelectorAll('[data-testid^="gg-brk-"]')).toHaveLength(1);
  });

  it('NEGATIVE: no tile served a breakout → no line anywhere, no stray words', async () => {
    board = (u) => withBreakout(GG1[u.searchParams.get('sub') || 'bull_flag'] || GG1.bull_flag, {});
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(container);
    expect(container.querySelectorAll('[data-testid^="gg-brk-"], .gg-brk')).toHaveLength(0);
    expect(container.textContent).not.toMatch(/no breakout|broke out on the/);
  });
});

describe('⏸ 🧠 potential card + 📈 today row on the real potential board (deep-copied golden)', () => {
  const pot = () => GOLD.potential;
  const firstTile = () => pot().tiles.find((t: any) => t.gajjala?.potential);
  const rowId = (r: any) => `${r.symbol}-${r.setup}`;

  it('a 🧠 tile renders no_break_yet after its plan slot; a today row renders the word after ⚡, before the timeline', async () => {
    const tile = firstTile();
    const r0 = pot().track.today.rows.find((r: any) => (r.timeline || []).length);
    expect(tile && r0).toBeTruthy();
    const id = rowId(r0);
    board = () => withBreakout(pot(), { [tile.symbol]: YET }, { [id]: NOBRK }, { [id]: '⚡ break rang 10:41:02 ET (shadow)' });
    stub();
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    const el = container.querySelector(`[data-testid="gg-brk-${tile.symbol}"]`) as HTMLElement;
    expect(el).not.toBeNull();
    expect(el.textContent).toBe(YET.text);
    expect(el.classList.contains('gg-brk-no_break_yet')).toBe(true);
    const extras = el.closest('[data-testid="gg-extras"]') as HTMLElement;
    const plan = extras.querySelector('[data-testid="gg-plan"]');
    expect(plan).not.toBeNull();
    expect(plan!.nextElementSibling).toBe(el);
    const potTile = extras.querySelector('[data-testid="gg-pot-tile"]');
    expect(potTile).not.toBeNull();
    expect(precedes(el, potTile!)).toBe(true);

    const row = container.querySelector(`[data-testid="gg-track-row-${id}"]`) as HTMLElement;
    expect(row).not.toBeNull();
    const word = row.querySelector(`[data-testid="gg-track-nobrk-${id}"]`) as HTMLElement;
    expect(word).not.toBeNull();
    expect(word.textContent).toBe(' · ' + NOBRK.head);
    expect(word.getAttribute('title')).toBe(NOBRK.text);
    const brk = row.querySelector(`[data-testid="gg-track-brk-${id}"]`) as HTMLElement;
    expect(brk).not.toBeNull();
    expect(brk.nextElementSibling).toBe(word);
    const tl = row.querySelector(`[data-testid="gg-track-timeline-${id}"]`) as HTMLElement;
    expect(tl).not.toBeNull();
    expect(word.nextElementSibling).toBe(tl);
  });

  it('the row word without a ⚡ word still sits before the timeline', async () => {
    const r0 = pot().track.today.rows.find((r: any) => (r.timeline || []).length);
    const id = rowId(r0);
    board = () => withBreakout(pot(), {}, { [id]: NOBRK });
    stub();
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    const row = container.querySelector(`[data-testid="gg-track-row-${id}"]`) as HTMLElement;
    const word = row.querySelector(`[data-testid="gg-track-nobrk-${id}"]`) as HTMLElement;
    expect(word).not.toBeNull();
    expect(row.querySelector(`[data-testid="gg-track-brk-${id}"]`)).toBeNull();
    expect(word.nextElementSibling).toBe(row.querySelector(`[data-testid="gg-track-timeline-${id}"]`));
  });

  it('NEGATIVE: tiles and rows without `breakout` print nothing; yesterday never prints a word', async () => {
    const tile = firstTile();
    const r0 = pot().track.today.rows[0];
    const id = rowId(r0);
    board = () => withBreakout(pot(), { [tile.symbol]: YET }, { [id]: NOBRK });
    stub();
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    expect(container.querySelectorAll('[data-testid^="gg-brk-"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-testid^="gg-track-nobrk-"]')).toHaveLength(1);
    for (const r of pot().track.today.rows) {
      if (rowId(r) === id) continue;
      expect(container.querySelector(`[data-testid="gg-track-nobrk-${rowId(r)}"]`)).toBeNull();
    }
    expect(container.textContent).not.toMatch(/NaN|undefined|\[object Object\]/);
  });

  it('NEGATIVE: nothing served at all → no line, no word', async () => {
    board = () => withBreakout(pot(), {});
    stub();
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    expect(container.querySelectorAll('[data-testid^="gg-brk-"], [data-testid^="gg-track-nobrk-"]')).toHaveLength(0);
    expect(container.textContent).not.toMatch(/no breakout/);
  });

  it('phone: the card line carries gg-line (the existing 430 px wrap rule) — no new CSS class needed for wrapping', async () => {
    const tile = firstTile();
    board = () => withBreakout(pot(), { [tile.symbol]: YET });
    stub();
    const { container } = mount('tab=gajjala&sub=potential');
    await loaded(container);
    const el = container.querySelector(`[data-testid="gg-brk-${tile.symbol}"]`) as HTMLElement;
    expect(el.classList.contains('gg-line')).toBe(true);
  });
});
