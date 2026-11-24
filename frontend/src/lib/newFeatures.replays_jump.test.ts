// WIDENED +2 2026-11-23 (📈 VWAP all hours + 📺 TV link ✨ FIRST): every NEW_FEATURES[n] pin here moved +2.
// WIDENED 2026-11-23 (🟩 glassy zone bands ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🔌 Watch connections ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (👀 Watch 1/5/15 · 📈 VWAP · 📐 daily zones ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
/* 🏆 Past-winner tag opens the video ✨ (2026-11-22). Ajay: "New feature when I click on this past winner tag take me to
 * that video so change the date and focus me on that video at that. time". */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-replays-past-winner-jump-2026-11-22';

describe('✨ the 🏆 past-winner jump entry (2026-11-22)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;
  it('is FIRST, listed once, dated, routed to 🎬 Replays; the 💸 entry follows', () => {
    expect(NEW_FEATURES[5].id).toBe(ID);
    expect(NEW_FEATURES[6].id).toBe('gajjala-borrow-fee-ibkr-2026-11-22');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-22');
    expect(f.route).toBe('/chart-maps?tab=replays');
  });
  it('quotes him verbatim and says where it lands', () => {
    expect(f.label).toContain('“New feature when I click on this past winner tag take me to that video so change the date and focus me on that video at that. time”');
    expect(f.label).toContain('VWAV: 15:54 ET');
    expect(f.label).toContain('Back returns you to the card');
    expect(f.label).toContain('Navigation only. UNMEASURED. Not advice.');
  });
  it('NEGATIVE: never an edge, the b-word, a push or a gate', () => {
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/bounc/i);
    expect(f.label).not.toMatch(/\bpush(es)?\b|\balert\b|\bgate\b/i);
  });
});
