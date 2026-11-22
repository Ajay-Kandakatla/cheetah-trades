/* 🗂 The compact 👀 Watch tile (2026-11-22, spec watch_org rev 4 §3.5 / §4 WP-FE-WATCH).
 * Ajay 2026-11-22: "I need gajjalas watch tab little more organized. With less info, I want to know previous day winner
 * auto additions vs intraday may be a time stamp." The compact head prints SYM · 🎯 · the served setup chip · float · 🚫
 * · … · ⋯ ⤢ ↗ ✕; then the ONE served time line (when · 📅 only with a served chip text · 🏆); then the ⋯ drawer (kept
 * mounted, `hidden` while closed). Every word in these fixtures is a stand-in for a served one. NEGATIVES: Tile without
 * `compact` = `compact={false}` byte for byte (the 🚩 / 🧪 grid and GgCardView never pass it); junk org → no chip; one
 * testid per tile (float, 🚫, as-of, 🤖, 🎯, 🔔); no typed section / time / 📅 word in any component file; `usePhone`
 * keeps its export (the 📅 runners strip imports it). */
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import { GgwStretch, Tile, usePhone } from './GajjalaWatchTile';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { _resetGrowthTagsCache } from '../hooks/useGrowthTags';
import { parseGgw, parseRowOrg, type GgwBoard, type GgwRow } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const B = parseGgw(clone(autoFixture)) as GgwBoard;
const OK_AUTO = B.rows.find((r) => r.symbol === 'XXII')!;          // ok, 3 frames, an auto block
const STALE = B.rows.find((r) => r.symbol === 'NVDA')!;            // ok, stale, one rang chip

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const ORG_FULL = {
  group: 'auto',
  when: { bucket: 'premarket', verb: 'added', at_et: '07:12', date: '2026-11-20', text: 'served-when-chip', title: 'served-when-title' },
  setup: { text: 'served-setup-chip', title: 'served-setup-hover' },
  ran: { counts: true, premarket_peak: false, run_pct: 165.2, text: 'served-ran-chip', title: 'served-ran-title' },
  past_winner: { past_winner: [{ text: 'served-win-1' }, { text: 'served-win-2' }], past_winner_more_text: 'served-more' },
};
function rowOf(base: GgwRow, o: Partial<GgwRow> = {}): GgwRow {
  return {
    ...clone(base),
    aplus: { tag: '🎯', text: 'served-aplus-chip', title: 'served-aplus-title', items: [] },
    float: { text: 'served-float', shares: 1, src: null, as_of: null, suspect: false, suspect_text: null, title: null, read_from: null },
    broker_text: 'served-broker',
    org: parseRowOrg(ORG_FULL),
    ...o,
  };
}
function mount(row: GgwRow, extra: Record<string, unknown> = {}) {
  return render(
    <Tile row={row} phone={false} fit={false} removeLabel="served-remove" focused={false} busy={false}
          onRemove={() => {}} onStretch={() => {}} tags={{ room: null, study: null }} siNote {...extra} />,
    { wrapper: MemoryRouter },
  ).container;
}
const q = (c: HTMLElement, id: string) => c.querySelector(`[data-testid="${id}"]`) as HTMLElement | null;
const all = (c: HTMLElement, id: string) => c.querySelectorAll(`[data-testid="${id}"]`);

beforeEach(() => {
  _resetShortInterestCache();
  _resetBounceRoomCache();
  _resetGrowthTagsCache();
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 404, json: async () => ({}) }) as unknown as Response));
  vi.stubGlobal('matchMedia', (m: string) => ({ matches: false, media: m, addEventListener: () => {}, removeEventListener: () => {} }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('🗂 NEGATIVE: no compact → today\'s tile, byte for byte', () => {
  it('Tile without `compact` renders innerHTML equal to compact={false} (org served or not)', () => {
    for (const r of [rowOf(OK_AUTO), rowOf(STALE), clone(OK_AUTO)]) {
      const a = mount(r).innerHTML;
      cleanup();
      const b = mount(r, { compact: false }).innerHTML;
      cleanup();
      expect(b).toBe(a);
      expect(a).not.toContain('ggw-prov');
      expect(a).not.toContain('ggw-drawer');
      expect(a).not.toContain('ggw-setup-chip');
    }
  });
  it('the stretch view without `compact` is unchanged and has no drawer', () => {
    const r = rowOf(OK_AUTO);
    const a = render(<GgwStretch row={r} phone={false} removeLabel={null} onClose={() => {}} onStep={null} />, { wrapper: MemoryRouter });
    const html = document.querySelector('[data-testid="ggw-stretch"]')!.outerHTML;
    a.unmount();
    const b = render(<GgwStretch row={r} phone={false} removeLabel={null} onClose={() => {}} onStep={null} compact={false} />, { wrapper: MemoryRouter });
    expect(document.querySelector('[data-testid="ggw-stretch"]')!.outerHTML).toBe(html);
    expect(document.querySelector('.ggw-drawer')).toBeNull();
    b.unmount();
  });
});

describe('🗂 the compact head + the ONE time line', () => {
  it('head order: SYM · 🎯 · setup · float · 🚫 … ⋯ ⤢ ↗ ✕; the 🤖 chip is behind ⋯', () => {
    const c = mount(rowOf(OK_AUTO), { compact: true });
    const head = c.querySelector('.ggw-tile-head')!;
    const ids = Array.from(head.querySelectorAll('[data-testid]')).map((e) => e.getAttribute('data-testid'));
    const at = (id: string) => ids.indexOf(id);
    expect(at('ggw-aplus')).toBeGreaterThanOrEqual(0);
    expect(at('ggw-setup-chip-XXII')).toBeGreaterThan(at('ggw-aplus'));
    expect(at('ggw-float-XXII')).toBeGreaterThan(at('ggw-setup-chip-XXII'));
    expect(at('ggw-broker-XXII')).toBeGreaterThan(at('ggw-float-XXII'));
    expect(at('ggw-drawer-btn-XXII')).toBeGreaterThan(at('ggw-broker-XXII'));
    expect(at('ggw-stretch-btn-XXII')).toBeGreaterThan(at('ggw-drawer-btn-XXII'));
    expect(head.querySelector('[data-testid="ggw-auto"]')).toBeNull();
    expect(q(c, 'ggw-setup-chip-XXII')!.textContent).toBe('served-setup-chip');
    expect(q(c, 'ggw-setup-chip-XXII')!.getAttribute('title')).toBe('served-setup-hover');
    expect(c.querySelector('.ggw-tile')!.classList.contains('ggw-tile--compact')).toBe(true);
    /* no tags row above the head in compact mode — it lives in the drawer */
    expect(c.querySelector('.ggw-tile > .ggw-tags')).toBeNull();
  });
  it('the time line: when · 📅 · 🏆, served words verbatim, served titles on hover', () => {
    const c = mount(rowOf(OK_AUTO), { compact: true });
    const prov = q(c, 'ggw-prov-XXII')!;
    expect(Array.from(prov.children).map((e) => e.getAttribute('data-testid'))).toEqual(['ggw-when-XXII', 'ggw-ran-XXII', 'ggw-past-XXII']);
    expect(q(c, 'ggw-when-XXII')!.textContent).toBe('served-when-chip');
    expect(q(c, 'ggw-when-XXII')!.getAttribute('title')).toBe('served-when-title');
    expect(q(c, 'ggw-when-XXII')!.getAttribute('data-bucket')).toBe('premarket');
    expect(q(c, 'ggw-ran-XXII')!.textContent).toBe('served-ran-chip');
    expect(q(c, 'ggw-ran-XXII')!.getAttribute('title')).toBe('served-ran-title');
    expect(q(c, 'ggw-past-XXII')!.textContent).toBe('served-win-1');
    expect(q(c, 'ggw-past-XXII')!.getAttribute('title')).toBe('served-win-1 · served-win-2 · served-more');
    /* the line sits between the head and the drawer */
    const kids = Array.from(c.querySelector('.ggw-tile')!.children).map((e) => e.className.split(' ')[0]);
    expect(kids.indexOf('ggw-prov')).toBe(kids.indexOf('ggw-tile-head') + 1);
    expect(kids.indexOf('ggw-drawer')).toBe(kids.indexOf('ggw-prov') + 1);
  });
  it('📅 premarket-peak name: NO chip; the drawer prints the served title', () => {
    const org = parseRowOrg({ ...ORG_FULL, ran: { counts: false, premarket_peak: true, text: null, title: 'served-pm-peak-title' } });
    const c = mount(rowOf(OK_AUTO, { org }), { compact: true });
    expect(q(c, 'ggw-ran-XXII')).toBeNull();
    expect(q(c, 'ggw-ran-title')!.textContent).toBe('served-pm-peak-title');
  });
  it('NEGATIVE: junk org (blank group, NaN, ran with no text, empty past) → no chip at all', () => {
    for (const raw of [
      { group: '', when: ORG_FULL.when }, { group: Number.NaN }, null,
      { group: 'auto', when: { text: '' }, setup: { text: Number.NaN }, ran: { text: '', run_pct: Number.NaN }, past_winner: { past_winner: [] } },
    ]) {
      const c = mount(rowOf(OK_AUTO, { org: parseRowOrg(raw) }), { compact: true });
      for (const id of ['ggw-prov-XXII', 'ggw-when-XXII', 'ggw-ran-XXII', 'ggw-past-XXII', 'ggw-setup-chip-XXII']) expect(q(c, id)).toBeNull();
      expect(c.textContent).not.toContain('NaN');
      cleanup();
    }
  });
  it('NEGATIVE: no quote chip — the compact head prints no price of its own', () => {
    const c = mount(rowOf(OK_AUTO), { compact: true });
    expect(c.querySelector('[data-testid^="ggw-quote"]')).toBeNull();
    expect(c.querySelector('.ggw-tile-head')!.textContent).not.toMatch(/\$\d/);
  });
});

describe('🗂 ⋯ the drawer', () => {
  it('closed by default; ⋯ toggles `hidden` and aria-expanded; the content stays mounted', () => {
    const c = mount(rowOf(OK_AUTO), { compact: true });
    const btn = q(c, 'ggw-drawer-btn-XXII')!;
    const dr = q(c, 'ggw-drawer-XXII')!;
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    expect(dr.hidden).toBe(true);
    expect(dr.querySelector('[data-testid="ggw-auto"]')).not.toBeNull();
    fireEvent.click(btn);
    expect(btn.getAttribute('aria-expanded')).toBe('true');
    expect(dr.hidden).toBe(false);
    expect(btn.getAttribute('aria-controls')).toBe(dr.id);
    fireEvent.click(btn);
    expect(dr.hidden).toBe(true);
  });
  it('the drawer: the 🤖 chip + its served lines, the A+ / when / 📅 titles, each 🏆 win, the non-stale as-of', () => {
    const c = mount(rowOf(OK_AUTO), { compact: true, drawerOpen: true });
    const dr = q(c, 'ggw-drawer-XXII')!;
    expect(dr.hidden).toBe(false);
    expect(dr.querySelector('[data-testid="ggw-auto"]')!.textContent).toBe(OK_AUTO.auto!.text);
    const lines = Array.from(dr.querySelectorAll('[data-testid="ggw-auto-line"]')).map((e) => e.textContent);
    expect(lines).toEqual([OK_AUTO.auto!.added_text, OK_AUTO.auto!.volume_text, OK_AUTO.auto!.leaving_text].filter(Boolean));
    expect(dr.querySelector('[data-testid="ggw-aplus-title"]')!.textContent).toBe('served-aplus-title');
    expect(dr.querySelector('[data-testid="ggw-when-title"]')!.textContent).toBe('served-when-title');
    expect(dr.querySelector('[data-testid="ggw-ran-title"]')!.textContent).toBe('served-ran-title');
    expect(Array.from(dr.querySelectorAll('[data-testid="ggw-past-line"]')).map((e) => e.textContent))
      .toEqual(['served-win-1', 'served-win-2', 'served-more']);
    expect(dr.querySelector('[data-testid="ggw-asof"]')!.textContent).toBe(OK_AUTO.as_of_et);
  });
  it('⤢ opens with the drawer open (GgwStretch compact)', () => {
    const r = render(<GgwStretch row={rowOf(OK_AUTO)} phone={false} removeLabel={null} onClose={() => {}} onStep={null} compact />, { wrapper: MemoryRouter });
    const dr = document.querySelector('[data-testid="ggw-stretch"] [data-testid="ggw-drawer-XXII"]') as HTMLElement;
    expect(dr).not.toBeNull();
    expect(dr.hidden).toBe(false);
    expect(document.querySelector('[data-testid="ggw-stretch"] [data-testid="ggw-drawer-btn-XXII"]')!.getAttribute('aria-expanded')).toBe('true');
    r.unmount();
  });
});

describe('🗂 NEGATIVE: no duplicate testid per tile', () => {
  it('float, 🚫, as-of, 🤖, 🎯 once each; 🔔 once per served rang (head only) — fresh row', () => {
    const c = mount(rowOf(OK_AUTO), { compact: true });
    for (const id of ['ggw-float-XXII', 'ggw-broker-XXII', 'ggw-asof', 'ggw-auto', 'ggw-aplus']) expect(all(c, id).length).toBe(1);
    expect(c.querySelector('.ggw-tile-head [data-testid="ggw-asof"]')).toBeNull();          // non-stale → drawer only
  });
  it('a STALE row prints its as-of in the head (⚠️) and NOT in the drawer; rang once each', () => {
    const r = rowOf(STALE, { auto: OK_AUTO.auto });
    const c = mount(r, { compact: true });
    expect(all(c, 'ggw-asof').length).toBe(1);
    expect(c.querySelector('.ggw-tile-head [data-testid="ggw-asof"]')!.textContent).toContain('⚠️');
    expect(all(c, 'ggw-rang').length).toBe(r.rang.length);
    expect(c.querySelector('.ggw-drawer [data-testid="ggw-rang"]')).toBeNull();
    for (const id of ['ggw-float-NVDA', 'ggw-broker-NVDA', 'ggw-auto', 'ggw-aplus']) expect(all(c, id).length).toBe(1);
  });
});

describe('🗂 source guards', () => {
  const FILES = ['GajjalaWatchCompact.tsx', 'GajjalaWatchTile.tsx', 'GajjalaWatchLayout.tsx', 'GajjalaWatchBoard.tsx', 'GajjalaWatchTags.tsx'];
  it('NEGATIVE: no section / time / 📅 word and no section-key literal typed in a component file', async () => {
    for (const f of FILES) {
      const src = await readSource(`src/components/${f}`);
      for (const bad of ['Your names', 'Added today', 'premarket ', 're-added']) expect(src, `${f}: ${bad}`).not.toContain(bad);
      expect(src, `${f}: Ran/ran`).not.toMatch(/\b[Rr]an /);
      expect(src, `${f}: a section key literal`).not.toMatch(/['"`](yours|ran)['"`]/);
      expect(src, `${f}: a section-key array`).not.toMatch(/\[\s*['"`](yours|aplus|auto)['"`]\s*,/);
    }
  });
  it('NEGATIVE: the b-word never appears in the new component file', async () => {
    expect(await readSource('src/components/GajjalaWatchCompact.tsx')).not.toMatch(/bounc/i);
  });
  it('usePhone keeps its export and its no-argument signature (the 📅 runners strip imports it)', async () => {
    expect(typeof usePhone).toBe('function');
    expect(usePhone.length).toBe(0);
    expect(await readSource('src/components/GajjalaWatchTile.tsx')).toMatch(/export function usePhone\(\): boolean \{/);
  });
  it('the float testid literal stays exactly once in GajjalaWatchTags.tsx (one float chip, the compact head reuses it)', async () => {
    const src = await readSource('src/components/GajjalaWatchTags.tsx');
    expect(src.split('ggw-float-${')).toHaveLength(2);
    expect(src).toMatch(/export function GgwFloatChip\b/);
    expect(src).toMatch(/export function GgwBrokerChip\b/);
  });
});

void act;
