/* 🧘 GG-like calm check — chip, check list, card, 🚩 filter toggle, count line, fold note (2026-11-27, spec gglike §3.9,
 * WP fe-core).
 *
 * Ajay 2026-11-27: "find calmer and better setups.. I want to make sure we are finding similar setups to Gajjala".
 *
 * Every word on screen is served (lib/ggLike.ts parses it). This file types control glyphs, class names and testids
 * only. The note sentences belong inside a ⓘ fold body, never above the cards. */
import { useState } from 'react';
import { ggLikeLabel, ggLikeLine } from '../lib/ggLike';
import type { GgLike, GgLikeBoard, GgLikeCheck, GgLikeSplit } from '../lib/ggLike';
import '../styles/ggLike.css';

const INFO_MARK = 'ⓘ';

/** The one chip. A <button> when onToggle is given (opens the list), else a <span>. Hover = the served title. */
export function GgLikeChip({ like, sym, open, onToggle }: { like: GgLike; sym: string; open?: boolean; onToggle?: () => void }) {
  const cls = `gg-like-chip gg-like-${like.tone}`;
  const title = like.title ?? undefined;
  if (onToggle) {
    return (
      <button type="button" className={cls} title={title} aria-expanded={!!open} data-testid={`gg-like-chip-${sym}`}
              data-gg-like={like.verdict} onClick={onToggle}>
        {like.chip}
      </button>
    );
  }
  return (
    <span className={cls} title={title} data-testid={`gg-like-chip-${sym}`} data-gg-like={like.verdict}>{like.chip}</span>
  );
}

function rowClass(c: GgLikeCheck): string {
  if (c.info) return 'gg-like-row gg-like-row--info';
  if (c.ok === true) return 'gg-like-row gg-like-row--ok';
  if (c.ok === false) return 'gg-like-row gg-like-row--no';
  return 'gg-like-row gg-like-row--na';
}

function CheckRow({ c }: { c: GgLikeCheck }) {
  return (
    <li className={rowClass(c)} data-gg-like-key={c.key}>
      <span className="gg-like-mark" aria-hidden="true">{c.info ? INFO_MARK : c.mark}</span>
      <span className="gg-like-label">{c.label}</span>
      {c.value ? <span className="gg-like-value">{c.value}</span> : null}
      {c.need ? <span className="gg-like-need">{c.need}</span> : null}
    </li>
  );
}

/** The ✓ / ✗ / n/a rows in the served order, then the ⓘ info rows (muted, never counted), then the served info line,
 *  the served source text and the given note. */
export function GgLikeList({ like, sym, note }: { like: GgLike; sym: string; note?: string | null }) {
  const counted = like.checks.filter((c) => !c.info);
  const info = like.checks.filter((c) => c.info);
  return (
    <div className="gg-like-list" data-testid={`gg-like-list-${sym}`}>
      {counted.length || info.length ? (
        <ul className="gg-like-rows">
          {counted.map((c) => <CheckRow key={c.key} c={c} />)}
          {info.map((c) => <CheckRow key={c.key} c={c} />)}
        </ul>
      ) : null}
      {like.info ? <p className="gg-like-line gg-like-muted" data-testid={`gg-like-info-${sym}`}>{like.info}</p> : null}
      {like.source_text ? <p className="gg-like-line gg-like-muted" data-testid={`gg-like-source-${sym}`}>{like.source_text}</p> : null}
      {note ? <p className="gg-like-line gg-like-muted" data-testid={`gg-like-note-${sym}`}>{note}</p> : null}
    </div>
  );
}

/** Chip + list; the list is closed until the chip is tapped (local state). A null block draws nothing. */
export function GgLikeCard({ like, sym, note }: { like: GgLike | null; sym: string; note?: string | null }) {
  const [open, setOpen] = useState(false);
  if (!like) return null;
  return (
    <div className="gg-like-card" data-testid={`gg-like-card-${sym}`}>
      <GgLikeChip like={like} sym={sym} open={open} onToggle={() => setOpen((o) => !o)} />
      {open ? <GgLikeList like={like} sym={sym} note={note} /> : null}
    </div>
  );
}

/** The 🚩 filter toggle: the served label with the live count (seen before the tap), the served hint on hover. */
export function GgLikeToggle({ board, n, on, onToggle, testid }:
  { board: GgLikeBoard; n: number; on: boolean; onToggle: () => void; testid?: string }) {
  return (
    <button type="button" className={`cm-phase-btn gg-like-toggle${on ? ' cm-phase-on' : ''}`} aria-pressed={on}
            title={board.hint ?? undefined} data-testid={testid} onClick={onToggle}>
      {ggLikeLabel(board, n)}
    </button>
  );
}

/** The count line + the served `show all` button. `on` = the filter is ON: then the served `show all` is ALWAYS drawn,
 *  even when nothing is hidden, kept, can't-tell or unchecked (spec T10: "while ON the count line is always drawn") —
 *  the empty line part is simply left out, no word is invented. Without `on`, an empty line draws nothing (an OFF split
 *  has zero counts). */
export function GgLikeHiddenLine({ board, split, onShowAll, testid, on }:
  { board: GgLikeBoard; split: GgLikeSplit<unknown>; onShowAll: () => void; testid?: string; on?: boolean }) {
  const line = ggLikeLine(board, split);
  if (!line && on !== true) return null;
  return (
    <div className="gg-like-hidden" data-testid={testid}>
      {line ? <span className="gg-like-muted gg-like-hidden-line">{line}</span> : null}
      <button type="button" className="gg-like-show-all" onClick={onShowAll}
              data-testid={testid ? `${testid}-show-all` : undefined}>
        {board.show_all_text}
      </button>
    </div>
  );
}

/** The served note, the separation and census sentences, then one row per check — for a ⓘ fold body ONLY. */
export function GgLikeNote({ board, testid }: { board: GgLikeBoard; testid?: string }) {
  const lines = [board.note, board.separation_text, board.census_text].filter((s): s is string => !!s);
  if (!lines.length && !board.rows.length) return null;
  return (
    <div className="gg-like-note" data-testid={testid}>
      {lines.map((s, i) => <p key={i} className="gg-like-line">{s}</p>)}
      {board.rows.length ? (
        <ul className="gg-like-note-rows">
          {board.rows.map((r, i) => <li key={i} className="gg-like-line">{r}</li>)}
        </ul>
      ) : null}
    </div>
  );
}
