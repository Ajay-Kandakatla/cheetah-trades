import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HotSectors, { chipLabel, scanStamp } from './HotSectors';

const PAYLOAD = {
  as_of: '2026-08-31', start: '2026-06-01', benchmark: 'RSP',
  ranked_by: 'rel_21d',
  in: [
    { group: 'Technology · large caps', sector: 'Technology', tier: 'large',
      index: 'S&P 500', n: 25, rel_21d: 5.7, rel_window: -8.17 },
    { group: 'Energy · small caps', sector: 'Energy', tier: 'small',
      index: 'S&P 600', n: 25, rel_21d: 5.11, rel_window: 6.32 },
  ],
  out: [
    { group: 'Real Estate · small caps', sector: 'Real Estate', tier: 'small',
      index: 'S&P 600', n: 25, rel_21d: -7.44, rel_window: -2.39 },
  ],
};

function stub(body: any, ok = true) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok, status: ok ? 200 : 503, json: () => Promise.resolve(body),
  } as any));
}

const draw = () => render(<MemoryRouter><HotSectors /></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('HotSectors', () => {
  it('renders cohort chips with signed 21-day numbers', async () => {
    stub(PAYLOAD);
    draw();
    await waitFor(() =>
      expect(screen.getByText('Technology · large caps +5.7%')).toBeTruthy());
    expect(screen.getByText('Energy · small caps +5.1%')).toBeTruthy();
    expect(screen.getByText('Real Estate · small caps -7.4%')).toBeTruthy();
    expect(screen.getByText(/money in/i)).toBeTruthy();
    expect(screen.getByText(/money out/i)).toBeTruthy();
    expect(screen.getByText(/vs RSP/)).toBeTruthy();
  });

  it('links to the full rotation page', async () => {
    stub(PAYLOAD);
    draw();
    await waitFor(() => expect(screen.getByText(/full rotation/)).toBeTruthy());
    expect(screen.getByRole('link', { name: /full rotation/ }))
      .toHaveAttribute('href', '/rotation');
  });

  it('renders NOTHING on error — a strip must never break its page', async () => {
    stub({ error: 'boom' }, false);
    const { container } = draw();
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector('.hs')).toBeNull();
  });

  it('renders nothing while loading and nothing when empty', async () => {
    stub({ in: [], out: [] });
    const { container } = draw();
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector('.hs')).toBeNull();
  });

  it('chipLabel never prints "null%"', () => {
    expect(chipLabel({ group: 'X', rel_21d: null })).toBe('X');
    expect(chipLabel({ group: 'X', rel_21d: 2.15 })).toBe('X +2.1%');
    expect(chipLabel({ group: 'X', rel_21d: -0.24 })).toBe('X -0.2%');
  });
});


/* ── the scan stamp (Ajay 2026-09-06: "make ... Hot sectors part of the scans") ── */
describe('scanStamp — the strip says which scan built it', () => {
  it('prints the ET clock of a scan-built strip and nothing for a live build', () => {
    expect(scanStamp({ source: 'scan', built_at_iso: '2026-09-04T16:41:12-04:00' })).toBe('16:41');
    expect(scanStamp({ source: 'live', built_at_iso: '2026-09-04T16:41:12-04:00' })).toBe('');
    expect(scanStamp({ source: 'scan', built_at_iso: null })).toBe('');
    expect(scanStamp({ source: 'scan', built_at_iso: 'garbage' })).toBe('');
    expect(scanStamp({})).toBe('');
  });
});


/* ── industry cohorts on the strip (Ajay 2026-09-09) ────────────────────────
 * "increase our sectors ... money got moved in to technology too from Semis
 *  or reduced in semis today."
 * The sector row cannot show this: on 2026-09-09 Technology read -4.72 while
 * Semiconductors was -13.32 over 63 days and Software-Infrastructure +19.10.
 * These pin that the finer rows render, and that the strip still degrades to
 * nothing rather than breaking the page it rides on. */
describe('HotSectors — industry cohorts (2026-09-09)', () => {
  const withIndustries = {
    as_of: '2026-09-09', benchmark: 'RSP', source: 'scan' as const,
    built_at_iso: '2026-09-09T16:31:50-04:00',
    in: [{ group: 'Energy · large caps', n: 40, rel_21d: 8.61 }],
    out: [{ group: 'Technology · large caps', n: 40, rel_21d: -4.72 }],
    industries_in: [
      { group: 'Oil & Gas E&P', sector: 'Energy', n: 25, rel_21d: 9.22, rel_63d: 8.74 },
      { group: 'Gold', sector: 'Basic Materials', n: 10, rel_21d: 14.25, rel_63d: 25.61 },
    ],
    industries_out: [
      { group: 'Semiconductors', sector: 'Technology', n: 25, rel_21d: -1.95, rel_63d: -13.32 },
      { group: 'Aerospace & Defense', sector: 'Industrials', n: 25, rel_21d: -12.13, rel_63d: -8.36 },
    ],
  };

  it('renders the finer rows with their numbers beside the sector rows', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(withIndustries) } as Response)));
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    expect(await screen.findByText(/Oil & Gas E&P \+9\.2%/)).toBeInTheDocument();
    expect(screen.getByText(/^Semiconductors -[12]\.\d%$/)).toBeInTheDocument();
    expect(screen.getByText('industry in')).toBeInTheDocument();
    expect(screen.getByText('industry out')).toBeInTheDocument();
    // the sector rows are still there — the finer grain ADDS, never replaces
    expect(screen.getByText(/Energy · large caps/)).toBeInTheDocument();
  });

  it('says which sector an industry sits inside, so the split is legible', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(withIndustries) } as Response)));
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    const chip = await screen.findByText(/^Semiconductors -[12]\.\d%$/);
    expect(chip.getAttribute('title')).toMatch(/inside Technology/);
    expect(chip.getAttribute('title')).toMatch(/-13\.32% rel/);
  });

  it('NEGATIVE: an old payload with no industry keys still renders the strip', async () => {
    const legacy = { ...withIndustries, industries_in: undefined, industries_out: undefined };
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(legacy) } as Response)));
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    expect(await screen.findByText(/Energy · large caps/)).toBeInTheDocument();
    expect(screen.queryByText('industry in')).not.toBeInTheDocument();
  });

  it('NEGATIVE: industries alone (no sector rows) still render', async () => {
    const only = { ...withIndustries, in: [], out: [] };
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(only) } as Response)));
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    expect(await screen.findByText(/Gold \+14\.3%/)).toBeInTheDocument();
  });
});
