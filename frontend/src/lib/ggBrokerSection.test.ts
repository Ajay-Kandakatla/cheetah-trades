import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  GG_SECTION_COLLAPSED_LS, GG_SECTION_OPENED_LS, ggBrokerSectionStart, ggSectionFolded, ggSectionSplice, ggSectionToggle,
  parseGgBrokerSection, readGgSectionFold, saveGgSectionFold,
} from './ggBrokerSection';
import { GGW_COLLAPSED_KEY, GGW_OPENED_KEY } from './gajjalaWatch';
import libSrc from './ggBrokerSection.ts?raw';

/* 🚫 2026-11-25 (spec fidsec §3.2, fe-section test 14) — the pure lib under the 🧠 bottom section header.
 * Every word here is a CLONE marker ("served clone text"), never the served broker word. NEGATIVES throughout: junk
 * payloads parse to null, a non-tail section never starts, the splice returns the SAME array when it does nothing, the
 * desktop is never folded, a blocked store reads empty and never throws. */

const SEC = (over: Record<string, unknown> = {}) => ({
  key: 'broker', title: 'served clone title', text: 'served clone text · 2', hint: null, n: 2, symbols: ['CCC', 'HHH'], ...over,
});

function mem(seed: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(seed));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(),
    dump: () => Object.fromEntries(m),
  };
}
let store = mem();
beforeEach(() => { store = mem(); vi.stubGlobal('localStorage', store); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('ggBrokerSection — parse (the 👀 Watch parser, one engine)', () => {
  it('a served block parses to the Watch section shape, in served order', () => {
    expect(parseGgBrokerSection(SEC())).toEqual({
      key: 'broker', title: 'served clone title', text: 'served clone text · 2', hint: null, n: 2, symbols: ['CCC', 'HHH'],
    });
  });
  it('NEGATIVE junk / no words / no symbols / blank key → null', () => {
    for (const v of [undefined, null, 0, 'x', [], {}, SEC({ key: '' }), SEC({ key: 3 }), SEC({ text: '', title: '' }),
      SEC({ text: '  ', title: null }), SEC({ symbols: [] }), SEC({ symbols: 'HHH' }), SEC({ symbols: [1, null] })]) {
      expect(parseGgBrokerSection(v), JSON.stringify(v)).toBeNull();
    }
  });
  it('text falls back to the served title (the Watch rule)', () => {
    expect(parseGgBrokerSection(SEC({ text: null }))?.text).toBe('served clone title');
  });
  it('folded_default only when served === true; NEGATIVE "yes" / 1 / false leave it absent', () => {
    expect(parseGgBrokerSection(SEC({ folded_default: true }))?.folded_default).toBe(true);
    for (const v of ['yes', 1, false, null]) {
      const s = parseGgBrokerSection(SEC({ folded_default: v }))!;
      expect('folded_default' in s, String(v)).toBe(false);
    }
  });
});

describe('ggBrokerSection — start index + the tail guard', () => {
  const sec = parseGgBrokerSection(SEC())!;
  it('the first drawn card of the section when the listed cards are the tail', () => {
    expect(ggBrokerSectionStart(['EEE', 'DDD', 'CCC', 'HHH'], sec)).toBe(2);
    expect(ggBrokerSectionStart(['EEE', 'HHH'], sec)).toBe(1);        // one listed card not drawn: still the tail
    expect(ggBrokerSectionStart(['CCC', 'HHH'], sec)).toBe(0);
  });
  it('NEGATIVE not the tail / none drawn / no section → -1', () => {
    expect(ggBrokerSectionStart(['CCC', 'EEE', 'HHH'], sec)).toBe(-1);
    expect(ggBrokerSectionStart(['CCC', 'EEE'], sec)).toBe(-1);
    expect(ggBrokerSectionStart(['EEE', 'DDD'], sec)).toBe(-1);
    expect(ggBrokerSectionStart([], sec)).toBe(-1);
    expect(ggBrokerSectionStart(['CCC'], null)).toBe(-1);
  });
});

describe('ggBrokerSection — ggSectionSplice', () => {
  it('NEGATIVE null / undefined head, at -1, at past the end, a non-integer at → the SAME array', () => {
    const a = ['a', 'b', 'c'];
    expect(ggSectionSplice(a, 1, null)).toBe(a);
    expect(ggSectionSplice(a, 1, undefined)).toBe(a);
    expect(ggSectionSplice(a, -1, 'h')).toBe(a);
    expect(ggSectionSplice(a, 4, 'h')).toBe(a);
    expect(ggSectionSplice(a, 1.5, 'h')).toBe(a);
    expect(ggSectionSplice(a, NaN, 'h')).toBe(a);
  });
  it('head inserted BEFORE `at`, length + 1, order kept, input not mutated', () => {
    const a = ['a', 'b', 'c'];
    const out = ggSectionSplice(a, 2, 'h');
    expect(out).toEqual(['a', 'b', 'h', 'c']);
    expect(out).not.toBe(a);
    expect(a).toEqual(['a', 'b', 'c']);
    expect(ggSectionSplice(a, 0, 'h')).toEqual(['h', 'a', 'b', 'c']);
    expect(ggSectionSplice(a, 3, 'h')).toEqual(['a', 'b', 'c', 'h']);
  });
});

describe('ggBrokerSection — the phone fold (the Watch fold helpers, this board\'s own keys)', () => {
  const sec = parseGgBrokerSection(SEC())!;
  const dsec = parseGgBrokerSection(SEC({ folded_default: true }))!;
  it('own storage keys, never the Watch tab\'s', () => {
    expect(GG_SECTION_COLLAPSED_LS).not.toBe(GGW_COLLAPSED_KEY);
    expect(GG_SECTION_OPENED_LS).not.toBe(GGW_OPENED_KEY);
  });
  it('NEGATIVE junk storage → empty lists; a blocked store reads empty and saving never throws', () => {
    store = mem({ [GG_SECTION_COLLAPSED_LS]: '{nope', [GG_SECTION_OPENED_LS]: '[1, "has space", "ok"]' });
    vi.stubGlobal('localStorage', store);
    expect(readGgSectionFold()).toEqual({ collapsed: [], opened: ['ok'] });
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); },
      removeItem: () => { throw new Error('blocked'); },
    });
    expect(readGgSectionFold()).toEqual({ collapsed: [], opened: [] });
    expect(() => saveGgSectionFold({ collapsed: ['broker'], opened: [] })).not.toThrow();
  });
  it('save writes a JSON list; an empty list removes the key', () => {
    saveGgSectionFold({ collapsed: ['broker'], opened: [] });
    expect(store.dump()).toEqual({ [GG_SECTION_COLLAPSED_LS]: '["broker"]' });
    saveGgSectionFold({ collapsed: [], opened: ['broker'] });
    expect(store.dump()).toEqual({ [GG_SECTION_OPENED_LS]: '["broker"]' });
    saveGgSectionFold({ collapsed: [], opened: [] });
    expect(store.dump()).toEqual({});
  });
  it('NEGATIVE desktop is never folded, whatever the state or the served default', () => {
    expect(ggSectionFolded(sec, { collapsed: ['broker'], opened: [] }, false)).toBe(false);
    expect(ggSectionFolded(dsec, { collapsed: [], opened: [] }, false)).toBe(false);
    expect(ggSectionFolded(null, { collapsed: ['broker'], opened: [] }, true)).toBe(false);
  });
  it('phone: an ordinary section folds via `collapsed`; toggle both ways', () => {
    const st0 = { collapsed: [], opened: [] };
    expect(ggSectionFolded(sec, st0, true)).toBe(false);
    const st1 = ggSectionToggle(sec, st0);
    expect(st1).toEqual({ collapsed: ['broker'], opened: [] });
    expect(ggSectionFolded(sec, st1, true)).toBe(true);
    const st2 = ggSectionToggle(sec, st1);
    expect(st2).toEqual({ collapsed: [], opened: [] });
    expect(ggSectionFolded(sec, st2, true)).toBe(false);
  });
  it('phone: a served folded_default section starts folded and opens via `opened`; toggle both ways', () => {
    const st0 = { collapsed: [], opened: [] };
    expect(ggSectionFolded(dsec, st0, true)).toBe(true);
    const st1 = ggSectionToggle(dsec, st0);
    expect(st1).toEqual({ collapsed: [], opened: ['broker'] });
    expect(ggSectionFolded(dsec, st1, true)).toBe(false);
    const st2 = ggSectionToggle(dsec, st1);
    expect(st2).toEqual({ collapsed: [], opened: [] });
    expect(ggSectionFolded(dsec, st2, true)).toBe(true);
  });
});

describe('ggBrokerSection — no banned word, no NaN / undefined', () => {
  it('the lib CODE (comments stripped) types no broker word, no ordering word, no sub key', () => {
    const code = libSrc.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');
    expect(code).not.toMatch(/not eligible|at the bottom|highest volume|potential|activeSub/i);
    expect(code).not.toMatch(/\bfidel/i);
  });
  it('no parsed field prints NaN / undefined', () => {
    const s = parseGgBrokerSection(SEC({ n: NaN, hint: undefined }))!;
    expect(JSON.stringify(s)).not.toMatch(/NaN|undefined/);
    expect(s.n).toBeNull();
    expect(`${s.text}`).not.toMatch(/NaN|undefined/);
  });
});
