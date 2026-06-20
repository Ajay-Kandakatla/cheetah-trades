/**
 * AddHoldingForm — type in a position by hand (how many shares + price paid).
 *
 * POSTs to /portfolio { ticker, shares, cost_basis } where cost_basis is the
 * TOTAL spent (shares × price). The row then merges into the same holdings
 * table / rollup / attribution as Plaid-synced and CSV-imported positions,
 * tagged source="manual". Re-adding the same ticker updates it (upsert).
 */
import { useState, type CSSProperties } from 'react';
import { API } from '../lib/apiBase';

interface Props {
  onAdded: () => void | Promise<void>;
}

const field: CSSProperties = {
  background: '#0e1117', color: '#cfd8e9', border: '1px solid #2c3a5a',
  borderRadius: 6, padding: '0.4rem 0.55rem', fontSize: '0.85rem',
};
const labelCol: CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 3,
  fontSize: '0.72rem', color: '#8b97ad',
};

export function AddHoldingForm({ onAdded }: Props) {
  const [symbol, setSymbol] = useState('');
  const [shares, setShares] = useState('');
  const [price, setPrice] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const sh = parseFloat(shares);
  const pr = parseFloat(price);
  const total = Number.isFinite(sh) && Number.isFinite(pr) ? sh * pr : null;
  const valid =
    symbol.trim().length > 0 &&
    Number.isFinite(sh) && sh > 0 &&
    Number.isFinite(pr) && pr >= 0;

  const submit = async () => {
    if (!valid || busy) return;
    const tkr = symbol.trim().toUpperCase();
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch(`${API}/portfolio`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: tkr, shares: sh, cost_basis: sh * pr }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setMsg({ ok: true, text: `Added ${sh} ${tkr} @ $${pr} (total $${(sh * pr).toLocaleString()})` });
      setSymbol(''); setShares(''); setPrice('');
      await onAdded();
    } catch (e) {
      setMsg({ ok: false, text: `Could not add — ${String(e)}` });
    } finally {
      setBusy(false);
    }
  };

  const onEnter = (e: React.KeyboardEvent) => { if (e.key === 'Enter') void submit(); };

  return (
    <section style={{
      marginBottom: '1rem', padding: '0.75rem 0.9rem', background: '#13161e',
      border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8,
    }}>
      <div style={{ marginBottom: 6 }}>
        <span className="eyebrow">Add a holding manually</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '0.6rem', flexWrap: 'wrap' }}>
        <label style={labelCol} htmlFor="ahf-symbol">
          Symbol
          <input id="ahf-symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)} onKeyDown={onEnter}
            placeholder="AAPL" style={{ ...field, width: 90, textTransform: 'uppercase' }} />
        </label>
        <label style={labelCol} htmlFor="ahf-shares">
          Shares (how many)
          <input id="ahf-shares" value={shares} onChange={(e) => setShares(e.target.value)} onKeyDown={onEnter}
            inputMode="decimal" placeholder="10" style={{ ...field, width: 110 }} />
        </label>
        <label style={labelCol} htmlFor="ahf-price">
          Price / share (how much)
          <input id="ahf-price" value={price} onChange={(e) => setPrice(e.target.value)} onKeyDown={onEnter}
            inputMode="decimal" placeholder="306.50" style={{ ...field, width: 130 }} />
        </label>
        <div style={{ fontSize: '0.72rem', color: '#8b97ad', minWidth: 90 }}>
          Total cost
          <div style={{ color: '#cfd8e9', fontSize: '0.95rem', fontWeight: 600 }}>
            {total != null ? `$${total.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '—'}
          </div>
        </div>
        <button type="button" onClick={() => void submit()} disabled={!valid || busy}
          style={{
            padding: '0.45rem 0.9rem',
            background: valid && !busy ? '#1f6f43' : '#222',
            color: '#dff3e6', border: '1px solid #2c5a3a', borderRadius: 6,
            cursor: valid && !busy ? 'pointer' : 'not-allowed', fontSize: '0.85rem',
          }}>
          {busy ? 'Adding…' : '+ Add'}
        </button>
      </div>
      {msg && (
        <div style={{ marginTop: 6, fontSize: '0.78rem', color: msg.ok ? '#4ad29a' : '#e86e6e' }}>
          {msg.text}
        </div>
      )}
      <div style={{ marginTop: 6, fontSize: '0.72rem', color: '#6b7689' }}>
        Tracked alongside your synced holdings (live price + P&amp;L + attribution). Re-adding the
        same symbol updates it; remove from the table with 🗑.
      </div>
    </section>
  );
}
