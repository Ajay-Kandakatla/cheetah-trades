// ✨ 👀 Watch 5-min grid + frames multi-select (Ajay 2026-11-27). Placed past index 100 right above the 📚 Playbook entry
// (moved 2026-11-27 on rebase: 📚 / 🧘 / 🧮 landed first and 🧮 → 📅 runners is pinned),
// his four messages verbatim, display only; numbers from the constants; NEGATIVES below. Pinned by scripts/contracts.mjs
// ("👀 Watch 5-min grid + frames multi-select (2026-11-27)").
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';
import { GGW_DENSE, GGW_DENSE_DEFAULT, GGW_DENSE_ORDER, GGW_FRAMES_WORDS } from './ggwFrames';
import { VOLUME_SMA_LEN } from './volumePane';

const ID = 'gajjala-watch-5m-grid-2026-11-27';
const HIS = [
  'This is how I want our watch list to be designed.. So I can look at 5 mins charts like 6 in one go...',
  'its not about the visual to look like but the intention is for me to look at more on my watch at a one point of time',
  'Also on the expanded view I need 5 mins by default to look in detail and not sure what the line on volume is its blocking my story..',
  'Give me a drop down or multi select like button to toggle 1 mins and 15 mins 5 mins by default..',
];
const at = NEW_FEATURES.findIndex((x) => x.id === ID);
const f = NEW_FEATURES[at];

describe('✨ 👀 Watch 5-min grid + frames multi-select', () => {
  it('is listed once, dated, routed to 👀 Watch, right above the 📚 Playbook entry and past every index pin', () => {
    expect(at).toBeGreaterThan(100);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-27');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
    expect(NEW_FEATURES[at + 1].id).toBe('chart-maps-playbook-videos-2026-11-27');
    expect(NEW_FEATURES[102].id).toBe('chart-maps-gajjala-track-record-tape-2026-10-29');
  });
  it('quotes all four of his messages in curly quotes', () => {
    for (const q of HIS) expect(f.label).toContain(`“${q}”`);
  });
  it('states the picks, the default shape, the line length and the menu item from the constants', () => {
    expect(f.label).toContain(`the per-screen pick goes ${GGW_DENSE_ORDER.join(' · ')}`);
    const d = GGW_DENSE[GGW_DENSE_DEFAULT];
    expect(f.label).toContain(`${GGW_DENSE_DEFAULT} per screen (${d.cols} × ${d.rows})`);
    expect(f.label).toContain(`the ${VOLUME_SMA_LEN}-bar average volume`);
    expect(f.label).toContain(`“${GGW_FRAMES_WORDS.volAvg}”`);
    for (const w of ['on Watch tiles and in ⤢', 'the 📅 runner chart keeps it', 'one frame always stays on', 'remembered in this browser',
      'Display only: no alert, rule or push changed.']) expect(f.label).toContain(w);
  });
  it('NEGATIVE: no straight double quote, no other bar length, never claims a push, never the b-word or edge', () => {
    expect(f.label).not.toContain('"');
    for (const m of f.label.matchAll(/(\d+)-bar/g)) expect(Number(m[1])).toBe(VOLUME_SMA_LEN);
    const l = f.label.toLowerCase();
    expect(l).not.toMatch(/\brings? your phone\b|\bpush(es)? you\b|\balerts? you\b/);
    expect(l).not.toMatch(/\bbounc/);
    expect(l).not.toMatch(/\bedges?\b/);
  });
  it('NEGATIVE: an unknown id is not listed', () => {
    expect(NEW_FEATURES.findIndex((x) => x.id === `${ID}-x`)).toBe(-1);
  });
});
