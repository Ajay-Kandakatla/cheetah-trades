/* PatternMatchCards — the `only` prop, i.e. the 🎯 enterable cut reaching the
 * 📐 card grid (2026-09-15).
 *
 * Why this file exists. The grid reads the shared verdict cache itself, so the
 * page's partition could not reach it: with "Enterable only" ON, the pattern
 * LIST went quiet while the cards underneath it kept drawing the very ⛔ names
 * the filter had just removed ("I do not want to see not enterable ... stocks
 * in any of the chart maps"). The prop is a plain symbol allow-list handed down
 * by the caller — this component still grades nothing and fetches nothing.
 *
 * The negatives carry it: `only` undefined is the identity every OTHER mount of
 * this component (Portfolio, Leaderboard, Top Picks) depends on, and an allow-
 * list that keeps a name must keep it whatever its verdict is — WATCH and a
 * name with no read at all are the caller's to pass through, never this file's
 * to second-guess.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternMatchCards } from './PatternMatchCards';
import type { PatternVerdict } from '../hooks/usePatternVerdicts';

const match = (symbol: string) => ({
  symbol, pattern: 'double_bottom', status: 'confirmed' as const,
  neckline: 10, pattern_low: 8, target: 12, stop: 7, last_close: 10.5, bars_since_confirm: 1,
});
const verdict = (symbol: string, over: Partial<PatternVerdict> = {}): PatternVerdict => ({
  symbol, matches: [match(symbol)], no_match: false,
  sepa: { rs_rank: 70, stage: 2 }, ...over,
});

/* READY · WATCH · BLOCKED · no read at all — the four shapes the partition can
   produce, so the allow-list is exercised on every one of them. */
const VERDICTS = new Map<string, PatternVerdict>([
  ['RDY', verdict('RDY', { sources: ['holding'] })],
  ['WCH', verdict('WCH', { sources: ['watchlist'] })],
  ['BLK', verdict('BLK')],
  ['UNREAD', verdict('UNREAD')],
  ['NOPAT', verdict('NOPAT', { matches: [], no_match: true })],
]);

vi.mock('../hooks/usePatternVerdicts', () => ({
  usePatternVerdicts: () => ({ verdicts: VERDICTS, generatedAt: 1789000000 }),
}));
vi.mock('../hooks/useEarningsMap', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../hooks/useEarningsMap')>()),
  useEarningsMap: () => new Map(),
}));
vi.mock('../hooks/useCompanyNames', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../hooks/useCompanyNames')>()),
  useCompanyNames: () => new Map(),
}));

const draw = (props: Parameters<typeof PatternMatchCards>[0] = {}) =>
  render(<MemoryRouter><PatternMatchCards {...props} /></MemoryRouter>);

const drawn = () => ['RDY', 'WCH', 'BLK', 'UNREAD', 'NOPAT']
  .filter((s) => screen.queryByText(s) !== null);

describe('PatternMatchCards — the 🎯 enterable allow-list', () => {
  it('draws only the names the caller kept — the ⛔ one is gone', () => {
    draw({ only: new Set(['RDY', 'WCH', 'UNREAD']) });
    expect(drawn()).toEqual(['RDY', 'WCH', 'UNREAD']);
    expect(screen.queryByText('BLK')).not.toBeInTheDocument();
  });

  it('keeps a WATCH name and a name with no read — the caller decides, not this file', () => {
    draw({ only: new Set(['WCH', 'UNREAD']) });
    expect(screen.getByText('WCH')).toBeInTheDocument();
    expect(screen.getByText('UNREAD')).toBeInTheDocument();
    expect(screen.queryByText('RDY')).not.toBeInTheDocument();
  });

  it('matches on the UPPERCASED symbol, the way every served map is keyed', () => {
    draw({ only: new Set(['RDY']) });
    expect(drawn()).toEqual(['RDY']);
  });

  it('NEGATIVE: `only` undefined is the identity — every matched name is drawn', () => {
    draw();
    // NOPAT has no pattern match, so it was never part of this grid.
    expect(drawn()).toEqual(['RDY', 'WCH', 'BLK', 'UNREAD']);
  });

  it('NEGATIVE: an empty allow-list draws nothing and fails quiet (no empty heading)', () => {
    const { container } = draw({ only: new Set<string>(), title: '📐 Pattern matched (4 · 0 enterable)' });
    expect(container.querySelector('section')).toBeNull();
    expect(screen.queryByText(/Pattern matched/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: the allow-list narrows, it never ADDS a name the grid never had', () => {
    // A symbol that is not in the verdict cache at all cannot conjure a card.
    draw({ only: new Set(['RDY', 'GHOST', 'NOPAT']) });
    expect(drawn()).toEqual(['RDY']);
  });

  it('NEGATIVE: `filterSources` still applies on top of the allow-list', () => {
    // Both survive `only`; only the 💼 holding survives the source filter.
    draw({ only: new Set(['RDY', 'WCH']), filterSources: ['holding'] });
    expect(screen.getByText('RDY')).toBeInTheDocument();
    expect(screen.queryByText('WCH')).not.toBeInTheDocument();
  });
});
