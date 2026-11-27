/* 📅 GgwRunRoster — the runners kept on the 👀 Watch for two weeks (2026-11-26, spec watchrun rev 2 §3.5, WP fe-roster).
 * Ajay 2026-11-26: "Ok then add them to our watch list and track them please.. I know he tracks them for two weeks
 * sometimes.. before he discards them.. Can you do that please" · "Make it 30% please after A+".
 * The real roster, fetch stubbed, the served golden (lib/__fixtures__/ggwRunRoster.golden.json). NEGATIVES throughout:
 * junk → nothing, no track fetch until a fold opens, the roster × NEVER fetches ggwSymbolPath, no hint / sentence outside
 * the ⓘ fold, no admin address in any source file. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import gold from '../lib/__fixtures__/ggwRunRoster.golden.json';
import GgwRunRoster from './GgwRunRoster';
import { ggwSymbolPath } from '../lib/gajjalaWatch';
import { closeGgRunChart, useGgRunChartOpen } from '../lib/ggRunChart';
import {
  GGW_RUNSEAT_PATH, GGW_RUNTRACK_PATH, ggwRunSeatPath, parseRunRoster, type GgwRunRoster as Block,
} from '../lib/ggwRunRoster';

const G = gold as any;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const block = (o: Record<string, unknown> = {}): Block => parseRunRoster({ ...clone(G.runners), ...o }) as Block;
const res = (body: unknown, ok = true) => ({ ok, status: ok ? 200 : 500, json: async () => body }) as unknown as Response;
function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

type Call = { url: string; method: string };
let calls: Call[] = [];
let seatAnswer: () => Response | Promise<Response> = () => res(G.seat_answers.dismissed);
function stubFetch() {
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    calls.push({ url, method });
    if (url.includes(GGW_RUNSEAT_PATH)) return seatAnswer();
    if (url.includes(`${GGW_RUNTRACK_PATH}?symbol=`)) return res(G.track_symbol);
    if (url.includes(GGW_RUNTRACK_PATH)) return res(G.track_all);
    /* the shared ➕ button's list read */
    if (url.endsWith('/chart-maps/gajjala-watch/symbols')) {
      return res({ state: 'ok', symbols: ['POM'], full: false, full_text: null,
        labels: { add: '➕', remove: '➖', add_title: 'served-add {symbol}', remove_title: 'served-rm {symbol}' } });
    }
    return res({});
  }));
}
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
const flushN = async (n = 4) => { for (let i = 0; i < n; i += 1) await flush(); };
let lastOpen: ReturnType<typeof useGgRunChartOpen> = null;
function OpenProbe() { lastOpen = useGgRunChartOpen(); return null; }
function mount(b: Block, o: { phone?: boolean; onChanged?: (t: string | null) => void } = {}) {
  const onChanged = o.onChanged ?? vi.fn();
  const r = render(<><GgwRunRoster block={b} phone={o.phone ?? false} onChanged={onChanged} /><OpenProbe /></>);
  return { ...r, onChanged };
}
const rowIds = () => Array.from(document.querySelectorAll('[data-testid^="ggw-rr-row-"]'))
  .map((e) => (e.getAttribute('data-testid') as string).replace('ggw-rr-row-', ''));
const openInfo = async () => {
  const det = screen.getByTestId('ggw-rr-info') as HTMLDetailsElement;
  await act(async () => { det.open = true; fireEvent(det, new Event('toggle')); });
  await flushN();
  return det;
};
const trackGets = () => calls.filter((c) => c.url.includes(GGW_RUNTRACK_PATH));

beforeEach(() => {
  calls = [];
  seatAnswer = () => res(G.seat_answers.dismissed);
  vi.stubGlobal('localStorage', memStorage());
  stubFetch();
});
afterEach(() => { cleanup(); act(() => closeGgRunChart()); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('📅 the roster draws the served words, in served order', () => {
  it('desktop: the served head, the first fold_at rows in served order (🚫 last as served) and the served "+n more"', () => {
    mount(block());
    expect(screen.getByTestId('ggw-rr-head').textContent).toBe(G.runners.text);
    const all = G.runners.rows.map((r: any) => r.symbol);
    expect(rowIds()).toEqual(all.slice(0, G.runners.fold_at));
    expect(screen.getByTestId('ggw-rr-more').textContent).toBe(`+${all.length - G.runners.fold_at} more`);
    fireEvent.click(screen.getByTestId('ggw-rr-more'));
    expect(rowIds()).toEqual(all);
    expect(rowIds()[rowIds().length - 1]).toBe('WORX');
    expect(screen.getByTestId('ggw-rr-broker-WORX').textContent).toBe('🚫 Fidelity');
    expect(screen.getByTestId('ggw-rr-more').textContent).toBe(G.runners.less_text);
  });
  it('every chip is the served string: day, seat (hover = the served seat title), on-your-Watch words', () => {
    mount(block());
    const r0 = G.runners.rows[0];
    expect(screen.getByTestId('ggw-rr-day-BGLC').textContent).toBe(r0.day_text);
    expect(screen.getByTestId('ggw-rr-seat-BGLC').textContent).toBe(r0.seat_text);
    expect(screen.getByTestId('ggw-rr-seat-BGLC').getAttribute('title')).toBe(r0.seat_title);
    expect(screen.getByTestId('ggw-rr-seat-GLXG').textContent).toBe('🎯 +41% from A+');
    expect(screen.getByTestId('ggw-rr-onwatch-POM').textContent).toBe('on your Watch above');
  });
  it('NEGATIVE: an on_watch row prints the served words and NO ➕; a row off the Watch gets the shared ➕ (not the words)', async () => {
    mount(block());
    await flushN();
    expect(screen.queryByTestId('ggw-card-btn-POM')).toBeNull();
    expect(screen.queryByTestId('ggw-card-btn-BGLC')).not.toBeNull();
    expect(screen.queryByTestId('ggw-rr-onwatch-BGLC')).toBeNull();
  });
  it('the ticker opens the continuous chart with the roster list in served order', () => {
    mount(block());
    fireEvent.click(screen.getByTestId('ggw-rr-sym-GLXG'));
    expect(lastOpen).toEqual({ symbol: 'GLXG', list: G.runners.rows.map((r: any) => r.symbol) });
  });
  it('NEGATIVE: "unreadable" → the served line only (no head, no rows, no fold)', () => {
    const b = parseRunRoster(G.unreadable) as Block;
    mount(b);
    expect(screen.getByTestId('ggw-rr-warn').textContent).toBe(G.unreadable.text);
    expect(screen.queryByTestId('ggw-rr-head')).toBeNull();
    expect(screen.queryByTestId('ggw-rr-info')).toBeNull();
    expect(rowIds()).toEqual([]);
  });
  it('NEGATIVE: junk never reaches the board — parseRunRoster(junk) is null', () => {
    for (const j of [null, 'x', 3, [], {}, { state: '' }, { state: 4, rows: [] }]) expect(parseRunRoster(j)).toBeNull();
  });
  it('NEGATIVE: fewer rows than fold_at → no "+n more"', () => {
    mount(block({ rows: clone(G.runners.rows).slice(0, 3) }));
    expect(rowIds()).toEqual(['BGLC', 'POM', 'GLXG']);
    expect(screen.queryByTestId('ggw-rr-more')).toBeNull();
  });
});

describe('📅 ⓘ — the only place any explanation lives', () => {
  it('the served hint and the served not_seated sentences, verbatim, INSIDE the fold', () => {
    mount(block());
    const det = screen.getByTestId('ggw-rr-info');
    expect(det.tagName).toBe('DETAILS');
    expect(det.querySelector('[data-testid="ggw-rr-hint"]')!.textContent).toBe(G.runners.hint);
    const ns = Array.from(det.querySelectorAll('[data-testid="ggw-rr-not-seated"]')).map((e) => e.textContent);
    expect(ns).toEqual(G.runners.not_seated.map((n: any) => n.text));
  });
  it('NEGATIVE: no hint, no not-seated sentence and no seat title anywhere outside the fold', () => {
    const { container } = mount(block());
    const det = screen.getByTestId('ggw-rr-info');
    const outside = container.cloneNode(true) as HTMLElement;
    outside.querySelector('[data-testid="ggw-rr-info"]')!.remove();
    const text = outside.textContent ?? '';
    expect(text).not.toContain(G.runners.hint);
    for (const n of G.runners.not_seated) expect(text).not.toContain(n.text);
    for (const r of G.runners.rows) expect(text).not.toContain(r.seat_title);
    expect(det).not.toBeNull();
    expect(outside.querySelectorAll('p').length).toBe(0);
  });
  it('NEGATIVE: no track fetch until ⓘ opens; opening it fetches the record ONCE and prints its served summary, note and table', async () => {
    mount(block());
    await flushN();
    expect(trackGets()).toEqual([]);
    await openInfo();
    expect(trackGets().map((c) => c.url)).toEqual([expect.stringMatching(new RegExp(`${GGW_RUNTRACK_PATH}$`))]);
    expect(trackGets()[0].method).toBe('GET');
    expect(screen.getByTestId('ggw-rr-track-summary').textContent).toBe(G.track_all.summary_text);
    expect(screen.getByTestId('ggw-rr-track-note').textContent).toBe(G.track_all.note);
    const table = screen.getByTestId('ggw-rr-track-table');
    expect(Array.from(table.querySelectorAll('th')).map((t) => t.textContent)).toEqual(G.track_all.heads.map((h: any) => h[1]));
    expect(table.querySelectorAll('tbody tr').length).toBe(G.track_all.rows.length);
    expect(table.querySelector('tbody tr td')!.textContent).toBe('AIMD');
    expect(screen.getByTestId('ggw-rr-info').contains(table)).toBe(true);
    expect(table.parentElement!.classList.contains('ggw-rr-scroll')).toBe(true);
  });
  it('NEGATIVE: closing ⓘ drops the record (nothing of it outside the fold, the next open reads again)', async () => {
    mount(block());
    const det = await openInfo();
    await act(async () => { det.open = false; fireEvent(det, new Event('toggle')); });
    expect(screen.queryByTestId('ggw-rr-track')).toBeNull();
    await openInfo();
    expect(trackGets().length).toBe(2);
  });
  it('a row 🧾 fetches ?symbol= only when opened, prints the served seat title and the served docs', async () => {
    mount(block());
    await flushN();
    expect(trackGets()).toEqual([]);
    fireEvent.click(screen.getByTestId('ggw-rr-hist-btn-BGLC'));
    await flushN();
    expect(trackGets().map((c) => c.url)).toEqual([expect.stringContaining(`${GGW_RUNTRACK_PATH}?symbol=BGLC`)]);
    expect(screen.getByTestId('ggw-rr-seat-title-BGLC').textContent).toBe(G.runners.rows[0].seat_title);
    expect(screen.getByTestId('ggw-rr-doc-BGLC').textContent).toContain(G.track_symbol.docs[0].base_note);
    expect(screen.getByTestId('ggw-rr-doc-table-BGLC').querySelectorAll('tbody tr').length).toBe(2);
  });
});

describe('📅 the roster × [C4] — its own route, never the tile\'s', () => {
  it('on EVERY row (on_watch too), titled with the served remove_title', () => {
    mount(block());
    fireEvent.click(screen.getByTestId('ggw-rr-more'));
    for (const r of G.runners.rows) {
      const x = screen.getByTestId(`ggw-rr-x-${r.symbol}`);
      expect(x.getAttribute('title')).toBe(r.remove_title);
    }
    expect(screen.getByTestId('ggw-rr-x-POM')).not.toBeNull();
  });
  it('one DELETE on ggwRunSeatPath(sym), NEVER ggwSymbolPath(sym); the row leaves at once; onChanged(served text) once', async () => {
    const { onChanged } = mount(block());
    await flushN();
    calls = [];
    fireEvent.click(screen.getByTestId('ggw-rr-x-POM'));
    expect(rowIds()).not.toContain('POM');
    await flushN();
    expect(calls.filter((c) => c.method === 'DELETE').map((c) => c.url)).toEqual([expect.stringMatching(/\/runners\/seat\/POM$/)]);
    expect(calls[0].url.endsWith(ggwRunSeatPath('POM'))).toBe(true);
    expect(calls.some((c) => c.url.endsWith(ggwSymbolPath('POM')))).toBe(false);
    expect(calls.some((c) => c.url.includes('/gajjala-watch/symbols/'))).toBe(false);
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(onChanged).toHaveBeenCalledWith(G.seat_answers.dismissed.text);
  });
  it('NEGATIVE: two taps in one tick → ONE DELETE', async () => {
    mount(block());
    calls = [];
    const x = screen.getByTestId('ggw-rr-x-BGLC');
    fireEvent.click(x);
    fireEvent.click(x);
    await flushN();
    expect(calls.filter((c) => c.method === 'DELETE').length).toBe(1);
  });
  it('a failed × (served "error") → the served text; the row is back once the re-GET still lists it', async () => {
    seatAnswer = () => res(G.seat_answers.error);
    const { onChanged, rerender } = mount(block());
    fireEvent.click(screen.getByTestId('ggw-rr-x-BGLC'));
    expect(rowIds()).not.toContain('BGLC');
    await flushN();
    expect(onChanged).toHaveBeenCalledWith(G.seat_answers.error.text);
    rerender(<><GgwRunRoster block={block()} phone={false} onChanged={onChanged} /><OpenProbe /></>);
    expect(rowIds()).toContain('BGLC');
  });
  it('NEGATIVE: a request that fails → onChanged(null); a served roster that dropped the name keeps it gone', async () => {
    seatAnswer = () => Promise.reject(new Error('net'));
    const { onChanged, rerender } = mount(block());
    fireEvent.click(screen.getByTestId('ggw-rr-x-BGLC'));
    await flushN();
    expect(onChanged).toHaveBeenCalledWith(null);
    const without = block({ rows: clone(G.runners.rows).filter((r: any) => r.symbol !== 'BGLC') });
    rerender(<><GgwRunRoster block={without} phone={false} onChanged={onChanged} /><OpenProbe /></>);
    expect(rowIds()).not.toContain('BGLC');
  });
  it('NEGATIVE: a newer roster served while the × is still in flight does not bring the row back', async () => {
    let release!: (r: Response) => void;
    seatAnswer = () => new Promise<Response>((ok) => { release = ok; });
    const { onChanged, rerender } = mount(block());
    fireEvent.click(screen.getByTestId('ggw-rr-x-BGLC'));
    await flushN();
    rerender(<><GgwRunRoster block={block()} phone={false} onChanged={onChanged} /><OpenProbe /></>);
    expect(rowIds()).not.toContain('BGLC');
    await act(async () => { release(res(G.seat_answers.dismissed)); });
    await flushN();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });
});

describe('📅 source guards', () => {
  const FILES = ['src/components/GgwRunRoster.tsx', 'src/lib/ggwRunRoster.ts', 'src/styles/ggwRunRoster.css',
    'src/components/GajjalaWatchCompact.tsx', 'src/components/GajjalaWatchBoard.tsx', 'src/lib/gajjalaWatch.ts',
    'src/pages/ChartMaps.tsx', 'src/lib/__fixtures__/ggwRunRoster.golden.json',
    'src/components/GgwRunRoster.test.tsx', 'src/components/GgwRunRoster.phone.test.tsx', 'src/lib/ggwRunRoster.test.ts',
    'src/lib/gajjalaWatch.runroster.test.ts', 'src/components/GajjalaWatchCompact.runner.test.tsx',
    'src/components/GajjalaWatchBoard.runroster.test.tsx', 'src/pages/ChartMaps.runChartWatch.test.tsx'];
  it('NEGATIVE: the admin email appears in no source file of this package (nor any gmail address)', async () => {
    const admin = new RegExp(`${['ajay', 'kandakatla'].join('')}|@${'g'}mail`, 'i');   /* built, so this file never holds it */
    for (const f of FILES) {
      const src = await readSource(f);
      expect(src, f).not.toMatch(admin);
    }
  });
  it('NEGATIVE: the roster never names the tile route, the board write or a number of its own', async () => {
    const comp = await readSource('src/components/GgwRunRoster.tsx');
    const lib = await readSource('src/lib/ggwRunRoster.ts');
    const code = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
    for (const s of [code(comp), code(lib)]) {
      expect(s).not.toMatch(/ggwSymbolPath|\/symbols\//);
      expect(s).not.toMatch(/write\(/);
      expect(s).not.toMatch(/bounc|calm|pullback/i);
      expect(s).not.toMatch(/toFixed\(|toLocaleString\(|Intl\.|\.sort\(/);
    }
    expect(code(comp)).not.toMatch(/\d/);
    expect(lib).not.toMatch(/from '\.\/gajjalaWatch'/);
  });
});
