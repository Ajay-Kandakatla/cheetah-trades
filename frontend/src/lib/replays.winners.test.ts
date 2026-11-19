/* 🏆 Past winners — lib pins (2026-11-18, pastwinners spec §3.6, WP-APP). Ajay 2026-11-18, verbatim: "can you work on
 * todays videos and also..  Winners in general from the past". NEGATIVES throughout. */
import { describe, expect, it } from 'vitest';
import { API } from './apiBase';
import {
  RP_PATH, RP_WINNERS_PARAM, RP_WINNERS_PATH, RP_WINNERS_TITLE, rpVideoSrc, rpWinnerSrc, rpWinnersParams,
} from './replays';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('🏆 constants', () => {
  it('the route, the param and the ONE FE word', () => {
    expect(RP_WINNERS_PATH).toBe('/chart-maps/replays/winners');
    expect(RP_WINNERS_PATH.startsWith(RP_PATH)).toBe(true);
    expect(RP_WINNERS_PARAM).toBe('winners');
    expect(RP_WINNERS_TITLE).toBe('🏆 Past winners');
  });
  it('the title equals backend constants.WINNERS_TITLE', async () => {
    const py = await readSource('../backend/chart_maps/replays/constants.py');
    const m = /^WINNERS_TITLE = "([^"]+)"/m.exec(py);
    expect(m && m[1]).toBe(RP_WINNERS_TITLE);
    expect(/^WINNERS_API_PATH = API_PATH \+ "\/winners"$/m.test(py)).toBe(true);
  });
});

describe('🏆 rpWinnerSrc', () => {
  it('builds API + the served src on the 🏆 video route, both subs', () => {
    for (const src of ['/chart-maps/replays/winners/video/winners/2026-11-12_GP_45x.mp4',
      '/chart-maps/replays/winners/video/multiday/2026-08-19_BTCT_45x.mp4']) {
      expect(rpWinnerSrc({ src })).toBe(`${API}${src}`);
    }
  });
  it('NEGATIVE: a src off the 🏆 route (incl. the day route) is never put on a <video>', () => {
    for (const src of ['/chart-maps/replays/video/2026-11-17/CENN_reversal_squeeze_24x.mp4',
      '/chart-maps/replays/winners', '/chart-maps/replays/winners/x.mp4', 'https://evil.example/x.mp4',
      '//evil.example/chart-maps/replays/winners/video/x.mp4', '', 42, null, undefined]) {
      expect(rpWinnerSrc({ src } as any)).toBe('');
    }
    expect(rpWinnerSrc(null)).toBe('');
    expect(rpWinnerSrc(undefined)).toBe('');
  });
  it('NEGATIVE: the day guard still refuses a 🏆 src only by its own rule (unchanged)', () => {
    expect(rpVideoSrc({ src: '/chart-maps/replays/winners/video/winners/x.mp4' })).toBe('');
  });
});

describe('🏆 rpWinnersParams', () => {
  it('open sets winners=1; close deletes it', () => {
    expect(rpWinnersParams(new URLSearchParams('tab=replays'), true).get('winners')).toBe('1');
    expect(rpWinnersParams(new URLSearchParams('tab=replays&winners=1'), false).has('winners')).toBe(false);
  });
  it('NEGATIVE: tab and date survive; prev itself is not mutated', () => {
    const prev = new URLSearchParams('tab=replays&date=2026-11-17');
    const next = rpWinnersParams(prev, true);
    expect(next.get('tab')).toBe('replays');
    expect(next.get('date')).toBe('2026-11-17');
    expect(prev.has('winners')).toBe(false);
    const back = rpWinnersParams(next, false);
    expect(back.toString()).toBe('tab=replays&date=2026-11-17');
  });
});
