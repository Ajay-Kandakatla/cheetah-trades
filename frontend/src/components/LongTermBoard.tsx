/* LongTermBoard — 📅 Long Term tab on Chart Maps (2026-11-12, long-term spec §3.10 / §3.13, WP-FE).
 *
 * Ajay 2026-11-12: "Save this entire list for me. In a New tab - Long Term - Remember this analays criteria I am asking
 * you to for this tab and keep updating it from all the other tabs info.. Weekly and if something gets dropped let me
 * know when to like is Sales drop or Stage 2 to Stage 3 or stage 4 changes." and "Yeah I wanna find out the ones that
 * are actually great in fundamentals and growth and sales and no debt but not growing in price action yet.."
 *
 * ONE read-only GET on mount (GET /chart-maps/long-term, backend long_term_list/api.py) — no polling: the list is
 * re-read once a week by the server. States: `owner_only` → the served reason only (the server sends nothing else);
 * `error` → the served reason; `seed_only` / `ready` → header (title, note, his words, next-run line, per-source as-of
 * lines) → digest → 🧭 zones (the 🔔 block from the served `zones.alert` when present — names in one of Pankaj's zones
 * now, the served reason / stale / push lines and the session's reach log with each row's served push line; otherwise
 * the closed-bar at-zone strip, never both) → 🌱 started moving → ⚠️ changed → the categories (label,
 * criteria, caveat, also line, saved rows, the neutral moved line — never ⚠️ — and the unsaved weekly top strip with ✨
 * on a name new to it) → forward (an inline chart only once the served record is past "too early") → history → rules
 * and caveats. A request that fails prints FETCH_FAILED (the ONE FE sentence).
 *
 * NO ordering toggle and no filter here — his saved list keeps its saved order (rows in seed order, as served). The
 * four house chips (🚀 GrowthChip, 🩳 ShortInterestChip, 🧨 ExplosiveChip, 🎯 EnterableChip) sit on every SAVED row from
 * ONE useBounceRoom call over the saved symbols on screen (the LukBoard pattern); weekly strip rows carry no house chips
 * (the strip is unsaved, spec C6), and an owner-only / error answer asks the room for nothing.
 *
 * The FE composes NO word and NO number about a stock: every visible string is a served field; the only FE-typed glyphs
 * are structural (🌱 / ⚠️ section marks, ✨ on a served `new`, the verdict marks, "·" separators). UNMEASURED. */
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { API } from '../lib/apiBase';
import {
  FETCH_FAILED, LT_CHART, LT_PATH, listOr, ltCategoryRows, ltForwardLines, ltMark, ltSavedSymbols, ltState, ltText,
  ltToken, textOr,
  type LtAny, type LtCategory, type LtPayload, type LtRow, type LtTop, type LtZoneAlert,
} from '../lib/longTerm';
import { TickerLink } from './TickerLink';
import { useBounceRoom } from '../hooks/useBounceRoom';
import { GrowthChip } from './GrowthChip';
import { ShortInterestChip } from './ShortInterestChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import '../styles/longTerm.css';

type Load = { phase: 'loading' } | { phase: 'failed' } | { phase: 'loaded'; p: LtAny };

function Line({ text, testId, className = 'lt-line' }: { text: unknown; testId?: string; className?: string }) {
  const t = ltText(text);
  return t ? <p className={className} data-testid={testId}>{t}</p> : null;
}

function RowCard({ row, houseChips }: { row: LtRow; houseChips: ReactNode }) {
  const chips = listOr(row.chips);
  const fields = listOr(row.fields);
  const events = listOr(row.events);
  const pk = row.pankaj;
  return (
    <article className="lt-card" data-testid={`lt-row-${row.symbol}`} data-status={ltToken(row.status?.key)}>
      <div className="lt-card-head">
        <TickerLink ticker={row.symbol} showWatchlist={false} />
        <span className="lt-muted lt-line">{textOr(row.name)}</span>
        <span className="lt-muted lt-line">{textOr(row.sector)}</span>
      </div>
      {chips.length ? (
        <div className="lt-pills" data-testid={`lt-chips-${row.symbol}`}>
          {chips.map((c) => <span key={c.key} className="lt-pill" data-chip={ltToken(c.key)}>{textOr(c.label)}</span>)}
        </div>
      ) : null}
      <div className="lt-house-chips" data-testid={`lt-house-${row.symbol}`}>{houseChips}</div>
      <p className="lt-line" data-testid={`lt-stage-${row.symbol}`}>{textOr(row.stage?.text)}</p>
      <p className="lt-line" data-testid={`lt-sales-${row.symbol}`}>{textOr(row.sales?.text)}</p>
      {row.status ? (
        <p className={`lt-status lt-status-${ltToken(row.status.key)}`} data-testid={`lt-status-${row.symbol}`}>{textOr(row.status.text)}</p>
      ) : null}
      {fields.length ? (
        <div className="lt-fields">
          {fields.map((f) => (
            <span key={`${f.category}-${f.key}`} className={`lt-field lt-v-${ltToken(f.verdict)} lt-k-${ltToken(f.kind)}`}
                  data-testid={`lt-field-${row.symbol}-${f.category}-${f.key}`}>
              {ltMark(f.verdict)} {textOr(f.label)}: {textOr(f.text)}
            </span>
          ))}
        </div>
      ) : null}
      {pk ? (
        <div className="lt-pankaj" data-testid={`lt-pankaj-${row.symbol}`}>
          <Line text={pk.tier_text} />
          <Line text={pk.zones_text} />
          <Line text={pk.zone_text} />
        </div>
      ) : null}
      {events.length ? (
        <ul className="lt-list">
          {events.map((e, i) => (
            <li key={`${e.kind}-${e.date}-${i}`} className="lt-line" data-testid={`lt-event-${row.symbol}`}>
              {ltText(e.date) ? <span className="lt-muted">{e.date} · </span> : null}{textOr(e.text)}
            </li>
          ))}
        </ul>
      ) : null}
      <Line text={row.caveat_tag} className="lt-line lt-muted" />
    </article>
  );
}

function StripItem({ t }: { t: LtTop }) {
  return (
    <span className="lt-strip-item" data-testid={`lt-top-${t.symbol}`}>
      {t.new === true ? <span data-testid={`lt-new-${t.symbol}`}>{'✨'}</span> : null}
      <TickerLink ticker={t.symbol} showWatchlist={false} />
      {ltText(t.name) ? <span className="lt-muted">{t.name}</span> : null}
      {ltText(t.sector) ? <span className="lt-muted">{t.sector}</span> : null}
      {ltText(t.rank_text) ? <span>{t.rank_text}</span> : null}
    </span>
  );
}

/* 🔔 zones.alert (pkzone spec §3.9): every node is a served string; a served null renders no node. */
function ZoneAlert({ a }: { a: LtZoneAlert }) {
  const now = listOr(a.now);
  const log = listOr(a.log);
  return (
    <div className="lt-alert" data-testid="lt-zone-alert" data-live={a.live === true ? 'true' : 'false'}>
      {ltText(a.title) ? <h3 className="lt-h">{a.title}</h3> : null}
      <Line text={a.as_of_text} testId="lt-zone-alert-asof" className="lt-line lt-muted" />
      {now.length ? (
        <ul className="lt-list">
          {now.map((z) => (
            <li key={`${z.symbol}-${z.zone}`} className="lt-line" data-testid={`lt-zone-now-${z.symbol}`}>
              <TickerLink ticker={z.symbol} showWatchlist={false} title={ltText(z.his_symbol) ?? undefined} />
              {' '}{textOr(z.text)}
            </li>
          ))}
        </ul>
      ) : <Line text={a.empty_text} testId="lt-zone-now-empty" />}
      <Line text={a.reason} testId="lt-zone-alert-reason" />
      <Line text={a.stale_text} testId="lt-zone-alert-stale" />
      <Line text={a.push_text} testId="lt-zone-alert-push" className="lt-line lt-muted" />
      {ltText(a.log_title) ? <h4 className="lt-h" data-testid="lt-zone-log-title">{a.log_title}</h4> : null}
      {log.length ? (
        <ul className="lt-list" data-testid="lt-zone-log">
          {log.map((r) => (
            <li key={`${r.symbol}-${r.zone}`} className="lt-line" data-testid={`lt-zone-log-${r.symbol}-${r.zone}`}>
              {textOr(r.at_text)}{' · '}
              <TickerLink ticker={r.symbol} showWatchlist={false} title={ltText(r.his_symbol) ?? undefined} />
              {' '}{textOr(r.text)}{' · '}<span className="lt-muted">{textOr(r.push_text)}</span>
            </li>
          ))}
        </ul>
      ) : <Line text={a.log_empty_text} testId="lt-zone-log-empty" />}
    </div>
  );
}

export default function LongTermBoard() {
  const [load, setLoad] = useState<Load>({ phase: 'loading' });

  /* ONE GET on mount; no polling (the server re-reads the list weekly). */
  useEffect(() => {
    let alive = true;
    fetch(`${API}${LT_PATH}`, { credentials: 'include', cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j) => {
        if (!alive) return;
        setLoad(ltState(j) ? { phase: 'loaded', p: j as LtAny } : { phase: 'failed' });
      })
      .catch(() => { if (alive) setLoad({ phase: 'failed' }); });
    return () => { alive = false; };
  }, []);

  const state = load.phase === 'loaded' ? ltState(load.p) : null;
  const p: LtPayload | null = state === 'seed_only' || state === 'ready' ? (load as { p: LtPayload }).p : null;
  /* The house chips: ONE room POST over the saved symbols on screen. Owner-only / error / loading → [] (nothing asked). */
  const savedSymbols = useMemo(() => ltSavedSymbols(p), [p]);
  const room = useBounceRoom(savedSymbols);

  const house = (sym: string) => {
    const r = room.map.get(sym.toUpperCase());
    return (
      <>
        <GrowthChip symbol={sym} />
        {' '}<ShortInterestChip symbol={sym} />
        {' '}<ExplosiveChip read={r?.explosive} study={room.payload?.explosive_study} />
        {' '}<EnterableChip read={r?.enterable} />
      </>
    );
  };
  const card = (row: LtRow) => <RowCard key={row.symbol} row={row} houseChips={house(row.symbol)} />;

  if (load.phase === 'loading') {
    return <div className="lt-board" data-state="loading" aria-busy="true"><span className="lt-muted">{'…'}</span></div>;
  }
  if (load.phase === 'failed' || !state) {
    return <div className="lt-board" data-state="failed"><p className="lt-line" data-testid="lt-reason">{FETCH_FAILED}</p></div>;
  }
  if (state === 'owner_only' || state === 'error' || !p) {
    /* owner_only / error: the served reason and nothing else (the server sends nothing else for owner_only). */
    const reason = ltText((load as { p: LtAny }).p.reason);
    return (
      <div className="lt-board" data-state={state}>
        {reason ? <p className="lt-line" data-testid="lt-reason">{reason}</p> : null}
      </div>
    );
  }

  const asOf = p.as_of;
  const digest = p.digest;
  const zones = p.zones;
  const atZone = listOr(zones?.at_zone);
  /* 🔔 present → it replaces the closed-bar strip (heading + at_zone list); absent → the strip renders as before. */
  const alert = zones?.alert && typeof zones.alert === 'object' ? zones.alert : null;
  const started = listOr(p.started_moving);
  const changed = listOr(p.changed);
  const categories = listOr(p.categories);
  const fwd = p.forward;
  const lines = ltForwardLines(fwd);
  const history = listOr(p.history);
  const rules = listOr(p.rules);
  const caveats = listOr(p.caveats);

  return (
    <div className="lt-board" data-state={state}>
      <header className="lt-section" data-testid="lt-header" data-section="header">
        {ltText(p.title) ? <h2 className="lt-title" data-testid="lt-title">{p.title}</h2> : null}
        <Line text={p.note} testId="lt-note" />
        {listOr(p.his_words).length ? (
          <ul className="lt-list" data-testid="lt-his-words">
            {listOr(p.his_words).map((w, i) => <li key={i} className="lt-line">{textOr(w)}</li>)}
          </ul>
        ) : null}
        <Line text={asOf?.next_run_text} testId="lt-next-run" />
        {listOr(asOf?.sources).length ? (
          <ul className="lt-list" data-testid="lt-sources">
            {listOr(asOf?.sources).map((s) => (
              <li key={s.key} className={`lt-line lt-muted${s.ok === false ? ' lt-v-fail' : ''}`}>
                {textOr(s.label)} · {textOr(s.as_of_text)}
              </li>
            ))}
          </ul>
        ) : null}
      </header>

      {digest ? (
        <section className="lt-section" data-testid="lt-digest" data-section="digest">
          {ltText(digest.title) ? <h3 className="lt-h">{digest.title}</h3> : null}
          {listOr(digest.lines).length ? (
            <ul className="lt-list">{listOr(digest.lines).map((l, i) => <li key={i} className="lt-line">{textOr(l)}</li>)}</ul>
          ) : null}
          <Line text={digest.pushed_text} className="lt-line lt-muted" />
        </section>
      ) : null}

      {zones && (alert || atZone.length || ltText(zones.as_of_text) || ltText(zones.rows_note)) ? (
        <section className="lt-section" data-testid="lt-zones" data-section="zones">
          {alert ? <ZoneAlert a={alert} /> : null}
          {!alert && ltText(zones.as_of_text) ? <h3 className="lt-h">{zones.as_of_text}</h3> : null}
          {!alert && atZone.length ? (
            <ul className="lt-list">
              {atZone.map((z) => (
                <li key={z.symbol} className="lt-line" data-testid={`lt-zone-${z.symbol}`}>
                  <TickerLink ticker={z.symbol} showWatchlist={false} title={ltText(z.his_symbol) ?? undefined} />
                  {' '}{textOr(z.zone_text)}
                </li>
              ))}
            </ul>
          ) : null}
          <Line text={zones.rows_note} className="lt-line lt-muted" />
        </section>
      ) : null}

      {started.length ? (
        <section className="lt-section lt-started" data-testid="lt-started" data-section="started_moving">
          <h3 className="lt-h" aria-hidden="true">{'\u{1F331}'}</h3>
          <ul className="lt-list">
            {started.map((s) => (
              <li key={s.symbol} className="lt-line" data-testid={`lt-started-${s.symbol}`}>
                <TickerLink ticker={s.symbol} showWatchlist={false} />{' '}{textOr(s.text)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {changed.length ? (
        <section className="lt-section lt-changed" data-testid="lt-changed" data-section="changed">
          <h3 className="lt-h" aria-hidden="true">{'⚠️'}</h3>
          <div className="lt-grid">{changed.map(card)}</div>
        </section>
      ) : null}

      {categories.map((c: LtCategory) => {
        const rows = ltCategoryRows(p, c.key);
        const top = listOr(c.top);
        return (
          <section key={c.key} className="lt-section lt-category" data-testid={`lt-cat-${c.key}`} data-section="category">
            <h3 className="lt-h">{textOr(c.label)}</h3>
            <Line text={c.source_tab} className="lt-line lt-muted" />
            <Line text={c.criteria_text} testId={`lt-criteria-${c.key}`} />
            <Line text={c.caveat} testId={`lt-caveat-${c.key}`} className="lt-line lt-muted" />
            <Line text={c.also_text} className="lt-line lt-muted" />
            {rows.length ? <div className="lt-grid">{rows.map(card)}</div> : null}
            <Line text={c.moved_text} testId={`lt-moved-${c.key}`} className="lt-moved" />
            {top.length || ltText(c.top_text) ? (
              <div className="lt-top" data-testid={`lt-strip-${c.key}`}>
                <Line text={c.top_text} className="lt-line lt-muted" />
                {top.length ? <div className="lt-strip">{top.map((t) => <StripItem key={t.symbol} t={t} />)}</div> : null}
              </div>
            ) : null}
          </section>
        );
      })}

      {fwd ? (
        <section className="lt-section" data-testid="lt-forward" data-section="forward">
          <Line text={fwd.line} testId="lt-forward-line" />
          <Line text={fwd.counts_line} className="lt-line lt-muted" />
          {lines.length ? (
            <>
              <svg className="lt-chart" data-testid="lt-chart" viewBox={`0 0 ${LT_CHART.w} ${LT_CHART.h}`} role="img"
                   aria-label={lines.map((l) => l.label).join(' · ')}>
                {lines.map((l, i) => <polyline key={l.key} className={`lt-s-${i}`} points={l.points} data-series={l.key} />)}
              </svg>
              <div className="lt-legend">
                {lines.map((l, i) => <span key={l.key} className={`lt-s-${i}`}>{l.label}</span>)}
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      {history.length ? (
        <section className="lt-section" data-testid="lt-history" data-section="history">
          <ul className="lt-list">
            {history.map((h) => <li key={h.week} className="lt-line">{textOr(h.text)}</li>)}
          </ul>
        </section>
      ) : null}

      {rules.length || caveats.length ? (
        <section className="lt-section" data-testid="lt-rules" data-section="rules">
          {rules.length ? (
            <ul className="lt-list">
              {rules.map((r) => (
                <li key={r.key} className="lt-line" data-testid={`lt-rule-${r.key}`}>
                  {textOr(r.label)}: {textOr(r.text)}{ltText(r.source) ? <span className="lt-muted"> · {r.source}</span> : null}
                </li>
              ))}
            </ul>
          ) : null}
          {caveats.length ? (
            <ul className="lt-list" data-testid="lt-caveats">
              {caveats.map((c, i) => <li key={i} className="lt-line lt-muted">{textOr(c)}</li>)}
            </ul>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
