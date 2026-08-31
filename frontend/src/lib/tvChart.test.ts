import { describe, it, expect, vi, afterEach } from 'vitest';
import { openTvChart, tvChartUrl } from './tvChart';

describe('tvChartUrl', () => {
  it('preconfigures symbol + daily interval', () => {
    expect(tvChartUrl('ACN'))
      .toBe('https://www.tradingview.com/chart/?symbol=ACN&interval=D');
  });

  it('maps the session timeframes to TV interval codes', () => {
    expect(tvChartUrl('QBTS', '15m')).toContain('interval=15');
    expect(tvChartUrl('QBTS', '60m')).toContain('interval=60');
    expect(tvChartUrl('QBTS', 'daily')).toContain('interval=D');
  });

  it('falls back to daily on a timeframe it has never heard of', () => {
    expect(tvChartUrl('QBTS', '5m')).toContain('interval=D');
  });

  it('rewrites dash share classes to the dot TradingView uses', () => {
    expect(tvChartUrl('brk-b')).toContain('symbol=BRK.B');
  });
});

describe('openTvChart', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('cancels the tile Link navigation AND opens a noopener tab', () => {
    // The tile is an <a> — without both cancels the click would ALSO open
    // the SEPA detail page underneath the TV tab.
    const open = vi.fn();
    vi.stubGlobal('open', open);
    const e = { preventDefault: vi.fn(), stopPropagation: vi.fn() };
    openTvChart(e, 'ACN');
    expect(e.preventDefault).toHaveBeenCalled();
    expect(e.stopPropagation).toHaveBeenCalled();
    expect(open).toHaveBeenCalledWith(
      'https://www.tradingview.com/chart/?symbol=ACN&interval=D', '_blank', 'noopener');
  });
});
