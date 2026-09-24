/* 📰 News tab against the REAL payload (captured 2026-09-24 ~14:10 ET from the
 * branch API on :8001, with the live Mongo, FRED, gauge and news routine
 * behind it). Synthetic fixtures prove the branches; this proves the SHAPE
 * the server actually serves renders — the check that has caught backend↔
 * frontend drift, NaN and bad rounding on this app before.
 *
 * What the capture held, and what these pin:
 *   · market: daily mixed (Caution 60) · weekly bullish (Constructive 84) —
 *     the two disagree, so the tab must say so;
 *   · macro: 8 T1/T2 rows over 14 days with ONE "Jobless claims" per week,
 *     Thursdays only, and no "Retail sales" — the shadow-release fix, seen on
 *     live FRED data rather than the unit fixture;
 *   · sectors: 11 rows, the day leg LIVE, Technology the one 🔥 hot sector
 *     lagging RSP on the day.
 */
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import LIVE from './__fixtures__/news_tab_live_2026_09_24.json';
import NewsTabBoard from './NewsTabBoard';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => LIVE })) as any);
});
afterEach(() => vi.unstubAllGlobals());

const mount = async () => {
  const r = render(<MemoryRouter><NewsTabBoard /></MemoryRouter>);
  await screen.findByTestId('news-tab-board');
  return r;
};

describe('📰 News tab — the REAL served payload', () => {
  it('renders every block with no NaN, undefined or null leaking into the copy', async () => {
    const { container } = await mount();
    const text = container.textContent || '';
    // `[object Object]` is the exact failure this file first caught: the
    // benchmark is an object on the wire and was rendered as a string.
    for (const bad of ['NaN', 'undefined', 'Infinity', '[object Object]']) expect(text).not.toContain(bad);
    // "null" is legitimate prose here — the served study note speaks of the
    // 21-day NULL result — so it is only a leak where it stands in for a number.
    expect(text).not.toMatch(/\bnull\s*(pp|%|h\b|d\b|days)|vs null|· null/);
    for (const id of ['nt-section-verdict', 'nt-section-macro', 'nt-section-sectors', 'nt-section-headlines']) {
      expect(screen.getByTestId(id)).toBeInTheDocument();
    }
  });

  it('the market read is the gauge’s: daily mixed · weekly bullish, and it says they disagree', async () => {
    await mount();
    const daily = screen.getByTestId('nt-card-daily');
    const weekly = screen.getByTestId('nt-card-weekly');
    expect(daily).toHaveTextContent(/mixed/);
    expect(daily).toHaveTextContent(/Caution/);
    expect(daily).toHaveTextContent(/60/);
    expect(weekly).toHaveTextContent(/bullish/);
    expect(weekly).toHaveTextContent(/Constructive/);
    expect(weekly).toHaveTextContent(/84/);
    expect(screen.getByTestId('nt-section-verdict')).toHaveTextContent(/disagree/i);
  });

  it('macro: ONE jobless-claims row per week, Thursdays only, and no phantom retail sales', async () => {
    await mount();
    const rows = screen.getAllByTestId(/^nt-macro-row-/);
    expect(rows).toHaveLength(8);
    const claims = rows.filter((r) => /Jobless claims/.test(r.textContent || ''));
    expect(claims).toHaveLength(3);
    // one per ISO week — the double-count put a second row on each Friday
    const dates = (LIVE as any).macro.events
      .filter((e: any) => e.label === 'Jobless claims').map((e: any) => e.date);
    expect(dates).toEqual(['2026-09-24', '2026-10-01', '2026-10-08']);
    for (const d of dates) expect(new Date(`${d}T12:00:00Z`).getUTCDay()).toBe(4);
    expect(screen.getByTestId('nt-section-macro')).not.toHaveTextContent(/Retail sales/);
    expect(screen.getByTestId('nt-next-t1')).toHaveTextContent('Core PCE');
  });

  it('all eleven sectors, in served order, the day column labelled "today" because d1 is live', async () => {
    await mount();
    const rows = screen.getAllByTestId(/^nt-row-/);
    expect(rows.map((r) => r.getAttribute('data-testid')!.replace('nt-row-', '')))
      .toEqual((LIVE as any).sectors.rows.map((r: any) => r.sector));
    expect(rows).toHaveLength(11);
    expect(screen.getByTestId('nt-section-sectors')).toHaveTextContent(/today/i);
  });

  it('"🔥 hot, lagging today" is Technology — his "hot sectors that are bearish", one click', async () => {
    await mount();
    fireEvent.click(screen.getByTestId('nt-view-hot_lagging'));
    const rows = screen.getAllByTestId(/^nt-row-/);
    expect(rows.map((r) => r.getAttribute('data-testid'))).toEqual(['nt-row-Technology']);
  });

  it('each sector links to ITS OWN StockTitan sector, by GICS name', async () => {
    await mount();
    const tech = within(screen.getByTestId('nt-row-Technology')).getByTestId('nt-heatmap-Technology');
    expect(tech.getAttribute('href')).toBe(
      'https://www.stocktitan.net/stock-market-heatmap#sector=Information%20Technology');
    expect(tech).toHaveAttribute('target', '_blank');
  });

  it('NEGATIVE: never says "bounce" anywhere it renders', async () => {
    const { container } = await mount();
    expect(container.innerHTML).not.toMatch(/bounce/i);
  });
});

/* 🧠 the REAL model read (captured 2026-09-24 ~14:40 ET from the branch API on
 * :8001 after one live run of huihui_ai/Qwen3.8-abliterated:27b, 68 s): lean
 * mixed, both cases written, Technology named news-bullish, three served
 * releases to watch. The prose quotes 20% / 74% / S&P 500 — every one of them
 * is in the facts it was handed, which is why the server's guard let it through. */
import LIVE_MR from './__fixtures__/news_tab_live_model_read_2026_09_24.json';

describe('🧠 News tab model read — the REAL served payload', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => LIVE_MR })) as any);
  });

  it('renders the stored read with no object, NaN or undefined leaking', async () => {
    const { container } = await mount();
    const text = container.textContent || '';
    for (const bad of ['NaN', 'undefined', 'Infinity', '[object Object]']) expect(text).not.toContain(bad);
    expect(screen.getByTestId('nt-model-lean')).toHaveTextContent('lean: mixed');
    expect((screen.getByTestId('nt-model-bull').textContent || '').length).toBeGreaterThan(40);
    expect((screen.getByTestId('nt-model-bear').textContent || '').length).toBeGreaterThan(40);
    expect(screen.getByTestId('nt-model-meta')).toHaveTextContent('read by huihui_ai/Qwen3.8-abliterated:27b');
    expect(screen.getByTestId('nt-model-sectors')).toHaveTextContent('news-bullish Technology');
    expect(screen.getByTestId('nt-model-watch')).toHaveTextContent('Jobless claims');
    expect(screen.getByTestId('nt-model-note')).toHaveTextContent('UNMEASURED');
  });

  it('every sector and release the model named is one the same payload serves', () => {
    const read = (LIVE_MR as any).model_read.read;
    const sectors = new Set((LIVE_MR as any).sectors.rows.map((r: any) => r.sector));
    const labels = new Set((LIVE_MR as any).macro.events.map((e: any) => e.label));
    for (const s of [...read.sectors_bullish, ...read.sectors_bearish]) expect(sectors.has(s), s).toBe(true);
    for (const w of read.watch) expect(labels.has(w), w).toBe(true);
  });
});
