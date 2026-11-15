import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/longTerm.payload.json';
import { ltSavedRows, type LtLiveQuote, type LtPayload, type LtZone, type LtZoneBand, type LtZoneRules } from './longTerm';
import type { LtLive } from '../hooks/useLtToday';
import {
  LT_ZONE_DEFAULT, LT_ZONE_LS_KEY, loadLtZoneFilter, ltBandState, ltLevelKey, ltMmdd, ltZoneBandsFor, ltZoneCellText,
  ltZoneEffective, ltZonePartition, ltZonePrice, ltZoneRead, saveLtZoneFilter, type LtZoneFilter, type LtZoneRead,
} from './ltZones';

/* 🎯 Enterable (zones) — the pure half (2026-11-14, ltenter spec §3.5 / §3.6). Ajay 2026-11-14: "Make a enterable check
 * box in longterm stocks with zone and filters please". The FE read is a transliteration of backend zones.read over
 * pankaj_picks.setup_status; the §3.6 case table is pinned on BOTH sides and every fixture row's served close read is
 * re-derived here byte for byte. NEGATIVES throughout. */

const P = (): LtPayload => JSON.parse(JSON.stringify(fixture)) as LtPayload;
const RULES = (): LtZoneRules => P().zone_rules as LtZoneRules;
const W = RULES().words;
const ON: LtZoneFilter = { ...LT_ZONE_DEFAULT, on: true };
const pk = (key: string, lo: number, hi: number): LtZoneBand => ({ source: 'pankaj', key, level: key, label: `Pankaj ${key}`, lo, hi });
const gb = (key: string, lo: number, hi: number, level = key): LtZoneBand => ({ source: 'gabbar', key, level, label: `Gabbar ${key}`, lo, hi });
const Z = (bands: LtZoneBand[]): LtZone => ({ bands, gabbar_text: null, close: null });
const close = (price: number) => ({ price, basis: 'close' as const, at: '2026-11-13' });
const rowZone = (sym: string): LtZone => ltSavedRows(P()).find((r) => r.symbol === sym)!.zone as LtZone;

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

/** An in-memory store (the emaFrames / kiss_rvol precedent — this jsdom build has no usable localStorage). */
function mem() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
           removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear() };
}
beforeEach(() => { vi.stubGlobal('localStorage', mem()); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

/* §3.6 — the shared case table (no .x5 ties). */
type Case = { name: string; bands: LtZoneBand[]; price: number | null; state: string; pct: number | null; enterable: boolean | null; band?: number };
const CASES: Case[] = [
  { name: 'VRT inside C1', bands: [pk('C1', 195, 205)], price: 200.0, state: 'inside', pct: 0.0, enterable: true, band: 0 },
  { name: 'pad edge, 0.4% above hi', bands: [pk('C1', 100, 110)], price: 110.44, state: 'inside', pct: 0.0, enterable: true, band: 0 },
  { name: '0.6% above hi', bands: [pk('C1', 100, 110)], price: 110.66, state: 'near', pct: 0.6, enterable: true, band: 0 },
  { name: '1.0% above hi', bands: [pk('C1', 100, 110)], price: 111.1, state: 'near', pct: 1.0, enterable: true, band: 0 },
  { name: 'META 1.9% above C1', bands: [pk('C1', 620, 630)], price: 641.97, state: 'above', pct: 1.9, enterable: false, band: 0 },
  { name: 'NFLX 3.6% above Gabbar cons.2', bands: [gb('conservative 2', 55, 60, 'conservative 2+')], price: 62.16, state: 'above', pct: 3.6, enterable: false, band: 0 },
  { name: 'pad edge, 0.4% under lo', bands: [pk('C1', 100, 110)], price: 99.6, state: 'inside', pct: 0.0, enterable: true, band: 0 },
  { name: '0.6% under lo (fell through)', bands: [pk('C1', 100, 110)], price: 99.4, state: 'below', pct: -0.6, enterable: false, band: 0 },
  { name: 'GOOGL 4.6% under C1', bands: [pk('C1', 310, 315)], price: 295.74, state: 'below', pct: -4.6, enterable: false, band: 0 },
  { name: 'BKNG Gabbar aggressive ÷25', bands: [gb('aggressive', 148, 156)], price: 150.0, state: 'inside', pct: 0.0, enterable: true, band: 0 },
  { name: 'price null', bands: [pk('C1', 195, 205)], price: null, state: 'no_price', pct: null, enterable: null },
  { name: 'no bands', bands: [], price: 200.0, state: 'no_zone', pct: null, enterable: null },
  { name: 'two bands, inside the second', bands: [pk('Agg', 100, 110), pk('C1', 120, 130)], price: 125.0, state: 'inside', pct: 0.0, enterable: true, band: 1 },
  { name: 'two bands, 0.8% above band 1, band 2 far', bands: [pk('Agg', 100, 110), pk('C1', 150, 160)], price: 110.88, state: 'near', pct: 0.8, enterable: true, band: 0 },
  { name: 'two bands, 2.0% above band 1, 1.0% under band 2', bands: [pk('Agg', 100, 110), pk('C1', 113.33, 120)], price: 112.2, state: 'below', pct: -1.0, enterable: false, band: 1 },
];

describe('🎯 ltZoneRead — the §3.6 case table (pinned on both sides)', () => {
  for (const c of CASES) {
    it(c.name, () => {
      const r = ltZoneRead(Z(c.bands), c.price === null ? null : close(c.price), RULES(), LT_ZONE_DEFAULT);
      expect(r.state).toBe(c.state);
      expect(r.pct).toBe(c.pct);
      expect(r.enterable).toBe(c.enterable);
      expect(r.band).toBe(c.band === undefined ? null : c.bands[c.band]);
    });
  }
  it('ltBandState: in / above / below with the served pad', () => {
    expect(ltBandState(pk('C1', 100, 110), 110.44, 0.5)).toEqual({ st: 'in', pct: 0 });
    expect(ltBandState(pk('C1', 100, 110), 110.66, 0.5)).toEqual({ st: 'above', pct: 0.6 });
    expect(ltBandState(pk('C1', 100, 110), 99.4, 0.5)).toEqual({ st: 'below', pct: -0.6 });
  });
  it('NEGATIVE: fell through the bottom → below, not enterable; 1.9% over the top → above, not enterable', () => {
    expect(ltZoneRead(Z([pk('C1', 100, 110)]), close(99.4), RULES(), ON)).toMatchObject({ state: 'below', enterable: false, reason: 'below' });
    expect(ltZoneRead(Z([pk('C1', 620, 630)]), close(641.97), RULES(), ON)).toMatchObject({ state: 'above', enterable: false, reason: 'above' });
  });
  it('NEGATIVE: no price → no_price (enterable null); no bands → no_zone even with no price (the order)', () => {
    expect(ltZoneRead(Z([pk('C1', 1, 2)]), null, RULES(), ON)).toMatchObject({ state: 'no_price', enterable: null, band: null, pct: null, reason: 'no_price' });
    expect(ltZoneRead(Z([]), null, RULES(), ON)).toMatchObject({ state: 'no_zone', enterable: null, reason: 'no_zone' });
    expect(ltZoneRead(null, close(5), RULES(), ON)).toMatchObject({ state: 'no_zone', enterable: null });
  });
  it('NEGATIVE: the proximity is the SERVED number — a served 3.0 makes the 1.9% case near (never typed FE-side)', () => {
    const r = { ...RULES(), above_pct: 3.0 };
    expect(ltZoneRead(Z([pk('C1', 620, 630)]), close(641.97), r, ON).state).toBe('near');
    expect(ltZoneRead(Z([pk('C1', 620, 630)]), close(641.97), RULES(), ON).state).toBe('above');
  });
});

describe('🎯 filters — source / level / OFF = unfiltered', () => {
  const amd = () => rowZone('AMD');
  it('a Gabbar-only name under source pankaj → filtered, enterable null', () => {
    const r = ltZoneRead(amd(), close(185), RULES(), { ...ON, source: 'pankaj' });
    expect(r).toMatchObject({ state: 'filtered', enterable: null, reason: 'filtered' });
  });
  it('level conservative 2+ reads only the deep bands: AMD 115 → inside conservative 2 (110–120)', () => {
    const f = { ...ON, levels: ['gabbar:conservative 2+'] };
    expect(ltZoneBandsFor(amd(), f).map((b) => b.key)).toEqual(['conservative 2', 'conservative 3']);
    const r = ltZoneRead(amd(), close(115), RULES(), f);
    expect(r.state).toBe('inside');
    expect(r.band!.key).toBe('conservative 2');
  });
  it('NEGATIVE: AMD 185 under the deep level → above +54.2, not enterable — the unselected aggressive band never reads inside', () => {
    const f = { ...ON, levels: ['gabbar:conservative 2+'] };
    const r = ltZoneRead(amd(), close(185), RULES(), f);
    expect(r).toMatchObject({ state: 'above', pct: 54.2, enterable: false });
    expect(ltZoneRead(amd(), close(185), RULES(), ON).state).toBe('inside');
  });
  it('ltZoneEffective: OFF → the default; NEGATIVE: a saved source gabbar does not make TSM "filtered" while OFF', () => {
    const off: LtZoneFilter = { on: false, source: 'gabbar', levels: ['gabbar:aggressive'], unhide: ['below'] };
    expect(ltZoneEffective(off)).toBe(LT_ZONE_DEFAULT);
    const tsm = rowZone('TSM');
    const r = ltZoneRead(tsm, close(405.49), RULES(), ltZoneEffective(off));
    expect(r.state).toBe('inside');
    expect(ltZoneCellText(r, W)).toBe('inside Pankaj Agg 400–410 · close 11-13');
    expect(ltZoneRead(tsm, close(405.49), RULES(), ltZoneEffective({ ...off, on: true })).state).toBe('filtered');
  });
  it('ltLevelKey composes source:level', () => {
    expect(ltLevelKey({ source: 'gabbar', level: 'conservative 2+' })).toBe('gabbar:conservative 2+');
  });
});

describe('🎯 ltZonePrice — live only when the house flags the print', () => {
  const DAY = '2026-11-14';
  const bar = (t: string, c: number) => ({ t, c });
  const q = (now: LtLiveQuote['now'], b = bar(DAY, 110), prev = bar('2026-11-13', 100)): LtLiveQuote => ({ bar: b, prev_bar: prev, now });
  const L = (session: string | null | undefined, quotes: Record<string, LtLiveQuote> = {}): LtLive => (
    session === undefined ? { as_of: `${DAY} 10:31:05 ET`, quotes } : { as_of: `${DAY} 10:31:05 ET`, session, quotes });
  const zone = rowZone('TSM');
  it('rth + add_line true + a price → live at the quote\'s own as_of', () => {
    expect(ltZonePrice(q({ price: 171.36, add_line: true, as_of: '10:31:04 ET' }), L('rth'), zone))
      .toEqual({ price: 171.36, basis: 'live', at: '10:31:04 ET' });
  });
  it('rth + add_line true, no now.as_of → the answer stamp\'s time part (never the full stamp)', () => {
    expect(ltZonePrice(q({ price: 171.36, add_line: true, as_of: null }), L('rth'), zone))
      .toEqual({ price: 171.36, basis: 'live', at: '10:31:05 ET' });
  });
  it('NEGATIVE: a carried print (add_line false) is NOT live → the closed bar (prev_bar while today\'s bar forms)', () => {
    expect(ltZonePrice(q({ price: 171.36, add_line: false, as_of: null }), L('premarket'), zone))
      .toEqual({ price: 100, basis: 'close', at: '2026-11-13' });
  });
  it('closed session + today\'s bar → that bar is the close', () => {
    expect(ltZonePrice(q({ price: 111, add_line: true }), L('closed'), zone)).toEqual({ price: 110, basis: 'close', at: DAY });
  });
  it('premarket with no now → prev_bar', () => {
    expect(ltZonePrice(q(null), L('premarket'), zone)).toEqual({ price: 100, basis: 'close', at: '2026-11-13' });
  });
  it('no session key → counted closed (bar), never live', () => {
    expect(ltZonePrice(q({ price: 111, add_line: true }), L(undefined), zone)).toEqual({ price: 110, basis: 'close', at: DAY });
  });
  it('no quote / no live answer → the served zone.close', () => {
    expect(ltZonePrice(undefined, L('rth'), zone)).toEqual({ price: 405.49, basis: 'close', at: '2026-11-13' });
    expect(ltZonePrice(undefined, null, zone)).toEqual({ price: 405.49, basis: 'close', at: '2026-11-13' });
  });
  it('NEGATIVE: NaN / 0 prices fall to the next rule; nothing at all → null', () => {
    expect(ltZonePrice(q({ price: Number.NaN, add_line: true }), L('rth'), zone)).toEqual({ price: 100, basis: 'close', at: '2026-11-13' });
    expect(ltZonePrice(q({ price: 0, add_line: true }, bar(DAY, 0), bar('2026-11-13', 0)), L('rth'), zone))
      .toEqual({ price: 405.49, basis: 'close', at: '2026-11-13' });
    expect(ltZonePrice(undefined, null, rowZone('XPEL'))).toBeNull();
    expect(ltZonePrice(undefined, null, null)).toBeNull();
  });
});

describe('🎯 ltMmdd mirrors words.mmdd', () => {
  it('ISO → MM-DD; short string as is; none → the served dash', () => {
    expect(ltMmdd('2026-11-13', '—')).toBe('11-13');
    expect(ltMmdd(null, '—')).toBe('—');
    expect(ltMmdd('11-13', '—')).toBe('11-13');
    expect(W.dash).toBe('—');
  });
});

describe('🎯 cross-pin — the FE read equals every fixture row\'s served close read, byte for byte', () => {
  const rows = ltSavedRows(P());
  it('every saved fixture row carries a zone block', () => {
    for (const r of rows) expect(r.zone, r.symbol).toBeTruthy();
  });
  for (const r of ltSavedRows(P())) {
    it(`${r.symbol}: state, enterable, pct, band.key and the cell text`, () => {
      const z = r.zone as LtZone;
      const c = z.close!;
      const px = typeof c.price === 'number' ? { price: c.price, basis: 'close' as const, at: c.date } : null;
      const read = ltZoneRead(z, px, RULES(), LT_ZONE_DEFAULT);
      expect(read.state).toBe(c.state);
      expect(read.enterable).toBe(c.enterable);
      expect(read.pct).toBe(c.pct);
      expect(read.band?.key ?? null).toBe(c.band?.key ?? null);
      expect(ltZoneCellText(read, W)).toBe(c.text);
    });
  }
  it('the live basis composes the same shape with the served live word (TSM +1.0% over Agg → just above)', () => {
    const read = ltZoneRead(rowZone('TSM'), { price: 414.1, basis: 'live', at: '10:31:05 ET' }, RULES(), LT_ZONE_DEFAULT);
    expect(ltZoneCellText(read, W)).toBe('just above Pankaj Agg 400–410 · +1.0% · live 10:31:05 ET');
  });
  it('NVDA 171.36 is 0.8% over C2\'s top but INSIDE C1 170–175 (the first band it sits in wins — never "just above")', () => {
    const read = ltZoneRead(rowZone('NVDA'), { price: 171.36, basis: 'live', at: '10:31:05 ET' }, RULES(), LT_ZONE_DEFAULT);
    expect(ltZoneCellText(read, W)).toBe('inside Pankaj C1 170–175 · live 10:31:05 ET');
    const c2only = ltZoneRead({ ...rowZone('NVDA'), bands: [rowZone('NVDA').bands[2]] }, { price: 171.36, basis: 'live', at: '10:31:05 ET' }, RULES(), LT_ZONE_DEFAULT);
    expect(ltZoneCellText(c2only, W)).toBe('just above Pankaj C2 160–170 · +0.8% · live 10:31:05 ET');
  });
  it('no_zone / no_price / filtered print their served word only', () => {
    const base: LtZoneRead = { state: 'no_zone', enterable: null, band: null, pct: null, basis: null, at: null, reason: 'no_zone' };
    expect(ltZoneCellText(base, W)).toBe(W.no_zone);
    expect(ltZoneCellText({ ...base, state: 'no_price' }, W)).toBe(W.no_price);
    expect(ltZoneCellText({ ...base, state: 'filtered' }, W)).toBe(W.filtered);
  });
});

describe('🎯 ltZonePartition — a stable partition, never a sort', () => {
  const rows = () => ltSavedRows(P());
  const reads = () => new Map(rows().map((r) => {
    const z = r.zone as LtZone;
    const c = z.close!;
    const px = typeof c.price === 'number' ? { price: c.price, basis: 'close' as const, at: c.date } : null;
    return [r.symbol.toUpperCase(), ltZoneRead(z, px, RULES(), LT_ZONE_DEFAULT)] as const;
  }));
  it('OFF → every symbol shown, nothing hidden, no reasons', () => {
    const p = ltZonePartition(rows(), reads(), LT_ZONE_DEFAULT, RULES());
    expect([...p.shown]).toEqual(rows().map((r) => r.symbol));
    expect(p).toMatchObject({ hidden: 0, unhidden: 0, reasons: [] });
  });
  it('ON → enterable rows shown; counts per served reason; every served reason listed (zeros too)', () => {
    const p = ltZonePartition(rows(), reads(), ON, RULES());
    expect([...p.shown]).toEqual(['AMD', 'NVDA', 'TSM']);
    expect(p.hidden).toBe(5);
    const by = Object.fromEntries(p.reasons.map((r) => [r.code, r.baseline]));
    expect(by).toEqual({ no_zone: 3, above: 1, no_price: 1, below: 0, filtered: 0 });
    expect(p.reasons.map((r) => r.code).sort()).toEqual(RULES().reasons.map((r) => r.code).sort());
    expect(p.reasons.reduce((a, r) => a + r.hidden, 0)).toBe(p.hidden);
    expect(p.reasons[0].code).toBe('no_zone');
    expect(p.reasons.map((r) => r.label)).toEqual(p.reasons.map((r) => RULES().reasons.find((x) => x.code === r.code)!.label));
  });
  it('un-hiding a reason brings back exactly that code; the order key (baseline) does not move', () => {
    const before = ltZonePartition(rows(), reads(), ON, RULES());
    const p = ltZonePartition(rows(), reads(), { ...ON, unhide: ['no_zone'] }, RULES());
    expect([...p.shown]).toEqual(['MANH', 'AMD', 'FIGS', 'NVDA', 'MPWR', 'TSM']);
    expect(p.hidden).toBe(2);
    expect(p.unhidden).toBe(3);
    const nz = p.reasons.find((r) => r.code === 'no_zone')!;
    expect(nz).toMatchObject({ baseline: 3, hidden: 0, ignored: true });
    expect(p.reasons.map((r) => r.code)).toEqual(before.reasons.map((r) => r.code));
  });
  it('NEGATIVE: for 50 random filters the shown rows are a SUBSEQUENCE of the saved order', () => {
    const order = rows().map((r) => r.symbol);
    const codes = RULES().reasons.map((r) => r.code);
    const levels = RULES().levels.map((l) => ltLevelKey({ source: l.source, level: l.key }));
    let seed = 7;
    const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    for (let i = 0; i < 50; i += 1) {
      const f: LtZoneFilter = {
        on: rnd() > 0.2, source: (['both', 'pankaj', 'gabbar'] as const)[Math.floor(rnd() * 3)],
        levels: levels.filter(() => rnd() > 0.6), unhide: codes.filter(() => rnd() > 0.6),
      };
      const m = new Map(rows().map((r) => [r.symbol, ltZoneRead(r.zone, ltZonePrice(undefined, null, r.zone), RULES(), ltZoneEffective(f))] as const));
      const shown = [...ltZonePartition(rows(), m, f, RULES()).shown];
      expect(shown).toEqual(order.filter((s) => shown.includes(s)));
    }
  });
});

describe('🎯 load / save — per viewer, in try/catch', () => {
  const LV = new Set(['pankaj:Agg', 'gabbar:conservative 2+']);
  const RS = new Set(['below', 'no_zone']);
  it('the key literal equals backend constants.ZONE_FILTER_LS_KEY', async () => {
    expect(LT_ZONE_LS_KEY).toBe('lt_zone_filter_v1');
    const src = await readSource('../backend/long_term_list/constants.py');
    expect(/^ZONE_FILTER_LS_KEY = "([^"]+)"/m.exec(src)?.[1]).toBe(LT_ZONE_LS_KEY);
    expect(RULES().ls_key).toBe(LT_ZONE_LS_KEY);
  });
  it('round-trips', () => {
    const f: LtZoneFilter = { on: true, source: 'gabbar', levels: ['gabbar:conservative 2+'], unhide: ['no_zone'] };
    saveLtZoneFilter(f);
    expect(loadLtZoneFilter(LV, RS)).toEqual(f);
  });
  it('nothing stored → the default (OFF)', () => {
    expect(loadLtZoneFilter(LV, RS)).toEqual(LT_ZONE_DEFAULT);
  });
  it('NEGATIVE: garbage JSON / a non-object → default; unknown level / reason / source keys dropped', () => {
    window.localStorage.setItem(LT_ZONE_LS_KEY, '{nope');
    expect(loadLtZoneFilter(LV, RS)).toEqual(LT_ZONE_DEFAULT);
    window.localStorage.setItem(LT_ZONE_LS_KEY, '[1,2]');
    expect(loadLtZoneFilter(LV, RS)).toEqual(LT_ZONE_DEFAULT);
    window.localStorage.setItem(LT_ZONE_LS_KEY, JSON.stringify({ on: 'yes', source: 'tv', levels: ['pankaj:Agg', 'x:y', 4], unhide: ['below', 'gone'] }));
    expect(loadLtZoneFilter(LV, RS)).toEqual({ on: false, source: 'both', levels: ['pankaj:Agg'], unhide: ['below'] });
  });
  it('NEGATIVE: storage throwing on get AND on set → default, never a throw', () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } });
    expect(() => saveLtZoneFilter({ ...ON })).not.toThrow();
    expect(loadLtZoneFilter(LV, RS)).toEqual(LT_ZONE_DEFAULT);
  });
  it('source guard: ltZones.ts wraps storage in try/catch (≥ 2 try blocks) and carries no buy/sell vocabulary', async () => {
    const src = await readSource('src/lib/ltZones.ts');
    expect((src.match(/try \{/g) || []).length).toBeGreaterThanOrEqual(2);
    expect(src).not.toMatch(/\b(buy|buying|bought|sell|selling|sold|entry|entries|exit|exits)\b/i);
    expect(src).not.toMatch(/\bbounce\b/i);
  });
});
