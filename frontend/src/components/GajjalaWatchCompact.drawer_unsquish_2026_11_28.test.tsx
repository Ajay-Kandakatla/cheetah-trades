/* 🗂 The ⋯ drawer of a compact 👀 Watch tile, un-squished (2026-11-28). Ajay, on the NXAT tile with the drawer open over
 * the 5-min chart: "On the cards for show details can you make them available they are getting squished.. Ad the tags to be
 * scrollable".
 * Desktop: the drawer takes the tile's whole height below the head (no 70% cap) and scrolls down inside itself; its lines
 * wrap. Every width: the drawer's tags row is ONE line that scrolls sideways — each chip whole, no ellipsis. The fitted
 * tile-head tags row OUTSIDE the drawer keeps its 11-16 one-line ellipsis (NEGATIVE). Planting the pre-fix sheet fails
 * every check (NEGATIVE). Display only. */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import board from '../lib/__fixtures__/ggwAllRules.golden.json';
import { parseGgw, type GgwBoard, type GgwRow } from '../lib/gajjalaWatch';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';
import { GgwDrawer } from './GajjalaWatchCompact';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

/* ── a small CSS reader: every rule with its @media context and its selector list ─────────────────────────────── */
type Rule = { media: string | null; sels: string[]; body: string };
const norm = (s: string) => s.replace(/\s+/g, ' ').trim();
function parseCss(src: string): Rule[] {
  const css = src.replace(/\/\*[\s\S]*?\*\//g, '');
  const out: Rule[] = [];
  const walk = (text: string, media: string | null) => {
    let i = 0;
    while (i < text.length) {
      const open = text.indexOf('{', i);
      if (open < 0) break;
      const head = norm(text.slice(i, open));
      let depth = 1;
      let j = open + 1;
      while (j < text.length && depth > 0) { if (text[j] === '{') depth += 1; else if (text[j] === '}') depth -= 1; j += 1; }
      const inner = text.slice(open + 1, j - 1);
      if (head.startsWith('@media')) walk(inner, head);
      else if (!head.startsWith('@')) out.push({ media, sels: head.split(',').map(norm), body: inner });
      i = j;
    }
  };
  walk(css, null);
  return out;
}
const DESK = '@media (min-width: 641px)';
const bodyOf = (rules: Rule[], media: string | null, sel: string): string | null => {
  const hits = rules.filter((r) => r.media === media && r.sels.includes(sel));
  return hits.length ? hits.map((r) => r.body).join(';') : null;
};
/** class / attribute / pseudo-class count (the selectors here carry no ids). */
const spec = (sel: string) => (sel.replace(/::[\w-]+/g, '').match(/\.[\w-]+|\[[^\]]*\]|:[\w-]+/g) || []).length;

/* the in-drawer selectors this fix adds (desktop) and their base twins (phone / every width) */
const D = '.ggw-grid--fit .ggw-tile--compact .ggw-drawer';
const DESK_ROW = `${D} .ggw-tags`;
const DESK_CHIPS = [`${D} .ggw-tags > *`, `${D} .ggw-tags .gg-stages > *`];
const DESK_STAGES = `${D} .ggw-tags .gg-stages`;
const B = '.ggw-tile--compact .ggw-drawer';
const BASE_ROW = `${B} .ggw-tags`;
const BASE_CHIPS = [`${B} .ggw-tags > *`, `${B} .ggw-tags .gg-stages > *`, `${B} .ggw-tags .cm-badge`, `${B} .ggw-tags .gg-stage`];

const drawerFills = (rules: Rule[]) => {
  const d = bodyOf(rules, DESK, '.ggw-tile--compact .ggw-drawer');
  return !!d && /position:\s*absolute/.test(d) && /top:\s*34px/.test(d) && /bottom:\s*8px/.test(d)
    && !/max-height:\s*70%/.test(d) && /overflow-y:\s*auto/.test(d) && /overscroll-behavior:\s*contain/.test(d);
};
const scrollsSideways = (d: string | null) => !!d && /overflow-x:\s*auto/.test(d) && /flex-wrap:\s*nowrap/.test(d)
  && /flex:\s*none/.test(d) && !/overflow:\s*hidden/.test(d);
const chipWhole = (d: string | null) => !!d && /white-space:\s*nowrap/.test(d) && /flex:\s*none/.test(d)
  && !/text-overflow:\s*ellipsis/.test(d) && !/overflow:\s*hidden/.test(d) && /text-overflow:\s*clip/.test(d);
const deskInDrawer = (rules: Rule[]) => scrollsSideways(bodyOf(rules, DESK, DESK_ROW))
  && DESK_CHIPS.every((s) => chipWhole(bodyOf(rules, DESK, s)))
  && /flex-wrap:\s*nowrap/.test(bodyOf(rules, DESK, DESK_STAGES) ?? '');
const baseInDrawer = (rules: Rule[]) => {
  const row = bodyOf(rules, null, BASE_ROW);
  return scrollsSideways(row) && /max-width:\s*100%/.test(row!) && /min-width:\s*0\b/.test(row!)
    && /-webkit-overflow-scrolling:\s*touch/.test(row!) && /scrollbar-width:\s*thin/.test(row!)
    && BASE_CHIPS.every((s) => chipWhole(bodyOf(rules, null, s)));
};
/** the fitted tile-head row OUTSIDE the drawer — the 11-16 GP one-line ellipsis rule */
const outsideEllipsis = (rules: Rule[]) => {
  const row = bodyOf(rules, DESK, '.ggw-grid--fit .ggw-tags');
  const kids = bodyOf(rules, DESK, '.ggw-grid--fit .ggw-tags > *');
  return !!row && /flex-wrap:\s*nowrap/.test(row) && /overflow:\s*hidden/.test(row)
    && !!kids && /white-space:\s*nowrap/.test(kids) && /text-overflow:\s*ellipsis/.test(kids) && /overflow:\s*hidden/.test(kids);
};

/* the sheet as it stood before the fix (its drawer and tags rules, verbatim) */
const PRE_FIX = `.ggw-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 0.25rem 0.45rem; min-width: 0; max-width: 100%; margin: 0 0 2px; }
.ggw-tags .cm-badge, .ggw-tags .gg-stage, .ggw-tags .gg-stages { white-space: normal; overflow-wrap: anywhere; min-width: 0; max-width: 100%; }
.ggw-tags .gg-stages { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; font-size: 0.74rem; margin: 0; }
@media (min-width: 641px) {
  .ggw-grid--fit .ggw-tags { flex: none; flex-wrap: nowrap; overflow: hidden; }
  .ggw-grid--fit .ggw-tags > *, .ggw-grid--fit .ggw-tags .gg-stages > * { flex: 0 1 auto; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ggw-grid--fit .ggw-tags .gg-stages { flex-wrap: nowrap; overflow: hidden; }
  .ggw-grid--stretch.ggw-grid--fit .ggw-tags, .ggw-grid--stretch.ggw-grid--fit .ggw-tags .gg-stages { flex-wrap: wrap; overflow: visible; }
  .ggw-grid--stretch.ggw-grid--fit .ggw-tags > *, .ggw-grid--stretch.ggw-grid--fit .ggw-tags .gg-stages > * { white-space: normal; overflow: visible; text-overflow: clip; }
}
.ggw-drawer .ggw-tags { margin: 0; }
@media (min-width: 641px) {
  .ggw-tile--compact .ggw-drawer {
    position: absolute; left: 8px; right: 8px; top: 34px; z-index: 2; max-height: 70%; overflow: auto;
    background: rgb(13, 17, 23); border-style: solid; box-shadow: 0 6px 24px rgba(0, 0, 0, 0.55);
  }
  .ggw-grid--stretch .ggw-tile--compact .ggw-drawer { position: static; max-height: none; box-shadow: none; }
}`;

describe('🗂 drawer un-squish — the stylesheet', () => {
  let rules: Rule[] = [];
  beforeEach(async () => { rules = parseCss(await readSource('src/styles/gajjalaWatch.css')); });

  it('desktop: the drawer takes the tile height below the head (top 34px · bottom 8px), no 70% cap, scrolls down inside itself', () => {
    expect(drawerFills(rules)).toBe(true);
    expect(bodyOf(rules, DESK, '.ggw-tile--compact .ggw-drawer > *')).toMatch(/flex:\s*none/);
  });
  it('desktop: the drawer\'s served levels line wraps (no ellipsis inside the drawer)', () => {
    const d = bodyOf(rules, DESK, `${D} .ggw-levels`);
    expect(d).toMatch(/white-space:\s*normal/);
    expect(d).toMatch(/text-overflow:\s*clip/);
    expect(d).not.toMatch(/ellipsis/);
    expect(spec(`${D} .ggw-levels`)).toBeGreaterThan(spec('.ggw-grid--fit .ggw-levels'));
  });
  it('desktop: the in-drawer tags row scrolls sideways one line; every chip whole (nowrap, clip, no overflow hidden)', () => {
    expect(deskInDrawer(rules)).toBe(true);
  });
  it('desktop: the in-drawer rules out-rank EVERY fitted / ⤢ tags rule by specificity (not by source order)', () => {
    const tagRules = rules.filter((r) => r.media === DESK).flatMap((r) => r.sels)
      .filter((s) => /\.ggw-tags/.test(s) && !/\.ggw-drawer/.test(s));
    const rowRivals = tagRules.filter((s) => /\.ggw-tags$/.test(s));
    const stageRivals = tagRules.filter((s) => /\.gg-stages$/.test(s));
    const kidRivals = tagRules.filter((s) => /> \*$/.test(s));
    expect(rowRivals.length).toBeGreaterThanOrEqual(2);
    expect(stageRivals.length).toBeGreaterThanOrEqual(2);
    expect(kidRivals.length).toBeGreaterThanOrEqual(4);
    const maxKid = Math.max(...kidRivals.map(spec));
    expect(spec(DESK_ROW)).toBeGreaterThan(Math.max(...rowRivals.map(spec)));
    expect(spec(DESK_STAGES)).toBeGreaterThan(Math.max(...stageRivals.map(spec)));
    expect(spec(DESK_CHIPS[1])).toBeGreaterThan(maxKid);
    expect(spec(DESK_CHIPS[0])).toBeGreaterThan(Math.max(...kidRivals.filter((s) => !/gg-stages/.test(s)).map(spec)));
  });
  it('phone / every width: the base twin scrolls inside itself (max-width 100%, min-width 0, touch, thin bar) and beats the base wrap rules', () => {
    expect(baseInDrawer(rules)).toBe(true);
    expect(spec(BASE_ROW)).toBeGreaterThan(spec('.ggw-tags'));
    for (const s of BASE_CHIPS) expect(spec(s)).toBeGreaterThan(spec('.ggw-tags .gg-stages'));
    expect(bodyOf(rules, null, `${B} .ggw-tags .gg-stages`)).toMatch(/flex-wrap:\s*nowrap/);
    expect(spec(`${B} .ggw-tags .gg-stages`)).toBeGreaterThan(spec('.ggw-tags .gg-stages'));
    expect(bodyOf(rules, null, `${B} .ggw-tags::-webkit-scrollbar`)).toMatch(/height:\s*4px/);
  });
  it('NEGATIVE: the phone drawer stays static — no base (un-media\'d) rule positions the drawer; the ⤢ drawer stays static', () => {
    const base = rules.filter((r) => r.media === null && r.sels.some((s) => /\.ggw-drawer$/.test(s)));
    expect(base.length).toBeGreaterThan(0);
    for (const r of base) expect(r.body).not.toMatch(/position:\s*(absolute|fixed)/);
    expect(bodyOf(rules, DESK, '.ggw-grid--stretch .ggw-tile--compact .ggw-drawer')).toMatch(/position:\s*static/);
    expect(spec('.ggw-grid--stretch .ggw-tile--compact .ggw-drawer')).toBeGreaterThan(spec('.ggw-tile--compact .ggw-drawer'));
  });
  it('NEGATIVE: the fitted tile-head tags row OUTSIDE the drawer keeps its one-line ellipsis (11-16 GP rule) — unchanged', () => {
    expect(outsideEllipsis(rules)).toBe(true);
    expect(bodyOf(rules, DESK, '.ggw-grid--fit .ggw-tags .gg-stages')).toMatch(/overflow:\s*hidden/);
  });
  it('NEGATIVE: no in-drawer tags rule anywhere carries an ellipsis or overflow hidden', () => {
    const inDrawer = rules.filter((r) => r.sels.some((s) => /\.ggw-drawer .*\.ggw-tags/.test(s)));
    expect(inDrawer.length).toBeGreaterThanOrEqual(6);
    for (const r of inDrawer) {
      expect(r.body, r.sels.join(',')).not.toMatch(/text-overflow:\s*ellipsis/);
      expect(r.body, r.sels.join(',')).not.toMatch(/overflow:\s*hidden/);
    }
  });
  it('NEGATIVE: the pre-fix sheet fails every new check (and still passes the outside-row one)', () => {
    const pre = parseCss(PRE_FIX);
    expect(drawerFills(pre)).toBe(false);
    expect(deskInDrawer(pre)).toBe(false);
    expect(baseInDrawer(pre)).toBe(false);
    expect(outsideEllipsis(pre)).toBe(true);
    expect(bodyOf(pre, DESK, '.ggw-tile--compact .ggw-drawer')).toMatch(/max-height:\s*70%/);
  });
  it('NEGATIVE: re-planting the 70% cap or an ellipsis on the in-drawer chips fails the checks', async () => {
    const live = await readSource('src/styles/gajjalaWatch.css');
    const capped = live.replace(/bottom:\s*8px;\s*z-index:\s*2;\s*max-height:\s*none;/, 'z-index: 2; max-height: 70%;');
    expect(capped).not.toBe(live);
    expect(drawerFills(parseCss(capped))).toBe(false);
    const cut = live.replace(/(\.gg-stages > \* \{ flex: none; white-space: nowrap; overflow: )visible; text-overflow: clip;/,
      '$1hidden; text-overflow: ellipsis;');
    expect(cut).not.toBe(live);
    expect(deskInDrawer(parseCss(cut))).toBe(false);
  });
});

/* ── the mount: the tags row lives INSIDE the drawer and wears the class the CSS targets ─────────────────────────── */
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const TAGS = {
  on_board: true,
  setups: [{ setup: 'tennis', label: 'served-label-tennis', state: 'armed', state_label: null },
           { setup: 'squeeze', label: 'served-label-squeeze', state: 'armed', state_label: null }],
  stages: null, float: null, broker_text: null, trader_text: null, promo_text: null,
};
function rowOf(tags: unknown): GgwRow {
  const raw = clone(board) as any;
  raw.rows[0].tags = tags;
  raw.rows[0].float = null;
  return (parseGgw(raw) as GgwBoard).rows[0];
}

describe('🗂 drawer un-squish — the mount', () => {
  beforeEach(() => {
    _resetShortInterestCache(); _resetGrowthTagsCache();
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetShortInterestCache(); _resetGrowthTagsCache(); });

  it('GgwDrawer with tags: the .ggw-tags row is the drawer\'s FIRST child, inside the drawer, every served chip in it', () => {
    const r = rowOf(TAGS);
    render(<GgwDrawer row={r} open tags={{ room: null, study: null }} />);
    const drawer = screen.getByTestId(`ggw-drawer-${r.symbol}`);
    const row = screen.getByTestId(`ggw-tags-${r.symbol}`);
    expect(drawer.className).toBe('ggw-drawer');
    expect(row.className).toBe('ggw-tags');
    expect(row.closest('.ggw-drawer')).toBe(drawer);
    expect(drawer.firstElementChild).toBe(row);
    expect(screen.getByTestId(`ggw-setup-${r.symbol}-tennis`).parentElement).toBe(row);
    expect(screen.getByTestId(`ggw-setup-${r.symbol}-squeeze`).textContent).toBe('served-label-squeeze');
    expect(row.getAttribute('style')).toBeNull();
  });
  it('the compact tile wears .ggw-tile--compact and mounts the drawer only when compact (what the CSS prefix needs)', async () => {
    const src = await readSource('src/components/GajjalaWatchTile.tsx');
    expect(src).toMatch(/className=\{`ggw-tile\$\{compact \? ' ggw-tile--compact' : ''\}/);
    expect(src).toMatch(/\{compact \? <GgwDrawer /);
  });
  it('NEGATIVE: no tags ctx → no tags row in the drawer; an off-board tags block with nothing served → none either', () => {
    const r = rowOf(TAGS);
    const a = render(<GgwDrawer row={r} open />);
    expect(a.container.querySelector('.ggw-drawer .ggw-tags')).toBeNull();
    a.unmount();
    const off = rowOf({ ...TAGS, on_board: false });
    const b = render(<GgwDrawer row={off} open tags={{ room: null, study: null }} />);
    expect(b.container.querySelector('.ggw-drawer .ggw-tags')).toBeNull();
  });
  it('NEGATIVE: the compact component adds no inline style / nowrap / overflow to the drawer or its tags', async () => {
    const src = await readSource('src/components/GajjalaWatchCompact.tsx');
    const lines = src.split('\n').filter((l) => /ggw-drawer"|<GgwTagsRow/.test(l));
    expect(lines.length).toBe(2);
    for (const l of lines) expect(l).not.toMatch(/style=|nowrap|overflow/);
  });
});
