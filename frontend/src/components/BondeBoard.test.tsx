import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BondeBoard, { type BondeBoardData } from './BondeBoard';
import { CM_TABS, TAB_META, isBoardTab, parseTab } from '../lib/chartMaps';

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

beforeEach(() => vi.unstubAllGlobals());

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
