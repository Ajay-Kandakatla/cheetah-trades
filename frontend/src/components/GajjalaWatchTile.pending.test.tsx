/* ⏳ 2026-11-19 (watchnew2 spec §3.5 / §4 WP-FE-tile) — Ajay: "When I add a new ticket they are gettinf added in to que
 * but not active" / "charts are not loading I amhaving to click on the chips again".
 * A pending row (no frames, served words) prints its words ONCE, in the tile BODY (GgwPendingPanel), and the head
 * skips them; when the frames arrive the same Tile draws its 3 charts and the panel goes.
 * NEGATIVES: an ok row (stale or not) keeps its head words and draws no panel; a card row ('loading', no frames) draws
 * no panel; a pending row with no words draws no panel.
 * Fit / hidden → shown proof: a fitted tile mounted hidden (0×0) still draws at the fallback ggwChartHeight, refits on
 * the ResizeObserver callback, and is shown with its 3 charts once offPage clears; with no ResizeObserver it still
 * draws at the fallback height. */
import { act, cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { Tile } from './GajjalaWatchTile';
import { GgwPendingPanel, ggwPendingPanelShown } from './GajjalaWatchPending';
import { PATTERN_CHART_VIEW_W } from './PatternChart';
import { ggwChartHeight, ggwFitViewBoxH, ggwFitViewW, parseGgw, type GgwBoard, type GgwRow } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const okRow = (): GgwRow => (parseGgw(clone(fixture)) as GgwBoard).rows[0];
const S = (fixture as any).rows[0].symbol as string;
/* The served words are stubs here: the panel prints whatever `row.text` holds (the FE composes none). */
const PENDING_WORDS = 'stub served pending words';
const LATE_WORDS = 'stub served late words';
const pendingRow = (text: string | null = PENDING_WORDS): GgwRow =>
  ({ ...okRow(), state: 'pending', text, frames: [], rang: [], from_session: null, as_of_et: null, stale: false });

const tile = (row: GgwRow, extra: Partial<{ fit: boolean; offPage: boolean }> = {}) => (
  <MemoryRouter>
    <Tile row={row} phone={false} fit={extra.fit ?? false} removeLabel="Remove" focused={false} busy={false}
          onRemove={() => {}} offPage={extra.offPage} />
  </MemoryRouter>
);
const svgs = (c: HTMLElement) => c.querySelectorAll('figure .ggw-chartbox svg.cm-svg');

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('GgwPendingPanel — the pending words in the tile BODY, printed once', () => {
  it('pending row, no frames → the panel holds row.text, aria-busy; the head has NO ggw-row-text; no svg', () => {
    const { container } = render(tile(pendingRow()));
    const p = screen.getByTestId(`ggw-pending-${S}`);
    expect(p.textContent).toBe(PENDING_WORDS);
    expect(p.getAttribute('aria-busy')).toBe('true');
    expect(p.className).toBe('ggw-dark ggw-charts ggw-pending');
    expect(p.querySelector('p.ggw-line.ggw-pending-text')?.textContent).toBe(PENDING_WORDS);
    expect(screen.queryByTestId('ggw-row-text')).toBeNull();
    expect(container.textContent!.split(PENDING_WORDS).length - 1).toBe(1);
    expect(container.querySelectorAll('svg.cm-svg').length).toBe(0);
    expect(p.parentElement).toBe(screen.getByTestId(`ggw-tile-${S}`));
  });
  it('the same Tile re-rendered with an ok row (frames arrive after mount) → 3 svgs and no panel', () => {
    const { container, rerender } = render(tile(pendingRow()));
    expect(screen.getByTestId(`ggw-pending-${S}`)).toBeTruthy();
    rerender(tile(okRow()));
    expect(screen.queryByTestId(`ggw-pending-${S}`)).toBeNull();
    expect(svgs(container).length).toBe(3);
  });
  it('a row whose text the board swapped to the served late words → the panel prints those', () => {
    render(tile(pendingRow(LATE_WORDS)));
    expect(screen.getByTestId(`ggw-pending-${S}`).textContent).toBe(LATE_WORDS);
    expect(screen.queryByText(PENDING_WORDS)).toBeNull();
  });
  it('NEGATIVE: a stale ok row keeps its head ggw-row-text (DOM unchanged) and draws no panel', () => {
    const r = { ...okRow(), text: 'stub stale words', stale: true };
    const { container } = render(tile(r));
    const head = screen.getByTestId('ggw-row-text');
    expect(head.textContent).toBe('stub stale words');
    expect(head.className).toBe('ggw-line ggw-row-text ggw-warn');
    expect(container.querySelector('.ggw-pending')).toBeNull();
    expect(svgs(container).length).toBe(3);
  });
  it('NEGATIVE: a card row (state loading, no frames) draws no panel; its words stay in the head', () => {
    const r: GgwRow = { ...pendingRow('stub card words'), state: 'loading' };
    const { container } = render(tile(r));
    expect(container.querySelector('.ggw-pending')).toBeNull();
    expect(screen.getByTestId('ggw-row-text').textContent).toBe('stub card words');
    expect(ggwPendingPanelShown(r)).toBe(false);
  });
  it('NEGATIVE: an ok row draws no panel; a pending row with no words or with frames draws none', () => {
    expect(render(tile(okRow())).container.querySelector('.ggw-pending')).toBeNull();
    cleanup();
    expect(render(<GgwPendingPanel row={pendingRow(null)} />).container.innerHTML).toBe('');
    cleanup();
    const withFrames: GgwRow = { ...okRow(), state: 'pending', text: PENDING_WORDS };
    expect(ggwPendingPanelShown(withFrames)).toBe(false);
    const { container } = render(tile(withFrames));
    expect(container.querySelector('.ggw-pending')).toBeNull();
    expect(screen.getByTestId('ggw-row-text').textContent).toBe(PENDING_WORDS);
  });
});

describe('fit / hidden → shown (no hidden-tile chart defect)', () => {
  const box = { w: 0, h: 0 };
  const stubRect = () => vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(
    () => ({ width: box.w, height: box.h, top: 0, left: 0, x: 0, y: 0, right: box.w, bottom: box.h, toJSON: () => ({}) }) as DOMRect);
  const viewBoxes = (c: HTMLElement) => Array.from(svgs(c)).map((s) => s.getAttribute('viewBox'));
  const fallback = (row: GgwRow) => row.frames.map((f) => `0 0 ${PATTERN_CHART_VIEW_W} ${ggwChartHeight(f.tf, false)}`);

  it('mounted hidden at 0×0 → drawn at the fallback height; the RO callback refits; shown → 3 svgs, no hidden attr', () => {
    box.w = 0; box.h = 0;
    stubRect();
    const cbs: Array<() => void> = [];
    vi.stubGlobal('ResizeObserver', class {
      cb: () => void;
      constructor(cb: () => void) { this.cb = cb; cbs.push(cb); }
      observe() {}
      unobserve() {}
      disconnect() {}
    });
    const row = okRow();
    const { container, rerender } = render(tile(row, { fit: true, offPage: true }));
    const t = screen.getByTestId(`ggw-tile-${S}`);
    expect(t.hasAttribute('hidden')).toBe(true);
    expect(svgs(container).length).toBe(3);
    expect(viewBoxes(container).sort()).toEqual(fallback(row).sort());
    expect(cbs.length).toBe(3);
    box.w = 600; box.h = 300;
    act(() => { cbs.forEach((cb) => cb()); });
    const w = ggwFitViewW(600, PATTERN_CHART_VIEW_W);
    const fitted = `0 0 ${w} ${ggwFitViewBoxH(600, 300, w)}`;
    expect(viewBoxes(container)).toEqual([fitted, fitted, fitted]);
    expect(viewBoxes(container)).not.toEqual(fallback(row));
    rerender(tile(row, { fit: true, offPage: false }));
    expect(screen.getByTestId(`ggw-tile-${S}`).hasAttribute('hidden')).toBe(false);
    expect(svgs(container).length).toBe(3);
    expect(viewBoxes(container)).toEqual([fitted, fitted, fitted]);
  });
  it('NEGATIVE: no ResizeObserver at all → still drawn, at the fallback height', () => {
    box.w = 0; box.h = 0;
    stubRect();
    vi.stubGlobal('ResizeObserver', undefined);
    const row = okRow();
    const { container } = render(tile(row, { fit: true, offPage: true }));
    expect(svgs(container).length).toBe(3);
    expect(viewBoxes(container).sort()).toEqual(fallback(row).sort());
  });
});
