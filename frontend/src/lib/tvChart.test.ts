/* 📺 TV ↗ beside Yahoo ↗ (2026-11-23). Ajay: "Also add traderview charts on charts please.. Yahoo has been hard to
 * configure" · question card: "TV ↗ button only". The helper: URL, interval only when the frame is known, the dash →
 * dot share class rule, the double-cancel click, noopener. NEGATIVES: junk / absent frame → no interval; nothing but
 * symbol + interval in the URL; Yahoo's helper is untouched. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  TV_CHART_BASE, TV_INTERVAL, TV_LABEL, openTvChart, tvChartUrl, tvInterval, tvLinkTestId, tvTfFromHref, tvTitle,
} from './tvChart';
import { YAHOO_LABEL, yahooQuoteUrl } from './yahooLink';

describe('tvChartUrl', () => {
  it('his own chart page, symbol only when no frame is given', () => {
    expect(TV_CHART_BASE).toBe('https://www.tradingview.com/chart/');
    expect(tvChartUrl('IONQ')).toBe('https://www.tradingview.com/chart/?symbol=IONQ');
  });

  it('maps the known frames to TradingView interval codes (1 / 5 / 15 / 60 / D / W)', () => {
    expect(tvChartUrl('IONQ', '1min')).toBe('https://www.tradingview.com/chart/?symbol=IONQ&interval=1');
    expect(tvChartUrl('IONQ', '5m_today')).toBe('https://www.tradingview.com/chart/?symbol=IONQ&interval=5');
    expect(tvChartUrl('IONQ', '24h')).toBe('https://www.tradingview.com/chart/?symbol=IONQ&interval=5');
    expect(tvChartUrl('IONQ', '15m')).toBe('https://www.tradingview.com/chart/?symbol=IONQ&interval=15');
    expect(tvChartUrl('IONQ', '60m')).toBe('https://www.tradingview.com/chart/?symbol=IONQ&interval=60');
    expect(tvChartUrl('IONQ', 'daily')).toBe('https://www.tradingview.com/chart/?symbol=IONQ&interval=D');
    expect(tvChartUrl('IONQ', 'weekly')).toBe('https://www.tradingview.com/chart/?symbol=IONQ&interval=W');
    // the two retired keys keep their bar size
    expect(tvChartUrl('IONQ', '5m_live')).toContain('&interval=5');
    expect(tvChartUrl('IONQ', '15m_open')).toContain('&interval=15');
  });

  it('NEGATIVE: a junk, empty, null or prototype-key frame sends NO interval (his last-used interval opens)', () => {
    for (const tf of ['5m', '1m', 'junk', '', null, undefined, 'toString', 'constructor', '__proto__', 'DAILY']) {
      const u = tvChartUrl('IONQ', tf as string | null | undefined);
      expect(u, String(tf)).toBe('https://www.tradingview.com/chart/?symbol=IONQ');
      expect(u, String(tf)).not.toContain('interval');
      expect(tvInterval(tf as string | null | undefined), String(tf)).toBeNull();
    }
  });

  it('dash share class → the dot TradingView writes; trim + upper-case; encoded', () => {
    expect(tvChartUrl('brk-b')).toBe('https://www.tradingview.com/chart/?symbol=BRK.B');
    expect(tvChartUrl('  pom ')).toBe('https://www.tradingview.com/chart/?symbol=POM');
    expect(tvChartUrl('A B')).toBe('https://www.tradingview.com/chart/?symbol=A%20B');
    expect(tvChartUrl('x&interval=1')).toBe('https://www.tradingview.com/chart/?symbol=X%26INTERVAL%3D1');
  });

  it('NEGATIVE: only symbol (+ interval) ride — no other query key, never a Yahoo URL', () => {
    const u = new URL(tvChartUrl('IONQ', '15m'));
    expect(Array.from(u.searchParams.keys())).toEqual(['symbol', 'interval']);
    expect(u.host).toBe('www.tradingview.com');
    expect(tvChartUrl('IONQ', '15m')).not.toContain('yahoo');
  });

  it('the map has the nine 2026-08-31 rows, no more', () => {
    expect(Object.keys(TV_INTERVAL).sort()).toEqual(
      ['15m', '15m_open', '1min', '24h', '5m_live', '5m_today', '60m', 'daily', 'weekly']);
  });
});

describe('tvTfFromHref — the frame a served tile href carries', () => {
  it('reads tf off the query string', () => {
    expect(tvTfFromHref('/sepa/IONQ?tab=supply&tf=5m_today')).toBe('5m_today');
    expect(tvTfFromHref('/sepa/IONQ?tf=15m&tab=supply')).toBe('15m');
  });
  it('NEGATIVE: no query, no tf, empty or absent href → null', () => {
    expect(tvTfFromHref('/sepa/IONQ?tab=supply')).toBeNull();
    expect(tvTfFromHref('/sepa/IONQ')).toBeNull();
    expect(tvTfFromHref('')).toBeNull();
    expect(tvTfFromHref(undefined)).toBeNull();
    expect(tvTfFromHref(null)).toBeNull();
  });
});

describe('label / title / testid', () => {
  it('TV ↗, a title naming TradingView, an upper-case testid', () => {
    expect(TV_LABEL).toBe('TV ↗');
    expect(tvTitle('IONQ')).toBe('Open IONQ on your TradingView chart');
    expect(tvLinkTestId(' ionq')).toBe('tv-link-IONQ');
  });
  it('NEGATIVE: Yahoo ↗ is unchanged — its label and quote URL are the 2026-11-09 ones', () => {
    expect(YAHOO_LABEL).toBe('Yahoo ↗');
    expect(yahooQuoteUrl('BRK.B')).toBe('https://finance.yahoo.com/quote/BRK-B/');
    expect(TV_LABEL).not.toBe(YAHOO_LABEL);
  });
});

describe('openTvChart', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('cancels the tile navigation, stops the bubble, opens a new noopener tab', () => {
    const open = vi.fn();
    vi.stubGlobal('open', open);
    const e = { preventDefault: vi.fn(), stopPropagation: vi.fn() };
    openTvChart(e, 'IONQ', '1min');
    expect(e.preventDefault).toHaveBeenCalledTimes(1);
    expect(e.stopPropagation).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith('https://www.tradingview.com/chart/?symbol=IONQ&interval=1', '_blank', 'noopener,noreferrer');
    expect(String(open.mock.calls[0][2])).toContain('noopener');
  });

  it('NEGATIVE: no frame → no interval in the opened URL', () => {
    const open = vi.fn();
    vi.stubGlobal('open', open);
    openTvChart({ preventDefault: vi.fn(), stopPropagation: vi.fn() }, 'brk-b');
    expect(open).toHaveBeenCalledWith('https://www.tradingview.com/chart/?symbol=BRK.B', '_blank', 'noopener,noreferrer');
  });
});
