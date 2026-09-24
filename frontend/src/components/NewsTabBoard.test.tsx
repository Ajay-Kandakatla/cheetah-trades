import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import NewsTabBoard from './NewsTabBoard';
import { stockTitanHeatmapUrl } from '../lib/rotation';

/* 📰 News tab (2026-09-24). A REAL-shaped payload of GET /chart-maps/news
 * (backend/chart_maps/news_tab.py): four blocks, each able to fail alone.
 *
 * The rule with teeth: the day column says "today" ONLY when the served
 * `sectors.d1.live` is true. Before the open, after the close and on weekends
 * the leg is the LAST CLOSE — "lagging today" there would be a lie. */

const WATCH_DISAGREE =
  'WEEKLY structure stronger than the day — near-term softness inside a '
  + 'constructive weekly trend; dips have been bought';

const STUDY_NOTE =
  'Sector heat describes what already moved; it is not a forecast. MEASURED 2026-09-09 on the '
  + 'rel_21d definition over 50,191 demand-zone arrivals: a hot sector changed the win rate by '
  + '−0.57pp (95% CI −1.87 to +0.71) — nothing. \'A cold sector just sits there\' measured INVERTED: '
  + 'at 5 sessions hot minus cold was −2.55pp (95% CI −4.48 to −0.65), the one interval in the study '
  + 'clear of zero — cold turned faster. The 🔥/🧊 word on this table is decided on the 5-session leg '
  + '(rel_5d), which is UNMEASURED; the 21-day null neither validates nor condemns it. '
  + 'Script: backend/studies/sector_heat_study.py.';

const TIMED_OUT = 'still loading — timed out after 8s, refresh';

const DAY_TAG = {
  date: '2026-09-24', sector: 'Technology', symbol: 'NVDA', company: 'NVIDIA',
  positive: true, why_positive: 'new supply deal', bull: 'Supply deal extends the backlog.',
  bear: 'Already priced after a +40% quarter.', headline_count: 4,
  trigger: null, headlines: [], facts: null, read_by: 'claude-sonnet', measured: false,
};

function payload(over: Record<string, any> = {}) {
  const base: any = {
    generated_at_iso: '2026-09-24T14:05:00Z',
    verdict: {
      ok: true, as_of_label: 'as of 10:05 ET', generated_at_iso: '2026-09-24T14:05:00Z',
      daily: { score: 60, state: 'caution', state_label: 'Caution', word: 'mixed' },
      weekly: { score: 84, state: 'constructive', state_label: 'Constructive', word: 'bullish' },
      agree: false,
      drivers: ['distribution days climbing (4 in 25 sessions)'],
      outlook: { label: 'Next day', note: 'bias caution', watch: [WATCH_DISAGREE] },
      disclaimer: 'A regime read, not a forecast.',
    },
    macro: {
      ok: true, days: 14,
      tier_labels: { 1: 'Market movers', 2: 'Trend shapers', 3: 'Context' },
      next_tier1: { date: '2026-10-02', kind: 'jobs', tier: 1, label: 'Jobs report (NFP)', when_label: 'in 8 days' },
      events: [
        { date: '2026-09-24', kind: 'claims', tier: 2, tier_label: 'Trend shapers', label: 'Jobless claims', days_until: 0, when_label: 'today' },
        { date: '2026-09-30', kind: 'pce', tier: 1, tier_label: 'Market movers', label: 'Core PCE', days_until: 6, when_label: 'in 6 days' },
        { date: '2026-10-02', kind: 'jobs', tier: 1, tier_label: 'Market movers', label: 'Jobs report (NFP)', days_until: 8, when_label: 'in 8 days' },
      ],
      disclaimer: 'A heads-up on what data could move the regime — not a forecast or advice.',
    },
    sectors: {
      ok: true, as_of: '2026-09-24T14:00:00Z',
      // the REAL shape — an object, as /rotation serves it. The string 'RSP' here
      // is how the first build shipped a board that crashed on its first real payload.
      benchmark: { symbol: 'RSP', window: 1.58, d1: -0.31, d5: -0.07, d21: -4.41, d63: 0.83 },
      ranked_by: 'rel_5d', heat_window: '5d',
      d1: { live: true, basis: 'close', as_of: '2026-09-24T14:00:00Z', reason: null, market_closed: null },
      rows: [
        { sector: 'Technology', n: 420, benchmark: { symbol: 'RSP', d1: -0.31, d5: -0.07 }, rel_1d: -0.6, rel_5d: 2.4, rel_21d: 5.1, pct_positive_1d: 38,
          read: { '1d': 'bearish', '5d': 'bullish', '21d': 'bullish' },
          heat: { tone: 'hot', percentile: 91, heat_window: '5d', thin: false, grain: 'sector' },
          hot_lagging_1d: true, cold_leading_1d: false, leader: 'NVDA', day_tag: DAY_TAG },
        { sector: 'Industrials', n: 390, benchmark: { symbol: 'RSP', d1: -0.31, d5: -0.07 }, rel_1d: 0.1, rel_5d: 0.3, rel_21d: -0.4, pct_positive_1d: 52,
          read: { '1d': 'bullish', '5d': 'bullish', '21d': 'bearish' },
          heat: { tone: 'neutral', percentile: 50, heat_window: '5d', thin: false, grain: 'sector' },
          hot_lagging_1d: false, cold_leading_1d: false, leader: 'GE', day_tag: null },
        { sector: 'Crypto Miners', n: 12, benchmark: { symbol: 'RSP', d1: -0.31, d5: -0.07 }, rel_1d: 1.9, rel_5d: -3.1, rel_21d: -6.0, pct_positive_1d: 75,
          read: { '1d': 'bullish', '5d': 'bearish', '21d': 'bearish' },
          heat: { tone: 'cold', percentile: 8, heat_window: '5d', thin: true, grain: 'sector' },
          hot_lagging_1d: false, cold_leading_1d: true, leader: 'MARA', day_tag: null },
      ],
      tags_date: '2026-09-24', study: { note: STUDY_NOTE, measured_on: 'rel_21d', shipped_on: 'rel_5d' },
      source: 'mongo', built_at_iso: '2026-09-24T13:30:00Z', stale: false,
    },
    headlines: {
      ok: true, window_hours: 36, query: 'stock market OR Nasdaq OR S&P 500',
      items: [
        { title: 'Stocks slip as yields climb', url: 'https://example.test/a', source: 'Reuters', published: 1_790_000_000, provider: 'google' },
        { title: 'Nasdaq steadies after chip rally', url: 'https://example.test/b', source: 'Bloomberg', published: 1_789_990_000, provider: 'google' },
      ],
      counts: { raw: 2 }, fetched_at: 1_790_000_100,
    },
    budget_sec: 8, note: 'A read of what the app already serves. Not advice.', measured: false,
  };
  for (const [k, v] of Object.entries(over)) base[k] = v;
  return base;
}

function stub(p: any) {
  const spy = vi.fn(async () => ({ ok: true, json: async () => p }));
  vi.stubGlobal('fetch', spy);
  return spy;
}

async function mount(p: any = payload()) {
  const spy = stub(p);
  render(<MemoryRouter><NewsTabBoard /></MemoryRouter>);
  await screen.findByTestId('news-tab-board');
  return spy;
}

describe('NewsTabBoard', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('fetches the one composed endpoint', async () => {
    const spy = await mount();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(String((spy.mock.calls[0] as unknown[])[0])).toMatch(/\/chart-maps\/news$/);
  });

  it('prints both market words with the gauge labels, the disagreement, and the served watch line verbatim', async () => {
    await mount();
    const daily = screen.getByTestId('nt-card-daily');
    const weekly = screen.getByTestId('nt-card-weekly');
    expect(daily).toHaveTextContent('mixed');
    expect(daily).toHaveTextContent('Caution 60');
    expect(weekly).toHaveTextContent('bullish');
    expect(weekly).toHaveTextContent('Constructive 84');
    expect(screen.getByTestId('nt-agree')).toHaveTextContent(
      'Daily and weekly disagree — daily mixed (Caution 60) · weekly bullish (Constructive 84)');
    expect(screen.getByText(WATCH_DISAGREE)).toBeInTheDocument();
  });

  it('lists the T1/T2 macro rows over the served window and marks the next market mover', async () => {
    await mount();
    expect(screen.getByTestId('nt-macro-head')).toHaveTextContent('next 14 days');
    expect(screen.getByTestId('nt-macro-head')).toHaveTextContent('T1 market movers + T2 trend shapers');
    const r0 = screen.getByTestId('nt-macro-row-0');
    const r2 = screen.getByTestId('nt-macro-row-2');
    expect(r0).toHaveTextContent('T2');
    expect(r0).toHaveTextContent('Jobless claims');
    expect(screen.getByTestId('nt-macro-row-1')).toHaveTextContent('T1');
    expect(r2).toHaveClass('is-next');
    expect(r2).toHaveTextContent('next market mover');
    expect(r0).not.toHaveClass('is-next');
    expect(screen.getByTestId('nt-next-t1')).toHaveTextContent('Jobs report (NFP)');
  });

  it('draws one row per served sector, in served order', async () => {
    await mount();
    const rows = Array.from(document.querySelectorAll('[data-testid^="nt-row-"]'))
      .map((n) => n.getAttribute('data-testid'));
    expect(rows).toEqual(['nt-row-Technology', 'nt-row-Industrials', 'nt-row-Crypto Miners']);
    expect(screen.getByTestId('nt-day-head')).toHaveTextContent('Today vs RSP');
    expect(screen.getByTestId('nt-heat-Technology')).toHaveTextContent('🔥');
    expect(screen.getByTestId('nt-heat-Crypto Miners')).toHaveTextContent('🧊');
    expect(screen.getByTestId('nt-row-Technology')).toHaveTextContent('-0.6pp');
    expect(screen.getByTestId('nt-row-Technology')).toHaveTextContent('bearish');
    expect(screen.queryByTestId('nt-d1-note')).toBeNull();
  });

  it('"🔥 hot, lagging today" is one click, counted, and filters to that row', async () => {
    await mount();
    const chip = screen.getByTestId('nt-view-hot_lagging');
    expect(chip).toHaveTextContent('🔥 hot, lagging today (1)');
    expect(screen.getByTestId('nt-view-cold_leading')).toHaveTextContent('🧊 cold, leading today (1)');
    fireEvent.click(chip);
    const rows = Array.from(document.querySelectorAll('[data-testid^="nt-row-"]'))
      .map((n) => n.getAttribute('data-testid'));
    expect(rows).toEqual(['nt-row-Technology']);
    fireEvent.click(screen.getByTestId('nt-view-all'));
    expect(document.querySelectorAll('[data-testid^="nt-row-"]')).toHaveLength(3);
  });

  it('the 📰 day tag opens the bull case AND the bear case with who read it', async () => {
    await mount();
    const tag = screen.getByTestId('nt-daytag-Technology');
    expect(tag).toHaveTextContent('📰 NVDA');
    expect(tag.getAttribute('title')).toMatch(/NOT measured/);
    expect(screen.queryByTestId('nt-daytag-open-Technology')).toBeNull();
    fireEvent.click(tag);
    const open = screen.getByTestId('nt-daytag-open-Technology');
    expect(within(open).getByText('Bull case')).toBeInTheDocument();
    expect(within(open).getByText('Bear case')).toBeInTheDocument();
    expect(open).toHaveTextContent(DAY_TAG.bull);
    expect(open).toHaveTextContent(DAY_TAG.bear);
    expect(open).toHaveTextContent('read by claude-sonnet');
    expect(open).toHaveTextContent('2026-09-24');
    expect(screen.queryByTestId('nt-daytag-Industrials')).toBeNull();
  });

  it('links the StockTitan heatmap for a mapped sector and omits it for an unmapped one', async () => {
    await mount();
    const a = screen.getByTestId('nt-heatmap-Technology');
    expect(a.getAttribute('href')).toBe(stockTitanHeatmapUrl('Technology'));
    expect(stockTitanHeatmapUrl('Crypto Miners')).toBeNull();
    expect(screen.queryByTestId('nt-heatmap-Crypto Miners')).toBeNull();
  });

  it('prints the served study note with both CIs and the UNMEASURED caveat, and links to 🔥 Hottest', async () => {
    await mount();
    const note = screen.getByTestId('nt-study');
    expect(note).toHaveTextContent('95% CI −1.87 to +0.71');
    expect(note).toHaveTextContent('95% CI −4.48 to −0.65');
    expect(note).toHaveTextContent('UNMEASURED');
    const link = screen.getByText(/Hottest board/).closest('a');
    expect(link?.getAttribute('href')).toBe('/chart-maps?tab=hot_sectors');
  });

  it('lists the headlines over the served window', async () => {
    await mount();
    const sec = screen.getByTestId('nt-section-headlines');
    expect(sec).toHaveTextContent('Headlines · last 36h');
    expect(within(sec).getByText('Stocks slip as yields climb').closest('a')?.getAttribute('href'))
      .toBe('https://example.test/a');
    expect(within(sec).getByText('Nasdaq steadies after chip rally')).toBeInTheDocument();
  });

  /* ── NEGATIVES ─────────────────────────────────────────────────────────── */

  it('NEGATIVE — d1.live false: "Last close vs RSP", the chip says last close, the reason line shows, "lagging today" is ABSENT', async () => {
    const p = payload();
    p.sectors.d1 = { live: false, basis: 'close', as_of: '2026-09-23', reason: 'pre-market — last close', market_closed: null };
    await mount(p);
    expect(screen.getByTestId('nt-day-head')).toHaveTextContent('Last close vs RSP');
    expect(screen.getByTestId('nt-view-hot_lagging')).toHaveTextContent('🔥 hot, lagging last close (1)');
    const note = screen.getByTestId('nt-d1-note');
    expect(note).toHaveTextContent('day column = last close (2026-09-23) — pre-market — last close');
    expect(document.body.textContent).not.toContain('lagging today');
    expect(document.body.textContent).not.toContain('leading today');
    expect(document.body.textContent).not.toContain('Today vs');
  });

  it('NEGATIVE — a string "yes" for live is not live', async () => {
    const p = payload();
    p.sectors.d1 = { live: 'yes', basis: 'close', as_of: '2026-09-23', reason: null, market_closed: null };
    await mount(p);
    expect(screen.getByTestId('nt-day-head')).toHaveTextContent('Last close vs RSP');
    expect(document.body.textContent).not.toContain('lagging today');
  });

  it('NEGATIVE — verdict ok:false shows its reason and the sectors still render', async () => {
    await mount(payload({ verdict: { ok: false, reason: 'market gauge unavailable' } }));
    expect(screen.getByTestId('nt-verdict-reason')).toHaveTextContent('market gauge unavailable');
    expect(screen.queryByTestId('nt-card-daily')).toBeNull();
    expect(screen.getByTestId('nt-row-Technology')).toBeInTheDocument();
  });

  it('NEGATIVE — a leg past the server budget prints its "refresh" reason in place', async () => {
    await mount(payload({ macro: { ok: false, reason: TIMED_OUT, events: [] } }));
    expect(screen.getByTestId('nt-macro-reason')).toHaveTextContent('refresh');
    expect(screen.getByTestId('nt-card-daily')).toBeInTheDocument();
    expect(screen.getByTestId('nt-section-headlines')).toHaveTextContent('Stocks slip as yields climb');
  });

  it('NEGATIVE — a timed-out leg prints NO window in its header, never a typed-in one', async () => {
    /* Review 2026-09-24: the headers read `days ?? 14` and `window_hours ?? 36`,
     * so a leg that timed out (it serves neither key) still announced a
     * "next 14 days" / "last 36h" window nobody measured. */
    await mount(payload({
      macro: { ok: false, reason: TIMED_OUT, events: [] },
      headlines: { ok: false, reason: TIMED_OUT, items: [] },
    }));
    const macroHead = screen.getByTestId('nt-macro-head');
    expect(macroHead).toHaveTextContent('T1 market movers + T2 trend shapers');
    expect(macroHead).not.toHaveTextContent(/next \d+ days/);
    expect(macroHead.textContent).not.toMatch(/\b14\b/);
    const newsHead = screen.getByTestId('nt-headlines-head');
    expect(newsHead).not.toHaveTextContent(/last \d+h/);
    expect(newsHead.textContent).not.toMatch(/\b36\b/);
  });

  it('a served window is still printed, exactly as served', async () => {
    const p = payload();
    p.macro.days = 14;
    p.headlines.window_hours = 36;
    await mount(p);
    expect(screen.getByTestId('nt-macro-head')).toHaveTextContent('next 14 days');
    expect(screen.getByTestId('nt-headlines-head')).toHaveTextContent('last 36h');
  });

  it('NEGATIVE — a timed-out sectors leg does not take the headlines with it', async () => {
    await mount(payload({ sectors: { ok: false, reason: TIMED_OUT, rows: [] } }));
    expect(screen.getByTestId('nt-sectors-reason')).toHaveTextContent('refresh');
    expect(screen.queryByTestId('nt-view-all')).toBeNull();
    expect(screen.getByTestId('nt-section-headlines')).toHaveTextContent('Nasdaq steadies');
  });

  it('NEGATIVE — no macro events → the empty line names the window', async () => {
    const p = payload();
    p.macro.events = [];
    p.macro.next_tier1 = null;
    await mount(p);
    expect(screen.getByTestId('nt-macro-empty')).toHaveTextContent('No T1/T2 releases in the next 14 days');
    expect(screen.queryByTestId('nt-next-t1')).toBeNull();
  });

  it('NEGATIVE — sectors.rows [] → empty state, chips count zero', async () => {
    const p = payload();
    p.sectors.rows = [];
    await mount(p);
    expect(screen.getByTestId('nt-sectors-empty')).toBeInTheDocument();
    expect(screen.getByTestId('nt-view-hot_lagging')).toHaveTextContent('(0)');
    expect(document.querySelectorAll('[data-testid^="nt-row-"]')).toHaveLength(0);
  });

  it('NEGATIVE — headlines.items [] → empty state', async () => {
    const p = payload();
    p.headlines.items = [];
    await mount(p);
    expect(screen.getByTestId('nt-headlines-empty')).toHaveTextContent('No market headlines in the last 36h');
  });

  it('NEGATIVE — an unknown heat tone prints "?", never 🔥', async () => {
    const p = payload();
    p.sectors.rows[0].heat = { tone: 'unknown' };
    await mount(p);
    const cell = screen.getByTestId('nt-heat-Technology');
    expect(cell).toHaveTextContent('?');
    expect(cell).not.toHaveTextContent('🔥');
    expect(screen.getByTestId('nt-view-hot')).toHaveTextContent('(0)');
  });

  it('NEGATIVE — weekly null → one card and no agree line', async () => {
    const p = payload();
    p.verdict.weekly = null;
    p.verdict.agree = null;
    await mount(p);
    expect(screen.getByTestId('nt-card-daily')).toBeInTheDocument();
    expect(screen.queryByTestId('nt-card-weekly')).toBeNull();
    expect(screen.queryByTestId('nt-agree')).toBeNull();
  });

  it('NEGATIVE — a rejected fetch prints an error line, not a blank tab', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('network down'); }));
    render(<MemoryRouter><NewsTabBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('nt-error')).toHaveTextContent('network down'));
    expect(screen.queryByTestId('news-tab-board')).toBeNull();
  });

  it('NEGATIVE — a non-2xx response is an error too', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })));
    render(<MemoryRouter><NewsTabBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('nt-error')).toHaveTextContent('HTTP 503'));
  });

  it('NEGATIVE — "bounce" is nowhere on the rendered tab', async () => {
    await mount();
    fireEvent.click(screen.getByTestId('nt-daytag-Technology'));
    expect(document.body.textContent || '').not.toMatch(/\bbounce\b/i);
  });

  it('NEGATIVE — the component types no gauge state literal, and carries both contract exemptions', async () => {
    const src = (await import('./NewsTabBoard.tsx?raw')).default as string;
    for (const lit of ["'constructive'", '"constructive"', "'risk_off'", '"risk_off"']) {
      expect(src.includes(lit), lit).toBe(false);
    }
    expect(src).toContain('no ticker rows on this tab — nothing for a growth / explosive / enterable chip to read');
    expect(src).toContain('no read on this board to rank by');
    expect(src).toContain('stockTitanHeatmapUrl');
    expect(src).toContain('dayTagChipLabel');
    expect(src).not.toMatch(/\bbounce\b/i);
  });
});
