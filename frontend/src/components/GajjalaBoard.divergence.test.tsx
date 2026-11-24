import '../test/ggCardWatchOff';   // 2026-11-18: this file pins the OLD card grid; the 👀 Watch layout is the default now
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import { GG_DIVERGENCE_SUB, GG_DIVERGING_SUB, GG_HIGH_SI_SUB, GG_SUBS, GG_TABLE_SUB } from '../lib/gajjala';

/* 🧨 the Divergence sub on 🚩 Gajjala's 5-min board (2026-11-18, divergence spec §3.8 / WP-C). Ajay: "Do we still capture
 * divergence alerts? Can you add a tab for in in Gajjals 5 min please" · "yes should do a track recird fir the divergence
 * aftger EMA 9 Cross over bullish". `?sub=divergence` → the served panel ABOVE the served cards, the served 🏁 fold BELOW
 * them; no bar-size toggle on that sub; the GET carries no `sort` (the fold sorts FE-only); 🧨 after 🎾 in the strip.
 * The pre-board fallback strip: 🧨 on 🚩 Gajjala's only; the 1-min page KEEPS 📋 first (11-16) and omits 🧨; 🧪 / 🥇 omit
 * both. Every word is a SENTINEL ("served …"). NEGATIVES: an older API (no `divergence`) → no panel, no fold, no crash;
 * a null block → the served empty note only; NaN texts print nothing. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({ PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const HAND: Record<string, any> = (hand as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const cell = (state: string, text: string) => ({ state, text });
const ROW = (key: string, sym: string, bucket: string) => ({
  key, id: key, date: '2026-11-18', symbol: sym, window: 'rth', window_text: `served window ${sym}`, at_text: `served at ${sym}`,
  ring_text: `served ring ${sym}`, entry: cell('ok', `served entry ${sym}`), exit: cell('ok', `served exit ${sym}`),
  gross: cell(bucket, `served gross ${sym}`), net: cell(bucket, `served net ${sym}`), bucket, bucket_text: `served ${bucket}`,
  flag_text: `served flag ${sym}`, href: null,
});
const TRACK = {
  title: 'served fold title', span: 'today', spans: [{ key: 'today', label: 'served Today' }, { key: '10d', label: 'served 10d' }],
  heads: [{ key: 'symbol', label: 'served Ticker' }, { key: 'at', label: 'served Listed' }, { key: 'net', label: 'served Net' }],
  days: [{ date: '2026-11-18', label: 'served day', rows: [ROW('L1', 'AAA', 'loss'), ROW('W1', 'BBB', 'win')] }],
  counts_text: { rth: 'served counts rth', ah: 'served counts ah' }, oos_progress_text: 'served oos progress',
  categories: [{ key: 'all', text: 'served all', n: 2 }, { key: 'win', text: 'served win', n: 1 }],
  sorts: [{ key: 'served', label: 'served order', bucket_sort: false }, { key: 'wins', label: 'served wins', bucket_sort: true }],
  sort_default: 'served', bucket_order: ['win', 'loss'], honesty: 'served fold honesty',
};
const BLOCK = {
  title: 'served dv title', ask_text: 'served his words', rule_label: 'served rule label', rule_text: 'served rule text',
  honesty: 'served honesty', is_line: { rth: { text: 'served IS rth' }, ah: { text: 'served IS ah' } },
  oos_text: 'served oos', cohort_text: 'served cohort', window_text: 'served window', n_today: 1, order_note: 'served order',
  chartless: [], faults_text: null, track_record: TRACK, track_record_fault_text: null,
};
const DV_CHIP = { key: GG_DIVERGENCE_SUB, emoji: '\u{1F9E8}', label: 'Divergence', count: 1, title: null };
/** A 🚩 5-min board on the divergence sub: the regenerated strip (📋 first, 🧨 after 🎾), one served 🧨 card. */
function dvBoard(over: Record<string, unknown> = {}): any {
  const b = clone(HAND.bull_flag);
  b.sub = GG_DIVERGENCE_SUB;
  b.session = { ...b.session, refresh_sec: 0 };
  const t = clone(b.tiles[0]);
  t.gajjala = { ...t.gajjala, setup: GG_DIVERGENCE_SUB, state: 'divergence', state_label: 'served card state' };
  b.tiles = [t];
  b.empty_note = null;
  const subs = b.subs.map((s: any) => ({ ...s, title: null }));
  const at = subs.findIndex((s: any) => s.key === 'reversal_squeeze') + 1;
  // WIDENED 2026-11-18 — 🌱 Diverging after 🧨 (diverging spec §4 WP-B): the hand-built strip keeps GG_SUBS.length.
  // WIDENED 2026-11-23 — 🩳 High SI after 🌱 (high SI spec §4 WP fe-sub): the hand-built strip keeps GG_SUBS.length.
  subs.splice(at, 0, DV_CHIP, { key: GG_DIVERGING_SUB, emoji: '\u{1F331}', label: 'Diverging', count: 0, title: null },
    { key: GG_HIGH_SI_SUB, emoji: '\u{1FA73}', label: 'High SI', count: 0, title: null });
  b.subs = [{ key: GG_TABLE_SUB, emoji: '\u{1F4CB}', label: 'All strategies', count: 0, title: null }, ...subs,
    { key: 'potential', emoji: '\u{1F9E0}', label: 'Potential', count: 0, title: null },
    { key: 'track_record', emoji: '\u{1F3C1}', label: 'Track record', count: 0, title: null }];
  b.divergence = clone(BLOCK);
  return { ...b, ...over };
}

let boardFor: (sub: string | null) => any = () => dvBoard();
const fetchMock = vi.fn(async (url: string, _init?: RequestInit): Promise<any> => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.endsWith('/chart-maps/gajjala')) return { ok: true, status: 200, json: async () => boardFor(u.searchParams.get('sub')) };
  return { ok: true, status: 200, json: async () => ({}) };
});
const gets = () => fetchMock.mock.calls.filter(([u]) => String(u).includes('/chart-maps/gajjala?'));

let lastSearch = '';
function Probe() { lastSearch = useLocation().search; return null; }
const mount = async (q: string) => {
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /><Probe /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
};
const subBtns = () => screen.getAllByRole('tab').filter((b) => b.getAttribute('data-testid')?.startsWith('gg-sub-'));

beforeEach(() => {
  fetchMock.mockClear();
  boardFor = () => dvBoard();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🧨 the divergence sub on the board', () => {
  it('renders the served panel ABOVE the served card and the 🏁 fold BELOW it; no bar-size toggle on the sub', async () => {
    const { container } = await mount(`tab=gajjala&sub=${GG_DIVERGENCE_SUB}`);
    expect(gets()[0][0]).toContain(`sub=${GG_DIVERGENCE_SUB}`);
    const panel = screen.getByTestId('gg-dv');
    const tile = screen.getByTestId(`gg-tile-${dvBoard().tiles[0].symbol}`);
    const fold = screen.getByTestId('gg-dv-tr');
    expect(screen.getByTestId('gg-dv-title').textContent).toBe('served dv title');
    expect(screen.getByTestId('gg-dv-is-rth').textContent).toBe('served IS rth');
    expect(within(tile).getByTestId(`chart-${dvBoard().tiles[0].symbol}`)).toBeTruthy();
    expect(panel.compareDocumentPosition(tile) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(tile.compareDocumentPosition(fold) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByTestId('gg-tr-net-W1').textContent).toBe('served net BBB');
    expect(screen.getByTestId('gg-dv-tr-oos-progress').textContent).toBe('served oos progress');
    // the bar-size toggle is hidden on 🧨 (the cards are the 5m frame)
    expect(container.querySelector('[data-testid^="gg-tf-"]')).toBeNull();
  });

  it('NEGATIVE: the bar-size toggle still shows on a setup sub', async () => {
    boardFor = () => { const b = clone(HAND.bull_flag); b.session = { ...b.session, refresh_sec: 0 }; return b; };
    const { container } = await mount('tab=gajjala&sub=bull_flag');
    expect(container.querySelector('[data-testid="gg-tf-5m"]')).toBeTruthy();
    expect(screen.queryByTestId('gg-dv')).toBeNull();
    expect(screen.queryByTestId('gg-dv-tr')).toBeNull();
  });

  it('GG_SUBS.length chips on GG5 with 🧨 right after 🎾', async () => {
    await mount(`tab=gajjala&sub=${GG_DIVERGENCE_SUB}`);
    const ids = subBtns().map((b) => b.getAttribute('data-testid'));
    expect(ids).toHaveLength(GG_SUBS.length);
    expect(ids.indexOf(`gg-sub-${GG_DIVERGENCE_SUB}`)).toBe(ids.indexOf('gg-sub-reversal_squeeze') + 1);
    expect(GG_SUBS.map((s) => s.key).indexOf(GG_DIVERGENCE_SUB)).toBe(GG_SUBS.map((s) => s.key).indexOf('reversal_squeeze') + 1);
    expect(screen.getByTestId(`gg-sub-${GG_DIVERGENCE_SUB}`)).toHaveAttribute('aria-selected', 'true');
  });

  it('sortForGet: the GET carries no `sort` on 🧨; a fold sort chip refetches nothing; a span chip refetches WITH span', async () => {
    await mount(`tab=gajjala&sub=${GG_DIVERGENCE_SUB}&sort=wins`);
    expect(gets()).toHaveLength(1);
    expect(new URL(String(gets()[0][0]), 'http://x').searchParams.get('sort')).toBeNull();
    fireEvent.click(screen.getByTestId('gg-tr-sort-served'));
    fireEvent.click(screen.getByTestId('gg-tr-cat-win'));
    await act(async () => { await Promise.resolve(); });
    expect(gets()).toHaveLength(1);
    expect(lastSearch).toContain('cat=win');
    fireEvent.click(screen.getByTestId('gg-dv-tr-span-10d'));
    await waitFor(() => expect(gets().length).toBe(2));
    expect(new URL(String(gets()[1][0]), 'http://x').searchParams.get('span')).toBe('10d');
    expect(new URL(String(gets()[1][0]), 'http://x').searchParams.get('sort')).toBeNull();
  });

  it('NEGATIVE: a setup sub still sends its served tile sort on the GET', async () => {
    boardFor = () => { const b = clone(HAND.bull_flag); b.session = { ...b.session, refresh_sec: 0 }; return b; };
    await mount('tab=gajjala&sub=bull_flag&sort=served_x');
    expect(new URL(String(gets()[0][0]), 'http://x').searchParams.get('sort')).toBe('served_x');
  });

  it('chartless lines + faults_text print when served; NEGATIVE: nothing when absent', async () => {
    boardFor = () => dvBoard({ divergence: { ...clone(BLOCK), chartless: [{ symbol: 'ZZZ', at_text: 'x', state_label: 'served chartless ZZZ', href: null }],
      faults_text: 'served faults' } });
    const r = await mount(`tab=gajjala&sub=${GG_DIVERGENCE_SUB}`);
    expect(screen.getByTestId('gg-dv-chartless-ZZZ').textContent).toBe('served chartless ZZZ');
    expect(screen.getByTestId('gg-dv-faults').textContent).toBe('served faults');
    r.unmount();
    boardFor = () => dvBoard();
    await mount(`tab=gajjala&sub=${GG_DIVERGENCE_SUB}`);
    expect(screen.queryByTestId(/^gg-dv-chartless-/)).toBeNull();
    expect(screen.queryByTestId('gg-dv-faults')).toBeNull();
  });

  it('the fold fault: track_record null + served fault text → that line, the panel and the card still serve', async () => {
    boardFor = () => dvBoard({ divergence: { ...clone(BLOCK), track_record: null, track_record_fault_text: 'served fold fault' } });
    await mount(`tab=gajjala&sub=${GG_DIVERGENCE_SUB}`);
    expect(screen.getByTestId('gg-dv-tr-fault').textContent).toBe('served fold fault');
    expect(screen.queryByTestId('gg-dv-tr')).toBeNull();
    expect(screen.getByTestId('gg-dv')).toBeTruthy();
    expect(screen.getByTestId(`gg-tile-${dvBoard().tiles[0].symbol}`)).toBeTruthy();
  });

  it('NEGATIVE: a null block (the record unreadable) → the served empty note only, no panel, no fold', async () => {
    boardFor = () => dvBoard({ divergence: null, tiles: [], empty_note: 'served fault note' });
    await mount(`tab=gajjala&sub=${GG_DIVERGENCE_SUB}`);
    expect(screen.getByTestId('gg-empty').textContent).toBe('served fault note');
    expect(screen.queryByTestId('gg-dv')).toBeNull();
    expect(screen.queryByTestId('gg-dv-tr')).toBeNull();
  });

  it('NEGATIVE: an older API (no `divergence` key; answers bull_flag) → the URL adopts the served sub, no crash', async () => {
    boardFor = () => { const b = clone(HAND.bull_flag); b.session = { ...b.session, refresh_sec: 0 }; return b; };
    await mount(`tab=gajjala&sub=${GG_DIVERGENCE_SUB}`);
    await waitFor(() => expect(lastSearch).toContain('sub=bull_flag'));
    expect(screen.queryByTestId('gg-dv')).toBeNull();
    expect(screen.queryByTestId('gg-dv-tr')).toBeNull();
  });

  it('NEGATIVE: NaN / undefined served texts print nothing on the board', async () => {
    boardFor = () => dvBoard({ divergence: { ...clone(BLOCK), title: NaN, honesty: undefined, is_line: { rth: { text: NaN } },
      track_record: { ...clone(TRACK), counts_text: { rth: NaN }, oos_progress_text: undefined, honesty: NaN } } });
    const { container } = await mount(`tab=gajjala&sub=${GG_DIVERGENCE_SUB}`);
    expect(screen.queryByTestId('gg-dv-title')).toBeNull();
    expect(screen.queryByTestId('gg-dv-honesty')).toBeNull();
    expect(screen.queryByTestId('gg-dv-is-rth')).toBeNull();
    expect(screen.queryByTestId('gg-dv-tr-counts-rth')).toBeNull();
    expect(screen.queryByTestId('gg-dv-tr-honesty')).toBeNull();
    expect(container.querySelector('.gg-dv')!.textContent).not.toMatch(/NaN|undefined/);
  });
});

describe('🧨 [C6] the pre-board fallback strip', () => {
  const never = () => new Promise<any>(() => { /* the first board never lands */ });
  it('🚩 Gajjala\'s before its first board: 📋 FIRST, 🧨 right after 🎾, GG_SUBS.length chips', () => {
    fetchMock.mockImplementation(never);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala']}><GajjalaBoard /></MemoryRouter>);
    const ids = subBtns().map((b) => b.getAttribute('data-testid'));
    expect(ids).toHaveLength(GG_SUBS.length);
    expect(ids[0]).toBe(`gg-sub-${GG_TABLE_SUB}`);
    expect(ids.indexOf(`gg-sub-${GG_DIVERGENCE_SUB}`)).toBe(ids.indexOf('gg-sub-reversal_squeeze') + 1);
  });

  it('the 1-minute page: 📋 STILL first (11-16) and NO 🧨', () => {
    fetchMock.mockImplementation(never);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_1m']}><GajjalaBoard variant="gajjala_1m" /></MemoryRouter>);
    const ids = subBtns().map((b) => b.getAttribute('data-testid'));
    expect(ids[0]).toBe(`gg-sub-${GG_TABLE_SUB}`);
    expect(ids).not.toContain(`gg-sub-${GG_DIVERGENCE_SUB}`);
    // WIDENED 2026-11-18 — 🌱 Diverging is GG5 only too: the 1-min page omits 🧨 AND 🌱.
    expect(ids).not.toContain(`gg-sub-${GG_DIVERGING_SUB}`);
    // WIDENED 2026-11-23 — 🩳 High SI after 🌱: 🩳 High SI is GG5 only too — the 1-min page omits 🧨, 🌱 AND 🩳.
    expect(ids).not.toContain(`gg-sub-${GG_HIGH_SI_SUB}`);
    expect(ids).toHaveLength(GG_SUBS.length - 3);
  });

  for (const v of ['gajjala_audited', 'luk'] as const) {
    it(`NEGATIVE: the ${v} page: NO 📋 and NO 🧨; the rest in GG_SUBS order`, () => {
      fetchMock.mockImplementation(never);
      render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala']}><GajjalaBoard variant={v} /></MemoryRouter>);
      const ids = subBtns().map((b) => b.getAttribute('data-testid'));
      expect(ids).not.toContain(`gg-sub-${GG_TABLE_SUB}`);
      expect(ids).not.toContain(`gg-sub-${GG_DIVERGENCE_SUB}`);
      // WIDENED 2026-11-18 — 🌱 Diverging is GG5 only: the 🧪 / 🥇 strips also omit it.
      // WIDENED 2026-11-23 — 🩳 High SI after 🌱: the 🧪 / 🥇 strips also omit 🩳.
      expect(ids).toEqual(GG_SUBS.filter((s) => s.key !== GG_TABLE_SUB && s.key !== GG_DIVERGENCE_SUB && s.key !== GG_DIVERGING_SUB
        && s.key !== GG_HIGH_SI_SUB).map((s) => `gg-sub-${s.key}`));
    });
  }
});

describe('🧨 source guards on the board', () => {
  it('the board renders the 🧨 pieces only on the sub, hides the toggle there, and keeps the 📋 1-min clause', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    expect(src).toMatch(/s === 'track_record' \|\| s === GG_DIVERGENCE_SUB \? null : sort/);
    expect(src).toMatch(/vkey === 'gajjala' \|\| vkey === 'gajjala_1m' \|\| s\.key !== GG_TABLE_SUB\)/);
    expect(src).toMatch(/&& \(vkey === 'gajjala' \|\| s\.key !== GG_DIVERGENCE_SUB\)\)/);
    expect(src).toMatch(/\(activeSub === GG_DIVERGENCE_SUB \? \[\] : tfs\)\.map/);
    expect(src).toMatch(/activeSub === GG_DIVERGENCE_SUB \? <GgDivergencePanel/);
  });
});
