import { describe, expect, it } from 'vitest';
import served from '../components/__fixtures__/support_timeframes_2026_10_26.json';
import {
  FALLBACK_TIMEFRAMES, STRUCTURE_TIMEFRAMES,
  parseTf, parseWindow, retiredTf, shortHistoryNote,
  windowForFrame, windowsForFrame, zoomApplies,
  type SupportPayload,
} from './supportLevels';
import { tvChartUrl } from './tvChart';

/* 🕐 The 1-minute + weekly Support frames (2026-10-26).
 *
 * Ajay: "Can you build me 1 min bar chart and also 1 week bar chart in the
 * supply and demand".
 *
 * The picker renders the SERVED list; FALLBACK_TIMEFRAMES is the first-paint
 * mirror that `parseTf(?tf=)` and `windowsForFrame` resolve against, so it is
 * pinned here to the GENERATED fixture (json.dumps of
 * `tf_options(include_live=True)`), never to typed strings. */

type Row = { key: string; label: string; span: string; bar_label: string;
  window_label: string; bars: number };
const SERVED = served as Row[];

describe('🕐 the 1-minute and weekly frames — FE mirror', () => {
  it('FALLBACK_TIMEFRAMES mirrors the SERVED list verbatim, in order', () => {
    expect(FALLBACK_TIMEFRAMES.map((t) => t.key)).toEqual(SERVED.map((r) => r.key));
    SERVED.forEach((r, i) => {
      const t = FALLBACK_TIMEFRAMES[i];
      expect({ key: t.key, label: t.label, span: t.span, bar_label: t.bar_label,
               window_label: t.window_label, bars: t.bars }, r.key).toEqual(r);
    });
  });

  it('parseTf resolves 1min and weekly and every alias', () => {
    for (const k of ['1min', ' 1-MIN ', '1minute', 'm1']) expect(parseTf(k), k).toBe('1min');
    for (const k of ['weekly', 'W', 'week', 'wk', '1wk']) expect(parseTf(k), k).toBe('weekly');
  });

  it("NEGATIVE: '1m' is the one-month WINDOW, never the 1-minute frame", () => {
    expect(parseTf('1m')).toBe('daily');
    expect(parseWindow('1m')).toBe('1m');
  });

  it("NEGATIVE: '1w' is the one-week WINDOW, never the weekly frame", () => {
    expect(parseTf('1w')).toBe('daily');
    expect(parseWindow('1w')).toBe('1w');
  });

  it('the 1-minute frame defines its own window', () => {
    expect(windowsForFrame('1min')).toEqual([]);
    expect(zoomApplies('1min')).toBe(false);
    expect(windowForFrame('1min', '1y')).toBe('6m');
  });

  it('the weekly frame offers only what weekly bars can fill', () => {
    expect(windowsForFrame('weekly')).toEqual(['6m', '1y', '2y', '3y', '5y']);
    expect(windowForFrame('weekly', '2y')).toBe('2y');
    for (const w of ['1w', '2w', '1m', '3m', 'all', 'junk']) {
      expect(windowForFrame('weekly', w), w).toBe('1y');
    }
    expect(zoomApplies('weekly')).toBe(true);
  });

  it('NEGATIVE: an unknown frame still falls back exactly as before', () => {
    expect(parseTf('fortnightly')).toBe('daily');
    expect(windowsForFrame('fortnightly')).toEqual(windowsForFrame('daily'));
    // weekly is a real frame now, not a retirement — no "was retired" notice.
    expect(retiredTf('weekly')).toBeNull();
  });

  it('NEGATIVE: neither new frame reaches the structure picker', () => {
    expect(STRUCTURE_TIMEFRAMES.map((t) => t.key)).toEqual(['15m', '60m', 'daily']);
  });

  it('NEGATIVE: the five existing rows are byte-identical', () => {
    // Literal copy of supportLevels.ts FALLBACK_TIMEFRAMES at origin/main a218264a.
    const FIVE = [
      { key: '5m_today', label: 'Today, for an entry',
        bar_label: '5-minute', window_label: 'today only, from 04:00 ET',
        span: '5-minute bars · today only, from 04:00 ET', bars: 192, ext: true },
      { key: '24h', label: 'Last 24 hours',
        bar_label: '5-minute',
        window_label: 'the 24 hours up to the last print, pre-market through after-hours',
        span: '5-minute bars · the 24 hours up to the last print, pre-market through after-hours',
        bars: 288, ext: true },
      { key: '15m', label: 'The last two weeks',
        bar_label: '15-minute', window_label: 'the last ~10 sessions',
        span: '15-minute bars · the last ~10 sessions', bars: 260 },
      { key: '60m', label: 'The last two months',
        bar_label: '1-hour', window_label: 'the last ~47 sessions',
        span: '1-hour bars · the last ~47 sessions', bars: 330 },
      { key: 'daily', label: 'The big picture',
        bar_label: 'daily',
        window_label: '1 year by default — the Zoom dropdown sets how far back',
        span: 'daily bars · 1 year by default — the Zoom dropdown sets how far back',
        bars: 252 },
    ];
    const keys = new Set(FIVE.map((r) => r.key));
    expect(FALLBACK_TIMEFRAMES.filter((t) => keys.has(t.key))).toEqual(FIVE);
  });

  it('tvChartUrl opens 1-minute and weekly charts; the window keys open daily', () => {
    expect(tvChartUrl('NVDA', '1min')).toContain('interval=1');
    expect(tvChartUrl('NVDA', '1min')).not.toContain('interval=15');
    expect(tvChartUrl('NVDA', 'weekly')).toContain('interval=W');
    expect(tvChartUrl('NVDA', '1m')).toContain('interval=D');
    expect(tvChartUrl('NVDA', '1w')).toContain('interval=D');
  });

  it('shortHistoryNote prints the SERVED unit', () => {
    const p = { short_history: { have: 30, asked: 52, unit: 'weekly bars' } } as SupportPayload;
    expect(shortHistoryNote(p)).toBe(
      'Only 30 weekly bars of history — less than the 52 this window asks for. '
      + 'Levels are read from what exists.');
  });

  it('NEGATIVE: without a served unit the sentence is unchanged', () => {
    const p = { short_history: { have: 30, asked: 126 } } as SupportPayload;
    expect(shortHistoryNote(p)).toBe(
      'Only 30 sessions of history — less than the 126 this window asks for. '
      + 'Levels are read from what exists.');
  });

  it('NEGATIVE: no new row says bounce, and no label is a bar size', () => {
    const fresh = FALLBACK_TIMEFRAMES.filter((t) => t.key === '1min' || t.key === 'weekly');
    expect(fresh.map((t) => t.key)).toEqual(['1min', 'weekly']);
    for (const t of fresh) {
      expect(`${t.label} ${t.span}`).not.toMatch(/bounc/i);
      expect(t.label, `${t.key} is named by its bar size`)
        .not.toMatch(/^\s*(daily|\d+\s*(min|minute|hour|h|m))\b/i);
      expect(t.span).not.toMatch(/2\.5 sessions/);
    }
  });
});
