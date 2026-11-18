// WIDENED 🎬 chart-maps-replays-slot-search-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 🧨 gajjala-divergence-sub-2026-11-18: a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-18 (🩳 extreme SI note): a new ✨ entry sits FIRST, every NEW_FEATURES[n] pin here moved +1.
// WIDENED 2026-11-18 — the ⏹ 1-minute page retired ✨ entry now sits FIRST (Ajay: "This is good info stop 1 min tab it was a good experiment"), so every NEW_FEATURES[n] position pin here moved +1 again.
// WIDENED 2026-11-17 — the 🎬 Replays ✨ entry now sits FIRST, so every NEW_FEATURES[n] position pin here moved +1.
/* 📶 run-bases ✨ (2026-11-15, ggbase spec main-session) — Ajay: "There is a concept of 3 bases and climax run can you bake
 * that in to the app please" and "I need that tracked in to Gajjala's". FIRST, routed to 🚩 Gajjala's tab, dated, his two
 * sentences verbatim; the 3rd / 4th base words are the SERVED words (read from backend chart_maps/gajjala/run_bases.py
 * BASE_WORDS, never typed here); the 6-bar minimum and the 2-hour restart are read from constants.py by name
 * (RUN_BASE_MIN_BARS = K4_HF_BASE_MIN, RUN_BASE_MAX_BARS = K4_HF_BASE_MAX on 5-minute bars); information only,
 * UNMEASURED, Not advice. */
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-gajjala-run-bases-2026-11-15';
const HIS = [
  'There is a concept of 3 bases and climax run can you bake that in to the app please',
  "I need that tracked in to Gajjala's",
];

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const num = (src: string, name: string): number => {
  const m = new RegExp(`^${name} = ([0-9.]+)`, 'm').exec(src);
  if (!m) throw new Error(`lost ${name}`);
  return Number(m[1]);
};
const alias = (src: string, name: string): string => {
  const m = new RegExp(`^${name} = ([A-Za-z_0-9"]+)`, 'm').exec(src);
  if (!m) throw new Error(`lost ${name}`);
  return m[1];
};

describe('✨ the 📶 run-bases entry (2026-11-15)', () => {
  const f = NEW_FEATURES.find((x) => x.id === ID)!;

  it('is FIRST, listed once, dated and routed to 🚩 Gajjala', () => {
    // WIDENED +1 (2026-11-17: 🎯 chart-maps-gajjala-watch-aplus-push-2026-11-17 FIRST — Ajay: "Push new Apluses immediately in to watch list and an alert for me please Missed AKAN and GP") — every NEW_FEATURES[n] pin below → [n+1].
    expect(NEW_FEATURES[22].id).toBe(ID);
    expect(NEW_FEATURES[23].id).toBe('chart-maps-gajjala-watch-2026-11-15');
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
    expect(f.addedAt).toBe('2026-11-15');
    expect(f.route).toBe('/chart-maps?tab=gajjala');
  });

  it('quotes him verbatim', () => {
    for (const q of HIS) expect(f.label).toContain(`“${q}”`);
  });

  it('prints the served base words, read from run_bases.py BASE_WORDS', async () => {
    const py = await readSource('../backend/chart_maps/gajjala/run_bases.py');
    const m = /^BASE_WORDS = \(([^)]*)\)/m.exec(py);
    expect(m).not.toBeNull();
    const words = [...m![1].matchAll(/"([^"]*)"/g)].map((x) => x[1]);
    expect(words.length).toBe(4);
    expect(words[2]).toContain('climax run');
    expect(words[3]).toContain('came out of everything');
    expect(f.label).toContain(`“${words[2]}”`);
    expect(f.label).toContain(`“${words[3]}”`);
    expect(f.label).toContain('“📶 1st base”');
    expect(f.label).toContain('“📶 2nd base”');
  });

  it('the 6-bar minimum and the 2-hour restart are the constants in force', async () => {
    const gc = await readSource('../backend/chart_maps/gajjala/constants.py');
    expect(alias(gc, 'RUN_BASE_MIN_BARS')).toBe('K4_HF_BASE_MIN');
    expect(alias(gc, 'RUN_BASE_MAX_BARS')).toBe('K4_HF_BASE_MAX');
    expect(alias(gc, 'RUN_BASE_FRAME')).toBe('"5m"');
    expect(alias(gc, 'RUN_BASE_FROM')).toBe('"rth"');
    expect(alias(gc, 'RUN_BASE_RESTART')).toBe('True');
    const min = num(gc, 'K4_HF_BASE_MIN');
    const max = num(gc, 'K4_HF_BASE_MAX');
    expect(f.label).toContain(`bases of ${min} or more 5-minute bars (${min * 5} minutes)`);
    expect(f.label).toContain(`a pause of more than ${(max * 5) / 60} hours`);
    expect(f.label).toContain('from the 09:30 open');
  });

  it('says information only, the A+ stamp, UNMEASURED and Not advice', () => {
    expect(f.label).toContain('Information only');
    expect(f.label).toContain('nothing rings, peels, sorts or trades on it');
    expect(f.label).toContain('Each A+ alert records the base it fired in');
    expect(f.label).toContain('UNMEASURED');
    expect(f.label.trim().endsWith('Not advice.')).toBe(true);
  });

  it('NEGATIVE: never advice, never the b-word, never an edge claim', () => {
    expect(f.label).not.toMatch(/\bbounce/i);
    expect(f.label).not.toMatch(/\b(buy|sell|exit now|edge|win rate)\b/i);
    expect(f.label).not.toMatch(/\d+(\.\d+)?\s?%/);                     // no measured number — UNMEASURED
    expect(f.label).not.toContain('1-bar');                              // a 1-bar flag no longer counts (his "2nd option")
  });
});
