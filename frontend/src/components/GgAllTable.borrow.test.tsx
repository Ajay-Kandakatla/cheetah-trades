/* 💸 Borrow read in the 📋 All strategies table (2026-11-22, spec borrow §3.4 / §4 fe part B).
 *
 * The served `short` form sits INSIDE the 🩳 `si` cell, after the served si_text and the 🔒 short chip. An absent name
 * prints exactly what the server serves for the short form — nothing when it serves null [C1]. NEGATIVES: a table served
 * WITHOUT an `si` head makes ZERO borrow fetches; GgAllTable.tsx mounts exactly one 💸 chip, in the si cell (source guard). */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgAllTable } from './GgAllTable';
import { resetGgwList } from '../lib/ggWatchList';
import { _resetRegShoCache } from '../hooks/useRegSho';
import { _resetBorrowCache } from '../hooks/useBorrow';

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}

const LOCK = {
  state: 'on', symbol: 'AKAN', market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: 'served 🔒 chip AKAN', short: 'served 🔒 short AKAN', label: 'served 🔒 label AKAN', title: 'served 🔒 title AKAN',
};
const RS = { kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items: { AKAN: LOCK }, fault_text: null,
             refreshing: false, retry_after_sec: null };
const DBGI = {
  state: 'listed', symbol: 'DBGI', name: 'SERVED CO', chip: '💸 served chip DBGI', short: '💸 served short DBGI',
  label: '💸 served label DBGI', title: 'served 💸 title DBGI', stale: false, fee_pct: 196.2308, available: 100000,
};
const AKAN = { ...DBGI, symbol: 'AKAN', chip: '💸 served chip AKAN', short: '💸 served short AKAN', title: 'served 💸 title AKAN' };
const ABS = (sym: string, over: Record<string, unknown> = {}) => ({
  state: 'absent', symbol: sym, name: null, chip: null, short: null, label: `💸 served absent label ${sym}`,
  title: `served absent title ${sym}`, stale: false, fee_pct: null, available: null, ...over,
});
const br = (items: Record<string, unknown>) => ({
  kind: 'ibkr_borrow', status: 'ok', stale: false, items, asked: 3, n: Object.keys(items).length, max_symbols: 200,
  refreshing: false, retry_after_sec: null, keep_sec: 3600,
});

const HEADS = [
  { key: 'rank', label: 'served #' }, { key: 'symbol', label: 'served Ticker' }, { key: 'float', label: 'served Float' },
  { key: 'si', label: 'served SI head' },
];
const HEADS_OLD = HEADS.filter((h) => h.key !== 'si');
const row = (rank: number, sym: string, over: Record<string, unknown> = {}) => ({
  rank, near_rank: rank, tier: 1, symbol: sym, setup: 'reversal_squeeze', float_text: `served float ${sym}`, in_watch: true,
  si_text: `served si ${sym}`, si_title: `served si title ${sym}`, si_stale: false, si_asof: '2026-10-30', ...over,
});
const block = (rows: any[], heads = HEADS) => ({
  title: 'served title', heads, order_text: 'served order', rows, fault_text: null, si_head_title: 'served head', si_fault_text: null,
});
const mount = (b: any) => render(<MemoryRouter><GgAllTable block={b} search="" back="/" /></MemoryRouter>);
const siCell = (sym: string) => screen.getByTestId(`gg-all-si-${sym}-reversal_squeeze`);

let calls: string[] = [];
let BR: unknown = br({ DBGI, AKAN });
function stub() {
  calls = [];
  const f = vi.fn(async (u: string) => {
    calls.push(String(u));
    const path = new URL(String(u), 'http://x').pathname;
    if (path.endsWith('/short-interest/reg-sho')) return { ok: true, json: async () => JSON.parse(JSON.stringify(RS)) };
    if (path.endsWith('/short-interest/borrow')) return { ok: true, json: async () => JSON.parse(JSON.stringify(BR)) };
    return { ok: true, json: async () => ({ state: 'owner_only', reason: 'r', title: 't' }) };
  });
  vi.stubGlobal('fetch', f);
  return f;
}
const brCalls = () => calls.filter((u) => new URL(u, 'http://x').pathname.endsWith('/short-interest/borrow'));

beforeEach(() => {
  vi.stubGlobal('localStorage', memStorage()); resetGgwList(); _resetRegShoCache(); _resetBorrowCache();
  BR = br({ DBGI, AKAN });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetRegShoCache(); _resetBorrowCache(); });

describe('💸 the short chip inside the si cell', () => {
  it('si_text, then the 🔒 short chip, then the 💸 short chip in the same cell; ONE borrow GET for the table', async () => {
    stub();
    mount(block([row(1, 'AKAN'), row(2, 'DBGI'), row(3, 'ZZZ')]));
    const chip = await screen.findByTestId('gg-all-brw-AKAN-reversal_squeeze');
    const lock = await screen.findByTestId('gg-all-htb-AKAN-reversal_squeeze');
    expect(siCell('AKAN').contains(chip)).toBe(true);
    expect(lock.nextElementSibling).toBe(chip);
    expect(chip.textContent).toBe(AKAN.short);
    expect(chip.getAttribute('title')).toBe(AKAN.title);
    expect(chip.className).toBe('cm-badge gg-brw');
    expect(siCell('AKAN').firstChild!.textContent).toBe('served si AKAN');
    expect(siCell('AKAN').textContent).toBe(`served si AKAN${LOCK.short}${AKAN.short}`);
    const d = await screen.findByTestId('gg-all-brw-DBGI-reversal_squeeze');
    expect(d.textContent).toBe(DBGI.short);
    expect(siCell('DBGI').textContent).toBe(`served si DBGI${DBGI.short}`);
    expect(brCalls()).toHaveLength(1);
    expect((new URL(brCalls()[0], 'http://x').searchParams.get('symbols') || '').split(',').sort()).toEqual(['AKAN', 'DBGI', 'ZZZ']);
    /* NEGATIVE: the long card chip never prints in the table */
    expect(siCell('AKAN').textContent).not.toContain(AKAN.chip);
  });

  it('[C1] an absent name served WITH a short → that short in the cell', async () => {
    BR = br({ DBGI: ABS('DBGI', { short: '💸 served absent short DBGI' }) });
    stub();
    mount(block([row(1, 'DBGI')]));
    const c = await screen.findByTestId('gg-all-brw-DBGI-reversal_squeeze');
    expect(c.textContent).toBe('💸 served absent short DBGI');
    expect(c.getAttribute('data-brw-state')).toBe('absent');
    expect(siCell('DBGI').textContent).toBe('served si DBGI💸 served absent short DBGI');
  });

  it('a listed row with NO SI text still shows the short chip', async () => {
    stub();
    mount(block([row(1, 'DBGI', { si_text: null, si_title: null, si_stale: null, si_asof: null })]));
    const chip = await screen.findByTestId('gg-all-brw-DBGI-reversal_squeeze');
    expect(siCell('DBGI').textContent).toBe(DBGI.short);
    expect(chip.textContent).toBe(DBGI.short);
  });
});

describe('💸 table — NEGATIVES', () => {
  it('an absent name served label-only → the cell innerHTML is the served si text only', async () => {
    BR = br({ DBGI, ZZZ: ABS('ZZZ') });
    stub();
    mount(block([row(1, 'DBGI'), row(2, 'ZZZ')]));
    await screen.findByTestId('gg-all-brw-DBGI-reversal_squeeze');
    expect(siCell('ZZZ').innerHTML).toBe('served si ZZZ');
    expect(screen.queryByTestId('gg-all-brw-ZZZ-reversal_squeeze')).toBeNull();
  });

  it('a name the payload does not serve, and DBGIW beside a served DBGI → the cell is the served si text only', async () => {
    stub();
    mount(block([row(1, 'DBGI'), row(2, 'QQQX'), row(3, 'DBGIW')]));
    await screen.findByTestId('gg-all-brw-DBGI-reversal_squeeze');
    for (const s of ['QQQX', 'DBGIW']) expect(siCell(s).innerHTML, s).toBe(`served si ${s}`);
  });

  it('a failed GET → no chip, the cell is the served si text only', async () => {
    const f = vi.fn(async () => { throw new Error('down'); });
    vi.stubGlobal('fetch', f);
    mount(block([row(1, 'DBGI')]));
    await waitFor(() => expect(f).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 10));
    expect(siCell('DBGI').innerHTML).toBe('served si DBGI');
  });

  it('a table with NO si head → zero borrow GETs (control: the si head makes one)', async () => {
    stub();
    mount(block([row(1, 'DBGI'), row(2, 'AKAN')], HEADS_OLD));
    await new Promise((r) => setTimeout(r, 20));
    expect(brCalls()).toHaveLength(0);
    expect(document.querySelector('.gg-brw')).toBeNull();
    cleanup();
    _resetBorrowCache();
    stub();
    mount(block([row(1, 'DBGI')]));
    await screen.findByTestId('gg-all-brw-DBGI-reversal_squeeze');
    expect(brCalls()).toHaveLength(1);
  });
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('💸 source guard — GgAllTable.tsx', () => {
  it('ONE 💸 chip, short form, directly after the 🔒 chip line; the 🔒 lines byte-for-byte unchanged; no hook call', async () => {
    const src = await readSource('src/components/GgAllTable.tsx');
    const lines = src.split('\n').map((l) => l.trim());
    const pairs: Array<[string, string]> = [
      ["import { GgHardToBorrowChip } from './GgHardToBorrow';", "import { GgBorrowChip } from './GgBorrow';"],
      ['<GgHardToBorrowChip symbol={row.symbol} testid={`gg-all-htb-${rid(row)}`} form="short" />',
        '<GgBorrowChip symbol={row.symbol} testid={`gg-all-brw-${rid(row)}`} form="short" />'],
    ];
    for (const [lock, brw] of pairs) {
      const i = lines.indexOf(lock);
      expect(i, lock).toBeGreaterThan(-1);
      expect(lines[i + 1], brw).toBe(brw);
    }
    expect(src.match(/<GgBorrowChip /g) || []).toHaveLength(1);
    expect(src).not.toMatch(/GgBorrowLabel|useBorrow/);
  });
});
