import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BondeBoard, { type BondeBoardData } from './BondeBoard';
import { CM_TABS, TAB_META, isBoardTab, parseTab } from '../lib/chartMaps';

/* 📈 Bonde tab (Ajay 2026-09-13). The negatives matter most: this board shows
 * percentages off revenue bases that can be negative or immaterial, and an
 * empty headline section that has a structural cause. Each of those reads as
 * something it is not unless the board says otherwise. */

const row = (symbol: string, over: Partial<any> = {}) => ({
  symbol, name: `${symbol} Inc`, tier: 'explosive',
  growth_yoy_pct: 120, base_rev: 5_000_000, latest_rev: 11_000_000,
  rev_added: 6_000_000, base_state: 'ok', sales_score: 100,
  accelerating: true, consecutive_growth_q: 4, sales_led: true,
  pivot: null, is_new: false, ...over,
});

const payload = (over: Partial<BondeBoardData> = {}): BondeBoardData => ({
  sections: { pivot: [], explosive: [row('PTGX')], strong: [], steady: [] },
  counts: { pivot: 0, explosive: 69, strong: 304, steady: 677 },
  caps: { pivot: 60, explosive: 60, strong: 60, steady: 40 },
  n_pass: 1051, n_scanned: 2076, n_new: 0, new_days: 30,
  regime: { is_bull: false, label: 'market_in_correction', score: 66.5, scanners_paused: true },
  note: 'note', ...over,
});

const draw = (d: BondeBoardData) => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => d } as any)));
  return render(<MemoryRouter><BondeBoard /></MemoryRouter>);
};

beforeEach(() => vi.unstubAllGlobals());

describe('the tab is registered as a non-tile board', () => {
  it('is in CM_TABS with copy, and is not a tile board', () => {
    expect(CM_TABS).toContain('bonde');
    expect(TAB_META.bonde.label).toMatch(/Bonde/);
    expect(isBoardTab('bonde')).toBe(false);
    expect(parseTab('bonde')).toBe('bonde');
  });

  it('the blurb states WHOSE numbers are whose', () => {
    // His 5/25/100 tiers are documented in his own writing; the Pivot's 8%/5x
    // and the $1M base floor are this app's. A board that blurs that is
    // attributing thresholds to him that he never published.
    const b = TAB_META.bonde.blurb;
    expect(b).toMatch(/sales_confidence_methodology/);
    expect(b).toMatch(/THIS APP’S owner settings/);
    expect(b).toMatch(/1,051 of 2,076/);
    expect(b).toMatch(/DECLINING sales/);
  });
});

describe('the board', () => {
  it('leads with how many pass and how many are NEW', async () => {
    draw(payload());
    expect(await screen.findByText(/pass his screen/)).toBeInTheDocument();
    expect(screen.getByText('1,051')).toBeInTheDocument();
    expect(screen.getByText(/new in 30d/)).toBeInTheDocument();
  });

  it('shows the growth percentage WITH the dollars behind it', async () => {
    // The percentage alone is the thing that can lie. $5.0M → $11.0M cannot.
    draw(payload());
    expect(await screen.findByText('+120%')).toBeInTheDocument();
    expect(screen.getByText(/\$5\.0M → \$11\.0M/)).toBeInTheDocument();
  });

  it('NEGATIVE — a negative base is flagged, not rendered as clean growth', async () => {
    draw(payload({ sections: { pivot: [], strong: [], steady: [],
      explosive: [row('DBRG', { growth_yoy_pct: 15961.5, base_rev: -3_207_000,
                                rev_added: null, base_state: 'non_positive' })] } }));
    const cell = await screen.findByText(/15962%|15961/);
    expect(cell.textContent).toMatch(/⚠/);
    expect(cell.getAttribute('title')).toMatch(/NEGATIVE/);
    expect(cell.getAttribute('title')).toMatch(/sign flip/);
  });

  it('NEGATIVE — an immaterial base says the floor is THIS APP’S, not Bonde’s', async () => {
    draw(payload({ sections: { pivot: [], strong: [], steady: [],
      explosive: [row('QUBT', { growth_yoy_pct: 9000, base_rev: 61_000,
                                base_state: 'too_small' })] } }));
    const cell = await screen.findByText(/9000%/);
    expect(cell.getAttribute('title')).toMatch(/not a Bonde number/);
  });

  it('explains an empty Pivots section instead of looking broken', async () => {
    draw(payload());
    expect(await screen.findByText(/Pivots are paused/)).toBeInTheDocument();
    expect(screen.getByText(/market in correction/)).toBeInTheDocument();
    expect(screen.getByText(/none — the scanners are paused/)).toBeInTheDocument();
  });

  it('NEGATIVE — says nothing about pausing when the scanners are running', async () => {
    draw(payload({ regime: { is_bull: true, label: 'confirmed_uptrend', scanners_paused: false } }));
    await screen.findByText(/pass his screen/);
    expect(screen.queryByText(/Pivots are paused/)).not.toBeInTheDocument();
  });

  it('the NEW filter narrows to arrivals and says so when there are none', async () => {
    draw(payload({ sections: { pivot: [], strong: [], steady: [],
      explosive: [row('AAA'), row('BBB', { is_new: true })] }, n_new: 1 }));
    await screen.findByText('AAA');
    fireEvent.click(screen.getByLabelText(/new arrivals only/i));
    await waitFor(() => expect(screen.queryByText('AAA')).not.toBeInTheDocument());
    expect(screen.getByText('BBB')).toBeInTheDocument();
    expect(screen.getAllByText(/no new arrivals in this tier/).length).toBeGreaterThan(0);
  });

  it('badges an arrival and says WHEN in the tooltip', async () => {
    draw(payload({ sections: { pivot: [], strong: [], steady: [],
      explosive: [row('CCC', { is_new: true, first_seen: '2026-09-10T12:00:00Z' })] } }));
    const badge = await screen.findByText('✨ NEW');
    expect(badge.getAttribute('title')).toMatch(/2026-09-10/);
  });

  it('shows the section total when the cap is hiding rows', async () => {
    draw(payload({ sections: { pivot: [], explosive: [], strong: [], steady: [row('DDD')] },
                   counts: { pivot: 0, explosive: 0, strong: 0, steady: 677 } }));
    expect(await screen.findByText(/1 of 677/)).toBeInTheDocument();
  });

  it('NEGATIVE — a failed fetch shows an error, not an empty board', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503 } as any)));
    render(<MemoryRouter><BondeBoard /></MemoryRouter>);
    expect(await screen.findByText(/⛔/)).toBeInTheDocument();
  });
});
