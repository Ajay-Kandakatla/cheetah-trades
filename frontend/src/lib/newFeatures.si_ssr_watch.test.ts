// ✨ 🩳⛔ SI / SSR potentials → 👀 Watch with the day's time (Ajay 2026-11-24, spec sissr rev 2 §4 main-session).
// HELD 2026-11-24 (verify refix): the entry promises a 👀 ⛔🩳🔒 section kept across sessions, which exists only once
// be-watch lands — gajjala_watch/constants.RULES_KINDS[2] == "si_ssr" (the ✅ engine allrules.step seats it). Until then
// the entry must be ABSENT. The full entry text is saved at scratchpad sissr/held_new_feature/widened_state.patch.
// Seated: past index 100 right above the ✅ entry (2026-11-25, the 💧 / ✅ way — no NEW_FEATURES[n] pin moves), his
// messages 1 + 3 + the 00:25 🩳 ask verbatim in curly quotes (message 2 carries the b-word); NEGATIVES below.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'gajjala-si-ssr-potentials-watch-2026-11-24';
const M1 = 'Make this new routine 1. Scan Short interest tabs sotkcs that become potentials also and also look for new SSR stocks 2. Then potentials to be alerts sooner - add them to watch list and give them a time stamp of the day';
const M3 = 'Days past little bit like AKAN is what I am mainly looking for many were so confident on SSR..';
const M4 = 'I do need a mention of High SI stock when alerting for potential though..';
const NODE = { fs: 'node:fs', path: 'node:path', url: 'node:url' };

/** RULES_KINDS[2] read the same way scripts/contracts.mjs reads it — no backend file is required to exist. */
export function seatedFrom(allrules: string | null, constants: string): boolean {
  if (allrules == null) return false;
  // '#' comments stripped first (2026-11-25, the contract's own fix): the live tuple's comments carry parentheses.
  const m = /^RULES_KINDS = \(([^)]*)\)/m.exec(constants.replace(/#[^\n]*/g, ''));
  const ks = m ? [...m[1].matchAll(/"([a-z_]+)"/g)].map((x) => x[1]) : [];
  return ks[2] === 'si_ssr';
}

async function seatedNow(): Promise<boolean> {
  const fs = await import(/* @vite-ignore */ NODE.fs);
  const path = await import(/* @vite-ignore */ NODE.path);
  const url = await import(/* @vite-ignore */ NODE.url);
  const W = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), '../../../backend/chart_maps/gajjala_watch');
  const ar = path.join(W, 'allrules.py'), co = path.join(W, 'constants.py');
  return seatedFrom(fs.existsSync(ar) ? fs.readFileSync(ar, 'utf8') : null, fs.existsSync(co) ? fs.readFileSync(co, 'utf8') : '');
}

describe('✨ 🩳⛔ the seat gate (pure)', () => {
  it('seated only when allrules.py exists AND RULES_KINDS[2] == "si_ssr"', () => {
    expect(seatedFrom('def step(', 'RULES_KINDS = ("armed", "aplus", "si_ssr")')).toBe(true);
  });
  it('NEGATIVE: no allrules.py, a two-kind tuple, another third kind, si_ssr in the wrong slot, no tuple → not seated', () => {
    expect(seatedFrom(null, 'RULES_KINDS = ("armed", "aplus", "si_ssr")')).toBe(false);
    expect(seatedFrom('def step(', 'RULES_KINDS = ("armed", "aplus")')).toBe(false);
    expect(seatedFrom('def step(', 'RULES_KINDS = ("armed", "aplus", "other")')).toBe(false);
    expect(seatedFrom('def step(', 'RULES_KINDS = ("si_ssr", "armed", "aplus")')).toBe(false);
    expect(seatedFrom('def step(', '')).toBe(false);
  });
  it('reads the live commented tuple (comments with parentheses) as seated', () => {
    const live = 'RULES_KINDS = ("armed", "aplus",   # "armed" == X (a test pins); "aplus" = a seat\n               "si_ssr")   # appended\n';
    expect(seatedFrom('def step(', live)).toBe(true);
    expect(seatedFrom('def step(', live.replace('"si_ssr"', '"other"'))).toBe(false);
  });
});

describe('✨ 🩳⛔ SI / SSR potentials → 👀 Watch', () => {
  it('HELD before be-watch: absent, and no label carries his message 3; seated: past index 100 above ✅, once, dated, routed to 👀 Watch', async () => {
    const seated = await seatedNow();
    if (!seated) {
      expect(NEW_FEATURES.some((x) => x.id === ID)).toBe(false);
      expect(NEW_FEATURES.some((x) => x.label.includes(M3))).toBe(false);
      return;
    }
    const f = NEW_FEATURES.find((x) => x.id === ID)!;
    const at = NEW_FEATURES.findIndex((x) => x.id === ID);
    expect(at).toBeGreaterThan(100);
    expect(NEW_FEATURES[at + 1].id).toBe('gajjala-watch-all-rules-2026-11-24');
    expect(NEW_FEATURES[0].id).not.toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-24');
    expect(f.route).toBe('/chart-maps?tab=gajjala_watch');
  });
  it('seated: quotes messages 1 and 3 verbatim in curly quotes; NEGATIVE: no straight quote, no message 2, never the b-word, no loosened gate', async () => {
    if (!(await seatedNow())) return;
    const f = NEW_FEATURES.find((x) => x.id === ID)!;
    expect(f.label).toContain(`“${M1}”`);
    expect(f.label).toContain(`“${M3}”`);
    expect(f.label).toContain(`“${M4}”`);
    for (const w of ['every 🧠 alert title', 'tier and short-interest %', '🩳', '⛔', '🔒', '🧠 potential', '👀 Watch', 'AKAN', 'day 2', 'date, time, source and setup', 'never rung', 'same minute as before', 'No gate loosened', 'UNMEASURED', 'Not advice.']) expect(f.label).toContain(w);
    expect(f.label).not.toContain('"');
    expect(f.label).not.toContain('Speicifically setups like AKAN today');
    expect(f.label.toLowerCase()).not.toMatch(/\bbounc/);
    expect(f.label.toLowerCase()).not.toMatch(/\b(buy|sell) (now|signal)\b|\bedge\b|\bforecast/);
  });
});
