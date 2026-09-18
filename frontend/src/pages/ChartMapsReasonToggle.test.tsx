/* 🎯 UN-HIDE BY REASON on Chart Maps (Ajay 2026-09-17):
 *
 *   "Can you give me a toggle for the room too?
 *    I am not seeing all stocks on the selected filter due to this now"
 *
 * The screenshot was the AMD tab: `4 hidden (2 room < 5% · 1 floor swept ·
 * 1 no band) · show all`, one surviving tile. The words in that parenthetical
 * are now buttons.
 *
 * THE PAYLOAD IS HIS. `__fixtures__/chart_maps_amd_2026_09_17.json` is the
 * real `GET /chart-maps?tab=amd&limit=40` response captured read-only on
 * 2026-09-17 (40 tiles, 40/40 BLOCKED, `enterable_kind = demand`, bars trimmed
 * to the last 20 for size — nothing else touched). Every number below is
 * computed FROM that fixture, never typed: a hand-typed expectation is how a
 * test keeps passing after the served contract moves.
 *
 * What the negatives protect:
 *   - a row blocked for TWO reasons stays hidden until BOTH are clicked, or the
 *     count line lies about what he is looking at;
 *   - the second click never erases the first;
 *   - the preference reaches NO endpoint — not the board query, not the
 *     bounce-room POST body. A view filter that can reach a gate is not a view
 *     filter;
 *   - an un-hidden tile still wears its ⛔ chip: it is still BLOCKED, still not
 *     pushed, never entered;
 *   - a garbage `?unhide=` lands on the shipped board, never on "show
 *     everything";
 *   - the state is in the URL and nowhere else — no localStorage.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChartMaps from './ChartMaps';
import { UNHIDE_PARAM, parseUnhide, unhideParam } from '../lib/chartMaps';
import RAW from './__fixtures__/chart_maps_amd_2026_09_17.json?raw';

type Read = { verdict?: string | null; reasons?: string[]; reason_short?: string[] };
type Tile = { symbol: string; enterable?: Read | null };
const BOARD = JSON.parse(RAW) as { tiles: Tile[]; enterable_kind: string };

/* ── what his payload actually says, derived ─────────────────────────────── */
const blocked = BOARD.tiles.filter((t) => t.enterable?.verdict === 'BLOCKED');
const codesOf = (t: Tile) => (t.enterable?.reasons || []);
const labelOf = (code: string) => {
  for (const t of BOARD.tiles) {
    const i = codesOf(t).indexOf(code);
    if (i >= 0) return (t.enterable?.reason_short || [])[i];
  }
  return '';
};
/** Symbols whose EVERY block code is in `set` — the rows that come back. */
const recovered = (set: string[]) =>
  blocked.filter((t) => codesOf(t).length && codesOf(t).every((c) => set.includes(c)))
    .map((t) => t.symbol);
/** Baseline attribution: the first block code, i.e. exactly today's rule. */
const baseline = () => {
  const n: Record<string, number> = {};
  for (const t of blocked) n[codesOf(t)[0]] = (n[codesOf(t)[0]] || 0) + 1;
  return n;
};
const ALL_CODES = Array.from(new Set(blocked.flatMap(codesOf)));
const MULTI = blocked.filter((t) => codesOf(t).length > 1);

function stub() {
  return vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    if (url.includes('/chart-maps')) return { ok: true, json: async () => BOARD } as unknown as Response;
    if (url.includes('/supply-demand/bounce-room')) {
      bodies.push(typeof init?.body === 'string' ? init.body : '');
      return { ok: true, json: async () => ({ rows: {} }) } as unknown as Response;
    }
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
}
let bodies: string[] = [];
const urls = () => vi.mocked(fetch as never as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
const boardUrls = () => urls().filter((u) => u.includes('/chart-maps'));
const page = (entry: string) =>
  render(<MemoryRouter initialEntries={[entry]}><ChartMaps /></MemoryRouter>);
/** The grid's own count line — the one in his screenshot. Matched on its
 *  leading `N hidden`, because `N un-hidden` now lives on the same line. */
const line = async (): Promise<HTMLElement> => {
  let el: HTMLElement | null = null;
  await waitFor(() => {
    el = Array.from(document.querySelectorAll<HTMLElement>('.cm-hidden-count'))
      .find((d) => /^\d[\d,]* hidden/.test(d.textContent || '')) || null;
    expect(el).not.toBeNull();
  });
  return el!;
};
const chip = (code: string) => document.querySelector(`[data-reason="${code}"]`) as HTMLButtonElement | null;

describe('the un-hide chips on his AMD tab', () => {
  beforeEach(() => { vi.restoreAllMocks(); bodies = []; });
  afterEach(() => cleanup());

  it('the fixture IS the shape the rule rests on — 40 BLOCKED rows, labels 1:1 with codes', () => {
    expect(BOARD.enterable_kind).toBe('demand');
    expect(blocked.length).toBe(BOARD.tiles.length);
    for (const t of BOARD.tiles) {
      expect((t.enterable?.reason_short || []).length).toBe(codesOf(t).length);
      expect(codesOf(t).length).toBeGreaterThan(0);
    }
    expect(MULTI.length).toBeGreaterThan(0);   // the multi-reason case exists
  });

  it('names every served reason as a clickable chip, with the SERVED label and the baseline count', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=amd');
    const el = await line();
    const base = baseline();
    for (const code of ALL_CODES) {
      const b = chip(code);
      expect(b).not.toBeNull();
      expect(b!.textContent).toBe(`${base[code].toLocaleString()} ${labelOf(code)}`);
    }
    expect(el.textContent).toContain(`${blocked.length} hidden`);
    // NEGATIVE: the 3-reason cap of the text line is gone once the chips are on
    // — a reason with no chip is a reason he cannot un-hide.
    expect(ALL_CODES.length).toBeGreaterThan(3);
  });

  it('clicking the room chip writes ?unhide=room and brings back exactly the room-only tiles', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=amd');
    await line();
    fireEvent.click(chip('room')!);
    const back = recovered(['room']);
    await waitFor(() => expect(screen.getByText(back[0])).toBeInTheDocument());
    for (const sym of back) expect(screen.getByText(sym)).toBeInTheDocument();
    const el = await line();
    expect(el.textContent).toContain(`✓ ${labelOf('room')}`);
    expect(el.textContent).toContain(`${back.length} un-hidden`);
    expect(el.textContent).toContain(`${blocked.length - back.length} hidden`);
  });

  it('NEGATIVE: a tile blocked for TWO reasons stays gone until both chips are on', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=amd');
    await line();
    const both = MULTI[0];
    const [first, second] = codesOf(both);
    fireEvent.click(chip(second)!);
    await waitFor(() => expect(chip(second)).toHaveAttribute('aria-pressed', 'true'));
    expect(screen.queryByText(both.symbol)).toBeNull();
    fireEvent.click(chip(first)!);
    await waitFor(() => expect(screen.getByText(both.symbol)).toBeInTheDocument());
  });

  it('SECOND TOGGLE: the second click adds, it never replaces the first', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=amd');
    await line();
    fireEvent.click(chip('room')!);
    await waitFor(() => expect(chip('room')).toHaveAttribute('aria-pressed', 'true'));
    fireEvent.click(chip('proximity')!);
    await waitFor(() => expect(chip('proximity')).toHaveAttribute('aria-pressed', 'true'));
    expect(chip('room')).toHaveAttribute('aria-pressed', 'true');
    const back = recovered(['room', 'proximity']);
    for (const sym of back) expect(screen.getByText(sym)).toBeInTheDocument();
    const el = await line();
    expect(el.textContent).toContain(`${back.length} un-hidden`);
  });

  it('all of them on shows the whole payload at 0 hidden', async () => {
    vi.stubGlobal('fetch', stub());
    page(`/chart-maps?tab=amd&${UNHIDE_PARAM}=${ALL_CODES.slice().sort().join(',')}`);
    const el = await line();
    expect(el.textContent).toContain('0 hidden');
    expect(el.textContent).toContain(`${blocked.length} un-hidden`);
    for (const code of ALL_CODES) expect(chip(code)!.textContent).toBe(`✓ ${labelOf(code)}`);
  });

  it('an un-hidden tile still wears its ⛔ chip — BLOCKED did not move', async () => {
    vi.stubGlobal('fetch', stub());
    page(`/chart-maps?tab=amd&${UNHIDE_PARAM}=room`);
    const sym = recovered(['room'])[0];
    await waitFor(() => expect(screen.getByText(sym)).toBeInTheDocument());
    // The ⛔ chip is `enterableChipText`'s own, untouched by the ignore set.
    expect(screen.getAllByText(`⛔ ${labelOf('room')}`).length).toBeGreaterThan(0);
  });

  it('NEGATIVE: the preference never reaches the board query', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=amd');
    await line();
    const before = boardUrls().slice();
    fireEvent.click(chip('room')!);
    await waitFor(() => expect(chip('room')).toHaveAttribute('aria-pressed', 'true'));
    expect(boardUrls()).toEqual(before);
    expect(urls().some((u) => u.includes(`${UNHIDE_PARAM}=`))).toBe(false);
  });

  it('NEGATIVE: the bounce-room POST body is byte-identical with and without ?unhide=', async () => {
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=amd');
    await line();
    const plain = bodies.slice();
    const plainUrls = urls().slice();
    cleanup();
    vi.restoreAllMocks();
    bodies = [];
    vi.stubGlobal('fetch', stub());
    page(`/chart-maps?tab=amd&${UNHIDE_PARAM}=room,proximity`);
    await line();
    // Same requests, same bodies — the view preference reaches no endpoint, not
    // even as a symbol-list change.
    expect(bodies).toEqual(plain);
    expect(urls()).toEqual(plainUrls);
    for (const b of bodies) expect(b).not.toContain('unhide');
  });

  it('NEGATIVE: a garbage ?unhide= lands on the shipped board, not on "show everything"', async () => {
    for (const bad of [';;;', 'room!', 'x'.repeat(200), '', ',,,', 'ro om']) {
      cleanup();
      vi.stubGlobal('fetch', stub());
      page(`/chart-maps?tab=amd&${UNHIDE_PARAM}=${encodeURIComponent(bad)}`);
      const el = await line();
      expect(el.textContent).toContain(`${blocked.length} hidden`);
      expect(el.textContent).not.toContain('un-hidden');
      expect(document.querySelector('[aria-pressed="true"][data-reason]')).toBeNull();
    }
  });

  it('NEGATIVE: ?show=all names the un-hidden count, and re-checking keeps his selection', async () => {
    vi.stubGlobal('fetch', stub());
    page(`/chart-maps?tab=amd&show=all&${UNHIDE_PARAM}=room`);
    const off = await screen.findByText(/showing all/);
    expect(off.textContent).toContain('1 reason un-hidden');
    expect(document.querySelector('[data-reason]')).toBeNull();
    fireEvent.click(screen.getAllByRole('button', { name: 'enterable only' })[0]);
    const el = await line();
    expect(el.textContent).toContain(`✓ ${labelOf('room')}`);
  });

  it('NEGATIVE: the state is in the URL and nowhere else — localStorage is never written', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    vi.stubGlobal('fetch', stub());
    page('/chart-maps?tab=amd');
    await line();
    setItem.mockClear();
    fireEvent.click(chip('room')!);
    await waitFor(() => expect(chip('room')).toHaveAttribute('aria-pressed', 'true'));
    expect(setItem.mock.calls.filter(([k]) => String(k).includes('unhide'))).toHaveLength(0);
  });

  it('the selection survives a tab change — one set for the page', async () => {
    vi.stubGlobal('fetch', stub());
    page(`/chart-maps?tab=amd&${UNHIDE_PARAM}=room`);
    await line();
    expect(chip('room')).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('tab', { name: 'Gabbar Levels' }));
    await waitFor(() => expect(boardUrls().some((u) => u.includes('tab=gabbar'))).toBe(true));
    // The param rides along (setTab preserves every param but `pattern`).
    expect(urls().some((u) => u.includes(`${UNHIDE_PARAM}=`))).toBe(false);
    expect(chip('room')).toHaveAttribute('aria-pressed', 'true');
  });
});

describe('parseUnhide / unhideParam', () => {
  it('round-trips, deduped and sorted ascending', () => {
    expect(unhideParam(parseUnhide('room,proximity,room'))).toBe('proximity,room');
    expect(Array.from(parseUnhide('proximity,room')).sort()).toEqual(['proximity', 'room']);
  });

  it('writes NO param for an empty selection — the default rides nowhere', () => {
    expect(unhideParam(new Set())).toBeNull();
    expect(unhideParam([])).toBeNull();
  });

  it('NEGATIVE: FAILS CLOSED on anything unreadable — never on "show everything"', () => {
    for (const bad of [null, undefined, '', '   ', ';;;', ',,,', 'room!', 'a'.repeat(41), 'ro om']) {
      expect(parseUnhide(bad).size).toBe(0);
    }
    // …and it never throws, whatever lands in the bar.
    expect(() => parseUnhide('%%%%')).not.toThrow();
  });

  it('trims and lower-cases a well-formed token, per the parser’s stated steps', () => {
    // §3.3: split `,`, trim, lowercase, keep /^[a-z0-9_]{1,40}$/. So `ROOM%20`
    // in the bar normalises to the served code rather than being thrown away —
    // the same normalisation `unhideParam` writes back.
    expect(Array.from(parseUnhide('ROOM '))).toEqual(['room']);
    expect(Array.from(parseUnhide(' room , PROXIMITY '))).toEqual(['room', 'proximity']);
  });

  it('keeps an unknown but well-formed code — the codes are the payload’s, not this file’s', () => {
    expect(Array.from(parseUnhide('gremlin'))).toEqual(['gremlin']);
    expect(unhideParam(['gremlin', 'ROOM'])).toBe('gremlin,room');
  });
});
