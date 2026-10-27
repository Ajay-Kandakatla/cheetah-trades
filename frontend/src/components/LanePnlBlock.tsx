/* LanePnlBlock — 💵 P&L by lane on the Auto-Pilot Dashboard (2026-10-27).
 *
 * Ajay 2026-10-27: "Also in autopilot looks like Gajjala's strategy is making
 * money.. Anyway you can can show me which tab made money or not?"
 * (BUILD_SPEC28 §3.15.)
 *
 * Every word and every number on this block is SERVED by
 * trading/journal.lane_pnl through GET /trading/status → `lane_pnl`. This
 * component prints the served strings only: it formats no number and adds no
 * text of its own. Colors come only from the served `tone`.
 *
 * Phone (430 px): no table, no horizontal scroll, no fixed px width; every
 * flex container wraps and carries min-width 0 so a long chip breaks instead
 * of pushing the page sideways.
 */
import type { CSSProperties } from 'react';
import { Link } from 'react-router-dom';

export type LanePnlTone = 'up' | 'down' | 'flat';

export type LanePnlRow = {
  key?: string | null;
  label?: string | null;
  url?: string | null;
  link_text?: string | null;
  closed?: number | null;
  open?: number | null;
  held?: number | null;
  unbooked?: number | null;
  unheld?: number | null;
  wins?: number | null;
  losses?: number | null;
  win_rate_pct?: number | null;
  realized_pnl?: number | null;
  unrealized_pnl?: number | null;
  total_pnl?: number | null;
  first_ts?: string | null;
  last_ts?: string | null;
  total_text?: string | null;
  record_text?: string | null;
  realized_text?: string | null;
  open_text?: string | null;
  dates_text?: string | null;
  note_text?: string | null;
  tone?: LanePnlTone | null;
};

export type LanePnlAccount = {
  starting?: number | null;
  equity?: number | null;
  total_pnl?: number | null;
  unrealized_pnl?: number | null;
  realized_pnl?: number | null;
};

export type LanePnlTotals = {
  realized_pnl?: number | null;
  unrealized_pnl?: number | null;
  total_pnl?: number | null;
};

export type LanePnl = {
  title?: string | null;
  as_of?: string | null;
  since?: string | null;
  verdict_text?: string | null;
  honesty_text?: string | null;
  account?: LanePnlAccount | null;
  account_text?: string | null;
  lanes_total?: LanePnlTotals | null;
  unexplained?: LanePnlTotals | null;
  unexplained_text?: string | null;
  rows?: LanePnlRow[] | null;
  untraded?: string[] | null;
  untraded_text?: string | null;
  positions_text?: string | null;
  error?: string | null;
};

const TONE: Record<LanePnlTone, string> = { up: '#10b981', down: '#ef4444', flat: '#94a3b8' };
const NOTE = '#f59e0b';
const SUB = '#8a93a6';

const SECTION: CSSProperties = {
  minWidth: 0, maxWidth: '100%', overflowWrap: 'anywhere', margin: '0.7rem 0 0.4rem',
  border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 10, padding: '0.6rem 0.7rem',
};
const TITLE: CSSProperties = {
  fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: SUB, fontWeight: 600,
};
const VERDICT: CSSProperties = { margin: '0.3rem 0 0.5rem', fontSize: '0.85rem' };
const ROWS: CSSProperties = { display: 'grid', gap: 6, minWidth: 0 };
const ROW: CSSProperties = { minWidth: 0, borderTop: '1px solid var(--hairline,#2a2a2a)', paddingTop: 6 };
const HEAD: CSSProperties = {
  display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: 6, minWidth: 0,
};
const LABEL: CSSProperties = { fontWeight: 700, minWidth: 0 };
const CHIPS: CSSProperties = { display: 'flex', flexWrap: 'wrap', gap: 4, minWidth: 0, marginTop: 3 };
const CHIP: CSSProperties = {
  fontSize: '0.7rem', color: SUB, border: `1px solid ${SUB}55`, borderRadius: 999, padding: '1px 7px',
  whiteSpace: 'normal', minWidth: 0,
};
const LINK: CSSProperties = { fontSize: '0.7rem', minWidth: 0 };
const NOTE_S: CSSProperties = { color: NOTE, fontSize: '0.7rem', marginTop: 3 };
const LINE: CSSProperties = { fontSize: '0.74rem', color: SUB, margin: '0.4rem 0 0' };
const HONESTY: CSSProperties = { fontSize: '0.66rem', color: SUB, margin: '0.4rem 0 0' };

function toneColor(t?: string | null): string | undefined {
  return t && Object.prototype.hasOwnProperty.call(TONE, t) ? TONE[t as LanePnlTone] : undefined;
}

export function LanePnlBlock({ data }: { data?: LanePnl | null }) {
  if (!data || typeof data !== 'object') return null;
  if (data.error) {
    return (
      <section data-testid="lane-pnl" className="lane-pnl">
        <p className="lane-pnl__error">{data.error}</p>
      </section>
    );
  }
  const rows = Array.isArray(data.rows) ? data.rows.filter((r) => r && typeof r === 'object') : [];
  return (
    <section data-testid="lane-pnl" className="lane-pnl" style={SECTION}>
      <div className="lane-pnl__title" style={TITLE}>{data.title}</div>
      <p className="lane-pnl__verdict" data-testid="lane-pnl-verdict" style={VERDICT}><b>{data.verdict_text}</b></p>
      <div className="lane-pnl__rows" style={ROWS}>
        {rows.map((r, i) => (
          <div key={r.key || i} className="lane-pnl__row" data-testid="lane-pnl-row" data-lane={r.key || undefined} style={ROW}>
            <div className="lane-pnl__head" style={HEAD}>
              <span className="lane-pnl__label" style={LABEL}>{r.label}</span>
              <b className="lane-pnl__total" style={{ color: toneColor(r.tone) }}>{r.total_text}</b>
            </div>
            <div className="lane-pnl__chips" style={CHIPS}>
              {[r.record_text, r.realized_text, r.open_text, r.dates_text].filter(Boolean).map((t, j) => (
                <span key={j} className="lane-pnl__chip" style={CHIP}>{t}</span>
              ))}
              {r.url && r.link_text && <Link className="lane-pnl__link" to={r.url} style={LINK}>{r.link_text}</Link>}
            </div>
            {r.note_text && <div className="lane-pnl__note" style={NOTE_S}>{r.note_text}</div>}
          </div>
        ))}
      </div>
      {data.untraded_text && <p className="lane-pnl__untraded" style={LINE}>{data.untraded_text}</p>}
      {data.positions_text && <p className="lane-pnl__positions" style={LINE}>{data.positions_text}</p>}
      <p className="lane-pnl__account" style={LINE}>{data.account_text}</p>
      {data.unexplained_text && <p className="lane-pnl__unexplained" style={LINE}>{data.unexplained_text}</p>}
      <p className="lane-pnl__honesty" style={HONESTY}>{data.honesty_text}</p>
    </section>
  );
}
