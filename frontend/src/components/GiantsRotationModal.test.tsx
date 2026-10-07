/* Giants 13F rotation — stale funds are NAMED, never mixed in (2026-10-06).
 *
 * Greenlight last filed Q4 2023, Scion Q3 2025, Pershing Square filed a
 * 13F-NT for Q2 2026 — the rotation used to diff their old filings as if
 * current and its header read "Q4 2023". The backend now leaves them out
 * and lists them; this pins how the line reads.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { GiantsRotationModal, staleFundsText, type StaleFund } from './GiantsRotationModal';

const STALE: StaleFund[] = [
  { fund: 'Pershing Sq', latest_quarter: 'Q1 2026',
    reason: 'filed a 13F-NT for Q2 2026 (holdings reported by another manager)' },
  { fund: 'Greenlight', latest_quarter: 'Q4 2023', reason: 'not filed for Q2 2026 (latest Q4 2023)' },
  { fund: 'ValueAct', latest_quarter: null, reason: 'no 13F-HR on file' },
  { fund: 'Gappy', latest_quarter: 'Q2 2026', reason: 'no Q1 2026 filing to compare against' },
];

describe('staleFundsText', () => {
  it('names every left-out fund with why', () => {
    expect(staleFundsText(STALE, 'Q2 2026')).toBe(
      'Not filed for Q2 2026: Pershing Sq (13F-NT) · Greenlight (last Q4 2023) · '
      + 'ValueAct (none on file) · Gappy (no prior quarter)');
  });

  it('NEGATIVE: nothing to say when every fund filed', () => {
    expect(staleFundsText([], 'Q2 2026')).toBeNull();
    expect(staleFundsText(undefined, 'Q2 2026')).toBeNull();
    expect(staleFundsText(null, null)).toBeNull();
  });
});

describe('GiantsRotationModal', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  const payload = (stale: StaleFund[]) => ({
    symbol: 'VST', quarter: 'Q2 2026', n_funds_checked: 38, n_funds_current: 34,
    stale_funds: stale,
    sellers: [{ fund: 'Citadel', name: 'Citadel Advisors LLC', tier: 'S', style: 'quant',
                manager: 'Ken Griffin', quarter: 'Q2 2026', delta_usd: -63_878_874,
                action: 'trim', pct_change_shares: -50.7, position_now_usd: 62_000_000,
                their_top_adds: [] }],
    buyers: [],
  });

  it('header shows the dominant quarter and the stale line lists the funds', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(payload(STALE)) })));
    render(<GiantsRotationModal symbol="VST" onClose={() => {}} />);
    expect(await screen.findByText('Q2 2026 filings')).toBeTruthy();
    expect(screen.getByText(/Greenlight \(last Q4 2023\)/)).toBeTruthy();
    expect(screen.getByText(/Citadel/)).toBeTruthy();
    // NEGATIVE: the stale fund's quarter never becomes the header
    expect(screen.queryByText('Q4 2023 filings')).toBeNull();
  });

  it('NEGATIVE: no stale line when every fund filed', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(payload([])) })));
    render(<GiantsRotationModal symbol="VST" onClose={() => {}} />);
    expect(await screen.findByText('Q2 2026 filings')).toBeTruthy();
    expect(screen.queryByText(/Not filed for/)).toBeNull();
  });
});
