import '../test/ggCardWatchOff';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import golden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';
import { resetGgFold } from '../lib/ggFold';

/* 🧠 from every tab on the 🧠 Potential sub — the board wiring (2026-11-24, potall spec §3.3 / §4 WP fe-potall).
 *
 * Ajay 2026-11-24: "I need a common place to see all the potnetials from all tabs" · "I mean all Gajjala's tabs".
 *
 * Pinned: the served rows print UNDER the last 🧠 card and ABOVE 📈 Track [C6]; the title / order / rule / as-of words sit
 * ONLY in the 🧠 ⓘ fold (closed by default) [C3]; no visible as-of / closed-day stamp from this block; the fault / more
 * lines stay visible; `gg-empty` steps aside only when there is no card and ≥ 1 row; an absent / null block = today's
 * DOM. NEGATIVES: never on another sub, never before the cards, nothing outside the fold, no b-word, no admin email. Every
 * string is a SENTINEL (the shape of pot_all.block); boards are CLONES of the 🧠 golden. */

vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: null, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', async (importOriginal) => {
  const m: any = await importOriginal();
  return { ...m, PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> };
});
vi.mock('./GgWatchButton', () => ({ GgWatchButton: () => <span /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('./GgTimeWindow', () => ({ GgTimeWindow: () => null }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));
vi.mock('../hooks/useCardLive', () => ({ useCardLive: () => ({ answer: null, footer: null }) }));
vi.mock('../hooks/useGgLive', () => ({ useGgLive: () => ({ quotesEvt: null, passNudge: 0, laneNudge: 0 }) }));

import GajjalaBoard from './GajjalaBoard';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const GOLD: Record<string, any> = (golden as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

/** The served block — sentinels in pot_all.block's shape (spec §3.1 step 8). */
function block(over: Record<string, any> = {}): any {
  return {
    title: 'served potall title',
    order_text: 'served potall order',
    rule_text: 'served potall rule',
    live: true,
    as_of_text: 'served potall as of',
    rows: [
      { symbol: 'APUS', setup: 'horizontal_fade', tier: 'forming', state: 'forming', kind: null, emoji: '➖', label: 'Fade',
        also: [], state_word: 'served apus word', state_label: 'served apus pill', broke_at: null, broke_text: null,
        alert_text: 'served no alert', read_at_text: 'served read at 19:56', href: '/chart-maps?tab=gajjala&sub=horizontal_fade&focus=APUS',
        text: 'APUS · served row text one', trader_text: 'served trader', promo_text: 'served promo', broker_text: null },
      { symbol: 'GLXG', setup: 'reversal_squeeze', tier: 'broke', state: 'partial', kind: null, emoji: '🎾', label: 'Squeeze',
        also: [{ key: 'high_si', emoji: '🩳', label: 'High SI' }], state_word: 'served glxg word', state_label: 'served glxg pill',
        broke_at: '17:01', broke_text: 'served broke 17:01', alert_text: null, read_at_text: null, href: null,
        text: 'GLXG · served row text two' },
      { symbol: 'GMM', setup: 'kiss_fly', tier: 'broke', state: 'invalid', kind: null, emoji: '💋', label: 'Kiss',
        also: [], state_word: 'served gmm word', state_label: null, broke_at: '12:26', broke_text: 'served broke 12:26',
        alert_text: null, read_at_text: null, href: 'javascript:alert(1)', text: 'GMM · served row text three' },
    ],
    n: 3, more_n: 0, more_text: null,
    counts: { potential: 1, forming: 1, broke: 2 },
    faults_n: 0, fault_text: null,
    ...over,
  };
}

/** A 🧠 board: the golden clone with its served block REMOVED (an older API) unless `over` sets one. */
function pot(over: Record<string, any> = {}): any {
  const b = clone(GOLD.potential);
  delete b.all_potentials;
  b.session = { ...(b.session || {}), refresh_sec: 0 };
  return { ...b, ...over };
}

let boardFor: (sub: string | null) => any = () => pot({ all_potentials: block() });
function stubFetch() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) return ok(boardFor(u.searchParams.get('sub')));
    return ok({});
  }));
}
async function mount(sub = 'potential') {
  stubFetch();
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala&sub=${sub}`]}><GajjalaBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
}
/** The card grid: `.cm-grid` with 👀 card-watch off (ggCardWatchOff), `gg-cardgrid` with it on. */
const gridOf = (c: HTMLElement) => (c.querySelector('[data-testid="gg-cardgrid"]') ?? c.querySelector('.cm-grid')) as HTMLElement;
const before = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
const inFold = (el: Element) => el.closest('.gg-fold-body') != null;
const tileIds = (c: HTMLElement) => Array.from(c.querySelectorAll('[data-testid^="gg-tile-"]'))
  .map((e) => e.getAttribute('data-testid')).filter((t) => !t!.startsWith('gg-tile-link-'));
const NOTE_WORDS = ['served potall title', 'served potall order', 'served potall rule', 'served potall as of'];

beforeEach(() => { resetGgFold(); boardFor = () => pot({ all_potentials: block() }); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🧠 from every tab — rows (served order, served words)', () => {
  it('prints every served row in SERVED order with the text verbatim, the chips, the link and the pill hover', async () => {
    await mount();
    const list = screen.getByTestId('gg-potall');
    const rows = within(list).getAllByRole('listitem');
    expect(rows.map((r) => r.getAttribute('data-testid'))).toEqual([
      'gg-potall-row-APUS-horizontal_fade', 'gg-potall-row-GLXG-reversal_squeeze', 'gg-potall-row-GMM-kiss_fly']);
    expect(rows[0].getAttribute('title')).toBe('served apus pill');
    const link = screen.getByTestId('gg-potall-link-APUS-horizontal_fade');
    expect(link.textContent).toBe('APUS · served row text one');
    expect(link.getAttribute('href')!.startsWith('/chart-maps?tab=gajjala&sub=horizontal_fade&focus=APUS')).toBe(true);
    expect(screen.getByTestId('gg-potall-alert-APUS-horizontal_fade').textContent).toBe('served no alert');
    expect(screen.getByTestId('gg-potall-readat-APUS-horizontal_fade').textContent).toBe('served read at 19:56');
    expect(screen.getByTestId('gg-trader-potall-APUS-horizontal_fade').textContent).toBe('served trader');
    expect(screen.getByTestId('gg-promo-potall-APUS-horizontal_fade').textContent).toBe('served promo');
    expect(screen.getByTestId('gg-potall-broke-GLXG-reversal_squeeze').textContent).toBe('served broke 17:01');
    expect(screen.getByTestId('gg-potall-broke-GMM-kiss_fly').textContent).toBe('served broke 12:26');
    for (const r of rows) expect(r).toBeVisible();
  });

  it('NEGATIVE: href null or junk → plain text, no link; absent chips → no node; no pill → no title', async () => {
    const { container } = await mount();
    expect(screen.queryByTestId('gg-potall-link-GLXG-reversal_squeeze')).toBeNull();
    expect(screen.getByTestId('gg-potall-plain-GLXG-reversal_squeeze').textContent).toBe('GLXG · served row text two');
    expect(screen.queryByTestId('gg-potall-link-GMM-kiss_fly')).toBeNull();
    expect(screen.getByTestId('gg-potall-plain-GMM-kiss_fly').textContent).toBe('GMM · served row text three');
    expect(container.querySelector('a[href^="javascript"]')).toBeNull();
    for (const id of ['GLXG-reversal_squeeze', 'GMM-kiss_fly']) {
      expect(screen.queryByTestId(`gg-potall-alert-${id}`)).toBeNull();
      expect(screen.queryByTestId(`gg-potall-readat-${id}`)).toBeNull();
      expect(screen.queryByTestId(`gg-trader-potall-${id}`)).toBeNull();
      expect(screen.queryByTestId(`gg-broker-potall-${id}`)).toBeNull();
    }
    expect(screen.queryByTestId('gg-potall-broke-APUS-horizontal_fade')).toBeNull();
    expect(screen.getByTestId('gg-potall-row-GMM-kiss_fly').hasAttribute('title')).toBe(false);
  });
});

describe('🧠 from every tab — the SERVED golden block (pot_all.block via tab.build, regenerated 2026-11-24)', () => {
  it('the golden 🧠 board renders its served rows verbatim, in served order, links via ggHref; fold words in the fold', async () => {
    const served = clone(GOLD.potential.all_potentials);
    expect(Array.isArray(served?.rows) && served.rows.length > 0).toBe(true);
    boardFor = () => ({ ...clone(GOLD.potential), session: { ...(GOLD.potential.session || {}), refresh_sec: 0 } });
    await mount();
    const items = within(screen.getByTestId('gg-potall')).getAllByRole('listitem');
    expect(items.map((i) => i.getAttribute('data-testid'))).toEqual(
      served.rows.map((r: any) => `gg-potall-row-${r.symbol}-${r.setup}`));
    for (const r of served.rows) {
      const id = `${r.symbol}-${r.setup}`;
      const text = screen.getByTestId(r.href ? `gg-potall-link-${id}` : `gg-potall-plain-${id}`);
      expect(text.textContent).toBe(r.text);
      if (r.broke_text) expect(screen.getByTestId(`gg-potall-broke-${id}`).textContent).toBe(r.broke_text);
      if (r.alert_text) expect(screen.getByTestId(`gg-potall-alert-${id}`).textContent).toBe(r.alert_text);
    }
    for (const k of ['title', 'order_text', 'rule_text', 'as_of_text']) {
      if (typeof served[k] !== 'string') continue;
      const hits = Array.from(document.querySelectorAll('[data-testid^="gg-potall-"]')).filter((e) => e.textContent === served[k]);
      expect(hits.length, k).toBe(1);
      expect(inFold(hits[0]), k).toBe(true);
      expect(hits[0], k).not.toBeVisible();
    }
    expect(document.body.textContent).not.toMatch(/NaN|undefined|None/);
  });
});

describe('🧠 from every tab — placement [C6]', () => {
  it('sits AFTER the last 🧠 card and BEFORE 📈 Track (then 👀); the cards / Track / watch keep their DOM order', async () => {
    const { container } = await mount();
    const list = screen.getByTestId('gg-potall');
    const grid = gridOf(container);
    const track = screen.getByTestId('gg-track');
    const watch = screen.getByTestId('gg-watch');
    const ids = tileIds(container);
    expect(ids.length).toBe(GOLD.potential.tiles.length);
    const lastCard = screen.getByTestId(ids[ids.length - 1]!);
    expect(before(lastCard, list)).toBe(true);
    expect(before(grid, list)).toBe(true);
    expect(grid.contains(list)).toBe(false);
    expect(before(list, track)).toBe(true);
    expect(before(track, watch)).toBe(true);
    cleanup();
    boardFor = () => pot();
    const plain = await mount();
    expect(tileIds(plain.container)).toEqual(ids);
  });

  it('NEGATIVE: never before the card grid, never before the first card', async () => {
    const { container } = await mount();
    const list = screen.getByTestId('gg-potall');
    const first = screen.getByTestId(tileIds(container)[0]!);
    expect(before(list, first)).toBe(false);
    expect(gridOf(container)).not.toBeNull();
    expect(before(list, gridOf(container))).toBe(false);
  });
});

describe('🧠 from every tab — the ⓘ fold [C3]', () => {
  it('title / order / rule / as-of are mounted ONLY inside the 🧠 sub fold, closed (hidden) by default', async () => {
    await mount();
    const body = screen.getByTestId('gg-sub-body');
    for (const [id, w] of [['gg-potall-title', NOTE_WORDS[0]], ['gg-potall-order', NOTE_WORDS[1]],
      ['gg-potall-rule', NOTE_WORDS[2]], ['gg-potall-asof', NOTE_WORDS[3]]]) {
      const el = screen.getByTestId(id);
      expect(el.textContent).toBe(w);
      expect(body.contains(el), id).toBe(true);
      expect(inFold(el), id).toBe(true);
      expect(el, id).not.toBeVisible();
    }
    fireEvent.click(screen.getByTestId('gg-sub-toggle'));
    expect(screen.getByTestId('gg-potall-rule')).toBeVisible();
  });

  it('NEGATIVE: none of the fold words (nor any as-of / closed-day stamp) is anywhere outside the fold', async () => {
    const { container } = await mount();
    const board = container.querySelector('.gg-board')!.cloneNode(true) as HTMLElement;
    for (const f of Array.from(board.querySelectorAll('.gg-fold-body'))) f.remove();
    for (const w of NOTE_WORDS) expect(board.textContent, w).not.toContain(w);
    const list = screen.getByTestId('gg-potall-block');
    expect(inFold(list)).toBe(false);
    for (const w of NOTE_WORDS) expect(list.textContent).not.toContain(w);
    expect(list.textContent).not.toMatch(/as of|closed/i);
  });

  it('fault_text and more_text stay VISIBLE outside the fold', async () => {
    boardFor = () => pot({ all_potentials: block({ more_n: 4, more_text: 'served more 4', faults_n: 1, fault_text: 'served fault line' }) });
    await mount();
    for (const [id, w] of [['gg-potall-more', 'served more 4'], ['gg-potall-fault', 'served fault line']]) {
      const el = screen.getByTestId(id);
      expect(el.textContent).toBe(w);
      expect(inFold(el)).toBe(false);
      expect(el).toBeVisible();
    }
  });

  it('a fault with no row still prints the fault line (and the empty / card logic is untouched)', async () => {
    boardFor = () => pot({ all_potentials: block({ rows: [], n: 0, fault_text: 'served fault line' }) });
    await mount();
    expect(screen.getByTestId('gg-potall-fault')).toBeVisible();
    expect(screen.queryByTestId('gg-potall')).toBeNull();
  });
});

describe('🧠 from every tab — the empty line', () => {
  it('tiles [] and rows [] → gg-empty with the served empty_note (today\'s words), no list', async () => {
    boardFor = () => pot({ tiles: [], all_potentials: block({ rows: [], n: 0 }) });
    await mount();
    expect(screen.getByTestId('gg-empty').textContent).toBe(GOLD.potential.empty_note);
    expect(screen.queryByTestId('gg-potall')).toBeNull();
    expect(screen.queryByTestId('gg-potall-block')).toBeNull();
  });

  it('tiles [] and rows ≥ 1 → NO gg-empty, the list prints', async () => {
    boardFor = () => pot({ tiles: [], all_potentials: block() });
    await mount();
    expect(screen.queryByTestId('gg-empty')).toBeNull();
    expect(screen.getByTestId('gg-potall')).toBeVisible();
  });

  it('NEGATIVE: block absent (older API) or null → gg-empty exactly as today, no list node, no fold words', async () => {
    for (const over of [{ tiles: [] }, { tiles: [], all_potentials: null }]) {
      boardFor = () => pot(over);
      const { container } = await mount();
      expect(screen.getByTestId('gg-empty').textContent).toBe(GOLD.potential.empty_note);
      expect(container.querySelector('[data-testid^="gg-potall"]')).toBeNull();
      cleanup();
    }
  });

  it('NEGATIVE: block absent → the 🧠 board DOM is byte-identical to a null block', async () => {
    boardFor = () => pot();
    const a = await mount();
    const htmlA = a.container.innerHTML;
    cleanup();
    boardFor = () => pot({ all_potentials: null });
    const b = await mount();
    expect(b.container.innerHTML).toBe(htmlA);
  });
});

describe('🧠 from every tab — never on another sub', () => {
  it('NEGATIVE: a block served on bull_flag (should never happen) prints no row and no fold word', async () => {
    boardFor = () => ({ ...clone(GOLD.bull_flag), session: { ...(GOLD.bull_flag.session || {}), refresh_sec: 0 },
      all_potentials: block() });
    const { container } = await mount('bull_flag');
    expect(container.querySelector('[data-testid^="gg-potall"]')).toBeNull();
    for (const w of NOTE_WORDS) expect(container.textContent).not.toContain(w);
    expect(container.textContent).not.toContain('served row text one');
  });
});

describe('🧠 from every tab — words and phone', () => {
  it('NEGATIVE: no "bounce" in any rendered row / fold word; no admin email in the new files', async () => {
    const { container } = await mount();
    expect(container.textContent!.toLowerCase()).not.toContain('bounce');
    for (const rel of ['src/components/GgPotAll.tsx', 'src/components/GajjalaBoard.potall_2026_11_24.test.tsx',
      'src/components/GgPotAll.test.tsx']) {
      const src = await readSource(rel);
      expect(src, rel).not.toMatch(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}/);
    }
  });

  it('430 px: the row wraps its tags, never widens the board (class + css check)', async () => {
    await mount();
    const row = screen.getByTestId('gg-potall-row-APUS-horizontal_fade');
    expect(row.className).toContain('gg-potall-row');
    expect(screen.getByTestId('gg-potall').className).toContain('gg-potall-rows');
    const css = await readSource('src/styles/gajjala.css');
    const rule = css.match(/\.gg-potall-row \{[^}]*\}/)?.[0] ?? '';
    expect(rule).toContain('flex-wrap: wrap');
    expect(rule).toContain('min-width: 0');
    expect(rule).toContain('overflow-wrap: anywhere');
    expect(rule).not.toMatch(/white-space:\s*nowrap/);
    const wrap = css.match(/\.gg-potall \{[^}]*\}/)?.[0] ?? '';
    expect(wrap).toContain('max-width: 100%');
  });
});
