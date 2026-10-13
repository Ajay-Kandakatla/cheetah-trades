import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { GrowthArrivalsStrip } from './GrowthArrivalsStrip';
import {
  _resetGrowthTagsCache, fetchGrowthPayload, fetchGrowthTags, useGrowthArrivals, useGrowthTags,
} from '../hooks/useGrowthTags';

/* ✨ Growth arrivals strip (2026-10-12) — Ajay: "In the eplosive growth there
 * are 7 new one can you gave me special emphasis wiht a tag or something in
 * the chart map pages top". The "7" was the push's digest spill; the strip
 * shows the SERVED arrivals_n. Pinned here:
 *   - 2026-10-12 #7: OPEN on first paint for a viewer who never folded it,
 *     folded after his fold for the same batch, re-opened by a newer batch
 *     (StudyNote freshKey = newest served first_seen);
 *   - 2026-10-12 #5: every chip href and `all 🚀 →` carry show=all;
 *   - 2026-10-12 #8: per-tab links from the served also_on[];
 *   - chips in SERVED order with SERVED glyphs, linking to ?tab=growth&focus=;
 *   - the note verbatim; nothing at all when nothing arrived or on an outage;
 *   - one /growth/tags fetch shared with every GrowthChip. */

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const STAMP = '2026-10-12T02:29:05.396512+00:00';
const LIQUID = ['PGEN', 'BBT', 'BW', 'FBK', 'KLIC', 'AAON'];
/* The live 11 (read-only probe 2026-10-12), in a deliberately non-alphabetical
 * served order so a re-sort would show. */
const ORDER = ['PGEN', 'MGNX', 'BBT', 'RYM', 'BW', 'BMRC', 'FBK', 'PED', 'KLIC', 'CHMG', 'AAON'];
const ARRIVALS = ORDER.map((symbol) => {
  const refused = symbol === 'MGNX' || symbol === 'BMRC';
  return {
    symbol, first_seen: STAMP, liquid: LIQUID.includes(symbol), refused,
    warnings: refused ? [`⛔ known cap under the engine floor (${symbol})`] : [],
  };
});
const NOTE = 'SERVED NOTE — a list event, not a signal. NOT BACKTESTED.';
const PAYLOAD = {
  tags: { PGEN: { sales: 120, eps: 90, refused: false } },
  arrivals: ARRIVALS, arrivals_n: 11, new_days: 30, arrivals_note: NOTE,
};

function stub(body: unknown = PAYLOAD, ok = true) {
  const f = vi.fn(async () => ({ ok, json: async () => body }) as unknown as Response);
  vi.stubGlobal('fetch', f);
  return f;
}

function Where() {
  const loc = useLocation();
  return <output data-testid="where">{loc.search}</output>;
}
const draw = (entry = '/chart-maps?tab=zones&universe=full') => render(
  <MemoryRouter initialEntries={[entry]}><GrowthArrivalsStrip /><Where /></MemoryRouter>,
);

const memStore = (init: Record<string, string> = {}) => {
  const m = new Map(Object.entries(init));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(), key: () => null, length: 0, _m: m,
  };
};

async function openStrip() {
  const det = (await screen.findByTestId('cm-growth-arrivals')) as HTMLDetailsElement;
  act(() => {
    det.open = true;
    fireEvent(det, new Event('toggle'));
  });
  return det;
}

describe('GrowthArrivalsStrip', () => {
  beforeEach(() => {
    _resetGrowthTagsCache();
    vi.stubGlobal('localStorage', memStore());
  });
  afterEach(() => {
    _resetGrowthTagsCache();
    vi.unstubAllGlobals();
  });

  it('#7 first paint with no memory is OPEN: the served headline and the chips', async () => {
    stub();
    draw();
    const det = (await screen.findByTestId('cm-growth-arrivals')) as HTMLDetailsElement;
    expect(det.tagName).toBe('DETAILS');
    await waitFor(() => expect(det.open).toBe(true));
    expect(screen.getByText('✨ 11 new on 🚀 Explosive Growth (last 30 days)')).toBeVisible();
    expect(screen.getByTestId('cm-growth-arrivals-chips')).toBeVisible();
  });

  it('#7 folded for the SAME batch → stays folded on the next mount', async () => {
    const store = memStore();
    vi.stubGlobal('localStorage', store);
    stub();
    const { unmount } = draw();
    const det = (await screen.findByTestId('cm-growth-arrivals')) as HTMLDetailsElement;
    await waitFor(() => expect(det.open).toBe(true));
    act(() => { det.open = false; fireEvent(det, new Event('toggle')); });
    expect(store._m.get('cm.study.open.growth-arrivals')).toBe('0');
    expect(store._m.get('cm.study.fresh.growth-arrivals')).toBe(STAMP);
    unmount();
    _resetGrowthTagsCache();
    stub();
    draw();
    const again = (await screen.findByTestId('cm-growth-arrivals')) as HTMLDetailsElement;
    await act(async () => { await fetchGrowthPayload(); });
    expect(again.open).toBe(false);
    expect(screen.getByText('✨ 11 new on 🚀 Explosive Growth (last 30 days)')).toBeVisible();
  });

  it('#7 folded on an OLDER batch → a newer served first_seen re-opens it', async () => {
    vi.stubGlobal('localStorage', memStore({
      'cm.study.open.growth-arrivals': '0',
      'cm.study.fresh.growth-arrivals': '2026-10-05T02:29:05.000000+00:00',
    }));
    stub();
    draw();
    const det = (await screen.findByTestId('cm-growth-arrivals')) as HTMLDetailsElement;
    await waitFor(() => expect(det.open).toBe(true));
  });

  it('#5 every chip href and all 🚀 → carry show=all', async () => {
    stub();
    draw('/chart-maps?tab=zones&universe=full');
    await openStrip();
    const hrefs = [
      ...screen.getAllByTestId(/^cm-growth-arrival-[A-Z]+$/),
      screen.getByTestId('cm-growth-arrivals-all'),
    ].map((a) => a.getAttribute('href')!);
    expect(hrefs).toHaveLength(12);
    for (const h of hrefs) {
      const q = new URLSearchParams(h.slice(1));
      expect(q.getAll('show')).toEqual(['all']);
      expect(q.get('tab')).toBe('growth');
    }
  });

  it('NEGATIVE #5: a page already on show=all never gets a duplicated param', async () => {
    stub();
    draw('/chart-maps?tab=zones&show=all');
    await openStrip();
    const q = new URLSearchParams(screen.getByTestId('cm-growth-arrival-PGEN').getAttribute('href')!.slice(1));
    expect(q.getAll('show')).toEqual(['all']);
  });

  it('opened: one chip per served arrival, in SERVED order, with served glyphs', async () => {
    stub();
    draw();
    await openStrip();
    const chips = screen.getAllByTestId(/^cm-growth-arrival-[A-Z]+$/);
    expect(chips).toHaveLength(11);
    expect(chips.map((c) => c.getAttribute('data-testid')!.replace('cm-growth-arrival-', ''))).toEqual(ORDER);
    for (const s of ['MGNX', 'BMRC']) {
      const c = screen.getByTestId(`cm-growth-arrival-${s}`);
      expect(c.className).toContain('cm-badge-bad');
      expect(c.textContent).toBe(`${s} ⛔`);
    }
    for (const s of ['RYM', 'PED', 'CHMG']) {
      const c = screen.getByTestId(`cm-growth-arrival-${s}`);
      expect(c.className).toContain('cm-badge-new');
      expect(c.textContent).toBe(`${s} ⚠️`);
    }
    const p = screen.getByTestId('cm-growth-arrival-PGEN');
    expect(p.textContent).toBe('PGEN');
    expect(p.className).toContain('cm-badge-new');
    expect(p.className).not.toContain('cm-badge-bad');
    expect(p.getAttribute('title')).toBe('Arrived on 🚀 Explosive Growth 2026-10-12 · no warnings');
  });

  it('chip hrefs are ?tab=growth&focus=SYM and keep the rest of the URL', async () => {
    stub();
    draw('/chart-maps?tab=winners&pattern=cup&universe=full');
    await openStrip();
    const href = screen.getByTestId('cm-growth-arrival-PGEN').getAttribute('href')!;
    const q = new URLSearchParams(href.slice(1));
    expect(q.get('tab')).toBe('growth');
    expect(q.get('focus')).toBe('PGEN');
    expect(q.get('universe')).toBe('full');
    expect(q.has('pattern')).toBe(false);
    const all = new URLSearchParams(screen.getByTestId('cm-growth-arrivals-all').getAttribute('href')!.slice(1));
    expect(all.get('tab')).toBe('growth');
    expect(all.has('focus')).toBe(false);
  });

  it('a plain click routes in place; a ⌘-click is left to the browser', async () => {
    stub();
    draw();
    await openStrip();
    const chip = screen.getByTestId('cm-growth-arrival-MGNX');
    /* Read what the strip did, then stop jsdom's own (unimplemented) navigation. */
    const prevented: boolean[] = [];
    const trap = (e: Event) => { prevented.push(e.defaultPrevented); e.preventDefault(); };
    window.addEventListener('click', trap);
    const meta = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, metaKey: true });
    chip.dispatchEvent(meta);
    window.removeEventListener('click', trap);
    expect(prevented).toEqual([false]);
    expect(screen.getByTestId('where').textContent).toBe('?tab=zones&universe=full');

    const plain = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 });
    act(() => { chip.dispatchEvent(plain); });
    expect(plain.defaultPrevented).toBe(true);
    const q = new URLSearchParams(screen.getByTestId('where').textContent!.slice(1));
    expect(q.get('tab')).toBe('growth');
    expect(q.get('focus')).toBe('MGNX');
    expect(q.get('universe')).toBe('full');
  });

  it('the note is the served string, verbatim, under the fold', async () => {
    stub();
    draw();
    await openStrip();
    expect(screen.getByTestId('cm-growth-arrivals-note').textContent).toBe(NOTE);
  });

  it('NEGATIVE: no served note → no note paragraph (never a typed one)', async () => {
    stub({ ...PAYLOAD, arrivals_note: null });
    draw();
    await openStrip();
    expect(screen.queryByTestId('cm-growth-arrivals-note')).toBeNull();
  });

  it('remembers his open choice under cm.study.open.growth-arrivals', async () => {
    const store = memStore();
    vi.stubGlobal('localStorage', store);
    stub();
    draw();
    await openStrip();
    expect(store._m.get('cm.study.open.growth-arrivals')).toBe('1');
  });

  it('a remembered open re-opens on mount', async () => {
    vi.stubGlobal('localStorage', memStore({ 'cm.study.open.growth-arrivals': '1' }));
    stub();
    draw();
    const det = (await screen.findByTestId('cm-growth-arrivals')) as HTMLDetailsElement;
    await waitFor(() => expect(det.open).toBe(true));
  });

  it('NEGATIVE: a throwing localStorage still renders the strip — OPEN (no memory)', async () => {
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => { throw new Error('blocked'); },
    });
    stub();
    draw();
    const det = (await screen.findByTestId('cm-growth-arrivals')) as HTMLDetailsElement;
    await waitFor(() => expect(det.open).toBe(true));
    await openStrip();
    expect(screen.getAllByTestId(/^cm-growth-arrival-[A-Z]+$/)).toHaveLength(11);
  });

  it.each([
    ['arrivals: []', { ...PAYLOAD, arrivals: [], arrivals_n: 0 }, true],
    ['arrivals key absent', { tags: PAYLOAD.tags }, true],
    ['fetch 500', {}, false],
  ])('NEGATIVE: %s → nothing at all', async (_n, body, ok) => {
    const f = stub(body, ok as boolean);
    const { container } = draw();
    await waitFor(() => expect(f).toHaveBeenCalled());
    await act(async () => { await fetchGrowthPayload(); });
    expect(screen.queryByTestId('cm-growth-arrivals')).toBeNull();
    expect(container.textContent ?? '').not.toMatch(/new on/);
  });

  it('NEGATIVE: a network error → nothing, no throw', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('down'); }));
    draw();
    await act(async () => { await fetchGrowthPayload(); });
    expect(screen.queryByTestId('cm-growth-arrivals')).toBeNull();
  });

  it('#8 per-tab links under a chip: served order by tab, glyph text, served as-of on hover', async () => {
    const withAlso = ARRIVALS.map((a) => (a.symbol === 'PGEN' ? {
      ...a,
      also_on: [
        { tab: 'bonde', built_at: '2026-10-12T13:00:00+00:00', source_as_of: null, ttl_name: null, limit: null, stale: null },
        { tab: 'ath', built_at: '2026-10-12T14:05:33+00:00', source_as_of: '2026-10-12T09:41:07-04:00',
          ttl_name: 'chart_maps.ath_tab.MEMO_TTL_SEC', limit: 80, stale: true },
        { tab: 'zones', built_at: '2026-10-12T14:00:00+00:00', source_as_of: null, ttl_name: null, limit: 80, stale: null },
        { tab: 'growth', built_at: '2026-10-12T14:00:00+00:00', limit: 80 },
      ],
    } : a));
    stub({ ...PAYLOAD, arrivals: withAlso });
    draw('/chart-maps?tab=amd&universe=full');
    await openStrip();
    const box = screen.getByTestId('cm-growth-also-PGEN');
    expect(box.className).toBe('cm-arrival-also');
    const links = Array.from(box.querySelectorAll('a'));
    expect(links.map((l) => new URLSearchParams(l.getAttribute('href')!.slice(1)).get('tab')))
      .toEqual(['zones', 'ath', 'bonde']);
    expect(links.map((l) => l.textContent)).toEqual(['Back in Demand', '🏔️', '📈']);
    const ath = screen.getByTestId('cm-growth-also-PGEN-ath');
    expect(ath.getAttribute('title')).toBe(
      "🏔️ ATH · in the served top 80 as of 2026-10-12 09:41 · stale: older than this tab's cache window (chart_maps.ath_tab.MEMO_TTL_SEC)");
    expect(ath.getAttribute('data-stale')).toBe('true');
    expect(screen.getByTestId('cm-growth-also-PGEN-bonde').getAttribute('title'))
      .toBe('📈 Bonde · in the served list as of 2026-10-12 13:00');
    for (const l of links) {
      const q = new URLSearchParams(l.getAttribute('href')!.slice(1));
      expect(q.has('focus')).toBe(false);
      expect(q.get('universe')).toBe('full');
    }
    /* the chip itself is unchanged */
    const chip = screen.getByTestId('cm-growth-arrival-PGEN');
    expect(chip.textContent).toBe('PGEN');
    expect(new URLSearchParams(chip.getAttribute('href')!.slice(1)).get('focus')).toBe('PGEN');
    /* a plain click on a per-tab link routes in place */
    act(() => { fireEvent.click(ath, { button: 0 }); });
    expect(new URLSearchParams(screen.getByTestId('where').textContent!.slice(1)).get('tab')).toBe('ath');
  });

  it.each([
    ['absent', undefined],
    ['empty', []],
    ['not an array', { zones: true }],
    ['junk entries', [null, 3, 'zones', { tab: 'nope' }, { tab: 'growth' }, { tab: 'supply' }]],
  ])('NEGATIVE #8: also_on %s → no links, chip unchanged', async (_n, also_on) => {
    const arr = ARRIVALS.map((a) => (a.symbol === 'PGEN' ? { ...a, also_on } : a));
    stub({ ...PAYLOAD, arrivals: arr });
    draw();
    await openStrip();
    expect(screen.queryByTestId('cm-growth-also-PGEN')).toBeNull();
    expect(document.querySelectorAll('.cm-arrival-also')).toHaveLength(0);
    const chip = screen.getByTestId('cm-growth-arrival-PGEN');
    expect(chip.textContent).toBe('PGEN');
    expect(screen.getAllByTestId(/^cm-growth-arrival-[A-Z]+$/)).toHaveLength(11);
  });

  it('NEGATIVE: no rendered text says "bounce"', async () => {
    stub();
    const { container } = draw();
    await openStrip();
    expect((container.textContent ?? '').toLowerCase()).not.toContain('bounce');
  });

  it('NEGATIVE source guards: no 🆕, no defaultOpen, no pp/CI literal, no admin email', async () => {
    for (const rel of ['src/components/GrowthArrivalsStrip.tsx', 'src/lib/growthArrivals.ts']) {
      const src = await readSource(rel);
      expect(src).not.toContain('🆕');
      expect(src).not.toMatch(/[+−-]?\d+(\.\d+)?\s*pp\b/);
      expect(src).not.toMatch(/\bCI\b/);
      expect(src).not.toContain('@gmail');
      expect(src).not.toContain('ajaykandakatla');
    }
    expect(await readSource('src/components/GrowthArrivalsStrip.tsx')).not.toContain('defaultOpen');
  });
});

describe('useGrowthTags payload cache (2026-10-12)', () => {
  beforeEach(() => _resetGrowthTagsCache());
  afterEach(() => { _resetGrowthTagsCache(); vi.unstubAllGlobals(); });

  function Both() {
    const tags = useGrowthTags();
    const a = useGrowthArrivals();
    return <output data-testid="both">{`${Object.keys(tags).join(',')}|${a.n}|${a.arrivals.length}|${a.newDays}`}</output>;
  }

  it('one fetch serves both hooks (chips and the strip)', async () => {
    const f = stub();
    render(<><Both /><Both /></>);
    await waitFor(() => expect(screen.getAllByTestId('both')[0].textContent).toBe('PGEN|11|11|30'));
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('fetchGrowthTags still resolves the plain tags map', async () => {
    stub();
    expect(await fetchGrowthTags()).toEqual(PAYLOAD.tags);
  });

  it('NEGATIVE: a payload with no arrivals key → empty arrivals, tags intact', async () => {
    stub({ tags: PAYLOAD.tags, arrivals_n: 5 });
    const p = await fetchGrowthPayload();
    expect(p.tags).toEqual(PAYLOAD.tags);
    expect(p.arrivals).toEqual([]);
    expect(p.arrivals_n).toBe(0);
  });

  it('NEGATIVE: 500 and network error → empty, never throws', async () => {
    stub({}, false);
    expect((await fetchGrowthPayload()).arrivals).toEqual([]);
    _resetGrowthTagsCache();
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('down'); }));
    const p = await fetchGrowthPayload();
    expect(p.arrivals).toEqual([]);
    expect(p.tags).toEqual({});
  });

  it('NEGATIVE: malformed arrival entries are dropped, never rendered', async () => {
    stub({ ...PAYLOAD, arrivals: [null, { symbol: '' }, { nope: 1 }, ARRIVALS[0]], arrivals_n: 1 });
    const p = await fetchGrowthPayload();
    expect(p.arrivals.map((a) => a.symbol)).toEqual(['PGEN']);
  });

  it('_resetGrowthTagsCache clears the payload (tags AND arrivals) — next call refetches', async () => {
    const f = stub();
    await fetchGrowthPayload();
    await fetchGrowthPayload();
    expect(f).toHaveBeenCalledTimes(1);
    _resetGrowthTagsCache();
    stub({ tags: {} });
    const p = await fetchGrowthPayload();
    expect(p.arrivals).toEqual([]);
    expect(p.tags).toEqual({});
  });
});
