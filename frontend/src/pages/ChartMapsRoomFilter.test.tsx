/* 🧱 The ROOM filter on the Chart Maps toolbar (Ajay 2026-09-17):
 *
 *   "Can you give me a ROOM filter toggle in AMD please or any please so I can
 *    look at stocks with Any room"
 *
 * Every name on his boards read BLOCKED for "room < 5%" that morning and Deep
 * Demand was hiding 106 of them. The control and the hidden-count readout were
 * already on the page (2026-09-05); what this file pins is the part that was
 * still duplicated and the part that was still silent:
 *
 *   1. ONE ROOM_FLOORS list in the repo, with no floor but ROOM_MIN_PCT and 0.
 *      A second copy is how the Back in Demand panel and Chart Maps drift into
 *      offering different floors.
 *   2. The control sends min_room=0 for "any room" and the house floor
 *      otherwise, and reaches ONLY the tabs whose builder honours it.
 *   3. The hidden count reaches him, and a payload that never carries one does
 *      not crash and renders nothing.
 *
 * It is a VIEW filter. Nothing here gates an alert, an entry or a stop.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, within, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import { ANY_ROOM_LABEL, ROOM_FLOORS, ROOM_MIN_PCT } from '../lib/bounceRoom';
import { cmRoomLabel } from './ChartMaps';
import { DEFAULT_MIN_ROOM, ROOM_TABS, boardQuery } from '../lib/chartMaps';

/* ── 1. the ONE list ─────────────────────────────────────────────────────────
 * The SOURCE scan that proves there is only one declaration of it lives in
 * src/lib/roomFloors.source.test.js (plain .js so `fs` stays out of the typed
 * tsconfig). What follows is the list's VALUES. */

describe('ROOM_FLOORS — exactly two floors', () => {
  it('carries no floor other than ROOM_MIN_PCT and 0 — a third is a number nobody gave', () => {
    expect(ROOM_FLOORS.map((f) => f.key)).toEqual([String(ROOM_MIN_PCT), '0']);
    expect(ROOM_FLOORS).toHaveLength(2);
    // NEGATIVE: none of the floors the repo keeps being asked for exist.
    const keys = ROOM_FLOORS.map((f) => Number(f.key));
    for (const invented of [1, 2, 3, 7, 10, 15]) expect(keys).not.toContain(invented);
  });

  it('the default floor IS the alert gate mirror, on both mirrors of it', () => {
    expect(ROOM_MIN_PCT).toBe(5);
    expect(DEFAULT_MIN_ROOM).toBe(ROOM_MIN_PCT);
  });

  it('ANY_ROOM_LABEL is read off the list, not retyped', () => {
    expect(ANY_ROOM_LABEL).toBe(ROOM_FLOORS.find((f) => f.key === '0')!.label);
  });

});

/* ── 2. the query ────────────────────────────────────────────────────────── */

describe('boardQuery min_room — only the tabs whose builder honours it', () => {
  it('ROOM_TABS mirrors chart_maps/board.board(): zones, deep_demand, quick_bounce, breaking', () => {
    expect(ROOM_TABS).toEqual(['zones', 'deep_demand', 'quick_bounce', 'breaking']);
  });

  it('POSITIVE: "any room" rides as min_room=0 on every room tab', () => {
    for (const tab of ROOM_TABS) {
      expect(boardQuery({ tab, minRoom: 0 })).toContain('min_room=0');
    }
  });

  it('POSITIVE: the default floor rides as min_room=5 on every room tab', () => {
    for (const tab of ROOM_TABS) {
      expect(boardQuery({ tab, minRoom: DEFAULT_MIN_ROOM })).toContain(`min_room=${DEFAULT_MIN_ROOM}`);
    }
  });

  it('NEGATIVE: a tab with no room read never receives the param, at either floor', () => {
    // amd is the tab he named; its builder is turning_bullish_tiles, which has
    // no room read at all. ict / vcp / gabbar / keltner likewise.
    for (const tab of ['amd', 'keltner', 'ict', 'vcp', 'gabbar', 'supply', 'topping'] as const) {
      expect(ROOM_TABS).not.toContain(tab);
      expect(boardQuery({ tab, minRoom: 0 })).not.toContain('min_room');
      expect(boardQuery({ tab, minRoom: DEFAULT_MIN_ROOM })).not.toContain('min_room');
    }
  });

  it('NEGATIVE: a caller that did not decide sends no floor at all', () => {
    expect(boardQuery({ tab: 'zones' })).toBe('tab=zones');
    expect(boardQuery({ tab: 'deep_demand' })).toBe('tab=deep_demand');
  });
});

/* ── 3. the page ─────────────────────────────────────────────────────────── */

const TILE = {
  symbol: 'EOSE', name: 'Eos Energy', href: '/sepa/EOSE?tab=supply',
  price: 15.1, chg_pct: 1.2,
  bars: Array.from({ length: 30 }, (_, i) => ({
    t: `2026-02-${String(i + 1).padStart(2, '0')}`,
    o: 14 + i * 0.1, h: 14.5 + i * 0.1, l: 13.8 + i * 0.1, c: 14.2 + i * 0.1, v: 3e6,
  })),
  bands: [{ kind: 'demand', lo: 14.6, hi: 14.95 }],
  lines: [], markers: [], badges: [], stats: [{ k: 'room', v: '+12.4% -> 84.10' }],
  why: 'back inside a tested band',
};

const BOARD = (over: Record<string, unknown> = {}) => ({
  tab: 'deep_demand', count: 1, matched: 3, scanned: 1746, tiles: [TILE],
  min_room: 5, min_room_default: 5, hidden_low_room: 106,
  disclaimer: 'Study board.', ...over,
});

function stub(board: Record<string, unknown>) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps')) {
      const asked = new URL(url, 'http://x').searchParams.get('min_room');
      const body = asked === '0'
        ? { ...board, min_room: 0, hidden_low_room: 0, count: 69 }
        : board;
      return { ok: true, json: async () => body } as unknown as Response;
    }
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}

const urls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /></MemoryRouter>);

describe('the room control on the Chart Maps toolbar', () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => cleanup());

  it('renders BOTH shared floors, default selected, and picking "any room" asks for min_room=0', async () => {
    vi.stubGlobal('fetch', stub(BOARD()));
    page('/chart-maps?tab=deep_demand');
    const ctl = await screen.findByRole('tablist', { name: 'Room floor' });
    // Every FLOOR of the shared list is on the toolbar — pinned by the floor
    // VALUE through this page's labeller, not by bounceRoom's label string.
    // The shared thing is the set of floors (so the panel and the tiles can
    // never offer different ones); the wording belongs to each surface.
    for (const f of ROOM_FLOORS) {
      expect(within(ctl).getByRole('tab', { name: cmRoomLabel(Number(f.key)) }))
        .toBeInTheDocument();
    }
    expect(within(ctl).getByRole('tab', { name: cmRoomLabel(ROOM_MIN_PCT) }))
      .toHaveAttribute('aria-selected', 'true');
    // NEGATIVE: the toolbar offers nothing BEYOND the shared floors.
    expect(within(ctl).getAllByRole('tab')).toHaveLength(ROOM_FLOORS.length);

    fireEvent.click(within(ctl).getByRole('tab', { name: cmRoomLabel(0) }));
    await waitFor(() => expect(urls().some((u) => u.includes('tab=deep_demand') && u.includes('min_room=0'))).toBe(true));
  });

  it('says how many names the floor hid and names the way out of it', async () => {
    vi.stubGlobal('fetch', stub(BOARD()));
    page('/chart-maps?tab=deep_demand');
    const note = await screen.findByTestId('hidden-low-room');
    expect(note).toHaveTextContent('106 hidden');
    expect(note).toHaveTextContent('room < 5%');
    // THE INVARIANT: the readout must name the button that actually exists on
    // THIS toolbar. The floors are shared with the Back in Demand panel; the
    // wording is this page's own, so a readout pinned to the panel's label
    // would send him hunting for a control that is not there.
    expect(note).toHaveTextContent(cmRoomLabel(0));
    const ctl2 = screen.getByLabelText('Room floor');
    expect(within(ctl2).getByRole('tab', { name: cmRoomLabel(0) })).toBeInTheDocument();
    // It must say it is a view filter, not a gate.
    expect(note.getAttribute('title') || '').toMatch(/view filter/i);
  });

  it('NEGATIVE: hidden_low_room 0 renders no readout at all', async () => {
    vi.stubGlobal('fetch', stub(BOARD({ hidden_low_room: 0 })));
    page('/chart-maps?tab=deep_demand');
    expect(await screen.findByText('EOSE')).toBeInTheDocument();
    expect(screen.queryByTestId('hidden-low-room')).toBeNull();
  });

  it('NEGATIVE: a payload with NO hidden_low_room / min_room / min_room_default keys does not crash and renders no readout', async () => {
    const legacy = BOARD();
    delete (legacy as Record<string, unknown>).hidden_low_room;
    delete (legacy as Record<string, unknown>).min_room;
    delete (legacy as Record<string, unknown>).min_room_default;
    vi.stubGlobal('fetch', stub(legacy));
    page('/chart-maps?tab=deep_demand');
    expect(await screen.findByText('EOSE')).toBeInTheDocument();
    expect(screen.queryByTestId('hidden-low-room')).toBeNull();
    // The control is still offered — the floor is a server behaviour, not a
    // payload key, so an old cache must not take the toggle away from him.
    expect(screen.getByRole('tablist', { name: 'Room floor' })).toBeInTheDocument();
  });

  it('NEGATIVE: the amd tab — the one he named — has no room read, so it offers NO control and sends no floor', async () => {
    vi.stubGlobal('fetch', stub({ tab: 'amd', count: 1, matched: 1, tiles: [TILE], disclaimer: 'Study board.' }));
    page('/chart-maps?tab=amd');
    expect(await screen.findByText('EOSE')).toBeInTheDocument();
    expect(screen.queryByRole('tablist', { name: 'Room floor' })).toBeNull();
    expect(urls().some((u) => u.includes('min_room'))).toBe(false);
  });
});
