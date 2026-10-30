import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import onOpen from './__fixtures__/gajjala_on_open_golden_2026_10_15.json';
import potGolden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';
import trGolden from './__fixtures__/gajjala_track_record_golden_2026_10_16.json';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import type { CurrentUser } from '../hooks/useUser';

/* 📌 Trader tag on Gajjala's board (2026-10-27, BUILD_SPEC26 §3.4 / §4 WP-C).
 *
 * Ajay: "Add them to Gajjals, they are pretty good". The names a tracked trader flagged for this tab posted join the
 * scan as candidates, and every surface that names a symbol prints the SERVED `trader_text` as a muted chip just before
 * the 🚫 chip; the strip prints the SERVED `trader_text` / `trader_skip_text` lines after its own text.
 *
 * FIXTURES ARE SYNTHETIC: in-file clones of the goldens (the broker test's pattern, GajjalaBoard.broker.test.tsx) with
 * `trader_text` set on ONE row per surface. The tag and the two strip lines below are typed here from the spec's served
 * shapes (trader_names.text_for → f"{TRADER_TAG} {handle}", STRIP_TEXT, SKIP_HEAD + SKIP_TEXT) — they are test data,
 * not words the board types. What is pinned: the chip prints the served text verbatim on all 7 surfaces with the spec's
 * testids, before the 🚫 chip, served to every viewer (no owner block needed); the strip lines verbatim. NEGATIVES:
 * null / "" / whitespace / absent / a non-string → no chip and no strip line; the board's source types no trader name
 * and no 📌 in its code; the chip adds no fixed width (phone: it sits in the existing wrapping rows). */

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

const OPEN: Record<string, any> = (onOpen as any).boards;
const POT: Record<string, any> = (potGolden as any).boards;
const TR: Record<string, any> = (trGolden as any).boards;
const HAND: Record<string, any> = (hand as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

/* SYNTHETIC served values (spec §3.3 shapes) — test data only. */
const TAG = '\u{1F4CC} algo888';
const STRIP_LINE = "\u{1F4CC} 2 of algo888's posted names on this pass's list — your call 2026-10-27; GG's rules decide every read and every A+";
const SKIP_LINE = "\u{1F4CC} not on the list: NOPE — not in today's market snapshot (OTC, or no trade yet); "
  + 'TQQQ — not common stock or an ADR (your instrument rule)';
const BROKER = 'served broker tag';

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
const traderChips = (c: ParentNode) => c.querySelectorAll('.gg-trader');
/** The trader chip comes BEFORE the 🚫 chip in document order. */
const before = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const tsCode = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '').replace(/(^|\s)\/\/[^\n]*/g, '$1');

describe('GajjalaBoard — 📌 the served trader chip on every surface', () => {
  beforeEach(() => { userRet = null; });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

  it('setup tile + 🎯 row (on-open bull_flag clone): chip == the served tag, inside the tile chip row, before the 🚫 chip', async () => {
    const b = clone(OPEN.bull_flag);
    b.tiles[0].trader_text = TAG;
    b.tiles[0].broker_text = BROKER;
    b.enterable.rows[0].trader_text = TAG;
    stub(() => b);
    const { container } = mount();
    const sym = b.tiles[0].symbol;
    const tile = await screen.findByTestId(`gg-trader-tile-${sym}`);
    expect(tile.textContent).toBe(TAG);
    expect(within(screen.getByTestId(`gg-chips-${sym}`)).getByTestId(`gg-trader-tile-${sym}`)).toBe(tile);
    expect(before(tile, screen.getByTestId(`gg-broker-tile-${sym}`))).toBe(true);
    const r = b.enterable.rows[0];
    const id = `${r.symbol}-${r.setup}`;
    expect(screen.getByTestId(`gg-trader-aplus-${id}`).textContent).toBe(TAG);
    expect(screen.getByTestId(`gg-aplus-row-${id}`).textContent).toBe(r.text);
    expect(traderChips(container).length).toBe(2);
    // the prefix counters never see a trader element
    for (const sel of ['[data-testid^="gg-tile-"]', '[data-testid^="gg-aplus-row-"]']) {
      expect([...document.querySelectorAll(sel)].some((e) => /trader/.test(e.getAttribute('data-testid') || ''))).toBe(false);
    }
  });

  it('🧠 strip row (potential bull_flag clone): chip after the row button, the row keeps its served line + tells', async () => {
    const b = clone(POT.bull_flag);
    const r = b.potential.rows.find((x: any) => x.symbol === 'JJJ');
    r.trader_text = TAG;
    stub(() => b);
    const { container } = mount();
    const chip = await screen.findByTestId(`gg-trader-pot-JJJ-${r.setup}`);
    expect(chip.textContent).toBe(TAG);
    const row = screen.getByTestId('gg-potential-row-JJJ');
    expect(row.textContent).toBe(r.text + (r.tells || []).map((t: any) => t.text).join(''));
    expect(row.contains(chip)).toBe(false);
    expect(traderChips(container).length).toBe(1);
    expect(screen.queryByTestId('gg-trader-pot-AAA-bull_flag')).toBeNull();   // NEGATIVE the untagged row
  });

  it('📈 Track row + 👀 watch symbol (🧠 sub clone): chips beside the link, the link text unchanged', async () => {
    const b = clone(POT.potential);
    const tr = b.track.today.rows[0];
    tr.trader_text = TAG;
    b.watch.symbols[0].trader_text = TAG;
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=potential');
    const id = `${tr.symbol}-${tr.setup}`;
    const chip = await screen.findByTestId(`gg-trader-track-${id}`);
    expect(chip.textContent).toBe(TAG);
    expect(screen.getByTestId(`gg-track-row-${id}`).querySelector('a.gg-track-text')!.textContent).toBe(tr.text);
    const w = b.watch.symbols[0];
    expect(screen.getByTestId(`gg-trader-watch-${w.symbol}`).textContent).toBe(TAG);
    expect(screen.getByTestId(`gg-watch-tk-${w.symbol}`).textContent).toBe(w.symbol);
    expect(screen.queryByTestId(`gg-trader-watch-${b.watch.symbols[1].symbol}`)).toBeNull();
    expect(traderChips(container).length).toBe(2);
  });

  it('🌙 recap row (post-market clone): chip after the row text, the row text unchanged', async () => {
    const b = clone(HAND.postmarket);
    const r = b.postmarket.recap.rows[0];
    r.trader_text = TAG;
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=postmarket');
    const id = `${r.symbol}-${r.setup ?? ''}`;
    const chip = await screen.findByTestId(`gg-trader-recap-${id}`);
    expect(chip.textContent).toBe(TAG);
    expect(screen.getByTestId(`gg-recap-row-${id}`).textContent).toBe(`${r.symbol} ${r.text}${TAG}`);
    expect(traderChips(container).length).toBe(1);
  });

  it('🏁 Track record row (track-record golden clone): chip in the symbol cell beside the link', async () => {
    const b = clone(TR['5d']);
    const rows = b.track_record.days.flatMap((d: any) => d.rows);
    const row = rows.find((x: any) => x.symbol === 'XLAB');
    row.trader_text = TAG;
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=track_record&span=5d');
    const chip = await screen.findByTestId(`gg-tr-trader-${row.key}`);
    expect(chip.textContent).toBe(TAG);
    expect(screen.getByTestId(`gg-tr-row-${row.key}`).contains(chip)).toBe(true);
    expect(chip.closest('td')!.querySelector('a')!.textContent).toBe('XLAB');
    expect(traderChips(container).length).toBe(1);                // NEGATIVE every other row: no chip
  });

  it('served to every viewer: a non-owner payload (broker_flags null) still prints the trader chip', async () => {
    const b = clone(OPEN.bull_flag);
    b.broker_flags = null;
    b.tiles[0].trader_text = TAG;
    stub(() => b);
    const { container } = mount();
    expect((await screen.findByTestId(`gg-trader-tile-${b.tiles[0].symbol}`)).textContent).toBe(TAG);
    expect(container.querySelectorAll('.gg-broker').length).toBe(0);
  });
});

describe('GajjalaBoard — 📌 the strip lines', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('prints strip.trader_text and strip.trader_skip_text verbatim, after the strip text', async () => {
    const b = clone(OPEN.bull_flag);
    b.strip = { ...b.strip, trader_text: STRIP_LINE, trader_skip_text: SKIP_LINE };
    stub(() => b);
    mount();
    const line = await screen.findByTestId('gg-strip-trader');
    expect(line.textContent).toBe(STRIP_LINE);
    const skip = screen.getByTestId('gg-strip-trader-skip');
    expect(skip.textContent).toBe(SKIP_LINE);
    const text = screen.getByTestId('gg-strip-text');
    expect(text.textContent).toBe(b.strip.text);
    expect(before(text, line)).toBe(true);
    expect(before(line, skip)).toBe(true);
    expect(within(screen.getByTestId('gg-strip')).getByTestId('gg-strip-trader')).toBe(line);
  });

  for (const [name, v] of [['null', null], ['empty', ''], ['whitespace', '   '], ['a number', 5]] as const) {
    it(`NEGATIVE: a ${name} strip line prints nothing`, async () => {
      const b = clone(OPEN.bull_flag);
      b.strip = { ...b.strip, trader_text: v, trader_skip_text: v };
      stub(() => b);
      mount();
      await screen.findByTestId('gg-strip-text');
      expect(screen.queryByTestId('gg-strip-trader')).toBeNull();
      expect(screen.queryByTestId('gg-strip-trader-skip')).toBeNull();
    });
  }

  it('NEGATIVE: an older API (the golden, no trader keys) prints no strip line and no chip', async () => {
    stub(() => OPEN.bull_flag);
    const { container } = mount();
    await screen.findByTestId('gg-strip-text');
    await waitFor(() => expect(container.querySelector('.gg-board')!.getAttribute('data-state')).toBe('loaded'));
    expect(screen.queryByTestId('gg-strip-trader')).toBeNull();
    expect(screen.queryByTestId('gg-strip-trader-skip')).toBeNull();
    expect(traderChips(container).length).toBe(0);
  });
});

describe('GajjalaBoard — 📌 NEGATIVES: nothing composed, nothing typed', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('NEGATIVE: null / "" / whitespace / a non-string / absent trader_text → no chip on any surface', async () => {
    const b = clone(OPEN.bull_flag);
    b.tiles[0].trader_text = null;
    b.enterable.rows[0].trader_text = '';
    stub(() => b);
    const { container } = mount();
    await screen.findByTestId(`gg-tile-${b.tiles[0].symbol}`);
    expect(traderChips(container).length).toBe(0);

    cleanup();
    const p = clone(POT.potential);
    p.track.today.rows[0].trader_text = '   ';
    p.watch.symbols[0].trader_text = 7;
    stub(() => p);
    const m2 = mount('tab=gajjala&sub=potential');
    await screen.findByTestId('gg-watch');
    expect(traderChips(m2.container).length).toBe(0);
    expect(document.querySelectorAll('[data-testid^="gg-trader-"], [data-testid^="gg-tr-trader-"]').length).toBe(0);
  });

  it('NEGATIVE: GajjalaBoard.tsx types no trader name anywhere and no 📌 in its code (JSX text included)', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    expect(src.toLowerCase()).not.toContain('algo888');
    const code = tsCode(src);
    expect(code).not.toContain('\u{1F4CC}');
    expect(code).not.toMatch(/\\u\{1F4CC\}|\\uD83D\\uDCCC/i);
    // 2026-10-29: chip module — the chip body moved to GgTraderChip.tsx; the same checks read it there (never loosened).
    expect(src).toMatch(/^import \{ GgTraderChip \} from '\.\/GgTraderChip';$/m);
    const chip = await readSource('src/components/GgTraderChip.tsx');
    expect(chip.toLowerCase()).not.toContain('algo888');
    const chipCode = tsCode(chip);
    expect(chipCode).not.toContain('\u{1F4CC}');
    expect(chipCode).not.toMatch(/\\u\{1F4CC\}|\\uD83D\\uDCCC/i);
    // the chip prints only the served prop: its JSX has no text of its own
    const a = chip.indexOf('\nfunction GgTraderChip(');
    expect(a).toBeGreaterThan(-1);
    const body = tsCode(chip.slice(a, chip.indexOf('\n}\n', a + 1))).replace(/=>/g, '=');
    const texts = [...body.matchAll(/>([^<>{}\n]+)</g)].map((m) => m[1].trim()).filter(Boolean);
    expect(texts).toEqual([]);
  });

  it('NEGATIVE: lib/gajjala.ts types no trader name in code', async () => {
    const src = await readSource('src/lib/gajjala.ts');
    expect(src.toLowerCase()).not.toContain('algo888');
  });

  it('phone: the chip is a cm-badge with no inline style, and the stylesheet gives .gg-trader no fixed width or nowrap', async () => {
    const b = clone(OPEN.bull_flag);
    b.tiles[0].trader_text = TAG;
    stub(() => b);
    mount();
    const chip = await screen.findByTestId(`gg-trader-tile-${b.tiles[0].symbol}`);
    expect(chip.classList.contains('cm-badge')).toBe(true);
    expect(chip.getAttribute('style')).toBeNull();
    expect(chip.closest('.cm-tile-chips')).not.toBeNull();         // the existing wrapping row (gajjala.css chip-wrap rule)
    // 2026-10-29: chip module — widened to the chip's own sheet too.
    for (const sheet of ['src/styles/gajjala.css', 'src/styles/ggTraderChip.css']) {
      const css = await readSource(sheet);
      for (const m of css.matchAll(/([^{}]*\.gg-trader\b[^{}]*)\{([^}]*)\}/g)) {
        expect(m[2]).not.toMatch(/(^|[;\s])(min-)?width\s*:/);
        expect(m[2]).not.toMatch(/white-space:\s*nowrap/);
      }
    }
  });
});
