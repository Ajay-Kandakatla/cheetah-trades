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
 * 🔄 Scan now (2026-11-11). Ajay, verbatim: "Can you put an ondeman scan button for Luk' scans too". The 🚩 button —
 * since the later 2026-11-11 change in the title row (.luk-topline), right after the title, its answer lines under that
 * row, above the honesty paragraph (it used to sit at the far right end of the pass line) — owner only (user.is_admin — 🚩 parity): a tap POSTs LUK_SCAN_PATH once and prints the SERVED answer
 * line for every state (started / waiting / reused / closed / refused); a served poll plan (ggScanPlan) re-reads the
 * existing GET on a setTimeout chain until the awaited pass lands (lukScanLanded) or the served wait-max passes. Button
 * only — no scan on open (HIS CALL H5). The button never hides on a served state (a closed session included); it is
 * disabled only while the POST is out or the poll it started runs. Every word is a served field.
 *
 * 🔴 Realtime cards (2026-11-12, spec §3.5). Ajay, verbatim: "Luks scan is not realtime I see all dated values can you
 * make it realtime". (1) The house card poll: ONE useCardLive call for the cards on screen (setup subs only, inside the
 * SERVED window — refresh_sec > 0), its `levels` the served per-card `live_level`s copied verbatim (a stopped card
 * serves none). Poll only: no `stream`, no `variant` — 🥇 is not in 🚩's stream registry. The served footer prints in
 * the pass line. The overlay never changes a card's state, its order or the counts line. (2) The board re-read: when
 * the pass serves `next_read_sec`, ONE setTimeout, re-armed after EVERY GET settles (a failed one included), replaces
 * the cadence interval; absent → the served cadence interval exactly as before.
 *
 * 🏁 Ended cards fold (2026-11-12, lukend spec §3.6). Ajay, verbatim: "Is this still good ro enter? From Luks" → "I
 * shouldn't be seeing this" → "I want it to be realtime". The server folds every card whose Luk trade is over into the
 * served `ended` block (its count, its words, its cards); this board draws the live `tiles` in the grid and ONE fold line
 * under it (a <details>, cards mounted only when open). Real time: a trade card serves a `live_fold` rule, and the moment
 * a FRESH answer of the one card poll matches it the card is latched into the fold (no pass, no GET). Fresh = the answer
 * changed on a run where the tiles did not — the commit that brings new tiles (a sub switch, a re-GET) still carries the
 * previous board's answer (useCardLive clears it one commit later), so that run is skipped (critique C3). The poll's
 * symbols and levels stay on the served tiles (a fold never changes the poll's key). The latch is cleared when the served
 * session date changes. Every word is served; the FE adds only the count. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { FOCUS_PARAM, parseFocus } from '../lib/growthArrivals';
import {
  LUK_BASE, LUK_PLAYBOOK_SUB, LUK_SCAN_PATH, LUK_SPAN_PARAM, LUK_SUB_PARAM, LUK_TRACK_SUB,
  lukEndedLine, lukHref, lukInWindow, lukLegendRows, lukLiveLevels, lukNewLiveEnds, lukNextReadMs, lukQuery,
  lukRefreshMs, lukScanLanded, lukSplitLive, lukText, parseLukSub,
  type LukBoard as LukBoardPayload, type LukLatch, type LukTile,
} from '../lib/luk';
import { ggScanPlan, type GgScanResponse } from '../lib/gajjala';
import { cardLiveSymbols } from '../lib/cardLive';
import type { CmTapeSession } from '../lib/chartMaps';
import { useCardLive } from '../hooks/useCardLive';
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

/** 🏁 a null board's tiles — ONE frozen empty list, so a board that has not landed never churns the tiles' identity. */
const NO_TILES: LukTile[] = Object.freeze([] as LukTile[]) as LukTile[];
/** 🏁 an empty latch — one frozen object, so "nothing latched" never churns the split. */
const NO_LATCH: Record<string, LukLatch> = Object.freeze({}) as Record<string, LukLatch>;

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
  /* 🔴 2026-11-12: bumped when the LATEST GET settles (success or error) — re-arms the served next-read timer. */
  const [settled, setSettled] = useState(0);
  /* 🏁 2026-11-12: the request key of the board on screen — the fold's open state resets to the served `ended.open`
   * only when a board of a NEW request lands (a re-GET never closes what he opened). */
  const [boardReq, setBoardReq] = useState<string | null>(null);

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
        setBoardReq(reqKey);
        setBoardSeq(my);
        setErr(null);
      })
      .catch((e) => { if (alive && my === seq.current) setErr(String(e?.message ?? e)); })
      .finally(() => {
        if (inFlight.current === my) { inFlight.current = null; settleReused(); }
        if (my === seq.current && mounted.current) setSettled((n) => n + 1);
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reqKey, tick]);

  const every = lukRefreshMs(board);
  /* 🔴 2026-11-12: a served next-read time replaces the interval; none served → the cadence interval as before. */
  const nextServed = lukNextReadMs(board) != null;
  useEffect(() => {
    if (nextServed) return undefined;
    const id = window.setInterval(() => setTick((n) => n + 1), every);
    return () => window.clearInterval(id);
  }, [every, nextServed]);
  /* ONE timer at the served `next_read_sec` of the board on screen, re-armed after every GET settles (a failed GET keeps
   * the board and re-arms on its served time). A GET still out when it fires re-arms on its own settle. */
  useEffect(() => {
    const ms = lukNextReadMs(boardRef.current);
    if (ms == null) return undefined;
    const id = window.setTimeout(() => { if (inFlight.current == null) setTick((n) => n + 1); }, ms);
    return () => window.clearTimeout(id);
  }, [settled]);

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
  const tiles = board?.tiles ?? NO_TILES;
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
   * hidden or reordered by a read. 2026-11-11 — the served tile order is the only order: a card's served
   * `not_reread` flag tags it (LukCard's pill) and never reorders it here; `tiles.map` is the one order. */
  const cardsShown = sub !== LUK_PLAYBOOK_SUB && sub !== LUK_TRACK_SUB && !screen;
  const shownSymbols = useMemo(() => (cardsShown ? tiles.map((t) => t.symbol) : []), [cardsShown, tiles]);
  const room = useBounceRoom(shownSymbols);
  /* 🔴 2026-11-12 — the house card poll on the cards on screen (setup subs, inside the served window), poll only. */
  const inWindow = lukInWindow(board);
  const liveSyms = useMemo(() => (cardsShown ? cardLiveSymbols(tiles) : []), [cardsShown, tiles]);
  const liveLevels = useMemo(() => (cardsShown ? lukLiveLevels(tiles) : {}), [cardsShown, tiles]);
  const cardPoll = useCardLive(liveSyms, inWindow && liveSyms.length > 0, {
    resetKey: board, initialSession: (board?.session?.tape ?? null) as CmTapeSession | null, levels: liveLevels,
  });
  const liveFooter = inWindow && liveSyms.length > 0 ? lukText(cardPoll.footer) : null;
  /* 🏁 2026-11-12 — the live latch, per served session date (a new date starts empty). */
  const servedDate = board?.session?.date;
  const sessionDate = typeof servedDate === 'string' ? servedDate : null;
  const [latch, setLatch] = useState<{ date: string | null; map: Record<string, LukLatch> }>({ date: null, map: {} });
  const latched = latch.date === sessionDate ? latch.map : NO_LATCH;
  const prevAnswer = useRef(cardPoll.answer);
  const prevTiles = useRef(tiles);
  useEffect(() => {
    const fresh = cardPoll.answer !== prevAnswer.current && tiles === prevTiles.current;
    prevAnswer.current = cardPoll.answer;
    prevTiles.current = tiles;
    if (!fresh) return;
    const answer = cardPoll.answer;
    setLatch((prev) => {
      const base = prev.date === sessionDate ? prev.map : NO_LATCH;
      const add = lukNewLiveEnds(tiles, answer, base);
      return add ? { date: sessionDate, map: { ...base, ...add } } : prev;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cardPoll.answer, tiles]);
  const split = useMemo(() => lukSplitLive(tiles, latched), [tiles, latched]);
  const ended = board?.ended ?? null;
  const endedLine = cardsShown ? lukEndedLine(ended, split.ended.length) : null;
  /* his tap wins for the request it was made on; a board of a new request opens as served. */
  const [openPick, setOpenPick] = useState<{ req: string | null; open: boolean } | null>(null);
  const endedOpen = openPick && openPick.req === boardReq ? openPick.open : ended?.open === true;
  const endedToggle = lukText(ended?.toggle_text);
  /* 🔄 2026-11-11 — the ONE button, owner only, in the title row right after the title (luk.css .luk-topline); its
   * served answer lines print directly under that row, above the honesty paragraph, for every state. */
  const rescan = isOwner && scan && lukText(scan.rescan_label) ? (
    <button type="button" className="gg-rescan" data-testid="luk-rescan" disabled={scanning || posting}
            aria-busy={posting ? 'true' : undefined} data-scanning={scanning ? 'true' : undefined}
            title={rescanTitle ?? undefined} onClick={() => void startScan()}>
      {scan.rescan_label}
    </button>
  ) : null;

  return (
    <div className="luk-board" data-testid="luk-board" data-state={board ? 'loaded' : err ? 'error' : 'loading'}>
      {!board && !err ? <div className="cm-note" data-testid="luk-loading">…</div> : null}
      {err ? <div className="cm-note cm-note-err" role="status" data-testid="luk-err">{`⚠ ${err}`}</div> : null}
      {board ? (
        <>
          {lukText(board.title) || rescan ? (
            <div className="luk-topline" data-testid="luk-topline">
              {lukText(board.title) ? <h2 className="luk-title" data-testid="luk-title">{board.title}</h2> : null}
              {rescan}
            </div>
          ) : null}
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
          {lukText(board.honesty) ? <p className="luk-honesty" data-testid="luk-honesty">{board.honesty}</p> : null}
          <div className="luk-passline">
            {lukText(board.session?.badge) ? (
              <span className="cm-badge cm-badge-muted" data-testid="luk-session-badge">{board.session!.badge as string}</span>
            ) : null}
            {lukText(pass?.text) ? <span className="luk-muted" data-testid="luk-pass">{pass!.text}</span> : null}
            {pass?.stale && lukText(pass.stale_text) ? (
              <span className="luk-stale" data-testid="luk-stale">{pass.stale_text}</span>
            ) : null}
            {liveFooter ? <span className="luk-muted" data-testid="luk-live-footer">{liveFooter}</span> : null}
          </div>
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
              {split.live.length ? (
                <div className="cm-grid luk-grid" data-testid="luk-grid">
                  {split.live.map((t) => (
                    <LukCard key={`${t.symbol}-${t.setup}`} tile={t} focus={focus === t.symbol}
                             live={cardPoll.answer?.quotes[(t.symbol || '').toUpperCase()]}
                             nowLabels={cardPoll.answer?.now_labels}
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
              {endedLine ? (
                <details className="luk-ended" data-testid="luk-ended" open={endedOpen}>
                  <summary data-testid="luk-ended-line"
                           onClick={(e) => { e.preventDefault(); setOpenPick({ req: boardReq, open: !endedOpen }); }}>
                    {endedLine}{!endedOpen && endedToggle ? ` · ${endedToggle}` : ''}
                  </summary>
                  {endedOpen ? (
                    <>
                      {lukText(ended?.note_text) ? <p className="luk-line luk-muted" data-testid="luk-ended-note">{ended!.note_text}</p> : null}
                      <div className="cm-grid luk-grid" data-testid="luk-ended-grid">
                        {[...split.ended, ...(ended?.tiles ?? [])].map((t) => (
                          <LukCard key={`ended-${t.symbol}-${t.setup}`} tile={t} focus={focus === t.symbol} />
                        ))}
                      </div>
                      {lukText(ended?.more_text) ? <p className="luk-line luk-muted" data-testid="luk-ended-more">{ended!.more_text}</p> : null}
                    </>
                  ) : null}
                </details>
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
