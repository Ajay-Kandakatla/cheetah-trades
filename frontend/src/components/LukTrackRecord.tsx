/* LukTrackRecord — 🥇 Luk's 🏁 Track record (2026-11-01, luk spec §3.9 / §3.10 / §3.13; 2026-11-02 rewrite).
 *
 * Ajay 2026-11-02: "Can you make Luk's track record similar to Gajjal's and also can you make sure you are not
 * accounting for duplicates of the same stock as winner unless it did the same pattern again and met all the criteria
 * on the same day".
 *
 * The SAME 🏁 pieces as 🚩 Gajjala's (GajjalaBoard's exported GgTr* components, GajjalaAplusCharts), never a copy, in
 * 🚩's order: the served title, the served span chips (?span=), the served ✅ / ❌ category chips (?cat=), the served
 * ✅ wins-first chips (?sort=), the served counts line, the served charts block (always, when served), one table per
 * served day (the served heads, the served Tape column second, the served rows — flags, the 🔁 duplicate chip, the
 * served fill / exit cells), the served more / empty lines, the served rule folded under ⓘ, the served honesty LAST.
 * Every 🥇 A+ is graded by LUK's trade math on the server (fill, the stop or the first daily close below the 9 EMA).
 * The table sits in GgVariantContext 'luk', so the 📈 tape reads GET /chart-maps/luk/entry-tape — never a 🚩 route.
 * `cat` / `sort` are FE-only (no GET). An older block (no heads / views / charts) still renders its lines and day
 * headings. A record, never a study: this file types no word and no number. UNMEASURED. */
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import {
  LUK_CAT_PARAM, LUK_SORT_PARAM, LUK_SPAN_PARAM, lukSpan, lukText, type LukTrackRecord as LukTrackRecordBlock,
} from '../lib/luk';
import { ggCatDays, ggCatOn, ggSortRows, ggTrSort, type GgTrDay } from '../lib/gajjala';
import { GgTrCats, GgTrHead, GgTrSorts, GgTrTapeRow, ggTrTapeAt } from './GajjalaBoard';
import GajjalaAplusCharts from './GajjalaAplusCharts';
import { GgVariantContext } from './ggVariant';
import '../styles/gajjala.css';

export function LukTrackRecord({ track }: { track?: LukTrackRecordBlock | null }) {
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  if (!track) return null;
  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value == null) next.delete(key); else next.set(key, value);
    setParams(next, { replace: true });
  };
  const spanHref = (key: string) => {
    const next = new URLSearchParams(location.search);
    next.set(LUK_SPAN_PARAM, key);
    return `${location.pathname}?${next.toString()}`;
  };
  const cat = params.get(LUK_CAT_PARAM);
  const sort = params.get(LUK_SORT_PARAM);
  const spans = (track.spans ?? []).map(lukSpan);
  const heads = track.heads ?? [];
  const views = track.views ?? null;
  const cats = track.categories ?? null;
  const sortItem = ggTrSort(sort, track);
  const days: GgTrDay[] = (track.days ?? []).map((d) => ({ date: d.date, label: lukText(d.label) ?? d.date, rows: d.rows ?? [] }));
  const listDays = ggCatDays(days, cat, cats);
  const shownDays = listDays.map((d) => ({ ...d, rows: ggSortRows(d.rows || [], sortItem, track.bucket_order) }));
  const catEmpty = ggCatOn(cat, cats) && !listDays.length && days.some((d) => !!d.rows.length);
  const tapeAt = ggTrTapeAt(heads);
  return (
    <GgVariantContext.Provider value="luk">
      <section className="gg-track-record luk-tr" data-testid="luk-tr">
        {lukText(track.title) ? <h3 className="luk-h" data-testid="luk-tr-title">{track.title}</h3> : null}
        {spans.length ? (
          <div className="luk-chip-row luk-spans" role="group" aria-label="span" data-testid="luk-tr-spans">
            {spans.map((s) => (
              <Link key={s.key} to={spanHref(s.key)} replace
                    className={`cm-badge luk-span${s.key === track.span ? ' is-active' : ''}`}
                    aria-current={s.key === track.span ? 'true' : undefined}
                    data-testid={`luk-tr-span-${s.key}`}>{s.label}</Link>
            ))}
          </div>
        ) : null}
        <GgTrCats cats={cats} cat={cat} onCat={(k) => setParam(LUK_CAT_PARAM, k === cats?.[0]?.key ? null : k)} />
        <GgTrSorts sorts={track.sorts} on={sortItem}
                   onSort={(k) => setParam(LUK_SORT_PARAM, k === track.sort_default ? null : k)} />
        {lukText(track.counts_text) ? <p className="luk-line" data-testid="luk-tr-counts">{track.counts_text}</p> : null}
        {track.charts ? <GajjalaAplusCharts block={track.charts} /> : null}
        {catEmpty && lukText(track.category_empty_text) ? (
          <div className="cm-note" data-testid="luk-tr-cat-empty">{track.category_empty_text}</div>
        ) : null}
        {shownDays.map((d) => (
          <div key={d.date} className="gg-tr-day">
            <h4 className="luk-h4" data-testid={`luk-tr-day-${d.date}`}>{d.label}</h4>
            <div className="gg-tr-scroll">
              <table className="gg-tr-table luk-tr-table">
                <GgTrHead heads={heads} views={views} at={tapeAt} />
                <tbody>
                  {d.rows.map((r) => (
                    <GgTrTapeRow key={r.key ?? r.id} row={r} heads={heads} views={views} at={tapeAt} tid="luk-tr" />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
        {lukText(track.more_text) ? <p className="luk-line luk-muted" data-testid="luk-tr-more">{track.more_text}</p> : null}
        {!days.length && lukText(track.empty_text) ? <p className="luk-line luk-muted" data-testid="luk-tr-empty">{track.empty_text}</p> : null}
        {lukText(track.rule_text) ? (
          <details className="luk-fold" data-testid="luk-tr-rule">
            <summary>{'ⓘ'}</summary>
            <p className="luk-line">{track.rule_text}</p>
          </details>
        ) : null}
        {lukText(track.honesty) ? <p className="luk-line luk-muted" data-testid="luk-tr-honesty">{track.honesty}</p> : null}
      </section>
    </GgVariantContext.Provider>
  );
}

export default LukTrackRecord;
