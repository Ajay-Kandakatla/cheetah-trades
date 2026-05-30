import { useState } from 'react';
import type { EntryExitPlan } from '../hooks/useSepa';

/* ==========================================================================
   EntryExitPlanBlock — the "what do I do THIS week" decision + timeline.

   Renders on SEPA candidate cards directly under the TradePlanInline row.
   Source: backend/sepa/entry_exit.py (synthesis of trade_plan + stage +
   volume + ATR/ADX, grounded in the 2026-05-29 swing-entry research).

   Two parts:
     1. DECISION banner — one adjudicated verdict (ENTER/WAIT/HOLD/AVOID/CUT)
        with a plain-English reason. Color-coded so the eye lands on it.
     2. Collapsible TIMELINE — dated event strip (entry window, earnings
        blackout, R-target ETAs, time-stop) + missed-entry recovery.

   Decision-support only — never an auto-trade. Every number carries its
   reasoning in a tooltip.
   ========================================================================== */

type Props = { plan: EntryExitPlan | null | undefined };

const DECISION_STYLE: Record<string, { bg: string; border: string; fg: string; emoji: string }> = {
  ENTER:      { bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.45)',  fg: '#34d399', emoji: '🟢' },
  WAIT:       { bg: 'rgba(217,119,6,0.12)',   border: 'rgba(217,119,6,0.45)',   fg: '#fbbf24', emoji: '🟡' },
  HOLD_WATCH: { bg: 'rgba(148,163,184,0.10)', border: 'rgba(148,163,184,0.40)', fg: '#cbd5e1', emoji: '⚪️' },
  AVOID:      { bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.45)',   fg: '#f87171', emoji: '🔴' },
  CUT:        { bg: 'rgba(239,68,68,0.18)',   border: 'rgba(239,68,68,0.6)',    fg: '#fca5a5', emoji: '🔴' },
};

const DECISION_LABEL: Record<string, string> = {
  ENTER: 'ENTER', WAIT: 'WAIT', HOLD_WATCH: 'WATCH', AVOID: 'AVOID', CUT: 'CUT',
};

const KIND_ICON: Record<string, string> = {
  entry: '🎯', earnings: '📅', target: '📈', timestop: '⏱️',
};

export function EntryExitPlanBlock({ plan }: Props) {
  const [open, setOpen] = useState(false);
  if (!plan || !plan.decision) return null;

  const style = DECISION_STYLE[plan.decision] ?? DECISION_STYLE.HOLD_WATCH;
  const label = DECISION_LABEL[plan.decision] ?? plan.decision;
  const entry = plan.entry;
  const missed = plan.missed;

  return (
    <div style={{ marginTop: '0.4rem' }}>
      {/* DECISION banner — click toggles the timeline detail */}
      <button
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          textAlign: 'left',
          background: style.bg,
          border: `1px solid ${style.border}`,
          borderRadius: 6,
          padding: '0.45rem 0.6rem',
          cursor: 'pointer',
          color: 'inherit',
        }}
        title="Tap for the dated entry/exit timeline. Decision-support only — not financial advice."
      >
        <span style={{ fontSize: '0.95rem' }}>{style.emoji}</span>
        <span style={{
          fontWeight: 700, fontSize: '0.8rem', letterSpacing: '0.04em',
          color: style.fg, flexShrink: 0,
          fontFamily: '"SF Mono", Menlo, monospace',
        }}>{label}</span>
        <span style={{
          fontSize: '0.72rem', color: 'var(--cm-slate, #94a3b8)',
          overflow: 'hidden', textOverflow: 'ellipsis',
          lineHeight: 1.25,
        }}>{plan.decision_reason}</span>
        <span style={{ marginLeft: 'auto', flexShrink: 0, opacity: 0.5, fontSize: '0.7rem' }}>
          {open ? '▲' : '▼'}
        </span>
      </button>

      {/* Entry zone summary line — always visible when actionable / waiting */}
      {entry && (plan.decision === 'ENTER' || plan.decision === 'WAIT') && (
        <div style={{
          fontSize: '0.68rem', color: 'var(--cm-slate, #94a3b8)',
          margin: '0.25rem 0 0', fontFamily: '"SF Mono", Menlo, monospace',
        }}>
          {entry.status === 'wait_trigger' && (
            <>trigger ${entry.trigger.toFixed(2)} · window→{shortDate(entry.valid_through)}</>
          )}
          {entry.status === 'actionable' && (
            <>zone ${entry.zone_lo.toFixed(2)}-${entry.zone_hi.toFixed(2)} · valid→{shortDate(entry.valid_through)}</>
          )}
          {(entry.status === 'missed_extended' || entry.status === 'above_zone') && missed && (
            <>+{entry.distance_pct.toFixed(1)}% past pivot · next ${missed.next_entry_lo.toFixed(2)}</>
          )}
        </div>
      )}

      {/* Collapsible detail */}
      {open && (
        <div style={{
          marginTop: '0.4rem', padding: '0.5rem 0.6rem',
          background: 'rgba(0,0,0,0.18)', borderRadius: 6,
          border: '1px solid var(--rule, #2a2a2a)',
        }}>
          {/* Missed-entry recovery */}
          {missed && (
            <div style={{ marginBottom: '0.55rem' }}>
              <div style={{ fontSize: '0.68rem', fontWeight: 600, color: '#fbbf24', marginBottom: 2 }}>
                ↩ Missed entry — next best
              </div>
              <div style={{ fontSize: '0.68rem', color: 'var(--ink-body, #c7c9d1)', lineHeight: 1.4 }}>
                {missed.next_entry_note}
              </div>
              <div style={{ fontSize: '0.64rem', color: 'var(--cm-slate, #94a3b8)', marginTop: 2 }}>
                {missed.rescan_hint}
              </div>
            </div>
          )}

          {/* Timeline strip */}
          <div style={{ fontSize: '0.68rem', fontWeight: 600, color: 'var(--cm-slate)', marginBottom: '0.3rem' }}>
            Timeline
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.25rem' }}>
            {plan.timeline.map((ev, i) => (
              <li key={`${ev.key}-${i}`} style={{
                display: 'grid', gridTemplateColumns: 'auto auto 1fr', gap: '0.5rem',
                alignItems: 'baseline', fontSize: '0.68rem',
              }}>
                <span style={{ fontSize: '0.72rem' }}>{KIND_ICON[ev.kind] ?? '•'}</span>
                <span style={{
                  fontFamily: '"SF Mono", Menlo, monospace', color: 'var(--cm-slate)',
                  whiteSpace: 'nowrap',
                }}>
                  {ev.when === plan.as_of ? 'now' : shortDate(ev.when)}
                </span>
                <span style={{ color: 'var(--ink-body, #c7c9d1)' }}>{ev.label}</span>
              </li>
            ))}
          </ul>

          {/* Exit rules footer */}
          {plan.exit && (
            <div style={{
              marginTop: '0.5rem', paddingTop: '0.45rem',
              borderTop: '1px dashed var(--rule, #2a2a2a)',
              fontSize: '0.64rem', color: 'var(--cm-slate)', lineHeight: 1.45,
            }}>
              {plan.exit.stop != null && (
                <div>🛑 Stop ${plan.exit.stop.toFixed(2)} — {plan.exit.stop_rule}</div>
              )}
              <div>⏱️ {plan.exit.time_stop_rule}</div>
              {plan.regime?.chop && (
                <div style={{ color: '#fbbf24' }}>
                  ⚠ ADX {plan.regime.adx?.toFixed(0)} — chop regime, breakout edge weak.
                </div>
              )}
            </div>
          )}

          <div style={{ marginTop: '0.45rem', fontSize: '0.58rem', color: 'var(--cm-slate)', opacity: 0.7 }}>
            Decision-support from your scan signals — not financial advice. Verify before trading.
          </div>
        </div>
      )}
    </div>
  );
}

function shortDate(iso: string): string {
  // "2026-06-08" → "Jun 8"
  try {
    const [, m, d] = iso.split('-').map(Number);
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${months[m - 1]} ${d}`;
  } catch {
    return iso;
  }
}
