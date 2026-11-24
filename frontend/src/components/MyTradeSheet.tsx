/**
 * 🧾 2026-11-23 — the journal sheet behind MyDayLine's 🧾 button (spec accountability §3.1 / §3.5 / WP-FE step 2).
 * Ajay 2026-11-23: "Please create a rule to warn me to not over trade and hold me accountable if I am missing out any
 * gajjalas rules". GG's own journal fields (VR R8): the setup grade A+ or B, why a B, patient or impulse, the
 * discipline kept or broke, and how he peeled off (the exit note).
 *
 * Facts are HIS: the entry has NO prefill (the app's last price is a placeholder hint only, never posted); the stop is
 * typed, or set by ONE explicit tap on "use the alert's stop" (stop_src "alert"); neither → stop_src "none" (the server
 * grades it). The POST carries only what he typed or tapped — an untouched entry, symbol, grade, patience or discipline
 * blocks it. After the POST the SERVED `verdict_text` and `warn_lines` print verbatim; a refusal prints the SERVED
 * `detail` when it is a string. Exit = exit px + an optional note; void keeps the doc (a second tap confirms). One write
 * at a time. Every verdict, check and warning word is served — this file grades nothing.
 * WORDS ONLY: no order, no broker call, no push; the record is his taps (tap times, not fills).
 */
import { useRef, useState, type FormEvent } from 'react';
import { API } from '../lib/apiBase';
import type { MyAplus, MyTrade, MyTradesOk } from './MyDayLine';

/** == backend chart_maps/gajjala/accountability_api.py GET / POST base. */
export const MY_TRADES_PATH = '/chart-maps/gajjala/my-trades';

type Grade = 'A+' | 'B';
type Patience = 'patient' | 'impulse';
type Discipline = 'kept' | 'broke';
type StopSrc = 'typed' | 'alert' | 'none';

export type MyTradeBody = {
  sym: string;
  entry: number;
  stop?: number;
  stop_src: StopSrc;
  shares?: number;
  grade: Grade;
  why_b?: string;
  patience: Patience;
  discipline: Discipline;
};

export type MyTapAnswer = { verdict_text: string | null; warn_lines: string[] };

const WRAP = { minWidth: 0, overflowWrap: 'anywhere' as const };
const ROW = { ...WRAP, display: 'flex', flexWrap: 'wrap' as const, gap: 6, alignItems: 'center' };
const INPUT = { minWidth: 0, maxWidth: '100%', width: '7.5em' };

const pos = (s: string): number | null => {
  if (!s.trim()) return null;
  const n = Number(s);
  return Number.isFinite(n) && n > 0 ? n : null;
};
const symOf = (s: string) => s.trim().toUpperCase();

/** The POST body from what was typed / tapped, or null when a required field is untouched. Pure. */
export function buildTapBody(f: {
  sym: string; entry: string; stop: string; stopSrc: StopSrc; alertStop: number | null; shares: string;
  grade: Grade | null; whyB: string; patience: Patience | null; discipline: Discipline | null;
}): MyTradeBody | null {
  const sym = symOf(f.sym);
  const entry = pos(f.entry);
  if (!sym || entry == null || !f.grade || !f.patience || !f.discipline) return null;
  const body: MyTradeBody = { sym, entry, stop_src: 'none', grade: f.grade, patience: f.patience, discipline: f.discipline };
  if (f.stopSrc === 'alert' && f.alertStop != null) { body.stop = f.alertStop; body.stop_src = 'alert'; }
  else if (f.stopSrc === 'typed') {
    const st = pos(f.stop);
    if (st != null) { body.stop = st; body.stop_src = 'typed'; }
  }
  const sh = pos(f.shares);
  if (sh != null) body.shares = sh;
  if (f.grade === 'B' && f.whyB.trim()) body.why_b = f.whyB.trim();
  return body;
}

async function servedDetail(r: Response): Promise<string> {
  try {
    const d = ((await r.json()) as { detail?: unknown } | null)?.detail;
    if (typeof d === 'string' && d.trim()) return d;
  } catch { /* no body */ }
  return `HTTP ${r.status}`;
}

function Pick<T extends string>({ value, options, onPick, testid }: {
  value: T | null; options: readonly T[]; onPick: (v: T) => void; testid: string;
}) {
  return (
    <span style={ROW} role="group" data-testid={testid}>
      {options.map((o) => (
        <button key={o} type="button" className={`cat-tab${value === o ? ' is-active' : ''}`} aria-pressed={value === o}
                data-testid={`${testid}-${o}`} onClick={() => onPick(o)}>{o}</button>
      ))}
    </span>
  );
}

function TradeRow({ t, busy, write }: { t: MyTrade; busy: boolean; write: (path: string, body?: object) => Promise<string | null> }) {
  const [exitOpen, setExitOpen] = useState(false);
  const [px, setPx] = useState('');
  const [note, setNote] = useState('');
  const [confirmVoid, setConfirmVoid] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const shown = (t.checks || []).filter((c) => (c.state === 'flag' || c.kind === 'info') && typeof c.words === 'string' && c.words);
  const sendExit = async (e: FormEvent) => {
    e.preventDefault();
    const exit_px = pos(px);
    if (exit_px == null) return;
    const body: { exit_px: number; exit_note?: string } = { exit_px };
    if (note.trim()) body.exit_note = note.trim();
    const err = await write(`/${encodeURIComponent(t.id)}/exit`, body);
    setMsg(err);
    if (!err) { setExitOpen(false); setPx(''); setNote(''); }
  };
  const sendVoid = async () => {
    const err = await write(`/${encodeURIComponent(t.id)}/void`);
    setMsg(err);
    setConfirmVoid(false);
  };
  return (
    <li style={WRAP} data-testid={`my-trade-${t.id}`}>
      <div style={ROW}>
        <strong>{t.sym}</strong>
        {t.verdict_text ? <span style={WRAP} data-testid={`my-trade-verdict-${t.id}`}>{t.verdict_text}</span> : null}
      </div>
      {shown.length ? (
        <ul style={WRAP} data-testid={`my-trade-checks-${t.id}`}>
          {shown.map((c) => <li key={c.id} style={WRAP} data-state={c.state} data-kind={c.kind}>{c.words}</li>)}
        </ul>
      ) : null}
      {t.alert_same?.text ? <div className="gg-muted" style={WRAP}>{t.alert_same.text}</div> : null}
      {t.exit_text ? <div className="gg-muted" style={WRAP} data-testid={`my-trade-exit-text-${t.id}`}>{t.exit_text}</div> : null}
      <div style={ROW}>
        <button type="button" className="gg-rescan" disabled={busy} data-testid={`my-trade-exit-open-${t.id}`}
                onClick={() => setExitOpen((o) => !o)}>exit</button>
        {confirmVoid ? (
          <>
            <button type="button" className="gg-rescan" disabled={busy} data-testid={`my-trade-void-yes-${t.id}`}
                    onClick={() => void sendVoid()}>void it</button>
            <button type="button" className="gg-rescan" data-testid={`my-trade-void-no-${t.id}`}
                    onClick={() => setConfirmVoid(false)}>keep</button>
          </>
        ) : (
          <button type="button" className="gg-rescan" disabled={busy} data-testid={`my-trade-void-${t.id}`}
                  onClick={() => setConfirmVoid(true)}>void</button>
        )}
      </div>
      {exitOpen ? (
        <form style={ROW} onSubmit={(e) => void sendExit(e)} data-testid={`my-trade-exit-form-${t.id}`}>
          <input type="text" inputMode="decimal" required aria-label="exit price" placeholder="exit px" style={INPUT}
                 value={px} onChange={(e) => setPx(e.target.value)} data-testid={`my-trade-exit-px-${t.id}`} />
          <input type="text" aria-label="how I peeled off" placeholder="how I peeled off" style={{ ...INPUT, width: '14em' }}
                 value={note} onChange={(e) => setNote(e.target.value)} data-testid={`my-trade-exit-note-${t.id}`} />
          <button type="submit" className="gg-rescan" disabled={busy || pos(px) == null}
                  data-testid={`my-trade-exit-send-${t.id}`}>log exit</button>
        </form>
      ) : null}
      {msg ? <div className="cm-note cm-note-err" style={WRAP} data-testid={`my-trade-err-${t.id}`}>{msg}</div> : null}
    </li>
  );
}

export function MyTradeSheet({ data, priceOf, onChanged, onClose }: {
  data: MyTradesOk;
  priceOf?: (sym: string) => number | null;
  onChanged: () => void;
  onClose: () => void;
}) {
  const [sym, setSym] = useState('');
  const [entry, setEntry] = useState('');
  const [stop, setStop] = useState('');
  const [stopSrc, setStopSrc] = useState<StopSrc>('none');
  const [shares, setShares] = useState('');
  const [grade, setGrade] = useState<Grade | null>(null);
  const [whyB, setWhyB] = useState('');
  const [patience, setPatience] = useState<Patience | null>(null);
  const [discipline, setDiscipline] = useState<Discipline | null>(null);
  const [answer, setAnswer] = useState<MyTapAnswer | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);

  const alert: MyAplus | null = data.aplus_today.find((a) => symOf(a.sym) === symOf(sym) && a.stop != null && a.stop > 0) ?? null;
  const alertStop = alert?.stop ?? null;
  const hint = sym && priceOf ? priceOf(symOf(sym)) : null;
  /** A new symbol drops an alert stop picked for the old one (the stop box is cleared with it). */
  const dropAlertStop = () => { if (stopSrc === 'alert') { setStopSrc('none'); setStop(''); } };
  const body = buildTapBody({ sym, entry, stop, stopSrc, alertStop, shares, grade, whyB, patience, discipline });

  /** ONE write at a time; ok → the line re-reads; a refusal → the served detail (returned). */
  const write = async (suffix: string, payload?: object): Promise<string | null> => {
    if (busyRef.current) return null;
    busyRef.current = true;
    setBusy(true);
    try {
      const r = await fetch(`${API}${MY_TRADES_PATH}${suffix}`, {
        method: 'POST', credentials: 'include', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' }, body: payload ? JSON.stringify(payload) : undefined,
      });
      if (!r.ok) return await servedDetail(r);
      onChanged();
      return null;
    } catch (e) {
      return String((e as Error)?.message ?? e);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!body || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      const r = await fetch(`${API}${MY_TRADES_PATH}`, {
        method: 'POST', credentials: 'include', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      if (!r.ok) { setErr(await servedDetail(r)); setAnswer(null); return; }
      let a: unknown = null;
      try { a = await r.json(); } catch { a = null; }
      const o = (a && typeof a === 'object' ? a : {}) as { verdict_text?: unknown; warn_lines?: unknown };
      setAnswer({
        verdict_text: typeof o.verdict_text === 'string' && o.verdict_text ? o.verdict_text : null,
        warn_lines: Array.isArray(o.warn_lines) ? o.warn_lines.filter((x): x is string => typeof x === 'string' && !!x) : [],
      });
      setErr(null);
      setSym(''); setEntry(''); setStop(''); setStopSrc('none'); setShares('');
      setGrade(null); setWhyB(''); setPatience(null); setDiscipline(null);
      onChanged();
    } catch (ex) {
      setErr(String((ex as Error)?.message ?? ex));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  return (
    <div className="gg-my-sheet" role="dialog" aria-label="🧾 my trade" data-testid="my-sheet" style={{ ...WRAP, width: '100%' }}>
      {data.my_day?.data_text ? <div className="gg-muted" style={WRAP} data-testid="my-sheet-data">{data.my_day.data_text}</div> : null}
      <form style={{ ...WRAP, display: 'grid', gap: 6 }} onSubmit={(e) => void submit(e)} data-testid="my-sheet-form">
        {data.aplus_today.length ? (
          <div style={ROW} data-testid="my-sheet-aplus">
            {data.aplus_today.map((a) => (
              <button key={`${a.sym}|${a.setup ?? ''}`} type="button" className={`cat-tab${symOf(sym) === symOf(a.sym) ? ' is-active' : ''}`}
                      data-testid={`my-sheet-aplus-${a.sym}`}
                      onClick={() => { setSym(symOf(a.sym)); dropAlertStop(); }}>
                🎯 {a.sym}{a.setup ? ` · ${a.setup}` : ''}
              </button>
            ))}
          </div>
        ) : null}
        <div style={ROW}>
          <input type="text" required aria-label="symbol" placeholder="symbol" style={INPUT} autoCapitalize="characters"
                 value={sym} onChange={(e) => { setSym(e.target.value); dropAlertStop(); }}
                 data-testid="my-sheet-sym" />
          <input type="text" inputMode="decimal" required aria-label="entry" style={INPUT}
                 placeholder={hint != null ? String(hint) : 'entry'}
                 value={entry} onChange={(e) => setEntry(e.target.value)} data-testid="my-sheet-entry" />
          <input type="text" inputMode="decimal" aria-label="stop" placeholder="stop" style={INPUT}
                 value={stop} onChange={(e) => { setStop(e.target.value); setStopSrc(e.target.value.trim() ? 'typed' : 'none'); }}
                 data-testid="my-sheet-stop" />
          <input type="text" inputMode="numeric" aria-label="shares" placeholder="shares" style={INPUT}
                 value={shares} onChange={(e) => setShares(e.target.value)} data-testid="my-sheet-shares" />
        </div>
        {alertStop != null ? (
          <div style={ROW}>
            <button type="button" className={`cat-tab${stopSrc === 'alert' ? ' is-active' : ''}`} aria-pressed={stopSrc === 'alert'}
                    data-testid="my-sheet-alert-stop"
                    onClick={() => { setStop(String(alertStop)); setStopSrc('alert'); }}>
              use the alert&apos;s stop {alertStop}
            </button>
          </div>
        ) : null}
        <div style={ROW}>
          <Pick testid="my-sheet-grade" value={grade} options={['A+', 'B'] as const} onPick={setGrade} />
          <Pick testid="my-sheet-patience" value={patience} options={['patient', 'impulse'] as const} onPick={setPatience} />
          <Pick testid="my-sheet-discipline" value={discipline} options={['kept', 'broke'] as const} onPick={setDiscipline} />
        </div>
        {grade === 'B' ? (
          <input type="text" aria-label="why a B" placeholder="why a B" style={{ ...INPUT, width: '100%' }}
                 value={whyB} onChange={(e) => setWhyB(e.target.value)} data-testid="my-sheet-why-b" />
        ) : null}
        <div style={ROW}>
          <button type="submit" className="gg-rescan" disabled={busy || !body} data-testid="my-sheet-send">🧾 log</button>
          <button type="button" className="gg-rescan" onClick={onClose} data-testid="my-sheet-close">close</button>
        </div>
      </form>
      {answer ? (
        <div className="cm-note" role="status" style={WRAP} data-testid="my-sheet-answer">
          {answer.verdict_text ? <div style={WRAP} data-testid="my-sheet-verdict">{answer.verdict_text}</div> : null}
          {answer.warn_lines.map((w, i) => <div key={i} style={WRAP} data-testid="my-sheet-warn">{w}</div>)}
        </div>
      ) : null}
      {err ? <div className="cm-note cm-note-err" role="status" style={WRAP} data-testid="my-sheet-err">{err}</div> : null}
      {data.trades.length ? (
        <ul style={{ ...WRAP, listStyle: 'none', padding: 0 }} data-testid="my-sheet-trades">
          {data.trades.map((t) => <TradeRow key={t.id} t={t} busy={busy} write={write} />)}
        </ul>
      ) : null}
      {data.voided.length ? (
        <ul className="gg-muted" style={{ ...WRAP, listStyle: 'none', padding: 0 }} data-testid="my-sheet-voided">
          {data.voided.map((t) => <li key={t.id} style={WRAP} data-testid={`my-voided-${t.id}`}><s>{t.sym}</s> voided</li>)}
        </ul>
      ) : null}
    </div>
  );
}

export default MyTradeSheet;
