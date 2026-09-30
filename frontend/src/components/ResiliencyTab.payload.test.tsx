import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FIXTURE from './__fixtures__/resiliency_tab_2026_09_30.json';
import { PatternChart } from './PatternChart';
import ResiliencyBoardNote from './ResiliencyBoardNote';
import ChartMaps from '../pages/ChartMaps';
import type { CmBoard, CmTile } from '../lib/chartMaps';

/* 🛡️ Resiliency tab — payloads through the REAL components and page (2026-09-30).
 *
 * Ajay 2026-09-30, verbatim: "Can you build me a new tab- Resileincy. This is
 * to help me with #1 - Stocks that are not going to by more than 0.5% during a
 * T1 event like FOMC or any others like todays Inflation and GDP track T2s as
 * well. #3 - Tape is positive and bullish EOD or Pre market. but volume has to
 * be accounted for. We have all of this data already."
 *
 * THE FIXTURE starts SYNTHETIC (its `_comment` says so), shaped as spec §3.8
 * with an event-session payload (unfiltered and 🛡️ T1 ticked), a non-event
 * payload (?sort=res_today coerced), a warming and an error payload. The main
 * session overwrites it with the probe's REAL bytes (spec §5). This test is
 * LAYOUT-AGNOSTIC so the real capture drops in unchanged: every top-level
 * value that is a `tab: "resiliency"` payload is read, and each is classified
 * by its OWN served state (`resiliency_board.state`, `today.event_day`) —
 * never by its key. Only contract keys are read. */

type Payload = CmBoard & { warming?: boolean };
/* Fix round 2026-09-30: the probe writes every payload at the TOP level (plus a
 * forced warming and error payload); an older capture nested them under
 * `variants`. Both layouts are read, so a real capture drops in unchanged. */
const RAW = FIXTURE as unknown as Record<string, unknown>;
const NESTED = RAW.variants && typeof RAW.variants === 'object' && !Array.isArray(RAW.variants)
  ? (RAW.variants as Record<string, unknown>) : {};
const F: Record<string, unknown> = { ...RAW, ...NESTED };
const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity'];
const SHIELD = '\u{1F6E1}\u{FE0F}';
const CAL = '\u{1F4C5}';
const FACE_STATS = ['T1 held', 'T2 held', 'EOD tape', 'Pre-market'];

const PAYLOADS: Array<[string, Payload]> = Object.entries(F)
  .filter(([, v]) => !!v && typeof v === 'object' && !Array.isArray(v) && (v as { tab?: unknown }).tab === 'resiliency')
  .map(([k, v]) => [k, v as Payload]);
const stateOf = (p: Payload) => p.resiliency_board?.state ?? 'none';
const READY = PAYLOADS.filter(([, p]) => stateOf(p) === 'ready' && (p.tiles || []).length > 0);
const EVENT = READY.filter(([, p]) => p.resiliency_board?.today?.event_day === true);
const NON_EVENT = READY.filter(([, p]) => p.resiliency_board?.today?.event_day === false);
const WARMING = PAYLOADS.filter(([, p]) => stateOf(p) === 'warming');
const ERROR = PAYLOADS.filter(([, p]) => stateOf(p) === 'error');

const renderTile = (t: CmTile) =>
  render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);

describe('🛡️ Resiliency fixture — what it covers', () => {
  it('carries at least one ready payload with cards, and every payload is the resiliency tab with the four served sorts', () => {
    expect(PAYLOADS.length).toBeGreaterThan(0);
    expect(READY.length).toBeGreaterThan(0);
    for (const [k, p] of PAYLOADS) {
      expect(p.tab, k).toBe('resiliency');
      expect((p.sorts || []).map((s) => s.key), k).toEqual(['default', 'res_t2', 'res_down', 'res_today']);
      expect(p.resiliency_board, k).toBeTruthy();
      expect(p.resiliency_board!.measured, k).toBe(false);
      expect(p.resiliency_board!.note, k).toContain('UNMEASURED');
      expect(p.enterable_kind ?? 'n/a', k).toBe('n/a');
    }
  });

  it('every ready payload serves a boolean today.event_day (so each is checked as an event or a non-event session)', () => {
    expect(EVENT.length + NON_EVENT.length).toBe(READY.length);
    // eslint-disable-next-line no-console
    console.log(`🛡️ fixture: ${EVENT.length} event-session, ${NON_EVENT.length} non-event, ${WARMING.length} warming, ${ERROR.length} error payload(s)`);
  });
});

describe.each(READY)('🛡️ Resiliency payload %s → real components', (key, P) => {
  const board = P;
  const rb = board.resiliency_board!;
  const tiles = board.tiles as CmTile[];
  const event = rb.today?.event_day === true;
  const active = new Set(rb.filters?.active ?? []);

  it('every card: the 🛡️ hold chip on the IDENT rung, the four face stats, no junk, never bounce / fake', () => {
    const rows: string[] = [];
    for (const t of tiles) {
      const r = t.resiliency!;
      expect(r, t.symbol).toBeTruthy();
      const { container, unmount } = renderTile(t);
      const ident = container.querySelector('.cm-tile-ident');
      expect(ident, `${t.symbol} IDENT`).not.toBeNull();
      const hold = (t.badges || []).find((b) => b.text.startsWith(`${SHIELD} T1 held`));
      if (r.t1 && r.t1.n > 0) {
        expect(hold, `${t.symbol} 🛡️ T1 chip`).toBeTruthy();
        expect(ident!.textContent || '', t.symbol).toContain(hold!.text);
        expect(hold!.tone, t.symbol).toBe(t.res_filter?.t1 === true ? 'good' : 'muted');
      } else {
        expect(hold, `${t.symbol} has no T1 sessions, so no chip`).toBeUndefined();
      }
      const keys = (t.stats || []).map((s) => s.k);
      for (const k of FACE_STATS) {
        expect(keys, `${t.symbol} ${k}`).toContain(k);
        const face = container.querySelector('.cm-rung-setup');
        expect(face?.textContent || '', `${t.symbol} ${k} on the face`).toContain(k);
      }
      // Every served box badge sits on IDENT and matches a TICKED box the tile passed.
      for (const b of (t.badges || []).filter((x) => x.res_filter)) {
        expect(active.has(b.res_filter!), `${t.symbol} ${b.text}`).toBe(true);
        expect(t.res_filter?.[b.res_filter as 't1' | 't2' | 'eod' | 'pre'], `${t.symbol} ${b.text}`).toBe(true);
        expect(ident!.textContent || '', t.symbol).toContain(b.text);
      }
      const html = container.innerHTML;
      for (const bad of JUNK) expect(html.includes(bad), `${t.symbol} ${bad}`).toBe(false);
      expect(/bounce|fake|won't drop/i.test(container.textContent || ''), t.symbol).toBe(false);
      rows.push(`${t.symbol}: ${hold?.text ?? '(no T1 sessions)'}`);
      unmount();
    }
    // eslint-disable-next-line no-console
    console.log([`🛡️ Resiliency ${key} — IDENT rows`, ...rows].join('\n'));
  });

  it(event
    ? 'event session: every card with a print today carries the 📅 today pill on the PRICE rung; one with none says so and carries none'
    : 'non-event session: no card carries a 📅 today pill or a Today stat', () => {
    for (const t of tiles) {
      const r = t.resiliency!;
      const pill = (t.badges || []).find((b) => b.text.startsWith(CAL));
      const { container, unmount } = renderTile(t);
      if (event && r.today.state === 'read') {
        expect(pill, `${t.symbol} 📅`).toBeTruthy();
        expect(pill!.text.startsWith(`${CAL} T${r.today.tier} today`), t.symbol).toBe(true);
        expect(pill!.tone, t.symbol).toBe(r.today.holding ? 'good' : 'warn');
        const price = container.querySelector('.cm-rung-price');
        expect(price, `${t.symbol} PRICE rung`).not.toBeNull();
        expect(price!.textContent || '', t.symbol).toContain(pill!.text);
        expect(pill!.text.includes('holding'), t.symbol).toBe(r.today.holding === true);
      } else {
        expect(pill, `${t.symbol} no 📅 without a read`).toBeUndefined();
        // NEGATIVE: never "holding +0.00%" for a name with no print
        expect((container.textContent || '').includes('holding +0.00%'), t.symbol).toBe(false);
      }
      if (!event) {
        expect((t.stats || []).some((s) => s.k === 'Today'), t.symbol).toBe(false);
        expect((container.textContent || '').includes(CAL), t.symbol).toBe(false);
      }
      unmount();
    }
  });

  it('the served board lines render verbatim; the counts add up; the pressed button is the served sort', () => {
    const { getByTestId, queryByTestId } = render(
      <ResiliencyBoardNote board={rb} sorts={board.sorts} sort={board.sort} onSort={() => {}}
                           onToggleFilter={() => {}} onToggleMode={() => {}} />);
    expect(getByTestId('cm-res-header').textContent).toBe(rb.header);
    if (rb.today_line) expect(getByTestId('cm-res-today').textContent).toBe(rb.today_line);
    if (rb.events_line) expect(getByTestId('cm-res-events').textContent).toBe(rb.events_line);
    expect(getByTestId(`cm-res-sort-${board.sort}`).getAttribute('aria-pressed')).toBe('true');
    expect(rb.sort).toBe(board.sort);
    for (const it of rb.filters?.items ?? []) {
      expect((getByTestId(`cm-res-filter-${it.key}`) as HTMLInputElement).checked, it.key).toBe(it.on === true);
    }
    if (!active.size) expect(queryByTestId('cm-res-filter-mode')).toBeNull();
    const c = rb.counts!;
    expect(c.rated_t1 + c.partial_t1 + c.no_bars).toBeLessThanOrEqual(c.scanned);
    expect(c.t1_pass).toBeLessThanOrEqual(c.rated_t1);
    expect(c.t2_pass).toBeLessThanOrEqual(c.rated_t2);
    expect(c.eod_pass).toBeLessThanOrEqual(c.eod_read);
    expect(c.pre_pass).toBeLessThanOrEqual(c.pre_read);
    expect(tiles.length).toBeLessThanOrEqual(80);
    const text = getByTestId('cm-res-board').textContent || '';
    for (const bad of JUNK) expect(text.includes(bad), bad).toBe(false);
    expect(/bounce|fake|won't drop/i.test(text)).toBe(false);
  });

  it(event ? 'event session: no "not a data day" coercion' : 'non-event: a served res_today request is coerced, and the served reason says so', () => {
    if (event) {
      expect(board.sort_unavailable ?? null).toBeNull();
    } else if (board.sort_unavailable) {
      expect(board.sort).toBe('default');
      expect(board.sort_unavailable).toContain('not a T1 or T2 data day');
    }
  });
});

describe('🛡️ Resiliency warming / error payloads → the note', () => {
  // A ready-state capture may carry neither (an empty suite fails the run).
  if (WARMING.length + ERROR.length === 0) it.skip('this capture carries no warming or error payload', () => {});
  it.each(WARMING)('%s: the served warming line with role=status, no boxes, no cards', (_k, P) => {
    const rb = P.resiliency_board!;
    expect(P.tiles).toEqual([]);
    const { getByTestId, queryByTestId } = render(
      <ResiliencyBoardNote board={rb} sorts={P.sorts} sort={P.sort} onSort={() => {}} onToggleFilter={() => {}} />);
    expect(getByTestId('cm-res-header').textContent).toBe(rb.header);
    expect(getByTestId('cm-res-header').getAttribute('role')).toBe('status');
    expect(queryByTestId('cm-res-filters')).toBeNull();
  });
  it.each(ERROR)('%s: the served error line, no cards', (_k, P) => {
    const rb = P.resiliency_board!;
    expect(P.tiles).toEqual([]);
    const { getByTestId } = render(
      <ResiliencyBoardNote board={rb} sorts={P.sorts} sort={P.sort} onSort={() => {}} />);
    expect(getByTestId('cm-res-header').textContent).toBe(rb.header);
    expect(getByTestId('cm-res-board').getAttribute('data-state')).toBe('error');
  });
});

describe('🛡️ Resiliency — the real page on the payloads', () => {
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

  it.each(READY)('%s: the cards in served order, the served header, the toggle asks the server for ?sort=res_t2', async (_k, P) => {
    const fetchMock = stub(() => fresh(P));
    vi.stubGlobal('fetch', fetchMock);
    page('/chart-maps?tab=resiliency&show=all');
    const want = (P.tiles as CmTile[]).map((t) => t.symbol);
    await waitFor(() => expect(order()).toEqual(want));
    expect(screen.getByTestId('cm-res-header').textContent).toBe(P.resiliency_board!.header);
    fireEvent.click(screen.getByTestId('cm-res-sort-res_t2'));
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes('sort=res_t2'))).toBe(true));
    const body = document.body.textContent || '';
    for (const bad of JUNK) expect(body.includes(bad), bad).toBe(false);
    expect(/bounce|fake|won't drop/i.test(body)).toBe(false);
    if (P.sort_unavailable) expect(body).toContain(P.sort_unavailable);
  });

  it.each(WARMING)('%s: the page prints the served warming line and skips the generic demand-scan wait', async (_k, P) => {
    vi.stubGlobal('fetch', stub(() => fresh(P)));
    page('/chart-maps?tab=resiliency');
    await waitFor(() => expect(screen.getByTestId('cm-res-header').textContent).toBe(P.resiliency_board!.header));
    expect(screen.getByTestId('cm-res-header').getAttribute('role')).toBe('status');
    const exact = Array.from(document.querySelectorAll('p')).filter((p) => p.textContent === GENERIC_WAIT);
    expect(exact).toHaveLength(0);
    expect(order()).toEqual([]);
  });
});
