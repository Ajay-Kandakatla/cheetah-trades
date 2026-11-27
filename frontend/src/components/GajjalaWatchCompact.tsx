/* 🗂 GajjalaWatchCompact — the organised 👀 Watch tile's pieces (2026-11-22, spec watch_org rev 4 §3.5, WP-FE-WATCH).
 *
 * Ajay 2026-11-22: "I need gajjalas watch tab little more organized. With less info, I want to know previous day winner
 * auto additions vs intraday may be a time stamp. or something figure out a better way to organize that info for me.."
 * and "Manual ones I add them need to be on top then auto intraday..".
 *
 * Three pieces the compact Tile mounts (GajjalaWatchTile.tsx, `compact` — the Watch passes it ONLY when the server
 * serves sections; the 🚩 / 🧪 card grid and GgCardView never do):
 *   - GgwSetupChip — the served setup chip in the head (🎾 picked first by the server);
 *   - GgwProvLine  — the ONE time line under the head: the served "when" chip, the 📅 chip ONLY when the served 📅
 *                    block carries a chip `text`, the 🏆 chip; each hover = its served title;
 *   - GgwDrawer    — ⋯ everything else, one tap away (kept MOUNTED while closed — its hooks never re-run on a tap): the
 *                    tags row (without the float / 🚫 chips the head already prints), the 🤖 chip and its served lines,
 *                    the served A+ / when / 📅 titles (a phone has no hover — the premarket-peak and under-the-bar
 *                    lines live here even when there is no 📅 chip), every 🏆 win, and the non-stale as-of stamp.
 * Every visible string is SERVED; this file types no word about a stock and no section key. Descriptive, UNMEASURED.
 *
 * 📐 2026-11-23 (vwapzones spec §3.9) — Ajay: "can you add vwap and supply demand zone in the daily time frame on the
 * watch list please". GgwLevelsLine = the row's served daily-zones line (text verbatim, hover = the served title); the
 * plain Tile mounts it under the head, GgwDrawer mounts it here on a compact tile (once per tile either way).
 *
 * 📅 2026-11-26 (spec watchrun §3.5) — Ajay: "Ok then add them to our watch list and track them please.. I know he tracks
 * them for two weeks sometimes.. before he discards them..". A name seated on 📅 Runners that also has a tile carries the
 * served `row.runner`: GgwProvLine draws its two served chips (day · seat, hover = the served seat title) after the when
 * chip; GgwDrawer prints the served seat title (a phone has no hover). A row without `runner` draws nothing new.
 *
 * 🧘 2026-11-27 (spec gglike §3.9, WP fe-watch) — Ajay: "find calmer and better setups.. I want to make sure we are finding
 * similar setups to Gajjala". GgwGgLikeChip = the SERVED GG-like chip of the tile's setup (lib/gajjalaWatch.ggwTileGgLike:
 * the served setup chip's key, else 🎾, else the first carded), a <span> right after GgwSetupChip; GgwDrawer prints that
 * block's ✓ / ✗ / n/a rows (GgLikeList). Display only: NO toggle, NO hidden line, NO `hidden`, NO storage key — nothing on
 * the Watch is ever hidden by 🧘 (every A+ push lands here). Observed on GG's example charts, not his rule; UNMEASURED. */
import { ggwTileGgLike, type GgwRow } from '../lib/gajjalaWatch';
import { GgLikeChip, GgLikeList } from './GgLike';
import { GgwTagsRow, type GgwTagsCtx } from './GajjalaWatchTags';

/** The served setup chip of an organised row; nothing when none is served. */
export function GgwSetupChip({ row }: { row: GgwRow }) {
  const s = row.org?.setup;
  if (!s) return null;
  return (
    <span className="ggw-chip ggw-setup-chip" data-testid={`ggw-setup-chip-${row.symbol}`} title={s.title ?? undefined}>
      {s.text}
    </span>
  );
}

/** 🧘 The served GG-like chip of the tile's setup (a span — the list lives in the ⋯ drawer); nothing without a block. */
export function GgwGgLikeChip({ row }: { row: GgwRow }) {
  const g = ggwTileGgLike(row);
  return g ? <GgLikeChip like={g.like} sym={row.symbol} /> : null;
}

/** 📐 The row's served daily-zones line (row.levels — ok / retry / none / pending, every word served). No text → nothing. */
export function GgwLevelsLine({ row }: { row: GgwRow }) {
  const lv = row.levels;
  if (!lv || !lv.text) return null;
  return (
    <p className="ggw-line ggw-levels" data-testid={`ggw-levels-${row.symbol}`} data-state={lv.state}
       title={lv.title ?? undefined}>{lv.text}</p>
  );
}

/** The 🏆 chip's hover: the served title, else every served win's words. */
function pastTitle(row: GgwRow): string | undefined {
  const p = row.org?.past_winner;
  if (!p) return undefined;
  return p.title ?? ([...p.items, p.more].filter(Boolean).join(' · ') || undefined);
}

/** The ONE time line: when · 📅 (only with a served chip text) · 🏆. Nothing served → nothing drawn. */
export function GgwProvLine({ row }: { row: GgwRow }) {
  const o = row.org;
  const when = o?.when ?? null;
  const ranText = o?.ran?.text ?? null;
  const past = o?.past_winner ?? null;
  const run = row.runner ?? null;
  if (!when && !ranText && !past && !run) return null;
  const sym = row.symbol;
  return (
    <div className="ggw-prov" data-testid={`ggw-prov-${sym}`}>
      {when ? (
        <span className="ggw-chip ggw-when" data-testid={`ggw-when-${sym}`} data-bucket={when.bucket ?? undefined}
              title={when.title ?? undefined}>{when.text}</span>
      ) : null}
      {run?.day_text ? (
        <span className="ggw-chip ggw-runner-day" data-testid={`ggw-runner-day-${sym}`}>{run.day_text}</span>
      ) : null}
      {run?.seat_text ? (
        <span className="ggw-chip ggw-runner-seat" data-testid={`ggw-runner-seat-${sym}`}
              title={run.seat_title ?? undefined}>{run.seat_text}</span>
      ) : null}
      {ranText ? (
        <span className="ggw-chip ggw-ran" data-testid={`ggw-ran-${sym}`} title={o?.ran?.title ?? undefined}>{ranText}</span>
      ) : null}
      {past ? (
        <span className="ggw-chip ggw-past" data-testid={`ggw-past-${sym}`} title={pastTitle(row)}>{past.text}</span>
      ) : null}
    </div>
  );
}

/** ⋯ the per-tile drawer. `open` drives `hidden` (the tile's ⋯ button carries aria-expanded). */
export function GgwDrawer({ row, open, tags, domId }: { row: GgwRow; open: boolean; tags?: GgwTagsCtx; domId?: string }) {
  const sym = row.symbol;
  const o = row.org;
  const a = row.auto;
  const autoLines = a ? [a.added_text, a.volume_text, a.leaving_text].filter((x): x is string => !!x) : [];
  const past = o?.past_winner ?? null;
  const like = ggwTileGgLike(row);
  return (
    <div className="ggw-drawer" id={domId} data-testid={`ggw-drawer-${sym}`} hidden={!open || undefined}>
      {tags ? <GgwTagsRow row={row} room={tags.room} study={tags.study} omitFloat omitBroker /> : null}
      {like ? (
        <div className="ggw-drawer-row ggw-gglike" data-testid={`ggw-gglike-${sym}`} data-setup={like.setup}>
          <GgLikeList like={like.like} sym={sym} />
        </div>
      ) : null}
      {a ? (
        <div className="ggw-drawer-row">
          <span className="ggw-chip ggw-auto" data-testid="ggw-auto">{a.text}</span>
        </div>
      ) : null}
      {autoLines.map((t, i) => <p key={`a${i}`} className="ggw-line" data-testid="ggw-auto-line">{t}</p>)}
      {row.aplus?.title ? <p className="ggw-line" data-testid="ggw-aplus-title">{row.aplus.title}</p> : null}
      {o?.when?.title ? <p className="ggw-line" data-testid="ggw-when-title">{o.when.title}</p> : null}
      {o?.ran?.title ? <p className="ggw-line" data-testid="ggw-ran-title">{o.ran.title}</p> : null}
      {row.runner?.seat_title ? <p className="ggw-line" data-testid="ggw-runner-title">{row.runner.seat_title}</p> : null}
      {past ? [...(past.items.length ? past.items : [past.text]), ...(past.more ? [past.more] : [])].map((t, i) => (
        <p key={`p${i}`} className="ggw-line" data-testid="ggw-past-line">{t}</p>
      )) : null}
      <GgwLevelsLine row={row} />
      {row.as_of_et && !row.stale ? (
        <div className="ggw-drawer-row">
          <span className="ggw-chip ggw-asof" data-testid="ggw-asof">{row.as_of_et}</span>
        </div>
      ) : null}
    </div>
  );
}
