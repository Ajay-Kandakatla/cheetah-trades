// ✨ 🧘 GG-like calm check (Ajay 2026-11-27). Placed past index 100 right above the 📅 Runners entry, his words verbatim,
// display only; every number cross-checked against backend/chart_maps/gajjala/gg_like.py (CENSUS / SEPARATION / bounds).
// NEGATIVES below. Pinned by scripts/contracts.mjs ("🧘 GG-like calm check (2026-11-27)").
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const ID = 'gajjala-gg-like-calm-check-2026-11-27';
const HIS = [
  'Yes please, I think we are in bear market and looking at bad setups and make them work, forcing them to work honestly...',
  'Can you update them please.. find calmer and better setups..',
  'Continue to track the runners we might evolve and find patterns in the current runners too but I want to make sure we are finding similar setups to Gajjala',
];
const at = NEW_FEATURES.findIndex((x) => x.id === ID);
const f = NEW_FEATURES[at];

describe('✨ 🧘 GG-like calm check', () => {
  it('is listed once, dated, routed to 🚩, past every index pin, right above the 🧮 float-guard entry (moved 2026-11-27 on rebase)', () => {
    expect(at).toBeGreaterThan(100);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-27');
    expect(f.route).toBe('/chart-maps?tab=gajjala');
    expect(NEW_FEATURES[at + 1].id).toBe('gajjala-si-float-accuracy-guard-2026-11-26');
    expect(NEW_FEATURES[102].id).toBe('chart-maps-gajjala-track-record-tape-2026-10-29');
  });
  it('quotes his three sentences verbatim in curly quotes', () => {
    for (const h of HIS) expect(f.label).toContain(`“${h}”`);
  });
  it('every number equals gg_like.py (CENSUS, SEPARATION, the bounds) and the chip word is the served CHIP_OK', async () => {
    const py = await readSource('../backend/chart_maps/gajjala/gg_like.py');
    const n = (re: RegExp) => { const m = re.exec(py); expect(m, String(re)).not.toBeNull(); return m!; };
    const from = n(/"from": "([^"]+)"/)[1];
    const to = n(/"to": "([^"]+)"/)[1];
    const gg = n(/"gg_like": (\d+)/)[1];
    const carded = n(/"carded": (\d+)/)[1];
    const med = n(/"median": (\d+)/)[1];
    const rs = n(/"reversal_squeeze": \((\d+), (\d+)\)/);
    const inv = n(/"invalid": \{"n": (\d+), "pass_all": (\d+)/);
    const hi = Number(n(/^MAX_UNDER_HIGH_PCT = ([\d.]+)/m)[1]);
    const tn = Number(n(/^TENNIS_MIN_DROP_PCT = ([\d.]+)/m)[1]);
    const chip = n(/^CHIP_OK = "([^"]+)"/m)[1];
    for (const w of [`${from} → ${to}`, `about ${med} cards a day`, `(${gg} of ${carded})`, `(${rs[1]} of ${rs[2]})`,
      `pass ${inv[2]} of his ${inv[1]} invalid examples`, `within ${hi}% of the day's high so far`, `tennis ball drop of ${tn}% or more`, chip]) {
      expect(f.label).toContain(w);
    }
    const bars = await readSource('../backend/chart_maps/gajjala/bars.py');
    const tones = [...bars.matchAll(/\("ema\d+", "(\d+) EMA", GC\.EMA_(?:FAST|SLOW)\)/g)].map((m) => m[1]);
    expect(tones.length).toBe(2);
    expect(f.label).toContain(`the ${tones[0]} or ${tones[1]} EMA`);
  });
  it('says plainly it is rare, not a valid-vs-invalid test, never hides a rung card, and moves nothing', () => {
    for (const w of ['Rare by design', 'almost none', 'not a test of his valid vs invalid charts', 'never hidden', 'on this device only',
      'Display only — no rule, gate, count, sort or push changed', 'the A+ gate is unchanged', 'UNMEASURED', 'Not advice.']) {
      expect(f.label).toContain(w);
    }
  });
  it('NEGATIVE: no straight double quote, never the b-word, signal or edge, never claims a push or a rule change', () => {
    expect(f.label).not.toContain('"');
    const l = f.label.toLowerCase();
    expect(l).not.toMatch(/\bbounc/);
    expect(l).not.toMatch(/\b(signal|edge)s?\b/);
    expect(l).not.toMatch(/\b(now rings|new push|new alert|gate changed|wins|win rate)\b/);
  });
  it('NEGATIVE: a drifted census number would not be found in the label', async () => {
    const py = await readSource('../backend/chart_maps/gajjala/gg_like.py');
    const gg = Number(/"gg_like": (\d+)/.exec(py)![1]);
    const carded = /"carded": (\d+)/.exec(py)![1];
    expect(f.label).not.toContain(`(${gg + 1} of ${carded})`);
    expect(f.label).not.toContain('about 7 cards a day');
  });
});
