/* 🔥 Hottest — multi-column sort (Ajay 2026-09-28: "can you help me with
 * multi column sort").
 *
 * WHAT IS PINNED HERE
 *  - a plain click is today's click, byte for byte, and clears tie-breaks;
 *  - shift / ⌘ / ctrl adds a tie-break, sent as ONE extra `then_by` param;
 *  - every mark (1▼ 2▲, aria-sort, "ranked on … then …") draws the SERVED
 *    plan once the read has landed, the request while it is in flight;
 *  - the rows print in the order served — no client sort anywhere.
 * The stub ECHOES the requested plan unless a test says otherwise. */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HottestSectors } from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const name = (symbol: string, over: Record<string, unknown> = {}) => ({
  symbol, name: `${symbol} Inc.`, industry: 'Semiconductors',
  rel_1d: 0.4, rel_5d: 3.1, rel_21d: 8.2, d1_source: 'close',
  sales_yoy: 12, sales_tier: 'steady', q_eps_yoy: 30, net_margin: 11,
  eq_score: 90, eq_tier: 'steady', next_earnings: '2026-10-28', ...over,
});
const sector = (group: string, names: ReturnType<typeof name>[]) => ({
  group, n_full: 40, sampled_of: 40, sampled_used: 40, basis: 'rotation grid sample',
  n_measured: 40, rel_1d: 0.1, rel_5d: 2.0, rel_21d: -1.0, d1_source: 'close',
  sales_yoy: 10, sales_tier: 'steady', q_eps_yoy: 12, net_margin: 9, eq_score: 55,
  fund_basis: 'median of full membership',
  names, names_total: names.length, industries: [],
});

const IDLE_PRE = {
  basis: 'premarket', live: false, ran: false, show: false, open: true,
  session: 'premarket', pre_window: '4:00-9:30 ET', reason: 'not requested',
};
const NO_BENCH_PRE = { ...IDLE_PRE, ran: true,
  reason: 'no pre-market print for RSP yet, so nothing can be measured against it' };

type Plan = { sort: string; dir: string; thenBy: { key: string; dir: string }[]; basis: string };
function planOf(url: string): Plan {
  const u = new URL(url, 'http://x');
  const thenBy = (u.searchParams.get('then_by') || '').split(',').filter(Boolean)
    .map((t) => { const [key, dir] = t.split(':'); return { key, dir }; });
  return { sort: u.searchParams.get('sort') || '', dir: u.searchParams.get('dir') || '',
           thenBy, basis: u.searchParams.get('basis') || 'close' };
}

/** The echo answer: the server applied exactly what was asked, except that a
 *  pre_1d request is DEMOTED to 5 days (nothing printed yet) — the server's
 *  own rule. `tweak` lets a test serve something else. */
function answer(url: string, tweak?: (p: Plan, body: Record<string, unknown>) => void) {
  const p = planOf(url);
  const demoted = p.sort === 'pre_1d';
  const body: Record<string, unknown> = {
    as_of: '2026-09-25', benchmark: 'RSP',
    sorted_by: demoted ? 'rel_5d' : p.sort, sorted_dir: p.dir,
    sorted_then_by: demoted ? [] : p.thenBy, sort_max_keys: 3,
    legs: ['rel_1d', 'rel_5d', 'rel_21d'],
    d1: { basis: 'close', live: false, close_as_of: '2026-09-25', in_session: false,
          session_window: '9:30-16:00 ET' },
    pre: p.basis === 'premarket' ? NO_BENCH_PRE : IDLE_PRE,
    sectors: [sector('Technology', [name('NVDA')]), sector('Energy', [name('XOM')])],
  };
  tweak?.(p, body);
  return body;
}

function stub(tweak?: (p: Plan, body: Record<string, unknown>) => void) {
  const hottest: string[] = [];
  const held: Array<() => void> = [];
  const state = { hold: false };
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/supply-demand/bounce-room')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ rows: [] }) } as Response);
    }
    hottest.push(String(url));
    const res = { ok: true, json: () => Promise.resolve(answer(String(url), tweak)) } as Response;
    if (!state.hold) return Promise.resolve(res);
    return new Promise<Response>((r) => { held.push(() => r(res)); });
  }));
  return { hottest, held, state, last: () => hottest[hottest.length - 1] };
}

const view = () => render(
  <MemoryRouter>
    <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
      <HottestSectors />
    </EnterableFilterProvider>
  </MemoryRouter>);

const head = (re: RegExp) => screen.getByRole('button', { name: re });
const th = (re: RegExp) => head(re).closest('th') as HTMLElement;

beforeEach(() => { _resetSignalWatchlist(); _resetBounceRoomCache(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('additive clicks send then_by', () => {
  for (const mod of ['shiftKey', 'metaKey', 'ctrlKey'] as const) {
    it(`${mod}-click on Q EPS adds a tie-break after 5 days`, async () => {
      const s = stub();
      view();
      await screen.findByText(/Technology/);
      fireEvent.click(head(/^Q EPS/), { [mod]: true });
      await waitFor(() => expect(s.last())
        .toContain('sort=rel_5d&dir=desc&then_by=q_eps_yoy%3Adesc'));
    });
  }

  it('the served plan numbers the headers; aria-sort sits on the primary only', async () => {
    const s = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(head(/^Q EPS/), { shiftKey: true });
    await waitFor(() => expect(head(/^Q EPS/).textContent).toContain('2▼'));
    expect(head(/^5 days/).textContent).toContain('1▼');
    expect(th(/^5 days/).getAttribute('aria-sort')).toBe('descending');
    // NEGATIVE: the tie-break is not announced as the sort
    expect(th(/^Q EPS/).getAttribute('aria-sort')).toBe('none');
    expect(th(/^Q EPS/).getAttribute('data-sort-priority')).toBe('2');
    expect(s.hottest.length).toBe(2);
  });

  it('NEGATIVE: a plain click goes back to ONE key — no then_by, single ▼', async () => {
    const s = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(head(/^Q EPS/), { shiftKey: true });
    await waitFor(() => expect(head(/^Q EPS/).textContent).toContain('2▼'));
    fireEvent.click(head(/^Margin/));
    await waitFor(() => expect(s.last()).toContain('sort=net_margin&dir=desc'));
    expect(s.last()).not.toContain('then_by');
    await waitFor(() => expect(head(/^Margin/).textContent).toBe('Margin ▼'));
    expect(head(/^Q EPS/).textContent).toBe('Q EPS');
  });

  it('NEGATIVE: a 4th additive key fires no fetch', async () => {
    const s = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(head(/^Q EPS/), { shiftKey: true });
    await waitFor(() => expect(head(/^Q EPS/).textContent).toContain('2▼'));
    fireEvent.click(head(/^Margin/), { shiftKey: true });
    await waitFor(() => expect(head(/^Margin/).textContent).toContain('3▼'));
    const n = s.hottest.length;
    fireEvent.click(head(/^Sales YoY/), { shiftKey: true });
    await new Promise((r) => setTimeout(r, 20));
    expect(s.hottest.length).toBe(n);
    expect(head(/^Sales YoY/).textContent).toBe('Sales YoY');
  });
});

describe('the "then by" control, ✕ clear and ☀️', () => {
  it('"then by" adds a tie-break and is disabled at the max', async () => {
    const s = stub();
    view();
    await screen.findByText(/Technology/);
    const sel = screen.getByRole('combobox', { name: 'then by' }) as HTMLSelectElement;
    expect(sel.disabled).toBe(false);
    fireEvent.change(sel, { target: { value: 'eq_score' } });
    await waitFor(() => expect(s.last()).toContain('then_by=eq_score%3Adesc'));
    await waitFor(() => expect(head(/^Quality/).textContent).toContain('2▼'));
    fireEvent.change(screen.getByRole('combobox', { name: 'then by' }), { target: { value: 'net_margin' } });
    await waitFor(() => expect(s.last()).toContain('then_by=eq_score%3Adesc%2Cnet_margin%3Adesc'));
    await waitFor(() => expect(
      (screen.getByRole('combobox', { name: 'then by' }) as HTMLSelectElement).disabled).toBe(true));
  });

  it('✕ clear goes back to 5 days ▼ with no then_by; NEGATIVE: hidden when already default', async () => {
    const s = stub();
    view();
    await screen.findByText(/Technology/);
    expect(screen.queryByTestId('hs-sort-clear')).toBeNull();
    fireEvent.click(head(/^Q EPS/));
    fireEvent.click(await screen.findByTestId('hs-sort-clear'));
    await waitFor(() => expect(s.last()).toContain('sort=rel_5d&dir=desc'));
    expect(s.last()).not.toContain('then_by');
    await waitFor(() => expect(screen.queryByTestId('hs-sort-clear')).toBeNull());
  });

  it('NEGATIVE: the ☀️ pre-market read carries no then_by', async () => {
    const s = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(head(/^Q EPS/), { shiftKey: true });
    await waitFor(() => expect(head(/^Q EPS/).textContent).toContain('2▼'));
    fireEvent.click(screen.getByTestId('hs-premarket'));
    await waitFor(() => expect(s.last()).toContain('basis=premarket'));
    expect(s.last()).not.toContain('then_by');
  });

  it('"ranked on" prints served labels; NEGATIVE: a raw key never reaches the screen', async () => {
    stub();
    const { container } = view();
    await screen.findByText(/Technology/);
    fireEvent.click(head(/^Q EPS/), { shiftKey: true });
    await waitFor(() => expect(head(/^Q EPS/).textContent).toContain('2▼'));
    const line = container.querySelector('.hs-sorted-by') as HTMLElement;
    expect(line.textContent).toContain('ranked on 5 days');
    expect(line.textContent).toContain('then Q EPS ▼');
    expect(container.textContent).not.toContain('q_eps_yoy');
  });

  it('rows print in SERVED order — NEGATIVE: a reversed served list renders reversed', async () => {
    stub((p, body) => {
      if (p.thenBy.length) body.sectors = [...(body.sectors as unknown[])].reverse();
    });
    const { container } = view();
    await screen.findByText(/Technology/);
    const order = () => Array.from(container.querySelectorAll('tr.hs-sector .hs-disc'))
      .map((b) => (b.textContent || '').replace(/^[▸▾]\s*/, ''));
    expect(order()).toEqual(['Technology', 'Energy']);
    fireEvent.click(head(/^Q EPS/), { shiftKey: true });
    await waitFor(() => expect(order()).toEqual(['Energy', 'Technology']));
  });
});

describe('the SERVED plan wins over the request (critic #3)', () => {
  it('served shorter than requested: one mark, the select re-opens, net_margin is never re-sent', async () => {
    const s = stub((p, body) => {
      body.sorted_then_by = p.thenBy.filter((t) => t.key !== 'net_margin');
    });
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(head(/^Q EPS/), { shiftKey: true });
    await waitFor(() => expect(head(/^Q EPS/).textContent).toContain('2▼'));
    fireEvent.click(head(/^Margin/), { shiftKey: true });
    await waitFor(() => expect(s.last()).toContain('then_by=q_eps_yoy%3Adesc%2Cnet_margin%3Adesc'));
    await waitFor(() => expect(head(/^Margin/).textContent).toBe('Margin'));
    // NEGATIVE: no third mark anywhere
    expect(document.querySelector('thead')?.textContent).not.toMatch(/3[▼▲]/);
    const sel = screen.getByRole('combobox', { name: 'then by' }) as HTMLSelectElement;
    expect(sel.disabled).toBe(false);
    fireEvent.change(sel, { target: { value: 'sales_yoy' } });
    await waitFor(() => expect(s.last()).toContain('then_by=q_eps_yoy%3Adesc%2Csales_yoy%3Adesc'));
    expect(s.last()).not.toContain('net_margin');
  });

  it('NEGATIVE: served no tie-breaks → no 2 mark, and ✕ follows the served plan', async () => {
    stub((_p, body) => { body.sorted_then_by = []; });
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(head(/^Q EPS/), { shiftKey: true });
    await waitFor(() => expect(screen.queryByText(/Scanning/)).toBeNull());
    await waitFor(() => expect(head(/^5 days/).textContent).toBe('5 days ▼'));
    expect(head(/^Q EPS/).textContent).toBe('Q EPS');
    // served plan is the default → nothing to clear
    expect(screen.queryByTestId('hs-sort-clear')).toBeNull();
  });

  it('demoted ☀️ + shift-click flips 5 days — NEGATIVE: never sort=pre_1d&then_by=rel_5d', async () => {
    const s = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByTestId('hs-premarket'));
    await waitFor(() => expect(s.last()).toContain('sort=pre_1d'));
    await waitFor(() => expect(head(/^5 days/).textContent).toBe('5 days ▼'));
    fireEvent.click(head(/^5 days/), { shiftKey: true });
    await waitFor(() => expect(s.last()).toContain('sort=rel_5d&dir=asc'));
    expect(s.last()).not.toContain('then_by');
    expect(s.hottest.some((u) => u.includes('sort=pre_1d') && u.includes('then_by'))).toBe(false);
  });

  it('NEGATIVE: a PLAIN click on 5 days in the demoted state keeps today\'s rule', async () => {
    const s = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByTestId('hs-premarket'));
    await waitFor(() => expect(head(/^5 days/).textContent).toBe('5 days ▼'));
    await waitFor(() => expect(screen.queryByText('Scanning…')).toBeNull());
    fireEvent.click(head(/^5 days/));
    await waitFor(() => expect(s.last()).toContain('sort=rel_5d&dir=desc'));
  });

  it('in flight: two shift-clicks compose on the request, then marks follow the answer', async () => {
    const s = stub();
    view();
    await screen.findByText(/Technology/);
    s.state.hold = true;
    fireEvent.click(head(/^Q EPS/), { shiftKey: true });
    fireEvent.click(head(/^Margin/), { shiftKey: true });
    expect(s.last()).toContain('then_by=q_eps_yoy%3Adesc%2Cnet_margin%3Adesc');
    // while pending the header draws the request
    expect(head(/^Margin/).textContent).toContain('3▼');
    s.state.hold = false;
    await act(async () => { s.held.splice(0).forEach((r) => r()); });
    await waitFor(() => expect(head(/^Q EPS/).textContent).toContain('2▼'));
    expect(head(/^Margin/).textContent).toContain('3▼');
    expect(head(/^5 days/).textContent).toContain('1▼');
  });
});

/* Critic 2026-09-28 (#1): a click whose read FAILS keeps the old board on
 * screen. The header must keep describing THAT board — primary included — and
 * the next click must build on it, never on the request that failed. */
function stubFailing(fails: (url: string) => 'http' | 'empty' | null) {
  const hottest: string[] = [];
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/supply-demand/bounce-room')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ rows: [] }) } as Response);
    }
    hottest.push(String(url));
    const f = fails(String(url));
    if (f === 'http') {
      return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response);
    }
    const body = answer(String(url));
    if (f === 'empty') { body.sectors = []; body.reason = 'the provider timed out'; }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  }));
  return { hottest, last: () => hottest[hottest.length - 1] };
}

describe('a FAILED re-rank keeps header and rows in agreement (critic #1)', () => {
  for (const kind of ['http', 'empty'] as const) {
    it(`NEGATIVE (${kind}): the header still reads 5 days 1▲ then Q EPS 2▼, not Quality`, async () => {
      const s = stubFailing((u) => (u.includes('sort=eq_score') ? kind : null));
      const { container } = view();
      await screen.findByText(/Technology/);
      fireEvent.click(head(/^5 days/));
      await waitFor(() => expect(head(/^5 days/).textContent).toBe('5 days ▲'));
      fireEvent.click(head(/^Q EPS/), { shiftKey: true });
      await waitFor(() => expect(head(/^Q EPS/).textContent).toContain('2▼'));
      fireEvent.click(head(/^Quality/));
      await waitFor(() => expect(s.last()).toContain('sort=eq_score&dir=desc'));
      await waitFor(() => expect(screen.queryByText('Scanning…')).toBeNull());
      await waitFor(() => expect(head(/^5 days/).textContent).toContain('1▲'));
      expect(head(/^Q EPS/).textContent).toContain('2▼');
      expect(head(/^Quality/).textContent).toBe('Quality');
      expect(th(/^Quality/).getAttribute('aria-sort')).toBe('none');
      expect(th(/^5 days/).getAttribute('aria-sort')).toBe('ascending');
      expect((container.querySelector('.hs-sorted-by') as HTMLElement).textContent)
        .toContain('ranked on 5 days ▲');
      // the next shift-click composes on the board on screen, not the failed ask
      fireEvent.click(head(/^Margin/), { shiftKey: true });
      await waitFor(() => expect(s.last())
        .toContain('sort=rel_5d&dir=asc&then_by=q_eps_yoy%3Adesc%2Cnet_margin%3Adesc'));
      expect(s.last()).not.toContain('eq_score');
    });
  }

  it('NEGATIVE: clicking the failed column again RETRIES at its default dir (not a flip to ▲)', async () => {
    const s = stubFailing((u) => (u.includes('sort=eq_score') ? 'http' : null));
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(head(/^Quality/));
    await waitFor(() => expect(s.last()).toContain('sort=eq_score&dir=desc'));
    await waitFor(() => expect(screen.queryByText('Scanning…')).toBeNull());
    const n = s.hottest.length;
    fireEvent.click(head(/^Quality/));
    await waitFor(() => expect(s.hottest.length).toBe(n + 1));
    expect(s.last()).toContain('sort=eq_score&dir=desc');
    expect(s.hottest.some((u) => u.includes('sort=eq_score&dir=asc'))).toBe(false);
  });

  it('NEGATIVE: ✕ clear after a failed default read retries instead of going dead', async () => {
    let failDefault = false;
    const s = stubFailing((u) => (failDefault && u.includes('sort=rel_5d&dir=desc') ? 'http' : null));
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(head(/^Q EPS/));
    await waitFor(() => expect(head(/^Q EPS/).textContent).toBe('Q EPS ▼'));
    failDefault = true;
    fireEvent.click(await screen.findByTestId('hs-sort-clear'));
    await waitFor(() => expect(s.last()).toContain('sort=rel_5d&dir=desc'));
    await waitFor(() => expect(screen.queryByText('Scanning…')).toBeNull());
    // the board on screen is still Q EPS, so ✕ is still offered — and it works
    expect(head(/^Q EPS/).textContent).toBe('Q EPS ▼');
    const n = s.hottest.length;
    failDefault = false;
    fireEvent.click(screen.getByTestId('hs-sort-clear'));
    await waitFor(() => expect(s.hottest.length).toBe(n + 1));
    await waitFor(() => expect(head(/^5 days/).textContent).toBe('5 days ▼'));
  });
});
