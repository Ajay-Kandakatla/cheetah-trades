/* 📈 Bonde table density (Ajay 2026-09-28: "Once done can you fix this table
 * too? so much empty space").
 *
 * The REAL /bonde/board, bounce-room, growth-tags and promo-tags payloads
 * (captured 2026-09-28, trimmed to 14 rows that hold every served extreme) are
 * drawn through the REAL BondeBoard. jsdom lays nothing out, so this file pins
 * the STRUCTURE the CSS relies on (three ticker lines, one scroll box per
 * section, the served-rows EP collapse) and that NO DATUM was removed: every
 * row's text / titles / test ids / links deep-equal a golden written on the
 * UNCHANGED component (HEAD a2f6144, before the re-pack). The real-browser
 * check is scripts/bonde-layout-probe.mjs, fed by the gated snapshot writer
 * at the bottom. docs/sepa/bonde_table_density_2026_09_28.md */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BondeBoard, { pivotColumnEmpty, type BondeRow } from './BondeBoard';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';
import { _resetPromoOriginCache } from '../hooks/usePromoOriginTags';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import REAL from './__fixtures__/bonde_real_2026_09_28.json';

const GOLDEN_REL = 'src/components/__fixtures__/bonde_real_2026_09_28.golden.json';

type Fixture = { board: any; bounce_room: any; growth_tags: any; promo_tags: any };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const env = (k: string): string | undefined =>
  (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.[k];

async function fsMod(): Promise<any> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  return mod?.default || mod;
}
const root = () => (globalThis as any).process?.cwd?.() || '.';

function stub(F: Fixture) {
  vi.stubGlobal('fetch', vi.fn(async (url: any) => {
    const u = String(url);
    const body = u.includes('/bonde/board') ? F.board
      : u.includes('/supply-demand/bounce-room') ? F.bounce_room
      : u.includes('/growth/tags') ? F.growth_tags
      : u.includes('/catalysts/promo-curate/tags') ? F.promo_tags
      : u.includes('/signal-lab/watchlist') ? { symbols: [] }
      : {};
    return { ok: true, status: 200, json: async () => clone(body) } as any;
  }));
}

const rowOf = (container: HTMLElement, sym: string): HTMLElement =>
  container.querySelector(`[data-testid="bd-today-${sym}"]`)!.closest('.bd-row') as HTMLElement;

async function drawReal(F: Fixture = REAL as Fixture) {
  stub(F);
  const utils = render(<MemoryRouter><BondeBoard /></MemoryRouter>);
  const first = F.board.sections.explosive[0].symbol as string;
  await screen.findByTestId(`bd-today-${first}`);
  await waitFor(() => {
    const r = rowOf(utils.container, first);
    expect(r.querySelector('.cm-badge-band, .cm-badge-band-muted')).not.toBeNull();
  });
  // the growth tags are a second fetch: wait for them, or the golden races
  const tagged = Object.keys(F.growth_tags?.tags || {})
    .find((s) => utils.container.querySelector(`[data-testid="bd-today-${s}"]`));
  if (tagged) {
    await waitFor(() => expect(rowOf(utils.container, tagged).querySelector('.bd-gchip-growth, .bd-gchip-bad'))
      .not.toBeNull());
  }
  return utils;
}

/** Order-insensitive facts of one row: what a reader can get out of it. */
function rowFacts(rowEl: Element) {
  const texts: string[] = [];
  const walker = document.createTreeWalker(rowEl, NodeFilter.SHOW_TEXT);
  for (let t = walker.nextNode(); t; t = walker.nextNode()) {
    const s = (t.textContent || '').replace(/\s+/g, ' ').trim();
    if (s) texts.push(s);
  }
  const attr = (sel: string, a: string) =>
    [...rowEl.querySelectorAll(sel)].map((e) => e.getAttribute(a) || '').sort();
  return {
    texts: texts.sort(),
    titles: attr('[title]', 'title'),
    testids: attr('[data-testid]', 'data-testid'),
    hrefs: attr('a[href]', 'href'),
  };
}

const bodyRows = (container: HTMLElement) =>
  [...container.querySelectorAll('.bd-row:not(.bd-hdr)')] as HTMLElement[];
const symOf = (rowEl: Element) => rowEl.querySelector('.bd-today')!.getAttribute('data-testid')!.replace('bd-today-', '');
const sectionOf = (container: HTMLElement, key: string) =>
  container.querySelector(`[data-testid="bd-scroll-${key}"]`)!.closest('section') as HTMLElement;

async function loadGolden(): Promise<Record<string, ReturnType<typeof rowFacts>>> {
  const fs = await fsMod();
  return JSON.parse(fs.readFileSync(`${root()}/${GOLDEN_REL}`, 'utf8'));
}

beforeEach(() => {
  vi.unstubAllGlobals();
  _resetBounceRoomCache();
  _resetGrowthTagsCache();
  _resetPromoOriginCache();
  _resetSignalWatchlist([]);
});
afterEach(() => { vi.unstubAllGlobals(); });

const withPivot = (F: Fixture, sym: string, section = 'explosive'): Fixture => {
  const G = clone(F);
  const r = G.board.sections[section].find((x: any) => x.symbol === sym);
  r.pivot = { gap_pct: 9.1, vol_mult: 5.2, hours_ago: 20 };
  return G;
};

// ───────────────────────────────────────────── gated writers (run by hand)
describe('gated writers', () => {
  it.runIf(!!env('BD_GOLDEN_WRITE'))('writes the no-datum-removed golden (run on UNCHANGED HEAD a2f6144)', async () => {
    const { container } = await drawReal();
    const out: Record<string, ReturnType<typeof rowFacts>> = {};
    for (const r of bodyRows(container)) out[symOf(r)] = rowFacts(r);
    const fs = await fsMod();
    fs.writeFileSync(`${root()}/${GOLDEN_REL}`, JSON.stringify(out, null, 1) + '\n', 'utf8');
    expect(Object.keys(out).length).toBe(14);
  });

  it.runIf(!!env('BD_LAYOUT_SNAPSHOT'))('writes the rendered board for the real-browser probe', async () => {
    const prefix = env('BD_LAYOUT_SNAPSHOT')!;
    const fs = await fsMod();
    const alt = env('BD_LAYOUT_FIXTURE');
    const F: Fixture = alt ? JSON.parse(fs.readFileSync(alt, 'utf8')) : (REAL as Fixture);
    const { container, unmount } = await drawReal(F);
    fs.writeFileSync(`${prefix}.html`, container.innerHTML, 'utf8');
    unmount();
    if (!alt) {
      _resetBounceRoomCache(); _resetGrowthTagsCache(); _resetPromoOriginCache();
      const v = await drawReal(withPivot(REAL as Fixture, 'LQDA'));
      fs.writeFileSync(`${prefix}-pivot.html`, v.container.innerHTML, 'utf8');
    }
  });
});

// ───────────────────────────────────────────── the real payload
describe('the real 2026-09-28 payload, drawn through the real board', () => {
  it('T1 draws the served order and the served counts', async () => {
    const { container } = await drawReal();
    const F = REAL as Fixture;
    for (const key of ['explosive', 'strong', 'rejected']) {
      const sec = sectionOf(container, key);
      const got = bodyRows(sec).map(symOf);
      expect(got).toEqual(F.board.sections[key].map((r: any) => r.symbol));
      expect(sec.querySelector('.bd-count')!.textContent)
        .toBe(`${got.length} of ${F.board.counts[key]}`);
    }
    expect(bodyRows(sectionOf(container, 'explosive')).map(symOf))
      .toEqual(['PTGX', 'LQDA', 'ONDS', 'PFSI', 'ARR', 'NLY', 'DBRG', 'ASST', 'SBET', 'VEEA']);
  });

  it('T2 every ticker cell is exactly three lines, and nothing else is a direct child', async () => {
    const { container } = await drawReal();
    for (const r of bodyRows(container)) {
      const sym = r.querySelector(':scope > .bd-sym')!;
      const kids = [...sym.children].map((c) => c.className.split(' ')[0]);
      expect(kids).toEqual(['bd-sym-l1', 'bd-sym-l2', 'bd-pick']);
      for (const c of sym.children) {
        expect(c.matches('.bd-coname, .cm-watch, .bd-gchip, .cm-badge, .bd-dchip, .bd-new')).toBe(false);
      }
    }
  });

  it('T3 line 1 is the identity: ticker ☆, company, ✨ NEW, then + Signals last', async () => {
    const { container } = await drawReal();
    for (const r of bodyRows(container)) {
      const s = symOf(r);
      const l1 = r.querySelector('.bd-sym-l1')!;
      expect(l1.children[0].querySelector('a.tk-link')!.textContent).toBe(s);
      expect(l1.querySelector('.bd-coname')).not.toBeNull();
      expect(l1.lastElementChild!.getAttribute('data-testid')).toBe(`watch-${s}`);
    }
    const veea = rowOf(container, 'VEEA');
    expect(veea.querySelector('.bd-sym-l1 [data-testid="bd-new-VEEA"]')).not.toBeNull();
  });

  it('T4 line 2 holds the live reads, the 🪜 sentence last', async () => {
    const { container } = await drawReal();
    const l2 = rowOf(container, 'PTGX').querySelector('.bd-sym-l2')!;
    expect(l2.querySelector('.bd-dchip')!.textContent).toBe('🎯 in demand band');
    expect(l2.querySelector('.bd-gchip-growth')).not.toBeNull();
    expect(l2.querySelector('[class*="bd-gchip-explosive"], .bd-gchip.explosive, .bd-gchip[class*="explosive"]')
      ?? l2.querySelector('.bd-gchip:not(.bd-gchip-growth):not([class*="enterable"])')).not.toBeNull();
    expect(l2.querySelector('[class*="bd-gchip-enterable-"]')).not.toBeNull();
    const band = l2.querySelector('.cm-badge-band, .cm-badge-band-muted')!;
    expect(band).not.toBeNull();
    expect(l2.lastElementChild).toBe(band);
  });

  it('T5 NO DATUM REMOVED — every row equals the golden written on the unchanged board', async () => {
    const golden = await loadGolden();
    const { container } = await drawReal();
    const rows = bodyRows(container);
    expect(rows.map(symOf).sort()).toEqual(Object.keys(golden).sort());
    for (const r of rows) expect(rowFacts(r)).toEqual(golden[symOf(r)]);
  });

  it('T6 NEGATIVE — the golden sees a drop (company, 🪜, one 📋 chip)', async () => {
    const golden = await loadGolden();
    const { container } = await drawReal();
    const base = rowOf(container, 'PTGX');
    expect(rowFacts(base)).toEqual(golden.PTGX);
    for (const sel of ['.bd-coname', '.cm-badge-band, .cm-badge-band-muted', '.bd-pick-chip']) {
      const c = base.cloneNode(true) as HTMLElement;
      c.querySelector(sel)!.remove();
      expect(rowFacts(c)).not.toEqual(golden.PTGX);
    }
  });

  it('T7 EP collapses where EVERY served row has no pivot; the body still prints —', async () => {
    const { container } = await drawReal();
    for (const key of ['explosive', 'strong', 'rejected']) {
      const sec = sectionOf(container, key);
      expect(sec.querySelector('.bd-rows')!.classList.contains('bd-rows--pivot-empty')).toBe(true);
      const head = sec.querySelector('.bd-hdr .bd-pivot')!;
      expect(head.textContent).toBe('EP');
      expect(head.getAttribute('title')!.startsWith('Episodic pivot (EP).')).toBe(true);
      expect(head.getAttribute('aria-label')).toBe('Episodic pivot');
      for (const r of bodyRows(sec)) expect(r.querySelector('.bd-pivot')!.textContent).toBe('—');
    }
  });

  it('T8 NEGATIVE — a single pivot keeps its section wide; the others stay collapsed', async () => {
    const { container } = await drawReal(withPivot(REAL as Fixture, 'LQDA'));
    const ex = sectionOf(container, 'explosive');
    expect(ex.querySelector('.bd-rows')!.classList.contains('bd-rows--pivot-empty')).toBe(false);
    expect(ex.querySelector('.bd-hdr .bd-pivot')!.textContent).toBe('Episodic pivot');
    expect(rowOf(container, 'LQDA').querySelector('.bd-pivot')!.textContent).toContain('gap +9.1%');
    for (const key of ['strong', 'rejected']) {
      expect(sectionOf(container, key).querySelector('.bd-rows')!.classList
        .contains('bd-rows--pivot-empty')).toBe(true);
    }
  });

  it('T9 NEGATIVE — served, not filtered: a hidden pivot row keeps the column wide', async () => {
    const { container } = await drawReal(withPivot(REAL as Fixture, 'ARR'));
    fireEvent.click(screen.getByLabelText(/new arrivals only/));
    await waitFor(() => expect(bodyRows(sectionOf(container, 'explosive')).map(symOf)).toEqual(['VEEA']));
    const ex = sectionOf(container, 'explosive');
    expect(ex.querySelector('.bd-rows')!.classList.contains('bd-rows--pivot-empty')).toBe(false);
    expect(ex.querySelector('.bd-hdr .bd-pivot')!.textContent).toBe('Episodic pivot');
  });

  it('T10 pivotColumnEmpty is true only when every served row has no pivot', () => {
    const r = (pivot: any) => ({ symbol: 'X', pivot } as unknown as BondeRow);
    expect(pivotColumnEmpty([])).toBe(false);
    expect(pivotColumnEmpty(null)).toBe(false);
    expect(pivotColumnEmpty(undefined)).toBe(false);
    expect(pivotColumnEmpty([r(null), { symbol: 'Y' } as unknown as BondeRow])).toBe(true);
    expect(pivotColumnEmpty([r(null), r({})])).toBe(false);
    expect(pivotColumnEmpty([r(null), r({ gap_pct: null })])).toBe(false);
  });

  it('T11 NEGATIVE — a row with no reads leaves line 2 truly empty (the :empty rule hides it)', async () => {
    const G = clone(REAL as Fixture);
    const src = G.board.sections.explosive[0];
    G.board.sections.explosive.push({ ...clone(src), symbol: 'ZZNOREAD', name: 'No Read Corp', is_new: false });
    const { container } = await drawReal(G);
    const l2 = rowOf(container, 'ZZNOREAD').querySelector('.bd-sym-l2')!;
    expect(l2.childNodes.length).toBe(0);
    expect(rowOf(container, 'PTGX').querySelector('.bd-sym-l2')!.childNodes.length).toBeGreaterThan(0);
  });

  it('T12 the head has 7 cells in the fixed order and every row has 4 metric cells', async () => {
    const { container } = await drawReal();
    for (const h of container.querySelectorAll('.bd-row.bd-hdr')) {
      expect([...h.children].map((c) => c.className.split(' ')[0]))
        .toEqual(['bd-sym', 'bd-today', 'bd-since', 'bd-sales', 'bd-chips', 'bd-pivot', 'bd-metrics']);
      expect(h.querySelectorAll('.bd-metrics > .bd-m').length).toBe(4);
    }
    for (const r of bodyRows(container)) expect(r.querySelectorAll('.bd-metrics > .bd-m').length).toBe(4);
  });

  it('T13 NEGATIVE — nothing in the tables prints as a hole', async () => {
    // Scoped to the tables: the SERVED verdict prose above them legitimately
    // says "`accelerating` is a null" (a statistical null), which is not a hole.
    const { container } = await drawReal();
    const boxes = [...container.querySelectorAll('.bd-scroll')];
    expect(boxes.length).toBe(3);
    const text = boxes.map((b) => b.textContent || '').join(' ');
    for (const bad of ['NaN', 'undefined', 'null', '[object Object]']) expect(text).not.toContain(bad);
  });

  it('every section with rows sits inside its own sideways scroll box', async () => {
    const { container } = await drawReal();
    for (const key of ['explosive', 'strong', 'rejected']) {
      const box = container.querySelector(`[data-testid="bd-scroll-${key}"]`)!;
      expect(box.classList.contains('bd-scroll')).toBe(true);
      expect(box.firstElementChild!.classList.contains('bd-rows')).toBe(true);
    }
  });
});
