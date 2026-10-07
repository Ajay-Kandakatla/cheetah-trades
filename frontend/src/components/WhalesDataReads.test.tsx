import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

/* Whales data-read defects (2026-10-06).
 *
 *  1. EDGAR renamed the 5% forms "SC 13D/G" → "SCHEDULE 13D/G" (Dec 2024).
 *     The SEC-activity modal must label both generations as 13D / 13G.
 *  2. major_holders now parses (yfinance 1.2.0 index-keyed frame), so the
 *     "Institutional held / Insider / out of N reporting funds" lines render.
 *     A count of 0 or a missing count must not print "0".
 *  3. moves.n_new / n_sold_out are null (unknown) — never printed as 0.
 */

vi.mock('./GiantsRotationModal', () => ({ GiantsRotationModal: () => null }));
vi.mock('../hooks/useWhalesFlow', () => ({ patchWhalesFlowRow: vi.fn() }));

const whalesState: { data: any } = { data: null };
vi.mock('../hooks/useSupplyDemand', () => ({
  useNodeThesis: () => ({ data: null, loading: false }),
  useWhales: () => ({ data: whalesState.data, loading: false }),
}));

import { WhalesFlowModal } from './WhalesFlowModal';
import { Whales13DModal } from './Whales13DModal';
import { NodeThesisPanel } from './NodeThesisPanel';

const mover = (holder: string, pc: number) => ({ holder, pct_change: pc, type: 'other', value: 1e9, pct_held: 0.01 });

function whalesPayload(over: Record<string, any> = {}) {
  return {
    ticker: 'VST',
    n_holders: 10,
    major: {
      insider_pct: '0.78%', institutional_pct: '92.02%',
      institutional_float_pct: '92.74%', n_institutions: 1881,
    },
    moves: {
      net_signal: 'accumulating', n_buying: 6, n_selling: 2, n_unchanged: 2,
      n_new: null, n_sold_out: null,
      notable_buys: [mover('ALPHA FUND', 0.2)], notable_sells: [mover('BETA FUND', -0.3)],
    },
    period: null,
    ...over,
  };
}

function stubFetch(body: any) {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(body) })));
}

afterEach(() => { vi.unstubAllGlobals(); whalesState.data = null; });

describe('WhalesFlowModal — major holders + unknown counts', () => {
  it('renders institutional %, insider % and the reporting-fund count', async () => {
    stubFetch(whalesPayload());
    render(<WhalesFlowModal symbol="VST" onClose={() => {}} />);
    await waitFor(() => expect(document.body.textContent).toContain('Institutional held'));
    const txt = document.body.textContent || '';
    expect(txt).toContain('92.02%');
    expect(txt).toContain('Insider');
    expect(txt).toContain('0.78%');
    expect(txt).toContain('out of 1881 reporting funds');
  });

  it('NEGATIVE: empty major ({}) shows no holder lines and no "out of" count', async () => {
    stubFetch(whalesPayload({ major: {} }));
    render(<WhalesFlowModal symbol="VST" onClose={() => {}} />);
    await waitFor(() => expect(document.body.textContent).toContain('6 buying'));
    const txt = document.body.textContent || '';
    expect(txt).not.toContain('Institutional held');
    expect(txt).not.toContain('reporting funds');
  });

  it.each([0, '0'])('NEGATIVE: a %j fund count never prints "out of 0"', async (n) => {
    // '0' = the legacy string shape older yfinance rows produced.
    stubFetch(whalesPayload({ major: { institutional_pct: '92.02%', n_institutions: n } }));
    render(<WhalesFlowModal symbol="VST" onClose={() => {}} />);
    await waitFor(() => expect(document.body.textContent).toContain('6 buying'));
    expect(document.body.textContent).not.toContain('out of 0');
  });

  it('NEGATIVE: null n_new / n_sold_out are not printed as zeros', async () => {
    stubFetch(whalesPayload());
    render(<WhalesFlowModal symbol="VST" onClose={() => {}} />);
    await waitFor(() => expect(document.body.textContent).toContain('6 buying'));
    const txt = document.body.textContent || '';
    expect(txt).not.toMatch(/\b0 new\b/i);
    expect(txt).not.toMatch(/sold out/i);
    expect(txt).not.toContain('null');
  });
});

describe('Whales13DModal — both 13D/G naming generations', () => {
  const filing = (form: string, date: string) => ({
    form, filing_date: date, accession_number: `${form}-${date}`,
    primary_doc_url: 'https://www.sec.gov/x', bucket: 'form13',
  });

  it('labels SCHEDULE 13G / 13G/A like SC 13G, under the 5% section', async () => {
    stubFetch({
      ticker: 'VST', window_days: 120, n_filings: 3, n_form4: 0, n_form144: 0, n_form13: 3,
      filings: [filing('SCHEDULE 13G', '2026-08-07'), filing('SCHEDULE 13D/A', '2026-07-01'),
                filing('SC 13G/A', '2026-06-20')],
    });
    render(<Whales13DModal symbol="VST" onClose={() => {}} />);
    await waitFor(() => expect(document.body.textContent).toContain('SCHEDULE 13G'));
    const txt = document.body.textContent || '';
    expect(txt).toContain('5% ownership threshold');
    expect(txt).toContain('📑 SCHEDULE 13G');
    expect(txt).toContain('📜 SCHEDULE 13D/A');
    expect(txt).toContain('📑 SC 13G/A');
  });

  it('NEGATIVE: an unrelated schedule (13E3) does not get a 13D/G icon', async () => {
    stubFetch({
      ticker: 'VST', window_days: 120, n_filings: 1, n_form13: 1,
      filings: [filing('SCHEDULE 13E3', '2026-08-07')],
    });
    render(<Whales13DModal symbol="VST" onClose={() => {}} />);
    await waitFor(() => expect(document.body.textContent).toContain('SCHEDULE 13E3'));
    const txt = document.body.textContent || '';
    expect(txt).toContain('📄 SCHEDULE 13E3');
    expect(txt).not.toContain('📜 SCHEDULE 13E3');
    expect(txt).not.toContain('📑 SCHEDULE 13E3');
  });
});

describe('NodeThesisPanel — major holders line', () => {
  const renderPanel = () => render(
    <MemoryRouter><NodeThesisPanel ticker="VST" onClose={() => {}} /></MemoryRouter>,
  );

  it('renders Inst held, Insider and the fund count from the parsed major block', () => {
    whalesState.data = whalesPayload();
    renderPanel();
    const line = document.querySelector('.ntp-major');
    expect(line?.textContent).toContain('Inst held: 92.02%');
    expect(line?.textContent).toContain('Insider: 0.78%');
    expect(line?.textContent).toContain('1881 funds');
  });

  it('NEGATIVE: a 0 fund count is hidden, not printed as "0"', () => {
    whalesState.data = whalesPayload({ major: { institutional_pct: '92.02%', n_institutions: 0 } });
    renderPanel();
    const line = document.querySelector('.ntp-major');
    expect(line?.textContent).toBe('Inst held: 92.02%');
    expect(screen.queryByText(/funds$/)).toBeNull();
  });

  it('NEGATIVE: empty major renders no holder line at all', () => {
    whalesState.data = whalesPayload({ major: {} });
    renderPanel();
    expect(document.querySelector('.ntp-major')).toBeNull();
  });
});
