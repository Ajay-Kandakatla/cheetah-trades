/* 🚩 PatternChart opt-in `onOpenView` + the separate SEPA page link (2026-11-16, spec ggcard3 §3.5 / WP-B).
 *
 * Ajay 2026-11-16: "Also when I click on a card from any of the Gajjala I would like us to open the 3 chart extension
 * like in the Watch list... Also put a SEPA page link for it separaetely on the card" and then "Actually instead of
 * 3 mins make it 15 mins timeframe".
 *
 * With the prop the card body is a role="button" root that opens the ⤢ view; the stock page is the "SEPA page" link in
 * the action row (the served tile.href, &tf= kept). [C5] a keydown that bubbled from an inner link / button never
 * opens the view and is never preventDefault-ed. [C4] the prop is ONE stable function: same props ⇒ no re-render.
 * NEGATIVES: without the prop the card is today's SEPA Link with no SEPA link chip; chartOnly ignores the prop; Yahoo,
 * ➕ Watch and ▸ more never open the view. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { filterTile } from '../lib/chartOverlays';
import { withSource } from '../lib/navSource';
import { GGW_LIST_PATH, resetGgwList } from '../lib/ggWatchList';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { openViewTestId, openViewTitle, SEPA_LINK_LABEL, sepaLinkTestId, sepaLinkTitle } from '../lib/cardLinks';
import { yahooTitle } from '../lib/yahooLink';
import { VOYA } from '../lib/__fixtures__/cardLadder.tiles';
import type { CmBar, CmTile } from '../lib/chartMaps';

/* [C4] render-count probe: cardLadder runs exactly once per PatternChart body render. */
const ladderCalls = vi.hoisted(() => ({ n: 0 }));
vi.mock('../lib/cardLadder', async (importOriginal) => {
  const real = await importOriginal<typeof import('../lib/cardLadder')>();
  return {
    ...real,
    cardLadder: (...a: Parameters<typeof real.cardLadder>) => { ladderCalls.n += 1; return real.cardLadder(...a); },
  };
});

const bars = (n = 40): CmBar[] => Array.from({ length: n }, (_, i) => {
  const c = 10 + i * 0.1;
  return { t: `2026-11-16 ${String(9 + Math.floor((30 + i * 5) / 60)).padStart(2, '0')}:${String((30 + i * 5) % 60).padStart(2, '0')}`,
    o: c - 0.1, h: c + 0.3, l: c - 0.4, c, v: 1_000 };
});
/* The served 🚩 href: board_mod._href(sym) + &tf=5m_today (chart_href, F8). */
const HREF = '/sepa/IONQ?tab=supply&tf=5m_today';
const TILE: CmTile = {
  symbol: 'IONQ', name: 'IonQ Inc', href: HREF, bars: bars(), bands: [], lines: [], markers: [], stats: [], why: '',
};
/* VOYA carries a ▸ more fold (the ladder fixture). */
const MORE_TILE: CmTile = { ...filterTile(VOYA, new Set(['trade'])), href: '/sepa/VOYA?tab=supply&tf=5m_today' };

let loc = { pathname: '', search: '' };
function Probe() { const l = useLocation(); loc = { pathname: l.pathname, search: l.search }; return null; }

const START = '/chart-maps?tab=gajjala';
const draw = (props: Record<string, unknown> = {}, tile: CmTile = TILE) => render(
  <MemoryRouter initialEntries={[START]}>
    <Probe />
    <PatternChart tile={tile} {...props} />
  </MemoryRouter>,
);

const LABELS = { add: '➕ Watch', remove: '➖ Watch', add_title: "Add {sym} to 👀 Gajjala's Watch",
  remove_title: "Remove {sym} from 👀 Gajjala's Watch" };
let writes: string[];
beforeEach(() => {
  resetGgwList();
  _resetSignalWatchlist();
  writes = [];
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    if (method !== 'GET') writes.push(`${method} ${url}`);
    if (String(url).endsWith(GGW_LIST_PATH)) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(
        { state: 'ok', symbols: [], max: 12, full: false, full_text: 'full', labels: LABELS }) });
    }
    return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
  }));
  vi.stubGlobal('open', vi.fn());
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('PatternChart onOpenView — the card body opens the ⤢ view', () => {
  it('root = role="button" div with the served title words, the test id, tabIndex 0; NO <a> wraps the card', () => {
    const { container } = draw({ onOpenView: vi.fn() });
    const root = screen.getByTestId(openViewTestId('IONQ'));
    expect(root.tagName).toBe('DIV');
    expect(root.getAttribute('role')).toBe('button');
    expect(root.getAttribute('tabindex')).toBe('0');
    expect(root.getAttribute('aria-label')).toBe(openViewTitle('IONQ'));
    expect(root.getAttribute('aria-label')).toBe('Open IONQ — 15, 5 and 1-minute charts (⤢)');
    /* §3.5: aria-label only — no hover tooltip over the whole card (chips, stats) */
    expect(root.hasAttribute('title')).toBe(false);
    expect(container.querySelector(`[title="${openViewTitle('IONQ')}"]`)).toBeNull();
    expect(root.classList.contains('cm-tile')).toBe(true);
    expect(root.classList.contains('cm-tile-openview')).toBe(true);
    expect(root.closest('a')).toBeNull();
    expect(container.querySelector('a[aria-label$="open SEPA detail"]')).toBeNull();
    expect(container.firstElementChild).toBe(root);
  });

  it('a click on the body calls onOpenView(symbol) once and does NOT navigate', () => {
    const fn = vi.fn();
    draw({ onOpenView: fn });
    fireEvent.click(screen.getByTestId(openViewTestId('IONQ')));
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('IONQ');
    expect(loc.pathname + loc.search).toBe(START);
  });

  it('a click on the chart svg / the head (inside the body) opens the view too', () => {
    const fn = vi.fn();
    const { container } = draw({ onOpenView: fn });
    fireEvent.click(container.querySelector('svg')!);
    fireEvent.click(container.querySelector('.cm-tile-id b')!);
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('Enter and Space ON THE ROOT open the view and are preventDefault-ed', () => {
    const fn = vi.fn();
    draw({ onOpenView: fn });
    const root = screen.getByTestId(openViewTestId('IONQ'));
    expect(fireEvent.keyDown(root, { key: 'Enter' })).toBe(false);
    expect(fireEvent.keyDown(root, { key: ' ' })).toBe(false);
    expect(fn).toHaveBeenCalledTimes(2);
    expect(fn).toHaveBeenNthCalledWith(2, 'IONQ');
  });

  it('NEGATIVE: other keys on the root (Tab, Escape, a) do nothing and are not preventDefault-ed', () => {
    const fn = vi.fn();
    draw({ onOpenView: fn });
    const root = screen.getByTestId(openViewTestId('IONQ'));
    for (const key of ['Tab', 'Escape', 'a', 'ArrowDown']) expect(fireEvent.keyDown(root, { key })).toBe(true);
    expect(fn).not.toHaveBeenCalled();
  });
});

describe('PatternChart onOpenView — the SEPA page link', () => {
  it('FIRST in the action row; href = withSource(tile.href) keeping &tf=; label and title are the structural words', () => {
    const { container } = draw({ onOpenView: vi.fn() });
    const link = screen.getByTestId(sepaLinkTestId('IONQ'));
    expect(link.tagName).toBe('A');
    expect(link.textContent).toBe(SEPA_LINK_LABEL);
    expect(link.textContent).toBe('SEPA page');
    expect(link.getAttribute('aria-label')).toBe(sepaLinkTitle('IONQ'));
    expect(link.getAttribute('title')).toBe('Open IONQ on the SEPA page');
    expect(link.classList.contains('cm-sepa-link')).toBe(true);
    expect(link.getAttribute('href')).toBe(withSource(HREF, 'chart-maps', '?tab=gajjala'));
    expect(link.getAttribute('href')).toContain('tf=5m_today');
    expect(link.getAttribute('href')).toContain('from=chart-maps');
    const actions = container.querySelector('.cm-tile-actions')!;
    expect(actions.firstElementChild).toBe(link);
  });

  it('a click on the SEPA link navigates to the stock page (&tf= kept) and does NOT call onOpenView', () => {
    const fn = vi.fn();
    draw({ onOpenView: fn });
    fireEvent.click(screen.getByTestId(sepaLinkTestId('IONQ')));
    expect(fn).not.toHaveBeenCalled();
    expect(loc.pathname).toBe('/sepa/IONQ');
    expect(new URLSearchParams(loc.search).get('tf')).toBe('5m_today');
    expect(new URLSearchParams(loc.search).get('tab')).toBe('supply');
  });

  it('[C5] Enter / Space dispatched on the focused SEPA link → onOpenView NOT called and the event NOT defaultPrevented', () => {
    const fn = vi.fn();
    draw({ onOpenView: fn });
    const link = screen.getByTestId(sepaLinkTestId('IONQ'));
    link.focus();
    expect(document.activeElement).toBe(link);
    expect(fireEvent.keyDown(link, { key: 'Enter' })).toBe(true);
    expect(fireEvent.keyDown(link, { key: ' ' })).toBe(true);
    expect(fn).not.toHaveBeenCalled();
  });
});

describe('PatternChart onOpenView — NEGATIVES: the other action-row controls never open the view', () => {
  it('Yahoo: click opens Yahoo, never the view; Enter on it does not open the view and is not preventDefault-ed', () => {
    const fn = vi.fn();
    draw({ onOpenView: fn });
    const y = screen.getByRole('button', { name: yahooTitle('IONQ') });
    expect(fireEvent.keyDown(y, { key: 'Enter' })).toBe(true);
    fireEvent.click(y);
    expect(fn).not.toHaveBeenCalled();
    expect(window.open).toHaveBeenCalledTimes(1);
    expect(loc.pathname + loc.search).toBe(START);
  });

  it('➕ Watch: click toggles the watch (a write), never the view; Enter on it does not open the view', async () => {
    const fn = vi.fn();
    draw({ onOpenView: fn });
    const w = await screen.findByTestId('ggw-card-btn-IONQ');
    expect(fireEvent.keyDown(w, { key: 'Enter' })).toBe(true);
    await act(async () => { fireEvent.click(w); });
    expect(fn).not.toHaveBeenCalled();
    expect(writes.some((x) => x.includes('gajjala-watch'))).toBe(true);
  });

  it('+ Signals: click never opens the view', () => {
    const fn = vi.fn();
    draw({ onOpenView: fn });
    fireEvent.click(screen.getByTestId('watch-IONQ'));
    expect(fn).not.toHaveBeenCalled();
  });

  it('▸ more: click toggles the fold, never the view; Enter on it does not open the view', () => {
    const fn = vi.fn();
    const { container } = draw({ onOpenView: fn }, MORE_TILE);
    const more = container.querySelector('.cm-badge-more') as HTMLButtonElement;
    expect(more).not.toBeNull();
    expect(fireEvent.keyDown(more, { key: 'Enter' })).toBe(true);
    fireEvent.click(more);
    expect(more.getAttribute('aria-expanded')).toBe('true');
    expect(fn).not.toHaveBeenCalled();
    expect(loc.pathname + loc.search).toBe(START);
  });
});

describe('PatternChart onOpenView — [C4] memo holds with ONE stable function', () => {
  it('same tile + the SAME onOpenView reference ⇒ the body does not run again; NEGATIVE: a NEW function ⇒ it does', () => {
    const fn = vi.fn();
    const tree = (cb: (s: string) => void) => (
      <MemoryRouter initialEntries={[START]}><PatternChart tile={TILE} onOpenView={cb} /></MemoryRouter>
    );
    ladderCalls.n = 0;
    const { rerender } = render(tree(fn));
    const settled = ladderCalls.n;
    expect(settled).toBeGreaterThan(0);
    rerender(tree(fn));
    rerender(tree(fn));
    expect(ladderCalls.n).toBe(settled);
    rerender(tree(vi.fn()));
    expect(ladderCalls.n).toBeGreaterThan(settled);
  });
});

describe('PatternChart without onOpenView — NEGATIVES: every other board unchanged', () => {
  it('the whole card is the SEPA Link ("— open SEPA detail"); NO cm-sepa-link, NO role="button", NO openview class', () => {
    const { container } = draw();
    const a = container.querySelector('a[aria-label="IONQ — open SEPA detail"]')!;
    expect(a).not.toBeNull();
    expect(a.getAttribute('href')).toBe(withSource(HREF, 'chart-maps', '?tab=gajjala'));
    expect(a.firstElementChild!.className).toBe('cm-tile');
    expect(screen.queryByTestId(sepaLinkTestId('IONQ'))).toBeNull();
    expect(container.querySelector('.cm-sepa-link')).toBeNull();
    expect(container.querySelector('[role="button"]')).toBeNull();
    expect(container.querySelector('.cm-tile-openview')).toBeNull();
    expect(screen.queryByTestId(openViewTestId('IONQ'))).toBeNull();
    fireEvent.click(container.querySelector('svg')!);
    expect(loc.pathname).toBe('/sepa/IONQ');
  });

  it('the body inside is the same nodes: the openview root minus the SEPA link == the default .cm-tile', () => {
    const plain = draw().container.querySelector('a > .cm-tile')!.innerHTML;
    cleanup();
    const { container } = draw({ onOpenView: vi.fn() });
    const root = container.querySelector('.cm-tile-openview')!.cloneNode(true) as HTMLElement;
    root.querySelector('.cm-sepa-link')!.remove();
    expect(root.innerHTML).toBe(plain);
  });

  it('chartOnly ignores onOpenView: a plain chart tile, no button, no SEPA link, a click calls nothing', () => {
    const fn = vi.fn();
    const { container } = draw({ chartOnly: true, onOpenView: fn });
    expect(container.querySelector('.cm-tile-chart-only')).not.toBeNull();
    expect(container.querySelector('[role="button"]')).toBeNull();
    expect(container.querySelector('.cm-sepa-link')).toBeNull();
    expect(container.querySelector('a')).toBeNull();
    fireEvent.click(container.querySelector('svg')!);
    fireEvent.keyDown(container.querySelector('.cm-tile-chart-only')!, { key: 'Enter' });
    expect(fn).not.toHaveBeenCalled();
  });
});
