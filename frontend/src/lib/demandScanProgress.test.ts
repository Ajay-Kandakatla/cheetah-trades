/* The Back in Demand scan counter.
 *
 * Ajay 2026-08-17, mid-scan: "I am looking at this and its hard to tell if its
 * scanning or now". Every test here exists to keep the panel from telling him
 * something that is not true about a job he is waiting on.
 */
import { describe, expect, it } from 'vitest';
import { fmtEta, progressView, type DemandScanProgress } from './demandScanProgress';

const p = (o: Partial<DemandScanProgress> = {}): DemandScanProgress => ({
  universe_key: 'sp1500', universe_label: 'S&P 1500',
  phase: 'scanning', running: true,
  current: 412, total: 1500, hits: 6, errors: 0, symbol: 'NVDA',
  elapsed_sec: 41.2, eta_sec: 108.6, pct: 27.5, ...o,
});

describe('fmtEta — coarse on purpose', () => {
  it('rounds under a minute to 5s steps', () => {
    expect(fmtEta(41)).toBe('40s');
    expect(fmtEta(58)).toBe('60s');
  });

  it('says "a few seconds" rather than counting down the last breath', () => {
    expect(fmtEta(3)).toBe('a few seconds');
    expect(fmtEta(0)).toBe('a few seconds');
  });

  it('rounds minutes to 10s steps — a projection is not precise to the second', () => {
    expect(fmtEta(108.6)).toBe('1m 50s');
    expect(fmtEta(180)).toBe('3m');
  });

  it('is null for junk rather than "NaNs left"', () => {
    expect(fmtEta(null)).toBeNull();
    expect(fmtEta(undefined)).toBeNull();
    expect(fmtEta(NaN)).toBeNull();
    expect(fmtEta(-5)).toBeNull();
  });
});

describe('progressView while scanning', () => {
  it('reports the running ticker, the count and the live hit total', () => {
    const v = progressView(p());
    expect(v.visible).toBe(true);
    expect(v.symbol).toBe('NVDA');
    expect(v.countLabel).toBe('412 / 1,500');
    expect(v.hits).toBe(6);
    expect(v.pct).toBe(27.5);
    expect(v.etaLabel).toBe('~1m 50s left');
  });

  it('names the universe it is actually scanning', () => {
    expect(progressView(p()).message).toContain('S&P 1500');
  });

  it('falls back to the caller-supplied label before the backend knows one', () => {
    // The first seconds of a cold scan are when the page most needs to say
    // what it is doing, and that is exactly when the server has no label yet.
    const v = progressView(p({ phase: 'universe', universe_label: null, total: 0 }),
                           'S&P 1500 (500 + 400 mid + 600 small)');
    expect(v.message).toContain('S&P 1500 (500 + 400 mid + 600 small)');
  });
});

describe('the honesty cases', () => {
  it('shows NO percentage while the universe is still being fetched', () => {
    // 0% reads as "stuck at zero" — the exact impression this panel exists to
    // kill. The bar renders indeterminate instead.
    const v = progressView(p({ phase: 'universe', current: 0, total: 0 }));
    expect(v.pct).toBeNull();
    expect(v.countLabel).toBeNull();
    expect(v.message).toContain('Loading');
  });

  it('gives enriching its own phase instead of parking the bar at 100%', () => {
    const v = progressView(p({ phase: 'enriching', current: 1500, total: 1500 }));
    expect(v.phaseLabel).toBe('enriching');
    expect(v.message).toContain('tape');
  });

  it('surfaces a failed scan rather than leaving a frozen bar', () => {
    const v = progressView(p({ phase: 'failed', error: 'universe fetch died' }));
    expect(v.isError).toBe(true);
    expect(v.message).toContain('failed');
    expect(v.message).toContain('universe fetch died');
    expect(v.etaLabel).toBeNull();
  });

  it('drops the ETA once the scan is done — there is nothing left to wait for', () => {
    const v = progressView(p({ phase: 'done', current: 1500, hits: 9, took_sec: 141.2 }));
    expect(v.isDone).toBe(true);
    expect(v.etaLabel).toBeNull();
    expect(v.message).toContain('9 in demand');
    expect(v.message).toContain('141.2s');
  });

  it('renders nothing at all when idle', () => {
    expect(progressView(p({ phase: 'idle' })).visible).toBe(false);
    expect(progressView(null).visible).toBe(false);
    expect(progressView(undefined).visible).toBe(false);
  });
});

describe('negatives — junk must not draw a lie', () => {
  it('clamps a percentage that would overflow the bar', () => {
    expect(progressView(p({ current: 1600, total: 1500 })).pct).toBe(100);
    expect(progressView(p({ current: -5, total: 1500 })).pct).toBe(0);
  });

  it('treats a missing count as zero, never NaN', () => {
    const v = progressView({ phase: 'scanning' } as DemandScanProgress);
    expect(v.hits).toBe(0);
    expect(v.pct).toBeNull();
    expect(v.countLabel).toBeNull();
  });

  it('survives non-numeric counters', () => {
    const v = progressView(p({
      current: 'x' as unknown as number, total: null as unknown as number,
      hits: undefined,
    }));
    expect(v.pct).toBeNull();
    expect(v.hits).toBe(0);
    expect(() => v.message).not.toThrow();
  });

  it('falls back to idle for a phase the backend has not taught it', () => {
    const v = progressView(p({ phase: 'teleporting' as never }));
    expect(v.phase).toBe('idle');
    expect(v.visible).toBe(false);
  });

  it('never shows a ticker with no name', () => {
    expect(progressView(p({ symbol: null })).symbol).toBeNull();
    expect(progressView(p({ symbol: '' })).symbol).toBeNull();
  });

  it('maps every phase onto a CSS modifier that actually exists', () => {
    // styles.css defines .sepa-progress__phase--{scanning,warming_names,
    // enriching,done,error,retrying,rs}. A class with no rule renders unstyled.
    const defined = new Set(['scanning', 'warming_names', 'enriching', 'done',
                             'error', 'retrying', 'rs']);
    for (const phase of ['idle', 'universe', 'scanning', 'enriching', 'done', 'failed'] as const) {
      expect(defined.has(progressView(p({ phase })).phaseClass)).toBe(true);
    }
  });
});

describe('the board flag beats the poll — never go silent', () => {
  // The board payload arrives with the page; the first progress poll is up to
  // POLL_MS behind it and may never land at all. A panel that renders nothing
  // in that gap reproduces the original complaint.
  it('shows a starting state when the board says warming and no poll has landed', () => {
    const v = progressView(null, 'S&P 1500', { running: true });
    expect(v.visible).toBe(true);
    expect(v.pct).toBeNull();
    expect(v.message).toContain('S&P 1500');
  });

  it('treats an idle poll during warming as "starting", not "nothing running"', () => {
    const v = progressView(p({ phase: 'idle' }), null, { running: true });
    expect(v.visible).toBe(true);
  });

  it('never overrides a REAL phase with the fallback', () => {
    const v = progressView(p({ phase: 'scanning', current: 412 }), null, { running: true });
    expect(v.phase).toBe('scanning');
    expect(v.pct).toBe(27.5);
  });

  it('lets a finished scan stay finished even while the board still says warming', () => {
    // The board polls every 10s, the progress every 1.5s — so `done` is known
    // several seconds before `warming` clears. Showing "scanning" over a
    // finished scan would be a fresh version of the same lie.
    const v = progressView(p({ phase: 'done', hits: 9 }), null, { running: true });
    expect(v.isDone).toBe(true);
    expect(v.message).toContain('9 in demand');
  });

  it('stays invisible when nothing is running and nothing claims otherwise', () => {
    expect(progressView(null, 'S&P 1500', { running: false }).visible).toBe(false);
    expect(progressView(null, 'S&P 1500').visible).toBe(false);
  });
});
