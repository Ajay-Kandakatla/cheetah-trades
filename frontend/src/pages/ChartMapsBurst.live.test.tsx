/* ⚡ Momentum burst — the REAL branch payload through the real Chart Maps page.
 *
 * Ajay 2026-09-24: "Can you add this as a check box in our filters please.."
 * → "Pin + badge, hide nothing".
 *
 * Fixture: `components/__fixtures__/momentum_burst_live_2026_09_24.json` = the
 * zones board served by the branch API (tape "closed", 24 tiles; MELI is the one
 * ⚡ name, ORCL — his example — reads "no · runway_used" on that close; every
 * tile carries a served `burst` read and the board its `burst_counts`).
 * Pinned against the real payload, not a hand-built read:
 *   - no "[object Object]", "NaN" or "undefined" reaches the page;
 *   - every served ⚡ name carries the badge, verbatim, and no other tile does;
 *   - ON = the ⚡ names first in served order, then the rest in served order;
 *   - the checkbox count equals `burst_counts.burst` and the names pinned;
 *   - 🎯 (default ON) holds MELI back → "1 behind 🎯", nothing pinned from nowhere.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import LIVE_RAW from '../components/__fixtures__/momentum_burst_live_2026_09_24.json?raw';

type Read = { state?: string; on?: boolean; badge?: string | null; title?: string; reasons?: string[] };
type LiveTile = { symbol: string; burst?: Read | null; enterable?: { verdict?: string } };
type LiveBoard = { tab: string; tiles: LiveTile[]; burst_counts: { burst: number; no: number; unknown: number } };

const LIVE = (): LiveBoard => JSON.parse(LIVE_RAW) as LiveBoard;
const SERVED = LIVE().tiles.map((t) => t.symbol);
const BURSTS = LIVE().tiles.filter((t) => t.burst?.on === true && t.burst.state === 'burst').map((t) => t.symbol);

function stub(board: unknown) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => board } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const boardCalls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls
  .map((c) => String(c[0])).filter((u) => u.includes('/chart-maps?'));
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /></MemoryRouter>);

const tileEls = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile'));
const symOf = (el: Element) => el.querySelector('.cm-tile-id b')?.textContent ?? '';
const order = () => tileEls().map(symOf);
const chips = () => Array.from(document.querySelectorAll('.cm-grid .cm-badge-burst'));
const box = () => document.querySelector('label.mb-toggle input[type="checkbox"]') as HTMLInputElement;
const count = () => document.querySelector('label.mb-toggle .mb-count')?.textContent;

function noJunk() {
  const texts = [
    document.querySelector('.cm-grid')?.textContent ?? '',
    document.querySelector('label.mb-toggle')?.textContent ?? '',
    document.querySelector('label.mb-toggle')?.getAttribute('title') ?? '',
    document.querySelector('[data-testid="cm-burst-note"]')?.textContent ?? '',
    ...chips().map((c) => `${c.textContent} ${c.getAttribute('title')}`),
  ];
  for (const s of texts) {
    expect(s).not.toContain('[object Object]');
    expect(s).not.toMatch(/\bNaN\b/);
    expect(s).not.toMatch(/\bundefined\b/);
  }
}

describe('⚡ Momentum burst — the live branch payload (zones, 2026-09-24 close)', () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('the fixture is the real served shape: every tile has a read, counts sum to the tiles, MELI ⚡, ORCL no', () => {
    const b = LIVE();
    expect(b.tab).toBe('zones');
    expect(b.tiles.length).toBe(24);
    expect(b.tiles.every((t) => t.burst && typeof t.burst.state === 'string')).toBe(true);
    const { burst, no, unknown } = b.burst_counts;
    expect(burst + no + unknown).toBe(b.tiles.length);
    expect(BURSTS).toEqual(['MELI']);
    expect(burst).toBe(BURSTS.length);
    const orcl = b.tiles.find((t) => t.symbol === 'ORCL')!;
    expect(orcl.burst!.state).toBe('no');
    expect(orcl.burst!.reasons).toEqual(['runway_used']);
  });

  it('?burst=1&show=all: ⚡ names pinned first in served order, the rest in served order, badge on each, count == burst_counts', async () => {
    vi.stubGlobal('fetch', stub(LIVE()));
    page('/chart-maps?tab=zones&burst=1&show=all');
    await waitFor(() => expect(order()).toHaveLength(SERVED.length));
    await waitFor(() => expect(box()).not.toBeNull());
    expect(box().checked).toBe(true);

    const rest = SERVED.filter((s) => !BURSTS.includes(s));
    expect(order()).toEqual([...BURSTS, ...rest]);
    // nothing hidden: a permutation of the served tiles
    expect([...order()].sort()).toEqual([...SERVED].sort());

    // a badge on every ⚡ name, verbatim from the payload, and on no other tile
    const byBadge = tileEls().filter((el) => el.querySelector('.cm-badge-burst')).map(symOf);
    expect(byBadge).toEqual(BURSTS);
    const tiles = LIVE().tiles;
    for (const el of tileEls()) {
      const c = el.querySelector('.cm-badge-burst');
      if (!c) continue;
      const served = tiles.find((t) => t.symbol === symOf(el))!.burst!;
      expect(c.textContent).toBe(served.badge);
      expect(c.getAttribute('title')).toContain(served.title!);
      expect(c.getAttribute('title')).toContain('UNMEASURED');
    }

    // the count on the checkbox == burst_counts.burst == the names pinned
    expect(count()).toBe(` · ${LIVE().burst_counts.burst}`);
    expect(chips()).toHaveLength(LIVE().burst_counts.burst);
    expect(document.querySelector('label.mb-toggle .mb-behind')).toBeNull();

    noJunk();
    expect(boardCalls()).toHaveLength(1);
    expect(boardCalls()[0]).not.toContain('burst');
  });

  it('NEGATIVE: OFF (show=all) keeps the served order and shows no ⚡ badge — the count still says what ON would pin', async () => {
    vi.stubGlobal('fetch', stub(LIVE()));
    page('/chart-maps?tab=zones&show=all');
    await waitFor(() => expect(order()).toHaveLength(SERVED.length));
    await waitFor(() => expect(box()).not.toBeNull());
    expect(box().checked).toBe(false);
    expect(order()).toEqual(SERVED);
    expect(chips()).toHaveLength(0);
    expect(count()).toBe(` · ${BURSTS.length}`);
    noJunk();

    fireEvent.click(box());
    await waitFor(() => expect(order()[0]).toBe(BURSTS[0]));
    expect(chips()).toHaveLength(BURSTS.length);
    fireEvent.click(box());
    await waitFor(() => expect(order()).toEqual(SERVED));
    expect(boardCalls()).toHaveLength(1);
  });

  it('NEGATIVE: with 🎯 on (the default) MELI is held back — not pinned, "1 behind 🎯", the grid stays in served order', async () => {
    vi.stubGlobal('fetch', stub(LIVE()));
    page('/chart-maps?tab=zones&burst=1');
    await waitFor(() => expect(box()).not.toBeNull());
    await waitFor(() => expect(document.querySelector('label.mb-toggle .mb-behind')).not.toBeNull());
    expect(order()).not.toContain('MELI');
    expect(chips()).toHaveLength(0);
    expect(count()).toBe(' · 0');
    expect(document.querySelector('label.mb-toggle .mb-behind')!.textContent).toBe(' · 1 behind 🎯');
    // what 🎯 shows is a subsequence of the served order — ⚡ never re-ranks a hidden name in
    const shown = order();
    const idx = shown.map((s) => SERVED.indexOf(s));
    expect(idx.every((v, i) => v >= 0 && (i === 0 || v > idx[i - 1]))).toBe(true);
    noJunk();
  });
});
