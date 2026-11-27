/* 📅 GgwRunRoster — the runners kept on the 👀 Watch for two weeks, as a light roster under the tiles (2026-11-26,
 * spec watchrun rev 2 §3.5, WP fe-roster).
 *
 * Ajay 2026-11-26: "Ok then add them to our watch list and track them please.. I know he tracks them for two weeks
 * sometimes.. before he discards them.. Can you do that please" · "Make it 30% please after A+".
 *
 * One line per seated runner, in the SERVED order (🚫 last as served): the ticker (opens the existing continuous 📅 chart
 * with every roster name as its ‹ › list), the served day chip, the served seat chip (hover = its served title), the
 * served 🚫 word, the served "on your Watch" words OR the shared ➕ button, a 🧾 toggle (that ticker's record, fetched
 * when opened) and the roster's OWN × on EVERY row (title = the served `remove_title`).
 * TWO ×, TWO LISTS [fixed: C4]: this × is lib/ggwRunRoster.useGgwRunSeatRemove → DELETE ggwRunSeatPath(sym) only; the row
 * leaves at once, then the board makes ONE re-GET (`onChanged`, the useGgwBrokerMark precedent). The board's own
 * write('DELETE') is never handed here, and a tile above is never touched.
 * Phone: folded to its one header line until tapped (remembered beside `ggw.opened`); desktop: the first served `fold_at`
 * rows + the served "+n more". ONE ⓘ fold holds the served hint, the served not-seated sentences and — fetched only when
 * it opens — the record's served summary, note and closed table. No explanation text outside the fold; no word, number
 * or threshold typed here (control glyphs only). Display + his own 📅 list write only; UNMEASURED. */
import { useEffect, useMemo, useState, type SyntheticEvent } from 'react';
import { GGW_SECTION_GLYPH } from '../lib/gajjalaWatch';
import { openGgRunChart, ggrcOpenTitle } from '../lib/ggRunChart';
import { ggrMoreText } from '../lib/ggRunners';
import {
  GGW_RUNROSTER, ggwRunHistoryTitle, readGgwRunRosterOpen, saveGgwRunRosterOpen, useGgwRunSeatRemove, useGgwRunTrack,
  type GgwRunRoster as GgwRunRosterBlock, type GgwRunRosterRow, type GgwRunTable,
} from '../lib/ggwRunRoster';
import { GgWatchButton } from './GgWatchButton';
import '../styles/ggwRunRoster.css';

/** A served table in its own sideways scroll box (430 px: never wider than the viewport). Empty → nothing. */
export function GgwRunTableView({ table, testid }: { table: GgwRunTable; testid: string }) {
  if (!table.rows.length) return null;
  return (
    <div className="ggw-rr-scroll" data-testid={`${testid}-scroll`}>
      <table className="ggw-rr-table" data-testid={testid}>
        {table.heads.length ? (
          <thead><tr>{table.heads.map((h, i) => <th key={`h${i}`} scope="col">{h}</th>)}</tr></thead>
        ) : null}
        <tbody>
          {table.rows.map((r, i) => (
            <tr key={`r${i}`}>{r.map((c, j) => <td key={`c${j}`}>{c}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const line = (cls: string, t: string | null, testid?: string) =>
  (t ? <p className={`ggw-line ${cls}`} data-testid={testid ?? cls}>{t}</p> : null);

/** ⓘ the record of every run — read only while the fold is open. */
function TrackAll({ open }: { open: boolean }) {
  const st = useGgwRunTrack(open);
  if (st.phase !== 'all') return null;
  const d = st.data;
  return (
    <div className="ggw-rr-track" data-testid="ggw-rr-track" data-state={d.state}>
      {line('ggw-rr-track-title', d.title)}
      {line('ggw-rr-track-text', d.text)}
      {line('ggw-rr-track-summary', d.summary_text)}
      {line('ggw-rr-track-note', d.note)}
      {line('ggw-rr-track-asof', d.asof_text)}
      <GgwRunTableView table={d.table} testid="ggw-rr-track-table" />
      {line('ggw-rr-track-shown', d.shown_text)}
    </div>
  );
}

/** 🧾 one ticker's record (and the seat chip's served title — a phone has no hover), read only while it is open. */
function TrackSymbol({ row }: { row: GgwRunRosterRow }) {
  const st = useGgwRunTrack(true, row.symbol);
  const d = st.phase === 'symbol' ? st.data : null;
  const sym = row.symbol;
  return (
    <div className="ggw-rr-hist" data-testid={`ggw-rr-hist-${sym}`}>
      {line('ggw-rr-seat-title', row.seat_title, `ggw-rr-seat-title-${sym}`)}
      {d ? (
        <>
          {line('ggw-rr-hist-title', d.title)}
          {line('ggw-rr-hist-text', d.text)}
          {d.docs.map((doc, i) => (
            <div key={`${doc.run_day ?? ''}-${i}`} className="ggw-rr-doc" data-testid={`ggw-rr-doc-${sym}`}>
              {line('ggw-rr-doc-seat', doc.seat_text)}
              {line('ggw-rr-doc-state', doc.state_text)}
              {line('ggw-rr-doc-base', doc.base_note)}
              <GgwRunTableView table={doc.table} testid={`ggw-rr-doc-table-${sym}`} />
            </div>
          ))}
          {line('ggw-rr-hist-note', d.note)}
        </>
      ) : null}
    </div>
  );
}

function Row({ row, syms, onRemove }: {
  row: GgwRunRosterRow; syms: string[]; onRemove: (sym: string) => void;
}) {
  const [hist, setHist] = useState(false);
  const sym = row.symbol;
  const histTitle = ggwRunHistoryTitle(sym);
  return (
    <li className="ggw-rr-row" data-testid={`ggw-rr-row-${sym}`} data-rule={row.rule ?? undefined}>
      <button type="button" className="ggw-rr-sym" data-testid={`ggw-rr-sym-${sym}`} title={ggrcOpenTitle(sym)}
              onClick={() => openGgRunChart(sym, syms)}>{sym}</button>
      {row.day_text ? <span className="ggw-chip ggw-rr-day" data-testid={`ggw-rr-day-${sym}`}>{row.day_text}</span> : null}
      {row.seat_text ? (
        <span className="ggw-chip ggw-rr-seat" data-testid={`ggw-rr-seat-${sym}`} title={row.seat_title ?? undefined}>
          {row.seat_text}
        </span>
      ) : null}
      {row.broker_text ? (
        <span className="ggw-chip ggw-rr-broker" data-testid={`ggw-rr-broker-${sym}`}>{row.broker_text}</span>
      ) : null}
      {row.on_watch
        ? (row.on_watch_text ? <span className="ggw-rr-onwatch" data-testid={`ggw-rr-onwatch-${sym}`}>{row.on_watch_text}</span> : null)
        : <GgWatchButton symbol={sym} />}
      <button type="button" className="ggw-btn ggw-rr-hist-btn" data-testid={`ggw-rr-hist-btn-${sym}`} title={histTitle}
              aria-label={histTitle} aria-expanded={hist} onClick={() => setHist((h) => !h)}>{GGW_RUNROSTER.history}</button>
      <button type="button" className="ggw-btn ggw-rr-x" data-testid={`ggw-rr-x-${sym}`} title={row.remove_title ?? undefined}
              aria-label={row.remove_title ?? undefined} onClick={() => onRemove(sym)}>
        {GGW_RUNROSTER.remove}
      </button>
      {hist ? <TrackSymbol row={row} /> : null}
    </li>
  );
}

/** The roster. `block` = the served `board.runners`; `onChanged(text)` = the board's message + ONE re-GET. */
export default function GgwRunRoster({ block, phone, onChanged }: {
  block: GgwRunRosterBlock; phone: boolean; onChanged: (text: string | null) => void;
}) {
  const [open, setOpen] = useState<boolean>(readGgwRunRosterOpen);
  const [more, setMore] = useState(false);
  const [info, setInfo] = useState(false);
  /* a × hides its row NOW. At each newly served roster a name whose × is no longer in flight is let go — the re-GET
   * after the answer then draws it again only when the server still lists it (a failed ×). */
  const seat = useGgwRunSeatRemove((text) => onChanged(text));
  const [gone, setGone] = useState<ReadonlySet<string>>(() => new Set());
  useEffect(() => {
    setGone((g) => {
      const keep = [...g].filter((s) => seat.pending(s));
      return keep.length === g.size ? g : new Set(keep);
    });
  }, [block]); // eslint-disable-line react-hooks/exhaustive-deps
  const removeRow = (sym: string) => {
    if (seat.pending(sym)) return;
    setGone((g) => new Set(g).add(sym));
    seat.remove(sym);
  };
  const rows = useMemo(() => block.rows.filter((r) => !gone.has(r.symbol)), [block.rows, gone]);

  if (block.state !== 'ok') {
    return block.text ? (
      <section className="ggw-rr" data-testid="ggw-rr" data-state={block.state}>
        <p className="ggw-line ggw-warn ggw-rr-warn" data-testid="ggw-rr-warn">{block.text}</p>
      </section>
    ) : null;
  }

  const syms = block.rows.map((r) => r.symbol);
  const folded = phone && block.folded_default && !open;
  const toggleOpen = () => { const next = !open; setOpen(next); saveGgwRunRosterOpen(next); };
  const onInfo = (e: SyntheticEvent<HTMLDetailsElement>) => setInfo(e.currentTarget.open);
  const head = phone ? (
    <button type="button" className="ggw-rr-head-btn" data-testid="ggw-rr-head" aria-expanded={!folded} onClick={toggleOpen}>
      {`${folded ? GGW_SECTION_GLYPH.closed : GGW_SECTION_GLYPH.open} ${block.text ?? block.title ?? ''}`}
    </button>
  ) : (
    <span className="ggw-rr-head-text" data-testid="ggw-rr-head">{block.text ?? block.title}</span>
  );
  const fold = (
    <details className="ggw-rr-info" data-testid="ggw-rr-info" onToggle={onInfo}>
      <summary aria-label={GGW_RUNROSTER.infoLabel}>{GGW_RUNROSTER.info}</summary>
      {line('ggw-rr-hint', block.hint)}
      {block.not_seated.map((n, i) => (
        <p key={`${n.symbol ?? ''}-${n.session ?? ''}-${i}`} className="ggw-line ggw-rr-not-seated"
           data-testid="ggw-rr-not-seated">{n.text}</p>
      ))}
      <TrackAll open={info} />
    </details>
  );
  const limit = phone ? null : block.fold_at;
  const folds = limit !== null && rows.length > limit && !!block.more_text;
  const shown = folds && !more ? rows.filter((_r, i) => i < (limit as number)) : rows;
  const moreBtn = folds ? (
    more ? (block.less_text ? (
      <button type="button" className="ggw-rr-more" data-testid="ggw-rr-more" aria-expanded onClick={() => setMore(false)}>
        {block.less_text}
      </button>
    ) : null) : (
      <button type="button" className="ggw-rr-more" data-testid="ggw-rr-more" aria-expanded={false} onClick={() => setMore(true)}>
        {ggrMoreText(block.more_text as string, rows.length - shown.length)}
      </button>
    )
  ) : null;
  return (
    <section className={`ggw-rr${phone ? ' is-phone' : ''}`} data-testid="ggw-rr" data-state={block.state}
             data-folded={folded || undefined}>
      <div className="ggw-rr-headline">{head}{fold}</div>
      {folded ? null : (
        <>
          <ul className="ggw-rr-rows">
            {shown.map((r) => (
              <Row key={r.symbol} row={r} syms={syms} onRemove={removeRow} />
            ))}
          </ul>
          {moreBtn}
        </>
      )}
    </section>
  );
}
