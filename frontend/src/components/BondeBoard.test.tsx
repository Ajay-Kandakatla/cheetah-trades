import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BondeBoard, { type BondeBoardData } from './BondeBoard';
import { CM_TABS, TAB_META, isBoardTab, parseTab } from '../lib/chartMaps';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';

/* 📈 Bonde tab (Ajay 2026-09-13). The negatives matter most: this board shows
 * percentages off revenue bases that can be negative or immaterial, and an
 * empty headline section that has a structural cause. Each of those reads as
 * something it is not unless the board says otherwise. */

const row = (symbol: string, over: Partial<any> = {}) => ({
  symbol, name: `${symbol} Inc`, tier: 'explosive',
  growth_yoy_pct: 120, base_rev: 5_000_000, latest_rev: 11_000_000,
  rev_added: 6_000_000, base_state: 'ok', sales_score: 100,
  accelerating: true, consecutive_growth_q: 4, sales_led: true,
  pivot: null, is_new: false, ...over,
});

const payload = (over: Partial<BondeBoardData> = {}): BondeBoardData => ({
  sections: { pivot: [], explosive: [row('PTGX')], strong: [], steady: [], rejected: [] },
  counts: { pivot: 0, explosive: 69, strong: 304, steady: 677, rejected: 120 },
  caps: { pivot: 60, explosive: 60, strong: 60, steady: 40, rejected: 40 },
  n_pass: 1051, n_rejected: 120, n_scanned: 2076, n_new: 0, new_days: 30,
  measured: {
    headline: 'MEASURED 2026-09-13 AND THIS BOARD’S OWN THESIS IS INVERTED',
    body: 'the 376 that ALSO passed his sales gate returned a median −3.22% over the next 21 sessions (win rate 39.8%) against −0.11% (49.6%) for date-matched non-EP names — a lift of −3.11pp. THIS IS A STUDY BOARD, NOT A BUY LIST.',
    not_a_short: 'that cohort’s 21-day MEAN is −2.18% with a CI that includes zero.',
    tiers: 'the ≥100% and ≥25% tiers beat the scored universe by a MEDIAN of +0.45pp and +0.37pp',
    rejected: 'the rejected names win 56.8% of the next 21 sessions against 51.2%',
    struck: 'Struck on re-measurement: that EP+PASS also loses to EP+FAIL.',
    limits: 'delisting survivorship is unmeasured.',
    scripts: 'backend/scripts/bonde_audit/',
  },
  regime: { is_bull: false, label: 'market_in_correction', score: 66.5, scanners_paused: true },
  note: 'note', ...over,
});

const draw = (d: BondeBoardData) => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => d } as any)));
  return render(<MemoryRouter><BondeBoard /></MemoryRouter>);
};

beforeEach(() => { vi.unstubAllGlobals(); _resetBounceRoomCache(); });

describe('the tab is registered as a non-tile board', () => {
  it('is in CM_TABS with copy, and is not a tile board', () => {
    expect(CM_TABS).toContain('bonde');
    expect(TAB_META.bonde.label).toMatch(/Bonde/);
    expect(isBoardTab('bonde')).toBe(false);
    expect(parseTab('bonde')).toBe('bonde');
  });

  it('the blurb states WHOSE numbers are whose', () => {
    // His 5/25/100 tiers are documented in his own writing; the Pivot's 8%/5x
    // and the $1M base floor are this app's. A board that blurs that is
    // attributing thresholds to him that he never published.
    const b = TAB_META.bonde.blurb;
    expect(b).toMatch(/sales_confidence_methodology/);
    expect(b).toMatch(/THIS APP’S owner settings/);
  });

  it('the blurb LEADS with the inverted measurement, not with the rules', () => {
    // The tab shipped on a thesis that measured the wrong way round hours
    // later. Same treatment the Keltner and AMD tabs got the same day: the
    // reader meets the verdict before the mechanics, or they have already read
    // the rows as a buy list.
    const b = TAB_META.bonde.blurb;
    expect(b.startsWith('MEASURED 2026-09-13 AND THIS BOARD’S OWN THESIS IS INVERTED')).toBe(true);
    expect(b).toMatch(/−3\.22%/);            // the cell
    expect(b).toMatch(/−0\.11% and 49\.6%/); // its placebo, beside it
    expect(b).toMatch(/−3\.11pp/);
    expect(b).toMatch(/CI −5\.28 to −1\.16/); // never a bare point estimate
    expect(b).toMatch(/backend\/scripts\/bonde_audit\//);
  });

  it('NEGATIVE — the blurb never claims the sales gate confirms the pivot', () => {
    // The measured direction is the opposite: the gate passes 48.2% of Pivot
    // events and 46.0% of matched non-Pivot draws, so it carries no
    // information about the pivot at all.
    const b = TAB_META.bonde.blurb;
    expect(b).toMatch(/separated nothing at any horizon/);
    expect(b).not.toMatch(/high-conviction/i);
    expect(b).not.toMatch(/quality-confirmed/i);
    // ...and it is not read the other way either
    expect(b).toMatch(/NOT A LICENCE TO SHORT/);
  });

  it('NEGATIVE — the blurb prints tier MEDIANS and win rates, never a lone mean', () => {
    // The first pass's "+3.8pp / +1.6pp" were MEAN lifts printed as if they
    // were typical outcomes. The medians are +0.45pp and +0.37pp with CIs
    // that include zero.
    const b = TAB_META.bonde.blurb;
    expect(b).toMatch(/MEDIAN of \+0\.45pp and \+0\.37pp/);
    expect(b).toMatch(/both CIs including zero/);
    expect(b).toMatch(/falls to \+0\.26pp/);
    expect(b).toMatch(/never sorts on the 0-100 sales score/);
  });
});

describe('the board', () => {
  it('leads with how many pass and how many are NEW', async () => {
    draw(payload());
    expect(await screen.findByText(/pass his screen/)).toBeInTheDocument();
    expect(screen.getByText('1,051')).toBeInTheDocument();
    expect(screen.getByText(/new in 30d/)).toBeInTheDocument();
  });

  it('shows the growth percentage WITH the dollars behind it', async () => {
    // The percentage alone is the thing that can lie. $5.0M → $11.0M cannot.
    draw(payload());
    expect(await screen.findByText('+120%')).toBeInTheDocument();
    expect(screen.getByText(/\$5\.0M → \$11\.0M/)).toBeInTheDocument();
  });

  it('NEGATIVE — a negative base is flagged, not rendered as clean growth', async () => {
    draw(payload({ sections: { pivot: [], strong: [], steady: [],
      explosive: [row('DBRG', { growth_yoy_pct: 15961.5, base_rev: -3_207_000,
                                rev_added: null, base_state: 'non_positive' })] } }));
    const cell = await screen.findByText(/15962%|15961/);
    expect(cell.textContent).toMatch(/⚠/);
    expect(cell.getAttribute('title')).toMatch(/NEGATIVE/);
    expect(cell.getAttribute('title')).toMatch(/sign flip/);
  });

  it('NEGATIVE — an immaterial base says the floor is THIS APP’S, not Bonde’s', async () => {
    draw(payload({ sections: { pivot: [], strong: [], steady: [],
      explosive: [row('QUBT', { growth_yoy_pct: 9000, base_rev: 61_000,
                                base_state: 'too_small' })] } }));
    const cell = await screen.findByText(/9000%/);
    expect(cell.getAttribute('title')).toMatch(/not a Bonde number/);
  });

  it('explains an empty Pivots section instead of looking broken', async () => {
    draw(payload());
    expect(await screen.findByText(/Pivots are paused/)).toBeInTheDocument();
    expect(screen.getByText(/market in correction/)).toBeInTheDocument();
    expect(screen.getByText(/none — the scanners are paused/)).toBeInTheDocument();
  });

  it('NEGATIVE — says nothing about pausing when the scanners are running', async () => {
    draw(payload({ regime: { is_bull: true, label: 'confirmed_uptrend', scanners_paused: false } }));
    await screen.findByText(/pass his screen/);
    expect(screen.queryByText(/Pivots are paused/)).not.toBeInTheDocument();
  });

  it('the NEW filter narrows to arrivals and says so when there are none', async () => {
    draw(payload({ sections: { pivot: [], strong: [], steady: [],
      explosive: [row('AAA'), row('BBB', { is_new: true })] }, n_new: 1 }));
    await screen.findByText('AAA');
    fireEvent.click(screen.getByLabelText(/new arrivals only/i));
    await waitFor(() => expect(screen.queryByText('AAA')).not.toBeInTheDocument());
    expect(screen.getByText('BBB')).toBeInTheDocument();
    expect(screen.getAllByText(/no new arrivals in this tier/).length).toBeGreaterThan(0);
  });

  it('badges an arrival and says WHEN in the tooltip', async () => {
    draw(payload({ sections: { pivot: [], strong: [], steady: [],
      explosive: [row('CCC', { is_new: true, first_seen: '2026-09-10T12:00:00Z' })] } }));
    const badge = await screen.findByText('✨ NEW');
    expect(badge.getAttribute('title')).toMatch(/2026-09-10/);
  });

  it('shows the section total when the cap is hiding rows', async () => {
    draw(payload({ sections: { pivot: [], explosive: [], strong: [], steady: [row('DDD')] },
                   counts: { pivot: 0, explosive: 0, strong: 0, steady: 677 } }));
    expect(await screen.findByText(/1 of 677/)).toBeInTheDocument();
  });

  it('NEGATIVE — a failed fetch shows an error, not an empty board', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503 } as any)));
    render(<MemoryRouter><BondeBoard /></MemoryRouter>);
    expect(await screen.findByText(/⛔/)).toBeInTheDocument();
  });
});

describe('the verdict banner', () => {
  it('renders FIRST, above the counts, with the served numbers', async () => {
    // The tab shipped on a thesis that came back inverted. A reader who meets
    // the rows first has already read them as a buy list.
    const { container } = draw(payload());
    await screen.findByText(/OWN THESIS IS INVERTED/);
    expect(screen.getByText(/STUDY BOARD, NOT A BUY LIST/)).toBeTruthy();
    expect(screen.getByText(/−3\.11pp/)).toBeTruthy();
    expect(screen.getByText(/−0\.11% \(49\.6%\)/)).toBeTruthy();   // the placebo
    expect(screen.getByText(/backend\/scripts\/bonde_audit\//)).toBeTruthy();

    const wrap = container.querySelector('.bd-wrap')!;
    const verdict = wrap.querySelector('.bd-verdict')!;
    const head = wrap.querySelector('.bd-head')!;
    expect(verdict.compareDocumentPosition(head) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
  });

  it('NEGATIVE — nothing in the banner is typed in the component', async () => {
    // Every figure comes from the server (sepa/bonde.py::MEASURED). Hand the
    // component a payload with no `measured` and the banner must VANISH rather
    // than fall back to a hard-coded sentence that can silently go stale.
    const { container } = draw(payload({ measured: undefined }));
    await waitFor(() => expect(container.querySelector('.bd-stats')).toBeTruthy());
    expect(container.querySelector('.bd-verdict')).toBeNull();
    expect(screen.queryByText(/THESIS IS INVERTED/)).toBeNull();
  });

  it('NEGATIVE — it does not read as a short signal', async () => {
    const { container } = draw(payload());
    await screen.findByText(/MEAN is −2\.18%/);
    const dim = [...container.querySelectorAll('.bd-verdict p.bd-vdim')]
      .map((p) => p.textContent || '');
    expect(dim.some((t) => /MEAN is −2\.18% with a CI that includes zero/.test(t))).toBe(true);
  });
});

describe('🔎 the cohort his gate rejects', () => {
  const rej = row('AAON', { tier: 'steady', growth_yoy_pct: 18, accelerating: false,
                            consecutive_growth_q: 1, is_new: false });

  it('is its own section, LAST, and says it is not on his screen', async () => {
    const { container } = draw(payload({
      sections: { pivot: [], explosive: [row('PTGX')], strong: [], steady: [], rejected: [rej] },
    }));
    await screen.findByText(/Cleared his floor, rejected for character/);
    expect(screen.getByText(/NOT ON HIS SCREEN/)).toBeTruthy();
    // the measured reason it is shown at all, with its placebo
    const blurb = [...container.querySelectorAll('.bd-blurb')]
      .map((p) => p.textContent || '')
      .find((t) => t.includes('NOT ON HIS SCREEN'))!;
    expect(blurb).toMatch(/56\.8% of the next 21 sessions against 51\.2%/);
    expect(blurb).toMatch(/\+5\.64pp, CI \+3\.91 to \+7\.52/);
    // ...and its caveat travels with it
    expect(blurb).toMatch(/does not survive date clustering at 21 days/);

    const heads = [...container.querySelectorAll('.bd-h')].map((h) => h.textContent || '');
    expect(heads[heads.length - 1]).toMatch(/Cleared his floor/);
  });

  it('counts the rejected cohort beside the pass count', async () => {
    draw(payload());
    await screen.findByText(/floor-clearers rejected/);
    expect(screen.getByText('120')).toBeTruthy();
  });

  it('NEGATIVE — the ✨ NEW filter explains why this section empties', async () => {
    // "arrived on his screen" cannot describe a name that is not on it, so the
    // generic "no new arrivals in this tier" would be a wrong explanation.
    draw(payload({
      sections: { pivot: [], explosive: [row('PTGX')], strong: [], steady: [], rejected: [rej] },
    }));
    await screen.findByText(/Cleared his floor/);
    fireEvent.click(screen.getByLabelText(/new arrivals only/i));
    await waitFor(() =>
      expect(screen.getByText(/never lights here — these names are not on his screen/)).toBeTruthy());
  });
});

describe('the tier blurbs carry their own measurement', () => {
  it('each tier prints a median lift with a CI that includes zero', async () => {
    const r = draw(payload({
      sections: { pivot: [], explosive: [row('PTGX')], strong: [row('MU', { tier: 'strong' })], steady: [], rejected: [] },
    }));
    const { container } = r;
    await screen.findByText(/Explosive · sales \+100%/);
    const blurbs = [...container.querySelectorAll('.bd-blurb')].map((p) => p.textContent || '');
    expect(blurbs.some((b) => /\+0\.45pp at 21 days, CI −0\.31 to \+1\.36 — it includes zero/.test(b))).toBe(true);
    expect(blurbs.some((b) => /\+0\.37pp at 21 days, CI −0\.16 to \+0\.78/.test(b))).toBe(true);
  });

  it('NEGATIVE — the ⚡ Pivots blurb no longer calls itself the selection', async () => {
    draw(payload());
    await screen.findByText(/Episodic Pivots/);
    const blurbs = [...document.querySelectorAll('.bd-blurb')].map((p) => p.textContent || '');
    const pivot = blurbs.find((b) => b.includes('gapping hard'))!;
    expect(pivot).toMatch(/measured INVERTED/);
    expect(pivot).not.toMatch(/only part of this board that is a selection/);
    expect(pivot).toMatch(/not because anything measured says to buy them/);
  });
});

/* 🎯 headers + demand proximity (Ajay 2026-09-14: "Can you add headers. also
 * sort this by the ones close to demand zone. or give a check box to filter
 * ones closer to demand zones or in the demand zone"). The read is the shared
 * bounce-room POST; the board never computes a band. */
const demand = (lo: number, hi: number, print: number, touches = 2) => {
  const inBand = lo <= print && print <= hi;
  const distance_pct = inBand ? 0 : Math.round(((print - hi) / print) * 10000) / 100;
  return { lo, hi, touches, in_band: inBand, distance_pct, near: inBand || distance_pct <= 2 };
};
const roomPayload = (rows: Record<string, any>, over: Partial<any> = {}) => ({
  as_of: '2026-09-14T11:00:00-04:00', in_session: true, store_date: '2026-09-13',
  params: { touch_tol_pct: 1, wick_pct: 1.5, bounce_min_pct: 3, strong_pct: 5, lookback_sessions: 5,
            near_pct: 2, demand_near_pct: 2, stale_print_sec: 180, new_high_tol: 0.98 },
  rows, requested: Object.keys(rows).length, covered: Object.keys(rows).length, pending: 0, unavailable: 0,
  disclaimer: 'not advice', ...over,
});
const drawWithRoom = (d: BondeBoardData, room: any) => {
  const spy = vi.fn(async (url: string, _init?: RequestInit) => {
    const u = String(url);
    if (u.includes('/supply-demand/bounce-room')) return { ok: true, status: 200, json: async () => room } as any;
    return { ok: true, status: 200, json: async () => d } as any;
  });
  vi.stubGlobal('fetch', spy);
  render(<MemoryRouter><BondeBoard /></MemoryRouter>);
  return spy;
};
const FOUR = { sections: { pivot: [], strong: [], steady: [], rejected: [],
  explosive: [row('PTGX'), row('LQDA'), row('ONDS'), row('UMAC')] } };
const ROOM = roomPayload({
  PTGX: { symbol: 'PTGX', coverage: 'store', print: 100, fresh: true, bounce: null, room: { state: 'CLEAR' },
          demand: demand(80, 90, 100) },                     // 10% above → not near
  LQDA: { symbol: 'LQDA', coverage: 'store', print: 12, fresh: true, bounce: null, room: { state: 'CLEAR' },
          demand: demand(11.5, 12.4, 12) },                  // inside
  ONDS: { symbol: 'ONDS', coverage: 'store', print: 5.1, fresh: true, bounce: null, room: { state: 'CLEAR' },
          demand: demand(4.6, 5.02, 5.1) },                  // 1.57% above → near
  UMAC: { symbol: 'UMAC', coverage: 'pending' },             // no read
});

describe('🎯 headers and the demand-band filter', () => {
  it('every section with rows carries a header row over the five columns', async () => {
    drawWithRoom(payload(FOUR), ROOM);
    await screen.findByText('PTGX');
    for (const h of ['Ticker', 'Sales YoY · base → latest', 'Character', 'Episodic pivot',
                     'Shares YoY', 'Cash − debt', 'EV / sales', 'FCF yield']) {
      expect(screen.getByText(h)).toBeInTheDocument();
    }
    // the heads sit in the SAME grid as a row, so they align with the cells
    expect(screen.getByText('Ticker').closest('.bd-row')).toHaveClass('bd-hdr');
    expect(screen.getByText('Shares YoY').closest('.bd-metrics')).not.toBeNull();
  });

  it('asks the shared read for every row once, and prints the served near distance', async () => {
    const spy = drawWithRoom(payload(FOUR), ROOM);
    await screen.findByText('PTGX');
    await waitFor(() => expect(screen.getByLabelText(/in \/ near a demand band only/i)).toBeInTheDocument());
    const posts = spy.mock.calls.filter((c) => String(c[0]).includes('/supply-demand/bounce-room'));
    expect(posts.length).toBe(1);
    expect(JSON.parse(String((posts[0][1] as any).body)).symbols).toEqual(['LQDA', 'ONDS', 'PTGX', 'UMAC']);
    await waitFor(() => expect(screen.getByText(/≤ 2% above/)).toBeInTheDocument());
  });

  it('the checkbox keeps in-band and near rows, NEAREST FIRST, and drops the rest', async () => {
    drawWithRoom(payload(FOUR), ROOM);
    await screen.findByText('PTGX');
    await waitFor(() => expect(screen.getByText('🎯 in demand band')).toBeInTheDocument());
    // served order first
    const before = screen.getAllByText(/^(PTGX|LQDA|ONDS|UMAC)$/).map((el) => el.textContent);
    expect(before).toEqual(['PTGX', 'LQDA', 'ONDS', 'UMAC']);
    fireEvent.click(screen.getByLabelText(/in \/ near a demand band only/i));
    await waitFor(() => expect(screen.queryByText('PTGX')).not.toBeInTheDocument());
    expect(screen.queryByText('UMAC')).not.toBeInTheDocument();
    const after = screen.getAllByText(/^(PTGX|LQDA|ONDS|UMAC)$/).map((el) => el.textContent);
    expect(after).toEqual(['LQDA', 'ONDS']);
    expect(screen.getByText(/band read on 3 of 4/)).toBeInTheDocument();
  });

  it('a qualifying row wears the 🎯 chip with the band, touches and store date in the tooltip', async () => {
    drawWithRoom(payload(FOUR), ROOM);
    const chip = await screen.findByText('🎯 in demand band');
    expect(chip.getAttribute('title')).toMatch(/11\.5–12\.4/);
    expect(chip.getAttribute('title')).toMatch(/2× tested/);
    expect(chip.getAttribute('title')).toMatch(/2026-09-13/);
    expect(chip.getAttribute('title')).toMatch(/Not a buy signal/);
    expect(screen.getByText('🎯 1.6% above demand')).toBeInTheDocument();
  });

  it('NEGATIVE — a name 10% above its band gets no chip, and a pending name gets none either', async () => {
    drawWithRoom(payload(FOUR), ROOM);
    await screen.findByText('🎯 in demand band');
    expect(document.querySelectorAll('.bd-dchip').length).toBe(2);
    // PTGX's row exists but wears no 🎯
    expect(screen.getByText('PTGX').closest('.bd-row')!.textContent).not.toMatch(/🎯/);
    expect(screen.getByText('UMAC').closest('.bd-row')!.textContent).not.toMatch(/🎯/);
  });

  it('NEGATIVE — with the box on and nothing qualifying, the section SAYS so rather than looking empty', async () => {
    drawWithRoom(payload({ sections: { pivot: [], strong: [], steady: [], rejected: [], explosive: [row('PTGX')] } }),
                 roomPayload({ PTGX: { symbol: 'PTGX', coverage: 'store', print: 100, fresh: true, bounce: null,
                                       room: { state: 'CLEAR' }, demand: demand(80, 90, 100) } }));
    await screen.findByText('PTGX');
    fireEvent.click(screen.getByLabelText(/in \/ near a demand band only/i));
    await waitFor(() => expect(screen.getByText(/none in or near a demand band right now/)).toBeInTheDocument());
  });

  it('NEGATIVE — the near distance is never typed in the component: no params, no number', async () => {
    drawWithRoom(payload(FOUR), roomPayload({}, { params: {} }));
    await screen.findByText('PTGX');
    const label = screen.getByLabelText(/in \/ near a demand band only/i).closest('label')!;
    expect(label.textContent).not.toMatch(/2%/);
    expect(label.textContent).not.toMatch(/≤/);
  });

  it('NEGATIVE — a failed band read leaves the board drawn and says the read failed when the box is on', async () => {
    const spy = vi.fn(async (url: string) => {
      const u = String(url);
      if (u.includes('/supply-demand/bounce-room')) return { ok: false, status: 503, json: async () => ({}) } as any;
      return { ok: true, status: 200, json: async () => payload(FOUR) } as any;
    });
    vi.stubGlobal('fetch', spy);
    render(<MemoryRouter><BondeBoard /></MemoryRouter>);
    await screen.findByText('PTGX');
    fireEvent.click(screen.getByLabelText(/in \/ near a demand band only/i));
    await waitFor(() => expect(screen.getByText(/read failed: HTTP 503/)).toBeInTheDocument());
  });
});


/* 🎯 ENTERABLE on a row board (2026-09-15). Ajay: "I do not want to see not
 * enterable alerts or stocks in any of the chart maps."
 *
 * Bonde is the hardest case on purpose: it already has TWO row filters (✨ new
 * arrivals, 🎯 in/near a demand band) and his own sections, so the pins here
 * are that the enterable cut COMPOSES with them, never merges the sections, and
 * reports only what IT removed — otherwise an empty section sends him looking
 * at the wrong checkbox. Mounted standalone (this file's other tests) there is
 * no provider and the board is unchanged, which is the §7.8 default.
 */
const enterable = (verdict: string | null, short: string[] = [], text: string[] = []) => ({
  kind: 'demand', verdict, reasons: short, reason_short: short, reason_text: text,
  measured: { status: 'pending' },
});
const ROOM_ENTERABLE = roomPayload({
  PTGX: { symbol: 'PTGX', coverage: 'store', print: 100, fresh: true, bounce: null, room: { state: 'CLEAR' },
          demand: demand(80, 90, 100),
          enterable: enterable('BLOCKED', ['not at band'], ['The print sits more than 1.0% above the band top.']) },
  LQDA: { symbol: 'LQDA', coverage: 'store', print: 12, fresh: true, bounce: null, room: { state: 'CLEAR' },
          demand: demand(11.5, 12.4, 12),
          enterable: enterable('WATCH', ['reclaim from below'], ['Reclaiming the band from below — 66% hit the floor stop.']) },
  ONDS: { symbol: 'ONDS', coverage: 'store', print: 5.1, fresh: true, bounce: null, room: { state: 'CLEAR' },
          demand: demand(4.6, 5.02, 5.1), enterable: enterable('READY') },
  UMAC: { symbol: 'UMAC', coverage: 'pending' },   // no read at all
});

const drawFiltered = (d: BondeBoardData, room: any, opts: { on?: boolean; kind?: string } = {}) => {
  const spy = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/supply-demand/bounce-room')) return { ok: true, status: 200, json: async () => room } as any;
    return { ok: true, status: 200, json: async () => d } as any;
  });
  vi.stubGlobal('fetch', spy);
  const set = vi.fn();
  render(
    <MemoryRouter>
      <EnterableFilterProvider enterableOnly={opts.on ?? true} kind={opts.kind ?? 'demand'}
                               setEnterableOnly={set}>
        <BondeBoard />
      </EnterableFilterProvider>
    </MemoryRouter>);
  return set;
};

describe('📈 Bonde — the 🎯 enterable cut', () => {
  it('hides the BLOCKED row, keeps WATCH and READY, and names the served reason', async () => {
    drawFiltered(payload(FOUR), ROOM_ENTERABLE);
    await screen.findByText('ONDS');
    await waitFor(() => expect(screen.queryByText('PTGX')).not.toBeInTheDocument());
    expect(screen.getByText('LQDA')).toBeInTheDocument();
    expect(screen.getByText('🎯 WATCH · reclaim from below')).toBeInTheDocument();
    expect(screen.getByText('🎯 READY')).toBeInTheDocument();
    const line = screen.getByText(/hidden/).closest('.cm-hidden-count') as HTMLElement;
    expect(line.textContent).toMatch(/1 hidden \(1 not at band\)/);
  });

  it('a row the server has no read for STAYS and is counted separately', async () => {
    drawFiltered(payload(FOUR), ROOM_ENTERABLE);
    expect(await screen.findByText('UMAC')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/without a read/).textContent)
      .toMatch(/1 without a read \(shown last\)/));
  });

  it('composes with the 🎯 in/near-demand box — the count reports only the ENTERABLE cut', async () => {
    drawFiltered(payload(FOUR), ROOM_ENTERABLE);
    await screen.findByText('ONDS');
    await waitFor(() => expect(screen.getByLabelText(/in \/ near a demand band only/i)).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText(/in \/ near a demand band only/i));
    // PTGX (10% above) is gone on the proximity box; LQDA and ONDS stay.
    await waitFor(() => expect(screen.queryByText('UMAC')).not.toBeInTheDocument());
    expect(screen.getByText('LQDA')).toBeInTheDocument();
    // …and the enterable line now reports ZERO, because the proximity box had
    // already taken the only BLOCKED row. The other box is what emptied it.
    const line = screen.getByText(/hidden/).closest('.cm-hidden-count') as HTMLElement;
    expect(line.textContent).toMatch(/^0 hidden/);
  });

  it('NEGATIVE: the filter OFF changes nothing and prints no count line', async () => {
    drawFiltered(payload(FOUR), ROOM_ENTERABLE, { on: false });
    await screen.findByText('PTGX');
    expect(screen.getByText('LQDA')).toBeInTheDocument();
    expect(screen.getByText('UMAC')).toBeInTheDocument();
    expect(screen.queryByText(/hidden/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: kind n/a is inert — every row stays even with the box ticked', async () => {
    drawFiltered(payload(FOUR), ROOM_ENTERABLE, { kind: 'n/a' });
    await screen.findByText('PTGX');
    expect(screen.getByText('LQDA')).toBeInTheDocument();
    expect(screen.getByText('UMAC')).toBeInTheDocument();
  });

  it('NEGATIVE: a legacy payload with no enterable key at all hides nothing', async () => {
    drawFiltered(payload(FOUR), ROOM);
    await screen.findByText('PTGX');
    await waitFor(() => expect(screen.getByText(/without a read/).textContent)
      .toMatch(/4 without a read/));
    expect(screen.getByText(/hidden/).closest('.cm-hidden-count')!.textContent).toMatch(/^0 hidden/);
  });
});


/* 🪜 BAND STRUCTURE on a ROW board (2026-09-16).
 *
 * Ajay 2026-09-16: "Now in all chartmaps tabs, can you prioritize stock by the
 * thinnest over head or Supply zone where ever is applicable" — Bonde is one of
 * the ten row boards that carried NOTHING before this: no chip, and no line
 * saying why, unlike the six `n/a` tabs which say so out loud.
 *
 * Everything the chip prints is SERVED (`row.band_structure.stat`). The board
 * formats nothing, so the only things worth pinning are that the read arrives,
 * that a row WITHOUT one shows nothing, and that a board where NOTHING came
 * back says so instead of going quiet.
 */
const bandRead = (stat: string) => ({
  symbol: 'X', kind: 'demand', applicable: true, score: null, na_text: null, stat,
  ceiling: { state: 'ROOM', height_pct: 3.4, distance_pct: 18.9 },
  floor: { height_pct: 3.5, gap_pct: 6.4, bands_below: 2 },
  measured: { status: 'pending', run_date: null, n_episodes: null, oos_lift: null, oos_ci: null, mdl: null },
});
const BAND_STUDY = { headline: 'MEASURED: pending — ordered by ceiling thickness', body: null,
                     fallback_note: 'descriptive ordering', limits: null };

describe('🪜 Bonde — the served band-structure read', () => {
  it('a row WITH a served read shows the chip, printing the served sentence verbatim', async () => {
    drawWithRoom(payload(FOUR), roomPayload({
      ...ROOM.rows,
      PTGX: { ...ROOM.rows.PTGX,
              band_structure: bandRead('ceiling 3.4% wide, 18.9% up · floor 3.5% wide, 2nd band 6.4% under') },
    }, { band_structure_study: BAND_STUDY,
         band_structure_coverage: { rows_with_read: 1, rows_without_read: 3, note: null } }));
    await screen.findByText('PTGX');
    const chip = await screen.findByText(
      /🪜 ceiling 3\.4% wide, 18\.9% up · floor 3\.5% wide, 2nd band 6\.4% under/);
    expect(chip).toBeInTheDocument();
    // muted while the study is pending — it is descriptive, never a grade
    expect(chip).toHaveClass('cm-badge-band-muted');
    expect(chip.getAttribute('title')).toMatch(/MEASURED: pending/);
  });

  it('NEGATIVE: a row with NO read shows no chip, and no figure is invented for it', async () => {
    drawWithRoom(payload(FOUR), roomPayload({
      ...ROOM.rows,
      PTGX: { ...ROOM.rows.PTGX, band_structure: bandRead('ceiling 3.4% wide, 18.9% up') },
      LQDA: { ...ROOM.rows.LQDA, band_structure: null },
    }, { band_structure_study: BAND_STUDY,
         band_structure_coverage: { rows_with_read: 1, rows_without_read: 3, note: null } }));
    await screen.findByText('LQDA');
    await waitFor(() => expect(screen.getAllByText(/🪜/)).toHaveLength(1));
    expect(screen.queryByTestId('band-structure-note')).not.toBeInTheDocument();
  });

  it('NEGATIVE: when NO row has a read the board prints the SERVED reason, not silence', async () => {
    drawWithRoom(payload(FOUR), roomPayload(ROOM.rows, {
      band_structure_study: BAND_STUDY,
      band_structure_coverage: { rows_with_read: 0, rows_without_read: 4,
                                 note: 'No band read for these names — no ceiling or floor to show on this board.' },
    }));
    await screen.findByText('PTGX');
    const note = await screen.findByTestId('band-structure-note');
    expect(note.textContent).toMatch(/No band read for these names/);
    expect(screen.queryByText(/🪜 ceiling/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: a legacy payload with no band fields at all does not crash the board', async () => {
    drawWithRoom(payload(FOUR), roomPayload(ROOM.rows));
    expect(await screen.findByText('PTGX')).toBeInTheDocument();
    expect(screen.queryByTestId('band-structure-note')).not.toBeInTheDocument();
    expect(screen.queryByText(/🪜/)).not.toBeInTheDocument();
  });
});
