import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import type { CmBar, CmTile } from '../lib/chartMaps';

/* PatternChart — one Chart Maps study tile.
 *
 * Locks the things that make the tile trustworthy rather than merely present:
 * every tile is a link to the SEPA detail (the whole point of the board), the
 * plan labels are actually drawn, a marker only appears when its date is in
 * the drawn window, and a tile with no bars renders NOTHING rather than an
 * empty frame implying a chart that failed to load. */

const bars = (n = 40): CmBar[] =>
  Array.from({ length: n }, (_, i) => {
    const day = String((i % 27) + 1).padStart(2, '0');
    const c = 10 + i * 0.1;
    return { t: `2026-07-${day}`, o: c - 0.1, h: c + 0.3, l: c - 0.4, c, v: 1_000 };
  });

const TILE: CmTile = {
  symbol: 'IONQ',
  name: 'IonQ Inc',
  href: '/sepa/IONQ?tab=setup',
  bars: bars(),
  bands: [{ kind: 'base', lo: 10.2, hi: 12.0, label: 'base 61d' }],
  lines: [
    { price: 12.4, label: 'PIVOT', tone: 'buy' },
    { price: 11.1, label: 'STOP', tone: 'stop' },
  ],
  markers: [],
  stats: [{ k: 'Tightness', v: '82' }, { k: 'Contractions', v: '3' }],
  why: 'tightens 28%→4% · volume drying up',
  theme: 'quantum',
  badges: [{ text: 'Setup ready', tone: 'warn' }],
};

const draw = (tile: CmTile) =>
  render(<MemoryRouter><PatternChart tile={tile} /></MemoryRouter>);

describe('PatternChart', () => {
  it('renders the ticker, its why-line and its stats', () => {
    draw(TILE);
    expect(screen.getByText('IONQ')).toBeInTheDocument();
    expect(screen.getByText('IonQ Inc')).toBeInTheDocument();
    expect(screen.getByText(/tightens 28%/)).toBeInTheDocument();
    expect(screen.getByText('Tightness')).toBeInTheDocument();
    expect(screen.getByText('82')).toBeInTheDocument();
  });

  // The board exists to be clicked through — a tile that is not a link is a
  // dead end, which is the one thing Ajay asked for explicitly.
  it('is a link to the ticker SEPA detail page', () => {
    draw(TILE);
    const link = screen.getByRole('link', { name: /IONQ — open SEPA detail/ });
    expect(link).toHaveAttribute('href', '/sepa/IONQ?tab=setup');
  });

  it('writes the plan levels onto the chart', () => {
    draw(TILE);
    expect(screen.getByText('PIVOT')).toBeInTheDocument();
    expect(screen.getByText('STOP')).toBeInTheDocument();
  });

  it('shows the theme tag so an off-index name is never mistaken for an index one', () => {
    draw(TILE);
    expect(screen.getByText(/Quantum/)).toBeInTheDocument();
  });

  it('shows the tier badge verbatim — "Setup ready" is not "Buyable"', () => {
    draw(TILE);
    expect(screen.getByText('Setup ready')).toBeInTheDocument();
    expect(screen.queryByText('Buyable')).not.toBeInTheDocument();
  });

  it('renders the last close', () => {
    draw(TILE);
    expect(screen.getByText('Last')).toBeInTheDocument();
  });

  /* ── negatives ───────────────────────────────────────────────────────── */

  it('renders nothing at all when the price series is empty', () => {
    const { container } = draw({ ...TILE, bars: [] });
    expect(container).toBeEmptyDOMElement();
  });

  it('draws a dated marker that falls inside the window', () => {
    draw({ ...TILE, markers: [{ date: '2026-07-05', label: 'confirmed' }] });
    expect(screen.getByText('confirmed')).toBeInTheDocument();
  });

  it('silently skips a marker whose date is NOT in the drawn window', () => {
    draw({ ...TILE, markers: [{ date: '2019-01-01', label: 'confirmed' }] });
    expect(screen.queryByText('confirmed')).not.toBeInTheDocument();
  });

  it('omits a plan label that sits far outside the price range', () => {
    draw({ ...TILE, lines: [{ price: 9_999, label: 'TARGET', tone: 'target' }] });
    expect(screen.queryByText('TARGET')).not.toBeInTheDocument();
  });

  it('handles a tile with no bands, badges, theme or name', () => {
    draw({ ...TILE, bands: [], badges: [], theme: null, name: null });
    expect(screen.getByText('IONQ')).toBeInTheDocument();
    expect(screen.queryByText('IonQ Inc')).not.toBeInTheDocument();
  });
});
