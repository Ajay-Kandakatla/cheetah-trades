/* 👀 GajjalaWatchBoard (2026-11-15, gajjala-watch spec §3.8, WP-C). Ajay: "I need dashboard to add tickers to Gajjalas
 * watch dashboard. I wanna be able to remove and add remove tickers from the dashboard. When I add a ticker I need 1 min
 * 3 min and 5 min charts... Not the SEPA" · "I have a 27 inch monitor I wanna fit 3x3 tikers on watch".
 * The real board over the §3.7 fixture (4 rows: ok with crosses + a held chip / pending / no_prints / ok-but-stale) with
 * fetch stubbed: owner gate, add / remove, the three charts per tile, the ℹ️ printed once, no SEPA link, the cadence (the
 * served refresh_sec, ONE re-GET at next_window_sec, the pending poll on ?symbols= only). NEGATIVES throughout. */
import { act, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_CHART_H, GGW_PATH, ggwRowsPath, ggwSymbolPath } from '../lib/gajjalaWatch';

type Call = { url: string; method: string };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

function stubFetch(board: () => any, opts: { write?: any; rows?: (syms: string[]) => any } = {}) {
  const calls: Call[] = [];
  const fn = vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    calls.push({ url, method });
    if (method !== 'GET') {
      return { ok: true, json: async () => opts.write ?? { state: 'added', symbols: [], symbol: 'OMH', text: 'OMH added' } } as unknown as Response;
    }
    const q = url.split('?symbols=')[1];
    if (q != null) {
      const syms = decodeURIComponent(q).split(',');
      const b = opts.rows ? opts.rows(syms) : { ...board(), rows: board().rows.filter((r: any) => syms.includes(r.symbol)) };
      return { ok: true, json: async () => b } as unknown as Response;
    }
    return { ok: true, json: async () => board() } as unknown as Response;
  });
  vi.stubGlobal('fetch', fn);
  return calls;
}
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
async function mount(search = '') {
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala_watch${search}`]}><GajjalaWatchBoard /></MemoryRouter>);
  await flush();
  await flush();
  return r;
}
const gets = (calls: Call[]) => calls.filter((c) => c.method === 'GET');
const full = (calls: Call[]) => gets(calls).filter((c) => c.url.endsWith(GGW_PATH));
// 2026-11-18: the 🩳 EXTREME note adds ONE GET /short-interest/map?symbols=… per mount — the Watch's own row polls are the GGW_PATH ones
const rows = (calls: Call[]) => gets(calls).filter((c) => c.url.includes(GGW_PATH + '?symbols='));
const noPending = () => { const b = clone(fixture) as any; b.rows = b.rows.filter((r: any) => r.state !== 'pending'); delete b.pending_poll_sec; delete b.pending_wait_max_sec; return b; };

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('👀 owner gate and states', () => {
  it('owner_only → the served reason only — NEGATIVE: no input, no chart, no tile', async () => {
    stubFetch(() => ({ state: 'owner_only', reason: 'Shown to the account owner only.', title: 'x' }));
    const { container } = await mount();
    expect(container.textContent).toBe('Shown to the account owner only.');
    expect(container.querySelector('input')).toBeNull();
    expect(container.querySelector('svg')).toBeNull();
    expect(container.querySelector('.ggw-tile')).toBeNull();
  });
  it('an empty list → the served empty_text and the add box', async () => {
    stubFetch(() => ({ ...clone(fixture), rows: [], symbols: [] }));
    const { container, getByTestId } = await mount();
    expect(getByTestId('ggw-empty').textContent).toBe((fixture as any).empty_text);
    expect(container.querySelector('input.ggw-input')).not.toBeNull();
    expect(container.querySelector('.ggw-tile')).toBeNull();
  });
  it('NEGATIVE: junk → the one FE sentence, no tile', async () => {
    stubFetch(() => ({ nope: 1 }));
    const { container } = await mount();
    expect(container.textContent).toBe('Could not load the watch.');
  });
});

describe('👀 tiles', () => {
  it('rows in served order; every ok row draws 3 charts: 1m first full width, then 3m + 5m in .ggw-frame-pair', async () => {
    stubFetch(noPending);
    const { container } = await mount();
    const tiles = Array.from(container.querySelectorAll('.ggw-tile')).map((t) => t.getAttribute('data-testid'));
    expect(tiles).toEqual(['ggw-tile-OMH', 'ggw-tile-XYZQ', 'ggw-tile-NVDA']);
    for (const sym of ['OMH', 'NVDA']) {
      const charts = container.querySelector(`[data-testid="ggw-tile-${sym}"] .ggw-charts`)!;
      const first = charts.firstElementChild!;
      expect(first.getAttribute('data-tf')).toBe('1m');
      const pair = charts.querySelector('.ggw-frame-pair')!;
      expect(Array.from(pair.querySelectorAll('.ggw-frame')).map((f) => f.getAttribute('data-tf'))).toEqual(['3m', '5m']);
      const vb = (tf: string) => charts.querySelector(`.ggw-frame[data-tf="${tf}"] svg`)!.getAttribute('viewBox');
      expect(vb('1m')).toBe(`0 0 620 ${GGW_CHART_H['1m']}`);
      expect(vb('3m')).toBe(`0 0 620 ${GGW_CHART_H['3m']}`);
      expect(vb('5m')).toBe(`0 0 620 ${GGW_CHART_H['5m']}`);
      // the bold 9 / 21 and the diamonds on every chart that has crosses
      expect(charts.querySelectorAll('polyline.pc-ema-bold-ema9')).toHaveLength(3);
    }
    // NEGATIVE: a no_prints row draws no chart, only its served sentence
    const x = container.querySelector('[data-testid="ggw-tile-XYZQ"]')!;
    expect(x.querySelector('svg')).toBeNull();
    expect(x.textContent).toContain('No prints yet today for XYZQ');
    expect(x.textContent).not.toContain('check the ticker');
  });
  it('[C4.6] captions print label · uptrend.short and the served held text; info printed exactly ONCE (inside .ggw-info)', async () => {
    stubFetch(noPending);
    const { container } = await mount();
    const f = (fixture as any).rows[0].frames[0];
    const cap = container.querySelector('[data-testid="ggw-tile-OMH"] .ggw-frame[data-tf="1m"] figcaption')!;
    expect(cap.textContent).toContain(`${f.label} · ${f.uptrend.short}`);
    expect(cap.querySelector('[data-testid="ggw-held"]')!.textContent).toBe(f.held.text);
    expect(container.querySelectorAll('[data-testid="ggw-held"]')).toHaveLength(1);
    const info = (fixture as any).info;
    const text = container.textContent || '';
    for (const s of [info.uptrend_rule, info.push_text, info.honesty]) {
      expect(text.split(s).length - 1).toBe(1);
      expect(container.querySelector('details.ggw-info')!.textContent).toContain(s);
    }
    expect(container.querySelector('details.ggw-info')!.hasAttribute('open')).toBe(false);
  });
  it('a stale row → ⚠️ + the served text + as_of_et', async () => {
    stubFetch(noPending);
    const { container } = await mount();
    const t = container.querySelector('[data-testid="ggw-tile-NVDA"]')!;
    const row = (fixture as any).rows[3];
    expect(t.querySelector('[data-testid="ggw-row-text"]')!.textContent).toBe(row.text);
    expect(t.querySelector('[data-testid="ggw-asof"]')!.textContent).toBe(`⚠️ ${row.as_of_et}`);
    expect(t.querySelector('[data-testid="ggw-rang"]')!.textContent).toBe(row.rang[0].text);
    // NEGATIVE: a fresh row's as-of carries no ⚠️
    expect(container.querySelector('[data-testid="ggw-tile-OMH"] [data-testid="ggw-asof"]')!.textContent).toBe('10:30');
  });
  it('NEGATIVE: no <a> whose href starts /sepa/ anywhere; the Yahoo ↗ once per tile', async () => {
    stubFetch(() => clone(fixture));
    const { container } = await mount();
    expect(container.querySelectorAll('a[href^="/sepa/"]')).toHaveLength(0);
    expect(container.querySelectorAll('a')).toHaveLength(0);
    for (const t of Array.from(container.querySelectorAll('.ggw-tile'))) {
      expect(t.querySelectorAll('button.ggw-yahoo')).toHaveLength(1);
    }
  });
  it('?focus=NVDA scrolls that tile into view and outlines it — NEGATIVE: no other tile outlined', async () => {
    const spy = vi.fn();
    (Element.prototype as any).scrollIntoView = spy;
    stubFetch(noPending);
    const { container } = await mount('&focus=nvda');
    expect(container.querySelector('[data-testid="ggw-tile-NVDA"]')!.classList.contains('ggw-tile-focus')).toBe(true);
    expect(container.querySelectorAll('.ggw-tile-focus')).toHaveLength(1);
    expect(spy).toHaveBeenCalledTimes(1);
  });
});

describe('👀 add / remove', () => {
  it('add → POST ggwSymbolPath(OMH) then a full GET; Enter submits', async () => {
    const calls = stubFetch(noPending);
    const { container } = await mount();
    const before = full(calls).length;
    const input = container.querySelector('input.ggw-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'OMH' } });
    fireEvent.submit(input.closest('form')!);
    await flush(); await flush(); await flush();
    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.url.endsWith(ggwSymbolPath('OMH'))).toBe(true);
    expect(full(calls).length).toBe(before + 1);
    expect(calls.indexOf(post)).toBeLessThan(calls.lastIndexOf(full(calls).pop()!));
    expect(container.querySelector('[data-testid="ggw-msg"]')!.textContent).toBe('OMH added');
  });
  it('NEGATIVE: an empty box sends nothing', async () => {
    const calls = stubFetch(noPending);
    const { container } = await mount();
    fireEvent.submit(container.querySelector('form.ggw-add')!);
    await flush();
    expect(calls.filter((c) => c.method !== 'GET')).toHaveLength(0);
  });
  it('full → the input is disabled with the served text', async () => {
    stubFetch(() => ({ ...noPending(), full: true }));
    const { container, getByTestId } = await mount();
    const input = container.querySelector('input.ggw-input') as HTMLInputElement;
    expect(input.disabled).toBe(true);
    expect(input.placeholder).toBe((fixture as any).full_text);
    expect(getByTestId('ggw-full').textContent).toBe((fixture as any).full_text);
  });
  it('✕ → DELETE ggwSymbolPath(sym), no confirm, then a full GET', async () => {
    const conf = vi.fn(() => true);
    vi.stubGlobal('confirm', conf);
    const calls = stubFetch(noPending, { write: { state: 'removed', symbols: [], symbol: 'NVDA', text: 'NVDA removed' } });
    const { container } = await mount();
    const before = full(calls).length;
    fireEvent.click(container.querySelector('[data-testid="ggw-tile-NVDA"] button.ggw-remove')!);
    await flush(); await flush(); await flush();
    const del = calls.find((c) => c.method === 'DELETE')!;
    expect(del.url.endsWith(ggwSymbolPath('NVDA'))).toBe(true);
    expect(full(calls).length).toBe(before + 1);
    expect(conf).not.toHaveBeenCalled();
  });
});

describe('👀 cadence', () => {
  it('re-GETs the full board at the served refresh_sec', async () => {
    const calls = stubFetch(noPending);
    await mount();
    expect(full(calls)).toHaveLength(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(59_000); });
    expect(full(calls)).toHaveLength(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1_500); });
    expect(full(calls)).toHaveLength(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(full(calls)).toHaveLength(3);
  });
  it('NEGATIVE: a hidden page does not re-GET; the chain resumes when visible', async () => {
    const calls = stubFetch(noPending);
    await mount();
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    await act(async () => { await vi.advanceTimersByTimeAsync(180_500); });
    expect(full(calls)).toHaveLength(1);
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(full(calls)).toHaveLength(2);
  });
  it('NEGATIVE: refresh_sec 0 and no next_window_sec → no re-GET at all', async () => {
    const calls = stubFetch(() => ({ ...noPending(), refresh_sec: 0, next_window_sec: null }));
    await mount();
    await act(async () => { await vi.advanceTimersByTimeAsync(6 * 3600_000); });
    expect(full(calls)).toHaveLength(1);
    expect(rows(calls)).toHaveLength(0);
  });
  it('[C2.7] out of window: ONE re-GET after next_window_sec', async () => {
    let n = 0;
    const calls = stubFetch(() => { n += 1; return { ...noPending(), refresh_sec: 0, next_window_sec: n === 1 ? 3600 : null }; });
    await mount();
    await act(async () => { await vi.advanceTimersByTimeAsync(3_599_000); });
    expect(full(calls)).toHaveLength(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(full(calls)).toHaveLength(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(3 * 3600_000); });
    expect(full(calls)).toHaveLength(2);
  });
  it('[C2.4] the pending poll asks ?symbols=<pending> only, every pending_poll_sec, and stops after pending_wait_max_sec', async () => {
    const calls = stubFetch(() => ({ ...clone(fixture), refresh_sec: 0, next_window_sec: null }));
    await mount();
    const poll = (fixture as any).pending_poll_sec as number;
    const max = (fixture as any).pending_wait_max_sec as number;
    await act(async () => { await vi.advanceTimersByTimeAsync(poll * 1000 + 100); });
    const partial = rows(calls);
    expect(partial).toHaveLength(1);
    expect(partial[0].url.endsWith(ggwRowsPath(['AMD']))).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(max * 1000); });
    const n = rows(calls).length;
    expect(n).toBeGreaterThan(3);
    expect(n).toBeLessThanOrEqual(Math.ceil(max / poll));
    await act(async () => { await vi.advanceTimersByTimeAsync(10 * max * 1000); });
    expect(rows(calls).length).toBe(n);
    // NEGATIVE: the poll never re-reads the full board, and never names a loaded row
    expect(full(calls)).toHaveLength(1);
    for (const c of rows(calls)) expect(c.url).not.toContain('OMH');
  });
  it('a pending row that loads is merged in place and the poll stops', async () => {
    const calls = stubFetch(() => ({ ...clone(fixture), refresh_sec: 0, next_window_sec: null }), {
      rows: (syms) => {
        const b = clone(fixture) as any;
        const ready = clone(b.rows[0]);
        ready.symbol = 'AMD';
        b.rows = syms.includes('AMD') ? [ready] : [];
        return b;
      },
    });
    const { container } = await mount();
    await act(async () => { await vi.advanceTimersByTimeAsync(5_100); });
    expect(container.querySelector('[data-testid="ggw-tile-AMD"]')!.getAttribute('data-state')).toBe('ok');
    expect(Array.from(container.querySelectorAll('.ggw-tile')).map((t) => t.getAttribute('data-testid')))
      .toEqual(['ggw-tile-OMH', 'ggw-tile-AMD', 'ggw-tile-XYZQ', 'ggw-tile-NVDA']);
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(rows(calls)).toHaveLength(1);
  });
  it('[C4.5] NEGATIVE: never a /chart-maps/live request', async () => {
    const calls = stubFetch(() => clone(fixture));
    await mount();
    await act(async () => { await vi.advanceTimersByTimeAsync(300_000); });
    expect(calls.some((c) => c.url.includes('/chart-maps/live'))).toBe(false);
  });
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('👀 source guards', () => {
  it('[C4.5] NEGATIVE: GajjalaWatchBoard.tsx imports neither useCardLive nor cardLive', async () => {
    const src = await readSource('src/components/GajjalaWatchBoard.tsx');
    expect(src).not.toMatch(/import[^;]*useCardLive/);
    expect(src).not.toMatch(/from '[^']*cardLive'/);
    expect(src).not.toMatch(/chart-maps\/live/);
  });
  it('NEGATIVE: no email address in any watch source', async () => {
    for (const f of ['src/components/GajjalaWatchBoard.tsx', 'src/lib/gajjalaWatch.ts', 'src/styles/gajjalaWatch.css',
                     'src/components/__fixtures__/gajjala_watch_board_2026_11_15.json']) {
      expect(await readSource(f)).not.toMatch(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/);
    }
  });
  it('NEGATIVE: no "bounce" and no "buy" word on the board source', async () => {
    const src = await readSource('src/components/GajjalaWatchBoard.tsx');
    expect(src).not.toMatch(new RegExp('b' + 'ounce', 'i'));
    expect(src).not.toMatch(/\bbuy\b/i);
  });
});
