/* 🧬 Chart Maps ▸ Catalysts ▸ 🧬 Medical — the board rendered through the real
 * components off the §3.10 payload fixture (lib/__fixtures__/medicalCatalysts;
 * the main session swaps in the captured real payload and re-runs this file).
 *
 * Ajay 2026-09-29: "… sector them separatively like new fdaapprovals or break
 * throughs like mrnaresearch how to catch thsse sectorsand companiesand add
 * right setup and alerts". Pinned: the served UNMEASURED note + `Setup: pending
 * study`, the KOD row's served words, ticker → Supply & Demand, the timeline
 * link, the unresolved row, the filters, the roll-up's small-n greying, and —
 * NEGATIVE — no "bounce" and no Stop / Target / Entry anywhere. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { MED_BOARD, UNMEASURED_NOTE, ROLLUP_NOTE } from '../lib/__fixtures__/medicalCatalysts';

/* The CatalystsBoard shell's own fetchers are mocked — the last describe only
 * asserts which sub-tab mounts. */
vi.mock('../hooks/useCatalysts', () => ({
  useCatalystScan: () => ({ data: null, loading: false, refreshing: false, refetch: vi.fn(), forceRefresh: vi.fn() }),
  useVolumeAlerts: () => ({ alerts: [], session_date: undefined }),
  useDeepDive: () => ({ data: null, loading: false }),
  usePremarketScan: () => ({ data: null, loading: false, refetch: vi.fn() }),
  useInsiderSignal: () => ({ data: null, loading: false }),
  useCatalystCalendar: () => ({ data: null, loading: false, refetch: vi.fn(), forceRefresh: vi.fn() }),
  useCatalystTimeline: () => ({ data: null, loading: false, refetch: vi.fn() }),
  useCatalystStale: () => ({ data: null, loading: false, refetch: vi.fn() }),
  useCatalystMultiDayAccumulators: () => ({ data: null, loading: false, refetch: vi.fn() }),
  usePredictions: () => ({ data: null, loading: false, refreshing: false, refetch: vi.fn(), forceRefresh: vi.fn() }),
  useFrenzyRadar: () => ({ data: null, loading: false, refetch: vi.fn() }),
}));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));
vi.mock('./MarketGaugeBanner', () => ({ MarketGaugeBanner: () => <div data-testid="gauge-banner" /> }));
vi.mock('./PromoCircuit', () => ({ PromoCircuit: () => <div data-testid="promo-circuit" /> }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: true, features: new Set(['catalysts', 'chart-maps']), catalog: [], email: null }),
}));

import { MedicalCatalysts } from './MedicalCatalysts';
import { CatalystsBoard } from '../pages/Catalysts';

type Resp = { ok: boolean; status: number; json: () => Promise<unknown> };
function stubFetch(board: unknown = MED_BOARD, status = 200) {
  const fn = vi.fn(async (url: string): Promise<Resp> => {
    const u = String(url);
    if (u.includes('/catalysts/medical')) {
      return { ok: status === 200, status, json: async () => board };
    }
    return { ok: true, status: 200, json: async () => ({ rows: [] }) };
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}
const medUrls = (fn: ReturnType<typeof vi.fn>) =>
  fn.mock.calls.map((c) => String(c[0])).filter((u) => u.includes('/catalysts/medical'));

const draw = () => render(<MemoryRouter initialEntries={['/chart-maps?tab=catalysts&sub=medical']}><MedicalCatalysts /></MemoryRouter>);
const rowOf = (key: string) => document.querySelector(`[data-event-key="${key}"]`) as HTMLElement;

beforeEach(() => { stubFetch(); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🧬 MedicalCatalysts board', () => {
  it('renders the KOD row in its served words, with the HIGH chip', async () => {
    draw();
    await screen.findByTestId('mc-board');
    const kod = rowOf('KOD|topline_positive|2026-09-28');
    expect(kod).toBeTruthy();
    const w = within(kod);
    expect(w.getByText('Phase 3 topline positive')).toHaveClass('mc-dir--pos');
    expect(w.getByText('ophthalmology')).toBeInTheDocument();
    expect(w.getByText('Antibodies & bispecifics')).toBeInTheDocument();
    expect(w.getByText('DAYBREAK')).toBeInTheDocument();
    expect(w.getByText('HIGH')).toBeInTheDocument();
    expect(kod.textContent).toContain('close +178.0%');
    expect(kod.textContent).toContain('seen +72.0%');
    expect(kod.textContent).toContain('pre-market');
    expect(kod.textContent).toContain('RVOL 57.1×');
    expect(kod.textContent).toContain('50d median $22.7M/day');
    expect(w.getByTestId('mc-push')).toHaveTextContent('🔔 pushed 04:05');
    expect(w.getByText('sources (3)')).toBeInTheDocument();
  });

  it('prints the SERVED UNMEASURED note and Setup: pending study', async () => {
    draw();
    expect(await screen.findByTestId('mc-unmeasured')).toHaveTextContent(UNMEASURED_NOTE);
    expect(screen.getByTestId('mc-setup')).toHaveTextContent('Setup: pending study');
    expect(screen.getByTestId('mc-roll-note')).toHaveTextContent(ROLLUP_NOTE);
    expect(screen.getByTestId('mc-pass')).toHaveTextContent('last pass 00:45 ET · 36 names read');
  });

  it('NEGATIVE: the note is served, not typed — a different served note replaces it', async () => {
    stubFetch({ ...MED_BOARD, labels: { ...MED_BOARD.labels, note: 'SERVED-NOTE-XYZ', setup: 'served-setup' } });
    draw();
    expect(await screen.findByTestId('mc-unmeasured')).toHaveTextContent('SERVED-NOTE-XYZ');
    expect(screen.getByTestId('mc-setup')).toHaveTextContent('Setup: served-setup');
  });

  it('the ticker opens Supply & Demand; the 🧬 timeline link goes to the Catalyst tab', async () => {
    draw();
    await screen.findByTestId('mc-board');
    const kod = within(rowOf('KOD|topline_positive|2026-09-28'));
    const tk = kod.getByRole('link', { name: 'KOD' });
    expect(tk.getAttribute('href')).toMatch(/^\/sepa\/KOD\?tab=supply/);
    expect(kod.getByRole('link', { name: '🧬 timeline' }).getAttribute('href')).toBe('/sepa/KOD?tab=catalyst');
  });

  it('NEGATIVE: an unresolved issuer renders the company as text, with no ticker link and no timeline link', async () => {
    draw();
    await screen.findByTestId('mc-board');
    const el = rowOf('UNRESOLVED:elevar-therapeutics|fda_approval|2026-09-26');
    expect(within(el).getByTestId('mc-unresolved')).toHaveTextContent('Elevar Therapeutics');
    expect(within(el).queryAllByRole('link').filter((a) => (a.getAttribute('href') ?? '').startsWith('/sepa/'))).toHaveLength(0);
    expect(within(el).getByTestId('mc-push')).toHaveTextContent('not rung: no ticker');
    // RLAY was only a partner tag on that story — it must not appear as the issuer
    expect(el.textContent).not.toContain('RLAY');
  });

  it('groups by family in the served order', async () => {
    draw();
    await screen.findByTestId('mc-board');
    const secs = [...document.querySelectorAll('[data-testid^="mc-fam-"]')].map((s) => s.getAttribute('data-testid'));
    expect(secs).toEqual(['mc-fam-fda', 'mc-fam-trial', 'mc-fam-conference']);
  });

  it('"High impact only" hides the low rows and keeps the high ones', async () => {
    draw();
    await screen.findByTestId('mc-board');
    expect(rowOf('MNOV|topline_unknown|2026-09-28')).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/High impact only/));
    expect(rowOf('MNOV|topline_unknown|2026-09-28')).toBeNull();
    expect(rowOf('MRNA|conference_data|2026-09-24')).toBeNull();
    expect(rowOf('KOD|topline_positive|2026-09-28')).toBeTruthy();
  });

  it('modality / area / family filters match the served keys', async () => {
    draw();
    await screen.findByTestId('mc-board');
    fireEvent.change(screen.getByLabelText('modality'), { target: { value: 'mrna' } });
    expect(screen.getAllByTestId('mc-row')).toHaveLength(1);
    expect(rowOf('MRNA|conference_data|2026-09-24')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('modality'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('area'), { target: { value: 'ophthalmology' } });
    fireEvent.click(screen.getByRole('button', { name: /FDA decisions/ }));
    expect(screen.queryAllByTestId('mc-row')).toHaveLength(0);
    expect(screen.getByTestId('mc-empty-filter')).toHaveTextContent('No events match these filters');
  });

  it('roll-up: MIRM’s two events on one session are ONE observation; small-n rows are greyed', async () => {
    draw();
    await screen.findByTestId('mc-roll');
    fireEvent.click(screen.getByRole('button', { name: 'By area' }));
    const rare = screen.getByTestId('mc-roll-rare_disease');
    const cells = [...rare.querySelectorAll('td')].map((td) => td.textContent);
    expect(cells[1]).toBe('2');     // events
    expect(cells[5]).toBe('1');     // obs
    expect(rare).toHaveClass('mc-roll__row--small');
    expect(within(rare).getByText('n<5')).toBeInTheDocument();
  });

  it('NEGATIVE: a roll-up row with small_n false is NOT greyed', async () => {
    const big = { ...MED_BOARD.rollup.by_modality[0], small_n: false, n_tickers: 7 };
    stubFetch({ ...MED_BOARD, rollup: { ...MED_BOARD.rollup, by_modality: [big] } });
    draw();
    const row = await screen.findByTestId(`mc-roll-${big.key}`);
    expect(row).not.toHaveClass('mc-roll__row--small');
    expect(within(row).queryByText('n<5')).toBeNull();
  });

  it('the window buttons refetch with ?days=', async () => {
    const fn = stubFetch();
    draw();
    await screen.findByTestId('mc-board');
    expect(medUrls(fn)[0]).toContain('/catalysts/medical?days=30');
    fireEvent.click(screen.getByRole('button', { name: '7d' }));
    await waitFor(() => expect(medUrls(fn).some((u) => u.includes('days=7'))).toBe(true));
  });

  it('NEGATIVE: no "bounce" and no Stop / Target / Entry anywhere on the board', async () => {
    const { container } = draw();
    await screen.findByTestId('mc-board');
    // open every sources list so their text counts too
    container.querySelectorAll('details').forEach((d) => { d.open = true; });
    const text = container.textContent ?? '';
    expect(text).not.toMatch(/bounce/i);
    expect(text).not.toMatch(/\b(Stop|Target|Entry)\b/);
  });

  it('empty payload → the empty state with the pass stamp and counts', async () => {
    stubFetch({ ...MED_BOARD, events: [], rollup: { ...MED_BOARD.rollup, by_modality: [], by_area: [] } });
    draw();
    const empty = await screen.findByTestId('mc-empty');
    expect(empty).toHaveTextContent('No classified medical events in the last 30 days — last pass 00:45 ET');
    expect(empty).toHaveTextContent('roster 362');
    expect(screen.getByTestId('mc-unmeasured')).toHaveTextContent(UNMEASURED_NOTE);
  });

  it('NEGATIVE: an empty store with no pass says so instead of inventing a time', async () => {
    stubFetch({ ...MED_BOARD, events: [], pass: null });
    draw();
    expect(await screen.findByTestId('mc-empty')).toHaveTextContent('no pass recorded yet');
  });

  it('a fetch error is a message, not a crash', async () => {
    stubFetch({}, 500);
    draw();
    expect(await screen.findByTestId('mc-error')).toHaveTextContent('🧬 Medical catalysts unavailable (HTTP 500)');
    expect(screen.queryByTestId('mc-board')).toBeNull();
  });
});

describe('Chart Maps ▸ Catalysts mounts 🧬 Medical on ?sub=medical', () => {
  const drawShell = (search: string) =>
    render(<MemoryRouter initialEntries={[`/chart-maps${search}`]}><CatalystsBoard embedded /></MemoryRouter>);

  it('?sub=medical selects the tab and renders the board', async () => {
    drawShell('?tab=catalysts&sub=medical');
    const btn = screen.getByRole('button', { name: '🧬 Medical' });
    expect(btn).toHaveClass('is-active');
    expect(await screen.findByTestId('mc-board')).toBeInTheDocument();
  });

  it('NEGATIVE: another sub-tab does not mount the medical board or fetch it', async () => {
    const fn = stubFetch();
    drawShell('?tab=catalysts&sub=promo');
    expect(await screen.findByTestId('promo-circuit')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '🧬 Medical' })).not.toHaveClass('is-active');
    expect(screen.queryByTestId('mc-board')).toBeNull();
    expect(medUrls(fn)).toHaveLength(0);
  });

  it('clicking 🧬 Medical switches to it', async () => {
    drawShell('?tab=catalysts&sub=promo');
    fireEvent.click(screen.getByRole('button', { name: '🧬 Medical' }));
    expect(await screen.findByTestId('mc-board')).toBeInTheDocument();
  });
});
