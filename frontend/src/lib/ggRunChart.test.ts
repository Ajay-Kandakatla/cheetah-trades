/* 📅 lib/ggRunChart — parse, shaping, ranges, geometry, hover, busy re-ask, the open store, source guards
 * (2026-11-26, spec runcharts rev 2 §3.6 / §4.2). Ajay: "I wanna able to horizontal scroll tp check continuity like he
 * does". Payloads are built by the small in-file builder below, which follows the spec's §3.4 shape exactly (the golden
 * is be-chart's and is checked by fe-mount). */
import { describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import {
  GG_RUNCHART_PATH, GGRC_BUSY_TRIES, GGRC_DOWN, GGRC_KEY_PAN_FRAC, GGRC_UP, GGRC_VWAP_COLOR,
  closeGgRunChart, ggrcBusyDelayMs, ggrcCandles, ggrcHover, ggrcInitialRange, ggrcKeepRange, ggrcLine, ggrcPan,
  ggrcPath, ggrcPrecision, ggrcSeparators, ggrcShadeRects, ggrcStepSession, ggrcVolAvg, ggrcVolume,
  ggrcVwapSegments, openGgRunChart, parseGgrc, stepGgRunChart, useGgRunChartOpen,
  type GgrcPayload,
} from './ggRunChart';
import { pxText } from './chartMaps';
import { volumeColor } from './volumePane';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

/* ── the §3.4 builder: per session 2 pre bars (09:20, 09:25), 2 regular (09:30, 09:35), 2 after (16:00, 16:05) ── */
const STARTS: [number, number, 'pre' | 'ah' | null][] = [[9, 20, 'pre'], [9, 25, 'pre'], [9, 30, null], [9, 35, null],
  [16, 0, 'ah'], [16, 5, 'ah']];
const DATES = ['2026-11-23', '2026-11-24', '2026-11-25'];
const LABELS = ['Mon 11-23', 'Tue 11-24', 'Wed 11-25'];
const pad = (n: number) => String(n).padStart(2, '0');

function build(nSessions = 3, opts: { vwap?: boolean } = {}): Record<string, any> {
  const bars: any[] = [], sessions: any[] = [], shade: any[] = [];
  for (let d = 0; d < nSessions; d += 1) {
    const [y, m, dd] = DATES[d].split('-').map(Number);
    const from = bars.length;
    STARTS.forEach(([hh, mm, s], k) => {
      const x = Date.UTC(y, m - 1, dd, hh, mm) / 1000;
      const end = new Date((x + 300) * 1000);
      const t = `${DATES[d]} ${pad(end.getUTCHours())}:${pad(end.getUTCMinutes())}`;
      const c = 1 + d + k * 0.1;
      const bar: any = { t, x, o: c - 0.05, h: c + 0.1, l: c - 0.1, c, v: 1000 * (k + 1) };
      if (k === 1) bar.o = c + 0.05;              // one red bar per session
      if (s) bar.s = s;
      bars.push(bar);
    });
    sessions.push({ date: DATES[d], label: LABELS[d], from, to: bars.length - 1, half_day: false, ran: d === nSessions - 1 });
    shade.push({ from, to: from + 1, kind: 'pre' }, { from: from + 4, to: from + 5, kind: 'ah' });
  }
  const curves: any[] = [
    { tone: 'ema9', label: '9 EMA', values: bars.map((b, i) => (i < 2 ? null : b.c)) },
    { tone: 'ema21', label: '21 EMA', values: bars.map((b, i) => (i < 4 ? null : b.c - 0.01)) },
  ];
  if (opts.vwap) curves.push({ tone: 'vwap', label: 'VWAP', values: bars.map((b) => b.c + 0.02) });
  return {
    state: 'ok', symbol: 'BGLC', tf: '5m', frame_min: 5,
    frames: [{ key: '1m', label: '1-min' }, { key: '5m', label: '5-min' }, { key: '15m', label: '15-min' }],
    title: `📅 BGLC · 5-min · ${LABELS[0]} → ${LABELS[nSessions - 1]}`, text: null, notes: [],
    as_of_text: 'last bar closed Wed 11-25 16:10 ET · read 09:12 ET', as_of_bar_t: 'x',
    live: false, refresh_sec: 0, hint: 'hint words',
    words: { pre: 'pre-market', ah: 'after-hours', regular: 'regular hours' },
    ran: { date: DATES[nSessions - 1], text: '📅 ran Wed +176%', title: 'ran title' },
    sessions, bars, curves,
    vol_avg: { period: 50, label: '50-bar avg volume', values: bars.map((_, i) => (i < 3 ? null : 2000)) },
    shade, view: { sessions: 2, sessions_phone: 1, right_gap_bars: 12 }, seed: { sessions: 1, bars: 192 }, dropped: 0,
  };
}
const ok = (raw = build()): GgrcPayload => parseGgrc(raw) as GgrcPayload;

describe('parseGgrc', () => {
  it('parses a good payload, every bar and list kept', () => {
    const p = ok();
    expect(p.state).toBe('ok');
    expect(p.bars).toHaveLength(18);
    expect(p.sessions).toHaveLength(3);
    expect(p.shade).toHaveLength(6);
    expect(p.curves.map((c) => c.tone)).toEqual(['ema9', 'ema21']);
    expect(p.vol_avg?.values).toHaveLength(18);
    expect(p.bars[0].s).toBe('pre');
    expect(p.bars[2].s).toBeNull();
    expect(p.view).toEqual({ sessions: 2, sessions_phone: 1, right_gap_bars: 12 });
    expect(p.retry_sec).toBe(0);
    expect(p.ran?.text).toBe('📅 ran Wed +176%');
  });

  it('NEGATIVE: null, an array, a string, an unknown state → null', () => {
    expect(parseGgrc(null)).toBeNull();
    expect(parseGgrc([build()])).toBeNull();
    expect(parseGgrc('ok')).toBeNull();
    expect(parseGgrc({ ...build(), state: 'fine' })).toBeNull();
    expect(parseGgrc({ ...build(), state: undefined })).toBeNull();
  });

  it('NEGATIVE: NaN or Infinity anywhere → null', () => {
    const a = build(); a.bars[3].v = NaN; expect(parseGgrc(a)).toBeNull();
    const b = build(); b.curves[0].values[5] = Infinity; expect(parseGgrc(b)).toBeNull();
    const c = build(); c.refresh_sec = NaN; expect(parseGgrc(c)).toBeNull();
    const d = build(); d.seed.bars = -Infinity; expect(parseGgrc(d)).toBeNull();
    const e = build(); e.vol_avg.values[4] = NaN; expect(parseGgrc(e)).toBeNull();
  });

  it('NEGATIVE: a bar without x, a fractional x, a price ≤ 0, a negative volume, a non-string t → null', () => {
    const a = build(); delete a.bars[2].x; expect(parseGgrc(a)).toBeNull();
    const b = build(); b.bars[2].x += 0.5; expect(parseGgrc(b)).toBeNull();
    const c = build(); c.bars[2].l = 0; expect(parseGgrc(c)).toBeNull();
    const d = build(); d.bars[2].o = -1; expect(parseGgrc(d)).toBeNull();
    const e = build(); e.bars[2].v = -1; expect(parseGgrc(e)).toBeNull();
    const f = build(); f.bars[2].t = 5; expect(parseGgrc(f)).toBeNull();
  });

  it('NEGATIVE: x equal or decreasing → null (never a re-sorted or shifted chart)', () => {
    const a = build(); a.bars[4].x = a.bars[3].x; expect(parseGgrc(a)).toBeNull();
    const b = build(); b.bars[4].x = a.bars[3].x - 60; expect(parseGgrc(b)).toBeNull();
  });

  it('a curve of the wrong length is dropped, the bars kept', () => {
    const a = build(); a.curves[1].values.pop();
    const p = ok(a);
    expect(p.bars).toHaveLength(18);
    expect(p.curves.map((c) => c.tone)).toEqual(['ema9']);
  });

  it('a mismatched vol_avg → vol_avg null, the rest kept', () => {
    const a = build(); a.vol_avg.values.push(1);
    const p = ok(a);
    expect(p.vol_avg).toBeNull();
    expect(p.bars).toHaveLength(18);
  });

  it('NEGATIVE: shade / session indexes out of range, fractional or reversed → that entry dropped', () => {
    const a = build();
    a.sessions[0].to = 99; a.sessions[1].from = 1.5;
    a.shade[0] = { from: 5, to: 4, kind: 'pre' }; a.shade[1] = { from: -1, to: 2, kind: 'ah' };
    a.shade[2] = { from: 6, to: 7, kind: 'mid' };
    const p = ok(a);
    expect(p.sessions.map((s) => s.date)).toEqual(['2026-11-25']);
    expect(p.shade).toHaveLength(3);
  });

  it('NEGATIVE: an unknown tone → dropped', () => {
    const a = build(); a.curves[0].tone = 'sma50';
    expect(ok(a).curves.map((c) => c.tone)).toEqual(['ema21']);
  });

  it('owner_only parses with empty lists', () => {
    const p = parseGgrc({ state: 'owner_only' }) as GgrcPayload;
    expect(p.state).toBe('owner_only');
    expect(p.bars).toEqual([]);
    expect(p.sessions).toEqual([]);
    expect(p.curves).toEqual([]);
    expect(p.shade).toEqual([]);
    expect(p.vol_avg).toBeNull();
  });

  it('busy parses with its retry_sec; NEGATIVE a negative or non-number retry_sec → null', () => {
    const p = parseGgrc({ state: 'busy', symbol: 'NXAT', text: 'Still reading NXAT — asking again in 2 s.', retry_sec: 2 });
    expect(p?.state).toBe('busy');
    expect(p?.retry_sec).toBe(2);
    expect(p?.text).toBe('Still reading NXAT — asking again in 2 s.');
    expect(parseGgrc({ state: 'busy', retry_sec: -1 })).toBeNull();
    expect(parseGgrc({ state: 'busy', retry_sec: '2' })).toBeNull();
  });
});

describe('shaping', () => {
  it('time = x on every series', () => {
    const p = ok(build(3, { vwap: true }));
    const xs = p.bars.map((b) => b.x);
    expect(ggrcCandles(p).map((c) => c.time)).toEqual(xs);
    expect(ggrcVolume(p).map((c) => c.time)).toEqual(xs);
    expect(ggrcCandles(p)[0]).toEqual({ time: xs[0], open: p.bars[0].o, high: p.bars[0].h, low: p.bars[0].l, close: p.bars[0].c });
  });

  it('volume colours are volumePane.volumeColor', () => {
    const p = ok();
    ggrcVolume(p).forEach((v, i) => expect(v.color).toBe(volumeColor(p.bars[i].o, p.bars[i].c)));
    expect(new Set(ggrcVolume(p).map((v) => v.color)).size).toBe(2);
  });

  it('ggrcLine omits nulls and keeps the served values', () => {
    const p = ok();
    const e21 = ggrcLine(p, 'ema21');
    expect(e21).toHaveLength(14);
    expect(e21[0]).toEqual({ time: p.bars[4].x, value: p.curves[1].values[4] });
    expect(ggrcLine(p, 'vwap')).toEqual([]);
    expect(ggrcVolAvg(p)).toHaveLength(15);
  });

  it('ggrcVwapSegments: one array per session, never joined across the overnight', () => {
    const p = ok(build(3, { vwap: true }));
    const segs = ggrcVwapSegments(p);
    expect(segs).toHaveLength(3);
    segs.forEach((seg, j) => {
      expect(seg).toHaveLength(6);
      expect(seg[0].time).toBe(p.bars[p.sessions[j].from].x);
      expect(seg[seg.length - 1].time).toBe(p.bars[p.sessions[j].to].x);
    });
    expect(ggrcVwapSegments(ok())).toEqual([]);
  });

  it('ggrcPrecision agrees with pxText', () => {
    for (const px of [0.4123, 1, 12.5]) {
      const dp = (pxText(px) as string).split('.')[1].length;
      expect(ggrcPrecision(px).precision).toBe(dp);
      expect(ggrcPrecision(px).minMove).toBeCloseTo(10 ** -dp, 12);
    }
    expect(ggrcPrecision(0.4123).precision).toBe(3);
    expect(ggrcPrecision(12.5).precision).toBe(2);
  });
});

describe('ranges', () => {
  it('initial: the last view.sessions on a desktop, view.sessions_phone on the phone, + the right gap', () => {
    const p = ok();
    expect(ggrcInitialRange(p, false)).toEqual({ from: 6 - 0.5, to: 17 + 12 });
    expect(ggrcInitialRange(p, true)).toEqual({ from: 12 - 0.5, to: 17 + 12 });
  });

  it('initial: one session only → from that session; no session → null', () => {
    const one = ok(build(1));
    expect(ggrcInitialRange(one, false)).toEqual({ from: -0.5, to: 5 + 12 });
    const none = ok({ ...build(), sessions: [] });
    expect(ggrcInitialRange(none, false)).toBeNull();
    expect(ggrcInitialRange(ok({ ...build(), view: undefined }), false)).toBeNull();
  });

  it('keep: at the edge both ends shift; panned away stays; null stays null', () => {
    expect(ggrcKeepRange({ from: 10, to: 29 }, 18, 19)).toEqual({ from: 11, to: 30 });
    expect(ggrcKeepRange({ from: 5, to: 17 }, 18, 20)).toEqual({ from: 7, to: 19 });
    expect(ggrcKeepRange({ from: 2, to: 9 }, 18, 19)).toEqual({ from: 2, to: 9 });
    expect(ggrcKeepRange(null, 18, 19)).toBeNull();
  });

  it('pan: a quarter of the width each way', () => {
    expect(GGRC_KEY_PAN_FRAC).toBe(0.25);
    expect(ggrcPan({ from: 10, to: 30 }, -1)).toEqual({ from: 5, to: 25 });
    expect(ggrcPan({ from: 10, to: 30 }, 1)).toEqual({ from: 15, to: 35 });
    expect(ggrcPan({ from: 10, to: 30 }, 1, 0.5)).toEqual({ from: 20, to: 40 });
  });

  it('step a session both ways, the width kept; at both ends unchanged', () => {
    const s = ok().sessions;
    expect(ggrcStepSession({ from: 5.5, to: 20 }, s, 1)).toEqual({ from: 11.5, to: 26 });
    expect(ggrcStepSession({ from: 5.5, to: 20 }, s, -1)).toEqual({ from: -0.5, to: 14 });
    expect(ggrcStepSession({ from: 8, to: 20 }, s, -1)).toEqual({ from: 5.5, to: 17.5 });
    expect(ggrcStepSession({ from: -0.5, to: 10 }, s, -1)).toEqual({ from: -0.5, to: 10 });
    expect(ggrcStepSession({ from: 11.5, to: 20 }, s, 1)).toEqual({ from: 11.5, to: 20 });
    expect(ggrcStepSession({ from: 1, to: 2 }, [], 1)).toEqual({ from: 1, to: 2 });
  });
});

describe('geometry', () => {
  const toX = (i: number) => i * 10;   // a fake linear time scale: bar i at x = 10 i

  it('shade: one rect per run, clipped at both edges', () => {
    const r = ggrcShadeRects([{ from: 0, to: 1, kind: 'pre' }, { from: 10, to: 20, kind: 'ah' }], toX, 120);
    expect(r).toEqual([{ x: 0, w: 15, kind: 'pre' }, { x: 95, w: 25, kind: 'ah' }]);
  });

  it('NEGATIVE shade: a null coordinate skipped, zero width skipped, fully off-screen skipped', () => {
    const nul = (i: number) => (i > 5 ? null : i * 10);
    expect(ggrcShadeRects([{ from: 4, to: 8, kind: 'pre' }], nul, 200)).toEqual([]);
    expect(ggrcShadeRects([{ from: 0, to: 1, kind: 'pre' }], toX, 0)).toEqual([]);
    expect(ggrcShadeRects([{ from: 30, to: 31, kind: 'ah' }], toX, 120)).toEqual([]);
  });

  it('separators: the first has no line; the session over the left edge keeps its label at x = 0', () => {
    const s = ok().sessions;   // 0..5, 6..11, 12..17
    const shift = (i: number) => i * 10 - 30;
    const m = ggrcSeparators(s, shift, 500);
    expect(m).toEqual([
      { x: 0, line: false, label: 'Mon 11-23' },
      { x: 25, line: true, label: 'Tue 11-24' },
      { x: 85, line: true, label: 'Wed 11-25' },
    ]);
    const m2 = ggrcSeparators(s, toX, 500);
    expect(m2[0]).toEqual({ x: 0, line: false, label: 'Mon 11-23' });
  });

  it('NEGATIVE separators: off-screen and null sessions skipped', () => {
    const s = ok().sessions;
    const far = (i: number) => i * 10 - 120;   // sessions 0 and 1 end left of 0
    expect(ggrcSeparators(s, far, 500).map((m) => m.label)).toEqual(['Wed 11-25']);
    expect(ggrcSeparators(s, toX, 100).map((m) => m.label)).toEqual(['Mon 11-23', 'Tue 11-24']);
    expect(ggrcSeparators(s, () => null, 500)).toEqual([]);
  });
});

describe('hover', () => {
  it("`when` is the bar's START read with UTC getters — a bar whose t is '… 20:00' at 5-min reads 19:55", () => {
    const raw = build(1);
    const x = Date.UTC(2026, 10, 23, 19, 55) / 1000;
    raw.bars[5] = { ...raw.bars[5], t: '2026-11-23 20:00', x, s: 'ah' };
    const h = ggrcHover(ok(raw), 5);
    expect(h?.when).toBe('Mon 11-23 · 19:55');
    expect(h?.session).toBe('after-hours');
  });

  it('the served session word; prices via pxText; change against the prior close', () => {
    const p = ok();
    const pre = ggrcHover(p, 0)!;
    expect(pre.session).toBe('pre-market');
    expect(pre.when).toBe('Mon 11-23 · 09:20');
    const reg = ggrcHover(p, 2)!;
    expect(reg.session).toBe('regular hours');
    expect(reg.close).toBe(pxText(p.bars[2].c));
    expect(reg.changePct).toMatch(/^\+\d+\.\d\d%$/);
    expect(reg.ema9).toBe(pxText(p.curves[0].values[2]));
    expect(reg.ema21).toBeNull();
    expect(reg.volume).toBe('3K');
  });

  it('NEGATIVE: no prior bar → no change; an index off the bars → null', () => {
    const p = ok();
    expect(ggrcHover(p, 0)?.changePct).toBeNull();
    expect(ggrcHover(p, -1)).toBeNull();
    expect(ggrcHover(p, 18)).toBeNull();
    expect(ggrcHover(null, 0)).toBeNull();
  });
});

describe('ggrcBusyDelayMs', () => {
  const busy = parseGgrc({ state: 'busy', retry_sec: 2 });
  it('busy + tries 0 → retry_sec × 1000', () => {
    expect(ggrcBusyDelayMs(busy, 0)).toBe(2000);
    expect(ggrcBusyDelayMs(busy, GGRC_BUSY_TRIES - 1)).toBe(2000);
  });
  it('NEGATIVES: tries = GGRC_BUSY_TRIES → null; retry_sec 0 → null; state ok → null; null → null', () => {
    expect(ggrcBusyDelayMs(busy, GGRC_BUSY_TRIES)).toBeNull();
    expect(ggrcBusyDelayMs(parseGgrc({ state: 'busy', retry_sec: 0 }), 0)).toBeNull();
    expect(ggrcBusyDelayMs(parseGgrc({ state: 'busy' }), 0)).toBeNull();
    expect(ggrcBusyDelayMs(ok(), 0)).toBeNull();
    expect(ggrcBusyDelayMs(null, 0)).toBeNull();
  });
});

describe('the open store', () => {
  it('open / step clamped at both ends / close, subscribers told', () => {
    const { result } = renderHook(() => useGgRunChartOpen());
    expect(result.current).toBeNull();
    act(() => openGgRunChart('NXAT', ['BGLC', 'NXAT', 'ALGS']));
    expect(result.current).toEqual({ symbol: 'NXAT', list: ['BGLC', 'NXAT', 'ALGS'] });
    act(() => stepGgRunChart(1));
    expect(result.current?.symbol).toBe('ALGS');
    act(() => stepGgRunChart(1));
    expect(result.current?.symbol).toBe('ALGS');            // no wrap
    act(() => { stepGgRunChart(-1); stepGgRunChart(-1); stepGgRunChart(-1); });
    expect(result.current?.symbol).toBe('BGLC');             // clamped
    act(() => closeGgRunChart());
    expect(result.current).toBeNull();
  });

  it('NEGATIVE: an empty symbol opens nothing; a list without the symbol → the symbol alone; step while closed → nothing', () => {
    const { result } = renderHook(() => useGgRunChartOpen());
    act(() => openGgRunChart(''));
    expect(result.current).toBeNull();
    act(() => stepGgRunChart(1));
    expect(result.current).toBeNull();
    act(() => openGgRunChart('MEDS', ['BGLC']));
    expect(result.current).toEqual({ symbol: 'MEDS', list: ['MEDS'] });
    act(() => openGgRunChart('MEDS'));
    expect(result.current).toEqual({ symbol: 'MEDS', list: ['MEDS'] });
    act(() => closeGgRunChart());
  });

  it('a subscriber is told exactly once per change and not after unmount', () => {
    let renders = 0;
    const { unmount } = renderHook(() => { renders += 1; return useGgRunChartOpen(); });
    const base = renders;
    act(() => openGgRunChart('A', ['A', 'B']));
    expect(renders).toBe(base + 1);
    act(() => stepGgRunChart(-1));                           // clamped: no change, no render
    expect(renders).toBe(base + 1);
    unmount();
    const spy = vi.fn();
    act(() => { closeGgRunChart(); spy(); });
    expect(renders).toBe(base + 1);
  });
});

describe('ggrcPath', () => {
  it('upper-cased, encoded, ?tf= only when given', () => {
    expect(GG_RUNCHART_PATH).toBe('/chart-maps/gajjala-watch/runners/chart');
    expect(ggrcPath('nxat')).toBe('/chart-maps/gajjala-watch/runners/chart/NXAT');
    expect(ggrcPath('brk/b')).toBe('/chart-maps/gajjala-watch/runners/chart/BRK%2FB');
    expect(ggrcPath('NXAT', '1m')).toBe('/chart-maps/gajjala-watch/runners/chart/NXAT?tf=1m');
    expect(ggrcPath('NXAT', null)).toBe('/chart-maps/gajjala-watch/runners/chart/NXAT');
    expect(ggrcPath('NXAT', '')).toBe('/chart-maps/gajjala-watch/runners/chart/NXAT');
  });
});

describe('source guards', () => {
  it('the lib holds no matchMedia(, no EventSource, no bounce, no @; no host-mount or glyph export', async () => {
    const src = await readSource('src/lib/ggRunChart.ts');
    expect(src).not.toContain('matchMedia(');
    expect(src).not.toContain('EventSource');
    // the word, not a substring: the spec's own identifier GGRC_DEBOUNCE_MS holds the letters (an internal name)
    expect(src).not.toMatch(/\bbounce/i);
    expect(src.replace(/GGRC_DEBOUNCE_MS/g, '')).not.toMatch(/bounce/i);
    expect(src).not.toContain('@');
    expect(src).not.toMatch(/export[^\n]*ggrcHostMount/);
    expect(src).not.toMatch(/export[^\n]*useGgRunChartHost/);
    expect(src).not.toMatch(/export[^\n]*GGRC_GLYPH/);
  });

  it("GGRC_VWAP_COLOR is the hex on chartMaps.ts's vwap tone line", async () => {
    const src = await readSource('src/lib/chartMaps.ts');
    const m = src.match(/tone === 'vwap'\) return 'var\(--info, (#[0-9a-fA-F]{6})\)'/);
    expect(m).not.toBeNull();
    expect(GGRC_VWAP_COLOR).toBe(m![1]);
  });

  it("GGRC_UP / GGRC_DOWN equal LiveCandlesChart's", async () => {
    const src = await readSource('src/components/LiveCandlesChart.tsx');
    expect(src).toContain(`const UP = '${GGRC_UP}';`);
    expect(src).toContain(`const DOWN = '${GGRC_DOWN}';`);
  });
});
