import { describe, expect, it, beforeEach } from 'vitest';
import {
  ggwActivateNew, ggwNewNames, GGW_SEEN_KEY, readGgwSeen, saveGgwSeen,
} from './gajjalaWatch';

describe('🆕 a name new to the list joins the pick', () => {
  beforeEach(() => {
    const m = new Map<string, string>();
    Object.defineProperty(window, 'localStorage', { configurable: true, value: {
      getItem: (k: string) => (m.has(k) ? (m.get(k) as string) : null),
      setItem: (k: string, v: string) => { m.set(k, v); },
      removeItem: (k: string) => { m.delete(k); },
    } });
  });

  it('puts new names first and keeps the pick', () => {
    expect(ggwActivateNew(['GP', 'AKAN'], ['GP', 'AKAN', 'CLS', 'NVT'], ['GP', 'AKAN'])).toEqual(['CLS', 'NVT', 'GP', 'AKAN']);
  });
  it('NEGATIVE: no pick (the pages) is left alone, and nothing new leaves the pick unchanged', () => {
    expect(ggwActivateNew(null, ['GP', 'CLS'], ['GP'])).toBeNull();
    expect(ggwActivateNew(['GP'], ['GP', 'CLS'], ['GP', 'CLS'])).toEqual(['GP']);
  });
  it('NEGATIVE: a name already in the pick is not doubled; a name he hid that was already seen stays hidden', () => {
    expect(ggwActivateNew(['GP', 'CLS'], ['GP', 'AKAN', 'CLS'], ['GP', 'AKAN', 'CLS'])).toEqual(['GP', 'CLS']);
    expect(ggwActivateNew(['GP', 'CLS'], ['GP', 'AKAN', 'CLS'], ['GP', 'AKAN'])).toEqual(['GP', 'CLS']);
  });
  it('NEGATIVE: no seen list (a shared link opened cold) adds nothing — the link keeps its own picked names', () => {
    expect(ggwNewNames(['GP', 'CLS'], null)).toEqual([]);
    expect(ggwActivateNew(['GP'], ['GP', 'CLS'], null)).toEqual(['GP']);
  });
  it('the seen list round-trips and an empty list clears it', () => {
    saveGgwSeen(['GP', 'CLS']);
    expect(window.localStorage.getItem(GGW_SEEN_KEY)).toBe('GP,CLS');
    expect(readGgwSeen()).toEqual(['GP', 'CLS']);
    saveGgwSeen([]);
    expect(readGgwSeen()).toBeNull();
  });
});
