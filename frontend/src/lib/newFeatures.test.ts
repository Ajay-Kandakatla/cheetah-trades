import { describe, it, expect } from 'vitest';
import { isRecent, NEW_FEATURES, NEW_WINDOW_DAYS } from './newFeatures';

/* newFeatures — the "what's new" registry + recency window (Ajay 2026-06-18:
   highlight each shipped feature until viewed). */

describe('isRecent', () => {
  const now = new Date('2026-06-18T12:00:00Z');

  it('is true inside the highlight window', () => {
    expect(isRecent('2026-06-18', now)).toBe(true);
    expect(isRecent('2026-06-17', now)).toBe(true);
    expect(isRecent('2026-05-25', now)).toBe(true);          // ~24d, < 30d
  });

  it('is false once the feature has aged past the window', () => {
    expect(isRecent('2026-01-01', now)).toBe(false);
    expect(isRecent('2026-05-01', now)).toBe(false);         // > 30d
  });

  it('is false for an unparseable date (never a crash)', () => {
    expect(isRecent('nope', now)).toBe(false);
    expect(isRecent('', now)).toBe(false);
  });

  it('window is the documented length', () => {
    expect(NEW_WINDOW_DAYS).toBe(30);
  });
});

describe('NEW_FEATURES registry', () => {
  it('every entry is well-formed (id, label, parseable date)', () => {
    expect(NEW_FEATURES.length).toBeGreaterThan(0);
    const ids = new Set<string>();
    for (const f of NEW_FEATURES) {
      expect(f.id).toBeTruthy();
      expect(f.label).toBeTruthy();
      expect(Number.isNaN(Date.parse(`${f.addedAt}T00:00:00`))).toBe(false);
      expect(ids.has(f.id)).toBe(false);                     // ids unique
      ids.add(f.id);
    }
  });
});
