/* 👀 2026-11-27 (spec watch5m §3.5, WP tile) — Ajay: "Only 5 mins may be give me option in our existing Watch charts to
 * disable all 15 and all 1 min or on the chart itself.." and "Also on the expanded view I need 5 mins by default to look
 * in detail and not sure what the line on volume is its blocking my story..".
 * Opt-in props on the shared tile: `frames` / `one` / `volAvg` / `framesMenu` on Tile, `frames` / `volAvg` /
 * `framesMenu` on GgwStretch, `volAvg` on Frame.
 * NEGATIVES: no `frames` (and `[GGW_FRAMES_EVERY]`, and all three) → HTML identical to today; `frames` without `one` →
 * no one-chart tile; `one` with three frames → no one-chart tile; ⤢ never gets `ggw-tile--one`; the card click's ⤢ call
 * (no new prop) keeps three frames, the average line and no menu; `volAvg` absent → the line draws; `stack` ignores
 * `one`; a pending row stays the pending panel; a stored frame that is not served never blanks the tile. */
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { Frame, GgwStretch, Tile } from './GajjalaWatchTile';
import { GGW_FIT_GROW, ggwChartHeight, parseGgw, type GgwBoard, type GgwFrame, type GgwRow } from '../lib/gajjalaWatch';
import { GGW_FRAMES_EVERY } from '../lib/ggwFrames';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');

/** OMH's served row with frames 1m / 5m / 15m in the backend FRAMES order (the fixture's 3m relabelled — the live Watch's
 *  set); `keep` filters them. */
function row(keep: (tf: string) => boolean = () => true): GgwRow {
  const raw = clone(fixture) as any;
  const r = raw.rows[0];
  for (const f of r.frames) if (f.tf === '3m') { f.tf = '15m'; f.label = '15-min'; }
  const served = ['1m', '5m', '15m'];
  r.frames = r.frames.filter((f: any) => keep(f.tf)).sort((a: any, b: any) => served.indexOf(a.tf) - served.indexOf(b.tf));
  raw.rows = [r];
  return (parseGgw(raw) as GgwBoard).rows[0];
}
const S = (fixture as any).rows[0].symbol as string;
const pendingRow = (): GgwRow =>
  ({ ...row(), state: 'pending', text: 'stub served pending words', frames: [], rang: [], from_session: null, as_of_et: null, stale: false });

type TileExtra = Partial<{ frames: ReadonlyArray<string>; one: boolean; volAvg: boolean; framesMenu: ReactNode;
  fit: boolean; stack: boolean; run: { button: ReactNode; panel: ReactNode; open: boolean } }>;
const tile = (r: GgwRow, x: TileExtra = {}) => {
  const { fit = false, ...rest } = x;
  return render(
    <MemoryRouter>
      <Tile row={r} phone={false} fit={fit} removeLabel="Remove" focused={false} busy={false} onRemove={() => {}}
            onStretch={() => {}} {...rest} />
    </MemoryRouter>,
  );
};
const tfs = (el: ParentNode) => Array.from(el.querySelectorAll('figure.ggw-frame')).map((f) => f.getAttribute('data-tf'));
const tileEl = (c: HTMLElement) => c.querySelector(`[data-testid="ggw-tile-${S}"]`) as HTMLElement;

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); document.body.style.overflow = ''; });

describe('Tile frames + one — the one-chart 5-min tile', () => {
  it("frames={['5m']} one → exactly one 5-min frame in ggw-one-charts, root ggw-tile--one; NEGATIVE no 1m / 15m, no pair", () => {
    const { container } = tile(row(), { frames: ['5m'], one: true });
    const t = tileEl(container);
    expect(t.className.split(' ')).toContain('ggw-tile--one');
    expect(container.querySelectorAll('.ggw-frame')).toHaveLength(1);
    expect(container.querySelector('.ggw-frame')!.getAttribute('data-tf')).toBe('5m');
    const win = screen.getByTestId('ggw-one-charts');
    expect(win.className).toBe('ggw-dark ggw-charts ggw-charts--one');
    expect(container.querySelector('[data-tf="1m"]')).toBeNull();
    expect(container.querySelector('[data-tf="15m"]')).toBeNull();
    expect(container.querySelector('.ggw-frame-pair')).toBeNull();
    expect(container.querySelector('.ggw-charts--stretch')).toBeNull();
    expect(screen.queryByTestId('ggw-stretch-charts')).toBeNull();
  });
  it('fitted one-chart tile: the frame grows to fill (flexGrow 1); the ▶ Rules panel stays the LAST child when open', () => {
    const { container } = tile(row(), { frames: ['5m'], one: true, fit: true,
      run: { button: <button type="button" data-testid="run-b">▶</button>, panel: <aside data-testid="run-p" />, open: true } });
    const win = screen.getByTestId('ggw-one-charts');
    expect(win.className).toBe('ggw-dark ggw-charts ggw-charts--one ggw-charts--run');
    expect((container.querySelector('.ggw-frame') as HTMLElement).style.flexGrow).toBe('1');
    expect(win.lastElementChild).toBe(screen.getByTestId('run-p'));
  });
  it("NEGATIVE: frames={['5m']} WITHOUT one → no ggw-tile--one; the board branch with a lone pair frame", () => {
    const { container } = tile(row(), { frames: ['5m'] });
    expect(tileEl(container).className.split(' ')).not.toContain('ggw-tile--one');
    expect(screen.queryByTestId('ggw-one-charts')).toBeNull();
    const pair = container.querySelector('.ggw-frame-pair')!;
    expect(tfs(pair)).toEqual(['5m']);
    expect(tfs(container)).toEqual(['5m']);
  });
  it('NEGATIVE: one with three frames shown → no ggw-tile--one (today\'s 1-min on top + the pair)', () => {
    const { container } = tile(row(), { frames: ['1m', '5m', '15m'], one: true });
    expect(tileEl(container).className.split(' ')).not.toContain('ggw-tile--one');
    expect(screen.queryByTestId('ggw-one-charts')).toBeNull();
    expect(tfs(container.querySelector('.ggw-frame-pair')!)).toEqual(['5m', '15m']);
  });
  it("frames={['3m']} on a 1m / 5m / 15m row → the 5-min frame (fallback), never blank", () => {
    const { container } = tile(row(), { frames: ['3m'], one: true });
    expect(tfs(container)).toEqual(['5m']);
    expect(tileEl(container).className.split(' ')).toContain('ggw-tile--one');
  });
});

describe('Tile frames — two frames on, and the byte-identical opt-out', () => {
  it("['1m','5m'] → the 1-min on top + a ONE-frame pair; ['5m','15m'] → the pair only", () => {
    const a = tile(row(), { frames: ['1m', '5m'] });
    const charts = a.container.querySelector('.ggw-charts')!;
    expect((charts.firstElementChild as HTMLElement).getAttribute('data-tf')).toBe('1m');
    expect(tfs(a.container.querySelector('.ggw-frame-pair')!)).toEqual(['5m']);
    a.unmount();
    const b = tile(row(), { frames: ['5m', '15m'] });
    expect(b.container.querySelector('.ggw-charts > figure.ggw-frame')).toBeNull();
    expect(tfs(b.container.querySelector('.ggw-frame-pair')!)).toEqual(['5m', '15m']);
  });
  it('fitted, two frames on: a one-frame pair grows by that frame\'s own GGW_CHART_H height; NEGATIVE the two-frame pair keeps GGW_FIT_GROW.pair', () => {
    const a = tile(row(), { frames: ['1m', '5m'], fit: true });
    expect((a.container.querySelector('.ggw-frame-pair') as HTMLElement).style.flexGrow).toBe(String(ggwChartHeight('5m', false)));
    a.unmount();
    const b = tile(row(), { frames: ['5m', '15m'], fit: true });
    expect((b.container.querySelector('.ggw-frame-pair') as HTMLElement).style.flexGrow).toBe(String(GGW_FIT_GROW.pair));
  });
  it('NEGATIVE: with NO frames prop a served 1m + 5m row keeps today\'s GGW_FIT_GROW.pair share (the rule is opt-in)', () => {
    const { container } = tile(row((tf) => tf !== '15m'), { fit: true });
    expect((container.querySelector('.ggw-frame-pair') as HTMLElement).style.flexGrow).toBe(String(GGW_FIT_GROW.pair));
  });
  for (const fit of [false, true]) {
    it(`NEGATIVE (fit=${fit}): all three, and [GGW_FRAMES_EVERY], and one=false → HTML identical to no frames prop`, () => {
      const base = tile(row(), { fit });
      const want = base.container.innerHTML;
      base.unmount();
      expect(want).toContain('ggw-frame-pair');
      for (const x of [{ frames: ['1m', '5m', '15m'] }, { frames: [GGW_FRAMES_EVERY] }, { frames: [GGW_FRAMES_EVERY], one: false },
                       { frames: undefined, one: undefined, volAvg: undefined, framesMenu: undefined }] as TileExtra[]) {
        const r = tile(row(), { fit, ...x });
        expect(r.container.innerHTML).toBe(want);
        r.unmount();
      }
    });
  }
  it("NEGATIVE: [GGW_FRAMES_EVERY] with one → never the one-chart tile (three frames shown)", () => {
    const { container } = tile(row(), { frames: [GGW_FRAMES_EVERY], one: true });
    expect(tileEl(container).className.split(' ')).not.toContain('ggw-tile--one');
    expect(tfs(container)).toEqual(['1m', '5m', '15m']);
  });
});

describe('Tile volAvg + framesMenu', () => {
  it('volAvg={false} reaches every Frame (0 path.pc-vol-sma, columns still drawn); NEGATIVE absent → the line draws', () => {
    const off = tile(row(), { volAvg: false });
    expect(off.container.querySelectorAll('path.pc-vol-sma')).toHaveLength(0);
    expect(off.container.querySelectorAll('rect.pc-vol').length).toBeGreaterThan(0);
    off.unmount();
    const on = tile(row());
    for (const fig of Array.from(on.container.querySelectorAll('figure.ggw-frame'))) {
      expect(fig.querySelectorAll('path.pc-vol-sma').length).toBeGreaterThan(0);
    }
  });
  it('volAvg={false} on the one-chart tile too', () => {
    const { container } = tile(row(), { frames: ['5m'], one: true, volAvg: false });
    expect(container.querySelectorAll('path.pc-vol-sma')).toHaveLength(0);
    expect(container.querySelectorAll('rect.pc-vol').length).toBeGreaterThan(0);
  });
  it('Frame volAvg={false} → no line; NEGATIVE Frame without it → HTML identical to volAvg={true}', () => {
    const f: GgwFrame = row().frames.find((x) => x.tf === '5m')!;
    const r1 = render(<MemoryRouter><Frame f={f} phone fit={false} volAvg={false} /></MemoryRouter>);
    expect(r1.container.querySelectorAll('path.pc-vol-sma')).toHaveLength(0);
    r1.unmount();
    const r2 = render(<MemoryRouter><Frame f={f} phone fit={false} /></MemoryRouter>);
    const want = r2.container.innerHTML;
    expect(r2.container.querySelectorAll('path.pc-vol-sma').length).toBeGreaterThan(0);
    r2.unmount();
    const r3 = render(<MemoryRouter><Frame f={f} phone fit={false} volAvg /></MemoryRouter>);
    expect(r3.container.innerHTML).toBe(want);
  });
  it('framesMenu renders inside .ggw-actions right after the ▶ Rules button; NEGATIVE absent → nothing there', () => {
    const run = { button: <button type="button" data-testid="run-b">▶</button>, panel: null, open: false };
    const a = tile(row(), { run, framesMenu: <span data-testid="fm">5-min ▾</span> });
    const fm = screen.getByTestId('fm');
    expect(fm.parentElement!.className).toBe('ggw-actions');
    expect(screen.getByTestId('run-b').nextElementSibling).toBe(fm);
    a.unmount();
    tile(row(), { run });
    expect(screen.queryByTestId('fm')).toBeNull();
    expect(screen.getByTestId('run-b').nextElementSibling!.getAttribute('data-testid')).toBe(`ggw-stretch-btn-${S}`);
  });
});

describe('Tile edge cases — pending, stack', () => {
  it('a pending row (no frames) with frames + one → the pending panel as today; NEGATIVE no chart, no ggw-tile--one', () => {
    const want = tile(pendingRow()).container.innerHTML;
    cleanup();
    const { container } = tile(pendingRow(), { frames: ['5m'], one: true });
    expect(container.innerHTML).toBe(want);
    expect(screen.getByTestId(`ggw-pending-${S}`)).toBeTruthy();
    expect(container.querySelector('figure.ggw-frame')).toBeNull();
    expect(screen.queryByTestId('ggw-one-charts')).toBeNull();
    expect(tileEl(container).className.split(' ')).not.toContain('ggw-tile--one');
  });
  it('NEGATIVE: stack (the card grid) ignores one — still ggw-stack-charts, never ggw-tile--one', () => {
    const { container } = tile(row(), { stack: true, frames: ['5m'], one: true });
    expect(screen.getByTestId('ggw-stack-charts')).toBeTruthy();
    expect(screen.queryByTestId('ggw-one-charts')).toBeNull();
    expect(tileEl(container).className.split(' ')).not.toContain('ggw-tile--one');
  });
});

describe('GgwStretch frames / volAvg / framesMenu (the Watch ⤢)', () => {
  const stretch = (x: Partial<{ frames: ReadonlyArray<string>; volAvg: boolean; framesMenu: ReactNode }> = {}) => render(
    <MemoryRouter><GgwStretch row={row()} phone={false} removeLabel={null} onClose={() => {}} onStep={null} {...x} /></MemoryRouter>,
  );
  it("frames={['5m']} → ONE frame in ggw-stretch-charts; NEGATIVE ggw-tile--one is never on the ⤢ tile", () => {
    stretch({ frames: ['5m'] });
    const layer = screen.getByTestId('ggw-stretch');
    expect(tfs(screen.getByTestId('ggw-stretch-charts'))).toEqual(['5m']);
    expect(layer.querySelector('.ggw-tile--one')).toBeNull();
    expect(screen.queryByTestId('ggw-one-charts')).toBeNull();
    expect((layer.querySelector('figure.ggw-frame') as HTMLElement).style.flexGrow).toBe('1');
  });
  it("['1m','15m','5m'] → DOM order 15m, 5m, 1m (GGW_STRETCH_ORDER among the frames on)", () => {
    stretch({ frames: ['1m', '15m', '5m'] });
    expect(tfs(screen.getByTestId('ggw-stretch-charts'))).toEqual(['15m', '5m', '1m']);
  });
  it("['1m','5m'] → 5m above 1m, no 15m", () => {
    stretch({ frames: ['1m', '5m'] });
    expect(tfs(screen.getByTestId('ggw-stretch-charts'))).toEqual(['5m', '1m']);
  });
  it('framesMenu + volAvg={false} reach the ⤢ tile: the menu in .ggw-actions, no average line', () => {
    stretch({ frames: ['5m'], volAvg: false, framesMenu: <span data-testid="sfm">5-min ▾</span> });
    expect(screen.getByTestId('sfm').parentElement!.className).toBe('ggw-actions');
    expect(screen.getByTestId('ggw-stretch').querySelectorAll('path.pc-vol-sma')).toHaveLength(0);
  });
  it('[C4] NEGATIVE: NO frames / volAvg / framesMenu (the card click\'s call) → three frames 15 / 5 / 1, the line in each, no menu; HTML identical to every-frame + volAvg on', () => {
    const a = stretch();
    const layer = screen.getByTestId('ggw-stretch');
    expect(tfs(screen.getByTestId('ggw-stretch-charts'))).toEqual(['15m', '5m', '1m']);
    for (const fig of Array.from(layer.querySelectorAll('figure.ggw-frame'))) {
      expect(fig.querySelectorAll('path.pc-vol-sma').length).toBeGreaterThan(0);
    }
    expect(layer.querySelector('.ggw-frames')).toBeNull();
    const want = layer.outerHTML;
    a.unmount();
    stretch({ frames: [GGW_FRAMES_EVERY], volAvg: true });
    expect(screen.getByTestId('ggw-stretch').outerHTML).toBe(want);
  });
});

describe('source guards', () => {
  it('the Tile reads the choice ONLY through ggwFramesShown (no .includes / .indexOf on `frames`); one import line from lib/ggwFrames', async () => {
    const src = noComments(await readSource('src/components/GajjalaWatchTile.tsx'));
    expect(src).toMatch(/ggwFramesShown\(row\.frames, frames\)/);
    expect(src).not.toMatch(/(?<![.\w])frames\??\.(includes|indexOf|some|find)\(/);
    expect(src.match(/from '\.\.\/lib\/ggwFrames'/g)).toHaveLength(1);
    expect(src).not.toMatch(/ggwDenseMode/);
  });
  it('the new import sits on its own line right after the lib/ggwLive import (clear of the concurrent branch\'s hunks)', async () => {
    const lines = (await readSource('src/components/GajjalaWatchTile.tsx')).split('\n');
    const i = lines.findIndex((l) => l.includes("from '../lib/ggwLive';"));
    expect(i).toBeGreaterThan(0);
    expect(lines[i + 1]).toBe("import { ggwFramesShown } from '../lib/ggwFrames';");
  });
});
