/* 🧘 GG-like on the 👀 Watch and the 📅 roster — chip and list only (2026-11-27, spec gglike §3.9, WP fe-watch).
 * Ajay 2026-11-27: "find calmer and better setups.. Continue to track the runners we might evolve and find patterns in the
 * current runners too but I want to make sure we are finding similar setups to Gajjala".
 * The REAL board, fetch stubbed (the sections-test harness). Every word in these fixtures is a stand-in for a served one.
 * The tile prints the SERVED block of ITS setup (the served setup chip's key, else 🎾, else the first carded) as a chip right
 * after the setup chip; the ✓ / ✗ rows live in the ⋯ drawer. [C1, C7] NOTHING on the Watch is hidden by 🧘: no toggle, no
 * hidden line, no `hidden` attribute, no storage key — a Watch of ✗ rows with both filter keys set by hand renders the same
 * tiles, pager and section counts as a Watch with the blocks stripped, and a push link (?focus=) on a ✗ row is outlined
 * and scrolled to. Roster: the chip after the seat chip, no filter; the 📅 counts line ONLY inside the ⓘ fold. 430 px
 * source guards. NEGATIVES throughout. Display only; UNMEASURED. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import gold from '../lib/__fixtures__/ggwRunRoster.golden.json';
vi.mock('./GgWatchButton', () => ({ GgWatchButton: ({ symbol }: any) => <span data-testid={`ggwatch-${symbol}`} /> }));
import GajjalaWatchBoard from './GajjalaWatchBoard';
import GgwRunRoster from './GgwRunRoster';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';
import { GGW_PATH, ggwTileGgLike, parseRowOrg, parseRowTags } from '../lib/gajjalaWatch';
import { GGW_RUNTRACK_PATH, parseRunRoster, parseRunTrack, type GgwRunRoster as RosterBlock } from '../lib/ggwRunRoster';
import { GG_LIKE_LS } from '../lib/ggLike';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = fixture as any;
const G = gold as any;
/** The Watch filter key the critique cut [C7] — set by hand to prove nothing reads it. */
const WATCH_KEY = 'gg-like-only:watch';

/* ── served stand-ins ─────────────────────────────────────────────────────────────────────────────────────────── */
const LIKE = (setup: string, verdict: 'gg_like' | 'not' | 'unknown' = 'not', o: Record<string, unknown> = {}) => ({
  verdict, tone: verdict === 'gg_like' ? 'ok' : verdict === 'not' ? 'no' : 'unknown',
  chip: `🧘 served-chip-${setup}-${verdict}`, title: `served-title-${setup}`,
  reason: verdict === 'not' ? { code: 'near_high', label: `served-reason-${setup}` } : null,
  keep: false,
  checks: [
    { key: 'near_high', ok: verdict === 'gg_like', info: false, mark: verdict === 'gg_like' ? '✓' : '✗',
      label: `served-row-${setup}`, value: 'served-value', need: 'served-need' },
    { key: 'lower_highs', ok: null, info: true, mark: 'ⓘ', label: 'served-info-row', value: 'served-info-value', need: null },
  ],
  info: null, source: 'read', source_text: null, ...o,
});
const TAGS = (setups: Array<[string, unknown]>) => ({
  on_board: true,
  setups: setups.map(([s, gl]) => ({ setup: s, label: `served-label-${s}`, state: 'armed', state_label: null,
    ...(gl === undefined ? {} : { gg_like: gl }) })),
  stages: null, float: null, broker_text: null, trader_text: null, promo_text: null,
});
const SETUP = (key: string) => ({ setup: key, label: `served-setup-${key}`, state_label: null, source: 'board',
  text: `served-setup-chip-${key}`, title: null });
const ORG = (group: string, sym: string, o: Record<string, unknown> = {}) => ({
  group, when: { bucket: 'intraday', text: `served-when-${sym}`, title: `served-when-title-${sym}` },
  setup: null, ran: null, past_winner: null, ...o,
});
function rowOf(sym: string, o: Record<string, unknown> = {}): any {
  const base = clone(RAW.rows[2]);
  base.symbol = sym;
  if (typeof base.text === 'string') base.text = base.text.split('XYZQ').join(sym);
  return { ...base, auto: null, aplus: null, added_at: null, ...o };
}
const SEC = (key: string, n: number, syms: string[]) => ({
  key, title: `served-title-${key}`, text: `served-head-${key} · ${n}`, hint: `served-hint-${key}`, n, symbols: syms,
});
/** H1: setup chip = 💋 (two carded) · H2: setup chip = 🎾 · AU1: no setup chip (fallback 🎾) · AU2: ✗ 🎾 · AU3: chip names
 *  an UNCARDED setup (bull flag) — every block ✗ unless said. */
function orgRows(): any[] {
  const two = () => TAGS([['kiss_fly', LIKE('kiss_fly')], ['reversal_squeeze', LIKE('reversal_squeeze', 'gg_like')]]);
  return [
    rowOf('H1', { org: ORG('yours', 'H1', { setup: SETUP('kiss_fly') }), tags: two() }),
    rowOf('H2', { org: ORG('yours', 'H2', { setup: SETUP('reversal_squeeze') }), tags: two() }),
    rowOf('AU1', { auto: { tag: '🤖', text: 'served-auto', why: 'potential' }, org: ORG('auto', 'AU1'), tags: two() }),
    rowOf('AU2', { auto: { tag: '🤖', text: 'served-auto', why: 'potential' },
      org: ORG('auto', 'AU2', { setup: SETUP('reversal_squeeze') }), tags: TAGS([['reversal_squeeze', LIKE('reversal_squeeze')]]) }),
    rowOf('AU3', { auto: { tag: '🤖', text: 'served-auto', why: 'potential' },
      org: ORG('auto', 'AU3', { setup: SETUP('bull_flag') }), tags: TAGS([['kiss_fly', LIKE('kiss_fly')]]) }),
  ];
}
const SECTIONS = () => [SEC('yours', 2, ['H1', 'H2']), SEC('auto', 3, ['AU1', 'AU2', 'AU3'])];
function boardOf(rows: any[]): any {
  const b = clone(RAW);
  b.rows = rows;
  b.symbols = rows.filter((r) => !r.auto).map((r) => r.symbol);
  b.refresh_sec = 0;
  b.next_window_sec = null;
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  b.auto = { state: 'ok', n: 3, symbols: ['AU1', 'AU2', 'AU3'], title: 'served-auto-head', hint: 'served-auto-hint', removed: [] };
  b.sections = SECTIONS();
  return b;
}
/** Every row's `gg_like` keys stripped (today's server). */
function stripLike(rows: any[]): any[] {
  return rows.map((r) => {
    const x = clone(r);
    for (const s of x.tags?.setups ?? []) delete s.gg_like;
    return x;
  });
}
/** Every served block turned ✗ (so a filter, if there were one, would hide every tile). */
function allNot(rows: any[]): any[] {
  return rows.map((r) => {
    const x = clone(r);
    for (const s of x.tags?.setups ?? []) if (s.gg_like) s.gg_like = LIKE(s.setup, 'not');
    return x;
  });
}

/* ── harness ──────────────────────────────────────────────────────────────────────────────────────────────────── */
let reads: string[] = [];
let writes: string[] = [];
function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => { reads.push(k); return m.has(k) ? m.get(k)! : null; },
    setItem: (k: string, v: string) => { writes.push(k); m.set(k, String(v)); },
    removeItem: (k: string) => { writes.push(k); m.delete(k); },
  } as Storage;
}
const res = (body: unknown) => ({ ok: true, json: async () => body }) as unknown as Response;
let serve: () => any = () => boardOf(orgRows());
let scrolled: string[] = [];
let phoneNow = false;
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });

async function mount(search = '') {
  vi.stubGlobal('matchMedia', (qq: string) => ({ matches: phoneNow, media: qq, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    const qs = url.split('?symbols=')[1];
    if (url.includes(GGW_PATH + '?symbols=') && qs != null) {
      const syms = decodeURIComponent(qs).split(',');
      return res({ ...serve(), rows: serve().rows.filter((r: any) => syms.includes(r.symbol)) });
    }
    if (url.includes(GGW_PATH)) return res(serve());
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala_watch${search}`]}><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 5; i += 1) await flush();
  return r.container;
}
const q = (c: ParentNode, id: string) => c.querySelector(`[data-testid="${id}"]`) as HTMLElement | null;
const tile = (c: ParentNode, s: string) => q(c, `ggw-tile-${s}`);
const SYMS = ['H1', 'H2', 'AU1', 'AU2', 'AU3'];
/** What a filter would move: every tile's hidden flag, every pager chip (text + pressed), every section / group header. */
function snapshot(c: HTMLElement) {
  return {
    tiles: SYMS.map((s) => [s, !!tile(c, s), tile(c, s)?.hidden ?? null]),
    grid: Array.from(c.querySelector('.ggw-grid')!.children).map((e) => [e.getAttribute('data-testid'), (e as HTMLElement).hidden]),
    pager: Array.from(c.querySelectorAll('[data-testid^="ggw-pager-"]'))
      .map((e) => [e.getAttribute('data-testid'), e.textContent, e.getAttribute('aria-pressed')]),
    sections: Array.from(c.querySelectorAll('[data-testid^="ggw-section-"]')).map((e) => [e.getAttribute('data-testid'), e.textContent]),
  };
}

const origScroll = (Element.prototype as any).scrollIntoView;
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse('2026-11-27T15:00:00.000Z'));
  reads = []; writes = [];
  vi.stubGlobal('localStorage', memStorage());
  vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache();
  serve = () => boardOf(orgRows());
  scrolled = [];
  phoneNow = false;
  (Element.prototype as any).scrollIntoView = function (this: HTMLElement) { if (this.id) scrolled.push(this.id); };
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache();
  (Element.prototype as any).scrollIntoView = origScroll;
  document.body.style.overflow = '';
});

/* ── parsers ──────────────────────────────────────────────────────────────────────────────────────────────────── */
describe('🧘 the strict parsers carry gg_like', () => {
  it('parseRowTags keeps each setup\'s own served block; junk / null / absent → no key', () => {
    const t = parseRowTags(TAGS([['kiss_fly', LIKE('kiss_fly')], ['reversal_squeeze', { verdict: 'maybe', chip: 'x' }],
      ['bull_flag', null], ['horizontal_fade', undefined], ['intraday_vcp', { verdict: 'not', chip: '' }]]))!;
    expect(t.setups.map((s) => s.setup)).toEqual(['kiss_fly', 'reversal_squeeze', 'bull_flag', 'horizontal_fade', 'intraday_vcp']);
    expect(t.setups[0].gg_like!.chip).toBe('🧘 served-chip-kiss_fly-not');
    expect(t.setups[0].gg_like!.checks.map((c) => c.key)).toEqual(['near_high', 'lower_highs']);
    for (const s of t.setups.slice(1)) expect('gg_like' in s, s.setup).toBe(false);
  });
  it('NEGATIVE: a tags block without gg_like parses exactly as before (no new key)', () => {
    const t = parseRowTags(TAGS([['kiss_fly', undefined]]))!;
    expect(t.setups[0]).toEqual({ setup: 'kiss_fly', label: 'served-label-kiss_fly', state: 'armed', state_label: null });
  });
  it('parseRowOrg keeps the served setup key ONLY with a parsed chip; NEGATIVE: no key / blank key / no chip → absent', () => {
    expect(parseRowOrg(ORG('auto', 'X', { setup: SETUP('kiss_fly') }))!.setup_key).toBe('kiss_fly');
    expect('setup_key' in parseRowOrg(ORG('auto', 'X', { setup: { text: 'chip', title: null } }))!).toBe(false);
    expect('setup_key' in parseRowOrg(ORG('auto', 'X', { setup: { ...SETUP('kiss_fly'), setup: '  ' } }))!).toBe(false);
    expect('setup_key' in parseRowOrg(ORG('auto', 'X', { setup: { setup: 'kiss_fly', text: '' } }))!).toBe(false);
    expect(parseRowOrg(ORG('auto', 'X', { setup: SETUP('kiss_fly') }))!.setup).toEqual({ text: 'served-setup-chip-kiss_fly', title: null });
  });
  it('ggwTileGgLike: the chip\'s setup, else 🎾, else the first carded; NEGATIVE: an uncarded chip setup / no tags → null', () => {
    const two = parseRowTags(TAGS([['kiss_fly', LIKE('kiss_fly')], ['reversal_squeeze', LIKE('reversal_squeeze', 'gg_like')]]));
    expect(ggwTileGgLike({ org: parseRowOrg(ORG('a', 'X', { setup: SETUP('kiss_fly') })), tags: two })!.setup).toBe('kiss_fly');
    expect(ggwTileGgLike({ org: parseRowOrg(ORG('a', 'X')), tags: two })!.setup).toBe('reversal_squeeze');
    const one = parseRowTags(TAGS([['bull_flag', LIKE('bull_flag')], ['kiss_fly', LIKE('kiss_fly')]]));
    expect(ggwTileGgLike({ org: null, tags: one })!.setup).toBe('bull_flag');
    expect(ggwTileGgLike({ org: parseRowOrg(ORG('a', 'X', { setup: SETUP('intraday_vcp') })), tags: one })).toBeNull();
    expect(ggwTileGgLike({ org: null, tags: null })).toBeNull();
    /* the picked setup carries no block → null, never another setup's block */
    const noBlk = parseRowTags(TAGS([['reversal_squeeze', undefined], ['kiss_fly', LIKE('kiss_fly')]]));
    expect(ggwTileGgLike({ org: null, tags: noBlk })).toBeNull();
  });
  it('roster row + record: gg_like / gg_like_text carried; NEGATIVE: junk → absent / null, every other key unchanged', () => {
    const raw = clone(G.runners);
    raw.rows[0].gg_like = { setup: 'reversal_squeeze', label: '🎾 served', ...LIKE('reversal_squeeze') };
    raw.rows[1].gg_like = { verdict: 'nope', chip: 'x' };
    const b = parseRunRoster(raw)!;
    expect(b.rows[0].gg_like!.chip).toBe('🧘 served-chip-reversal_squeeze-not');
    expect('gg_like' in b.rows[1]).toBe(false);
    expect('gg_like' in b.rows[2]).toBe(false);
    const { gg_like: _g, ...rest } = b.rows[0];
    expect(rest).toEqual({ ...G.runners.rows[0] });
    expect(parseRunTrack({ ...G.track_all, gg_like_text: '🧘 served counts' })!.gg_like_text).toBe('🧘 served counts');
    for (const j of [undefined, null, '', '   ', 5]) expect(parseRunTrack({ ...G.track_all, gg_like_text: j })!.gg_like_text).toBeNull();
  });
});

/* ── the 👀 tile ──────────────────────────────────────────────────────────────────────────────────────────────── */
describe('🧘 the chip after the setup chip, the list in the ⋯ drawer', { timeout: 30000 }, () => {
  it('the chip is the NEXT sibling of the setup chip, a <span>, and carries THAT setup\'s served block', async () => {
    const c = await mount();
    const h1 = q(tile(c, 'H1')!, 'gg-like-chip-H1')!;
    expect(q(tile(c, 'H1')!, 'ggw-setup-chip-H1')!.nextElementSibling).toBe(h1);
    expect(h1.tagName).toBe('SPAN');
    expect(h1.textContent).toBe('🧘 served-chip-kiss_fly-not');             // 💋 chip → the 💋 block, not the 🎾 one
    expect(h1.getAttribute('title')).toBe('served-title-kiss_fly');
    expect(h1.className).toContain('gg-like-no');
    const h2 = q(tile(c, 'H2')!, 'gg-like-chip-H2')!;
    expect(q(tile(c, 'H2')!, 'ggw-setup-chip-H2')!.nextElementSibling).toBe(h2);
    expect(h2.textContent).toBe('🧘 served-chip-reversal_squeeze-gg_like');
    expect(h2.className).toContain('gg-like-ok');
    expect(tile(c, 'H1')!.querySelectorAll('.gg-like-chip')).toHaveLength(1);   // one chip per tile
  });
  it('no served setup chip → the 🎾 block (fallback); NEGATIVE: a chip naming an uncarded setup draws no 🧘 chip', async () => {
    const c = await mount();
    expect(q(tile(c, 'AU1')!, 'gg-like-chip-AU1')!.textContent).toBe('🧘 served-chip-reversal_squeeze-gg_like');
    expect(q(tile(c, 'AU3')!, 'ggw-setup-chip-AU3')).not.toBeNull();
    expect(tile(c, 'AU3')!.querySelector('.gg-like-chip')).toBeNull();
    expect(q(c, 'ggw-gglike-AU3')).toBeNull();
  });
  it('the ✓ / ✗ rows are inside the ⋯ drawer (closed until ⋯), info row muted, never in the head', async () => {
    const c = await mount();
    const drawer = q(c, 'ggw-drawer-H1')!;
    const list = q(drawer, 'gg-like-list-H1')!;
    expect(list).not.toBeNull();
    expect(q(c, 'ggw-gglike-H1')!.getAttribute('data-setup')).toBe('kiss_fly');
    expect(drawer.hidden).toBe(true);
    expect(tile(c, 'H1')!.querySelector('.ggw-tile-head .gg-like-list')).toBeNull();
    expect(tile(c, 'H1')!.querySelectorAll('.gg-like-list')).toHaveLength(1);
    const rows = list.querySelectorAll('li');
    expect(rows[0].className).toContain('gg-like-row--no');
    expect(rows[0].textContent).toContain('served-row-kiss_fly');
    expect(rows[1].className).toContain('gg-like-row--info');
    expect(rows[1].className).not.toContain('gg-like-row--no');
    fireEvent.click(q(c, 'ggw-drawer-btn-H1')!);
    expect(q(c, 'ggw-drawer-H1')!.hidden).toBe(false);
  });
  it('NEGATIVE: tags null / no block / a junk block → nothing new on the tile (byte-equal to today\'s tile)', async () => {
    const variants: Array<(r: any) => any> = [
      (r) => ({ ...r, tags: null }),
      (r) => ({ ...r, tags: TAGS([['kiss_fly', undefined], ['reversal_squeeze', undefined]]) }),
      (r) => ({ ...r, tags: TAGS([['kiss_fly', { verdict: 'maybe', chip: 'x' }], ['reversal_squeeze', { verdict: 'not' }]]) }),
    ];
    const html: string[] = [];
    for (const v of variants) {
      serve = () => boardOf(orgRows().map((r) => (r.symbol === 'H1' ? v(r) : r)));
      const c = await mount();
      const t = tile(c, 'H1')!;
      expect(t.querySelector('.gg-like-chip')).toBeNull();
      expect(t.querySelector('.gg-like-list')).toBeNull();
      expect(q(c, 'ggw-gglike-H1')).toBeNull();
      html.push(t.querySelector('.ggw-tile-head')!.outerHTML);
      cleanup();
    }
    expect(html[2]).toBe(html[1]);
  });
});

/* ── [C1, C7] nothing is hidden ───────────────────────────────────────────────────────────────────────────────── */
describe('🧘 [C1, C7] nothing on the Watch is ever hidden by 🧘', { timeout: 40000 }, () => {
  for (const phone of [false, true]) {
    it(`a Watch of ✗ rows with BOTH filter keys set → same tiles, pager and section counts as the stripped Watch (${phone ? 'phone' : 'desktop'})`, async () => {
      phoneNow = phone;
      serve = () => boardOf(stripLike(orgRows()));
      const base = snapshot(await mount());
      cleanup();
      reads = []; writes = [];
      localStorage.setItem(WATCH_KEY, '1');
      localStorage.setItem(GG_LIKE_LS.board, '1');
      writes = [];
      serve = () => boardOf(allNot(orgRows()));
      const c = await mount();
      expect(c.querySelectorAll('.gg-like-chip').length).toBe(SYMS.length - 1);   // the chips ARE drawn (AU3 has none)
      expect(snapshot(c)).toEqual(base);
      expect(c.querySelectorAll('.ggw-tile[hidden]').length)
        .toBe(base.tiles.filter((t) => t[2] === true).length);
      expect(c.querySelector('.gg-like-toggle')).toBeNull();
      expect(c.querySelector('.gg-like-hidden')).toBeNull();
      expect(c.querySelector('.gg-like-note')).toBeNull();
      expect(c.querySelector('[class*="gg-like-show-all"]')).toBeNull();
      expect(reads.filter((k) => k.startsWith('gg-like-only'))).toEqual([]);   // no key is ever read …
      expect(writes.filter((k) => k.startsWith('gg-like-only'))).toEqual([]);  // … or written
    });
  }
  it('?focus= on a ✗ row (both keys set) → that tile is shown, outlined and scrolled to once', async () => {
    phoneNow = true;
    localStorage.setItem(WATCH_KEY, '1');
    localStorage.setItem(GG_LIKE_LS.board, '1');
    serve = () => boardOf(allNot(orgRows()));
    const c = await mount('&focus=AU2');
    for (let i = 0; i < 3; i += 1) await flush();
    const t = tile(c, 'AU2')!;
    expect(q(t, 'gg-like-chip-AU2')!.getAttribute('data-gg-like')).toBe('not');
    expect(t.hidden).toBe(false);
    expect(t.classList.contains('ggw-tile-focus')).toBe(true);
    expect(scrolled.filter((x) => x === 'ggw-AU2')).toHaveLength(1);
  });
});

/* ── 📅 the roster ────────────────────────────────────────────────────────────────────────────────────────────── */
describe('🧘 📅 roster: the chip after the seat chip, no filter; the record line only in the ⓘ fold', () => {
  const rosterOf = (o: (raw: any) => void = () => {}): RosterBlock => {
    const raw = clone(G.runners);
    o(raw);
    return parseRunRoster(raw) as RosterBlock;
  };
  const withLike = (raw: any) => {
    raw.rows[0].gg_like = { setup: 'reversal_squeeze', label: '🎾 served', ...LIKE('reversal_squeeze', 'not') };
    raw.rows[1].gg_like = { setup: 'kiss_fly', label: '💋 served', ...LIKE('kiss_fly', 'gg_like') };
    raw.rows[2].gg_like = { verdict: 'junk', chip: 'x' };
  };
  let urls: string[] = [];
  let track: any = G.track_all;
  beforeEach(() => {
    vi.useRealTimers();
    urls = [];
    track = { ...G.track_all, gg_like_text: '🧘 served counts line' };
    vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
      urls.push(String(u));
      return res(String(u).includes(GGW_RUNTRACK_PATH) ? track : {});
    }));
  });
  const flushR = async () => { for (let i = 0; i < 4; i += 1) await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); };
  const openInfo = async () => {
    const det = screen.getByTestId('ggw-rr-info') as HTMLDetailsElement;
    await act(async () => { det.open = true; fireEvent(det, new Event('toggle')); });
    await flushR();
    return det;
  };

  it('the chip is the next sibling of the seat chip, a <span> with the served words; NEGATIVE: no / junk block → none', () => {
    render(<GgwRunRoster block={rosterOf(withLike)} phone={false} onChanged={() => {}} />);
    const [a, b, c] = G.runners.rows.map((r: any) => r.symbol);
    const chipA = screen.getByTestId(`gg-like-chip-${a}`);
    expect(screen.getByTestId(`ggw-rr-seat-${a}`).nextElementSibling).toBe(chipA);
    expect(chipA.tagName).toBe('SPAN');
    expect(chipA.textContent).toBe('🧘 served-chip-reversal_squeeze-not');
    expect(chipA.getAttribute('title')).toBe('served-title-reversal_squeeze');
    expect(screen.getByTestId(`gg-like-chip-${b}`).className).toContain('gg-like-ok');
    expect(screen.queryByTestId(`gg-like-chip-${c}`)).toBeNull();
    expect(screen.queryByTestId(`gg-like-chip-${G.runners.rows[3].symbol}`)).toBeNull();
  });
  it('NEGATIVE: no filter on the roster — a ✗ row stays, the rows are the stripped roster\'s, no toggle / hidden line', () => {
    const plain = render(<GgwRunRoster block={rosterOf()} phone={false} onChanged={() => {}} />);
    const rowsOf = (root: ParentNode) => Array.from(root.querySelectorAll('[data-testid^="ggw-rr-row-"]')).map((e) => e.getAttribute('data-testid'));
    const before = rowsOf(plain.container);
    const moreBefore = q(plain.container, 'ggw-rr-more')?.textContent ?? null;
    plain.unmount();
    const r = render(<GgwRunRoster block={rosterOf(withLike)} phone={false} onChanged={() => {}} />);
    expect(rowsOf(r.container)).toEqual(before);
    expect(q(r.container, 'ggw-rr-more')?.textContent ?? null).toBe(moreBefore);
    expect(r.container.querySelector('.gg-like-toggle')).toBeNull();
    expect(r.container.querySelector('.gg-like-hidden')).toBeNull();
  });
  it('the 📅 counts line prints ONLY inside the ⓘ fold, after it opens; NEGATIVE: closed → not in the DOM, no fetch', async () => {
    render(<GgwRunRoster block={rosterOf(withLike)} phone={false} onChanged={() => {}} />);
    await flushR();
    expect(screen.queryByTestId('ggw-rr-track-gglike')).toBeNull();
    expect(urls.filter((u) => u.includes(GGW_RUNTRACK_PATH))).toEqual([]);
    const det = await openInfo();
    const line = screen.getByTestId('ggw-rr-track-gglike');
    expect(line.textContent).toBe('🧘 served counts line');
    expect(det.contains(line)).toBe(true);
    expect(screen.getByTestId('ggw-rr-track-summary').nextElementSibling).toBe(line);
  });
  it('NEGATIVE: a record without gg_like_text (today\'s server) → no 🧘 line in the open fold', async () => {
    track = G.track_all;
    render(<GgwRunRoster block={rosterOf()} phone={false} onChanged={() => {}} />);
    await openInfo();
    expect(screen.getByTestId('ggw-rr-track-summary')).not.toBeNull();
    expect(screen.queryByTestId('ggw-rr-track-gglike')).toBeNull();
  });
});

/* ── 📱 430 px source guards ──────────────────────────────────────────────────────────────────────────────────── */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const ruleOf = (src: string, sel: string): string | null => {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)\\s*${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
};
const wraps = (decl: string | null) => !!decl && /flex-wrap:\s*wrap/.test(decl) && /min-width:\s*0\b/.test(decl);
const chipWraps = (decl: string | null) => !!decl && /white-space:\s*normal/.test(decl) && /overflow-wrap:\s*anywhere/.test(decl)
  && /min-width:\s*0\b/.test(decl) && /max-width:\s*100%/.test(decl);
const PRE_FIX = `.ggw-tile-head { display: flex; align-items: center; }
.ggw-drawer-row { display: flex; }
.ggw-rr-row { display: flex; }
.gg-like-chip { white-space: nowrap; }`;

describe('📱 430 px: the 🧘 chip and list wrap inside the tile / the roster row', () => {
  it('the tile head, the drawer row and the roster row wrap with min-width 0; the chip wraps anywhere', async () => {
    const watch = await readSource('src/styles/gajjalaWatch.css');
    const roster = await readSource('src/styles/ggwRunRoster.css');
    const like = await readSource('src/styles/ggLike.css');
    expect(wraps(ruleOf(watch, '.ggw-tile-head'))).toBe(true);
    expect(wraps(ruleOf(watch, '.ggw-drawer-row'))).toBe(true);
    expect(wraps(ruleOf(roster, '.ggw-rr-row'))).toBe(true);
    expect(chipWraps(ruleOf(like, '.gg-like-chip'))).toBe(true);
    expect(like).not.toMatch(/nowrap/);
  });
  it('NEGATIVE: the same matchers reject a pre-fix sheet', () => {
    expect(wraps(ruleOf(PRE_FIX, '.ggw-tile-head'))).toBe(false);
    expect(wraps(ruleOf(PRE_FIX, '.ggw-drawer-row'))).toBe(false);
    expect(wraps(ruleOf(PRE_FIX, '.ggw-rr-row'))).toBe(false);
    expect(chipWraps(ruleOf(PRE_FIX, '.gg-like-chip'))).toBe(false);
  });
  it('the mounts add no inline width / nowrap, no storage key and no 🧘 word (every word served)', async () => {
    for (const f of ['src/components/GajjalaWatchCompact.tsx', 'src/components/GgwRunRoster.tsx', 'src/components/GajjalaWatchTile.tsx']) {
      const src = await readSource(f);
      const mine = src.split('\n').filter((l) => /GgLike|ggLike|gg_like|GgwGgLikeChip|gglike/i.test(l) && !/^\s*(\*|\/\*|\/\/|\{\/\*)/.test(l));
      expect(mine.length, f).toBeGreaterThan(0);
      for (const l of mine) {
        expect(l, f).not.toMatch(/style=|nowrap|localStorage|GG_LIKE_LS|hidden=/);
        expect(l, f).not.toMatch(/GG-like|tennis|EMA/);
      }
    }
    for (const f of ['src/components/GajjalaWatchBoard.tsx', 'src/components/GajjalaWatchLayout.tsx']) {
      expect(await readSource(f), f).not.toMatch(/ggLike|GgLike|gg_like|gg-like/);
    }
  });
});
