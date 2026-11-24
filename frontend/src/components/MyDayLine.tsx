/**
 * 🧾 2026-11-23 — My trades vs GG: the owner's day line + the 🧾 journal button (spec accountability §3.4 / §3.5 / WP-FE).
 * Ajay 2026-11-23: "I think I am going outside Gajjalas now.. Please create a rule to warn me to not over trade and hold
 * me accountable if I am missing out any gajjalas rules". HIS ANSWER #1 "Build it", #2 "Before trade #3".
 *
 * Mounted by GajjalaBoard right under 🌫️ Day read, on the 🚩 5-minute page only, and only when the board SERVES its
 * owner-only `broker_flags` block (never isOwner — the server serves that block to the primary owner only). It GETs
 * MY_TRADES_PATH once per session date and again after each journal write. `owner_only`, an error or junk → renders
 * nothing. It prints the served `my_day` words verbatim (text, next_text, quiet_text, footer): the FE composes no count,
 * no quote and no rule. A served null `my_day` → no line (the 🧾 button stays: the GET said `ok`, so it is the owner).
 * WORDS ONLY: nothing here trades, blocks a broker, hides a card, sorts, filters or pushes.
 *
 * 🧹 2026-11-24 (ggclean §3.3) — Ajay: "Hide all of this nouce besides the scan button and log trade button no explantions
 * on the landing pages anymor". One optional prop, `textTo`. Undefined (every older caller): today's markup, byte for byte.
 * Defined ("bare", the 🚩 action row): the section is `display: contents` (no box) so the 🧾 button is a flex item of
 * .gg-actions; the sentence block portals into `textTo` (the header fold's slot; nothing while it is null); the ⚠️
 * next_text stays OUTSIDE the fold, right after the button, full width with `order: 1` — like the open sheet — so line
 * one is always 🔄 · 🧾 · ⓘ. Same GET, same button, same sheet; no word added. The keyboard order (🧾 → ⚠️ / sheet → ⓘ)
 * differs from the visual one; acceptable for a disclosure toggle.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { todayEtKey } from '../lib/alertKinds';
import { API } from '../lib/apiBase';
import { MY_TRADES_PATH, MyTradeSheet } from './MyTradeSheet';

export { MY_TRADES_PATH };

export type MyCheck = {
  id: string;
  kind: 'hard' | 'soft' | 'info' | string;
  state: 'ok' | 'flag' | 'unknown' | string;
  words?: string | null;
  rule?: string | null;
  quote_ref?: string | null;
};

export type MyTrade = {
  id: string;
  sym: string;
  verdict?: string | null;
  verdict_text?: string | null;
  checks?: MyCheck[] | null;
  warned_at_tap?: string[] | null;
  alert_id?: string | null;
  alert_same?: { state?: string | null; text?: string | null } | null;
  exit_text?: string | null;
};

export type MyDay = {
  text: string;
  next_text?: string | null;
  quiet_text?: string | null;
  footer?: string | null;
  data_text?: string | null;
};

export type MyAplus = { sym: string; setup?: string | null; trigger?: number | null; stop?: number | null };

export type MyTradesOk = {
  state: 'ok';
  date: string | null;
  my_day: MyDay | null;
  trades: MyTrade[];
  voided: MyTrade[];
  aplus_today: MyAplus[];
};

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null);
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

function parseTrade(v: unknown): MyTrade | null {
  if (!isObj(v) || !str(v.id) || !str(v.sym)) return null;
  const checks = Array.isArray(v.checks)
    ? v.checks.filter((c): c is MyCheck => isObj(c) && typeof c.id === 'string') : [];
  const same = isObj(v.alert_same) ? { state: str(v.alert_same.state), text: str(v.alert_same.text) } : null;
  return {
    id: v.id as string, sym: v.sym as string, verdict: str(v.verdict), verdict_text: str(v.verdict_text), checks,
    warned_at_tap: Array.isArray(v.warned_at_tap) ? v.warned_at_tap.filter((x): x is string => typeof x === 'string') : [],
    alert_id: str(v.alert_id), alert_same: same, exit_text: str(v.exit_text),
  };
}

/** The served GET, or null for anything but `state: "ok"` (owner_only / error / junk → nothing is drawn). */
export function parseMyTrades(raw: unknown): MyTradesOk | null {
  if (!isObj(raw) || raw.state !== 'ok') return null;
  const md = raw.my_day;
  const my_day: MyDay | null = isObj(md) && str(md.text)
    ? { text: md.text as string, next_text: str(md.next_text), quiet_text: str(md.quiet_text), footer: str(md.footer),
        data_text: str(md.data_text) }
    : null;
  const list = (v: unknown) => (Array.isArray(v) ? v.map(parseTrade).filter((t): t is MyTrade => t !== null) : []);
  const aplus = Array.isArray(raw.aplus_today)
    ? raw.aplus_today.filter((a): a is Record<string, unknown> => isObj(a) && !!str(a.sym))
      .map((a) => ({ sym: a.sym as string, setup: str(a.setup), trigger: num(a.trigger), stop: num(a.stop) }))
    : [];
  return { state: 'ok', date: str(raw.date), my_day, trades: list(raw.trades), voided: list(raw.voided), aplus_today: aplus };
}

/** The GET url — the board's served session date rides as `date` when it is a YYYY-MM-DD string. */
export function myTradesUrl(date?: string | null): string {
  const d = typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null;
  return `${API}${MY_TRADES_PATH}${d ? `?date=${encodeURIComponent(d)}` : ''}`;
}

/** 2026-11-24 (verifier refix): the board's session date rides only when it IS today ET. Before the first pass the
 *  board still shows the last market day, while a tap is stored under today — so any other date → null and the GET
 *  takes the server's default (today ET), never yesterday's list. */
export function myDayDate(sessionDate?: string | null, nowMs: number = Date.now()): string | null {
  return typeof sessionDate === 'string' && sessionDate === todayEtKey(nowMs) ? sessionDate : null;
}

const WRAP = { minWidth: 0, overflowWrap: 'anywhere' as const };

export function MyDayLine({ date, priceOf, textTo }: {
  date?: string | null; priceOf?: (sym: string) => number | null; textTo?: HTMLElement | null;
}) {
  const [data, setData] = useState<MyTradesOk | null>(null);
  const [tick, setTick] = useState(0);
  const [open, setOpen] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    let alive = true;
    const my = ++seq.current;
    fetch(myTradesUrl(date), { credentials: 'include', cache: 'no-store' })
      .then(async (r) => (r.ok ? parseMyTrades(await r.json()) : null))
      .catch(() => null)
      .then((p) => { if (alive && my === seq.current) setData(p); });
    return () => { alive = false; };
  }, [date, tick]);

  const reread = useCallback(() => setTick((n) => n + 1), []);

  if (!data) return null;
  const md = data.my_day;
  const bare = textTo !== undefined;
  if (bare) {
    const block = md ? (
      <div className="cm-note" style={WRAP} data-testid="my-day-line">
        <div style={WRAP} data-testid="my-day-text">{md.text}</div>
        {md.quiet_text ? <div style={WRAP} data-testid="my-day-quiet">{md.quiet_text}</div> : null}
        {md.footer ? <div className="gg-muted" style={WRAP} data-testid="my-day-footer">{md.footer}</div> : null}
      </div>
    ) : null;
    return (
      <section className="gg-my-day gg-my-day--bare" data-testid="my-day" style={{ display: 'contents' }}>
        {block && textTo ? createPortal(block, textTo) : null}
        <button type="button" className="gg-rescan" data-testid="my-day-open" aria-expanded={open ? 'true' : 'false'}
                onClick={() => setOpen((o) => !o)}>
          🧾 log trade
        </button>
        {md?.next_text ? (
          <div style={{ ...WRAP, flexBasis: '100%', order: 1 }} data-testid="my-day-next">{md.next_text}</div>
        ) : null}
        {open ? (
          <div style={{ ...WRAP, flexBasis: '100%', order: 1 }}>
            <MyTradeSheet data={data} priceOf={priceOf} onChanged={reread} onClose={() => setOpen(false)} />
          </div>
        ) : null}
      </section>
    );
  }
  return (
    <section className="cm-note gg-my-day" data-testid="my-day" style={{ ...WRAP, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {md ? (
        <div style={{ ...WRAP, flex: '1 1 0' }} data-testid="my-day-line">
          <div style={WRAP} data-testid="my-day-text">{md.text}</div>
          {md.next_text ? <div style={WRAP} data-testid="my-day-next">{md.next_text}</div> : null}
          {md.quiet_text ? <div style={WRAP} data-testid="my-day-quiet">{md.quiet_text}</div> : null}
          {md.footer ? <div className="gg-muted" style={WRAP} data-testid="my-day-footer">{md.footer}</div> : null}
        </div>
      ) : null}
      <button type="button" className="gg-rescan" data-testid="my-day-open" aria-expanded={open ? 'true' : 'false'}
              onClick={() => setOpen((o) => !o)}>
        🧾 log trade
      </button>
      {open ? (
        <div style={{ ...WRAP, flexBasis: '100%' }}>
          <MyTradeSheet data={data} priceOf={priceOf} onChanged={reread} onClose={() => setOpen(false)} />
        </div>
      ) : null}
    </section>
  );
}

export default MyDayLine;
