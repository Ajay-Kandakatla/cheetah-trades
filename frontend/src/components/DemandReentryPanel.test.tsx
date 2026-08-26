/* DemandReentryPanel — universe-provenance banners.
 *
 * The panel claims "S&P 500" in its heading, its button, and its empty state.
 * These tests lock the two ways that claim can be false, because each one
 * degrades differently and must be reported differently:
 *
 *   1. WRONG UNIVERSE — fetch_sp500() fell through to the 158-name curated
 *      list. Loud red error; the names are not the S&P 500 at all.
 *   2. STALE UNIVERSE (the 2026-08-13 hole) — the real constituents, but
 *      frozen on the day the live fetch broke. `universe_is_sp500` stays true,
 *      so case 1's banner never fires and the list aged 76 days in silence.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { DemandReentryPanel } from './DemandReentryPanel';

type Overrides = Record<string, unknown>;

function payload(over: Overrides = {}) {
  return {
    rows: [],
    n: 0,
    scanned: 503,
    universe: 503,
    universe_note: 'S&P 500 constituents (503 names)',
    universe_is_sp500: true,
    universe_stale_days: null,
    universe_source: 'wikipedia',
    took_sec: 12.3,
    as_of: '2026-08-13T12:00:00+00:00',
    cached: false,
    disclaimer: 'Not advice.',
    ...over,
  };
}

function mockFetch(over: Overrides = {}) {
  const fn = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => payload(over),
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe('DemandReentryPanel — universe provenance', () => {
  it('says nothing about provenance when the list is fresh', async () => {
    mockFetch();
    render(<DemandReentryPanel />);

    await waitFor(() => expect(screen.getByText(/503 scanned/)).toBeInTheDocument());
    // NEGATIVE: neither banner may fire on the happy path.
    expect(screen.queryByText(/NOT the full universe/)).not.toBeInTheDocument();
    expect(screen.queryByText(/days old/)).not.toBeInTheDocument();
  });

  it('warns loudly when the scan fell through to the curated list', async () => {
    mockFetch({
      universe_is_sp500: false,
      universe_source: 'curated',
      universe: 158,
      scanned: 158,
      universe_note: 'S&P 500 unavailable — scanned the curated list instead',
    });
    render(<DemandReentryPanel />);

    await waitFor(() =>
      expect(screen.getByText(/NOT the full universe/)).toBeInTheDocument());
  });

  it('reports a stale-but-real constituent list with its age', async () => {
    /* THE REGRESSION: universe_is_sp500 is TRUE here — these really are the
     * S&P 500 names — so the curated-fallback banner correctly stays silent.
     * Without its own banner the page said nothing at all while the list drifted. */
    mockFetch({
      universe_is_sp500: true,
      universe_source: 'stale-cache',
      universe_stale_days: 76,
    });
    render(<DemandReentryPanel />);

    await waitFor(() =>
      expect(screen.getByText(/76 days old/)).toBeInTheDocument());
    expect(screen.getByText(/live S&P 500 fetch is failing/)).toBeInTheDocument();
    // It must NOT masquerade as the wrong-universe error — different failure.
    expect(screen.queryByText(/NOT the full universe/)).not.toBeInTheDocument();
  });

  it('keeps a mildly stale list muted and escalates a badly stale one', async () => {
    mockFetch({ universe_source: 'stale-cache', universe_stale_days: 40 });
    const mild = render(<DemandReentryPanel />);
    await waitFor(() => expect(screen.getByText(/40 days old/)).toBeInTheDocument());
    expect(screen.getByText(/40 days old/).closest('div'))
      .not.toHaveClass('sepa-err');
    mild.unmount();

    mockFetch({ universe_source: 'stale-cache', universe_stale_days: 200 });
    render(<DemandReentryPanel />);
    await waitFor(() => expect(screen.getByText(/200 days old/)).toBeInTheDocument());
    expect(screen.getByText(/200 days old/).closest('div')).toHaveClass('sepa-err');
  });

  it('survives a payload from an older backend with no provenance fields', async () => {
    /* NEGATIVE: the API and frontend deploy separately. A payload predating
     * universe_stale_days must render normally, not crash or show "undefined
     * days old". */
    const fn = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => {
        const p = payload() as Record<string, unknown>;
        delete p.universe_stale_days;
        delete p.universe_source;
        return p;
      },
    });
    vi.stubGlobal('fetch', fn);
    render(<DemandReentryPanel />);

    await waitFor(() => expect(screen.getByText(/503 scanned/)).toBeInTheDocument());
    expect(screen.queryByText(/days old/)).not.toBeInTheDocument();
  });
});
