import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HotSectors, {
  chipFace, marketLine, monthLeg, scanStamp, themeTitle, windowLabel,
} from './HotSectors';

const PAYLOAD = {
  as_of: '2026-09-10', start: '2026-06-01', benchmark: 'RSP',
  ranked_by: 'rel_5d',
  in: [
    { group: 'Technology · large caps', sector: 'Technology', tier: 'large',
      index: 'S&P 500', n: 25, rel_1d: 0.9, rel_5d: 5.7, rel_21d: 2.1, rel_window: -8.17 },
    { group: 'Energy · small caps', sector: 'Energy', tier: 'small',
      index: 'S&P 600', n: 25, rel_1d: -0.3, rel_5d: 5.11, rel_21d: 6.4, rel_window: 6.32 },
  ],
  out: [
    { group: 'Real Estate · small caps', sector: 'Real Estate', tier: 'small',
      index: 'S&P 600', n: 25, rel_1d: -1.4, rel_5d: -7.44, rel_21d: -2.2, rel_window: -2.39 },
  ],
};

function stub(body: any, ok = true) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok, status: ok ? 200 : 503, json: () => Promise.resolve(body),
  } as any));
}

const draw = () => render(<MemoryRouter><HotSectors /></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('HotSectors', () => {
  it('leads every chip with TODAY and prints the week beside it', async () => {
    stub(PAYLOAD);
    draw();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Technology · large caps +0.9% · 5d +5.7%' }))
        .toBeTruthy());
    expect(screen.getByRole('button', { name: 'Energy · small caps -0.3% · 5d +5.1%' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Real Estate · small caps -1.4% · 5d -7.4%' })).toBeTruthy();
    expect(screen.getByText(/money in/i)).toBeTruthy();
    expect(screen.getByText(/money out/i)).toBeTruthy();
    expect(screen.getByText(/vs RSP/)).toBeTruthy();
  });

  it('says WHICH window the order is made of, so 5 days is never read as 21', async () => {
    stub(PAYLOAD);
    draw();
    await waitFor(() => expect(screen.getByText(/ranked by the last 5 sessions/)).toBeTruthy());
    expect(screen.getByText(/today first/)).toBeTruthy();
  });

  it('links to the full rotation page', async () => {
    stub(PAYLOAD);
    draw();
    await waitFor(() => expect(screen.getByText(/full rotation/)).toBeTruthy());
    expect(screen.getByRole('link', { name: /full rotation/ }))
      .toHaveAttribute('href', '/rotation');
  });

  it('renders NOTHING on error — a strip must never break its page', async () => {
    stub({ error: 'boom' }, false);
    const { container } = draw();
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector('.hs')).toBeNull();
  });

  it('renders nothing while loading, and nothing when the build measured nothing', async () => {
    stub({ in: [], out: [] });
    const { container } = draw();
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector('.hs')).toBeNull();
  });
});


/* ── THE INVERSION (Ajay 2026-09-10) ─────────────────────────────────────────
 * "Actually this is red but it picked up today so its the inverse.. Basically
 *  what ever today is what I wanna see in green but keep the other days too ...
 *  Ignore the 21 day even if its read now recently market rotated that is the
 *  actual truth to us."
 *
 * Aerospace & Defense read rel_21d -11.9 on a day its members were +2 to +7
 * over five sessions. These pin that the month can no longer tone a chip, that
 * today can be green inside the money-OUT bucket, and that an unmeasurable day
 * fails closed to flat rather than to green. */
describe('today decides the colour, the month decides nothing', () => {
  const TAPE = {
    as_of: '2026-09-10', benchmark: 'RSP', ranked_by: 'rel_5d',
    in: [{ group: 'Aerospace & Defense', sector: 'Industrials', n: 25,
           rel_1d: 1.2, rel_5d: 3.0, rel_21d: -11.9, rel_63d: -8.36,
           pct_positive_1d: 71 }],
    out: [{ group: 'Utilities · large caps', sector: 'Utilities', n: 25,
            rel_1d: 0.4, rel_5d: -2.2, rel_21d: 4.8, rel_window: 1.1 }],
  };

  it('a group deep red over the month reads GREEN when today is green', () => {
    const f = chipFace(TAPE.in[0]);
    expect(f.day).toBe('+1.2%');
    expect(f.week).toBe('+3.0%');
    expect(f.tone).toBe('up');           // NOT 'down', which -11.9 would have given
  });

  it('a money-OUT row that is up today still tones up — the bucket does not colour it', () => {
    expect(chipFace(TAPE.out[0]).tone).toBe('up');
  });

  it('a row green over the month but red today tones DOWN', () => {
    expect(chipFace({ group: 'x', rel_21d: 9.9, rel_1d: -0.5, rel_5d: -1.0 }).tone).toBe('down');
  });

  it('NEGATIVE: an unmeasurable day is flat and prints a dash — never hot', () => {
    const f = chipFace({ group: 'x', rel_21d: 12.0, rel_1d: null });
    expect(f.tone).toBe('flat');
    expect(f.day).toBe('—');
    expect(f.week).toBe('—');
    expect(chipFace({ group: 'x', rel_21d: 12.0 }).tone).toBe('flat');
    // NaN is not a number, however hard a JSON payload insists
    expect(chipFace({ group: 'x', rel_21d: null, rel_1d: NaN }).tone).toBe('flat');
  });

  it('exactly flat today is flat, not green', () => {
    expect(chipFace({ group: 'x', rel_21d: 5, rel_1d: 0, rel_5d: 0 }).tone).toBe('flat');
  });

  it('the chip FACE carries no 21-day number, and the hover still does', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(TAPE) } as Response)));
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    const chip = await screen.findByRole('button', { name: /Aerospace & Defense/ });
    expect(chip.textContent).toBe('Aerospace & Defense +1.2% · 5d +3.0%');
    expect(chip.textContent).not.toContain('11.9');
    expect(chip.className).toContain('hs-chip-up');
    // kept, because "keep the other days too" — on the hover, with the breadth
    expect(chip.getAttribute('title')).toContain('21d -11.9% rel');
    expect(chip.getAttribute('title')).toContain('71% of members up today');
  });

  it('monthLeg keeps the number and survives a missing one', () => {
    expect(monthLeg({ group: 'x', rel_21d: -11.9 })).toBe(' · 21d -11.9% rel');
    expect(monthLeg({ group: 'x', rel_21d: null })).toBe(' · 21d —% rel');
  });
});


/* ── the market line (Ajay 2026-09-10) ───────────────────────────────────────
 * "when there are none hot that day it helps to know overall market it red."
 * 9 of 11 sectors were red that day; RSP -0.68 with 23% of names up. An empty
 * inflow side must read as a red tape, never as a broken scan. */
describe('marketLine — what the tape did when nothing is hot', () => {
  const market = { benchmark: 'RSP', ret_1d: -0.68, ret_5d: -2.48, pct_positive_1d: 23 };

  it('prints the sentence he asked for, verbatim', () => {
    expect(marketLine({ market })).toBe(
      'nothing is hot today; the whole tape is red: RSP -0.7%, 23% of names up');
  });

  it('says green when the tape is green and flat when it is flat', () => {
    expect(marketLine({ market: { ...market, ret_1d: 0.9 } }))
      .toMatch(/the whole tape is green: RSP \+0\.9%, 23% of names up/);
    expect(marketLine({ market: { ...market, ret_1d: 0 } }))
      .toMatch(/the tape is flat: RSP —%|the tape is flat: RSP \+?0\.0%/);
  });

  it('falls back to the payload benchmark when the market read does not name one', () => {
    expect(marketLine({ benchmark: 'RSP', market: { ret_1d: -0.68, pct_positive_1d: 23 } }))
      .toContain('RSP -0.7%');
    expect(marketLine({ market: { ret_1d: -0.68 } })).toContain('RSP -0.7%');
  });

  it('prints whichever half it has, and never invents the other', () => {
    expect(marketLine({ market: { ret_1d: -0.68 } }))
      .toBe('nothing is hot today; the whole tape is red: RSP -0.7%');
    expect(marketLine({ market: { pct_positive_1d: 23 } }))
      .toBe('nothing is hot today; the tape reads: 23% of names up');
  });

  it('NEGATIVE: nothing measured says nothing at all', () => {
    expect(marketLine({})).toBeNull();
    expect(marketLine({ market: null })).toBeNull();
    expect(marketLine({ market: { ret_5d: -2.48 } })).toBeNull();
    expect(marketLine({ market: { ret_1d: NaN, pct_positive_1d: null } })).toBeNull();
  });
});

describe('the strip on a day nothing is hot', () => {
  const RED_TAPE = {
    as_of: '2026-09-10', benchmark: 'RSP', ranked_by: 'rel_5d',
    in: [],
    out: [{ group: 'Utilities · large caps', n: 25, rel_1d: -1.9, rel_5d: -4.1, rel_21d: -3.0 }],
    market: { benchmark: 'RSP', ret_1d: -0.68, ret_5d: -2.48, pct_positive_1d: 23 },
  };
  const stubHot = (d: unknown) => vi.stubGlobal('fetch', vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(d) } as Response)));

  it('says so in words and prints the market-wide read', async () => {
    stubHot(RED_TAPE);
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    expect(await screen.findByText(
      'nothing is hot today; the whole tape is red: RSP -0.7%, 23% of names up',
    )).toBeInTheDocument();
    // and the outflow side still renders — the strip is not blanked
    expect(screen.getByRole('button', { name: /Utilities · large caps/ })).toBeInTheDocument();
    // an inflow tag with no chips under it reads as a broken scan, so it is gone
    expect(screen.queryByText('money in')).not.toBeInTheDocument();
  });

  it('renders the line even when there is not a single row', async () => {
    stubHot({ ...RED_TAPE, out: [] });
    const { container } = render(<MemoryRouter><HotSectors /></MemoryRouter>);
    expect(await screen.findByText(/the whole tape is red/)).toBeInTheDocument();
    expect(container.querySelector('.hs')).not.toBeNull();
  });

  it('NEGATIVE: no rows AND no market read renders nothing, as it always did', async () => {
    stubHot({ ...RED_TAPE, out: [], market: null });
    const { container } = render(<MemoryRouter><HotSectors /></MemoryRouter>);
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector('.hs')).toBeNull();
  });

  it('NEGATIVE: the line is absent on a day something IS hot', async () => {
    stubHot({ ...RED_TAPE, in: [{ group: 'Gold', n: 10, rel_1d: 2.0, rel_5d: 6.0, rel_21d: 14.2 }] });
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    await screen.findByRole('button', { name: /Gold/ });
    expect(screen.queryByText(/nothing is hot today/)).not.toBeInTheDocument();
  });
});


describe('windowLabel — the header can never claim a window it did not rank by', () => {
  it('names the backend ranking key', () => {
    expect(windowLabel('rel_5d')).toBe('the last 5 sessions');
    expect(windowLabel('rel_21d')).toBe('the last 21 sessions');
    expect(windowLabel('rel_63d')).toBe('the last 63 sessions');
    expect(windowLabel('rel_1d')).toBe('today');
    expect(windowLabel('rel_window')).toBe('the full window');
  });
  it('NEGATIVE: an unknown or missing key claims no window', () => {
    expect(windowLabel(undefined)).toBe('the ranking window');
    expect(windowLabel('rel_totally_new')).toBe('the ranking window');
  });
  it('a stale build ranked by the month makes the header SAY the month', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      ok: true, json: () => Promise.resolve({ ...PAYLOAD, ranked_by: 'rel_21d' }),
    } as Response)));
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    expect(await screen.findByText(/ranked by the last 21 sessions/)).toBeInTheDocument();
  });
});


/* ── the scan stamp (Ajay 2026-09-06: "make ... Hot sectors part of the scans") ── */
describe('scanStamp — the strip says which scan built it', () => {
  it('prints the ET clock of a scan-built strip and nothing for a live build', () => {
    expect(scanStamp({ source: 'scan', built_at_iso: '2026-09-04T16:41:12-04:00' })).toBe('16:41');
    expect(scanStamp({ source: 'live', built_at_iso: '2026-09-04T16:41:12-04:00' })).toBe('');
    expect(scanStamp({ source: 'scan', built_at_iso: null })).toBe('');
    expect(scanStamp({ source: 'scan', built_at_iso: 'garbage' })).toBe('');
    expect(scanStamp({})).toBe('');
  });
});


/* ── industry cohorts on the strip (Ajay 2026-09-09) ────────────────────────
 * "increase our sectors ... money got moved in to technology too from Semis
 *  or reduced in semis today."
 * The sector row cannot show this: on 2026-09-09 Technology read -4.72 while
 * Semiconductors was -13.32 over 63 days and Software-Infrastructure +19.10.
 * These pin that the finer rows render, and that the strip still degrades to
 * nothing rather than breaking the page it rides on. */
describe('HotSectors — industry cohorts (2026-09-09)', () => {
  const withIndustries = {
    as_of: '2026-09-09', benchmark: 'RSP', source: 'scan' as const,
    built_at_iso: '2026-09-09T16:31:50-04:00', ranked_by: 'rel_5d',
    in: [{ group: 'Energy · large caps', n: 40, rel_1d: 1.1, rel_5d: 8.61, rel_21d: 8.61 }],
    out: [{ group: 'Technology · large caps', n: 40, rel_1d: -0.8, rel_5d: -4.72, rel_21d: -4.72 }],
    industries_in: [
      { group: 'Oil & Gas E&P', sector: 'Energy', n: 25, rel_1d: 1.4, rel_5d: 9.22, rel_21d: 9.22, rel_63d: 8.74 },
      { group: 'Gold', sector: 'Basic Materials', n: 10, rel_1d: 2.6, rel_5d: 14.25, rel_21d: 14.25, rel_63d: 25.61 },
    ],
    industries_out: [
      { group: 'Semiconductors', sector: 'Technology', n: 25, rel_1d: -0.7, rel_5d: -1.95, rel_21d: -1.95, rel_63d: -13.32 },
      { group: 'Aerospace & Defense', sector: 'Industrials', n: 25, rel_1d: 1.2, rel_5d: -12.13, rel_21d: -12.13, rel_63d: -8.36 },
    ],
  };

  it('renders the finer rows with their numbers beside the sector rows', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(withIndustries) } as Response)));
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    expect(await screen.findByRole('button', { name: 'Oil & Gas E&P +1.4% · 5d +9.2%' }))
      .toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Semiconductors -0.7% · 5d -1.9%' })).toBeInTheDocument();
    expect(screen.getByText('industry in')).toBeInTheDocument();
    expect(screen.getByText('industry out')).toBeInTheDocument();
    // the sector rows are still there — the finer grain ADDS, never replaces
    expect(screen.getByRole('button', { name: /Energy · large caps/ })).toBeInTheDocument();
  });

  it('says which sector an industry sits inside, so the split is legible', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(withIndustries) } as Response)));
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    const chip = await screen.findByRole('button', { name: /^Semiconductors/ });
    expect(chip.getAttribute('title')).toMatch(/inside Technology/);
    expect(chip.getAttribute('title')).toMatch(/-13\.32% rel/);
  });

  it('NEGATIVE: an old payload with no industry keys still renders the strip', async () => {
    const legacy = { ...withIndustries, industries_in: undefined, industries_out: undefined };
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(legacy) } as Response)));
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    expect(await screen.findByRole('button', { name: /Energy · large caps/ })).toBeInTheDocument();
    expect(screen.queryByText('industry in')).not.toBeInTheDocument();
  });

  it('NEGATIVE: industries alone (no sector rows) still render', async () => {
    const only = { ...withIndustries, in: [], out: [] };
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(only) } as Response)));
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    expect(await screen.findByRole('button', { name: 'Gold +2.6% · 5d +14.3%' })).toBeInTheDocument();
  });

      // The window tag is DERIVED from ranked_by, never hardcoded: a stale build
    // still ranked on the month must say "21d", not print "5d" over 21-day
    // numbers. That mislabel is the whole complaint this change answers.
    it('NEGATIVE: a pre-2026-09-10 build prints dashes AND its own window, not zeros under a 5d tag', async () => {
    const stale = {
      as_of: '2026-09-08', benchmark: 'RSP', ranked_by: 'rel_21d',
      in: [{ group: 'Energy · large caps', n: 40, rel_21d: 8.61 }], out: [],
    };
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(stale) } as Response)));
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    const chip = await screen.findByRole('button', { name: /Energy · large caps/ });
    expect(chip.textContent).toBe('Energy · large caps — · 21d —');
    expect(chip.className).toContain('hs-chip-flat');
    expect(chip.className).not.toContain('hs-chip-up');
  });
});


/* ── theme rows (Ajay 2026-09-09: "robotics, energy and optic fiber,
 * constructipn like for data centers add these") ──────────────────────────
 * Three of those four were already tracked and had never been rendered — the
 * bug was invisibility, not absence. These pin that they render, that a thin
 * cohort says so, and that an old payload without the keys still works. */
describe('HotSectors — build-out theme rows (2026-09-09)', () => {
  const withThemes = {
    as_of: '2026-09-09', benchmark: 'RSP', ranked_by: 'rel_5d',
    in: [{ group: 'Energy · large caps', n: 40, rel_1d: 1.1, rel_5d: 8.61, rel_21d: 8.61 }],
    out: [{ group: 'Technology · large caps', n: 40, rel_1d: -0.8, rel_5d: -4.72, rel_21d: -4.72 }],
    themes_in: [
      { group: 'energy', n: 20, rel_1d: 1.0, rel_5d: 9.03, rel_21d: 9.03, rel_63d: 7.53, pct_positive: 90 },
      { group: 'rare_earth', n: 4, rel_1d: 0.5, rel_5d: 2.96, rel_21d: 2.96, rel_63d: -11.27, pct_positive: 0, thin: true },
    ],
    themes_out: [
      { group: 'datacenter_build', n: 10, rel_1d: -1.2, rel_5d: -6.98, rel_21d: -6.98, rel_63d: -23.71, pct_positive: 10 },
      { group: 'robotics', n: 19, rel_1d: -0.9, rel_5d: -4.19, rel_21d: -4.19, rel_63d: -7.75, pct_positive: 31.6 },
      { group: 'optical', n: 12, rel_1d: -0.4, rel_5d: -3.13, rel_21d: -3.13, rel_63d: -20.69, pct_positive: 16.7 },
    ],
  };
  const stubThemes = (d: unknown) => vi.stubGlobal('fetch', vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(d) } as Response)));

  it('renders every theme he named, with its numbers', async () => {
    stubThemes(withThemes);
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    expect(await screen.findByRole('button', { name: 'energy +1.0% · 5d +9.0%' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'robotics -0.9% · 5d -4.2%' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'optical -0.4% · 5d -3.1%' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'datacenter_build -1.2% · 5d -7.0%' })).toBeInTheDocument();
  });

  it('marks a thin cohort on the chip AND explains it on hover', async () => {
    stubThemes(withThemes);
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    const chip = await screen.findByRole('button', { name: /rare_earth .* ·thin/ });
    expect(chip.getAttribute('title')).toMatch(/THIN/);
    expect(chip.getAttribute('title')).toMatch(/4 names/);
  });

  it('a non-thin theme carries no thin marker (NEGATIVE)', async () => {
    stubThemes(withThemes);
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    const chip = await screen.findByRole('button', { name: /^robotics/ });
    expect(chip.textContent).not.toMatch(/thin/);
    expect(chip.getAttribute('title')).not.toMatch(/THIN/);
  });

  it('NEGATIVE: an old payload with no theme keys still renders the strip', async () => {
    stubThemes({ ...withThemes, themes_in: undefined, themes_out: undefined });
    render(<MemoryRouter><HotSectors /></MemoryRouter>);
    expect(await screen.findByRole('button', { name: /Energy · large caps/ })).toBeInTheDocument();
    expect(screen.queryByText('theme in')).not.toBeInTheDocument();
  });
});

describe('themeTitle', () => {
  it('names the count, the 63-day read, the month it no longer ranks by, and the breadth', () => {
    expect(themeTitle({ group: 'robotics', n: 19, rel_21d: -4.19, rel_63d: -7.75, pct_positive: 31.6 }))
      .toBe('robotics — 19 names · 63d -7.75% rel · 21d -4.19% rel · 31.6% of members positive');
  });
  it('carries today’s breadth when the build measured it', () => {
    expect(themeTitle({ group: 'robotics', n: 19, rel_21d: -4.19, rel_63d: -7.75,
                        pct_positive: 31.6, pct_positive_1d: 68.4 }))
      .toMatch(/68% of members up today$/);
  });
  it('warns when the cohort is too thin to mean much', () => {
    expect(themeTitle({ group: 'rare_earth', n: 4, rel_21d: 2.96, rel_63d: -11.27, pct_positive: 0, thin: true }))
      .toMatch(/THIN: too few names/);
  });
  it('survives missing numbers', () => {
    expect(themeTitle({ group: 'x', rel_21d: null }))
      .toBe('x — undefined names · 63d —% rel · 21d —% rel');
  });
});
