/**
 * ⏰ GgTimeWindow (2026-11-24). Ajay 2026-11-24, verbatim: "can you add a reminder of that somwhere for me like radiating
 * when we enter those timings". The line glows ONLY while the ET clock is inside a served window; nothing at 10:30 /
 * 10:31 / 14:59 / 17:01, nothing on a closed day, a fault, a failed GET or a stale date; reduced motion = static (no
 * animation); the FE types no digit or served word (source guards); 📱 430 px rules are CSS source guards (jsdom has no
 * layout). The fixture is a HAND copy of the served shape — test data only.
 */
import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgTimeWindow } from './GgTimeWindow';
import { activeWindow, etMinutes, hhmmMinutes, type GgTimeWindows } from '../lib/ggTimeWindows';
import { TICK_MS } from '../hooks/useGgTimeWindows';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const W1_TEXT = 'W1 SERVED TEXT — test words';
const W2_TEXT = 'W2 SERVED TEXT — test words';
const SRC = 'SOURCE LINE — test words';
const BLOCK: GgTimeWindows = {
  kind: 'gajjala_time_windows', date: '2026-11-24', closed: false, closed_reason: null, half_day: false, state: 'ok',
  windows: [
    { key: 'burst_window', start: '09:30', end: '10:30', label: 'L1', text: W1_TEXT },
    { key: 'second_wave', start: '15:00', end: '17:00', label: 'L2', text: W2_TEXT },
  ],
  note: null, source_text: SRC, fault_text: null,
};
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

/** 2026-11-24 is EST (UTC−5): ET hh:mm → the UTC instant. */
const et = (hhmm: string, day = '2026-11-24') => {
  const [h, m] = hhmm.split(':').map(Number);
  const [y, mo, d] = day.split('-').map(Number);
  return new Date(Date.UTC(y, mo - 1, d, h + 5, m, 0));
};

let fetchMock: ReturnType<typeof vi.fn>;
function serve(body: unknown, ok = true) {
  fetchMock = vi.fn(() => Promise.resolve({ ok, json: () => Promise.resolve(body) }));
  vi.stubGlobal('fetch', fetchMock);
}
async function flush() {
  await act(async () => { for (let i = 0; i < 5; i++) await Promise.resolve(); });
}
async function mountAt(hhmm: string, body: unknown = BLOCK, props: { enabled?: boolean } = {}, day?: string) {
  vi.setSystemTime(et(hhmm, day));
  serve(body);
  render(<GgTimeWindow {...props} />);
  await flush();
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] });
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('GgTimeWindow — glows inside a served window only', () => {
  it('inside W1 (09:45 ET): the served text + source line, glowing', async () => {
    await mountAt('09:45');
    const el = screen.getByTestId('gg-time-window');
    expect(el).toHaveAttribute('data-window', 'burst_window');
    expect(el).toHaveClass('gg-tw-glow');
    expect(el).toHaveAttribute('data-motion', 'glow');
    expect(screen.getByTestId('gg-time-window-text')).toHaveTextContent(W1_TEXT);
    expect(screen.getByTestId('gg-time-window-src')).toHaveTextContent(SRC);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/chart-maps\/gajjala\/time-windows$/);
  });

  it('inside W2 (16:30 ET) and at its first minute (15:00)', async () => {
    await mountAt('16:30');
    expect(screen.getByTestId('gg-time-window')).toHaveAttribute('data-window', 'second_wave');
    expect(screen.getByTestId('gg-time-window-text')).toHaveTextContent(W2_TEXT);
  });

  it.each(['10:30', '10:31', '14:59', '17:00', '17:01', '09:29'])('NEGATIVE: nothing at %s ET', async (t) => {
    await mountAt(t);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('gg-time-window')).toBeNull();
  });

  it('the 30 s tick turns the glow on at 15:00 and off at 17:00 — no extra GET', async () => {
    await mountAt('14:59');
    expect(screen.queryByTestId('gg-time-window')).toBeNull();
    await act(async () => { vi.advanceTimersByTime(2 * TICK_MS); });
    expect(screen.getByTestId('gg-time-window')).toHaveAttribute('data-window', 'second_wave');
    await act(async () => { vi.setSystemTime(et('17:00')); vi.advanceTimersByTime(TICK_MS); });
    expect(screen.queryByTestId('gg-time-window')).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('the ET date rollover re-reads the route once', async () => {
    await mountAt('23:59');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await act(async () => { vi.advanceTimersByTime(2 * TICK_MS); });
    await flush();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe('GgTimeWindow — NEGATIVES: nothing renders', () => {
  it('closed day (closed: true) inside W1', async () => {
    await mountAt('09:45', { ...clone(BLOCK), closed: true, closed_reason: 'weekend' });
    expect(screen.queryByTestId('gg-time-window')).toBeNull();
  });

  it('a fault block', async () => {
    await mountAt('09:45', { ...clone(BLOCK), state: 'fault', windows: [], source_text: null, fault_text: 'x' });
    expect(screen.queryByTestId('gg-time-window')).toBeNull();
  });

  it('an HTTP error and a rejected GET', async () => {
    vi.setSystemTime(et('09:45'));
    serve(BLOCK, false);
    render(<GgTimeWindow />);
    await flush();
    expect(screen.queryByTestId('gg-time-window')).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('down'))));
    render(<GgTimeWindow />);
    await flush();
    expect(screen.queryByTestId('gg-time-window')).toBeNull();
  });

  it('a block for another ET date (stale)', async () => {
    await mountAt('09:45', { ...clone(BLOCK), date: '2026-11-23' });
    expect(screen.queryByTestId('gg-time-window')).toBeNull();
  });

  it('enabled=false (the 1-minute page / Luk) never fetches', async () => {
    await mountAt('09:45', BLOCK, { enabled: false });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.queryByTestId('gg-time-window')).toBeNull();
  });
});

describe('GgTimeWindow — reduced motion', () => {
  it('prefers-reduced-motion → static highlight, no glow class', async () => {
    vi.stubGlobal('matchMedia', vi.fn((q: string) => ({ matches: q.includes('reduce'), media: q })));
    await mountAt('09:45');
    const el = screen.getByTestId('gg-time-window');
    expect(el).toHaveClass('gg-tw-static');
    expect(el).not.toHaveClass('gg-tw-glow');
    expect(el).toHaveAttribute('data-motion', 'reduce');
  });

  it('NEGATIVE: motion allowed → glow class', async () => {
    vi.stubGlobal('matchMedia', vi.fn((q: string) => ({ matches: false, media: q })));
    await mountAt('09:45');
    expect(screen.getByTestId('gg-time-window')).toHaveClass('gg-tw-glow');
  });
});

describe('ggTimeWindows lib', () => {
  it('etMinutes reads the ET clock (EST and EDT)', () => {
    expect(etMinutes(et('09:45'))).toBe(hhmmMinutes('09:45'));
    expect(etMinutes(new Date(Date.UTC(2026, 6, 1, 13, 30)))).toBe(hhmmMinutes('09:30'));   // EDT: UTC−4
  });
  it('NEGATIVE: malformed served windows never match', () => {
    const b = { ...clone(BLOCK), windows: [{ key: 'x', start: '9:30', end: '10:30', label: '', text: 'x' },
      { key: 'y', start: '09:30', end: '10:30', label: '', text: '  ' }] };
    expect(activeWindow(b, et('09:45'))).toBeNull();
    expect(activeWindow(null, et('09:45'))).toBeNull();
    expect(activeWindow(clone(BLOCK), et('09:45'))?.key).toBe('burst_window');
  });
});

describe('source guards — the FE types no digit, window or served word', () => {
  const strip = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  const SERVED = [/Burst window/i, /Second wave/i, /Not advice/i, /UNMEASURED/, /bounce/i, /ajaykandakatla/i,
    /\d{2}:\d{2}/, /33\.8|22\.7|20\.8|39\.0|38\.1|15\.0/];
  const hits = (src: string) => SERVED.filter((r) => r.test(strip(src))).map(String);

  it('GgTimeWindow.tsx contains no digit at all (comments aside)', async () => {
    const src = await readSource('src/components/GgTimeWindow.tsx');
    expect(strip(src)).not.toMatch(/\d/);
    expect(hits(src)).toEqual([]);
  });
  it('the lib and the hook type no window, number or served word', async () => {
    for (const f of ['src/lib/ggTimeWindows.ts', 'src/hooks/useGgTimeWindows.ts']) {
      expect(hits(await readSource(f))).toEqual([]);
    }
  });
  it('NEGATIVE: the guards catch typed text', () => {
    expect(hits("<span>⏰ Burst window 09:30 — 33.8% · Not advice</span>").length).toBeGreaterThanOrEqual(4);
    expect(strip('<b>3</b>')).toMatch(/\d/);
  });
  it('mounted on the 🚩 board for GG5 + 🧪 audited only', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    expect(src).toContain("<GgTimeWindow enabled={vkey === 'gajjala' || vkey === 'gajjala_audited'} />");
    expect(src.match(/<GgTimeWindow\b/g)?.length).toBe(1);
  });
});

describe('gajjala_time_window.css — glow, reduced motion, 📱 430 px (source guards; jsdom has no layout)', () => {
  const rule = (src: string, sel: string): string | null => {
    const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const m = src.match(new RegExp(`(^|\\n)\\s*${esc}\\s*\\{([^}]*)\\}`));
    return m ? m[2] : null;
  };
  const has = (decl: string | null, prop: string, val: string) =>
    !!decl && new RegExp(`(^|;|\\s)${prop}\\s*:\\s*${val.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*(;|$)`).test(decl);
  const phoneOk = (src: string) => {
    const box = rule(src, '.gg-tw'), text = rule(src, '.gg-tw-text'), s = rule(src, '.gg-tw-src');
    return has(box, 'min-width', '0') && has(box, 'max-width', '100%')
      && [text, s].every((d) => has(d, 'min-width', '0') && has(d, 'white-space', 'normal') && has(d, 'overflow-wrap', 'anywhere'));
  };
  const motionOk = (src: string) => /\.gg-tw-glow\s*\{[^}]*animation:\s*gg-tw-radiate/.test(src)
    && /@keyframes gg-tw-radiate/.test(src)
    && /@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.gg-tw-glow\s*\{[^}]*animation:\s*none/.test(src);

  it('the shipped CSS wraps on a phone and stills the glow under reduced motion', async () => {
    const src = await readSource('src/styles/gajjala_time_window.css');
    expect(phoneOk(src)).toBe(true);
    expect(motionOk(src)).toBe(true);
  });
  it('NEGATIVE: a CSS without the wrap rules or the reduced-motion block fails', () => {
    const PRE = '.gg-tw { display: flex; }\n.gg-tw-text { font-weight: 600; }\n.gg-tw-src { font-size: 1px; }\n'
      + '.gg-tw-glow { animation: gg-tw-radiate 2s infinite; }\n@keyframes gg-tw-radiate { 0% { opacity: 1; } }\n';
    expect(phoneOk(PRE)).toBe(false);
    expect(motionOk(PRE)).toBe(false);
  });
});
