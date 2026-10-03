import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FIXTURE from './__fixtures__/fallen_tab_2026_10_02.json';
import { PatternChart } from './PatternChart';
import FallenBoardNote from './FallenBoardNote';
import FallenCardExtras from './FallenCardExtras';
import ChartMaps from '../pages/ChartMaps';
import type { CmBoard, CmTile } from '../lib/chartMaps';

/* 📉 Down 40%+ tab — payloads through the REAL components and page (2026-10-02).
 *
 * Ajay 2026-10-02, verbatim: "Can you build me a tab in chart maps about
 * stocks that dropped more than 40% lowers from like app loving company as an
 * example whcih si 60% low. But I also need you to capture informations about
 * sales like Bondes and other indicators based on Bondes formula please." then
 * "Scan the universe and bring me these stocks" and "also add things like
 * possible catalyst that made is drop like that."
 *
 * THE FIXTURE starts SYNTHETIC (its `_comment` says so), shaped as spec §3.7:
 * a ready payload at the default depth, one at 60%, a warming and an error
 * payload. The main session overwrites it with the probe's REAL bytes (spec
 * §5.4) — possibly ONE payload at the top level. This test is
 * LAYOUT-AGNOSTIC so the real capture drops in unchanged: the top level
 * itself, every top-level value and every `variants` value that is a
 * `tab: "fallen"` payload is read, each classified by its OWN served state
 * (`fallen_board.state`) — never by its key. Only contract keys are read.
 *
 * THE REAL-DATA PINS (APP 63.18% under 738.01 set 2025-12-22; CTVA held out,
 * named in the suspects fold) switch on by themselves once the capture is a
 * real one — i.e. once `_comment` no longer says SYNTHETIC. */

type Payload = CmBoard & { warming?: boolean; _comment?: string };
const RAW = FIXTURE as unknown as Record<string, unknown>;
const NESTED = RAW.variants && typeof RAW.variants === 'object' && !Array.isArray(RAW.variants)
  ? (RAW.variants as Record<string, unknown>) : {};
const isFallen = (v: unknown): v is Payload =>
  !!v && typeof v === 'object' && !Array.isArray(v) && (v as { tab?: unknown }).tab === 'fallen';
const PAYLOADS: Array<[string, Payload]> = [
  ...(isFallen(RAW) ? [['top', RAW as unknown as Payload] as [string, Payload]] : []),
  ...Object.entries({ ...RAW, ...NESTED }).filter(([, v]) => isFallen(v)).map(([k, v]) => [k, v as Payload] as [string, Payload]),
];
const SYNTHETIC = /SYNTHETIC/.test(String(RAW._comment ?? ''));
const stateOf = (p: Payload) => p.fallen_board?.state ?? 'none';
const READY = PAYLOADS.filter(([, p]) => stateOf(p) === 'ready' && (p.tiles || []).length > 0);
const WARMING = PAYLOADS.filter(([, p]) => stateOf(p) === 'warming');
const ERROR = PAYLOADS.filter(([, p]) => stateOf(p) === 'error');
const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity'];
const MARK = '\u{1F4C9}';
const SORT_KEYS = ['default', 'fallen_depth', 'fallen_sales', 'market_cap', 'market_cap_asc'];

const renderCard = (t: CmTile, legend: unknown) => render(
  <MemoryRouter>
    <PatternChart tile={t} />
    <FallenCardExtras tile={t} legend={legend as never} />
  </MemoryRouter>);

describe('📉 fixture — what it covers', () => {
  it('carries at least one ready payload with cards; every payload is the fallen tab with the five served sorts, measured false, UNMEASURED', () => {
    expect(PAYLOADS.length).toBeGreaterThan(0);
    expect(READY.length).toBeGreaterThan(0);
    for (const [k, p] of PAYLOADS) {
      expect(p.tab, k).toBe('fallen');
      expect((p.sorts || []).map((s) => s.key), k).toEqual(SORT_KEYS);
      expect(p.fallen_board, k).toBeTruthy();
      expect(p.fallen_board!.measured, k).toBe(false);
      expect(p.fallen_board!.note, k).toContain('UNMEASURED');
      expect(p.enterable_kind ?? 'n/a', k).toBe('n/a');
    }
    // eslint-disable-next-line no-console
    console.log(`📉 fixture (${SYNTHETIC ? 'synthetic' : 'real'}): ${READY.length} ready, ${WARMING.length} warming, ${ERROR.length} error payload(s)`);
  });
});

describe.each(READY)('📉 payload %s → real components', (_key, P) => {
  const fb = P.fallen_board!;
  const tiles = P.tiles as CmTile[];

  it('the board: served lines verbatim, the legend once, served depth / sort pressed, counts invariant', () => {
    const { getByTestId, getAllByTestId } = render(
      <FallenBoardNote board={fb} sorts={P.sorts} sort={P.sort} onSort={() => {}} onDepth={() => {}} />);
    expect(getByTestId('cm-fallen-header').textContent).toBe(fb.header);
    expect(getByTestId('cm-fallen-note').textContent).toBe(fb.note);
    if (fb.count_line) expect(getByTestId('cm-fallen-counts').textContent).toBe(fb.count_line);
    expect(getAllByTestId('bonde-criteria')).toHaveLength(1);
    const on = (fb.depths || []).filter((d) => d.on);
    expect(on).toHaveLength(1);
    expect(getByTestId(`cm-fallen-depth-${on[0].key}`).getAttribute('aria-pressed')).toBe('true');
    expect(getByTestId(`cm-fallen-sort-${P.sort}`).getAttribute('aria-pressed')).toBe('true');
    const c = fb.counts!;
    expect(c.scanned).toBe(c.no_bars + c.delisted + c.etf + c.stale + c.short_history + c.under_threshold + c.data_suspect + c.fallen);
    expect(c.at_depth).toBeLessThanOrEqual(c.fallen);
    expect(c.shown).toBeLessThanOrEqual(c.at_depth - c.dropped_thin);
    expect(tiles.length).toBeLessThanOrEqual(80);
    const text = getByTestId('cm-fallen-board').textContent || '';
    for (const bad of JUNK) expect(text.includes(bad), bad).toBe(false);
    expect(/bounce|fake/i.test(text)).toBe(false);
  });

  it('every card: the 📉 pill on the PRICE rung, its served 💥 line, the Bonde chips; at or past the served depth; never junk / bounce / fake', () => {
    const rows: string[] = [];
    for (const t of tiles) {
      const f = t.fallen!;
      expect(f, t.symbol).toBeTruthy();
      expect(f.pct_below, t.symbol).toBeGreaterThanOrEqual(fb.depth_pct);
      expect(f.pct_below, t.symbol).toBeGreaterThanOrEqual(fb.threshold_pct);
      const { container, unmount } = renderCard(t, fb.pick_legend);
      const pill = (t.badges || []).find((b) => b.text.startsWith(`${MARK} `) && b.text.endsWith(' below the 52-week high'));
      expect(pill, `${t.symbol} 📉 pill`).toBeTruthy();
      expect(container.querySelector('.cm-rung-price')?.textContent || '', `${t.symbol} PRICE rung`).toContain(pill!.text);
      expect(screen.getByTestId(`cm-fallen-hit-${t.symbol}`).textContent).toBe(f.hit.text);
      expect(f.hit.text, t.symbol).toContain('possible:');
      if (t.pick && t.pick.legs) expect(screen.getByTestId(`bd-pick-${t.symbol}`), t.symbol).toBeTruthy();
      const html = container.innerHTML;
      for (const bad of JUNK) expect(html.includes(bad), `${t.symbol} ${bad}`).toBe(false);
      expect(/bounce|fake|caused|because/i.test(container.textContent || ''), t.symbol).toBe(false);
      rows.push(`${t.symbol}: ${pill!.text} · ${f.hit.class}`);
      unmount();
    }
    // eslint-disable-next-line no-console
    console.log([`📉 ${_key} — cards`, ...rows].join('\n'));
  });

  it(SYNTHETIC ? 'APP spot-check (63.18% under 738.01, 2025-12-22, close 271.73) — synthetic capture carries it by hand'
    : 'REAL capture: APP listed 63.18% under 738.01 set 2025-12-22, close 271.73; CTVA held out and named', () => {
    const app = tiles.find((t) => t.symbol === 'APP');
    // APP must be listed on the default view (the trimmed capture keeps it);
    // on any other view it is checked wherever it appears.
    if (fb.depth_pct === fb.threshold_pct && P.sort === 'default') expect(app, 'APP listed').toBeTruthy();
    if (app) {
      expect(app.fallen!.pct_below).toBe(63.18);
      expect(app.fallen!.high).toBe(738.01);
      expect(app.fallen!.high_date).toBe('2025-12-22');
      expect(app.fallen!.close).toBe(271.73);
    }
    expect(tiles.some((t) => t.symbol === 'CTVA'), 'CTVA never listed').toBe(false);
    if (!SYNTHETIC) expect((fb.suspects?.lines || []).some((l) => l.startsWith('CTVA ')), 'CTVA named in the fold').toBe(true);
  });
});

describe('📉 warming / error payloads → the note', () => {
  if (WARMING.length + ERROR.length === 0) it.skip('this capture carries no warming or error payload', () => {});
  it.each(WARMING)('%s: the served warming line with role=status, no legend, no cards', (_k, P) => {
    const fb = P.fallen_board!;
    expect(P.tiles).toEqual([]);
    expect(fb.counts).toBeNull();
    const { getByTestId, queryByTestId } = render(
      <FallenBoardNote board={fb} sorts={P.sorts} sort={P.sort} onSort={() => {}} onDepth={() => {}} />);
    expect(getByTestId('cm-fallen-header').textContent).toBe(fb.header);
    expect(getByTestId('cm-fallen-header').getAttribute('role')).toBe('status');
    expect(queryByTestId('bonde-criteria')).toBeNull();
  });
  it.each(ERROR)('%s: the served error line, no cards', (_k, P) => {
    const fb = P.fallen_board!;
    expect(P.tiles).toEqual([]);
    const { getByTestId } = render(
      <FallenBoardNote board={fb} sorts={P.sorts} sort={P.sort} onSort={() => {}} onDepth={() => {}} />);
    expect(getByTestId('cm-fallen-header').textContent).toBe(fb.header);
    expect(getByTestId('cm-fallen-board').getAttribute('data-state')).toBe('error');
  });
});

describe('📉 the real page on the payloads', () => {
  const fresh = (p: Payload) => JSON.parse(JSON.stringify(p)) as Payload;
  const stub = (pick: (url: string) => unknown) => vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => pick(url) } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
  const page = (entry: string) =>
    render(<MemoryRouter initialEntries={[entry]}><ChartMaps /></MemoryRouter>);
  const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);
  const GENERIC_WAIT = "The charts appear here as soon as it lands; you don't need to refresh.";

  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it.each(READY)('%s: the cards in served order, each wrapped with its 💥 line, the legend once on the page', async (_k, P) => {
    vi.stubGlobal('fetch', stub(() => fresh(P)));
    page('/chart-maps?tab=fallen&show=all');
    const want = (P.tiles as CmTile[]).map((t) => t.symbol);
    await waitFor(() => expect(order()).toEqual(want));
    expect(screen.getByTestId('cm-fallen-header').textContent).toBe(P.fallen_board!.header);
    expect(screen.getAllByTestId('bonde-criteria')).toHaveLength(1);
    for (const t of P.tiles as CmTile[]) {
      const card = screen.getByTestId(`cm-fallen-card-${t.symbol}`);
      expect(card.querySelector('.cm-tile')).not.toBeNull();
      expect(card.textContent || '').toContain(t.fallen!.hit.text);
      // the extras are a SIBLING of the tile's link — never an <a> inside an <a>
      expect(card.querySelector('a a')).toBeNull();
    }
    const body = document.body.textContent || '';
    for (const bad of JUNK) expect(body.includes(bad), bad).toBe(false);
    expect(/bounce|fake/i.test(body)).toBe(false);
  });

  it.each(WARMING)('%s: the page prints the served warming line and skips the generic demand-scan wait', async (_k, P) => {
    vi.stubGlobal('fetch', stub(() => fresh(P)));
    page('/chart-maps?tab=fallen');
    await waitFor(() => expect(screen.getByTestId('cm-fallen-header').textContent).toBe(P.fallen_board!.header));
    expect(screen.getByTestId('cm-fallen-header').getAttribute('role')).toBe('status');
    const exact = Array.from(document.querySelectorAll('p')).filter((p) => p.textContent === GENERIC_WAIT);
    expect(exact).toHaveLength(0);
    expect(order()).toEqual([]);
  });
});
