/* ==========================================================================
   PositionSignal — compact "hold or sell?" read for ONE portfolio position.

   Auto-evaluates from the holding's cost basis (no form) and renders the same
   verdict the SEPA cards/PositionLens use: HOLD / TIGHTEN / TRIM / SELL, plus
   the R-multiple, the recommended Minervini stop, and the R1/R2/R3 target ladder.
   Same backend logic — GET /sepa/position-lens/{symbol} (sell_signals.evaluate +
   stage + trade_plan). Works for any ticker, not just scan candidates.
   ========================================================================== */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type Verdict = 'FULL_EXIT' | 'REDUCE' | 'TIGHTEN_STOP' | 'HOLD';
type LensTrigger = { rule: string; verdict: Verdict; msg: string };
type LensResponse = {
  ok: boolean;
  reason?: string;
  verdict?: Verdict;
  summary?: string;
  pnl?: { gain_pct: number; gain_dollars?: number; current_value?: number };
  r_multiple?: number | null;
  current?: { last_close: number; stage: number; rs_rank: number; rating: string; score: number };
  stop?: { used: number; source: string; distance_pct: number };
  targets?: { r1?: number | null; r2?: number | null; r3?: number | null };
  triggers?: LensTrigger[];
  signals_panel?: { stage?: number; stage_label?: string; sepa_score?: number };
};

const TONE: Record<Verdict, { color: string; bg: string; label: string }> = {
  FULL_EXIT:    { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  label: '🚨 SELL' },
  REDUCE:       { color: '#d97706', bg: 'rgba(217,119,6,0.12)',  label: '⚠️ TRIM' },
  TIGHTEN_STOP: { color: '#eab308', bg: 'rgba(234,179,8,0.12)',  label: '🔒 TIGHTEN STOP' },
  HOLD:         { color: '#10b981', bg: 'rgba(16,185,129,0.12)', label: '✓ HOLD' },
};

const f2 = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function PositionSignal({ symbol, entry, shares, stop }: {
  symbol: string;
  entry: number | null;
  shares?: number | null;
  stop?: number | null;
}) {
  const [data, setData] = useState<LensResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [openWhy, setOpenWhy] = useState(false);

  useEffect(() => {
    if (!entry || entry <= 0) { setData(null); return; }
    let cancelled = false;
    setLoading(true);
    const p = new URLSearchParams({ entry: String(entry) });
    if (shares) p.set('shares', String(shares));
    if (stop) p.set('stop', String(stop));
    fetch(`${API}/sepa/position-lens/${encodeURIComponent(symbol)}?${p}`, { credentials: 'include' })
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setData({ ok: false, reason: String(e?.message || e) }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [symbol, entry, shares, stop]);

  if (!entry || entry <= 0) {
    return <div className="pos-sig pos-sig--muted mono">Add your cost basis to get a hold/sell read.</div>;
  }
  if (loading && !data) return <div className="pos-sig pos-sig--muted mono">…reading {symbol}</div>;
  if (!data || data.ok === false) {
    return <div className="pos-sig pos-sig--muted mono">No read for {symbol}{data?.reason ? ` — ${data.reason}` : ''}.</div>;
  }

  const tone = data.verdict ? TONE[data.verdict] : TONE.HOLD;
  const cur = data.current?.last_close ?? null;
  const tg = data.targets ?? {};
  const pctTo = (t: number) => (cur ? `${t >= cur ? '+' : ''}${(((t - cur) / cur) * 100).toFixed(1)}%` : '');
  const targetRows: Array<{ k: string; v: number | null | undefined }> = [
    { k: 'R1', v: tg.r1 }, { k: 'R2', v: tg.r2 }, { k: 'R3', v: tg.r3 },
  ];

  return (
    <div className="pos-sig">
      <div className="pos-sig__head">
        <span className="pos-sig__verdict" style={{ color: tone.color, borderColor: tone.color, background: tone.bg }}>
          {tone.label}
        </span>
        {data.r_multiple != null && (
          <span
            className="pos-sig__r mono"
            title="Open profit in units of initial risk (R)"
            style={{ color: data.r_multiple >= 1 ? '#10b981' : data.r_multiple < 0 ? '#ef4444' : 'inherit' }}
          >
            {data.r_multiple >= 0 ? '+' : ''}{data.r_multiple}R
          </span>
        )}
        {data.signals_panel?.stage != null && (
          <span className="pos-sig__chip mono" title="Weinstein 4-stage">
            S{data.signals_panel.stage} {data.signals_panel.stage_label ?? ''}
          </span>
        )}
        {data.summary && <span className="pos-sig__summary">{data.summary}</span>}
      </div>

      {/* stop + R-target ladder — the same R1/R2/R3 the cards use, measured off your basis */}
      <div className="pos-sig__targets mono">
        {data.stop?.used != null && (
          <span className="pos-sig__t pos-sig__t--stop" title={`Recommended stop · ${data.stop.source}`}>
            stop ${f2(data.stop.used)} <em>({Math.abs(data.stop.distance_pct)}% below)</em>
          </span>
        )}
        {targetRows.filter((t) => t.v != null).map((t) => (
          <span key={t.k} className="pos-sig__t pos-sig__t--tgt" title={`${t.k} target`}>
            {t.k} ${f2(t.v as number)} <em>{pctTo(t.v as number)}</em>
          </span>
        ))}
      </div>

      {data.triggers && data.triggers.length > 0 && (
        <>
          <button className="pos-sig__why-btn mono" onClick={() => setOpenWhy((v) => !v)}>
            {openWhy ? '▾ why this read' : `▸ why this read (${data.triggers.length})`}
          </button>
          {openWhy && (
            <ul className="pos-sig__why">
              {data.triggers.map((t, i) => (
                <li key={i}>
                  <span style={{ color: TONE[t.verdict].color }}>{t.verdict.replace('_', ' ')}</span> · {t.msg}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
