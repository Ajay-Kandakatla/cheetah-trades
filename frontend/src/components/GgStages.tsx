import { Fragment } from 'react';
import type { GgStageTag, GgStages as GgStagesBlock } from '../lib/gajjala';

/**
 * 🧭 Setup stages on every Gajjala card (2026-11-11, stages spec §3.5).
 *
 * Ajay 2026-11-11: "Another big thing I need is what stages a stock has crossed in the past like Bullflag -> EMA Kiss
 * and Fly -> and Horizontal -Fade so I know their stages may be add them like tags or some UI to show me stages with
 * time stamps if its same day"
 *
 * Display only. Every word is SERVED (backend chart_maps/gajjala/stages.py): the title, each session's label, each
 * tag's text and the arrow between tags. The FE types none — no step word, no clock, no date, no arrow. A group with no
 * tag carrying served text is skipped; no tag at all → nothing renders.
 */
const served = (x: unknown): x is string => typeof x === 'string' && x.trim() !== '';

export function GgStages({ stages, sym }: { stages: GgStagesBlock | null | undefined; sym: string }) {
  if (!stages || typeof stages !== 'object' || !served(stages.title)) return null;
  const groups = (Array.isArray(stages.groups) ? stages.groups : [])
    .filter((g) => g && typeof g === 'object')
    .map((g) => ({
      g,
      tags: (Array.isArray(g.tags) ? g.tags : []).filter((t): t is GgStageTag => !!t && typeof t === 'object' && served(t.text)),
    }))
    .filter((x) => x.tags.length > 0);
  if (!groups.length) return null;
  const sep = served(stages.sep) ? stages.sep : null;
  let n = 0;
  /** The served arrow before every tag but the very first, across groups too (it leads a new session's label). */
  const arrow = (k: string) => {
    const first = n === 0;
    n += 1;
    return !first && sep ? <span key={k} className="gg-stage-sep" aria-hidden>{sep}</span> : null;
  };
  return (
    <div
      className="gg-stages"
      data-testid={`gg-stages-${sym}`}
      title={served(stages.hint) ? stages.hint : undefined}
      aria-label={served(stages.text) ? stages.text : undefined}
    >
      <span className="gg-stages-title">{stages.title}</span>
      {groups.map(({ g, tags }, gi) => (
        <Fragment key={`${gi}-${g.date}`}>
          {arrow(`${gi}-sep`)}
          {served(g.label) ? (
            <span className="gg-stage-day" data-testid={`gg-stage-day-${sym}-${g.date}`}>{g.label}</span>
          ) : null}
          {tags.map((t, ti) => (
            <Fragment key={`${gi}-${ti}-${t.setup}`}>
              {ti > 0 ? arrow(`${gi}-${ti}-sep`) : null}
              <span
                className={t.here === true ? 'cm-badge gg-stage gg-stage-here' : 'cm-badge gg-stage'}
                data-testid={`gg-stage-${sym}-${g.date}-${t.setup}`}
              >
                {t.text}
              </span>
            </Fragment>
          ))}
        </Fragment>
      ))}
    </div>
  );
}
