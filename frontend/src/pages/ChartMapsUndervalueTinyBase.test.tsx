/* 💎 Under Value — growth off a near-zero year-ago quarter (2026-11-12).
 *
 * Ajay, verbatim: "We got wrong numbers for Joby in sales in the undervalye
 * can you verfy". The server now excludes a name whose year-ago quarter is too
 * small to carry a percentage (JOBY: +257,493% off a $15K quarter), names it in
 * the served `growth_excluded` list, and serves the quarter each kept card's
 * growth comes from as the `Rev quarter` stat. The real page, fetch stubbed:
 * the page renders what was served and never turns `growth_excluded` into a
 * card or prints the arithmetic number. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChartMaps from './ChartMaps';

const OLDER = 'FY2026 Q2 (to 2026-06-30) · older than the P/S revenue (to 2026-09-30)';
const SENTENCE = '1 more had sales growth off a year-ago quarter under $1M (JOBY) — a percentage '
  + 'off that base is arithmetic, not growth, so they are excluded too, never ranked. ';
const HEAD = 'Bonde strong/explosive sales across the whole universe (120 screened), kept only when '
  + 'the price tag LAGS the growth: price-to-sales ÷ revenue growth (PSG) ≤ 0.15 — calibrated on LPTH '
  + '(~12x sales at +109% = 0.11). 40 growers already priced for it; 3 lacked a revenue figure and '
  + '1 a share count — excluded, never estimated. ';
const TAIL = 'Backlog and contracts are not machine-readable, so check the story before the chart. '
  + 'Cheapest-for-growth ranks first.';
const NOTE_WITH = HEAD + SENTENCE + TAIL;
const NOTE_OLD = HEAD + TAIL;

const cheap = () => ({
  symbol: 'CHEAP', href: '/sepa/CHEAP',
  /* One bar, not `bars: []`: PatternChart renders nothing for a tile with no
   * bars, so an empty list would hide the card the test reads. */
  bars: [{ t: '2026-11-12', o: 10, h: 11, l: 9.5, c: 10.5, v: 1000 }], bands: [], lines: [], markers: [], why: '',
  stats: [
    { k: 'P/S', v: '11.9x' },
    { k: 'Rev YoY', v: '+109%' },
    { k: 'Rev quarter', v: OLDER },
    { k: 'PSG', v: '0.109' },
    { k: 'Mkt cap', v: '$745M' },
  ],
  badges: [
    { text: '💎 11.9x sales vs +109% growth', tone: 'good' },
    { text: '🟢 Sales explosive +109%', tone: 'good' },
  ],
});
const JOBY_EXCLUDED = {
  symbol: 'JOBY', reason: 'base_too_small', base_state: 'too_small',
  base_rev: 15000, latest_rev: 38639000, period: 'FY2026 Q2',
};

type Over = { tiles?: unknown[]; note?: string; growth_not_comparable?: number; growth_excluded?: unknown[] };
const board = (over: Over) => ({
  tab: 'undervalue', matched: 1, screened: 120,
  tiles: [cheap()], note: NOTE_WITH,
  growth_not_comparable: 1, growth_excluded: [JOBY_EXCLUDED],
  ...over,
});

function stub(make: () => Record<string, unknown>) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => make() } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const page = () =>
  render(<MemoryRouter initialEntries={['/chart-maps?tab=undervalue']}><ChartMaps /></MemoryRouter>);
const bodyText = () => document.body.textContent || '';
const cardSymbols = () =>
  Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);

describe('💎 Under Value — tiny year-ago base excluded, quarter served', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('the CHEAP card prints the served Rev quarter words', async () => {
    vi.stubGlobal('fetch', stub(() => board({})));
    page();
    await waitFor(() => expect(cardSymbols()).toEqual(['CHEAP']));
    expect(bodyText()).toContain(OLDER);
    expect(bodyText()).toContain('Rev quarter');
  });

  it('NEGATIVE: no 257493 and no +257 anywhere on the page', async () => {
    vi.stubGlobal('fetch', stub(() => board({})));
    page();
    await waitFor(() => expect(cardSymbols()).toEqual(['CHEAP']));
    expect(bodyText()).not.toContain('257493');
    expect(bodyText()).not.toContain('+257');
  });

  it('NEGATIVE: growth_excluded never becomes a card', async () => {
    vi.stubGlobal('fetch', stub(() => board({})));
    page();
    await waitFor(() => expect(cardSymbols()).toEqual(['CHEAP']));
    expect(cardSymbols()).not.toContain('JOBY');
    expect(document.querySelector('a[href="/sepa/JOBY"]')).toBeNull();
  });

  it('the served exclusion sentence renders verbatim when the board prints its note (no tiles)', async () => {
    vi.stubGlobal('fetch', stub(() => board({ tiles: [] })));
    page();
    await waitFor(() => expect(bodyText()).toContain(SENTENCE.trim()));
    expect(bodyText()).toContain(NOTE_WITH.trim());
    expect(bodyText()).not.toContain('257493');
  });

  it('NEGATIVE: zero exclusions + the old note print no exclusion sentence', async () => {
    vi.stubGlobal('fetch', stub(() => board({
      tiles: [], note: NOTE_OLD, growth_not_comparable: 0, growth_excluded: [],
    })));
    page();
    await waitFor(() => expect(bodyText()).toContain(NOTE_OLD.trim()));
    expect(bodyText()).not.toContain('more had sales growth off a year-ago quarter');
    expect(bodyText()).not.toContain('JOBY');
  });

  it('with cards on the board the served exclusion note prints once, verbatim', async () => {
    vi.stubGlobal('fetch', stub(() => board({})));
    page();
    await waitFor(() => expect(cardSymbols()).toEqual(['CHEAP']));
    const notes = document.querySelectorAll('[data-testid="uv-growth-excluded-note"]');
    expect(notes.length).toBe(1);
    expect(notes[0].textContent).toBe(NOTE_WITH);
    expect(bodyText()).not.toContain('257493');
  });

  it('NEGATIVE: cards on the board but zero exclusions print no exclusion note', async () => {
    vi.stubGlobal('fetch', stub(() => board({ note: NOTE_OLD, growth_not_comparable: 0, growth_excluded: [] })));
    page();
    await waitFor(() => expect(cardSymbols()).toEqual(['CHEAP']));
    expect(document.querySelector('[data-testid="uv-growth-excluded-note"]')).toBeNull();
  });

  it('NEGATIVE: no cards — the note prints once, not twice', async () => {
    vi.stubGlobal('fetch', stub(() => board({ tiles: [] })));
    page();
    await waitFor(() => expect(bodyText()).toContain(SENTENCE.trim()));
    expect(document.querySelector('[data-testid="uv-growth-excluded-note"]')).toBeNull();
    expect(bodyText().split(SENTENCE.trim()).length - 1).toBe(1);
  });
});
