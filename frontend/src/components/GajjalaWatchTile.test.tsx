vi.mock('../lib/ggwFrames', async (orig) => (await import('../test/ggwFramesLegacy')).ggwFramesLegacy(orig));
/* 🚩 / 👀 the shared tile + ⤢ full-screen view (2026-11-16, ggcard3 spec §3.3 / §4 WP-A). A PURE MOVE out of
 * GajjalaWatchBoard.tsx plus opt-in additions for the 🚩 card view — Ajay 2026-11-16: "Also when I click on a card from
 * any of the Gajjala I would like us to open the 3 chart extension like in the Watch list..." → "Actually instead of 3
 * mins make it 15 mins timeframe".
 * NEGATIVES: a frame with bars draws its chart and no words; a Watch frame (no `as_of_et` key) prints no stamp chip;
 * the Watch's own ⤢ root keeps its exact class with no data-kind, no per-frame stamp and no empty words; the board file
 * no longer declares the moved functions; neither file renders a house chip. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { Frame, GgwStretch, Tile } from './GajjalaWatchTile';
import { GGC_STRETCH_ORDER } from '../lib/gajjalaCardView';
import { parseGgw, type GgwBoard, type GgwFrame, type GgwRow } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');

/** OMH's served row, frames relabelled 15m / 5m / 1m as the card view serves them; `mut` edits the raw frames. */
function cardRow(mut: (fr: any) => void = () => {}): GgwRow {
  const raw = clone(fixture) as any;
  const r = raw.rows[0];
  for (const f of r.frames) { if (f.tf === '3m') f.tf = '15m'; mut(f); }
  raw.rows = [r];
  return (parseGgw(raw) as GgwBoard).rows[0];
}
const watchRow = (): GgwRow => (parseGgw(clone(fixture)) as GgwBoard).rows[0];
const frameOf = (row: GgwRow, tf: string): GgwFrame => row.frames.find((f) => f.tf === tf)!;
const S = (fixture as any).rows[0].symbol as string;
const renderFrame = (f: GgwFrame) => render(<MemoryRouter><Frame f={f} phone fit={false} /></MemoryRouter>);

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); document.body.style.overflow = ''; });

describe('GgwStretch with an order (the 🚩 card view)', () => {
  it('draws 15m above 5m above 1m (DOM order); NEGATIVE: no 3m frame', () => {
    render(<MemoryRouter><GgwStretch row={cardRow()} phone removeLabel={null} onClose={() => {}} onStep={null}
                                     order={GGC_STRETCH_ORDER} kind="card" /></MemoryRouter>);
    const layer = screen.getByTestId('ggw-stretch');
    const ids = Array.from(layer.querySelectorAll('[data-testid="ggw-stretch-charts"] > figure')).map((f) => f.getAttribute('data-testid'));
    expect(ids).toEqual([`ggw-frame-${S}-15m`, `ggw-frame-${S}-5m`, `ggw-frame-${S}-1m`]);
    expect(layer.querySelector(`[data-testid="ggw-frame-${S}-3m"]`)).toBeNull();
    expect(layer.className).toBe('ggw-stretch ggw-stretch--card');
    expect(layer.getAttribute('data-kind')).toBe('card');
    expect(layer.parentElement).toBe(document.body);
  });
  // 2026-11-23 (vwapzones §3.9): the Watch order is now 15 / 5 / 1 — the card's — so the fallback draws the same order.
  it('NEGATIVE: without an order the same frames fall back to the Watch order (15m / 5m / 1m since 2026-11-23); no card root', () => {
    render(<MemoryRouter><GgwStretch row={cardRow()} phone removeLabel={null} onClose={() => {}} onStep={null} /></MemoryRouter>);
    const tfs = Array.from(screen.getByTestId('ggw-stretch').querySelectorAll('[data-testid="ggw-stretch-charts"] > figure'))
      .map((f) => f.getAttribute('data-tf'));
    expect(tfs).toEqual(['15m', '5m', '1m']);
    expect(screen.getByTestId('ggw-stretch').className).toBe('ggw-stretch');
    expect(screen.getByTestId('ggw-stretch').hasAttribute('data-kind')).toBe(false);
  });
  it('Esc calls onClose, ← → call onStep(−1 / +1), focus lands on ⤡, the page under it does not scroll', () => {
    const onClose = vi.fn();
    const onStep = vi.fn();
    render(<MemoryRouter><GgwStretch row={cardRow()} phone removeLabel={null} onClose={onClose} onStep={onStep}
                                     order={GGC_STRETCH_ORDER} kind="card" /></MemoryRouter>);
    expect(document.activeElement).toBe(screen.getByTestId('ggw-unstretch'));
    expect(document.body.style.overflow).toBe('hidden');
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(onStep.mock.calls).toEqual([[-1], [1]]);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId('ggw-stretch-prev'));
    fireEvent.click(screen.getByTestId('ggw-stretch-next'));
    expect(onStep.mock.calls).toEqual([[-1], [1], [-1], [1]]);
    fireEvent.click(screen.getByTestId('ggw-unstretch'));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
  it('NEGATIVE: onStep null → no ◀ ▶ and the arrows do nothing; no ✕ in the full-screen view', () => {
    const onClose = vi.fn();
    render(<MemoryRouter><GgwStretch row={cardRow()} phone removeLabel={null} onClose={onClose} onStep={null}
                                     order={GGC_STRETCH_ORDER} kind="card" /></MemoryRouter>);
    expect(screen.queryByTestId('ggw-stretch-prev')).toBeNull();
    expect(screen.queryByTestId('ggw-stretch-next')).toBeNull();
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByTestId('ggw-stretch').querySelector('.ggw-remove')).toBeNull();
  });
  it('Tile in stretch mode takes the order too', () => {
    render(<MemoryRouter><Tile row={cardRow()} phone fit={false} removeLabel={null} focused={false} busy={false}
                               onRemove={() => {}} onUnstretch={() => {}} order={GGC_STRETCH_ORDER} /></MemoryRouter>);
    const tfs = Array.from(screen.getByTestId('ggw-stretch-charts').querySelectorAll(':scope > figure')).map((f) => f.getAttribute('data-tf'));
    expect(tfs).toEqual(['15m', '5m', '1m']);
  });
});

describe('Frame — served empty words', () => {
  it('bars: [] + empty_text → the words and NO svg; the caption still prints', () => {
    const words = `No 1-minute bars stored for ${S} this session yet — a pass has to read it first`;
    const f = frameOf(cardRow((fr) => { if (fr.tf === '1m') { fr.tile.bars = []; fr.empty_text = words; } }), '1m');
    const { container } = renderFrame(f);
    expect(screen.getByTestId(`ggw-frame-empty-${S}-1m`).textContent).toBe(words);
    expect(container.querySelector('svg')).toBeNull();
    expect(container.querySelector('.ggw-cap-label')).not.toBeNull();
  });
  it('NEGATIVE: bars present → the svg and no words (even with empty_text served)', () => {
    const f = frameOf(cardRow((fr) => { fr.empty_text = 'should not print'; }), '1m');
    const { container } = renderFrame(f);
    expect(container.querySelector('svg')).not.toBeNull();
    expect(screen.queryByTestId(`ggw-frame-empty-${S}-1m`)).toBeNull();
    expect(container.textContent).not.toContain('should not print');
  });
  it('NEGATIVE: bars: [] with NO served words → the chart path as before (no words node)', () => {
    const f = frameOf(cardRow((fr) => { if (fr.tf === '1m') fr.tile.bars = []; }), '1m');
    renderFrame(f);
    expect(screen.queryByTestId(`ggw-frame-empty-${S}-1m`)).toBeNull();
  });
});

describe('Frame — its own served stamp (C3)', () => {
  it("as_of_et '09:41' → the chip prints 09:41 with the head chip's look", () => {
    const f = frameOf(cardRow((fr) => { fr.as_of_et = '09:41'; fr.stale = false; }), '1m');
    renderFrame(f);
    const chip = screen.getByTestId(`ggw-frame-asof-${S}-1m`);
    expect(chip.textContent).toBe('09:41');
    expect(chip.className).toBe('ggw-chip ggw-asof');
    expect(chip.closest('figcaption')).not.toBeNull();
  });
  it('stale: true → "⚠️ 09:41" and ggw-warn', () => {
    const f = frameOf(cardRow((fr) => { fr.as_of_et = '09:41'; fr.stale = true; }), '1m');
    renderFrame(f);
    const chip = screen.getByTestId(`ggw-frame-asof-${S}-1m`);
    expect(chip.textContent).toBe('⚠️ 09:41');
    expect(chip.classList.contains('ggw-warn')).toBe(true);
  });
  it('NEGATIVE: a Watch frame (no as_of_et key) → NO ggw-frame-asof node; served null → none either', () => {
    const { container } = renderFrame(frameOf(watchRow(), '1m'));
    expect(container.querySelector('[data-testid^="ggw-frame-asof-"]')).toBeNull();
    cleanup();
    const f = frameOf(cardRow((fr) => { fr.as_of_et = null; fr.stale = false; }), '5m');
    const r2 = renderFrame(f);
    expect(r2.container.querySelector('[data-testid^="ggw-frame-asof-"]')).toBeNull();
  });
});

describe('👀 the Watch keeps its exact view (pure move)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('localStorage', {
      getItem: () => null, setItem: () => {}, removeItem: () => {}, clear: () => {}, key: () => null, length: 0,
    });
  });
  it('NEGATIVE: the Watch ⤢ root has no kind class / data-kind, no per-frame stamp, no empty words; order 5 → 3 → 1', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {},
    }));
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => clone(fixture) })));
    render(<MemoryRouter><GajjalaWatchBoard /></MemoryRouter>);
    for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${S}`));
    const layer = screen.getByTestId('ggw-stretch');
    expect(layer.className).toBe('ggw-stretch');
    expect(layer.hasAttribute('data-kind')).toBe(false);
    expect(document.querySelector('[data-testid^="ggw-frame-asof-"]')).toBeNull();
    expect(document.querySelector('.ggw-frame-empty')).toBeNull();
    const tfs = Array.from(layer.querySelectorAll('[data-testid="ggw-stretch-charts"] > figure')).map((f) => f.getAttribute('data-tf'));
    expect(tfs).toEqual(['5m', '1m', '3m']);   // 2026-11-23: order 15/5/1 over this older 1m/3m/5m payload — the 3m follows
  });
});

describe('source guards (the move)', () => {
  it('the board imports GgwStretch / Tile / usePhone from ./GajjalaWatchTile and declares none of the moved functions', async () => {
    const src = noComments(await readSource('src/components/GajjalaWatchBoard.tsx'));
    expect(src).toMatch(/import \{[^}]*\bGgwStretch\b[^}]*\} from '\.\/GajjalaWatchTile'/);
    for (const fn of ['Stretch', 'Tile', 'Frame', 'usePhone', 'phoneNow', 'useFitBox']) {
      expect(src, fn).not.toMatch(new RegExp(`function ${fn}\\b`));
    }
    expect(src).toContain('<GgwStretch ');
  });
  it('NEGATIVE: the tile file renders no house chip, no 📡 and no feed word', async () => {
    const src = await readSource('src/components/GajjalaWatchTile.tsx');
    expect(src).not.toMatch(/<(GrowthChip|ExplosiveChip|ShortInterestChip)\b/);
    expect(src).not.toContain('📡');
    expect(noComments(src)).not.toMatch(/['"`][^'"`\n]*\b(kicked|quiet|reconnect)/i);
  });
});
