import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EarningsFreshChip, type EarningsFresh } from './EarningsFreshChip';
import { fmtDate } from './EarningsChip';

/* 📣 The just-reported chip (Ajay 2026-09-17).
 *
 * It is a CALENDAR FACT. The tests below hold the three lines that turn a fact
 * into a claim if they slip: it renders NOTHING unless the backend said fresh,
 * the tooltip says out loud that it decides nothing, and the date is never
 * parsed with the Date constructor (a bare ISO string is read as UTC and prints
 * the PREVIOUS day in ET). Measured on his own board the day it shipped: 0 of
 * 21 names fresh, 16 of 21 with no report date on file at all.
 */

const fresh = (over: Partial<EarningsFresh> = {}): EarningsFresh => ({
  known: true, reported_on: '2026-09-16', when: 'AMC', days_ago: 2,
  fresh: true, surprise_pct: null, window_days: 7, ...over,
});

describe('EarningsFreshChip', () => {
  it('renders for a name reported today / yesterday / 3 days ago', () => {
    const { rerender } = render(
      <EarningsFreshChip symbol="CRDO"
        read={fresh({ reported_on: '2026-09-18', days_ago: 0, when: 'BMO' })} />);
    // no `when` suffix on the today branch: AMC-today is still UPCOMING and
    // last_report.date can never equal today, so that combination is dead code.
    expect(screen.getByText('📣 reported today')).toBeInTheDocument();

    rerender(<EarningsFreshChip symbol="CRDO"
      read={fresh({ reported_on: '2026-09-17', days_ago: 1, when: 'AMC' })} />);
    expect(screen.getByText('📣 reported yesterday · AMC')).toBeInTheDocument();

    rerender(<EarningsFreshChip symbol="CRDO"
      read={fresh({ reported_on: '2026-09-15', days_ago: 3, when: 'AMC' })} />);
    expect(screen.getByText('📣 reported Sep 15 · AMC')).toBeInTheDocument();
  });

  it('NEGATIVE — THE TZ PIN: the date comes from EarningsChip.fmtDate, never the Date constructor', () => {
    expect(fmtDate('2026-09-16')).toBe('Sep 16');
    // what the forbidden call would have printed, in his timezone
    expect(new Date('2026-09-16').toLocaleDateString('en-US',
      { month: 'short', day: 'numeric', timeZone: 'America/New_York' })).toBe('Sep 15');
    // the SOURCE guard (no Date constructor in the file) lives in
    // EarningsFreshChip.guard.test.js — node's fs cannot be imported from a
    // .tsx the production `tsc -b` type-checks.

    render(<EarningsFreshChip symbol="CRDO" read={fresh({ reported_on: '2026-09-16', days_ago: 2 })} />);
    expect(screen.getByText('📣 reported Sep 16 · AMC')).toBeInTheDocument();
  });

  it('NEGATIVE: renders NOTHING when fresh is false', () => {
    // CRDO's real state the day this shipped: reported, 17 days ago.
    const { container } = render(<EarningsFreshChip symbol="CRDO"
      read={fresh({ reported_on: '2026-09-01', days_ago: 17, fresh: false })} />);
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: renders NOTHING when the read is undefined, null or {}', () => {
    for (const read of [undefined, null, {} as EarningsFresh]) {
      const { container } = render(<EarningsFreshChip symbol="CRDO" read={read} />);
      expect(container.innerHTML).toBe('');
    }
  });

  it('NEGATIVE: renders NOTHING when known is false — the last_report: None shape', () => {
    // 16 of the 21 live rows. Unknown is NOT "did not report".
    const { container } = render(<EarningsFreshChip symbol="NVDA"
      read={{ known: false, reported_on: null, when: null, days_ago: null,
              fresh: false, surprise_pct: null, window_days: 7 }} />);
    expect(container.innerHTML).toBe('');
  });

  it('tooltip carries the no-edge sentence', () => {
    render(<EarningsFreshChip symbol="CRDO" read={fresh({ when: 'AMC' })} />);
    const title = screen.getByText(/reported Sep 16/).getAttribute('title') ?? '';
    expect(title).toContain('CRDO reported earnings on 2026-09-16, after the close');
    expect(title).toContain('2 days ago');
    expect(title).toContain('7-day');
    expect(title).toContain('CALENDAR FACT, NOT A SIGNAL');
    expect(title).toContain("does not change this row's order");
    expect(title).toContain('EarningsWhispers');
  });

  it('NEGATIVE: the tooltip never claims a surprise when surprise_pct is null', () => {
    render(<EarningsFreshChip symbol="CRDO" read={fresh({ surprise_pct: null })} />);
    const title = screen.getByText(/reported Sep 16/).getAttribute('title') ?? '';
    expect(title).not.toMatch(/beat|missed/);
  });

  it('states the surprise when the backend served one', () => {
    const { rerender } = render(
      <EarningsFreshChip symbol="CRDO" read={fresh({ surprise_pct: 6.1 })} />);
    expect(screen.getByText(/reported Sep 16/).getAttribute('title'))
      .toContain('Reported EPS beat the estimate by 6.1%.');
    rerender(<EarningsFreshChip symbol="CRDO" read={fresh({ surprise_pct: -28.0 })} />);
    expect(screen.getByText(/reported Sep 16/).getAttribute('title'))
      .toContain('Reported EPS missed the estimate by 28.0%.');
  });
});

/* ── source guards ────────────────────────────────────────────────────────────
 * These lived in a sibling `.guard.test.js` until 2026-09-18. Two problems:
 * vitest.config.ts includes only ts/tsx test files under src, so the `.js`
 * was NEVER COLLECTED — it was reported passing while running zero times; and
 * it proved the CSS contract by `writeFileSync`-ing src/styles.css, a tracked
 * source file, while 160 other test files run in parallel workers.
 *
 * Ported here with `?raw`, which reads the same bytes with no fs and no
 * mutation. The mutation proof is deliberately dropped; what replaces it is the
 * second assertion below, which pins that the CONTRACT ITSELF still exists —
 * a guard that was silently deleted is the failure the mutation test was for.
 */
import chipSrc from './EarningsFreshChip.tsx?raw';
import contractsSrc from '../../scripts/contracts.mjs?raw';

describe('EarningsFreshChip source guards', () => {
  it('NEGATIVE — THE TZ PIN: the chip never calls the Date constructor', () => {
    // `new Date('2026-09-16')` parses a bare ISO date as UTC and renders the
    // PREVIOUS day in ET ("Sep 15"). The chip must reuse EarningsChip.fmtDate.
    expect(chipSrc).not.toMatch(/new Date\(/);
    expect(chipSrc).toMatch(/import \{ fmtDate \} from '\.\/EarningsChip'/);
  });

  it('the CSS-rule guard for the chip class still exists in the contracts script', () => {
    // The RULE itself cannot be asserted from here: vitest.config.ts sets
    // css:false, which stubs every CSS import — `?raw` included — to ''. And a
    // typed test cannot read it with fs: there is no @types/node and
    // tsconfig.json includes all of src, so `tsc --noEmit` would break. That is
    // why this guard was a .js file in the first place.
    //
    // contracts.mjs already enforces the rule (it runs in node, in CI, and in
    // the pre-commit hook). What is pinned here is that the guard was not
    // quietly deleted — which is the failure the old mutation test existed for.
    expect(contractsSrc).toContain('.cm-badge-earnings has no CSS rule');
  });
});
