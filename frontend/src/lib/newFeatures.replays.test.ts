// WIDENED 2026-11-23 (🔒 Reg SHO close-out day ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 % in the High SI chip ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🩳 High SI sub + 9/21 EMA cross alerts ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED +1 2026-11-23 (🕯 1-min candles ✨ FIRST): every NEW_FEATURES[n] pin here moved +1.
// WIDENED +2 2026-11-23 (📈 VWAP all hours + 📺 TV link ✨ FIRST): every NEW_FEATURES[n] pin here moved +2.
// WIDENED 2026-11-23 (🟩 glassy zone bands ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (🔌 Watch connections ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-23 (👀 Watch 1/5/15 · 📈 VWAP · 📐 daily zones ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (🏆 past-winner jump ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (💸 Borrow fee ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (🔒 Hard to borrow ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (👀 Watch sections + 📅 runners ✨ FIRST): a new ✨ entry sits on top, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-22 (🏆 setup + timing ✨ FIRST, 🏆 past-winner tag ✨ SECOND): two new ✨ entries sit on top, every NEW_FEATURES[n] pin here moved +2.
// WIDENED 2026-11-21 (👀 Watch float first): a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED past-winners-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED watch-newest-first-charts-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED watch-not-eligible-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED watch-new-names-active-2026-11-19: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🩳 gajjala-si-tier-words-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🌱 gajjala-diverging-sub-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🏷 chart-maps-gajjala-watch-tags-row-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 👀 chart-maps-gajjala-watch-18-replace-oldest-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 👀 chart-maps-gajjala-card-grid-watch-layout-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🎬 chart-maps-replays-slot-search-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🧨 gajjala-divergence-sub-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-18 (🩳 extreme SI note): a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
/* 🎬 Replays ✨ (2026-11-17, replays spec §4 main-session) — Ajay 2026-11-17: "Can you store the videos in to the app
 * please". FIRST, once, dated, routed to the tab, his words verbatim, Owner only, UNMEASURED. NEGATIVE: no window literal
 * typed (the served text carries 04:00-20:00 ET), no admin email, no b-word, no "edge", the older ✨ entries kept. The
 * contract "🎬 Replays (2026-11-17)" pins the backend side from source. */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-replays-tab-2026-11-17';
const HIS = 'Can you store the videos in to the app please';
const f = NEW_FEATURES.find((x) => x.id === ID);

describe('✨ the 🎬 Replays tab entry (2026-11-17)', () => {
  it('is FIRST, listed once, dated 2026-11-17, routed to ?tab=replays', () => {
    expect(NEW_FEATURES[29].id).toBe(ID);   // WIDENED 2026-11-18 — the ⏹ 1-minute page retired ✨ now sits FIRST
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f?.addedAt).toBe('2026-11-17');
    expect(f?.route).toBe('/chart-maps?tab=replays');
  });

  it('quotes him verbatim and names the tab, the groups, the 4 AM to 8 PM rule and the owner gate', () => {
    const l = f?.label ?? '';
    expect(l).toContain(`“${HIS}”`);
    for (const need of ['🎬 Replays', 'A+ winners and losers', 'the biggest mover', '🎾 Reversal Squeeze potentials',
      'from 4 AM to 8 PM', 'nothing shorter is listed', 'Owner only.']) expect(l).toContain(need);
  });

  it('says UNMEASURED and that a replay is not a signal', () => {
    const l = f?.label ?? '';
    expect(l).toContain('UNMEASURED');
    expect(l).toContain('a replay is for your eyes, not a signal.');
  });

  it('NEGATIVE: no window literal, no admin email, no b-word, no "edge", no buy/sell word', () => {
    const l = f?.label ?? '';
    expect(l).not.toContain('04:00-20:00');
    expect(l).not.toMatch(/ajaykandakatla/i);
    expect(l).not.toMatch(/bounc/i);
    expect(l).not.toMatch(/\bedge\b/i);
    expect(l).not.toMatch(/\b(buy|buying|bought|sell|selling|sold)\b/i);
  });

  it('NEGATIVE: the matchers are live', () => {
    expect('a real edge').toMatch(/\bedge\b/i);
    expect('a bounce').toMatch(/bounc/i);
    expect('we sell here').toMatch(/\b(buy|buying|bought|sell|selling|sold)\b/i);
  });

  it('NEGATIVE: the 🎯 A+ push ✨ is not replaced — right after this entry, listed once; ids stay unique', () => {
    expect(NEW_FEATURES[30].id).toBe('chart-maps-gajjala-watch-aplus-push-2026-11-17');   // WIDENED 2026-11-18 (⏹ retired ✨ FIRST)
    expect(NEW_FEATURES.filter((x) => x.id === 'chart-maps-gajjala-watch-aplus-push-2026-11-17').length).toBe(1);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});
