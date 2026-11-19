/* 🚫 GgwBrokerMark — the 👀 Watch's one-way broker mark (2026-11-19, spec watchfid §3.3, WP-C).
 *
 * Ajay 2026-11-19 asked for a button on the Watch that marks a name as not tradable at his broker and keeps it off the
 * Watch (his words verbatim: the 2026-11-19 watchfid doc under docs/gajjala/). One click:
 *   1) POST the name to his ONE 🚫 list (GG_BROKER_PATH — the 🚩 board's own route, never a second list);
 *   2) then DELETE it from the Watch (ggwSymbolPath — his name is removed, a 🤖 name is dismissed).
 * ONE-WAY: this file never DELETEs on GG_BROKER_PATH (the undo stays on the 🚩 strip ✕ / the 🚩 card toggle — HIS CALL #4).
 * The button is drawn only when the SERVED block says `editable` (the server serves it to the primary owner only — never
 * a client-side owner check here), lit (aria-pressed) from the SERVED row word. No confirm (HIS CALL #8); it sits FIRST in the tile's
 * action group, away from ✕. Every visible string is served, except GGW_FETCH_FAILED (the request itself failed).
 * The look is the scoped `.ggw-broker-mark` rules in styles/gajjalaWatch.css (this file imports no stylesheet).
 * Display + his own list write only; UNMEASURED. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { GG_BROKER_PATH } from '../lib/gajjala';
import { GGW_FETCH_FAILED, ggwSymbolPath, type GgwRow } from '../lib/gajjalaWatch';
import { ggwBrokerText, type GgwBroker } from '../lib/ggwBroker';
import { loadGgwList } from '../lib/ggWatchList';

export type GgwMarkResult = { ok: boolean; text: string | null; err: string | null };

const served = (x: unknown): x is string => typeof x === 'string' && x.trim() !== '';

/** POST the name to his 🚫 list, then DELETE it from the Watch. A failed POST stops (404 → nothing; else the SERVED
 *  `detail`). A failed DELETE after a good POST → {ok: true, text: null, err: GGW_FETCH_FAILED}. */
export async function ggwMarkNotEligible(sym: string, fetchImpl: typeof fetch = fetch): Promise<GgwMarkResult> {
  const symbol = String(sym || '').trim();
  if (!symbol) return { ok: false, text: null, err: null };
  let post: Response;
  try {
    post = await fetchImpl(`${API}${GG_BROKER_PATH}`, {
      method: 'POST', credentials: 'include', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol }),
    });
  } catch {
    return { ok: false, text: null, err: GGW_FETCH_FAILED };
  }
  if (!post.ok) {
    if (post.status === 404) return { ok: false, text: null, err: null };
    let detail: unknown = null;
    try { detail = ((await post.json()) as { detail?: unknown } | null)?.detail; } catch { detail = null; }
    return { ok: false, text: null, err: served(detail) ? detail : null };
  }
  try {
    const del = await fetchImpl(`${API}${ggwSymbolPath(symbol)}`, { method: 'DELETE', credentials: 'include', cache: 'no-store' });
    if (!del.ok) return { ok: true, text: null, err: GGW_FETCH_FAILED };
    let text: string | null = null;
    try {
      const a = (await del.json()) as { text?: unknown } | null;
      text = served(a?.text) ? (a!.text as string) : null;
    } catch { text = null; }
    return { ok: true, text, err: null };
  } catch {
    return { ok: true, text: null, err: GGW_FETCH_FAILED };
  }
}

/** ONE mark at a time (the ref blocks a second click in the same tick). Always refreshes the shared ➕/➖ list; `onDone`
 *  (the served answer text, or null) only while mounted. */
export function useGgwBrokerMark(onDone: (text: string | null) => void): {
  busy: boolean; err: string | null; mark: (sym: string) => void;
} {
  const busyRef = useRef(false);
  const mounted = useRef(true);
  const done = useRef(onDone);
  done.current = onDone;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const mark = useCallback((sym: string) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    let text: string | null = null;
    void ggwMarkNotEligible(sym)
      .then((r) => { text = r.text; if (mounted.current) setErr(r.err); })
      .catch(() => { if (mounted.current) setErr(GGW_FETCH_FAILED); })
      .finally(() => {
        busyRef.current = false;
        void loadGgwList(true);
        if (!mounted.current) return;
        setBusy(false);
        done.current(text);
      });
  }, []);
  return { busy, err, mark };
}

/** The 🚫 button of one Watch tile: nothing unless the SERVED block is editable; lit from the SERVED row word. */
export function GgwBrokerButton({ row, block, busy, onMark }: {
  row: GgwRow; block: GgwBroker | null; busy: boolean; onMark: (sym: string) => void;
}) {
  if (!block || block.editable !== true) return null;
  const label = block.title ?? block.text;
  return (
    <button type="button" className="ggw-btn ggw-broker-mark" data-testid={`ggw-broker-mark-${row.symbol}`}
            aria-pressed={!!ggwBrokerText(row)} title={label} aria-label={label} disabled={busy}
            onClick={() => onMark(row.symbol)}>
      {block.toggle}
    </button>
  );
}

/** The served 🚫 head lines (the list fault, the 🤖 kept-off names, the 🤖 fault) and the last mark's error. */
export function GgwBrokerHead({ block, err }: { block: GgwBroker | null; err: string | null }) {
  const fault = block?.fault_text ?? null;
  const autoText = block?.auto_text ?? null;
  const autoFault = block?.auto_fault_text ?? null;
  if (!fault && !autoText && !autoFault && !err) return null;
  return (
    <>
      {fault ? <span className="ggw-line ggw-warn" data-testid="ggw-broker-fault">{fault}</span> : null}
      {autoText ? <span className="ggw-line ggw-broker-auto" data-testid="ggw-broker-auto">{autoText}</span> : null}
      {autoFault ? <span className="ggw-line ggw-warn" data-testid="ggw-broker-auto-fault">{autoFault}</span> : null}
      {err ? <span className="ggw-line ggw-warn" data-testid="ggw-broker-err">{err}</span> : null}
    </>
  );
}
