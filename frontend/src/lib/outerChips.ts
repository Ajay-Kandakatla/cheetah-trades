/* 📋 outerChipsFor — which chips the WRAPPER prints so the tile skips its own
 * copy (Chart Maps card entry ladder, repair 2026-09-25). Kept out of
 * lib/cardLadder.ts, whose contract keeps it strings-only and free of the
 * room module. */
import type { CmTile } from './chartMaps';
import type { OuterChip } from './cardLadder';
import { enterableChipText, type EnterableRead } from './enterable';
import { explosiveChipText, type ExplosiveRead, type ExplosiveStudy } from './bounceRoom';

/* ── Outer chips (repair 2026-09-25) ────────────────────────────────────────
 * A wrapper (Support sl-head, POTUS head, 9 EMA strip) prints 🚀 🎪 🧨 🎯 for
 * the same symbol. 🚀 / 🎪 / + Signals are the same component on the same
 * symbol, so skipping the tile's copy is equality by construction. 🎯 and 🧨
 * are NOT: the wrapper's read comes from the room endpoint (its own snapshot, absent
 * while loading or after a failed POST), the tile's from the served tile. The
 * tile's copy is skipped ONLY when both chips print the identical string —
 * otherwise both print (dedupe only on equality; nothing removed). */
export function outerChipsFor(
  base: ReadonlyArray<OuterChip>,
  tile: Pick<CmTile, 'enterable' | 'explosive'> | null | undefined,
  outer: {
    enterable?: EnterableRead | null;
    explosive?: ExplosiveRead | null;
    outerStudy?: ExplosiveStudy | null;
    tileStudy?: ExplosiveStudy | null;
  },
): ReadonlyArray<OuterChip> {
  const entSame = (enterableChipText(outer.enterable)?.text ?? null)
    === (enterableChipText(tile?.enterable)?.text ?? null);
  const expSame = (explosiveChipText(outer.explosive, outer.outerStudy)?.text ?? null)
    === (explosiveChipText(tile?.explosive, outer.tileStudy)?.text ?? null);
  if (entSame && expSame) return base;            // same reference: PatternChart's memo holds
  /* One cached array per (base, variant), so a re-render of the wrapper hands
   * PatternChart the same prop and its memo still holds. */
  const key = `${entSame ? 1 : 0}${expSame ? 1 : 0}`;
  let byKey = CACHE.get(base);
  if (!byKey) { byKey = new Map(); CACHE.set(base, byKey); }
  let hit = byKey.get(key);
  if (!hit) {
    hit = base.filter((c) => (c === 'enterable' ? entSame : c === 'explosive' ? expSame : true));
    byKey.set(key, hit);
  }
  return hit;
}
const CACHE = new WeakMap<ReadonlyArray<OuterChip>, Map<string, ReadonlyArray<OuterChip>>>();
