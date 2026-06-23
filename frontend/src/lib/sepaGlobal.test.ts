import { describe, it, expect } from 'vitest';
import {
  toGlobalCard, strengthOf, isAvoid, filterForTab, byConviction,
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
