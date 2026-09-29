import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PAYLOAD from './__fixtures__/dual_momentum_tab_2026_09_29.json';
import LIVE from './__fixtures__/dual_momentum_tab_live_2026_09_29.json';
import { PatternChart } from './PatternChart';
import DualMomentumBoardNote, { DualMomentumSortToggle } from './DualMomentumBoardNote';
import type { CmBoard, CmTile } from '../lib/chartMaps';

/* 🏎️ Dual Momentum tab — a GET /chart-maps?tab=dual_momentum payload through
 * the REAL components (Ajay 2026-09-29: "Can you pull these in to chart maps
 * and add the demand zones logic to these?" + "I want a toggle and also the
 * check boxes we have like AMD and supple and demand zones computing and also
 * key levels"). The fixture is hand-written in the spec §3.4 contract shape
 * (WP-FE); the LIVE step (2026-09-29) added the REAL trimmed payload from
 * the branch API (12 tiles: ranks 1-9, the two READY, one with no stored
 * bands). Only contract keys are read here, so every test runs on BOTH. */

const FIXTURES = [
  ['hand-written §3.4 fixture', PAYLOAD],
  ['REAL branch-API payload', LIVE],
] as const;
const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity'];
const RANK_PREFIX = '\u{1F3CE}\u{FE0F} #';

const renderTile = (t: CmTile) =>
  render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);

describe.each(FIXTURES)('🏎️ Dual Momentum tab payload → real components (%s)', (_name, P) => {
  const board = P as unknown as CmBoard;
  const tiles = board.tiles as CmTile[];
  it('the board is the dual_momentum tab and carries its served, UNMEASURED block', () => {
    expect(board.tab).toBe('dual_momentum');
    expect(board.dual_momentum_board?.measured).toBe(false);
    expect(board.enterable_kind).toBe('demand');
    expect(tiles.length).toBeGreaterThan(0);
    // The fixture must hold at least one tile with NO demand band, so the
    // no-fake-band test below is never vacuous.
    expect(tiles.some((t) => t.dm_zone?.reason !== 'ok')).toBe(true);
  });

  it('the served sorts carry the toggle pair, rank first then 📍', () => {
    const keys = (board.sorts || []).map((s) => s.key);
    expect(keys[0]).toBe('default');
    expect(keys[1]).toBe('nearest_demand');
  });

  it('under the served sort `default` the ranks are non-decreasing in served order (themes off)', () => {
    expect(board.sort).toBe('default');
    const r = tiles.map((t) => t.dual_momentum!.rank);
    for (let i = 1; i < r.length; i++) expect(r[i]).toBeGreaterThanOrEqual(r[i - 1]);
  });

  it('every tile: rank chip on the IDENT line, 12m/6m/3m/1m/RS stats, the 🎯 chip in ENTRY, no junk', () => {
    const lines: string[] = [];
    for (const t of tiles) {
      const { container, unmount } = renderTile(t);
      const ident = container.querySelector('.cm-tile-ident');
      expect(ident, t.symbol).not.toBeNull();
      expect(ident!.textContent || '', t.symbol).toContain(`${RANK_PREFIX}${t.dual_momentum!.rank} `);
      const txt = container.textContent || '';
      for (const k of ['12m', '6m', '3m', '1m', 'RS']) {
        const v = t.stats.find((s) => s.k === k)!.v;
        expect(txt, `${t.symbol} ${k}`).toContain(String(v));
      }
      const entry = container.querySelector('.cm-rung-entry');
      expect(entry, `${t.symbol} ENTRY rung`).not.toBeNull();
      // The 🎯 read's own chip, as lib/enterable.enterableChip words it.
      const en = t.enterable!;
      const chip = en.verdict === 'READY' ? '🎯 READY' : `⛔ ${en.reason_short[0]}`;
      expect(entry!.textContent || '', t.symbol).toContain(chip);
      const html = container.innerHTML;
      for (const bad of JUNK) expect(html.includes(bad), `${t.symbol} ${bad}`).toBe(false);
      expect(/bounce/i.test(txt), t.symbol).toBe(false);
      lines.push(`${t.symbol} #${t.dual_momentum!.rank}: ${container.querySelector('.cm-rung-price')?.textContent ?? ''}`);
      unmount();
    }
    // eslint-disable-next-line no-console
    console.log(['🏎️ Dual Momentum tab — PRICE rows', ...lines].join('\n'));
  });

  it('a tile with a demand band draws it; a tile WITHOUT one shows its served text and draws NO demand band', () => {
    let withBand = 0; let without = 0;
    for (const t of tiles) {
      const { container, unmount } = renderTile(t);
      const drawn = container.querySelectorAll('[data-band-kind="demand"]').length;
      if (t.dm_zone!.reason === 'ok') {
        withBand++;
        expect(drawn, t.symbol).toBeGreaterThan(0);
        // The distance lives on the PRICE rung only (critic 9a): no To band stat.
        expect(t.stats.some((s) => s.k === 'To band'), t.symbol).toBe(false);
      } else {
        without++;
        expect(drawn, t.symbol).toBe(0);
        expect(t.bands.filter((b) => b.kind === 'demand'), t.symbol).toHaveLength(0);
        const price = container.querySelector('.cm-rung-price')!;
        expect(price.textContent || '', t.symbol).toMatch(/→ no demand band/);
      }
      unmount();
    }
    expect(withBand).toBeGreaterThan(0);
    expect(without).toBeGreaterThan(0);
  });

  it('the regime line, header and note render verbatim through DualMomentumBoardNote, with UNMEASURED', () => {
    const db = board.dual_momentum_board!;
    const { getByTestId } = render(
      <MemoryRouter>
        <DualMomentumBoardNote board={db} sorts={board.sorts} sort={board.sort} onSort={() => {}} />
      </MemoryRouter>);
    const el = getByTestId('cm-dm-board');
    expect(el.getAttribute('data-state')).toBe('ready');
    expect(getByTestId('cm-dm-regime').textContent).toBe(db.regime_line);
    expect(getByTestId('cm-dm-header').textContent).toBe(db.header);
    expect(getByTestId('cm-dm-note').textContent).toBe(db.note);
    expect(el.textContent).toContain('UNMEASURED');
    expect(getByTestId('cm-dm-page-link').getAttribute('href')).toBe('/dual-momentum');
    const t = el.textContent || '';
    for (const bad of JUNK) expect(t.includes(bad), bad).toBe(false);
    expect(/bounce/i.test(t)).toBe(false);
  });

  it('the counts invariant holds on the served block (held + swept + broken + unknown == with_band)', () => {
    const c = board.dual_momentum_board!.counts!;
    expect(c.held + c.swept + c.broken + c.floor_unknown).toBe(c.with_band);
  });
});

describe('DualMomentumSortToggle / DualMomentumBoardNote — negatives', () => {
  const SORTS = [{ key: 'default', label: '🏎️ Dual-momentum rank' },
                 { key: 'nearest_demand', label: '📍 Nearest demand first' }];

  it('labels come from the served sorts; pressed = the served sort; a click hands the key up', () => {
    const onSort = vi.fn();
    const { getByTestId } = render(<DualMomentumSortToggle sorts={SORTS} sort="nearest_demand" onSort={onSort} />);
    const rank = getByTestId('cm-dm-sort-default');
    const near = getByTestId('cm-dm-sort-nearest_demand');
    expect(rank.textContent).toBe(SORTS[0].label);
    expect(near.textContent).toBe(SORTS[1].label);
    expect(rank.getAttribute('aria-pressed')).toBe('false');
    expect(near.getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(rank);
    expect(onSort).toHaveBeenCalledWith('default');
  });

  it('NEGATIVE: a served sort that is neither key lights neither button', () => {
    const { getByTestId } = render(<DualMomentumSortToggle sorts={SORTS} sort="rs" onSort={() => {}} />);
    expect(getByTestId('cm-dm-sort-default').getAttribute('aria-pressed')).toBe('false');
    expect(getByTestId('cm-dm-sort-nearest_demand').getAttribute('aria-pressed')).toBe('false');
  });

  it('NEGATIVE: the toggle does not render when either served entry is missing (never a no-op button)', () => {
    for (const sorts of [[SORTS[0]], [SORTS[1]], [], null, undefined,
                         [{ key: 'default', label: '' }, SORTS[1]]]) {
      const { queryByTestId, unmount } = render(
        <DualMomentumSortToggle sorts={sorts as never} sort="default" onSort={() => {}} />);
      expect(queryByTestId('cm-dm-toggle')).toBeNull();
      unmount();
    }
  });

  it('NEGATIVE: an absent or malformed block renders nothing', () => {
    for (const b of [null, undefined, [], 'x', {}, { header: '' }, { header: 42 }]) {
      const { container, unmount } = render(
        <MemoryRouter>
          <DualMomentumBoardNote board={b as never} sorts={SORTS} sort="default" onSort={() => {}} />
        </MemoryRouter>);
      expect(container.innerHTML).toBe('');
      unmount();
    }
  });

  it('warming: the served warming line carries role=status; no regime line is invented', () => {
    const warming = { state: 'warming', counts: null, header: '🏎️ served warming line', note: 'served note',
                      measured: false } as never;
    const { getByTestId, queryByTestId } = render(
      <MemoryRouter>
        <DualMomentumBoardNote board={warming} sorts={SORTS} sort="default" onSort={() => {}} />
      </MemoryRouter>);
    expect(getByTestId('cm-dm-board').getAttribute('data-state')).toBe('warming');
    expect(getByTestId('cm-dm-header').getAttribute('role')).toBe('status');
    expect(queryByTestId('cm-dm-regime')).toBeNull();
  });

  it('NEGATIVE: a failed build is served as error — never shown as warming', () => {
    const failed = { state: 'error', counts: null,
                     header: '🏎️ The Dual Momentum ranking could not be built (engine down). It is retried every 5 minutes — this is not a warming state.',
                     note: 'served note', measured: false } as never;
    const { getByTestId } = render(
      <MemoryRouter>
        <DualMomentumBoardNote board={failed} sorts={SORTS} sort="default" onSort={() => {}} />
      </MemoryRouter>);
    expect(getByTestId('cm-dm-board').getAttribute('data-state')).toBe('error');
    expect(getByTestId('cm-dm-header').getAttribute('role')).toBeNull();
    expect(getByTestId('cm-dm-header').textContent).toContain('could not be built (engine down)');
  });

  it('NEGATIVE: an unknown served state reads as ready, never as warming', () => {
    const odd = { state: 'bogus', counts: null, header: 'served header', measured: false } as never;
    const { getByTestId } = render(
      <MemoryRouter>
        <DualMomentumBoardNote board={odd} sorts={SORTS} sort="default" onSort={() => {}} />
      </MemoryRouter>);
    expect(getByTestId('cm-dm-board').getAttribute('data-state')).toBe('ready');
    expect(getByTestId('cm-dm-header').getAttribute('role')).toBeNull();
  });
});
