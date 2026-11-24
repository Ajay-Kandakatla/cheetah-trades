// REVERTED 2026-11-23 (👀 Watch layout default OFF — his "I cannot see the height of the chart"): the ON-mode cases here now seed 'gg-card-watch' = '1' explicitly.
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import { GG_DIVERGENCE_SUB, GG_DIVERGING_SUB, GG_SUBS, GG_TABLE_SUB } from '../lib/gajjala';
import { GGC_PATH } from '../lib/gajjalaCardView';

/* 🌱 the Diverging sub on 🚩 Gajjala's 5-min board (2026-11-18, diverging spec §3.9 / §4 WP-B). Ajay: "For the divergence
 * thing create a separate tab that are potentially diverging with uptrend and volume breakout." `?sub=diverging` → the
 * served panel ABOVE the served cards; the cards go through the 👀 Watch-layout grid (the product default — this file does
 * NOT import ../test/ggCardWatchOff; it seeds 'gg-card-watch' = '0' itself for the OFF path); each card prints its five
 * served criteria rows, the served state, NO plan line; no bar-size toggle on the sub; 🌱 right after 🧨 in the strip.
 * A forming read, never an entry: nothing here rings, gates, records or trades. UNMEASURED. Every word is a SENTINEL
 * ("served …"). NEGATIVES: an older API (no `diverging`) → no panel, no crash; a null block → the served fault line only;
 * the 1-min / 🧪 / 🥇 fallback strips omit 🌱 (and 🧨); the toggle still shows on a setup sub. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', async (importOriginal) => {
  const m: any = await importOriginal();
  return {
    ...m,
    PatternChart: (props: any) => (props.chartOnly
      ? <div data-testid="frame-chart" />
      : <div data-testid={`chart-${props.tile.symbol}`} />),
  };
});
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

const BLOCK = {
  title: 'served dg title', ask_text: 'served his words', pick_texts: ['served pick one', 'served pick two'],
  rule_label: 'served rule label', rule_text: 'served rule text', honesty: 'served honesty',
  cohort_text: 'served cohort', window_text: 'served window', bars_text: null, order_note: 'served order',
  n: 1, n_read: 73, faults_text: null, empty_text: 'served empty', chartless: [],
};
const CRITERIA = [
  { key: 'gap', label: 'served gap label', ok: true, value: 'served gap value', need: 'served gap need' },
  { key: 'widening', label: 'served widening label', ok: true, value: 'served widening value', need: 'served widening need' },
  { key: 'uptrend', label: 'served uptrend label', ok: true, value: 'served uptrend value', need: 'served uptrend need' },
  { key: 'bar_volume', label: 'served bar volume label', ok: true,
    value: 'served 4.1× · 20 of the 20 bars in the mean closed before 09:35 ET (pre-market or the prior session)',
    need: 'served bar volume need' },
  { key: 'k11_volume', label: 'served K11 label', ok: true, value: '', need: '' },
];
const DG_CHIP = { key: GG_DIVERGING_SUB, emoji: '\u{1F331}', label: 'Diverging', count: 1, title: null };
const DV_CHIP = { key: GG_DIVERGENCE_SUB, emoji: '\u{1F9E8}', label: 'Divergence', count: 0, title: null };

/** The served 13-chip strip: 📋 first, 🧨 after 🎾, 🌱 after 🧨, 🧠 / 🏁 last. */
function strip(b: any): any[] {
  const subs = b.subs.map((s: any) => ({ ...s, title: null }));
  const at = subs.findIndex((s: any) => s.key === 'reversal_squeeze') + 1;
  subs.splice(at, 0, DV_CHIP, DG_CHIP);
  return [{ key: GG_TABLE_SUB, emoji: '\u{1F4CB}', label: 'All strategies', count: 0, title: null }, ...subs,
    { key: 'potential', emoji: '\u{1F9E0}', label: 'Potential', count: 0, title: null },
    { key: 'track_record', emoji: '\u{1F3C1}', label: 'Track record', count: 0, title: null }];
}
/** A 🚩 5-min board on the diverging sub: one served 🌱 card (no lines, no plan, five ok criteria). */
function dgBoard(over: Record<string, unknown> = {}): any {
  const b = clone(HAND.bull_flag);
  b.sub = GG_DIVERGING_SUB;
  b.session = { ...b.session, refresh_sec: 0 };
  const t = clone(b.tiles[0]);
  t.lines = [];
  t.gajjala = { setup: GG_DIVERGING_SUB, state: 'diverging', state_label: 'served dg card state', criteria: clone(CRITERIA),
    missed: [], unjudged: [], plan_text: null, chips: {}, listed: null, diverging: { at_text: 'served 10:05 ET' } };
  b.tiles = [t];
  b.empty_note = null;
  b.sorts = [];
  b.subs = strip(b);
  b.diverging = clone(BLOCK);
  return { ...b, ...over };
}
const SYM = () => dgBoard().tiles[0].symbol;
function bullBoard(): any { const b = clone(HAND.bull_flag); b.session = { ...b.session, refresh_sec: 0 }; b.subs = strip(b); return b; }

let boardFor: (sub: string | null) => any = () => dgBoard();
const fetchMock = vi.fn(async (url: string, _init?: RequestInit): Promise<any> => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.startsWith(GGC_PATH + '/')) {
    return { ok: true, status: 200, json: async () => ({ state: 'ok', symbol: 'x', frames: [], text: null }) };
  }
  if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) return { ok: true, status: 200, json: async () => boardFor(u.searchParams.get('sub')) };
  return { ok: true, status: 200, json: async () => ({}) };
});
const gets = () => fetchMock.mock.calls.filter(([u]) => /\/chart-maps\/gajjala\?/.test(String(u)));

function mem(seed: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(seed));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(),
  };
}

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
  boardFor = () => dgBoard();
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('EventSource', class { close() { /* no stream */ } addEventListener() { /* none */ } });
  vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '1' }));
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🌱 the diverging sub on the board (the 👀 Watch layout is the default)', () => {
  it('the served panel ABOVE the cards; the card drawn through the Watch grid with its five served criteria rows', async () => {
    const { container } = await mount(`tab=gajjala&sub=${GG_DIVERGING_SUB}`);
    expect(gets()[0][0]).toContain(`sub=${GG_DIVERGING_SUB}`);
    const panel = screen.getByTestId('gg-dg');
    const grid = await screen.findByTestId('gg-cardgrid');
    expect(panel.compareDocumentPosition(grid) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByTestId('gg-dg-title').textContent).toBe('served dg title');
    expect(screen.getByTestId('gg-dg-pick-1').textContent).toBe('served pick two');
    expect(screen.getByTestId('gg-dg-honesty').textContent).toBe('served honesty');
    expect(screen.queryByTestId('gg-dg-bars')).toBeNull();          // bars_text null on a clean pass
    const tile = screen.getByTestId(`gg-tile-${SYM()}`);
    expect(grid.contains(tile)).toBe(true);
    expect(tile.className).toContain('gg-card--watch');
    expect(within(tile).queryByTestId(`chart-${SYM()}`)).toBeNull();  // no small-card PatternChart
    expect(container.querySelector('.cm-grid')).toBeNull();
    expect(within(tile).getByTestId('gg-state').textContent).toBe('served dg card state');
    expect(within(tile).queryByTestId('gg-plan')).toBeNull();
    const lis = [...within(tile).getByTestId('gg-criteria').querySelectorAll('li')];
    expect(lis).toHaveLength(5);
    for (const li of lis) expect(li.className).toBe('gg-ok');
    CRITERIA.forEach((c, i) => {
      expect(lis[i].textContent).toContain(c.label);
      if (c.value) expect(lis[i].textContent).toContain(c.value);
      if (c.need) expect(lis[i].textContent).toContain(c.need);
    });
    // the FE never composes the pre-market phrase — it prints the served value verbatim
    expect(lis[3].textContent).toContain('20 of the 20 bars in the mean closed before 09:35 ET (pre-market or the prior session)');
  });

  it('bars_text served → printed between window and order', async () => {
    boardFor = () => dgBoard({ diverging: { ...clone(BLOCK), bars_text: 'served bars line' } });
    await mount(`tab=gajjala&sub=${GG_DIVERGING_SUB}`);
    const bars = screen.getByTestId('gg-dg-bars');
    expect(bars.textContent).toBe('served bars line');
    expect(screen.getByTestId('gg-dg-window').compareDocumentPosition(bars) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(bars.compareDocumentPosition(screen.getByTestId('gg-dg-order')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('the OFF path: gg-card-watch = "0" seeded → the old grid draws (PatternChart), the panel still above', async () => {
    vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '0' }));
    const { container } = await mount(`tab=gajjala&sub=${GG_DIVERGING_SUB}`);
    const tile = screen.getByTestId(`gg-tile-${SYM()}`);
    expect(within(tile).getByTestId(`chart-${SYM()}`)).toBeTruthy();
    expect(tile.className).not.toContain('gg-card--watch');
    expect(screen.queryByTestId('gg-cardgrid')).toBeNull();
    const grid = container.querySelector('.cm-grid')!;
    expect(screen.getByTestId('gg-dg').compareDocumentPosition(grid) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(tile).getAllByRole('listitem').filter((li) => li.className === 'gg-ok')).toHaveLength(5);
  });

  it('no bar-size toggle on the sub; NEGATIVE the toggle still shows on bull_flag (and no 🌱 panel there)', async () => {
    const r = await mount(`tab=gajjala&sub=${GG_DIVERGING_SUB}`);
    expect(r.container.querySelector('[data-testid^="gg-tf-"]')).toBeNull();
    r.unmount();
    boardFor = () => bullBoard();
    const r2 = await mount('tab=gajjala&sub=bull_flag');
    expect(r2.container.querySelector('[data-testid="gg-tf-5m"]')).toBeTruthy();
    expect(screen.queryByTestId('gg-dg')).toBeNull();
  });

  it('the GET for the sub carries no new param (the same keys as a setup sub GET)', async () => {
    const r = await mount(`tab=gajjala&sub=${GG_DIVERGING_SUB}`);
    const dgKeys = [...new URL(String(gets()[0][0]), 'http://x').searchParams.keys()].sort();
    r.unmount();
    fetchMock.mockClear();
    boardFor = () => bullBoard();
    await mount('tab=gajjala&sub=bull_flag');
    const bfKeys = [...new URL(String(gets()[0][0]), 'http://x').searchParams.keys()].sort();
    expect(dgKeys).toEqual(bfKeys);
    expect(new URL(String(gets()[0][0]), 'http://x').searchParams.get('sub')).toBe('bull_flag');
  });

  it('the strip: GG_SUBS.length chips, 🌱 right after 🧨, selected on the sub', async () => {
    await mount(`tab=gajjala&sub=${GG_DIVERGING_SUB}`);
    const ids = subBtns().map((b) => b.getAttribute('data-testid'));
    expect(ids).toHaveLength(GG_SUBS.length);
    expect(ids.indexOf(`gg-sub-${GG_DIVERGING_SUB}`)).toBe(ids.indexOf(`gg-sub-${GG_DIVERGENCE_SUB}`) + 1);
    expect(GG_SUBS.map((s) => s.key).indexOf(GG_DIVERGING_SUB)).toBe(GG_SUBS.map((s) => s.key).indexOf(GG_DIVERGENCE_SUB) + 1);
    expect(screen.getByTestId(`gg-sub-${GG_DIVERGING_SUB}`)).toHaveAttribute('aria-selected', 'true');
  });

  it('every string in the panel is a served sentinel (nothing typed by the FE)', async () => {
    await mount(`tab=gajjala&sub=${GG_DIVERGING_SUB}`);
    let text = screen.getByTestId('gg-dg').textContent || '';
    const served = [BLOCK.title, BLOCK.ask_text, ...BLOCK.pick_texts, BLOCK.cohort_text, BLOCK.window_text, BLOCK.order_note,
      BLOCK.rule_label, BLOCK.rule_text, BLOCK.honesty].sort((a, b) => b.length - a.length);
    for (const s of served) text = text.split(s).join('');
    expect(text.trim()).toBe('');
    expect(screen.getByTestId('gg-dg').textContent).not.toMatch(/NaN|undefined|bounc/i);
  });

  it('NEGATIVE: an older API (no `diverging` key; answers bull_flag) → the URL adopts the served sub, no panel, no crash', async () => {
    boardFor = () => { const b = clone(HAND.bull_flag); b.session = { ...b.session, refresh_sec: 0 }; return b; };
    await mount(`tab=gajjala&sub=${GG_DIVERGING_SUB}`);
    await waitFor(() => expect(lastSearch).toContain('sub=bull_flag'));
    expect(screen.queryByTestId('gg-dg')).toBeNull();
  });

  it('NEGATIVE: an older API that answers the sub with no `diverging` key → no panel, the cards still draw', async () => {
    boardFor = () => { const b = dgBoard(); delete b.diverging; return b; };
    await mount(`tab=gajjala&sub=${GG_DIVERGING_SUB}`);
    expect(screen.queryByTestId('gg-dg')).toBeNull();
    expect(screen.getByTestId(`gg-tile-${SYM()}`)).toBeTruthy();
  });

  it('NEGATIVE: a null block (the read faulted) → the served fault line only, no panel, no card', async () => {
    boardFor = () => dgBoard({ diverging: null, tiles: [], empty_note: 'served fault note' });
    await mount(`tab=gajjala&sub=${GG_DIVERGING_SUB}`);
    expect(screen.getByTestId('gg-empty').textContent).toBe('served fault note');
    expect(screen.queryByTestId('gg-dg')).toBeNull();
    expect(screen.queryByTestId(/^gg-tile-/)).toBeNull();
  });

  it('NEGATIVE: the 🧨 panel never draws on the 🌱 sub, and the 🌱 panel never on the 🧨 sub', async () => {
    boardFor = () => dgBoard({ divergence: { title: 'served dv title' } });
    const r = await mount(`tab=gajjala&sub=${GG_DIVERGING_SUB}`);
    expect(screen.queryByTestId('gg-dv')).toBeNull();
    expect(screen.getByTestId('gg-dg')).toBeTruthy();
    r.unmount();
    boardFor = () => dgBoard({ sub: GG_DIVERGENCE_SUB, divergence: { title: 'served dv title' } });
    await mount(`tab=gajjala&sub=${GG_DIVERGENCE_SUB}`);
    expect(screen.queryByTestId('gg-dg')).toBeNull();
    expect(screen.getByTestId('gg-dv')).toBeTruthy();
  });
});

describe('🌱 the pre-board fallback strip (GG5 only)', () => {
  const never = () => new Promise<any>(() => { /* the first board never lands */ });
  it('🚩 Gajjala\'s before its first board: GG_SUBS.length chips, 🌱 right after 🧨', () => {
    fetchMock.mockImplementation(never);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala']}><GajjalaBoard /></MemoryRouter>);
    const ids = subBtns().map((b) => b.getAttribute('data-testid'));
    expect(ids).toHaveLength(GG_SUBS.length);
    expect(ids[0]).toBe(`gg-sub-${GG_TABLE_SUB}`);
    expect(ids.indexOf(`gg-sub-${GG_DIVERGING_SUB}`)).toBe(ids.indexOf(`gg-sub-${GG_DIVERGENCE_SUB}`) + 1);
  });

  it('NEGATIVE: the 1-minute page omits 🌱 and 🧨 and keeps 📋 first', () => {
    fetchMock.mockImplementation(never);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_1m']}><GajjalaBoard variant="gajjala_1m" /></MemoryRouter>);
    const ids = subBtns().map((b) => b.getAttribute('data-testid'));
    expect(ids[0]).toBe(`gg-sub-${GG_TABLE_SUB}`);
    expect(ids).not.toContain(`gg-sub-${GG_DIVERGING_SUB}`);
    expect(ids).not.toContain(`gg-sub-${GG_DIVERGENCE_SUB}`);
    expect(ids).toEqual(GG_SUBS.filter((s) => s.key !== GG_DIVERGENCE_SUB && s.key !== GG_DIVERGING_SUB).map((s) => `gg-sub-${s.key}`));
  });

  for (const v of ['gajjala_audited', 'luk'] as const) {
    it(`NEGATIVE: the ${v} page omits 🌱, 🧨 and 📋; the rest in GG_SUBS order`, () => {
      fetchMock.mockImplementation(never);
      render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala']}><GajjalaBoard variant={v} /></MemoryRouter>);
      const ids = subBtns().map((b) => b.getAttribute('data-testid'));
      expect(ids).not.toContain(`gg-sub-${GG_DIVERGING_SUB}`);
      expect(ids).toEqual(GG_SUBS.filter((s) => s.key !== GG_TABLE_SUB && s.key !== GG_DIVERGENCE_SUB && s.key !== GG_DIVERGING_SUB)
        .map((s) => `gg-sub-${s.key}`));
    });
  }
});

describe('🌱 source guards', () => {
  it('the board keeps the pinned 📋 / 🧨 strip lines byte-for-byte and chains the 🌱 GG5-only filter after them', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    expect(src).toContain("GG_SUBS.filter((s) => (vkey === 'gajjala' || vkey === 'gajjala_1m' || s.key !== GG_TABLE_SUB)");
    expect(src).toContain("&& (vkey === 'gajjala' || s.key !== GG_DIVERGENCE_SUB))");
    expect(src).toMatch(/s\.key !== GG_DIVERGENCE_SUB\)\)[^\n]*\n\s*\.filter\(\(s\) => vkey === 'gajjala' \|\| s\.key !== GG_DIVERGING_SUB\)/);
    expect(src).toMatch(/activeSub === GG_DIVERGING_SUB \? <GgDivergingPanel block=\{board\.diverging \?\? null\} \/>/);
    expect(src).toMatch(/activeSub === GG_DIVERGING_SUB \? null : \(activeSub === GG_DIVERGENCE_SUB \? \[\] : tfs\)\.map/);
  });

  it('the lib spells the sub ONCE as a value (GG_DIVERGING_SUB); NEGATIVE no b-word in the new files', async () => {
    const lib = await readSource('src/lib/gajjala.ts');
    const code = lib.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
    expect((code.match(/'diverging'/g) || []).length).toBe(3);   // the GgSub member, the GG_SUBS row, GG_DIVERGING_SUB
    expect(lib).toMatch(/^export const GG_DIVERGING_SUB: GgSub = 'diverging';$/m);
    expect(await readSource('src/components/GgDiverging.tsx')).not.toMatch(/bounc/i);
  });
});
