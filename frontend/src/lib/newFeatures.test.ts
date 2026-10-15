import { describe, it, expect } from 'vitest';
import { isRecent, NEW_FEATURES, NEW_WINDOW_DAYS } from './newFeatures';

/* newFeatures — the "what's new" registry + recency window (Ajay 2026-06-18:
   highlight each shipped feature until viewed). */

describe('isRecent', () => {
  const now = new Date('2026-06-18T12:00:00Z');

  it('is true inside the highlight window', () => {
    expect(isRecent('2026-06-18', now)).toBe(true);
    expect(isRecent('2026-06-17', now)).toBe(true);
    expect(isRecent('2026-05-25', now)).toBe(true);          // ~24d, < 30d
  });

  it('is false once the feature has aged past the window', () => {
    expect(isRecent('2026-01-01', now)).toBe(false);
    expect(isRecent('2026-05-01', now)).toBe(false);         // > 30d
  });

  it('is false for an unparseable date (never a crash)', () => {
    expect(isRecent('nope', now)).toBe(false);
    expect(isRecent('', now)).toBe(false);
  });

  it('window is the documented length', () => {
    expect(NEW_WINDOW_DAYS).toBe(30);
  });
});

describe('NEW_FEATURES registry', () => {
  it('every entry is well-formed (id, label, parseable date)', () => {
    expect(NEW_FEATURES.length).toBeGreaterThan(0);
    const ids = new Set<string>();
    for (const f of NEW_FEATURES) {
      expect(f.id).toBeTruthy();
      expect(f.label).toBeTruthy();
      expect(Number.isNaN(Date.parse(`${f.addedAt}T00:00:00`))).toBe(false);
      expect(ids.has(f.id)).toBe(false);                     // ids unique
      ids.add(f.id);
    }
  });
});

/* 🎢 🗺️ tape-burst ✨ entry (2026-10-14) — the numbers it types (burst rule, caps,
   window, cadence) are read from the engines here, so a change there fails this
   file instead of drifting on the served label (review 2026-10-14: the entry's
   comment said "contract-pinned" while no contract read it). */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

type TapeTruth = { win: number; dollars: number; oneSided: number; trades: number;
                   capHB: number; capCM: number; open: string; close: string; step: number };

async function tapeTruth(): Promise<TapeTruth> {
  const tape = await readSource('../backend/orderflow/tape.py');
  const tbk = await readSource('../backend/orderflow/tape_burst_kinds.py');
  const tf = await readSource('../backend/orderflow/trade_flash.py');
  const cron = await readSource('../backend/crontab');
  const num = (src: string, name: string) => {
    const m = new RegExp(`^${name} = ([0-9_.]+)`, 'm').exec(src);
    if (!m) throw new Error(`lost ${name}`);
    return Number(m[1].replace(/_/g, ''));
  };
  const hm = (name: string) => {
    const m = new RegExp(`^${name} = dtime\\((\\d+),\\s*(\\d+)\\)`, 'm').exec(tf);
    if (!m) throw new Error(`lost ${name}`);
    return `${m[1].padStart(2, '0')}:${m[2].padStart(2, '0')}`;
  };
  const lines = cron.split('\n').filter((l) => !/^\s*#/.test(l) && /sepa\.cli trade-flash-watch/.test(l));
  if (lines.length !== 1) throw new Error(`expected one trade-flash-watch line, found ${lines.length}`);
  const step = /^\S*\/(\d+)\s/.exec(lines[0].trim());
  if (!step) throw new Error('trade-flash-watch line has no minute step');
  return {
    win: num(tape, 'BURST_WINDOW_SEC'), dollars: num(tape, 'BURST_MIN_DOLLARS'),
    oneSided: num(tape, 'BURST_ONE_SIDED'), trades: num(tape, 'BURST_MIN_TRADES'),
    capHB: num(tbk, 'HIGHBETA_MAX_SYMBOLS'), capCM: num(tbk, 'CHARTMAPS_MAX_SYMBOLS'),
    open: hm('WATCH_OPEN_ET'), close: hm('WATCH_CLOSE_ET'), step: Number(step[1]),
  };
}

/** Every problem with the entry against the engines; [] = clean. PURE. */
function tapeEntryErrors(f: { route?: string; label: string } | undefined, t: TapeTruth): string[] {
  if (!f) return ['entry alerts-tape-bursts-2026-10-14 missing'];
  const d = f.label, errs: string[] = [];
  if (f.route !== '/alerts') errs.push(`route ${f.route}`);
  if (!d.includes('UNMEASURED')) errs.push('no UNMEASURED');
  if (!d.includes('ON for you')) errs.push('no "ON for you"');
  if (/bounc|fake/i.test(d)) errs.push('says bounce/fake');
  if (/shadow/i.test(d)) errs.push('says shadow — both kinds ring live');
  const pct = Math.round(t.oneSided * 100);
  for (const need of [`${t.win}-second window`, `$${t.dollars / 1000}K+`, `${pct}%+ of it on one side`,
                      `${t.trades}+ prints`, `${t.open}–${t.close} ET`, `Every ${t.step} minutes`]) {
    if (!d.includes(need)) errs.push(`missing "${need}"`);
  }
  for (const m of d.matchAll(/(\d+)-second/g)) if (Number(m[1]) !== t.win) errs.push(m[0]);
  for (const m of d.matchAll(/\$(\d+)K/g)) if (Number(m[1]) * 1000 !== t.dollars) errs.push(m[0]);
  for (const m of d.matchAll(/(\d+)%\+/g)) if (Number(m[1]) !== pct) errs.push(m[0]);
  for (const m of d.matchAll(/(\d+)\+ prints/g)) if (Number(m[1]) !== t.trades) errs.push(m[0]);
  for (const m of d.matchAll(/(\d\d:\d\d)–(\d\d:\d\d)/g)) if (m[1] !== t.open || m[2] !== t.close) errs.push(m[0]);
  for (const m of d.matchAll(/Every (\d+) minutes|(\d+)-minute/g)) if (Number(m[1] || m[2]) !== t.step) errs.push(m[0]);
  // Each kind's cap sits in its own sentence: 🎢 first, then 🗺️, then the burst rule.
  const iHB = d.indexOf('🎢 High-Beta tape burst watches'), iCM = d.indexOf('🗺️ Chart Maps tape burst watches');
  const iRule = d.indexOf('A burst is');
  if (iHB < 0 || iCM < iHB || iRule < iCM) errs.push('the two kinds\' sentences moved — cap check cannot place them');
  else {
    const caps = (s: string) => [...s.matchAll(/up to (\d+)/g)].map((m) => Number(m[1]));
    const hb = caps(d.slice(iHB, iCM)), cm = caps(d.slice(iCM, iRule));
    if (hb.length !== 1 || hb[0] !== t.capHB) errs.push(`🎢 cap ${hb} != ${t.capHB}`);
    if (cm.length !== 1 || cm[0] !== t.capCM) errs.push(`🗺️ cap ${cm} != ${t.capCM}`);
    if (caps(d.slice(0, iHB)).length || caps(d.slice(iRule)).length) errs.push('an "up to N" outside the two kinds\' sentences');
  }
  return errs;
}

describe('alerts-tape-bursts-2026-10-14 ✨ entry = the engines', () => {
  const entry = () => NEW_FEATURES.find((f) => f.id === 'alerts-tape-bursts-2026-10-14');

  it('every typed number equals tape.py / tape_burst_kinds.py / trade_flash.py / the crontab step', async () => {
    expect(tapeEntryErrors(entry(), await tapeTruth())).toEqual([]);
  });

  it('NEG: a drifted number, window, cap, cadence or word is caught', async () => {
    const t = await tapeTruth();
    const base = entry()!;
    const swaps: [string, string][] = [
      [`${t.win}-second`, '30-second'],
      [`$${t.dollars / 1000}K+`, '$90K+'],
      [`${Math.round(t.oneSided * 100)}%+`, '51%+'],
      [`${t.trades}+ prints`, '7+ prints'],
      [`${t.open}–${t.close} ET`, '08:00–18:00 ET'],
      [`Every ${t.step} minutes`, 'Every 15 minutes'],
      [`up to ${t.capHB}`, 'up to 400'],
      ['UNMEASURED', 'measured'],
      ['ON for you', 'on'],
    ];
    for (const [from, to] of swaps) {
      expect(base.label.includes(from), from).toBe(true);
      const bad = { ...base, label: base.label.replace(from, to) };
      expect(tapeEntryErrors(bad, t).length, `${from} → ${to}`).toBeGreaterThan(0);
    }
    expect(tapeEntryErrors({ ...base, label: `${base.label} A reversal or a bounce.` }, t).length).toBeGreaterThan(0);
    expect(tapeEntryErrors({ ...base, route: '/chart-maps' }, t).length).toBeGreaterThan(0);
    expect(tapeEntryErrors(undefined, t)).toEqual(['entry alerts-tape-bursts-2026-10-14 missing']);
  });

  it('NEG: the 🗺️ cap is checked on its own sentence, not the 🎢 one', async () => {
    const t = await tapeTruth();
    const base = entry()!;
    const iCM = base.label.indexOf('🗺️ Chart Maps tape burst watches');
    const bad = base.label.slice(0, iCM) + base.label.slice(iCM).replace(`up to ${t.capCM}`, 'up to 151');
    expect(tapeEntryErrors({ ...base, label: bad }, { ...t })).toContain(`🗺️ cap 151 != ${t.capCM}`);
  });
});
