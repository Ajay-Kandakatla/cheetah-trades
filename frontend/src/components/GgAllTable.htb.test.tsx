/* 🔒 Hard to borrow tag in the 📋 All strategies table (2026-11-22, spec htb §3.4 M5 / §4 fe).
 *
 * The served `short` form sits INSIDE the 🩳 `si` cell, after the served si_text; a listed row with no SI text still
 * shows it. NEGATIVES: a name not on the list → the cell is byte-identical to today's; a table served WITHOUT an `si`
 * head makes ZERO fetches [C5]; GgAllTable.tsx mounts no fault line and never calls the payload hook (source guard). */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgAllTable } from './GgAllTable';
import { resetGgwList } from '../lib/ggWatchList';
import { _resetRegShoCache } from '../hooks/useRegSho';

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}

const AKAN = {
  state: 'on', symbol: 'AKAN', market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: '🔒 Hard to borrow · threshold security · 11/20', short: '🔒 Hard to borrow · 11/20',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20', title: 'served title AKAN',
};
const OPTT = { ...AKAN, symbol: 'OPTT', market: 'nyse_american', exchange: 'NYSE American', short: 'served short OPTT', title: 't OPTT' };
const RS = { kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items: { AKAN, OPTT }, fault_text: 'served fault',
             refreshing: false, retry_after_sec: null };

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
function stub(body: unknown = RS) {
  calls = [];
  const f = vi.fn(async (u: string) => {
    calls.push(String(u));
    if (String(u).endsWith('/short-interest/reg-sho')) return { ok: true, json: async () => JSON.parse(JSON.stringify(body)) };
    return { ok: true, json: async () => ({ state: 'owner_only', reason: 'r', title: 't' }) };
  });
  vi.stubGlobal('fetch', f);
  return f;
}
const htbCalls = () => calls.filter((u) => u.endsWith('/short-interest/reg-sho'));

beforeEach(() => { vi.stubGlobal('localStorage', memStorage()); resetGgwList(); _resetRegShoCache(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetRegShoCache(); });

describe('M5 — the short chip inside the si cell', () => {
  it('a listed row: the served si_text, then the served short chip in the same cell; ONE GET for the table', async () => {
    stub();
    mount(block([row(1, 'AKAN'), row(2, 'OPTT'), row(3, 'ZZZ')]));
    const chip = await screen.findByTestId('gg-all-htb-AKAN-reversal_squeeze');
    expect(siCell('AKAN').contains(chip)).toBe(true);
    expect(chip.textContent).toBe(AKAN.short);
    expect(chip.getAttribute('title')).toBe(AKAN.title);
    expect(chip.className).toBe('cm-badge gg-htb');
    expect(siCell('AKAN').firstChild!.textContent).toBe('served si AKAN');
    expect(siCell('AKAN').textContent).toBe(`served si AKAN${AKAN.short}`);
    expect(screen.getByTestId('gg-all-htb-OPTT-reversal_squeeze').textContent).toBe('served short OPTT');
    expect(htbCalls()).toHaveLength(1);
    /* NEGATIVE: the long card chip never prints in the table */
    expect(siCell('AKAN').textContent).not.toContain(AKAN.chip);
  });

  it('a listed row with NO SI text still shows the tag', async () => {
    stub();
    mount(block([row(1, 'AKAN', { si_text: null, si_title: null, si_stale: null, si_asof: null })]));
    const chip = await screen.findByTestId('gg-all-htb-AKAN-reversal_squeeze');
    expect(siCell('AKAN').textContent).toBe(AKAN.short);
    expect(chip.textContent).toBe(AKAN.short);
  });

  it('NEGATIVE: a name not on the list → the cell is exactly today\'s (served si_text only, no node, no space)', async () => {
    stub();
    mount(block([row(1, 'AKAN'), row(2, 'ZZZ'), row(3, 'AKANW')]));
    await screen.findByTestId('gg-all-htb-AKAN-reversal_squeeze');
    for (const s of ['ZZZ', 'AKANW']) {
      expect(siCell(s).innerHTML, s).toBe(`served si ${s}`);
      expect(screen.queryByTestId(`gg-all-htb-${s}-reversal_squeeze`)).toBeNull();
    }
  });

  it('NEGATIVE: the fault line is never drawn inside the table component (it lives in GajjalaBoard)', async () => {
    stub();
    const { container } = mount(block([row(1, 'AKAN')]));
    await screen.findByTestId('gg-all-htb-AKAN-reversal_squeeze');
    expect(container.querySelector('.gg-htb-fault')).toBeNull();
    expect(screen.queryByTestId('gg-htb-fault')).toBeNull();
  });

  it('NEGATIVE: a failed GET → no chip, the cell is today\'s', async () => {
    const f = vi.fn(async () => { throw new Error('down'); });
    vi.stubGlobal('fetch', f);
    mount(block([row(1, 'AKAN')]));
    await waitFor(() => expect(f).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 10));
    expect(siCell('AKAN').innerHTML).toBe('served si AKAN');
  });

  it('[C5] NEGATIVE: a table with NO si head and a spy fetch → zero reg-sho calls (control: the si head makes one)', async () => {
    stub();
    mount(block([row(1, 'AKAN'), row(2, 'OPTT')], HEADS_OLD));
    await new Promise((r) => setTimeout(r, 20));
    expect(htbCalls()).toHaveLength(0);
    expect(document.querySelector('.gg-htb')).toBeNull();
    cleanup();
    _resetRegShoCache();
    stub();
    mount(block([row(1, 'AKAN')]));
    await screen.findByTestId('gg-all-htb-AKAN-reversal_squeeze');
    expect(htbCalls()).toHaveLength(1);
  });
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('[C5] source guard — GgAllTable.tsx', () => {
  it('mounts the chip in the si cell only: no GgHardToBorrowFault, no useRegShoPayload, no useRegSho', async () => {
    const src = await readSource('src/components/GgAllTable.tsx');
    expect(src).not.toContain('GgHardToBorrowFault');
    expect(src).not.toContain('useRegShoPayload');
    expect(src).not.toMatch(/\buseRegSho\b/);
    expect(src.match(/<GgHardToBorrowChip /g) || []).toHaveLength(1);
    expect(src).toContain("form=\"short\"");
  });
});
