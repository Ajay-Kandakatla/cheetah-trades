/* 📅 GgRunChart — the overlay: one GET per open / frame / refresh tick / busy re-ask, the debounce on a ‹ › step, the
 * busy re-ask and ↻, the series and options handed to lightweight-charts, the range rules, focus and keys, the states
 * (2026-11-26, spec runcharts rev 2 §3.7 / §4.2). Ajay: "I wanna able to horizontal scroll tp check continuity like he
 * does".
 *
 * lightweight-charts is mocked (jsdom has no canvas — the ZoneChart.expand.test.tsx way) with spies on the chart, its
 * series and its time scale. Payloads come from the small in-file builder that follows the spec's §3.4 shape. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';

const h = vi.hoisted(() => {
  type Spy = ReturnType<typeof vi.fn>;
  const charts: any[] = [];
  const createChart: Spy = vi.fn((_el: unknown, opts: unknown) => {
    const ts = {
      setVisibleLogicalRange: vi.fn(),
      getVisibleLogicalRange: vi.fn(() => ({ from: 10, to: 30 })),
      fitContent: vi.fn(),
      logicalToCoordinate: vi.fn(() => 0),
    };
    const c: any = { opts, series: [] as any[], ts, removeSeries: vi.fn(), timeScale: () => ts,
      subscribeCrosshairMove: vi.fn(), unsubscribeCrosshairMove: vi.fn(), applyOptions: vi.fn(), remove: vi.fn() };
    const add = (kind: string) => vi.fn((o: unknown) => {
      const s = { kind, opts: o, setData: vi.fn(), applyOptions: vi.fn(), attachPrimitive: vi.fn(),
                  priceScale: () => ({ applyOptions: vi.fn() }) };
      c.series.push(s);
      return s;
    });
    c.addCandlestickSeries = add('candle');
    c.addLineSeries = add('line');
    c.addHistogramSeries = add('hist');
    charts.push(c);
    return c;
  });
  return { charts, createChart };
});

vi.mock('lightweight-charts', () => ({
  ColorType: { Solid: 'solid' },
  CrosshairMode: { Normal: 0 },
  createChart: h.createChart,
}));

import GgRunChart from './GgRunChart';
import { EMA_BOLD, EMA_LINE_W } from '../lib/chartMaps';
import {
  GGRC_BUSY_TRIES, GGRC_CTRL, GGRC_DEBOUNCE_MS, GGRC_FETCH_FAILED, GGRC_VWAP_COLOR, ggrcInitialRange, ggrcPath,
  parseGgrc, type GgrcPayload,
} from '../lib/ggRunChart';

/* ── the §3.4 builder (3 sessions × 6 bars: 2 pre, 2 regular, 2 after) ── */
const DATES = ['2026-11-23', '2026-11-24', '2026-11-25'];
const LABELS = ['Mon 11-23', 'Tue 11-24', 'Wed 11-25'];
const STARTS: [number, number, string | null][] = [[9, 20, 'pre'], [9, 25, 'pre'], [9, 30, null], [9, 35, null],
  [16, 0, 'ah'], [16, 5, 'ah']];
function build(o: { sym?: string; vwap?: boolean; refresh?: number; notes?: any[]; extra?: number } = {}): any {
  const bars: any[] = [], sessions: any[] = [], shade: any[] = [];
  DATES.forEach((d, j) => {
    const [y, m, dd] = d.split('-').map(Number);
    const from = bars.length;
    STARTS.forEach(([hh, mm, s], k) => {
      const c = 1 + j + k * 0.1;
      const b: any = { t: `${d} x`, x: Date.UTC(y, m - 1, dd, hh, mm) / 1000, o: c - 0.05, h: c + 0.1, l: c - 0.1, c, v: 1000 };
      if (s) b.s = s;
      bars.push(b);
    });
    sessions.push({ date: d, label: LABELS[j], from, to: bars.length - 1, half_day: false, ran: false });
    shade.push({ from, to: from + 1, kind: 'pre' }, { from: from + 4, to: from + 5, kind: 'ah' });
  });
  for (let e = 0; e < (o.extra ?? 0); e += 1) {
    const last = bars[bars.length - 1];
    bars.push({ ...last, x: last.x + 300 });
    sessions[2].to = bars.length - 1;
  }
  const curves: any[] = [
    { tone: 'ema9', label: '9 EMA', values: bars.map((b) => b.c) },
    { tone: 'ema21', label: '21 EMA', values: bars.map((b, i) => (i < 3 ? null : b.c)) },
  ];
  if (o.vwap) curves.push({ tone: 'vwap', label: 'VWAP', values: bars.map((b) => b.c) });
  const sym = o.sym ?? 'NXAT';
  return {
    state: 'ok', symbol: sym, tf: '5m', frame_min: 5,
    frames: [{ key: '1m', label: '1-min' }, { key: '5m', label: '5-min' }, { key: '15m', label: '15-min' }],
    title: `📅 ${sym} · 5-min · Mon 11-23 → Wed 11-25`, text: null, notes: o.notes ?? [],
    as_of_text: 'last bar closed Wed 11-25 16:10 ET · read 09:12 ET', live: (o.refresh ?? 0) > 0,
    refresh_sec: o.refresh ?? 0, hint: 'the served hint', words: { pre: 'pre-market', ah: 'after-hours', regular: 'regular hours' },
    ran: null, sessions, bars, curves, vol_avg: { period: 50, label: '50-bar avg volume', values: bars.map(() => 1000) },
    shade, view: { sessions: 2, sessions_phone: 1, right_gap_bars: 12 }, seed: { sessions: 1, bars: 0 }, dropped: 0,
  };
}
const BUSY = { state: 'busy', symbol: 'NXAT', text: 'Still reading NXAT — asking again in 2 s.', retry_sec: 2 };

/* ── fetch: a queue of answers; once exhausted the last repeats ── */
type Ans = { json?: unknown; status?: number; reject?: boolean };
let answers: Ans[] = [];
const fetchMock = vi.fn((_url: string, _init?: RequestInit) => {
  const a = answers.length > 1 ? answers.shift()! : answers[0];
  if (!a || a.reject) return Promise.reject(new Error('down'));
  const status = a.status ?? 200;
  return Promise.resolve({ ok: status < 300, status, json: () => Promise.resolve(a.json) } as Response);
});
const urls = () => fetchMock.mock.calls.map((c) => String(c[0]));
const flush = async () => { await act(async () => { for (let i = 0; i < 12; i += 1) await Promise.resolve(); }); };
const advance = async (ms: number) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); await flush(); };

let vis = 'visible';
beforeEach(() => {
  vi.useFakeTimers();
  h.charts.length = 0;
  h.createChart.mockClear();
  fetchMock.mockClear();
  answers = [{ json: build() }];
  (globalThis as any).fetch = fetchMock;
  (globalThis as any).ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  vis = 'visible';
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => vis });
  document.body.style.overflow = '';
});
afterEach(() => {
  vi.useRealTimers();
  document.body.style.overflow = '';
});

const noop = () => {};
async function open(props: Partial<Parameters<typeof GgRunChart>[0]> = {}) {
  const r = render(<GgRunChart symbol="NXAT" onClose={noop} onStep={null} {...props} />);
  await flush();
  return r;
}
const chart = () => h.charts[h.charts.length - 1];
const lines = (c = chart()) => c.series.filter((s: any) => s.kind === 'line');

describe('fetch on open', () => {
  it('ONE GET to ggrcPath(sym) with credentials, at once (no debounce on the first open)', async () => {
    render(<GgRunChart symbol="NXAT" onClose={noop} onStep={null} />);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(urls()[0].endsWith(ggrcPath('NXAT'))).toBe(true);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'include', cache: 'no-store' });
    await flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe('the chart', () => {
  it('candles get every bar; the EMA series carry EMA_BOLD colours at EMA_LINE_W; drag / touch / wheel / pinch on', async () => {
    await open();
    expect(h.createChart).toHaveBeenCalledTimes(1);
    const c = chart();
    const candle = c.series.find((s: any) => s.kind === 'candle');
    expect(candle.setData.mock.calls[0][0]).toHaveLength(18);
    expect(candle.setData.mock.calls[0][0][0].time).toBe(build().bars[0].x);
    const colors = lines().map((s: any) => s.opts.color);
    expect(colors).toContain(EMA_BOLD.ema9.color);
    expect(colors).toContain(EMA_BOLD.ema21.color);
    for (const s of lines().filter((x: any) => x.opts.color === EMA_BOLD.ema9.color || x.opts.color === EMA_BOLD.ema21.color)) {
      expect(s.opts.lineWidth).toBe(EMA_LINE_W);
    }
    expect(c.opts.handleScroll).toMatchObject({ pressedMouseMove: true, horzTouchDrag: true, mouseWheel: true });
    expect(c.opts.handleScale).toMatchObject({ pinch: true, mouseWheel: true });
    expect(candle.attachPrimitive).toHaveBeenCalledTimes(1);
  });

  it('the first range = ggrcInitialRange', async () => {
    await open();
    const want = ggrcInitialRange(parseGgrc(build()) as GgrcPayload, false);
    expect(chart().ts.setVisibleLogicalRange).toHaveBeenCalledTimes(1);
    expect(chart().ts.setVisibleLogicalRange).toHaveBeenCalledWith(want);
  });

  it('with no VWAP curve exactly three line series (9, 21, volume average); one served → one more per session', async () => {
    const r = await open();
    expect(lines()).toHaveLength(3);
    r.unmount();
    answers = [{ json: build({ vwap: true }) }];
    await open();
    expect(lines()).toHaveLength(6);
    expect(lines().filter((s: any) => s.opts.color === GGRC_VWAP_COLOR)).toHaveLength(3);
  });
});

describe('frame and refresh', () => {
  it('a frame button → a GET with ?tf=1m at once; aria-pressed moves', async () => {
    await open();
    expect(screen.getByTestId('ggrc-tf-5m').getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByTestId('ggrc-tf-1m'));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(urls()[1].endsWith(ggrcPath('NXAT', '1m'))).toBe(true);
    expect(screen.getByTestId('ggrc-tf-1m').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('ggrc-tf-5m').getAttribute('aria-pressed')).toBe('false');
    await flush();
  });

  it('a refresh tick → setData on the SAME series, no second createChart, the range kept', async () => {
    answers = [{ json: build({ refresh: 60 }) }, { json: build({ refresh: 60, extra: 1 }) }];
    await open();
    const c = chart();
    const candle = c.series.find((s: any) => s.kind === 'candle');
    await advance(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(h.createChart).toHaveBeenCalledTimes(1);
    expect(candle.setData).toHaveBeenCalledTimes(2);
    expect(candle.setData.mock.calls[1][0]).toHaveLength(19);
    // the newest bar was in view (to 30 ≥ 17) → both ends follow the one new bar
    expect(c.ts.setVisibleLogicalRange).toHaveBeenLastCalledWith({ from: 11, to: 31 });
  });

  it('NEGATIVE: a refresh tick while panned away keeps his range unchanged', async () => {
    answers = [{ json: build({ refresh: 60 }) }, { json: build({ refresh: 60, extra: 1 }) }];
    await open();
    chart().ts.getVisibleLogicalRange.mockReturnValue({ from: 2, to: 9 });
    await advance(60_000);
    expect(chart().ts.setVisibleLogicalRange).toHaveBeenLastCalledWith({ from: 2, to: 9 });
  });

  it('NEGATIVE: a hidden document → no refetch', async () => {
    answers = [{ json: build({ refresh: 60 }) }];
    await open();
    vis = 'hidden';
    await advance(180_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    vis = 'visible';
    await advance(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('NEGATIVE: not live (refresh_sec 0) → never a second GET', async () => {
    await open();
    await advance(600_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe('keys', () => {
  it('← / → set the panned range; Esc calls onClose', async () => {
    const onClose = vi.fn();
    await open({ onClose });
    const ts = chart().ts;
    fireEvent.keyDown(document.body, { key: 'ArrowLeft' });
    expect(ts.setVisibleLogicalRange).toHaveBeenLastCalledWith({ from: 5, to: 25 });
    fireEvent.keyDown(document.body, { key: 'ArrowRight' });
    expect(ts.setVisibleLogicalRange).toHaveBeenLastCalledWith({ from: 15, to: 35 });
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: a document listener (bubble) does NOT see Escape / ← / → while open, and DOES see "a"', async () => {
    await open();
    const seen: string[] = [];
    const l = (e: KeyboardEvent) => seen.push(e.key);
    document.addEventListener('keydown', l);
    for (const key of ['Escape', 'ArrowLeft', 'ArrowRight', 'a']) fireEvent.keyDown(screen.getByTestId('ggrc'), { key });
    document.removeEventListener('keydown', l);
    expect(seen).toEqual(['a']);
  });

  it('NEGATIVE: arrows typed in an input are not captured', async () => {
    await open();
    const input = document.createElement('input');
    document.body.appendChild(input);
    const seen: string[] = [];
    const l = (e: KeyboardEvent) => seen.push(e.key);
    document.addEventListener('keydown', l);
    const calls = chart().ts.setVisibleLogicalRange.mock.calls.length;
    fireEvent.keyDown(input, { key: 'ArrowLeft' });
    document.removeEventListener('keydown', l);
    input.remove();
    expect(seen).toEqual(['ArrowLeft']);
    expect(chart().ts.setVisibleLogicalRange.mock.calls.length).toBe(calls);
  });
});

describe('debounce on a ‹ › step', () => {
  it('three symbols in a row inside GGRC_DEBOUNCE_MS → ONE GET, for the LAST name; NEGATIVE none for the two stepped past', async () => {
    answers = [{ json: build() }];
    const r = await open({ list: ['NXAT', 'BGLC', 'ALGS', 'TOPP'], onStep: noop });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    for (const sym of ['BGLC', 'ALGS', 'TOPP']) {
      r.rerender(<GgRunChart symbol={sym} list={['NXAT', 'BGLC', 'ALGS', 'TOPP']} onClose={noop} onStep={noop} />);
      await advance(GGRC_DEBOUNCE_MS / 3);
    }
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await advance(GGRC_DEBOUNCE_MS);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(urls()[1].endsWith(ggrcPath('TOPP'))).toBe(true);
    await advance(10_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(urls().some((u) => u.endsWith(ggrcPath('BGLC')) || u.endsWith(ggrcPath('ALGS')))).toBe(false);
  });
});

describe('busy', () => {
  it('a busy first answer → the served text, no chart, ONE GET after retry_sec; then ok → the chart', async () => {
    answers = [{ json: BUSY }, { json: build() }];
    await open();
    expect(screen.getByTestId('ggrc-msg').textContent).toContain(BUSY.text);
    expect(h.createChart).not.toHaveBeenCalled();
    await advance(1_999);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(h.createChart).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: GGRC_BUSY_TRIES busy answers in a row → no further GET, the text + ↻; a click → exactly one GET', async () => {
    answers = [{ json: BUSY }];
    await open();
    for (let i = 1; i < GGRC_BUSY_TRIES; i += 1) await advance(2_000);
    expect(fetchMock).toHaveBeenCalledTimes(GGRC_BUSY_TRIES);
    await advance(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(GGRC_BUSY_TRIES);
    expect(screen.getByTestId('ggrc-msg').textContent).toContain(BUSY.text);
    const retry = screen.getByTestId('ggrc-retry');
    expect(retry.textContent).toBe(GGRC_CTRL.retry);
    answers = [{ json: build() }];
    fireEvent.click(retry);
    await flush();
    expect(fetchMock).toHaveBeenCalledTimes(GGRC_BUSY_TRIES + 1);
    await advance(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(GGRC_BUSY_TRIES + 1);
    expect(h.createChart).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: busy on a RE-read → the chart stays and no extra timer is set', async () => {
    answers = [{ json: build({ refresh: 60 }) }, { json: BUSY }, { json: build({ refresh: 60 }) }];
    await open();
    await advance(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId('ggrc-canvas')).toBeTruthy();
    expect(chart().remove).not.toHaveBeenCalled();
    await advance(10_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);            // no busy re-ask; the next refresh tick asks
    await advance(50_000);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('NEGATIVE: unmount during the wait → no GET', async () => {
    answers = [{ json: BUSY }];
    const r = await open();
    r.unmount();
    await advance(10_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe('focus', () => {
  it('on open the ✕ has focus; on unmount the opener has it again', async () => {
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();
    const r = await open();
    expect(document.activeElement).toBe(screen.getByTestId('ggrc-close'));
    r.unmount();
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });

  it('Tab on the last control → the first; Shift+Tab on the first → the last', async () => {
    await open();
    const close = screen.getByTestId('ggrc-close');
    const first = screen.getByTestId('ggrc-tf-1m');
    close.focus();
    expect(fireEvent.keyDown(close, { key: 'Tab' })).toBe(false);
    expect(document.activeElement).toBe(first);
    expect(fireEvent.keyDown(first, { key: 'Tab', shiftKey: true })).toBe(false);
    expect(document.activeElement).toBe(close);
  });

  it('NEGATIVE: a Tab in the middle of the dialog is not prevented', async () => {
    await open();
    const mid = screen.getByTestId('ggrc-all');
    mid.focus();
    expect(fireEvent.keyDown(mid, { key: 'Tab' })).toBe(true);
    expect(document.activeElement).toBe(mid);
  });

  it('NEGATIVE: the opener removed from the document meanwhile → no throw, focus not forced', async () => {
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();
    const r = await open();
    opener.remove();
    expect(() => r.unmount()).not.toThrow();
    expect(document.activeElement).not.toBe(opener);
  });
});

describe('controls', () => {
  it('NEGATIVE: ‹ › absent with onStep null', async () => {
    await open();
    expect(screen.queryByTestId('ggrc-prev-sym')).toBeNull();
    expect(screen.queryByTestId('ggrc-next-sym')).toBeNull();
  });

  it('‹ › disabled at the ends of list, and they call onStep', async () => {
    const onStep = vi.fn();
    const r = await open({ list: ['NXAT', 'BGLC'], onStep });
    expect((screen.getByTestId('ggrc-prev-sym') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId('ggrc-next-sym') as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByTestId('ggrc-next-sym'));
    expect(onStep).toHaveBeenCalledWith(1);
    r.rerender(<GgRunChart symbol="BGLC" list={['NXAT', 'BGLC']} onClose={noop} onStep={onStep} />);
    expect((screen.getByTestId('ggrc-prev-sym') as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByTestId('ggrc-next-sym') as HTMLButtonElement).disabled).toBe(true);
  });

  it('NEGATIVE: a backdrop click does not close; ✕ does', async () => {
    const onClose = vi.fn();
    await open({ onClose });
    fireEvent.click(screen.getByTestId('ggrc'));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('ggrc-close'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('notes sit outside the closed <details>; the hint inside it', async () => {
    answers = [{ json: build({ notes: [{ kind: 'failed', text: 'Fri 11-20 could not be read — not drawn; reopen to try again' }] }) }];
    await open();
    const details = screen.getByTestId('ggrc-hint') as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(details.textContent).toContain('the served hint');
    const notes = screen.getByTestId('ggrc-notes');
    expect(notes.textContent).toContain('could not be read');
    expect(details.contains(notes)).toBe(false);
  });

  it('body overflow is hidden while open and restored on unmount', async () => {
    document.body.style.overflow = 'scroll';
    const r = await open();
    expect(document.body.style.overflow).toBe('hidden');
    r.unmount();
    expect(document.body.style.overflow).toBe('scroll');
  });
});

describe('states', () => {
  it('NEGATIVE: empty / bad_symbol → the served text and createChart never called', async () => {
    answers = [{ json: { state: 'empty', symbol: 'NXAT', text: 'No bars for NXAT in the last 5 sessions (a → b).' } }];
    const r = await open();
    expect(screen.getByTestId('ggrc-msg').textContent).toContain('No bars for NXAT');
    expect(screen.queryByTestId('ggrc-retry')).toBeNull();
    r.unmount();
    answers = [{ json: { state: 'bad_symbol', text: 'Not a ticker' } }];
    await open();
    expect(screen.getByTestId('ggrc-msg').textContent).toContain('Not a ticker');
    expect(h.createChart).not.toHaveBeenCalled();
  });

  it('NEGATIVE: error → the served text + the retry button, no chart; the button asks once', async () => {
    answers = [{ json: { state: 'error', symbol: 'NXAT', text: 'The bars for NXAT could not be read — the 1-minute feed did not answer.' } }];
    await open();
    expect(screen.getByTestId('ggrc-msg').textContent).toContain('did not answer');
    expect(h.createChart).not.toHaveBeenCalled();
    answers = [{ json: build() }];
    fireEvent.click(screen.getByTestId('ggrc-retry'));
    await flush();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(h.createChart).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: owner_only / garbage / HTTP 500 / a network fault on the first read → GGRC_FETCH_FAILED + the retry button', async () => {
    for (const a of [{ json: { state: 'owner_only' } }, { json: 'nonsense' }, { json: { state: 'ok', bars: [{ x: 1 }] } },
                     { status: 500 }, { reject: true }] as Ans[]) {
      answers = [a];
      const r = await open();
      expect(screen.getByTestId('ggrc-msg').textContent).toContain(GGRC_FETCH_FAILED);
      expect(screen.getByTestId('ggrc-retry')).toBeTruthy();
      r.unmount();
    }
    expect(h.createChart).not.toHaveBeenCalled();
  });

  it('NEGATIVE: a failed RE-read keeps the chart', async () => {
    answers = [{ json: build({ refresh: 60 }) }, { status: 500 }, { reject: true }, { json: 'nonsense' }];
    await open();
    for (let i = 0; i < 3; i += 1) {
      await advance(60_000);
      expect(screen.getByTestId('ggrc-canvas')).toBeTruthy();
      expect(screen.queryByTestId('ggrc-msg')).toBeNull();
    }
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(h.createChart).toHaveBeenCalledTimes(1);
    expect(chart().remove).not.toHaveBeenCalled();
  });
});
