/* /portfolio — Plaid-backed broker portfolio view.
 *
 * Render state machine (three branches):
 *   A. Plaid env keys missing → "Setup Plaid" instructions card.
 *   B. Configured, no linked broker → "Connect Fidelity via Plaid" CTA.
 *   C. Linked → heatmap + R-multiples table + sync timestamp.
 *
 * State A and B never load react-plaid-link's modal. State C uses
 * usePlaidLink() only after the user clicks Connect AND a link_token
 * has been minted server-side — so an offline backend doesn't break
 * the page render.
 *
 * R-multiple math is in `computeR()` below; entry/stop come from the
 * /portfolio/position-meta store, current_price comes from Plaid
 * (refreshed with a yfinance live overlay).
 */
import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { InfoButton } from '../components/InfoButton';
import {
  useStatus,
  useHoldings,
  usePositionMeta,
  fetchLinkToken,
  exchangePublicToken,
  disconnectPlaid,
  uploadFidelityCsv,
  syncCsvFromDisk,
  ackAlert,
  runAlertsNow,
  useAlertState,
  type HoldingRow,
  type PortfolioStatus,
  type CsvImportResult,
  type AlertStateRow,
} from '../hooks/usePortfolio';

// ──────────────────────────────────────────────────────────────────────
// Plaid Link is opened via the imperative window.Plaid.create() API
// from Plaid's hosted CDN script (loaded in index.html). The npm
// package react-plaid-link exports a React hook (usePlaidLink) but
// NOT a Plaid global — that global only exists when link-initialize.js
// is loaded. We use the imperative API so the open flow stays outside
// React's render path (single click → popup, no extra state plumbing).
// ──────────────────────────────────────────────────────────────────────
async function openPlaidLink(linkToken: string, onSuccess: (publicToken: string) => void) {
  try {
    const PlaidGlobal: any = (window as any).Plaid;
    if (!PlaidGlobal || typeof PlaidGlobal.create !== 'function') {
      throw new Error(
        'window.Plaid.create() not available — the Plaid Link CDN script '
        + '(https://cdn.plaid.com/link/v2/stable/link-initialize.js) failed '
        + 'to load. Check the network tab and any ad-blocker / CSP rules.'
      );
    }
    const handler = PlaidGlobal.create({
      token: linkToken,
      onSuccess: (publicToken: string) => onSuccess(publicToken),
      onExit: (err: any, _meta: any) => {
        // User-cancelled is err=null — no alert needed. Real Plaid errors
        // (mfa fail, institution down, etc.) come through with err set.
        if (err) {
          // eslint-disable-next-line no-console
          console.warn('Plaid Link exited with error', err);
        }
      },
    });
    if (handler && typeof handler.open === 'function') {
      handler.open();
      return;
    }
    throw new Error('Plaid.create() returned no usable handler');
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('Plaid Link failed to open', err);
    alert('Failed to open Plaid Link. See console for details.');
  }
}

// ──────────────────────────────────────────────────────────────────────
// R-multiple — reward / risk for a long position.
//   R = (price - entry) / (entry - stop)
// Positive when price has moved your way; negative when underwater.
// Source: Van Tharp's position-sizing math, also used by Minervini.
// ──────────────────────────────────────────────────────────────────────
function computeR(currentPrice: number | null, entry: number | null, stop: number | null): number | null {
  if (currentPrice == null || entry == null || stop == null) return null;
  if (entry === stop) return null;
  const risk = entry - stop;
  const reward = currentPrice - entry;
  return reward / risk;
}

function formatMoney(v: number | null | undefined, sign: boolean = false): string {
  if (v == null) return '—';
  const sgn = sign && v > 0 ? '+' : '';
  return `${sgn}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}${v < 0 ? '' : ''}`
    .replace('$-', '-$');
}

function formatPct(v: number | null | undefined, sign: boolean = true): string {
  if (v == null) return '—';
  const sgn = sign && v > 0 ? '+' : '';
  return `${sgn}${v.toFixed(1)}%`;
}

function formatR(v: number | null | undefined): string {
  if (v == null) return '—';
  const sgn = v > 0 ? '+' : '';
  return `${sgn}${v.toFixed(2)}R`;
}

function timeAgo(epochSec: number | null | undefined): string {
  if (!epochSec) return 'never';
  const dt = Date.now() / 1000 - epochSec;
  if (dt < 60) return 'just now';
  if (dt < 3600) return `${Math.round(dt / 60)} min ago`;
  if (dt < 86400) return `${Math.round(dt / 3600)} h ago`;
  return `${Math.round(dt / 86400)} d ago`;
}

// Heatmap color — green tint for positive P&L, red tint for negative.
// Saturation maxes out at ±20% so a single huge winner doesn't drain
// color out of the rest of the grid.
function heatColor(plPct: number | null | undefined): string {
  if (plPct == null) return 'rgba(120,120,140,0.18)';
  const clamped = Math.max(-20, Math.min(20, plPct));
  const intensity = Math.abs(clamped) / 20;
  if (clamped >= 0) {
    return `rgba(16, 185, 129, ${0.18 + intensity * 0.5})`;   // emerald
  }
  return `rgba(239, 68, 68, ${0.18 + intensity * 0.5})`;       // red
}

const PageInfo = (
  <>
    <p>
      Your Fidelity holdings imported via Plaid, augmented with R-multiples
      so you can see at a glance whether each position is up or down vs.
      its risk unit.
    </p>
    <p>
      <strong>R-multiple</strong> = (current price − entry) / (entry − stop).
      Setting your stop is what tells the math how big "1R" is for the
      position. Targets are typically 2–3R for swing trades.
    </p>
    <p>
      Plaid handles the Fidelity login — your broker password is never
      typed into this app. We only store the long-lived access token Plaid
      gives us, encrypted at rest.
    </p>
  </>
);

// ──────────────────────────────────────────────────────────────────────
// State A — Plaid env keys missing. Owner-facing setup steps.
// ──────────────────────────────────────────────────────────────────────
function NotConfiguredState() {
  return (
    <div className="sepa-empty-card" style={{ maxWidth: 640 }}>
      <div className="eyebrow">Setup</div>
      <h2 style={{ marginTop: 8 }}>Plaid not configured yet</h2>
      <p style={{ color: '#9aa8c8' }}>
        The portfolio page imports broker holdings via Plaid. Add API keys
        to enable it.
      </p>
      <ol style={{ paddingLeft: '1.25rem', lineHeight: 1.75 }}>
        <li>
          Sign up at{' '}
          <a href="https://dashboard.plaid.com" target="_blank" rel="noreferrer">
            dashboard.plaid.com
          </a>
        </li>
        <li>Enable the <strong>Investments</strong> product on your team</li>
        <li>Copy <code>client_id</code> and the <code>development</code> secret</li>
        <li>
          Add to <code>backend/.env</code>:
          <pre style={{
            background: '#101019',
            padding: '0.75rem 1rem',
            borderRadius: 8,
            marginTop: '0.5rem',
            fontSize: '0.85rem',
            color: '#cfd8e9',
            overflowX: 'auto',
          }}>{`PLAID_CLIENT_ID=...
PLAID_SECRET=...
PLAID_ENV=development
PLAID_TOKEN_ENC_KEY=...   # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`}</pre>
        </li>
        <li>Restart the <code>api</code> container: <code>docker compose restart api</code></li>
      </ol>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// State B — configured but no linked broker. Single CTA → Plaid Link.
// ──────────────────────────────────────────────────────────────────────
function ConnectState({ onLinked }: { onLinked: () => void }) {
  const [opening, setOpening] = useState(false);
  const [linkErr, setLinkErr] = useState<string | null>(null);

  const onConnect = async () => {
    setOpening(true);
    setLinkErr(null);
    try {
      const linkToken = await fetchLinkToken();
      await openPlaidLink(linkToken, async (publicToken) => {
        try {
          await exchangePublicToken(publicToken);
          onLinked();
        } catch (e) {
          setLinkErr(String(e));
        }
      });
    } catch (e) {
      setLinkErr(String(e));
    } finally {
      setOpening(false);
    }
  };

  return (
    <div className="sepa-empty-card" style={{ maxWidth: 560 }}>
      <div className="eyebrow">Connect broker</div>
      <h2 style={{ marginTop: 8 }}>Not connected yet</h2>
      <p style={{ color: '#9aa8c8' }}>
        Click the button below to link your Fidelity account through Plaid.
        Plaid hosts the Fidelity login — we never see your password.
      </p>
      <button
        type="button"
        onClick={onConnect}
        disabled={opening}
        style={{
          marginTop: '0.75rem',
          padding: '0.6rem 1.25rem',
          borderRadius: 8,
          border: 'none',
          background: '#3b82f6',
          color: '#fff',
          fontSize: '0.95rem',
          fontWeight: 600,
          cursor: opening ? 'wait' : 'pointer',
        }}
      >
        {opening ? 'Opening Plaid…' : 'Connect Fidelity via Plaid'}
      </button>
      {linkErr && (
        <p style={{ marginTop: '0.75rem', color: '#fca5a5', fontSize: '0.88rem' }}>
          Couldn't open Plaid: {linkErr}
        </p>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Inline editor for entry / stop / target. PUT lands on
// /portfolio/position-meta and triggers a meta refetch on success.
// ──────────────────────────────────────────────────────────────────────
function MetaEditor({
  symbol,
  initial,
  onSave,
}: {
  symbol: string;
  initial: { entry: number | null; stop: number | null; target: number | null };
  onSave: (fields: { entry: number | null; stop: number | null; target: number | null }) => void;
}) {
  const [entry, setEntry]   = useState<string>(initial.entry == null ? '' : String(initial.entry));
  const [stop, setStop]     = useState<string>(initial.stop == null ? '' : String(initial.stop));
  const [target, setTarget] = useState<string>(initial.target == null ? '' : String(initial.target));

  const parse = (s: string): number | null => {
    const t = s.trim();
    if (t === '') return null;
    const n = Number(t);
    return Number.isFinite(n) ? n : null;
  };

  const submit = () => onSave({ entry: parse(entry), stop: parse(stop), target: parse(target) });

  const inputStyle: CSSProperties = {
    width: 70,
    background: 'transparent',
    border: '1px solid #2c2f3a',
    borderRadius: 4,
    color: '#e6e8ee',
    padding: '2px 6px',
    fontSize: '0.85rem',
  };

  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      <input
        type="number"
        step="0.01"
        placeholder="entry"
        value={entry}
        onChange={(e) => setEntry(e.target.value)}
        onBlur={submit}
        style={inputStyle}
        aria-label={`${symbol} entry`}
      />
      <input
        type="number"
        step="0.01"
        placeholder="stop"
        value={stop}
        onChange={(e) => setStop(e.target.value)}
        onBlur={submit}
        style={inputStyle}
        aria-label={`${symbol} stop`}
      />
      <input
        type="number"
        step="0.01"
        placeholder="target"
        value={target}
        onChange={(e) => setTarget(e.target.value)}
        onBlur={submit}
        style={inputStyle}
        aria-label={`${symbol} target`}
      />
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// State C — connected. The big "real" view: heatmap + table + sync.
// ──────────────────────────────────────────────────────────────────────
function ConnectedState({ status, onDisconnected }: { status: PortfolioStatus; onDisconnected: () => void }) {
  const { data, loading, error, refresh } = useHoldings(true);
  const { metas, set: setMeta } = usePositionMeta();
  const navigate = useNavigate();
  const [disconnecting, setDisconnecting] = useState(false);
  const [csvUploading, setCsvUploading] = useState(false);
  const [csvResult, setCsvResult] = useState<CsvImportResult | null>(null);
  const [alertRunning, setAlertRunning] = useState(false);
  const [alertResult, setAlertResult] = useState<{ scanned?: number; pushed?: number; by_verdict?: Record<string, number>; error?: string } | null>(null);
  const { rows: alertStateRows, refresh: refreshAlertState } = useAlertState();

  // Build a per-symbol lookup so each row in the Positions table can show
  // its alert state (fired N × today · last at HH:MM · ack'd or not).
  const alertBySymbol = useMemo(() => {
    const m: Record<string, AlertStateRow> = {};
    for (const r of alertStateRows) m[r.symbol.toUpperCase()] = r;
    return m;
  }, [alertStateRows]);

  const onRunAlerts = async (kind: 'intraday' | 'eod_brief' | 'eod_escalate') => {
    setAlertRunning(true);
    setAlertResult(null);
    try {
      const res = await runAlertsNow(kind);
      setAlertResult({
        scanned:    res.scanned,
        pushed:     res.pushed,
        by_verdict: res.by_verdict,
      });
      await refreshAlertState();
    } catch (e) {
      setAlertResult({ error: String(e) });
    } finally {
      setAlertRunning(false);
    }
  };

  // Push-notification acknowledgement: when the user taps a portfolio
  // alert on their phone, the push opens /portfolio?ack=<symbol>. We
  // POST that ticker to /portfolio/alerts/ack so the 15-min re-ringing
  // stops for the rest of the day, then strip the query param so a
  // refresh doesn't re-ack (idempotent but noisy).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sym = params.get('ack');
    if (!sym) return;
    ackAlert(sym).catch(() => { /* silent — the alert state is best-effort */ });
    params.delete('ack');
    const qs = params.toString();
    const url = window.location.pathname + (qs ? `?${qs}` : '');
    window.history.replaceState({}, '', url);
  }, []);

  const onCsvFile = async (file: File) => {
    setCsvUploading(true);
    setCsvResult(null);
    try {
      const res = await uploadFidelityCsv(file);
      setCsvResult(res);
      // On success, refetch holdings so CSV rows show up in heatmap/table.
      if (res.ok) await refresh();
    } catch (e) {
      setCsvResult({ ok: false, reason: String(e) });
    } finally {
      setCsvUploading(false);
    }
  };

  // "Sync from disk" — ingest the newest CSV from backend/fidelity/
  // without going through the file-picker. Cheaper UX for users who
  // already drop their Fidelity export into a watched folder (cloud-
  // sync, scripted save, etc).
  const onSyncFromDisk = async () => {
    setCsvUploading(true);
    setCsvResult(null);
    try {
      const res = await syncCsvFromDisk(false);
      setCsvResult(res);
      if (res.ok) await refresh();
    } catch (e) {
      setCsvResult({ ok: false, reason: String(e) });
    } finally {
      setCsvUploading(false);
    }
  };

  const onDisconnect = async () => {
    const inst = status.institution_name || 'your broker';
    // Native confirm() is enough here — destructive enough to need a
    // pause, not destructive enough to deserve a custom modal.
    if (!window.confirm(`Disconnect ${inst}? Your holdings will stop syncing until you re-link.`)) return;
    setDisconnecting(true);
    try {
      const res = await disconnectPlaid();
      if (res.removed) {
        onDisconnected();
      } else {
        alert(`Disconnect failed: ${res.error || 'unknown error'}`);
      }
    } catch (e) {
      alert(`Disconnect failed: ${String(e)}`);
    } finally {
      setDisconnecting(false);
    }
  };

  // Join meta in by symbol so the inline editor starts from the current
  // saved values without an extra fetch.
  const metaBySymbol = useMemo(() => {
    const m: Record<string, { entry: number | null; stop: number | null; target: number | null }> = {};
    for (const row of metas) {
      m[row.symbol] = {
        entry:  row.entry ?? null,
        stop:   row.stop ?? null,
        target: row.target ?? null,
      };
    }
    return m;
  }, [metas]);

  // The backend already computes pl_pct, pl_dollars, r_multiple — but
  // when the user edits entry/stop inline, the next render needs to
  // reflect their new numbers BEFORE the backend has refetched. Compute
  // R locally on top of whatever the backend returned for the price.
  const rows: HoldingRow[] = useMemo(() => {
    return (data?.rows || []).map((r) => {
      const meta = metaBySymbol[r.symbol] || { entry: r.entry, stop: r.stop, target: r.target };
      const r_multiple = computeR(r.current_price, meta.entry, meta.stop);
      return {
        ...r,
        entry:  meta.entry,
        stop:   meta.stop,
        target: meta.target,
        r_multiple,
      };
    });
  }, [data?.rows, metaBySymbol]);

  // Two totals to track:
  //   - holdingsValue: sum of per-position rows (only useful where Plaid
  //     returned per-position detail — e.g. self-directed brokerage, HSA).
  //   - accountsValue: sum of account-level balances (the REAL broker total,
  //     covers 401k / RSU / restricted plans where Plaid only returns the
  //     aggregate balance, not the underlying positions).
  // We display accountsValue (when present) as the headline number because
  // it matches what Fidelity shows the user. holdingsValue is still used
  // for per-row P&L math because it's the only thing with cost basis.
  const accounts = data?.accounts || [];
  const accountsValue = accounts.reduce(
    (sum, a) => sum + ((a.balances?.current as number | null) ?? 0),
    0,
  );
  const holdingsValue = rows.reduce((sum, r) => sum + (r.current_value ?? 0), 0);
  const totalValue = accountsValue > 0 ? accountsValue : holdingsValue;
  const totalCost = rows.reduce((sum, r) => sum + (r.cost_basis ?? 0), 0);
  // P&L can only be computed against rows with cost basis. When most of
  // the value lives in accounts without per-position detail (401k, RSU),
  // the % gain shown reflects only the priced rows — flagged in the UI
  // by the "X of Y accounts priced" note in the Accounts section.
  const totalPL = holdingsValue - totalCost;
  const totalPLPct = totalCost > 0 ? (holdingsValue / totalCost - 1) * 100 : null;

  return (
    <>
      <div style={{
        display:        'flex',
        justifyContent: 'space-between',
        alignItems:     'center',
        flexWrap:       'wrap',
        gap:            '0.75rem',
        marginBottom:   '1rem',
      }}>
        <div>
          <div className="eyebrow">{status.institution_name || 'Fidelity'}</div>
          <div style={{ color: '#9aa8c8', fontSize: '0.9rem' }}>
            Last synced: {timeAgo(status.last_sync)}
            {data && (
              <span style={{ marginLeft: 8, fontSize: '0.8rem' }}>
                ({data.fresh ? 'live' : 'cached'})
              </span>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.78rem', color: '#9aa8c8' }}>Portfolio value</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 600 }}>{formatMoney(totalValue)}</div>
            <div style={{
              fontSize: '0.9rem',
              color: totalPL >= 0 ? '#10b981' : '#ef4444',
            }}>
              {formatMoney(totalPL, true)} ({formatPct(totalPLPct)})
            </div>
          </div>
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            title="Refresh from Plaid"
            style={{
              padding: '0.45rem 0.7rem',
              background: 'transparent',
              border: '1px solid #2c2f3a',
              borderRadius: 6,
              color: '#cfd8e9',
              cursor: loading ? 'wait' : 'pointer',
            }}
          >
            {loading ? '…' : '↻'}
          </button>
          <button
            type="button"
            onClick={onDisconnect}
            disabled={disconnecting}
            title="Disconnect broker (revokes Plaid access token)"
            className="portfolio-disconnect"
            style={{
              padding: '0.45rem 0.7rem',
              background: 'transparent',
              border: '1px solid #2c2f3a',
              borderRadius: 6,
              color: '#7a8499',
              fontSize: '0.82rem',
              cursor: disconnecting ? 'wait' : 'pointer',
              transition: 'color 0.15s, border-color 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#ef4444';
              e.currentTarget.style.borderColor = '#ef4444';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#7a8499';
              e.currentTarget.style.borderColor = '#2c2f3a';
            }}
          >
            {disconnecting ? 'Disconnecting…' : 'Disconnect'}
          </button>
        </div>
      </div>

      {error && (
        <div className="sepa-empty-card" style={{ marginBottom: '1rem' }}>
          <div className="eyebrow">Could not load holdings</div>
          <p style={{ color: '#fca5a5', fontSize: '0.9rem' }}>{error}</p>
          <button onClick={() => refresh()}>Retry</button>
        </div>
      )}

      {/* Fidelity CSV upload — manual fallback when Plaid Investments Trial
          withholds per-position detail. The user clicks "Download" on the
          Fidelity Positions page and drops the file here; backend parses,
          stores in portfolio.store, and the rows show up in the heatmap +
          table tagged `source: "csv"`. */}
      <section style={{
        marginBottom: '1rem',
        padding:      '0.75rem 0.9rem',
        background:   '#13161e',
        border:       '1px solid rgba(255,255,255,0.06)',
        borderRadius: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span className="eyebrow">Import Fidelity CSV</span>
          <InfoButton inline title="Import Fidelity CSV">
            <p>
              Plaid's Investments product in Trial tier only returns balances
              for active Fidelity brokerage sub-accounts — not the line-item
              positions. Until your team's Investments Production access is
              approved, you can dump Fidelity's own CSV here and get the same
              heatmap + R-multiples + alerts treatment.
            </p>
            <p>
              <strong>How to get the CSV:</strong> Fidelity → Accounts & Trade
              → Positions → "Download" button (top right). Save the file and
              upload it here.
            </p>
            <p>
              Re-uploading replaces the previous import for the same account.
              Plaid-returned positions are preserved separately and take
              priority when both sources have the same ticker.
            </p>
          </InfoButton>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
          <input
            id="fidelity-csv-input"
            type="file"
            accept=".csv,text/csv"
            disabled={csvUploading}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onCsvFile(f);
              // Reset so the same file can be re-selected (chrome quirk).
              e.target.value = '';
            }}
            style={{ display: 'none' }}
          />
          <label
            htmlFor="fidelity-csv-input"
            style={{
              display:      'inline-flex',
              alignItems:   'center',
              gap:          6,
              padding:      '0.45rem 0.8rem',
              background:   csvUploading ? '#222' : '#1f2a44',
              color:        '#cfd8e9',
              border:       '1px solid #2c3a5a',
              borderRadius: 6,
              cursor:       csvUploading ? 'wait' : 'pointer',
              fontSize:     '0.85rem',
            }}
          >
            {csvUploading ? 'Uploading…' : '📄 Choose Fidelity CSV'}
          </label>
          <button
            type="button"
            onClick={onSyncFromDisk}
            disabled={csvUploading}
            title="Read the newest CSV from backend/fidelity/ on the server"
            style={{
              display:      'inline-flex',
              alignItems:   'center',
              gap:          6,
              padding:      '0.45rem 0.8rem',
              background:   csvUploading ? '#222' : 'transparent',
              color:        '#cfd8e9',
              border:       '1px solid #2c3a5a',
              borderRadius: 6,
              cursor:       csvUploading ? 'wait' : 'pointer',
              fontSize:     '0.85rem',
              fontFamily:   'inherit',
            }}
          >
            🔄 Sync from backend/fidelity/
          </button>
          <span style={{ fontSize: '0.78rem', color: '#7a8499' }}>
            From Fidelity Positions page → Download
          </span>
        </div>
        {csvResult && (
          <div style={{
            marginTop:    8,
            padding:      '0.5rem 0.7rem',
            background:   csvResult.ok ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
            border:       `1px solid ${csvResult.ok ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)'}`,
            borderRadius: 6,
            fontSize:     '0.83rem',
            color:        csvResult.ok ? '#10b981' : '#fca5a5',
          }}>
            {csvResult.ok ? (
              <>
                ✓ Imported <strong>{csvResult.written || csvResult.parsed_summary?.imported_rows || 0}</strong> positions
                {csvResult.parsed_summary?.total_value
                  ? ` worth ${formatMoney(csvResult.parsed_summary.total_value)}`
                  : ''}
                {csvResult.parsed_summary?.skipped
                  ? ` · ${csvResult.parsed_summary.skipped} skipped (pending / non-position rows)`
                  : ''}
              </>
            ) : (
              <>
                ✗ {csvResult.reason || 'Upload failed'}
                {csvResult.hint && (
                  <div style={{ marginTop: 4, color: '#9aa8c8', fontSize: '0.78rem' }}>
                    {csvResult.hint}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </section>

      {/* Alerts — manual trigger + result summary. Cron handles the scheduled
          runs (every 15 min during market hours + 3:00 PM + 3:30 PM EOD).
          The buttons here are for ad-hoc testing or when the user wants to
          see verdicts NOW without waiting for the next cron tick. */}
      <section style={{
        marginBottom: '1rem',
        padding:      '0.75rem 0.9rem',
        background:   '#13161e',
        border:       '1px solid rgba(255,255,255,0.06)',
        borderRadius: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span className="eyebrow">Alerts</span>
          <InfoButton inline title="Position alerts">
            <p>
              Three scheduled pipelines monitor your positions and fire Web Push
              when action is needed:
            </p>
            <ul style={{ paddingLeft: '1.1rem', marginTop: 4 }}>
              <li>
                <strong>Intraday</strong> — every 15 min, 9:30–15:45 ET. Pushes when
                live price ≤ your stop, or ≤ 7% below entry, or ≤ 12% below avg cost.
                Re-rings every 15 min until you tap the notification. Max 12/day/ticker.
              </li>
              <li>
                <strong>EOD brief</strong> — 3:00 PM ET. One push per position with the
                Minervini verdict (FULL_EXIT / REDUCE / TIGHTEN / HOLD) using the
                same logic as the SEPA cards.
              </li>
              <li>
                <strong>EOD escalate</strong> — 3:30 PM ET. Re-pings any unacknowledged
                SELL verdict from the 3:00 PM round.
              </li>
            </ul>
            <p>
              Tap a notification to acknowledge — stops the re-ringing for that
              ticker for the rest of the day.
            </p>
          </InfoButton>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => onRunAlerts('intraday')}
            disabled={alertRunning}
            title="Live stop-breach check against all your positions"
            style={{
              padding:      '0.4rem 0.7rem',
              background:   alertRunning ? '#222' : 'transparent',
              color:        '#cfd8e9',
              border:       '1px solid #2c3a5a',
              borderRadius: 6,
              cursor:       alertRunning ? 'wait' : 'pointer',
              fontSize:     '0.82rem',
              fontFamily:   'inherit',
            }}
          >
            🔔 Run intraday now
          </button>
          <button
            type="button"
            onClick={() => onRunAlerts('eod_brief')}
            disabled={alertRunning}
            title="3:00 PM verdict — runs position_lens against all your positions"
            style={{
              padding:      '0.4rem 0.7rem',
              background:   alertRunning ? '#222' : 'transparent',
              color:        '#cfd8e9',
              border:       '1px solid #2c3a5a',
              borderRadius: 6,
              cursor:       alertRunning ? 'wait' : 'pointer',
              fontSize:     '0.82rem',
              fontFamily:   'inherit',
            }}
          >
            📊 Run EOD brief now
          </button>
          <button
            type="button"
            onClick={() => onRunAlerts('eod_escalate')}
            disabled={alertRunning}
            title="3:30 PM escalation — re-pings unacked SELL verdicts"
            style={{
              padding:      '0.4rem 0.7rem',
              background:   alertRunning ? '#222' : 'transparent',
              color:        '#cfd8e9',
              border:       '1px solid #2c3a5a',
              borderRadius: 6,
              cursor:       alertRunning ? 'wait' : 'pointer',
              fontSize:     '0.82rem',
              fontFamily:   'inherit',
            }}
          >
            ⏰ Run EOD escalate
          </button>
          <span style={{ fontSize: '0.72rem', color: '#7a8499' }}>
            Cron handles scheduled runs automatically
          </span>
        </div>
        {alertResult && (
          <div style={{
            marginTop:    8,
            padding:      '0.45rem 0.65rem',
            background:   alertResult.error ? 'rgba(239,68,68,0.08)' : 'rgba(120,150,200,0.08)',
            border:       `1px solid ${alertResult.error ? 'rgba(239,68,68,0.25)' : 'rgba(120,150,200,0.25)'}`,
            borderRadius: 6,
            fontSize:     '0.8rem',
            color:        alertResult.error ? '#fca5a5' : '#cfd8e9',
          }}>
            {alertResult.error ? (
              <>✗ {alertResult.error}</>
            ) : (
              <>
                Scanned <strong>{alertResult.scanned ?? 0}</strong> · Pushed <strong>{alertResult.pushed ?? 0}</strong>
                {alertResult.by_verdict && Object.keys(alertResult.by_verdict).length > 0 && (
                  <span style={{ marginLeft: 8 }}>
                    · {Object.entries(alertResult.by_verdict)
                        .map(([v, n]) => `${n} ${v}`)
                        .join(', ')}
                  </span>
                )}
                {alertResult.pushed === 0 && alertResult.scanned !== 0 && (
                  <div style={{ marginTop: 4, fontSize: '0.72rem', color: '#7a8499' }}>
                    0 pushed — either no triggers fired, or no push subscriptions registered yet
                    (enable browser notifications via /notifications).
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </section>

      {/* Accounts — one card per linked Plaid account.
          Some accounts (401k, RSU, employer plans) only return aggregate
          balances via Plaid — no per-position breakdown. Showing the cards
          here makes the "missing positions" honest rather than hiding the
          balance entirely. Account-level balances also feed the headline
          Portfolio value above. */}
      {accounts.length > 0 && (
        <section style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span className="eyebrow">Accounts ({accounts.length})</span>
            <InfoButton inline title="Accounts">
              <p>
                Every account Plaid found in your Fidelity login. The headline
                "Portfolio value" is the sum of these balances — that's what
                Fidelity itself shows.
              </p>
              <p>
                Some account types (401k, RSU, restricted plans) only return
                an aggregate balance via Plaid — no per-position breakdown.
                Those accounts contribute to the total but won't appear in the
                Heatmap or Positions table below. Self-directed brokerage and
                HSA accounts return full per-position detail.
              </p>
            </InfoButton>
          </div>
          <div style={{
            display:             'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap:                 '0.6rem',
          }}>
            {accounts.map((a) => {
              const bal = (a.balances?.current as number | null) ?? null;
              const subtype = (a.subtype || a.type || '').toString().toUpperCase();
              const positionsInAccount = rows.filter(r => r.account_id === a.account_id).length;
              return (
                <div
                  key={`acct-${a.account_id}`}
                  style={{
                    padding:      '0.65rem 0.75rem',
                    background:   '#13161e',
                    border:       '1px solid rgba(255,255,255,0.06)',
                    borderRadius: 8,
                  }}
                >
                  <div style={{
                    display:        'flex',
                    justifyContent: 'space-between',
                    alignItems:     'baseline',
                    gap:            8,
                  }}>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#e6e8ee' }}>
                      {a.name || a.official_name || 'Account'}
                    </div>
                    {a.mask && (
                      <div style={{ fontSize: '0.72rem', color: '#7a8499', fontFamily: 'monospace' }}>
                        ····{a.mask}
                      </div>
                    )}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#9aa8c8', marginTop: 2 }}>
                    {subtype || 'INVESTMENT'}
                  </div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#e6e8ee', marginTop: 4 }}>
                    {formatMoney(bal)}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#7a8499', marginTop: 2 }}>
                    {positionsInAccount > 0
                      ? `${positionsInAccount} position${positionsInAccount === 1 ? '' : 's'}`
                      : 'balance only — no position detail'}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Heatmap */}
      {rows.length > 0 && (
        <section style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span className="eyebrow">Heatmap</span>
            <InfoButton inline title="Heatmap">
              <p>
                Each cell is a position, colored by total P&L %. Click a cell to
                open the SEPA detail for that ticker.
              </p>
            </InfoButton>
          </div>
          <div style={{
            display:             'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
            gap:                 '0.5rem',
          }}>
            {rows.map((r) => (
              <button
                key={`heat-${r.symbol}-${r.account_id || ''}`}
                onClick={(e) => {
                  const url = `/sepa/${encodeURIComponent(r.symbol)}`;
                  if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) {
                    window.open(url, '_blank', 'noopener,noreferrer');
                  } else {
                    navigate(url, { state: { from: '/portfolio', label: 'Portfolio' } });
                  }
                }}
                style={{
                  textAlign:    'left',
                  padding:      '0.65rem 0.75rem',
                  background:   heatColor(r.pl_pct),
                  border:       '1px solid rgba(255,255,255,0.06)',
                  borderRadius: 8,
                  color:        '#e6e8ee',
                  cursor:       'pointer',
                  fontFamily:   'inherit',
                }}
              >
                <div
                  style={{
                    fontWeight:   600,
                    fontSize:     '0.95rem',
                    overflow:     'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace:   'nowrap',
                    // Constrain to tile width so 18-char synthetic symbols
                    // like RESTRICTED.STOCK.UNITS or Fidelity target-date
                    // tickers (BTC.LP.IDX.2055.H) don't bleed into the
                    // next grid cell. minmax(120px,1fr) on the grid means
                    // the inner label needs its own clamp.
                    maxWidth:     '100%',
                  }}
                  title={r.symbol || ''}
                >
                  {r.symbol || '—'}
                </div>
                <div style={{ fontSize: '0.78rem', opacity: 0.92 }}>
                  {formatPct(r.pl_pct)}
                </div>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Table */}
      <section>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span className="eyebrow">Positions</span>
          <InfoButton inline title="Positions">
            <p>
              Sortable list of every position from your linked Fidelity account.
              The <em>entry / stop / target</em> columns are user-typed (Plaid
              doesn't have these) — set them inline to make the R-multiple math
              meaningful for that row.
            </p>
            <p>
              <strong>R</strong> = (current price − entry) / (entry − stop).
              Positive R means you're in profit relative to your risk unit.
            </p>
          </InfoButton>
        </div>

        {loading && !data ? (
          <div className="sepa-empty-card" style={{ color: '#9a9aa3' }}>loading positions…</div>
        ) : rows.length === 0 ? (
          <div className="sepa-empty-card">
            <p>No positions returned by Plaid yet. If you just linked, hit ↻ above.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width:          '100%',
              borderCollapse: 'collapse',
              fontSize:       '0.9rem',
            }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #2c2f3a', color: '#9aa8c8', textAlign: 'left' }}>
                  <th style={{ padding: '0.5rem' }}>Symbol</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>Shares</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>Price</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>Cost</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>P&amp;L $</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>P&amp;L %</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>R</th>
                  <th style={{ padding: '0.5rem' }}>Entry / Stop / Target</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`row-${r.symbol}-${r.account_id || ''}`}
                       style={{ borderBottom: '1px solid #1d1f28' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 600 }}>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, flexWrap: 'wrap' }}>
                        <button
                          onClick={() => navigate(`/sepa/${encodeURIComponent(r.symbol)}`)}
                          style={{
                            background: 'transparent', border: 'none',
                            color: '#9aa8ff', cursor: 'pointer',
                            padding: 0, fontWeight: 600, fontFamily: 'inherit',
                            fontSize: '0.92rem',
                          }}
                        >
                          {r.symbol || '—'}
                        </button>
                        {r.source && r.source !== 'plaid' && (
                          <span
                            title={r.source === 'csv'
                              ? 'Imported from a Fidelity CSV upload — not from Plaid'
                              : 'Manually typed entry'}
                            style={{
                              fontSize: '0.6rem', fontWeight: 600, letterSpacing: '0.05em',
                              padding: '1px 5px', borderRadius: 3,
                              background: r.source === 'csv' ? 'rgba(245,158,11,0.18)' : 'rgba(120,120,140,0.18)',
                              color: r.source === 'csv' ? '#f59e0b' : '#9aa8c8',
                              textTransform: 'uppercase',
                            }}
                          >
                            {r.source}
                          </span>
                        )}
                        {(() => {
                          const a = alertBySymbol[(r.symbol || '').toUpperCase()];
                          if (!a) return null;
                          // Render verdict pill: green = HOLD, yellow = TIGHTEN,
                          // orange = REDUCE, red = FULL_EXIT. ack'd → muted gray.
                          const acked = !!a.acknowledged_at;
                          const verdictColor =
                              acked ? 'rgba(120,120,140,0.18)' :
                              a.verdict === 'FULL_EXIT' ? 'rgba(239,68,68,0.22)' :
                              a.verdict === 'REDUCE'    ? 'rgba(245,158,11,0.22)' :
                              a.verdict === 'TIGHTEN_STOP' ? 'rgba(234,179,8,0.18)' :
                                                          'rgba(16,185,129,0.18)';
                          const verdictText =
                              acked ? '#9aa8c8' :
                              a.verdict === 'FULL_EXIT' ? '#f87171' :
                              a.verdict === 'REDUCE'    ? '#f59e0b' :
                              a.verdict === 'TIGHTEN_STOP' ? '#eab308' :
                                                          '#10b981';
                          const lastTime = new Date(a.last_fired_at * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
                          const title = acked
                            ? `Ack'd at ${new Date((a.acknowledged_at || 0) * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })} · last fired ${lastTime} · ${a.fired_count}× today`
                            : `${a.verdict} · last fired ${lastTime} · ${a.fired_count}× today · NOT acknowledged`;
                          return (
                            <span
                              title={title}
                              style={{
                                fontSize: '0.6rem', fontWeight: 600, letterSpacing: '0.04em',
                                padding: '1px 5px', borderRadius: 3,
                                background: verdictColor,
                                color: verdictText,
                                textTransform: 'uppercase',
                              }}
                            >
                              {acked ? '✓' : '🔔'} {a.verdict.replace('_', ' ')}
                              {!acked && a.fired_count > 1 ? ` ×${a.fired_count}` : ''}
                            </span>
                          );
                        })()}
                      </div>
                      {r.name && (
                        <div style={{ fontSize: '0.75rem', color: '#6f7689' }}>
                          {r.name.length > 32 ? r.name.slice(0, 32) + '…' : r.name}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '0.5rem', textAlign: 'right' }}>
                      {r.quantity.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                    </td>
                    <td style={{ padding: '0.5rem', textAlign: 'right' }}>
                      {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—'}
                    </td>
                    <td style={{ padding: '0.5rem', textAlign: 'right' }}>
                      {formatMoney(r.cost_basis)}
                    </td>
                    <td style={{
                      padding: '0.5rem', textAlign: 'right',
                      color: (r.pl_dollars ?? 0) >= 0 ? '#10b981' : '#ef4444',
                    }}>
                      {formatMoney(r.pl_dollars, true)}
                    </td>
                    <td style={{
                      padding: '0.5rem', textAlign: 'right',
                      color: (r.pl_pct ?? 0) >= 0 ? '#10b981' : '#ef4444',
                    }}>
                      {formatPct(r.pl_pct)}
                    </td>
                    <td style={{
                      padding: '0.5rem', textAlign: 'right',
                      color: (r.r_multiple ?? 0) >= 0 ? '#10b981' : '#ef4444',
                    }}>
                      {formatR(r.r_multiple)}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      <MetaEditor
                        symbol={r.symbol}
                        initial={{
                          entry:  r.entry ?? null,
                          stop:   r.stop ?? null,
                          target: r.target ?? null,
                        }}
                        onSave={(fields) => setMeta(r.symbol, fields)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Page shell — picks state A/B/C off the /portfolio/status response.
// ──────────────────────────────────────────────────────────────────────
export default function PortfolioPage() {
  const { status, loading, error, refresh } = useStatus();
  // Re-poll status after a successful link so we flip to State C.
  const [, setNonce] = useState(0);
  useEffect(() => {
    // no-op — refresh() is what triggers re-render
  }, [refresh]);

  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">№ — Portfolio</div>
          <h1
            className="display sepa-page__h1"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
          >
            Portfolio
            <InfoButton inline title="Portfolio">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">
            Your live broker positions with R-multiples and a P&amp;L heatmap.
            Imported via Plaid — we never see your Fidelity password.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="sepa-empty-card" style={{ color: '#9a9aa3' }}>loading…</div>
      ) : error ? (
        <div className="sepa-empty-card">
          <div className="eyebrow">Couldn't load portfolio</div>
          <p style={{ color: '#fca5a5' }}>{error}</p>
          <button onClick={refresh}>Retry</button>
        </div>
      ) : !status ? (
        <div className="sepa-empty-card">No status returned.</div>
      ) : !status.plaid_configured ? (
        <NotConfiguredState />
      ) : !status.has_linked_account ? (
        <ConnectState onLinked={() => { refresh(); setNonce((n) => n + 1); }} />
      ) : (
        <ConnectedState
          status={status}
          onDisconnected={() => { refresh(); setNonce((n) => n + 1); }}
        />
      )}
    </div>
  );
}
