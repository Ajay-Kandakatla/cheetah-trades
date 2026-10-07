/* Giants 13F rotation — stale funds are NAMED, never mixed in (2026-10-06).
 *
 * Greenlight last filed Q4 2023, Scion Q3 2025, Pershing Square filed a
 * 13F-NT for Q2 2026 — the rotation used to diff their old filings as if
 * current and its header read "Q4 2023". The backend now leaves them out
 * and lists them; this pins how the line reads.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import {
  GiantsRotationModal, UnitsTag, cusipChangesText, staleFundsText, type StaleFund,
} from './GiantsRotationModal';

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

/* Critic round 2026-10-06: a retired → live CUSIP change (Honeywell's spin)
 * is named, never an exit; an undetermined VALUE unit carries a muted mark. */
describe('UnitsTag', () => {
  afterEach(() => cleanup());

  it('marks an undetermined VALUE unit', () => {
    render(<UnitsTag units="undetermined" />);
    expect(screen.getByText('units?')).toBeTruthy();
  });

  it('NEGATIVE: no mark for dollars, thousands (already scaled) or missing', () => {
    for (const u of ['dollars', 'thousands', null, undefined]) {
      render(<UnitsTag units={u} />);
      expect(screen.queryByText('units?')).toBeNull();
      cleanup();
    }
  });
});

describe('cusipChangesText', () => {
  it('names every fund with the note', () => {
    expect(cusipChangesText([
      { fund: 'Wellington', ticker: 'HON', note: 'CUSIP change / corporate action, not a decision' },
      { fund: 'Primecap', ticker: 'HON', note: 'CUSIP change / corporate action, not a decision' },
    ])).toBe('CUSIP change / corporate action, not a decision: Wellington · Primecap');
  });

  it('NEGATIVE: nothing when there are no changes', () => {
    expect(cusipChangesText([])).toBeNull();
    expect(cusipChangesText(undefined)).toBeNull();
  });
});

describe('GiantsRotationModal — CUSIP change + units', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  const hon = {
    symbol: 'HON', quarter: 'Q2 2026', n_funds_checked: 38, n_funds_current: 34, stale_funds: [],
    sellers: [{ fund: 'Trian', name: 'Trian Fund Mgmt', tier: 'A', style: 'activist', manager: '',
                quarter: 'Q2 2026', delta_usd: -5_000_000, action: 'trim', pct_change_shares: -10,
                position_now_usd: 45_000_000, value_units: 'undetermined', their_top_adds: [] }],
    buyers: [{ fund: 'Citadel', name: 'Citadel Advisors LLC', tier: 'S', style: 'quant', manager: '',
               quarter: 'Q2 2026', delta_usd: 34_100_000, action: 'new', pct_change_shares: null,
               position_now_usd: 34_100_000, value_units: 'dollars', their_top_trims: [] }],
    cusip_changes: [{ fund: 'Wellington', ticker: 'HON',
                      note: 'CUSIP change / corporate action, not a decision' }],
  };

  it('lists the CUSIP change and marks only the undetermined filer', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(hon) })));
    render(<GiantsRotationModal symbol="HON" onClose={() => {}} />);
    expect(await screen.findByText(/CUSIP change \/ corporate action, not a decision: Wellington/)).toBeTruthy();
    // exactly one mark: Trian (undetermined), NEGATIVE: not Citadel (dollars)
    expect(screen.getAllByText('units?')).toHaveLength(1);
    // NEGATIVE: the changed fund is not presented as a seller
    expect(screen.queryByText(/fully exited HON/)).toBeNull();
  });
});
