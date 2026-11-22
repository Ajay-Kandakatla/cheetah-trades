/* 🏷️ GajjalaWatchTags — the tags row above each 👀 Gajjala's Watch tile (2026-11-18, spec wtags §3.3, WP-B).
 *
 * Ajay 2026-11-18: "Also add Short Interest tag and other tags on top of stock ticker information for me to read, like
 * here" — "here" = the 🚩 Gajjala card grid, where a row of chips sits ABOVE each card.
 *
 * The row prints, in the card's own order (GajjalaBoard.tsx `.cm-tile-chips`): 🚀 GrowthChip, 🩳 ShortInterestChip (hidden
 * when the head's EXTREME note already prints — one SI line per tile), then — for a name CARDED on today's 🚩 GG5 board
 * only (the served `tags` block) — 🧨 ExplosiveChip, 🎯 / ⛔ EnterableChip, 📌 / 🎪 GgTraderChip, 🚫 the broker span, the
 * Float chip, and the 🧭 GgStages line (or one chip per carded setup when no stages block exists). EVERY chip wears the
 * house `cm-badge` skin. The component types NO sentence: class names, testids and the served strings only.
 *
 * The room / band reads come from ONE board-level POST (useGgwTags below) for the carded names only — never per tile,
 * never for an off-board name (HIS CALL #3). Nothing prints → null (a tag-less tile's DOM is today's exactly).
 * Display only — nothing rings, orders or sorts. UNMEASURED.
 * 🔢 2026-11-21 (spec watchfloat) — Ajay: "can you add the current float value also to the tickers on the watch list." */
import { useCallback, useMemo } from 'react';
import { ggwFloat, type GgwRow } from '../lib/gajjalaWatch';
import { useBounceRoom as useRoomRead } from '../hooks/useBounceRoom';
import { explosiveChipText, type BounceRoomRow as RoomRow, type ExplosiveStudy } from '../lib/bounceRoom';
import { enterableChipText } from '../lib/enterable';
import { useShortInterest } from '../hooks/useShortInterest';
import { siChip, siExtreme } from '../lib/shortInterest';
import { growthChip, useGrowthTags } from '../hooks/useGrowthTags';
import { GrowthChip } from './GrowthChip';
import { ShortInterestChip } from './ShortInterestChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import { GgTraderChip, servedChip } from './GgTraderChip';
import { GgStages } from './GgStages';
import { ggwBrokerText } from '../lib/ggwBroker';

/** What the board hands each Watch tile: this name's room row (null when none) and the served study verdict. */
export type GgwTagsCtx = { room?: RoomRow | null; study?: ExplosiveStudy | null };

const served = (x: unknown): x is string => typeof x === 'string' && x.trim() !== '';

/** The served stages block draws something (GgStages' own test: a served title and at least one tag with served text). */
function stagesPrint(t: GgwRow['tags']): boolean {
  const s = t?.stages;
  if (!s || !served(s.title)) return false;
  return (Array.isArray(s.groups) ? s.groups : []).some(
    (g) => !!g && Array.isArray(g.tags) && g.tags.some((x) => !!x && served(x.text)));
}

/** The board's ONE room read for the names carded on today's 🚩 board (their served tags block says so). An empty list
 *  sends nothing (the hook's own rule). Called unconditionally by the board — hooks order. */
export function useGgwTags(rows: ReadonlyArray<GgwRow> | null): (r: GgwRow) => GgwTagsCtx {
  const syms = useMemo(() => (rows ?? []).filter((r) => r.tags?.on_board).map((r) => r.symbol), [rows]);
  const room = useRoomRead(syms);
  const study = room.payload?.explosive_study ?? null;
  return useCallback(
    (r: GgwRow): GgwTagsCtx => ({ room: room.map.get(r.symbol.toUpperCase()) ?? null, study }),
    [room.map, study],
  );
}

/** 🔢 The ONE float chip of a Watch row (+ its served suspect line) — defined ONCE (the float contract counts its testid).
 *  2026-11-22 (spec watch_org §3.5): exported so the compact tile head draws the SAME chip; the tags row then omits it. */
/* 🔢 2026-11-21 (spec watchfloat): the row's own served float (any row, carded or not), else the CARDED tags' float — ONE read. */
const rowFloat = (row: GgwRow) => ggwFloat({ float: row.float, tags: row.tags?.on_board ? row.tags : null });

export function GgwFloatChip({ row }: { row: GgwRow }) {
  const sym = row.symbol;
  const fl = rowFloat(row);
  return fl ? (
    <>
      <span className="cm-badge cm-badge-muted ggw-float" data-testid={`ggw-float-${sym}`}
            title={fl.title ?? undefined}>{fl.text}</span>
      {served(fl.suspect_text)
        ? <span className="cm-badge cm-badge-warn ggw-float-suspect" data-testid={`ggw-float-suspect-${sym}`}>{fl.suspect_text}</span>
        : null}
    </>
  ) : null;
}

/** 🚫 The ONE broker chip of a Watch row — 2026-11-22: exported so the compact tile head draws the SAME chip. */
export function GgwBrokerChip({ row }: { row: GgwRow }) {
  const t = row.tags?.on_board ? row.tags : null;
  /* 🚫 2026-11-19 (spec watchfid): the row's own served word (any row, carded or not), else the CARDED tags' word — ONE chip. */
  const brokerText = ggwBrokerText({ broker_text: row.broker_text, tags: t });
  return servedChip(brokerText, 'gg-broker ggw-broker', `ggw-broker-${row.symbol}`);
}

export function GgwTagsRow({ row, room, study, omitFloat, omitBroker }: {
  row: GgwRow; room?: RoomRow | null; study?: ExplosiveStudy | null;
  /** 🗂 2026-11-22: the compact tile prints the float / 🚫 chip in its head — the row then omits it (one chip per tile).
   *  Absent → today's row exactly. */
  omitFloat?: boolean; omitBroker?: boolean;
}) {
  const sym = row.symbol;
  const growth = growthChip(useGrowthTags(), sym);
  const { read } = useShortInterest(sym);
  const siText = siExtreme(read) ? null : siChip(read);
  const t = row.tags?.on_board ? row.tags : null;
  const ex = t ? explosiveChipText(room?.explosive, study) : null;
  const en = t ? enterableChipText(room?.enterable) : null;
  const trader = t && (served(t.trader_text) || served(t.promo_text));
  const brokerText = omitBroker ? null : ggwBrokerText({ broker_text: row.broker_text, tags: t });
  const fl = omitFloat ? null : rowFloat(row);
  const floatChip = fl ? <GgwFloatChip row={row} /> : null;
  const brokerChip = brokerText ? <GgwBrokerChip row={row} /> : null;
  const stages = t && stagesPrint(t);
  const setups = t && !stages ? t.setups.filter((s) => served(s.label)) : [];
  if (!growth && !siText && !ex && !en && !trader && !brokerText && !fl && !stages && !setups.length) return null;
  return (
    <div className="ggw-tags" data-testid={`ggw-tags-${sym}`}>
      <GrowthChip symbol={sym} />
      {siText ? <ShortInterestChip symbol={sym} /> : null}
      {!t ? brokerChip : null}
      {!t ? floatChip : null}
      {t ? (
        <>
          <ExplosiveChip read={room?.explosive} study={study} />
          <EnterableChip read={room?.enterable} />
          <GgTraderChip text={t.trader_text} testid={`ggw-trader-${sym}`}
                        promoText={t.promo_text} promoTestid={`ggw-promo-${sym}`} />
          {brokerChip}
          {floatChip}
          {stages ? <GgStages stages={t.stages} sym={sym} /> : null}
          {setups.map((s) => (
            <span key={s.setup} className="cm-badge cm-badge-muted ggw-setup" data-testid={`ggw-setup-${sym}-${s.setup}`}
                  title={s.state_label ?? undefined}>{s.label}</span>
          ))}
        </>
      ) : null}
    </div>
  );
}
