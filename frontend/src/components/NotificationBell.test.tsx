/* NotificationBell — the 🔔 dropdown, with per-ticker chips.
 *
 * Ajay 2026-09-20: the bell showed a digest's title and body and linked no
 * name at all. Each row now carries a chip per name, every chip a real
 * <a href>. The row stopped being one big <Link> for the same reason the
 * /notifications card did (an <a> inside an <a> is invalid HTML) — the title
 * carries the link, and clicking it still closes the dropdown.
 *
 * Negatives pinned: 3 / 1 / 0 anchors for digest / single / nothing-to-link;
 * no nested anchors; a row with no url renders no title link; the chips take
 * their `from=` from the PAGE the bell is on, not from a hard-coded key.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NotificationBell } from './NotificationBell';

const TS = Math.floor(Date.parse('2026-09-20T13:05:00Z') / 1000);

const ROWS = [
  { _id: 'd1', ts: TS, ts_iso: '2026-09-20T13:05:00+00:00', kind: 'growth_demand_alert',
    title: '🚀 3 growth names at demand', body: 'AAA, BBB, CCC · pushed 09:05 ET',
    ticker: null, tickers: ['AAA', 'BBB', 'CCC'], url: '/chart-maps?tab=growth', source: 'push' as const },
  { _id: 's1', ts: TS - 60, ts_iso: '2026-09-20T13:04:00+00:00', kind: 'demand_alert',
    title: '🧲 NVDA in demand', body: 'Arrived inside the band.',
    ticker: 'NVDA', tickers: null, url: '/sepa/NVDA?tab=supply', source: 'push' as const },
  { _id: 'n1', ts: TS - 120, ts_iso: '2026-09-20T13:03:00+00:00', kind: 'todo_reminder',
    title: '📝 Desk todo', body: 'Nothing to link here.',
    ticker: null, tickers: null, url: null, source: 'push' as const },
];

function stubFetch(rows: unknown = ROWS) {
  const fn = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ rows }) } as Response));
  vi.stubGlobal('fetch', fn);
  return fn;
}

const draw = (entry = '/supply-demand') =>
  render(<MemoryRouter initialEntries={[entry]}><NotificationBell /></MemoryRouter>);

/** Open the dropdown (the bell renders rows only when open). */
async function openBell() {
  await waitFor(() => expect(screen.getByRole('button', { name: /Notifications/ })).toBeInTheDocument());
  fireEvent.click(screen.getByRole('button', { name: /Notifications/ }));
  await waitFor(() => expect(screen.getAllByTestId('bell-row').length).toBeGreaterThan(0));
}

beforeEach(() => { try { window.localStorage.clear(); } catch { /* */ } });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('NotificationBell — per-ticker chips', () => {
  it('a 3-name digest gives 3 chips, a single gives 1, a row with neither gives none', async () => {
    stubFetch();
    const { container } = draw();
    await openBell();
    const rows = screen.getAllByTestId('bell-row');
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getAllByRole('link', { name: /^(AAA|BBB|CCC)$/ })).toHaveLength(3);
    expect(within(rows[1]).getAllByRole('link', { name: 'NVDA' })).toHaveLength(1);
    // NEGATIVE: no url and no ticker → the row holds no anchor at all.
    expect(rows[2].querySelectorAll('a')).toHaveLength(0);
    // NEGATIVE: never an anchor inside an anchor (the row used to be a Link).
    expect(container.querySelectorAll('a a')).toHaveLength(0);
  });

  it('the chips take their source from the PAGE the bell is rendered on', async () => {
    stubFetch();
    draw('/supply-demand');
    await openBell();
    const a = within(screen.getByTestId('bell-tk-AAA')).getByRole('link');
    expect(a.getAttribute('href')).toMatch(/^\/sepa\/AAA\?/);
    expect(a.getAttribute('href')).toMatch(/tab=supply/);
    expect(a.getAttribute('href')).toMatch(/from=supply-demand/);
  });

  it('on /notifications the same chips say from=notifications', async () => {
    stubFetch();
    draw('/notifications');
    await openBell();
    expect(within(screen.getByTestId('bell-tk-BBB')).getByRole('link').getAttribute('href'))
      .toMatch(/from=notifications/);
  });

  it('the title is the link and closes the dropdown on click', async () => {
    stubFetch();
    draw();
    await openBell();
    const title = screen.getByRole('link', { name: /3 growth names at demand/ });
    expect(title.getAttribute('href')).toBe('/chart-maps?tab=growth');
    fireEvent.click(title);
    await waitFor(() => expect(screen.queryAllByTestId('bell-row')).toHaveLength(0));
  });

  it('NEGATIVE: a row with url null renders its title as text, never a dead link', async () => {
    stubFetch();
    draw();
    await openBell();
    expect(screen.getByText('📝 Desk todo')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '📝 Desk todo' })).not.toBeInTheDocument();
  });

  it('NEGATIVE: an older row with no `tickers` key still links its single ticker', async () => {
    stubFetch([{ ...ROWS[1], _id: 'l1', tickers: undefined }]);
    draw();
    await openBell();
    expect(within(screen.getByTestId('bell-tk-NVDA')).getByRole('link')).toBeInTheDocument();
  });
});

/* ── 2026-09-21: the served fold line ──────────────────────────────────────
 *
 * push/recent folds a run of identical adjacent rows into the newest one and
 * hands over a `repeat` block. The bell prints `line` and nothing else: no
 * arithmetic on `count`, no stamp of its own. **[C7]** the badge still counts
 * ROWS — a folded block is one unread — and that is pinned, not incidental.
 */
const FOLD_LINE = 'served: three more of these';

describe('NotificationBell — the fold line', () => {
  let restoreStorage: (() => void) | null = null;
  afterEach(() => { restoreStorage?.(); restoreStorage = null; });

  it('prints repeat.line verbatim under the row that carries it', async () => {
    stubFetch([{ ...ROWS[0], repeat: { line: FOLD_LINE } }, ROWS[1], ROWS[2]]);
    draw();
    await openBell();
    const rows = screen.getAllByTestId('bell-row');
    expect(within(rows[0]).getByTestId('bell-repeat').textContent).toBe(FOLD_LINE);
  });

  it('NEGATIVE: rows without a block (and with repeat: null) print no fold line, and nothing is derived from count', async () => {
    stubFetch([{ ...ROWS[0], repeat: { count: 4, line: FOLD_LINE } }, { ...ROWS[1], repeat: null }, ROWS[2]]);
    draw();
    await openBell();
    expect(screen.getAllByTestId('bell-repeat')).toHaveLength(1);
    const page = document.body.textContent ?? '';
    expect(page).not.toMatch(/more like this/);
    expect(page).not.toMatch(/3 more/);
    expect(page).not.toMatch(/4 /);
  });

  it('[C7] NEGATIVE: the badge counts ROWS, not fires — a folded block is one unread', async () => {
    // jsdom here has no localStorage (the component's own reads are try/catch'd),
    // so the "already seen" stamp is injected directly.
    const original = Object.getOwnPropertyDescriptor(window, 'localStorage');
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: { getItem: () => String(TS - 120), setItem: () => {}, clear: () => {} },
    });
    restoreStorage = () => {
      if (original) Object.defineProperty(window, 'localStorage', original);
      else delete (window as unknown as Record<string, unknown>).localStorage;
    };
    stubFetch([{ ...ROWS[0], repeat: { count: 4, line: FOLD_LINE } }, ROWS[1], ROWS[2]]);
    draw();
    // two rows are newer than lastSeen; one of them stands for four fires
    await waitFor(() => expect(screen.getByRole('button', { name: 'Notifications (2 new)' })).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /5 new/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /6 new/ })).not.toBeInTheDocument();
  });
});
