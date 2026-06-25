import { describe, it, expect, vi, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { marketPosture, MarketPostureBanner } from './MarketPostureBanner';

/* Hooks + router are mocked (mutable, so each test can pick a regime) so we can
   render the pill standalone. The render tests below lock Bug-2's fix
   (2026-06-23): the label used to be position:fixed and floated OVER the nav
   bar (desktop) and OVER scrolled content (mobile). It now lives in-flow inside
   the nav's flex layout, must NOT carry fixed/absolute positioning, and (v2)
   only renders in the DEFENSIVE (red) regime so bull markets stay clean. */
let gaugeRet: unknown = { state: 'caution', score: 59 };
let regimeRet: unknown = { data: { label: 'market_in_correction' } };
vi.mock('../hooks/useMarketGauge', () => ({ useMarketGauge: () => gaugeRet }));
vi.mock('../hooks/useMarketRegime', () => ({ useMarketRegime: () => regimeRet }));
vi.mock('react-router-dom', () => ({ useNavigate: () => () => {} }));

afterEach(() => {
  vi.clearAllMocks();
  gaugeRet = { state: 'caution', score: 59 };
  regimeRet = { data: { label: 'market_in_correction' } };
});

describe('marketPosture — regime-led top banner', () => {
  it('reads RED "Market in correction" in a confirmed correction', () => {
    expect(marketPosture('market_in_correction', 'caution')).toEqual({
      label: 'Market in correction', tone: 'red',
    });
  });

  it('a correction in the caution score-band is still RED', () => {
    expect(marketPosture('market_in_correction', 'caution')?.tone).toBe('red');
  });

  it('RED whenever the gauge flags risk_off', () => {
    expect(marketPosture('confirmed_uptrend', 'risk_off')?.tone).toBe('red');
  });

  it('AMBER when the uptrend is under pressure', () => {
    expect(marketPosture('uptrend_under_pressure', 'caution')).toEqual({
      label: 'Uptrend under pressure', tone: 'amber',
    });
  });

  it('GREEN in a confirmed uptrend / constructive gauge', () => {
    expect(marketPosture('confirmed_uptrend', 'constructive')?.tone).toBe('green');
    expect(marketPosture(null, 'constructive')?.tone).toBe('green');
  });

  it('hides (null) while nothing is known yet — no pill on load', () => {
    expect(marketPosture(null, null)).toBeNull();
    expect(marketPosture(undefined, undefined)).toBeNull();
  });
});

describe('MarketPostureBanner — in-flow nav pill (no overlap)', () => {
  it('renders the posture pill with the nav-chrome class', () => {
    const { container } = render(<MarketPostureBanner />);
    const pill = container.querySelector('.cm-posture-pill') as HTMLElement;
    expect(pill).not.toBeNull();
    expect(pill.textContent).toContain('Market in correction');
    expect(pill.textContent).toContain('59');
  });

  it('REGRESSION (Bug 2): is NOT fixed/absolute — so it cannot overlap nav or content', () => {
    const { container } = render(<MarketPostureBanner />);
    const pill = container.querySelector('.cm-posture-pill') as HTMLElement;
    // The old bug was position:fixed; top:8; z-index:9100 floating over the page.
    // An in-flow pill has static/normal positioning and no viewport pinning.
    expect(pill.style.position).not.toBe('fixed');
    expect(pill.style.position).not.toBe('absolute');
    expect(pill.style.zIndex).toBe('');   // no stacking-context escape
    expect(pill.style.top).toBe('');
  });

  it('placement="bottom" (mobile): floats fixed at the BOTTOM, never the top — so it cannot crowd the hamburger', () => {
    const { container } = render(<MarketPostureBanner placement="bottom" />);
    const pill = container.querySelector('.cm-posture-pill--bottom') as HTMLElement;
    expect(pill).not.toBeNull();
    expect(pill.style.position).toBe('fixed');
    expect(pill.style.bottom).not.toBe('');   // pinned to the bottom
    expect(pill.style.top).toBe('');          // NOT the top (where the nav/hamburger live)
  });

  it('v2: stays hidden (null) in a bull regime — clean chrome, no banner', () => {
    regimeRet = { data: { label: 'confirmed_uptrend' } };
    gaugeRet = { state: 'constructive', score: 72 };
    const { container } = render(<MarketPostureBanner />);
    expect(container.querySelector('.cm-posture-pill')).toBeNull();
    expect(container).toBeEmptyDOMElement();
  });

  it('v2: stays hidden (null) when the uptrend is merely under pressure', () => {
    regimeRet = { data: { label: 'uptrend_under_pressure' } };
    gaugeRet = { state: 'caution', score: 55 };
    const { container } = render(<MarketPostureBanner />);
    expect(container.querySelector('.cm-posture-pill')).toBeNull();
  });
});
