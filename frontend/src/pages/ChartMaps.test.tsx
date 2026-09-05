import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ChartMaps } from './ChartMaps';

/* ChartMaps — the /chart-maps study board.
 *
 * Fetch is stubbed with payloads copied from the REAL endpoint (verified
 * 2026-08-15 against GET /chart-maps on the live API), so this doubles as a
 * contract test: if backend/chart_maps/board.py renames a field, this fails
 * rather than the page silently rendering blank tiles.
 *
 * Locks the two things that would quietly mislead if they broke — the winners
 * tab always showing its stop-first losses next to the wins, and the demand
 * tab reporting that it is still scanning rather than "nothing matched".
 */

const VCP_TILE = {
  symbol: 'AVGO',
  name: 'Broadcom Inc.',
  href: '/sepa/AVGO?tab=setup',
  bars: Array.from({ length: 30 }, (_, i) => ({
    t: `2026-02-${String(i + 1).padStart(2, '0')}`,
    o: 380 + i, h: 385 + i, l: 375 + i, c: 382 + i, v: 3e7,
  })),
  bands: [{ kind: 'base', lo: 360.45, hi: 481.57, label: 'base 50d' }],
  lines: [
    { price: 396.81, label: 'PIVOT', tone: 'buy' },
    { price: 370.32, label: 'STOP', tone: 'stop' },
  ],
  markers: [],
  stats: [{ k: 'Tightness', v: '85' }, { k: 'Contractions', v: '4' }],
  why: 'tightens 23%→7% · volume drying up · 4 contractions',
  theme: 'ai_semis',
  badges: [{ text: 'Setup ready', tone: 'warn' }],
};

const VCP_BOARD = {
  tab: 'vcp', count: 1, matched: 265, scanned: 2974,
  tiles: [VCP_TILE],
  disclaimer: 'Study board. Past pattern outcomes are a measured sample of what happened, not a forecast.',
};

const WINNERS_BOARD = {
  tab: 'winners', count: 1,
  tiles: [{
    ...VCP_TILE,
    symbol: 'HASI', name: null, href: '/sepa/HASI?tab=breakout',
    bands: [], theme: null, pattern: 'triple_bottom',
    lines: [
      { price: 396.81, label: 'BREAKOUT', tone: 'buy' },
      { price: 405.0, label: 'TARGET', tone: 'target' },
      { price: 370.32, label: 'STOP', tone: 'stop' },
    ],
    markers: [{ date: '2026-02-05', label: 'confirmed', kind: 'confirm' }],
    why: 'Triple Bottom — hit target in 5 bars',
    badges: [{ text: 'Target hit', tone: 'good' }],
  }],
  excluded_already_past_target: 8,
  patterns: ['cup_with_handle', 'double_bottom', 'triple_bottom'],
  record: {
    overall: { wins: 57, losses: 52, n: 109, win_pct: 52.3 },
    by_pattern: [
      { pattern: 'cup_with_handle', label: 'Cup With Handle', wins: 17, losses: 32, n: 49, win_pct: 34.7 },
      { pattern: 'double_bottom', label: 'Double Bottom', wins: 28, losses: 13, n: 41, win_pct: 68.3 },
      { pattern: 'inverse_head_shoulders', label: 'Inverse Head Shoulders', wins: 0, losses: 3, n: 3, win_pct: 0.0 },
    ],
    caveat: 'Wins are target-before-stop within 21 bars. Stop brackets differ ~2x between patterns, so these win rates are NOT comparable across patterns.',
  },
  disclaimer: 'Study board.',
};

const WARMING_BOARD = {
  tab: 'zones', count: 0, tiles: [], warming: true,
  universe_key: 'sp1500_plus', note: 'scanning for demand-zone pullbacks…',
};

function stubFetch(byTab: Record<string, unknown>) {
  return vi.fn(async (url: string) => {
    const tab = new URL(url, 'http://x').searchParams.get('tab') || 'vcp';
    return { ok: true, status: 200, json: async () => byTab[tab] ?? { tab, count: 0, tiles: [] } } as Response;
  });
}

const draw = () => render(<MemoryRouter initialEntries={['/chart-maps']}><ChartMaps /></MemoryRouter>);

/* Access features (backend/access/store.py): `catalysts` is its own grant, so
 * the Catalysts tab is offered only to users who hold it. Mutable per test. */
const FEATS = vi.hoisted(() => ({ loaded: true, set: new Set(['chart-maps', 'catalysts']) }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: FEATS.loaded, features: FEATS.set, catalog: [], email: null }),
}));

beforeEach(() => {
  vi.stubGlobal('fetch', stubFetch({ vcp: VCP_BOARD, winners: WINNERS_BOARD, zones: WARMING_BOARD }));
  FEATS.loaded = true;
  FEATS.set = new Set(['chart-maps', 'catalysts']);
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('ChartMaps', () => {
  it('lands on the VCP tab and renders its tiles as links', async () => {
    draw();
    expect(await screen.findByText('AVGO')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /AVGO — open SEPA detail/ }))
      .toHaveAttribute('href', '/sepa/AVGO?tab=setup&from=chart-maps');
    expect(screen.getByText(/tightens 23%/)).toBeInTheDocument();
  });

  it('offers all three tabs', () => {
    draw();
    ['Strong VCP', 'Back in Demand', 'Past Winners'].forEach((label) => {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument();
    });
  });

  it('reports how many matched out of how many were scanned', async () => {
    draw();
    expect(await screen.findByText(/265 matches/)).toBeInTheDocument();
    expect(screen.getByText(/2974 names scanned/)).toBeInTheDocument();
  });

  it('switches to the winners tab and shows the wins AND the stop-outs', async () => {
    draw();
    fireEvent.click(screen.getByRole('tab', { name: 'Past Winners' }));

    expect(await screen.findByText(/57 hit target/)).toBeInTheDocument();
    expect(screen.getByText(/52 stopped out/)).toBeInTheDocument();
    expect(screen.getByText(/109 resolved setups/)).toBeInTheDocument();
    // the excluded-late count is surfaced, not silently dropped
    expect(screen.getByText(/8 more were already past target/)).toBeInTheDocument();
  });

  it('carries the cross-pattern caveat and flags thin samples', async () => {
    draw();
    fireEvent.click(screen.getByRole('tab', { name: 'Past Winners' }));

    expect(await screen.findByText(/NOT\s+comparable across patterns/)).toBeInTheDocument();
    // inverse H&S has n=3 — below the 20-observation floor
    expect(screen.getByText('small n')).toBeInTheDocument();
    // cup-with-handle (n=49) and double bottom (n=41) are not flagged
    expect(screen.getAllByText('small n')).toHaveLength(1);
  });

  it('shows each pattern record with its losses, never wins alone', async () => {
    draw();
    fireEvent.click(screen.getByRole('tab', { name: 'Past Winners' }));
    expect(await screen.findByText(/17 hit target · 32 stopped out · 34.7% of 49/))
      .toBeInTheDocument();
  });

  it('says it is still scanning rather than "nothing matched" while warming', async () => {
    // The static sentence became a live panel (Ajay 2026-08-17: "its hard to
    // tell if its scanning or now"), and it must show even before the first
    // progress poll lands — the board's own `warming` flag drives it, so a
    // silent gap here is the exact regression to guard against.
    draw();
    fireEvent.click(screen.getByRole('tab', { name: 'Back in Demand' }));

    expect(await screen.findByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/Scanning|Loading the/)).toBeInTheDocument();
    expect(screen.queryByText(/Nothing matched/i)).not.toBeInTheDocument();
  });

  it('requests the right tab and universe from the API', async () => {
    draw();
    await screen.findByText('AVGO');
    fireEvent.click(screen.getByRole('tab', { name: 'Back in Demand' }));

    await waitFor(() => {
      const urls = (globalThis.fetch as any).mock.calls.map((c: any[]) => String(c[0]));
      expect(urls.some((u: string) => u.includes('tab=zones') && u.includes('universe=full'))).toBe(true);
    });
  });

  it('surfaces a failed load instead of showing an empty board', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503 } as Response)));
    draw();
    expect(await screen.findByText(/Couldn't load the board/)).toBeInTheDocument();
  });

  it('says nothing matched when the board is genuinely empty', async () => {
    vi.stubGlobal('fetch', stubFetch({ vcp: { tab: 'vcp', count: 0, tiles: [] } }));
    draw();
    expect(await screen.findByText(/Nothing matched on this tab/)).toBeInTheDocument();
  });
});

// ── 0DTE tab (Ajay 2026-08-24) ───────────────────────────────────────────────
// Payload copied from the REAL endpoint (GET /chart-maps?tab=zero_dte on the
// live API, 2026-08-24 after the close), so this doubles as a contract test on
// the two fields no other tab has: `session` and `with_contract`.
const ZERO_DTE_BOARD = {
  tab: 'zero_dte',
  count: 2,
  matched: 13,
  expiry: '2026-08-24',
  with_chain: 13,
  with_contract: 3,
  session: {
    state: 'post',
    actionable: false,
    label: "After the close on expiry day — these contracts have settled. Strikes still listed are pennies with wide spreads; this is the day's record, not a live board.",
  },
  disclaimer: '0DTE is same-day-expiry options. Every threshold here is a house value with NO measured edge behind it — there is no intraday option history to backtest against.',
  tiles: [
    {
      symbol: 'QQQ',
      name: 'Invesco QQQ Trust',
      href: '/sepa/QQQ?tab=options',
      bars: Array.from({ length: 30 }, (_, i) => ({
        t: `2026-08-${String(i + 1).padStart(2, '0')}`,
        o: 700 + i, h: 705 + i, l: 698 + i, c: 703 + i, v: 4e7,
      })),
      bands: [{ kind: 'neutral', lo: 706, hi: 713, label: 'gamma walls' }],
      lines: [{ price: 706.5, label: 'now', tone: 'now' },
              { price: 707, label: 'put 707', tone: 'neutral' }],
      markers: [],
      stats: [
        { k: 'Expected move', v: '±0.45%' },
        { k: 'Call', v: '—' },
        { k: 'Put', v: '707 · 0.38x' },
        { k: 'Theta/day', v: '611% of premium' },
        { k: 'Spread', v: '10%' },
      ],
      why: "needs 0.38x today's expected move to double · dealers AMPLIFY · expected ±0.45% · theta 611%/day",
      badges: [{ text: 'Amplifying', tone: 'good' },
               { text: 'Theta > 2x premium', tone: 'warn' }],
    },
    {
      symbol: 'AAPL',
      name: 'Apple Inc.',
      href: '/sepa/AAPL?tab=options',
      bars: Array.from({ length: 30 }, (_, i) => ({
        t: `2026-08-${String(i + 1).padStart(2, '0')}`,
        o: 310 + i, h: 312 + i, l: 308 + i, c: 311 + i, v: 5e7,
      })),
      bands: [],
      lines: [{ price: 310.7, label: 'now', tone: 'now' }],
      markers: [],
      stats: [
        { k: 'Expected move', v: '±0.76%' },
        { k: 'Call', v: '—' },
        { k: 'Put', v: '—' },
        { k: 'Theta/day', v: '—' },
        { k: 'Spread', v: '—' },
      ],
      why: 'nothing clears the spread and delta floors · dealers AMPLIFY · expected ±0.76%',
      badges: [{ text: 'Nothing tradeable', tone: 'muted' }],
    },
  ],
};

describe('ChartMaps — the 0DTE tab', () => {
  const openTab = async () => {
    vi.stubGlobal('fetch', stubFetch({ vcp: VCP_BOARD, zero_dte: ZERO_DTE_BOARD }));
    draw();
    fireEvent.click(await screen.findByRole('tab', { name: /0DTE Options/i }));
  };

  it('tells the reader the board is NOT live before showing a single tile', async () => {
    // After the close the chain has settled. A thin board is correct then, but
    // without this banner it reads as broken.
    await openTab();
    expect(await screen.findByText('Not live')).toBeInTheDocument();
    expect(screen.getByText(/these contracts have settled/i)).toBeInTheDocument();
  });

  it('states how few names actually carry a tradeable contract', async () => {
    // The gap between with_chain and with_contract is where the cost floors
    // bite — the honest headline, not a footnote.
    await openTab();
    expect(await screen.findByText(/3 of 13 names have a contract/i)).toBeInTheDocument();
    expect(screen.getByText(/expiry 2026-08-24/i)).toBeInTheDocument();
  });

  it('renders the cost stats, including theta as a share of premium', async () => {
    await openTab();
    expect(await screen.findByText('707 · 0.38x')).toBeInTheDocument();
    expect(screen.getByText('611% of premium')).toBeInTheDocument();
    expect(screen.getByText('±0.45%')).toBeInTheDocument();
  });

  it('deep-links each tile to a SEPA tab that actually exists', async () => {
    // Shipped once pointing at ?tab=zero_dte, which SepaCandidate does not
    // define — every click silently fell back to the chart tab.
    await openTab();
    const link = await screen.findByRole('link', { name: /QQQ — open SEPA detail/ });
    const url = new URL(link.getAttribute('href')!, 'http://x');
    expect(url.pathname).toBe('/sepa/QQQ');
    expect(url.searchParams.get('tab')).toBe('options');
  });

  it('shows a name with nothing tradeable rather than hiding it', async () => {
    // Absence is information: AAPL has a chain and nothing worth buying on it.
    await openTab();
    expect(await screen.findByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('Nothing tradeable')).toBeInTheDocument();
    expect(screen.getByText(/nothing clears the spread and delta floors/i)).toBeInTheDocument();
  });

  it('keeps the no-measured-edge disclaimer on screen', async () => {
    await openTab();
    expect(await screen.findByText(/NO measured edge/i)).toBeInTheDocument();
  });

  it('offers no sort or liquidity control — there is nothing to sort by', async () => {
    // It reads live option chains, not the equity scan. A control that did
    // nothing would be worse than none.
    await openTab();
    await screen.findByText('Not live');
    expect(screen.queryByLabelText(/Sort/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Liquidity/i)).not.toBeInTheDocument();
  });
});

describe('background auto-refresh', () => {
  // Why: 2026-08-25 — a tab left open since ~10:57 kept showing that reload's
  // board while fresh scans landed server-side; there was NO code path that
  // ever refetched an idle tab. The interval is the fix; the hidden-tab guard
  // keeps a backgrounded browser from burning the API for nobody.
  it('refetches the board on the slow clock while the tab is visible', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      draw();
      expect(await screen.findByText('AVGO')).toBeInTheDocument();
      const before = (fetch as ReturnType<typeof vi.fn>).mock.calls.length;
      await vi.advanceTimersByTimeAsync(5 * 60_000 + 100);
      const after = (fetch as ReturnType<typeof vi.fn>).mock.calls.length;
      expect(after).toBeGreaterThan(before);
    } finally {
      vi.useRealTimers();
    }
  });

  it('does NOT refetch while the tab is hidden', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const spy = vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
    try {
      draw();
      expect(await screen.findByText('AVGO')).toBeInTheDocument();
      const before = (fetch as ReturnType<typeof vi.fn>).mock.calls.length;
      await vi.advanceTimersByTimeAsync(5 * 60_000 + 100);
      const after = (fetch as ReturnType<typeof vi.fn>).mock.calls.length;
      expect(after).toBe(before);
    } finally {
      spy.mockRestore();
      vi.useRealTimers();
    }
  });
});

describe('tile links carry the tab back (2026-08-25)', () => {
  it('a tile clicked from a non-default tab returns to THAT tab', async () => {
    // Render the page on ?tab=vcp with an explicit extra param and check the
    // tile href carries from_q — the durable half of the round trip (the
    // state half is covered by navSource.test.ts resolveBack precedence).
    render(
      <MemoryRouter initialEntries={['/chart-maps?tab=vcp&sort=rs']}>
        <ChartMaps />
      </MemoryRouter>,
    );
    const link = await screen.findByRole('link', { name: /AVGO — open SEPA detail/ });
    const href = link.getAttribute('href') || '';
    const q = new URLSearchParams(href.split('?')[1]);
    expect(q.get('from')).toBe('chart-maps');
    expect(q.get('from_q')).toBe('tab=vcp&sort=rs');
  });
});

/* ── reaching vs already reached (Ajay 2026-08-31) ─────────────────────────── */
describe('the phase toggle', () => {
  it('shows on the two demand boards and nowhere else', async () => {
    render(<MemoryRouter initialEntries={['/chart-maps?tab=zones']}><ChartMaps /></MemoryRouter>);
    expect(await screen.findByRole('tab', { name: /Approaching/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Already reached/ })).toBeInTheDocument();

    render(<MemoryRouter initialEntries={['/chart-maps?tab=vcp']}><ChartMaps /></MemoryRouter>);
    // VCP has one moment only — no toggle.
    expect(screen.getAllByRole('tab', { name: /Approaching/ })).toHaveLength(1); // only the zones render above
  });

  it('sends phase=approaching to the board and writes it to the URL', async () => {
    const fetchSpy = vi.mocked(fetch as any);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=zones&phase=approaching']}><ChartMaps /></MemoryRouter>);
    await screen.findAllByRole('tab', { name: /Approaching/ });
    const urls = fetchSpy.mock.calls.map((c: any[]) => String(c[0]));
    expect(urls.some((u: string) => u.includes('tab=zones') && u.includes('phase=approaching')))
      .toBe(true);
  });

  it('the default sends no phase param at all', async () => {
    const fetchSpy = vi.mocked(fetch as any);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=zones']}><ChartMaps /></MemoryRouter>);
    await screen.findAllByRole('tab', { name: /Already reached/ });
    const urls = fetchSpy.mock.calls.map((c: any[]) => String(c[0]));
    expect(urls.some((u: string) => u.includes('tab=zones') && !u.includes('phase='))).toBe(true);
  });
});

/* ── approaching: zone vs order block (Ajay 2026-08-31) ────────────────────── */
describe('the approach-target switch', () => {
  it('appears on both phases of zones, and sends target=order_block', async () => {
    const fetchSpy = vi.mocked(fetch as any);
    render(<MemoryRouter
      initialEntries={['/chart-maps?tab=zones&phase=approaching&target=order_block']}>
      <ChartMaps /></MemoryRouter>);
    expect(await screen.findByRole('tab', { name: 'Order block' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Demand zone' })).toBeInTheDocument();
    const urls = fetchSpy.mock.calls.map((c: any[]) => String(c[0]));
    expect(urls.some((u: string) =>
      u.includes('phase=approaching') && u.includes('target=order_block'))).toBe(true);
  });

  it('reached + Order block = IN the block, and still sends the target', async () => {
    // Superseded same day: "hit the 'In the orderblock' to see all the
    // stocks" — the switch now lives on BOTH phases.
    const fetchSpy = vi.mocked(fetch as any);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=zones&target=order_block']}>
      <ChartMaps /></MemoryRouter>);
    expect(await screen.findByRole('tab', { name: 'Order block' })).toBeInTheDocument();
    const urls = fetchSpy.mock.calls.map((c: any[]) => String(c[0]));
    expect(urls.some((u: string) =>
      u.includes('tab=zones') && u.includes('target=order_block')
      && !u.includes('phase='))).toBe(true);
  });

  it('lens tabs get the three-state phase toggle, default All', async () => {
    const fetchSpy = vi.mocked(fetch as any);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=undervalue']}>
      <ChartMaps /></MemoryRouter>);
    expect(await screen.findByRole('tab', { name: 'All' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Already reached/ })).toBeInTheDocument();
    // default All sends NO phase param — the historical board byte for byte
    const urls = fetchSpy.mock.calls.map((c: any[]) => String(c[0]));
    expect(urls.some((u: string) =>
      u.includes('tab=undervalue') && !u.includes('phase='))).toBe(true);
  });

  it('is absent on deep_demand even while approaching — its second band IS the level', async () => {
    render(<MemoryRouter initialEntries={['/chart-maps?tab=deep_demand&phase=approaching']}>
      <ChartMaps /></MemoryRouter>);
    await screen.findAllByRole('tab', { name: /Approaching/ });
    expect(screen.queryByRole('tab', { name: 'Order block' })).toBeNull();
  });

  it('explains names hidden by the 7% already-bounced gate (Ajay 2026-09-03)', async () => {
    vi.stubGlobal('fetch', stubFetch({
      vcp: VCP_BOARD, winners: WINNERS_BOARD,
      zones: { ...WARMING_BOARD, warming: false, count: 0, tiles: [], matched: 2, dropped_bounced: 2, bounce_done_pct: 7 },
    }));
    draw();
    fireEvent.click(screen.getByRole('tab', { name: 'Back in Demand' }));
    await waitFor(() => expect(screen.getByText(/2 names hidden — already/)).toBeInTheDocument());
    expect(screen.getByText(/bounced 7%\+ off the demand zone/)).toBeInTheDocument();
  });
});

/* ── ICT tab (Ajay 2026-09-03, late) ────────────────────────────────────────
 * "create a new chart maps tab for ICT Strategy, replace supply tab with this
 * new tab." Payload shape is the backend/chart_maps/board.py ict_tiles
 * envelope contract (tiles + as_of + counts + params + source); the tile is
 * the ONE tile shape every tab shares, with the ICT bands / lines / markers. */
const ICT_TILE = {
  symbol: 'NTAP',
  name: 'NetApp',
  href: '/sepa/NTAP?tab=supply',
  bars: Array.from({ length: 30 }, (_, i) => ({
    t: `2026-08-${String(i + 1).padStart(2, '0')}`,
    o: 160 + i * 0.3, h: 163 + i * 0.3, l: 158 + i * 0.3, c: 161 + i * 0.3, v: 2e6,
  })),
  bands: [
    { kind: 'base', lo: 161.0, hi: 163.5, label: 'accumulation' },
    { kind: 'demand', lo: 162.2, hi: 162.9, label: 'FVG' },
    { kind: 'neutral', lo: 163.8, hi: 164.4, label: 'IFVG' },
    { kind: 'demand', lo: 163.8, hi: 164.4, label: 'entry' },
  ],
  lines: [
    { price: 160.4, label: 'STOP', tone: 'stop' },
    { price: 171.2, label: 'TARGET', tone: 'target' },
    { price: 161.0, label: 'key low', tone: 'neutral' },
  ],
  markers: [
    { date: '2026-08-27', label: 'MANIP', kind: 'sweep', price: 160.6 },
    { date: '2026-08-28', label: 'MSS', kind: 'bos', price: 163.9 },
    { date: '2026-08-29', label: 'IFVG', kind: 'buy', price: 164.0 },
  ],
  stats: [
    { k: 'State', v: 'entry' }, { k: 'Grade', v: '100' }, { k: 'R:R', v: '2.1' },
    { k: 'Bias', v: 'bullish' }, { k: 'Micro tf', v: '60m' }, { k: 'Tapped', v: 'swing_low 161.00' },
  ],
  why: 'swept the daily swing low 161.00 without displacing · 60m push back left a new FVG and closed past the last swing (MSS) · IFVG 163.80–164.40',
  badges: [{ text: 'MSS ✓', tone: 'good' }, { text: 'no displacement ✓', tone: 'good' },
           { text: 'stacked consolidations', tone: 'warn' }],
};

const ICT_BOARD = {
  tab: 'ict', count: 1, tiles: [ICT_TILE],
  as_of: '2026-09-03T15:45:00-04:00',
  counts: { macro_n: 1124, tapped_n: 37, micro_n: 37 },
  // the exact shape ict/engine.py params() sends: a LIST, with the two values
  // the video states flagged so the page never files them as owner rules
  params: [
    { key: 'FRACTAL_WINDOW', value: 1, from_video: true, note: 'video' },
    { key: 'STACK_MIN', value: 2, from_video: true, note: 'video' },
    { key: 'ATR_PERIOD', value: 14, from_video: false, note: 'owner rule — not from the video' },
    { key: 'CONSOL_MIN_BARS', value: 5, from_video: false, note: 'owner rule — not from the video' },
    { key: 'CONSOL_MAX_ATR', value: 1.5, from_video: false, note: 'owner rule — not from the video' },
    { key: 'DISPLACE_MAX_ATR', value: 0.0, from_video: false, note: 'owner rule — not from the video' },
    { key: 'DISPLACE_MIN_ATR', value: 1.0, from_video: false, note: 'owner rule — not from the video' },
    { key: 'CONFIRM_MAX_BARS', value: 3, from_video: false, note: 'owner rule — not from the video' },
    { key: 'N_SWINGS', value: 5, from_video: false, note: 'owner rule — not from the video' },
    { key: 'TAP_LOOKBACK', value: 2, from_video: false, note: 'owner rule — not from the video' },
    { key: 'TAP_TOL_PCT', value: 0.25, from_video: false, note: 'owner rule — not from the video' },
    { key: 'ENTRY_TOL_PCT', value: 0.5, from_video: false, note: 'owner rule — not from the video' },
    { key: 'STOP_BUFFER_ATR', value: 0.2, from_video: false, note: 'owner rule — not from the video' },
    { key: 'MICRO_MAX', value: 40, from_video: false, note: 'owner rule — not from the video' },
    { key: 'BUDGET_SEC', value: 120, from_video: false, note: 'owner rule — not from the video' },
  ],
  source: { video: 'https://www.youtube.com/watch?v=Q7Ryv1M7CvI', timestamps: ['02:39', '03:57', '05:30'] },
  note: null,
  disclaimer: 'Study board. Not advice.',
};

describe('ChartMaps — the ICT tab (2026-09-03)', () => {
  const openIct = (query = '?tab=ict', boards: Record<string, unknown> = {}) => {
    vi.stubGlobal('fetch', stubFetch({ vcp: VCP_BOARD, ict: ICT_BOARD, ...boards }));
    return render(<MemoryRouter initialEntries={[`/chart-maps${query}`]}><ChartMaps /></MemoryRouter>);
  };

  it('offers ICT where Into Supply used to be, and Into Supply is gone', () => {
    openIct();
    const tabs = screen.getAllByRole('tab').map((t) => t.textContent);
    expect(tabs).toContain('ICT');
    expect(tabs).not.toContain('Into Supply');
    const zones = tabs.indexOf('Back in Demand');
    expect(tabs[zones + 1]).toBe('ICT');
  });

  it('renders the engine tiles through the shared tile component', async () => {
    openIct();
    expect(await screen.findByText('NTAP')).toBeInTheDocument();
    expect(screen.getByText(/without displacing/)).toBeInTheDocument();
    expect(screen.getByText('MSS ✓')).toBeInTheDocument();
    expect(screen.getByText('no displacement ✓')).toBeInTheDocument();
    expect(screen.getByText('stacked consolidations')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /NTAP — open SEPA detail/ }))
      .toHaveAttribute('href', expect.stringContaining('/sepa/NTAP?tab=supply'));
  });

  it('shows the Bias and Micro controls on this tab only', async () => {
    openIct();
    await screen.findByText('NTAP');
    expect(screen.getByLabelText('ICT bias')).toBeInTheDocument();
    expect(screen.getByLabelText('ICT micro timeframe')).toBeInTheDocument();
    expect(screen.getByLabelText('ICT bias')).toHaveValue('all');
    expect(screen.getByLabelText('ICT micro timeframe')).toHaveValue('60m');
    fireEvent.click(screen.getByRole('tab', { name: 'Strong VCP' }));
    await screen.findByText('AVGO');
    expect(screen.queryByLabelText('ICT bias')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('ICT micro timeframe')).not.toBeInTheDocument();
  });

  it('the default request carries neither bias nor micro', async () => {
    openIct();
    await screen.findByText('NTAP');
    const urls = (globalThis.fetch as any).mock.calls.map((c: any[]) => String(c[0]));
    expect(urls.some((u: string) => u.includes('tab=ict') && !u.includes('bias=') && !u.includes('micro='))).toBe(true);
  });

  it('reads bias and micro from the URL and sends them to the board', async () => {
    openIct('?tab=ict&bias=bullish&micro=15m');
    await screen.findByText('NTAP');
    expect(screen.getByLabelText('ICT bias')).toHaveValue('bullish');
    expect(screen.getByLabelText('ICT micro timeframe')).toHaveValue('15m');
    const urls = (globalThis.fetch as any).mock.calls.map((c: any[]) => String(c[0]));
    expect(urls.some((u: string) => u.includes('tab=ict') && u.includes('bias=bullish') && u.includes('micro=15m'))).toBe(true);
  });

  it('changing the bias refetches with the new side; switching back to All drops it', async () => {
    openIct();
    await screen.findByText('NTAP');
    fireEvent.change(screen.getByLabelText('ICT bias'), { target: { value: 'bearish' } });
    await waitFor(() => {
      const urls = (globalThis.fetch as any).mock.calls.map((c: any[]) => String(c[0]));
      expect(urls.some((u: string) => u.includes('tab=ict') && u.includes('bias=bearish'))).toBe(true);
    });
    const before = (globalThis.fetch as any).mock.calls.length;
    fireEvent.change(screen.getByLabelText('ICT bias'), { target: { value: 'all' } });
    await waitFor(() => {
      const urls = (globalThis.fetch as any).mock.calls.slice(before).map((c: any[]) => String(c[0]));
      expect(urls.length).toBeGreaterThan(0);
      expect(urls.every((u: string) => !u.includes('bias='))).toBe(true);
    });
  });

  it('an unknown bias or micro on the URL falls back to the defaults, never a broken request', async () => {
    openIct('?tab=ict&bias=long&micro=5m');
    await screen.findByText('NTAP');
    expect(screen.getByLabelText('ICT bias')).toHaveValue('all');
    expect(screen.getByLabelText('ICT micro timeframe')).toHaveValue('60m');
    const urls = (globalThis.fetch as any).mock.calls.map((c: any[]) => String(c[0]));
    expect(urls.every((u: string) => !u.includes('bias=long') && !u.includes('micro=5m'))).toBe(true);
  });

  it('under the board: legend, dormant-loop counts, owner constants from the payload, and the source', async () => {
    openIct();
    await screen.findByText('NTAP');
    const foot = await screen.findByTestId('ict-foot');
    expect(foot).toHaveTextContent('Legend');
    expect(foot).toHaveTextContent(/MANIP/);
    expect(foot).toHaveTextContent(/MSS/);
    expect(foot).toHaveTextContent(/IFVG/);
    // the dormant loop is the design: most names never reach the 60m clock
    expect(foot).toHaveTextContent(/1124 names on the daily pass/);
    expect(foot).toHaveTextContent(/37 tapped a level/);
    expect(foot).toHaveTextContent(/37 ran the 60m loop/);
    // owner constants come from the payload, labelled, and say they are his
    const owner = screen.getByTestId('ict-owner-params');
    expect(owner).toHaveTextContent(/not from the video/);
    expect(owner).toHaveTextContent(/tap tolerance \(% of level\) = 0\.25/);
    expect(owner).toHaveTextContent(/stop buffer under the wick \(× micro ATR\) = 0\.2/);
    expect(owner).toHaveTextContent(/consolidation: min bars = 5/);
    // …and the two values the video states sit on their own line, never
    // under the "not from the video" header
    const video = screen.getByTestId('ict-video-params');
    expect(video).toHaveTextContent(/From the video/);
    expect(video).toHaveTextContent(/3-candle fractal\) = 1/);
    expect(video).toHaveTextContent(/stacked consolidations: min count = 2/);
    expect(video).not.toHaveTextContent(/not from the video/);
    expect(owner).not.toHaveTextContent(/fractal/);
    // source line links the name to the video and lists the timestamps
    const links = screen.getAllByRole('link', { name: 'Jesse Rogers' });
    expect(links.length).toBeGreaterThanOrEqual(1);
    for (const a of links) {
      expect(a).toHaveAttribute('href', 'https://www.youtube.com/watch?v=Q7Ryv1M7CvI');
      expect(a).toHaveAttribute('target', '_blank');
    }
    expect(foot).toHaveTextContent(/02:39 · 03:57 · 05:30/);
    expect(foot).toHaveTextContent(/Not advice/);
  });

  it('the blurb links the source name even before the board lands', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => { /* never resolves */ })));
    render(<MemoryRouter initialEntries={['/chart-maps?tab=ict']}><ChartMaps /></MemoryRouter>);
    const a = screen.getByRole('link', { name: 'Jesse Rogers' });
    expect(a).toHaveAttribute('href', 'https://www.youtube.com/watch?v=Q7Ryv1M7CvI');
    expect(screen.getByText(/fails to close through it/)).toBeInTheDocument();
  });

  it('an old ?tab=supply bookmark opens the ICT tab', async () => {
    openIct('?tab=supply');
    expect(await screen.findByText('NTAP')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'ICT' })).toHaveAttribute('aria-selected', 'true');
    const urls = (globalThis.fetch as any).mock.calls.map((c: any[]) => String(c[0]));
    expect(urls.some((u: string) => u.includes('tab=ict'))).toBe(true);
    expect(urls.every((u: string) => !u.includes('tab=supply'))).toBe(true);
  });

  it('while the engine warms it says so, in its own words, and never "nothing matched"', async () => {
    openIct('?tab=ict', { ict: { tab: 'ict', count: 0, tiles: [], warming: true, note: 'scanning…' } });
    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent(/Scanning the ICT universe/);
    expect(status).toHaveTextContent(/60m loop only for the names that tapped/);
    expect(screen.queryByText(/Nothing matched/i)).not.toBeInTheDocument();
    // the owner-constant block waits for a real board — nothing to list yet
    expect(screen.queryByTestId('ict-foot')).not.toBeInTheDocument();
  });

  it('a genuinely empty ICT board says so and still lists the owner settings', async () => {
    openIct('?tab=ict', { ict: { ...ICT_BOARD, count: 0, tiles: [], note: 'no name tapped a daily level today' } });
    expect(await screen.findByText(/no name tapped a daily level today/)).toBeInTheDocument();
    expect(screen.getByTestId('ict-foot')).toHaveTextContent(/not from the video/);
  });

  it('a flat {key: value} params map (the spec wording) still lists, all as owner settings', async () => {
    openIct('?tab=ict', { ict: { ...ICT_BOARD, params: { tap_tol_pct: 0.25, consol_min_bars: 5 } } });
    await screen.findByText('NTAP');
    const foot = screen.getByTestId('ict-foot');
    expect(foot).toHaveTextContent(/tap tolerance \(% of level\) = 0\.25/);
    expect(foot).toHaveTextContent(/consolidation: min bars = 5/);
    expect(screen.queryByTestId('ict-video-params')).not.toBeInTheDocument();
  });

  it('a payload without params or source degrades to the legend and the fallback source link', async () => {
    openIct('?tab=ict', { ict: { tab: 'ict', count: 1, tiles: [ICT_TILE] } });
    await screen.findByText('NTAP');
    const foot = screen.getByTestId('ict-foot');
    expect(foot).toHaveTextContent('Legend');
    expect(foot).not.toHaveTextContent(/Owner settings/);
    expect(foot).not.toHaveTextContent(/Dormant loop/);
    expect(screen.getAllByRole('link', { name: 'Jesse Rogers' }).length).toBeGreaterThanOrEqual(1);
  });

  it('source timestamps sent as {at, rule} objects print as stamps, never [object Object]', async () => {
    openIct('?tab=ict', { ict: { ...ICT_BOARD, source: {
      video: 'https://www.youtube.com/watch?v=Q7Ryv1M7CvI',
      timestamps: [{ at: '02:39', rule: 'lack of displacement' }, { at: '03:57' }, null],
    } } });
    await screen.findByText('NTAP');
    const foot = screen.getByTestId('ict-foot');
    expect(foot).toHaveTextContent(/02:39 · 03:57/);
    expect(foot).not.toHaveTextContent(/object/i);
  });

  it('the previous tab\'s payload never feeds the ICT footer while the board reloads', async () => {
    // Switching VCP → ICT keeps the VCP tiles on screen until the ICT board
    // lands (page design). The footer must wait for an ICT payload too.
    let release: (v: unknown) => void = () => {};
    const vcpResp = { ok: true, status: 200, json: async () => VCP_BOARD };
    vi.stubGlobal('fetch', vi.fn((url: string) => String(url).includes('tab=ict')
      ? new Promise((res) => { release = res; })
      : Promise.resolve(vcpResp)));
    render(<MemoryRouter initialEntries={['/chart-maps?tab=vcp']}><ChartMaps /></MemoryRouter>);
    await screen.findByText('AVGO');
    fireEvent.click(screen.getByRole('tab', { name: 'ICT' }));
    expect(screen.getByRole('tab', { name: 'ICT' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByTestId('ict-foot')).not.toBeInTheDocument();
    release({ ok: true, status: 200, json: async () => ICT_BOARD });
    expect(await screen.findByTestId('ict-foot')).toHaveTextContent(/Legend/);
  });
});


/* ── the Catalysts tab (Ajay 2026-09-05: "move catalyst tab in to Chart maps") ─ */
vi.mock('../pages/Catalysts', () => ({
  CatalystsBoard: ({ embedded }: { embedded?: boolean }) => (
    <div data-testid="catalysts-board">{embedded ? 'embedded' : 'standalone'}</div>
  ),
  CatalystsPage: () => null,
}));

describe('the Catalysts tab', () => {
  it('mounts the Catalysts board EMBEDDED and never asks /chart-maps for it', async () => {
    const fetchSpy = vi.mocked(fetch as any);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=catalysts']}><ChartMaps /></MemoryRouter>);
    expect(await screen.findByTestId('catalysts-board')).toHaveTextContent('embedded');
    expect(screen.getByRole('tab', { name: /Catalysts/ })).toHaveAttribute('aria-selected', 'true');
    // The blurb is the tab's own copy, drawn above the board.
    expect(screen.getByText(/moved here from its own page/i)).toBeInTheDocument();
    // NEGATIVE: it is not a board tab — no /chart-maps fetch, no tile-grid
    // states. `/chart-maps` answers an unknown tab with the VCP board, which
    // would draw AVGO tiles under the Catalysts heading.
    await new Promise((r) => setTimeout(r, 30));
    const urls = fetchSpy.mock.calls.map((c: any[]) => String(c[0]));
    expect(urls.some((u: string) => u.includes('/chart-maps'))).toBe(false);
    expect(screen.queryByText('AVGO')).not.toBeInTheDocument();
    expect(screen.queryByText(/Nothing matched on this tab/)).not.toBeInTheDocument();
  });

  it('clicking the tab from VCP switches the URL param and mounts the board', async () => {
    draw();
    await screen.findByText('AVGO');
    fireEvent.click(screen.getByRole('tab', { name: /Catalysts/ }));
    expect(await screen.findByTestId('catalysts-board')).toBeInTheDocument();
    expect(screen.queryByText('AVGO')).not.toBeInTheDocument();
  });

  it('is NOT offered to a user without the `catalysts` feature, and ?tab=catalysts falls back to VCP (negative)', async () => {
    FEATS.set = new Set(['chart-maps']);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=catalysts']}><ChartMaps /></MemoryRouter>);
    expect(screen.queryByRole('tab', { name: /Catalysts/ })).not.toBeInTheDocument();
    expect(screen.queryByTestId('catalysts-board')).not.toBeInTheDocument();
    expect(await screen.findByText('AVGO')).toBeInTheDocument();          // the first tab's board
    expect(screen.getByRole('tab', { name: 'Strong VCP' })).toHaveAttribute('aria-selected', 'true');
    // Every other tab is still there — only the gated one is missing.
    ['Back in Demand', 'Past Winners', 'ICT'].forEach((label) => {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument();
    });
  });

  it('is offered while the features fetch is still in flight (permissive, like the nav)', () => {
    FEATS.loaded = false;
    FEATS.set = new Set();
    draw();
    expect(screen.getByRole('tab', { name: /Catalysts/ })).toBeInTheDocument();
  });
});
