/* 🔻 Down 10%+ today — the one pure helper (2026-10-05). */
import { describe, expect, it } from 'vitest';
import { drop10RefreshMs } from './drop10';

describe('drop10RefreshMs — the live re-read cadence is SERVED', () => {
  it('a ready LIVE board re-reads on the served refresh_sec', () => {
    expect(drop10RefreshMs({ state: 'ready', mode: 'live', refresh_sec: 60 })).toBe(60_000);
    expect(drop10RefreshMs({ state: 'ready', mode: 'live', refresh_sec: 90 })).toBe(90_000);
  });

  it('NEGATIVE: after the close, overnight, warming or error never re-reads on the live clock', () => {
    expect(drop10RefreshMs({ state: 'ready', mode: 'after_close', refresh_sec: 60 })).toBeNull();
    expect(drop10RefreshMs({ state: 'ready', mode: 'closed', refresh_sec: null })).toBeNull();
    expect(drop10RefreshMs({ state: 'warming', mode: 'live', refresh_sec: 60 })).toBeNull();
    expect(drop10RefreshMs({ state: 'error', mode: 'live', refresh_sec: 60 })).toBeNull();
  });

  it('NEGATIVE: a malformed cadence or block is null, and a tiny one is floored at 15 s', () => {
    for (const bad of [null, undefined, 'x', [], {}, { state: 'ready', mode: 'live' }]) {
      expect(drop10RefreshMs(bad)).toBeNull();
    }
    for (const s of [0, -5, Number.NaN, Number.POSITIVE_INFINITY, '60']) {
      expect(drop10RefreshMs({ state: 'ready', mode: 'live', refresh_sec: s })).toBeNull();
    }
    expect(drop10RefreshMs({ state: 'ready', mode: 'live', refresh_sec: 1 })).toBe(15_000);
  });
});
