import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TICKER_DEBOUNCE_MS, TICKER_TIMEOUT_MS } from '../hooks/useTickerSearch';

/* GlobalSearch — the ⌘K palette (Ajay 2026-09-06), now with TICKERS in the same
   field (Ajay 2026-09-18: "can you make global search help find ickers also
   directly in the same field"). Menu + router navigate + the analytics /
   new-feature hooks are mocked so the palette renders standalone; the ranking
   itself is covered in lib/navSearch.test.ts and lib/tickerSearch.test.ts.

   /symbol-search is stubbed for the WHOLE suite — the mocked menu grants
   `sepa`, so without a stub every test that types ≥2 characters would fire a
   real request into localhost:8000 that lands after the test ended. The default
   stub is the EMPTY envelope, which is why every pre-existing assertion still
   holds once the debounce is advanced. src/test/setup.ts is untouched. */

const navigateMock = vi.fn();
const trackMock = vi.fn();
const markSeenMock = vi.fn();
let isNewRet = false;

const FULL_MENU = {
  primary:  [{ to: '/morning', label: 'Morning Brief', feature: 'morning' }, { to: '/chart-maps', label: '🗺️ Chart Maps', feature: 'chart-maps' }],
  scanners: [{ to: '/sepa', label: 'SEPA', feature: 'sepa' }],
  misc:     [{ to: '/alerts', label: '🔔 Alerts', feature: 'alerts' }, { to: '/supply-demand', label: 'Supply / Demand', feature: 'supply-demand' }, { to: '/signal-lab', label: '⚡ Signal Lab', feature: 'signal-lab' }],
  profile:  [{ to: '/notifications', label: 'Notifications', feature: 'notifications' }],
  admin:    [] as any[],
  is_owner: true,
  is_admin: true,
};
/** The same menu with SEPA taken away — a friend without the feature. */
const NO_SEPA_MENU = { ...FULL_MENU, scanners: [] as any[] };
let menuRet: any = FULL_MENU;

vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigateMock };
});
vi.mock('../hooks/useMyMenu', () => ({
  useMyMenu: () => ({ loaded: true, menu: menuRet }),
}));
vi.mock('../hooks/useNewFeatures', () => ({
  useNewFeatures: () => ({ isNew: () => isNewRet, markSeen: markSeenMock, isNewRoute: () => false, unseen: [] }),
}));
vi.mock('../lib/usageTracker', () => ({ trackFeature: (k: string) => trackMock(k) }));

import { GlobalSearch } from './GlobalSearch';

/* ── the live /symbol-search bodies, captured 2026-09-18 ───────────────────
   rtk proxy curl -s -H "X-User-Email: …" "http://127.0.0.1:8000/symbol-search?q=<q>" */
const EMPTY = { q: '', results: [], cached: true };
const PAYLOAD = {
  docn: { q: 'DOCN', cached: true, results: [{ symbol: 'DOCN', display_symbol: 'DOCN', name: 'DIGITALOCEAN HOLDINGS INC', type: 'Common Stock' }] },
  amd:  { q: 'amd',  cached: true, results: [
    { symbol: 'AMD', display_symbol: 'AMD', name: 'ADVANCED MICRO DEVICES', type: 'Common Stock' },
    { symbol: 'CPT', display_symbol: 'CPT', name: 'Camden Property Trust',  type: 'Common Stock' },
  ] },
  maps: { q: 'maps', cached: true, results: [{ symbol: 'MAPS', display_symbol: 'MAPS', name: 'WM TECHNOLOGY INC', type: 'Common Stock' }] },
  lab:  { q: 'lab',  cached: true, results: [{ symbol: 'LAB', display_symbol: 'LAB', name: 'STANDARD BIOTOOLS INC', type: 'Common Stock' }] },
};

let fetchMock: ReturnType<typeof vi.fn>;
const serve = (body: unknown) => { fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => body }); };

beforeEach(() => {
  isNewRet = false;
  menuRet = FULL_MENU;
  vi.useFakeTimers();
  fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => EMPTY });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

const subgroupOf = (f?: string) => ({ alerts: 'Signals', 'supply-demand': 'Screeners' }[f ?? ''] ?? 'More');
const renderIt = (props: { compact?: boolean } = {}) =>
  render(<MemoryRouter initialEntries={['/morning']}><GlobalSearch subgroupOf={subgroupOf} {...props} /></MemoryRouter>);

const dialog = () => screen.queryByRole('dialog', { name: 'Search pages and tickers' });
const input = () => screen.getByPlaceholderText('Search pages or a ticker… (e.g. notification, DOCN)') as HTMLInputElement;
const optionLabels = () => screen.getAllByRole('option').map((o) => o.querySelector('.cm-search__label')?.textContent);
/** Let the debounce fire and the stubbed response settle. */
const settle = async (ms = TICKER_DEBOUNCE_MS) => { await act(async () => { vi.advanceTimersByTime(ms); }); };
const openAndType = async (q: string, body?: unknown) => {
  if (body !== undefined) serve(body);
  renderIt();
  fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
  fireEvent.change(input(), { target: { value: q } });
};

describe('GlobalSearch — trigger', () => {
  it('desktop pill reads "Search" with the shortcut hint and opens on click', () => {
    renderIt();
    const btn = screen.getByRole('button', { name: 'Search pages and tickers' });
    expect(btn.textContent).toContain('Search');
    expect(btn.querySelector('kbd')?.textContent).toMatch(/⌘K|Ctrl K/);
    expect(dialog()).toBeNull();
    fireEvent.click(btn);
    expect(dialog()).not.toBeNull();
    expect(document.activeElement).toBe(input());
  });

  it('compact trigger is icon-only with aria-label "Search"', () => {
    renderIt({ compact: true });
    const btn = screen.getByRole('button', { name: 'Search' });
    expect(btn.textContent).not.toContain('Search');
    expect(btn.querySelector('kbd')).toBeNull();
    expect(btn.getAttribute('title')).toContain('Search pages and tickers');
    fireEvent.click(btn);
    expect(dialog()).not.toBeNull();
  });

  it('wears the ✨ dot while the feature is unseen and marks it seen on first open', () => {
    isNewRet = true;
    renderIt();
    expect(document.querySelector('.nav-new-dot')).not.toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Search pages and tickers' }));
    expect(markSeenMock).toHaveBeenCalledWith('global-search');
    expect(markSeenMock).toHaveBeenCalledWith('global-search-tickers');
  });
});

describe('GlobalSearch — shortcuts', () => {
  it('opens on Ctrl+K and toggles closed on a second Ctrl+K', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    expect(dialog()).not.toBeNull();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    expect(dialog()).toBeNull();
  });

  it('opens on ⌘K (meta) too', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'K', metaKey: true });
    expect(dialog()).not.toBeNull();
  });

  it('opens on "/" when focus is not in a text field, and NOT when it is', () => {
    renderIt();
    const field = document.createElement('textarea');
    document.body.appendChild(field);
    fireEvent.keyDown(field, { key: '/' });
    expect(dialog()).toBeNull();
    field.remove();
    fireEvent.keyDown(document.body, { key: '/' });
    expect(dialog()).not.toBeNull();
  });

  it('a plain "k" without a modifier does nothing', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k' });
    expect(dialog()).toBeNull();
  });
});

describe('GlobalSearch — palette', () => {
  it('blank query lists the menu in order with group chips', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    const opts = screen.getAllByRole('option');
    expect(opts).toHaveLength(8);                       // capped at the result limit
    expect(opts[0]).toHaveTextContent('Morning Brief');
    expect(opts[0]).toHaveTextContent('Primary');
    expect(opts[1]).toHaveTextContent('Chart Maps');    // menu order, tabs follow their parent
    expect(opts[2]).toHaveTextContent('Chart Maps ▸ Demand zones');
    fireEvent.change(input(), { target: { value: 'alerts' } });
    const alerts = screen.getAllByRole('option').find((o) => o.textContent?.includes('Alerts'))!;
    expect(alerts).toHaveTextContent('Tools ▸ Signals');
  });

  it('typing filters — "notification" shows Notifications first and Alerts too', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'notification' } });
    const labels = optionLabels();
    expect(labels[0]).toBe('Notifications');
    expect(labels).toContain('🔔 Alerts');
    expect(labels).not.toContain('Morning Brief');
  });

  it('ArrowDown + Enter navigates to the SECOND result and tracks the pick', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'notification' } });
    const labels = optionLabels();
    expect(labels.length).toBeGreaterThan(1);
    fireEvent.keyDown(input(), { key: 'ArrowDown' });
    expect(screen.getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true');
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).toHaveBeenCalledTimes(1);
    expect(navigateMock).toHaveBeenCalledWith('/alerts');
    expect(trackMock).toHaveBeenCalledWith('global-search');
    expect(dialog()).toBeNull();
  });

  it('ArrowUp from the top wraps to the last result', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'notification' } });
    const n = screen.getAllByRole('option').length;
    fireEvent.keyDown(input(), { key: 'ArrowUp' });
    expect(screen.getAllByRole('option')[n - 1]).toHaveAttribute('aria-selected', 'true');
  });

  it('Enter on the first result navigates there; a click on a row does the same', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'sepa' } });
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).toHaveBeenLastCalledWith('/sepa');
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'in demand' } });
    fireEvent.click(screen.getByText('Chart Maps ▸ Demand zones'));
    expect(navigateMock).toHaveBeenLastCalledWith('/chart-maps?tab=zones');
  });

  it('Esc closes; backdrop click closes; the panel itself does not', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.keyDown(input(), { key: 'Escape' });
    expect(dialog()).toBeNull();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.mouseDown(dialog()!);
    expect(dialog()).not.toBeNull();
    fireEvent.mouseDown(screen.getByTestId('global-search-backdrop'));
    expect(dialog()).toBeNull();
  });

  it('shows the "No matches" state and Enter then navigates nowhere', async () => {
    await openAndType('zzqqxx');
    await settle();                                     // the lookup must have answered
    expect(screen.queryAllByRole('option')).toHaveLength(0);
    expect(screen.getByRole('status')).toHaveTextContent('No matches for “zzqqxx”');
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).not.toHaveBeenCalled();
    expect(trackMock).not.toHaveBeenCalled();
  });

  it('reopening starts from a blank query and the first row', () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    fireEvent.change(input(), { target: { value: 'alerts' } });
    fireEvent.keyDown(input(), { key: 'Escape' });
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    expect(input().value).toBe('');
    expect(screen.getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'true');
  });
});

/* ── tickers in the same field (Ajay 2026-09-18) ─────────────────────────── */

describe('GlobalSearch — the ask: a ticker in the same field', () => {
  it('"docn" — a query with ZERO page matches renders a list, not "No matches"', async () => {
    await openAndType('docn', PAYLOAD.docn);
    await settle();

    const opts = screen.getAllByRole('option');
    expect(opts).toHaveLength(1);
    expect(opts.filter((o) => o.className.includes('cm-search__item--ticker'))).toHaveLength(1);
    expect(opts[0]).toHaveTextContent('DOCN');
    expect(opts[0]).toHaveTextContent('DIGITALOCEAN HOLDINGS INC');
    expect(opts[0]).toHaveTextContent('Ticker');
    expect(screen.queryByText(/No matches/)).toBeNull();

    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).toHaveBeenCalledWith('/sepa/DOCN');
    expect(trackMock).toHaveBeenCalledWith('global-search');
  });

  it('a pure-ticker query still sets aria-activedescendant on the input', async () => {
    await openAndType('docn', PAYLOAD.docn);
    await settle();
    const id = input().getAttribute('aria-activedescendant');
    expect(id).toBe('cm-search-opt-0');
    expect(document.getElementById(id!)).toHaveAttribute('role', 'option');
  });

  it('a click on the ticker row opens it too', async () => {
    await openAndType('docn', PAYLOAD.docn);
    await settle();
    fireEvent.click(screen.getByText('DIGITALOCEAN HOLDINGS INC'));
    expect(navigateMock).toHaveBeenLastCalledWith('/sepa/DOCN');
  });

  it('a blank query lists exactly 8 pages and fires ZERO lookups (negative)', async () => {
    renderIt();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    await settle(TICKER_DEBOUNCE_MS + TICKER_TIMEOUT_MS);
    expect(screen.getAllByRole('option')).toHaveLength(8);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('a one-character query fires zero lookups (negative)', async () => {
    await openAndType('d');
    await settle(TICKER_DEBOUNCE_MS + TICKER_TIMEOUT_MS);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('GlobalSearch — the pin never hijacks a page he named', () => {
  it('"maps" opens 🗺️ Chart Maps, never /sepa/MAPS (negative)', async () => {
    await openAndType('maps', PAYLOAD.maps);
    await settle();
    const opts = screen.getAllByRole('option');
    expect(opts[0]).toHaveTextContent('Chart Maps');
    expect(opts[0].className).not.toContain('--ticker');
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).toHaveBeenLastCalledWith('/chart-maps');
    expect(navigateMock).not.toHaveBeenCalledWith('/sepa/MAPS');
  });

  it('"lab" opens ⚡ Signal Lab, never /sepa/LAB (negative)', async () => {
    await openAndType('lab', PAYLOAD.lab);
    await settle();
    expect(screen.getAllByRole('option')[0]).toHaveTextContent('Signal Lab');
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).toHaveBeenLastCalledWith('/signal-lab');
    expect(navigateMock).not.toHaveBeenCalledWith('/sepa/LAB');
  });

  it('the blocked symbol is still reachable — it sits in the Tickers section below the pages', async () => {
    await openAndType('maps', PAYLOAD.maps);
    await settle();
    const opts = screen.getAllByRole('option');
    expect(opts[opts.length - 1]).toHaveTextContent('WM TECHNOLOGY INC');
    expect(screen.getByText('Pages')).toBeInTheDocument();
    expect(screen.getByText('Tickers')).toBeInTheDocument();
    // section headers are NOT options
    expect(screen.getByText('Pages').getAttribute('role')).toBe('presentation');
  });
});

describe('GlobalSearch — a late ticker row never moves a highlight HE placed', () => {
  /* THE DEFECT THIS REPLACES (found 2026-09-18, before ship). These two cases
   * used to assert the OPPOSITE: that the pin lands at row 0 and Enter still
   * opens a page. Measured against his real menu that hit 9 of his 18 symbols —
   * he typed AMD, saw `📈 AMD` highlighted-looking on top, pressed Enter and
   * got Supply/Demand; LLY went to /volleyball. The seed-once rule was too
   * broad: what must be protected is a highlight HE moved, not the first one
   * we happened to place. */
  it('"amd" pins the ticker at row 0 and Enter opens the TICKER', async () => {
    await openAndType('amd', PAYLOAD.amd);
    const before = screen.getAllByRole('option');
    expect(before.length).toBeGreaterThan(0);
    expect(before[0]).toHaveAttribute('aria-selected', 'true');   // a page, for now

    await settle();                                     // the pin lands ~300 ms later

    const after = screen.getAllByRole('option');
    expect(after[0]).toHaveTextContent('AMD');
    expect(after[0].className).toContain('--ticker');
    // the highlight FOLLOWS the pin, because he never moved it himself
    expect(after[0]).toHaveAttribute('aria-selected', 'true');
    expect(after.filter((o) => o.getAttribute('aria-selected') === 'true')).toHaveLength(1);

    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).toHaveBeenLastCalledWith('/sepa/AMD');
  });

  it('NEGATIVE: once HE has moved the highlight, a late pin must not steal it', async () => {
    await openAndType('amd', PAYLOAD.amd);
    fireEvent.keyDown(input(), { key: 'ArrowDown' });   // his choice, before the pin exists
    const chosen = screen.getAllByRole('option')
      .find((o) => o.getAttribute('aria-selected') === 'true')!
      .querySelector('.cm-search__label')?.textContent;

    await settle();                                     // the pin arrives above it

    const after = screen.getAllByRole('option');
    expect(after[0]).toHaveTextContent('AMD');
    expect(after[0]).toHaveAttribute('aria-selected', 'false');
    const selected = after.find((o) => o.getAttribute('aria-selected') === 'true')!;
    expect(selected.querySelector('.cm-search__label')?.textContent).toBe(chosen);

    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).not.toHaveBeenCalledWith('/sepa/AMD');
  });

  it('NEGATIVE: a new query clears that — arrowing on one search does not poison the next', async () => {
    await openAndType('amd', PAYLOAD.amd);
    fireEvent.keyDown(input(), { key: 'ArrowDown' });
    await settle();
    // he retypes; the highlight is ours again, so the new pin takes it
    serve(PAYLOAD.docn);
    fireEvent.change(input(), { target: { value: 'docn' } });
    await settle();
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).toHaveBeenLastCalledWith('/sepa/DOCN');
  });

  it('the highlight is SEEDED when the rows go from empty to a ticker row', async () => {
    await openAndType('docn', PAYLOAD.docn);
    await settle();
    fireEvent.keyDown(input(), { key: 'Enter' });        // never touched an arrow key
    expect(navigateMock).toHaveBeenCalledWith('/sepa/DOCN');
  });

  it('hovering a row moves the highlight to THAT row', async () => {
    await openAndType('maps', PAYLOAD.maps);
    await settle();
    const opts = screen.getAllByRole('option');
    fireEvent.mouseEnter(opts[opts.length - 1]);
    expect(opts[opts.length - 1]).toHaveAttribute('aria-selected', 'true');
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).toHaveBeenLastCalledWith('/sepa/MAPS');
  });
});

describe('GlobalSearch — what it says while the lookup is slow or broken', () => {
  it('says "Looking up tickers…", never "No matches", while in flight', async () => {
    fetchMock.mockImplementation(() => new Promise(() => {}));   // never settles
    await openAndType('docn');
    expect(screen.getByRole('status')).toHaveTextContent('Looking up tickers…');
    expect(screen.queryByText(/No matches/)).toBeNull();
  });

  it('a failed lookup with no page matches says so instead of "No matches"', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });
    await openAndType('docn');
    await settle();
    expect(screen.getByRole('status')).toHaveTextContent('No page matches for “docn” — ticker lookup unavailable');
  });

  it('a failed lookup WITH page matches renders the pages plus one muted note', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    await openAndType('alerts');
    await settle();
    expect(screen.getAllByRole('option').length).toBeGreaterThan(0);
    expect(screen.getByTestId('ticker-note')).toHaveTextContent('Ticker lookup unavailable — pages only');
    expect(screen.getByTestId('ticker-note')).not.toHaveAttribute('role', 'status');
  });

  it('a lookup that never answers times out and says so (negative)', async () => {
    fetchMock.mockImplementation((_u: string, init: any) => new Promise((_res, rej) => {
      init?.signal?.addEventListener('abort', () => { const e = new Error('x'); e.name = 'AbortError'; rej(e); });
    }));
    await openAndType('docn');
    await settle(TICKER_DEBOUNCE_MS + TICKER_TIMEOUT_MS);
    expect(screen.getByRole('status')).toHaveTextContent('ticker lookup unavailable');
  });

  it.each([
    ['a 500',            () => fetchMock.mockResolvedValue({ ok: false, status: 500, json: async () => ({}) })],
    ['a rejection',      () => fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))],
    ['an empty envelope',() => serve({ q: 'alerts', results: [], cached: true })],
    ['a malformed body', () => serve({ results: 'nope' })],
    ['a junk body',      () => serve(['not', 'rows', 3])],
  ])('FAILS OPEN on %s — the pages are still there and Enter still opens one', async (_label, arrange) => {
    arrange();
    await openAndType('alerts');
    await settle();
    expect(screen.getAllByRole('option').length).toBeGreaterThan(0);
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(navigateMock).toHaveBeenCalledTimes(1);
    expect(String(navigateMock.mock.calls[0][0])).not.toContain('/sepa/');
  });

  it('exactly ONE role="status" node in the empty, loading and error states', async () => {
    fetchMock.mockImplementation(() => new Promise(() => {}));
    await openAndType('docn');
    expect(screen.getAllByRole('status')).toHaveLength(1);       // loading
    fireEvent.change(input(), { target: { value: '' } });
    expect(screen.queryAllByRole('status')).toHaveLength(0);     // blank query lists the menu

    fetchMock.mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });
    fireEvent.change(input(), { target: { value: 'docn' } });
    await settle();
    expect(screen.getAllByRole('status')).toHaveLength(1);       // error
  });

  it('never blocks typing — page rows for the NEW query are there before the lookup answers', async () => {
    fetchMock.mockImplementation(() => new Promise(() => {}));
    await openAndType('docn');
    fireEvent.change(input(), { target: { value: 'notification' } });
    expect(optionLabels()[0]).toBe('Notifications');              // synchronous, nothing advanced
  });
});

describe('GlobalSearch — the sepa menu gate', () => {
  it('a user without SEPA gets zero lookups and zero ticker rows (negative)', async () => {
    menuRet = NO_SEPA_MENU;
    await openAndType('docn', PAYLOAD.docn);
    await settle(TICKER_DEBOUNCE_MS + TICKER_TIMEOUT_MS);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.queryAllByRole('option')).toHaveLength(0);
    expect(screen.getByRole('status')).toHaveTextContent('No matches for “docn”');
  });
});

describe('GlobalSearch — the rows survive a trailing space', () => {
  it('the pin stays at row 0 and no extra lookup fires', async () => {
    await openAndType('amd', PAYLOAD.amd);
    await settle();
    expect(screen.getAllByRole('option')[0]).toHaveTextContent('AMD');
    const calls = fetchMock.mock.calls.length;

    fireEvent.change(input(), { target: { value: 'amd ' } });
    await settle(TICKER_DEBOUNCE_MS + TICKER_TIMEOUT_MS);
    expect(screen.getAllByRole('option')[0]).toHaveTextContent('AMD');
    expect(fetchMock.mock.calls.length).toBe(calls);
  });
});
