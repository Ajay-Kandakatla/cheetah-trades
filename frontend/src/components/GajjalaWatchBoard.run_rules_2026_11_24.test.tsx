/* ▶ Run Gajjala's rules from the 👀 Watch — the REAL board (2026-11-24, spec ggrun §3.5 / §4 fe-run).
 * Ajay 2026-11-24: "On the Watch list I need a run button to run against Gajjalas rules of a stock to see for patterns of
 * 5 patterns he has especially reversal squeeze.. so can check for patterns mid day when I can add a small slide in in
 * the chart window for giving verbatim of passed rules and failed rules of that stock like you do in other tabs..".
 * The 2026-11-17 auto fixture + a served 🚫 block; fetch routed by method + path; the run answer is a stand-in for the
 * served one (every word "served …").
 * Positives: ONE ▶ per tile, order 🚫 ▶ ⤢ TV Y ✕; a tap → ONE POST to ${API}${ggwRunPath(sym)} and NO board re-GET; the
 * panel opens AT ONCE busy with an enabled ✕, inside THAT tile's chart window; the minute re-GET keeps it open; the ⤢
 * view shows the same button and panel; ✕ closes; a second ▶ re-runs; a pending tile hosts it under its words.
 * NEGATIVES: no other tile gains a panel; ✕ while busy → the late answer prints nothing; 404 → nothing; `Tile` without
 * `run` / with `run` closed → no ggw-charts--run, no .ggw-run, today's DOM; the card grid / card view never pass `run=`;
 * the board keeps ONE <GgwBrokerButton, tags={tagsOf(r)}, no actions= on <GgwStretch; the hook sits above the early
 * returns. No test depends on a ✨ id. UNMEASURED. */
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GgwStretch, Tile } from './GajjalaWatchTile';
import { GgwRunButton, GgwRunPanel } from './GgwRunRules';
import { API } from '../lib/apiBase';
import { GG_BROKER_PATH } from '../lib/gajjala';
import { GGW_LIVE_PATH, GGW_PATH, parseGgw, type GgwBoard } from '../lib/gajjalaWatch';
import { GGW_RUN, GGW_RUN_PATH, ggwRunPath } from '../lib/ggwRun';
import type { GgwBroker } from '../lib/ggwBroker';
import boardSrc from './GajjalaWatchBoard.tsx?raw';
import tileSrc from './GajjalaWatchTile.tsx?raw';
import cardGridSrc from './GgCardGrid.tsx?raw';
import cardViewSrc from './GgCardView.tsx?raw';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = autoFixture as any;
const BLOCK: GgwBroker = {
  toggle: '🚫', text: '🚫 served broker word', title: 'served mark title', editable: true,
  fault_text: null, auto_text: null, auto_fault_text: null,
};
const SETUP = (setup: string, extra: Record<string, unknown> = {}) => ({
  setup, label: `served label ${setup}`, state: 'partial', state_label: `served state words ${setup}`, gate_text: null,
  plan_text: `served plan ${setup}`, variant_label: null, grade_label: null, vol_dried_text: null, frame: '5m',
  as_of_bar_t: '2026-11-13 10:35',
  criteria: [
    { key: `${setup}_a`, label: `served row a ${setup}`, ok: true, value: 'served value', need: 'served need' },
    { key: `${setup}_b`, label: `served row b ${setup}`, ok: false, value: null, need: null },
  ],
  tally_text: `served tally ${setup}`, ...extra,
});
const answerFor = (sym: string) => ({
  state: 'ok', symbol: sym, title: `served title ${sym}`, text: null,
  as_of: { bar_t5: '2026-11-13 10:35', bar_t15: '2026-11-13 10:30', read_at_et: '10:36:12', text: 'served as-of line' },
  reused_text: null, scanner: { listed: true, text: 'served scanner line' }, float_text: 'served float line',
  volume_text: 'served volume line', note: 'served note line',
  setups: [
    SETUP('reversal_squeeze', { state: 'none', state_label: 'served none words', gate_text: 'served gate sentence',
      criteria: [], tally_text: null, plan_text: null }),
    SETUP('bull_flag'), SETUP('kiss_fly'), SETUP('horizontal_fade'), SETUP('intraday_vcp'),
  ],
});
function boardWith(): any {
  const b = clone(RAW);
  b.broker = clone(BLOCK);
  for (const r of b.rows) r.broker_text = null;
  return b;
}
function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}

type Call = { url: string; method: string };
let calls: Call[] = [];
let runStatus = 200;
/** run answers held until released (null → answer at once) */
let holdRuns = false;
let held: Array<() => void> = [];
async function mount() {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  calls = [];
  held = [];
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method ?? 'GET').toUpperCase();
    calls.push({ url, method });
    const ok = (j: unknown) => ({ ok: true, status: 200, json: async () => j } as unknown as Response);
    if (method === 'POST' && url.includes(`${GGW_RUN_PATH}/`)) {
      const sym = decodeURIComponent(url.slice(url.lastIndexOf('/') + 1));
      const out = runStatus === 200 ? ok(answerFor(sym))
        : ({ ok: false, status: runStatus, json: async () => ({ detail: 'served detail' }) } as unknown as Response);
      if (!holdRuns) return out;
      return new Promise<Response>((res) => { held.push(() => res(out)); });
    }
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return ok({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] });
    if (method === 'POST' && url.endsWith(GG_BROKER_PATH)) return ok({ state: 'ok', symbols: [] });
    if (method === 'POST') return ok({ items: {}, rows: {} });
    if (url.includes('/short-interest/') || url.includes('/growth/')) return ok({ items: {}, tags: {} });
    if (url.includes('?symbols=')) return ok({ ...boardWith(), rows: [] });
    return ok(boardWith());
  }));
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_watch']}><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 4; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const flush = async () => { for (let i = 0; i < 6; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); }); };
const tile = (c: ParentNode, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement;
const runBtn = (c: ParentNode, s: string) => c.querySelector(`[data-testid="ggw-run-btn-${s}"]`) as HTMLButtonElement | null;
const runPosts = () => calls.filter((x) => x.method === 'POST' && x.url.includes(`${GGW_RUN_PATH}/`));
const fullGets = () => calls.filter((x) => x.method === 'GET' && x.url === `${API}${GGW_PATH}`);

describe('▶ Rules on the 👀 Watch board', { timeout: 30000 }, () => {
  beforeEach(() => {
    runStatus = 200;
    holdRuns = false;
    vi.useFakeTimers();
    vi.stubGlobal('localStorage', memStorage());
    vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); document.body.style.overflow = ''; });

  it('ONE ▶ per tile, right after the 🚫; the board order 🚫 ▶ ⤢ TV Y ✕; it never hides', async () => {
    const c = await mount();
    for (const s of RAW.rows.map((r: any) => r.symbol)) {
      const acts = tile(c, s).querySelector('.ggw-actions') as HTMLElement;
      expect(acts.querySelectorAll('.ggw-run-btn'), s).toHaveLength(1);
      expect(acts.children[1], s).toBe(runBtn(c, s));
      expect(runBtn(c, s)!.textContent).toBe('▶ Rules');
      expect(runBtn(c, s)!.disabled).toBe(false);
    }
    const kids = Array.from(tile(c, 'OMH').querySelector('.ggw-actions')!.children).map((e) => e.className);
    expect(kids).toEqual(['ggw-btn ggw-broker-mark', 'ggw-btn ggw-run-btn', 'ggw-btn ggw-stretch-btn', 'ggw-btn ggw-tv',
      'ggw-btn ggw-yahoo', 'ggw-btn ggw-remove']);
    expect(c.querySelector('.ggw-run')).toBeNull();
    expect(c.querySelector('.ggw-charts--run')).toBeNull();
  });

  it('a tap → ONE POST to ${API}${ggwRunPath(sym)}, NO board re-GET; the panel opens AT ONCE busy with an enabled ✕', async () => {
    holdRuns = true;
    const c = await mount();
    const gets = fullGets().length;
    calls.length = 0;
    fireEvent.click(runBtn(c, 'OMH')!);
    await act(async () => { await Promise.resolve(); });
    expect(runPosts().map((x) => x.url)).toEqual([`${API}${ggwRunPath('OMH')}`]);
    const panel = within(tile(c, 'OMH')).getByTestId('ggw-run-OMH');
    expect(within(panel).getByTestId('ggw-run-busy').textContent).toBe(GGW_RUN.busy);
    expect((within(panel).getByTestId('ggw-run-close-OMH') as HTMLButtonElement).disabled).toBe(false);
    expect(runBtn(c, 'OMH')!.disabled).toBe(true);
    expect(runBtn(c, 'OMH')!.getAttribute('aria-busy')).toBe('true');
    fireEvent.click(runBtn(c, 'OMH')!);
    expect(runPosts()).toHaveLength(1);
    await act(async () => { held.forEach((f) => f()); });
    await flush();
    expect(within(panel).queryByTestId('ggw-run-busy')).toBeNull();
    expect(within(panel).getByTestId('ggw-run-title').textContent).toBe('served title OMH');
    expect(within(panel).getByTestId('ggw-run-gate-reversal_squeeze').textContent).toBe('served gate sentence');
    expect(fullGets()).toHaveLength(0);
    expect(gets).toBeGreaterThanOrEqual(1);
  });

  it('the panel sits inside THAT tile\'s chart window (last child of .ggw-charts--run); NEGATIVE: no other tile gains one', async () => {
    const c = await mount();
    fireEvent.click(runBtn(c, 'OMH')!);
    await flush();
    const panel = screen.getByTestId('ggw-run-OMH');
    const charts = panel.closest('.ggw-charts') as HTMLElement;
    expect(charts).not.toBeNull();
    expect(charts.className).toBe('ggw-dark ggw-charts ggw-charts--run');
    expect(charts.lastElementChild).toBe(panel);
    expect(charts.closest('[data-testid="ggw-tile-OMH"]')).toBe(tile(c, 'OMH'));
    expect(c.querySelectorAll('.ggw-run')).toHaveLength(1);
    expect(c.querySelectorAll('.ggw-charts--run')).toHaveLength(1);
    expect(tile(c, 'NVDA').querySelector('.ggw-run')).toBeNull();
    expect(runBtn(c, 'OMH')!.getAttribute('aria-expanded')).toBe('true');
    expect(runBtn(c, 'NVDA')!.getAttribute('aria-expanded')).toBe('false');
  });

  it('the minute re-GET keeps it open; ✕ closes it; a second ▶ re-runs', async () => {
    const c = await mount();
    fireEvent.click(runBtn(c, 'OMH')!);
    await flush();
    const before = fullGets().length;
    await act(async () => { await vi.advanceTimersByTimeAsync(61_000); });
    await flush();
    expect(fullGets().length).toBeGreaterThan(before);
    expect(within(tile(c, 'OMH')).getByTestId('ggw-run-title').textContent).toBe('served title OMH');
    fireEvent.click(screen.getByTestId('ggw-run-close-OMH'));
    expect(c.querySelector('.ggw-run')).toBeNull();
    expect(c.querySelector('.ggw-charts--run')).toBeNull();
    fireEvent.click(runBtn(c, 'OMH')!);
    await flush();
    expect(runPosts()).toHaveLength(2);
    expect(within(tile(c, 'OMH')).getByTestId('ggw-run-title').textContent).toBe('served title OMH');
  });

  it('NEGATIVE: ✕ while busy → the panel closes, the button is enabled, the late answer prints NOTHING', async () => {
    holdRuns = true;
    const c = await mount();
    fireEvent.click(runBtn(c, 'OMH')!);
    await act(async () => { await Promise.resolve(); });
    fireEvent.click(screen.getByTestId('ggw-run-close-OMH'));
    expect(c.querySelector('.ggw-run')).toBeNull();
    expect(runBtn(c, 'OMH')!.disabled).toBe(false);
    await act(async () => { held.forEach((f) => f()); });
    await flush();
    expect(c.querySelector('.ggw-run')).toBeNull();
    expect(c.textContent).not.toContain('served title OMH');
  });

  it('NEGATIVE: 404 → no panel, nothing printed', async () => {
    runStatus = 404;
    const c = await mount();
    fireEvent.click(runBtn(c, 'OMH')!);
    await flush();
    expect(runPosts()).toHaveLength(1);
    expect(c.querySelector('.ggw-run')).toBeNull();
    expect(c.textContent).not.toContain('served detail');
    expect(c.textContent).not.toContain(GGW_RUN.failed);
  });

  it('a pending tile (no chart yet) hosts the panel in its own dark box right after the pending words', async () => {
    const c = await mount();
    fireEvent.click(runBtn(c, 'AMD')!);
    await flush();
    const panel = screen.getByTestId('ggw-run-AMD');
    const host = panel.parentElement as HTMLElement;
    expect(host.className).toBe('ggw-dark ggw-run-host');
    expect(host.parentElement).toBe(tile(c, 'AMD'));
    expect(host.previousElementSibling).toBe(screen.getByTestId('ggw-pending-AMD'));
    expect(tile(c, 'AMD').querySelector('.ggw-charts--run')).toBeNull();
  });

  it('the ⤢ view shows the same button and the same open panel (inside its stretch chart window); ✕ there closes both', async () => {
    const c = await mount();
    fireEvent.click(runBtn(c, 'OMH')!);
    await flush();
    fireEvent.click(screen.getByTestId('ggw-stretch-btn-OMH'));
    await flush();
    const st = screen.getByTestId('ggw-stretch');
    const b = within(st).getByTestId('ggw-run-btn-OMH');
    expect(b.textContent).toBe('▶ Rules');
    const sp = within(st).getByTestId('ggw-run-OMH');
    expect(within(sp).getByTestId('ggw-run-title').textContent).toBe('served title OMH');
    expect(sp.closest('.ggw-charts')!.className).toContain('ggw-charts--run');
    expect(sp.closest('.ggw-charts')!.className).toContain('ggw-charts--stretch');
    expect(within(tile(c, 'OMH')).getByTestId('ggw-run-OMH')).toBeTruthy();
    /* the ⤢ row: ▶ Rules then the pager's ▶ Next (HIS CALL 8) */
    const acts = Array.from(st.querySelector('.ggw-actions')!.children).map((e) => e.className);
    expect(acts[0]).toBe('ggw-btn ggw-run-btn');
    expect(acts).toContain('ggw-btn ggw-pager-btn');
    fireEvent.click(within(st).getByTestId('ggw-run-close-OMH'));
    expect(document.querySelectorAll('.ggw-run')).toHaveLength(0);
  });
});

describe('▶ Tile `run` — opt-in, today\'s DOM when absent or closed', () => {
  afterEach(() => cleanup());
  const R = (el: JSX.Element) => render(<MemoryRouter>{el}</MemoryRouter>);
  const B = parseGgw(clone(RAW)) as GgwBoard;
  const okRow = B.rows.find((r) => r.symbol === 'OMH')!;
  const pendingRow = B.rows.find((r) => r.symbol === 'AMD')!;
  const base = { phone: false, fit: false, removeLabel: 'Remove', focused: false, busy: false, onRemove: () => {}, onStretch: () => {} };
  const slot = (sym: string, open: boolean) => ({
    button: null, panel: <GgwRunPanel sym={sym} state={open ? { phase: 'busy' } : null} onClose={() => {}} />, open,
  });

  it('NEGATIVE: no `run` → no ▶, no ggw-charts--run, no .ggw-run; `run` closed with no button → the same innerHTML', () => {
    for (const row of [okRow, pendingRow]) {
      const a = R(<Tile {...base} row={row} />).container.innerHTML;
      cleanup();
      const b = R(<Tile {...base} row={row} run={slot(row.symbol, false)} />).container.innerHTML;
      cleanup();
      expect(b, row.symbol).toBe(a);
      expect(a).not.toContain('ggw-run');
    }
    const { container } = R(<Tile {...base} row={okRow} />);
    expect(container.querySelector('.ggw-charts')!.className).toBe('ggw-dark ggw-charts');
  });
  it('`run` with a button, closed → only the button is added (after `actions`), no panel', () => {
    const a = R(<Tile {...base} row={okRow} />).container;
    const acts0 = Array.from(a.querySelector('.ggw-actions')!.children).map((e) => e.className);
    cleanup();
    const { container } = R(<Tile {...base} row={okRow} actions={<i className="x-act" />}
      run={{ button: <GgwRunButton sym="OMH" state={null} onRun={() => {}} />, panel: null, open: false }} />);
    const acts = Array.from(container.querySelector('.ggw-actions')!.children).map((e) => e.className);
    expect(acts).toEqual(['x-act', 'ggw-btn ggw-run-btn', ...acts0]);
    expect(container.querySelector('.ggw-run')).toBeNull();
    expect(container.querySelector('.ggw-charts--run')).toBeNull();
  });
  it('`run` open on the ⤢ Tile → the panel is the last child of the stretch chart window', () => {
    const { container } = R(<Tile {...base} row={okRow} onUnstretch={() => {}} run={slot('OMH', true)} />);
    const charts = container.querySelector('[data-testid="ggw-stretch-charts"]')!;
    expect(charts.className).toBe('ggw-dark ggw-charts ggw-charts--stretch ggw-charts--run');
    expect(charts.lastElementChild!.getAttribute('data-testid')).toBe('ggw-run-OMH');
  });
  it('GgwStretch forwards `run`', () => {
    R(<GgwStretch row={okRow} phone={false} removeLabel="Remove" onClose={() => {}} onStep={null}
      run={{ button: <GgwRunButton sym="OMH" state={{ phase: 'busy' }} onRun={() => {}} />, panel: slot('OMH', true).panel, open: true }} />);
    const st = screen.getByTestId('ggw-stretch');
    expect(within(st).getByTestId('ggw-run-btn-OMH')).toBeTruthy();
    expect(within(st).getByTestId('ggw-run-OMH')).toBeTruthy();
  });
});

describe('▶ source guards', () => {
  it('NEGATIVE: the 🚩 / 🧪 card grid and card view never pass `run=`', () => {
    expect(cardGridSrc.length).toBeGreaterThan(500);
    expect(cardViewSrc.length).toBeGreaterThan(500);
    expect(cardGridSrc).not.toMatch(/\brun=/);
    expect(cardViewSrc).not.toMatch(/\brun=/);
  });
  it('the board: ONE useGgwRun() above the early returns; run= on <Tile and <GgwStretch; the 🚫 pins kept', () => {
    expect(boardSrc.match(/useGgwRun\(\)/g)).toHaveLength(1);
    expect(boardSrc.indexOf('const runRules = useGgwRun();')).toBeGreaterThan(boardSrc.indexOf('useGgwBrokerMark('));
    expect(boardSrc.indexOf('const runRules = useGgwRun();')).toBeLessThan(boardSrc.indexOf("if (load.phase === 'loading')"));
    expect(boardSrc).toContain('run={runOf(r)}');
    expect(boardSrc).toContain('run={runOf(stretchRow)}');
    expect(boardSrc.match(/<GgwBrokerButton /g)).toHaveLength(1);
    expect(boardSrc).toContain('tags={tagsOf(r)}');
    const stretch = boardSrc.slice(boardSrc.indexOf('<GgwStretch '));
    expect(stretch.slice(0, stretch.indexOf('/>'))).not.toContain('actions=');
  });
  it('the tile draws run.button after actions in BOTH views and the panel only when open', () => {
    expect(tileSrc).toContain('{actions && !onUnstretch ? actions : null}\n          {run?.button ?? null}');
    expect(tileSrc.match(/\{runOpen \? run!\.panel : null\}/g)).toHaveLength(2);
    expect(tileSrc).toContain('{runOpen ? <div className="ggw-dark ggw-run-host">{run!.panel}</div> : null}');
  });
});
