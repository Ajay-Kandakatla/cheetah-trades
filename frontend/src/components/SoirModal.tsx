/**
 * SoirModal — tap-to-open options-sentiment (SOIR) detail.
 *
 * Replaces the native `title` tooltip on the SOIR chip, which on mobile had no
 * close affordance and let the tap fall through to the card → SEPA details.
 * Portal + backdrop/✕ both stopPropagation + close on Escape, so dismissing
 * never navigates.
 */
import { useEffect } from 'react';
import { createPortal } from 'react-dom';

export type SoirData = {
  put_oi?: number | null;
  call_oi?: number | null;
  soir?: number | null;
  soir_percentile?: number | null;
  signal?: string | null;
  reason?: string | null;
};

export function SoirModal({ soir, symbol, onClose }: {
  soir: SoirData;
  symbol: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onEsc);
    return () => window.removeEventListener('keydown', onEsc);
  }, [onClose]);

  const sig = soir.signal ?? '—';
  const sigColor =
    sig === 'BULLISH' ? '#4ad29a' :
    sig === 'BEARISH' ? '#e86e6e' :
    sig === 'WATCH'   ? '#e8b25a' : '#cfd8e9';

  const Row = ({ label, value }: { label: string; value: string }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', padding: '3px 0', fontSize: '0.86rem' }}>
      <span style={{ color: '#9aa8c8' }}>{label}</span>
      <span className="mono" style={{ color: '#e6e6e6' }}>{value}</span>
    </div>
  );

  return createPortal(
    <div
      role="dialog" aria-modal="true" aria-label={`Options sentiment for ${symbol}`}
      onClick={(e) => { e.stopPropagation(); onClose(); }}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '1rem', zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#141416', color: '#e6e6e6',
          width: 'min(460px, calc(100vw - 2rem))',
          maxHeight: 'calc(100vh - 2rem)', overflowY: 'auto',
          border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12,
          padding: '1.1rem 1.2rem 1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.6rem' }}>
          <div>
            <div className="eyebrow" style={{ fontSize: '0.66rem', color: '#9aa8c8' }}>Options sentiment · {symbol}</div>
            <h2 style={{ margin: '0.1rem 0 0', fontSize: '1.1rem', fontFamily: '"Times New Roman", Georgia, serif', fontStyle: 'italic' }}>
              📊 Schaeffer's Open Interest Ratio
            </h2>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); onClose(); }} aria-label="Close"
            style={{ background: 'none', border: '1px solid rgba(255,255,255,0.15)', color: '#cfcfd4', padding: '4px 10px', borderRadius: 4, cursor: 'pointer', fontSize: '0.85rem', fontFamily: 'inherit' }}
          >✕</button>
        </div>

        <p style={{ fontSize: '0.8rem', color: '#aeb6c6', margin: '0 0 0.7rem', lineHeight: 1.5 }}>
          Put/call open-interest balance from the option chain. A high put/call ratio
          (crowd loaded with puts) is contrarian-bullish — those bearish bets unwinding
          can fuel upside.
        </p>

        <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '0.5rem' }}>
          <Row label="Puts open" value={(soir.put_oi ?? 0).toLocaleString()} />
          <Row label="Calls open" value={(soir.call_oi ?? 0).toLocaleString()} />
          <Row
            label="SOIR (put/call OI)"
            value={`${soir.soir != null ? soir.soir.toFixed(2) : '—'}${soir.soir_percentile != null ? `  (${soir.soir_percentile.toFixed(0)}th pct)` : ''}`}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '0.86rem' }}>
            <span style={{ color: '#9aa8c8' }}>Signal</span>
            <span style={{ color: sigColor, fontWeight: 700 }}>{sig}</span>
          </div>
        </div>

        {soir.reason && (
          <p style={{ fontSize: '0.82rem', color: '#cfd8e9', marginTop: '0.7rem', lineHeight: 1.5 }}>{soir.reason}</p>
        )}
      </div>
    </div>,
    document.body,
  );
}
