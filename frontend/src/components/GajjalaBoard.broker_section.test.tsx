import '../test/ggCardWatchOff';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import potGolden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';
import boardSrc from './GajjalaBoard.tsx?raw';
import { GG_SECTION_COLLAPSED_LS, GG_SECTION_OPENED_LS } from '../lib/ggBrokerSection';
import { GGW_SECTION_GLYPH } from '../lib/gajjalaWatch';
import { GGC_PATH } from '../lib/gajjalaCardView';

/* 🚫 2026-11-25 — the 🧠 Potential sub's served bottom section header (spec fidsec §3.3, fe-section tests 1-13).
 *
 * His words are quoted in lib/ggBrokerSection.ts (this file never types the broker word). What is built: a header above
 * the 🚫 cards. NOTHING MOVES — those cards have sat last since 2026-11-09 — and nothing is hidden by the server.
 *
 * Boards are in-file CLONES of the OWNER golden the backend writes (`boards.potential`: EEE DDD AAA JJJ CCC all 🔝 focus,
 * then HHH; `focus.n == 5`), built to match what the server serves: k = 1 → HHH tagged with the golden block's own text
 * and a section built from that same text; k ≥ 2 → `board.focus` and every tile `focus` deleted first (tab.focus_block
 * serves no focus with fewer than five non-🚫 picks), then tagged. NEGATIVES: 0 flagged → byte-identical DOM; a non-owner
 * draws nothing; a section that is not the tail draws nothing; the 👀 Watch layout draws no in-grid header; one drawn
 * card → no pager label but the chip prints; the header never remounts a card; mounting writes no storage. */

vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: null, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({ PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <span data-testid={`short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

/* tsc-safe source read (the GajjalaBoard.potential.test precedent): vitest serves a `.css?raw` import empty. */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const root = (globalThis as any).process?.cwd?.() || '.';
  return (mod?.default || mod).readFileSync(`${root}/${rel}`, 'utf8');
}

const POT: Record<string, any> = (potGolden as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));
const BLOCK = (): any => POT.potential.broker_flags;
const TAG = (): string => BLOCK().text;
const ORDER: string[] = POT.potential.tiles.map((t: any) => t.symbol);       // EEE DDD AAA JJJ CCC HHH

/** The served section, built from the golden block's own word (tab.broker_section shape; `{title} · {n}`). */
const section = (symbols: string[], extra: Record<string, unknown> = {}) => ({
  key: 'broker', title: TAG(), text: `${TAG()} · ${symbols.length}`, hint: null, n: symbols.length, symbols, ...extra,
});
/** The owner board as served with `syms` on his list: the list, each tile's tag, and (unless `sec` is false) the section. */
function served(base: any, syms: string[], opts: { sec?: any; dropFocus?: boolean } = {}) {
  const b = clone(base);
  if (opts.dropFocus) {
    delete b.focus;
    for (const t of b.tiles) delete t.focus;
  }
  b.broker_flags = { ...b.broker_flags, symbols: [...syms] };
  for (const t of b.tiles) if (syms.includes(t.symbol)) t.broker_text = TAG();
  const sec = opts.sec === undefined ? section(syms) : opts.sec;
  if (sec !== false) b.broker_flags.section = sec;
  return b;
}
const k1 = (extra: Record<string, unknown> = {}) => served(POT.potential, ['HHH'], { sec: section(['HHH'], extra) });
const k2 = () => served(POT.potential, ['CCC', 'HHH'], { dropFocus: true });

type Call = { method: string; path: string };
let calls: Call[] = [];
function stub(getBoard: (n: number, u: URL) => any) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    const method = String(init?.method || 'GET').toUpperCase();
    calls.push({ method, path: u.pathname });
    if (u.pathname.endsWith('/chart-maps/gajjala/scan') || u.pathname.startsWith(GGC_PATH)) {
      return { ok: false, status: 404, json: async () => ({ detail: 'Not Found' }) };
    }
    if (u.pathname.includes('/chart-maps/gajjala/broker-flags')) return { ok: true, status: 200, json: async () => ({}) };
    if (/\/chart-maps\/gajjala$/.test(u.pathname)) {
      return { ok: true, status: 200, json: async () => clone(getBoard(gets().length, u)) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  }));
}
const gets = () => calls.filter((c) => c.method === 'GET' && /\/chart-maps\/gajjala$/.test(c.path));
const brokers = () => calls.filter((c) => c.path.includes('/chart-maps/gajjala/broker-flags'));
const sleep = (ms: number) => act(() => new Promise<void>((r) => setTimeout(r, ms)));
async function mount(q = 'tab=gajjala&sub=potential') {
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  await sleep(20);
  return r;
}
const phone = (on: boolean) => vi.stubGlobal('matchMedia', (qq: string) => ({
  matches: on, media: qq, addEventListener: () => {}, removeEventListener: () => {},
}));
/** The card grid's direct children, as tokens: SYM for a card, `HEAD` for the section header, `HR` for the 🔝 divider. */
function gridSeq(c: HTMLElement): string[] {
  const g = c.querySelector('.cm-grid') as HTMLElement;
  return [...g.children].map((e) => {
    const id = e.getAttribute('data-testid') || '';
    if (id === 'gg-broker-section') return 'HEAD';
    if (id === 'gg-focus-divider') return 'HR';
    return id.startsWith('gg-tile-') ? id.slice('gg-tile-'.length) : `?${e.tagName}`;
  });
}
const cardSyms = (c: HTMLElement) => gridSeq(c).filter((s) => s !== 'HEAD' && s !== 'HR');
const hiddenCards = (c: HTMLElement) => [...c.querySelectorAll('.cm-grid > .gg-card')]
  .filter((e) => (e as HTMLElement).hidden).map((e) => e.getAttribute('data-testid')!.slice('gg-tile-'.length));

beforeEach(() => { calls = []; });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🚫 bottom section — desktop default grid', () => {
  it('1. k = 1: ONE header, the served text, right before HHH; the 🔝 divider still after CCC; order === served; no button, nothing hidden', async () => {
    stub(() => k1());
    const { container } = await mount();
    const heads = container.querySelectorAll('[data-testid="gg-broker-section"]');
    expect(heads).toHaveLength(1);
    const head = heads[0] as HTMLElement;
    expect(head.textContent).toBe(`${TAG()} · 1`);
    expect(head.nextElementSibling?.getAttribute('data-testid')).toBe('gg-tile-HHH');
    expect(gridSeq(container)).toEqual(['EEE', 'DDD', 'AAA', 'JJJ', 'CCC', 'HR', 'HEAD', 'HHH']);
    expect(cardSyms(container)).toEqual(ORDER);
    expect(within(head).queryByRole('button')).toBeNull();
    expect(hiddenCards(container)).toEqual([]);
    expect(head).toBeVisible();
  });

  it('2. k = 2 as served (no focus): the header right before CCC, no divider, CCC then HHH after it', async () => {
    stub(() => k2());
    const { container } = await mount();
    expect(screen.getByTestId('gg-broker-section').textContent).toBe(`${TAG()} · 2`);
    expect(gridSeq(container)).toEqual(['EEE', 'DDD', 'AAA', 'JJJ', 'HEAD', 'CCC', 'HHH']);
    expect(container.querySelector('[data-testid="gg-focus-divider"]')).toBeNull();
    expect(hiddenCards(container)).toEqual([]);
  });

  it('3. NEGATIVE 0 flagged / junk section → no header and the DOM byte-identical to the untouched golden', async () => {
    stub(() => POT.potential);
    const base = await mount();
    const html0 = base.container.innerHTML;
    expect(screen.queryByTestId('gg-broker-section')).toBeNull();
    cleanup();
    const junk = [null, {}, section(['HHH'], { text: '  ', title: null }), section([]), section(['ZZZ'])];
    for (const sec of junk) {
      stub(() => { const b = clone(POT.potential); b.broker_flags.section = sec; return b; });
      const r = await mount();
      expect(screen.queryByTestId('gg-broker-section'), JSON.stringify(sec)).toBeNull();
      expect(r.container.innerHTML, JSON.stringify(sec)).toBe(html0);
      cleanup();
    }
  });

  it('4. NEGATIVE non-owner (broker_flags null, no tag): no header, the tag word nowhere, same card order', async () => {
    stub(() => { const b = clone(POT.potential); b.broker_flags = null; return b; });
    const { container } = await mount();
    expect(screen.queryByTestId('gg-broker-section')).toBeNull();
    expect(document.body.textContent || '').not.toContain(TAG());
    expect(cardSyms(container)).toEqual(ORDER);
  });

  it('5. ONE GATE: a served block on another sub (bull_flag) DRAWS — the FE holds no sub list', async () => {
    const bf = POT.bull_flag;
    const last = bf.tiles[bf.tiles.length - 1].symbol;
    stub(() => served(bf, [last]));
    const { container } = await mount('tab=gajjala&sub=bull_flag');
    const head = screen.getByTestId('gg-broker-section');
    expect(head.textContent).toBe(`${TAG()} · 1`);
    expect(head.nextElementSibling?.getAttribute('data-testid')).toBe(`gg-tile-${last}`);
    expect(cardSyms(container)).toEqual(bf.tiles.map((t: any) => t.symbol));
  });

  it('6. NEGATIVE the listed cards are not the tail (the section names the FIRST card) → no header, order kept', async () => {
    stub(() => served(POT.potential, ['EEE'], { dropFocus: true }));
    const { container } = await mount();
    expect(screen.queryByTestId('gg-broker-section')).toBeNull();
    expect(cardSyms(container)).toEqual(ORDER);
  });

  it('7. NEGATIVE impossible payload (focus kept, CCC + HHH tagged): header AND divider both render, 6 cards, served order', async () => {
    stub(() => served(POT.potential, ['CCC', 'HHH']));
    const { container } = await mount();
    expect(gridSeq(container)).toEqual(['EEE', 'DDD', 'AAA', 'JJJ', 'HEAD', 'CCC', 'HR', 'HHH']);
    expect(cardSyms(container)).toHaveLength(6);
    expect(hiddenCards(container)).toEqual([]);
  });
});

describe('🚫 bottom section — phone fold', () => {
  it('8. phone: a button (▾ + served text, aria-expanded); tap folds the 🚫 cards (still in the DOM), tap again opens', async () => {
    phone(true);
    stub(() => k2());
    const { container } = await mount();
    const btn = screen.getByTestId('gg-broker-section-btn');
    expect(btn.textContent).toBe(`${GGW_SECTION_GLYPH.open} ${TAG()} · 2`);
    expect(btn.getAttribute('aria-expanded')).toBe('true');
    expect(hiddenCards(container)).toEqual([]);
    fireEvent.click(btn);
    expect(hiddenCards(container)).toEqual(['CCC', 'HHH']);
    expect(cardSyms(container)).toEqual(ORDER);                    // still in the DOM, same order
    expect(screen.getByTestId('gg-broker-section-btn').textContent).toBe(`${GGW_SECTION_GLYPH.closed} ${TAG()} · 2`);
    expect(screen.getByTestId('gg-broker-section-btn').getAttribute('aria-expanded')).toBe('false');
    expect(screen.getByTestId('gg-broker-section').className).toContain('ggw-section--folded');
    expect(screen.getByTestId('gg-broker-section')).not.toHaveAttribute('hidden');
    expect(localStorage.getItem(GG_SECTION_COLLAPSED_LS)).toBe('["broker"]');
    fireEvent.click(screen.getByTestId('gg-broker-section-btn'));
    expect(hiddenCards(container)).toEqual([]);
    expect(localStorage.getItem(GG_SECTION_COLLAPSED_LS)).toBeNull();
  });

  it('9. served folded_default: phone starts folded, NEGATIVE mounting writes no storage; tap opens (remembered across a remount); NEGATIVE desktop all visible, no button', async () => {
    phone(true);
    const fd = () => served(POT.potential, ['CCC', 'HHH'], { dropFocus: true, sec: section(['CCC', 'HHH'], { folded_default: true }) });
    stub(fd);
    let r = await mount();
    expect(hiddenCards(r.container)).toEqual(['CCC', 'HHH']);
    expect(localStorage.getItem(GG_SECTION_COLLAPSED_LS)).toBeNull();
    expect(localStorage.getItem(GG_SECTION_OPENED_LS)).toBeNull();
    fireEvent.click(screen.getByTestId('gg-broker-section-btn'));
    expect(hiddenCards(r.container)).toEqual([]);
    expect(localStorage.getItem(GG_SECTION_OPENED_LS)).toBe('["broker"]');
    cleanup();
    stub(fd);
    r = await mount();
    expect(hiddenCards(r.container)).toEqual([]);
    cleanup();
    phone(false);
    localStorage.removeItem(GG_SECTION_OPENED_LS);
    stub(fd);
    r = await mount();
    expect(hiddenCards(r.container)).toEqual([]);
    expect(screen.queryByTestId('gg-broker-section-btn')).toBeNull();
    expect(screen.getByTestId('gg-broker-section').textContent).toBe(`${TAG()} · 2`);
    expect(localStorage.getItem(GG_SECTION_OPENED_LS)).toBeNull();
  });

  it('10. focus: desktop ?focus=🚫 scrolls once; phone + folded_default opens the section then scrolls once on a visible card; NEGATIVE ?focus=other leaves it folded', async () => {
    const scrolled: Array<{ id: string | null; hidden: boolean }> = [];
    const proto = Element.prototype as any;
    const had = Object.prototype.hasOwnProperty.call(proto, 'scrollIntoView');
    const prev = proto.scrollIntoView;
    proto.scrollIntoView = function (this: HTMLElement) {
      scrolled.push({ id: this.getAttribute('data-testid'), hidden: this.hidden });
    };
    try {
    const fd = () => served(POT.potential, ['CCC', 'HHH'], { dropFocus: true, sec: section(['CCC', 'HHH'], { folded_default: true }) });

    stub(() => k1());
    await mount('tab=gajjala&sub=potential&focus=HHH');
    expect(scrolled.filter((s) => s.id?.startsWith('gg-tile-'))).toEqual([{ id: 'gg-tile-HHH', hidden: false }]);
    cleanup();

    scrolled.length = 0;
    phone(true);
    stub(fd);
    let r = await mount('tab=gajjala&sub=potential&focus=HHH');
    expect(screen.getByTestId('gg-broker-section-btn').getAttribute('aria-expanded')).toBe('true');
    expect(hiddenCards(r.container)).toEqual([]);
    expect(scrolled.filter((s) => s.id?.startsWith('gg-tile-'))).toEqual([{ id: 'gg-tile-HHH', hidden: false }]);
    expect(localStorage.getItem(GG_SECTION_OPENED_LS)).toBe('["broker"]');
    cleanup();

    scrolled.length = 0;
    localStorage.removeItem(GG_SECTION_OPENED_LS);
    stub(fd);
    r = await mount('tab=gajjala&sub=potential&focus=EEE');
    expect(screen.getByTestId('gg-broker-section-btn').getAttribute('aria-expanded')).toBe('false');
    expect(hiddenCards(r.container)).toEqual(['CCC', 'HHH']);
    expect(scrolled.filter((s) => s.id?.startsWith('gg-tile-'))).toEqual([{ id: 'gg-tile-EEE', hidden: false }]);
    expect(localStorage.getItem(GG_SECTION_OPENED_LS)).toBeNull();
    } finally {
      if (had) proto.scrollIntoView = prev; else delete proto.scrollIntoView;
    }
  });
});

describe('🚫 bottom section — 👀 Watch layout, remount, source guards', () => {
  it('11. Watch layout ON: the pager label prints the served text before HHH, no in-grid header; NEGATIVE no section → no label; NEGATIVE one drawn 🚫 card → no pager, no label, no header, the chip still prints', async () => {
    localStorage.setItem('gg-card-watch', '1');
    stub(() => k1());
    let r = await mount();
    expect(r.container.querySelector('[data-testid="gg-cardwatch"]')).not.toBeNull();
    const grp = screen.getByTestId('ggc-pager-group-broker');
    expect(grp.textContent).toBe(`${TAG()} · 1`);
    expect(grp.nextElementSibling?.querySelector('[data-testid="ggc-pager-HHH"]')).not.toBeNull();
    expect(screen.queryByTestId('gg-broker-section')).toBeNull();
    cleanup();

    stub(() => POT.potential);
    r = await mount();
    expect(r.container.querySelector('[data-testid="ggc-pager"]')).not.toBeNull();
    expect(r.container.querySelector('[data-testid^="ggc-pager-group-"]')).toBeNull();
    cleanup();

    stub(() => { const b = k1(); b.tiles = b.tiles.filter((t: any) => t.symbol === 'HHH'); delete b.focus; delete b.tiles[0].focus; return b; });
    r = await mount();
    expect(r.container.querySelector('[data-testid="gg-cardwatch"]')).not.toBeNull();
    expect(r.container.querySelector('[data-testid="ggc-pager"]')).toBeNull();
    expect(r.container.querySelector('[data-testid^="ggc-pager-group-"]')).toBeNull();
    expect(screen.queryByTestId('gg-broker-section')).toBeNull();
    expect(screen.getByTestId('gg-tile-HHH')).toBeTruthy();
    expect(screen.getByTestId('gg-broker-tile-HHH').textContent).toContain(TAG());
  });

  it('12. NO REMOUNT: the header appearing / disappearing (the card toggle re-read) keeps the SAME card node', async () => {
    stub((n) => (n === 1 ? POT.potential : k1()));
    await mount();
    const before = screen.getByTestId('gg-tile-HHH');
    expect(screen.queryByTestId('gg-broker-section')).toBeNull();
    fireEvent.click(screen.getByTestId('gg-broker-toggle-HHH'));
    await waitFor(() => expect(screen.queryByTestId('gg-broker-section')).not.toBeNull());
    expect(brokers().map((c) => c.method)).toEqual(['POST']);
    expect(gets()).toHaveLength(2);
    expect(screen.getByTestId('gg-tile-HHH')).toBe(before);
    cleanup();

    stub((n) => (n === 1 ? k1() : POT.potential));
    await mount();
    const again = screen.getByTestId('gg-tile-HHH');
    expect(screen.getByTestId('gg-broker-section')).toBeTruthy();
    fireEvent.click(screen.getByTestId('gg-broker-toggle-HHH'));
    await waitFor(() => expect(screen.queryByTestId('gg-broker-section')).toBeNull());
    expect(brokers().map((c) => c.method)).toEqual(['DELETE']);
    expect(gets()).toHaveLength(2);
    expect(screen.getByTestId('gg-tile-HHH')).toBe(again);
  });

  it('13. source guards: no broker name in GajjalaBoard.tsx; the pinned map literal survives inside the splice; no sub in the derivations; the header CSS rule; NEGATIVES fail the same matchers', async () => {
    const cssSrc = await readSource('src/styles/gajjala.css');
    const name = String(BLOCK().broker || '');
    expect(name.length).toBeGreaterThan(0);
    expect(boardSrc.toLowerCase()).not.toContain(name.toLowerCase());
    expect(boardSrc).toContain('liveTiles.map((t) => {');
    expect(boardSrc).toContain('ggSectionSplice(liveTiles.map((t) => {');
    expect(boardSrc).not.toMatch(/liveTiles\.flatMap\(/);

    const oneGate = (src: string) => src.includes('parseGgBrokerSection(brokerBlock?.section)')
      && !src.split('\n').filter((l) => /\b(brokerSec|secAt|secOn)\b\s*=/.test(l) || /parseGgBrokerSection\(/.test(l))
        .some((l) => /activeSub/.test(l));
    expect(oneGate(boardSrc)).toBe(true);
    const rev1 = "  const brokerSec = useMemo(() => (activeSub === 'potential' ? parseGgBrokerSection(brokerBlock?.section) : null), [brokerBlock, activeSub]);";
    expect(oneGate(rev1)).toBe(false);

    const cssOk = (css: string) => {
      const m = css.match(/\.ggw-section\.gg-broker-section\s*\{([^}]*)\}/);
      return !!m && /grid-column:\s*1\s*\/\s*-1/.test(m[1]) && /min-width:\s*0/.test(m[1]) && /overflow-wrap:\s*anywhere/.test(m[1]);
    };
    expect(cssOk(cssSrc)).toBe(true);
    expect(cssSrc).toMatch(/\.cm-grid > \.gg-card\[hidden\]\s*\{\s*display:\s*none;\s*\}/);
    expect(cssOk(cssSrc.replace(/\.ggw-section\.gg-broker-section\s*\{[^}]*\}/, ''))).toBe(false);
    expect(cssOk('.ggw-section.gg-broker-section { grid-column: 1 / -1; }')).toBe(false);
  });
});
