/* GajjalaBoard — 🚩 Gajjala's tab on Chart Maps (2026-10-13).
 *
 * Ajay: "Now can you build a new tab and build sub tabs for it with multiple
 * strategies. Name the Tab Gajjala's he has multiple strategies..around this.
 * He is volume and price action based traded with short squeeze. He also has
 * premarket and post market analysis." … "Implement his full stategy do not
 * assume anything."
 *
 * Goverdhan Gajjala's five 5-minute setups over HIS scanner on the whole US
 * market, plus ☀️ Premarket, 🌙 Post-market and 📓 his Playbook (then 🧠
 * Potential and 🏁 Track record, below) — ten sub tabs, one endpoint
 * (GET /chart-maps/gajjala). The cron pass scans, reads and stores; the endpoint reads Mongo and ORDERS; this file draws. Every sentence
 * the card prints — the state label, the strip, the criteria, the chips, the
 * quotes — is SERVED; the FE types only structural words. No rule number is
 * typed here, so a changed knob on the server shows up with no FE deploy.
 *
 * The tiles are PatternChart (bars + the served 9 and 21 EMA curves + BUY /
 * STOP lines + the A+ marker + the volume pane). The 🚀 / 🩳 / 🧨 / 🎯 chips in
 * the head row are that NAME's house reads, carried so the tab is not a dead
 * end (HIS CALL 19) — this board is not ordered, filtered or gated by them.
 *
 * NO 🧨 ordering toggle — his setup state orders this board (A+ → forming →
 * partial). The order is the server's (spec §3.4.1 ordering keys); a 🧨 daily
 * S&D ordering would rank his 5-minute setups by a read he does not use.
 *
 * UNMEASURED. Nothing here trades, enters a lane or sizes a position.
 *
 * 🧠 Potential + 📈 Track (2026-10-15, BUILD_SPEC4 §3.11). Ajay: "In Gajjalas
 * setup I wanna find potential stocks this shows me what has happened I am
 * trying to setup for this tab to act like Gajjalas brain. So create a
 * potential category in this section." and "In all the sub tab and add a track
 * and alert to show me new potential is added everyday." Each setup sub draws
 * a compact 🧠 strip above its grid (a row click sets `focus`, so the existing
 * once-per-value scroll lands on that tile — no sixth card grid, Rule #5); the
 * ninth sub 🧠 Potential draws the 📈 Track (today open, the session before
 * folded, a timeline per row), the 👀 watch line, then the roll-up tiles. The
 * live 🧠 push line sits under the A+ line (LIVE since 2026-10-16). Every word and number of
 * those surfaces is SERVED (potential.py / tab.py); the FE types none. A
 * potential, not an entry. UNMEASURED.
 *
 * 🔄 Scan on open + 🎯 A+ line (2026-10-15, BUILD_SPEC5 §3.8). Ajay: "When
 * ever I open Gajjala's intiate a new scan of stocks.  In that moment and if
 * there are any enterable stocks on the top which I see in potential i guess".
 * Mounting this board (opening the tab, or switching into tab=gajjala — the
 * ChartMaps ternary remounts it) POSTs GG_SCAN_PATH ONCE, for the house owner
 * only (`is_admin === true`; anyone else sees the cron read and never POSTs).
 * The server answers at once (started / reused / waiting / closed / refused)
 * and sets the poll plan; the board re-reads the EXISTING GET on that plan
 * until the served pass.at advances on a board read AFTER the POST answered
 * (2026-10-16 fix round 1 — a board one re-read old never ends the scan; the
 * last step re-reads before it gives up), and the board it had stays on screen
 * under the served "scanning…" line meanwhile — never a blank board (2026-10-16
 * fix round 2: a poll step never starts a GET over one still in flight, and a
 * 🔄 answered "reused" for a pass newer than the board on screen re-reads ONCE,
 * the served line showing until that read lands). An open
 * rings no device: both push gates run dry on an on-open pass. The 🎯 line is
 * A+ only — the served rows of the latest pass (the server picks them; the FE
 * filters nothing and composes no word) — on every sub, right under the sub
 * strip, so on 🧠 Potential it leads the 📈 Track. UNMEASURED.
 *
 * 🏁 Track record (2026-10-16, BUILD_SPEC9 §3.11). Ajay: "also can you track
 * all Gajjals stocks and keep a new tab to show wins vs losses. To see a
 * percentage and the ticker." and "We are not looking for winners just in time
 * but when they got in to our alerts if they made it or not. Like XLAB today
 * was a winner I made good money on it". The tenth sub, LAST, draws no tiles
 * (so no room POST): a table per day of the served rows — ticker, setup, alert
 * time, kind, the plan, the same-session and through-next-session cells — under
 * the served header counts, with the served day picker (`?span=`, the only new
 * param; a sub click drops it). The server grades every alert by GG's trade
 * math and words every cell, count, label and %; this panel types no word and
 * no number. A ledger of the alerts as sent, not a study. UNMEASURED.
 *
 * 🎯 A+ entry live (2026-10-16, DECISIONS10). Ajay: "can you add liver tracker
 * for Gajjala's entry." and "Dont understand the question I amlooking for Entry
 * of his stocks from all 5 tabs. When every they satisfy all his criteria.. LIke
 * for some he says we need to make sure EMA is kissed you alert me when that
 * happens 5 mins track of it when there are potentials and also look for new
 * potentials". A 🧠 Track row prints the SERVED entry_text when its entry rang;
 * the 🏁 panel prints the SERVED entries_text line right under the shadow line
 * (AMENDMENTS10 F3 — the live A+ entries on their own line, never pooled with
 * the 🧠 %); this file types no entry word. UNMEASURED.
 *
 * ☀️ / 🌙 movers clickable (2026-10-16, DECISIONS10 D7). Ajay: "Also in the
 * after market movers under Gajjala's can you make sure I can click on them."
 * — same place as other Gajjala rows (his answer). A bar-less ☀️ / 🌙 tile is a
 * router Link to its SERVED tile.href (the charted tile's own target, through
 * withSource + the back state — no full-page reload); a 🌙 A+ recap row is a
 * router Link to its SERVED href (the setup card, tab.recap). Both pass ggHref
 * first — an href that is not an in-app path renders the symbol as text. The
 * CardExtras lines stay text (the tile is the link). The FE composes no href.
 *
 * 🕰️ Entries timeline (2026-10-16, DECISIONS11 D1–D3). Ajay: "We have a Promo Circuit tab in Catalyst tab. Can you
 * use the graph component from  that to show what happened to Entries alert of Gajjala with all the 100% criteria
 * satisfier. One you alert it from the alert system you built please". The 🏁 panel gains the SERVED view toggle
 * (`?view=`, FE-only — the GET never carries it; a sub click drops it, a span click keeps it): 📋 all alerts (the
 * default, the tables as shipped) | 🕰️ entries timeline — only the rows whose kind is in the served `views.kinds`
 * (the A+ entries), in the served order, each with the Promo Circuit's lazy mini tape and a 📈 toggle that opens
 * the full tape under the row (the Promo table's pattern). The FE types no tape word: every label, line, dot and
 * read on the tape is served by chart_maps/gajjala/tape.py. UNMEASURED — a record of what each alert did.
 *
 * ⏪ Replayed line + ✅ / ❌ categories (2026-10-16 night, DECISIONS11 D4–D5 / D11–D12, AMENDMENTS11 F13). Ajay: "Would
 * you be able to back test for the past week from his alerts any way to do so? build a pre historic timeline or so?"
 * and "I want winners and losers category in his track record and would like us to study the losers". The 🏁 panel
 * prints the SERVED ⏪ replayed line and its caveat line right under the 🎯 entries line (replayed rows never rang and
 * are in no %), the served ⏪ chip in a replayed row's Kind cell, the SERVED category chips (`?cat=`, FE-only — the GET
 * never carries it; a sub click drops it, a span or view click keeps it; each chip's ROW count is inside its served
 * text) that filter either view client-side by the served row `bucket`, and a ❌ row's served loss facts as a sub-line
 * under it (in the 🕰️ timeline, under its tape). No per-row ✅ / ❌ chip (AMENDMENTS11 F13 — the Same / Through-next
 * cells already say it). The FE types no category, loss or replay word. UNMEASURED — rows, never a %.
 *
 * 🚫 Broker tag (2026-10-17, DECISIONS12 D1–D9, AMENDMENTS12). His second and third lines of the ask (DECISIONS12
 * §The ask) are quoted verbatim in lib/gajjala.ts and in the ✨ entry — this file never spells the broker's name, not
 * even in a comment. A TAG, never a filter: nothing here hides, filters, mutes or counts a name. Each row that names a
 * symbol prints its SERVED `broker_text` as a muted chip beside the symbol (tiles, ☀️ / 🌙 movers, the 🌙 recap, the
 * 🧠 strip, 📈 Track, 👀 watch, the 🎯 line, 🪦 graveyard and the 🏁 rows — siblings after the pinned elements). The
 * owner's 🚫 strip under the header (the served words, his names each with ✕ → DELETE, one add field → POST) and the
 * icon-only 🚫 card toggle mount only when the SERVED `broker_flags` block says editable — the server serves it to the
 * primary owner alone (null for anyone else), so the FE gates on nothing of its own; a served `fault_text` prints in
 * place of the add box. One write at a time (every broker control disabled while one is in flight); a write that lands
 * re-reads the board ONCE. The owner header comes from the proxy, never typed here. Every word is served by tab.py;
 * the FE never types the broker's name.
 */
import { Fragment, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { PatternChart } from './PatternChart';
import { GrowthChip } from './GrowthChip';
import { ShortInterestChip } from './ShortInterestChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import { RulesInfo } from './RulesInfo';
import { GgEntryMiniTape, GgEntryTape } from './GgEntryTape';
import { useBounceRoom } from '../hooks/useBounceRoom';
import { useCurrentUser } from '../hooks/useUser';
import { outerChipsFor } from '../lib/outerChips';
import { FOCUS_PARAM, parseFocus } from '../lib/growthArrivals';
import { trackFeature } from '../lib/usageTracker';
import { pxText, shortVol } from '../lib/chartMaps';
import { sanitizeSourceQuery, withSource } from '../lib/navSource';
import {
  GG_BROKER_PATH, GG_CAT_PARAM, GG_OUTER_CHIPS, GG_SCAN_PATH, GG_SORT_PARAM, GG_SPAN_PARAM, GG_SUBS, GG_SUB_PARAM, GG_TFS, GG_TF_PARAM, GG_VIEW_PARAM, GG_VIEW_TIMELINE,
  changeText, chipText, criteriaText, ggCatDays, ggCatOn, ggHref, gradeText, ggQuery, ggRefreshMs, ggTimelineOn, isGgSetup, parseGgSub, parseGgTf,
  ggScanAdvanced, ggScanPlan, playbookItem, riskText, variantText, watchParts,
  type GgBoard, type GgBrokerFlags, type GgEnterable, type GgScanResponse, type GgPlaybook, type GgPlaybookItem, type GgPotentialStrip, type GgRead, type GgSub, type GgTell,
  type GgTf, type GgTile, type GgTrack, type GgTrackBlock, type GgTrackRecord, type GgTrackRow, type GgTrCell,
  type GgTrCategory, type GgTrDay, type GgTrRow, type GgTrViews as GgTrViewsBlock, type GgWatch,
} from '../lib/gajjala';
import '../styles/gajjala.css';

const NO_TOGGLE_REASON = 'NO \u{1F9E8} ordering toggle — his setup state orders this board (A+ → forming → partial)';

/** Structural words for the counts line when the server sends no sentence. */
const COUNT_WORDS: ReadonlyArray<[string, string]> = [
  ['aplus', 'A+'], ['triggered', 'triggered'], ['forming', 'forming'], ['partial', 'partial'],
  ['stopped', 'stopped'], ['invalid', 'invalid'], ['none', 'none'], ['awaiting_answer', 'awaiting your number'],
  ['listed', 'listed'],
];

export default function GajjalaBoard() {
  const [params, setParams] = useSearchParams();
  /* The back-to-tab glue of PatternChart.tsx:235-236 (Ajay 2026-08-25: "back button do not take me to the same place
   * in these tabs") — a bar-less ☀️ / 🌙 tile links the same way a charted tile does, state + ?from/from_q. */
  const location = useLocation();
  const carryQ = sanitizeSourceQuery(location.search);
  const backTarget = carryQ ? `/chart-maps?${carryQ}` : '/chart-maps';
  const urlSub = parseGgSub(params.get(GG_SUB_PARAM));
  const tf = parseGgTf(params.get(GG_TF_PARAM));
  const focus = parseFocus(params.get(FOCUS_PARAM));
  const sort = (params.get(GG_SORT_PARAM) || '').trim() || null;
  const span = (params.get(GG_SPAN_PARAM) || '').trim() || null;
  /* 🕰️ the 🏁 view — FE-only: it never rides the GET (ggQuery has no view), so a toggle click fetches nothing. */
  const view = (params.get(GG_VIEW_PARAM) || '').trim() || null;
  /* ✅ / ❌ the 🏁 category — FE-only too (a client-side filter by the served row bucket): a chip click fetches nothing. */
  const cat = (params.get(GG_CAT_PARAM) || '').trim() || null;

  const [board, setBoard] = useState<GgBoard | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const seq = useRef(0);
  /* The `seq` of the GET whose answer is the board on screen — the 🔄 poll judges "landed" only on a board read
   * AFTER the scan POST answered (a board one re-read old must never end the scan it asked for). */
  const [boardSeq, setBoardSeq] = useState(0);
  /* The request the URL write-back below would trigger again: when the server
   * resolves a `focus` deep link to a sub, the URL adopts it with `replace` —
   * the board already in hand IS that sub's board, so no second fetch. */
  const adoptedKey = useRef<string | null>(null);
  /* The `seq` of the GET still in flight (null = none). A 🔄 poll step never starts a GET over it — a newer GET
   * supersedes the older one, so a GET slower than the served poll would never land and the board would stay blank
   * for the whole wait (2026-10-16 fix round 2). */
  const inFlight = useRef<number | null>(null);
  /* The board last applied — read by startScan after its await and by a GET's settle step (a closure would hold the
   * board of an older render). */
  const boardRef = useRef<GgBoard | null>(null);

  const reqKey = ggQuery({ sub: urlSub, tf, focus, sort, span });

  useEffect(() => {
    if (adoptedKey.current === reqKey) { adoptedKey.current = null; return; }
    adoptedKey.current = null;
    let alive = true;
    const my = ++seq.current;
    inFlight.current = my;
    setLoading(true);
    fetch(`${API}/chart-maps/gajjala?${reqKey}`, { credentials: 'include', cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return (await r.json()) as GgBoard;
      })
      .then((b) => {
        if (!alive || my !== seq.current) return;
        boardRef.current = b;
        setBoard(b);
        setBoardSeq(my);
        setErr(null);
        // The SERVED sub is authoritative: an absent `sub` (a `focus` deep
        // link) or an unknown one is written back with `replace`.
        const served = parseGgSub(b?.sub);
        if (served && served !== params.get(GG_SUB_PARAM)) {
          const next = new URLSearchParams(params);
          next.set(GG_SUB_PARAM, served);
          const nextKey = ggQuery({ sub: served, tf, focus, sort, span });
          if (nextKey !== reqKey) adoptedKey.current = nextKey;
          setParams(next, { replace: true });
        }
      })
      .catch((e) => { if (alive && my === seq.current) setErr(String(e?.message ?? e)); })
      .finally(() => {
        if (alive && my === seq.current) setLoading(false);
        if (inFlight.current === my) { inFlight.current = null; settleReused(); }
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reqKey, tick]);

  // Re-read on the SERVED cadence only; 0 / absent (a closed session) = no timer.
  const every = ggRefreshMs(board);
  useEffect(() => {
    if (!every) return;
    const id = window.setInterval(() => setTick((n) => n + 1), every);
    return () => window.clearInterval(id);
  }, [every]);

  /* 🔄 scan on open (2026-10-15). ONE POST per mount, owner only; the poll is a
   * chain of setTimeouts on the SERVED plan (never a second setInterval), each
   * step a re-read of the existing GET above (`tick`). */
  const { user } = useCurrentUser();
  const isOwner = user?.is_admin === true;
  const [scanResp, setScanResp] = useState<GgScanResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const scanAsked = useRef(false);
  const scanPosting = useRef(false);
  const scanTimer = useRef<number | null>(null);
  const scanUntil = useRef(0);
  /* seq.current when the POST answered: only a GET started after it may show the awaited pass. */
  const scanFromSeq = useRef(0);
  const mounted = useRef(true);
  /* A 🔄 answered "reused" for a pass newer than the board on screen: ONE re-read, the served line meanwhile
   * (2026-10-16 fix round 2 — the board re-reads on the served cadence only, so it could lag a whole cadence).
   * Settled right after the POST answers, and again as each GET finishes (never while one is in flight). */
  const reusedWant = useRef<{ at: string; issued: boolean } | null>(null);
  const [reusedText, setReusedText] = useState<string | null>(null);
  const settleReused = () => {
    const want = reusedWant.current;
    if (!want || !mounted.current || inFlight.current != null) return;
    if (want.issued || boardRef.current?.pass?.at === want.at) {
      reusedWant.current = null;
      setReusedText(null);
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
    let resp: GgScanResponse | null = null;
    try {
      const r = await fetch(`${API}${GG_SCAN_PATH}`, { method: 'POST', credentials: 'include', cache: 'no-store' });
      if (!r.ok) return;
      resp = (await r.json()) as GgScanResponse;
    } catch {
      return;
    } finally {
      scanPosting.current = false;
    }
    if (!mounted.current || !resp || typeof resp !== 'object') return;
    setScanResp(resp);
    reusedWant.current = null;
    setReusedText(null);
    if (resp.state === 'reused' && typeof resp.latest_at === 'string' && resp.latest_at
        && boardRef.current?.pass?.at !== resp.latest_at) {
      reusedWant.current = { at: resp.latest_at, issued: false };
      setReusedText(typeof resp.text === 'string' && resp.text.trim() ? resp.text : null);
      settleReused();
      return;
    }
    const plan = ggScanPlan(resp);
    if (!plan) return;
    clearScanTimer();
    scanFromSeq.current = seq.current;
    setScanning(true);
    scanUntil.current = Date.now() + plan.untilMs;
    // Each step re-reads FIRST, then gives up if the served wait-max has passed: an eta equal to the wait-max
    // (the "waiting for the first cron pass" answer) still gets its one re-read. A step that finds a GET still in
    // flight starts none — that GET's answer is the re-read, and the board it had stays on screen meanwhile.
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
    if (!isOwner || scanAsked.current) return;
    scanAsked.current = true;
    void startScan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOwner]);
  useEffect(() => {
    if (scanning && scanResp && boardSeq > scanFromSeq.current && ggScanAdvanced(board, scanResp.latest_at)) stopScan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [board, boardSeq, scanning, scanResp]);

  /* 🚫 the owner's list writes (2026-10-17, AMENDMENTS12 F2): ONE write at a time — the ref blocks a second click in
   * the same tick, the state disables every broker control while it is in flight. ok → ONE board re-read (`tick`);
   * 404 → nothing; anything else → the SERVED `detail` when it is a string, else nothing (the FE types no word). */
  const brokerBusyRef = useRef(false);
  const [brokerBusy, setBrokerBusy] = useState(false);
  const [brokerErr, setBrokerErr] = useState<string | null>(null);
  const brokerWrite = async (method: 'POST' | 'DELETE', sym: string): Promise<boolean> => {
    const symbol = String(sym || '').trim();
    if (!symbol || brokerBusyRef.current) return false;
    brokerBusyRef.current = true;
    setBrokerBusy(true);
    try {
      const r = method === 'POST'
        ? await fetch(`${API}${GG_BROKER_PATH}`, {
          method: 'POST', credentials: 'include', cache: 'no-store',
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol }),
        })
        : await fetch(`${API}${GG_BROKER_PATH}/${encodeURIComponent(symbol)}`, {
          method: 'DELETE', credentials: 'include', cache: 'no-store',
        });
      if (!mounted.current) return false;
      if (r.ok) { setBrokerErr(null); setTick((n) => n + 1); return true; }
      if (r.status === 404) return false;
      let detail: unknown = null;
      try { detail = ((await r.json()) as { detail?: unknown } | null)?.detail; } catch { detail = null; }
      if (mounted.current) setBrokerErr(typeof detail === 'string' && detail.trim() ? detail : null);
      return false;
    } catch {
      return false;
    } finally {
      brokerBusyRef.current = false;
      if (mounted.current) setBrokerBusy(false);
    }
  };
  /* The gate is the SERVED block — never isOwner: the server serves it to the primary owner only. */
  const brokerBlock: GgBrokerFlags | null = board?.broker_flags && typeof board.broker_flags === 'object' ? board.broker_flags : null;
  const brokerEditable = brokerBlock?.editable === true;
  const brokerFault = typeof brokerBlock?.fault_text === 'string' && brokerBlock.fault_text.trim() ? brokerBlock.fault_text : null;

  const activeSub: GgSub | null = parseGgSub(board?.sub) ?? urlSub;
  useEffect(() => {
    if (activeSub) trackFeature(`chart-maps:tab:gajjala:${activeSub}`);
  }, [activeSub]);

  // 📓 and 🏁 draw no tiles, so useBounceRoom posts nothing on them.
  const tiles = useMemo<GgTile[]>(
    () => (activeSub === 'playbook' || activeSub === 'track_record' ? [] : (board?.tiles || [])), [board, activeSub]);
  const shownSymbols = useMemo(() => tiles.map((t) => t.symbol), [tiles]);
  /* ONE room POST (useBounceRoom) for every name on screen — the 🧨 / 🎯 chips read that
   * one map (the EmaFramesBoard precedent; a per-tile fetch is the 2026-09-21
   * AMD mistake). Nothing on this board is ordered or hidden by it. */
  const room = useBounceRoom(shownSymbols);

  // `focus` scrolls to that tile ONCE per focus value, the first time its tile
  // has landed. The param stays in the URL (the outline keeps marking the tile)
  // and every served refresh hands a new `tiles` array — keyed on the tiles
  // alone, the page jumped back to the focused tile every 5 minutes.
  const tileRefs = useRef(new Map<string, HTMLDivElement>());
  const scrolledFor = useRef<string | null>(null);
  useEffect(() => {
    if (!focus) { scrolledFor.current = null; return; }
    if (scrolledFor.current === focus) return;
    const el = tileRefs.current.get(focus);
    if (!el) return;
    scrolledFor.current = focus;
    if (typeof el.scrollIntoView === 'function') el.scrollIntoView({ block: 'center' });
  }, [focus, tiles]);

  const setParam = (key: string, value: string | null, drop: string[] = []) => {
    const next = new URLSearchParams(params);
    if (value == null) next.delete(key); else next.set(key, value);
    for (const d of drop) next.delete(d);
    setParams(next);
  };
  // A sub click keeps `tab=gajjala` (it is what keeps this board mounted) and
  // drops the ☀️ / 🌙 sort and the 🏁 span + 🕰️ view + ✅ / ❌ category, which belong to the sub they were picked on.
  const pickSub = (s: GgSub) => setParam(GG_SUB_PARAM, s, [GG_SORT_PARAM, GG_SPAN_PARAM, GG_VIEW_PARAM, GG_CAT_PARAM]);

  const subs = board?.subs?.length ? board.subs : GG_SUBS.map((s) => ({ ...s, count: null }));
  const session = board?.session;
  const pass = board?.pass;
  const strip = board?.strip;
  const servedTf = board?.tf ?? tf ?? '5m';
  const scan = board?.scan ?? null;
  const scanOpen = !!scan && scan.state !== 'closed';
  const asOfServed = scanOpen && typeof scan?.as_of_text === 'string' && scan.as_of_text.trim() ? scan.as_of_text : null;
  const scanningLine = scan?.state === 'scanning' && scan.scanning_text ? scan.scanning_text : scanResp?.text;

  return (
    <div className="gg-board" data-no-toggle={NO_TOGGLE_REASON} data-state={board ? 'loaded' : 'loading'}>
      {/* (1) situational-awareness strip — his read of the day (S8 43:39). */}
      <div className="gg-strip" data-testid="gg-strip" role="status">
        {strip?.text ? <span className="gg-strip-text" data-testid="gg-strip-text">{strip.text}</span> : null}
        {session?.badge ? <span className="cm-badge cm-badge-muted" data-testid="gg-session-badge">{session.badge}</span> : null}
        {session?.label ? <span className="gg-muted">{session.label}</span> : null}
        {asOfServed ? <span className="gg-muted" data-testid="gg-as-of">{asOfServed}</span>
          : pass?.as_of_et ? <span className="gg-muted" data-testid="gg-as-of">as of {pass.as_of_et}</span> : null}
        {isOwner && scanOpen && scan?.rescan_label ? (
          <button type="button" className="gg-rescan" data-testid="gg-rescan" disabled={scanning}
                  title={scan.rescan_title || undefined} onClick={() => void startScan()}>
            {scan.rescan_label}
          </button>
        ) : null}
      </div>
      {brokerBlock && (brokerEditable || brokerFault) ? (
        <BrokerFlagsStrip block={brokerBlock} editable={brokerEditable} fault={brokerFault} busy={brokerBusy}
                          err={brokerErr} onWrite={brokerWrite} />
      ) : null}
      {pass?.stale ? (
        <div className="cm-note cm-note-err" data-testid="gg-stale">
          {pass.stale_text || `stale · last pass ${pass.as_of_et ?? '—'}`}
        </div>
      ) : null}
      {pass?.warming ? (
        <div className="cm-note" data-testid="gg-warming">
          {pass.warming_text || 'warming · no pass this session yet'}
        </div>
      ) : null}
      {scanning && scanningLine ? (
        <div className="cm-note gg-scanning" role="status" data-testid="gg-scanning">{scanningLine}</div>
      ) : null}
      {!scanning && reusedText ? (
        <div className="cm-note" role="status" data-testid="gg-scan-reused">{reusedText}</div>
      ) : null}
      {scanResp?.state === 'refused' && scanResp.text ? (
        <div className="cm-note cm-note-err" data-testid="gg-scan-refused">{scanResp.text}</div>
      ) : null}
      {scan?.note ? <div className="cm-note" data-testid="gg-scan-note">{scan.note}</div> : null}
      {board?.push?.text ? <div className="cm-note" data-testid="gg-push">{board.push.text}</div> : null}
      {board?.push_potential?.text ? (
        <div className="cm-note gg-push-potential" data-testid="gg-push-potential">{board.push_potential.text}</div>
      ) : null}

      {/* (2) ⏳ his first 15 minutes (S8 14:41). */}
      {session?.first15 && session.first15_text ? (
        <div className="gg-first15" data-testid="gg-first15">{session.first15_text}</div>
      ) : null}

      {/* (3) the sub strip — the Catalysts markup. */}
      <div className="cat-tabs gg-subs" role="tablist" aria-label="Gajjala setups">
        {subs.map((s) => (
          <button key={s.key} type="button" role="tab" aria-selected={s.key === activeSub}
                  data-testid={`gg-sub-${s.key}`}
                  className={`cat-tab${s.key === activeSub ? ' is-active' : ''}`}
                  onClick={() => pickSub(s.key)}>
            {`${s.emoji} ${s.label}`}{typeof s.count === 'number' ? ` · ${s.count}` : ''}
          </button>
        ))}
      </div>
      {/* (3a) 🎾 the served ordering word (tab.RS_ORDER_TEXT, squeeze sub only; DECISIONS13 D3) — verbatim, no sort control. */}
      {typeof board?.order_note === 'string' && board.order_note.trim() ? (
        <span className="gg-muted" data-testid="gg-order-note">{board.order_note}</span>
      ) : null}

      {/* (3b) 🎯 the served A+ line — every sub, so on 🧠 Potential it leads the 📈 Track. */}
      {board?.enterable ? <AplusBanner block={board.enterable} /> : null}

      {err ? <div className="cm-note cm-note-err" data-testid="gg-error">Gajjala board: {err}</div> : null}

      {activeSub === 'playbook' ? (
        <PlaybookPanel pb={board?.playbook ?? null} />
      ) : activeSub === 'track_record' ? (
        <TrackRecordPanel tr={board?.track_record ?? null} emptyNote={board?.empty_note ?? null}
                          onSpan={(k) => setParam(GG_SPAN_PARAM, k)} view={view}
                          onView={(k) => setParam(GG_VIEW_PARAM, k === board?.track_record?.views?.default ? null : k)}
                          cat={cat}
                          onCat={(k) => setParam(GG_CAT_PARAM, k === board?.track_record?.categories?.[0]?.key ? null : k)} />
      ) : board ? (
        <>
          {/* (4) counts + graveyard + setups held by an unanswered number. */}
          <CountsLine board={board} />
          {(board.awaiting || []).map((a) => (
            <div key={`${a.setup}-${a.his_call}`} className="cm-note" data-testid="gg-awaiting">{a.text}</div>
          ))}

          {/* (5) bar size + the ☀️ / 🌙 served sorts. */}
          <div className="cm-phase" role="tablist" aria-label="Bar size">
            {GG_TFS.map((f) => (
              <button key={f} type="button" role="tab" aria-selected={f === servedTf}
                      data-testid={`gg-tf-${f}`}
                      className={`cm-phase-btn${f === servedTf ? ' cm-phase-on' : ''}`}
                      onClick={() => setParam(GG_TF_PARAM, f)}>
                {f}
              </button>
            ))}
            {(board.sorts || []).map((s) => (
              <button key={s.key} type="button" data-testid={`gg-sort-${s.key}`}
                      className={`cm-phase-btn${s.key === board.sort ? ' cm-phase-on' : ''}`}
                      onClick={() => setParam(GG_SORT_PARAM, s.key)}>
                {s.label}
              </button>
            ))}
          </div>
          {/* (5b) 🧠 this setup's own potentials — setup subs only; nothing on an older API. */}
          {isGgSetup(activeSub) && board.potential ? (
            <PotentialStrip strip={board.potential} onPick={(sym) => setParam(FOCUS_PARAM, sym)} />
          ) : null}
          {board.postmarket?.unchecked_text ? (
            <div className="cm-note" data-testid="gg-unchecked">{board.postmarket.unchecked_text}</div>
          ) : null}
          {board.postmarket?.recap?.rows?.length ? (
            <div className="gg-recap" data-testid="gg-recap">
              {board.postmarket.recap.title ? <strong>{board.postmarket.recap.title}</strong> : null}
              <ul>
                {board.postmarket.recap.rows.map((r) => {
                  const href = ggHref(r.href);
                  const id = `${r.symbol}-${r.setup ?? ''}`;
                  return (
                    <li key={`${r.symbol}-${r.text}`} data-testid={`gg-recap-row-${id}`}>
                      {href ? <Link to={href} className="gg-recap-link"><strong>{r.symbol}</strong> {r.text}</Link>
                            : <><strong>{r.symbol}</strong> {r.text}</>}
                      <GgBrokerChip text={r.broker_text} testid={`gg-broker-recap-${id}`} />
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}

          {/* (6) the tiles, in the SERVED order. */}
          {!tiles.length && board.empty_note ? (
            <div className="cm-note" data-testid="gg-empty">{board.empty_note}</div>
          ) : null}
          <div className={`cm-grid${loading ? ' cm-grid-stale' : ''}`} aria-busy={loading || undefined}>
            {tiles.map((t) => {
              const row = room.map.get(t.symbol);
              const isFocus = focus === t.symbol;
              return (
                <div key={t.symbol} data-testid={`gg-tile-${t.symbol}`}
                     className={`gg-card${isFocus ? ' gg-focus' : ''}`}
                     ref={(el) => { if (el) tileRefs.current.set(t.symbol, el); else tileRefs.current.delete(t.symbol); }}>
                  <div className="cm-tile-chips" data-testid={`gg-chips-${t.symbol}`}>
                    <GrowthChip symbol={t.symbol} />
                    {' '}<ShortInterestChip symbol={t.symbol} />
                    {' '}<ExplosiveChip read={row?.explosive} study={room.payload?.explosive_study} />
                    {' '}<EnterableChip read={row?.enterable} />
                    <GgBrokerChip text={t.broker_text} testid={`gg-broker-tile-${t.symbol}`} />
                    {/* The frame this card drew, when it is not the bar size the toggle shows (a ➖ Fade read
                        that fell back to 5-minute bars) — the served per-tile `tf`, never a guess. */}
                    {frameDiffers(t.tf, servedTf) ? (
                      <>{' '}<span className="cm-badge cm-badge-muted" data-testid={`gg-frame-${t.symbol}`}
                                   title={`this card is drawn on ${tfWords(t.tf as GgTf)} bars, not the ${tfWords(servedTf)} bars the toggle shows`}>
                        {`${tfWords(t.tf as GgTf)} read`}
                      </span></>
                    ) : null}
                  </div>
                  {t.bars?.length ? (
                    <PatternChart tile={t}
                                  outerChips={outerChipsFor(GG_OUTER_CHIPS, t, {
                                    enterable: row?.enterable,
                                    explosive: row?.explosive,
                                    outerStudy: room.payload?.explosive_study,
                                    tileStudy: null,
                                  })} />
                  ) : (
                    <div className="gg-row-head">
                      {ggHref(t.href) ? (
                        <Link to={withSource(ggHref(t.href)!, 'chart-maps', location.search)}
                              state={{ from: backTarget, label: 'Chart Maps' }}
                              data-testid={`gg-tile-link-${t.symbol}`}>{t.symbol}</Link>
                      ) : <strong>{t.symbol}</strong>}
                      {t.name ? ` ${t.name}` : ''}
                    </div>
                  )}
                  <CardExtras read={t.gajjala ?? null} board={board} sub={activeSub} />
                  {brokerEditable && brokerBlock ? (
                    <BrokerToggle sym={t.symbol} on={typeof t.broker_text === 'string' && t.broker_text.trim() !== ''}
                                  block={brokerBlock} busy={brokerBusy} onWrite={brokerWrite} />
                  ) : null}
                </div>
              );
            })}
          </div>
          {/* (6b) 🧠 sub: the 📈 Track and the 👀 watch line BELOW the live tiles — Ajay 2026-10-18, on a screenshot of
              this sub ("this view is confusing are there 2 potential here?" → "Oh I think we should bring them to the top
              of the view"): the 2 live potentials are what the sub is named for; the 74-row history came first and hid them. */}
          {activeSub === 'potential' && board.track ? <TrackPanel track={board.track} /> : null}
          {activeSub === 'potential' && board.watch ? <WatchLine watch={board.watch} /> : null}
        </>
      ) : null}

      {/* (7) the ℹ️ rules and the served UNMEASURED note. */}
      <div className="cm-rules">
        <RulesInfo section={board?.rules_section || 'gajjala'} />
      </div>
      {board?.note ? <div className="cm-note" data-testid="gg-note">{board.note}</div> : null}
    </div>
  );
}

/** '5m' → '5-min'. */
const tfWords = (f: GgTf | string) => String(f).replace(/m$/, '-min');
/** A served tile frame that is a real bar size and not the board's. */
const frameDiffers = (tileTf: unknown, boardTf: string): boolean =>
  typeof tileTf === 'string' && (GG_TFS as ReadonlyArray<string>).includes(tileTf) && tileTf !== boardTf;

function CountsLine({ board }: { board: GgBoard }) {
  const c = board.counts || {};
  const line = board.counts_text
    || COUNT_WORDS.filter(([k]) => typeof (c as Record<string, unknown>)[k] === 'number')
      .map(([k, w]) => `${w} ${(c as Record<string, number>)[k]}`).join(' · ');
  const grave = board.graveyard_today || [];
  return (
    <>
      {line ? <div className="cm-foot" data-testid="gg-counts">{line}</div> : null}
      {grave.length ? (
        <div className="cm-note" data-testid="gg-graveyard">
          {board.graveyard_text || `\u{1FAA6} moved to the graveyard today: ${grave.join(', ')}`}
        </div>
      ) : null}
      {grave.length && typeof board.graveyard_broker_text === 'string' && board.graveyard_broker_text.trim() ? (
        <div className="cm-note" data-testid="gg-graveyard-broker">{board.graveyard_broker_text}</div>
      ) : null}
    </>
  );
}

/** 🎯 the served A+ line (2026-10-15): the served title, one link per served row (its served text, its served
 *  in-app href), else the served quiet line; the served note folded. Reads ONLY `block` — never the S&D room map or
 *  its chip (C8). The FE filters no row by rule and composes no word. */
function AplusBanner({ block }: { block: GgEnterable }) {
  const rows = (block.rows || []).filter((r) => r && typeof r.symbol === 'string' && r.symbol && typeof r.text === 'string');
  return (
    <div className="gg-aplus" data-testid="gg-aplus" role="status">
      {rows.length ? (
        <>
          {block.title ? <span className="gg-aplus-title" data-testid="gg-aplus-title">{block.title}</span> : null}
          {rows.map((r) => {
            const id = `${r.symbol}-${r.setup}`;
            const href = ggHref(r.href);
            return (
              <Fragment key={id}>
                {href
                  ? <Link to={href} className="gg-aplus-row" data-testid={`gg-aplus-row-${id}`}>{r.text}</Link>
                  : <span className="gg-aplus-row" data-testid={`gg-aplus-row-${id}`}>{r.text}</span>}
                <GgBrokerChip text={r.broker_text} testid={`gg-broker-aplus-${id}`} />
              </Fragment>
            );
          })}
        </>
      ) : block.empty_text ? <span className="gg-aplus-empty" data-testid="gg-aplus-empty">{block.empty_text}</span> : null}
      {block.note ? (
        <details className="gg-aplus-note"><summary>ⓘ</summary><span data-testid="gg-aplus-note">{block.note}</span></details>
      ) : null}
    </div>
  );
}

/** State pill, plan line, criteria checklist and the chip row under a tile. */
function CardExtras({ read, board, sub }: { read: GgRead | null; board: GgBoard; sub: GgSub | null }) {
  if (!read) return null;
  const chips = read.chips || {};
  const trig = pxText(read.trigger);
  const stop = pxText(read.stop);
  const risk = riskText(read.risk_pct);
  const variant = variantText(read);
  const grade = gradeText(read);
  const first15 = typeof chips.first15 === 'string' ? chipText(chips.first15)
    : chips.first15 === true ? (board.session?.first15_text || null) : null;
  const vol = typeof chips.volume === 'number' && Number.isFinite(chips.volume) && chips.volume >= 0
    ? `vol ${shortVol(chips.volume)}${chips.vol_src ? ` (${chips.vol_src})` : ''}`
    : typeof chips.volume === 'string' && chips.volume.trim() ? chips.volume : null;
  const listed = read.listed?.text
    || (read.listed && typeof read.listed.day_n === 'number'
      ? `day ${read.listed.day_n}${read.listed.since ? ` · since ${read.listed.since}` : ''}` : null);
  const chipRow: (string | null)[] = [
    chipText(chips.float), chipText(chips.float_suspect), chipText(chips.rotation), chipText(chips.halts),
    ...(chips.psych || []).map(chipText),
    changeText(chips.change_pct), vol, listed,
    sub === 'reversal_squeeze' ? chipText(chips.squeeze_history) : null,
    chipText(chips.red_closes), chipText(chips.stopped_earlier), chipText(chips.read_at), chipText(chips.flag_k),
    chipText(chips.instrument), chipText(chips.session_badge), chipText(chips.outside_rth), first15,
  ];
  const shown = chipRow.filter((x): x is string => !!x);
  const lines = [read.premarket?.text, read.premarket?.carry_text, read.premarket?.off_pm_high_text,
                 read.postmarket?.text, read.postmarket?.checked_text, read.postmarket?.exhaustion_text]
    .filter((x): x is string => typeof x === 'string' && !!x.trim());
  return (
    <div className="gg-extras" data-testid="gg-extras">
      <div className="gg-pills">
        {read.state_label ? (
          <span className={`gg-state gg-state-${read.state}`} data-testid="gg-state">{read.state_label}</span>
        ) : null}
        {variant ? <span className="gg-variant" data-testid="gg-variant">{variant}</span> : null}
        {grade ? <span className="gg-variant" data-testid="gg-grade">{grade}</span> : null}
      </div>
      {trig || stop ? (
        <div className="gg-plan" data-testid="gg-plan">
          {[trig ? `trigger ${trig}` : null, stop ? `stop ${stop}` : null, risk ? `risk ${risk}` : null]
            .filter(Boolean).join(' · ')}
        </div>
      ) : null}
      {read.criteria?.length ? (
        <ul className="gg-criteria" data-testid="gg-criteria">
          {read.criteria.map((c) => (
            <li key={c.key} className={c.ok === true ? 'gg-ok' : c.ok === false ? 'gg-miss' : 'gg-unjudged'}>
              {criteriaText(c)}
            </li>
          ))}
        </ul>
      ) : null}
      {shown.length ? (
        <div className="gg-chip-row" data-testid="gg-chip-row">
          {shown.map((s, i) => <span key={`${i}-${s}`} className="cm-badge cm-badge-muted">{s}</span>)}
        </div>
      ) : null}
      {lines.map((l, i) => <div key={`${i}-${l}`} className="cm-note gg-line">{l}</div>)}
      {read.potential?.text ? (
        <div className="gg-pot-tile" data-testid="gg-pot-tile">
          <span className={`gg-pot-kind gg-pot-kind-${read.potential.kind}`} data-testid="gg-pot-kind">
            {read.potential.text}
          </span>
          <Tells tells={read.potential.tells} />
        </div>
      ) : null}
    </div>
  );
}

/** GG's tells as muted badges, each with his cited words on hover — display only. */
function Tells({ tells }: { tells: GgTell[] | null | undefined }) {
  const shown = (tells || []).filter((t) => t && typeof t.text === 'string' && t.text.trim());
  if (!shown.length) return null;
  return (
    <span className="gg-pot-tells" data-testid="gg-pot-tells">
      {shown.map((t) => (
        <span key={`${t.key}-${t.text}`} className="cm-badge cm-badge-muted" data-tell={t.key}
              title={t.cite || undefined}>{t.text}</span>
      ))}
    </span>
  );
}

/** 🧠 a setup sub's strip: the served title, the served definition folded, one
 *  row per served potential in the SERVED order. A row click writes `focus`. */
function PotentialStrip({ strip, onPick }: { strip: GgPotentialStrip; onPick: (sym: string) => void }) {
  const rows = (strip.rows || []).filter((r) => r && typeof r.symbol === 'string' && r.symbol);
  return (
    <div className="gg-potential" data-testid="gg-potential">
      <details className="gg-pot-head">
        <summary data-testid="gg-potential-title">{strip.title}</summary>
        {strip.text ? <div className="cm-note" data-testid="gg-potential-text">{strip.text}</div> : null}
      </details>
      {rows.length ? (
        <ul className="gg-pot-rows">
          {rows.map((r) => {
            const againTold = (r.tells || []).some((t) => t?.key === 'again');
            return (
              <li key={`${r.symbol}-${r.setup}`}>
                <button type="button" className={`gg-pot-row gg-pot-row-${r.kind}`}
                        data-testid={`gg-potential-row-${r.symbol}`} onClick={() => onPick(r.symbol)}>
                  <span className={`gg-pot-kind gg-pot-kind-${r.kind}`}>{r.text}</span>
                  {/* "↻" only when no served ↻ tell already says it — no chip printed twice. */}
                  {r.again && !againTold ? <span className="gg-pot-again" data-testid="gg-pot-again">↻</span> : null}
                  <Tells tells={r.tells} />
                </button>
                <GgBrokerChip text={r.broker_text} testid={`gg-broker-pot-${r.symbol}-${r.setup}`} />
              </li>
            );
          })}
        </ul>
      ) : strip.empty_text ? (
        <div className="cm-note" data-testid="gg-potential-empty">{strip.empty_text}</div>
      ) : null}
    </div>
  );
}

function TrackRows({ block }: { block: GgTrackBlock }) {
  const rows = (block.rows || []).filter((r): r is GgTrackRow => !!r && typeof r.text === 'string');
  return (
    <>
      <ul className="gg-track-rows">
        {rows.map((r) => {
          const id = `${r.symbol}-${r.setup}`;
          const href = ggHref(r.href);
          const tl = (r.timeline || []).filter((e) => e && typeof e.text === 'string' && e.text.trim());
          return (
            <li key={id} className="gg-track-row" data-testid={`gg-track-row-${id}`}>
              {href ? <Link to={href} className="gg-track-text">{r.text}</Link> : <span className="gg-track-text">{r.text}</span>}
              <GgBrokerChip text={r.broker_text} testid={`gg-broker-track-${id}`} />
              {r.vs_trigger_text ? <span className="gg-muted"> · {r.vs_trigger_text}</span> : null}
              {r.push_text ? <span className="gg-track-push" data-testid={`gg-track-push-${id}`}> · {r.push_text}</span> : null}
              {r.entry_text ? <span className="gg-track-push gg-track-entry" data-testid={`gg-track-entry-${id}`}> · {r.entry_text}</span> : null}
              {tl.length ? (
                <details className="gg-timeline" data-testid={`gg-track-timeline-${id}`}>
                  <summary>timeline</summary>
                  <ol>{tl.map((e, i) => <li key={`${i}-${e.text}`}>{e.text}</li>)}</ol>
                </details>
              ) : null}
            </li>
          );
        })}
      </ul>
      {typeof block.more_n === 'number' && block.more_n > 0 ? (
        <div className="gg-muted" data-testid="gg-track-more">+{block.more_n} more</div>
      ) : null}
    </>
  );
}

/** 📈 Track — today's first sightings open, the session before folded; states
 *  and prices only, as served. UNMEASURED line always last. */
function TrackPanel({ track }: { track: GgTrack }) {
  const today = track.today;
  const yday = track.yesterday;
  const todayRows = today?.rows?.length ? today : null;
  return (
    <section className="gg-track" data-testid="gg-track">
      <details open className="gg-track-block" data-testid="gg-track-today">
        <summary data-testid="gg-track-title">{track.title}</summary>
        {todayRows ? <TrackRows block={todayRows} /> : track.empty_today ? (
          <div className="cm-note" data-testid="gg-track-empty">{track.empty_today}</div>
        ) : null}
      </details>
      {yday ? (
        <details className="gg-track-block" data-testid="gg-track-yesterday">
          <summary>{yday.title || yday.date || ''}</summary>
          {yday.rows?.length ? <TrackRows block={yday} /> : null}
        </details>
      ) : null}
      {track.unmeasured ? <div className="gg-muted" data-testid="gg-track-unmeasured">{track.unmeasured}</div> : null}
    </section>
  );
}

/** 🏁 one served cell: its served text, the served small line under it; `state` / `provisional` are CSS hooks only. */
function TrCell({ cell, testid }: { cell: GgTrCell | null | undefined; testid: string }) {
  if (!cell) return <td data-testid={testid} className="gg-tr-cell" />;
  const sub = typeof cell.sub_text === 'string' && cell.sub_text ? cell.sub_text : null;
  return (
    <td data-testid={testid} className={`gg-tr-cell gg-tr-${cell.state}${cell.provisional ? ' gg-tr-prov' : ''}`}>
      {cell.text}{sub ? <small>{sub}</small> : null}
    </td>
  );
}

/** 🏁 one served row, its cells in the SERVED heads' order. */
/** A served row chip (E1 rang / E4 thin R) prints only when it is a non-empty string — null / absent prints nothing. */
const trChip = (v: unknown): boolean => typeof v === 'string' && v.trim() !== '';

function TrRowCells({ row, head }: { row: GgTrRow; head: string }) {
  switch (head) {
    case 'symbol': {
      const href = ggHref(row.href);
      return (
        <td className="gg-tr-sym">
          {href ? <Link to={href}>{row.symbol}</Link> : row.symbol}
          <GgBrokerChip text={row.broker_text} testid={`gg-tr-broker-${row.key}`} />
        </td>
      );
    }
    case 'setup': return <td>{row.setup_label}</td>;
    case 'at': return <td>{row.at_text}</td>;
    case 'kind': return (
      <td>
        <span className={`gg-tr-kind gg-tr-${row.line}`}>{row.kind_text}</span>
        {trChip(row.replay_text) ? <span className="gg-tr-chip" data-testid={`gg-tr-replay-${row.key}`}>{row.replay_text}</span> : null}
        {trChip(row.rang_text) ? <span className="gg-tr-chip" data-testid={`gg-tr-rang-${row.key}`}>{row.rang_text}</span> : null}
        {trChip(row.thin_text) ? <span className="gg-tr-chip" data-testid={`gg-tr-thin-${row.key}`}>{row.thin_text}</span> : null}
      </td>
    );
    case 'plan': return (
      <td className="gg-tr-plan">
        {row.plan_text}
        {row.note ? <span className="gg-muted" data-testid={`gg-tr-note-${row.key}`}>{row.note}</span> : null}
      </td>
    );
    case 'same': return <TrCell cell={row.same} testid={`gg-tr-same-${row.key}`} />;
    case 'next': return <TrCell cell={row.next} testid={`gg-tr-next-${row.key}`} />;
    default: return <td />;
  }
}

/** 🏁 Track record (2026-10-16) — the served title, the served day picker, the served counts / A+ shadow / 🎯 entries / today
 *  lines, one table per served day (served heads, served rows), the served more / empty lines, the served rule folded
 *  and the served honesty line last. The panel types no word, no number and no percent sign; no tiles, no room POST.
 *  An older API (no `track_record` block) → the served empty note only. */
function TrackRecordPanel({ tr, emptyNote, onSpan, view, onView, cat, onCat }: {
  tr: GgTrackRecord | null; emptyNote: string | null; onSpan: (key: string) => void;
  view: string | null; onView: (key: string) => void; cat: string | null; onCat: (key: string) => void;
}) {
  if (!tr) return emptyNote ? <div className="cm-note" data-testid="gg-tr-empty">{emptyNote}</div> : null;
  const heads = tr.heads || [];
  const tl = ggTimelineOn(tr, view);
  const listDays = ggCatDays(tr.days || [], cat, tr.categories);
  const listCatEmpty = !tl && ggCatOn(cat, tr.categories) && !listDays.length && (tr.days || []).some((d) => !!d.rows?.length);
  return (
    <section className="gg-track-record" data-testid="gg-track-record">
      <h3 className="gg-pb-h" data-testid="gg-tr-title">{tr.title}</h3>
      {tr.spans?.length ? (
        <div className="cm-phase" role="tablist">
          {tr.spans.map((s) => (
            <button key={s.key} type="button" role="tab" aria-selected={s.key === tr.span}
                    data-testid={`gg-tr-span-${s.key}`}
                    className={`cm-phase-btn${s.key === tr.span ? ' cm-phase-on' : ''}`}
                    onClick={() => onSpan(s.key)}>
              {s.label}
            </button>
          ))}
        </div>
      ) : null}
      <GgTrViews views={tr.views} on={tl} onView={onView} />
      <GgTrCats cats={tl ? tr.categories_timeline : tr.categories} cat={cat} onCat={onCat} />
      {!tl && tr.counts_text?.same ? <div className="cm-foot" data-testid="gg-tr-counts-same">{tr.counts_text.same}</div> : null}
      {!tl && tr.counts_text?.next ? <div className="cm-foot" data-testid="gg-tr-counts-next">{tr.counts_text.next}</div> : null}
      {tr.shadow_text ? <div className="gg-muted gg-tr-shadow-line" data-testid="gg-tr-shadow">{tr.shadow_text}</div> : null}
      {tr.entries_text ? <div className="gg-muted gg-tr-shadow-line" data-testid="gg-tr-entries">{tr.entries_text}</div> : null}
      {tr.replayed_text ? <div className="gg-muted gg-tr-shadow-line" data-testid="gg-tr-replayed">{tr.replayed_text}</div> : null}
      {tr.replayed_note ? <div className="gg-muted" data-testid="gg-tr-replayed-note">{tr.replayed_note}</div> : null}
      {tr.today_text ? <div className="cm-note" data-testid="gg-tr-today">{tr.today_text}</div> : null}
      {listCatEmpty ? <div className="cm-note" data-testid="gg-tr-cat-empty">{tr.category_empty_text}</div> : null}
      {tl ? <GgEntryTimeline tr={tr} cat={cat} /> : listDays.map((d) => (
        <div key={d.date} className="gg-tr-day">
          <h4 className="gg-pb-h" data-testid={`gg-tr-day-${d.date}`}>{d.label}</h4>
          <div className="gg-tr-scroll">
            <table className="gg-tr-table">
              <thead><tr>{heads.map((h) => <th key={h.key}>{h.label}</th>)}</tr></thead>
              <tbody>
                {(d.rows || []).map((r) => (
                  <Fragment key={r.key}>
                    <tr data-testid={`gg-tr-row-${r.key}`}>
                      {heads.map((h) => <TrRowCells key={h.key} row={r} head={h.key} />)}
                    </tr>
                    <GgTrLossLine row={r} heads={heads} />
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      {tr.more_text ? <div className="gg-muted" data-testid="gg-tr-more">{tr.more_text}</div> : null}
      {tr.empty_text ? <div className="cm-note" data-testid="gg-tr-empty">{tr.empty_text}</div> : null}
      {tr.rule_text ? (
        <details className="gg-tr-rule" data-testid="gg-tr-rule">
          {tr.rule_label ? <summary>{tr.rule_label}</summary> : null}
          {tr.rule_text}
        </details>
      ) : null}
      {tr.honesty ? <div className="gg-muted" data-testid="gg-tr-honesty">{tr.honesty}</div> : null}
    </section>
  );
}

/** 🕰️ the served view toggle (DECISIONS11 D3): one house phase button per served item, its served label; the
 *  selected one is the timeline when it is on, else the served default. An older API (no views) draws nothing. */
function GgTrViews({ views, on, onView }: {
  views: GgTrViewsBlock | null | undefined; on: boolean; onView: (key: string) => void;
}) {
  const items = (views?.items || []).filter((i) => i && typeof i.key === 'string' && i.key && typeof i.label === 'string');
  if (!views || !items.length) return null;
  const sel = on ? GG_VIEW_TIMELINE : views.default;
  return (
    <div className="cm-phase gg-tr-views" role="tablist" data-testid="gg-tr-views">
      {items.map((i) => (
        <button key={i.key} type="button" role="tab" aria-selected={i.key === sel}
                data-testid={`gg-tr-view-${i.key}`}
                className={`cm-phase-btn${i.key === sel ? ' cm-phase-on' : ''}`}
                onClick={() => onView(i.key)}>
          {i.label}
        </button>
      ))}
    </div>
  );
}

/** ✅ / ❌ the served category chips (DECISIONS11 D11): one house phase button per served chip, its served text (the
 *  ROW count inside it — never composed here); the selected one is `cat` when it is a served key other than the first,
 *  else the first (ledger.CATEGORY_KEYS[0]). A click filters client-side — no GET. No served chips → nothing. */
function GgTrCats({ cats, cat, onCat }: {
  cats: GgTrCategory[] | null | undefined; cat: string | null; onCat: (key: string) => void;
}) {
  const items = (cats || []).filter((c) => c && typeof c.key === 'string' && c.key && typeof c.text === 'string' && c.text);
  if (!items.length) return null;
  const sel = ggCatOn(cat, items) ? cat : items[0].key;
  return (
    <div className="cm-phase gg-tr-cats" role="tablist" data-testid="gg-tr-cats">
      {items.map((c) => (
        <button key={c.key} type="button" role="tab" aria-selected={c.key === sel}
                data-testid={`gg-tr-cat-${c.key}`}
                className={`cm-phase-btn${c.key === sel ? ' cm-phase-on' : ''}`}
                onClick={() => onCat(c.key)}>
          {c.text}
        </button>
      ))}
    </div>
  );
}

/** ❌ a row's served loss facts (ledger.loss_text, DECISIONS11 D12) as a sub-line row under it — the served string
 *  only; nothing when the row serves none (every non-loss row). `tape` = the 🕰️ table (one more column). */
function GgTrLossLine({ row, heads, tape = false }: {
  row: GgTrRow; heads: { key: string; label: string }[]; tape?: boolean;
}) {
  if (typeof row.loss_text !== 'string' || !row.loss_text.trim()) return null;
  return (
    <tr className="gg-tr-sub">
      <td colSpan={heads.length + (tape ? 1 : 0)} data-testid={`gg-tr-loss-${row.key}`}>{row.loss_text}</td>
    </tr>
  );
}

/** 🕰️ the entries timeline (DECISIONS11 D3): per served day, only the rows whose kind is in the served
 *  `views.kinds`, in the SERVED order (days newest first, the panel's own grouping); a day without one is skipped;
 *  none at all → the served empty line. One table per day: the served heads + the served Tape head; each row = the
 *  🏁 cells + a lazy mini tape and a 📈 toggle that opens the full tape under the row (the Promo table's pattern). */
function GgEntryTimeline({ tr, cat }: { tr: GgTrackRecord; cat: string | null }) {
  const views = tr.views;
  if (!views) return null;
  const kinds = views.kinds || [];
  const heads = tr.heads || [];
  const listed: GgTrDay[] = (tr.days || [])
    .map((d) => ({ ...d, rows: (d.rows || []).filter((r) => !!r && kinds.includes(r.kind)) }))
    .filter((d) => d.rows.length > 0);
  if (!listed.length) return <div className="cm-note" data-testid="gg-tl-empty">{views.empty_text}</div>;
  /* ✅ / ❌ the same client-side filter as the list view, over the timeline's own served chips. */
  const days = ggCatDays(listed, cat, tr.categories_timeline).map((d) => ({ d, rows: d.rows }));
  if (!days.length) return <div className="cm-note" data-testid="gg-tr-cat-empty">{tr.category_empty_text}</div>;
  return (
    <div className="gg-tl" data-testid="gg-tl">
      {days.map(({ d, rows }) => (
        <div key={d.date} className="gg-tr-day">
          <h4 className="gg-pb-h" data-testid={`gg-tl-day-${d.date}`}>{d.label}</h4>
          <div className="gg-tr-scroll">
            <table className="gg-tr-table gg-tl-table">
              <thead><tr>{heads.map((h) => <th key={h.key}>{h.label}</th>)}<th>{views.tape_head}</th></tr></thead>
              <tbody>
                {rows.map((r) => <GgEntryTimelineRow key={r.key} row={r} heads={heads} views={views} />)}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

/** 🕰️ one timeline row: the 🏁 cells (TrRowCells), the mini tape cell, and — when 📈 is open — the full tape row. */
function GgEntryTimelineRow({ row, heads, views }: {
  row: GgTrRow; heads: { key: string; label: string }[]; views: GgTrViewsBlock;
}) {
  const [open, setOpen] = useState(false);
  const toggle = () => setOpen((o) => !o);
  return (
    <Fragment>
      <tr data-testid={`gg-tl-row-${row.key}`}>
        {heads.map((h) => <TrRowCells key={h.key} row={row} head={h.key} />)}
        <td className="ptt__mini-cell">
          {row.id ? (
            <>
              <GgEntryMiniTape id={row.id} onOpen={toggle} width={100} />
              <button type="button" className={`ptt__toggle${open ? ' is-on' : ''}`}
                      data-testid={`gg-tl-open-${row.key}`} aria-expanded={open}
                      title={views.tape_toggle_title} onClick={toggle}>{views.tape_toggle}</button>
            </>
          ) : null}
        </td>
      </tr>
      {open && row.id ? (
        <tr className="ptt__row" data-testid={`gg-tl-tape-${row.key}`}>
          <td colSpan={heads.length + 1}><GgEntryTape id={row.id} /></td>
        </tr>
      ) : null}
      {/* D12 — the loser's facts under its tape (after the expanded tape row when it is open). */}
      <GgTrLossLine row={row} heads={heads} tape />
    </Fragment>
  );
}

/** 👀 the served watch line; its served names become in-tab links. */
function WatchLine({ watch }: { watch: GgWatch }) {
  const parts = watchParts(watch);
  if (!parts) return null;
  const links = (watch.symbols || []).filter((s) => s && typeof s.symbol === 'string' && ggHref(s.href));
  return (
    <div className="gg-watch" data-testid="gg-watch">
      {parts.lead}{!parts.trailing && links.length ? ' ' : ''}
      {links.map((s, i) => (
        <span key={s.symbol}>
          {i ? ', ' : ''}
          <Link to={ggHref(s.href)!} data-testid={`gg-watch-tk-${s.symbol}`}>{s.symbol}</Link>
          <GgBrokerChip text={s.broker_text} testid={`gg-broker-watch-${s.symbol}`} />
        </span>
      ))}
    </div>
  );
}

/* ---- 🚫 broker tag (2026-10-17, BUILD_SPEC12 §3.9, AMENDMENTS12 F2 / F5) — every word SERVED by tab.py; the JSX text
 * below is whitespace or the ✕ glyph only (contracts check 7). A TAG: nothing hides, filters or mutes a row. ---- */

/** 🚫 the served tag beside a symbol — nothing unless the server sent a non-empty string. */
function GgBrokerChip({ text, testid }: { text: unknown; testid: string }) {
  if (typeof text !== 'string' || !text.trim()) return null;
  return <span className="cm-badge cm-badge-muted gg-broker" data-testid={testid}>{text}</span>;
}

/** 🚫 the owner's strip (one line): the served words, his names each with ✕ (DELETE), one add field (POST) — or, when
 *  his list could not be read, the served fault line in place of the add box and no ✕ (F5). */
function BrokerFlagsStrip({ block, editable, fault, busy, err, onWrite }: {
  block: GgBrokerFlags; editable: boolean; fault: string | null; busy: boolean; err: string | null;
  onWrite: (method: 'POST' | 'DELETE', sym: string) => Promise<boolean>;
}) {
  const [value, setValue] = useState('');
  const syms = (block.symbols || []).filter((s): s is string => typeof s === 'string' && !!s);
  const canEdit = editable && !fault;
  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const sym = value.trim();
    if (!sym || busy) return;
    void onWrite('POST', sym).then((ok) => { if (ok) setValue(''); });
  };
  return (
    <div className="gg-broker-strip" data-testid="gg-broker-strip">
      {block.text ? <span className="gg-broker-text" data-testid="gg-broker-text">{block.text}</span> : null}
      {syms.map((s) => (
        <span key={s} className="cm-badge cm-badge-muted gg-broker-sym" data-testid={`gg-broker-sym-${s}`}>
          {s}
          {canEdit ? (
            <button type="button" data-testid={`gg-broker-del-${s}`} title={block.remove_title} aria-label={block.remove_title}
                    disabled={busy} onClick={() => void onWrite('DELETE', s)}>✕</button>
          ) : null}
        </span>
      ))}
      {fault ? <span className="cm-note cm-note-err" data-testid="gg-broker-fault">{fault}</span>
        : !syms.length && block.empty_text ? <span className="gg-muted" data-testid="gg-broker-empty">{block.empty_text}</span> : null}
      {canEdit ? (
        <form className="gg-broker-form" onSubmit={onSubmit}>
          <input type="text" data-testid="gg-broker-input" value={value} disabled={busy}
                 placeholder={block.add_placeholder} aria-label={block.add_placeholder}
                 onChange={(e) => setValue(e.target.value)} />
          <button type="submit" data-testid="gg-broker-add" disabled={busy}>{block.add_label}</button>
        </form>
      ) : null}
      {err ? <span className="cm-note cm-note-err" data-testid="gg-broker-err">{err}</span> : null}
    </div>
  );
}

/** 🚫 the owner's icon-only card toggle: its title / label = the served words; pressed when the name is on his list;
 *  a click removes it (DELETE) when on, else adds it (POST). */
/* `on` is the SERVED tile tag (tab.broker_text_for — it folds "." / "-", AMENDMENTS12 F8); the FE never re-derives
 * membership from the list, so a card can never contradict its own chip (critic 2026-10-17). */
function BrokerToggle({ sym, on, block, busy, onWrite }: {
  sym: string; on: boolean; block: GgBrokerFlags; busy: boolean;
  onWrite: (method: 'POST' | 'DELETE', sym: string) => Promise<boolean>;
}) {
  return (
    <button type="button" className="gg-broker-toggle" data-testid={`gg-broker-toggle-${sym}`} aria-pressed={on}
            title={block.text} aria-label={block.text} disabled={busy}
            onClick={() => void onWrite(on ? 'DELETE' : 'POST', sym)}>
      {block.toggle}
    </button>
  );
}

function PbList({ items, testid }: { items: GgPlaybookItem[] | undefined; testid: string }) {
  if (!items?.length) return null;
  return (
    <ul className="gg-pb-items" data-testid={testid}>
      {items.map((it, i) => {
        const p = playbookItem(it);
        return (
          <li key={`${i}-${p.text.slice(0, 24)}`}>
            {p.pill ? <span className="gg-pb-pill" data-testid="gg-pb-pill">{p.pill}</span> : null}
            <span className="gg-pb-text">{p.text}</span>
            {p.tag ? <span className="gg-pb-ts">{p.tag}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}

/** 📓 his Playbook — served quotes with timestamps, his avoids, the
 *  discretionary management (never computed), the knobs and the sources.
 *  No tiles and no bar fetch on this sub. */
function PlaybookPanel({ pb }: { pb: GgPlaybook | null }) {
  if (!pb) return null;
  return (
    <div className="gg-playbook" data-testid="gg-playbook">
      {pb.title ? <h3 className="gg-pb-h">{pb.title}</h3> : null}
      {pb.note ? <div className="cm-note">{pb.note}</div> : null}
      {(pb.sections || []).map((s) => (
        <section key={s.title} className="gg-pb-section">
          <h4 className="gg-pb-h">{s.title}</h4>
          <PbList items={s.items} testid="gg-pb-section" />
        </section>
      ))}
      {pb.management?.length ? (
        <section className="gg-pb-section"><h4 className="gg-pb-h">Management</h4>
          <PbList items={pb.management} testid="gg-pb-management" /></section>
      ) : null}
      {pb.avoids?.length ? (
        <section className="gg-pb-section"><h4 className="gg-pb-h">What he avoids</h4>
          <PbList items={pb.avoids} testid="gg-pb-avoids" /></section>
      ) : null}
      {pb.contradicted?.length ? (
        <section className="gg-pb-section"><h4 className="gg-pb-h">Contradicted / not used</h4>
          <PbList items={pb.contradicted} testid="gg-pb-contradicted" /></section>
      ) : null}
      {pb.knobs?.length ? (
        <section className="gg-pb-section"><h4 className="gg-pb-h">Knobs</h4>
          <ul className="gg-pb-items" data-testid="gg-pb-knobs">
            {pb.knobs.map((k) => (
              <li key={k.key}>
                <strong>{k.key}</strong>{k.text ? ` ${k.text}` : ''}
                {k.value != null && String(k.value).trim() ? ` — ${k.value}` : ''}
                {k.provenance ? <span className="gg-pb-ts">{k.provenance}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {pb.sources?.length ? (
        <section className="gg-pb-section"><h4 className="gg-pb-h">Sources</h4>
          <table className="gg-pb-sources" data-testid="gg-pb-sources">
            <tbody>
              {pb.sources.map((s) => (
                <tr key={s.url} data-testid="gg-pb-source">
                  <td>{s.key || ''}</td>
                  <td>{s.kind || (s.first_hand ? 'first-hand' : 'third-party')}</td>
                  <td>{s.date || ''}</td>
                  <td>
                    <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a>
                    {s.note ? <span className="gg-muted"> {s.note}</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}
