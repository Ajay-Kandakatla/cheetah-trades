// ✨ 📚 Playbook learning videos (Ajay 2026-11-27). Placed past index 100 right above the 🧘 GG-like entry, his words
// verbatim, routed to 🎬 Replays with the section open, owner only. NEGATIVES below. Pinned by scripts/contracts.mjs
// ("📚 Playbook videos (2026-11-27)").
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';
import { PBV_PARAM, PBV_WHERE } from './playbookVideos';

const ID = 'chart-maps-playbook-videos-2026-11-27';
const HIS = 'I loved the video can you move them under our replay tab with a PLaybook learning and also add it to the playbook tab too with videos';
const at = NEW_FEATURES.findIndex((x) => x.id === ID);
const f = NEW_FEATURES[at];

describe('✨ 📚 Playbook learning videos', () => {
  it('is listed once, dated, past every index pin, right above the 🧘 GG-like entry; the tape pin stays at 102', () => {
    expect(at).toBeGreaterThan(100);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-27');
    expect(NEW_FEATURES[at + 1].id).toBe('gajjala-gg-like-calm-check-2026-11-27');
    expect(NEW_FEATURES[102].id).toBe('chart-maps-gajjala-track-record-tape-2026-10-29');
  });
  it('routes to 🎬 Replays with the 📚 section open (the lib param)', () => {
    expect(f.route).toBe(`/chart-maps?tab=replays&${PBV_PARAM}=1`);
  });
  it('quotes him verbatim in curly quotes and names both places by their served titles', () => {
    expect(f.label).toContain(`“${HIS}”`);
    expect(f.label).toContain(PBV_WHERE.replays.title);
    expect(f.label).toContain(PBV_WHERE.playbook.title);
    for (const w of ['Only you see it.', 'UNMEASURED', 'not a signal']) expect(f.label).toContain(w);
  });
  it('NEGATIVE: generic words only — no straight double quote, no b-word / edge, no admin email, no $TICKER, no autoplay claim', () => {
    expect(f.label).not.toContain('"');
    const l = f.label.toLowerCase();
    expect(l).not.toMatch(/\bbounc/);
    expect(l).not.toMatch(/\bedges?\b/);
    expect(l).not.toContain('ajaykandakatla');
    expect(f.label).not.toMatch(/\$[A-Z]{1,5}\b/);
    expect(l).not.toMatch(/\b(autoplay|plays by itself|new push|new alert)\b/);
  });
  it('NEGATIVE: a near-miss of his sentence (case changed) would not be found', () => {
    expect(f.label).not.toContain(`“${HIS.replace('PLaybook', 'Playbook')}”`);
  });
});
