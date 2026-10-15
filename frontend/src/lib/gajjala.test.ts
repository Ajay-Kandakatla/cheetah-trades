import { describe, expect, it } from 'vitest';
import {
  GG_DEFAULT_SUB, GG_GRADE_LABEL, GG_OUTER_CHIPS, GG_SETUPS, GG_SUBS, GG_VARIANT_LABEL,
  changeText, chipText, criteriaText, ggHref, gradeText, ggQuery, ggRefreshMs, isGgSetup, parseGgSub, parseGgTf,
  playbookItem, riskText, variantText, watchParts,
} from './gajjala';

/* tsc-safe source read (the HottestSectors.width.test precedent): the app's
 * tsconfig carries no node types, so `node:fs` is imported dynamically. Paths
 * are relative to frontend/ (vitest's cwd). */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

/* 🚩 lib/gajjala (2026-10-13) — the URL plumbing and the print helpers. The
 * negatives carry the weight: an absent sub must stay absent (a push deep link
 * lets the server pick it), an unknown one must land on the default, and a
 * missing number must print NOTHING, never "NaN" / "undefined". */

describe('parseGgSub', () => {
  it('known keys pass, case and spaces folded', () => {
    for (const s of GG_SUBS) expect(parseGgSub(s.key)).toBe(s.key);
    expect(parseGgSub(' Reversal_Squeeze ')).toBe('reversal_squeeze');
  });
  it('NEGATIVE: absent / empty → null (the server resolves a focus link)', () => {
    expect(parseGgSub(null)).toBeNull();
    expect(parseGgSub(undefined)).toBeNull();
    expect(parseGgSub('   ')).toBeNull();
  });
  it('NEGATIVE: unknown → bull_flag', () => {
    for (const raw of ['nonsense', 'bull-flag', 'vcp', '<script>']) expect(parseGgSub(raw)).toBe('bull_flag');
    expect(GG_DEFAULT_SUB).toBe('bull_flag');
  });
});

describe('parseGgTf / ggQuery / ggRefreshMs', () => {
  it('only 5m / 15m are frames', () => {
    expect(parseGgTf('15m')).toBe('15m');
    expect(parseGgTf('5M')).toBe('5m');
    for (const raw of ['1m', '15', '', null]) expect(parseGgTf(raw as any)).toBeNull();
  });
  it('sends sub / tf / focus / sort only when set', () => {
    expect(ggQuery({})).toBe('');
    const q = new URLSearchParams(ggQuery({ sub: 'kiss_fly', tf: '15m', focus: 'PFAI', sort: 'change', limit: 24 }));
    expect([...q.keys()]).toEqual(['sub', 'tf', 'focus', 'sort', 'limit']);
    expect(ggQuery({ focus: 'PFAI' })).toBe('focus=PFAI');
  });
  it('NEGATIVE: a junk limit is not sent', () => {
    for (const limit of [0, -3, NaN, Infinity, null]) expect(ggQuery({ limit: limit as any })).not.toContain('limit');
  });
  it('re-reads on the served refresh_sec; NEGATIVE 0 / absent / junk → null', () => {
    expect(ggRefreshMs({ session: { refresh_sec: 300 } })).toBe(300_000);
    for (const b of [{ session: { refresh_sec: 0 } }, { session: {} }, {}, null, { session: { refresh_sec: '300' } },
                     { session: { refresh_sec: -1 } }, { session: { refresh_sec: NaN } }]) {
      expect(ggRefreshMs(b)).toBeNull();
    }
  });
});

describe('print helpers', () => {
  it('chipText prints a served string or an object text; NEGATIVE nothing for null / blank / junk', () => {
    expect(chipText('Float 3.1M')).toBe('Float 3.1M');
    expect(chipText({ text: 'shares out 8.1M (Massive)' })).toBe('shares out 8.1M (Massive)');
    for (const v of [null, undefined, '', '  ', {}, { text: null }, { text: '' }]) expect(chipText(v as any)).toBeNull();
  });
  it('criteriaText: ✓ / ✗ / · with value and need', () => {
    expect(criteriaText({ key: 'K4', label: 'pullback bars', ok: true, value: '2', need: '1–3' })).toBe('✓ pullback bars — 2 (1–3)');
    expect(criteriaText({ key: 'K4', label: 'pullback bars', ok: false, value: '5', need: '1–3' })).toBe('✗ pullback bars — 5 (1–3)');
    expect(criteriaText({ key: 'E', label: '9 EMA', ok: null, value: 'warming up', need: null })).toBe('· 9 EMA — warming up');
    expect(criteriaText({ key: 'E', label: '9 EMA', ok: null })).toBe('· 9 EMA');
  });
  it('changeText / riskText print served numbers; NEGATIVE non-finite → null', () => {
    expect(changeText(48.23)).toBe('+48.2%');
    expect(changeText(-3)).toBe('-3.0%');
    expect(changeText('+48.2% today')).toBe('+48.2% today');
    expect(riskText(4.126)).toBe('4.1%');
    for (const v of [null, undefined, NaN, Infinity, '', {}]) { expect(changeText(v)).toBeNull(); expect(riskText(v)).toBeNull(); }
  });
  it("variant / grade: the served label wins, else Ajay's word (DECISIONS); NEGATIVE unknown → null", () => {
    expect(variantText({ variant: 'long_flag' } as any)).toBe('long flag');
    expect(variantText({ variant: 'near_kiss' } as any)).toBe('near-kiss');
    expect(variantText({ variant: 'long_flag', variant_label: 'long flag (4 bars)' } as any)).toBe('long flag (4 bars)');
    expect(gradeText({ grade: 'B' } as any)).toBe('B — imperfect');
    expect(variantText({ variant: 'other' } as any)).toBeNull();
    expect(gradeText({ grade: 'C' } as any)).toBeNull();
    expect(variantText(null)).toBeNull();
    expect(Object.keys(GG_VARIANT_LABEL).sort()).toEqual(['long_flag', 'near_kiss']);
    expect(GG_GRADE_LABEL).toEqual({ B: 'B — imperfect' });
  });
  it('playbookItem: S8/S9 timestamp tag, served pill, raw code when no label; NEGATIVE no pill when none served', () => {
    expect(playbookItem({ text: 'x', ts: '14:41', source: 'S8', status_label: 'his words' })).toEqual({ text: 'x', tag: 'S8 14:41', pill: 'his words' });
    expect(playbookItem({ text: 'x', status: 'confirmed_multi_source' }).pill).toBe('confirmed_multi_source');
    expect(playbookItem({ text: 'x', sources: [{ key: 'S9', ts: '1:59:24' }, { key: 'S3' }] }).tag).toBe('S9 1:59:24 · S3');
    expect(playbookItem({ text: 'x' })).toEqual({ text: 'x', tag: null, pill: null });
    expect(playbookItem('plain')).toEqual({ text: 'plain', tag: null, pill: null });
  });
});

describe('GG_SUBS / GG_OUTER_CHIPS', () => {
  // WIDENED 2026-10-15 — Ajay "So create a potential category in this section": 🧠 Potential is the NINTH sub,
  // LAST (BUILD_SPEC4 §3.1, HIS CALL P8); the other eight keep their DECISIONS order.
  it('nine subs in DECISIONS order, 🧠 Potential last, labels his', () => {
    expect(GG_SUBS.map((s) => s.key)).toEqual(['bull_flag', 'kiss_fly', 'horizontal_fade', 'intraday_vcp',
      'reversal_squeeze', 'premarket', 'postmarket', 'playbook', 'potential']);
    expect(GG_SUBS.map((s) => `${s.emoji} ${s.label}`).join(' · ')).toBe(
      '\u{1F6A9} Bull Flag · \u{1F48B} EMA Kiss & Fly · ➖ Horizontal Fade · \u{1F300} Intraday VCP · '
      + '\u{1F3BE} Reversal Squeeze · ☀️ Premarket · \u{1F319} Post-market · \u{1F4D3} Playbook · \u{1F9E0} Potential');
    expect(parseGgSub('potential')).toBe('potential');
    expect(parseGgSub(' Potential ')).toBe('potential');
  });
  it('GG_SETUPS == backend constants.SETUPS; NEGATIVE ☀️ / 🌙 / 📓 / 🧠 are not setups', async () => {
    const py = await readSource('../backend/chart_maps/gajjala/constants.py');
    const m = /^SETUPS = \(([^)]*)\)/m.exec(py);
    expect(m, 'constants.SETUPS').toBeTruthy();
    expect([...m![1].matchAll(/"([a-z_]+)"/g)].map((x) => x[1])).toEqual([...GG_SETUPS]);
    for (const s of GG_SETUPS) expect(isGgSetup(s)).toBe(true);
    for (const s of ['premarket', 'postmarket', 'playbook', 'potential', '', null, undefined, 'Bull_Flag']) {
      expect(isGgSetup(s), String(s)).toBe(false);
    }
  });
  it('== backend constants.SUBS (key / emoji / label, in order)', async () => {
    const py = await readSource('../backend/chart_maps/gajjala/constants.py');
    const m = /^SUBS = \(([\s\S]*?)\)\n/m.exec(py);
    expect(m, 'constants.SUBS').toBeTruthy();
    const triples = [...m![1].matchAll(/\(\s*"([a-z_]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)/g)].map((x) => [x[1], x[2], x[3]]);
    expect(triples).toEqual(GG_SUBS.map((s) => [s.key, s.emoji, s.label]));
  });
  it('the head row prints the four house chips', () => {
    expect([...GG_OUTER_CHIPS].sort()).toEqual(['enterable', 'explosive', 'growth', 'short']);
  });
  it('NEGATIVE: the lib composes no rule number and never says bounce', async () => {
    const src = await readSource('src/lib/gajjala.ts');
    expect(src).not.toMatch(/bounce/i);
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    expect(code).not.toMatch(/1_000_000|\b0\.10\b|\b25(\.0)?\b|K8_|K1_/);
  });
});

/* 🧠 Potential plumbing (2026-10-15) — Ajay: "In all the sub tab and add a track and alert to show me new potential
 * is added everyday." The served links and the 👀 watch line; the negatives keep a foreign link off the tab. */
describe('ggHref / watchParts', () => {
  it('ggHref passes a same-origin path; NEGATIVE protocol-relative, absolute, junk → null', () => {
    expect(ggHref('/chart-maps?tab=gajjala&sub=bull_flag&focus=AAA')).toBe('/chart-maps?tab=gajjala&sub=bull_flag&focus=AAA');
    for (const v of ['//evil.example/x', 'https://evil.example/x', 'javascript:alert(1)', '', null, undefined, 3, {}]) {
      expect(ggHref(v), String(v)).toBeNull();
    }
  });
  it('watchParts cuts the served trailing names so they can be links', () => {
    const w = { text: '👀 On his watch list, no structure yet — (S8 13:21–14:34): PMX, CARY',
                symbols: [{ symbol: 'PMX', href: '/x' }, { symbol: 'CARY', href: '/y' }] };
    expect(watchParts(w)).toEqual({ lead: '👀 On his watch list, no structure yet — (S8 13:21–14:34): ', trailing: true });
  });
  it('NEGATIVE: names not at the end → the text is kept whole; empty / missing → null', () => {
    const w = { text: '👀 PMX, CARY are on his list', symbols: [{ symbol: 'PMX', href: '/x' }, { symbol: 'CARY', href: '/y' }] };
    expect(watchParts(w)).toEqual({ lead: w.text, trailing: false });
    expect(watchParts({ text: '👀 nothing', symbols: [] })).toEqual({ lead: '👀 nothing', trailing: false });
    for (const v of [null, undefined, { text: '', symbols: [] }, { text: '   ', symbols: [] }]) expect(watchParts(v as any)).toBeNull();
  });
});
