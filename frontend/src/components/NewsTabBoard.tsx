/* 📰 NewsTabBoard — the News tab on Chart Maps (2026-09-24).
 *
 * Ajay 2026-09-24: "build me a news tab in chartmaps to give me a bullish
 * market or bearsish market and also pull Macro calendar that has T1 and T2
 * tier events in to this tab consider in to news. If bullish or beaish I need
 * to whcih sectors are bullish or which hotsectors are bearish. In a table."
 *
 * ONE fetch, GET /chart-maps/news, FOUR independent blocks. Each block can
 * fail on its own (`ok: false` with a served reason — a leg that ran past the
 * server's budget says "still loading … refresh"), and the rest still draw:
 *
 *   ① Market read — the Market Gauge's daily AND weekly state, the served
 *     word beside the gauge's own label and score, the served watch lines
 *     printed verbatim (never rewritten here).
 *   ② Macro — the T1 market movers + T2 trend shapers of the FRED calendar,
 *     over the calendar's one default window, the next market mover marked.
 *   ③ Sectors vs RSP — the 🔥 Hottest sector rows in SERVED order, the heat
 *     word from rotation.heat, the 📰 day tag (bull AND bear case), the
 *     StockTitan heatmap link. The day column says "today" ONLY when the
 *     served `d1.live` is true; otherwise it is the last close and says so.
 *   ④ Headlines — the app's one news routine, last N hours.
 *
 * Contract exemptions (frontend/scripts/contracts.mjs):
 *   - no ticker rows on this tab — nothing for a growth / explosive / enterable chip to read
 *   - no read on this board to rank by
 *
 * Gates nothing, pushes nothing, sizes nothing. Not advice.
 */
import { Fragment, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { pp, stockTitanHeatmapUrl } from '../lib/rotation';
import { dayTagChipLabel, dayTagTitle } from './HottestSectors';
import {
  SECTOR_VIEWS, agreeLine, benchmarkSymbol, filterRows, heatGlyph, macroWhen, publishedAgo,
  verdictLine, viewLabel, wordTone,
  type NewsTabPayload, type NtMacro, type NtSectors, type NtVerdict, type NtHeadlines,
  type NtWord, type SectorView,
} from '../lib/newsTab';

function Reason({ text, testId }: { text?: string | null; testId: string }) {
  return <p className="nt-reason" data-testid={testId}>{text || 'unavailable'}</p>;
}

function WordCard({ title, v }: { title: string; v: NtWord }) {
  const word = (v.word || '').trim() || 'unknown';
  return (
    <div className="nt-card" data-testid={`nt-card-${title.toLowerCase()}`}>
      <div className="nt-card__title">{title}</div>
      <div className={`nt-word nt-word--${wordTone(word)}`}>{word}</div>
      <div className="nt-card__sub">{verdictLine(v)}</div>
    </div>
  );
}

function MarketRead({ v }: { v?: NtVerdict | null }) {
  if (!v || !v.ok) return <Reason text={v?.reason || 'market gauge unavailable'} testId="nt-verdict-reason" />;
  const agree = agreeLine(v.daily, v.weekly);
  return (
    <>
      <div className="nt-cards">
        {v.daily ? <WordCard title="Daily" v={v.daily} /> : null}
        {v.weekly ? <WordCard title="Weekly" v={v.weekly} /> : null}
      </div>
      {agree ? <p className="nt-agree" data-testid="nt-agree">{agree}</p> : null}
      {(v.drivers || []).length ? (
        <ul className="nt-list nt-drivers">
          {(v.drivers || []).map((d, i) => <li key={i}>{d}</li>)}
        </ul>
      ) : null}
      {(v.outlook?.watch || []).length ? (
        <div className="nt-watch">
          <div className="nt-sub">{v.outlook?.label || 'Watch'}</div>
          <ul className="nt-list">
            {(v.outlook?.watch || []).map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      ) : null}
      {v.as_of_label ? <p className="nt-muted">{v.as_of_label}</p> : null}
      {v.disclaimer ? <p className="nt-muted">{v.disclaimer}</p> : null}
    </>
  );
}

function MacroBlock({ m }: { m?: NtMacro | null }) {
  if (!m || !m.ok) return <Reason text={m?.reason || 'macro calendar unavailable'} testId="nt-macro-reason" />;
  const events = m.events || [];
  const next = m.next_tier1;
  const isNext = (e: { date: string; kind?: string | null; label: string }) =>
    !!next && next.date === e.date && (next.kind ? next.kind === e.kind : next.label === e.label);
  return (
    <>
      {next?.label ? (
        <p className="nt-next" data-testid="nt-next-t1">
          Next market mover: <strong>{next.label}</strong> {macroWhen(next)}
        </p>
      ) : null}
      {events.length === 0 ? (
        <p className="nt-empty" data-testid="nt-macro-empty">
          No T1/T2 releases {m.days != null ? `in the next ${m.days} days` : 'in this window'}
        </p>
      ) : (
        <table className="nt-table">
          <tbody>
            {events.map((e, i) => (
              <tr key={`${e.date}-${e.kind}-${i}`} data-testid={`nt-macro-row-${i}`}
                  className={isNext(e) ? 'is-next' : undefined}>
                <td><span className={`nt-tier nt-tier--${e.tier}`}
                          title={e.tier_label || m.tier_labels?.[String(e.tier)] || ''}>T{e.tier}</span></td>
                <td>{e.label}{isNext(e) ? <span className="nt-next-tag"> · next market mover</span> : null}</td>
                <td className="nt-num">{e.date}</td>
                <td className="nt-muted">{e.when_label || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {m.disclaimer ? <p className="nt-muted">{m.disclaimer}</p> : null}
    </>
  );
}

function LegCell({ v, word }: { v?: number | null; word?: string | null }) {
  const w = (word || '').trim() || 'unknown';
  return (
    <td className={`nt-num nt-word--${wordTone(w)}`}>
      {pp(v)} <span className="nt-leg-word">{w}</span>
    </td>
  );
}

function SectorsBlock({ s }: { s?: NtSectors | null }) {
  const [view, setView] = useState<SectorView>('all');
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const rows = s?.rows || [];
  const shown = useMemo(() => filterRows(rows, view), [rows, view]);
  if (!s || !s.ok) return <Reason text={s?.reason || 'sector table unavailable'} testId="nt-sectors-reason" />;
  const d1 = s.d1;
  const live = d1?.live === true;
  const bench = benchmarkSymbol(s.benchmark);
  const dayHead = `${live ? 'Today' : 'Last close'} vs ${bench}`;
  const heatWindow = s.heat_window || '5d';
  const span = 8;
  const toggle = (sector: string) => setOpen((prev) => {
    const next = new Set(prev);
    if (next.has(sector)) next.delete(sector); else next.add(sector);
    return next;
  });
  return (
    <>
      <div className="nt-chips" role="group" aria-label="Sector view">
        {SECTOR_VIEWS.map((v) => (
          <button key={v} type="button" data-testid={`nt-view-${v}`}
                  className={'nt-chip' + (view === v ? ' is-on' : '')}
                  aria-pressed={view === v} onClick={() => setView(v)}>
            {viewLabel(v, d1)} ({filterRows(rows, v).length})
          </button>
        ))}
      </div>
      {rows.length === 0 ? (
        <p className="nt-empty" data-testid="nt-sectors-empty">No sector rows served.</p>
      ) : (
        <div className="nt-scroll">
          <table className="nt-table nt-sectors">
            <thead>
              <tr>
                <th>Sector</th>
                <th title="rotation.heat — pooled industry / sector / theme scale. UNMEASURED on this window.">
                  heat rank · {heatWindow}
                </th>
                <th data-testid="nt-day-head">{dayHead}</th>
                <th>5d vs {bench}</th>
                <th>21d vs {bench}</th>
                <th>Breadth 1d</th>
                <th>{'\u{1F4F0}'}</th>
                <th>{'\u{1F5FA}️'}</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => {
                const url = stockTitanHeatmapUrl(r.sector);
                const tag = r.day_tag || null;
                const tone = r.heat?.tone || 'unknown';
                const pctl = r.heat?.percentile;
                return (
                  <Fragment key={r.sector}>
                    <tr data-testid={`nt-row-${r.sector}`}>
                      <td className="nt-sector">{r.sector}{r.n != null ? <span className="nt-muted"> · {r.n}</span> : null}</td>
                      <td data-testid={`nt-heat-${r.sector}`}
                          title={`${tone}${pctl != null ? ` · p${Math.round(pctl)}` : ''} on ${heatWindow}${r.heat?.thin ? ' · thin' : ''} — UNMEASURED`}>
                        {heatGlyph(tone)}
                      </td>
                      <LegCell v={r.rel_1d} word={r.read?.['1d']} />
                      <LegCell v={r.rel_5d} word={r.read?.['5d']} />
                      <LegCell v={r.rel_21d} word={r.read?.['21d']} />
                      <td className="nt-num">
                        {r.pct_positive_1d != null && Number.isFinite(r.pct_positive_1d)
                          ? `${Math.round(r.pct_positive_1d)}% up` : '—'}
                      </td>
                      <td>
                        {tag ? (
                          <button type="button" className="nt-daytag" data-testid={`nt-daytag-${r.sector}`}
                                  title={dayTagTitle(tag)} aria-expanded={open.has(r.sector)}
                                  onClick={() => toggle(r.sector)}>
                            {dayTagChipLabel(tag)}
                          </button>
                        ) : null}
                      </td>
                      <td>
                        {url ? (
                          <a href={url} target="_blank" rel="noreferrer" data-testid={`nt-heatmap-${r.sector}`}
                             title="StockTitan heatmap — S&P 500 only, a second view, not the same number">
                            {'\u{1F5FA}️'}
                          </a>
                        ) : null}
                      </td>
                    </tr>
                    {tag && open.has(r.sector) ? (
                      <tr className="nt-daytag-row" data-testid={`nt-daytag-open-${r.sector}`}>
                        <td colSpan={span}>
                          <div className="nt-daytag__meta">
                            <strong>{tag.symbol}</strong>{tag.company ? ` — ${tag.company}` : ''}
                            {' · '}{tag.date}{tag.read_by ? ` · read by ${tag.read_by}` : ''}
                            {' · not measured'}
                          </div>
                          <div className="nt-daytag__cases">
                            <div className="nt-daytag__case">
                              <span className="nt-daytag__lbl">Bull case</span>
                              <p>{tag.bull}</p>
                            </div>
                            <div className="nt-daytag__case">
                              <span className="nt-daytag__lbl">Bear case</span>
                              <p>{tag.bear}</p>
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {!live ? (
        <p className="nt-muted" data-testid="nt-d1-note">
          day column = last close{d1?.as_of ? ` (${d1.as_of})` : ''}{d1?.reason ? ` — ${d1.reason}` : ''}
        </p>
      ) : null}
      <p className="nt-muted">
        <Link to="/chart-maps?tab=hot_sectors">Open the {'\u{1F525}'} Hottest board</Link> for the industries and names.
      </p>
      {s.study?.note ? <p className="nt-study" data-testid="nt-study">{s.study.note}</p> : null}
    </>
  );
}

function HeadlinesBlock({ h }: { h?: NtHeadlines | null }) {
  if (!h || !h.ok) return <Reason text={h?.reason || 'headlines unavailable'} testId="nt-headlines-reason" />;
  const items = h.items || [];
  if (!items.length) {
    return (
      <p className="nt-empty" data-testid="nt-headlines-empty">
        No market headlines{h.window_hours != null ? ` in the last ${h.window_hours}h` : ''}.
      </p>
    );
  }
  return (
    <ul className="nt-list nt-headlines">
      {items.map((it, i) => (
        <li key={it.url || it.title || i}>
          {it.url ? <a href={it.url} target="_blank" rel="noreferrer">{it.title || it.url}</a> : (it.title || '')}
          <span className="nt-muted">
            {it.source ? ` · ${it.source}` : ''}{publishedAgo(it.published) ? ` · ${publishedAgo(it.published)}` : ''}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function NewsTabBoard() {
  const [payload, setPayload] = useState<NewsTabPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setErr(null);
    fetch(`${API}/chart-maps/news`, { credentials: 'include', cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        if (alive) setPayload(d || {});
      })
      .catch((e) => { if (alive) setErr(String(e?.message ?? e)); });
    return () => { alive = false; };
  }, []);

  if (err) return <p className="nt-error" data-testid="nt-error">Could not load the News tab — {err}</p>;
  if (!payload) return <p className="nt-muted" data-testid="nt-loading">Loading the News tab…</p>;

  /* The window in each header is the one the SERVER measured, or none at all.
   * A leg that timed out serves no `days` / `window_hours`, and a typed-in
   * "14" or "36" would print a window nobody read (review 2026-09-24). */
  const days = payload.macro?.days;
  const hours = payload.headlines?.window_hours;
  return (
    <div className="nt-board" data-testid="news-tab-board">
      <section className="nt-section" data-testid="nt-section-verdict">
        <h3 className="nt-head">Market read</h3>
        <MarketRead v={payload.verdict} />
      </section>
      <section className="nt-section" data-testid="nt-section-macro">
        <h3 className="nt-head" data-testid="nt-macro-head">
          {'\u{1F4C5}'} Macro{days != null ? ` · next ${days} days` : ''} · T1 market movers + T2 trend shapers
        </h3>
        <MacroBlock m={payload.macro} />
      </section>
      <section className="nt-section" data-testid="nt-section-sectors">
        <h3 className="nt-head">Sectors vs {benchmarkSymbol(payload.sectors?.benchmark)}</h3>
        <SectorsBlock s={payload.sectors} />
      </section>
      <section className="nt-section" data-testid="nt-section-headlines">
        <h3 className="nt-head" data-testid="nt-headlines-head">
          {'\u{1F4F0}'} Headlines{hours != null ? ` · last ${hours}h` : ''}
        </h3>
        <HeadlinesBlock h={payload.headlines} />
      </section>
      {payload.note ? <p className="nt-muted nt-note">{payload.note}</p> : null}
    </div>
  );
}
