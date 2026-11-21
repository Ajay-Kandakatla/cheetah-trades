/* 🔢 GgwTagsRow — the float chip on EVERY 👀 Watch row (2026-11-21, spec watchfloat §3.5, WP fe-float).
 * Ajay 2026-11-21: "can you add the current float value also to the tickers on the watch list."
 * The REAL hooks (useShortInterest, useGrowthTags) over fetch routed by PATHNAME, as GajjalaWatchTags.test.tsx does.
 * Every word is a stand-in for a served one. NEGATIVES: ONE chip per row, never two (carded + row float); float null and
 * nothing else → the row is null; suspect_text null → no warn chip; one skin; source guards (no typed float words, no
 * broker name, the testid literal once). Display only; UNMEASURED. */
import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import { GgwTagsRow } from './GajjalaWatchTags';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';
import { parseGgw, parseRowFloat, type GgwBoard, type GgwRow, type GgwRowFloat, type GgwRowTags } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SI_PATH = '/short-interest/map';
const GROWTH_PATH = '/growth/tags';
const SI: Record<string, unknown> = {
  OMH: { symbol: 'OMH', status: 'ok', chip: '🩳 SI 359.4K sh · 19.5d · 10/30', title: 'served SI hover', rows: [], extreme: null },
};
const GROWTH = { tags: { OMH: { sales: 120, eps: 80, refused: false } } };

let calls: string[] = [];
const pathOf = (u: string) => new URL(u, 'http://x').pathname;
const symsOf = (u: string) => decodeURIComponent(new URL(u, 'http://x').searchParams.get('symbols') || '').split(',').filter(Boolean);
function routedFetch(growth: unknown = GROWTH) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    calls.push(url);
    if (pathOf(url).endsWith(SI_PATH)) {
      const out: Record<string, unknown> = {};
      for (const s of symsOf(url)) if (SI[s]) out[s] = SI[s];
      return { ok: true, json: async () => ({ items: out, n: Object.keys(out).length, max_symbols: 200 }) } as unknown as Response;
    }
    if (pathOf(url).endsWith(GROWTH_PATH)) return { ok: true, json: async () => growth } as unknown as Response;
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
}
async function settle() {
  await waitFor(() => {
    expect(calls.some((u) => pathOf(u).endsWith(SI_PATH))).toBe(true);
    expect(calls.some((u) => pathOf(u).endsWith(GROWTH_PATH))).toBe(true);
  });
  await new Promise((r) => setTimeout(r, 30));
}

const BASE = (parseGgw(clone(autoFixture)) as GgwBoard).rows[0];
function rowOf(sym: string, tags: GgwRowTags | null = null, float: GgwRowFloat | null = null, extra: Partial<GgwRow> = {}): GgwRow {
  return { ...clone(BASE), symbol: sym, auto: null, aplus: null, tags, float, ...extra };
}
const FL = parseRowFloat({
  shares: 1800000.0, src: 'served-src', text: 'served row float 1.8', as_of: '2026-11-20T09:06:00+00:00', suspect: false,
  suspect_text: null, title: 'served row hover — read 2026-11-20 04:06 ET', read_from: 'cache',
})!;
const SUS = parseRowFloat({ ...FL, suspect: true, suspect_text: 'served suspect words with numbers' })!;
const TAGS: GgwRowTags = {
  on_board: true,
  setups: [{ setup: 'reversal_squeeze', label: '🎾 served label RS', state: 'forming', state_label: 'served RS state' }],
  stages: null,
  float: { text: 'served tags float 3.2', shares: 3200000, src: 'served', as_of: '2026-11-17', suspect: false },
  broker_text: null, trader_text: '📌 served trader', promo_text: null,
};
const ROW_BROKER = '🚫 served row broker word';

const mountRow = (row: GgwRow) => render(<GgwTagsRow row={row} />).container;
const rowEl = (c: ParentNode, s: string) => c.querySelector(`[data-testid="ggw-tags-${s}"]`) as HTMLElement | null;
const kinds = (r: HTMLElement) => Array.from(r.children).map((e) => e.getAttribute('data-testid') ?? e.className);

describe('🔢 the float chip on GgwTagsRow', { timeout: 20000 }, () => {
  beforeEach(() => { _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache(); });
  afterEach(() => {
    cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks();
    _resetShortInterestCache(); _resetBounceRoomCache(); _resetGrowthTagsCache();
  });

  it('an UNCARDED row with row.float → ONE ggw-float chip: served text, served title verbatim; order growth, si, broker, float', async () => {
    routedFetch();
    const c = mountRow(rowOf('OMH', null, FL, { broker_text: ROW_BROKER }));
    await settle();
    await waitFor(() => expect(c.querySelector('.cm-badge-growth')).not.toBeNull());
    const r = rowEl(c, 'OMH')!;
    const chips = r.querySelectorAll('[data-testid="ggw-float-OMH"]');
    expect(chips).toHaveLength(1);
    expect(chips[0].textContent).toBe(FL.text);
    expect(chips[0].getAttribute('title')).toBe(FL.title);
    expect(chips[0].className).toBe('cm-badge cm-badge-muted ggw-float');
    expect(kinds(r)).toEqual(['cm-badge cm-badge-growth', 'si-chip', 'ggw-broker-OMH', 'ggw-float-OMH']);
    /* without a broker word: the float follows the 🩳 chip */
    cleanup(); _resetShortInterestCache(); _resetGrowthTagsCache();
    routedFetch();
    const c2 = mountRow(rowOf('OMH', null, FL));
    await settle();
    await waitFor(() => expect(c2.querySelector('.cm-badge-growth')).not.toBeNull());
    expect(kinds(rowEl(c2, 'OMH')!)).toEqual(['cm-badge cm-badge-growth', 'si-chip', 'ggw-float-OMH']);
  });

  it('an uncarded row with ONLY the float still draws the row (the guard counts it)', async () => {
    routedFetch({ tags: {} });
    const c = mountRow(rowOf('NREC', null, FL));
    await settle();
    expect(kinds(rowEl(c, 'NREC')!)).toEqual(['ggw-float-NREC']);
  });

  it('a CARDED row with both floats → exactly ONE node printing row.float, at the card spot (after broker) — NEGATIVE: never two', async () => {
    routedFetch();
    const c = mountRow(rowOf('OMH', TAGS, FL, { broker_text: ROW_BROKER }));
    await settle();
    await waitFor(() => expect(c.querySelector('.cm-badge-growth')).not.toBeNull());
    const r = rowEl(c, 'OMH')!;
    expect(r.querySelectorAll('.ggw-float')).toHaveLength(1);
    expect(r.querySelector('[data-testid="ggw-float-OMH"]')!.textContent).toBe(FL.text);
    expect(r.querySelector('[data-testid="ggw-float-OMH"]')!.getAttribute('title')).toBe(FL.title);
    expect(r.textContent).not.toContain(TAGS.float!.text);
    const k = kinds(r);
    expect(k.indexOf('ggw-float-OMH')).toBe(k.indexOf('ggw-broker-OMH') + 1);
    expect(k.indexOf('ggw-float-OMH')).toBeLessThan(k.indexOf('ggw-setup-OMH-reversal_squeeze'));
  });

  it('an OLDER-server carded row (only tags.float) → ONE node with the tags text, NO title', async () => {
    routedFetch({ tags: {} });
    const c = mountRow(rowOf('OMH', TAGS, null));
    await settle();
    const r = rowEl(c, 'OMH')!;
    expect(r.querySelectorAll('.ggw-float')).toHaveLength(1);
    const el = r.querySelector('[data-testid="ggw-float-OMH"]')!;
    expect(el.textContent).toBe(TAGS.float!.text);
    expect(el.getAttribute('title')).toBeNull();
    expect(r.querySelector('.ggw-float-suspect')).toBeNull();
  });

  it('NEGATIVE: float null and nothing else → the row returns null (innerHTML "")', async () => {
    routedFetch({ tags: {} });
    const c = render(<>
      <GgwTagsRow row={rowOf('ABSN', null, null)} />
      <GgwTagsRow row={rowOf('NREC', { ...TAGS, setups: [], float: null, trader_text: null }, null)} />
    </>).container;
    await settle();
    expect(c.querySelector('[data-testid^="ggw-tags-"]')).toBeNull();
    expect(c.innerHTML).toBe('');
  });

  it('NEGATIVE: a blank row.float (built by hand, past the parser) falls to the tags float; none → no chip', async () => {
    routedFetch({ tags: {} });
    const c = render(<>
      <GgwTagsRow row={rowOf('OMH', TAGS, { ...FL, text: ' ' })} />
      <GgwTagsRow row={rowOf('ZZZ', null, { ...FL, text: '' }, { broker_text: ROW_BROKER })} />
    </>).container;
    await settle();
    expect(c.querySelector('[data-testid="ggw-float-OMH"]')!.textContent).toBe(TAGS.float!.text);
    expect(c.querySelector('[data-testid="ggw-float-ZZZ"]')).toBeNull();
  });

  it('suspect: the served suspect words in a warn chip RIGHT AFTER the float chip — uncarded and carded', async () => {
    routedFetch({ tags: {} });
    const c = render(<>
      <GgwTagsRow row={rowOf('OMH', null, SUS)} />
      <GgwTagsRow row={rowOf('CRD', TAGS, SUS)} />
    </>).container;
    await settle();
    for (const s of ['OMH', 'CRD']) {
      const r = rowEl(c, s)!;
      const sus = r.querySelectorAll(`[data-testid="ggw-float-suspect-${s}"]`);
      expect(sus, s).toHaveLength(1);
      expect(sus[0].textContent).toBe(SUS.suspect_text);
      expect(sus[0].className).toBe('cm-badge cm-badge-warn ggw-float-suspect');
      expect(r.querySelector(`[data-testid="ggw-float-${s}"]`)!.nextElementSibling).toBe(sus[0]);
      expect(r.querySelectorAll('.ggw-float')).toHaveLength(1);
    }
  });

  it('NEGATIVE: suspect_text null (even with suspect true) → no warn node', async () => {
    routedFetch({ tags: {} });
    const c = render(<>
      <GgwTagsRow row={rowOf('OMH', null, FL)} />
      <GgwTagsRow row={rowOf('SSS', null, { ...SUS, suspect_text: null })} />
      <GgwTagsRow row={rowOf('CRD', { ...TAGS, float: { ...TAGS.float!, suspect: true } }, null)} />
    </>).container;
    await settle();
    expect(c.querySelector('.ggw-float-suspect')).toBeNull();
    expect(c.querySelectorAll('.ggw-float')).toHaveLength(3);
  });

  it('one skin: every element in .ggw-tags carries cm-badge with BOTH float chips present', async () => {
    routedFetch();
    const c = render(<>
      <GgwTagsRow row={rowOf('OMH', null, SUS, { broker_text: ROW_BROKER })} />
      <GgwTagsRow row={rowOf('CRD', TAGS, SUS)} />
    </>).container;
    await settle();
    await waitFor(() => expect(c.querySelector('.cm-badge-growth')).not.toBeNull());
    expect(c.querySelectorAll('.ggw-float-suspect')).toHaveLength(2);
    const els = Array.from(c.querySelectorAll('.ggw-tags *'));
    for (const e of els) {
      const ok = e.classList.contains('cm-badge') || !!e.closest('.gg-stages');
      expect(ok, e.outerHTML).toBe(true);
    }
    expect(c.querySelector('.ggw-tags .ggw-chip')).toBeNull();
  });
});

/* ── source guards ── */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
const SERVED_WORDS = ['not realtime', 'older than', 'Float ', 'shares out', 'float unknown', 'Massive'];
/** every string literal ('…', "…", `…`) and every JSX text node of a comment-stripped source */
const literals = (body: string): string[] => [
  ...(body.match(/(['"`])(?:\\.|(?!\1)[^\\\n])*\1/g) ?? []),
  ...Array.from(body.matchAll(/>([^<>{}\n]+)</g), (m) => m[1]),
];

describe('🔢 source guards', () => {
  it('NEGATIVE: GajjalaWatchTags.tsx and gajjalaWatch.ts carry none of the served float words as a literal', async () => {
    for (const f of ['src/components/GajjalaWatchTags.tsx', 'src/lib/gajjalaWatch.ts']) {
      const lits = literals(noComments(await readSource(f)));
      expect(lits.length, f).toBeGreaterThan(5);                       // not vacuous
      for (const w of SERVED_WORDS) {
        expect(lits.filter((l) => l.includes(w)), `${f}: ${w}`).toEqual([]);
        expect(lits.filter((l) => l.toLowerCase().includes(w.trim().toLowerCase()) && w !== 'Float '), `${f}: ${w} (any case)`).toEqual([]);
      }
    }
    /* the scanner sees the chip's own class literal (so a typed word there would be caught) */
    expect(literals(noComments(await readSource('src/components/GajjalaWatchTags.tsx')))
      .some((l) => l.includes('ggw-float'))).toBe(true);
    expect(literals('const a = "Float 1.8M";').some((l) => l.includes('Float '))).toBe(true);   // the guard bites
  });
  it('NEGATIVE: no broker name / "not eligible" anywhere in either file (comments included)', async () => {
    for (const f of ['src/components/GajjalaWatchTags.tsx', 'src/lib/gajjalaWatch.ts']) {
      expect(await readSource(f), f).not.toMatch(/fidelity|not eligible/i);
    }
  });
  it('the ggw-float-${sym} literal appears exactly ONCE; ggwFloat( called once; no tags-only float read left', async () => {
    const src = await readSource('src/components/GajjalaWatchTags.tsx');
    expect(src.split('ggw-float-${sym}')).toHaveLength(2);
    expect(noComments(src).match(/ggwFloat\(/g)).toHaveLength(1);
    expect(noComments(src)).not.toMatch(/t\.float\b/);
    const lib = await readSource('src/lib/gajjalaWatch.ts');
    expect(lib).toMatch(/export function parseRowFloat\(/);
    expect(lib).toMatch(/export function ggwFloat\(/);
    expect(lib).toMatch(/float: parseRowFloat\(v\.float\)/);
  });
});
