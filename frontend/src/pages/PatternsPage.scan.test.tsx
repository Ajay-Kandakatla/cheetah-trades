/* The two rescan buttons — Ajay 2026-09-10:
 *
 *   "The chart patterns are only looking at qualified sepa list I want them to
 *    run against all"
 *
 * Part of why that was true was here, not in the backend. The PRIMARY gold
 * button — the one he actually clicks — posted scope `qualifiers`: ~300 names,
 * and it does not refresh `latest.results`, which is what the confirmed/forming
 * board below it renders. So the heavy full-universe sweep sat behind the
 * secondary outline button and the board he was looking at never widened.
 *
 * What these pin: the primary button sweeps the UNIVERSE, it never posts
 * `qualifiers`, and both buttons say on their face which scope they run. A
 * silent swap back would look identical on screen and read as "the scan is
 * broken" rather than "the wrong scan ran".
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternsBoard } from './PatternsPage';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

let USER: { is_admin: boolean } | null = { is_admin: true };
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: USER }) }));

const LATEST = {
  ok: true, generated_at: 1789000000, symbols_scanned: 2650, n_found: 239,
  n_results: 239, n_dropped: 0, max_results: 2000,
  results: [
    { symbol: 'BKH', pattern: 'cup_with_handle', status: 'confirmed', confirmed_date: '2026-09-09',
      last_close: 72.82, neckline: 74.16, stop: 70.51, target: 78.24,
      lows: [{ price: 70.1, date: '2026-07-14' }], sepa: { is_candidate: true, rs_rank: 71, stage: 2 } },
  ],
  validation: {},
};
const QUALS = { ok: true, generated_at: 1789000000, n_symbols: 313, verdicts: [] };

/** Every POST the page fires, in order. */
const POSTS: { url: string; body: Record<string, unknown> }[] = [];

function stubFetch() {
  return vi.fn((url: string, init?: RequestInit) => {
    const u = String(url);
    const reply = (body: unknown) =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
    if (init?.method === 'POST') {
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      POSTS.push({ url: u, body });
      return reply({ running: true, scope: body.scope, done: 0, total: 0 });
    }
    if (u.includes('/patterns/scan/status')) return reply({ running: false, done: 0, total: 0 });
    if (u.includes('/patterns/latest')) return reply(LATEST);
    if (u.includes('/patterns/qualifiers')) return reply(QUALS);
    if (u.includes('/patterns/accuracy')) return reply({ ok: true, patterns: {}, candles: {}, pending: 0 });
    return reply({ ok: true });
  });
}

const draw = () => render(<MemoryRouter><PatternsBoard /></MemoryRouter>);

/** The two scan buttons, in DOM order. They are the only ones whose tooltip
 *  names a scope, which is itself part of the contract below. */
const scanButtons = () =>
  screen.getAllByRole('button')
    .filter((b) => /universe|qualifier/i.test(b.getAttribute('title') || ''));

beforeEach(() => { USER = { is_admin: true }; POSTS.length = 0; vi.stubGlobal('fetch', stubFetch()); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('the primary rescan button sweeps the whole universe', () => {
  it('posts scope "universe"', async () => {
    draw();
    await screen.findByText('BKH');
    const [primary] = scanButtons();
    fireEvent.click(primary);
    await waitFor(() => expect(POSTS.length).toBe(1));
    expect(POSTS[0].url).toContain('/patterns/scan');
    expect(POSTS[0].body.scope).toBe('universe');
  });

  it('never posts scope "qualifiers" (NEGATIVE)', async () => {
    // The exact regression: the gold button used to run the ~300-name verdict
    // scan, which also does not refresh the board it sits above.
    draw();
    await screen.findByText('BKH');
    fireEvent.click(scanButtons()[0]);
    await waitFor(() => expect(POSTS.length).toBe(1));
    expect(POSTS[0].body.scope).not.toBe('qualifiers');
  });

  it('still refreshes today’s bar so a breakout confirming now is caught', async () => {
    draw();
    await screen.findByText('BKH');
    fireEvent.click(scanButtons()[0]);
    await waitFor(() => expect(POSTS.length).toBe(1));
    expect(POSTS[0].body.refresh_today).toBe(true);
  });

  it('is the visually primary button, not the demoted one', async () => {
    // Which button carries the weight is the whole defect — he clicks the
    // filled gold one, and that one used to be the ~300-name verdict scan.
    draw();
    await screen.findByText('BKH');
    const [primary, secondary] = scanButtons();
    expect(primary.style.fontWeight).toBe('700');
    expect(secondary.style.fontWeight).toBe('600');
    expect(primary.style.background).toContain('--gold');       // filled
    expect(secondary.style.background).toBe('transparent');     // outline
  });
});

describe('the secondary button still runs the qualifier verdict scan', () => {
  it('posts scope "qualifiers"', async () => {
    draw();
    await screen.findByText('BKH');
    fireEvent.click(scanButtons()[1]);
    await waitFor(() => expect(POSTS.length).toBe(1));
    expect(POSTS[0].body.scope).toBe('qualifiers');
  });

  it('the two buttons run two DIFFERENT scopes (NEGATIVE)', async () => {
    // Both pointing at one scope would leave a product unreachable — the
    // verdict scan is what fills the 📐 chips, the sweep is what fills the
    // board. Neither may quietly become the other. Two renders, because a
    // running scan correctly disables both buttons.
    const first = draw();
    await screen.findByText('BKH');
    fireEvent.click(scanButtons()[0]);
    await waitFor(() => expect(POSTS.length).toBe(1));
    first.unmount();

    draw();
    await screen.findByText('BKH');
    fireEvent.click(scanButtons()[1]);
    await waitFor(() => expect(POSTS.length).toBe(2));
    expect(new Set(POSTS.map((p) => p.body.scope))).toEqual(new Set(['universe', 'qualifiers']));
  });

  it('a scan already running disables both buttons (NEGATIVE)', async () => {
    // Backend start_scan is single-flight; a second click would look like it
    // did something and silently return "already running".
    draw();
    await screen.findByText('BKH');
    fireEvent.click(scanButtons()[0]);
    await waitFor(() => expect(POSTS.length).toBe(1));
    await waitFor(() => expect(scanButtons()[0]).toBeDisabled());
    expect(scanButtons()[1]).toBeDisabled();
    fireEvent.click(scanButtons()[1]);
    expect(POSTS.length).toBe(1);
  });
});

describe('both buttons name their scope', () => {
  it('there are exactly two, and each label says what it covers', async () => {
    draw();
    await screen.findByText('BKH');
    const [primary, secondary] = scanButtons();
    expect(scanButtons().length).toBe(2);
    expect(primary.textContent).toMatch(/all names|full universe/i);
    expect(secondary.textContent).toMatch(/qualifier/i);
  });

  it('each tooltip names the scope AND how many names it is', async () => {
    draw();
    await screen.findByText('BKH');
    const [primary, secondary] = scanButtons();
    expect(primary.getAttribute('title')).toMatch(/full universe/i);
    expect(primary.getAttribute('title')).toMatch(/2,650/);      // last run's symbols_scanned
    expect(secondary.getAttribute('title')).toMatch(/qualifier/i);
    expect(secondary.getAttribute('title')).toMatch(/313/);      // quals.n_symbols
  });

  it('the secondary is honest that it does NOT refresh the board below', async () => {
    draw();
    await screen.findByText('BKH');
    expect(scanButtons()[1].getAttribute('title')).toMatch(/does NOT refresh/i);
  });

  it('the primary does not let a wider board imply more phone alerts', async () => {
    // The consequence he must not be surprised by: widening the SCAN widens
    // the BOARD. The phone stays gated to $1B+ names sitting at a demand zone
    // (zone_store.MIN_CAP_USD + patterns/pattern_alerts.py). Never loosened to
    // make the wider board "work".
    draw();
    await screen.findByText('BKH');
    const title = scanButtons()[0].getAttribute('title') || '';
    expect(title).toMatch(/demand zone/i);
    expect(title).toMatch(/\$1B/i);
  });
});

describe('who can fire a 2,650-name sweep', () => {
  it('a non-admin sees neither button (NEGATIVE)', async () => {
    USER = null;
    draw();
    await screen.findByText('BKH');
    expect(scanButtons().length).toBe(0);
  });
});
