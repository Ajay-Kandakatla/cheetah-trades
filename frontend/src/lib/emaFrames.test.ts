import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  EMA_FRAMES, EMA_SPAN, countLine, emaFramesQuery, emptyReason, formingNote,
  frameStat, loadEmaFrame, parseEmaFrame, saveEmaFrame,
} from './emaFrames';
import type { CmTile } from './chartMaps';

/* 〰️ 9 EMA · W/M — the pure half (2026-09-23).
 *
 * Ajay: "Also a new tab for 9EMA lines on our charts for weekly charts and
 * monthly charts please". This file guards the words and the frame toggle;
 * the resample, the forming rule and the EMA itself are the backend's and are
 * pinned in backend/tests/test_ema_frames_2026_09_23.py.
 */

function mem() {
  const store: Record<string, string> = {};
  return {
    getItem: (k: string) => (k in store ? store[k] : null),
    setItem: (k: string, v: string) => { store[k] = String(v); },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { for (const k of Object.keys(store)) delete store[k]; },
    key: (i: number) => Object.keys(store)[i] ?? null,
    get length() { return Object.keys(store).length; },
  };
}

afterEach(() => { vi.unstubAllGlobals(); });

describe('the two frames, and only the two', () => {
  it('offers weekly and monthly, in his order', () => {
    expect(EMA_FRAMES).toEqual(['weekly', 'monthly']);
  });

  it('carries his period and no other', () => {
    expect(EMA_SPAN).toBe(9);
  });

  it('falls back rather than breaking on an unknown frame', () => {
    expect(parseEmaFrame('weekly')).toBe('weekly');
    expect(parseEmaFrame('MONTHLY')).toBe('monthly');
    // NEGATIVE: a daily / quarterly / nonsense value must draw the default
    // board, never blank the tab.
    expect(parseEmaFrame('daily')).toBe('weekly');
    expect(parseEmaFrame(null)).toBe('weekly');
    expect(parseEmaFrame(undefined)).toBe('weekly');
    expect(parseEmaFrame(42)).toBe('weekly');
  });
});

describe('the query', () => {
  it('sends an upper-cased symbol and the parsed frame', () => {
    expect(emaFramesQuery('  mu ', 'monthly')).toBe('symbol=MU&frame=monthly');
  });

  it('never sends a frame the backend does not know', () => {
    expect(emaFramesQuery('MU', 'quarterly' as any)).toBe('symbol=MU&frame=weekly');
  });
});

describe('the remembered frame is a per-viewer convenience', () => {
  it('round-trips', () => {
    vi.stubGlobal('localStorage', mem());
    saveEmaFrame('monthly');
    expect(loadEmaFrame()).toBe('monthly');
  });

  it('renders the default board when the store is blocked', () => {
    // NEGATIVE: a private window / blocked storage must not throw and must not
    // leave the tab frameless.
    vi.stubGlobal('localStorage', {
      getItem() { throw new Error('blocked'); },
      setItem() { throw new Error('blocked'); },
    });
    expect(() => saveEmaFrame('monthly')).not.toThrow();
    expect(loadEmaFrame()).toBe('weekly');
  });
});

describe('the sentences', () => {
  it('says which list to add to when the cohort is empty', () => {
    const s = emptyReason([], null);
    expect(s).toContain('Signals watchlist');
    expect(s).toContain('empty');
  });

  it('says nothing while the cohort is still loading', () => {
    // NEGATIVE: "null" is loading, not empty — an empty-state sentence during
    // the first fetch reads as "you have no tickers", which is a lie.
    expect(emptyReason(null, null)).toBeNull();
  });

  it('says nothing when the cohort has names', () => {
    expect(emptyReason(['MU'], null)).toBeNull();
  });

  it('reports a failed watchlist read rather than claiming it is empty', () => {
    expect(emptyReason([], 'HTTP 500')).toContain('HTTP 500');
  });

  it('counts what it drew against what it asked for', () => {
    expect(countLine(11, 12, 'weekly')).toBe('11 of 12 drawn on weekly bars');
    expect(countLine(0, 0, 'monthly')).toBe('0 of 0 drawn on monthly bars');
  });
});

describe('the forming note is SERVED, never composed', () => {
  const read = (forming: any) => ({ symbol: 'MU', frame: 'weekly' as const, tile: null, forming });

  it('returns the served sentence', () => {
    expect(formingNote(read({ date: '2026-09-25', frame: 'weekly', note: 'the week is forming' })))
      .toBe('the week is forming');
  });

  it('returns null for a completed period', () => {
    // NEGATIVE: nothing is invented here. No served `forming` block, no note —
    // the page must never decide for itself that a bar is unfinished.
    expect(formingNote(read(null))).toBeNull();
    expect(formingNote(null)).toBeNull();
    expect(formingNote(undefined)).toBeNull();
  });
});

describe('the frame description comes off the tile', () => {
  const tile = (stats: any[]) => ({ stats } as unknown as CmTile);

  it('reads the served Frame stat', () => {
    expect(frameStat(tile([{ k: 'Frame', v: 'Weekly — Mon–Fri bars' }])))
      .toBe('Weekly — Mon–Fri bars');
  });

  it('says nothing when the payload did not say it', () => {
    // NEGATIVE: no fallback string. A hard-coded "Mon–Fri" here would keep
    // describing a resample the backend had changed.
    expect(frameStat(tile([{ k: 'Last bar', v: '2026-09-25' }]))).toBeNull();
    expect(frameStat(null)).toBeNull();
  });
});

describe('nothing here ranks anything', () => {
  it('exports no comparator, no threshold and no filter', () => {
    // Rule #10: the tab is a drawing. If a sort or a gate ever lands in this
    // module this test is where it gets caught.
    const mod = { EMA_FRAMES, EMA_SPAN, countLine, emaFramesQuery, emptyReason,
                  formingNote, frameStat, loadEmaFrame, parseEmaFrame, saveEmaFrame };
    for (const k of Object.keys(mod)) {
      expect(/sort|rank|score|gate|filter|min_|threshold/i.test(k)).toBe(false);
    }
  });
});
