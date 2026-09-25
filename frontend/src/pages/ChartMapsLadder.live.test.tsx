/* 📋 The entry ladder against REAL served payloads (repair 2026-09-25).
 *
 * Ajay 2026-09-24: "I want them to categorized in a good way so I have enough
 * info for entry of a stock." → 2026-09-25 "Yes, build the ladder".
 *
 * Fixture `components/__fixtures__/card_ladder_live_2026_09_25.json` = the
 * Back in Demand (zones), supply and 🌀 amd boards as served by the live API
 * (read-only GET /chart-maps?tab=…, 24 tiles each) plus the three Back in
 * Demand tiles of `tiles.json` the spec was drawn from. The ⚡ slot is checked
 * against `momentum_burst_live_2026_09_24.json` (the ⚡ branch's served zones
 * board). Every tile goes through the grid's own filters, then the card:
 *   - no "NaN", "undefined" or "[object Object]"; never "bounce";
 *   - rung order ENTRY < PRICE < chart < SETUP < PLAN < TIMING < ▸ more;
 *   - no empty rung box;
 *   - PLAN's buy zone = the served enterable.band, both ends, in pxText;
 *   - ▸ more's count = the ladder's fold count = the folded items in the DOM,
 *     and a folded warn chip turns it amber with ⚠;
 *   - nothing removed: every served badge and every stat value prints
 *     somewhere, bar the spec's named dedupes (the kept copy carries the fact);
 *   - ⚡ ticked → the badge sits in PRICE; unticked → no ⚡ badge at all.
 */
import { describe, expect, it, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from '../components/PatternChart';
import { filterTile, filterForGrid, defaultHidden } from '../lib/chartOverlays';
import { cardLadder } from '../lib/cardLadder';
import { pxText, type CmTile } from '../lib/chartMaps';
import LIVE_RAW from '../components/__fixtures__/card_ladder_live_2026_09_25.json?raw';
import BURST_RAW from '../components/__fixtures__/momentum_burst_live_2026_09_24.json?raw';

type Board = { tab: string; generated_at?: string; tiles: any[]; explosive_study?: any };
const LIVE = JSON.parse(LIVE_RAW) as { boards: Record<string, Board> };
const BURST = JSON.parse(BURST_RAW) as Board;

const grid = (raw: any): CmTile => filterForGrid(filterTile(raw, defaultHidden()), true);
const card = (tile: CmTile, burst: any = null) => render(
  <MemoryRouter><PatternChart tile={tile} burst={burst} /></MemoryRouter>,
);
const RUNGS = ['cm-rung-entry', 'cm-rung-price', '<svg', 'cm-rung-setup', 'cm-rung-plan',
  'cm-rung-timing', 'class="cm-more"'];

describe('entry ladder — live served boards (2026-09-25)', () => {
  afterEach(() => cleanup());

  it('the fixture carries the three boards and the spec tiles', () => {
    for (const k of ['zones', 'supply', 'amd', 'tilesjson']) {
      expect(LIVE.boards[k]?.tiles?.length ?? 0).toBeGreaterThan(0);
    }
    /* Band coverage the PLAN check leans on — a fixture with no band would pass vacuously. */
    const withBand = LIVE.boards.zones.tiles.filter((t) => t?.enterable?.band).length;
    expect(withBand).toBeGreaterThan(10);
  });

  for (const [name, board] of Object.entries(LIVE.boards)) {
    it(`${name}: every card reads as the ladder, nothing junk, nothing lost`, () => {
      let drawn = 0;
      for (const raw of board.tiles) {
        if (!raw || !Array.isArray(raw.bars) || !raw.bars.length) continue;
        const tile = grid(raw);
        const tag = `${name}:${raw.symbol}`;
        const { container, unmount } = card(tile);
        drawn += 1;
        const txt = container.textContent || '';
        expect(txt, tag).not.toMatch(/\bNaN\b|undefined|\[object Object\]/);
        expect(txt, tag).not.toMatch(/bounce/i);

        const html = container.innerHTML;
        const at = RUNGS.map((k) => html.indexOf(k)).filter((i) => i >= 0);
        expect(at, `${tag} rung order`).toEqual([...at].sort((a, b) => a - b));
        expect(html.indexOf('<svg'), `${tag} chart`).toBeGreaterThanOrEqual(0);

        container.querySelectorAll('.cm-rung-items').forEach((el) => {
          expect((el.textContent || '').trim(), `${tag} empty ${el.parentElement?.className}`).not.toBe('');
        });

        const band = raw.enterable?.band;
        const plan = container.querySelector('.cm-rung-plan')?.textContent || '';
        if (band && pxText(band.lo) && pxText(band.hi)) {
          expect(plan, `${tag} buy zone`).toContain(`Buy zone${pxText(band.lo)}–${pxText(band.hi)}`);
        } else {
          expect(plan, `${tag} no band → no buy zone`).not.toContain('Buy zone');
        }
        /* A target-toned line that is not the served TARGET never reads "Target". */
        const tgt = (tile.plan_lines ?? tile.lines ?? []).find((l: any) => l?.tone === 'target');
        if (tgt && tgt.label !== 'TARGET') expect(plan, `${tag} ${tgt.label}`).not.toContain('Target');

        const L = cardLadder(tile);
        const more = container.querySelector('.cm-more');
        const btn = container.querySelector('.cm-badge-more')?.textContent || '';
        if (L.moreCount > 0) {
          expect(more, tag).not.toBeNull();
          const leaves = more!.querySelectorAll(
            '.cm-rung-items > .cm-badge, .cm-rung-items > span[class*="cm-badge"], .cm-kv > .cm-stat');
          expect(btn, tag).toContain(`more · ${L.moreCount}`);
          expect(leaves.length, `${tag} fold leaves`).toBe(L.moreCount);
          expect(btn.includes('⚠'), `${tag} amber`).toBe(L.moreWarn.length > 0);
        } else {
          expect(more, tag).toBeNull();
          expect(btn, tag).toBe('');
        }

        /* The spec's named dedupes (why tail, Bands, On board, Sector flow, Float/day
         * — D1-D5) drop a stat whose fact the kept pill already prints; every
         * other served stat value prints somewhere on the card. */
        for (const s of tile.stats || []) {
          if (L.dropped.includes(s.k)) continue;
          expect(txt, `${tag} stat ${s.k}`).toContain(String(s.v));
        }
        expect(L.dropped.every((d) => ['why-tail', 'Bands', 'On board', 'Sector flow (5d)', 'Float/day'].includes(d)),
          `${tag} dropped ${L.dropped}`).toBe(true);
        for (const b of tile.badges || []) {
          if (!b?.text || (b as any).group) continue;
          expect(txt, `${tag} badge ${b.text}`).toContain(b.text.split('_').join(' '));
        }
        unmount();
      }
      expect(drawn).toBeGreaterThan(0);
    });
  }

  it('⚡ ticked (?burst=1 hands the served read) → the badge sits in PRICE; unticked → no ⚡ badge', () => {
    const bursts = BURST.tiles.filter((t) => t?.burst?.on === true && t.burst.state === 'burst');
    expect(bursts.length).toBeGreaterThan(0);
    for (const raw of bursts) {
      const on = card(grid(raw), raw.burst);
      const price = on.container.querySelector('.cm-rung-price');
      expect(price?.querySelector('.cm-badge-burst'), raw.symbol).not.toBeNull();
      expect(on.container.querySelectorAll('.cm-badge-burst')).toHaveLength(1);
      on.unmount();
      const off = card(grid(raw), null);
      expect(off.container.querySelector('.cm-badge-burst'), raw.symbol).toBeNull();
      off.unmount();
    }
    /* NEGATIVE: a served "no" read with the box ticked draws no ⚡ badge. */
    const no = BURST.tiles.find((t) => t?.burst && t.burst.state !== 'burst' && t.bars?.length);
    expect(no).toBeTruthy();
    const r = card(grid(no), no.burst);
    expect(r.container.querySelector('.cm-badge-burst')).toBeNull();
  });
});
