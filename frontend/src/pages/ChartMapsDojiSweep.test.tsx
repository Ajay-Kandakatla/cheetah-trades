/* 🕯️ Doji Sweep on the real Chart Maps page (2026-10-16).
 *
 * Ajay 2026-10-16, verbatim: "create me a new tab for Doji candle after a
 * sweep. For any stocks after a down trend. May be from all chart maps
 * especially on the 60% 70% down stocks" — K3 "Yes, any read; chips narrow".
 *
 * The real page, fetch mocked (the ChartMapsFallen.test template). The mock
 * server reads the request's `dj` / `dj_body` / `sort` and serves the matching
 * entry: a HAND payload typed from the doji spec §3.4 envelope (always), and
 * the WP-B golden (components/__fixtures__/doji_sweep_board_golden_2026_10_16.json)
 * whose cases SKIP until that file exists. The server decides; the page only
 * asks — and asks for `dj` / `dj_body` on this tab alone. */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import { TAB_META } from '../lib/chartMaps';
import { _resetRulesInfoCache } from '../hooks/useRulesInfo';

type Board = Record<string, any> & { tiles: Array<Record<string, any>> };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;
const qs = (url: string) => new URLSearchParams(url.slice(url.indexOf('?') + 1));

async function readJsonIfPresent(rel: string): Promise<any | null> {
  try {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const p = `${root}/${rel}`;
    return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
  } catch {
    return null;
  }
}
const GOLDEN: Record<string, Board> | null =
  await readJsonIfPresent('src/components/__fixtures__/doji_sweep_board_golden_2026_10_16.json');

// ── the HAND payload (doji spec §3.4) ─────────────────────────────────────
const C = '\u{1F56F}\u{FE0F}';
const KEYS = ['w52_40', 'w52_60', 'w52_70', 'ath_60', 'mas', 'reclaimed'];
const SORTS = [
  { key: 'default', label: `${C} Newest candle, deepest first` },
  { key: 'doji_test', label: '\u{1F4CF} Closest to the prior low first' },
  { key: 'doji_ath', label: '\u{1F3D4}\u{FE0F} Deepest under the all-time high first' },
];
const bars = (base: number) => Array.from({ length: 40 }, (_, i) => {
  const d = new Date(Date.UTC(2026, 7, 20) + i * 86_400_000).toISOString().slice(0, 10);
  const c = base - i * 0.05;
  return { t: d, o: c + 0.02, h: c + 0.3, l: c - 0.3, c, v: 1_000_000 };
});
type Row = { sym: string; w52: number; reclaimed: boolean; mas: boolean; ath: boolean; doji5: boolean; test: number };
const ROWS: Row[] = [
  { sym: 'AAAA', w52: 72.4, reclaimed: true, mas: true, ath: true, doji5: true, test: -1.2 },
  { sym: 'BBBB', w52: 41.0, reclaimed: false, mas: true, ath: false, doji5: true, test: 3.4 },
  { sym: 'CCCC', w52: 63.0, reclaimed: false, mas: false, ath: true, doji5: true, test: 0.4 },
  { sym: 'DDDD', w52: 66.0, reclaimed: false, mas: true, ath: false, doji5: false, test: 2.0 },
];
const tf = (r: Row): Record<string, boolean> => ({ w52_40: r.w52 >= 40, w52_60: r.w52 >= 60, w52_70: r.w52 >= 70,
  ath_60: r.ath, mas: r.mas, reclaimed: r.reclaimed });
const tile = (r: Row) => ({
  symbol: r.sym, theme: null, href: `/sepa/${r.sym}?tab=supply`, last_close: 4.2, bars: bars(5), bands: [],
  lines: [{ price: 4.1, label: 'prior 20-session low', tone: 'neutral' }], markers: [{ date: '2026-09-28', label: C }],
  badges: [{ text: `${C} Doji · body 3.0% of the range`, tone: 'warn' }, { text: `Low ${r.test}% from the prior 20-session low`, tone: 'muted' }],
  stats: [{ k: 'Doji', v: 'Doji · upper wick 40% · lower wick 57%' }],
  why: `${C} Doji on 2026-09-28 · served why`,
  doji_sweep: { date: '2026-09-28', reclaimed: r.reclaimed, below_mas: r.mas, pct_below_52w: r.w52, doji5: r.doji5 },
});
function handServe(q: URLSearchParams): Board {
  const active = KEYS.filter((k) => (q.get('dj') || '').split(',').includes(k));
  const bodyKey = q.get('dj_body') === '10' ? '10' : '5';
  const sortWant = q.get('sort') || 'default';
  const sort = SORTS.some((s) => s.key === sortWant) ? sortWant : 'default';
  const atBody = ROWS.filter((r) => bodyKey === '10' || r.doji5);
  const kept = atBody.filter((r) => active.every((k) => tf(r)[k]));
  const items = KEYS.map((k) => ({ key: k, label: `L-${k}`, on: active.includes(k), pass: atBody.filter((r) => tf(r)[k]).length,
    fail: atBody.filter((r) => !tf(r)[k]).length, no_read: 0, hidden: 0, note: `N-${k}` }));
  return {
    tab: 'doji_sweep', sort, sorts: SORTS, tiles: kept.map(tile), matched: kept.length, note: 'served note',
    doji_sweep_board: {
      state: 'ready', session: '2026-10-16', as_of: '2026-10-15', built_at: '2026-10-15T20:05:00-04:00', measured: false,
      study: { status: 'unmeasured', text: `${C} UNMEASURED — served study line.`, verdict: null, prereg: 'p', script: 's' },
      sort, header: `${C} H-${kept.length} served header`, order_line: `O-${sort}`, count_line: `Showing ${kept.length} — served count line.`,
      note: 'served note',
      body: { param: 'dj_body', pct: Number(bodyKey), steps: [
        { key: '5', label: `${C} Body under 5%`, title: 'T5', on: bodyKey === '5', default: true },
        { key: '10', label: `${C} Body under 10%`, title: 'T10', on: bodyKey === '10', default: false }] },
      filters: { keys: KEYS, active, pool: atBody.length, mode: 'all', passed_all: active.length ? kept.length : null,
        shown: active.length ? kept.length : null, hidden: atBody.length - kept.length, items,
        line: active.length ? 'served chip line' : null, note: 'served chips note', measured: false },
      counts: { scanned: 9, at_body: atBody.length, shown: kept.length }, suspects: { n: 0, head: '', lines: [] },
      reads_legend: ['R1', 'R2', 'R3'], test_pct: 5, ref_sessions: 20, ref_min_age: 4, down_pct: 60, sma_fast: 50,
      sma_slow: 200, year_bars: 252, filter_param: 'dj',
    },
  };
}
const HAND_WARM: Board = {
  tab: 'doji_sweep', tiles: [], warming: true, sort: 'default', sorts: SORTS,
  note: `${C} Reading every name's last closed daily candle from the cached bars — served warming line.`,
  doji_sweep_board: {
    state: 'warming', session: '2026-10-16', as_of: null, built_at: null, measured: false,
    study: { status: 'unmeasured', text: `${C} UNMEASURED — served study line.`, verdict: null, prereg: 'p', script: 's' },
    sort: 'default', header: `${C} Reading every name's last closed daily candle from the cached bars — served warming line.`,
    order_line: 'O-default', count_line: null, note: 'served note',
    body: { param: 'dj_body', pct: 5, steps: [] }, filters: { items: [] }, counts: null, suspects: null,
    reads_legend: ['R1', 'R2', 'R3'], test_pct: 5, ref_sessions: 20, ref_min_age: 4, down_pct: 60, sma_fast: 50,
    sma_slow: 200, year_bars: 252, filter_param: 'dj',
  },
};

// ── the golden server: the entry the request asks for ──────────────────────
function goldenServe(q: URLSearchParams): Board {
  const G = GOLDEN!;
  if (q.get('dj') === 'w52_70') return clone(G.w52_70);
  if (q.get('dj') === 'reclaimed') return clone(G.reclaimed);
  if (q.get('dj_body') === '10') return clone(G.body10);
  if (q.get('sort') === 'doji_test') return clone(G.sort_test);
  return clone(G.default);
}

const RULES = { sections: { doji_sweep: { title: 'R-doji', emoji: C, picks: ['P-1'], stops: ['S-1'], alerts: ['A-1'], note: 'N' } } };
function stub(make: (q: URLSearchParams) => Record<string, unknown>) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) {
      const q = qs(url);
      if (q.get('tab') !== 'doji_sweep') return { ok: true, json: async () => ({ tab: q.get('tab'), tiles: [], note: 'other tab' }) } as unknown as Response;
      return { ok: true, json: async () => make(q) } as unknown as Response;
    }
    if (url.includes('/supply-demand/rules')) return { ok: true, json: async () => RULES } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const allCalls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
const boardCalls = () => allCalls().filter((u) => u.includes('/chart-maps?'));
const lastBoardCall = () => boardCalls()[boardCalls().length - 1];

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Loc /></MemoryRouter>);
const urlParam = (k: string) => new URLSearchParams(screen.getByTestId('loc').textContent || '').get(k);
const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);
const pressed = (id: string) => screen.getByTestId(id).getAttribute('aria-pressed');

beforeEach(() => {
  vi.restoreAllMocks();
  _resetRulesInfoCache();
  try { window.localStorage.clear(); } catch { /* no store in this runner */ }
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('🕯️ Doji Sweep — the HAND payload on the page', () => {
  const DEFAULT = handServe(new URLSearchParams('tab=doji_sweep'));
  const SYMS = DEFAULT.tiles.map((t) => String(t.symbol));

  it('?tab=doji_sweep mounts the note, one card per served tile in the served order, no dj / dj_body on the first ask', async () => {
    vi.stubGlobal('fetch', stub(handServe));
    page('/chart-maps?tab=doji_sweep&show=all');
    await waitFor(() => expect(order()).toEqual(SYMS));
    expect(screen.getByTestId('cm-dj-board').getAttribute('data-state')).toBe('ready');
    expect(screen.getByTestId('cm-dj-header').textContent).toBe(DEFAULT.doji_sweep_board.header);
    expect(screen.getByTestId('cm-dj-study').textContent).toBe(DEFAULT.doji_sweep_board.study.text);
    expect(qs(boardCalls()[0]).get('tab')).toBe('doji_sweep');
    expect(boardCalls().every((u) => !qs(u).has('dj') && !qs(u).has('dj_body'))).toBe(true);
    expect(pressed('cm-dj-body-5')).toBe('true');
  });

  it('the ℹ️ Rules pill mounts for section "doji_sweep"', async () => {
    vi.stubGlobal('fetch', stub(handServe));
    page('/chart-maps?tab=doji_sweep&show=all');
    await waitFor(() => expect(screen.getAllByTestId('rules-info-pill')).toHaveLength(1));
    fireEvent.click(screen.getByTestId('rules-info-pill'));
    await waitFor(() => expect(screen.getByTestId('rules-info-panel').textContent || '').toContain('R-doji'));
  });

  it('a chip click writes ?dj=<key>, the next board request carries it, the served on checks it; a second click removes it', async () => {
    vi.stubGlobal('fetch', stub(handServe));
    page('/chart-maps?tab=doji_sweep&show=all');
    await waitFor(() => expect(order()).toEqual(SYMS));
    fireEvent.click(screen.getByTestId('cm-dj-filter-reclaimed'));
    await waitFor(() => expect(urlParam('dj')).toBe('reclaimed'));
    await waitFor(() => expect(qs(lastBoardCall()).get('dj')).toBe('reclaimed'));
    await waitFor(() => expect(order()).toEqual(['AAAA']));
    expect((screen.getByTestId('cm-dj-filter-reclaimed') as HTMLInputElement).checked).toBe(true);
    expect(urlParam('tab')).toBe('doji_sweep');
    fireEvent.click(screen.getByTestId('cm-dj-filter-reclaimed'));
    await waitFor(() => expect(urlParam('dj')).toBeNull());
    await waitFor(() => expect(qs(lastBoardCall()).has('dj')).toBe(false));
  });

  it('a body click on "10" writes dj_body=10 and the request carries it; a click back on "5" deletes it', async () => {
    vi.stubGlobal('fetch', stub(handServe));
    page('/chart-maps?tab=doji_sweep&show=all');
    await waitFor(() => expect(order()).toEqual(SYMS));
    fireEvent.click(screen.getByTestId('cm-dj-body-10'));
    await waitFor(() => expect(urlParam('dj_body')).toBe('10'));
    await waitFor(() => expect(qs(lastBoardCall()).get('dj_body')).toBe('10'));
    await waitFor(() => expect(pressed('cm-dj-body-10')).toBe('true'));
    await waitFor(() => expect(order()).toContain('DDDD'));
    fireEvent.click(screen.getByTestId('cm-dj-body-5'));
    await waitFor(() => expect(urlParam('dj_body')).toBeNull());
    await waitFor(() => expect(qs(lastBoardCall()).has('dj_body')).toBe(false));
  });

  it('a deep link ?dj=w52_70&dj_body=10 sends both on the FIRST fetch (canonical order)', async () => {
    vi.stubGlobal('fetch', stub(handServe));
    page('/chart-maps?tab=doji_sweep&dj=reclaimed%2Cw52_70&dj_body=10&show=all');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    expect(qs(boardCalls()[0]).get('dj')).toBe('w52_70,reclaimed');
    expect(qs(boardCalls()[0]).get('dj_body')).toBe('10');
  });

  it('a served sort click persists ?sort=doji_test and the request carries it', async () => {
    vi.stubGlobal('fetch', stub(handServe));
    page('/chart-maps?tab=doji_sweep&show=all');
    await waitFor(() => expect(order()).toEqual(SYMS));
    fireEvent.click(screen.getByTestId('cm-dj-sort-doji_test'));
    await waitFor(() => expect(urlParam('sort')).toBe('doji_test'));
    await waitFor(() => expect(qs(lastBoardCall()).get('sort')).toBe('doji_test'));
    await waitFor(() => expect(pressed('cm-dj-sort-doji_test')).toBe('true'));
  });

  it('NEGATIVE: switching to 📉 drops dj / dj_body / the doji sort from the URL, and the fallen request carries none', async () => {
    vi.stubGlobal('fetch', stub(handServe));
    page('/chart-maps?tab=doji_sweep&dj=mas&dj_body=10&sort=doji_test&show=all');
    await waitFor(() => expect(screen.getByTestId('cm-dj-board')).toBeTruthy());
    fireEvent.click(screen.getByRole('tab', { name: TAB_META.fallen.label }));
    await waitFor(() => expect(urlParam('tab')).toBe('fallen'));
    expect(urlParam('dj')).toBeNull();
    expect(urlParam('dj_body')).toBeNull();
    expect(urlParam('sort')).toBeNull();
    await waitFor(() => expect(qs(lastBoardCall()).get('tab')).toBe('fallen'));
    const fallenCalls = boardCalls().filter((u) => qs(u).get('tab') === 'fallen');
    expect(fallenCalls.every((u) => !qs(u).has('dj') && !qs(u).has('dj_body'))).toBe(true);
    expect(screen.queryByTestId('cm-dj-board')).toBeNull();
  });

  it('NEGATIVE: a dj / dj_body on a fallen address never rides the fallen request', async () => {
    vi.stubGlobal('fetch', stub(handServe));
    page('/chart-maps?tab=fallen&dj=mas&dj_body=10');
    await waitFor(() => expect(boardCalls().length).toBeGreaterThan(0));
    expect(qs(boardCalls()[0]).get('tab')).toBe('fallen');
    expect(boardCalls().every((u) => !qs(u).has('dj') && !qs(u).has('dj_body'))).toBe(true);
    expect(screen.queryByTestId('cm-dj-board')).toBeNull();
  });

  it('NEGATIVE: while the memo warms, only the served warming header shows — the demand-scan counter is never polled', async () => {
    vi.stubGlobal('fetch', stub(() => clone(HAND_WARM)));
    page('/chart-maps?tab=doji_sweep');
    await waitFor(() => expect(screen.getByTestId('cm-dj-header').textContent).toBe(HAND_WARM.doji_sweep_board.header));
    expect(screen.getByTestId('cm-dj-header').getAttribute('role')).toBe('status');
    expect(screen.getByTestId('cm-dj-study').textContent).toBe(HAND_WARM.doji_sweep_board.study.text);
    await new Promise((r) => setTimeout(r, 50));
    expect(allCalls().some((u) => u.includes('/supply-demand/demand-reentry/progress'))).toBe(false);
    expect(screen.queryByTestId('cm-dj-filters')).toBeNull();
    expect(order()).toEqual([]);
  });
});

describe('🕯️ Doji Sweep — the WP-B GOLDEN on the page (skips until the fixture is written)', () => {
  it.skipIf(!GOLDEN)('the default entry: the note, one card per served tile in the served order, no NaN / undefined / None / b-word', async () => {
    vi.stubGlobal('fetch', stub(goldenServe));
    page('/chart-maps?tab=doji_sweep&show=all');
    const syms = GOLDEN!.default.tiles.map((t) => String(t.symbol));
    await waitFor(() => expect(order()).toEqual(syms));
    expect(screen.getByTestId('cm-dj-header').textContent).toBe(GOLDEN!.default.doji_sweep_board.header);
    expect(document.body.textContent || '').not.toMatch(new RegExp(`${['bou', 'nce'].join('')}|NaN|undefined|None`));
  });

  it.skipIf(!GOLDEN)('a w52_70 chip click serves the w52_70 entry and the request carries dj=w52_70', async () => {
    vi.stubGlobal('fetch', stub(goldenServe));
    page('/chart-maps?tab=doji_sweep&show=all');
    await waitFor(() => expect(screen.getByTestId('cm-dj-board')).toBeTruthy());
    fireEvent.click(screen.getByTestId('cm-dj-filter-w52_70'));
    await waitFor(() => expect(qs(lastBoardCall()).get('dj')).toBe('w52_70'));
    const syms = GOLDEN!.w52_70.tiles.map((t) => String(t.symbol));
    await waitFor(() => expect(order()).toEqual(syms));
    expect((screen.getByTestId('cm-dj-filter-w52_70') as HTMLInputElement).checked).toBe(true);
  });

  it.skipIf(!GOLDEN)('a body click on "10" serves the body10 entry', async () => {
    vi.stubGlobal('fetch', stub(goldenServe));
    page('/chart-maps?tab=doji_sweep&show=all');
    await waitFor(() => expect(screen.getByTestId('cm-dj-board')).toBeTruthy());
    fireEvent.click(screen.getByTestId('cm-dj-body-10'));
    await waitFor(() => expect(qs(lastBoardCall()).get('dj_body')).toBe('10'));
    await waitFor(() => expect(pressed('cm-dj-body-10')).toBe('true'));
    const syms = GOLDEN!.body10.tiles.map((t) => String(t.symbol));
    await waitFor(() => expect(order()).toEqual(syms));
  });

  it.skipIf(!GOLDEN)('NEGATIVE: the golden warming entry shows its served warming header, never the demand counter', async () => {
    vi.stubGlobal('fetch', stub(() => clone(GOLDEN!.warming)));
    page('/chart-maps?tab=doji_sweep');
    const h = GOLDEN!.warming.doji_sweep_board.header;
    await waitFor(() => expect(screen.getByTestId('cm-dj-header').textContent).toBe(h));
    expect(screen.getByTestId('cm-dj-header').getAttribute('role')).toBe('status');
    await new Promise((r) => setTimeout(r, 50));
    expect(allCalls().some((u) => u.includes('/supply-demand/demand-reentry/progress'))).toBe(false);
  });
});
