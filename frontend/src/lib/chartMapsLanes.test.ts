/* chartMapsLanes — pure helpers behind the 🗺️ Chart Maps strategies tab
 * (2026-09-27). A real-money trader reads these numbers to decide which
 * strategies to keep, so every formatter is pinned with its negatives: a null
 * CI prints "—" (never NaN, never "[null, null]"), a win-rate CI served as a
 * fraction prints as percent, the skip list is ordered by count, the prior
 * chip says MEASURED / UNMEASURED in words, an unknown sid never crashes, and
 * nothing he reads says "bounce". */
import { describe, it, expect } from 'vitest';
import {
  ageText, approxText, buyingNowText, capsLine, exitsSplit, expRText, fmtCi, fmtR, fmtUsd, laneLabel, lastTradeText,
  minuteText, openLine, priorText, proposalChange, sayReversal, staleText, topSkips, winCiPct, winText,
  isOpenProposal,
  type CmScoreboard, type CmStrategyRow,
} from './chartMapsLanes';

const SB: CmScoreboard = {
  n_closed: 5, n_open: 1, wins: 2, losses: 3, win_pct: 40, win_ci: [0.118, 0.769], exp_r: -0.21, exp_r_ci: [-0.83, 0.44],
  total_usd: -142.3, open_risk_usd: 88.1, n_approx: 2, n_unpriced: 1,
  exits_by_kind: { stop: 2, distribution_exit: 2, take_profit: 1, watchdog_exit: 0 },
  last_trade: { symbol: 'CTOS', exit_ts: '2026-09-25T15:02:00-04:00', r: -0.92 }, small_n: true, measured: false,
};

describe('CI + scoreboard text', () => {
  it('a null / half / short CI → "—" (negative)', () => {
    const f = (v: number) => v.toFixed(1);
    expect(fmtCi(null, f)).toBe('—');
    expect(fmtCi(undefined, f)).toBe('—');
    expect(fmtCi([null, null], f)).toBe('—');
    expect(fmtCi([0.1, null], f)).toBe('—');
    expect(fmtCi([1, 2], f)).toBe('[1.0, 2.0]');
  });

  it('reads a Wilson fraction CI as percent; a percent CI is left alone', () => {
    expect(winCiPct([0.118, 0.769])).toEqual([11.8, 76.9]);
    expect(winCiPct([12, 77])).toEqual([12, 77]);
    expect(winCiPct(null)).toBeNull();
    expect(winCiPct([null, 0.5])).toEqual([null, null]);
  });

  it('win % and exp R print with their CIs; nothing closed → "—" (negative: never 0%)', () => {
    expect(winText(SB)).toBe('40% [12%, 77%]');
    expect(expRText(SB)).toBe('−0.21R [−0.83R, +0.44R]');
    expect(winText({ ...SB, n_closed: 0, win_pct: 0 })).toBe('—');
    expect(expRText({ n_closed: 0 })).toBe('—');
    expect(winText(null)).toBe('—');
    expect(winText({ n_closed: 3, win_pct: 33.3, win_ci: [null, null] })).toBe('33% —');
  });

  it('formatters never print NaN', () => {
    for (const v of [null, undefined, NaN, 'x']) {
      expect(fmtR(v)).toBe('—');
      expect(fmtUsd(v)).toBe('—');
    }
    expect(fmtUsd(-142.3)).toBe('−$142');
    expect(fmtUsd(88.1, false)).toBe('$88');
  });

  it('"≈ N approx" only when some exits were priced at the tick last', () => {
    expect(approxText(SB)).toBe('≈ 2 approx');
    expect(approxText({ n_approx: 0 })).toBeNull();
    expect(approxText(null)).toBeNull();
  });

  it('the exits split names the SEPA sell and drops zero kinds', () => {
    expect(exitsSplit(SB.exits_by_kind)).toBe('SEPA sell 2 · stop 2 · target 1');
    expect(exitsSplit({})).toBe('—');
    expect(exitsSplit(null)).toBe('—');
    expect(exitsSplit({ odd_kind: 1 })).toBe('odd kind 1');
  });

  it('last trade reads a string or an object', () => {
    expect(lastTradeText(SB.last_trade)).toBe('CTOS 2026-09-25 −0.92R');
    expect(lastTradeText('2026-09-25')).toBe('2026-09-25');
    expect(lastTradeText(null)).toBe('—');
    expect(lastTradeText({})).toBe('—');
  });
});

describe('skips, priors, labels, wording', () => {
  it('top skip reasons by count, ties by reason, zeros dropped', () => {
    expect(topSkips({ a: 1, 'program-cap: zones daily cap 1 reached': 3, b: 1, c: 0, d: 2 })).toEqual([
      ['program-cap: zones daily cap 1 reached', 3], ['d', 2], ['a', 1],
    ]);
    expect(topSkips(null)).toEqual([]);
  });

  it('prior chip in words', () => {
    expect(priorText({ status: 'inverted' })).toBe('MEASURED INVERTED');
    expect(priorText({ status: 'null' })).toBe('MEASURED null');
    expect(priorText({ status: 'no_signal' })).toBe('MEASURED no signal');
    expect(priorText({ status: 'unmeasured' })).toBe('UNMEASURED');
    expect(priorText(null)).toBe('UNMEASURED');
    expect(priorText({ status: 'weird' })).toBe('WEIRD');
  });

  it('labels come from TAB_META; an unknown sid is echoed, never a crash (negative)', () => {
    expect(laneLabel('deep_demand')).toBe('Deep Demand');
    expect(laneLabel('signals', 'signals')).toMatch(/Signals/);
    expect(laneLabel('mystery_lane')).toBe('mystery lane');
    expect(laneLabel(null)).toBe('?');
  });

  it('NEGATIVE: the quick_bounce sid is never printed as "bounce"', () => {
    expect(laneLabel('quick_bounce')).not.toMatch(/bounc/i);
    expect(sayReversal('program-cap: quick_bounce daily cap 1 reached')).toBe('program-cap: Quick Reversal daily cap 1 reached');
    expect(sayReversal(null)).toBe('');
  });

  it('stale flag carries the served reason; a fresh snapshot has none', () => {
    expect(staleText({ stale: true, stale_reason: 'stale board (build time unknown)' })).toBe('stale — stale board (build time unknown)');
    expect(staleText({ stale: true })).toBe('stale');
    expect(staleText({ stale: false, stale_reason: null })).toBeNull();
    expect(staleText(null)).toBeNull();
    expect(ageText(45)).toBe('45s old');
    expect(ageText(600)).toBe('10m old');
    expect(ageText(null)).toBe('—');
  });
});

describe('program header text', () => {
  const caps = { risk_pct: 0.25, per_strategy_per_day: 1, per_strategy_open: 2, max_open: 15, one_entry_per_minute: true, gross_pct: 100, options_risk_pct: 0.25 };
  it('the caps line is built from the served caps', () => {
    expect(capsLine(caps)).toBe('0.25% risk a trade · 1 a day and 2 open per strategy · 15 open in all · 1 buy a minute · gross ≤ 100% of equity · options 0.25% premium');
    expect(capsLine(null)).toBe('—');
    expect(capsLine({})).toBe('—');
  });
  it('"N / 15 (P pending)" — pending may be a count or a list', () => {
    expect(openLine({ caps, open: { n: 6, positions: 5, pending: 1 } })).toBe('6 / 15 open (1 pending)');
    expect(openLine({ caps, open: { positions: ['A', 'B'], pending: ['C'] } })).toBe('3 / 15 open (1 pending)');
    expect(openLine(null)).toBe('0 / — open (0 pending)');
  });
  it('this minute: free, or the lane + symbol that took it', () => {
    expect(minuteText(null)).toBe('free');
    expect(minuteText({ key: '2026-09-28T09:31' })).toBe('free');
    expect(minuteText({ sid: 'amd', symbol: 'ORCL', at: '2026-09-28T13:31:45Z' })).toBe('🌀 AMD Raided ORCL at 09:31 ET');
    expect(minuteText(null, 'none yet')).toBe('none yet');
  });
});

describe('proposal before → after', () => {
  const rows: CmStrategyRow[] = [{ sid: 'amd', enabled: true }];
  it('a cm_lanes pause reads "before" off the strategy row', () => {
    const p = { id: 'a1', level: 'config', change: { key: 'cm_lanes', value: { amd: false } } };
    expect(proposalChange(p, rows)).toEqual({ key: 'cm_lanes', before: '{"amd":true}', after: '{"amd":false}' });
  });
  it('a served before wins; nothing known → "current"', () => {
    expect(proposalChange({ id: 'b', change: { key: 'zone_edge_rules', value: { min_touches: 2 }, before: { min_touches: 1 } } }, rows))
      .toEqual({ key: 'zone_edge_rules', before: '{"min_touches":1}', after: '{"min_touches":2}' });
    expect(proposalChange({ id: 'c', level: 'code', change: null }, rows)).toEqual({ key: '—', before: 'current', after: 'current' });
  });
  it('only a "proposed" (or status-less) card is open', () => {
    expect(isOpenProposal({ id: 'x', status: 'proposed' })).toBe(true);
    expect(isOpenProposal({ id: 'x' })).toBe(true);
    expect(isOpenProposal({ id: 'x', status: 'dismissed' })).toBe(false);
    expect(isOpenProposal({ id: 'x', status: 'todo' })).toBe(false);
  });
});

describe('switch vs buying now (fix round 2026-09-27)', () => {
  it('program OFF: an existing lane whose switch is OFF still buys on its own lane switch', () => {
    expect(buyingNowText({ enabled: false, buying_now: true })).toBe('buying now on its own lane switch (program OFF)');
  });
  it('program OFF: a row switched ON waits for the program', () => {
    expect(buyingNowText({ enabled: true, buying_now: false })).toBe('not buying until the program is ON');
  });
  it('NEGATIVE: no line when they agree, or when buying_now is not served', () => {
    expect(buyingNowText({ enabled: true, buying_now: true })).toBeNull();
    expect(buyingNowText({ enabled: false, buying_now: false })).toBeNull();
    expect(buyingNowText({ enabled: true })).toBeNull();
    expect(buyingNowText({ enabled: true, buying_now: null })).toBeNull();
  });
});
