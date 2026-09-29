/* 🔥 Hottest — ⓘ Quality (Ajay 2026-09-28: "can you help with info icon on
 * the quality?").
 *
 * The explainer is SERVED (backend/sepa/earnings_quality_info.py, pinned
 * against earnings_quality.compute() by tests/test_earnings_quality_info.py).
 * This file pins that the board prints only what was served, opens it as an
 * un-clipped sheet, and never turns it into a claim about returns. The fixture
 * mirrors the §3.3 wire shape; the real payload is pinned separately. */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HottestSectors, HS_COLS } from './HottestSectors';
import { showQualityInfo, tierLabel } from './HottestQualityInfo';
import type { HsQualityInfo } from './HottestQualityInfo';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const QI: HsQualityInfo = {
  version: 1,
  title: 'Quality — how the 0–100 score is built',
  summary: 'A 0–100 read of how the last filed quarters\' earnings were built.',
  measured: false,
  measured_note: 'A description of the company\'s last filed quarters, not a measured predictor of returns: no study on this app has tested whether a higher Quality score leads to better forward returns.',
  weights_note: 'The point weights and most cut-offs are this app\'s own choices.',
  points: [
    { key: 'eps_level', label: 'EPS growth', max: 20, rule: 'rising evenly to the full 20 at +25% or more.' },
    { key: 'sales', label: 'Sales score', max: 20, rule: 'The app\'s Sales score scaled down to 20.' },
    { key: 'margin', label: 'Net margin vs a year ago', max: 15, rule: 'widened by more than 0.5 percentage point.' },
    { key: 'eps_accel', label: 'EPS growth speeding up', max: 12, rule: 'rose step by step.' },
    { key: 'sales_accel', label: 'Sales growth speeding up', max: 12, rule: 'rose step by step.' },
    { key: 'margin_accel', label: 'Net margin rising', max: 11, rule: 'rose step by step.' },
    { key: 'surprise', label: 'Earnings surprise', max: 10, rule: 'never passed in, so it is 0 on every name today.' },
  ],
  penalties: [
    { key: 'low_quality_beat', label: 'A beat with no sales behind it', points: 25, rule: 'EPS up 25% on sales up less than 5%.' },
    { key: 'inventory', label: '⚠️ inventory flag', points: 10, rule: 'The ⚠️ mark below.' },
    { key: 'double_trouble', label: 'Double trouble', points: 20, rule: 'receivables too.' },
  ],
  ceiling_today: 90,
  ceiling_note: 'Added up and clamped to 0–100, then rounded. The most a name can score today is 90: the surprise points never arrive.',
  tiers: [
    { key: 'code33', label: '🎯 Code 33', rule: 'all three rose step by step.' },
    { key: 'red_flag', label: 'Red flag', rule: 'Double trouble, a beat with no sales, or ⚠️.' },
    { key: 'accelerating', label: 'Accelerating', rule: 'EPS or sales speeding up.' },
    { key: 'steady', label: 'Steady', rule: 'a score of 55 or more.' },
    { key: 'weak', label: 'Weak', rule: 'Everything else that has a score.' },
    { key: 'unknown', label: 'Blank (—)', rule: 'No score: neither EPS nor sales can be compared with a year ago for the latest quarter.' },
  ],
  tier_note: 'The first tier that matches wins, in this order. Hover a score to see its tier.',
  marks: [
    { mark: '🎯', rule: 'Code 33 — the top tier above.' },
    { mark: '⚠️', rule: 'Inventory grew more than 15 points faster than sales.' },
  ],
  blank: ['Neither EPS nor sales can be compared with a year ago for the latest quarter.',
          'The name\'s research-cache row is older than 16 days, so the board does not use it.'],
  group_rows: 'Sector, industry and roster rows show the median score of their full membership, with no 🎯 or ⚠️.',
  fundamentals_as_of: { oldest: '2026-09-20', newest: '2026-09-27', n: 1712,
                        note: 'A row older than 16 days is not used.' },
  source: 'sepa/earnings_quality.py · compute()',
};

const NAME = {
  symbol: 'LPG', name: 'Dorian LPG', industry: 'Oil & Gas Midstream',
  rel_1d: 0.4, rel_5d: 3.1, rel_21d: 8.2, d1_source: 'close',
  eq_score: 90, eq_tier: 'red_flag', code_33: false, inventory_flag: true,
};
const payload = (qi: HsQualityInfo | null | undefined) => ({
  as_of: '2026-09-25', benchmark: 'RSP', sorted_by: 'rel_5d', sorted_dir: 'desc',
  sorted_then_by: [], sort_max_keys: 3,
  d1: { basis: 'close', live: false, close_as_of: '2026-09-25' },
  ...(qi === undefined ? {} : { quality_info: qi }),
  themes: [{ group: 'energy', n_full: 20, ranked: true, thin: false, basis: 'full membership',
             rel_1d: 0.1, rel_5d: 1, rel_21d: 2, names: [NAME], names_total: 1 }],
  sectors: [],
});

function stub(body: unknown) {
  const hottest: string[] = [];
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/supply-demand/bounce-room')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ rows: [] }) } as Response);
    }
    hottest.push(String(url));
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  }));
  return hottest;
}
const view = () => render(
  <MemoryRouter>
    <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
      <HottestSectors />
    </EnterableFilterProvider>
  </MemoryRouter>);
const qTrigger = () => screen.getByRole('button', { name: 'What is Quality score?' });
const openEnergy = () => fireEvent.click(screen.getByRole('button', { name: /Energy \(curated\)/ }));

beforeEach(() => { _resetSignalWatchlist(); _resetBounceRoomCache(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('ⓘ Quality — pure helpers', () => {
  it('showQualityInfo needs served points', () => {
    expect(showQualityInfo({ quality_info: QI })).toBe(true);
    expect(showQualityInfo({ quality_info: { ...QI, points: [] } })).toBe(false);
    expect(showQualityInfo({ quality_info: null })).toBe(false);
    expect(showQualityInfo(null)).toBe(false);
  });
  it('tierLabel prints the served label, the raw key without an explainer', () => {
    expect(tierLabel('red_flag', QI)).toBe('Red flag');
    expect(tierLabel('red_flag', null)).toBe('red_flag');
    expect(tierLabel('brand_new_tier', QI)).toBe('brand_new_tier');
    expect(tierLabel(null, QI)).toBeUndefined();
    expect(tierLabel('', QI)).toBeUndefined();
  });
});

describe('ⓘ Quality on the board', () => {
  it('sits beside Quality and opens a sheet on <body> with every served part', async () => {
    stub(payload(QI));
    const { container } = view();
    await screen.findByText(/Energy/);
    const trig = qTrigger();
    expect(trig.closest('th')?.querySelector('.hs-sort')?.textContent).toMatch(/^Quality/);
    fireEvent.click(trig);
    const dlg = screen.getByRole('dialog', { name: 'Quality score' });
    expect(container.contains(dlg)).toBe(false);
    expect(dlg.closest('.hs-scroll')).toBeNull();
    const t = dlg.textContent || '';
    for (const p of QI.points!) { expect(t).toContain(p.label); expect(t).toContain(`${p.max} pts`); }
    for (const p of QI.penalties!) { expect(t).toContain(p.label); expect(t).toContain(`−${p.points} pts`); }
    for (const tr of QI.tiers!) expect(t).toContain(tr.label);
    expect(t).toContain('not a measured predictor');
    expect(t).toContain(QI.ceiling_note!);
    expect(within(dlg).getByTestId('hs-qi-asof').textContent)
      .toBe('cached 2026-09-20 → 2026-09-27 ET · A row older than 16 days is not used.');
    // the measured note leads
    expect(dlg.querySelector('.hs-qi > p')?.textContent).toContain('not a measured predictor');
  });

  it('is served-driven: a sentinel payload renders verbatim', async () => {
    const odd = { ...QI, points: [{ key: 'x', label: 'SENTINEL-Q', max: 777, rule: 'sentinel rule' }] };
    stub(payload(odd));
    view();
    await screen.findByText(/Energy/);
    fireEvent.click(qTrigger());
    const t = screen.getByRole('dialog').textContent || '';
    expect(t).toContain('SENTINEL-Q');
    expect(t).toContain('777 pts');
    // NEGATIVE: nothing from a hard-coded copy leaks in
    expect(t).not.toContain('EPS growth speeding up');
  });

  it('NEGATIVE: no page cite, no author, no claim of an edge, no cadence', async () => {
    stub(payload(QI));
    view();
    await screen.findByText(/Energy/);
    fireEvent.click(qTrigger());
    const t = screen.getByRole('dialog').textContent || '';
    expect(t).not.toMatch(/p\.\s?1|Minervini|\bedge\b|\bpredicts\b|\bweek/i);
  });

  it('Esc and an outside click close it; NEGATIVE: opening fires no hottest fetch', async () => {
    const hottest = stub(payload(QI));
    view();
    await screen.findByText(/Energy/);
    const n = hottest.length;
    fireEvent.click(qTrigger());
    expect(screen.getByRole('dialog')).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(qTrigger());
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole('dialog')).toBeNull();
    await new Promise((r) => setTimeout(r, 20));
    expect(hottest.length).toBe(n);
  });

  it('NEGATIVE: no quality_info → no ⓘ, and the header hover is byte-identical', async () => {
    stub(payload(undefined));
    view();
    await screen.findByText(/Energy/);
    expect(screen.queryByRole('button', { name: /What is Quality/ })).toBeNull();
    const q = screen.getByRole('button', { name: /^Quality/ });
    const col = HS_COLS.find((c) => c.key === 'eq_score')!;
    expect(col.title).toBe('Minervini Ch.8 earnings quality · 🎯 Code 33 · ⚠️ inventory vs sales');
    expect(q.getAttribute('title')).toBe(`${col.title} · click to sort`);
  });
});

describe('the Quality cell hover names the tier', () => {
  it('prints the SERVED tier label', async () => {
    stub(payload(QI));
    const { container } = view();
    await screen.findByText(/Energy/);
    openEnergy();
    await waitFor(() => expect(container.querySelector('tr.hs-name')).toBeTruthy());
    const cell = Array.from(container.querySelectorAll('tr.hs-name td'))
      .find((td) => (td.textContent || '').startsWith('90'))!;
    expect(cell.getAttribute('title')).toBe('Red flag');
  });

  it('a sentinel label renders verbatim', async () => {
    stub(payload({ ...QI, tiers: [{ key: 'red_flag', label: 'SENTINEL-TIER', rule: 'r' }] }));
    const { container } = view();
    await screen.findByText(/Energy/);
    openEnergy();
    await waitFor(() => expect(container.querySelector('tr.hs-name')).toBeTruthy());
    expect(container.querySelector('td[title="SENTINEL-TIER"]')).toBeTruthy();
  });

  it('NEGATIVE: without quality_info the hover is the raw key, as before', async () => {
    stub(payload(undefined));
    const { container } = view();
    await screen.findByText(/Energy/);
    openEnergy();
    await waitFor(() => expect(container.querySelector('tr.hs-name')).toBeTruthy());
    expect(container.querySelector('td[title="red_flag"]')).toBeTruthy();
    expect(container.querySelector('td[title="Red flag"]')).toBeNull();
  });
});
