/* GajjalaBoard — 🚩 Gajjala's tab on Chart Maps (2026-10-13).
 *
 * Ajay: "Now can you build a new tab and build sub tabs for it with multiple
 * strategies. Name the Tab Gajjala's he has multiple strategies..around this.
 * He is volume and price action based traded with short squeeze. He also has
 * premarket and post market analysis." … "Implement his full stategy do not
 * assume anything."
 *
 * Goverdhan Gajjala's five 5-minute setups over HIS scanner on the whole US
 * market, plus ☀️ Premarket, 🌙 Post-market and 📓 his Playbook — eight sub
 * tabs, one endpoint (GET /chart-maps/gajjala). The cron pass scans, reads and
 * stores; the endpoint reads Mongo and ORDERS; this file draws. Every sentence
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
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { PatternChart } from './PatternChart';
import { GrowthChip } from './GrowthChip';
import { ShortInterestChip } from './ShortInterestChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import { RulesInfo } from './RulesInfo';
import { useBounceRoom } from '../hooks/useBounceRoom';
import { outerChipsFor } from '../lib/outerChips';
import { FOCUS_PARAM, parseFocus } from '../lib/growthArrivals';
import { trackFeature } from '../lib/usageTracker';
import { pxText, shortVol } from '../lib/chartMaps';
import {
  GG_OUTER_CHIPS, GG_SORT_PARAM, GG_SUBS, GG_SUB_PARAM, GG_TFS, GG_TF_PARAM,
  changeText, chipText, criteriaText, gradeText, ggQuery, ggRefreshMs, parseGgSub, parseGgTf,
  playbookItem, riskText, variantText,
  type GgBoard, type GgPlaybook, type GgPlaybookItem, type GgRead, type GgSub, type GgTf, type GgTile,
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
  const urlSub = parseGgSub(params.get(GG_SUB_PARAM));
  const tf = parseGgTf(params.get(GG_TF_PARAM));
  const focus = parseFocus(params.get(FOCUS_PARAM));
  const sort = (params.get(GG_SORT_PARAM) || '').trim() || null;

  const [board, setBoard] = useState<GgBoard | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const seq = useRef(0);
  /* The request the URL write-back below would trigger again: when the server
   * resolves a `focus` deep link to a sub, the URL adopts it with `replace` —
   * the board already in hand IS that sub's board, so no second fetch. */
  const adoptedKey = useRef<string | null>(null);

  const reqKey = ggQuery({ sub: urlSub, tf, focus, sort });

  useEffect(() => {
    if (adoptedKey.current === reqKey) { adoptedKey.current = null; return; }
    adoptedKey.current = null;
    let alive = true;
    const my = ++seq.current;
    setLoading(true);
    fetch(`${API}/chart-maps/gajjala?${reqKey}`, { credentials: 'include', cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return (await r.json()) as GgBoard;
      })
      .then((b) => {
        if (!alive || my !== seq.current) return;
        setBoard(b);
        setErr(null);
        // The SERVED sub is authoritative: an absent `sub` (a `focus` deep
        // link) or an unknown one is written back with `replace`.
        const served = parseGgSub(b?.sub);
        if (served && served !== params.get(GG_SUB_PARAM)) {
          const next = new URLSearchParams(params);
          next.set(GG_SUB_PARAM, served);
          const nextKey = ggQuery({ sub: served, tf, focus, sort });
          if (nextKey !== reqKey) adoptedKey.current = nextKey;
          setParams(next, { replace: true });
        }
      })
      .catch((e) => { if (alive && my === seq.current) setErr(String(e?.message ?? e)); })
      .finally(() => { if (alive && my === seq.current) setLoading(false); });
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

  const activeSub: GgSub | null = parseGgSub(board?.sub) ?? urlSub;
  useEffect(() => {
    if (activeSub) trackFeature(`chart-maps:tab:gajjala:${activeSub}`);
  }, [activeSub]);

  const tiles = useMemo<GgTile[]>(
    () => (activeSub === 'playbook' ? [] : (board?.tiles || [])), [board, activeSub]);
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
  // drops the ☀️ / 🌙 sort, which belongs to the sub it was picked on.
  const pickSub = (s: GgSub) => setParam(GG_SUB_PARAM, s, [GG_SORT_PARAM]);

  const subs = board?.subs?.length ? board.subs : GG_SUBS.map((s) => ({ ...s, count: null }));
  const session = board?.session;
  const pass = board?.pass;
  const strip = board?.strip;
  const servedTf = board?.tf ?? tf ?? '5m';

  return (
    <div className="gg-board" data-no-toggle={NO_TOGGLE_REASON} data-state={board ? 'loaded' : 'loading'}>
      {/* (1) situational-awareness strip — his read of the day (S8 43:39). */}
      <div className="gg-strip" data-testid="gg-strip" role="status">
        {strip?.text ? <span className="gg-strip-text" data-testid="gg-strip-text">{strip.text}</span> : null}
        {session?.badge ? <span className="cm-badge cm-badge-muted" data-testid="gg-session-badge">{session.badge}</span> : null}
        {session?.label ? <span className="gg-muted">{session.label}</span> : null}
        {pass?.as_of_et ? <span className="gg-muted" data-testid="gg-as-of">as of {pass.as_of_et}</span> : null}
      </div>
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
      {board?.push?.text ? <div className="cm-note" data-testid="gg-push">{board.push.text}</div> : null}

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

      {err ? <div className="cm-note cm-note-err" data-testid="gg-error">Gajjala board: {err}</div> : null}

      {activeSub === 'playbook' ? (
        <PlaybookPanel pb={board?.playbook ?? null} />
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
          {board.postmarket?.unchecked_text ? (
            <div className="cm-note" data-testid="gg-unchecked">{board.postmarket.unchecked_text}</div>
          ) : null}
          {board.postmarket?.recap?.rows?.length ? (
            <div className="gg-recap" data-testid="gg-recap">
              {board.postmarket.recap.title ? <strong>{board.postmarket.recap.title}</strong> : null}
              <ul>
                {board.postmarket.recap.rows.map((r) => (
                  <li key={`${r.symbol}-${r.text}`}><strong>{r.symbol}</strong> {r.text}</li>
                ))}
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
                    <div className="gg-row-head"><a href={t.href}>{t.symbol}</a>{t.name ? ` ${t.name}` : ''}</div>
                  )}
                  <CardExtras read={t.gajjala ?? null} board={board} sub={activeSub} />
                </div>
              );
            })}
          </div>
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
    </>
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
    chipText(chips.red_closes), chipText(chips.stopped_earlier), chipText(chips.flag_k),
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
    </div>
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
