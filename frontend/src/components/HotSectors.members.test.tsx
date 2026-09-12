/* HotSectors → member popover: the WIRE between the strip and the panel.
 *
 * Ajay 2026-09-10: *"I would like to click on the sector category and see the
 * related stocks list in a pop over to see which ones are gaining traction"*.
 *
 * `SectorMembersModal.test.tsx` pins what the panel says once it has a
 * payload. These pin the join — the part that is invisible in a screenshot and
 * silently wrong in production:
 *
 *   1. the chip asks for the GRAIN the backend handed it. The money-in/out
 *      chips are sector × cap-tier COHORTS, not bare sectors; a popover that
 *      inferred "sector" from the row it came out of would answer a different
 *      question than the number above it (and 'Technology · large caps' is not
 *      a sector at all).
 *   2. HOUSE RULE — opening the panel does not change a number he already
 *      sees. The panel carries its own full-membership median; the chip keeps
 *      the sampled one it was built with, byte for byte.
 *   3. a second chip is a second request, not the first panel relabelled.
 *   4. the rows arrive with the numbers the ranking is made of.
 *   5. NEGATIVE — the sample-vs-full sentence cannot be dropped, not even by a
 *      member read that failed outright. That sentence is the only thing
 *      standing between "the full membership" and "the source of the median
 *      above it".
 *   6. NEGATIVE — a group with no stored member list says so in words; a blank
 *      panel reads as a sector with no stocks.
 *   7. Escape closes it and the strip it rides on is untouched.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HotSectors from './HotSectors';
import { _resetRotationMembersCache } from '../hooks/useRotationMembers';

const HOT = {
  as_of: '2026-09-10', start: '2026-06-01', benchmark: 'RSP', ranked_by: 'rel_5d',
  source: 'scan' as const, built_at_iso: '2026-09-10T16:31:50-04:00',
  in: [{ group: 'Technology · large caps', sector: 'Technology', tier: 'large',
         index: 'S&P 500', n: 25, rel_1d: 0.9, rel_5d: 5.7, rel_21d: -2.4,
         rel_window: -8.17 }],
  out: [{ group: 'Real Estate · small caps', sector: 'Real Estate', tier: 'small',
          index: 'S&P 600', n: 25, rel_1d: -1.4, rel_5d: -7.44, rel_21d: -2.39,
          rel_window: -2.39 }],
  industries_in: [{ group: 'Semiconductors', sector: 'Technology', n: 25,
                    rel_1d: 0.3, rel_5d: 9.22, rel_21d: 9.22, rel_63d: 8.74 }],
  themes_out: [{ group: 'robotics', n: 19, rel_1d: -0.9, rel_5d: -4.19,
                 rel_21d: -4.19, rel_63d: -7.75, pct_positive: 31.6 }],
};

/* THE ENDPOINT'S OWN PAYLOAD, key for key.
 *
 * This fixture used to be written in a vocabulary the backend never speaks
 * (`members`, `traction_score`, `traction` as a boolean, `vs_group_21d`,
 * `n_members`, `traction_def`). It matched the frontend's invented reader
 * exactly, so the suite passed green while every real popover rendered ZERO
 * rows. A fixture that agrees with the component instead of the server tests
 * nothing. These names come from backend/rotation/api.py. */
const MEMBERS = {
  grain: 'cohort', group: 'Technology · large caps', sector: 'Technology',
  tier: 'large', benchmark: 'RSP', as_of: '2026-09-10', source: 'scan',
  n_full: 348, priced: 342, unpriced: 6, unpriced_symbols: ['MRO', 'HES'],
  n_measured: 24, n_population: 25, sampled: true, median_21d_full: -1.2,
  median_note: 'Median above = the rotation grid\u2019s 25-name sample',
  traction: {
    field: 'traction', units: 'percentage points per session',
    formula: 'this week faster than its own month, and ahead of its own group',
    sort: 'gaining desc, traction desc, vs_group_21 desc, symbol asc',
  },
  zone: { as_of: '2026-09-09' }, at_demand: 180, zone_unmarked: 168,
  gaining: 1, n: 2, shown: 2,
  rows: [
    // INTC is FIRST on the wire on purpose: it is not gaining, so a reader
    // that sorts on the score alone leaves it first and the name the panel
    // flags as gaining comes second — the one thing the popover answers.
    { symbol: 'INTC', rel_5d: -2.0, rel_21d: -9.5, rel_63d: -14.0,
      vs_group_21: -8.3, traction: 0.105, gaining: false, at_demand: false },
    { symbol: 'NVDA', rel_5d: 3.1, rel_21d: 12.4, rel_63d: 22.0,
      vs_group_21: 13.6, traction: 0.082, gaining: true, at_demand: false },
  ],
};

/** Every /rotation/members request that reached the network, in order. */
let asked: string[] = [];

function stub(members: unknown = MEMBERS, ok = true) {
  asked = [];
  vi.stubGlobal('fetch', vi.fn((url: unknown) => {
    const u = String(url);
    if (u.includes('/rotation/members')) asked.push(u);
    return Promise.resolve({
      ok: u.includes('/rotation/members') ? ok : true,
      status: ok ? 200 : 503,
      json: () => Promise.resolve(u.includes('/rotation/members') ? members : HOT),
    }) as unknown as Promise<Response>;
  }));
}

/* The ~35-chip board is FOLDED on arrival (Ajay 2026-09-12: "this whole thing
 * is super messay"). Every chip assertion below therefore opens it first —
 * which is itself the contract: the chips are all still there, they are just
 * no longer the first thing on the page. */
const draw = async () => {
  const r = render(<MemoryRouter><HotSectors /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: /full board/ }));
  return r;
};
const chip = (name: RegExp) => screen.getByRole('button', { name });
/** The decoded query of the last member request (URLSearchParams encodes a
 *  space as '+', which decodeURIComponent leaves alone). */
const lastAsk = () => decodeURIComponent(asked[asked.length - 1] || '').replace(/\+/g, ' ');

beforeEach(() => { _resetRotationMembersCache(); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('the chip asks for the grain the backend handed it', () => {
  it('a money-in chip drills its COHORT, not the sector it sits in', async () => {
    /* "Technology · large caps" is a sector × cap-tier cohort. Reading the
     * label back as a sector would drill 348 names under a median measured on
     * the 25 large caps — two different questions, one number. */
    stub();
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /Technology · large caps/ }));
    await screen.findByRole('dialog');
    expect(asked).toHaveLength(1);
    expect(lastAsk()).toMatch(/(kind|grain)=cohort/);
    expect(lastAsk()).toContain('group=Technology · large caps');
    expect(lastAsk()).toMatch(/sector=Technology/);
    expect(lastAsk()).toMatch(/tier=large/);
  });

  it('an industry chip drills the industry grain', async () => {
    stub({ ...MEMBERS, kind: 'industry', group: 'Semiconductors' });
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /Semiconductors/ }));
    await screen.findByRole('dialog');
    expect(lastAsk()).toMatch(/(kind|grain)=industry/);
    expect(lastAsk()).toContain('group=Semiconductors');
  });

  it('a theme chip drills the theme grain', async () => {
    stub({ ...MEMBERS, kind: 'theme', group: 'robotics' });
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /robotics/ }));
    await screen.findByRole('dialog');
    expect(lastAsk()).toMatch(/(kind|grain)=theme/);
    expect(lastAsk()).toContain('group=robotics');
  });

  it('a second chip is a second request, not the first panel relabelled', async () => {
    stub();
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /Technology · large caps/ }));
    await screen.findByRole('dialog');
    fireEvent.click(chip(/Real Estate · small caps/));
    await screen.findByRole('dialog');
    expect(asked).toHaveLength(2);
    expect(lastAsk()).toContain('group=Real Estate · small caps');
  });
});

describe('opening the panel changes no number he already sees', () => {
  it('the chip label is byte-identical before and after', async () => {
    /* HOUSE RULE. The panel's own median is over the FULL membership; writing
     * it back onto the chip would silently restate the strip. */
    stub();
    await draw();
    const c = await screen.findByRole('button', { name: /Technology · large caps/ });
    const before = c.textContent;
    const title = c.getAttribute('title');
    fireEvent.click(c);
    await screen.findByRole('dialog');
    expect(c.textContent).toBe(before);
    expect(c.textContent).toBe('Technology · large caps +0.9% · 5d +5.7%');
    expect(c.getAttribute('title')).toBe(title);
    // the full-membership median (-1.2%) lives in the panel and nowhere else
    expect(c.textContent).not.toContain('1.2');
  });

  it('the rest of the strip is untouched while a panel is open', async () => {
    stub();
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /Technology · large caps/ }));
    await screen.findByRole('dialog');
    expect(chip(/Real Estate · small caps/).textContent)
      .toBe('Real Estate · small caps -1.4% · 5d -7.4%');
    expect(screen.getByText(/money in/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /full rotation/ })).toBeInTheDocument();
  });
});

describe('the rows carry the numbers the ranking is made of', () => {
  it('every member arrives with its 5 / 21 / 63 and its vs-group points', async () => {
    stub();
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /Technology · large caps/ }));
    const dialog = await screen.findByRole('dialog');

    const nvda = (await within(dialog).findByText('NVDA')).closest('tr') as HTMLElement;
    expect(nvda).toBeTruthy();
    expect(within(nvda).getByText('+3.1%')).toBeInTheDocument();
    expect(within(nvda).getByText('+12.4%')).toBeInTheDocument();
    expect(within(nvda).getByText('+22.0%')).toBeInTheDocument();
    expect(within(nvda).getByText('+13.6')).toBeInTheDocument();   // points, not %

    const intc = within(dialog).getByText('INTC').closest('tr') as HTMLElement;
    expect(within(intc).getByText('-9.5%')).toBeInTheDocument();
    expect(within(intc).getByText('-8.3')).toBeInTheDocument();
    // and the sort label names what the ranking measures
    expect(dialog.textContent).toContain(MEMBERS.traction.formula);
  });
});

describe('the sample-vs-full sentence cannot be dropped', () => {
  const RECONCILE = /not expected to reconcile/i;

  it('is on screen with the payload', async () => {
    stub();
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /Technology · large caps/ }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog.textContent).toMatch(RECONCILE);
    expect(dialog.textContent).toMatch(/25-name sample/);
    expect(dialog.textContent).toMatch(/all 348 members/);
  });

  it('NEGATIVE: a payload with no counts still says the two are different sets', async () => {
    stub({ ...MEMBERS, n_population: null, n_full: null });
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /Technology · large caps/ }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog.textContent).toMatch(RECONCILE);
    expect(dialog.textContent).not.toMatch(/null|NaN|undefined/);
  });

  it('NEGATIVE: a member read that FAILED still carries the sentence', async () => {
    /* The failure path is where a disclaimer normally goes missing, and it is
     * the path where the panel is emptiest — so it is the path where the full
     * list is most likely to be read as the chip's arithmetic. */
    stub({ error: 'HTTP 503' }, false);
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /Technology · large caps/ }));
    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText(/Member read failed/)).toBeInTheDocument();
    expect(dialog.textContent).toMatch(RECONCILE);
    // and the strip's own number survived the failure untouched
    expect(chip(/Technology · large caps/).textContent)
      .toBe('Technology · large caps +0.9% · 5d +5.7%');
  });
});

describe('an empty table is still information', () => {
  it('NEGATIVE: no stored member list says so, rather than rendering blank', async () => {
    stub({ ...MEMBERS, n_full: 0, priced: 0, unpriced: 0,
           unpriced_symbols: [], rows: [], n: 0, shown: 0 });
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /Technology · large caps/ }));
    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText(/No member list is stored/i)).toBeInTheDocument();
    expect(dialog.querySelector('table')).toBeNull();
    expect((dialog.textContent || '').trim().length).toBeGreaterThan(40);
  });

  it('NEGATIVE: names that could not be priced are counted, not hidden', async () => {
    stub({ ...MEMBERS, priced: 0, rows: [], n: 0, shown: 0 });
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /Technology · large caps/ }));
    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText(/None of this group/i)).toBeInTheDocument();
    expect(dialog.textContent).toMatch(/data gap, not an empty sector/i);
    expect(dialog.textContent).toMatch(/6 dropped/);
    expect(dialog.textContent).toMatch(/MRO/);
  });
});

describe('closing it', () => {
  it('Escape closes the panel and leaves the strip standing', async () => {
    stub();
    await draw();
    fireEvent.click(await screen.findByRole('button', { name: /Technology · large caps/ }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(chip(/Technology · large caps/)).toBeInTheDocument();
    expect(chip(/Technology · large caps/)).toHaveAttribute('aria-expanded', 'false');
  });
});
