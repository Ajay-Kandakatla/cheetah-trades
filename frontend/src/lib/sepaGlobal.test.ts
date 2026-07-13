import { describe, it, expect } from 'vitest';
import {
  toGlobalCard, toGlobalDetail, strengthOf, isAvoid, filterForTab, byConviction,
} from './sepaGlobal';
import type { SepaCandidate } from '../hooks/useSepa';

/* SEPA Global relabels the scanner's OWN gates (is_buyable / setup_ready /
   climax-distribution / conviction) into a plain-English, risk-first card.
   These lock the verdict mapping + the risk math + the tab filters. */

function row(o: Partial<SepaCandidate>): SepaCandidate {
  return {
    symbol: 'TST', name: 'Test Co', last_close: 100, day_change_pct: 1.2,
    is_candidate: true, ...o,
  } as unknown as SepaCandidate;
}

describe('toGlobalCard — verdict mapping (same gates, plain words)', () => {
  it('buyable → green "Buy zone"', () => {
    const c = toGlobalCard(row({ is_buyable: true, conviction: 80,
      trade_plan: { buy_zone: { lo: 100, hi: 103 }, stop: { recommended: 93, risk_pct: 7 } } as any }));
    expect(c.verdict).toBe('buy');
    expect(c.tone).toBe('green');
    expect(c.buyZone).toEqual({ lo: 100, hi: 103 });
    expect(c.sellIf).toBe(93);
    expect(c.riskPct).toBe(7);
  });

  it('setup_ready but not buyable → amber "Watch"', () => {
    const c = toGlobalCard(row({ setup_ready: true, is_buyable: false, conviction: 50 }));
    expect(c.verdict).toBe('watch');
    expect(c.tone).toBe('amber');
  });

  it('a qualifier with no setup → slate "Leader"', () => {
    const c = toGlobalCard(row({ is_buyable: false, setup_ready: false, conviction: 60 }));
    expect(c.verdict).toBe('leader');
    expect(c.tone).toBe('slate');
  });

  it('climax / distribution → red "Avoid", even if it looks buyable', () => {
    const c = toGlobalCard(row({ is_buyable: true, distribution_selling: true, conviction: 90 }));
    expect(c.verdict).toBe('avoid');
    expect(c.tone).toBe('red');
  });

  it('entry_exit AVOID also forces red (climax-top)', () => {
    const c = toGlobalCard(row({ is_buyable: true, entry_exit: { decision: 'AVOID' } as any }));
    expect(c.verdict).toBe('avoid');
  });
});

describe('strengthOf — conviction → High/Medium/Low', () => {
  it('maps the bands', () => {
    expect(strengthOf(row({ conviction: 75 }))).toBe('High');
    expect(strengthOf(row({ conviction: 50 }))).toBe('Medium');
    expect(strengthOf(row({ conviction: 20 }))).toBe('Low');
  });
  it('a suppressed (climax/exhaustion) name is always Low — it is a sell', () => {
    expect(strengthOf(row({ conviction: 95, conviction_detail: { suppressed: true } as any }))).toBe('Low');
  });
  it('missing conviction → Low (negative)', () => {
    expect(strengthOf(row({}))).toBe('Low');
  });
});

describe('risk math (negative / fallbacks)', () => {
  it('computes risk % from buy zone and stop when risk_pct is absent', () => {
    const c = toGlobalCard(row({ is_buyable: true,
      trade_plan: { buy_zone: { lo: 100, hi: 102 }, stop: { recommended: 92 } } as any }));
    expect(c.riskPct).toBe(8);    // (100 - 92) / 100
  });
  it('leaves buyZone/sellIf/riskPct null when there is no plan', () => {
    const c = toGlobalCard(row({ is_buyable: true }));
    expect(c.buyZone).toBeNull();
    expect(c.sellIf).toBeNull();
    expect(c.riskPct).toBeNull();
  });
  it('never crashes on a bare row and always returns a verdict', () => {
    const c = toGlobalCard({ symbol: 'X' } as any);
    expect(c.verdict).toBe('leader');
    expect(c.price).toBeNull();
  });
});

describe('live price override', () => {
  it('uses the live quote over the scan close and flags isLive', () => {
    const c = toGlobalCard(row({ last_close: 100, day_change_pct: 1 }), { price: 104.2, change_pct: 4.2 });
    expect(c.price).toBe(104.2);
    expect(c.dayChangePct).toBe(4.2);
    expect(c.isLive).toBe(true);
  });
  it('falls back to the scan close when no live quote (isLive false)', () => {
    const c = toGlobalCard(row({ last_close: 100 }));
    expect(c.price).toBe(100);
    expect(c.isLive).toBe(false);
  });
  it('ignores a malformed live quote (no usable price)', () => {
    const c = toGlobalCard(row({ last_close: 100 }), { price: null });
    expect(c.price).toBe(100);
    expect(c.isLive).toBe(false);
  });
});

describe('toGlobalDetail — the click-through detail', () => {
  const r = row({
    is_buyable: true, rs_rank: 92, conviction: 80,
    trend: { pass_all: true } as any,
    volume: { is_drying_up: true } as any,
    trade_plan: {
      buy_zone: { lo: 100, hi: 103 }, stop: { recommended: 93, risk_pct: 7 },
      targets: { r1: 110, r2: 121, reward_to_risk: 2.5 },
    } as any,
  });

  it('adds plain targets with % gain from the buy reference', () => {
    const d = toGlobalDetail(r);
    expect(d.targets).toEqual([
      { label: 'First target', price: 110, pct: 10 },   // (110-100)/100
      { label: 'Second target', price: 121, pct: 21 },
    ]);
  });
  it('carries reward:risk, leadership, trend and volume sentences', () => {
    const d = toGlobalDetail(r);
    expect(d.rewardRisk).toBe(2.5);
    expect(d.leadership).toBe(92);
    expect(d.trendText).toMatch(/confirmed up-trend/i);
    expect(d.volumeText).toMatch(/drying up/i);
  });
  it('degrades cleanly with no plan / no volume (negative)', () => {
    const d = toGlobalDetail(row({ is_buyable: false }));
    expect(d.targets).toEqual([]);
    expect(d.rewardRisk).toBeNull();
    expect(d.volumeText).toBeNull();
    expect(d.trendText).toMatch(/isn’t fully confirmed/i);
  });
});

describe('isAvoid', () => {
  it('flags distribution / climax / AVOID, not a clean name', () => {
    expect(isAvoid(row({ distribution_selling: true }))).toBe(true);
    expect(isAvoid(row({ climax_distribution: { is_distribution: true } } as any))).toBe(true);
    expect(isAvoid(row({ entry_exit: { decision: 'AVOID' } as any }))).toBe(true);
    expect(isAvoid(row({ is_buyable: true }))).toBe(false);
  });
});

describe('filterForTab + byConviction', () => {
  const rows = [
    row({ symbol: 'BUYHI', is_buyable: true, setup_ready: true, conviction: 90 }),
    row({ symbol: 'BUYLO', is_buyable: true, setup_ready: true, conviction: 60 }),
    row({ symbol: 'WATCH', is_buyable: false, setup_ready: true, conviction: 80 }),
    row({ symbol: 'LEAD',  is_buyable: false, setup_ready: false, conviction: 70 }),
  ];

  it('buy tab → only buyable, buyable sorted by conviction', () => {
    const r = filterForTab(rows, 'buy').map((x) => x.symbol);
    expect(r).toEqual(['BUYHI', 'BUYLO']);
  });
  it('watch tab → setup_ready but not buyable', () => {
    expect(filterForTab(rows, 'watch').map((x) => x.symbol)).toEqual(['WATCH']);
  });
  it('leaders tab → every qualifier, buyable first then conviction', () => {
    expect(filterForTab(rows, 'leaders').map((x) => x.symbol))
      .toEqual(['BUYHI', 'BUYLO', 'WATCH', 'LEAD']);
  });
  it('byConviction floats buyable above a higher-conviction non-buyable', () => {
    // WATCH (80, not buyable) must rank BELOW BUYLO (60, buyable).
    const sorted = [...rows].sort(byConviction).map((x) => x.symbol);
    expect(sorted.indexOf('BUYLO')).toBeLessThan(sorted.indexOf('WATCH'));
  });
});

describe('leaky pivot — Buy now demotes to Watch (Minervini X 2026)', () => {
  const leaky = { leaky: true, leaks: 2, last_leak_bars_ago: 2 };
  const quiet = { leaky: false, leaks: 1, last_leak_bars_ago: 7 };

  it('a leaky buyable reads Watch with a hold-above reason', () => {
    const c = toGlobalCard(row({ is_buyable: true, pivot_leakage: leaky, conviction: 80 }));
    expect(c.verdict).toBe('watch');
    expect(c.tone).toBe('amber');
    expect(c.reason).toMatch(/slipping back|HOLDS/);
  });

  it('a quiet-pivot buyable still reads Buy zone; missing field too (old scans)', () => {
    expect(toGlobalCard(row({ is_buyable: true, pivot_leakage: quiet })).verdict).toBe('buy');
    expect(toGlobalCard(row({ is_buyable: true })).verdict).toBe('buy');
    expect(toGlobalCard(row({ is_buyable: true, pivot_leakage: null })).verdict).toBe('buy');
  });

  it('avoid still outranks the leak demotion', () => {
    const c = toGlobalCard(row({ is_buyable: true, pivot_leakage: leaky, distribution_selling: true }));
    expect(c.verdict).toBe('avoid');
  });

  it('filterForTab moves leaky buyables from buy to watch', () => {
    const rows = [
      row({ symbol: 'HOLD', is_buyable: true, is_candidate: true, conviction: 90 }),
      row({ symbol: 'LEAK', is_buyable: true, is_candidate: true, pivot_leakage: leaky, conviction: 95 }),
      row({ symbol: 'BASE', setup_ready: true, is_candidate: true, conviction: 50 }),
    ];
    expect(filterForTab(rows, 'buy').map((r) => r.symbol)).toEqual(['HOLD']);
    expect(filterForTab(rows, 'watch').map((r) => r.symbol)).toEqual(['LEAK', 'BASE']);
    expect(filterForTab(rows, 'leaders')).toHaveLength(3);
  });
});
