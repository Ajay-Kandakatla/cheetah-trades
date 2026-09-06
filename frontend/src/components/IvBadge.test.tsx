import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { MarketIv } from '../hooks/useMarketIv';

/* IvBadge (Ajay 2026-09-06: "add that to our regular used pages as a global
   indicator? May be beside Market gauge metric?"). The hook is mocked (mutable,
   so each test picks a payload) and the badge renders inside a MemoryRouter
   because it is a NavLink to /market-gauge. */
let ivRet: MarketIv | null = null;
vi.mock('../hooks/useMarketIv', () => ({ useMarketIv: () => ivRet }));

import { IvBadge } from './IvBadge';

const FIXTURE: MarketIv = {
  vix: 14.5, prev: 14.3, chg: 0.2, chg_pct: 1.4, pct_252: 5,
  regime: 'calm', regime_label: 'Calm',
  bands: { calm_below: 15, normal_below: 20, elevated_below: 30 },
  term: { vix9d: 16.8, vix3m: 20.4, ratio_9d_30d: 1.16, ratio_30d_3m: 0.71, shape: 'contango', as_of: '2026-09-04' },
  vvix: 84, as_of: '2026-09-04',
  read: 'Options are pricing a quiet tape.',
  generated_at: 1_757_000_000, age_sec: 12,
  disclaimer: 'A regime read, not a forecast.',
};

function renderBadge(compact = false, path = '/sepa') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <IvBadge compact={compact} />
    </MemoryRouter>,
  );
}

afterEach(() => { ivRet = null; });

describe('IvBadge — nav implied-volatility read', () => {
  it('renders the level, the regime word and the percentile chip from the payload', () => {
    ivRet = FIXTURE;
    renderBadge();
    const link = screen.getByRole('link');
    expect(link.getAttribute('href')).toBe('/market-gauge');
    expect(link.textContent).toContain('IV');
    expect(link.textContent).toContain('14.5');
    expect(link.textContent).toContain('Calm');
    expect(link.textContent).toContain('5th pct');
    expect(link.className).toContain('iv-badge--calm');
    expect(link.className).not.toContain('iv-badge--compact');
  });

  it('title + aria-label carry the full read (level, change, regime, pct, term, VVIX, day, read)', () => {
    ivRet = FIXTURE;
    renderBadge();
    const link = screen.getByRole('link');
    const expected =
      'VIX 14.5 (▲0.2) · Calm · 5th pct of the year · 9D/30D 1.16 · 30D/3M 0.71 contango · VVIX 84 · as of Fri — Options are pricing a quiet tape.';
    expect(link.getAttribute('title')).toBe(expected);
    expect(link.getAttribute('aria-label')).toBe(`Implied volatility: ${expected}`);
  });

  it('compact keeps the level + arrow but hides the regime word and the percentile chip', () => {
    ivRet = FIXTURE;
    renderBadge(true);
    const link = screen.getByRole('link');
    expect(link.className).toContain('iv-badge--compact');
    expect(link.textContent).toContain('14.5');
    expect(link.textContent).toContain('▲0.2');
    expect(link.textContent).not.toContain('Calm');
    expect(link.textContent).not.toContain('pct');
    // the words still ride in the tooltip
    expect(link.getAttribute('title')).toContain('Calm');
  });

  it('renders NOTHING before the read has loaded (no layout flash)', () => {
    ivRet = null;
    const { container } = renderBadge();
    expect(container.firstChild).toBeNull();
  });

  it('renders NOTHING when the VIX level itself is null', () => {
    ivRet = { ...FIXTURE, vix: null };
    const { container } = renderBadge();
    expect(container.firstChild).toBeNull();
  });

  it.each([
    ['calm', 12.1],
    ['normal', 17.4],
    ['elevated', 24.9],
    ['stress', 38.2],
  ] as const)('wears the %s regime class', (regime, vix) => {
    ivRet = { ...FIXTURE, regime, regime_label: null, vix };
    renderBadge();
    const link = screen.getByRole('link');
    expect(link.className).toContain(`iv-badge--${regime}`);
    // no label from the backend → the key is capitalised
    expect(link.textContent).toContain(regime.charAt(0).toUpperCase() + regime.slice(1));
  });

  it('falls back to a neutral class when the regime is null but the level is present', () => {
    ivRet = { ...FIXTURE, regime: null, regime_label: null };
    renderBadge();
    expect(screen.getByRole('link').className).toContain('iv-badge--na');
  });

  it('arrow points ▲ on an up day and ▼ on a down day', () => {
    ivRet = { ...FIXTURE, chg: 0.2 };
    const { unmount } = renderBadge();
    expect(screen.getByRole('link').textContent).toContain('▲0.2');
    expect(screen.getByRole('link').querySelector('.iv-badge__chg--up')).not.toBeNull();
    unmount();
    ivRet = { ...FIXTURE, chg: -1.34 };
    renderBadge();
    expect(screen.getByRole('link').textContent).toContain('▼1.3');
    expect(screen.getByRole('link').querySelector('.iv-badge__chg--down')).not.toBeNull();
  });

  it('shows no arrow when |chg| < 0.1 or chg is null', () => {
    ivRet = { ...FIXTURE, chg: 0.04 };
    const { unmount } = renderBadge();
    expect(screen.getByRole('link').querySelector('.iv-badge__chg')).toBeNull();
    expect(screen.getByRole('link').getAttribute('title')).toContain('VIX 14.5 · Calm');
    unmount();
    ivRet = { ...FIXTURE, chg: null };
    renderBadge();
    expect(screen.getByRole('link').querySelector('.iv-badge__chg')).toBeNull();
  });

  it('omits the percentile chip when pct_252 is null and tolerates a null term / vvix', () => {
    ivRet = { ...FIXTURE, pct_252: null, term: null, vvix: null, as_of: null, read: '' };
    renderBadge();
    const link = screen.getByRole('link');
    expect(link.textContent).not.toContain('pct');
    expect(link.getAttribute('title')).toBe('VIX 14.5 (▲0.2) · Calm');
  });

  it('is-active on the Market Gauge page itself', () => {
    ivRet = FIXTURE;
    renderBadge(false, '/market-gauge');
    expect(screen.getByRole('link').className).toContain('is-active');
  });
});
