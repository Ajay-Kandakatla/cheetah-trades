/* 🧲 Bullish GEX first — the REAL branch payloads through the real Chart Maps page.
 *
 * Ajay 2026-09-27: "Can you add gex exposure bullish or bearish signal to the
 * stocks in our chartmaps and make it sorted by bullish gex please.." →
 * "Checkbox, ON by default" · "Also just in time GEX read too." · "One tab open both".
 *
 * Fixtures (components/__fixtures__/), captured from the branch API on Sun 2026-09-27:
 *   - gex_board_live_undervalue_2026_09_27.json — GET /chart-maps?tab=undervalue&limit=80,
 *     trimmed to 12 of 77 tiles (served order kept; gex_counts / count recomputed for
 *     the 12). Holds every bucket: 3 bullish, 1 mixed, 1 bearish, 4 Friday-expiry
 *     reads served as void "settled" (no read), 3 names with no ledger row.
 *   - gex_live_closed_2026_09_27.json — POST /chart-maps/gex-live for those 12 names
 *     (weekend → every row market_closed, the nightly read carried, no Massive call).
 *   - gex_live_disagree_derived_2026_09_27.json — DERIVED: the weekend has no live read,
 *     so STAA's live read = its real nightly read with ONLY the bucket edited
 *     (bullish → mixed; kind/as_of/as_of_text from the real JIT envelope), then
 *     re-composed by the branch's own gex_read.compose (chips/title/sort are served,
 *     never hand-written); counts recomputed by gex_read.counts. Envelope otherwise
 *     unchanged (still market_closed: weekend).
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import BOARD_RAW from '../components/__fixtures__/gex_board_live_undervalue_2026_09_27.json?raw';
import CLOSED_RAW from '../components/__fixtures__/gex_live_closed_2026_09_27.json?raw';
import DISAGREE_RAW from '../components/__fixtures__/gex_live_disagree_derived_2026_09_27.json?raw';
import { _resetGexLiveCache } from '../hooks/useGexLive';

type Chip = { kind: string; text: string; tone: string; title: string };
type Read = { kind: string; bucket: string | null; void: string | null } & Record<string, unknown>;
type TileRead = {
  symbol: string; live_status: string; nightly: Read | null; live: Read | null;
  chips: Chip[]; sort: { group: number; key: number | null; source: string | null };
};
type Legend = { no_read_group: number; groups: Array<{ group: number; key: string; label: string }> };
type Board = {
  tab: string; tiles: Array<{ symbol: string; gex?: TileRead }>;
  gex_legend: Legend; gex_counts: Record<string, number>; gex_rule: string; gex_scope: string;
  gex_sort_off: unknown; gex_as_of: string | null; gex_note: string;
};
type Live = { rows: Record<string, TileRead>; counts: Record<string, number>; market_closed: string | null } & Record<string, unknown>;

const BOARD = (): Board => JSON.parse(BOARD_RAW) as Board;
const CLOSED = (): Live => JSON.parse(CLOSED_RAW) as Live;
const DISAGREE = (): Live => JSON.parse(DISAGREE_RAW) as Live;

const SERVED = ['FUBO', 'BG', 'CMCO', 'JXN', 'EOSE', 'LUNR', 'STAA', 'LPG', 'DVN', 'MU', 'ONDS', 'CRDO'];
// ON with the nightly (closed) read: bullish strength desc → mixed → bearish → no read in served order.
const ON_CLOSED = ['LUNR', 'STAA', 'EOSE', 'LPG', 'JXN', 'FUBO', 'BG', 'CMCO', 'DVN', 'MU', 'ONDS', 'CRDO'];
// ON with the derived live read: STAA now mixed → leaves the bullish group, sits before LPG (served index).
const ON_DISAGREE = ['LUNR', 'EOSE', 'STAA', 'LPG', 'JXN', 'FUBO', 'BG', 'CMCO', 'DVN', 'MU', 'ONDS', 'CRDO'];

function stub(board: unknown, live: unknown) {
  return vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => board } as unknown as Response;
    if (url.includes('/chart-maps/gex-live')) return { ok: true, json: async () => live } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
const calls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /><Loc /></MemoryRouter>);

const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);
const box = () => document.querySelector('label.gex-toggle input[type="checkbox"]') as HTMLInputElement;
const search = () => screen.getByTestId('loc').textContent || '';
const tileOf = (sym: string) => Array.from(document.querySelectorAll('.cm-grid .cm-tile'))
  .find((el) => el.querySelector('.cm-tile-id b')?.textContent === sym) as HTMLElement | undefined;
const chipsOf = (sym: string) => Array.from(tileOf(sym)?.querySelectorAll('.cm-gex') ?? []);
const texts = (sym: string) => chipsOf(sym).map((c) => c.textContent);

function noJunk() {
  const all = [
    document.querySelector('.cm-grid')?.textContent ?? '',
    document.querySelector('label.gex-toggle')?.textContent ?? '',
    document.querySelector('label.gex-toggle')?.getAttribute('title') ?? '',
    ...Array.from(document.querySelectorAll('.cm-gex')).map((c) => `${c.textContent} ${c.getAttribute('title')}`),
  ];
  for (const s of all) {
    expect(s).not.toContain('[object Object]');
    expect(s).not.toMatch(/\bNaN\b/);
    expect(s).not.toMatch(/\bundefined\b/);
    expect(s.toLowerCase()).not.toContain('bounce');
  }
}

describe('🧲 GEX — the live branch payloads (undervalue, Sun 2026-09-27)', () => {
  beforeEach(() => { vi.restoreAllMocks(); _resetGexLiveCache(); });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('the fixtures are the real served shape: every tile has a read, counts sum, settled = no read', () => {
    const b = BOARD();
    expect(b.tab).toBe('undervalue');
    expect(b.tiles.map((t) => t.symbol)).toEqual(SERVED);
    expect(b.tiles.every((t) => t.gex && Array.isArray(t.gex.chips) && t.gex.chips.length >= 1)).toBe(true);
    expect(b.tiles.every((t) => t.gex!.live_status === 'not_asked' && t.gex!.live === null)).toBe(true);
    const sum = Object.values(b.gex_counts).reduce((a, n) => a + n, 0);
    expect(sum).toBe(b.tiles.length);
    expect(b.gex_legend.no_read_group).toBe(3);
    expect(b.gex_rule).toContain('UNMEASURED');
    expect(b.gex_sort_off).toBeNull();
    const settled = b.tiles.filter((t) => t.gex!.nightly?.void === 'settled');
    expect(settled.map((t) => t.symbol)).toEqual(['DVN', 'MU', 'ONDS', 'CRDO']);
    for (const t of settled) {
      expect(t.gex!.nightly!.bucket).toBeNull();
      expect(t.gex!.sort.group).toBe(b.gex_legend.no_read_group);
      expect(t.gex!.chips[0].title).toContain('settled');
    }
    // NEGATIVE: a void read never carries a bucket, a bucketed read is never void.
    for (const t of b.tiles) {
      const n = t.gex!.nightly;
      if (n) expect(n.void === null).toBe(n.bucket !== null);
    }
    const c = CLOSED();
    expect(Object.keys(c.rows).sort()).toEqual([...SERVED].sort());
    expect(c.market_closed).toBe('weekend');
    expect(Object.values(c.rows).every((r) => r.live_status === 'market_closed' && r.live === null)).toBe(true);
    expect(Object.keys(c).sort()).toEqual(['as_of', 'as_of_text', 'budget_sec', 'counts', 'legend', 'market_closed',
      'note', 'pending', 'rows', 'rule', 'scope', 'session', 'sort_off', 'truncated', 'ttl_sec']);
  });

  it('default ON → bullish first by strength, then mixed, bearish, no read; served chip text per bucket', async () => {
    vi.stubGlobal('fetch', stub(BOARD(), CLOSED()));
    page('/chart-maps?tab=undervalue');
    await waitFor(() => expect(order()).toEqual(ON_CLOSED));
    await waitFor(() => expect(document.querySelector('.gex-live')?.textContent).toBe(' · last close (market closed)'));
    expect(box().checked).toBe(true);
    expect(texts('LUNR')).toEqual(['🧲 GEX bullish · 0.09%']);
    expect(texts('STAA')).toEqual(['🧲 GEX bullish · 0.03%']);
    expect(texts('EOSE')).toEqual(['🧲 GEX bullish · 0.02%']);
    expect(texts('LPG')).toEqual(['🧲 GEX mixed']);
    expect(texts('JXN')).toEqual(['🧲 GEX bearish · 4.0%']);
    for (const s of ['FUBO', 'BG', 'CMCO', 'DVN', 'MU', 'ONDS', 'CRDO']) expect(texts(s)).toEqual(['🧲 no GEX read']);
    expect(chipsOf('LUNR')[0].className).toContain('cm-badge-good');
    expect(chipsOf('JXN')[0].className).toContain('cm-badge-warn');
    expect(chipsOf('DVN')[0].className).toContain('cm-badge-muted');
    expect(chipsOf('DVN')[0].getAttribute('title')).toContain('settled');
    expect(document.querySelector('.gex-count')!.textContent).toBe(' · 3 bullish · 1 mixed · 1 bearish · 7 no read');
    // Groups never go backwards down the page.
    const rows = CLOSED().rows;
    const groups = order().map((s) => rows[String(s)].sort.group);
    expect(groups).toEqual([...groups].sort((a, b) => a - b));
    // ONE just-in-time POST for the shown names.
    expect(calls().filter((u) => u.includes('/chart-maps/gex-live'))).toHaveLength(1);
    noJunk();
  });

  it('NEGATIVE: untick → the tab\'s own served order exactly, ?gex=off, nothing hidden, chips stay', async () => {
    vi.stubGlobal('fetch', stub(BOARD(), CLOSED()));
    page('/chart-maps?tab=undervalue');
    await waitFor(() => expect(order()).toEqual(ON_CLOSED));
    fireEvent.click(box());
    await waitFor(() => expect(search()).toContain('gex=off'));
    expect(order()).toEqual(SERVED);
    expect(texts('LUNR')).toEqual(['🧲 GEX bullish · 0.09%']);
    expect(calls().filter((u) => u.includes('/chart-maps?'))).toHaveLength(1);
    noJunk();
  });

  it('close and now disagree → both chips (close first), the tile sorts on the live read', async () => {
    vi.stubGlobal('fetch', stub(BOARD(), DISAGREE()));
    page('/chart-maps?tab=undervalue');
    await waitFor(() => expect(order()).toEqual(ON_DISAGREE));
    expect(texts('STAA')).toEqual(['🧲 close: bullish · 0.03%', '🧲 now: mixed']);
    const [close, now] = chipsOf('STAA');
    expect(close.className).toContain('cm-badge-good');
    expect(now.className).toContain('cm-badge-muted');
    expect(close.getAttribute('title')).toBe(now.getAttribute('title'));
    expect(close.getAttribute('title')).toContain('the order uses the live read');
    // NEGATIVE: agreeing names keep one chip.
    expect(texts('LUNR')).toEqual(['🧲 GEX bullish · 0.09%']);
    expect(document.querySelector('.gex-count')!.textContent).toBe(' · 2 bullish · 2 mixed · 1 bearish · 7 no read');
    fireEvent.click(box());
    await waitFor(() => expect(order()).toEqual(SERVED));
    expect(texts('STAA')).toEqual(['🧲 close: bullish · 0.03%', '🧲 now: mixed']);
    noJunk();
  });
});
