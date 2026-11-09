import { describe, it, expect, vi, afterEach } from 'vitest';
import { YAHOO_LABEL, YAHOO_QUOTE_BASE, openYahoo, yahooQuoteUrl, yahooTitle } from './yahooLink';

/* Ajay 2026-11-09: "Instead of traderview I need yahoo finance link here" / "To external ones please". */
describe('yahooQuoteUrl', () => {
  it('is the Yahoo Finance quote page for the symbol', () => {
    expect(yahooQuoteUrl('IONQ')).toBe('https://finance.yahoo.com/quote/IONQ/');
    expect(yahooQuoteUrl('IONQ').startsWith(YAHOO_QUOTE_BASE)).toBe(true);
  });

  it('trims and upper-cases the symbol', () => {
    expect(yahooQuoteUrl('  pom ')).toBe('https://finance.yahoo.com/quote/POM/');
  });

  it("keeps this app's dash share classes and rewrites a dot class to Yahoo's dash", () => {
    expect(yahooQuoteUrl('BRK-B')).toBe('https://finance.yahoo.com/quote/BRK-B/');
    expect(yahooQuoteUrl('BRK.B')).toBe('https://finance.yahoo.com/quote/BRK-B/');
  });

  it('NEGATIVE: never a dot or an encoded dot, never a TradingView URL, no interval', () => {
    const u = yahooQuoteUrl('brk-b');
    expect(u).not.toContain('BRK.B');
    expect(u).not.toContain('%2E');
    expect(u).not.toContain('tradingview');
    expect(u).not.toContain('interval');
  });

  it('URL-encodes anything odd in the symbol', () => {
    expect(yahooQuoteUrl('A B')).toBe('https://finance.yahoo.com/quote/A%20B/');
  });
});

describe('yahooTitle / YAHOO_LABEL', () => {
  it('names Yahoo Finance, never TradingView', () => {
    expect(yahooTitle('IONQ')).toBe('Open IONQ on Yahoo Finance');
    expect(YAHOO_LABEL).toBe('Yahoo ↗');
    expect(YAHOO_LABEL).not.toContain('TV');
  });
});

describe('openYahoo', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('cancels the tile navigation, stops the bubble, opens a new noopener tab', () => {
    const open = vi.fn();
    vi.stubGlobal('open', open);
    const e = { preventDefault: vi.fn(), stopPropagation: vi.fn() };
    openYahoo(e, 'IONQ');
    expect(e.preventDefault).toHaveBeenCalledTimes(1);
    expect(e.stopPropagation).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith('https://finance.yahoo.com/quote/IONQ/', '_blank', 'noopener');
  });

  it('rewrites a dot share class before opening and still cancels the click', () => {
    vi.stubGlobal('open', vi.fn());
    const e = { preventDefault: vi.fn(), stopPropagation: vi.fn() };
    openYahoo(e, 'brk.b');
    expect((window.open as unknown as { mock: { calls: unknown[][] } }).mock.calls[0][0]).toBe('https://finance.yahoo.com/quote/BRK-B/');
    expect(e.preventDefault).toHaveBeenCalled();
  });
});
