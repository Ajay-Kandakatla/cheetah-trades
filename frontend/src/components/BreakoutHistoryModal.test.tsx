import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BreakoutHistoryModal, BreakoutHistoryBody } from './BreakoutHistoryModal';

/* BreakoutHistoryModal — the chart of WHERE each breakout fired (Ajay
   2026-06-15). Locks: it plots one marker per breakout, lists them, and the
   negatives (fetch failure → honest error, never a crash). */

const HISTORY = {
  ok: true, symbol: 'ROKU', last_close: 143.66, breakout_count: 3, window_bars: 252,
  avg_vol_50: 2_700_000,
  series: Array.from({ length: 60 }, (_, i) => ({
    date: `2025-${String(1 + Math.floor(i / 30)).padStart(2, '0')}-${String((i % 30) + 1).padStart(2, '0')}`,
    close: 80 + i, volume: 3_000_000,
  })),
  breakouts: [
    { date: '2025-01-05', close: 84, volume: 9_900_000, vol_ratio: 2.2 },
    { date: '2025-02-08', close: 119, volume: 12_000_000, vol_ratio: 3.1 },
    { date: '2025-02-27', close: 137, volume: 15_000_000, vol_ratio: 5.5 },
  ],
};

const okFetch = (body: unknown) =>
  vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(body) });

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('BreakoutHistoryModal', () => {
  it('charts one marker per breakout and lists them', async () => {
    vi.stubGlobal('fetch', okFetch(HISTORY));
    render(<BreakoutHistoryModal symbol="ROKU" onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/3 volume-confirmed breakouts/i)).toBeInTheDocument());
    // one <circle> marker per breakout point
    expect(document.querySelectorAll('circle')).toHaveLength(3);
    // the list shows the breakout dates
    expect(screen.getByText('🟢 02/27/25')).toBeInTheDocument();
    // cites the rule
    expect(screen.getByText(/p\.203/)).toBeInTheDocument();
  });

  it('shows an honest error when the fetch fails (negative)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')));
    render(<BreakoutHistoryModal symbol="ROKU" onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/Couldn't load breakout history/i)).toBeInTheDocument());
  });

  it('handles a name with zero breakouts without crashing (negative)', async () => {
    vi.stubGlobal('fetch', okFetch({ ...HISTORY, breakout_count: 0, breakouts: [] }));
    render(<BreakoutHistoryModal symbol="FLAT" onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/No volume-confirmed breakouts/i)).toBeInTheDocument());
    expect(document.querySelectorAll('circle')).toHaveLength(0);
  });
});

// ── "Whose hands?" footprint + emerging breakout (Ajay 2026-06-21) ───────────
const HISTORY_FP = {
  ...HISTORY,
  breakouts: [
    { date: '2025-01-05', close: 84, volume: 9_900_000, vol_ratio: 2.2,
      footprint: { hands: 'institutional', strength: 64, close_location: 0.7,
                   vol_ratio: 2.2, up_days: 6, down_days: 4, up_down_vol_ratio: 1.8, big_block: true } },
    { date: '2025-02-08', close: 119, volume: 12_000_000, vol_ratio: 3.1,
      footprint: { hands: 'heavy_institutional', strength: 81, close_location: 0.6,
                   vol_ratio: 3.1, up_days: 7, down_days: 3, up_down_vol_ratio: 2.4, big_block: true } },
    { date: '2025-02-27', close: 137, volume: 15_000_000, vol_ratio: 5.5,
      footprint: { hands: 'suspect', strength: 48, close_location: -0.5,
                   vol_ratio: 5.5, up_days: 6, down_days: 4, up_down_vol_ratio: 0.9, big_block: false } },
  ],
  emerging: { emerging: true, distance_to_high_pct: 1.4, pivot_price: 145.0,
              cmf: 0.18, up_down_vol_ratio: 1.7, pocket_pivot: true, hands: 'institutional', strength: 80 },
};

describe('BreakoutHistoryModal — whose hands / emerging', () => {
  it('colours each breakout by its footprint and labels churn', async () => {
    vi.stubGlobal('fetch', okFetch(HISTORY_FP));
    render(<BreakoutHistoryModal symbol="ROKU" onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/3 volume-confirmed breakouts/i)).toBeInTheDocument());
    // the suspect break is labelled as churn (appears in both the list + hover title)
    expect(screen.getAllByText(/Suspect — churn/).length).toBeGreaterThan(0);
    // and its marker is rendered amber (not the institutional green)
    const fills = [...document.querySelectorAll('circle')].map((c) => c.getAttribute('fill'));
    expect(fills).toContain('#f59e0b');   // suspect
    expect(fills).toContain('#34d399');   // institutional
  });

  it('shows the emerging "setting up now" callout + dashed ring (forward read)', async () => {
    vi.stubGlobal('fetch', okFetch(HISTORY_FP));
    render(<BreakoutHistoryModal symbol="ROKU" onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getAllByText(/Emerging breakout — setting up now/i).length).toBeGreaterThan(0));
    expect(screen.getAllByText(/1\.4% under the \$145/).length).toBeGreaterThan(0);
    // the hollow dashed emerging ring
    const dashed = [...document.querySelectorAll('circle')].some(
      (c) => c.getAttribute('stroke') === '#38bdf8' && c.getAttribute('fill') === 'none');
    expect(dashed).toBe(true);
  });

  it('omits the emerging callout when nothing is setting up (negative)', async () => {
    vi.stubGlobal('fetch', okFetch({ ...HISTORY_FP, emerging: { emerging: false } }));
    render(<BreakoutHistoryModal symbol="ROKU" onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/3 volume-confirmed breakouts/i)).toBeInTheDocument());
    expect(screen.queryByText(/Emerging breakout/i)).not.toBeInTheDocument();
  });
});

// The shared body powers the SEPA detail page's Breakout tab (no modal chrome).
describe('BreakoutHistoryBody (Breakout tab)', () => {
  it('renders the count + markers inline', async () => {
    vi.stubGlobal('fetch', okFetch(HISTORY));
    const { container } = render(<BreakoutHistoryBody symbol="ROKU" />);
    await waitFor(() =>
      expect(screen.getByText(/3 volume-confirmed breakouts/i)).toBeInTheDocument());
    expect(container.querySelectorAll('circle')).toHaveLength(3);   // inline, not a portal
  });

  it('shows an honest error on fetch failure (negative)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')));
    render(<BreakoutHistoryBody symbol="ROKU" />);
    await waitFor(() =>
      expect(screen.getByText(/Couldn't load breakout history/i)).toBeInTheDocument());
  });
});
