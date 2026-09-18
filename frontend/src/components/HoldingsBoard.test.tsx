import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import HoldingsBoard from './HoldingsBoard';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

/* 📁 My holdings (2026-09-14). One Support tile per name he owns, his cost
 * on each, worst first — and a name whose chart fails must not take the
 * others down with it. */

vi.mock('./PatternChart', () => ({
  // `data-band-study` and the band read are exposed so the 2026-09-16 tests can
  // see what actually reached the one renderer that mounts BandStructureChip.
  PatternChart: ({ tile, bandStudy }: any) => (
    <div data-testid={`tile-${tile.symbol}`} data-band-study={bandStudy?.headline ?? ''}>
      {tile.symbol}
      {(tile.lines || []).map((l: any) => <span key={l.label}>{l.label}</span>)}
      {(tile.badges || []).map((b: any) => <span key={b.text}>{b.text}</span>)}
      {tile.band_structure
        ? <span data-testid={`band-${tile.symbol}`}>{tile.band_structure.stat}</span> : null}
    </div>
  ),
}));

const HOLDINGS = { rows: [
  { symbol: 'GLW', avg_cost: 143.37, quantity: 104.6, cost_basis: 14999.95, current_price: 143.6, stop: null },
  { symbol: 'CRDO', avg_cost: 167.649, quantity: 197, cost_basis: 33022.32, current_price: 150.09, stop: 140 },
  { symbol: 'BROKEN', avg_cost: 10, quantity: 1, cost_basis: 10, current_price: 9, stop: null },
] };

const tile = (sym: string) => ({
  symbol: sym, href: `/sepa/${sym}?tab=supply`, bars: [{ t: '2026-09-14', o: 1, h: 2, l: 0.5, c: 1.5, v: 1 }],
  bands: [{ kind: 'demand', lo: 1, hi: 1.2 }], lines: [{ price: 1.5, label: 'now', tone: 'now' }],
  markers: [], stats: [], why: '', badges: [],
});

function mem() {
  const store: Record<string, string> = {};
  return {
    getItem: (k: string) => (k in store ? store[k] : null),
    setItem: (k: string, v: string) => { store[k] = String(v); },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { for (const k of Object.keys(store)) delete store[k]; },
    key: (i: number) => Object.keys(store)[i] ?? null,
    get length() { return Object.keys(store).length; },
  };
}

function stubFetch(holdings: any = HOLDINGS) {
  const spy = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/portfolio/holdings')) return { ok: true, json: async () => holdings };
    const m = /symbol=([A-Z]+)/.exec(u);
    const sym = m ? m[1] : '';
    if (sym === 'BROKEN') return { ok: true, json: async () => ({ error: 'No price data for BROKEN.' }) };
    return { ok: true, json: async () => ({ tile: tile(sym), last_price: sym === 'CRDO' ? 150.09 : 143.6 }) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

describe('HoldingsBoard', () => {
  beforeEach(() => { vi.stubGlobal('localStorage', mem()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('draws one tile per holding with YOUR COST on it, worst position first', async () => {
    const spy = stubFetch();
    render(<MemoryRouter><HoldingsBoard days={130} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('tile-CRDO')).toBeInTheDocument());
    expect(screen.getByTestId('tile-GLW')).toBeInTheDocument();
    expect(screen.getByText('your cost 167.65')).toBeInTheDocument();
    expect(screen.getByText('your stop 140.00')).toBeInTheDocument();
    expect(screen.getByText('-10.5% vs your cost')).toBeInTheDocument();
    // worst first: CRDO (−10.5%) before GLW (+0.2%)
    const order = screen.getAllByTestId(/^tile-/).map((el) => el.getAttribute('data-testid'));
    expect(order).toEqual(['tile-CRDO', 'tile-GLW']);
    // 130 bars is the board's "6 months" → the 6m Support window
    const supportCalls = spy.mock.calls.map((c) => String(c[0])).filter((u) => u.includes('/chart-maps/support'));
    expect(supportCalls.length).toBe(3);
    expect(supportCalls.every((u) => u.includes('window=6m'))).toBe(true);
    // studies are off by default → no studies=true on the wire
    expect(supportCalls.some((u) => u.includes('studies=true'))).toBe(false);
  });

  it('NEGATIVE — a name whose chart fails is listed as failed, the rest still draw', async () => {
    stubFetch();
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('tile-CRDO')).toBeInTheDocument());
    expect(screen.queryByTestId('tile-BROKEN')).toBeNull();
    expect(screen.getByText(/No price data for BROKEN/)).toBeInTheDocument();
    expect(screen.getByText('BROKEN')).toBeInTheDocument();
  });

  it('NEGATIVE — no holdings is an empty state, never a blank grid', async () => {
    stubFetch({ rows: [] });
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/No holdings on your Portfolio page yet/)).toBeInTheDocument());
  });

  it('NEGATIVE — the holdings fetch failing says so instead of spinning forever', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500, json: async () => ({}) })));
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/Could not read your holdings/)).toBeInTheDocument());
  });
});


/* 🎯 ENTERABLE on 📁 My holdings (2026-09-15). The ONE board the filter must
 * never cut. He owns these; "not enterable" is a fact about a NEW entry, and
 * hiding a position he is already carrying is how a board stops answering
 * "what do I do about what I hold". The chip tells him; the row stays. */
describe('HoldingsBoard — the 🎯 read never hides a position', () => {
  beforeEach(() => { vi.stubGlobal('localStorage', mem()); _resetBounceRoomCache(); });
  afterEach(() => { vi.unstubAllGlobals(); _resetBounceRoomCache(); });

  const blocked = (short: string) => ({
    kind: 'demand', verdict: 'BLOCKED', reasons: [short], reason_short: [short],
    reason_text: [`served: ${short}`], measured: { status: 'pending' },
  });
  const withRoom = (holdings: any = HOLDINGS) => {
    const spy = vi.fn(async (url: string) => {
      const u = String(url);
      if (u.includes('/supply-demand/bounce-room')) {
        return { ok: true, json: async () => ({
          as_of: '2026-09-15T11:00:00-04:00', in_session: true, params: {},
          requested: 3, covered: 3, pending: 0, unavailable: 0,
          rows: {
            CRDO: { symbol: 'CRDO', coverage: 'store', print: 150.09, enterable: blocked('room < 5%') },
            GLW: { symbol: 'GLW', coverage: 'store', print: 143.6, enterable: blocked('not at band') },
            BROKEN: { symbol: 'BROKEN', coverage: 'store', print: 9, enterable: blocked('no band') },
          },
        }) };
      }
      if (u.includes('/portfolio/holdings')) return { ok: true, json: async () => holdings };
      const m = /symbol=([A-Z]+)/.exec(u);
      const sym = m ? m[1] : '';
      if (sym === 'BROKEN') return { ok: true, json: async () => ({ error: 'No price data for BROKEN.' }) };
      return { ok: true, json: async () => ({ tile: tile(sym), last_price: 100 }) };
    });
    vi.stubGlobal('fetch', spy);
    return spy;
  };

  it('every position is still drawn when every single read is BLOCKED', async () => {
    withRoom();
    render(
      <MemoryRouter>
        <EnterableFilterProvider enterableOnly kind="demand" setEnterableOnly={() => {}}>
          <HoldingsBoard />
        </EnterableFilterProvider>
      </MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('tile-CRDO')).toBeInTheDocument());
    expect(screen.getByTestId('tile-GLW')).toBeInTheDocument();
    // …and no count line: nothing was cut, so there is nothing to report.
    expect(screen.queryByText(/hidden/)).not.toBeInTheDocument();
  });

  it('the no-chart row still wears the served chip so he knows why it is not an entry', async () => {
    withRoom();
    render(
      <MemoryRouter>
        <EnterableFilterProvider enterableOnly kind="demand" setEnterableOnly={() => {}}>
          <HoldingsBoard />
        </EnterableFilterProvider>
      </MemoryRouter>);
    await waitFor(() => expect(screen.getByText('BROKEN')).toBeInTheDocument());
    expect(await screen.findByText('⛔ no band')).toBeInTheDocument();
  });
});


/* 🪜 BAND STRUCTURE on 📁 My holdings (2026-09-16).
 *
 * Every tile here is a /chart-maps/support response, so each one carries the
 * 🪜 read on its tile AND the served verdict beside it. The board used to
 * mount PatternChart without the verdict, so the chip appeared on a position he
 * owns with no "MEASURED: pending" banner anywhere near it. The negatives are
 * the point: a board that invents a banner the server never sent is the same
 * bug wearing the other face. */
describe('HoldingsBoard — the \u{1FA9C} read and its pending banner', () => {
  const READ = (sym: string) => ({
    applicable: true, kind: 'demand', score: null,
    stat: `${sym} ceiling 3.4% wide, 20.1% up · floor 3.2% wide, 2nd band 5.2% under`,
    ceiling: { state: 'ROOM', height_pct: 3.4, distance_pct: 20.1 },
    floor: { height_pct: 3.2, gap_pct: 5.2, bands_below: 5 },
    measured: { status: 'pending' },
  });
  const VERDICT = {
    headline: 'MEASURED: pending — the replay has not reported',
    fallback_note: 'a DESCRIPTIVE ordering of what the bands look like, not a prediction',
    status: 'pending',
  };

  const stub = (opts: { study?: unknown; read?: boolean } = {}) => {
    const spy = vi.fn(async (url: string) => {
      const u = String(url);
      if (u.includes('/portfolio/holdings')) return { ok: true, json: async () => HOLDINGS };
      const m = /symbol=([A-Z]+)/.exec(u);
      const sym = m ? m[1] : '';
      if (sym === 'BROKEN') return { ok: true, json: async () => ({ error: 'No price data for BROKEN.' }) };
      const t: any = tile(sym);
      if (opts.read !== false) t.band_structure = READ(sym);
      return { ok: true, json: async () => ({
        tile: t, last_price: 100,
        ...(opts.study === undefined ? {} : { band_structure_study: opts.study }),
      }) };
    });
    vi.stubGlobal('fetch', spy);
    return spy;
  };

  beforeEach(() => { vi.stubGlobal('localStorage', mem()); _resetBounceRoomCache(); });
  afterEach(() => { vi.unstubAllGlobals(); _resetBounceRoomCache(); });

  it('renders the SERVED pending banner once and hands the verdict to every tile', async () => {
    stub({ study: VERDICT });
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    const banner = await screen.findByTestId('hb-band-structure-study');
    expect(banner.textContent).toContain('MEASURED: pending');
    expect(banner.textContent).toContain('not a prediction');
    // ONE banner for the board, not one per position.
    expect(screen.getAllByTestId('hb-band-structure-study').length).toBe(1);
    for (const sym of ['CRDO', 'GLW']) {
      expect(screen.getByTestId(`tile-${sym}`).getAttribute('data-band-study'))
        .toBe(VERDICT.headline);
      expect(screen.getByTestId(`band-${sym}`).textContent).toContain('2nd band 5.2% under');
    }
  });

  it('NEGATIVE: no verdict served — the chips still render and NO banner is invented', async () => {
    stub();
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('tile-CRDO')).toBeInTheDocument());
    expect(screen.getByTestId('band-CRDO')).toBeInTheDocument();
    expect(screen.queryByTestId('hb-band-structure-study')).toBeNull();
    expect(screen.queryByText(/MEASURED/)).toBeNull();
    expect(screen.getByTestId('tile-CRDO').getAttribute('data-band-study')).toBe('');
  });

  it('NEGATIVE: a verdict with no headline is not a banner — nothing renders', async () => {
    stub({ study: { headline: '', fallback_note: 'orphan note' } });
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('tile-CRDO')).toBeInTheDocument());
    expect(screen.queryByTestId('hb-band-structure-study')).toBeNull();
    expect(screen.queryByText('orphan note')).toBeNull();
  });

  it('NEGATIVE: no read on any tile — no chip, and the banner is still the served one', async () => {
    stub({ study: VERDICT, read: false });
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('tile-CRDO')).toBeInTheDocument());
    expect(screen.queryByTestId('band-CRDO')).toBeNull();
    expect(screen.getByTestId('hb-band-structure-study').textContent).toContain('MEASURED: pending');
  });

  /* 🪜 THE SILENT BLANK, on one of HIS OWN POSITIONS (critique J2,
   * 2026-09-16). `attach_band_structure` reads bands from the zone store and
   * nothing else, so a position the zone store does not carry drew a chart
   * here with no Bands line and NO REASON — while the ten row boards, which
   * build the doc on demand, served the read for the same name the same day.
   * It was BTBT on his sheet: 7 holdings, 6 with a store doc. Every tile on
   * this board is its own /chart-maps/support response, so the reason is PER
   * NAME and must never silence the positions beside it that read fine. The
   * sentence is SERVED (bounce_room.band_structure_no_read_note) and never
   * typed here.
   *
   * THE SENTENCE IS NO LONGER ONE STRING (critique 5, BLOCKING). The server
   * decides per name whether the store is still warming it, whether it sits
   * UNDER the store's cap floor and will never get a read (BTBT, $562.6M
   * against $700M) or whether nobody can tell. These are the three shapes the
   * board has to be able to print AT ONCE, grouped by sentence — printing the
   * first name's note over all of them is the lie this fix removes. */
  const BASE = 'No band read for these names \u2014 no ceiling or floor to show '
    + 'on this board.';
  const NO_READ = BASE + ' Names the store is still warming arrive on the next refresh.';
  const BELOW_CAP = BASE + ' The store only draws bands for names at or above a '
    + '$700M market cap and these are under it, so no refresh brings a read.';

  /** `missing` -> the served note for that name (null = it read fine). */
  const stubNotes = (notes: Record<string, string>) => {
    const spy = vi.fn(async (url: string) => {
      const u = String(url);
      if (u.includes('/portfolio/holdings')) return { ok: true, json: async () => HOLDINGS };
      const m = /symbol=([A-Z]+)/.exec(u);
      const sym = m ? m[1] : '';
      if (sym === 'BROKEN') return { ok: true, json: async () => ({ error: 'No price data for BROKEN.' }) };
      const t: any = tile(sym);
      const note = notes[sym] || null;
      if (!note) t.band_structure = READ(sym);
      return { ok: true, json: async () => ({
        tile: t, last_price: 100, band_structure_study: VERDICT,
        band_structure_coverage: note
          ? { tiles_with_read: 0, tiles_without_read: 1, note }
          : { tiles_with_read: 1, tiles_without_read: 0, note: null },
      }) };
    });
    vi.stubGlobal('fetch', spy);
    return spy;
  };

  const stubMissing = (missing: string[]) =>
    stubNotes(Object.fromEntries(missing.map((s) => [s, NO_READ])));

  it('a position with NO read is NAMED and the SERVED reason is printed', async () => {
    stubMissing(['GLW']);
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    const line = await screen.findByTestId('hb-band-structure-no-read');
    expect(line.textContent).toContain('GLW');
    expect(line.textContent).toContain(NO_READ);
    // …and it does NOT silence the position beside it that read fine, nor
    // fabricate a chip for the one that did not.
    expect(screen.getByTestId('band-CRDO')).toBeInTheDocument();
    expect(screen.queryByTestId('band-GLW')).toBeNull();
    expect(screen.getAllByTestId('hb-band-structure-no-read').length).toBe(1);
  });

  it('NEGATIVE: every position read — no no-read line anywhere', async () => {
    stubMissing([]);
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('band-CRDO')).toBeInTheDocument());
    expect(screen.getByTestId('band-GLW')).toBeInTheDocument();
    expect(screen.queryByTestId('hb-band-structure-no-read')).toBeNull();
    expect(screen.queryByText(/No band read/)).toBeNull();
  });

  it('names are GROUPED BY THE SENTENCE they were served, never by the first one',
     async () => {
    // His real sheet, in miniature: one position under the store's cap floor
    // (no refresh will ever bring it a read) beside one the store is simply
    // still warming. One line each, each naming only its own names.
    stubNotes({ GLW: BELOW_CAP, CRDO: NO_READ });
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getAllByTestId('hb-band-structure-no-read').length).toBe(2));
    const lines = screen.getAllByTestId('hb-band-structure-no-read')
      .map((el) => el.textContent || '');
    const below = lines.find((t) => t.includes('$700M')) || '';
    const warming = lines.find((t) => t.includes('still warming')) || '';
    expect(below).toContain('GLW');
    expect(below).not.toContain('CRDO');
    expect(warming).toContain('CRDO');
    expect(warming).not.toContain('GLW');
  });

  it('NEGATIVE: a position UNDER the cap floor is never told to wait for a refresh',
     async () => {
    // The blocking bug, on the surface he hit it on: BTBT is $562.6M against a
    // $700M store floor, so "arrives on the next refresh" is a promise the
    // store can never keep about a name he owns.
    stubNotes({ GLW: BELOW_CAP });
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    const line = await screen.findByTestId('hb-band-structure-no-read');
    expect(line.textContent).toContain('GLW');
    expect(line.textContent).toContain(BELOW_CAP);
    expect(screen.queryByText(/still warming/)).toBeNull();
    expect(screen.queryByText(/next refresh/)).toBeNull();
  });

  it('NEGATIVE: two names on the SAME sentence share ONE line', async () => {
    stubNotes({ GLW: BELOW_CAP, CRDO: BELOW_CAP });
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getByTestId('hb-band-structure-no-read')).toBeInTheDocument());
    const lines = screen.getAllByTestId('hb-band-structure-no-read');
    expect(lines.length).toBe(1);
    expect(lines[0].textContent).toContain('GLW');
    expect(lines[0].textContent).toContain('CRDO');
  });

  it('NEGATIVE: no coverage block served — the board INVENTS no reason', async () => {
    stub({ study: VERDICT, read: false });
    render(<MemoryRouter><HoldingsBoard /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('tile-CRDO')).toBeInTheDocument());
    expect(screen.queryByTestId('band-CRDO')).toBeNull();
    expect(screen.queryByTestId('hb-band-structure-no-read')).toBeNull();
    expect(screen.queryByText(/No band read/)).toBeNull();
  });
});

/* ── 1-week / 2-week zooms on 📁 My holdings (Ajay 2026-09-18) ────────────── */
describe('HoldingsBoard · the short zooms', () => {
  beforeEach(() => { vi.stubGlobal('localStorage', mem()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  /* HB-4 */
  it('offers 1 week first but still OPENS on 6 months, and asks for window=1w when picked', async () => {
    const spy = stubFetch();
    render(<MemoryRouter><HoldingsBoard days={130} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('tile-CRDO')).toBeInTheDocument());
    const sel = screen.getByLabelText('Holdings window') as HTMLSelectElement;
    expect(sel.options[0].textContent).toBe('1 week');
    expect(sel.options[1].textContent).toBe('2 weeks');
    // the DEFAULT did not move
    expect(sel.value).toBe('6m');

    fireEvent.change(sel, { target: { value: '1w' } });
    await waitFor(() => expect(
      spy.mock.calls.map((c) => String(c[0]))
        .some((u) => u.includes('/chart-maps/support') && u.includes('window=1w')),
    ).toBe(true));
  });

  /* HB-5 NEGATIVE */
  it('a holding whose short-zoom read underflows shows the served error and no band', async () => {
    const spy = vi.fn(async (url: string) => {
      const u = String(url);
      if (u.includes('/portfolio/holdings')) return { ok: true, json: async () => HOLDINGS };
      const m = /symbol=([A-Z]+)/.exec(u);
      const sym = m ? m[1] : '';
      if (sym === 'BROKEN') {
        return { ok: true, json: async () => ({
          bars_used: 3,
          error: 'BROKEN has only 3 bars of history — too few to read a 1 month window.',
        }) };
      }
      return { ok: true, json: async () => ({ tile: tile(sym), last_price: 143.6 }) };
    });
    vi.stubGlobal('fetch', spy);
    render(<MemoryRouter><HoldingsBoard days={130} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('tile-CRDO')).toBeInTheDocument());
    expect(screen.getByText(/only 3 bars of history — too few to read a 1 month window/))
      .toBeInTheDocument();
    expect(screen.queryByTestId('tile-BROKEN')).toBeNull();
  });
});
