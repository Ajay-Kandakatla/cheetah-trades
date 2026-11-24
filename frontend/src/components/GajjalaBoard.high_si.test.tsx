import '../test/ggCardWatchOff';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import { GG_DIVERGENCE_SUB, GG_DIVERGING_SUB, GG_HIGH_SI_SUB, GG_SUBS, GG_TABLE_SUB } from '../lib/gajjala';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetRegShoCache } from '../hooks/useRegSho';
import { _resetBorrowCache } from '../hooks/useBorrow';

/* 🩳 the High SI sub on 🚩 Gajjala's 5-min board (2026-11-23, high SI spec §3.8 / §4 WP fe-sub). Ajay: "Can you create a tab
 * similarly like Divergent with high charging tested, SHO tag, and low floats similar to what we've done in Divergent tab
 * under Gazilla?" [voice typing: "high charging tested" = high short interest, "Gazilla" = Gajjala] · "New tab like
 * divergence*". `?sub=high_si` → the served panel ABOVE the served cards; the cards are the house cards (the 🩳 chip, the 🔒
 * chip, the 💸 chip, the 🚫 chip when served, ➕ Watch); the bar-size toggle STAYS (the cross reads both frames); 🩳 right
 * after 🌱 in the strip, GG5 only. Information only, never an entry. UNMEASURED. Every word is a SENTINEL ("served …").
 * NEGATIVES: the fallback strips of the 1-min / 🧪 / 🥇 pages omit 🩳; the panel never draws on 🌱 / 🧨 / 🚩 Bull Flag; a
 * criteria row with ok null draws neither ✓ nor ✗; an older API → no panel, no crash; a null block → the served fault line
 * only; the toggle still hidden on 🌱 / 🧨; phone: the panel wraps (no fixed width, no nowrap). */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', async (importOriginal) => {
  const m: any = await importOriginal();
  return { ...m, PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> };
});
vi.mock('./GgWatchButton', () => ({ GgWatchButton: ({ symbol }: { symbol: string }) => <span data-testid={`ggw-${symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const HAND: Record<string, any> = (hand as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const BLOCK = {
  title: 'served hs title', ask_text: 'served his words', rule_label: 'served rule label', rule_text: 'served rule text',
  honesty: 'served honesty', cohort_text: 'served cohort', counts_text: 'served counts', adds_text: 'served adds',
  asof_text: 'served as of', sho_text: 'served sho', push_text: 'served push off sentence', order_note: 'served order',
  shown_text: null, excluded_text: 'served excluded', disagree_text: 'served disagree', no_tier_text: 'served no tier',
  n: 2, n_read: 102, faults_text: null, empty_text: 'served empty', chartless: [],
};
const CRITERIA = [
  { key: 'si_tier', label: 'served si label', ok: true, value: 'served si value', need: 'served si need' },
  { key: 'float', label: 'served float label', ok: true, value: 'served float value', need: 'served float need' },
  { key: 'cross_5m', label: 'served 5m cross label', ok: false, value: 'served 5m cross value', need: '' },
  { key: 'cross_15m', label: 'served 15m cross label', ok: null, value: 'served 15m cross value', need: '' },
  { key: 'k11_volume', label: 'served K11 label', ok: null, value: 'served judged at the ring', need: 'served floor' },
];
const HS_CHIP = { key: GG_HIGH_SI_SUB, emoji: '\u{1FA73}', label: 'High SI', count: 2, title: null };
const DG_CHIP = { key: GG_DIVERGING_SUB, emoji: '\u{1F331}', label: 'Diverging', count: 1, title: null };
const DV_CHIP = { key: GG_DIVERGENCE_SUB, emoji: '\u{1F9E8}', label: 'Divergence', count: 0, title: null };

/** The served 14-chip strip: 📋 first, 🧨 after 🎾, 🌱 after 🧨, 🩳 after 🌱, 🧠 / 🏁 last. */
function strip(b: any): any[] {
  const subs = b.subs.map((s: any) => ({ ...s, title: null }));
  const at = subs.findIndex((s: any) => s.key === 'reversal_squeeze') + 1;
  subs.splice(at, 0, DV_CHIP, DG_CHIP, HS_CHIP);
  return [{ key: GG_TABLE_SUB, emoji: '\u{1F4CB}', label: 'All strategies', count: 0, title: null }, ...subs,
    { key: 'potential', emoji: '\u{1F9E0}', label: 'Potential', count: 0, title: null },
    { key: 'track_record', emoji: '\u{1F3C1}', label: 'Track record', count: 0, title: null }];
}
/** A 🚩 5-min board on the 🩳 sub: two served 🩳 cards — the first barred, the second chartless (no bars yet). */
function hsBoard(over: Record<string, unknown> = {}): any {
  const b = clone(HAND.bull_flag);
  b.sub = GG_HIGH_SI_SUB;
  b.session = { ...b.session, refresh_sec: 0 };
  const mk = (t: any) => {
    t.lines = [];
    t.gajjala = { setup: GG_HIGH_SI_SUB, state: 'high_si', state_label: 'served hs card state', criteria: clone(CRITERIA),
      missed: [], unjudged: [], plan_text: null, chips: {}, listed: null,
      high_si: { tier: 'high', float_check: 'confirmed', si_chip: 'served si chip', carried: false, add_text: null } };
    return t;
  };
  const a = mk(clone(b.tiles[0]));
  const c = mk(clone(b.tiles[1]));
  c.bars = [];
  b.tiles = [a, c];
  b.empty_note = null;
  b.sorts = [];
  b.subs = strip(b);
  b.high_si = clone(BLOCK);
  return { ...b, ...over };
}
const A = () => hsBoard().tiles[0].symbol;
const C = () => hsBoard().tiles[1].symbol;
function subBoard(sub: string, over: Record<string, unknown> = {}): any {
  const b = clone(HAND.bull_flag);
  b.sub = sub;
  b.session = { ...b.session, refresh_sec: 0 };
  b.subs = strip(b);
  b.high_si = clone(BLOCK);   // NEGATIVE bait: a stray block on another sub must never draw
  return { ...b, ...over };
}

const SI_TITLE = '🩳 Short interest — served title.';
const siBlock = (sym: string) => ({ symbol: sym, status: 'ok', chip: `🩳 served si chip ${sym}`, title: SI_TITLE, rows: [], extreme: null });
const htb = (sym: string) => ({
  state: 'on', symbol: sym, market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: `served 🔒 chip ${sym}`, short: `served 🔒 short ${sym}`, label: `served 🔒 label ${sym}`, title: `served 🔒 title ${sym}`,
});
const listedBr = (sym: string) => ({
  state: 'listed', symbol: sym, name: `SERVED CO ${sym}`, chip: `💸 served chip ${sym}`, short: `💸 served short ${sym}`,
  label: `💸 served label ${sym}`, title: `served 💸 title ${sym}`, stale: false,
  fee_pct: 196.2308, rebate_pct: -192.3508, available: 100000, available_floor: false,
});

let boardFor: (sub: string | null) => any = () => hsBoard();
const fetchMock = vi.fn(async (url: string, _init?: RequestInit): Promise<any> => {
  const u = new URL(String(url), 'http://x');
  const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
  const syms = [A(), C()];
  if (u.pathname.endsWith('/short-interest/borrow')) {
    return ok({ kind: 'ibkr_borrow', status: 'ok', stale: false, items: Object.fromEntries(syms.map((s) => [s, listedBr(s)])),
      asked: 2, n: 2, max_symbols: 200, refreshing: false, retry_after_sec: null, keep_sec: 3600 });
  }
  if (u.pathname.endsWith('/short-interest/reg-sho')) {
    return ok({ kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items: Object.fromEntries(syms.map((s) => [s, htb(s)])),
      fault_text: null, refreshing: false, retry_after_sec: null });
  }
  if (u.pathname.endsWith('/short-interest/map')) {
    const q = (u.searchParams.get('symbols') || '').split(',');
    return ok({ items: Object.fromEntries(q.filter((s) => syms.includes(s)).map((s) => [s, siBlock(s)])), n: q.length, max_symbols: 200 });
  }
  if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) return ok(boardFor(u.searchParams.get('sub')));
  return ok({});
});
const gets = () => fetchMock.mock.calls.filter(([u]) => /\/chart-maps\/gajjala\?/.test(String(u)));

let lastSearch = '';
function Probe() { lastSearch = useLocation().search; return null; }
const mount = async (q: string) => {
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /><Probe /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
};
const subBtns = () => screen.getAllByRole('tab').filter((b) => b.getAttribute('data-testid')?.startsWith('gg-sub-'));

beforeEach(() => {
  _resetShortInterestCache();
  _resetRegShoCache();
  _resetBorrowCache();
  fetchMock.mockClear();
  boardFor = () => hsBoard();
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('EventSource', class { close() { /* no stream */ } addEventListener() { /* none */ } });
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); _resetBorrowCache(); _resetRegShoCache(); _resetShortInterestCache(); });

describe('🩳 the high_si sub on the board', () => {
  it('the served strip shows "🩳 High SI · n", right after 🌱, selected on the sub; the GET carries sub=high_si', async () => {
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    expect(gets()[0][0]).toContain(`sub=${GG_HIGH_SI_SUB}`);
    const ids = subBtns().map((b) => b.getAttribute('data-testid'));
    expect(ids).toHaveLength(GG_SUBS.length);
    expect(ids.indexOf(`gg-sub-${GG_HIGH_SI_SUB}`)).toBe(ids.indexOf(`gg-sub-${GG_DIVERGING_SUB}`) + 1);
    const chip = screen.getByTestId(`gg-sub-${GG_HIGH_SI_SUB}`);
    expect(chip).toHaveAttribute('aria-selected', 'true');
    expect(chip.textContent).toContain('\u{1FA73}');
    expect(chip.textContent).toContain('High SI');
    expect(chip.textContent).toContain('2');
  });

  it('the served panel ABOVE the cards; the cards are the house cards with their served criteria rows, no plan line', async () => {
    const { container } = await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    const panel = screen.getByTestId('gg-hs');
    const tile = screen.getByTestId(`gg-tile-${A()}`);
    expect(panel.compareDocumentPosition(tile) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(container.querySelector('.cm-grid')!.contains(tile)).toBe(true);
    expect(screen.getByTestId('gg-hs-title').textContent).toBe('served hs title');
    expect(screen.getByTestId('gg-hs-push').textContent).toBe('served push off sentence');
    expect(screen.getByTestId('gg-hs-honesty').textContent).toBe('served honesty');
    expect(within(tile).getByTestId(`chart-${A()}`)).toBeTruthy();
    expect(within(tile).getByTestId('gg-state').textContent).toBe('served hs card state');
    expect(within(tile).queryByTestId('gg-plan')).toBeNull();
    const lis = [...within(tile).getByTestId('gg-criteria').querySelectorAll('li')];
    expect(lis).toHaveLength(CRITERIA.length);
    CRITERIA.forEach((c, i) => {
      expect(lis[i].textContent).toContain(c.label);
      expect(lis[i].textContent).toContain(c.value);
    });
  });

  it('a criteria row with ok null draws neither ✓ nor ✗ (gg-unjudged); ok true ✓ (gg-ok); ok false ✗ (gg-miss)', async () => {
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    const lis = [...within(screen.getByTestId(`gg-tile-${A()}`)).getByTestId('gg-criteria').querySelectorAll('li')];
    expect(lis.map((li) => li.className)).toEqual(['gg-ok', 'gg-ok', 'gg-miss', 'gg-unjudged', 'gg-unjudged']);
    for (const li of [lis[3], lis[4]]) {
      expect(li.textContent).not.toMatch(/[✓✗✔✘]/);
      expect(li.textContent!.startsWith('· ')).toBe(true);
      expect(li.className).not.toMatch(/gg-ok|gg-miss/);
    }
    expect(lis[0].textContent).toMatch(/✓/);
    expect(lis[2].textContent).toMatch(/✗/);
  });

  it('a 🩳 card draws the 🩳 ShortInterestChip, the 🔒 chip and the 💸 chip; the chartless card draws ➕ Watch', async () => {
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    const head = screen.getByTestId(`gg-chips-${A()}`);
    expect((await within(head).findByTestId('si-chip')).textContent).toBe(`🩳 served si chip ${A()}`);
    expect((await within(head).findByTestId(`gg-htb-${A()}`)).textContent).toBe(`served 🔒 chip ${A()}`);
    expect((await within(head).findByTestId(`gg-brw-${A()}`)).textContent).toBe(`💸 served chip ${A()}`);
    // the 🎾 label path is not taken on a 🩳 card: the chips sit in the head row, no label
    expect(screen.queryByTestId(`gg-si-label-${A()}`)).toBeNull();
    expect(screen.queryByTestId(`gg-htb-label-${A()}`)).toBeNull();
    // ➕ Watch: the chartless card's head row (a barred card carries it in PatternChart's action row)
    expect(screen.getByTestId(`ggw-${C()}`).closest('.gg-row-head')).not.toBeNull();
    expect(screen.queryByTestId(`ggw-${A()}`)).toBeNull();
  });

  it('the 🚫 chip when served; NEGATIVE no broker_text → no 🚫 chip', async () => {
    boardFor = () => { const b = hsBoard(); b.tiles[0].broker_text = 'served 🚫 not eligible'; return b; };
    const r = await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    expect(screen.getByTestId(`gg-broker-tile-${A()}`).textContent).toContain('served 🚫 not eligible');
    expect(screen.queryByTestId(`gg-broker-tile-${C()}`)).toBeNull();
    r.unmount();
    boardFor = () => hsBoard();
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    expect(screen.queryByTestId(`gg-broker-tile-${A()}`)).toBeNull();
  });

  it('the bar-size toggle IS drawn on the 🩳 sub (5m and 15m); NEGATIVE still hidden on 🌱 and 🧨', async () => {
    const r = await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    expect(r.container.querySelector('[data-testid="gg-tf-5m"]')).toBeTruthy();
    expect(r.container.querySelector('[data-testid="gg-tf-15m"]')).toBeTruthy();
    r.unmount();
    for (const sub of [GG_DIVERGING_SUB, GG_DIVERGENCE_SUB]) {
      boardFor = () => subBoard(sub);
      const r2 = await mount(`tab=gajjala&sub=${sub}`);
      expect(r2.container.querySelector('[data-testid^="gg-tf-"]'), sub).toBeNull();
      r2.unmount();
    }
  });

  it('NEGATIVE: the panel draws on the 🩳 sub only — never on 🌱, 🧨 or 🚩 Bull Flag (even with a stray block served)', async () => {
    for (const sub of [GG_DIVERGING_SUB, GG_DIVERGENCE_SUB, 'bull_flag']) {
      boardFor = () => subBoard(sub);
      const r = await mount(`tab=gajjala&sub=${sub}`);
      expect(screen.queryByTestId('gg-hs'), sub).toBeNull();
      r.unmount();
    }
  });

  it('NEGATIVE: a high_si: null board (the read faulted) → the served empty_note only, no panel, no card', async () => {
    boardFor = () => hsBoard({ high_si: null, tiles: [], empty_note: 'served fault note' });
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    expect(screen.getByTestId('gg-empty').textContent).toBe('served fault note');
    expect(screen.queryByTestId('gg-hs')).toBeNull();
    expect(screen.queryByTestId(/^gg-tile-/)).toBeNull();
  });

  it('NEGATIVE: an older API that answers the sub with no `high_si` key → no panel, the cards still draw', async () => {
    boardFor = () => { const b = hsBoard(); delete b.high_si; return b; };
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    expect(screen.queryByTestId('gg-hs')).toBeNull();
    expect(screen.getByTestId(`gg-tile-${A()}`)).toBeTruthy();
  });

  it('NEGATIVE: an older API that answers bull_flag → the URL adopts the served sub, no panel, no crash', async () => {
    boardFor = () => { const b = clone(HAND.bull_flag); b.session = { ...b.session, refresh_sec: 0 }; return b; };
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    await waitFor(() => expect(lastSearch).toContain('sub=bull_flag'));
    expect(screen.queryByTestId('gg-hs')).toBeNull();
  });

  it('NEGATIVE: NaN / undefined fields in the served block print nothing on the board — never "NaN" / "undefined"', async () => {
    boardFor = () => hsBoard({ high_si: { ...clone(BLOCK), adds_text: NaN, disagree_text: undefined, no_tier_text: 7,
      counts_text: NaN, push_text: undefined } });
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    for (const t of ['gg-hs-adds', 'gg-hs-disagree', 'gg-hs-notier', 'gg-hs-counts', 'gg-hs-push']) expect(screen.queryByTestId(t), t).toBeNull();
    expect(screen.getByTestId('gg-hs').textContent).not.toMatch(/NaN|undefined/);
  });

  it('every string in the panel is a served sentinel (nothing typed by the FE)', async () => {
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    let text = screen.getByTestId('gg-hs').textContent || '';
    const served = Object.values(BLOCK).filter((v): v is string => typeof v === 'string' && v !== BLOCK.empty_text)
      .sort((a, b) => b.length - a.length);
    for (const s of served) text = text.split(s).join('');
    expect(text.trim()).toBe('');
    expect(screen.getByTestId('gg-hs').textContent).not.toMatch(/bounc/i);
  });

  it('phone: the panel root is the wrapping gg-dv class — no inline width, no nowrap anywhere in it', async () => {
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    const panel = screen.getByTestId('gg-hs');
    expect(panel.className).toBe('gg-dv');
    for (const el of [panel, ...panel.querySelectorAll('*')]) {
      expect((el as HTMLElement).getAttribute('style') || '', el.tagName).not.toMatch(/width|nowrap/i);
    }
    const css = await readSource('src/styles/gajjala.css');
    const rule = /\n\.gg-dv \{([^}]*)\}/.exec(css)!;
    expect(rule[1]).toMatch(/min-width: 0/);
    expect(rule[1]).toMatch(/overflow-wrap: anywhere/);
    expect(rule[1]).not.toMatch(/nowrap/);
  });
});

describe('🩳 the pre-board fallback strip (GG5 only)', () => {
  const never = () => new Promise<any>(() => { /* the first board never lands */ });
  it("🚩 Gajjala's before its first board: GG_SUBS.length chips, 🩳 right after 🌱", () => {
    fetchMock.mockImplementation(never);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala']}><GajjalaBoard /></MemoryRouter>);
    const ids = subBtns().map((b) => b.getAttribute('data-testid'));
    expect(ids).toHaveLength(GG_SUBS.length);
    expect(ids[0]).toBe(`gg-sub-${GG_TABLE_SUB}`);
    expect(ids.indexOf(`gg-sub-${GG_HIGH_SI_SUB}`)).toBe(ids.indexOf(`gg-sub-${GG_DIVERGING_SUB}`) + 1);
  });

  it('NEGATIVE: the 1-minute page omits 🩳 (and 🌱 / 🧨) and keeps 📋 first', () => {
    fetchMock.mockImplementation(never);
    render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_1m']}><GajjalaBoard variant="gajjala_1m" /></MemoryRouter>);
    const ids = subBtns().map((b) => b.getAttribute('data-testid'));
    expect(ids[0]).toBe(`gg-sub-${GG_TABLE_SUB}`);
    expect(ids).not.toContain(`gg-sub-${GG_HIGH_SI_SUB}`);
    expect(ids).toEqual(GG_SUBS.filter((s) => s.key !== GG_DIVERGENCE_SUB && s.key !== GG_DIVERGING_SUB && s.key !== GG_HIGH_SI_SUB)
      .map((s) => `gg-sub-${s.key}`));
  });

  for (const v of ['gajjala_audited', 'luk'] as const) {
    it(`NEGATIVE: the ${v} page omits 🩳, 🌱, 🧨 and 📋; the rest in GG_SUBS order`, () => {
      fetchMock.mockImplementation(never);
      render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala']}><GajjalaBoard variant={v} /></MemoryRouter>);
      const ids = subBtns().map((b) => b.getAttribute('data-testid'));
      expect(ids).not.toContain(`gg-sub-${GG_HIGH_SI_SUB}`);
      expect(ids).toEqual(GG_SUBS.filter((s) => s.key !== GG_TABLE_SUB && s.key !== GG_DIVERGENCE_SUB && s.key !== GG_DIVERGING_SUB
        && s.key !== GG_HIGH_SI_SUB).map((s) => `gg-sub-${s.key}`));
    });
  }
});

describe('🩳 source guards', () => {
  it('the board keeps the pinned 📋 / 🧨 clauses and the 🌱 filter byte-for-byte and chains ONE 🩳 GG5-only filter after them', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    expect(src).toContain("GG_SUBS.filter((s) => (vkey === 'gajjala' || vkey === 'gajjala_1m' || s.key !== GG_TABLE_SUB)");
    expect(src).toContain("&& (vkey === 'gajjala' || s.key !== GG_DIVERGENCE_SUB))");
    expect(src).toMatch(/\.filter\(\(s\) => vkey === 'gajjala' \|\| s\.key !== GG_DIVERGING_SUB\)[^\n]*\n\s*\.filter\(\(s\) => vkey === 'gajjala' \|\| s\.key !== GG_HIGH_SI_SUB\)/);
    expect((src.match(/s\.key !== GG_HIGH_SI_SUB/g) || []).length).toBe(1);
    expect(src).toMatch(/activeSub === GG_HIGH_SI_SUB \? <GgHighSiPanel block=\{board\.high_si \?\? null\} \/>/);
    expect((src.match(/<GgHighSiPanel /g) || []).length).toBe(1);
    // the 🧨 / 🌱 toggle line is unchanged — 🩳 is NOT added to it (the toggle stays on 🩳)
    expect(src).toMatch(/activeSub === GG_DIVERGING_SUB \? null : \(activeSub === GG_DIVERGENCE_SUB \? \[\] : tfs\)\.map/);
    expect(src).not.toMatch(/activeSub === GG_HIGH_SI_SUB \? (null|\[\])/);
  });

  it('the lib spells the sub ONCE as a value (GG_HIGH_SI_SUB); NEGATIVE no b-word in the new files', async () => {
    const lib = await readSource('src/lib/gajjala.ts');
    const code = lib.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
    expect((code.match(/'high_si'/g) || []).length).toBe(3);   // the GgSub member, the GG_SUBS row, GG_HIGH_SI_SUB
    expect(lib).toMatch(/^export const GG_HIGH_SI_SUB: GgSub = 'high_si';$/m);
    expect(await readSource('src/components/GgHighSi.tsx')).not.toMatch(/bounc/i);
    const board = await readSource('src/components/GajjalaBoard.tsx');
    expect(board).not.toMatch(/'high_si'/);
  });
});
