/* 🌀 AMD grade filter (Ajay 2026-09-17).
 *
 * "I think the AMD is my priority honestly. I wanna see all AMD and also
 * filterable AMD ... I wanna know any new stocks are are are getting
 * manipulated and about to be Distrubuted too ... Feel free to bring stocks
 * that are getting distributed too but I need to see it as a filter."
 *
 * The sweep stores every name at every grade; this tab served only the turning
 * one. The chips must never ask for an empty board, never hide a grade the
 * server offers, and never move a count because a chip is off.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import { parseGrades, gradesParam, boardQuery, AMD_GRADE_LABEL } from '../lib/chartMaps';

const GRADES_ALL = ['marked_up', 'raided', 'stale', 'failed', 'basing'];
const COUNTS = { marked_up: 448, raided: 391, stale: 196, failed: 1002, basing: 641 };

const TILE = {
  symbol: 'ZZZA', name: 'Zed Corp', href: '/sepa/ZZZA',
  price: 10.2, chg_pct: 0.4,
  bars: Array.from({ length: 30 }, (_, i) => ({
    t: `2026-02-${String(i + 1).padStart(2, '0')}`,
    o: 9 + i * 0.05, h: 9.4 + i * 0.05, l: 8.9 + i * 0.05, c: 9.2 + i * 0.05, v: 2e6,
  })),
  bands: [{ kind: 'amd_accumulation', lo: 9.4, hi: 12.0 }],
  lines: [], markers: [], badges: [], stats: [],
  why: 'the raid means the stops under the base are gone',
  last_close: 10,
  amd_read: {
    grade: 'raided', phase: 'manipulation',
    raid_low: 9.1, raid_level: 9.4, distribution_level: 12.0,
    above_raid_low_pct: 9.89, to_distribution_pct: 20.0,
  },
};

const BOARD = (over: Record<string, unknown> = {}) => ({
  tab: 'amd', count: 1, matched: 391, scanned: 2678, tiles: [TILE],
  grades: ['raided'], grades_all: GRADES_ALL, grade_counts: COUNTS,
  note: 'measured INVERTED against a placebo', disclaimer: 'Study board.',
  ...over,
});

const urls: string[] = [];
function stub(board: Record<string, unknown>) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps')) {
      urls.push(url);
      return { ok: true, json: async () => board } as unknown as Response;
    }
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}

beforeEach(() => { urls.length = 0; vi.restoreAllMocks(); });
afterEach(() => { cleanup(); });

const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /></MemoryRouter>);

describe('parseGrades / gradesParam', () => {
  it('round-trips a selection', () => {
    expect(gradesParam(parseGrades('raided,basing'))).toBe('basing,raided');
  });
  it('NEGATIVE: nothing selected rides NO param — the server default, not an empty board', () => {
    expect(gradesParam(new Set())).toBeNull();
    expect(parseGrades('').size).toBe(0);
    expect(parseGrades(null).size).toBe(0);
    expect(parseGrades(undefined).size).toBe(0);
  });
  it('collapses a full selection to "all" when told the universe', () => {
    expect(gradesParam(new Set(GRADES_ALL), GRADES_ALL)).toBe('all');
  });
  it('NEGATIVE: junk is just an unmatched key, never a crash', () => {
    expect(() => parseGrades('%%%,,,')).not.toThrow();
    expect(gradesParam(parseGrades('%%%'))).toBe('%%%');
  });
  it('NEGATIVE: grades ride only on the tabs that have them', () => {
    expect(boardQuery({ tab: 'amd', grades: 'all' })).toContain('grades=all');
    expect(boardQuery({ tab: 'keltner', grades: 'all' })).toContain('grades=all');
    expect(boardQuery({ tab: 'zones', grades: 'all' })).not.toContain('grades');
    expect(boardQuery({ tab: 'amd' })).not.toContain('grades');
  });
});

describe('the chips', () => {
  it('renders every grade the SERVER offers, with its sweep count', async () => {
    vi.stubGlobal('fetch', stub(BOARD()));
    page('/chart-maps?tab=amd');
    const ctl = await screen.findByRole('tablist', { name: 'AMD grade' });
    for (const g of GRADES_ALL) {
      const chip = within(ctl).getByTestId(`amd-grade-${g}`);
      expect(chip).toHaveTextContent(String(COUNTS[g as keyof typeof COUNTS]));
      expect(chip).toHaveTextContent(AMD_GRADE_LABEL[g].replace(/^\S+\s/, ''));
    }
    expect(within(ctl).getAllByRole('tab')).toHaveLength(GRADES_ALL.length);
  });

  it('picking Distributed asks the server for it', async () => {
    vi.stubGlobal('fetch', stub(BOARD()));
    page('/chart-maps?tab=amd');
    const ctl = await screen.findByRole('tablist', { name: 'AMD grade' });
    fireEvent.click(within(ctl).getByTestId('amd-grade-marked_up'));
    await waitFor(() =>
      expect(urls.some((u) => u.includes('tab=amd') && u.includes('grades=marked_up'))).toBe(true));
  });

  it('NEGATIVE: unpicking the last chip asks for NO grades param at all', async () => {
    vi.stubGlobal('fetch', stub(BOARD()));
    page('/chart-maps?tab=amd&grades=raided');
    const ctl = await screen.findByRole('tablist', { name: 'AMD grade' });
    urls.length = 0;
    fireEvent.click(within(ctl).getByTestId('amd-grade-raided'));
    await waitFor(() => expect(urls.length).toBeGreaterThan(0));
    expect(urls.every((u) => !u.includes('grades='))).toBe(true);
  });

  it('NEGATIVE: a grade the label map has never seen still gets a chip', async () => {
    vi.stubGlobal('fetch', stub(BOARD({
      grades_all: [...GRADES_ALL, 'brand_new'],
      grade_counts: { ...COUNTS, brand_new: 7 },
    })));
    page('/chart-maps?tab=amd');
    const ctl = await screen.findByRole('tablist', { name: 'AMD grade' });
    expect(within(ctl).getByTestId('amd-grade-brand_new')).toHaveTextContent('brand_new');
  });

  it('NEGATIVE: no grades_all from the server renders no control at all', async () => {
    vi.stubGlobal('fetch', stub(BOARD({ grades_all: [], grade_counts: {} })));
    page('/chart-maps?tab=amd');
    await screen.findByText('ZZZA');
    expect(screen.queryByRole('tablist', { name: 'AMD grade' })).toBeNull();
  });

  it('NEGATIVE: the control does not appear on a tab that has no grades', async () => {
    vi.stubGlobal('fetch', stub(BOARD({ grades_all: GRADES_ALL })));
    page('/chart-maps?tab=zones');
    await screen.findByText('ZZZA');
    expect(screen.queryByRole('tablist', { name: 'AMD grade' })).toBeNull();
  });

  it('a grade with zero names is dimmed but still clickable — never hidden', async () => {
    vi.stubGlobal('fetch', stub(BOARD({ grade_counts: { ...COUNTS, stale: 0 } })));
    page('/chart-maps?tab=amd');
    const ctl = await screen.findByRole('tablist', { name: 'AMD grade' });
    const chip = within(ctl).getByTestId('amd-grade-stale');
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveAttribute('aria-disabled', 'true');
    fireEvent.click(chip);   // must not throw
  });
});

/* ── 🔻 the cycle IN FLIGHT ──────────────────────────────────────────────────
 * "Today its not granular we do not show potentially or in the flight mani
 * pulation i wanna see those." Live states, unconfirmed until the close. */
const FLIGHT_STATES = ['sweeping', 'reclaimed', 'holding'];
const FLIGHT_COUNTS = { sweeping: 172, reclaimed: 156, holding: 880 };
const FBOARD = (over: Record<string, unknown> = {}) =>
  BOARD({ flight: [], flight_states: FLIGHT_STATES, flight_counts: FLIGHT_COUNTS, ...over });

describe('the in-flight chips', () => {
  it('renders every live state with its live count', async () => {
    vi.stubGlobal('fetch', stub(FBOARD()));
    page('/chart-maps?tab=amd');
    const ctl = await screen.findByRole('tablist', { name: 'In flight' });
    for (const k of FLIGHT_STATES) {
      expect(within(ctl).getByTestId(`amd-flight-${k}`))
        .toHaveTextContent(String(FLIGHT_COUNTS[k as keyof typeof FLIGHT_COUNTS]));
    }
  });

  it('picking "Reclaimed today" asks the server for it', async () => {
    vi.stubGlobal('fetch', stub(FBOARD()));
    page('/chart-maps?tab=amd');
    const ctl = await screen.findByRole('tablist', { name: 'In flight' });
    fireEvent.click(within(ctl).getByTestId('amd-flight-reclaimed'));
    await waitFor(() =>
      expect(urls.some((u) => u.includes('flight=reclaimed'))).toBe(true));
  });

  it('says out loud that nothing in flight is confirmed', async () => {
    vi.stubGlobal('fetch', stub(FBOARD()));
    page('/chart-maps?tab=amd');
    const ctl = await screen.findByRole('tablist', { name: 'In flight' });
    const title = ctl.getAttribute('title') || '';
    expect(title).toMatch(/not closed|unconfirmed|forming/i);
  });

  it('NEGATIVE: selecting every state rides NO param — same board as no filter', async () => {
    vi.stubGlobal('fetch', stub(FBOARD()));
    page(`/chart-maps?tab=amd&flight=${FLIGHT_STATES.slice(0, 2).join(',')}`);
    const ctl = await screen.findByRole('tablist', { name: 'In flight' });
    urls.length = 0;
    fireEvent.click(within(ctl).getByTestId('amd-flight-holding'));
    await waitFor(() => expect(urls.length).toBeGreaterThan(0));
    expect(urls.every((u) => !u.includes('flight='))).toBe(true);
  });

  it('NEGATIVE: the control is absent on tabs with no flight read', async () => {
    vi.stubGlobal('fetch', stub(FBOARD()));
    page('/chart-maps?tab=keltner');
    await screen.findByText('ZZZA');
    expect(screen.queryByRole('tablist', { name: 'In flight' })).toBeNull();
  });

  it('NEGATIVE: no flight_states from the server renders no control', async () => {
    vi.stubGlobal('fetch', stub(BOARD({ flight_states: [] })));
    page('/chart-maps?tab=amd');
    await screen.findByText('ZZZA');
    expect(screen.queryByRole('tablist', { name: 'In flight' })).toBeNull();
  });

  it('boardQuery sends flight only on the amd tab', () => {
    expect(boardQuery({ tab: 'amd', flight: 'sweeping' })).toContain('flight=sweeping');
    expect(boardQuery({ tab: 'keltner', flight: 'sweeping' })).not.toContain('flight');
    expect(boardQuery({ tab: 'zones', flight: 'sweeping' })).not.toContain('flight');
  });
});
