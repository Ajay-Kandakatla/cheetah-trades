/* 📚 Playbook learning — the pure helpers of lib/playbookVideos (2026-11-27, playbookvid spec §3.5). Ajay 2026-11-27,
 * verbatim: "I loved the video can you move them under our replay tab with a PLaybook learning and also add it to the
 * playbook tab too with videos". NEGATIVES throughout. */
import { describe, expect, it } from 'vitest';
import fixture from '../components/__fixtures__/playbook_videos_2026_11_27.json';
import { API } from './apiBase';
import {
  PBV_FETCH_FAILED, PBV_PARAM, PBV_PATH, PBV_WHERE, pbvDefaultVariant, pbvFilms, pbvMarkers, pbvOpen, pbvOptions,
  pbvPick, pbvRowKey, pbvSrc, pbvText, pbvToggleParams, pbvVariants,
} from './playbookVideos';

const READY: any = (fixture as any).ready;
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const VSRC = `${PBV_PATH}/video/2026-11-27_gg_film/00_intro_phone.mp4`;

describe('constants', () => {
  it('route, param, the two mounts, the one FE sentence', () => {
    expect(PBV_PATH).toBe('/chart-maps/replays/playbook');
    expect(PBV_PARAM).toBe('playbook');
    expect(PBV_WHERE.replays).toEqual({ title: '📚 Playbook learning', defaultOpen: false, quiet: false });
    expect(PBV_WHERE.playbook).toEqual({ title: '🎬 Videos', defaultOpen: true, quiet: true });
    expect(PBV_FETCH_FAILED).toBe('Could not load the playbook videos.');
  });
});

describe('pbvText', () => {
  it('a string prints as itself — NEGATIVE: numbers, null, objects print nothing', () => {
    expect(pbvText('Bull Flag')).toBe('Bull Flag');
    expect(pbvText(5)).toBe('');
    expect(pbvText(null)).toBe('');
    expect(pbvText(undefined)).toBe('');
    expect(pbvText({ a: 1 })).toBe('');
  });
});

describe('pbvSrc', () => {
  it('API + served src on the playbook video route', () => {
    expect(pbvSrc({ src: VSRC })).toBe(`${API}${VSRC}`);
  });
  it('NEGATIVE: another route, an absolute URL, javascript:, the bare route, junk → ""', () => {
    expect(pbvSrc({ src: '/chart-maps/replays/video/2026-11-25/x.mp4' })).toBe('');
    expect(pbvSrc({ src: '/chart-maps/replays/winners/video/winners/x.mp4' })).toBe('');
    expect(pbvSrc({ src: `https://evil.example${VSRC}` })).toBe('');
    expect(pbvSrc({ src: 'javascript:alert(1)' })).toBe('');
    expect(pbvSrc({ src: PBV_PATH })).toBe('');
    expect(pbvSrc({ src: `${PBV_PATH}/videoX/a.mp4` })).toBe('');
    expect(pbvSrc({ src: 5 })).toBe('');
    expect(pbvSrc(null)).toBe('');
    expect(pbvSrc(undefined)).toBe('');
  });
});

describe('pbvVariants / pbvPick', () => {
  const vs = READY.films[0].chapters[0].variants;
  it('keeps the playable variants in served order', () => {
    expect(pbvVariants(vs).map((v) => v.key)).toEqual(['phone', 'desktop']);
  });
  it('NEGATIVE: no key, a non-string key, an off-route src, non-objects, a non-list → dropped / []', () => {
    const junk = [{ src: VSRC }, { key: 3, src: VSRC }, { key: 'phone', src: '/x' }, 'x', null, { key: '', src: VSRC }];
    expect(pbvVariants(junk)).toEqual([]);
    expect(pbvVariants('x')).toEqual([]);
    expect(pbvVariants(null)).toEqual([]);
  });
  it('pick: the wanted key, else the first playable, else null', () => {
    expect(pbvPick(vs, 'phone')?.file).toBe('00_intro_phone.mp4');
    expect(pbvPick(vs, 'desktop')?.file).toBe('00_intro.mp4');
    expect(pbvPick([vs[1]], 'phone')?.file).toBe('00_intro.mp4');
    expect(pbvPick(vs, 'nope')?.file).toBe('00_intro_phone.mp4');
  });
  it('NEGATIVE: the wanted key with an off-route src falls to the next playable; nothing playable → null', () => {
    const bad = clone(vs);
    bad[0].src = 'javascript:alert(1)';
    expect(pbvPick(bad, 'phone')?.file).toBe('00_intro.mp4');
    bad[1].src = 'https://x/y.mp4';
    expect(pbvPick(bad, 'phone')).toBeNull();
    expect(pbvPick('x', 'phone')).toBeNull();
  });
});

describe('pbvDefaultVariant', () => {
  it('phone width → phone; otherwise → desktop', () => {
    expect(pbvDefaultVariant(true)).toBe('phone');
    expect(pbvDefaultVariant(false)).toBe('desktop');
  });
});

describe('pbvOptions / pbvMarkers', () => {
  it('options: string key + string label, served order', () => {
    expect(pbvOptions(READY.variant_options)).toEqual([
      { key: 'phone', label: '📱 phone' }, { key: 'desktop', label: '🖥 desktop' },
    ]);
  });
  it('NEGATIVE: options with a missing / non-string key or label, a non-list → dropped / []', () => {
    expect(pbvOptions([{ key: 'phone' }, { label: 'x' }, { key: 1, label: 'x' }, { key: 'a', label: 2 }, null])).toEqual([]);
    expect(pbvOptions({})).toEqual([]);
  });
  it('markers: finite start_s >= 0 + non-empty text', () => {
    expect(pbvMarkers(READY.films[0].full.markers).map((m) => m.start_s)).toEqual([0, 438.167]);
  });
  it('NEGATIVE: negative / NaN / Infinity / string start_s, empty text, null → dropped / []', () => {
    expect(pbvMarkers([
      { start_s: -1, text: 'a' }, { start_s: NaN, text: 'a' }, { start_s: Infinity, text: 'a' },
      { start_s: '3', text: 'a' }, { start_s: 3, text: '' }, { start_s: 3 }, null,
    ])).toEqual([]);
    expect(pbvMarkers(null)).toEqual([]);
  });
});

describe('pbvFilms', () => {
  it('the served films in served order, rows kept', () => {
    const films = pbvFilms(READY.films);
    expect(films.map((f) => f.slug)).toEqual(['2026-11-27_gg_film']);
    expect(films[0].chapters!.map((c) => c.key)).toEqual(['00_intro', '01_bull_flag']);
    expect(films[0].full?.key).toBe('full');
  });
  it('a third chapter added to the payload is listed with no code change', () => {
    const p = clone(READY);
    const c = clone(p.films[0].chapters[1]);
    c.key = '02_kiss_fly';
    p.films[0].chapters.push(c);
    expect(pbvFilms(p.films)[0].chapters!.map((x) => x.key)).toEqual(['00_intro', '01_bull_flag', '02_kiss_fly']);
  });
  it('NEGATIVE: a film with zero playable rows, a non-string slug, junk rows and a non-list → dropped / []', () => {
    const p = clone(READY);
    for (const c of p.films[0].chapters) for (const v of c.variants) v.src = '/elsewhere.mp4';
    p.films[0].full.variants[0].src = 'javascript:x';
    expect(pbvFilms(p.films)).toEqual([]);
    expect(pbvFilms([{ slug: 5, chapters: READY.films[0].chapters }])).toEqual([]);
    expect(pbvFilms({})).toEqual([]);
    expect(pbvFilms(null)).toEqual([]);
    const j = clone(READY);
    j.films[0].chapters.push('x', null, { title: 'no key' });
    j.films[0].full = 'x';
    const out = pbvFilms(j.films);
    expect(out[0].chapters!.map((c) => c.key)).toEqual(['00_intro', '01_bull_flag']);
    expect(out[0].full).toBeNull();
  });
  it('the full film alone is a playable row', () => {
    const p = clone(READY);
    p.films[0].chapters = [];
    expect(pbvFilms(p.films)).toHaveLength(1);
  });
});

describe('pbvRowKey / pbvOpen / pbvToggleParams', () => {
  it('row key = slug/key; junk prints nothing', () => {
    expect(pbvRowKey('f', '00_intro')).toBe('f/00_intro');
    expect(pbvRowKey(5, null)).toBe('/');
  });
  it('open: 1 → open, 0 → closed, absent / junk → the mount default', () => {
    expect(pbvOpen(new URLSearchParams('playbook=1'), false)).toBe(true);
    expect(pbvOpen(new URLSearchParams('playbook=0'), true)).toBe(false);
    expect(pbvOpen(new URLSearchParams(''), false)).toBe(false);
    expect(pbvOpen(new URLSearchParams(''), true)).toBe(true);
    expect(pbvOpen(new URLSearchParams('playbook=yes'), false)).toBe(false);
    expect(pbvOpen(new URLSearchParams('playbook=yes'), true)).toBe(true);
  });
  it('toggle keeps tab / date / winners / reel and returns a COPY', () => {
    const prev = new URLSearchParams('tab=replays&date=2026-11-25&winners=1&reel=winners/x.mp4');
    const next = pbvToggleParams(prev, true, false);
    expect(next).not.toBe(prev);
    expect(prev.has('playbook')).toBe(false);
    expect(next.get('playbook')).toBe('1');
    expect(next.get('tab')).toBe('replays');
    expect(next.get('date')).toBe('2026-11-25');
    expect(next.get('winners')).toBe('1');
    expect(next.get('reel')).toBe('winners/x.mp4');
  });
  it('the param is deleted when the new state equals the mount default; else 1 / 0', () => {
    expect(pbvToggleParams(new URLSearchParams('playbook=1&tab=replays'), false, false).has('playbook')).toBe(false);
    expect(pbvToggleParams(new URLSearchParams('playbook=0&sub=playbook'), true, true).has('playbook')).toBe(false);
    expect(pbvToggleParams(new URLSearchParams('sub=playbook'), false, true).get('playbook')).toBe('0');
    expect(pbvToggleParams(new URLSearchParams('sub=playbook'), false, true).get('sub')).toBe('playbook');
  });
});
