/* 🔒 Hard to borrow tag in the 👀 Watch tile head (2026-11-22, spec htb §3.4 M4 / §4 fe).
 *
 * Behind the SAME `siNote` prop as the 🩳 EXTREME note (the Watch passes it; the 🚩 / 🧪 grid tile and GgCardView do
 * not): the served `short` form as a ggw-chip, right after the EXTREME slot, compact and non-compact, and in the ⤢ view.
 * NEGATIVES: no siNote → no ggw-htb-* node; not on the list / failed GET → the head is byte-identical. Every word in these
 * fixtures is a stand-in for a served one. */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import { GgwStretch, Tile } from './GajjalaWatchTile';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetRegShoCache } from '../hooks/useRegSho';
import { parseGgw, type GgwBoard, type GgwRow } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const B = parseGgw(clone(autoFixture)) as GgwBoard;
const ROW: GgwRow = B.rows.find((r) => r.symbol === 'OMH')!;

const item = (sym: string, over: Record<string, unknown> = {}) => ({
  state: 'on', symbol: sym, market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: `served long chip ${sym}`, short: `🔒 Hard to borrow · 11/20 ${sym}`, label: `served label ${sym}`, title: `served title ${sym}`,
  ...over,
});
const X = { text: '🩳 SI EXTREME 36.4% float · 1.0d · 10/30', short: '🩳 SI EXTREME 36.4% float', title: 'served x title', basis: 'si_doc_float' };
let RS: unknown = null;
let mode: 'ok' | 'throw' = 'ok';
let rsCalls = 0;
function stub() {
  rsCalls = 0;
  vi.stubGlobal('fetch', vi.fn(async (u: string) => {
    const url = String(u);
    if (url.endsWith('/short-interest/reg-sho')) {
      rsCalls += 1;
      if (mode === 'throw') throw new Error('down');
      return { ok: true, json: async () => clone(RS) } as unknown as Response;
    }
    if (url.includes('/short-interest/map')) {
      return { ok: true, json: async () => ({ items: { OMH: { symbol: 'OMH', status: 'ok', chip: 'c', title: 't', rows: [], extreme: X } }, n: 1, max_symbols: 200 }) } as unknown as Response;
    }
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
}
const rs = (items: Record<string, unknown>) => ({ kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items,
  fault_text: 'served fault (never on a tile)', refreshing: false, retry_after_sec: null });

function mount(row: GgwRow, extra: Record<string, unknown> = {}) {
  return render(
    <Tile row={row} phone={false} fit={false} removeLabel="served-remove" focused={false} busy={false}
          onRemove={() => {}} onStretch={() => {}} {...extra} />,
    { wrapper: MemoryRouter },
  ).container;
}
const settle = () => waitFor(() => expect(rsCalls).toBeGreaterThan(0)).then(() => new Promise((r) => setTimeout(r, 120)));

beforeEach(() => {
  _resetShortInterestCache();
  _resetRegShoCache();
  RS = rs({ OMH: item('OMH') });
  mode = 'ok';
  vi.stubGlobal('matchMedia', (m: string) => ({ matches: false, media: m, addEventListener: () => {}, removeEventListener: () => {} }));
  stub();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetRegShoCache(); _resetShortInterestCache(); });

describe('M4 — the short chip in the Watch tile head', () => {
  for (const compact of [false, true]) {
    it(`siNote${compact ? ' + compact' : ''}: the served short form, ggw-chip gg-htb, after the EXTREME slot, inside the head`, async () => {
      const c = mount(ROW, { siNote: true, compact });
      const chip = await screen.findByTestId('ggw-htb-OMH');
      expect(chip.textContent).toBe(item('OMH').short);
      expect(chip.getAttribute('title')).toBe(item('OMH').title);
      expect(chip.className).toBe('ggw-chip gg-htb');
      expect(chip.closest('.ggw-tile-head')).toBe(c.querySelector('.ggw-tile-head'));
      const x = await screen.findByTestId('ggw-si-extreme-OMH');
      expect(x.nextElementSibling).toBe(chip);
      /* NEGATIVE: never the long card chip, never the fault line on a tile */
      expect(c.textContent).not.toContain(item('OMH').chip);
      expect(c.querySelector('.gg-htb-fault')).toBeNull();
    });
  }

  it('the ⤢ view (GgwStretch with siNote) shows the short chip in its head too', async () => {
    render(<MemoryRouter><GgwStretch row={ROW} phone={false} removeLabel={null} onClose={() => {}} onStep={null} siNote /></MemoryRouter>);
    const chip = await screen.findByTestId('ggw-htb-OMH');
    expect(chip.textContent).toBe(item('OMH').short);
    expect(chip.closest('.ggw-tile-head')).not.toBeNull();
    expect(screen.getByTestId('ggw-stretch-tile-OMH').contains(chip)).toBe(true);
  });

  it('stale → gg-htb-stale with the served text', async () => {
    RS = rs({ OMH: item('OMH', { stale: true, short: '🔒 Hard to borrow · 11/17 · stale' }) });
    mount(ROW, { siNote: true });
    const chip = await screen.findByTestId('ggw-htb-OMH');
    expect(chip.className).toBe('ggw-chip gg-htb gg-htb-stale');
    expect(chip.textContent).toBe('🔒 Hard to borrow · 11/17 · stale');
  });
});

describe('M4 — NEGATIVES', () => {
  it('no siNote (the 🚩 grid tile) → no ggw-htb-* node and no reg-sho GET', async () => {
    const c = mount(ROW);
    await new Promise((r) => setTimeout(r, 50));
    expect(c.querySelector('[data-testid^="ggw-htb-"]')).toBeNull();
    expect(c.querySelector('.gg-htb')).toBeNull();
    expect(rsCalls).toBe(0);
  });

  it('not on the list → the head is byte-identical to a failed GET (no wrapper, no space)', async () => {
    RS = rs({ AKAN: item('AKAN') });
    const a = mount(ROW, { siNote: true });
    await settle();
    await screen.findByTestId('ggw-si-extreme-OMH');
    const head = a.querySelector('.ggw-tile-head')!.innerHTML;
    expect(a.querySelector('[data-testid^="ggw-htb-"]')).toBeNull();
    cleanup();
    _resetRegShoCache();
    _resetShortInterestCache();
    mode = 'throw';
    stub();
    const b = mount(ROW, { siNote: true });
    await settle();
    await screen.findByTestId('ggw-si-extreme-OMH');
    expect(b.querySelector('.ggw-tile-head')!.innerHTML).toBe(head);
    expect(b.querySelector('[data-testid^="ggw-htb-"]')).toBeNull();
  });

  it('exact match: OMHW listed does not tag OMH', async () => {
    RS = rs({ OMHW: item('OMHW') });
    const c = mount(ROW, { siNote: true });
    await settle();
    expect(c.querySelector('[data-testid^="ggw-htb-"]')).toBeNull();
  });
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('source guard — GajjalaWatchTile.tsx', () => {
  it('the chip rides the siNote prop, short form, right after the EXTREME note; the EXTREME line is unchanged', async () => {
    const src = await readSource('src/components/GajjalaWatchTile.tsx');
    const x = "{siNote ? <GgSiExtremeNote symbol={row.symbol} testid={`ggw-si-extreme-${row.symbol}`} /> : null}";
    const h = '{siNote ? <GgHardToBorrowChip symbol={row.symbol} testid={`ggw-htb-${row.symbol}`} className="ggw-chip" form="short" /> : null}';
    expect(src).toContain(x);
    expect(src).toContain(h);
    expect(src.indexOf(h)).toBeGreaterThan(src.indexOf(x));
    expect(src).not.toContain('GgHardToBorrowFault');
  });
});
