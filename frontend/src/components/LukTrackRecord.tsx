/* LukTrackRecord — 🥇 Luk's 🏁 Track record (2026-11-01, luk spec §3.9 / §3.10 / §3.13).
 *
 * Every 🥇 A+ recorded here since 2026-11-01, graded by LUK's trade math on the server (fill, the stop or the first
 * daily close below the 9 EMA, the 3R / 5R flags). The served span chips (?span=), the served counts line, the served
 * rule text folded under ⓘ, the served honesty line, then the served days → rows: plan / fill / exit / flags / rang
 * texts, verbatim. A 📈 toggle per row mounts LukEntryTape (GET /chart-maps/luk/entry-tape — the Luk route only).
 * A shadow record, never a study: this file types no word and no number. */
import { Fragment, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LUK_SPAN_PARAM, lukSpan, lukText, type LukTrackRecord as LukTrackRecordBlock, type LukTrRow } from '../lib/luk';
import { LukEntryTape } from './LukEntryTape';

const ROW_TEXTS: ReadonlyArray<keyof LukTrRow> = ['setup_label', 'at_et', 'rang_text', 'plan_text', 'fill_text', 'exit_text', 'flags_text'];

export function LukTrackRecord({ track }: { track?: LukTrackRecordBlock | null }) {
  const location = useLocation();
  const [open, setOpen] = useState<Record<string, boolean>>({});
  if (!track) return null;
  const spanHref = (key: string) => {
    const next = new URLSearchParams(location.search);
    next.set(LUK_SPAN_PARAM, key);
    return `${location.pathname}?${next.toString()}`;
  };
  const spans = (track.spans ?? []).map(lukSpan);
  const days = track.days ?? [];
  return (
    <div className="luk-tr" data-testid="luk-tr">
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
      {lukText(track.counts_text) ? <p className="luk-line" data-testid="luk-tr-counts">{track.counts_text}</p> : null}
      {lukText(track.rule_text) ? (
        <details className="luk-fold" data-testid="luk-tr-rule">
          <summary>{'ⓘ'}</summary>
          <p className="luk-line">{track.rule_text}</p>
        </details>
      ) : null}
      {lukText(track.honesty) ? <p className="luk-line luk-muted" data-testid="luk-tr-honesty">{track.honesty}</p> : null}
      {!days.length && lukText(track.empty_text) ? <p className="luk-line luk-muted" data-testid="luk-tr-empty">{track.empty_text}</p> : null}
      {days.map((d) => (
        <section key={d.date} className="luk-tr-day" data-testid={`luk-tr-day-${d.date}`}>
          <h4 className="luk-h4">{lukText(d.label) ?? d.date}</h4>
          <ul className="luk-tr-rows">
            {(d.rows ?? []).map((r) => (
              <Fragment key={r.id}>
                <li className="luk-tr-row" data-testid={`luk-tr-row-${r.id}`}>
                  {lukText(r.href) ? <Link to={r.href!}><strong>{r.symbol}</strong></Link> : <strong>{r.symbol}</strong>}
                  {ROW_TEXTS.map((k) => (lukText(r[k]) ? (
                    <span key={k} className={`luk-tr-${k}`} data-testid={`luk-tr-${k}-${r.id}`}>{' · '}{r[k] as string}</span>
                  ) : null))}
                  {' '}
                  <button type="button" className="luk-tape-toggle" aria-expanded={!!open[r.id]}
                          aria-label={`tape ${r.symbol}`} data-testid={`luk-tape-toggle-${r.id}`}
                          onClick={() => setOpen((o) => ({ ...o, [r.id]: !o[r.id] }))}>{'\u{1F4C8}'}</button>
                </li>
                {open[r.id] ? <li className="luk-tr-tape"><LukEntryTape id={r.id} /></li> : null}
              </Fragment>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

export default LukTrackRecord;
