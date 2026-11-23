/* 🏆 chip → jump to that win's replay at its peak — lib pins (2026-11-22, pwjump spec §3.3). Ajay 2026-11-22, verbatim:
 * "New feature when I click on this past winner tag take me to that video so change the date and focus me on that video
 * at that. time" · "past winner 11-18 +57%". NEGATIVES throughout. */
import { describe, expect, it } from 'vitest';
import { API } from './apiBase';
import {
  RP_CARD_PARAM, RP_FILE_RE, RP_REEL_PARAM, RP_WINNER_SUBS, rpCardKey, rpCardParam, rpDateParams, rpFindReel,
  rpJumpKey, rpJumpParams, rpJumpReel, rpOriginParams, rpPastWinItems, rpPlainClick, rpReelKey, rpSeekSeconds,
  rpSeekSrc, type RpJumpTarget,
} from './replays';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const VWAV_FILE = '2026-11-18_VWAV_45x.mp4';
const VWAV_ENTRY = { day: '2026-11-18', kind: 'single_day', close_gain_pct: 57.07, file: VWAV_FILE, sub: 'winners',
  text: '🏆 past winner 11-18 +57%' };
const VWAV_T: RpJumpTarget = { symbol: 'VWAV', day: '2026-11-18', sub: 'winners', file: VWAV_FILE,
  reel: `winners/${VWAV_FILE}` };
const src = (sub: string, file: string) => `/chart-maps/replays/winners/video/${sub}/${file}`;

describe('rpReelKey', () => {
  it('both 🏆 folders', () => {
    expect(rpReelKey('winners', VWAV_FILE)).toBe(`winners/${VWAV_FILE}`);
    expect(rpReelKey('multiday', '2026-04-22_AKAN_45x.mp4')).toBe('multiday/2026-04-22_AKAN_45x.mp4');
  });
  it('NEGATIVE: another folder, "..", a slash, a non-mp4, non-strings → ""', () => {
    expect(rpReelKey('phone', VWAV_FILE)).toBe('');
    expect(rpReelKey('..', VWAV_FILE)).toBe('');
    expect(rpReelKey('winners', '..')).toBe('');
    expect(rpReelKey('winners', '../x.mp4')).toBe('');
    expect(rpReelKey('winners', 'a/b.mp4')).toBe('');
    expect(rpReelKey('winners', '2026-11-18_VWAV_45x.mov')).toBe('');
    expect(rpReelKey(1, VWAV_FILE)).toBe('');
    expect(rpReelKey('winners', null)).toBe('');
    expect(rpReelKey(undefined, undefined)).toBe('');
  });
});

describe('rpPastWinItems', () => {
  it('the VWAV entry → its target; a multi-day entry → multiday/…', () => {
    const multi = { day: '2026-05-01', kind: 'multi_day', file: '2026-04-22_AKAN_45x.mp4', sub: 'multiday',
      text: '🏆 past winner 05-01 +1657% multi-day' };
    const out = rpPastWinItems({ symbol: 'VWAV', past_winner: [VWAV_ENTRY, multi] });
    expect(out).toEqual([
      { text: VWAV_ENTRY.text, target: VWAV_T },
      { text: multi.text, target: { symbol: 'VWAV', day: '2026-05-01', sub: 'multiday', file: multi.file,
        reel: 'multiday/2026-04-22_AKAN_45x.mp4' } },
    ]);
  });
  it('NEGATIVE: no sub / no file / a bad day / no symbol → target null with the text kept', () => {
    const { sub: _s, ...noSub } = VWAV_ENTRY;
    const { file: _f, ...noFile } = VWAV_ENTRY;
    const out = rpPastWinItems({ symbol: 'VWAV', past_winner: [noSub, noFile, { ...VWAV_ENTRY, day: '11-18' }] as any });
    expect(out.map((x) => x.target)).toEqual([null, null, null]);
    expect(out.map((x) => x.text)).toEqual([VWAV_ENTRY.text, VWAV_ENTRY.text, VWAV_ENTRY.text]);
    for (const symbol of [undefined, '', '  ', 7]) {
      const o = rpPastWinItems({ symbol, past_winner: [VWAV_ENTRY] } as any);
      expect(o).toEqual([{ text: VWAV_ENTRY.text, target: null }]);
    }
  });
  it('NEGATIVE: a blank / non-string text is dropped; no list → []', () => {
    expect(rpPastWinItems({ symbol: 'VWAV', past_winner: [{ ...VWAV_ENTRY, text: '' }, { ...VWAV_ENTRY, text: 5 }, null] as any }))
      .toEqual([]);
    expect(rpPastWinItems({ symbol: 'VWAV' })).toEqual([]);
    expect(rpPastWinItems(null)).toEqual([]);
    expect(rpPastWinItems(undefined)).toEqual([]);
  });
});

describe('rpJumpParams', () => {
  it('sets winners / sym / reel, deletes card, keeps tab and a stranger, sets date when listed', () => {
    const prev = new URLSearchParams('tab=replays&date=2026-11-20&card=2026-11-20%2Fx.mp4&zz=1');
    const next = rpJumpParams(prev, VWAV_T, ['2026-11-20', '2026-11-18']);
    expect(next.get('winners')).toBe('1');
    expect(next.get('sym')).toBe('VWAV');
    expect(next.get(RP_REEL_PARAM)).toBe(`winners/${VWAV_FILE}`);
    expect(next.has(RP_CARD_PARAM)).toBe(false);
    expect(next.get('tab')).toBe('replays');
    expect(next.get('zz')).toBe('1');
    expect(next.get('date')).toBe('2026-11-18');
    expect(next.toString()).toContain('reel=winners%2F2026-11-18_VWAV_45x.mp4');
  });
  it('NEGATIVE: an unlisted day leaves date exactly as it was (also when there was none); prev not mutated', () => {
    const prev = new URLSearchParams('tab=replays&date=2026-11-20');
    const before = prev.toString();
    expect(rpJumpParams(prev, VWAV_T, ['2026-11-20']).get('date')).toBe('2026-11-20');
    expect(prev.toString()).toBe(before);
    const none = rpJumpParams(new URLSearchParams('tab=replays'), VWAV_T, []);
    expect(none.has('date')).toBe(false);
  });
});

describe('rpOriginParams / rpCardKey / rpCardParam', () => {
  it('sets card, DELETES reel (C2), keeps winners / sym / date', () => {
    const prev = new URLSearchParams(`tab=replays&date=2026-11-20&winners=1&sym=AKAN&reel=multiday%2F2026-04-22_AKAN_45x.mp4`);
    const next = rpOriginParams(prev, '2026-11-20', 'VWAV_reversal_squeeze_potential_45x.mp4');
    expect(next.get(RP_CARD_PARAM)).toBe('2026-11-20/VWAV_reversal_squeeze_potential_45x.mp4');
    expect(next.has(RP_REEL_PARAM)).toBe(false);
    expect(next.get('winners')).toBe('1');
    expect(next.get('sym')).toBe('AKAN');
    expect(next.get('date')).toBe('2026-11-20');
    expect(prev.has(RP_REEL_PARAM)).toBe(true);                                   // prev not mutated
  });
  it('NEGATIVE: a null date / empty file → an unchanged copy (reel kept)', () => {
    const prev = new URLSearchParams('tab=replays&reel=winners%2Fx.mp4');
    for (const [d, f] of [[null, 'x.mp4'], ['', 'x.mp4'], ['2026-11-20', '']] as [string | null, string][]) {
      const next = rpOriginParams(prev, d, f);
      expect(next.toString()).toBe(prev.toString());
      expect(next).not.toBe(prev);
    }
  });
  it('rpCardKey / rpCardParam', () => {
    expect(rpCardKey('2026-11-20', 'a.mp4')).toBe('2026-11-20/a.mp4');
    for (const [d, f] of [[null, 'a.mp4'], ['2026-11-20', null], ['', 'a.mp4'], [1, 'a.mp4']]) expect(rpCardKey(d, f)).toBe('');
    expect(rpCardParam(new URLSearchParams('card=2026-11-20%2Fa.mp4'))).toBe('2026-11-20/a.mp4');
    expect(rpCardParam(new URLSearchParams('tab=replays'))).toBe('');
  });
});

describe('rpDateParams (C9)', () => {
  it('card deleted on a set AND on a clear; reel kept; tab kept; prev not mutated', () => {
    const prev = new URLSearchParams('tab=replays&date=2026-11-20&card=2026-11-20%2Fa.mp4&reel=winners%2Fx.mp4');
    const before = prev.toString();
    for (const d of ['2026-11-17', null, '']) {
      const next = rpDateParams(prev, d);
      expect(next.has(RP_CARD_PARAM)).toBe(false);
      expect(next.get(RP_REEL_PARAM)).toBe('winners/x.mp4');
      expect(next.get('tab')).toBe('replays');
    }
    expect(rpDateParams(prev, '2026-11-17').get('date')).toBe('2026-11-17');
    expect(rpDateParams(prev, null).has('date')).toBe(false);
    expect(prev.toString()).toBe(before);
  });
});

describe('rpJumpReel / rpJumpKey', () => {
  it('a valid reel param', () => {
    expect(rpJumpReel(new URLSearchParams(`reel=winners%2F${VWAV_FILE}`))).toBe(`winners/${VWAV_FILE}`);
    expect(rpJumpReel(new URLSearchParams(`reel=multiday/2026-04-22_AKAN_45x.mp4`))).toBe('multiday/2026-04-22_AKAN_45x.mp4');
  });
  it('NEGATIVE: "..", another folder, two slashes, empty, absent → ""', () => {
    for (const r of ['winners/../x.mp4', 'phone/x.mp4', 'winners/a/b.mp4', '', 'winners', `/winners/${VWAV_FILE}`]) {
      expect(rpJumpReel(new URLSearchParams({ reel: r }))).toBe('');
    }
    expect(rpJumpReel(new URLSearchParams('tab=replays'))).toBe('');
  });
  it('C1: "" reel → "" for any n; same reel, n 1 vs 2 → different keys', () => {
    for (const n of [0, 1, 2, 99]) expect(rpJumpKey('', n)).toBe('');
    const r = `winners/${VWAV_FILE}`;
    expect(rpJumpKey(r, 1)).not.toBe(rpJumpKey(r, 2));
    expect(rpJumpKey(r, 1)).toBe(rpJumpKey(r, 1));
    expect(rpJumpKey(r, 1)).not.toBe(rpJumpKey('winners/other.mp4', 1));
  });
});

describe('rpFindReel', () => {
  const vw = { file: VWAV_FILE, sub: 'winners', src: src('winners', VWAV_FILE), symbol: 'VWAV', seek_s: 952.05 };
  const ak = { file: '2026-11-18_AKAN_45x.mp4', sub: 'winners', src: src('winners', '2026-11-18_AKAN_45x.mp4'), symbol: 'AKAN' };
  const rows = [{ symbol: 'AKAN', videos: [ak] }, { symbol: 'VWAV', videos: [vw] }];
  it('the exact reel inside the sym row; a served "Abc" is found by "ABC" (OC-c)', () => {
    const hit = rpFindReel(rows, 'VWAV', `winners/${VWAV_FILE}`);
    expect(hit && hit.video).toBe(vw);
    expect(hit && hit.row).toBe(rows[1]);
    const abc = { file: '2026-11-18_Abc_45x.mp4', sub: 'winners', src: src('winners', '2026-11-18_Abc_45x.mp4'), symbol: 'Abc' };
    const r2 = [{ symbol: 'Abc', videos: [abc] }];
    expect(rpFindReel(r2, 'ABC', 'winners/2026-11-18_Abc_45x.mp4')!.video).toBe(abc);
  });
  it('NEGATIVE: the right reel under the WRONG sym, a wrong date, a src off the 🏆 route, blanks, junk → null', () => {
    expect(rpFindReel(rows, 'AKAN', `winners/${VWAV_FILE}`)).toBeNull();
    expect(rpFindReel(rows, 'VWAV', 'winners/2026-11-19_VWAV_45x.mp4')).toBeNull();
    expect(rpFindReel(rows, 'VWAV', `multiday/${VWAV_FILE}`)).toBeNull();
    const off = [{ symbol: 'VWAV', videos: [{ ...vw, src: '/chart-maps/replays/video/2026-11-18/x.mp4' }] }];
    expect(rpFindReel(off, 'VWAV', `winners/${VWAV_FILE}`)).toBeNull();
    expect(rpFindReel(rows, '', `winners/${VWAV_FILE}`)).toBeNull();
    expect(rpFindReel(rows, 'VWAV', '')).toBeNull();
    expect(rpFindReel(null, 'VWAV', `winners/${VWAV_FILE}`)).toBeNull();
    expect(rpFindReel([null, { symbol: 5 }, { symbol: 'VWAV', videos: 'x' }], 'VWAV', `winners/${VWAV_FILE}`)).toBeNull();
  });
});

describe('rpSeekSeconds / rpSeekSrc / rpPlainClick', () => {
  it('the served second; NEGATIVE: null, 0, −1, NaN, Infinity, "952" → null', () => {
    expect(rpSeekSeconds({ seek_s: 952.05 })).toBe(952.05);
    for (const s of [null, undefined, 0, -1, NaN, Infinity, '952']) expect(rpSeekSeconds({ seek_s: s })).toBeNull();
    expect(rpSeekSeconds(null)).toBeNull();
  });
  it('rpSeekSrc: `#t=` with a second; NEGATIVE: null → the src itself; no src → ""', () => {
    const s = `${API}${src('winners', VWAV_FILE)}`;
    expect(rpSeekSrc(s, 952.05)).toBe(`${s}#t=952.05`);
    expect(rpSeekSrc(s, null)).toBe(s);
    expect(rpSeekSrc('', 952.05)).toBe('');
  });
  it('rpPlainClick: a plain click; NEGATIVE: meta / ctrl / shift / alt / button 1 → false', () => {
    expect(rpPlainClick({ button: 0 })).toBe(true);
    expect(rpPlainClick({})).toBe(true);
    for (const e of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }, { button: 2 }]) {
      expect(rpPlainClick({ button: 0, ...e })).toBe(false);
    }
  });
});

describe('parity with the backend + source guards', () => {
  it('RP_WINNER_SUBS and RP_FILE_RE equal backend constants.py', async () => {
    const py = await readSource('../backend/chart_maps/replays/constants.py');
    const re = /^FILE_RE = re\.compile\(r"([^"]+)"\)/m.exec(py);
    expect(re && re[1]).toBe(RP_FILE_RE.source);
    const subs = /^WINNER_SUBS = \(([^\n]+)\)/m.exec(py);
    const keys = subs ? [...subs[1].matchAll(/\(\s*"([^"]+)",/g)].map((m) => m[1]) : [];
    expect(keys).toEqual([...RP_WINNER_SUBS]);
    expect(/^WINNER_SUB_KEYS = tuple\(s for s, _k, _t in WINNER_SUBS\)$/m.test(py)).toBe(true);
  });
  it('NEGATIVE: lib/replays.ts types no window literal and no clock arithmetic', async () => {
    const ts = await readSource('src/lib/replays.ts');
    expect(ts).not.toContain('04:00-20:00');
    expect(ts).not.toMatch(/\*\s*60\b/);
    expect(ts).not.toMatch(/\/\s*45\b/);
  });
});
