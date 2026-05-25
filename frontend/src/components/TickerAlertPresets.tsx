/* TickerAlertPresets — quick-toggle alerts for a specific ticker.

   Replaces the "type in a number" workflow for common cases. User taps
   "📉 -5%" and a percentage alert is created for this symbol. Tap again
   to remove it. Custom-level alerts still available via the existing
   PriceAlertModal — the "+ Custom level" button at the bottom.

   Active alerts for this ticker are shown above the presets so the user
   can see + remove what's currently set. */
import { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  createPriceAlert, deletePriceAlert, listPriceAlerts,
  type PriceAlert, type AlertKind,
} from '../hooks/usePriceAlerts';

type Props = {
  symbol: string;
  currentPrice?: number | null;
  onClose: () => void;
  /** Show a "+ Custom level…" button that opens the typed-input modal.
   *  Pass a handler that opens it; we don't import the modal here to
   *  keep the bundle slim. */
  onCustomLevel?: () => void;
};

type Preset = {
  id:    string;
  label: string;
  emoji: string;
  kind:  AlertKind;
  level: number;
  tone:  'good' | 'warn' | 'bad';
  hint:  string;
};

const PRESETS: Preset[] = [
  // ── Downside (drop from now) ────────────────────────────────────────
  { id: 'drop_3',  label: '−3%',  emoji: '📉', kind: 'drop_pct', level: 3,  tone: 'warn',
    hint: 'Mild dip — fires if price drops 3% from now.' },
  { id: 'drop_5',  label: '−5%',  emoji: '📉', kind: 'drop_pct', level: 5,  tone: 'warn',
    hint: 'Healthy pullback. Often a buy-the-dip cue in a strong trend.' },
  { id: 'drop_7',  label: '−7%',  emoji: '🛑', kind: 'drop_pct', level: 7,  tone: 'bad',
    hint: 'Minervini\'s hard-cap stop loss. If you bought today, this is where you sell.' },
  { id: 'drop_10', label: '−10%', emoji: '🛑', kind: 'drop_pct', level: 10, tone: 'bad',
    hint: 'Past the normal stop. Either you held too long or the trade was sized wrong.' },
  { id: 'drop_12', label: '−12%', emoji: '⚠️', kind: 'drop_pct', level: 12, tone: 'bad',
    hint: 'Structural break per Minervini. Exit immediately — don\'t wait for close.' },
  { id: 'drop_15', label: '−15%', emoji: '☠️', kind: 'drop_pct', level: 15, tone: 'bad',
    hint: 'Catastrophic — already double the max-loss line. Should never reach here.' },

  // ── Upside (rise from now) ──────────────────────────────────────────
  { id: 'rise_5',  label: '+5%',  emoji: '📈', kind: 'rise_pct', level: 5,  tone: 'good',
    hint: 'First +R move after entry. Tighten the stop to breakeven here.' },
  { id: 'rise_10', label: '+10%', emoji: '📈', kind: 'rise_pct', level: 10, tone: 'good',
    hint: 'Trade is paying. Watch for sell-into-strength signals at +20% (3R).' },
  { id: 'rise_20', label: '+20%', emoji: '🚀', kind: 'rise_pct', level: 20, tone: 'good',
    hint: 'Sell 25-50% partial — Minervini\'s 3-to-1 rule. Trail the rest.' },
  { id: 'rise_30', label: '+30%', emoji: '🏆', kind: 'rise_pct', level: 30, tone: 'good',
    hint: 'Big winner. Move trailing stop to 21-day EMA. Don\'t let it round-trip.' },
];

const toneColor = (t: Preset['tone']) =>
    t === 'good' ? 'var(--positive, #10b981)'
  : t === 'warn' ? 'var(--warn, #d97706)'
  :                'var(--negative, #ef4444)';

// toneBg removed — active state now uses the full tone color as
// background for high contrast (see button style below).

export function TickerAlertPresets({ symbol, currentPrice, onClose, onCustomLevel }: Props) {
  const [alerts, setAlerts] = useState<PriceAlert[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const all = await listPriceAlerts();
      setAlerts(all.filter(a => a.symbol === symbol.toUpperCase()));
    } catch (e: any) {
      setErr(String(e?.message || e));
    }
  }, [symbol]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  /** True if an alert matching this preset (kind + level) already exists. */
  const isActive = (p: Preset): PriceAlert | undefined =>
    (alerts || []).find(a => a.kind === p.kind && Math.abs(a.level - p.level) < 0.01);

  const toggle = async (p: Preset) => {
    setBusy(p.id);
    setErr(null);
    try {
      const existing = isActive(p);
      if (existing) {
        await deletePriceAlert(existing._id);
      } else {
        await createPriceAlert({
          symbol: symbol.toUpperCase(),
          kind:   p.kind,
          level:  p.level,
          channels: ['push', 'browser'],
          note:   `${p.label} preset`,
        });
      }
      await refresh();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(null);
    }
  };

  const removeOne = async (a: PriceAlert) => {
    setBusy(a._id);
    try { await deletePriceAlert(a._id); await refresh(); }
    finally { setBusy(null); }
  };

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '1rem', overflowY: 'auto',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-raised, #1a1a1a)', color: 'var(--ink, inherit)',
          border: '1px solid var(--rule, #333)', borderRadius: 8,
          width: '100%', maxWidth: 520, maxHeight: '90vh', overflow: 'auto',
          padding: '1.1rem 1.3rem',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.5rem' }}>
          <div>
            <div className="eyebrow">Quick alerts</div>
            <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.3rem' }}>
              {symbol}
              {currentPrice != null && (
                <span style={{ color: 'var(--cm-slate)', fontSize: '0.78rem', marginLeft: '0.4rem' }}>
                  last ${currentPrice.toFixed(2)}
                </span>
              )}
            </h2>
          </div>
          <button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 0, color: 'var(--cm-slate)', cursor: 'pointer', fontSize: '1.5rem', lineHeight: 1 }}>×</button>
        </div>
        <p style={{ fontSize: '0.78rem', color: 'var(--cm-slate)', margin: '0 0 0.7rem' }}>
          Tap any tile to toggle it ON or OFF. You can have several active at once —
          e.g., −7% (Minervini stop) AND −12% (structural break) both firing.
          Each ON tile is a fully independent alert.
        </p>

        {err && <div style={{ color: 'var(--negative)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>{err}</div>}

        {/* Current alerts for this symbol */}
        {alerts && alerts.length > 0 && (
          <section style={{ marginBottom: '0.9rem', padding: '0.55rem 0.7rem', background: 'rgba(255,255,255,0.02)', borderRadius: 4 }}>
            <div className="eyebrow" style={{ fontSize: '0.66rem', marginBottom: '0.3rem' }}>Active alerts ({alerts.length})</div>
            <div style={{ display: 'grid', gap: '0.3rem' }}>
              {alerts.map(a => (
                <div key={a._id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem' }}>
                  <span className="mono">
                    {a.kind === 'drop_pct' ? `📉 −${a.level}%` :
                     a.kind === 'rise_pct' ? `📈 +${a.level}%` :
                     a.kind === 'below'    ? `↓ $${a.level}` :
                                              `↑ $${a.level}`}
                    {a.note && <span style={{ color: 'var(--cm-slate)', marginLeft: '0.4rem' }}>· {a.note}</span>}
                  </span>
                  <button
                    onClick={() => removeOne(a)}
                    disabled={busy === a._id}
                    style={{
                      background: 'none', border: '1px solid var(--rule, #555)',
                      color: 'var(--negative)', padding: '2px 8px', borderRadius: 3,
                      cursor: 'pointer', fontSize: '0.7rem',
                    }}
                  >✕ remove</button>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Preset grid — split into Downside (drop) and Upside (rise) groups */}
        {(['drop', 'rise'] as const).map((dir) => {
          const groupPresets = PRESETS.filter(p =>
            (dir === 'drop' && p.kind === 'drop_pct') ||
            (dir === 'rise' && p.kind === 'rise_pct'));
          const label = dir === 'drop' ? '📉 Price drops (from now)' : '📈 Price rises (from now)';
          return (
            <div key={dir} style={{ marginBottom: '0.6rem' }}>
              <div className="eyebrow" style={{ fontSize: '0.66rem', marginBottom: '0.3rem', color: dir === 'drop' ? 'var(--negative)' : 'var(--positive)' }}>
                {label}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(85px, 1fr))', gap: '0.35rem' }}>
                {groupPresets.map(p => {
                  const active = isActive(p);
                  const color = toneColor(p.tone);
                  return (
                    <button
                      key={p.id}
                      onClick={() => toggle(p)}
                      disabled={busy === p.id}
                      title={`${p.hint}\n\n${active ? 'Currently ON — tap to turn OFF' : 'Currently OFF — tap to turn ON'}`}
                      aria-pressed={!!active}
                      style={{
                        position: 'relative',
                        // Vertical-flex layout keeps emoji, label, and the
                        // small "ON/OFF" caption stacked with predictable
                        // spacing instead of relying on an absolutely-
                        // positioned pill (which used to overlap the
                        // percentage when the tile was short).
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '0.15rem',
                        padding: '0.55rem 0.4rem 0.5rem',
                        minHeight: 88,                 // so all three lines breathe
                        background: active ? color : 'transparent',
                        border: '2px solid',
                        borderColor: active ? color : 'var(--rule, #555)',
                        borderRadius: 6,
                        cursor: 'pointer', fontFamily: 'inherit',
                        color: 'inherit',
                        textAlign: 'center',
                        opacity: busy === p.id ? 0.6 : 1,
                        transition: 'all 0.15s',
                        boxShadow: active ? `0 0 0 3px ${color}33` : 'none',  // glow on active
                      }}
                    >
                      {/* Corner status dot — top-right, doesn't compete for
                          center real-estate with the percentage label.
                          The strong tile background already signals ON/OFF;
                          this is just an explicit secondary cue. */}
                      <span
                        aria-hidden
                        style={{
                          position: 'absolute',
                          top: 4, right: 4,
                          width: 14, height: 14,
                          borderRadius: '50%',
                          background: active ? '#fff' : 'transparent',
                          border: '1.5px solid',
                          borderColor: active ? '#fff' : 'var(--rule, #666)',
                          color: active ? color : 'transparent',
                          fontSize: 10, lineHeight: '11px',
                          fontWeight: 900,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {active ? '✓' : ''}
                      </span>
                      <div style={{ fontSize: '1.25rem', opacity: active ? 1 : 0.55, lineHeight: 1 }}>
                        {p.emoji}
                      </div>
                      <div style={{
                        fontSize: '1rem', fontWeight: 800,
                        color: active ? '#fff' : 'var(--ink, inherit)',
                        lineHeight: 1.1,
                      }}>
                        {p.label}
                      </div>
                      {/* Compact ON/OFF caption beneath the percentage —
                          inline (not absolute), so it can never overlap
                          the label that sits above it. */}
                      <div style={{
                        fontSize: '0.6rem',
                        fontWeight: 700,
                        letterSpacing: '0.08em',
                        color: active ? '#fff' : 'var(--cm-slate, #888)',
                        opacity: active ? 0.9 : 0.7,
                      }}>
                        {active ? 'ON' : 'OFF'}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}

        {/* Custom level escape hatch */}
        {onCustomLevel && (
          <button
            onClick={() => { onCustomLevel(); onClose(); }}
            style={{
              marginTop: '0.8rem',
              width: '100%',
              padding: '0.6rem',
              background: 'transparent',
              border: '1px dashed var(--rule, #555)',
              borderRadius: 4,
              cursor: 'pointer',
              color: 'var(--cm-slate)',
              fontFamily: 'inherit',
              fontSize: '0.82rem',
            }}
          >
            + Custom level (type exact price)…
          </button>
        )}

        <p style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: '0.7rem', lineHeight: 1.5 }}>
          Percent alerts fire when price moves the specified % from the moment the alert was created. They survive across sessions and fire once per move. To change the global -12% emergency threshold, edit it in Notifications → Alert thresholds.
        </p>
      </div>
    </div>,
    document.body,
  );
}
