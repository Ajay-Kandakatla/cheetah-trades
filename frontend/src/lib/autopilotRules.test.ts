import { describe, it, expect } from 'vitest';
import { cleanRules, scanWarning } from './autopilotRules';

describe('cleanRules — engine-served rules list', () => {
  it('keeps well-formed rules in order', () => {
    const out = cleanRules([
      { rule: 'RS rank floor', value: 'RS >= 80', source: 'TLSW p.79' },
      { rule: 'Score floor', value: 'score >= 85', source: 'owner rule' },
    ]);
    expect(out).toHaveLength(2);
    expect(out[0]).toEqual({ rule: 'RS rank floor', value: 'RS >= 80', source: 'TLSW p.79' });
  });

  it('drops malformed entries and trims strings', () => {
    const out = cleanRules([
      { rule: '  padded  ', value: '  v  ', source: '' },
      { rule: '', value: 'orphan' },
      { rule: null, source: 'no rule text' },
      {} as any,
    ]);
    expect(out).toEqual([{ rule: 'padded', value: 'v', source: null }]);
  });

  it('never throws on garbage payloads', () => {
    expect(cleanRules(undefined)).toEqual([]);
    expect(cleanRules(null)).toEqual([]);
    expect(cleanRules('junk' as any)).toEqual([]);
    expect(cleanRules([null, 42, 'x'] as any)).toEqual([]);
  });
});

describe('scanWarning — why the engine is sitting out', () => {
  it('silent when trusted or when the API predates the feature', () => {
    expect(scanWarning({ trusted: true, fresh: true, sized: true })).toBeNull();
    expect(scanWarning(undefined)).toBeNull();
    expect(scanWarning(null)).toBeNull();
    expect(scanWarning({} as any)).toBeNull();   // no trusted flag = old API
  });

  it('names a stale scan with its date', () => {
    const w = scanWarning({ trusted: false, fresh: false, sized: true, scan_date: '2026-07-08' });
    expect(w).toContain('2026-07-08');
    expect(w).toContain('sitting out');
  });

  it('names a too-small universe with the counts', () => {
    const w = scanWarning({
      trusted: false, fresh: true, sized: false,
      universe_size: 120, min_universe: 500,
    });
    expect(w).toContain('120');
    expect(w).toContain('500');
  });

  it('combines both reasons and survives missing details', () => {
    const w = scanWarning({ trusted: false, fresh: false, sized: false });
    expect(w).toContain(' and ');
    expect(scanWarning({ trusted: false })).toContain('trust checks');
  });
});
