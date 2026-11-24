/* ⛔ SSR tag in the 👀 Watch tile head (2026-11-23, spec ssr §3.10 / §4 W4).
 *
 * Ajay 2026-11-23: "No shorting at the bid (SEC short-sale restriction)
 * Can we check or this for other stocks too?"
 *
 * Behind the SAME `siNote` prop as the 🩳 EXTREME note and the 🔒 short chip (the Watch passes it; the 🚩 / 🧪 grid tile
 * and GgCardView do not): the served `short` form as a ggw-chip, right after the 🔒 slot, compact and non-compact, and in
 * the ⤢ view. NEGATIVES: no siNote → no ggw-ssr-* node and no ssr GET; off / unknown (no short served) / failed GET →
 * the head is byte-identical. Every word in these fixtures is a stand-in for a served one. */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import { GgwStretch, Tile } from './GajjalaWatchTile';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetRegShoCache } from '../hooks/useRegSho';
import { _resetSsrCache } from '../hooks/useSsr';
import { parseGgw, type GgwBoard, type GgwRow } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const B = parseGgw(clone(autoFixture)) as GgwBoard;
const ROW: GgwRow = B.rows.find((r) => r.symbol === 'OMH')!;

const htb = (sym: string) => ({
  state: 'on', symbol: sym, market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: `served long 🔒 chip ${sym}`, short: `served 🔒 short ${sym}`, label: `served 🔒 label ${sym}`, title: `served 🔒 title ${sym}`,
});
const on = (sym: string, over: Record<string, unknown> = {}) => ({
  state: 'on', symbol: sym, chip: `served long ⛔ chip ${sym}`, short: `⛔ served short ${sym}`, label: `served ⛔ label ${sym}`,
  title: `served ⛔ title ${sym}`, ...over,
});
const ssr = (items: Record<string, unknown>) => ({ kind: 'ssr_rule_201', status: 'ok', items, states: {}, whys: {}, max_symbols: 200,
  fault_text: 'served fault (never on a tile)', refreshing: false, retry_after_sec: null, keep_sec: 300 });
const X = { text: '🩳 SI EXTREME 36.4% float · 1.0d · 10/30', short: '🩳 SI EXTREME 36.4% float', title: 'served x title', basis: 'si_doc_float' };
let SSR: unknown = null;
let mode: 'ok' | 'throw' = 'ok';
let ssrCalls = 0;
function stub() {
  ssrCalls = 0;
  vi.stubGlobal('fetch', vi.fn(async (u: string) => {
    const url = String(u);
    if (url.includes('/short-interest/ssr')) {
      ssrCalls += 1;
      if (mode === 'throw') throw new Error('down');
      return { ok: true, json: async () => clone(SSR) } as unknown as Response;
    }
    if (url.endsWith('/short-interest/reg-sho')) {
      return { ok: true, json: async () => ({ kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items: { OMH: htb('OMH') },
        fault_text: null, refreshing: false, retry_after_sec: null }) } as unknown as Response;
    }
    if (url.includes('/short-interest/map')) {
      return { ok: true, json: async () => ({ items: { OMH: { symbol: 'OMH', status: 'ok', chip: 'c', title: 't', rows: [], extreme: X } }, n: 1, max_symbols: 200 }) } as unknown as Response;
    }
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
}

function mount(row: GgwRow, extra: Record<string, unknown> = {}) {
  return render(
    <Tile row={row} phone={false} fit={false} removeLabel="served-remove" focused={false} busy={false}
          onRemove={() => {}} onStretch={() => {}} {...extra} />,
    { wrapper: MemoryRouter },
  ).container;
}
const settle = () => waitFor(() => expect(ssrCalls).toBeGreaterThan(0)).then(() => new Promise((r) => setTimeout(r, 120)));

beforeEach(() => {
  _resetShortInterestCache();
  _resetRegShoCache();
  _resetSsrCache();
  SSR = ssr({ OMH: on('OMH') });
  mode = 'ok';
  vi.stubGlobal('matchMedia', (m: string) => ({ matches: false, media: m, addEventListener: () => {}, removeEventListener: () => {} }));
  stub();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetSsrCache(); _resetRegShoCache(); _resetShortInterestCache(); });

describe('the ⛔ short chip in the Watch tile head', () => {
  for (const compact of [false, true]) {
    it(`siNote${compact ? ' + compact' : ''}: the served short form, ggw-chip gg-ssr, right after the 🔒 chip, inside the head`, async () => {
      const c = mount(ROW, { siNote: true, compact });
      const chip = await screen.findByTestId('ggw-ssr-OMH');
      expect(chip.textContent).toBe(on('OMH').short);
      expect(chip.getAttribute('title')).toBe(on('OMH').title);
      expect(chip.className).toBe('ggw-chip gg-ssr');
      expect(chip.getAttribute('data-ssr-state')).toBe('on');
      expect(chip.closest('.ggw-tile-head')).toBe(c.querySelector('.ggw-tile-head'));
      const lock = await screen.findByTestId('ggw-htb-OMH');
      expect(lock.nextElementSibling).toBe(chip);
      /* NEGATIVE: never the long card chip, never the label, never the fault line on a tile */
      expect(c.textContent).not.toContain(on('OMH').chip);
      expect(c.textContent).not.toContain(on('OMH').label);
      expect(c.querySelector('.gg-ssr-fault, .gg-ssr-label')).toBeNull();
    });
  }

  it('the ⤢ view (GgwStretch with siNote) shows the short chip in its head too', async () => {
    render(<MemoryRouter><GgwStretch row={ROW} phone={false} removeLabel={null} onClose={() => {}} onStep={null} siNote /></MemoryRouter>);
    const chip = await screen.findByTestId('ggw-ssr-OMH');
    expect(chip.textContent).toBe(on('OMH').short);
    expect(chip.closest('.ggw-tile-head')).not.toBeNull();
    expect(screen.getByTestId('ggw-stretch-tile-OMH').contains(chip)).toBe(true);
  });
});

describe('⛔ Watch — NEGATIVES', () => {
  it('no siNote (the 🚩 grid tile) → no ggw-ssr-* node and no ssr GET', async () => {
    const c = mount(ROW);
    await new Promise((r) => setTimeout(r, 50));
    expect(c.querySelector('[data-testid^="ggw-ssr-"]')).toBeNull();
    expect(c.querySelector('.gg-ssr')).toBeNull();
    expect(ssrCalls).toBe(0);
  });

  for (const [name, items] of [
    ['off (no item)', {}],
    ['unknown (label only, no short served)', { OMH: { state: 'unknown', symbol: 'OMH', chip: null, short: null, label: 'served unknown label', title: 'served t' } }],
    ['another name only', { OMHW: on('OMHW') }],
  ] as const) {
    it(`${name} → the head is byte-identical to a failed GET (no wrapper, no space)`, async () => {
      SSR = ssr(items as Record<string, unknown>);
      const a = mount(ROW, { siNote: true });
      await settle();
      await screen.findByTestId('ggw-htb-OMH');
      const head = a.querySelector('.ggw-tile-head')!.innerHTML;
      expect(a.querySelector('[data-testid^="ggw-ssr-"]')).toBeNull();
      cleanup();
      _resetSsrCache();
      _resetRegShoCache();
      _resetShortInterestCache();
      mode = 'throw';
      stub();
      const b = mount(ROW, { siNote: true });
      await settle();
      await screen.findByTestId('ggw-htb-OMH');
      expect(b.querySelector('.ggw-tile-head')!.innerHTML).toBe(head);
      expect(b.querySelector('[data-testid^="ggw-ssr-"]')).toBeNull();
    });
  }
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('source guard — GajjalaWatchTile.tsx', () => {
  it('the chip rides the siNote prop, short form, the line right after the 🔒 line; mounted once; no fault, no label', async () => {
    const src = await readSource('src/components/GajjalaWatchTile.tsx');
    const lines = src.split('\n').map((l) => l.trim());
    const h = '{siNote ? <GgHardToBorrowChip symbol={row.symbol} testid={`ggw-htb-${row.symbol}`} className="ggw-chip" form="short" /> : null}';
    const s = '{siNote ? <GgSsrChip symbol={row.symbol} testid={`ggw-ssr-${row.symbol}`} className="ggw-chip" form="short" /> : null}';
    expect(lines[lines.indexOf(h) + 1]).toBe(s);
    expect(lines[lines.indexOf("import { GgHardToBorrowChip } from './GgHardToBorrow';") + 1]).toBe("import { GgSsrChip } from './GgSsr';");
    expect(src.match(/<GgSsrChip /g) || []).toHaveLength(1);
    expect(src).not.toMatch(/GgSsrFault|GgSsrLabel|useSsr/);
  });
});
