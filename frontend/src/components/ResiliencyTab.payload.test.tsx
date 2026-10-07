import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FIXTURE from './__fixtures__/resiliency_tab_2026_10_07.json';
import { PatternChart } from './PatternChart';
import ResiliencyBoardNote from './ResiliencyBoardNote';
import ChartMaps from '../pages/ChartMaps';
import type { CmBoard, CmTile } from '../lib/chartMaps';

/* 🛡️ Resiliency tab — payloads through the REAL components and page
 * (2026-09-30; 📅 every session + 🚀 growth since 2026-10-07).
 *
 * Ajay 2026-10-07, verbatim: "Can you do a scan for me on the reseliency tab..
 * Is it working? Today is a very red day.. I wanna see which stocks were
 * reselient cuz Vista was very reselient", then "I want the highest growth
 * stocks on top like Vistra for example".
 *
 * THE FIXTURE is the probe's REAL capture (scripts/resiliency_tab_cost_probe.py
 * --dump-fixture): the api.chart_maps handler's JSONResponse bodies for
 * default / res_t1 / res_t2 / the boxes / res_today / res_growth, plus a forced
 * warming and error payload. This test is LAYOUT-AGNOSTIC: every top-level
 * value that is a `tab: "resiliency"` payload is read, and each is checked by
 * its OWN served state (`resiliency_board.state`, `today.mode`, the served
 * `sort`) — never by its key. Only contract keys are read. One SYNTHETIC
 * closed-mode payload (built below from the captured res_t1 one) joins them so
 * the dated `last_session` pill branch runs (critic 2026-10-07). */

type Payload = CmBoard & { warming?: boolean };
const RAW = FIXTURE as unknown as Record<string, unknown>;
const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity'];
const SHIELD = '\u{1F6E1}\u{FE0F}';
const CAL = '\u{1F4C5}';
const FACE_STATS = ['T1 held', 'T2 held', 'EOD tape', 'Pre-market'];
const SIX = ['default', 'res_today', 'res_t1', 'res_t2', 'res_down', 'res_growth'];
const FIVE = SIX.slice(1);
const RETIRED = 'not a T1 or T2 data day';

const CAPTURED: Array<[string, Payload]> = Object.entries(RAW)
  .filter(([, v]) => !!v && typeof v === 'object' && !Array.isArray(v) && (v as { tab?: unknown }).tab === 'resiliency')
  .map(([k, v]) => [k, v as Payload]);

/* SYNTHETIC closed-mode payload (critic 2026-10-07): the capture was taken after
 * the close, so the dated `last_session` pill branch never ran. Built from the
 * captured res_t1 payload by the backend's closed-mode words: today.mode
 * 'closed', every read `basis: 'last_session'` + `for_today: false` (no Today
 * stat), the 📅 badge `📅 last session Tue 10-06 · ±x.xx%`, one card stale (no
 * pill), served sort res_t1 with `default` labelled '🛡️ T1 hold rate (default)'. */
const LAST_DAY = '2026-10-06';
const signed = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
function closedPayload(): [string, Payload] | null {
  const src = CAPTURED.find(([, p]) => p.sort === 'res_t1' && (p.tiles || []).length > 1);
  if (!src) return null;
  const p = JSON.parse(JSON.stringify(src[1])) as Payload;
  const rb = p.resiliency_board!;
  p.sort = 'res_t1';
  rb.sort = 'res_t1';
  p.sorts = (p.sorts || []).map((s) => (s.key === 'default' ? { ...s, label: `${SHIELD} T1 hold rate (default)` } : s));
  rb.today = { ...rb.today!, mode: 'closed', day: LAST_DAY, data_pre: false, spy_basis: 'last_session' };
  rb.market_line = `${CAL} Last session (Tue 10-06 close): SPY +0.40% · RSP +0.10% · median name +0.25% (up) · 2 of 3 names read are up.`;
  (p.tiles as CmTile[]).forEach((t, i) => {
    const r = t.resiliency!;
    const stale = i === 1;
    const mv = i === 0 ? 2.5 : i % 3 === 0 ? -1.25 : 0.4;
    r.today = {
      ...r.today, mode: 'closed', day: LAST_DAY, for_today: false, tier: null, event_day: false, labels: [],
      tape: null, as_of_et: null,
      ...(stale
        ? { state: 'stale', move_pct: null, holding: null, print: null, prev_close: null, basis: null }
        : { state: 'read', move_pct: mv, holding: mv >= -0.5, print: 50, prev_close: 49, basis: 'last_session' }),
    } as typeof r.today;
    const rest = (t.badges || []).filter((b) => !b.text.startsWith(CAL));
    const pill = stale ? [] : [{ text: `${CAL} last session Tue 10-06 · ${signed(mv)}`, tone: mv >= -0.5 ? 'good' : 'warn' }];
    t.badges = [...rest.slice(0, 1), ...pill, ...rest.slice(1)] as typeof t.badges;
    t.stats = (t.stats || []).filter((st) => st.k !== 'Today');
  });
  return ['synthetic_closed_last_session', p];
}
const SYNTH = closedPayload();
const PAYLOADS: Array<[string, Payload]> = SYNTH ? [...CAPTURED, SYNTH] : CAPTURED;
const stateOf = (p: Payload) => p.resiliency_board?.state ?? 'none';
const READY = PAYLOADS.filter(([, p]) => stateOf(p) === 'ready' && (p.tiles || []).length > 0);
const WARMING = PAYLOADS.filter(([, p]) => stateOf(p) === 'warming');
const ERROR = PAYLOADS.filter(([, p]) => stateOf(p) === 'error');

const renderTile = (t: CmTile) =>
  render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);

describe('🛡️ Resiliency fixture — what it covers', () => {
  it('ready payloads with cards; every payload serves the six sorts, `default` labelled as resolved, an explicit served sort', () => {
    expect(PAYLOADS.length).toBeGreaterThan(0);
    expect(READY.length).toBeGreaterThan(0);
    for (const [k, p] of PAYLOADS) {
      expect(p.tab, k).toBe('resiliency');
      expect((p.sorts || []).map((s) => s.key), k).toEqual(SIX);
      expect((p.sorts || [])[0].label.endsWith(' (default)'), k).toBe(true);
      expect(FIVE, k).toContain(p.sort);
      expect(p.resiliency_board, k).toBeTruthy();
      expect(p.resiliency_board!.measured, k).toBe(false);
      expect(p.resiliency_board!.note, k).toContain('UNMEASURED');
      expect(p.enterable_kind ?? 'n/a', k).toBe('n/a');
      // NEGATIVE: the retired not-a-data-day sentence is served nowhere
      expect(JSON.stringify(p).includes(RETIRED), k).toBe(false);
    }
    // eslint-disable-next-line no-console
    console.log(`🛡️ fixture: ${READY.length} ready (${READY.map(([k, p]) => `${k}:${p.sort}/${p.resiliency_board?.today?.mode}`).join(', ')}), ${WARMING.length} warming, ${ERROR.length} error`);
  });
});

describe('🛡️ Resiliency synthetic closed-mode payload — the dated last-session branch', () => {
  it('is built and served: mode closed, res_t1, every read dated `last session`, none says today, no Today stat', () => {
    expect(SYNTH, 'the capture carries a res_t1 payload to build from').not.toBeNull();
    const [k, P] = SYNTH!;
    expect(READY.map(([key]) => key)).toContain(k);
    expect(P.resiliency_board!.today!.mode).toBe('closed');
    expect(P.sort).toBe('res_t1');
    expect((P.sorts || [])[0].label).toBe(`${SHIELD} T1 hold rate (default)`);
    const tiles = P.tiles as CmTile[];
    const reads = tiles.filter((t) => t.resiliency!.today.basis === 'last_session');
    expect(reads.length).toBeGreaterThan(0);
    for (const t of tiles) {
      const td = t.resiliency!.today;
      expect(td.for_today, t.symbol).toBe(false);
      const pills = (t.badges || []).filter((b) => b.text.startsWith(CAL));
      // NEGATIVE: a closed-mode card never says today; a stale card has no pill
      for (const b of pills) expect(b.text.startsWith(`${CAL} today`) || b.text.includes(' T1 today'), t.symbol).toBe(false);
      if (td.state !== 'read') expect(pills, t.symbol).toEqual([]);
      else expect(pills.map((b) => b.text), t.symbol).toEqual([expect.stringMatching(/^\u{1F4C5} last session Tue 10-06 · [+-]\d+\.\d{2}%$/u)]);
      expect((t.stats || []).some((st) => st.k === 'Today'), t.symbol).toBe(false);
    }
  });
});

describe.each(READY)('🛡️ Resiliency payload %s → real components', (key, P) => {
  const board = P;
  const rb = board.resiliency_board!;
  const tiles = board.tiles as CmTile[];
  const active = new Set(rb.filters?.active ?? []);

  it('every card: the 🛡️ hold chip and the growth chip on IDENT, the face stats, no junk, never bounce / fake', () => {
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
      } else {
        expect(hold, `${t.symbol} has no T1 sessions, so no chip`).toBeUndefined();
      }
      const chip = (t.badges || []).find((b) => b.text.startsWith('Sales ') && b.text.includes(' YoY ('));
      expect(chip, `${t.symbol} growth chip`).toBeTruthy();
      expect(ident!.textContent || '', `${t.symbol} growth chip on IDENT`).toContain(chip!.text);
      const g = r.growth;
      if (g && (['non_positive', 'too_small'] as string[]).includes(g.eps_base)) {
        expect(chip!.text, `${t.symbol} tiny / negative year-ago EPS shows blank`).toContain('EPS — YoY');
      }
      expect((t.stats || []).some((s) => s.k === 'Growth'), t.symbol).toBe(true);
      const keys = (t.stats || []).map((s) => s.k);
      for (const k of FACE_STATS) expect(keys, `${t.symbol} ${k}`).toContain(k);
      for (const b of (t.badges || []).filter((x) => x.res_filter)) {
        expect(active.has(b.res_filter!), `${t.symbol} ${b.text}`).toBe(true);
      }
      const html = container.innerHTML;
      for (const bad of JUNK) expect(html.includes(bad), `${t.symbol} ${bad}`).toBe(false);
      expect(/bounce|fake|won't drop/i.test(container.textContent || ''), t.symbol).toBe(false);
      unmount();
    }
  });

  it('the 📅 pill: T-label iff a tier on the session\'s own read, dated iff last session, plain otherwise; none without a read', () => {
    for (const t of tiles) {
      const td = t.resiliency!.today;
      const pill = (t.badges || []).find((b) => b.text.startsWith(CAL));
      const { container, unmount } = renderTile(t);
      if (td.state === 'read' && td.move_pct !== null) {
        expect(pill, `${t.symbol} 📅`).toBeTruthy();
        if (td.tier && td.for_today) expect(pill!.text.startsWith(`${CAL} T${td.tier} today · `), t.symbol).toBe(true);
        else if (td.basis === 'last_session') expect(pill!.text.startsWith(`${CAL} last session `), t.symbol).toBe(true);
        else expect(pill!.text.startsWith(`${CAL} today · `), t.symbol).toBe(true);
        expect(pill!.tone, t.symbol).toBe(td.holding ? 'good' : 'warn');
        const price = container.querySelector('.cm-rung-price');
        expect(price, `${t.symbol} PRICE rung`).not.toBeNull();
        expect(price!.textContent || '', t.symbol).toContain(pill!.text);
      } else {
        expect(pill, `${t.symbol} no 📅 without a read`).toBeUndefined();
        expect((t.badges || []).some((b) => b.text.includes('+0.00%')), t.symbol).toBe(false);
      }
      expect((t.stats || []).some((s) => s.k === 'Today'), `${t.symbol} Today stat iff for_today`).toBe(td.for_today === true);
      unmount();
    }
  });

  it('the order is the served sort\'s: 📅 reads first by move; 🚀 the EPS-ranked block first by score, unknown last', () => {
    if (board.sort === 'res_today') {
      const reads = tiles.map((t) => t.resiliency!.today.state === 'read' && t.resiliency!.today.move_pct !== null);
      const firstUnread = reads.indexOf(false);
      if (firstUnread >= 0) expect(reads.slice(firstUnread).every((x) => !x), key).toBe(true);
      const mv = tiles.filter((_t, i) => reads[i]).map((t) => t.resiliency!.today.move_pct as number);
      for (let i = 1; i < mv.length; i++) expect(mv[i], `${key} #${i}`).toBeLessThanOrEqual(mv[i - 1]);
    }
    if (board.sort === 'res_growth') {
      const gs = tiles.map((t) => t.resiliency!.growth!);
      const blk = gs.map((g) => (g.score === null ? 2 : g.eps_ranked ? 0 : 1));
      for (let i = 1; i < blk.length; i++) {
        expect(blk[i], `${key} block #${i}`).toBeGreaterThanOrEqual(blk[i - 1]);
        if (blk[i] === blk[i - 1] && blk[i] < 2) {
          expect(gs[i].score as number, `${key} score #${i}`).toBeLessThanOrEqual(gs[i - 1].score as number);
        }
      }
      if (tiles.length) expect(gs[0].eps_ranked, `${key} top is EPS-ranked`).toBe(true);
    }
  });

  it('the served board lines render verbatim (header, today line, 📅 market line); the pressed button is the served sort', () => {
    const { getByTestId, queryByTestId } = render(
      <ResiliencyBoardNote board={rb} sorts={board.sorts} sort={board.sort} onSort={() => {}}
                           onToggleFilter={() => {}} onToggleMode={() => {}} />);
    expect(getByTestId('cm-res-header').textContent).toBe(rb.header);
    if (rb.today_line) expect(getByTestId('cm-res-today').textContent).toBe(rb.today_line);
    if (rb.market_line) expect(getByTestId('cm-res-market').textContent).toBe(rb.market_line);
    else expect(queryByTestId('cm-res-market')).toBeNull();
    expect(getByTestId(`cm-res-sort-${board.sort}`).getAttribute('aria-pressed')).toBe('true');
    expect(queryByTestId('cm-res-sort-default')).toBeNull();
    expect(rb.sort).toBe(board.sort);
    const c = rb.counts!;
    expect(c.t1_pass).toBeLessThanOrEqual(c.rated_t1);
    expect(c.today_up ?? 0).toBeLessThanOrEqual(c.today_read ?? 0);
    expect(c.growth_eps_ranked ?? 0).toBeLessThanOrEqual(c.growth_ranked ?? 0);
    const text = getByTestId('cm-res-board').textContent || '';
    for (const bad of JUNK) expect(text.includes(bad), bad).toBe(false);
    expect(/bounce|fake|won't drop/i.test(text)).toBe(false);
    expect(text.includes(RETIRED)).toBe(false);
  });
});

describe('🛡️ Resiliency warming / error payloads → the note', () => {
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

  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it.each(READY)('%s: the cards in served order; 🚀 and 🛡️ T1 ask the server for sort=res_growth / sort=res_t1', async (_k, P) => {
    const fetchMock = stub(() => fresh(P));
    vi.stubGlobal('fetch', fetchMock);
    page('/chart-maps?tab=resiliency&show=all');
    const want = (P.tiles as CmTile[]).map((t) => t.symbol);
    await waitFor(() => expect(order()).toEqual(want));
    expect(screen.getByTestId('cm-res-header').textContent).toBe(P.resiliency_board!.header);
    if (P.resiliency_board!.market_line) {
      expect(screen.getByTestId('cm-res-market').textContent).toBe(P.resiliency_board!.market_line);
    }
    fireEvent.click(screen.getByTestId('cm-res-sort-res_growth'));
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes('sort=res_growth'))).toBe(true));
    fireEvent.click(screen.getByTestId('cm-res-sort-res_t1'));
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes('sort=res_t1'))).toBe(true));
    const body = document.body.textContent || '';
    for (const bad of JUNK) expect(body.includes(bad), bad).toBe(false);
    expect(/bounce|fake|won't drop/i.test(body)).toBe(false);
    expect(body.includes(RETIRED)).toBe(false);
  });
});
