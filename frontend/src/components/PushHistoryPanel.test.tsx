/* PushHistoryPanel — the /notifications feed, with per-ticker chips.
 *
 * Ajay 2026-09-20: a digest push listed three names and linked none of them.
 * Now every name is its own real <a href>, and — because an <a> inside an <a>
 * is invalid HTML and the browser un-nests it — the CARD stopped being one big
 * <Link>: the title carries the link instead.
 *
 * Pinned with negatives: 3 / 1 / 0 anchors for a digest / a single / a row
 * with nothing to link; the title still routes to `row.url`; no nested
 * anchors anywhere; the chips carry `from=notifications` so the back button
 * comes back here and not to /sepa.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PushHistoryPanel } from './PushHistoryPanel';

const TS = Math.floor(Date.parse('2026-09-20T13:05:00Z') / 1000);

const ROWS = [
  { _id: 'd1', ts: TS, ts_iso: '2026-09-20T13:05:00+00:00', kind: 'growth_demand_alert',
    title: '🚀 3 growth names at demand', body: 'AAA, BBB, CCC · pushed 09:05 ET',
    ticker: null, tickers: ['AAA', 'BBB', 'CCC'], url: '/chart-maps?tab=growth',
    user_email: null, sent: 1, failed: 0, total: 1, source: 'push' as const },
  { _id: 's1', ts: TS - 60, ts_iso: '2026-09-20T13:04:00+00:00', kind: 'demand_alert',
    title: '🧲 NVDA in demand', body: 'Arrived inside the band.',
    ticker: 'NVDA', tickers: null, url: '/sepa/NVDA?tab=supply',
    user_email: null, sent: 2, failed: 0, total: 2, source: 'push' as const },
  { _id: 'n1', ts: TS - 120, ts_iso: '2026-09-20T13:03:00+00:00', kind: 'todo_reminder',
    title: '📝 Desk todo', body: 'Nothing to link here.',
    ticker: null, tickers: null, url: null,
    user_email: null, sent: 1, failed: 0, total: 1, source: 'push' as const },
];

function stubFetch(rows: unknown = ROWS) {
  const fn = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ rows }) } as Response));
  vi.stubGlobal('fetch', fn);
  return fn;
}

const draw = () => render(<MemoryRouter initialEntries={['/notifications']}><PushHistoryPanel /></MemoryRouter>);

beforeEach(() => { vi.useFakeTimers({ now: new Date(TS * 1000), toFake: ['Date'] }); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('PushHistoryPanel — per-ticker chips', () => {
  it('a 3-name digest gives 3 anchors, a single gives 1, a row with neither gives 0', async () => {
    stubFetch();
    const { container } = draw();
    await waitFor(() => expect(screen.getAllByTestId('ph-row')).toHaveLength(3));
    const rows = screen.getAllByTestId('ph-row');
    expect(within(rows[0]).getAllByRole('link', { name: /^(AAA|BBB|CCC)$/ })).toHaveLength(3);
    expect(within(rows[1]).getAllByRole('link', { name: 'NVDA' })).toHaveLength(1);
    // NEGATIVE: the todo row has no url and no ticker → no anchor at all.
    expect(rows[2].querySelectorAll('a')).toHaveLength(0);
    // NEGATIVE: never an anchor inside an anchor (the card used to be a Link).
    expect(container.querySelectorAll('a a')).toHaveLength(0);
  });

  it('every chip is /sepa/SYM with tab=supply and from=notifications', async () => {
    stubFetch();
    draw();
    await waitFor(() => expect(screen.getAllByTestId('ph-row')).toHaveLength(3));
    for (const t of ['AAA', 'BBB', 'CCC']) {
      const a = within(screen.getByTestId(`ph-tk-${t}`)).getByRole('link');
      expect(a.getAttribute('href')).toMatch(new RegExp(`^/sepa/${t}\\?`));
      expect(a.getAttribute('href')).toMatch(/tab=supply/);
      expect(a.getAttribute('href')).toMatch(/from=notifications/);
    }
  });

  it('the TITLE still routes to row.url — internal via the router, external in a new tab', async () => {
    stubFetch([
      ROWS[0],
      { ...ROWS[1], _id: 'x1', url: 'https://example.com/doc', title: '📄 External' },
    ]);
    draw();
    await waitFor(() => expect(screen.getAllByTestId('ph-row')).toHaveLength(2));
    const title = screen.getByRole('link', { name: '🚀 3 growth names at demand' });
    expect(title.getAttribute('href')).toBe('/chart-maps?tab=growth');
    const ext = screen.getByRole('link', { name: '📄 External' });
    expect(ext.getAttribute('href')).toBe('https://example.com/doc');
    expect(ext).toHaveAttribute('target', '_blank');
  });

  it('NEGATIVE: a row whose url is null renders its title as plain text, never a dead link', async () => {
    stubFetch();
    draw();
    await waitFor(() => expect(screen.getAllByTestId('ph-row')).toHaveLength(3));
    expect(screen.getByText('📝 Desk todo')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '📝 Desk todo' })).not.toBeInTheDocument();
  });

  it('NEGATIVE: an older row with no `tickers` key still links its single ticker', async () => {
    const legacy = [{ ...ROWS[1], _id: 'l1', tickers: undefined }];
    stubFetch(legacy);
    draw();
    await waitFor(() => expect(screen.getAllByTestId('ph-row')).toHaveLength(1));
    expect(within(screen.getByTestId('ph-tk-NVDA')).getByRole('link')).toBeInTheDocument();
  });

  it('NEGATIVE: the ticker is never printed twice — the raw text line is gone', async () => {
    stubFetch([ROWS[1]]);
    draw();
    await waitFor(() => expect(screen.getAllByTestId('ph-row')).toHaveLength(1));
    expect(screen.getAllByText('NVDA')).toHaveLength(1);
  });
});

/* ── 2026-09-21: the served fold line ──────────────────────────────────────
 *
 * Same contract as the bell and /alerts: print `repeat.line` verbatim, compose
 * nothing from `count`, format no stamp here.
 */
const FOLD_LINE = 'served: three more of these';

describe('PushHistoryPanel — the fold line', () => {
  it('prints repeat.line verbatim under the row that carries it', async () => {
    stubFetch([{ ...ROWS[0], repeat: { line: FOLD_LINE } }, ROWS[1], ROWS[2]]);
    draw();
    await waitFor(() => expect(screen.getAllByTestId('ph-row')).toHaveLength(3));
    const rows = screen.getAllByTestId('ph-row');
    expect(within(rows[0]).getByTestId('history-repeat').textContent).toBe(FOLD_LINE);
    // the delivery line still sits under it
    expect(within(rows[0]).getByText('delivered to 1/1 device')).toBeInTheDocument();
  });

  it('NEGATIVE: rows without a block (and with repeat: null) print no fold line, and nothing is derived from count', async () => {
    stubFetch([{ ...ROWS[0], repeat: { count: 4, line: FOLD_LINE } }, { ...ROWS[1], repeat: null }, ROWS[2]]);
    draw();
    await waitFor(() => expect(screen.getAllByTestId('ph-row')).toHaveLength(3));
    expect(screen.getAllByTestId('history-repeat')).toHaveLength(1);
    const page = document.body.textContent ?? '';
    expect(page).not.toMatch(/more like this/);
    expect(page).not.toMatch(/3 more/);
  });
});
