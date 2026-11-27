// ✨ 🩳 on-entry SI source check (Ajay 2026-11-27). Placed past index 100 right above the 👀 5-min grid entry, all five
// of his messages verbatim, display only; every served word it names is read from the backend source here (never
// retyped), so a change there fails this file. NEGATIVES below. Pinned by scripts/contracts.mjs
// ("🩳 on-entry SI check (2026-11-27)"). Spec sicheck rev 2 §4.6.
import { describe, expect, it } from 'vitest';
import { NEW_FEATURES } from './newFeatures';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const pyStr = (src: string, name: string): string => {
  const m = new RegExp(`^${name} = "([^"]*)"`, 'm').exec(src);
  if (!m) throw new Error(`lost ${name}`);
  return m[1];
};

const ID = 'gajjala-si-entry-check-2026-11-27';
const HIS = [
  'Can you double check short interest for these two please?',
  'Anytime something is in our Gajjalas we need to initiate a flow checking these values',
  'WHLR is too much',
  'Can you check out volume for NXAT and POM … I think this is wrong..',
  'Look like its already 29 mullion traded today',
];
const at = NEW_FEATURES.findIndex((x) => x.id === ID);
const f = NEW_FEATURES[at];

describe('✨ 🩳 on-entry SI source check', () => {
  it('is listed once, dated, routed to 🚩 Gajjala, right above the 👀 5-min grid entry and past every index pin', () => {
    expect(at).toBeGreaterThan(100);
    expect(NEW_FEATURES.filter((x) => x.id === ID).length).toBe(1);
    expect(f.addedAt).toBe('2026-11-27');
    expect(f.route).toBe('/chart-maps?tab=gajjala');
    expect(NEW_FEATURES[at + 1].id).toBe('gajjala-watch-5m-grid-2026-11-27');
    expect(NEW_FEATURES[102].id).toBe('chart-maps-gajjala-track-record-tape-2026-10-29');
  });

  it('quotes all five of his messages verbatim in curly quotes', () => {
    for (const q of HIS) expect(f.label).toContain(`“${q}”`);
  });

  it('names every served word from the backend constants', async () => {
    const ec = await readSource('../backend/short_interest/entry_check.py');
    const sc = await readSource('../backend/short_interest/source_check.py');
    const bm = await readSource('../backend/short_interest/basis_math.py');
    const rd = await readSource('../backend/short_interest/read.py');
    const tab = await readSource('../backend/chart_maps/gajjala/tab.py');
    const doc = await readSource('../docs/short_interest/entry_check_flags_2026_11_27.md');
    // the Yahoo sentence, verbatim (TEXT_YAHOO carries a leading space)
    const yahoo = /^TEXT_YAHOO = "([^"]*)"/m.exec(ec);
    expect(yahoo).not.toBeNull();
    expect(f.label).toContain(yahoo![1].trim());
    // the row name
    expect(f.label).toContain(`an ${pyStr(rd, 'ROW_ENTRY_CHECK')} row`);
    // the chip tokens: EMOJI_WARN / EMOJI_SPLIT + their words
    const em = /^EMOJI_WARN, EMOJI_SPLIT, EMOJI_FILING, EMOJI_CHECK = "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)"/m.exec(bm);
    expect(em).not.toBeNull();
    const [, warn, split] = em!;
    expect(/^SHORT_SOURCES = BM\.EMOJI_WARN \+ " sources disagree"/m.test(sc)).toBe(true);
    expect(f.label).toContain(`${warn} sources disagree`);
    expect(/^SHORT_SPLIT_FILING = EMOJI_SPLIT \+ " split filing %s"/m.test(bm)).toBe(true);
    expect(f.label).toContain(`${split} split filing M/D`);
    expect(/^SHORT_DATE_GAP = EMOJI_WARN \+ " dates apart"/m.test(bm)).toBe(true);
    expect(f.label).toContain(`${warn} dates apart`);
    // the ⚠️ dates apart words = DATE_GAP_MODE_WORDS[FLOAT_STALE_WHEN]
    const when = pyStr(bm, 'FLOAT_STALE_WHEN');
    const words = new RegExp(`^\\s+"${when}": "([^"]+)",`, 'm').exec(bm.slice(bm.indexOf('DATE_GAP_MODE_WORDS = {')));
    expect(words).not.toBeNull();
    expect(f.label).toContain(`(${words![1]})`);
    // the stamp: ROW_ASOF_TEXT with HH:MM
    expect(f.label).toContain(pyStr(tab, 'ROW_ASOF_TEXT').replace('{hhmm}', 'HH:MM'));
    // the both-way count is the one the real engines gave (the doc's pinned table)
    const n = /\| \*\*(\d+) of (\d+)\*\* \|/.exec(doc);
    expect(n).not.toBeNull();
    expect(f.label).toContain(`${n![1]} of ${n![2]} names`);
    // the mode words the label leans on are on (a switch flipped off makes this entry stale)
    expect(pyStr(ec, 'EC_WHEN')).toBe('on');
    expect(/^RUNG_FLAG = "on"/m.test(sc)).toBe(true);
  });

  it('says what did NOT change and what is his call', () => {
    for (const w of ['Yahoo', 'the number itself is not refreshed (your call)', 'Nothing was built for WHLR', 'not usable and never adds it',
      'a proposal, a vote notice and an executed split all match', 'Display only — no alert, gate, sort or list changed',
      'the % and the tier word are unchanged', 'UNMEASURED']) expect(f.label).toContain(w);
    expect(f.label.endsWith('Not advice.')).toBe(true);
  });

  it('says the 🧠 potential push title of a 🩳-listed name carries the same new words, and nothing on the push moved', async () => {
    const bm = await readSource('../backend/short_interest/basis_math.py');
    const em = /^EMOJI_WARN, EMOJI_SPLIT, EMOJI_FILING, EMOJI_CHECK = "([^"]+)", "([^"]+)"/m.exec(bm);
    expect(em).not.toBeNull();
    const [, warn, split] = em!;
    expect(f.label).toContain(`The 🧠 potential push title of a 🩳-listed name now carries the same new words (${split} split filing, ${warn} sources disagree); no trigger, dedupe or count moved.`);
    /* NEGATIVE: the sentence sits after the display-only line and before the closing words, and never says a push was added */
    const i = f.label.indexOf('The 🧠 potential push title');
    expect(i).toBeGreaterThan(f.label.indexOf('Display only — no alert, gate, sort or list changed'));
    expect(i).toBeLessThan(f.label.indexOf('UNMEASURED'));
    expect(f.label.toLowerCase()).not.toMatch(/new push|push(es)? added|now pushes/);
  });

  it('NEGATIVE: no straight double quote, never signal / edge / the b-word, never claims a push or a changed word', () => {
    expect(f.label).not.toContain('"');
    const l = f.label.toLowerCase();
    expect(l).not.toMatch(/\bsignals?\b/);
    expect(l).not.toMatch(/\bedges?\b/);
    expect(l).not.toMatch(/\bbounc/);
    expect(l).not.toMatch(/\brings? your phone\b|\bpush(es)? you\b|\balerts? you\b/);
    expect(l).not.toMatch(/drops to high|extreme is held/);
  });

  it('NEGATIVE: an unknown id is not listed, and a paraphrase of his words would not pass', () => {
    expect(NEW_FEATURES.findIndex((x) => x.id === `${ID}-x`)).toBe(-1);
    expect(f.label).not.toContain('“Anytime something is in our Gajjala we');
    expect(f.label).not.toContain('29 million traded today”');
  });
});
