/* JournalByStrategy — the Auto-Pilot journal split by entry lane.
 *
 * Ajay 2026-09-05: "Keep the minervini entries but also make sure you have
 * demand zone and catalyst based entries time to time and journal it
 * appropriately." The journal's summary now carries by_strategy; this table
 * is the only place the three lanes are compared side by side, so every
 * number it prints is pinned here with negatives: a lane with no fills says
 * "no trades yet" (never a 0% win rate), an absent block renders all five
 * lanes muted (never a crash), null stats render "—" (never NaN), and a lane
 * the server adds that we do not know still gets a row.
 */
import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import {
  JournalByStrategy, StrategyChip, STRATEGY_ORDER, HONESTY_NOTE, NO_TRADES_TEXT,
  fmtInt, fmtPct, fmtR, fmtMoney, strategyMeta, strategyRows,
} from './JournalByStrategy';
import type { StrategyStats } from './JournalByStrategy';

const FULL: Record<string, StrategyStats> = {
  minervini:   { n: 6, open: 1, closed: 5, wins: 3, losses: 2, win_rate_pct: 60.0, avg_r: 0.42, expectancy_pct: 1.8, realized_pnl: 212.5 },
  demand_zone: { n: 3, open: 2, closed: 1, wins: 0, losses: 1, win_rate_pct: 0.0, avg_r: -1.0, expectancy_pct: -2.4, realized_pnl: -48.2 },
  breakout:    { n: 0, open: 0, closed: 0, wins: 0, losses: 0, win_rate_pct: null, avg_r: null, expectancy_pct: null, realized_pnl: 0 },
  catalyst:    { n: 1, open: 1, closed: 0, wins: 0, losses: 0, win_rate_pct: null, avg_r: null, expectancy_pct: null, realized_pnl: 0 },
  manual:      { n: 2, open: 0, closed: 2, wins: 1, losses: 1, win_rate_pct: 50.0, avg_r: 0.1, expectancy_pct: 0.3, realized_pnl: 12.0 },
};

const rowOf = (label: RegExp) => screen.getByRole('row', { name: label });

describe('JournalByStrategy — rows', () => {
  it('renders one row per lane in the fixed order with every stat', () => {
    render(<JournalByStrategy byStrategy={FULL} />);
    const rows = screen.getAllByRole('row').slice(1);        // drop the header
    expect(rows.map((r) => r.getAttribute('data-strategy'))).toEqual([...STRATEGY_ORDER]);
    const m = rowOf(/Minervini/);
    expect(within(m).getByText('6')).toBeInTheDocument();     // n
    expect(within(m).getByText('60%')).toBeInTheDocument();
    expect(within(m).getByText('+0.42R')).toBeInTheDocument();
    expect(within(m).getByText('+1.8%')).toBeInTheDocument();
    expect(within(m).getByText('+$212.50')).toBeInTheDocument();
    const d = rowOf(/demand zone/);
    expect(within(d).getByText('0%')).toBeInTheDocument();   // 0 of 1 closed IS a rate
    expect(within(d).getByText('-1.00R')).toBeInTheDocument();
    expect(within(d).getByText('-$48.20')).toBeInTheDocument();
  });

  it('a lane with no fills says "no trades yet" — never a 0% win rate (negative)', () => {
    render(<JournalByStrategy byStrategy={FULL} />);
    const b = rowOf(/breakout/);
    expect(within(b).getByText(NO_TRADES_TEXT)).toBeInTheDocument();
    expect(within(b).queryByText('0%')).toBeNull();
    // catalyst has ONE open trade and nothing closed: a row, with "—" for the
    // closed-only stats, not "no trades yet" and not "0%".
    const c = rowOf(/catalyst/);
    expect(within(c).queryByText(NO_TRADES_TEXT)).toBeNull();
    expect(within(c).getAllByText('—').length).toBeGreaterThanOrEqual(3);
    expect(within(c).queryByText('0%')).toBeNull();
  });

  // 2026-10-20: seven lanes (the 🚩 Gajjala lane joined, BUILD_SPEC17 §3.7) — the count is STRATEGY_ORDER's.
  it('an absent by_strategy block renders every lane muted, plus the honesty note (negative)', () => {
    expect(STRATEGY_ORDER).toHaveLength(7);
    render(<JournalByStrategy byStrategy={undefined} />);
    expect(screen.getAllByText(NO_TRADES_TEXT)).toHaveLength(7);
    expect(screen.getByText(HONESTY_NOTE)).toBeInTheDocument();
    render(<JournalByStrategy byStrategy={null} />);
    expect(screen.getAllByText(NO_TRADES_TEXT)).toHaveLength(14);
  });

  it('a lane the server adds that we do not know still gets a row, after the canonical lanes', () => {
    render(<JournalByStrategy byStrategy={{ ...FULL, zone_edge: { n: 4, open: 0, closed: 4, wins: 2, losses: 2, win_rate_pct: 50, avg_r: 0.2, expectancy_pct: 0.5, realized_pnl: 30 } }} />);
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[rows.length - 1].getAttribute('data-strategy')).toBe('zone_edge');
    expect(within(rows[rows.length - 1]).getByText(/zone edge/)).toBeInTheDocument();
  });

  it('null-soaked stats render "—", never NaN / null (negative)', () => {
    render(<JournalByStrategy byStrategy={{ minervini: { n: 2, open: null, closed: null, wins: null, losses: null, win_rate_pct: null, avg_r: null, expectancy_pct: null, realized_pnl: null } }} />);
    const m = rowOf(/Minervini/);
    expect(m.textContent).not.toMatch(/NaN|null|undefined/);
    expect(within(m).getAllByText('—').length).toBeGreaterThanOrEqual(5);
  });

  it('says it is a paper account with small n', () => {
    render(<JournalByStrategy byStrategy={FULL} />);
    expect(HONESTY_NOTE).toMatch(/paper account/i);
    expect(HONESTY_NOTE).toMatch(/small n/i);
    expect(screen.getByText(HONESTY_NOTE)).toBeInTheDocument();
  });
});

describe('StrategyChip', () => {
  it('shows the lane glyph + label from trade.entry.strategy', () => {
    render(<StrategyChip strategy="demand_zone" />);
    expect(screen.getByTestId('strategy-chip')).toHaveTextContent('🧲 demand zone');
  });
  it('falls back to manual when the tag is absent (pre-2026-09-05 rows)', () => {
    render(<StrategyChip strategy={undefined} />);
    expect(screen.getByTestId('strategy-chip')).toHaveTextContent('✋ manual');
    render(<StrategyChip strategy={null} />);
    expect(screen.getAllByTestId('strategy-chip')[1]).toHaveTextContent('✋ manual');
  });
  it('an unknown tag is shown as-is rather than mislabelled as a known lane (negative)', () => {
    render(<StrategyChip strategy="zone_edge" />);
    expect(screen.getByTestId('strategy-chip')).toHaveTextContent('zone edge');
    expect(screen.getByTestId('strategy-chip').textContent).not.toMatch(/manual|Minervini/);
  });
});

describe('pure helpers', () => {
  it('strategyMeta knows the five lanes and never throws on junk', () => {
    expect(strategyMeta('minervini').glyph).toBe('📈');
    expect(strategyMeta('demand_zone').glyph).toBe('🧲');
    expect(strategyMeta('breakout').glyph).toBe('🚀');
    expect(strategyMeta('catalyst').glyph).toBe('🗞️');
    expect(strategyMeta('manual').glyph).toBe('✋');
    expect(strategyMeta(undefined).label).toBe('manual');
    expect(strategyMeta('what_is_this').label).toBe('what is this');
  });
  it('strategyRows: canonical order first, extras after, missing lanes as null', () => {
    const rows = strategyRows({ manual: FULL.manual, extra: { n: 1 } });
    expect(rows.map(([k]) => k)).toEqual([...STRATEGY_ORDER, 'extra']);
    expect(rows[0][1]).toBeNull();
    expect(rows[STRATEGY_ORDER.indexOf('manual')][1]).toEqual(FULL.manual);
    expect(strategyRows(undefined).map(([, v]) => v)).toEqual(STRATEGY_ORDER.map(() => null));
  });
  it('formatters are null-safe and signed where a sign carries meaning', () => {
    expect(fmtInt(3)).toBe('3'); expect(fmtInt(null)).toBe('—'); expect(fmtInt(NaN)).toBe('—');
    expect(fmtPct(60)).toBe('60%'); expect(fmtPct(66.67)).toBe('67%'); expect(fmtPct(null)).toBe('—');
    expect(fmtR(0.42)).toBe('+0.42R'); expect(fmtR(-1)).toBe('-1.00R'); expect(fmtR(undefined)).toBe('—');
    expect(fmtMoney(212.5)).toBe('+$212.50'); expect(fmtMoney(-48.2)).toBe('-$48.20'); expect(fmtMoney(0)).toBe('$0.00');
    expect(fmtMoney(null)).toBe('—');
  });
});

/* Options lane (2026-09-06) — the backend merges options_lane.journal_block()
   into by_strategy under the key `options_zone`; the table must label it as
   the Options lane, never as an unknown "options zone". */
describe('JournalByStrategy — options lane (2026-09-06)', () => {
  it('labels the options_zone key "🎛️ Options" with its stats, before manual', () => {
    render(<JournalByStrategy byStrategy={{ ...FULL, options_zone: { n: 2, open: 1, closed: 1, wins: 1, losses: 0, win_rate_pct: 100, avg_r: null, expectancy_pct: 38.5, realized_pnl: 231.0 } }} />);
    const rows = screen.getAllByRole('row').slice(1);
    const keys = rows.map((r) => r.getAttribute('data-strategy'));
    expect(keys.indexOf('options_zone')).toBe(keys.indexOf('manual') - 1);
    const o = screen.getByRole('row', { name: /🎛️ Options/ });
    expect(within(o).getByText('🎛️ Options')).toBeInTheDocument();
    expect(within(o).getByText('+38.5%')).toBeInTheDocument();
    expect(within(o).getByText('+$231.00')).toBeInTheDocument();
    expect(within(o).getByText('100%')).toBeInTheDocument();
    // NEGATIVE: not rendered as an unknown lane.
    expect(screen.queryByText(/options zone/)).toBeNull();
  });

  it('the lane chip reads 🎛️ Options for an options_zone trade', () => {
    render(<StrategyChip strategy="options_zone" />);
    expect(screen.getByTestId('strategy-chip')).toHaveTextContent('🎛️ Options');
  });
});

describe('JournalByStrategy — wording he reads (2026-09-14)', () => {
  it('no lane blurb or label says "bounce" — he asked for "reversal" (2026-09-09)', () => {
    for (const key of STRATEGY_ORDER) {
      const m = strategyMeta(key);
      expect(`${m.label} ${m.blurb}`).not.toMatch(/bounc/i);
    }
    expect(strategyMeta('demand_zone').blurb).toMatch(/reversals off a demand band/);
  });
  it('NEGATIVE: an unknown lane tag is echoed as-is, never relabelled into a known lane', () => {
    const m = strategyMeta('bounce_lane');
    expect(m.label).toBe('bounce lane');
    expect(m.blurb).toMatch(/not one the page knows/);
  });
});

/* 🚩 Gajjala lane (2026-10-20) — Ajay: "in the autopilot can you stop rest of
   the strategies and only use the Gajjalas strategies please." The engine tags
   the lane's entries `gajjala`; the table must show it FIRST and by name, never
   as an unknown "gajjala" lane or folded into manual. */
describe('JournalByStrategy — 🚩 Gajjala lane (2026-10-20)', () => {
  const GG: StrategyStats = { n: 2, open: 1, closed: 1, wins: 1, losses: 0, win_rate_pct: 100, avg_r: 1.25, expectancy_pct: 3.6, realized_pnl: 398.4 };

  it('the 🚩 row is first, labelled Gajjala, with its stats', () => {
    render(<JournalByStrategy byStrategy={{ ...FULL, gajjala: GG }} />);
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[0].getAttribute('data-strategy')).toBe('gajjala');
    const g = rowOf(/🚩 Gajjala/);
    expect(within(g).getByText('🚩 Gajjala')).toBeInTheDocument();
    expect(within(g).getByText('+1.25R')).toBeInTheDocument();
    expect(within(g).getByText('+$398.40')).toBeInTheDocument();
    expect(STRATEGY_ORDER[0]).toBe('gajjala');
  });

  it('NEGATIVE: an absent gajjala block is a muted "no trades yet" row, not a missing row or a crash', () => {
    render(<JournalByStrategy byStrategy={FULL} />);
    const g = rowOf(/🚩 Gajjala/);
    expect(within(g).getByText(NO_TRADES_TEXT)).toBeInTheDocument();
    expect(g.getAttribute('style') || '').toMatch(/opacity: 0\.55/);
  });

  it('NEGATIVE: an unknown lane is still its own row after the canonical lanes, never relabelled 🚩', () => {
    render(<JournalByStrategy byStrategy={{ gajjala: GG, gajjala_v2: { n: 1, open: 1, closed: 0 } }} />);
    const rows = screen.getAllByRole('row').slice(1);
    const last = rows[rows.length - 1];
    expect(last.getAttribute('data-strategy')).toBe('gajjala_v2');
    expect(within(last).getByText(/gajjala v2/)).toBeInTheDocument();
    expect(last.textContent).not.toContain('🚩');
  });

  it('meta: glyph, label, blurb says owner rules + UNMEASURED; no b-word, no book cite', () => {
    const m = strategyMeta('gajjala');
    expect(m.glyph).toBe('🚩');
    expect(m.label).toBe('Gajjala');
    expect(m.blurb).toBe('The 🚩 Gajjala lane — his A+ ENTRY alerts on paper (owner rules, UNMEASURED).');
    expect(m.blurb).not.toMatch(/bounc|TLSW|TTLAC|Minervini p\./i);
    render(<StrategyChip strategy="gajjala" />);
    expect(screen.getByTestId('strategy-chip')).toHaveTextContent('🚩 Gajjala');
  });
});
