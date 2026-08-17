import { describe, expect, it } from 'vitest';
import {
  THIN_SAMPLE, churnRuns, headline, latestBoard, pct, tone, verdict,
} from './demandTrackRecord';

const rec = (over: Record<string, unknown> = {}) => ({
  ok: true, raced: 40, wins: 18, losses: 22, expectancy_pct: 0.4,
  excess_vs_spy_pct: -0.3, since: '2026-08-17', runs: [], ...over,
});

describe('verdict', () => {
  it('is empty before anything has finished racing', () => {
    // Recording starts 2026-08-17 and an episode can run 60 bars, so this is
    // the state the page will actually be in for weeks.
    expect(verdict(rec({ raced: 0 }))).toBe('empty');
    expect(verdict(null)).toBe('empty');
    expect(verdict({ ok: false })).toBe('empty');
  });

  it('flags a thin sample rather than presenting it as a result', () => {
    expect(verdict(rec({ raced: THIN_SAMPLE - 1 }))).toBe('thin');
    expect(verdict(rec({ raced: THIN_SAMPLE }))).toBe('ready');
  });
});

describe('headline', () => {
  it('leads with excess vs SPY, not the win rate', () => {
    // The whole point. A dip-buying board in a rising tape shows profit with
    // or without skill — win% cannot tell the two apart.
    const h = headline(rec({ excess_vs_spy_pct: -0.3, win_pct: 45 }));
    expect(h).toContain('vs SPY');
    expect(h).toContain('behind');
    expect(h).not.toContain('45');
  });

  it('says so plainly when it is ahead', () => {
    expect(headline(rec({ excess_vs_spy_pct: 1.2 }))).toContain('ahead of');
  });

  it('names the sample as too small to lean on', () => {
    const h = headline(rec({ raced: 4 }));
    expect(h).toContain('only 4 finished');
  });

  it('tells the truth about an empty ledger instead of showing zeros', () => {
    expect(headline(rec({ raced: 0, runs: [] }))).toContain('nothing graded yet');
    const started = headline(rec({ raced: 0, since: '2026-08-17', runs: [{ et_date: '2026-08-17', n: 9 }] }));
    expect(started).toContain('2026-08-17');
    expect(started).toContain('no episode has finished racing yet');
  });

  // --- negatives ---

  it('does not claim a direction when the benchmark is missing', () => {
    const h = headline(rec({ excess_vs_spy_pct: null }));
    expect(h).toContain('unmeasured against');
    expect(h).not.toContain('ahead');
    expect(h).not.toContain('behind');
  });
});

describe('pct', () => {
  it('signs a positive number and leaves a negative alone', () => {
    expect(pct(1.234)).toBe('+1.23%');
    expect(pct(-0.5)).toBe('-0.50%');
  });

  it('renders a missing value as a dash, never as 0.0%', () => {
    // "0.00%" is a measurement that came back flat. A blank is not that.
    expect(pct(null)).toBe('—');
    expect(pct(undefined)).toBe('—');
    expect(pct(NaN)).toBe('—');
  });
});

describe('tone', () => {
  it('is flat for zero and for unknown', () => {
    expect(tone(0)).toBe('flat');
    expect(tone(null)).toBe('flat');
    expect(tone(2)).toBe('good');
    expect(tone(-2)).toBe('bad');
  });
});

describe('runs', () => {
  const runs = [
    { et_date: '2026-08-19', n: 3, entered: ['TJX'], dropped: [] },
    { et_date: '2026-08-18', n: 3, entered: [], dropped: [] },
    { et_date: '2026-08-17', n: 3, entered: [], dropped: ['HOOD'] },
  ];

  it('returns the newest board first', () => {
    expect(latestBoard(rec({ runs }))?.et_date).toBe('2026-08-19');
    expect(latestBoard(rec({ runs: [] }))).toBeNull();
    expect(latestBoard(null)).toBeNull();
  });

  it('hides the days nothing changed', () => {
    // A board repeating yesterday's list is not news and must not take a row.
    expect(churnRuns(rec({ runs })).map((r) => r.et_date))
      .toEqual(['2026-08-19', '2026-08-17']);
  });

  it('survives runs with no churn fields at all', () => {
    expect(churnRuns(rec({ runs: [{ et_date: '2026-08-19', n: 3 }] }))).toEqual([]);
    expect(churnRuns(null)).toEqual([]);
  });
});
