/* 📺 TV ↗ on the Support tab head, right BEFORE Yahoo ↗ (2026-11-23). Ajay: "Also add traderview charts on charts
 * please.. Yahoo has been hard to configure" · "I was see a 5 day chart something on our 1 min, 5min and 15 min
 * location". The head knows its frame, so the interval is the frame the tab is SHOWING (parseTf → curTf).
 * NEGATIVES: Yahoo ↗ unchanged (quote page, no interval); one TV ↗; a junk ?tf= shows daily, so TV ↗ says daily. */
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SupportLevels } from './SupportLevels';
import type { SupportPayload } from '../lib/supportLevels';
import { TV_LABEL, tvLinkTestId, tvTitle } from '../lib/tvChart';
import { YAHOO_LABEL } from '../lib/yahooLink';

vi.mock('./PatternChart', () => ({
  PatternChart: ({ tile }: any) => <div data-testid="chart">{tile.symbol}</div>,
}));

const PAYLOAD: SupportPayload = {
  symbol: 'DHI', name: 'D.R. Horton', window: '3m', window_label: '3 months',
  windows: [{ key: '3m', label: '3 months', bars: 63 }],
  recent_bars: 21, last_price: 156.4, bars_used: 63, short_history: null,
  tile: { symbol: 'DHI', href: '/sepa/DHI?tab=supply', bars: [], bands: [], lines: [], markers: [], stats: [], why: 'x' } as any,
  supports: [], overhead: [], standing_in: null, levels_capped: false,
  note: 'Levels are read from this window only.', disclaimer: 'Not advice.',
} as any;

const noop = () => {};
beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve({
    ok: true, status: 200, json: async () => (String(url).includes('/chart-maps/support') ? PAYLOAD : {}),
  })));
});
afterEach(() => vi.unstubAllGlobals());

const head = async (tf?: string) => {
  render(<SupportLevels symbol="DHI" window="1d" tf={tf} onSymbol={noop} onWindow={noop} />);
  await waitFor(() => expect(screen.getByTestId(tvLinkTestId('DHI'))).toBeTruthy());
  return screen.getByTestId(tvLinkTestId('DHI')) as HTMLAnchorElement;
};

describe('TV ↗ on the Support tab head', () => {
  it('right BEFORE Yahoo ↗, same cm-tv chip, new tab with noopener noreferrer', async () => {
    const a = await head('15m');
    expect(a.tagName).toBe('A');
    expect(a.textContent).toBe(TV_LABEL);
    expect(a.className).toBe('cm-tv');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(a.getAttribute('rel')).toBe('noopener noreferrer');
    expect(a.getAttribute('title')).toBe(tvTitle('DHI'));
    expect(a.nextElementSibling!.textContent).toBe(YAHOO_LABEL);
  });

  it('carries the frame the tab is showing: 15m → 15, 1min → 1, 5m_today → 5, none → daily D', async () => {
    expect((await head('15m')).getAttribute('href')).toBe('https://www.tradingview.com/chart/?symbol=DHI&interval=15');
  });
  it('1min → interval=1', async () => {
    expect((await head('1min')).getAttribute('href')).toBe('https://www.tradingview.com/chart/?symbol=DHI&interval=1');
  });
  it('5m_today → interval=5', async () => {
    expect((await head('5m_today')).getAttribute('href')).toBe('https://www.tradingview.com/chart/?symbol=DHI&interval=5');
  });
  it('no ?tf= → the tab shows daily → interval=D', async () => {
    expect((await head()).getAttribute('href')).toBe('https://www.tradingview.com/chart/?symbol=DHI&interval=D');
  });
  it('NEGATIVE: a junk ?tf= is drawn as daily, so TV ↗ says daily — never the junk key', async () => {
    const href = (await head('junk')).getAttribute('href')!;
    expect(href).toBe('https://www.tradingview.com/chart/?symbol=DHI&interval=D');
    expect(href).not.toContain('junk');
  });

  it('NEGATIVE: Yahoo ↗ unchanged — quote page, no interval, no tradingview; one TV ↗ only', async () => {
    await head('15m');
    const y = screen.getByText(YAHOO_LABEL) as HTMLAnchorElement;
    expect(y.getAttribute('href')).toBe('https://finance.yahoo.com/quote/DHI/');
    expect(y.getAttribute('href')).not.toContain('tradingview');
    expect(y.getAttribute('href')).not.toContain('interval');
    expect(screen.getAllByText(TV_LABEL)).toHaveLength(1);
  });
});
