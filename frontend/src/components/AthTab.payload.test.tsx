import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FIXTURE from './__fixtures__/ath_tab_2026_09_29.json';
import { PatternChart } from './PatternChart';
import AthBoardNote from './AthBoardNote';
import ChartMaps from '../pages/ChartMaps';
import type { CmBoard, CmTile } from '../lib/chartMaps';

/* 🏔️ ATH tab — REAL payloads through the REAL components and page (2026-09-29).
 *
 * Ajay 2026-09-29, verbatim: "Can you give me a new tab - for all the stocks
 * that are reaching all time highs? call it ATH. Once some of them are going
 * below their ATH or 52 Week Highs.."
 *
 * The fixture is GET /chart-maps?tab=ath (and &sort=slipping) built in-process
 * inside the api container from the branch modules, read-only (every Mongo
 * write blocked, ATH_HISTORY_STORE=memory, the monthly history filled for the
 * whole universe first), after the 2026-09-29 close. Each group is trimmed to
 * a served-order subsequence that keeps both proven all-time and "high since"
 * cards; every other key is served verbatim. `empty_notes` are the backend's
 * own EMPTY_NOTE_AT / EMPTY_NOTE_SLIP strings. Only contract keys are read. */

type Fixture = { default: unknown; slipping: unknown; empty_notes: { at: string; slip: string } };
const F = FIXTURE as unknown as Fixture;
const JUNK = ['[object Object]', 'NaN', 'undefined', 'Infinity'];
const GROUPS = [
  ['default', 'at_ath', F.default],
  ['slipping', 'slipping', F.slipping],
] as const;

const renderTile = (t: CmTile) =>
  render(<MemoryRouter><PatternChart tile={t} /></MemoryRouter>);

describe.each(GROUPS)('🏔️ ATH payload sort=%s → real components', (sortKey, group, P) => {
  const board = P as unknown as CmBoard;
  const tiles = board.tiles as CmTile[];

  it('the board is the ath tab, the served group, UNMEASURED, the two served sorts', () => {
    expect(board.tab).toBe('ath');
    expect(board.sort).toBe(sortKey);
    expect((board.sorts || []).map((s) => s.key)).toEqual(['default', 'slipping']);
    const ab = board.ath_board!;
    expect(ab.state).toBe('ready');
    expect(ab.group).toBe(group);
    expect(ab.measured).toBe(false);
    expect(ab.note).toContain('UNMEASURED');
    expect(tiles.length).toBeGreaterThan(0);
    // both kinds present, so the proven / "high since" tests below are never vacuous
    expect(tiles.some((t) => t.ath!.proven)).toBe(true);
    expect(tiles.some((t) => !t.ath!.proven)).toBe(true);
    for (const t of tiles) expect(t.ath!.group, t.symbol).toBe(group);
  });

  it('every card: the served ATH pill on the PRICE rung, one neutral ATH reference line, no junk, never bounce / fake', () => {
    const lines: string[] = [];
    for (const t of tiles) {
      const a = t.ath!;
      expect(a.text, t.symbol).toBe(t.badges?.[0]?.text);
      const { container, unmount } = renderTile(t);
      const price = container.querySelector('.cm-rung-price');
      expect(price, `${t.symbol} PRICE rung`).not.toBeNull();
      expect(price!.textContent || '', t.symbol).toContain(a.text);
      // ONE ATH reference line (neutral), first; the 🔑 / now lines come from
      // the board's shared decorators.
      const neutral = t.lines.filter((l) => l.tone === 'neutral');
      expect(neutral, t.symbol).toHaveLength(1);
      expect(t.lines[0].tone, t.symbol).toBe('neutral');
      expect(t.lines[0].price, t.symbol).toBeCloseTo(a.slip ? a.slip.price : a.high, 4);
      const html = container.innerHTML;
      for (const bad of JUNK) expect(html.includes(bad), `${t.symbol} ${bad}`).toBe(false);
      expect(/bounce|fake/i.test(container.textContent || ''), t.symbol).toBe(false);
      lines.push(`${t.symbol}: ${a.text}`);
      unmount();
    }
    // eslint-disable-next-line no-console
    console.log([`🏔️ ATH sort=${sortKey} — PRICE rows`, ...lines].join('\n'));
  });

  it('an unproven card says "high since" and "not proven all-time", never "all-time high"; a proven one says all-time high', () => {
    for (const t of tiles) {
      const a = t.ath!;
      const from52 = a.slip?.from === '52w';
      if (a.proven) {
        expect(a.label, t.symbol).toBe('ATH');
        if (!from52) expect(a.text, t.symbol).toContain('all-time high');
        expect(a.text, t.symbol).not.toContain('not proven');
      } else {
        expect(a.label, t.symbol).toMatch(/^High since /);
        expect(a.text.includes('all-time high'), t.symbol).toBe(false);
        if (!from52) {
          expect(a.text, t.symbol).toContain('high since ');
          expect(a.text.endsWith('— not proven all-time'), t.symbol).toBe(true);
          expect(t.lines[0].label, t.symbol).toMatch(/^HIGH SINCE /);
        }
      }
    }
  });

  it('served order: 🏔️ by % over the prior high (through-today first); ↘️ freshest high first, smallest drop breaks ties', () => {
    if (group === 'at_ath') {
      const k = tiles.map((t) => t.ath!.px / (t.ath as unknown as { hi_prior: number }).hi_prior - 1);
      for (let i = 1; i < k.length; i++) expect(k[i], tiles[i].symbol).toBeLessThanOrEqual(k[i - 1] + 1e-12);
    } else {
      for (let i = 1; i < tiles.length; i++) {
        const p = tiles[i - 1].ath!.slip!;
        const c = tiles[i].ath!.slip!;
        expect(c.date <= p.date, tiles[i].symbol).toBe(true);
        if (c.date === p.date) expect(Math.abs(c.pct!), tiles[i].symbol).toBeGreaterThanOrEqual(Math.abs(p.pct!));
      }
    }
  });

  it('the served header and note render verbatim; proven all-time and "high since" are counted apart', () => {
    const ab = board.ath_board!;
    const { getByTestId } = render(
      <AthBoardNote board={ab} sorts={board.sorts} sort={board.sort} onSort={() => {}} />);
    expect(getByTestId('cm-ath-header').textContent).toBe(ab.header);
    expect(getByTestId('cm-ath-note').textContent).toBe(ab.note);
    expect(getByTestId(`cm-ath-sort-${sortKey}`).getAttribute('aria-pressed')).toBe('true');
    expect(ab.header).toContain('proven all-time high');
    expect(ab.header).toContain('not proven all-time');
    const c = ab.counts as Record<string, number>;
    expect(c.scanned).toBe(c.at_ath + c.slipping + c.at_52w_only + c.rest + c.stale + c.no_print + c.no_bars);
    expect(c.slipping).toBe(c.slip_from_ath + c.slip_from_high_since + c.slip_from_52w);
    expect(c.at_ath_proven).toBeLessThanOrEqual(c.at_ath);
    const text = getByTestId('cm-ath-board').textContent || '';
    for (const bad of JUNK) expect(text.includes(bad), bad).toBe(false);
    expect(/bounce|fake/i.test(text)).toBe(false);
  });
});

describe('🏔️ ATH — the real page on the real payloads', () => {
  const fresh = (k: 'default' | 'slipping') => JSON.parse(JSON.stringify(F[k]));
  const stub = (pick: (url: string) => unknown) => vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.includes('/chart-maps?')) return { ok: true, json: async () => pick(url) } as unknown as Response;
    return { ok: true, json: async () => ({}) } as unknown as Response;
  });
  const page = (entry: string) =>
    render(<MemoryRouter initialEntries={[entry]}><ChartMaps /></MemoryRouter>);
  const order = () => Array.from(document.querySelectorAll('.cm-grid .cm-tile-id b')).map((b) => b.textContent);

  beforeEach(() => {
    vi.restoreAllMocks();
    try { window.localStorage.clear(); } catch { /* no store in this runner */ }
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('both groups in served order, the toggle asks the server for ?sort=slipping', async () => {
    const fetchMock = stub((url) => fresh(url.includes('sort=slipping') ? 'slipping' : 'default'));
    vi.stubGlobal('fetch', fetchMock);
    page('/chart-maps?tab=ath&show=all');
    const want = (fresh('default').tiles as CmTile[]).map((t) => t.symbol);
    await waitFor(() => expect(order()).toEqual(want));
    expect(screen.getByTestId('cm-ath-header').textContent).toBe(fresh('default').ath_board.header);
    fireEvent.click(screen.getByTestId('cm-ath-sort-slipping'));
    const wantB = (fresh('slipping').tiles as CmTile[]).map((t) => t.symbol);
    await waitFor(() => expect(order()).toEqual(wantB));
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('sort=slipping'))).toBe(true);
    expect(screen.getByTestId('cm-ath-sort-slipping').getAttribute('aria-pressed')).toBe('true');
    const body = document.body.textContent || '';
    for (const bad of JUNK) expect(body.includes(bad), bad).toBe(false);
    expect(/bounce|fake/i.test(body)).toBe(false);
  });

  it('an empty group prints the served empty-group sentence', async () => {
    for (const [k, note] of [['default', F.empty_notes.at], ['slipping', F.empty_notes.slip]] as const) {
      const empty = { ...fresh(k), tiles: [], note };
      vi.stubGlobal('fetch', stub(() => JSON.parse(JSON.stringify(empty))));
      page(`/chart-maps?tab=ath${k === 'slipping' ? '&sort=slipping' : ''}`);
      await waitFor(() => expect(document.body.textContent || '').toContain(note));
      expect(note).not.toMatch(/bounce|fake|NaN|undefined/i);
      cleanup();
      vi.unstubAllGlobals();
    }
  });
});
