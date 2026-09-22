/* 📅 Since the report — one formatter for the 🚀 Explosive Growth and 📈 Bonde
 * boards (Ajay 2026-09-21, item #3: "Should the boards print a 'since
 * qualifying filing' column?" → Yes).
 *
 * The backend owns the number (`backend/sepa/since_report.py`); this file
 * turns a served cell into text, a tone and a title, and nothing else. No
 * arithmetic on a served number beyond `signedPct`, and the Date constructor
 * is never used — it parses an ISO date as UTC and prints the previous ET
 * day, which is why it is banned in every FE file in this app. Dates here are
 * printed exactly as served.
 *
 * TWO RULES THE ASK MADE EXPLICIT:
 *   1. A blank is NEVER `0%`. It is an em-dash whose title opens with
 *      "Not measured:" and says which refusal it was.
 *   2. The date is the REPORT date, not the SEC filing date the 2026-09-21
 *      study measured from. Every tooltip says so.
 */
import { signedPct, type Cell } from './boardMetrics';

export type SinceReport = {
  known?: boolean;
  pct?: number | null;
  report_date?: string | null;
  when?: 'BMO' | 'AMC' | null;
  anchor_date?: string | null;
  anchor_close?: number | null;
  as_of?: string | null;
  last_close?: number | null;
  sessions?: number | null;
  report_age_days?: number | null;
  stale_report?: boolean | null;
  calendar_fetched_at?: string | null;
  calendar_stale?: boolean | null;
  reason?: string | null;
};

export type SinceReportSummary = {
  n?: number; n_known?: number; n_positive?: number; n_blank?: number;
  blank_reasons?: Record<string, number>;
  n_stale_report?: number; n_calendar_stale?: number;
  as_of?: string | null;
  date_basis?: string; date_basis_note?: string;
  honesty?: string; source?: string;
  measured?: { run_date?: string; doc?: string; sessions_before?: number };
};

/** 157 — mirrors `backend/sepa/bonde_picks.SURPRISE_STALE_DAYS`, the app's own
 *  freshness LABEL for this calendar doc (a label, never a gate). A backend
 *  test reads this file and pins the literal to that constant, so the sentence
 *  can never drift from the rule it describes. */
export const SURPRISE_STALE_DAYS_LABEL = 157;

/** 3 — mirrors `backend/sepa/earnings_watch.REFETCH_AFTER_SEC` (3 days), the
 *  calendar's OWN refetch rule. Pinned by the same backend test. */
export const CALENDAR_STALE_DAYS_LABEL = 3;

export const SINCE_REPORT_HEAD = {
  text: 'Since report',
  title:
    'Return from the close of the first session the market could trade on the latest '
    + 'reported quarter to the latest cached close, per name. The date is the REPORT '
    + 'date (yfinance, via the app’s earnings calendar) — NOT the SEC filing date the '
    + '2026-09-21 study measured from (CRDO: reported 2026-09-01, 10-Q filed '
    + '2026-09-02). BMO reports anchor on the report day, AMC on the next session; '
    + 'unknown timing anchors like BMO (same day). A fact between two dates: it sorts, '
    + 'filters and gates nothing. — = not measured, never flat; hover the cell for why.',
};

/** Why a cell is blank, in words. Every sentence opens "Not measured:" — the
 *  ask forbids a dash that could read as flat. */
export const SINCE_REPORT_BLANK: Record<string, string> = {
  no_report:
    'Not measured: no report date on file for this name in the earnings calendar. '
    + 'Unknown — not "did not report", and not 0%.',
  bad_date:
    'Not measured: the calendar carries a report date this app cannot read.',
  report_predates_period:
    'Not measured: the newest report on the calendar is OLDER than the quarter this '
    + 'board screened on, so it is not the qualifying report. Withheld rather than '
    + 'measured from the wrong date.',
  not_traded_yet:
    'Not measured: no session has closed AFTER the first one the market could trade '
    + 'on this report — there is no ‘since’ yet.',
  no_bars:
    'Not measured: no cached price history for this name.',
  before_first_bar:
    'Not measured: the report date precedes the first bar of this name’s cached history.',
  insufficient_history:
    'Not measured: the app’s reaction-bar read could not anchor this report inside the '
    + 'cached history.',
};

const GENERIC_BLANK =
  'Not measured: this app has no "since the report" read for this name.';

const DASH = '—';

const num = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

function blank(reason?: string | null): Cell {
  const why = (reason && SINCE_REPORT_BLANK[reason]) || GENERIC_BLANK;
  return { text: DASH, tone: 'dim', title: why };
}

/** The per-row cell. `symbol` only ever appears in the title. */
export function sinceReportCell(r?: SinceReport | null, symbol?: string): Cell {
  if (!r) return blank(null);
  const pct = num(r.pct);
  // THE FE BELT for the backend guard: a served `known: true` with a null or
  // non-finite return is a backend bug, and it must still render as blank
  // rather than as `0.0%`.
  if (!r.known || pct === null) {
    if (r.known) {
      return {
        text: DASH, tone: 'dim',
        title: 'Not measured: the served return was not a finite number.',
      };
    }
    return blank(r.reason);
  }

  const sym = symbol ? `${symbol}: ` : '';
  const when = r.when ? ` ${r.when}` : '';
  const sessions = num(r.sessions);
  const parts = [
    `${sym}${signedPct(pct)} from the ${r.anchor_date} close (${r.anchor_close})`,
    ` — the first session the market could trade on the ${r.report_date}${when} report`,
    ` — to the ${r.as_of} close (${r.last_close})`,
    sessions === null ? '.' : `, ${sessions} sessions.`,
    ' Report date per the earnings calendar (yfinance), not the SEC filing date.',
  ];
  if (r.stale_report) {
    parts.push(
      ` The report on file is ${r.report_age_days} days old — older than the app’s `
      + `${SURPRISE_STALE_DAYS_LABEL}-day freshness label for this calendar (a label, `
      + 'not a rule); the qualifying quarter may be newer than the calendar knows.');
  }
  if (r.calendar_stale) {
    parts.push(
      ` Calendar row last refreshed ${r.calendar_fetched_at} (older than its `
      + `${CALENDAR_STALE_DAYS_LABEL}-day refresh window).`);
  }
  parts.push(' A fact, not a signal.');

  return {
    text: signedPct(pct),
    tone: pct > 0 ? 'good' : pct < 0 ? 'bad' : 'dim',
    title: parts.join(''),
  };
}

/** The one-line coverage sentence under a board. The repo's own bar: "a column
 *  blank for a third of the board is worse than no column" — so the board says
 *  its coverage out loud rather than drawing a wall of em-dashes. */
export function sinceReportCoverage(s?: SinceReportSummary | null): string | null {
  if (!s || typeof s.n !== 'number' || s.n <= 0) return null;
  const known = s.n_known ?? 0;
  const bits: string[] = [`Since report: known for ${known} of ${s.n} rows`];
  const blanks = s.n_blank ?? s.n - known;
  if (blanks > 0) {
    const reasons = Object.entries(s.blank_reasons || {})
      .sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `${reasonLabel(k)} ${v}`)
      .join(', ');
    bits.push(`${blanks} blank${reasons ? ` (${reasons})` : ''}`);
  }
  if (s.as_of) bits.push(`bars to ${s.as_of}`);
  if (s.n_calendar_stale) {
    bits.push(`${s.n_calendar_stale} calendar rows older than `
      + `${CALENDAR_STALE_DAYS_LABEL} days`);
  }
  return bits.join(' · ');
}

const REASON_LABEL: Record<string, string> = {
  no_report: 'no report date on file',
  bad_date: 'unreadable report date',
  report_predates_period: 'report older than the screened quarter',
  not_traded_yet: 'no session closed since',
  no_bars: 'no cached price history',
  before_first_bar: 'report before the first cached bar',
  insufficient_history: 'could not anchor the report',
};

function reasonLabel(k: string): string {
  return REASON_LABEL[k] || k;
}
