/* RulesInfo — the "ℹ️ Rules" pill every board wears, and the panel behind it.
 *
 * Ajay 2026-09-06: each board carries a short info section listing its rules.
 * The rules TEXT comes from GET /supply-demand/rules (hooks/useRulesInfo) —
 * the backend owns every number, next to the constant it describes — so
 * nothing here is authored by the UI: the panel renders exactly what the
 * endpoint sends (three labelled lists + a note), omits an empty list, and
 * renders NOTHING when the fetch failed or the section key is unknown, so a
 * board never shows a blank pill. Open / closed is remembered per section in
 * localStorage (best effort — private mode and blocked storage are fine).
 *
 * `compact` = the smaller chip for a filter bar; its panel floats under the
 * pill instead of taking a full row of the toolbar. The default pill is a
 * flex sibling: inside a wrapping toolbar the panel drops to its own line.
 *
 * Chip look: `.sepa-chip` (styles.css) — the same pill as the SEPA filter bar
 * and the Alerts kind filters, token-coloured so it follows the theme.
 */
import { useState, type CSSProperties } from 'react';
import { useRulesInfo, type RulesSection } from '../hooks/useRulesInfo';
import { trackFeature } from '../lib/usageTracker';

const LS_PREFIX = 'rulesInfo:open:';

export function readOpen(section: string): boolean {
  try {
    return localStorage.getItem(LS_PREFIX + section) === '1';
  } catch {
    return false;
  }
}

export function writeOpen(section: string, open: boolean): void {
  try {
    localStorage.setItem(LS_PREFIX + section, open ? '1' : '0');
  } catch {
    /* storage blocked — the pill still toggles for this render */
  }
}

/** The three lists, in the order the panel shows them. Only non-empty ones render. */
export const RULE_LISTS: ReadonlyArray<{ key: 'picks' | 'stops' | 'alerts'; label: string }> = [
  { key: 'picks', label: 'Stock picks' },
  { key: 'stops', label: 'Stops & targets' },
  { key: 'alerts', label: 'Alerts' },
];

const PILL: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap', textTransform: 'none',
};
const PILL_COMPACT: CSSProperties = { ...PILL, fontSize: '0.68rem', padding: '2px 8px' };

const PANEL: CSSProperties = {
  background: 'var(--bg-raised)',
  border: '1px solid var(--rule, var(--hairline))',
  borderRadius: 8,
  padding: '0.6rem 0.8rem',
  fontSize: '0.76rem',
  lineHeight: 1.45,
  color: 'var(--ink)',
  fontWeight: 400,
  textTransform: 'none',
  textAlign: 'left',
};
const PANEL_BLOCK: CSSProperties = {
  ...PANEL, flexBasis: '100%', width: '100%', boxSizing: 'border-box', margin: '0.35rem 0 0.2rem',
};
const PANEL_POP: CSSProperties = {
  ...PANEL, position: 'absolute', top: 'calc(100% + 4px)', left: 0, zIndex: 40,
  width: 'min(340px, 86vw)', boxShadow: '0 8px 24px rgba(0,0,0,0.28)',
};
const TITLE: CSSProperties = { fontWeight: 700, fontSize: '0.8rem', marginBottom: '0.3rem' };
const LABEL: CSSProperties = {
  fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
  color: 'var(--ink-subtle)', margin: '0.45rem 0 0.15rem',
};
const UL: CSSProperties = { margin: 0, paddingLeft: '1.1rem' };
const NOTE: CSSProperties = { marginTop: '0.5rem', fontSize: '0.68rem', color: 'var(--ink-subtle)' };

function Panel({ s, style }: { s: RulesSection; style: CSSProperties }) {
  const heading = [s.emoji, s.title].filter(Boolean).join(' ');
  return (
    <div style={style} data-testid="rules-info-panel" role="region" aria-label={`${s.title || 'Rules'} — rules`}>
      {heading && <div style={TITLE}>{heading}</div>}
      {RULE_LISTS.map(({ key, label }) => (
        s[key].length > 0 ? (
          <div key={key} data-testid={`rules-info-${key}`}>
            <div style={LABEL}>{label}</div>
            <ul style={UL}>
              {s[key].map((line, i) => <li key={i}>{line}</li>)}
            </ul>
          </div>
        ) : null
      ))}
      {s.note && <div style={NOTE} data-testid="rules-info-note">{s.note}</div>}
    </div>
  );
}

export function RulesInfo({ section, compact = false }: { section: string; compact?: boolean }) {
  const { section: s } = useRulesInfo(section);
  const [open, setOpen] = useState<boolean>(() => readOpen(section));
  if (!s) return null;

  const toggle = () => {
    const next = !open;
    setOpen(next);
    writeOpen(section, next);
    if (next) trackFeature(`rules:${section}`);   // which boards' rules he reads
  };

  const pill = (
    <button
      type="button"
      className={`sepa-chip${open ? ' is-active' : ''}`}
      style={compact ? PILL_COMPACT : PILL}
      aria-expanded={open}
      onClick={toggle}
      data-testid="rules-info-pill"
      title={`${s.title || 'Rules'} — the rules this board plays by`}
    >
      ℹ️ Rules
    </button>
  );

  if (compact) {
    return (
      <span className="rules-info rules-info--compact" style={{ position: 'relative', display: 'inline-flex' }}>
        {pill}
        {open && <Panel s={s} style={PANEL_POP} />}
      </span>
    );
  }
  return (
    <>
      {pill}
      {open && <Panel s={s} style={PANEL_BLOCK} />}
    </>
  );
}
