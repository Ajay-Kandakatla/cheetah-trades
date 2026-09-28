/* ChartMapsStrategiesTab — every Chart Maps tab as a paper lane, its journal
 * and the daily loss review (Trading page, 🗺️ Chart Maps view, 2026-09-27).
 *
 * Ajay 2026-09-27: "stop minerviews use all strategies from Most used from
 * Chart maps. All of them and journal the," — "Small: 0.25% risk, 15 open
 * max" — "analayze losses everyday with a routine or something and
 * restategize and confirm with me" — "Top 10 most-used first".
 *
 * Four parts, all from the server (no cap, rule or number is typed here):
 *   1. Program header — the master switch (ON asks first, OFF is one click),
 *      the caps line off `program.caps`, the open count "N / 15 (P pending)",
 *      this minute's entry and the last entry, and the rules list.
 *   2. Strategy table in SERVED order (usage order) — label + opens + rank,
 *      the row's note (LIST lanes buy a 🎯 READY demand reversal on a name
 *      from the tab's list, not the tab's own setup), the ON/OFF switch, a
 *      "lane switch OFF" warning, today's entries and top skip reasons (for
 *      the existing lanes too), the scoreboard with CIs, the prior chip and
 *      the snapshot age / stale reason.
 *   3. A folded "Not a lane" group.
 *   4. The latest daily review — loser lines and the proposal cards. Confirm
 *      ALWAYS goes through a dialog (level, key, before → after; a code-level
 *      card says nothing in the engine changes). Dismiss is one click and
 *      sends no config.
 *
 * Writes, owner-only:
 *   POST /trading/config {cm_program: bool}                 — master switch
 *   POST /trading/config {cm_lanes: {sid: bool}}            — one strategy
 *   POST /trading/review/proposals/{id}/confirm | /dismiss  — one card
 * It never places an order. PAPER forward measurement, UNMEASURED.
 */
import { useEffect, useState, type CSSProperties } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import {
  CODE_CONFIRM_TEXT, NO_REVIEW_TEXT, NO_STRATEGIES_TEXT, POLL_MS, UNMEASURED_TEXT,
  ageText, approxText, buyingNowText, capsLine, exitsSplit, expRText, fmtEt, fmtInt, fmtUsd, isKnownTab, isOpenProposal,
  laneLabel, lastTradeText, minuteText, openLine, priorText, proposalChange, sayReversal, staleText, topSkips,
  winText,
  type CmProposal, type CmReview, type CmStrategiesPayload, type CmStrategyRow,
} from '../lib/chartMapsLanes';

const C = { sub: 'var(--text-sub,#8a8f98)', good: '#3fb950', bad: '#f85149', warn: '#d29922', muted: '#94a3b8' };
const cell: CSSProperties = { padding: '6px 8px', borderBottom: '1px solid var(--hairline,#2a2a2a)', fontSize: 13, verticalAlign: 'top' };
const head: CSSProperties = { ...cell, color: C.sub, fontWeight: 500, textAlign: 'left', whiteSpace: 'nowrap' };
const chip: CSSProperties = { display: 'inline-block', fontSize: 11, fontWeight: 700, borderRadius: 999, padding: '1px 8px', border: '1px solid currentColor', whiteSpace: 'nowrap' };

async function post(path: string, body?: unknown): Promise<{ ok: boolean; json: unknown }> {
  const r = await fetch(`${API}${path}`, {
    method: 'POST', credentials: 'include',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let json: unknown = null;
  try { json = await r.json(); } catch { json = null; }
  return { ok: r.ok, json };
}

function errText(json: unknown, fallback: string): string {
  const d = json && typeof json === 'object' ? (json as { detail?: unknown }).detail : null;
  return typeof d === 'string' && d ? d : fallback;
}

function priorColor(text: string): string {
  if (/INVERTED|negative/.test(text)) return C.bad;
  if (/^MEASURED/.test(text) || text === 'inconclusive') return C.warn;
  return C.muted;
}

function evidenceText(e: unknown): string | null {
  if (e === null || e === undefined) return null;
  if (typeof e === 'string' || typeof e === 'number') return String(e);
  try { const s = JSON.stringify(e); return s.length > 240 ? `${s.slice(0, 240)}…` : s; } catch { return null; }
}

export function ChartMapsStrategiesTab({ onChanged }: { onChanged?: () => void }) {
  const [data, setData] = useState<CmStrategiesPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [review, setReview] = useState<CmReview | null>(null);
  const [reviewErr, setReviewErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [confirmProgram, setConfirmProgram] = useState(false);
  const [confirmSid, setConfirmSid] = useState<string | null>(null);
  const [confirmPid, setConfirmPid] = useState<string | null>(null);

  const load = async () => {
    try {
      const r = await fetch(`${API}/trading/strategies`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };
  const loadReview = async () => {
    try {
      const r = await fetch(`${API}/trading/review/latest?format=full`, { credentials: 'include' });
      if (r.status === 404) { setReview(null); setReviewErr(null); return; }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setReview(j && typeof j === 'object' && Object.keys(j).length ? j : null);
      setReviewErr(null);
    } catch (e) {
      setReviewErr(e instanceof Error ? e.message : String(e));
    }
  };
  const reload = async () => { await Promise.all([load(), loadReview()]); };
  useEffect(() => {
    void reload();
    const t = setInterval(() => { void reload(); }, POLL_MS);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const write = async (path: string, body: unknown | undefined, fail: string) => {
    setBusy(true);
    setActionErr(null);
    try {
      const res = await post(path, body);
      if (!res.ok) setActionErr(errText(res.json, fail));
      await reload();
      onChanged?.();
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : fail);
    } finally {
      setBusy(false);
      setConfirmProgram(false);
      setConfirmSid(null);
      setConfirmPid(null);
    }
  };
  const setProgram = (next: boolean) => write('/trading/config', { cm_program: next }, 'the program switch was refused');
  const setLane = (sid: string, next: boolean) => write('/trading/config', { cm_lanes: { [sid]: next } }, `the ${sid} switch was refused`);
  const confirmProposal = (pid: string) => write(`/trading/review/proposals/${encodeURIComponent(pid)}/confirm`, undefined, 'the confirm was refused');
  const dismissProposal = (pid: string) => write(`/trading/review/proposals/${encodeURIComponent(pid)}/dismiss`, undefined, 'the dismiss was refused');

  const p = data?.program ?? null;
  const enabled = !!p?.enabled;
  const isLive = p?.mode === 'live';
  const rows: CmStrategyRow[] = Array.isArray(data?.strategies) ? data!.strategies! : [];
  const notLanes = Array.isArray(data?.not_lanes) ? data!.not_lanes! : [];
  const proposals: CmProposal[] = Array.isArray(review?.proposals) ? review!.proposals! : [];
  const pending = proposals.find((x) => x.id === confirmPid) ?? null;
  const nOn = rows.filter((r) => r.enabled).length;

  return (
    <section aria-label="Chart Maps strategies" style={{ display: 'grid', gap: 14 }}>
      {/* 1 — program header */}
      <header style={{ display: 'grid', gap: 6 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>🗺️ Chart Maps strategies — paper program</h3>
          <span style={{ color: C.sub, fontSize: 12 }}>{p?.mode ? `${p.mode} account` : err ? `could not load: ${err}` : 'loading…'}</span>
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
            {confirmProgram ? (
              <span role="dialog" aria-label="Turn the Chart Maps program on?" style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', fontSize: 13 }}>
                Turn the Chart Maps program on? Paper only · {capsLine(p?.caps)}. The {nOn} strategies marked ON start buying.
                <button disabled={busy} onClick={() => { void setProgram(true); }}>Yes, on</button>
                <button disabled={busy} onClick={() => setConfirmProgram(false)}>No</button>
              </span>
            ) : (
              <button aria-pressed={enabled} disabled={busy || !p || isLive}
                      onClick={() => (enabled ? void setProgram(false) : setConfirmProgram(true))}>
                {enabled ? 'Program ON — turn off' : 'Program OFF — turn on'}
              </button>
            )}
          </span>
        </div>
        <p style={{ margin: 0, fontSize: 12, color: C.warn }}>{UNMEASURED_TEXT}</p>
        {isLive && <p style={{ margin: 0, fontSize: 12, color: C.bad }}>Live broker — the program never runs on a live account (paper and sim only).</p>}
        {p && (
          <div style={{ fontSize: 13, color: C.sub, display: 'grid', gap: 2 }}>
            <span data-testid="cm-caps">Caps: {capsLine(p.caps)}</span>
            <span data-testid="cm-open">{openLine(p)} · this minute: {minuteText(p.minute)} · last entry: {minuteText(p.last_entry, 'none yet')}</span>
            <span>
              Order: most-used Chart Maps tab first ({p.usage_order?.source === 'frozen' ? 'frozen 2026-09-27 counts' : 'tab opens'}
              {p.usage_order?.day ? `, read ${p.usage_order.day}` : ''}) · {nOn} of {rows.length} ON
              {p.started ? ` · measuring since ${p.started}` : ''}
            </span>
            {Array.isArray(p.rules) && p.rules.length > 0 && (
              <details>
                <summary style={{ cursor: 'pointer' }}>Rules ({p.rules.length})</summary>
                <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                  {p.rules.map((r, i) => <li key={i}>{sayReversal(r)}</li>)}
                </ul>
              </details>
            )}
          </div>
        )}
        {actionErr && <p role="alert" style={{ margin: 0, fontSize: 12, color: C.bad }}>⛔ {actionErr}</p>}
      </header>

      {/* 2 — the strategy table, served order */}
      <div style={{ overflowX: 'auto' }}>
        {data && rows.length === 0 ? (
          <p style={{ color: C.sub, fontSize: 13 }}>{NO_STRATEGIES_TEXT}</p>
        ) : (
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                <th style={head}>Strategy</th>
                <th style={head}>Switch</th>
                <th style={head}>Today</th>
                <th style={head} title="Closed paper trades since the program started. CIs are 95%; small n is flagged.">Scoreboard</th>
                <th style={head}>Snapshot</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const label = laneLabel(r.sid, r.label_tab);
                const sb = r.scoreboard ?? null;
                const skips = topSkips(r.today?.skips);
                const entries = Array.isArray(r.today?.entries) ? r.today!.entries! : [];
                const prior = priorText(r.prior);
                const stale = staleText(r.snapshot);
                const approx = approxText(sb);
                const laneOff = !!r.lane_switch && r.lane_switch.value === false;
                return (
                  <tr key={r.sid} data-sid={r.sid} aria-label={label} style={{ opacity: r.enabled ? 1 : 0.7 }}>
                    <td style={cell}>
                      <div style={{ fontWeight: 700 }}>{label}</div>
                      <div style={{ fontSize: 11, color: C.sub }}>
                        #{fmtInt(r.rank)} · {fmtInt(r.opens)} opens{r.default_on ? ' · top-10 default ON' : ''}
                      </div>
                      {r.note && <div style={{ fontSize: 11, color: C.sub, maxWidth: 320, whiteSpace: 'normal' }}>{sayReversal(r.note)}</div>}
                      <span style={{ ...chip, color: priorColor(prior) }} title={r.prior?.source ? `${r.prior?.note ?? ''} (${r.prior.source})` : r.prior?.note ?? ''}>
                        {prior}
                      </span>
                      {laneOff && (
                        <div style={{ fontSize: 11, color: C.warn }}>
                          ⚠ lane switch OFF ({r.lane_switch?.key}) — this lane's own switch stops its entries
                        </div>
                      )}
                    </td>
                    <td style={cell}>
                      {confirmSid === r.sid ? (
                        <span role="dialog" aria-label={`Turn ${label} on?`} style={{ display: 'grid', gap: 4, fontSize: 12 }}>
                          Turn {label} on? Paper only.
                          <span style={{ display: 'flex', gap: 4 }}>
                            <button disabled={busy} onClick={() => { void setLane(r.sid, true); }}>Yes, on</button>
                            <button disabled={busy} onClick={() => setConfirmSid(null)}>No</button>
                          </span>
                        </span>
                      ) : (
                        <button aria-pressed={!!r.enabled} aria-label={`${label} ${r.enabled ? 'ON' : 'OFF'}`} disabled={busy}
                                onClick={() => (r.enabled ? void setLane(r.sid, false) : setConfirmSid(r.sid))}>
                          {r.enabled ? 'ON' : 'OFF'}
                        </button>
                      )}
                      {r.switch?.value == null && <div style={{ fontSize: 10, color: C.sub }}>default</div>}
                      {buyingNowText(r) && <div data-testid="cm-buying-now" style={{ fontSize: 10, color: C.warn }}>{buyingNowText(r)}</div>}
                    </td>
                    <td style={cell}>
                      {entries.length ? (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {entries.map((e, i) => (
                            <span key={`${e.symbol}-${i}`}>
                              <TickerLink ticker={e.symbol} fromLabel="Auto-Pilot" showWatchlist={false} />
                              {e.at ? <span style={{ color: C.sub, fontSize: 11 }}> {fmtEt(e.at)}</span> : null}
                            </span>
                          ))}
                        </div>
                      ) : <span style={{ color: C.sub }}>no entry</span>}
                      {skips.length > 0 && (
                        <ul data-testid="cm-skips" style={{ margin: '4px 0 0', paddingLeft: 16, fontSize: 11, color: C.sub }}>
                          {skips.map(([reason, n]) => <li key={reason}>{sayReversal(reason)} ×{n}</li>)}
                        </ul>
                      )}
                    </td>
                    <td style={cell}>
                      <div>n {fmtInt(sb?.n_closed)} closed · {fmtInt(sb?.n_open)} open{sb?.small_n ? <span style={{ color: C.warn }}> · small n</span> : null}</div>
                      <div>win {winText(sb)} · exp {expRText(sb)}</div>
                      <div>{fmtUsd(sb?.total_usd)} · risk at entry {fmtUsd(sb?.open_risk_usd, false)} · last {lastTradeText(sb?.last_trade)}</div>
                      <div style={{ fontSize: 11, color: C.sub }}>
                        exits: {exitsSplit(sb?.exits_by_kind)}
                        {approx ? <span style={{ color: C.warn }}> · {approx}</span> : null}
                        {(sb?.n_unpriced ?? 0) > 0 ? <span> · {sb!.n_unpriced} unpriced</span> : null}
                      </div>
                    </td>
                    <td style={cell}>
                      {r.snapshot ? (
                        <>
                          <div>{fmtInt(r.snapshot.n)} READY · {ageText(r.snapshot.age_sec)}</div>
                          {stale && <div style={{ color: C.warn, fontSize: 11 }}>{stale}</div>}
                          {Array.isArray(r.snapshot.top) && r.snapshot.top.length > 0 && (
                            <div style={{ fontSize: 11, color: C.sub }}>{r.snapshot.top.slice(0, 5).join(' · ')}</div>
                          )}
                        </>
                      ) : <span style={{ color: C.sub }}>{r.lane && r.lane !== 'generic' ? 'own lane' : '—'}</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* 3 — not a lane */}
      {notLanes.length > 0 && (
        <details>
          <summary style={{ cursor: 'pointer', fontSize: 13 }}>Not a lane ({notLanes.length})</summary>
          <ul style={{ margin: '4px 0 0', paddingLeft: 18, fontSize: 12, color: C.sub }}>
            {notLanes.map((n) => (
              <li key={n.tab} data-tab={n.tab}>
                <b>{laneLabel(n.tab)}</b> · {fmtInt(n.opens)} opens — {sayReversal(n.reason ?? '')}
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* 4 — the latest daily review */}
      <section aria-label="Daily loss review" style={{ display: 'grid', gap: 8 }}>
        <h4 style={{ margin: 0, fontSize: 14 }}>📋 Daily loss review{review?.day ? ` — ${review.day}` : ''}</h4>
        {!review ? (
          <p style={{ margin: 0, color: C.sub, fontSize: 13 }}>{reviewErr ? `could not load the review: ${reviewErr}` : NO_REVIEW_TEXT}</p>
        ) : (
          <>
            {Array.isArray(review.summary_lines) && review.summary_lines.length > 0 && (
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                {review.summary_lines.map((l, i) => <li key={i}>{sayReversal(l)}</li>)}
              </ul>
            )}
            {(review.strategies ?? []).filter((s) => Array.isArray(s.losers_today) && s.losers_today.length > 0).map((s) => (
              <div key={s.sid} data-review-sid={s.sid} style={{ fontSize: 12 }}>
                <b>{isKnownTab(s.sid) ? laneLabel(s.sid) : sayReversal(s.label ?? laneLabel(s.sid))}</b>
                <ul style={{ margin: '2px 0 0', paddingLeft: 18 }}>
                  {s.losers_today!.map((l, i) => <li key={i}>{sayReversal(l)}</li>)}
                </ul>
              </div>
            ))}
            {proposals.length === 0 ? (
              <p style={{ margin: 0, color: C.sub, fontSize: 13 }}>No proposals.</p>
            ) : proposals.map((pr) => {
              const ch = proposalChange(pr, rows);
              const open = isOpenProposal(pr);
              const ev = evidenceText(pr.evidence);
              return (
                <div key={pr.id} role="group" aria-label={`proposal ${pr.id}`}
                     style={{ border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 8, padding: 8, fontSize: 13, display: 'grid', gap: 4 }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                    <b>{sayReversal(pr.title ?? pr.kind ?? pr.id)}</b>
                    {pr.sid && <span style={{ color: C.sub }}>{laneLabel(pr.sid)}</span>}
                    <span style={{ ...chip, color: pr.level === 'code' ? C.muted : C.warn }}>{pr.level === 'code' ? 'code change' : 'config'}</span>
                    {!open && <span style={{ ...chip, color: C.sub }}>{pr.status}</span>}
                  </div>
                  <div style={{ color: C.sub }}>{ch.key}: {ch.before} → {ch.after}</div>
                  {ev && <div style={{ color: C.sub, fontSize: 11 }}>evidence: {sayReversal(ev)}</div>}
                  {open && (confirmPid === pr.id && pending ? (
                    <div role="dialog" aria-label={`Confirm ${pr.title ?? pr.id}?`} style={{ display: 'grid', gap: 4, borderTop: '1px dashed var(--hairline,#2a2a2a)', paddingTop: 6 }}>
                      <span>Level: <b>{pr.level ?? '—'}</b> · key <b>{ch.key}</b>: {ch.before} → {ch.after}</span>
                      <span>{pr.level === 'code' ? CODE_CONFIRM_TEXT : `Confirm writes ${ch.key} in the paper program's config. Nothing else changes.`}</span>
                      <span style={{ display: 'flex', gap: 6 }}>
                        <button disabled={busy} onClick={() => { void confirmProposal(pr.id); }}>Yes, confirm</button>
                        <button disabled={busy} onClick={() => setConfirmPid(null)}>Cancel</button>
                      </span>
                    </div>
                  ) : (
                    <span style={{ display: 'flex', gap: 6 }}>
                      <button disabled={busy} onClick={() => setConfirmPid(pr.id)}>Confirm…</button>
                      <button disabled={busy} onClick={() => { void dismissProposal(pr.id); }}>Dismiss</button>
                    </span>
                  ))}
                </div>
              );
            })}
          </>
        )}
      </section>
    </section>
  );
}
