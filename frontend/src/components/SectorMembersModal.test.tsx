/* SectorMembersModal — the member popover behind a Hot sectors chip.
 *
 * Ajay 2026-09-09: "click on the sector category and see the related stocks
 * list in a pop over to see which ones are gaining traction".
 *
 * What these pin, in order of how much a break would cost him:
 *   1. the sample-vs-full-membership line is ON SCREEN, not in a tooltip;
 *   2. the traction flag comes from the payload — a name the backend did not
 *      flag never wears the marker;
 *   3. a group nothing could be priced in says so instead of rendering as an
 *      empty sector;
 *   4. Escape closes and focus goes back to the chip that opened it.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HotSectors from './HotSectors';
import { _resetRotationMembersCache } from '../hooks/useRotationMembers';

const HOT = {
  as_of: '2026-09-09', benchmark: 'RSP', ranked_by: 'rel_21d',
  in: [{ group: 'Technology · large caps', sector: 'Technology', tier: 'large',
         index: 'S&P 500', n: 25, rel_21d: 5.7, rel_window: -8.17 }],
  out: [{ group: 'Real Estate · small caps', sector: 'Real Estate', tier: 'small',
          n: 25, rel_21d: -7.44, rel_window: -2.39 }],
  themes_in: [{ group: 'robotics', n: 19, rel_21d: 4.2, rel_63d: 7.7, pct_positive: 60 }],
};

/* THE ENDPOINT'S OWN PAYLOAD, key for key (backend/rotation/api.py). The
 * earlier fixture spoke a vocabulary the server never sends, so it agreed with
 * the component's invented reader and the suite stayed green while every live
 * popover rendered zero rows. */
const MEMBERS = {
  grain: 'cohort', group: 'Technology · large caps', sector: 'Technology', tier: 'large',
  benchmark: 'RSP', as_of: '2026-09-09', source: 'scan',
  n_full: 348, priced: 342, unpriced: 6, unpriced_symbols: ['DEAD1', 'DEAD2'],
  n_measured: 24, n_population: 25, sampled: true, median_21d_full: -1.2,
  traction: {
    field: 'traction', units: 'percentage points per session',
    formula: '21-session rel vs RSP, confirmed by the last 5 sessions',
    sort: 'gaining desc, traction desc, vs_group_21 desc, symbol asc',
  },
  zone: { as_of: '2026-09-09' }, at_demand: 180, zone_unmarked: 168,
  median_1d_full: 0.6, up_today: 201,
  gaining: 2, n: 3, shown: 3,
  rows: [
    { symbol: 'NVDA', name: 'NVIDIA Corporation', rel_1d: 0.9, rel_5d: 3.1, rel_21d: 12.4, rel_63d: 22.0,
      vs_group_21: 13.6, traction: 0.42, gaining: true, at_demand: false },
    { symbol: 'AVGO', name: 'Broadcom Inc.', rel_1d: -0.4, rel_5d: 1.0, rel_21d: 4.0, rel_63d: -3.0,
      vs_group_21: 5.2, traction: 0.11, gaining: true, at_demand: true,
      zone_role: 'demand', zone_depth_pct: 1.4, zone_off_floor_pct: 4.2 },
    { symbol: 'INTC', rel_1d: -1.1, rel_5d: -2.0, rel_21d: -9.5, rel_63d: -14.0,
      vs_group_21: -8.3, traction: -0.27, gaining: false, at_demand: false },
  ],
};

function stub(members: unknown, ok = true) {
  vi.stubGlobal('fetch', vi.fn((url: string) =>
    Promise.resolve(String(url).includes('/rotation/members')
      ? { ok, status: ok ? 200 : 503, json: () => Promise.resolve(members) }
      : { ok: true, status: 200, json: () => Promise.resolve(HOT) }) as any));
}

const draw = () => render(<MemoryRouter><HotSectors /></MemoryRouter>);

async function openTech() {
  const chip = await screen.findByRole('button', { name: /Technology · large caps \+5\.7%/ });
  fireEvent.click(chip);
  return chip as HTMLButtonElement;
}

beforeEach(() => { _resetRotationMembersCache(); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('Hot sectors chips open a member popover', () => {
  it('every strip row is a keyboard-reachable button, not a dead span', async () => {
    stub(MEMBERS);
    draw();
    await screen.findByRole('button', { name: /Technology · large caps/ });
    expect(screen.getByRole('button', { name: /Real Estate · small caps/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /robotics/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Technology · large caps/ }))
      .toHaveAttribute('aria-haspopup', 'dialog');
  });

  it('names the group and how many members it covers', async () => {
    stub(MEMBERS);
    draw();
    await openTech();
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/342 of 348 members covered/)).toBeInTheDocument();
    expect(within(dialog).getByText(/2 gaining traction/)).toBeInTheDocument();
  });

  it('states the sample-vs-full-membership caveat IN THE BODY', async () => {
    stub(MEMBERS);
    draw();
    await openTech();
    const dialog = await screen.findByRole('dialog');
    const warn = within(dialog).getByText(/not expected to reconcile/);
    expect(warn.textContent).toBe(
      "The chip's +5.7% is the median of a 25-name sample of this group; "
      + 'this table is all 348 members — two different sets, so the two are '
      + 'not expected to reconcile.',
    );
    // ON SCREEN, not hidden in a title attribute.
    expect(warn.tagName).toBe('P');
  });

  it('labels the sort with the backend definition of traction', async () => {
    stub(MEMBERS);
    draw();
    await openTech();
    expect(await screen.findByText(
      /Sorted by traction, strongest first — 21-session rel vs RSP, confirmed by the last 5 sessions/,
    )).toBeInTheDocument();
  });

  it('ranks by the backend score and links every ticker to its page', async () => {
    stub(MEMBERS);
    draw();
    await openTech();
    const dialog = await screen.findByRole('dialog');
    const rows = within(dialog).getAllByRole('row').slice(1);   // drop the header
    expect(rows.map((r) => within(r).getByRole('link').textContent)).toEqual(['NVDA', 'AVGO', 'INTC']);
    expect(within(dialog).getByRole('link', { name: 'NVDA' }).getAttribute('href'))
      .toMatch(/^\/sepa\/NVDA/);
  });

  it('leads with TODAY, then the 5/21/63 legs and the vs-group column', async () => {
    stub(MEMBERS);
    draw();
    await openTech();
    const dialog = await screen.findByRole('dialog');
    const row = within(dialog).getByRole('link', { name: 'NVDA' }).closest('tr')!;
    expect(Array.from(row.querySelectorAll('td')).map((c) => c.textContent))
      .toEqual(['+0.9%', '+3.1%', '+12.4%', '+22.0%', '+13.6', '']);
  });

  it('prints the company name under each ticker (2026-09-10)', async () => {
    // Ajay: "Cna you add company name too next to these tickers".
    stub(MEMBERS);
    draw();
    await openTech();
    const dialog = await screen.findByRole('dialog');
    const nvda = within(dialog).getByRole('link', { name: 'NVDA' }).closest('th')!;
    expect(nvda.textContent).toContain('NVIDIA Corporation');
    expect(within(dialog).getByRole('link', { name: 'AVGO' }).closest('th')!.textContent)
      .toContain('Broadcom Inc.');
  });

  it('NEGATIVE: a name the cache has never seen still renders its row', async () => {
    // ~1% of the universe has no cached name. That must cost the second line
    // and nothing else -- never a blank row, and never a provider call from
    // inside the rotation build to go and find one.
    stub(MEMBERS);
    draw();
    await openTech();
    const dialog = await screen.findByRole('dialog');
    const intc = within(dialog).getByRole('link', { name: 'INTC' }).closest('tr')!;
    expect(intc).toBeInTheDocument();
    expect(Array.from(intc.querySelectorAll('td')).map((c) => c.textContent))
      .toEqual(['-1.1%', '-2.0%', '-9.5%', '-14.0%', '-8.3', '']);
    expect(intc.querySelector('.hsm-coname')).toBeNull();
  });

  it('prints the group\u2019s SAME-DAY move and its breadth (2026-09-10)', async () => {
    // Ajay: "Can you also check for same day sector too please?" -- the group
    // number, not just the per-name column. Breadth rides with it: a median
    // says nothing about whether one name is carrying the sector.
    stub(MEMBERS);
    draw();
    await openTech();
    const dialog = await screen.findByRole('dialog');
    expect(dialog.textContent).toMatch(/today \+0\.6%/);
    expect(dialog.textContent).toMatch(/201 of 342 up/);
  });

  it('marks the ones the BACKEND flagged, and only those (NEGATIVE)', async () => {
    stub(MEMBERS);
    draw();
    await openTech();
    const dialog = await screen.findByRole('dialog');
    const flagged = within(dialog).getAllByLabelText('gaining traction');
    expect(flagged).toHaveLength(2);
    const intc = within(dialog).getByRole('link', { name: 'INTC' }).closest('tr')!;
    expect(intc.className).not.toMatch(/traction/);
    expect(within(intc).queryByLabelText('gaining traction')).toBeNull();
  });

  it('marks a name standing at a demand band with the shared 🪃 read', async () => {
    stub(MEMBERS);
    draw();
    await openTech();
    const dialog = await screen.findByRole('dialog');
    const avgo = within(dialog).getByRole('link', { name: 'AVGO' }).closest('tr')!;
    // ◧, never 🪃. The tracker marks members with in_demand_read only ("the
    // print is inside an eligible band"); it does not run bounce_read, so a
    // reversal marker here would claim a read the backend never computes.
    expect(avgo.textContent).toMatch(/◧/);
    expect(avgo.textContent).not.toMatch(/🪃/);
    const nvda = within(dialog).getByRole('link', { name: 'NVDA' }).closest('tr')!;
    expect(nvda.textContent).not.toMatch(/🪃/);
  });

  it('counts what it dropped rather than hiding it', async () => {
    stub(MEMBERS);
    draw();
    await openTech();
    expect(await screen.findByText(/6 dropped \(dead or stale series\)/)).toBeInTheDocument();
    expect(screen.getByText(/dropped: DEAD1, DEAD2/)).toBeInTheDocument();
  });

  it('NEGATIVE: a group nothing could be priced says so, never reads as empty', async () => {
    stub({ ...MEMBERS, priced: 0, rows: [], n: 0, shown: 0 });
    draw();
    await openTech();
    expect(await screen.findByText(/None of this group’s 348 members could be priced/))
      .toBeInTheDocument();
    expect(screen.getByText(/data gap, not an empty sector/)).toBeInTheDocument();
  });

  it('NEGATIVE: a failed member read never touches the number on the chip', async () => {
    stub({ error: 'boom' }, false);
    draw();
    await openTech();
    expect(await screen.findByText(/Member read failed/)).toBeInTheDocument();
    expect(screen.getByText(/median on the strip is\s+unaffected/)).toBeInTheDocument();
    // The strip itself is untouched.
    expect(screen.getByRole('button', { name: /Technology · large caps \+5\.7%/ })).toBeInTheDocument();
  });

  it('Escape closes it and focus goes back to the chip that opened it', async () => {
    stub(MEMBERS);
    draw();
    const chip = await openTech();
    await screen.findByRole('dialog');
    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(document.activeElement).toBe(chip);
  });

  it('the ✕ button closes it too', async () => {
    stub(MEMBERS);
    draw();
    await openTech();
    fireEvent.click(await screen.findByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('a theme chip drills its own roster', async () => {
    stub({ ...MEMBERS, grain: 'theme', group: 'robotics', n_full: 19, priced: 19, sampled: false, n_population: 19,
           n_dropped: 0, dropped_symbols: [] });
    draw();
    fireEvent.click(await screen.findByRole('button', { name: /robotics \+4\.2%/ }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/19 of 19 members covered/)).toBeInTheDocument();
    const url = String((globalThis.fetch as any).mock.calls.at(-1)[0]);
    expect(url).toMatch(/kind=theme/);
    expect(url).toMatch(/group=robotics/);
  });
});
