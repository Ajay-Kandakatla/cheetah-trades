import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import onOpen from './__fixtures__/gajjala_on_open_golden_2026_10_15.json';
import potGolden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';
import trGolden from './__fixtures__/gajjala_track_record_golden_2026_10_16.json';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import type { CurrentUser } from '../hooks/useUser';

/* 🎪 Promo names on Gajjala's scan (2026-10-29, BUILD_SPEC32 D4).
 *
 * Ajay: "should we pull stocks from PROMO circuit by default every day ... I do wanna run them against Gajjalas
 * strategies". The day's Promo-circuit names join the scan; every surface that names a symbol prints the SERVED
 * `promo_text` as a muted chip right after the 📌 chip, through the SAME component (GgTraderChip) — one mount per surface.
 *
 * FIXTURES ARE SYNTHETIC: in-file clones of the goldens (the trader chip test's pattern) with `promo_text` set on one row
 * per surface. PROMO below is test data typed from the spec's served shape (promo_names text: "🎪 promo · first tag
 * HH:MM ET · @handle"), never a word the board types. Pinned: the chip prints the served text verbatim (tiles, 🎯, 🧠
 * strip, 📈 Track, 🏁 rows, 🌙 recap, 👀 watch), after the 📌 chip when a row carries both; NEGATIVES: absent / null /
 * "" / whitespace / a non-string → no chip; the `promo` bool alone prints nothing (the words are served, never typed);
 * the board's code types no 🎪 and no promo word; phone: the chip wraps (min-width 0, no px width, no nowrap). */

let userRet: CurrentUser | null = null;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: false }) }));
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
import { NEW_FEATURES } from '../lib/newFeatures';

const OPEN: Record<string, any> = (onOpen as any).boards;
const POT: Record<string, any> = (potGolden as any).boards;
const TR: Record<string, any> = (trGolden as any).boards;
const HAND: Record<string, any> = (hand as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

/* SYNTHETIC served values — test data only. */
const PROMO = '\u{1F3AA} promo · first tag 09:41 ET · @served_handle (S)';
const TAG = '\u{1F4CC} served_trader';

function stub(getBoard: () => any) {
  const spy = vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    if (u.pathname.endsWith('/chart-maps/gajjala/scan')) return { ok: false, status: 404, json: async () => ({ detail: 'Not Found' }) };
    if (u.pathname.includes('/chart-maps/gajjala/broker-flags')) return { ok: true, status: 200, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => clone(getBoard()) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const mount = (q = 'tab=gajjala&sub=bull_flag') =>
  render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /></MemoryRouter>);
const promoChips = (c: ParentNode) => c.querySelectorAll('.gg-promo');
const before = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const tsCode = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '').replace(/(^|\s)\/\/[^\n]*/g, '$1');

describe('GajjalaBoard — 🎪 the served promo chip on every surface', () => {
  beforeEach(() => { userRet = null; });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

  it('setup tile + 🎯 row: chip == the served promo_text, inside the tile chip row, before the 🚫 chip', async () => {
    const b = clone(OPEN.bull_flag);
    const sym = b.tiles[0].symbol;
    b.tiles[0].promo = true;
    b.tiles[0].promo_text = PROMO;
    b.tiles[0].broker_text = 'served broker tag';
    b.enterable.rows[0].promo_text = PROMO;
    stub(() => b);
    const { container } = mount();
    const chip = await screen.findByTestId(`gg-promo-tile-${sym}`);
    expect(chip.textContent).toBe(PROMO);
    expect(chip.classList.contains('cm-badge')).toBe(true);
    expect(within(screen.getByTestId(`gg-chips-${sym}`)).getByTestId(`gg-promo-tile-${sym}`)).toBe(chip);
    expect(before(chip, screen.getByTestId(`gg-broker-tile-${sym}`))).toBe(true);
    const r = b.enterable.rows[0];
    const id = `${r.symbol}-${r.setup}`;
    expect(screen.getByTestId(`gg-promo-aplus-${id}`).textContent).toBe(PROMO);
    expect(screen.getByTestId(`gg-aplus-row-${id}`).textContent).toBe(r.text);
    expect(promoChips(container).length).toBe(2);
    // NEGATIVE: a promo row with no trader text draws no 📌 chip
    expect(container.querySelectorAll('.gg-trader').length).toBe(0);
  });

  it('trader AND promo on one row: both chips, 📌 first then 🎪, each its own served text', async () => {
    const b = clone(OPEN.bull_flag);
    const sym = b.tiles[0].symbol;
    b.tiles[0].trader_text = TAG;
    b.tiles[0].promo = true;
    b.tiles[0].promo_text = PROMO;
    stub(() => b);
    mount();
    const p = await screen.findByTestId(`gg-promo-tile-${sym}`);
    const t = screen.getByTestId(`gg-trader-tile-${sym}`);
    expect(t.textContent).toBe(TAG);
    expect(p.textContent).toBe(PROMO);
    expect(t.classList.contains('gg-trader')).toBe(true);
    expect(p.classList.contains('gg-promo')).toBe(true);
    expect(t.classList.contains('gg-promo')).toBe(false);
    expect(before(t, p)).toBe(true);
  });

  it('🧠 strip row: chip after the row button, the row keeps its served line', async () => {
    const b = clone(POT.bull_flag);
    const r = b.potential.rows.find((x: any) => x.symbol === 'JJJ');
    r.promo_text = PROMO;
    stub(() => b);
    const { container } = mount();
    const chip = await screen.findByTestId(`gg-promo-pot-JJJ-${r.setup}`);
    expect(chip.textContent).toBe(PROMO);
    const row = screen.getByTestId('gg-potential-row-JJJ');
    expect(row.textContent).toBe(r.text + (r.tells || []).map((t: any) => t.text).join(''));
    expect(row.contains(chip)).toBe(false);
    expect(promoChips(container).length).toBe(1);
    expect(screen.queryByTestId('gg-promo-pot-AAA-bull_flag')).toBeNull();   // NEGATIVE the untagged row
  });

  it('📈 Track row + 👀 watch symbol: chips beside the link, the link text unchanged', async () => {
    const b = clone(POT.potential);
    const tr = b.track.today.rows[0];
    tr.promo_text = PROMO;
    b.watch.symbols[0].promo_text = PROMO;
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=potential');
    const id = `${tr.symbol}-${tr.setup}`;
    expect((await screen.findByTestId(`gg-promo-track-${id}`)).textContent).toBe(PROMO);
    expect(screen.getByTestId(`gg-track-row-${id}`).querySelector('a.gg-track-text')!.textContent).toBe(tr.text);
    const w = b.watch.symbols[0];
    expect(screen.getByTestId(`gg-promo-watch-${w.symbol}`).textContent).toBe(PROMO);
    expect(screen.getByTestId(`gg-watch-tk-${w.symbol}`).textContent).toBe(w.symbol);
    expect(screen.queryByTestId(`gg-promo-watch-${b.watch.symbols[1].symbol}`)).toBeNull();
    expect(promoChips(container).length).toBe(2);
  });

  it('🌙 recap row: chip after the row text', async () => {
    const b = clone(HAND.postmarket);
    const r = b.postmarket.recap.rows[0];
    r.promo_text = PROMO;
    stub(() => b);
    mount('tab=gajjala&sub=postmarket');
    const id = `${r.symbol}-${r.setup ?? ''}`;
    expect((await screen.findByTestId(`gg-promo-recap-${id}`)).textContent).toBe(PROMO);
    expect(screen.getByTestId(`gg-recap-row-${id}`).textContent).toBe(`${r.symbol} ${r.text}${PROMO}`);
  });

  it('🏁 Track record row: chip in the symbol cell beside the link; every other row none', async () => {
    const b = clone(TR['5d']);
    const rows = b.track_record.days.flatMap((d: any) => d.rows);
    const row = rows.find((x: any) => x.symbol === 'XLAB');
    row.promo = true;
    row.promo_text = PROMO;
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=track_record&span=5d');
    const chip = await screen.findByTestId(`gg-tr-promo-${row.key}`);
    expect(chip.textContent).toBe(PROMO);
    expect(screen.getByTestId(`gg-tr-row-${row.key}`).contains(chip)).toBe(true);
    expect(chip.closest('td')!.querySelector('a')!.textContent).toBe('XLAB');
    expect(promoChips(container).length).toBe(1);
  });
});

describe('GajjalaBoard — 🎪 NEGATIVES: nothing composed, nothing typed', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('NEGATIVE: an older API (the golden, no promo keys) prints no promo chip', async () => {
    stub(() => OPEN.bull_flag);
    const { container } = mount();
    await screen.findByTestId('gg-strip-text');
    await waitFor(() => expect(container.querySelector('.gg-board')!.getAttribute('data-state')).toBe('loaded'));
    expect(promoChips(container).length).toBe(0);
    expect(document.querySelectorAll('[data-testid^="gg-promo-"], [data-testid^="gg-tr-promo-"]').length).toBe(0);
  });

  for (const [name, v] of [['absent (the promo bool alone)', undefined], ['null', null], ['empty', ''], ['whitespace', '   '], ['a number', 7]] as const) {
    it(`NEGATIVE: ${name} promo_text → no chip on the tile or the 🎯 row`, async () => {
      const b = clone(OPEN.bull_flag);
      b.tiles[0].promo = true;                     // the bool never prints: the words are served or nothing
      b.enterable.rows[0].promo = true;
      if (v !== undefined) { b.tiles[0].promo_text = v; b.enterable.rows[0].promo_text = v; }
      stub(() => b);
      const { container } = mount();
      await screen.findByTestId(`gg-tile-${b.tiles[0].symbol}`);
      expect(promoChips(container).length).toBe(0);
      expect(document.querySelectorAll('[data-testid^="gg-promo-"]').length).toBe(0);
    });
  }

  it('NEGATIVE: GajjalaBoard.tsx types no 🎪 and no promo word in its code; the ONE chip has no JSX text of its own', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    const code = tsCode(src);
    expect(code).not.toContain('\u{1F3AA}');
    expect(code).not.toMatch(/\\u\{1F3AA\}|\\uD83C\\uDFAA/i);
    // only identifiers / class / testids carry "promo" — never a quoted word printed to him
    const lits = [...code.matchAll(/'([^'\n]*)'|"([^"\n]*)"/g)].map((m) => m[1] ?? m[2]);
    for (const s of lits) if (/promo/i.test(s)) expect(s).toBe('gg-promo');
    expect((src.match(/^function GgPromoChip\(/gm) || []).length).toBe(0);     // no twin copy
    // 2026-10-29: chip module — the board no longer defines the chip; it imports the ONE module and mounts it 7x.
    expect((src.match(/^function GgTraderChip\(/gm) || []).length).toBe(0);
    expect(src).toMatch(/^import \{ GgTraderChip \} from '\.\/GgTraderChip';$/m);
    expect((src.match(/<GgTraderChip /g) || []).length).toBe(7);
  });

  // 2026-10-29: chip module — the chip-body checks moved to GgTraderChip.tsx (where the body now lives), never loosened.
  it('NEGATIVE: GgTraderChip.tsx types no 🎪 and no promo word; the ONE chip has no JSX text of its own', async () => {
    const src = await readSource('src/components/GgTraderChip.tsx');
    const code = tsCode(src);
    expect(code).not.toContain('\u{1F3AA}');
    expect(code).not.toMatch(/\\u\{1F3AA\}|\\uD83C\\uDFAA/i);
    const lits = [...code.matchAll(/'([^'\n]*)'|"([^"\n]*)"/g)].map((m) => m[1] ?? m[2]);
    for (const s of lits) if (/promo/i.test(s)) expect(s).toBe('gg-promo');
    expect((src.match(/^function GgTraderChip\(/gm) || []).length).toBe(1);
    expect((src.match(/^function GgPromoChip\(/gm) || []).length).toBe(0);     // no twin copy
    expect(src).toMatch(/^export \{ GgTraderChip \};$/m);
    expect(src).toMatch(/servedChip\(promoText, 'gg-promo', promoTestid\)/);
    const a = src.indexOf('\nfunction GgTraderChip(');
    expect(a).toBeGreaterThan(-1);
    const body = tsCode(src.slice(a, src.indexOf('\n}\n', a + 1))).replace(/=>/g, '=');
    expect([...body.matchAll(/>([^<>{}\n]+)</g)].map((m) => m[1].trim()).filter(Boolean)).toEqual([]);
    expect(body).toContain('promoText');
  });

  it('NEGATIVE: GgTraderChip.tsx imports nothing from GajjalaBoard, PatternChart or gajjala.css (the chip module stays light)', async () => {
    const code = tsCode(await readSource('src/components/GgTraderChip.tsx'));
    const specs = [...code.matchAll(/(?:from|import)\s*\(?\s*'([^'\n]+)'/g)].map((m) => m[1]);
    expect(specs).toContain('../styles/ggTraderChip.css');
    for (const s of specs) expect(s).not.toMatch(/GajjalaBoard|PatternChart|gajjala\.css/);
  });

  it('NEGATIVE: lib/gajjala.ts types no 🎪 in code (types only)', async () => {
    const code = tsCode(await readSource('src/lib/gajjala.ts'));
    expect(code).not.toContain('\u{1F3AA}');
    expect(code).toMatch(/promo_text\?: string \| null/);
  });
});

/* 📱 430 px (the 2026-10-19 phone rule): .cm-badge is nowrap house-wide and the served promo words are long, so the
 * .gg-promo rule must let the chip wrap and never set its row's minimum width. jsdom has no layout: a SOURCE guard on
 * the stylesheet (GajjalaBoard.phone.test.tsx's pattern), with a NEGATIVE that the matcher rejects a nowrap rule. */
function promoRule(src: string): string | null {
  const m = src.match(/(^|\n)\s*\.gg-promo\s*\{([^}]*)\}/);
  return m ? m[2] : null;
}
const PRE_FIX_PROMO = '.gg-promo { white-space: nowrap; min-width: 18rem; }';

describe('📱 the 🎪 chip on the phone — wraps, never widens its row', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('the .gg-promo rule is white-space: normal, overflow-wrap: anywhere, min-width: 0, max-width: 100%', async () => {
    // 2026-10-29: chip module — the rule moved verbatim to the chip's own sheet; the fixed-width guard covers both sheets.
    const decl = promoRule(await readSource('src/styles/ggTraderChip.css'));
    expect(decl).not.toBeNull();
    expect(decl).toMatch(/white-space:\s*normal/);
    expect(decl).toMatch(/overflow-wrap:\s*anywhere/);
    expect(decl).toMatch(/(^|[;\s])min-width:\s*0\b/);
    expect(decl).toMatch(/max-width:\s*100%/);
    for (const sheet of ['src/styles/ggTraderChip.css', 'src/styles/gajjala.css']) {
      for (const m of (await readSource(sheet)).matchAll(/([^{}]*\.gg-promo\b[^{}]*)\{([^}]*)\}/g)) {
        expect(m[2]).not.toMatch(/(min-|max-)?width:\s*\d*\.?\d+(px|rem|em)/);
        expect(m[2]).not.toMatch(/white-space:\s*nowrap/);
      }
    }
  });

  it('NEGATIVE: a nowrap / fixed-width .gg-promo rule fails the same matcher', () => {
    const decl = promoRule(PRE_FIX_PROMO);
    expect(decl).not.toBeNull();
    expect(decl).not.toMatch(/white-space:\s*normal/);
    expect(decl).not.toMatch(/(^|[;\s])min-width:\s*0\b/);
  });

  it('the rendered chip carries no inline style (the stylesheet decides)', async () => {
    const b = clone(OPEN.bull_flag);
    b.tiles[0].promo_text = PROMO;
    stub(() => b);
    mount();
    const chip = await screen.findByTestId(`gg-promo-tile-${b.tiles[0].symbol}`);
    expect(chip.getAttribute('style')).toBeNull();
    expect(chip.classList.contains('gg-promo')).toBe(true);
  });
});

/* ✨ FIRST (BUILD_SPEC32 D5): his words verbatim, spelling kept; routed to /chart-maps; the caveats on the label. */
const HIS = "Also I see a some of stocks we see are also in Gajjalas page. Don't see some should we pull stocks from PROMO circuit by default every day they are having some good catched but I do wanna run them against Gajjalas strategies";

describe('✨ the 🎪 entry is NEW_FEATURES[0]', () => {
  it('first, dated 2026-10-29, routed /chart-maps, his words verbatim, INVERTED + UNMEASURED on the label', () => {
    const f = NEW_FEATURES[0];
    expect(f.id).toBe('chart-maps-gajjala-promo-names-2026-10-29');
    expect(f.addedAt).toBe('2026-10-29');
    expect(f.route).toBe('/chart-maps');
    expect(f.label).toContain(`"${HIS}"`);
    expect(f.label).toContain('INVERTED');
    expect(f.label).toContain('UNMEASURED');
    expect(f.label).not.toMatch(/bounc/i);
  });

  it('NEGATIVE: the entry is not duplicated, and the 📈 tape entry is now second', () => {
    expect(NEW_FEATURES.filter((x) => x.id === 'chart-maps-gajjala-promo-names-2026-10-29').length).toBe(1);
    expect(NEW_FEATURES[1].id).toBe('chart-maps-gajjala-track-record-tape-2026-10-29');
  });
});

/* ℹ️ the counts legend (tab.count_legend, backend LEGEND_KEYS — the ONE source): a served 🎪 row prints in served order
 * after the 📌 row, its word and text verbatim. The rows are SENTINELS; the FE types no definition. */
describe('ℹ️ the served 🎪 legend row', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
  const row = (key: string) => ({ key, word: `served word ${key}`, text: `served text for ${key}` });

  it('a served promo row prints verbatim, after the trader row, in served order', async () => {
    const b = clone(OPEN.bull_flag);
    b.counts_legend = [row('aplus'), row('listed'), row('trader'), row('promo')];
    stub(() => b);
    mount();
    const li = await screen.findByTestId('gg-legend-promo');
    expect(li.textContent).toBe('served word promo — served text for promo');
    expect(before(screen.getByTestId('gg-legend-trader'), li)).toBe(true);
    const keys = [...screen.getByTestId('gg-counts-legend').querySelectorAll('li')].map((e) => e.getAttribute('data-testid'));
    expect(keys).toEqual(['gg-legend-aplus', 'gg-legend-listed', 'gg-legend-trader', 'gg-legend-promo']);
  });

  it('NEGATIVE: no served promo row → no promo legend line (nothing typed in its place)', async () => {
    const b = clone(OPEN.bull_flag);
    b.counts_legend = [row('aplus'), row('trader')];
    stub(() => b);
    mount();
    await screen.findByTestId('gg-legend-trader');
    expect(screen.queryByTestId('gg-legend-promo')).toBeNull();
  });
});
