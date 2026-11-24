import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/* 🧹 ggFold store (2026-11-24, ggclean spec §3.1 / §4 fold-core). Ajay: "Hide all of this nouce besides the scan button
 * and log trade button no explantions on the landing pages anymor". Default CLOSED; '1' = open; junk / blocked storage =
 * closed; a blocked write still toggles for the visit; hooks on one key move together, another key does not; a null key
 * is no fold. [C1] ggFoldScanAnswer: the four served state keys only — 'refused' and anything else stay out.
 * NEGATIVES throughout. */

import {
  GG_FOLD_DEFAULT_OPEN, GG_FOLD_HEADER, GG_FOLD_LS, GG_FOLD_SCAN_ON_OPEN, GG_FOLD_SUB, ggFoldScanAnswer, ggFoldSubKey,
  readGgFold, resetGgFold, setGgFold, useGgFold, writeGgFold,
} from './ggFold';

type Store = Storage & { map: Map<string, string> };
function fakeStorage(opts: { getThrows?: boolean; setThrows?: boolean } = {}): Store {
  const map = new Map<string, string>();
  return {
    map,
    get length() { return map.size; },
    clear: () => map.clear(),
    key: (i: number) => [...map.keys()][i] ?? null,
    getItem: vi.fn((k: string) => { if (opts.getThrows) throw new Error('blocked'); return map.has(k) ? map.get(k)! : null; }),
    setItem: vi.fn((k: string, v: string) => { if (opts.setThrows) throw new Error('quota'); map.set(k, String(v)); }),
    removeItem: (k: string) => { map.delete(k); },
  } as Store;
}

let ls: Store;
beforeEach(() => {
  ls = fakeStorage();
  vi.stubGlobal('localStorage', ls);
  resetGgFold();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); resetGgFold(); });

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('constants', () => {
  it('keys, default CLOSED, sub key helper', () => {
    expect(GG_FOLD_LS).toBe('gg-fold:');
    expect(GG_FOLD_HEADER).toBe('header');
    expect(GG_FOLD_SUB).toBe('sub:');
    expect(GG_FOLD_DEFAULT_OPEN).toBe(false);
    expect(ggFoldSubKey('high_si')).toBe('sub:high_si');
  });
  it('NEGATIVE: ggFoldSubKey of null / undefined / "" / a non-string → null', () => {
    for (const v of [null, undefined, '', 3 as any, {} as any]) expect(ggFoldSubKey(v)).toBeNull();
  });
});

describe('readGgFold / writeGgFold', () => {
  it('empty storage → closed; stored "1" → open', () => {
    expect(readGgFold('header')).toBe(false);
    ls.map.set('gg-fold:header', '1');
    expect(readGgFold('header')).toBe(true);
  });
  it('NEGATIVE: "0", "true", "open", "", junk → closed', () => {
    for (const v of ['0', 'true', 'open', '', 'junk', ' 1', '1 ']) {
      ls.map.set('gg-fold:header', v);
      expect(readGgFold('header'), JSON.stringify(v)).toBe(false);
    }
  });
  it('writes "1" / "0" under gg-fold:<key>', () => {
    writeGgFold('sub:bull_flag', true);
    expect(ls.map.get('gg-fold:sub:bull_flag')).toBe('1');
    writeGgFold('sub:bull_flag', false);
    expect(ls.map.get('gg-fold:sub:bull_flag')).toBe('0');
  });
  it('NEGATIVE: getItem throws → closed, no throw', () => {
    vi.stubGlobal('localStorage', fakeStorage({ getThrows: true }));
    expect(() => readGgFold('header')).not.toThrow();
    expect(readGgFold('header')).toBe(false);
  });
  it('NEGATIVE: setItem throws → no throw', () => {
    vi.stubGlobal('localStorage', fakeStorage({ setThrows: true }));
    expect(() => writeGgFold('header', true)).not.toThrow();
  });
  it('NEGATIVE: no localStorage at all → closed, no throw', () => {
    vi.stubGlobal('localStorage', undefined);
    expect(readGgFold('header')).toBe(false);
    expect(() => writeGgFold('header', true)).not.toThrow();
  });
});

describe('useGgFold', () => {
  it('default closed; toggle writes "1" then "0"; a remount (fresh page) reads it back', () => {
    const a = renderHook(() => useGgFold('header'));
    expect(a.result.current).toMatchObject({ on: true, open: false });
    act(() => a.result.current.toggle());
    expect(a.result.current.open).toBe(true);
    expect(ls.map.get('gg-fold:header')).toBe('1');
    a.unmount();
    resetGgFold();                                   // a new page: the cache is gone, storage stays
    const b = renderHook(() => useGgFold('header'));
    expect(b.result.current.open).toBe(true);
    act(() => b.result.current.toggle());
    expect(b.result.current.open).toBe(false);
    expect(ls.map.get('gg-fold:header')).toBe('0');
    b.unmount();
    resetGgFold();
    expect(renderHook(() => useGgFold('header')).result.current.open).toBe(false);
  });
  it('reads storage once per key per page (cache)', () => {
    renderHook(() => useGgFold('header'));
    renderHook(() => useGgFold('header'));
    const calls = (ls.getItem as any).mock.calls.filter((c: string[]) => c[0] === 'gg-fold:header');
    expect(calls).toHaveLength(1);
  });
  it('two hooks on one key move together; NEGATIVE another key does not move', () => {
    const a = renderHook(() => useGgFold('sub:high_si'));
    const b = renderHook(() => useGgFold('sub:high_si'));
    const c = renderHook(() => useGgFold('sub:bull_flag'));
    act(() => a.result.current.toggle());
    expect(a.result.current.open).toBe(true);
    expect(b.result.current.open).toBe(true);
    expect(c.result.current.open).toBe(false);
    expect(ls.map.has('gg-fold:sub:bull_flag')).toBe(false);
  });
  it('setGgFold moves every subscriber', () => {
    const a = renderHook(() => useGgFold('header'));
    act(() => setGgFold('header', true));
    expect(a.result.current.open).toBe(true);
  });
  it('NEGATIVE: getItem throws → closed and the hook renders', () => {
    vi.stubGlobal('localStorage', fakeStorage({ getThrows: true }));
    const a = renderHook(() => useGgFold('header'));
    expect(a.result.current.open).toBe(false);
  });
  it('NEGATIVE: setItem throws → still toggles for the visit, no throw', () => {
    vi.stubGlobal('localStorage', fakeStorage({ setThrows: true }));
    const a = renderHook(() => useGgFold('header'));
    expect(() => act(() => a.result.current.toggle())).not.toThrow();
    expect(a.result.current.open).toBe(true);
    act(() => a.result.current.toggle());
    expect(a.result.current.open).toBe(false);
  });
  it('null key: on false, open true, toggle writes nothing', () => {
    const a = renderHook(() => useGgFold(null));
    expect(a.result.current).toMatchObject({ on: false, open: true });
    act(() => a.result.current.toggle());
    expect(a.result.current.open).toBe(true);
    expect(ls.setItem).not.toHaveBeenCalled();
    expect(ls.map.size).toBe(0);
  });
});

describe('[C1] ggFoldScanAnswer — the answers to the scan on open that fold', () => {
  it('the four served state keys → true', () => {
    expect([...GG_FOLD_SCAN_ON_OPEN]).toEqual(['started', 'waiting', 'reused', 'closed']);
    for (const s of ['started', 'waiting', 'reused', 'closed']) expect(ggFoldScanAnswer(s), s).toBe(true);
  });
  it('NEGATIVE: refused, error, "", case variants and non-strings → false', () => {
    for (const s of ['refused', 'error', '', 'Reused', 'CLOSED', ' started', null, undefined, 3, {}, [], ['reused'], true]) {
      expect(ggFoldScanAnswer(s), JSON.stringify(s)).toBe(false);
    }
  });
});

describe('source guards — ggFold.ts', () => {
  const code = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
  const literals = (s: string) => [...code(s).matchAll(/'([^'\\]*)'|"([^"\\]*)"/g)].map((m) => m[1] ?? m[2]);
  /* storage keys + flag values, the four served state keys, and the `typeof … === 'string'` operand — nothing else */
  const ALLOWED = new Set(['gg-fold:', 'header', 'sub:', '1', '0', 'started', 'waiting', 'reused', 'closed', 'string', 'react']);
  it('carries storage keys and the four served state keys only', async () => {
    const src = await readSource('src/lib/ggFold.ts');
    for (const l of literals(src)) expect(ALLOWED.has(l), l).toBe(true);
    expect(code(src)).not.toMatch(/`[^`$]*[A-Za-z]{3,}[^`]*`/);   // no template literal carrying words
  });
  it('NEGATIVE: the guard fires on a typed word or a fifth state', () => {
    expect(literals("const x = 'market closed';").every((l) => ALLOWED.has(l))).toBe(false);
    expect(literals("const s = ['refused'];").every((l) => ALLOWED.has(l))).toBe(false);
    expect(literals("/* 'refused' */ const y = 1;").every((l) => ALLOWED.has(l))).toBe(true);
  });
  it('no b-word, no email, no storage event listener', async () => {
    const src = await readSource('src/lib/ggFold.ts');
    expect(src).not.toMatch(/bounc/i);
    expect(src).not.toMatch(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/);
    expect(code(src)).not.toMatch(/addEventListener/);
  });
});
