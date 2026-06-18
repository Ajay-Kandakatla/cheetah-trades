import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MacroCalendar } from './MacroCalendar';

/* MacroCalendar — the "what could move the regime" panel on the Market Gauge
   (regime) page. Ajay 2026-06-17: "pull any events that might affect the stock
   market like FOMC today." Locks: a tier-1 FOMC-today event surfaces as the
   next-mover banner + a row, the empty state is honest (no fake events), and a
   wrong-shaped payload renders NOTHING rather than crashing the gauge page. */

// Local date (NOT toISOString, which is UTC) — dLabel compares against local
// `new Date()`, so a UTC date would read as "tomorrow" in the evening westward.
const _n = new Date();
const TODAY = `${_n.getFullYear()}-${String(_n.getMonth() + 1).padStart(2, '0')}-${String(_n.getDate()).padStart(2, '0')}`;

const payload = (over: Record<string, unknown> = {}) => ({
  available: true,
  days: 14,
  tier_labels: { '1': 'Market movers', '2': 'Trend shapers', '3': 'Context' },
  tier_taxonomy: { '1': ['CPI', 'FOMC'], '2': ['ISM'], '3': ['Housing'] },
  regime_weighting: 'inflation + labor-strength prints carry the most weight',
  macro: [{ date: TODAY, kind: 'fomc', tier: 1, label: 'FOMC decision' }],
  next_tier1: { date: TODAY, kind: 'fomc', tier: 1, label: 'FOMC decision' },
  earnings_by_day: [],
  disclaimer: 'A heads-up on what could move the regime — not a forecast.',
  ...over,
});

const okFetch = (body: unknown) =>
  vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(body) });

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('MacroCalendar (regime page events)', () => {
  it('surfaces a tier-1 FOMC-today event as the next market-mover + a row', async () => {
    vi.stubGlobal('fetch', okFetch(payload()));
    render(<MacroCalendar />);
    await waitFor(() => expect(screen.getByText(/Next market-mover/i)).toBeInTheDocument());
    // FOMC named, labelled "today", and tagged tier 1.
    expect(screen.getAllByText(/FOMC decision/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/today/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText('T1').length).toBeGreaterThan(0);   // row badge + tier legend
  });

  it('shows an honest empty state when nothing is scheduled (negative)', async () => {
    vi.stubGlobal('fetch', okFetch(payload({ macro: [], next_tier1: null })));
    render(<MacroCalendar />);
    await waitFor(() => expect(screen.getByText(/No scheduled releases/i)).toBeInTheDocument());
    expect(screen.queryByText(/Next market-mover/i)).toBeNull();
  });

  it('renders nothing for a wrong-shaped payload — never crashes the gauge (negative)', async () => {
    vi.stubGlobal('fetch', okFetch({ available: true }));   // no `macro` array
    const { container } = render(<MacroCalendar />);
    // give the effect a tick; component must bail to null, not throw
    await new Promise((r) => setTimeout(r, 0));
    expect(container).toBeEmptyDOMElement();
  });
});
