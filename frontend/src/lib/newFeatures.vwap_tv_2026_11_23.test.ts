// WIDENED 2026-11-23 (🎾 tag on 🩳 cards ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 close-out date sorts first ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🔒 Reg SHO close-out day ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 % in the High SI chip ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 High SI sub + 9/21 EMA cross alerts ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED +1 2026-11-23 (🕯 1-min candles ✨ FIRST): every NEW_FEATURES[n] pin here moved +1.
/* 📈 VWAP all hours + 📺 TV ↗ ✨ (2026-11-23). */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

describe('✨ 📈 VWAP all hours + 📺 TV ↗ (2026-11-23)', () => {
  const v = NEW_FEATURES.find((x) => x.id === 'gajjala-watch-vwap-all-hours-2026-11-23')!;
  const t = NEW_FEATURES.find((x) => x.id === 'chart-maps-tv-link-2026-11-23')!;
  it('sit right under the 🕯 candles entry, listed once each, dated; the 🟩 glass entry follows', () => {
    expect(NEW_FEATURES[6].id).toBe('gajjala-watch-vwap-all-hours-2026-11-23');
    expect(NEW_FEATURES[7].id).toBe('chart-maps-tv-link-2026-11-23');
    expect(NEW_FEATURES[8].id).toBe('gajjala-watch-zones-glass-2026-11-23');
    for (const f of [v, t]) { expect(NEW_FEATURES.filter((x) => x.id === f.id).length).toBe(1); expect(f.addedAt).toBe('2026-11-23'); }
  });
  it('quote him verbatim and say what changed', () => {
    expect(v.label).toContain('“Why is VWAP not showing up in AH?”');
    expect(v.label).toContain('“Please extend them to all hours..”');
    expect(v.label).toContain('from 04:00 premarket through after-hours, today only');
    expect(t.label).toContain('“Also add traderview charts on charts please.. Yahoo has been hard to configure”');
    expect(t.label).toContain('Yahoo ↗ is unchanged');
  });
  it('NEGATIVE: never an edge, the b-word, a gate or a threshold', () => {
    for (const f of [v, t]) {
      expect(f.label).not.toMatch(/\bedge\b/i);
      expect(f.label).not.toMatch(/bounc/i);
      expect(f.label).not.toMatch(/\bgate\b|\bthreshold\b/i);
    }
  });
});
