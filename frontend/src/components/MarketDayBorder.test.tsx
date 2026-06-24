import { describe, it, expect, vi, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { marketBorderColor, MarketDayBorder } from './MarketDayBorder';

const RED = '#ef4444', AMBER = '#f59e0b', GREEN = '#10b981', GRAY = '#6b7280';

// Mutable hook mocks so each render test can pick a regime.
let gaugeRet: unknown = { state: 'caution', score: 59 };
let regimeRet: unknown = { data: { label: 'market_in_correction' } };
vi.mock('../hooks/useMarketGauge', () => ({ useMarketGauge: () => gaugeRet }));
vi.mock('../hooks/useMarketRegime', () => ({ useMarketRegime: () => regimeRet }));
afterEach(() => {
  vi.clearAllMocks();
  gaugeRet = { state: 'caution', score: 59 };
  regimeRet = { data: { label: 'market_in_correction' } };
});

describe('marketBorderColor — regime-led', () => {
  it('is RED in a confirmed correction (defensive — sit out new buys)', () => {
    expect(marketBorderColor('market_in_correction', 'caution')).toBe(RED);
  });

  it('REGRESSION: a correction that still scores in the "caution" band is RED, not gray', () => {
    // Ajay 2026-06-23: the gauge sat at 59 (caution) during a market_in_correction
    // with the portfolio -8.7%; the old score-only border rendered gray.
    expect(marketBorderColor('market_in_correction', 'caution')).toBe(RED);
    expect(marketBorderColor('market_in_correction', 'constructive')).toBe(RED);
  });

  it('is RED whenever the gauge itself flags risk_off, regardless of regime', () => {
    expect(marketBorderColor('confirmed_uptrend', 'risk_off')).toBe(RED);
    expect(marketBorderColor(null, 'risk_off')).toBe(RED);
  });

  it('is AMBER when the uptrend is under pressure', () => {
    expect(marketBorderColor('uptrend_under_pressure', 'caution')).toBe(AMBER);
  });

  it('is GREEN in a confirmed uptrend', () => {
    expect(marketBorderColor('confirmed_uptrend', 'constructive')).toBe(GREEN);
    expect(marketBorderColor('confirmed_uptrend', 'caution')).toBe(GREEN);
  });

  it('falls back to the gauge (green on constructive) before the regime loads', () => {
    expect(marketBorderColor(null, 'constructive')).toBe(GREEN);
  });

  it('is GRAY when nothing is known yet (loading)', () => {
    expect(marketBorderColor(null, null)).toBe(GRAY);
    expect(marketBorderColor(undefined, undefined)).toBe(GRAY);
  });
});

describe('MarketDayBorder — defensive red glow (v2)', () => {
  it('renders a soft inner-glow overlay in a confirmed correction', () => {
    regimeRet = { data: { label: 'market_in_correction' } };
    const { getByTestId } = render(<MarketDayBorder />);
    const el = getByTestId('market-day-border') as HTMLElement;
    expect(el.className).toContain('cm-regime-glow');
    // Glow, not the old hard 3px solid frame that sliced the nav bar.
    expect(el.style.boxShadow).toContain('inset');
    expect(el.style.border).not.toContain('3px solid');
    expect(el.style.pointerEvents).toBe('none');   // click-through, never blocks
  });

  it('renders the glow when the gauge flags risk_off even outside a correction', () => {
    regimeRet = { data: { label: 'confirmed_uptrend' } };
    gaugeRet = { state: 'risk_off', score: 30 };
    const { queryByTestId } = render(<MarketDayBorder />);
    expect(queryByTestId('market-day-border')).not.toBeNull();
  });

  it('REGIME-OFF: renders nothing in a bull market — clean, no glow', () => {
    regimeRet = { data: { label: 'confirmed_uptrend' } };
    gaugeRet = { state: 'constructive', score: 72 };
    const { container } = render(<MarketDayBorder />);
    expect(container).toBeEmptyDOMElement();
  });

  it('REGIME-OFF: renders nothing under pressure or while loading', () => {
    regimeRet = { data: { label: 'uptrend_under_pressure' } };
    gaugeRet = { state: 'caution', score: 55 };
    expect(render(<MarketDayBorder />).container).toBeEmptyDOMElement();

    regimeRet = { data: null };
    gaugeRet = null;
    expect(render(<MarketDayBorder />).container).toBeEmptyDOMElement();
  });
});
