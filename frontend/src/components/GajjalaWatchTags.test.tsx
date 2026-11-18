/* 🏷️ GgwTagsRow — the tags row above each 👀 Watch tile (2026-11-18, spec wtags §3.3 / §4 WP-B).
 * Ajay 2026-11-18: "Also add Short Interest tag and other tags on top of stock ticker information for me to read, like
 * here". The REAL hooks (useShortInterest, useGrowthTags) over fetch routed by PATHNAME; the room row is handed in as
 * the board does (prop-fed). Every word is a stand-in for a served one. NEGATIVES: EXTREME → no plain SI chip (the
 * head's note is the one SI line); no record / failed / loading → nothing, never '0'; `tags` null → only 🚀 / 🩳 even
 * with a room row; nothing to print → null; no b-word rendered or typed; one skin (cm-badge). Display only; UNMEASURED. */
import { cleanup, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import { GgwTagsRow } from './GajjalaWatchTags';
import { Tile } from './GajjalaWatchTile';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { _resetGrowthTagsCache, growthChip } from '../hooks/useGrowthTags';
import { explosiveChipText, type BounceRoomRow, type ExplosiveStudy } from '../lib/bounceRoom';
import { enterableChipText } from '../lib/enterable';
import { parseGgw, type GgwBoard, type GgwRow, type GgwRowTags } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SI_PATH = '/short-interest/map';
const GROWTH_PATH = '/growth/tags';
const TITLE = '🩳 served SI hover sentence — FINRA settlement 2026-10-30.';
const blk = (sym: string, status: string, chip: string | null, extra: Record<string, unknown> = {}) =>
  ({ symbol: sym, status, chip, title: TITLE, rows: [], ...extra });
/* 2026-11-18 sitier: the EXTREME stand-in re-pinned to the served '🩳 SI EXTREME …' order (spec sitier §3.4). */
const X = { text: '🩳 SI EXTREME 36.4% float · 1.0d · 10/30', short: '🩳 SI EXTREME 36.4% float', title: 'served extreme hover', basis: 'si_doc_float' };
/* 2026-11-18 sitier: the CLRO and AKAN shapes, copied from spec sitier §3.4 */
const CLRO_X = { text: '🩳 SI EXTREME 44.0% float · 1.0d · 10/30', short: '🩳 SI EXTREME 44.0% float', title: 'served CLRO hover', basis: 'si_doc_float' };
const AK_CHIP = '🩳 SI High 36.4% float · float unconfirmed · 1.0d · 10/30';
const SI: Record<string, unknown> = {
  OMH: blk('OMH', 'ok', '🩳 SI 359.4K sh · 19.5d · 10/30', { extreme: null }),
  XTRM: blk('XTRM', 'ok', '🩳 SI 36.4% float · 1.0d · 10/30', { extreme: X }),
  AKAN: blk('AKAN', 'ok', AK_CHIP, { tier: 'high', float_check: 'unconfirmed', extreme: null }),
  CLRO: blk('CLRO', 'ok', CLRO_X.text, { tier: 'extreme', float_check: 'confirmed', extreme: CLRO_X }),
  STAL: blk('STAL', 'stale', '🩳 SI 2.5M sh · 9.0d · 8/31 · stale', { extreme: null }),
  NREC: blk('NREC', 'no_record', null),
};
const GROWTH = { tags: { OMH: { sales: 120, eps: 80, refused: false } } };

let calls: string[] = [];
let siMode: 'ok' | 'fail' | 'hang' = 'ok';
const pathOf = (u: string) => new URL(u, 'http://x').pathname;
const symsOf = (u: string) => decodeURIComponent(new URL(u, 'http://x').searchParams.get('symbols') || '').split(',').filter(Boolean);
function routedFetch(growth: unknown = GROWTH) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    calls.push(url);
    if (pathOf(url).endsWith(SI_PATH)) {
      if (siMode === 'fail') return { ok: false, status: 500, json: async () => ({}) } as unknown as Response;
      if (siMode === 'hang') return new Promise<Response>(() => {});
      const out: Record<string, unknown> = {};
      for (const s of symsOf(url)) if (SI[s]) out[s] = SI[s];
      return { ok: true, json: async () => ({ items: out, n: Object.keys(out).length, max_symbols: 200 }) } as unknown as Response;
    }
    if (pathOf(url).endsWith(GROWTH_PATH)) return { ok: true, json: async () => growth } as unknown as Response;
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
}
const siGets = () => calls.filter((u) => pathOf(u).endsWith(SI_PATH));
const growthGets = () => calls.filter((u) => pathOf(u).endsWith(GROWTH_PATH));
/** both reads asked and answered (the SI flush is SI_FLUSH_MS) */
async function settle() {
  await waitFor(() => { expect(siGets().length).toBeGreaterThan(0); expect(growthGets().length).toBeGreaterThan(0); });
  await new Promise((r) => setTimeout(r, 30));
}

const BASE = (parseGgw(clone(autoFixture)) as GgwBoard).rows[0];
function rowOf(sym: string, tags: GgwRowTags | null = null): GgwRow {
  return { ...clone(BASE), symbol: sym, auto: null, aplus: null, tags };
}
const STAGES = {
  title: '🧭 served stages title', hint: 'served stages hint', sep: '→', text: '🎾 served chain',
  groups: [{ date: '2026-11-18', label: 'served today', clock: true,
             tags: [{ setup: 'reversal_squeeze', text: '🎾 served tag A' }, { setup: 'kiss_fly', text: '💋 served tag B' }] }],
};
const TAGS: GgwRowTags = {
  on_board: true,
  setups: [
    { setup: 'reversal_squeeze', label: '🎾 served label RS', state: 'forming', state_label: 'served RS state words' },
    { setup: 'kiss_fly', label: '💋 served label KF', state: 'triggered', state_label: 'served KF state words no alert rang' },
  ],
  stages: STAGES,
  float: { text: 'Float 3.2M served', shares: 3200000, src: 'served', as_of: '2026-11-17', suspect: false },
  broker_text: '🚫 served broker words', trader_text: '📌 served trader', promo_text: '🎪 served promo',
};
const ROOM = {
  symbol: 'OMH', coverage: 'covered',
  explosive: { score: null, intact: false, state: null, room: { state: 'ROOM', room_pct: 1.1, atr_days: null, band: null },
               measured: { status: 'no_signal' } },
  enterable: { kind: 'demand', verdict: 'BLOCKED', reasons: ['band'], reason_text: ['served band sentence'],
               reason_short: ['not at band'] },
} as unknown as BounceRoomRow;
const STUDY = { headline: 'served study headline', status: 'no_signal' } as ExplosiveStudy;

const mountRow = (row: GgwRow, room: BounceRoomRow | null = null, study: ExplosiveStudy | null = null) =>
  render(<GgwTagsRow row={row} room={room} study={study} />).container;
const rowEl = (c: ParentNode, s: string) => c.querySelector(`[data-testid="ggw-tags-${s}"]`) as HTMLElement | null;
const CARD_IDS = (s: string) => [`ggw-trader-${s}`, `ggw-promo-${s}`, `ggw-broker-${s}`, `ggw-float-${s}`, `gg-stages-${s}`];

describe('🏷️ GgwTagsRow', { timeout: 20000 }, () => {
  beforeEach(() => {
    siMode = 'ok';
    _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache();
  });
  afterEach(() => {
    cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks();
    _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache();
  });

  it('🚀 prints when /growth/tags lists the name — NEGATIVE: absent when it does not', async () => {
    routedFetch();
    const c = mountRow(rowOf('OMH'));
    await settle();
    const r = rowEl(c, 'OMH')!;
    const want = growthChip(GROWTH.tags, 'OMH')!;
    await waitFor(() => expect(r.querySelector('.cm-badge-growth')).not.toBeNull());
    expect(r.querySelector('.cm-badge-growth')!.textContent).toBe(want.text);
    expect(r.firstElementChild!.className).toBe('cm-badge cm-badge-growth');    // FIRST in the row (the card's order)
    cleanup(); _resetShortInterestCache(); _resetGrowthTagsCache();
    routedFetch({ tags: {} });
    const c2 = mountRow(rowOf('OMH'));
    await settle();
    expect(rowEl(c2, 'OMH')!.querySelector('.cm-badge-growth')).toBeNull();
    expect(rowEl(c2, 'OMH')!.querySelector('[data-testid="si-chip"]')).not.toBeNull();
  });

  it('🩳 the served chip verbatim, served title, class "cm-badge cm-badge-muted"; stale keeps its own word', async () => {
    routedFetch({ tags: {} });
    const c = render(<>{['OMH', 'STAL'].map((s) => <GgwTagsRow key={s} row={rowOf(s)} />)}</>).container;
    await settle();
    await waitFor(() => expect(rowEl(c, 'STAL')).not.toBeNull());
    const omh = rowEl(c, 'OMH')!.querySelector('[data-testid="si-chip"]')!;
    expect(omh.textContent).toBe((SI.OMH as any).chip);
    expect(omh.getAttribute('title')).toBe(TITLE);
    expect(omh.className).toBe('cm-badge cm-badge-muted');
    expect(rowEl(c, 'STAL')!.querySelector('[data-testid="si-chip"]')!.textContent).toBe((SI.STAL as any).chip);
    expect(siGets()).toHaveLength(1);                                   // ONE batched map GET for both rows
    expect(new Set(symsOf(siGets()[0]))).toEqual(new Set(['OMH', 'STAL']));
  });

  it('NEGATIVE: EXTREME → NO si-chip in the row (and nothing else → the row is null)', async () => {
    routedFetch({ tags: {} });
    const c = mountRow(rowOf('XTRM'));
    await settle();
    expect(c.querySelector('[data-testid="si-chip"]')).toBeNull();
    expect(rowEl(c, 'XTRM')).toBeNull();
    expect(c.innerHTML).toBe('');
  });

  it('2026-11-18 sitier: the AKAN shape → the row prints the served High chip with float unconfirmed + data-si-tier="high"', async () => {
    routedFetch({ tags: {} });
    const c = mountRow(rowOf('AKAN'));
    await settle();
    await waitFor(() => expect(rowEl(c, 'AKAN')).not.toBeNull());
    const el = rowEl(c, 'AKAN')!.querySelector('[data-testid="si-chip"]')!;
    expect(el.textContent).toBe(AK_CHIP);
    expect(el.getAttribute('data-si-tier')).toBe('high');
    expect(el.className).toBe('cm-badge cm-badge-muted');
    expect(c.querySelector('.ggw-si-extreme')).toBeNull();
  });

  it('NEGATIVE (2026-11-18 sitier): the CLRO shape → NO SI chip in the row (the head note is the one SI line)', async () => {
    routedFetch({ tags: {} });
    const c = mountRow(rowOf('CLRO'));
    await settle();
    expect(c.querySelector('[data-testid="si-chip"]')).toBeNull();
    expect(rowEl(c, 'CLRO')).toBeNull();
    expect(c.textContent).not.toContain('EXTREME');
  });

  it('control (2026-11-18 sitier): Tile — CLRO → only the head note (tier "extreme"); AKAN → only the row chip', async () => {
    routedFetch({ tags: {} });
    const props = { phone: false, fit: false, removeLabel: null, focused: false, busy: false, siNote: true,
                    tags: { room: null, study: null } };
    const c = render(<MemoryRouter><Tile row={rowOf('CLRO')} {...props} /><Tile row={rowOf('AKAN')} {...props} /></MemoryRouter>).container;
    await settle();
    await waitFor(() => expect(c.querySelector('[data-testid="ggw-si-extreme-CLRO"]')).not.toBeNull());
    await waitFor(() => expect(c.querySelector('[data-testid="ggw-tile-AKAN"] [data-testid="si-chip"]')).not.toBeNull());
    const cl = c.querySelector('[data-testid="ggw-tile-CLRO"]')!;
    expect(cl.querySelectorAll('[data-testid="si-chip"], .ggw-si-extreme')).toHaveLength(1);
    expect(cl.querySelector('.ggw-si-extreme')!.textContent).toBe(CLRO_X.short);
    expect(cl.querySelector('.ggw-si-extreme')!.getAttribute('data-si-tier')).toBe('extreme');
    const ak = c.querySelector('[data-testid="ggw-tile-AKAN"]')!;
    expect(ak.querySelectorAll('[data-testid="si-chip"], .ggw-si-extreme')).toHaveLength(1);
    expect(ak.querySelector('[data-testid="si-chip"]')!.textContent).toBe(AK_CHIP);
    expect(ak.querySelector('.ggw-si-extreme')).toBeNull();
  });

  it('control: Tile with siNote + tags — EXTREME → exactly ONE SI element (the head note); plain → the row chip only', async () => {
    routedFetch({ tags: {} });
    const props = { phone: false, fit: false, removeLabel: null, focused: false, busy: false, siNote: true,
                    tags: { room: null, study: null } };
    const c = render(<MemoryRouter><Tile row={rowOf('XTRM')} {...props} /><Tile row={rowOf('OMH')} {...props} /></MemoryRouter>).container;
    await settle();
    await waitFor(() => expect(c.querySelector('[data-testid="ggw-si-extreme-XTRM"]')).not.toBeNull());
    const x = c.querySelector('[data-testid="ggw-tile-XTRM"]')!;
    expect(x.querySelectorAll('[data-testid="si-chip"], .ggw-si-extreme')).toHaveLength(1);
    expect(x.querySelector('.ggw-si-extreme')!.textContent).toBe(X.short);
    const o = c.querySelector('[data-testid="ggw-tile-OMH"]')!;
    expect(o.querySelectorAll('[data-testid="si-chip"], .ggw-si-extreme')).toHaveLength(1);
    expect(o.querySelector('[data-testid="si-chip"]')!.closest('.ggw-tags')).toBe(o.firstElementChild);
    expect(o.firstElementChild!.nextElementSibling!.className).toBe('ggw-tile-head');
  });

  it('NEGATIVE: no record / absent / request failed / loading → no chip, never "0"', async () => {
    routedFetch({ tags: {} });
    const c = render(<>{['NREC', 'ABSN'].map((s) => <GgwTagsRow key={s} row={rowOf(s)} />)}</>).container;
    await settle();
    expect(c.innerHTML).toBe('');
    cleanup(); _resetShortInterestCache(); _resetGrowthTagsCache();
    siMode = 'fail';
    routedFetch({ tags: {} });
    const c2 = mountRow(rowOf('OMH'));
    await settle();
    expect(c2.innerHTML).toBe('');
    cleanup(); _resetShortInterestCache(); _resetGrowthTagsCache();
    siMode = 'hang';
    routedFetch({ tags: {} });
    const c3 = mountRow(rowOf('OMH'));
    await settle();
    expect(c3.innerHTML).toBe('');
    for (const el of [c, c2, c3]) expect(el.textContent).not.toMatch(/(^|[^\d.])0(\.0+)?(%|\b)/);
  });

  it('NEGATIVE: tags null → only 🚀 / 🩳, no 🧨 / ⛔ / 📌 / 🚫 / Float / 🧭 nodes even with a room row handed in', async () => {
    routedFetch();
    const c = mountRow(rowOf('OMH', null), ROOM, STUDY);
    await settle();
    await waitFor(() => expect(c.querySelector('.cm-badge-growth')).not.toBeNull());
    const r = rowEl(c, 'OMH')!;
    expect(Array.from(r.children).map((e) => e.className)).toEqual(['cm-badge cm-badge-growth', 'cm-badge cm-badge-muted']);
    expect(r.querySelector('.cm-badge-explosive')).toBeNull();
    expect(r.querySelector('[class*="cm-badge-enterable"]')).toBeNull();
    for (const id of CARD_IDS('OMH')) expect(r.querySelector(`[data-testid="${id}"]`), id).toBeNull();
    expect(r.querySelector('[data-testid^="ggw-setup-"]')).toBeNull();
    /* a junk / off-board block parses to null and behaves the same */
    cleanup(); _resetShortInterestCache(); _resetGrowthTagsCache();
    routedFetch({ tags: {} });
    const c2 = mountRow(rowOf('OMH', { ...TAGS, on_board: false } as unknown as GgwRowTags), ROOM, STUDY);
    await settle();
    expect(Array.from(rowEl(c2, 'OMH')!.children).map((e) => e.getAttribute('data-testid'))).toEqual(['si-chip']);
  });

  it('on_board + a room row → 🧨 and ⛔ texts equal the card helpers of the same inputs; card order kept', async () => {
    routedFetch();
    const c = mountRow(rowOf('OMH', TAGS), ROOM, STUDY);
    await settle();
    await waitFor(() => expect(c.querySelector('.cm-badge-growth')).not.toBeNull());
    const r = rowEl(c, 'OMH')!;
    const ex = explosiveChipText(ROOM.explosive, STUDY)!;
    const en = enterableChipText(ROOM.enterable)!;
    expect(r.querySelector('.cm-badge-explosive')!.textContent).toBe(ex.text);
    expect(r.querySelector('.cm-badge-explosive')!.getAttribute('title')).toBe(ex.title);
    expect(r.querySelector('.cm-badge-enterable-blocked')!.textContent).toBe(en.text);
    const kinds = Array.from(r.children).map((e) => e.getAttribute('data-testid') ?? e.className);
    expect(kinds).toEqual([
      'cm-badge cm-badge-growth', 'si-chip', 'cm-badge cm-badge-explosive cm-badge-explosive-muted',
      'cm-badge cm-badge-enterable-blocked', 'ggw-trader-OMH', 'ggw-promo-OMH', 'ggw-broker-OMH', 'ggw-float-OMH',
      'gg-stages-OMH',
    ]);
  });

  it('stages → gg-stages-{sym} with the served text and NO ggw-setup-* chips', async () => {
    routedFetch({ tags: {} });
    const c = mountRow(rowOf('OMH', TAGS));
    await settle();
    const st = c.querySelector('[data-testid="gg-stages-OMH"]')!;
    expect(st.getAttribute('aria-label')).toBe(STAGES.text);
    expect(st.querySelector('.gg-stages-title')!.textContent).toBe(STAGES.title);
    expect(Array.from(st.querySelectorAll('.gg-stage')).map((e) => e.textContent)).toEqual(['🎾 served tag A', '💋 served tag B']);
    expect(c.querySelector('[data-testid^="ggw-setup-"]')).toBeNull();
  });

  it('stages null (or a block that draws nothing) → one ggw-setup-* chip per setup, title = state_label', async () => {
    routedFetch({ tags: {} });
    const noStages = { ...TAGS, stages: null };
    const empty = { ...TAGS, stages: { ...STAGES, groups: [{ date: 'd', label: 'x', tags: [{ setup: 'a', text: ' ' }] }] } };
    const c = render(<>{[['OMH', noStages], ['XYZ', empty]].map(([s, t]) =>
      <GgwTagsRow key={s as string} row={rowOf(s as string, t as GgwRowTags)} />)}</>).container;
    await settle();
    for (const s of ['OMH', 'XYZ']) {
      const chips = Array.from(c.querySelectorAll(`[data-testid^="ggw-setup-${s}-"]`));
      expect(chips.map((e) => e.getAttribute('data-testid'))).toEqual([`ggw-setup-${s}-reversal_squeeze`, `ggw-setup-${s}-kiss_fly`]);
      expect(chips.map((e) => e.textContent)).toEqual(TAGS.setups.map((x) => x.label));
      expect(chips.map((e) => e.getAttribute('title'))).toEqual(TAGS.setups.map((x) => x.state_label));
      expect(chips.every((e) => e.className === 'cm-badge cm-badge-muted ggw-setup')).toBe(true);
      expect(c.querySelector(`[data-testid="gg-stages-${s}"]`)).toBeNull();
    }
  });

  it('broker / trader / promo / float print the served strings; NEGATIVE: blank ones print nothing', async () => {
    routedFetch({ tags: {} });
    const c = mountRow(rowOf('OMH', TAGS));
    await settle();
    const t = (id: string) => c.querySelector(`[data-testid="${id}"]`);
    expect(t('ggw-broker-OMH')!.textContent).toBe(TAGS.broker_text);
    expect(t('ggw-broker-OMH')!.className).toBe('cm-badge cm-badge-muted gg-broker ggw-broker');
    expect(t('ggw-trader-OMH')!.textContent).toBe(TAGS.trader_text);
    expect(t('ggw-promo-OMH')!.textContent).toBe(TAGS.promo_text);
    expect(t('ggw-float-OMH')!.textContent).toBe(TAGS.float!.text);
    expect(t('ggw-float-OMH')!.className).toBe('cm-badge cm-badge-muted ggw-float');
    expect(t('ggw-float-OMH')!.getAttribute('title')).toBeNull();      // bare — no composed hover
    cleanup(); _resetShortInterestCache(); _resetGrowthTagsCache();
    routedFetch({ tags: {} });
    const bare = { ...TAGS, broker_text: null, trader_text: null, promo_text: null, float: null };
    const c2 = mountRow(rowOf('ZZZ', bare));
    await settle();
    for (const id of ['ggw-broker-ZZZ', 'ggw-trader-ZZZ', 'ggw-promo-ZZZ', 'ggw-float-ZZZ']) {
      expect(c2.querySelector(`[data-testid="${id}"]`), id).toBeNull();
    }
    expect(c2.querySelector('[data-testid="gg-stages-ZZZ"]')).not.toBeNull();
  });

  it('one skin: every element inside .ggw-tags carries cm-badge or sits inside .gg-stages — NEGATIVE: no ggw-chip', async () => {
    routedFetch();
    const c = render(<>
      <GgwTagsRow row={rowOf('OMH', TAGS)} room={ROOM} study={STUDY} />
      <GgwTagsRow row={rowOf('STAL', { ...TAGS, stages: null })} room={ROOM} study={STUDY} />
    </>).container;
    await settle();
    await waitFor(() => expect(c.querySelector('.cm-badge-growth')).not.toBeNull());
    const els = Array.from(c.querySelectorAll('.ggw-tags *'));
    expect(els.length).toBeGreaterThan(10);
    for (const e of els) {
      const ok = e.classList.contains('cm-badge') || !!e.closest('.gg-stages');
      expect(ok, e.outerHTML).toBe(true);
    }
    expect(c.querySelector('.ggw-tags .ggw-chip')).toBeNull();
  });

  it('NEGATIVE: nothing to print → null (no ggw-tags-* node)', async () => {
    routedFetch({ tags: {} });
    const c = render(<>
      <GgwTagsRow row={rowOf('ABSN')} room={ROOM} study={STUDY} />
      <GgwTagsRow row={rowOf('NREC', { ...TAGS, setups: [], stages: null, float: null, broker_text: null, trader_text: null, promo_text: null })} />
    </>).container;
    await settle();
    expect(c.querySelector('[data-testid^="ggw-tags-"]')).toBeNull();
    expect(c.innerHTML).toBe('');
  });

  it('NEGATIVE: the rendered row has no b-word', async () => {
    routedFetch();
    const c = mountRow(rowOf('OMH', TAGS), ROOM, STUDY);
    await settle();
    await waitFor(() => expect(c.querySelector('.cm-badge-growth')).not.toBeNull());
    expect(c.textContent!.length).toBeGreaterThan(20);
    expect(c.textContent).not.toMatch(/bounc/i);
    for (const e of Array.from(c.querySelectorAll('[title]'))) expect(e.getAttribute('title')).not.toMatch(/bounc/i);
  });
});

/* ── source guard [C3b] ── */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
const noImports = (t: string) => t.split('\n').filter((l) => !/^\s*import\b/.test(l)).join('\n');

describe('🏷️ GajjalaWatchTags source guards', () => {
  it('NEGATIVE: with import lines and comments stripped — no b-word and no ggw-chip', async () => {
    const src = await readSource('src/components/GajjalaWatchTags.tsx');
    const body = noComments(noImports(src));
    expect(body).not.toMatch(/bounc/i);
    expect(body).not.toContain('ggw-chip');
    /* the guard is not vacuous: the raw file does import the room hook */
    expect(src).toMatch(/bounc/i);
    expect(body).toContain('useRoomRead(');
  });
});
