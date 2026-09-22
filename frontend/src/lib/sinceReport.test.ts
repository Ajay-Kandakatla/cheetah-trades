/* 📅 sinceReport — the formatter's pins.
 *
 * The rule the ask wrote, and the one every test here exists to hold: a blank
 * is NEVER a zero. `—` is a dash whose title opens "Not measured:" and names
 * the refusal; `0.0%` may only ever be a real unchanged close over at least
 * one session.
 */
import { describe, it, expect } from 'vitest';
import {
  SINCE_REPORT_HEAD, SINCE_REPORT_BLANK, SURPRISE_STALE_DAYS_LABEL,
  CALENDAR_STALE_DAYS_LABEL, sinceReportCell, sinceReportCoverage,
  type SinceReport,
} from './sinceReport';

/* The repo's own source-read pattern: `import.meta.url` is not a file URL
   under the vitest transform, so resolve from the frontend root instead. */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const KNOWN: SinceReport = {
  known: true, pct: 12.34, report_date: '2026-09-01', when: 'AMC',
  anchor_date: '2026-09-02', anchor_close: 165.22, as_of: '2026-09-19',
  last_close: 187.27, sessions: 12, report_age_days: 18,
  stale_report: false, calendar_fetched_at: '2026-09-21', calendar_stale: false,
  reason: null,
};

describe('the known cell', () => {
  it('prints a signed percent with a real minus sign', () => {
    expect(sinceReportCell(KNOWN, 'CRDO').text).toBe('+12.3%');
    const down = sinceReportCell({ ...KNOWN, pct: -4.41 }, 'AAA');
    expect(down.text).toBe('−4.4%');
    expect(down.text).not.toContain('-');
    expect(down.tone).toBe('bad');
    expect(sinceReportCell(KNOWN).tone).toBe('good');
  });

  it('names both dates, both closes and the session count in the title', () => {
    const t = sinceReportCell(KNOWN, 'CRDO').title;
    expect(t).toContain('CRDO: +12.3%');
    expect(t).toContain('2026-09-02 close (165.22)');
    expect(t).toContain('2026-09-01 AMC report');
    expect(t).toContain('2026-09-19 close (187.27)');
    expect(t).toContain('12 sessions');
    expect(t).toContain('not the SEC filing date');
    expect(t).toContain('A fact, not a signal.');
  });

  it('C5 — says "the first session the market could trade on", never "after"', () => {
    const t = sinceReportCell({ ...KNOWN, when: 'BMO', anchor_date: '2026-09-01' },
                              'CRDO').title;
    expect(t).toContain('first session the market could trade on');
    expect(t).not.toContain('first session after');
  });

  it('C5 — the head tooltip says unknown timing anchors like BMO', () => {
    expect(SINCE_REPORT_HEAD.title).toContain('unknown timing anchors like BMO');
    expect(SINCE_REPORT_HEAD.title).toContain('not measured, never flat');
    expect(SINCE_REPORT_HEAD.title).toContain('REPORT');
    expect(SINCE_REPORT_HEAD.title).toContain('SEC filing date');
    expect(SINCE_REPORT_HEAD.title).toContain('sorts, filters and gates nothing');
  });

  it('adds the stale-report sentence only when the flag is set', () => {
    const stale = sinceReportCell(
      { ...KNOWN, stale_report: true, report_age_days: 400 }, 'AAA').title;
    expect(stale).toContain('400 days old');
    expect(stale).toContain(`${SURPRISE_STALE_DAYS_LABEL}-day freshness label`);
    expect(sinceReportCell(KNOWN, 'AAA').title)
      .not.toContain('freshness label');
  });

  it('adds the calendar-stale sentence only when the flag is set', () => {
    const stale = sinceReportCell({ ...KNOWN, calendar_stale: true }, 'AAA').title;
    expect(stale).toContain('last refreshed 2026-09-21');
    expect(stale).toContain(`${CALENDAR_STALE_DAYS_LABEL}-day refresh window`);
    expect(sinceReportCell(KNOWN, 'AAA').title).not.toContain('refresh window');
  });

  it('NEGATIVE — neither sentence when both flags are false', () => {
    const t = sinceReportCell(KNOWN, 'AAA').title;
    expect(t).not.toContain('freshness label');
    expect(t).not.toContain('refresh window');
  });

  it('a real unchanged close still prints 0.0% — it is a measured fact', () => {
    const flat = sinceReportCell({ ...KNOWN, pct: 0 }, 'AAA');
    expect(flat.text).toBe('0.0%');
    expect(flat.tone).toBe('dim');
  });
});

describe('NEGATIVE — the blank cell is never a zero', () => {
  it('renders an em-dash whose title opens "Not measured:"', () => {
    const c = sinceReportCell({ known: false, pct: null, reason: 'no_report' });
    expect(c.text).toBe('—');
    expect(c.tone).toBe('dim');
    expect(c.title.startsWith('Not measured:')).toBe(true);
    expect(c.text).not.toBe('0%');
    expect(c.text).not.toBe('0.0%');
  });

  it('maps every served reason to its own sentence', () => {
    for (const reason of Object.keys(SINCE_REPORT_BLANK)) {
      const c = sinceReportCell({ known: false, pct: null, reason });
      expect(c.text).toBe('—');
      expect(c.title).toBe(SINCE_REPORT_BLANK[reason]);
      expect(c.title.startsWith('Not measured:')).toBe(true);
    }
  });

  it('C1 — the not_traded_yet sentence says there is no "since" yet', () => {
    expect(SINCE_REPORT_BLANK.not_traded_yet).toContain('no ‘since’ yet');
  });

  it('an unknown reason falls back to a generic "Not measured"', () => {
    const c = sinceReportCell({ known: false, pct: null, reason: 'martians' });
    expect(c.text).toBe('—');
    expect(c.title.startsWith('Not measured:')).toBe(true);
  });

  it('a missing cell and a null cell both render blank', () => {
    for (const r of [undefined, null]) {
      const c = sinceReportCell(r as never);
      expect(c.text).toBe('—');
      expect(c.title.startsWith('Not measured:')).toBe(true);
    }
  });

  it('C4 — the FE belt: known:true with a null or NaN pct still renders blank', () => {
    for (const pct of [null, Number.NaN, Infinity, -Infinity]) {
      const c = sinceReportCell({ known: true, pct: pct as number, reason: null });
      expect(c.text).toBe('—');
      expect(c.title).toBe('Not measured: the served return was not a finite number.');
      expect(c.text).not.toBe('0.0%');
    }
  });
});

describe('the coverage sentence', () => {
  it('says how many rows it knows, what is blank and why, and the bar as-of', () => {
    const s = sinceReportCoverage({
      n: 200, n_known: 65, n_blank: 135, as_of: '2026-09-19',
      blank_reasons: { no_report: 135 }, n_calendar_stale: 0,
    });
    expect(s).toContain('known for 65 of 200 rows');
    expect(s).toContain('135 blank');
    expect(s).toContain('no report date on file 135');
    expect(s).toContain('bars to 2026-09-19');
  });

  it('adds the stale-calendar count only when there is one', () => {
    const with_ = sinceReportCoverage({
      n: 200, n_known: 65, n_blank: 135, blank_reasons: { no_report: 135 },
      n_calendar_stale: 44, as_of: '2026-09-21',
    });
    expect(with_).toContain(`44 calendar rows older than ${CALENDAR_STALE_DAYS_LABEL} days`);
    const without = sinceReportCoverage({
      n: 21, n_known: 19, n_blank: 2, blank_reasons: { before_first_bar: 2 },
      n_calendar_stale: 0, as_of: '2026-09-21',
    });
    expect(without).not.toContain('calendar rows older');
  });

  it('NEGATIVE — no summary, an empty one or a zero-row board says nothing', () => {
    expect(sinceReportCoverage(null)).toBeNull();
    expect(sinceReportCoverage(undefined)).toBeNull();
    expect(sinceReportCoverage({})).toBeNull();
    expect(sinceReportCoverage({ n: 0 })).toBeNull();
  });

  it('omits the blank clause when every row is known', () => {
    const s = sinceReportCoverage({
      n: 21, n_known: 21, n_blank: 0, blank_reasons: {}, as_of: '2026-09-21',
    });
    expect(s).toContain('known for 21 of 21 rows');
    expect(s).not.toContain('blank');
  });
});

describe('NEGATIVE — the lib composes no number of its own', () => {
  it('never uses the Date constructor', async () => {
    // A Date built from '2026-09-21' parses as UTC and prints the previous
    // ET day — banned in every FE file in this app.
    const src = await readSource('src/lib/sinceReport.ts');
    expect(src).not.toContain('new Date(');
  });

  it('carries no measured research figure — every number is served', async () => {
    const src = await readSource('src/lib/sinceReport.ts');
    for (const n of ['46.40', '2.21', '8.19', '4.41', '8 of 20']) {
      expect(src).not.toContain(n);
    }
  });
});
