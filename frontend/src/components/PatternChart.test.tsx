import { describe, it, expect, vi, afterEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
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
    const url = new URL(link.getAttribute('href')!, 'http://x');
    expect(url.pathname).toBe('/sepa/IONQ');
    expect(url.searchParams.get('tab')).toBe('setup');
  });

  // Ajay 2026-08-16: back from the detail page was dumping him on the scanner.
  // The tile stamps its origin into the URL, not just router state, because the
  // detail page's tab switch replaces the history entry and drops state.
  it('stamps the calling page into the link so Back returns to Chart Maps', () => {
    draw(TILE);
    const link = screen.getByRole('link', { name: /IONQ — open SEPA detail/ });
    const url = new URL(link.getAttribute('href')!, 'http://x');
    expect(url.searchParams.get('from')).toBe('chart-maps');
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

/* ── hover readout (Ajay 2026-08-19: "hover over prices at the level") ──────
 *
 * jsdom gives every element a zero-size bounding rect, and the handler bails on
 * that (a zero-width box would divide by zero and put the crosshair at NaN). So
 * the rect is stubbed to the real rendered aspect: 620 x 190 viewBox units. */
function hoverAt(container: HTMLElement, xFrac: number, yFrac: number) {
  const svg = container.querySelector('svg')!;
  svg.getBoundingClientRect = () => ({
    left: 0, top: 0, width: 620, height: 190,
    right: 620, bottom: 190, x: 0, y: 0, toJSON: () => ({}),
  }) as DOMRect;
  fireEvent.mouseMove(svg, { clientX: 620 * xFrac, clientY: 190 * yFrac });
  return svg;
}

describe('hover readout', () => {
  it('draws nothing extra until the pointer is actually over the chart', () => {
    const { container } = draw(TILE);
    // No crosshair, no readout — the 24-tile board must stay static at rest.
    expect(container.querySelectorAll('rect[rx="4"]').length).toBe(0);
  });

  it('shows a price for the row under the cursor', () => {
    const { container } = draw(TILE);
    hoverAt(container, 0.5, 0.5);
    const texts = Array.from(container.querySelectorAll('svg text'))
      .map((t) => t.textContent || '');
    // Mid-chart on a 10.0 -> 13.9 series: a two-decimal price in that range.
    const prices = texts.filter((t) => /^\d+\.\d{2}$/.test(t)).map(Number);
    expect(prices.length).toBeGreaterThan(0);
    expect(Math.max(...prices)).toBeGreaterThan(9);
    expect(Math.min(...prices)).toBeLessThan(20);
  });

  it('reads the OHLC of the bar under the cursor', () => {
    const { container } = draw(TILE);
    hoverAt(container, 0.5, 0.5);
    const all = container.textContent || '';
    expect(all).toMatch(/O \d+\.\d{2}\s+H \d+\.\d{2}/);
    expect(all).toMatch(/L \d+\.\d{2}\s+C \d+\.\d{2}/);
    expect(all).toContain('Vol');
  });

  it('names the band when the cursor is standing inside one', () => {
    const { container } = draw(TILE);
    // The base band is 10.2-12.0 and the series runs 10.0-13.9, so the lower
    // third of the chart is inside it.
    hoverAt(container, 0.5, 0.86);
    expect(container.textContent).toContain('base 61d');
  });

  it('clears everything on mouse leave', () => {
    const { container } = draw(TILE);
    const svg = hoverAt(container, 0.5, 0.5);
    expect(container.textContent).toContain('Vol');
    fireEvent.mouseLeave(svg);
    expect(container.textContent).not.toContain('Vol');
  });

  it('never emits NaN when the rect has no size (jsdom / hidden tab)', () => {
    const { container } = draw(TILE);
    const svg = container.querySelector('svg')!;
    fireEvent.mouseMove(svg, { clientX: 100, clientY: 50 });   // rect is 0x0
    expect(container.innerHTML).not.toContain('NaN');
  });

  it('a band carries a native title so a resting pointer still names it', () => {
    const { container } = draw(TILE);
    const title = container.querySelector('rect > title');
    expect(title?.textContent).toContain('base 61d');
  });
});

/* ── the right gutter must fit its labels (META screenshot, 2026-08-19) ────── */
describe('label clipping', () => {
  it('REGRESSION: a long plan label is not cut off at the SVG edge', () => {
    const { container } = render(
      <MemoryRouter>
        <PatternChart tile={{
          ...TILE,
          lines: [{ price: 12.4, label: 'overhead 553.67', tone: 'target' },
                  { price: 11.1, label: 'support 527.64', tone: 'buy' }],
        }} height={320} />
      </MemoryRouter>);
    const svg = container.querySelector('svg')!;
    const vbW = Number(svg.getAttribute('viewBox')!.split(' ')[2]);
    for (const t of Array.from(svg.querySelectorAll('text'))) {
      const x = Number(t.getAttribute('x'));
      const txt = t.textContent || '';
      if (!txt.includes('overhead') && !txt.includes('support')) continue;
      // 0.55em average advance is the same estimate gutterWidth uses.
      expect(x + txt.length * 0.55 * 9.5).toBeLessThanOrEqual(vbW);
    }
  });
});

// ── 0DTE gamma walls (Ajay 2026-08-24) ───────────────────────────────────────
describe('the neutral band', () => {
  const walls: CmTile = {
    ...TILE,
    bands: [{ kind: 'neutral', lo: 11.5, hi: 12.5, label: 'gamma walls' }],
    lines: [{ price: 12.0, label: 'now', tone: 'now' }],
  };

  it('draws a range that is neither a floor nor a lid', () => {
    // The 0DTE gamma walls bracket where dealer hedging is expected to contain
    // the tape. Reusing `demand` (green) or `supply` (red) would give the band
    // a direction it does not have.
    const { container } = draw(walls);
    const rects = Array.from(container.querySelectorAll('rect[fill]'));
    const muted = rects.filter((r) =>
      (r.getAttribute('fill') || '').includes('--text-muted'));
    expect(muted.length).toBeGreaterThan(0);
  });

  it('never paints it with the support or overhead colour', () => {
    // Targets the BAND rect specifically — the ones spanning the full plot and
    // carrying a <title>. A blanket rect[fill] sweep also catches the candles,
    // which are legitimately green and red.
    const { container } = draw(walls);
    const bandFills = Array.from(container.querySelectorAll('rect[x="0"]'))
      .filter((r) => r.querySelector('title'))
      .map((r) => r.getAttribute('fill') || '');
    expect(bandFills.length).toBeGreaterThan(0);
    expect(bandFills.some((f) => f.includes('--positive'))).toBe(false);
    expect(bandFills.some((f) => f.includes('--negative'))).toBe(false);
  });

  it('labels it by its own name rather than falling back to the kind', () => {
    draw(walls);
    expect(screen.getByText(/gamma walls/)).toBeInTheDocument();
  });

  it('falls back to "Range" when the band carries no label', () => {
    // A raw `neutral` leaking into the UI would read as a bug.
    draw({ ...walls, bands: [{ kind: 'neutral', lo: 11.5, hi: 12.5 }] });
    expect(screen.getByText(/Range/)).toBeInTheDocument();
    expect(screen.queryByText(/neutral/)).not.toBeInTheDocument();
  });
});

describe('the TV link-out', () => {
  // The Charting Library application was refused (auth-gated site), so the
  // pre-configured chart is a LINK to tradingview.com — never an embed.
  afterEach(() => vi.unstubAllGlobals());

  it('every tile carries a TV button that opens WITHOUT following the tile link', () => {
    const open = vi.fn();
    vi.stubGlobal('open', open);
    draw(TILE);
    fireEvent.click(screen.getByRole('button', { name: /IONQ in TradingView/ }));
    expect(open).toHaveBeenCalledWith(
      'https://www.tradingview.com/chart/?symbol=IONQ&interval=D', '_blank', 'noopener');
  });

  it('a session tile preconfigures the 15-minute interval', () => {
    const open = vi.fn();
    vi.stubGlobal('open', open);
    render(<MemoryRouter><PatternChart tile={TILE} tvTf="15m" /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /IONQ in TradingView/ }));
    expect(open.mock.calls[0][0]).toContain('interval=15');
  });
});
