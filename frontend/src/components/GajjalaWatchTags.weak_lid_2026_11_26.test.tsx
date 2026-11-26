/* 👀 GgwTagsRow × the served 🧨 weak lid (2026-11-26, spec sitrack §3.5 / WP4 `fe-room`, [C6]).
 *
 * `GajjalaWatchTags.tsx` is NOT edited: its 🧨 tag is `ExplosiveChip` over `explosiveChipText`, so it inherits the
 * served suffix. Pinned here: the tag prints the served `weak_text` ONCE, the hover leads with the served
 * `weak_title`, and nothing of it prints when it is absent (today's tag). A name NOT carded on the 🚩 board prints no
 * 🧨 at all, suffix or not. The REAL hooks over a fetch routed by pathname, as the house test does. Stand-in words. */
import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import { GgwTagsRow } from './GajjalaWatchTags';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';
import type { BounceRoomRow, ExplosiveStudy, RoomRead } from '../lib/bounceRoom';
import { parseGgw, type GgwBoard, type GgwRow, type GgwRowTags } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const WEAK_TEXT = '1× band +154% first';
const WEAK_TITLE = 'served weak-lid sentence — 13 untested bands under the tested target';
const ROOM: RoomRead = {
  state: 'ROOM', room_pct: 6666278.68, atr_days: 186298.9,
  band: { kind: 'supply', lo: 28395.04, hi: 29406.56, touches: 2 }, at_highs: false,
  weak: { lo: 1.08, hi: 1.12, touches: 1, strength: null, pct: 153.6 },
  skipped: 13, target_age: 187, weak_text: WEAK_TEXT, weak_title: WEAK_TITLE,
};
const { weak: _w, skipped: _s, target_age: _t, weak_text: _x, weak_title: _y, ...PLAIN } = ROOM;
const roomRow = (room: RoomRead): BounceRoomRow => ({
  symbol: 'WHLR', coverage: 'store',
  explosive: { score: null, intact: true, room, measured: { status: 'no_signal' } },
});
const STUDY = { headline: 'served study headline', status: 'no_signal' } as ExplosiveStudy;
const TAGS: GgwRowTags = { on_board: true, setups: [] } as unknown as GgwRowTags;

const BASE = (parseGgw(clone(autoFixture)) as GgwBoard).rows[0];
const rowOf = (tags: GgwRowTags | null): GgwRow => ({ ...clone(BASE), symbol: 'WHLR', auto: null, aplus: null, tags });

const pathOf = (u: string) => new URL(u, 'http://x').pathname;
let calls: string[] = [];
function routedFetch() {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    calls.push(url);
    if (pathOf(url).endsWith('/short-interest/map'))
      return { ok: true, json: async () => ({ items: {}, n: 0, max_symbols: 200 }) } as unknown as Response;
    if (pathOf(url).endsWith('/growth/tags')) return { ok: true, json: async () => ({ tags: {} }) } as unknown as Response;
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
}
async function settle() {
  await waitFor(() => expect(calls.some((u) => pathOf(u).endsWith('/short-interest/map'))).toBe(true));
  await new Promise((r) => setTimeout(r, 30));
}
const mount = (tags: GgwRowTags | null, room: RoomRead) =>
  render(<GgwTagsRow row={rowOf(tags)} room={roomRow(room)} study={STUDY} />).container;
const tag = (c: ParentNode) => c.querySelector('[data-testid="ggw-tags-WHLR"] .cm-badge-explosive') as HTMLElement | null;

describe('👀 GgwTagsRow — the served 🧨 weak lid', { timeout: 20000 }, () => {
  beforeEach(() => { _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache(); routedFetch(); });
  afterEach(() => {
    cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks();
    _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache();
  });

  it('the tag prints the served suffix ONCE, and its hover starts with the served sentence', async () => {
    const c = mount(TAGS, ROOM);
    await settle();
    const el = tag(c)!;
    expect(el.textContent).toBe('🧨 room +6666279% · 1× band +154% first · floor held');
    const row = c.querySelector('[data-testid="ggw-tags-WHLR"]')!;
    expect(row.textContent!.split(WEAK_TEXT)).toHaveLength(2);               // once in the whole row
    expect(el.getAttribute('title')!.startsWith(WEAK_TITLE)).toBe(true);
    expect(el.textContent).not.toMatch(/bounc/i);
  });

  it('NEGATIVE: no served weak_text → today\'s tag, no suffix, no sentence', async () => {
    const c = mount(TAGS, PLAIN as RoomRead);
    await settle();
    const el = tag(c)!;
    expect(el.textContent).toBe('🧨 room +6666279% · floor held');
    expect(el.getAttribute('title')).not.toContain(WEAK_TITLE);
    expect(c.textContent).not.toContain('band +');
  });

  it('NEGATIVE: weak_text empty / a number → nothing appended', async () => {
    for (const bad of ['', 154] as unknown[]) {
      const c = mount(TAGS, { ...ROOM, weak_text: bad as string });
      await settle();
      expect(tag(c)!.textContent).toBe('🧨 room +6666279% · floor held');
      cleanup();
    }
  });

  it('NEGATIVE: a name not carded on the 🚩 board (tags null) prints no 🧨 at all, suffix or not', async () => {
    const c = mount(null, ROOM);
    await settle();
    expect(tag(c)).toBeNull();
    expect(c.textContent ?? '').not.toContain(WEAK_TEXT);
  });
});
