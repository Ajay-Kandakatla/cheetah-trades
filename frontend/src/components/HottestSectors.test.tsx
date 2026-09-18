/* 🔥 Hottest — the tab Ajay asked for on 2026-09-11. The cases that matter are
 * the ones his own example exposes: a STRONG name inside a COLD sector, and a
 * thin industry that has no ranked row of its own. */
import { useCallback, useState } from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HottestSectors, pct, tone, tierChip } from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

/* Shaped exactly like the live payload, with ANDE's real numbers from
 * 2026-09-10: strong name, cold sector, thin industry, declining sales. */
const ANDE = {
  symbol: 'ANDE', name: 'The Andersons, Inc.', industry: 'Food Distribution',
  rel_1d: 1.47, rel_5d: 3.83, rel_21d: 15.55, traction: -0.308,
  sales_yoy: -1.22, sales_tier: 'declining', sales_accelerating: false,
  q_eps_yoy: 617.39, net_margin: 1.1, margin_expanding: true,
  eq_score: 29, eq_tier: 'weak', code_33: false, inventory_flag: false,
  next_earnings: '2026-11-03', earnings_when: 'AMC',
};
const NOFUND = {
  symbol: 'ASML', name: 'ASML Holding', industry: 'Semiconductor Equipment & Materials',
  rel_1d: -2.7, rel_5d: 7.1, rel_21d: 3.0,
  sales_yoy: null, sales_tier: null, q_eps_yoy: null, net_margin: null,
  eq_score: null, next_earnings: null,
};

const PAYLOAD = {
  as_of: '2026-09-10', benchmark: 'RSP', sorted_by: 'rel_5d',
  legs: ['rel_1d', 'rel_5d', 'rel_21d'],
  coverage: { priced: 1727, with_fundamentals: 1726, pct: 99.9 },
  note: 'Trailing returns only — a discovery list, not a measured signal.',
  sectors: [
    {
      group: 'Technology', n_full: 305, sampled_of: 305, sampled_used: 40,
      basis: 'rotation grid sample', n_measured: 40,
      rel_1d: -0.59, rel_5d: 2.0, rel_21d: -4.27,
      // the medians rotation/hottest.py::_fund_medians now ships on group rows
      sales_yoy: 12.4, sales_tier: 'steady', q_eps_yoy: 18.0,
      net_margin: 9.6, eq_score: 44, fund_basis: 'median of full membership',
      names: [NOFUND], names_total: 305,
      industries: [{
        group: 'Semiconductor Equipment & Materials', n_full: 23, ranked: true,
        thin: false, basis: 'rotation grid sample',
        rel_1d: -2.73, rel_5d: 7.13, rel_21d: 3.0, names: [NOFUND], names_total: 23,
      }],
    },
    {
      group: 'Consumer Defensive', n_full: 76, sampled_of: 76, sampled_used: 40,
      basis: 'rotation grid sample', n_measured: 40,
      rel_1d: 0.56, rel_5d: -0.94, rel_21d: 0.92,
      names: [ANDE], names_total: 76,
      industries: [{
        group: 'Food Distribution', n_full: 6, ranked: false, thin: true,
        basis: 'full membership',
        rel_1d: 0.53, rel_5d: 0.53, rel_21d: -1.18, names: [ANDE], names_total: 6,
      }],
    },
  ],
};

function stub(body: unknown = PAYLOAD, ok = true) {
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any) => {
    calls.push(String(url));
    return Promise.resolve({ ok, status: ok ? 200 : 500, json: async () => body });
  }));
  return calls;
}
function memStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(), key: (i: number) => [...m.keys()][i] ?? null,
    get length() { return m.size; },
  };
}
const view = () => render(<MemoryRouter><HottestSectors /></MemoryRouter>);

beforeEach(() => { vi.stubGlobal('localStorage', memStorage()); _resetSignalWatchlist(); });
afterEach(() => { vi.unstubAllGlobals(); _resetSignalWatchlist(); });

describe('HottestSectors formatting', () => {
  it('pct prints a sign, and a MISSING value is an em-dash, never a zero', () => {
    expect(pct(3.83)).toBe('+3.8%');
    expect(pct(-1.22)).toBe('-1.2%');
    expect(pct(0)).toBe('+0.0%');
    // NEGATIVE: a blank quarter is not flat growth
    expect(pct(null)).toBe('—');
    expect(pct(undefined)).toBe('—');
    expect(pct(NaN)).toBe('—');
    expect(pct(Infinity)).toBe('—');
  });

  it('tone follows each value OWN sign (Ajay: today is what I want in green)', () => {
    expect(tone(1.47)).toBe('hs-up');
    expect(tone(-2.73)).toBe('hs-dn');
    expect(tone(0)).toBe('hs-flat');
    expect(tone(null)).toBe('hs-flat');
    expect(tone(NaN)).toBe('hs-flat');
  });

  it('tierChip maps the Bonde tiers and stays silent on an unknown one', () => {
    expect(tierChip('explosive')).toBe('🚀');
    expect(tierChip('declining')).toBe('🔻');
    expect(tierChip(null)).toBe('');
    expect(tierChip('something-new')).toBe('');
  });
});

describe('HottestSectors board', () => {
  it('lists EVERY sector including cold ones — the strong-name-in-a-cold-sector case', async () => {
    stub();
    view();
    await screen.findByText(/Technology/);
    // Consumer Defensive is NEGATIVE over 5 days and must still be listed:
    // ANDE lives in it, and that is the whole reason this board exists.
    expect(screen.getByText(/Consumer Defensive/)).toBeTruthy();
  });

  it('opens a cold sector into a THIN industry and finds ANDE', async () => {
    stub();
    view();
    fireEvent.click(await screen.findByRole('button', { name: /Consumer Defensive/ }));
    const ind = await screen.findByRole('button', { name: /Food Distribution/ });
    // a 6-name median must never read as a 25-name one
    expect(screen.getByTitle(/6 names · full membership/)).toBeTruthy();
    fireEvent.click(ind);
    expect(await screen.findByText('ANDE')).toBeTruthy();
    expect(screen.getByText('The Andersons, Inc.')).toBeTruthy();
  });

  it('prints the sales block beside the move, so a price climb with falling sales is visible', async () => {
    stub();
    view();
    fireEvent.click(await screen.findByRole('button', { name: /Consumer Defensive/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Food Distribution/ }));
    const row = (await screen.findByText('ANDE')).closest('tr')!;
    const cells = within(row);
    expect(cells.getByText('+15.6%')).toBeTruthy();      // 21-day, the leg that found it
    expect(cells.getByText('-1.2%')).toBeTruthy();       // sales YoY — NOT confirming the move
    expect(cells.getByText(/declining/)).toBeTruthy();
    expect(cells.getByText(/2026-11-03/)).toBeTruthy();
  });

  it('NEGATIVE: a name with no fundamentals renders em-dashes, not zeros', async () => {
    stub();
    view();
    fireEvent.click(await screen.findByRole('button', { name: /Technology/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Semiconductor Equipment/ }));
    const row = (await screen.findByText('ASML')).closest('tr')!;
    const dashes = within(row).getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(4);
    expect(within(row).queryByText('+0.0%')).toBeNull();
  });

  it('says how much of the sector the HEAT was measured on', async () => {
    stub();
    view();
    await screen.findByText(/Technology/);
    // 40 of 305 — the number must be visible, not buried
    expect(screen.getByTitle(/heat measured on 40 of 305/)).toBeTruthy();
  });

  it('changing the leg refetches with that sort', async () => {
    const calls = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByRole('button', { name: /21 days/ }));
    await waitFor(() => expect(calls.some((u) => u.includes('sort=rel_21d'))).toBe(true));
  });

  /* Ajay 2026-09-12: "Add sort in this". */
  it('EVERY printed column is a sort control, not just the three legs', async () => {
    stub();
    view();
    await screen.findByText(/Technology/);
    // 'Today' became 'Last close <date>' on 2026-09-16: this fixture carries no
    // `d1` block, so the board is on the snapshot and the header must say so.
    for (const label of ['Last close', '5 days', '21 days', 'Sales YoY', 'Sales trend',
                         'Q EPS', 'Margin', 'Quality', 'Next ER']) {
      expect(screen.getByRole('button', { name: new RegExp(label) })).toBeTruthy();
    }
  });

  it('sorting a FUNDAMENTAL column round-trips to the server, not the browser', async () => {
    const calls = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByRole('button', { name: /Sales YoY/ }));
    // the server sort is the point: the payload keeps 25 names per group, so a
    // client-side reorder could never reach the 305th Technology name
    await waitFor(() => expect(calls.some((u) => u.includes('sort=sales_yoy'))).toBe(true));
  });

  it('clicking the ACTIVE column flips the direction instead of re-sorting it', async () => {
    const calls = stub();
    view();
    await screen.findByText(/Technology/);
    expect(calls.some((u) => u.includes('dir=desc'))).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /5 days/ }));   // already active
    await waitFor(() => expect(calls.some((u) => u.includes('sort=rel_5d&dir=asc'))).toBe(true));
  });

  it('Next ER opens ASCENDING — the useful question is who reports soonest', async () => {
    const calls = stub();
    view();
    await screen.findByText(/Technology/);
    fireEvent.click(screen.getByRole('button', { name: /Next ER/ }));
    await waitFor(() => expect(calls.some((u) => u.includes('sort=next_earnings&dir=asc'))).toBe(true));
  });

  it('the active column carries the direction arrow and aria-sort', async () => {
    stub();
    view();
    await screen.findByText(/Technology/);
    expect(screen.getByRole('button', { name: /5 days ▼/ })).toBeTruthy();
    expect(document.querySelector('th[aria-sort="descending"]')).toBeTruthy();
    // an idle column shows NO arrow — nine resting ⇅ glyphs is furniture
    expect(screen.getByRole('button', { name: /^Margin$/ })).toBeTruthy();
  });

  it('the sorted-on state is stated in words, once', async () => {
    stub();
    view();
    await screen.findByText(/ranked on/);
    expect(screen.getByText(/high → low/)).toBeTruthy();
    // the three leg CHIPS that used to duplicate the headers are gone
    expect(screen.queryByRole('button', { pressed: true })).toBeNull();
  });

  it('a GROUP row prints its median in the fundamental columns', async () => {
    stub();
    view();
    const row = (await screen.findByText(/Technology/)).closest('tr')!;
    // blank before 2026-09-12 — so a sort on one of these reordered the tree
    // with nothing on screen to explain the new order
    expect(within(row).getByText('+12.4%')).toBeTruthy();          // sales median
    expect(within(row).getAllByTitle(/median of full membership/).length).toBeGreaterThan(0);
  });

  it('NEGATIVE: a group with no filed fundamentals prints em-dashes, not zeros', async () => {
    stub({
      ...PAYLOAD,
      sectors: [{ ...PAYLOAD.sectors[0], sales_yoy: null, q_eps_yoy: null,
                  net_margin: null, eq_score: null, sales_tier: null,
                  fund_basis: 'median of full membership' }],
    });
    view();
    const row = (await screen.findByText(/Technology/)).closest('tr')!;
    expect(within(row).queryByText('+0.0%')).toBeNull();
    expect(within(row).getAllByText('—').length).toBeGreaterThan(0);
  });

  it('NEGATIVE: a failed fetch says so instead of rendering an empty board', async () => {
    stub(null, false);
    view();
    expect(await screen.findByText(/Hottest sectors unavailable/)).toBeTruthy();
  });

  it('NEGATIVE: a backend reason is shown, not swallowed into a blank table', async () => {
    stub({ sectors: [], reason: 'no persisted rotation build yet' });
    view();
    expect(await screen.findByText(/no persisted rotation build yet/)).toBeTruthy();
  });
});


/* 🎯 ENTERABLE on 🔥 Hottest (2026-09-15). This board's payload is SERVER-CUT —
 * only `names_per_group` rows per group, ranked on the server — so the cut here
 * is client-side over the rows already on screen and the count line has to SAY
 * SO. Hiding 4 of a group's 25 does not pull the 26th up; claiming otherwise
 * would be the board lying about its own membership. A server-side enterable
 * cut is his call (spec §7.9). */
describe('🔥 Hottest — the 🎯 enterable cut says it is over a server-cut list', () => {
  beforeEach(() => { _resetBounceRoomCache(); });
  afterEach(() => { _resetBounceRoomCache(); });

  const read = (verdict: string | null, short: string[] = []) => ({
    kind: 'demand', verdict, reasons: short, reason_short: short, reason_text: short,
    measured: { status: 'pending' },
  });
  const ROOM = {
    as_of: '2026-09-15T11:00:00-04:00', in_session: true, params: {},
    requested: 2, covered: 2, pending: 0, unavailable: 0,
    rows: {
      ANDE: { symbol: 'ANDE', coverage: 'store', print: 40, enterable: read('BLOCKED', ['no band']) },
      ASML: { symbol: 'ASML', coverage: 'store', print: 800, enterable: read('READY') },
    },
  };
  const filtered = (on = true) => {
    vi.stubGlobal('fetch', vi.fn(async (url: any) => ({
      ok: true, status: 200,
      json: async () => (String(url).includes('/supply-demand/bounce-room') ? ROOM : PAYLOAD),
    })));
    return render(
      <MemoryRouter>
        <EnterableFilterProvider enterableOnly={on} kind="demand" setEnterableOnly={() => {}}>
          <HottestSectors />
        </EnterableFilterProvider>
      </MemoryRouter>);
  };

  it('the count line is titled "server-cut" and names the served reason', async () => {
    filtered();
    await screen.findByRole('button', { name: /Consumer Defensive/ });
    const line = await screen.findByText(/hidden/);
    const box = line.closest('.cm-hidden-count') as HTMLElement;
    expect(box.textContent).toMatch(/1 hidden \(1 no band\)/);
    expect(box.getAttribute('title')).toMatch(/server-cut list/);
  });

  it('a BLOCKED name disappears from an opened group, a READY one stays', async () => {
    filtered();
    fireEvent.click(await screen.findByRole('button', { name: /Consumer Defensive/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Food Distribution/ }));
    await waitFor(() => expect(screen.queryByText('ANDE')).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Technology/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Semiconductor Equipment/ }));
    expect(await screen.findByText('ASML')).toBeInTheDocument();
    expect(screen.getByText('🎯 READY')).toBeInTheDocument();
  });

  it('the count line says WHAT it counted — every group, collapsed ones included (m4)', async () => {
    /* m4: the number is over the UNIQUE names in the payload, across themes,
     * sectors and industries, including the groups he has not opened. Every
     * group on this board starts collapsed, so on arrival ZERO name rows are
     * on screen while the line already reads "1 hidden" — a line that claimed
     * to count "rows on screen" would be describing a different set than the
     * one it counted. ANDE sits in both its sector and its industry group and
     * is counted ONCE. */
    filtered();
    const line = await screen.findByText(/hidden/);
    const box = line.closest('.cm-hidden-count') as HTMLElement;
    expect(screen.queryByText('ANDE')).not.toBeInTheDocument();
    expect(box.textContent).toMatch(/1 hidden/);
    const title = box.getAttribute('title') || '';
    expect(title).toMatch(/every group in this payload/);
    expect(title).toMatch(/collapsed ones included/);
    expect(title).toMatch(/unique name/);
    expect(title).not.toMatch(/rows on screen/);
  });

  it('NEGATIVE: with the filter off every name comes back and no line is printed', async () => {
    filtered(false);
    fireEvent.click(await screen.findByRole('button', { name: /Consumer Defensive/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Food Distribution/ }));
    expect(await screen.findByText('ANDE')).toBeInTheDocument();
    expect(screen.queryByText(/hidden/)).not.toBeInTheDocument();
  });
});

/* 🎯 UN-HIDE BY REASON on Hottest (Ajay 2026-09-17).
 *
 * This board is the OTHER hand-rolled call site: the count line comes from
 * `useEnterablePartition`, but each group's own rows are filtered by a plain
 * `isShown` closure. Miss the ignore set on that closure and the line says a
 * name came back while the group it lives in still refuses to draw it — which
 * is the exact lie the feature exists to stop. Both sides are pinned here.
 */
describe('🔥 Hottest — un-hide by reason (2026-09-17)', () => {
  beforeEach(() => { _resetBounceRoomCache(); });
  afterEach(() => { _resetBounceRoomCache(); });

  const read = (verdict: string | null, codes: string[] = [], short: string[] = []) => ({
    kind: 'demand', verdict, reasons: codes, reason_short: short,
    reason_text: short.map((s) => `${s}.`), measured: { status: 'pending' },
  });
  const ROOM2 = {
    as_of: '2026-09-15T11:00:00-04:00', in_session: true, params: {},
    requested: 2, covered: 2, pending: 0, unavailable: 0,
    rows: {
      ANDE: { symbol: 'ANDE', coverage: 'store', print: 40,
              enterable: read('BLOCKED', ['room'], ['room < 5%']) },
      ASML: { symbol: 'ASML', coverage: 'store', print: 800, enterable: read('READY') },
    },
  };

  const draw = () => {
    vi.stubGlobal('fetch', vi.fn(async (url: any) => ({
      ok: true, status: 200,
      json: async () => (String(url).includes('/supply-demand/bounce-room') ? ROOM2 : PAYLOAD),
    })));
    const Page = () => {
      const [ignore, setIgnore] = useState<ReadonlySet<string>>(new Set());
      const toggle = useCallback((code: string) => setIgnore((prev) => {
        const next = new Set(prev);
        if (next.has(code)) next.delete(code); else next.add(code);
        return next;
      }), []);
      return (
        <EnterableFilterProvider enterableOnly kind="demand" setEnterableOnly={() => {}}
                                 ignoreReasons={ignore} toggleReason={toggle}>
          <HottestSectors />
        </EnterableFilterProvider>
      );
    };
    return render(<MemoryRouter><Page /></MemoryRouter>);
  };
  const hsChip = (code: string) => document.querySelector(`[data-reason="${code}"]`) as HTMLButtonElement;

  it('the count line and the GROUP agree — un-hiding room draws the name again', async () => {
    draw();
    fireEvent.click(await screen.findByRole('button', { name: /Consumer Defensive/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Food Distribution/ }));
    await waitFor(() => expect(hsChip('room')).toBeTruthy());
    expect(screen.queryByText('ANDE')).not.toBeInTheDocument();
    fireEvent.click(hsChip('room'));
    await waitFor(() => expect(screen.getByText('ANDE')).toBeInTheDocument());
    const box = screen.getByText(/0 hidden/).closest('.cm-hidden-count') as HTMLElement;
    expect(box.textContent).toContain('✓ room < 5%');
    expect(box.textContent).toContain('1 un-hidden');
  });

  it('SECOND TOGGLE: clicking it again hides the name and the count comes back', async () => {
    draw();
    fireEvent.click(await screen.findByRole('button', { name: /Consumer Defensive/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Food Distribution/ }));
    await waitFor(() => expect(hsChip('room')).toBeTruthy());
    fireEvent.click(hsChip('room'));
    await waitFor(() => expect(screen.getByText('ANDE')).toBeInTheDocument());
    fireEvent.click(hsChip('room'));
    await waitFor(() => expect(screen.queryByText('ANDE')).not.toBeInTheDocument());
    expect(screen.getByText(/1 hidden/)).toBeInTheDocument();
  });

  it('NEGATIVE: an empty ignore set leaves the board exactly as it ships', async () => {
    draw();
    fireEvent.click(await screen.findByRole('button', { name: /Consumer Defensive/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Food Distribution/ }));
    await waitFor(() => expect(hsChip('room')).toBeTruthy());
    expect(screen.queryByText('ANDE')).not.toBeInTheDocument();
    expect(hsChip('room').getAttribute('aria-pressed')).toBe('false');
    expect(hsChip('room').textContent).toBe('1 room < 5%');
  });
});
