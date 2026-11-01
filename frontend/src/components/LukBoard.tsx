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
 * (aria labels, "ⓘ", the loading / error glyphs). Every alert is recorded in shadow, never sent. UNMEASURED. */
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { FOCUS_PARAM, parseFocus } from '../lib/growthArrivals';
import {
  LUK_BASE, LUK_PLAYBOOK_SUB, LUK_SPAN_PARAM, LUK_SUB_PARAM, LUK_TRACK_SUB,
  lukHref, lukLegendRows, lukQuery, lukRefreshMs, lukText, parseLukSub, type LukBoard as LukBoardPayload,
} from '../lib/luk';
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

export default function LukBoard() {
  const [params] = useSearchParams();
  const urlSub = parseLukSub(params.get(LUK_SUB_PARAM));
  const span = (params.get(LUK_SPAN_PARAM) || '').trim() || null;
  const focus = parseFocus(params.get(FOCUS_PARAM));
  const reqKey = lukQuery({ sub: urlSub, span, focus });

  const [board, setBoard] = useState<LukBoardPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    fetch(`${API}${LUK_BASE}${reqKey ? `?${reqKey}` : ''}`, { credentials: 'include', cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return (await r.json()) as LukBoardPayload;
      })
      .then((b) => { if (alive) { setBoard(b); setErr(null); } })
      .catch((e) => { if (alive) setErr(String(e?.message ?? e)); });
    return () => { alive = false; };
  }, [reqKey, tick]);

  const every = lukRefreshMs(board);
  useEffect(() => {
    const id = window.setInterval(() => setTick((n) => n + 1), every);
    return () => window.clearInterval(id);
  }, [every]);

  const sub = lukText(board?.sub) ?? urlSub;
  const subs = board?.subs ?? [];
  const legend = lukLegendRows(board?.counts_legend);
  const tiles = board?.tiles ?? [];
  const screen = board?.screens && board.screens.key === sub ? board.screens : null;
  const pass = board?.pass ?? null;
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
