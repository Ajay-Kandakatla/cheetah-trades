/* 🎬 Replays — lib + registry pins (2026-11-17, replays spec §3.3, WP-FE). Ajay: "Can you store the videos in to the
 * app please". NEGATIVES throughout. */
import { describe, expect, it } from 'vitest';
import { API } from './apiBase';
import { CM_TABS, DEFAULT_TAB, ENTERABLE_KIND, TAB_META, isBoardTab, parseTab } from './chartMaps';
import { BURST_EXEMPT } from './momentumBurst';
import {
  FETCH_FAILED, RP_DATE_PARAM, RP_PATH, RP_TAB, rpDateParams, rpDates, rpList, rpSelectDates, rpText, rpVideoSrc,
} from './replays';

describe('🎬 constants', () => {
  it('the tab, the route, the date param and the ONE FE sentence', () => {
    expect(RP_TAB).toBe('replays');
    expect(RP_PATH).toBe('/chart-maps/replays');
    expect(RP_DATE_PARAM).toBe('date');
    expect(FETCH_FAILED).toBe('Could not load the replays.');
  });
});

describe('🎬 rpVideoSrc', () => {
  it('builds API + the served src on the owner video route', () => {
    const src = '/chart-maps/replays/video/2026-11-17/CENN_reversal_squeeze_24x.mp4';
    expect(rpVideoSrc({ src })).toBe(`${API}${src}`);
  });
  it('NEGATIVE: a served src off the route is never put on a <video>', () => {
    for (const src of ['/chart-maps/long-term', 'https://evil.example/x.mp4', '/chart-maps/replays/x.mp4',
      '//evil.example/chart-maps/replays/video/x.mp4', '', 42, null, undefined]) {
      expect(rpVideoSrc({ src } as any)).toBe('');
    }
    expect(rpVideoSrc(null)).toBe('');
    expect(rpVideoSrc(undefined)).toBe('');
  });
});

describe('🎬 text guards', () => {
  it('rpText: a string is itself; NEGATIVE: junk → ""', () => {
    expect(rpText('L −1R')).toBe('L −1R');
    for (const x of [null, undefined, 3, {}, [], true]) expect(rpText(x)).toBe('');
  });
  it('rpList / rpDates: strings kept in order; NEGATIVE: junk → [] and non-strings dropped', () => {
    expect(rpList(['a', 1, 'b', null])).toEqual(['a', 'b']);
    expect(rpList('a')).toEqual([]);
    expect(rpList(null)).toEqual([]);
    expect(rpDates(['2026-11-17', '', 5, '2026-11-16'])).toEqual(['2026-11-17', '2026-11-16']);
    expect(rpDates({})).toEqual([]);
  });
});

describe('🎬 rpDateParams [C7]', () => {
  it('sets date; deletes it on null and on ""', () => {
    expect(rpDateParams(new URLSearchParams('tab=replays'), '2026-11-16').get('date')).toBe('2026-11-16');
    expect(rpDateParams(new URLSearchParams('tab=replays&date=2026-11-16'), null).has('date')).toBe(false);
    expect(rpDateParams(new URLSearchParams('tab=replays&date=2026-11-16'), '').has('date')).toBe(false);
  });
  it('NEGATIVE: tab=replays&focus=ABC survive untouched; prev itself is not mutated', () => {
    const prev = new URLSearchParams('tab=replays&focus=ABC&date=2026-11-17');
    const next = rpDateParams(prev, '2026-11-13');
    expect(next.get('tab')).toBe('replays');
    expect(next.get('focus')).toBe('ABC');
    expect(next.get('date')).toBe('2026-11-13');
    expect(prev.get('date')).toBe('2026-11-17');
    const cleared = rpDateParams(prev, null);
    expect(cleared.toString()).toBe('tab=replays&focus=ABC');
  });
});

describe('🎬 rpSelectDates [C8]', () => {
  const dates = ['2026-11-17', '2026-11-16', '2026-11-13'];
  it('served order kept, nothing disabled', () => {
    expect(rpSelectDates(dates, '2026-11-17')).toEqual(dates.map((value) => ({ value, disabled: false })));
  });
  it('a served date outside dates is PREPENDED disabled', () => {
    const o = rpSelectDates(dates, '2026-11-08');
    expect(o[0]).toEqual({ value: '2026-11-08', disabled: true });
    expect(o.slice(1).map((x) => x.value)).toEqual(dates);
  });
  it('NEGATIVE: a date inside dates adds nothing; null / "" add nothing', () => {
    expect(rpSelectDates(dates, '2026-11-16')).toHaveLength(3);
    expect(rpSelectDates(dates, null)).toHaveLength(3);
    expect(rpSelectDates(dates, '')).toHaveLength(3);
    expect(rpSelectDates([], null)).toEqual([]);
  });
});

describe('🎬 the Chart Maps registry', () => {
  it('replays once, right after long_term; long_term still right after growth; DEFAULT_TAB unchanged', () => {
    expect(CM_TABS.filter((t) => t === 'replays')).toHaveLength(1);
    expect(CM_TABS.indexOf('replays')).toBe(CM_TABS.indexOf('long_term') + 1);
    expect(CM_TABS.indexOf('long_term')).toBe(CM_TABS.indexOf('growth') + 1);
    expect(DEFAULT_TAB).toBe('zones');
  });
  it('a non-board tab; parses from ?tab=', () => {
    expect(isBoardTab('replays')).toBe(false);
    expect(parseTab('replays')).toBe('replays');
    expect(parseTab(' REPLAYS ')).toBe('replays');
  });
  it('NEGATIVE: near-miss spellings fall to the default tab', () => {
    for (const raw of ['replay', 'videos', 'replays_tab', 'reply']) expect(parseTab(raw)).toBe(DEFAULT_TAB);
  });
  it('TAB_META: the 🎬 label; the blurb carries his asks verbatim, UNMEASURED and owner only', () => {
    expect(TAB_META.replays.label).toBe('\u{1F3AC} Replays');
    const b = TAB_META.replays.blurb;
    expect(b).toContain('Can you store the videos in to the app please');
    expect(b).toContain('I only wanna see ones from 4 AM to 8 pm please');
    expect(b).toContain('UNMEASURED');
    expect(b).toContain('owner only');
  });
  it('NEGATIVE [C4]: ENTERABLE_KIND carries NO replays entry (the long_term / gajjala_watch shape)', () => {
    expect(Object.prototype.hasOwnProperty.call(ENTERABLE_KIND, 'replays')).toBe(false);
  });
  it('[P2] BURST_EXEMPT names replays with its written reason', () => {
    expect(BURST_EXEMPT.replays).toBe('videos in the served group order — never ranked');
  });
});
