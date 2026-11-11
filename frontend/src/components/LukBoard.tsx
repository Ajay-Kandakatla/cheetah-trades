/* LukBoard — 🥇 Luk's tab on Chart Maps (2026-11-01, luk spec §3.10 / §3.13).
 *
 * Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala.
 * Implement their strategy please if they have online resources. ... Make sure in your research you are able to find
 * full strategy is open to public not paid or something they are hiding away behind a paid wall.. I need something
 * like Gajjlala that is exposed"
 *
 * Martin Luk's published pullback / opening-range method. ONE read-only GET (GET /chart-maps/luk, backend
 * chart_maps/luk/tab.py) the Luk pass fills; re-read on the SERVED cadence (lukRefreshMs). On top: the served title,
 * honesty line, session badge and pass line; the folded strip (🧭 QQQ / IWM words + the push / record / external /
 * cost / latency lines); the served sub bar (links, aria-current); the served counts line with its folded ⓘ legend;
 * then the sub's body — the setup cards (LukCard, in the SERVED order), a scan table (LukScreens), the 📓 Playbook
 * (LukPlaybook) or the 🏁 Track record (LukTrackRecord). A block the server did not send renders nothing.
 *
 * The FE composes NO word and NO number: every visible string is a served field; the only FE strings are structural
 * (aria labels, "ⓘ", the loading / error glyphs). Every 🥇 A+ rings his phone since 2026-11-01 by his call; shadow =
 * recorded, never sent. UNMEASURED.
 *
 * 🔄 Scan now (2026-11-11). Ajay, verbatim: "Can you put an ondeman scan button for Luk' scans too". The 🚩 button in
 * the pass line, owner only (user.is_admin — 🚩 parity): a tap POSTs LUK_SCAN_PATH once and prints the SERVED answer
 * line for every state (started / waiting / reused / closed / refused); a served poll plan (ggScanPlan) re-reads the
 * existing GET on a setTimeout chain until the awaited pass lands (lukScanLanded) or the served wait-max passes. Button
 * only — no scan on open (HIS CALL H5). The button never hides on a served state (a closed session included); it is
 * disabled only while the POST is out or the poll it started runs. Every word is a served field. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { FOCUS_PARAM, parseFocus } from '../lib/growthArrivals';
import {
  LUK_BASE, LUK_PLAYBOOK_SUB, LUK_SCAN_PATH, LUK_SPAN_PARAM, LUK_SUB_PARAM, LUK_TRACK_SUB,
  lukHref, lukLegendRows, lukQuery, lukRefreshMs, lukScanLanded, lukText, parseLukSub, type LukBoard as LukBoardPayload,
} from '../lib/luk';
import { ggScanPlan, type GgScanResponse } from '../lib/gajjala';
import { useCurrentUser } from '../hooks/useUser';
import { LukStrip } from './LukStrip';
import { LukCard } from './LukCard';
import { LukScreens } from './LukScreens';
import { LukPlaybook } from './LukPlaybook';
import { LukTrackRecord } from './LukTrackRecord';
import { RulesInfo } from './RulesInfo';
import { useBounceRoom } from '../hooks/useBounceRoom';
import { GrowthChip } from './GrowthChip';
import { ShortInterestChip } from './ShortInterestChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import '../styles/luk.css';
/* `.gg-rescan` — the 🚩 scan-now button's look (solid accent, nowrap, margin-left auto, reduced-motion safe). */
import '../styles/gajjala.css';

export default function LukBoard() {
  const [params] = useSearchParams();
  const urlSub = parseLukSub(params.get(LUK_SUB_PARAM));
  const span = (params.get(LUK_SPAN_PARAM) || '').trim() || null;
  const focus = parseFocus(params.get(FOCUS_PARAM));
  const reqKey = lukQuery({ sub: urlSub, span, focus });

  const [board, setBoard] = useState<LukBoardPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  /* 🔄 each GET's sequence number; `boardSeq` = the one whose answer is on screen — only a read that STARTED after a
   * scan answer may clear its line or end its poll (🚩's rule, GajjalaBoard). `inFlight` = the GET still out (a poll
   * step never starts a second one over it); `boardRef` = the board last applied (read after an await). */
  const seq = useRef(0);
  const [boardSeq, setBoardSeq] = useState(0);
  const inFlight = useRef<number | null>(null);
  const boardRef = useRef<LukBoardPayload | null>(null);

  useEffect(() => {
    let alive = true;
    const my = ++seq.current;
    inFlight.current = my;
    fetch(`${API}${LUK_BASE}${reqKey ? `?${reqKey}` : ''}`, { credentials: 'include', cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return (await r.json()) as LukBoardPayload;
      })
      .then((b) => {
        if (!alive || my !== seq.current) return;
        boardRef.current = b;
        setBoard(b);
        setBoardSeq(my);
        setErr(null);
      })
      .catch((e) => { if (alive && my === seq.current) setErr(String(e?.message ?? e)); })
      .finally(() => {
        if (inFlight.current === my) { inFlight.current = null; settleReused(); }
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reqKey, tick]);

  const every = lukRefreshMs(board);
  useEffect(() => {
    const id = window.setInterval(() => setTick((n) => n + 1), every);
    return () => window.clearInterval(id);
  }, [every]);

  /* 🔄 scan now — the 🚩 contract (GajjalaBoard startScan) minus the scan on open. */
  const { user } = useCurrentUser();
  const isOwner = user?.is_admin === true;
  const [scanResp, setScanResp] = useState<GgScanResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [posting, setPosting] = useState(false);
  const [scanErr, setScanErr] = useState<string | null>(null);
  const scanPosting = useRef(false);
  const scanTimer = useRef<number | null>(null);
  const scanUntil = useRef(0);
  const scanFromSeq = useRef(0);
  const mounted = useRef(true);
  /* reused for a pass NEWER than the board on screen → ONE re-read, the served line meanwhile. */
  const reusedWant = useRef<{ at: string; seqAt: number; issued: boolean } | null>(null);
  const [noteText, setNoteText] = useState<string | null>(null);
  /* an answer with no poll (reused for the pass on screen / closed / no_room) keeps its served line until the first
   * board read that STARTS after the answer, or the next tap. */
  const noteSeq = useRef<number | null>(null);
  const settleReused = () => {
    const want = reusedWant.current;
    if (!want || !mounted.current || inFlight.current != null) return;
    if (want.issued) {
      reusedWant.current = null;
      setNoteText(null);
      return;
    }
    if (boardRef.current?.pass?.at === want.at) {
      reusedWant.current = null;
      noteSeq.current = want.seqAt;
      return;
    }
    want.issued = true;
    setTick((n) => n + 1);
  };
  const clearScanTimer = () => {
    if (scanTimer.current != null) { window.clearTimeout(scanTimer.current); scanTimer.current = null; }
  };
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; clearScanTimer(); };
  }, []);
  const stopScan = () => { clearScanTimer(); setScanning(false); };
  const startScan = async () => {
    if (scanning || scanPosting.current) return;
    scanPosting.current = true;
    setPosting(true);
    let resp: GgScanResponse | null = null;
    let detail: string | null = null;
    let failed = false;
    try {
      const r = await fetch(`${API}${LUK_SCAN_PATH}`, { method: 'POST', credentials: 'include', cache: 'no-store' });
      const body: unknown = await r.json().catch(() => null);
      if (r.ok) {
        resp = body as GgScanResponse;
      } else {
        failed = true;
        const d = (body as { detail?: unknown } | null)?.detail;
        detail = r.status !== 404 && typeof d === 'string' && d.trim() ? d : null;
      }
    } catch {
      failed = true;
    } finally {
      scanPosting.current = false;
      if (mounted.current) setPosting(false);
    }
    if (!mounted.current) return;
    // Every answer replaces the lines of the one before it.
    reusedWant.current = null;
    noteSeq.current = null;
    setNoteText(null);
    setScanErr(detail);
    if (failed || !resp || typeof resp !== 'object') { setScanResp(null); return; }
    setScanResp(resp);
    const text = lukText(resp.text);
    if (resp.state === 'reused' && typeof resp.latest_at === 'string' && resp.latest_at
        && boardRef.current?.pass?.at !== resp.latest_at) {
      reusedWant.current = { at: resp.latest_at, seqAt: seq.current, issued: false };
      setNoteText(text);
      settleReused();
      return;
    }
    const plan = ggScanPlan(resp);
    if (!plan) {
      if (resp.state !== 'refused' && text) { noteSeq.current = seq.current; setNoteText(text); }
      return;
    }
    clearScanTimer();
    scanFromSeq.current = seq.current;
    setScanning(true);
    scanUntil.current = Date.now() + plan.untilMs;
    const arm = (ms: number) => {
      scanTimer.current = window.setTimeout(() => {
        scanTimer.current = null;
        if (!mounted.current) return;
        if (inFlight.current == null) setTick((n) => n + 1);
        if (Date.now() >= scanUntil.current) { stopScan(); return; }
        arm(plan.everyMs);
      }, ms);
    };
    arm(plan.firstMs);
  };
  useEffect(() => {
    if (scanning && scanResp && boardSeq > scanFromSeq.current && lukScanLanded(board, scanResp.latest_at)) stopScan();
    if (noteSeq.current != null && boardSeq > noteSeq.current) { noteSeq.current = null; setNoteText(null); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [board, boardSeq, scanning, scanResp]);

  const sub = lukText(board?.sub) ?? urlSub;
  const subs = board?.subs ?? [];
  const legend = lukLegendRows(board?.counts_legend);
  const tiles = board?.tiles ?? [];
  const screen = board?.screens && board.screens.key === sub ? board.screens : null;
  const pass = board?.pass ?? null;
  const scan = board?.scan ?? null;
  const scanningLine = scan?.state === 'scanning' && lukText(scan.scanning_text) ? scan.scanning_text : lukText(scanResp?.text);
  const rescanTitle = scanning && scanningLine ? scanningLine
    : scan?.state === 'closed' && lukText(scan.as_of_text) ? scan.as_of_text
    : lukText(scan?.rescan_title) ?? undefined;
  /* The house chips reach this tab too (Ajay 2026-09-11 "ALL TABS IN CHART MAPS"; 2026-10-03 "add this field to all
   * our chart maps scan"): 🚀 <GrowthChip>, 🩳 <ShortInterestChip>, 🧨 <ExplosiveChip>, 🎯 <EnterableChip>, mounted
   * here per card and handed to LukCard. ONE room POST (useBounceRoom) for the cards on screen — the 🧨 / 🎯 chips
   * read that one map (the GajjalaBoard pattern; a per-card fetch is the 2026-09-21 AMD mistake). 📓 / 🏁 / a scan
   * table draw no cards → it posts nothing. NO 🧨 ordering toggle and no 🎯 filter here —
   * his setup state orders this board (A+ → triggered → forming → listed → stopped, the SERVED order); nothing is
   * hidden or reordered by a read. */
  const cardsShown = sub !== LUK_PLAYBOOK_SUB && sub !== LUK_TRACK_SUB && !screen;
  const shownSymbols = useMemo(() => (cardsShown ? tiles.map((t) => t.symbol) : []), [cardsShown, tiles]);
  const room = useBounceRoom(shownSymbols);

  return (
    <div className="luk-board" data-testid="luk-board" data-state={board ? 'loaded' : err ? 'error' : 'loading'}>
      {!board && !err ? <div className="cm-note" data-testid="luk-loading">…</div> : null}
      {err ? <div className="cm-note cm-note-err" role="status" data-testid="luk-err">{`⚠ ${err}`}</div> : null}
      {board ? (
        <>
          {lukText(board.title) ? <h2 className="luk-title" data-testid="luk-title">{board.title}</h2> : null}
          {lukText(board.honesty) ? <p className="luk-honesty" data-testid="luk-honesty">{board.honesty}</p> : null}
          <div className="luk-passline">
            {lukText(board.session?.badge) ? (
              <span className="cm-badge cm-badge-muted" data-testid="luk-session-badge">{board.session!.badge as string}</span>
            ) : null}
            {lukText(pass?.text) ? <span className="luk-muted" data-testid="luk-pass">{pass!.text}</span> : null}
            {pass?.stale && lukText(pass.stale_text) ? (
              <span className="luk-stale" data-testid="luk-stale">{pass.stale_text}</span>
            ) : null}
            {isOwner && scan && lukText(scan.rescan_label) ? (
              <button type="button" className="gg-rescan" data-testid="luk-rescan" disabled={scanning || posting}
                      aria-busy={posting ? 'true' : undefined} data-scanning={scanning ? 'true' : undefined}
                      title={rescanTitle ?? undefined} onClick={() => void startScan()}>
                {scan.rescan_label}
              </button>
            ) : null}
          </div>
          {scanning && scanningLine ? (
            <div className="cm-note gg-scanning" role="status" data-testid="luk-scanning">{scanningLine}</div>
          ) : null}
          {!scanning && noteText ? (
            <div className="cm-note" role="status" data-testid="luk-scan-note">{noteText}</div>
          ) : null}
          {scanResp?.state === 'refused' && lukText(scanResp.text) ? (
            <div className="cm-note cm-note-err" data-testid="luk-scan-refused">{scanResp.text}</div>
          ) : null}
          {scanErr ? <div className="cm-note cm-note-err" role="status" data-testid="luk-scan-err">{scanErr}</div> : null}
          <LukStrip strip={board.strip} />
          {subs.length ? (
            <nav className="cat-tabs luk-subs" aria-label="Luk sub-tabs" data-testid="luk-subs">
              {subs.map((s) => {
                const on = s.key === sub;
                return (
                  <Link key={s.key} to={lukHref(s.key)} title={lukText(s.title) ?? undefined}
                        aria-current={on ? 'page' : undefined}
                        className={`cat-tab${on ? ' is-active' : ''}`} data-testid={`luk-sub-${s.key}`}>
                    {lukText(s.emoji) ? `${s.emoji} ` : ''}{s.label}{typeof s.n === 'number' ? ` · ${s.n}` : ''}
                  </Link>
                );
              })}
            </nav>
          ) : null}
          {lukText(board.counts_text) || legend.length ? (
            <div className="luk-counts">
              {lukText(board.counts_text) ? <span data-testid="luk-counts">{board.counts_text}</span> : null}
              {legend.length ? (
                <details className="luk-fold" data-testid="luk-legend">
                  <summary aria-label="legend">{'ⓘ'}</summary>
                  <ul className="luk-legend">
                    {legend.map((l) => <li key={l.key} data-testid={`luk-legend-${l.key}`}>{l.text}</li>)}
                  </ul>
                </details>
              ) : null}
            </div>
          ) : null}

          {sub === LUK_PLAYBOOK_SUB ? (
            <LukPlaybook playbook={board.playbook} />
          ) : sub === LUK_TRACK_SUB ? (
            <LukTrackRecord track={board.track_record} />
          ) : screen ? (
            <LukScreens screen={screen} />
          ) : (
            <>
              {lukText(board.order_note) && tiles.length ? <p className="luk-line luk-muted" data-testid="luk-order-note">{board.order_note}</p> : null}
              {tiles.length ? (
                <div className="cm-grid luk-grid" data-testid="luk-grid">
                  {tiles.map((t) => (
                    <LukCard key={`${t.symbol}-${t.setup}`} tile={t} focus={focus === t.symbol}
                             houseChips={(
                               <>
                                 <GrowthChip symbol={t.symbol} />
                                 {' '}<ShortInterestChip symbol={t.symbol} />
                                 {' '}<ExplosiveChip read={room.map.get(t.symbol.toUpperCase())?.explosive} study={room.payload?.explosive_study} />
                                 {' '}<EnterableChip read={room.map.get(t.symbol.toUpperCase())?.enterable} />
                               </>
                             )} />
                  ))}
                </div>
              ) : null}
            </>
          )}
        </>
      ) : null}
      <div className="cm-rules">
        <RulesInfo section="luk" />
      </div>
    </div>
  );
}
