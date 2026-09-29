/* ⓘ Quality on 🔥 Hottest (2026-09-28).
 *
 * Ajay 2026-09-28: "can you help with info icon on the quality?"
 *
 * EVERY word and number in the body comes from the payload's `quality_info`
 * block, built by backend/sepa/earnings_quality_info.py from the constants
 * earnings_quality.compute() itself enforces and pinned against it by a test.
 * Nothing about the score is typed here: a second description on a second
 * surface is how an explainer drifts from the code it explains. A contract
 * keeps numbers and citations out of this file. */

export type HsQualityPoint = { key: string; label: string; max: number; rule: string };
export type HsQualityPenalty = { key: string; label: string; points: number; rule: string };
export type HsQualityTier = { key: string; label: string; rule: string };
export type HsQualityMark = { mark: string; rule: string };
export type HsQualityAsOf = { oldest: string; newest: string; n: number; note?: string | null };
export type HsQualityInfo = {
  version?: number;
  title?: string;
  summary?: string;
  measured?: boolean;
  measured_note?: string;
  weights_note?: string;
  points?: HsQualityPoint[];
  penalties?: HsQualityPenalty[];
  ceiling_today?: number;
  ceiling_note?: string;
  tiers?: HsQualityTier[];
  tier_note?: string;
  marks?: HsQualityMark[];
  blank?: string[];
  group_rows?: string;
  fundamentals_as_of?: HsQualityAsOf | null;
  source?: string;
};

/** Draw the ⓘ? Only when the server served an explainer with points in it. */
export function showQualityInfo(d?: { quality_info?: HsQualityInfo | null } | null): boolean {
  return !!d?.quality_info?.points?.length;
}

/** A Quality cell's hover: the SERVED tier label ("Red flag"), or the raw tier
 *  key when no explainer came back — exactly what the hover printed before. */
export function tierLabel(tier: string | null | undefined,
                          info?: HsQualityInfo | null): string | undefined {
  if (!tier) return undefined;
  const hit = (info?.tiers || []).find((t) => t.key === tier);
  return hit?.label || tier;
}

export function HottestQualityInfo({ info }: { info: HsQualityInfo }) {
  const asOf = info.fundamentals_as_of;
  return (
    <div className="hs-qi">
      {info.measured_note ? <p><b>{info.measured_note}</b></p> : null}
      {info.summary ? <p>{info.summary}</p> : null}

      {(info.points || []).length ? (
        <table className="hs-qi-table">
          <tbody>
            {(info.points || []).map((p) => (
              <tr key={p.key}>
                <th scope="row">{p.label}</th>
                <td className="mono">{p.max} pts</td>
                <td>{p.rule}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      {(info.penalties || []).length ? (
        <table className="hs-qi-table">
          <tbody>
            {(info.penalties || []).map((p) => (
              <tr key={p.key}>
                <th scope="row">{p.label}</th>
                <td className="mono">−{p.points} pts</td>
                <td>{p.rule}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      {info.ceiling_note ? <p className="hs-qi-note">{info.ceiling_note}</p> : null}

      {(info.tiers || []).length ? (
        <ul>
          {(info.tiers || []).map((t) => (
            <li key={t.key}><b>{t.label}</b> — {t.rule}</li>
          ))}
        </ul>
      ) : null}
      {info.tier_note ? <p className="hs-qi-note">{info.tier_note}</p> : null}

      {(info.marks || []).length ? (
        <ul>
          {(info.marks || []).map((m) => (
            <li key={m.mark}><b>{m.mark}</b> {m.rule}</li>
          ))}
        </ul>
      ) : null}

      {(info.blank || []).length ? (
        <ul>
          {(info.blank || []).map((b) => <li key={b}>— {b}</li>)}
        </ul>
      ) : null}

      {info.group_rows ? <p className="hs-qi-note">{info.group_rows}</p> : null}

      {asOf ? (
        <p className="hs-qi-note" data-testid="hs-qi-asof">
          cached {asOf.oldest} → {asOf.newest} ET{asOf.note ? ` · ${asOf.note}` : ''}
        </p>
      ) : null}

      {info.weights_note ? <p className="hs-qi-note">{info.weights_note}</p> : null}
    </div>
  );
}
