/* 🔌 Watch price connections ✨ (2026-11-23). Ajay: "Can you clean up some connection I am seeing delays price update
 * for AKAN on the watch chart..". Spec ggconn WP-1..WP-4. */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-watch-connections-2026-11-23';

describe('✨ the 🔌 Watch connections entry (2026-11-23)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to the 👀 Watch; the 👀 1/5/15 entry follows', () => {
    expect(NEW_FEATURES[0].id).toBe(ID);
    expect(NEW_FEATURES[1].id).toBe('gajjala-watch-frames-vwap-daily-zones-2026-11-23');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-23');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
  });
  it('quotes him verbatim and says plainly the main delay is NOT fixed', () => {
    expect(f.label).toContain('“Can you clean up some connection I am seeing delays price update for AKAN on the watch chart..”');
    expect(f.label).toContain('one failed minute read no longer freezes the live candle');
    expect(f.label).toContain('coming back to the tab reloads the charts');
    expect(f.label).toContain('The biggest cause of the lag is NOT fixed by this');
    expect(f.label).toContain('that one is your call');
    expect(f.label).toContain('UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, the b-word, a gate, a faster-alert or a fixed-delay claim', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bgate\b|\bthreshold\b/i);
    expect(f.label).not.toMatch(/delay (is )?fixed|no more delay|real[- ]time now/i);
  });
});
