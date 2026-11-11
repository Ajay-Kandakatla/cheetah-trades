/* 🧪 audited-modifications ✨ (2026-11-01, gg-audited-mods spec main-session) — Ajay: "Yes make the changes in audited
 * please" and "But keep a track record too to see the winners and loster". FIRST, routed to the 🧪 tab's 🏁 Track
 * record, dated, his two sentences verbatim (his spelling kept), every modification named by its REGISTRY name (read
 * from backend chart_maps/gajjala/audited_rules.py, never typed here), shadow / never sent, UNMEASURED, Not advice.
 * The contract "🧪 Gajjala · Audited tab (2026-11-01)" section 9 pins the same from the source. */
// WIDENED +1 (2026-11-05: the 🏁 three-track-records-alike ✨ went FIRST — Ajay: "Can you make both Gajjala's track record and Gajjalas 1 min and Gajjalas AUDIT HAVE similar track record.")
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

const ID = 'chart-maps-gajjala-audited-modifications-2026-11-01';
const HIS = ['Yes make the changes in audited please', 'But keep a track record too to see the winners and loster'];
const MODS = ['T1', 'T2', 'A1', 'H1', 'T4', 'A2', 'T3', 'T5'];
const f = NEW_FEATURES.find((x) => x.id === ID)!;

/** The served name of a registry Rule: the second string literal of `ID = Rule(` (the first is the id). */
const ruleName = (py: string, id: string): string | null => {
  const a = py.indexOf(`\n${id} = Rule(`);
  if (a < 0) return null;
  const body = py.slice(a);
  const strs = [...body.slice(0, 400).matchAll(/"([^"]*)"/g)].map((m) => m[1]);
  return strs[0] === id ? strs[1] ?? null : null;
};

describe('✨ the 🧪 audited-modifications entry', () => {
  // WIDENED +1 (2026-11-02: the 🏁 one-count / 🥇 Luk's-🏁 ✨ went FIRST — Ajay: "Can you make Luk's track record similar to Gajjal's …")
  // WIDENED +1 (2026-11-06: gajjala-chart-frame FIRST — Ajay: "If I click on Gajjalas tab stocks …") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-09: 🧪 K3S FIRST — Ajay: "yes change the audit as per you like that is yours") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-09 later: ⏱ Gajjala live FIRST — Ajay: "same for reuglar Gajjlas tab as well need it to be more live") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-09 latest: 🌐 Yahoo link-out FIRST — Ajay: "Instead of traderview I need yahoo finance link here") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-09 ~10:00 ET: 🛰 stream entries LIVE FIRST — Ajay: "With entries realtime like Gajjala does") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-09 ~10:30 ET: 🚩 float order on every Gajjala sub FIRST — Ajay: "can you update other tabs in the same way") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-09 ~10:45 ET: 🔴 now label in every session FIRST — Ajay: "I can't see now for them again") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-09 ~10:35 ET: 📊 volume order + 🚫 at the bottom FIRST — Ajay: "Ok sort any stocks by volume on all Gajjala's charts") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-10 ~19:20 ET: 🏠 landing on Gajjala's tab FIRST — Ajay: "Then default my landing page to Gajjala's tab in chartmaps on the app always.") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-10 ~22:00 ET: 🗣 plain words on every Gajjala rule row FIRST — Ajay: "not jus k3 please up date what he means in simple terms acroos k1 to k10") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-11 ~10:10 ET: 🔄 Luk's scan-now button FIRST — Ajay: "Can you put an ondeman scan button for Luk' scans too") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-11: 🔧 formulas-audit defects ship-now FIRST — Ajay 08:18 ET: "Can you fix the defects please") — every NEW_FEATURES[n] pin below → [n+1].
  it('is fourth (the 🚩 chart-frame ✨ 2026-11-06, the 🏁 records-alike ✨ 2026-11-05 and the 🏁 one-count ✨ 2026-11-02 went first), listed once, dated 2026-11-01, routed to the 🧪 🏁 Track record', () => {
    expect(NEW_FEATURES[0].id).toBe('chart-maps-gajjala-defects-ship-now-2026-11-11');   // 2026-11-11: the 🔧 defects ship-now ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[1].id).toBe('chart-maps-luk-scan-now-2026-11-11');   // 2026-11-11 ~10:10 ET: the 🔄 Luk scan-now ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[2].id).toBe('chart-maps-gajjala-plain-words-2026-11-10');   // 2026-11-10 ~22:00 ET: the 🗣 plain-words ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[3].id).toBe('chart-maps-landing-gajjala-tab-2026-11-10');   // 2026-11-10 ~19:20 ET: the 🏠 landing ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[4].id).toBe('chart-maps-gajjala-volume-sort-broker-bottom-2026-11-09');   // 2026-11-09 ~10:35 ET: the 📊 volume-order ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[5].id).toBe('chart-maps-live-now-label-every-session-2026-11-09');   // 2026-11-09 ~10:45 ET: the 🔴 now-label ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[6].id).toBe('chart-maps-gajjala-float-sort-all-subs-2026-11-09');   // 2026-11-09 ~10:30 ET: the 🚩 float-order ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[7].id).toBe('autopilot-gajjala-stream-live-2026-11-09');   // 2026-11-09 ~10:00 ET: the 🛰 stream-entries-LIVE ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[8].id).toBe('chart-maps-yahoo-link-2026-11-09');   // 2026-11-09 (latest): the 🌐 Yahoo link-out ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[9].id).toBe('chart-maps-gajjala-live-stream-2026-11-09');   // 2026-11-09 (later): the ⏱ Gajjala live ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[10].id).toBe('chart-maps-gajjala-audited-k3s-2026-11-09');   // 2026-11-09: the 🧪 K3S ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[11].id).toBe('chart-maps-gajjala-squeeze-chart-2026-11-08');   // 2026-11-08 (later): the 🎾 squeeze-chart ✨ went FIRST — every older index below is +1
    expect(NEW_FEATURES[12].id).toBe('chart-maps-gajjala-entry-zones-2026-11-08');   // 2026-11-08: three ✨ went FIRST (entry zones, 🎾 SI label, ➖ EMA rank) — every older index below is +3
    expect(NEW_FEATURES[13].id).toBe('chart-maps-gajjala-squeeze-si-label-2026-11-08');
    expect(NEW_FEATURES[14].id).toBe('chart-maps-gajjala-fade-ema-rank-2026-11-08');
    expect(NEW_FEATURES[16].id).toBe('chart-maps-gajjala-track-records-alike-2026-11-05');
    expect(NEW_FEATURES[17].id).toBe('luk-track-record-one-count-per-stock-2026-11-02');
    expect(NEW_FEATURES[18].id).toBe(ID);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-01');
    expect(f.route).toBe('/chart-maps?tab=gajjala_audited&sub=track_record');
  });

  it('quotes him verbatim, his spelling kept', () => {
    for (const h of HIS) expect(f.label).toContain(`“${h}”`);
    expect(f.label).toContain('loster');
  });

  it('names every modification by its registry name, and the per-rule winners / losers record', async () => {
    const { default: py } = await import('../../../backend/chart_maps/gajjala/audited_rules.py?raw');
    for (const id of MODS) {
      const nm = ruleName(py, id);
      expect(nm, `audited_rules.${id} served name`).toBeTruthy();
      expect(f.label.toLowerCase()).toContain(nm!.toLowerCase());
    }
    expect(f.label).toContain('winners and losers');
    expect(f.label).toContain('rule by rule');
    expect(f.label).toContain('never hidden');
  });

  it('says shadow / never sent, UNMEASURED and Not advice.', () => {
    expect(f.label).toMatch(/\bshadow\b/);
    expect(f.label).toContain('never sent');
    expect(f.label).toContain('UNMEASURED');
    expect(f.label).toContain('Not advice.');
  });

  it('NEGATIVE: never the b-word, never "edge", never a promise word, never a live ring', () => {
    expect(f.label).not.toMatch(/bounc|\bfake\b/i);
    expect(f.label).not.toMatch(/\bedge\b/i);
    expect(f.label).not.toMatch(/poised|expected to|likely to|predict|will reverse/i);
    expect(f.label).not.toMatch(/now rings your phone|rings your phone since/);
  });

  it('NEGATIVE: the earlier 🧪 tab entry is kept (not replaced) and every id is unique', () => {
    expect(NEW_FEATURES.some((x) => x.id === 'chart-maps-gajjala-audited-2026-11-01')).toBe(true);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });

  it('NEGATIVE: ruleName answers null for a missing id and for a prose line', () => {
    expect(ruleName('\nT1 = Rule(\n    "T1", "daily entry cap",\n)\n', 'T9')).toBeNull();
    expect(ruleName('\nT1 = Rule(\n    "T2", "wrong id",\n)\n', 'T1')).toBeNull();
    expect(ruleName('\nT1 = Rule(\n    "T1", "daily entry cap",\n)\n', 'T1')).toBe('daily entry cap');
  });
});

// 🧪 K3S ✨ (2026-11-09, gg_k3 spec §4 main-session) — Ajay: "yes change the audit as per you like that is yours I need
// you to make it successful and earn money that is the goal". FIRST, once, dated, routed to the 🧪 🏁, his words verbatim,
// shadow / never sent, 🚩 unchanged, UNMEASURED, Not advice.; never "edge", never the b-word, never a win claim.
describe('✨ the 🧪 K3S entry (2026-11-09)', () => {
  const K3S_ID = 'chart-maps-gajjala-audited-k3s-2026-11-09';
  const HIS_K3S = 'yes change the audit as per you like that is yours I need you to make it successful and earn money that is the goal';
  const k = NEW_FEATURES.find((x) => x.id === K3S_ID)!;

  // WIDENED +1 (2026-11-09 later: ⏱ Gajjala live FIRST — Ajay: "same for reuglar Gajjlas tab as well need it to be more live") — K3S [0] → [1], the NEGATIVE [1] → [2].
  // WIDENED +1 (2026-11-09 latest: 🌐 Yahoo link-out FIRST — Ajay: "Instead of traderview I need yahoo finance link here") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-09 ~10:00 ET: 🛰 stream entries LIVE FIRST — Ajay: "With entries realtime like Gajjala does") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-09 ~10:30 ET: 🚩 float order on every Gajjala sub FIRST — Ajay: "can you update other tabs in the same way") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-09 ~10:45 ET: 🔴 now label in every session FIRST — Ajay: "I can't see now for them again") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-09 ~10:35 ET: 📊 volume order + 🚫 at the bottom FIRST — Ajay: "Ok sort any stocks by volume on all Gajjala's charts") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-10 ~19:20 ET: 🏠 landing on Gajjala's tab FIRST — Ajay: "Then default my landing page to Gajjala's tab in chartmaps on the app always.") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-10 ~22:00 ET: 🗣 plain words on every Gajjala rule row FIRST — Ajay: "not jus k3 please up date what he means in simple terms acroos k1 to k10") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-11 ~10:10 ET: 🔄 Luk's scan-now button FIRST — Ajay: "Can you put an ondeman scan button for Luk' scans too") — every NEW_FEATURES[n] pin below → [n+1].
  // WIDENED +1 (2026-11-11: 🔧 formulas-audit defects ship-now FIRST — Ajay 08:18 ET: "Can you fix the defects please") — every NEW_FEATURES[n] pin below → [n+1].
  it('is ELEVENTH (the ⏱ Gajjala live ✨, the 🌐 Yahoo link-out ✨, the 🛰 stream-LIVE ✨, the 🚩 float-order ✨, the 🔴 now-label ✨ and the 📊 volume-order ✨ went FIRST 2026-11-09, the 🏠 landing ✨ and the 🗣 plain-words ✨ 2026-11-10, the 🔄 Luk scan-now ✨ and the 🔧 defects ✨ 2026-11-11), listed once, dated 2026-11-09, routed to the 🧪 Track record', () => {
    expect(NEW_FEATURES[10].id).toBe(K3S_ID);
    expect(NEW_FEATURES.filter((x) => x.id === K3S_ID).length).toBe(1);
    expect(k.addedAt).toBe('2026-11-09');
    expect(k.route).toBe('/chart-maps?tab=gajjala_audited&sub=track_record');
  });

  it('quotes him verbatim and says what it is: shadow, 🚩 unchanged, UNMEASURED, Not advice.', () => {
    expect(k.label).toContain(`“${HIS_K3S}”`);
    expect(k.label).toContain('“broke — not A+”');
    expect(k.label).toContain('never sent');
    expect(k.label).toContain('shadow');
    expect(k.label).toContain('“🧪 only”');
    expect(k.label).toContain('unchanged');
    expect(k.label).toContain('UNMEASURED');
    expect(k.label.endsWith('Not advice.')).toBe(true);
  });

  it('NEGATIVE: never "edge", never the b-word, never a win or money claim', () => {
    expect(/\bedge\b/i.test(k.label)).toBe(false);
    expect(k.label.toLowerCase().includes('b' + 'ounc')).toBe(false);
    expect(/\b(profitable|proven|guaranteed|wins more|beats)\b/i.test(k.label)).toBe(false);
    expect(NEW_FEATURES[11].id).not.toBe(K3S_ID);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});

// ⏱ Gajjala live ✨ (2026-11-09, gg_live spec §4 Z) — Ajay 2026-11-09 ~01:00 ET: "I would like the autopilot to be continously
// monitored or live tracked and changed as if Gallalas makes the trades can you modify and make it more live with websockets or
// something else where there is a low latency monitoring on the prices action changes please?" and "same for reuglar Gajjlas
// tab as well need it to be more live". FIRST, once, dated, routed to the 🚩 🏁, both sentences verbatim (his spelling kept);
// SHADOW stream entries, the bar-close PROBE, the measured "before" (read from the ledger doc's baseline table, never typed
// twice), every other number a constant read from the backend; UNMEASURED, Not advice.; never "edge", never the b-word.
describe('✨ the ⏱ Gajjala live entry (2026-11-09)', () => {
  const LIVE_ID = 'chart-maps-gajjala-live-stream-2026-11-09';
  const HIS_LIVE = [
    'I would like the autopilot to be continously monitored or live tracked and changed as if Gallalas makes the trades can you modify and make it more live with websockets or something else where there is a low latency monitoring on the prices action changes please?',
    'same for reuglar Gajjlas tab as well need it to be more live',
  ];
  const g = NEW_FEATURES.find((x) => x.id === LIVE_ID)!;
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

  it('is TENTH (the 🌐 Yahoo link-out ✨, the 🛰 stream-LIVE ✨, the 🚩 float-order ✨, the 🔴 now-label ✨ and the 📊 volume-order ✨ went FIRST 2026-11-09 later, the 🏠 landing ✨ and the 🗣 plain-words ✨ 2026-11-10, the 🔄 Luk scan-now ✨ and the 🔧 defects ✨ 2026-11-11), listed once, dated 2026-11-09, routed to the 🚩 Track record', () => {
    expect(NEW_FEATURES[9].id).toBe(LIVE_ID);
    expect(NEW_FEATURES.filter((x) => x.id === LIVE_ID).length).toBe(1);
    expect(g.addedAt).toBe('2026-11-09');
    expect(g.route).toBe('/chart-maps?tab=gajjala&sub=track_record');
  });

  it('quotes both of his sentences verbatim and says what shipped: SHADOW, PROBE, unchanged, UNMEASURED, Not advice.', () => {
    for (const h of HIS_LIVE) expect(g.label).toContain(`“${h}”`);
    expect(g.label).toContain('SHADOW');
    expect(g.label).toContain('zero orders change');
    expect(g.label).toContain('PROBE');
    expect(g.label).toContain('the pass timing is unchanged');
    expect(g.label).toContain('the 30 s refresh stays as the fallback');
    expect(g.label).toContain('⏱ Speed');
    expect(g.label).toContain('owner only');
    expect(g.label).toContain('UNMEASURED');
    expect(g.label.endsWith('Not advice.')).toBe(true);
  });

  it('every number is a measured baseline (the ledger doc) or a backend constant', async () => {
    const doc = await readSource('../docs/gajjala/latency_ledger_2026_11_09.md');
    for (const [col, step] of [['Read', 'Read'], ['Rang', 'Rang'], ['Lane saw', 'Lane saw'], ['Ordered', 'Ordered'], ['Filled', 'Filled']]) {
      const row = new RegExp(`^\\| [^|]*\\*\\*${step}\\*\\* \\| \\d+ \\| ([0-9.]+) \\|`, 'm').exec(doc);
      expect(row, `the ledger doc lost the ${step} baseline row`).not.toBeNull();
      expect(g.label).toContain(`${col} ${row![1]}`);
    }
    const ev = await readSource('../backend/chart_maps/gajjala/live_events.py');
    expect(num(ev, 'GG_LIVE_QUOTE_BATCH_SEC')).toBe(1);                        // "about once a second"
    const lc = await readSource('../backend/chart_maps/live_card.py');
    expect(num(lc, 'CARD_LIVE_SEC')).toBe(30);                                  // "the 30 s refresh"
    const gc = await readSource('../backend/chart_maps/gajjala/constants.py');
    expect(num(gc, 'BAR_SETTLE_SEC')).toBe(30);                                 // "final 30 s after it closes"
    expect(/^GAJJALA_BAR_CLOSE_MODE = "probe"/m.test(gc)).toBe(true);
    const st = await readSource('../backend/trading/gajjala_stream.py');
    // 2026-11-09 ~10:00 ET: HIS CALL #1 answered — Ajay: "With entries realtime like Gajjala does" → the built mode is "live".
    // This ⏱ label keeps the words of its ship time (SHADOW at 02:29 ET); the flip has its own, newer ✨ above it.
    expect(/^GG_STREAM_MODE = "live"/m.test(st)).toBe(true);
    const flipIdx = NEW_FEATURES.findIndex((x) => x.id === 'autopilot-gajjala-stream-live-2026-11-09');
    expect(flipIdx).toBeGreaterThanOrEqual(0);
    expect(flipIdx).toBeLessThan(NEW_FEATURES.findIndex((x) => x.id === LIVE_ID));
    const nums = g.label.replace(/\bp50\b/g, '').match(/\d+(?:\.\d+)?/g) || [];   // p50 is a name, not a number
    const allowed = new Set(['1', '5', '30', '61.0', '70.6', '122.0', '124.0', '127.0']);
    for (const n of nums) expect(allowed.has(n), `the label types ${n} — not a constant or a measured figure`).toBe(true);
  });

  it('NEGATIVE: never "edge", never the b-word, never a win claim, never says orders moved to the stream', () => {
    expect(/\bedge\b/i.test(g.label)).toBe(false);
    expect(g.label.toLowerCase().includes('b' + 'ounc')).toBe(false);
    expect(/\b(profitable|proven|guaranteed|wins more|beats|faster profits)\b/i.test(g.label)).toBe(false);
    expect(/orders (now )?go on the (stream|first print)/i.test(g.label)).toBe(false);
    expect(/\bLIVE\b.*\bnow\b/.test(g.label.replace('Stream entries LIVE and the earlier pass are your calls', ''))).toBe(false);
    expect(NEW_FEATURES[10].id).not.toBe(LIVE_ID);
    expect(new Set(NEW_FEATURES.map((x) => x.id)).size).toBe(NEW_FEATURES.length);
  });
});

// 🛰 stream entries LIVE (2026-11-09 ~10:00 ET) — Ajay: "Is the Autopilot logic up to date?  to do entries I would like to see it
// in action now.." / "With entries realtime like Gajjala does". HIS CALL #1 of the GG LIVE spec answered: the built
// GG_STREAM_MODE is "live"; the entry carries both sentences verbatim, names the same A+ / stop / sizes / window, paper only.
describe('✨ the 🛰 stream-entries-LIVE entry (2026-11-09)', () => {
  const FLIP_ID = 'autopilot-gajjala-stream-live-2026-11-09';
  const f = NEW_FEATURES.find((x) => x.id === FLIP_ID)!;
  async function readSrc(rel: string): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/${rel}`, 'utf8');
  }
  it('exists once, dated 2026-11-09, routed to the lane tab, above the ⏱ Gajjala live entry', () => {
    expect(f).toBeTruthy();
    expect(NEW_FEATURES.filter((x) => x.id === FLIP_ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-09');
    expect(f.route).toBe('/trading?view=gajjala');
    const i = NEW_FEATURES.findIndex((x) => x.id === FLIP_ID);
    expect(i).toBeLessThan(NEW_FEATURES.findIndex((x) => x.id === 'chart-maps-gajjala-live-stream-2026-11-09'));
  });
  it('carries both of his sentences verbatim and the LIVE words', () => {
    expect(f.label).toContain('to do entries I would like to see it in action now');
    expect(f.label).toContain('With entries realtime like Gajjala does');
    expect(f.label).toContain('🛰 Stream entries LIVE');
    expect(f.label).toContain('first regular print at or over the trigger');
    expect(f.label).toContain('paper only');
    expect(f.label).toContain('UNMEASURED');
    expect(f.label.endsWith('Not advice.')).toBe(true);
  });
  it('matches the backend: GG_STREAM_MODE is the literal "live" and the window / A+ words are the lane\'s', async () => {
    const st = await readSrc('../backend/trading/gajjala_stream.py');
    expect(/^GG_STREAM_MODE = "live"/m.test(st)).toBe(true);
    expect(/^GG_STREAM_MODES = \("off", "shadow", "live"\)/m.test(st)).toBe(true);
    expect(f.label).toContain('09:45–15:30');
    expect(f.label).toContain('5-minute bar closed through the trigger');
  });
  it('NEGATIVE: never "edge", never the b-word, never a result claim, never a probability', () => {
    expect(/\bedge\b/i.test(f.label)).toBe(false);
    expect(f.label.toLowerCase().includes('b' + 'ounc')).toBe(false);
    expect(/\b(profitable|proven|guaranteed|wins more|beats|faster profits|probability)\b/i.test(f.label)).toBe(false);
    const nums = f.label.match(/\d+(?:\.\d+)?/g) || [];
    const allowed = new Set(['1', '5', '09', '45', '15', '30']);
    for (const n of nums) expect(allowed.has(n), `the label types ${n}`).toBe(true);
  });
});
