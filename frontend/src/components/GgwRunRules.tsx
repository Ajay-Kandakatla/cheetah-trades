/* ▶ GgwRunRules — the 👀 Watch tile's "▶ Rules" button and its slide-in panel (2026-11-24, spec ggrun §3.5, WP fe-run).
 *
 * Ajay 2026-11-24: "On the Watch list I need a run button to run against Gajjalas rules of a stock to see for patterns of
 * 5 patterns he has especially reversal squeeze.. so can check for patterns mid day when I can add a small slide in in
 * the chart window for giving verbatim of passed rules and failed rules of that stock like you do in other tabs..".
 *
 * One tap = ONE owner-only POST (lib/ggwRun.ggwRunPath). The server grades the five setups with the 🚩 pass's own engine
 * and serves every word; this panel prints them VERBATIM, in the SERVED order, and the rule rows through the 🚩 card's
 * own printer (GgCriteriaList). The FE types no rule word, no state word and no number — only the control chrome of
 * lib/ggwRun.GGW_RUN. No timer: the server bounds the wait, and ✕ works in every phase (an answer that lands after ✕ is
 * dropped by its request token). 404 (not the owner) → nothing at all. Never touches the board's load chain.
 * Display only — the run rings nothing and records nothing. UNMEASURED. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { GGW_RUN, ggwRunPath, ggwRunTitle, parseGgwRun, type GgwRunAnswer, type GgwRunSetup } from '../lib/ggwRun';
import { GgCriteriaList } from './GgCriteria';
import '../styles/ggwRun.css';

export type GgwRunState = { phase: 'busy' } | { phase: 'done'; a: GgwRunAnswer } | { phase: 'failed'; text: string };

const served = (x: unknown): x is string => typeof x === 'string' && x.trim() !== '';
/** null = clear the state (404: not his — nothing printed). */
type Outcome = GgwRunState | null;

async function runOnce(sym: string): Promise<Outcome> {
  let r: Response;
  try {
    r = await fetch(`${API}${ggwRunPath(sym)}`, { method: 'POST', credentials: 'include', cache: 'no-store' });
  } catch {
    return { phase: 'failed', text: GGW_RUN.failed };
  }
  if (r.status === 404) return null;
  if (!r.ok) {
    let detail: unknown = null;
    try { detail = ((await r.json()) as { detail?: unknown } | null)?.detail; } catch { detail = null; }
    return { phase: 'failed', text: served(detail) ? detail : GGW_RUN.failed };
  }
  let raw: unknown = null;
  try { raw = await r.json(); } catch { return { phase: 'failed', text: GGW_RUN.failed }; }
  const a = parseGgwRun(raw);
  return a ? { phase: 'done', a } : { phase: 'failed', text: GGW_RUN.failed };
}

/** The board's run state per symbol. `run` makes ONE POST per tap (a second tap while that name is busy is ignored —
 *  a ref, so two clicks in one tick make one POST); `close` clears the state in every phase and retires the token. */
export function useGgwRun(): {
  stateOf: (sym: string) => GgwRunState | null; run: (sym: string) => void; close: (sym: string) => void;
} {
  const [states, setStates] = useState<Record<string, GgwRunState>>({});
  const tokens = useRef(new Map<string, number>());
  const seq = useRef(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  const put = useCallback((sym: string, s: GgwRunState | null) => {
    setStates((prev) => {
      if (s) return { ...prev, [sym]: s };
      if (!(sym in prev)) return prev;
      const next = { ...prev };
      delete next[sym];
      return next;
    });
  }, []);

  const run = useCallback((sym: string) => {
    if (tokens.current.has(sym)) return;                      // that name is still reading — ONE POST
    seq.current += 1;
    const token = seq.current;
    tokens.current.set(sym, token);
    put(sym, { phase: 'busy' });
    void runOnce(sym).then((out) => {
      if (tokens.current.get(sym) !== token) return;          // ✕ (or unmount) retired it — the late answer prints nothing
      tokens.current.delete(sym);
      if (!mounted.current) return;
      put(sym, out);
    });
  }, [put]);

  const close = useCallback((sym: string) => {
    tokens.current.delete(sym);
    put(sym, null);
  }, [put]);

  const stateOf = (sym: string): GgwRunState | null => states[sym] ?? null;
  return { stateOf, run, close };
}

/** "▶ Rules" — in the tile's action group (board AND ⤢ view). Never hides; disabled + aria-busy while its run reads. */
export function GgwRunButton({ sym, state, onRun }: {
  sym: string; state: GgwRunState | null; onRun: (sym: string) => void;
}) {
  const busy = state?.phase === 'busy';
  const title = ggwRunTitle(sym);
  return (
    <button type="button" className="ggw-btn ggw-run-btn" data-testid={`ggw-run-btn-${sym}`} title={title}
            aria-label={title} aria-expanded={state != null} aria-busy={busy || undefined} disabled={busy}
            onClick={() => onRun(sym)}>
      {`${GGW_RUN.glyph} ${GGW_RUN.label}`}
    </button>
  );
}

function SetupSection({ s }: { s: GgwRunSetup }) {
  const tags = [
    ['variant', s.variant_label], ['grade', s.grade_label], ['vol-dried', s.vol_dried_text],
  ].filter((x): x is [string, string] => !!x[1]);
  return (
    <section className="ggw-run-setup" data-testid={`ggw-run-setup-${s.setup}`} data-state={s.state}>
      {s.label ? <h4 className="ggw-run-label">{s.label}</h4> : null}
      {s.state_label ? (
        <span className={`gg-state gg-state-${s.state}`} data-testid={`ggw-run-state-${s.setup}`}>{s.state_label}</span>
      ) : null}
      {s.gate_text ? <p className="ggw-line ggw-run-gate" data-testid={`ggw-run-gate-${s.setup}`}>{s.gate_text}</p> : null}
      {tags.length ? (
        <p className="ggw-line ggw-run-tags">
          {tags.map(([k, t]) => (
            <span key={k} className="ggw-run-tag" data-testid={`ggw-run-${k}-${s.setup}`}>{t}</span>
          ))}
        </p>
      ) : null}
      {s.plan_text ? <p className="ggw-line ggw-run-plan" data-testid={`ggw-run-plan-${s.setup}`}>{s.plan_text}</p> : null}
      {s.tally_text ? <p className="ggw-line ggw-run-tally" data-testid={`ggw-run-tally-${s.setup}`}>{s.tally_text}</p> : null}
      <GgCriteriaList criteria={s.criteria} />
    </section>
  );
}

/** The slide-in panel inside the tile's chart window. state null → nothing. Every string verbatim; absent → nothing. */
export function GgwRunPanel({ sym, state, onClose }: {
  sym: string; state: GgwRunState | null; onClose: (sym: string) => void;
}) {
  if (!state) return null;
  const busy = state.phase === 'busy';
  const a = state.phase === 'done' ? state.a : null;
  const title = a?.title ?? ggwRunTitle(sym);
  const text = a ? a.text : state.phase === 'failed' ? state.text : null;
  const line = (cls: string, t: string | null) => (t ? <p className={`ggw-line ${cls}`} data-testid={cls}>{t}</p> : null);
  return (
    <aside className="ggw-run" role="region" aria-label={title} data-testid={`ggw-run-${sym}`} aria-busy={busy}>
      <div className="ggw-run-head">
        <b className="ggw-run-title" data-testid="ggw-run-title">{title}</b>
        <button type="button" className="ggw-btn ggw-run-close" data-testid={`ggw-run-close-${sym}`}
                title={GGW_RUN.closeTitle} aria-label={`${GGW_RUN.closeTitle} ${title}`} onClick={() => onClose(sym)}>
          {GGW_RUN.close}
        </button>
      </div>
      {busy ? line('ggw-run-busy', GGW_RUN.busy) : (
        <>
          {line('ggw-run-reused', a?.reused_text ?? null)}
          {line('ggw-run-asof', a?.as_of_text ?? null)}
          {line('ggw-run-text', text)}
          {line('ggw-run-scanner', a?.scanner_text ?? null)}
          {line('ggw-run-float', a?.float_text ?? null)}
          {line('ggw-run-volume', a?.volume_text ?? null)}
          {(a?.setups ?? []).map((s) => <SetupSection key={s.setup} s={s} />)}
          {line('ggw-run-note', a?.note ?? null)}
        </>
      )}
    </aside>
  );
}
