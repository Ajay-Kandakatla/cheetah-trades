/* 📅 Previous day runners — the strip (2026-11-22, spec watch_org rev 4 §3.6, WP-FE-STRIP).
 *
 * Ajay 2026-11-22: "remove hot sectors mess from Gajjalas top view I need a new thing there.. use that space between the
 * parent tab of Gajjala and watch tab to be for previous day runners but remove them if they don’t run the current day".
 *
 * Placement-neutral: this component is NOT mounted by any page yet — where it sits is HIS CALL #1 (the held package
 * `runners-mount-fe`). `fold={false}` draws every chip with no "+n more" (the body of a 📅 tab, option (c)).
 *
 * Every word, number and the order are SERVED (backend gajjala_watch/runners.py): the FE types no threshold, no clock
 * time and no sentence. The ➕ is the shared GgWatchButton (never a copy); the phone test is the Watch's own usePhone
 * (never a second media query). Desktop folded: the first `fold_at` full chips + "+n more". Phone folded: ONE line —
 * title · count · the first `fold_at_phone` names as SYM + gain only · "+n more"; open → every full chip.
 * Display only, UNMEASURED: nothing here rings, gates, adds or trades. */
import { useState } from 'react';
import {
  ggrMoreText, readGgrOpen, saveGgrOpen, useGgRunners, type GgRunnerRow, type GgRunnersPayload,
} from '../lib/ggRunners';
import { GgWatchButton } from './GgWatchButton';
import { usePhone } from './GajjalaWatchTile';
import '../styles/ggRunners.css';

function Chip({ row }: { row: GgRunnerRow }) {
  const sym = row.symbol;
  return (
    <span className={`ggr-chip${row.broker_text ? ' is-broker' : ''}`} data-testid={`ggr-chip-${sym}`}
          title={row.title ?? undefined}>
      <b>{sym}</b>
      <span className="ggr-run">{row.run_text}</span>
      {row.timing_text && <span className="ggr-timing">{row.timing_text}</span>}
      {row.float_text && <span className="ggr-float" title={row.float_title ?? undefined}>{row.float_text}</span>}
      {row.past_winner_text && (
        <span className="ggr-past" title={row.past_winner_title ?? undefined}>{row.past_winner_text}</span>
      )}
      {row.broker_text && <span className="ggr-broker">{row.broker_text}</span>}
      <GgWatchButton symbol={sym} />
    </span>
  );
}

function Head({ p, hint }: { p: GgRunnersPayload; hint: boolean }) {
  return (
    <>
      {p.title && <b className="ggr-title" data-testid="ggr-title">{p.title}</b>}
      {p.text && <span className="ggr-count" data-testid="ggr-count">{p.text}</span>}
      {hint && p.hint && (
        <details className="ggr-hint" data-testid="ggr-hint"><summary>ℹ️</summary>{p.hint}</details>
      )}
    </>
  );
}

export default function GgRunnersStrip({ fold = true }: { fold?: boolean }) {
  const { data: p } = useGgRunners();
  const phone = usePhone();
  const [open, setOpen] = useState<boolean>(readGgrOpen);

  if (!p || p.state === 'off' || p.state === 'owner_only') return null;

  if (p.state !== 'ok') {
    return (
      <div className="ggr-strip" data-testid="ggr-strip" data-state={p.state}>
        <div className="ggr-head"><Head p={p} hint /></div>
      </div>
    );
  }

  const rows = p.rows;
  const canFold = fold && !!p.more_text && !!p.less_text && rows.length > 0;
  const toggle = () => { const next = !open; setOpen(next); saveGgrOpen(next); };
  const more = (n: number) => (
    <button type="button" className="ggr-more" data-testid="ggr-more" aria-expanded={false} onClick={toggle}>
      {n > 0 ? ggrMoreText(p.more_text as string, n) : '⋯'}
    </button>
  );
  const less = (
    <button type="button" className="ggr-more" data-testid="ggr-more" aria-expanded onClick={toggle}>
      {p.less_text}
    </button>
  );
  const removed = p.removed_text && p.removed.length > 0 ? (
    <details className="ggr-removed" data-testid="ggr-removed">
      <summary>{p.removed_text}</summary>
      <ul>
        {p.removed.map((r) => (
          <li key={r.symbol} data-testid={`ggr-removed-${r.symbol}`}>
            {r.symbol} {r.run_text}{r.text ? ` · ${r.text}` : ''}
          </li>
        ))}
      </ul>
    </details>
  ) : null;

  /* 📱 folded: ONE line — title · count · the first fold_at_phone names (SYM + gain) · "+n more". */
  if (phone && canFold && !open) {
    const k = p.fold_at_phone ?? rows.length;
    const minis = rows.slice(0, k);
    return (
      <div className="ggr-strip is-phone" data-testid="ggr-strip" data-state={p.state}>
        <div className="ggr-line">
          <Head p={p} hint={false} />
          {minis.map((r) => (
            <span key={r.symbol} className="ggr-mini" data-testid={`ggr-mini-${r.symbol}`}>
              <b>{r.symbol}</b> {r.run_text}
            </span>
          ))}
          {more(rows.length - minis.length)}
        </div>
      </div>
    );
  }

  const limit = p.fold_at;
  const folds = canFold && limit !== null && rows.length > limit;
  const shown = folds && !open ? rows.slice(0, limit as number) : rows;
  /* the phone opens through the one-line view even when every name fits, so it always offers the way back */
  const button = !canFold ? null : open ? ((folds || phone) ? less : null) : (folds ? more(rows.length - shown.length) : null);

  return (
    <div className={`ggr-strip${phone ? ' is-phone' : ''}`} data-testid="ggr-strip" data-state={p.state}>
      <div className="ggr-head"><Head p={p} hint /></div>
      <div className="ggr-chips">
        {shown.map((r) => <Chip key={r.symbol} row={r} />)}
        {button}
      </div>
      {removed}
    </div>
  );
}
