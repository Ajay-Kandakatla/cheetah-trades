import { useState } from 'react';
import { createPriceAlert, type AlertKind } from '../hooks/usePriceAlerts';

type Props = {
  symbol: string;
  currentPrice?: number | null;
  onClose: () => void;
  onCreated?: () => void;
};

const KIND_LABEL: Record<AlertKind, string> = {
  below: 'Price drops below',
  above: 'Price rises above',
  drop_pct: 'Drops % from now',
  rise_pct: 'Rises % from now',
};

export function PriceAlertModal({ symbol, currentPrice, onClose, onCreated }: Props) {
  const [kind, setKind] = useState<AlertKind>('below');
  const [level, setLevel] = useState<string>(
    currentPrice ? String((currentPrice * 0.95).toFixed(2)) : ''
  );
  const [whatsapp, setWhatsapp] = useState(true);
  const [browser, setBrowser] = useState(true);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const isPercent = kind === 'drop_pct' || kind === 'rise_pct';

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const num = Number(level);
    if (!Number.isFinite(num) || num <= 0) {
      setErr('Enter a positive number.');
      return;
    }
    setBusy(true);
    try {
      if (browser && typeof Notification !== 'undefined' && Notification.permission === 'default') {
        await Notification.requestPermission();
      }
      const channels: string[] = [];
      if (whatsapp) channels.push('whatsapp');
      if (browser) channels.push('browser');
      await createPriceAlert({ symbol, kind, level: num, channels, note: note || undefined });
      onCreated?.();
      onClose();
    } catch (e: any) {
      setErr(e?.message ?? 'Failed to save alert.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="sepa-drawer-backdrop" onClick={onClose}>
      <div
        className="sepa-drawer"
        style={{ maxWidth: 460 }}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="sepa-drawer__head">
          <div>
            <div className="eyebrow">Set alert</div>
            <h2>{symbol}</h2>
            {currentPrice != null && (
              <div className="sepa-drawer__exchange mono">last ${currentPrice}</div>
            )}
          </div>
          <button className="sepa-drawer__close" onClick={onClose}>×</button>
        </header>

        <form className="sepa-alert-form" onSubmit={submit}>
          <label className="sepa-alert-form__row">
            <span>Trigger</span>
            <select value={kind} onChange={(e) => setKind(e.target.value as AlertKind)}>
              {(Object.keys(KIND_LABEL) as AlertKind[]).map((k) => (
                <option key={k} value={k}>{KIND_LABEL[k]}</option>
              ))}
            </select>
          </label>

          <label className="sepa-alert-form__row">
            <span>{isPercent ? 'Percent' : 'Price'}</span>
            <input
              type="number"
              step="0.01"
              min="0"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              placeholder={isPercent ? 'e.g. 5' : 'e.g. 38.50'}
              autoFocus
            />
          </label>

          <fieldset className="sepa-alert-form__channels">
            <legend>Notify via</legend>
            <label>
              <input type="checkbox" checked={whatsapp} onChange={(e) => setWhatsapp(e.target.checked)} />
              WhatsApp
            </label>
            <label>
              <input type="checkbox" checked={browser} onChange={(e) => setBrowser(e.target.checked)} />
              Browser
            </label>
          </fieldset>

          <label className="sepa-alert-form__row">
            <span>Note</span>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="optional — shown in the alert"
              maxLength={120}
            />
          </label>

          {err && <p className="sepa-alert-form__err">{err}</p>}

          <div className="sepa-alert-form__actions">
            <button type="button" onClick={onClose} className="btn-ghost">Cancel</button>
            <button type="submit" disabled={busy} className="btn-primary">
              {busy ? 'Saving…' : 'Save alert'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
