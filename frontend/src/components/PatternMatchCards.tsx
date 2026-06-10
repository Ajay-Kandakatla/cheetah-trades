/* PatternMatchCards — the tiny-card pattern view (Ajay 2026-06-09: "show the
 * pattern as small tiny cards with some information of buyable or enter
 * position, similar to what SEPA does, with minimal information; and the
 * pattern that is buyable the most and qualifies all the other Minervini
 * rules" — on Patterns, Portfolio AND Leaderboard).
 *
 * One compact card per pattern-matched name from the latest verdict scan.
 * Ranking puts the confluence first: ⭐ confirmed pattern AND clears the full
 * Minervini buy gate, then confirmed+qualifier, confirmed, forming+buyable,
 * forming. Minimal card: symbol · pattern ✓/… · buyable badge · line→target,
 * stop · RS/Stage · ⚠ bearish read when the candles disagree.
 * Click card → /sepa/{sym}. Fails quiet when no verdict scan exists yet. */
import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { usePatternVerdicts, type PatternVerdict } from '../hooks/usePatternVerdicts';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280', gold: 'var(--gold,#c9a227)' };
const SHORT: Record<string, string> = {
  double_bottom: 'Double bottom', triple_bottom: 'Triple bottom',
  inverse_head_shoulders: 'Inv H&S', cup_with_handle: 'Cup w/ handle',
};

/** Confluence rank — lower is better. 0 = the headline case: a CONFIRMED
 *  pattern on a name that clears the FULL Minervini buy gate right now. */
function rank(v: PatternVerdict): number {
  const conf = v.matches.some((m) => m.status === 'confirmed');
  const buy = !!v.sepa?.is_buyable;
  const qual = !!v.sepa?.is_candidate;
  if (conf && buy) return 0;
  if (conf && qual) return 1;
  if (conf) return 2;
  if (buy) return 3;
  if (qual) return 4;
  return 5;
}

export function PatternMatchCards({ title = '📐 Pattern matches', limit, filterSources, allLink = true }: {
  title?: string; limit?: number; filterSources?: string[]; allLink?: boolean;
}) {
  const navigate = useNavigate();
  const { verdicts, generatedAt } = usePatternVerdicts();

  const rows = useMemo(() => {
    let list = [...verdicts.values()].filter((v) => v.matches.length > 0);
    if (filterSources?.length) {
      list = list.filter((v) => (v.sources || []).some((s) => filterSources.includes(s)));
    }
    list.sort((a, b) => rank(a) - rank(b)
      || ((b.sepa?.rs_rank ?? 0) - (a.sepa?.rs_rank ?? 0)));
    return list;
  }, [verdicts, filterSources]);

  if (!rows.length) return null;   // no scan yet, or nothing matched — fail quiet
  const shown = limit ? rows.slice(0, limit) : rows;
  const starCount = rows.filter((v) => rank(v) === 0).length;

  return (
    <section style={{ margin: '0.9rem 0' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 6 }}>
        <span className="eyebrow">{title}</span>
        <span style={{ fontSize: '0.68rem', color: C.sub }}>
          {starCount > 0
            ? `${starCount} name${starCount === 1 ? '' : 's'} ⭐ confirmed pattern + full Minervini buy gate`
            : 'none currently pair a confirmed pattern with the full Minervini buy gate'}
          {generatedAt ? ` · scan ${new Date(generatedAt * 1000).toLocaleTimeString()}` : ''}
        </span>
        {allLink && (
          <Link to="/patterns" style={{ marginLeft: 'auto', fontSize: '0.68rem', color: C.gold }}>
            all verdicts →
          </Link>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(168px, 1fr))', gap: 7 }}>
        {shown.map((v) => {
          const m = v.matches[0];
          const conf = m.status === 'confirmed';
          const star = rank(v) === 0;
          const s = v.sepa || {};
          const bearish = (v.candles?.formations || []).some((f) => f.read === 'bearish_warning');
          const col = star ? C.green : conf ? `${'#10b981'}` : C.amber;
          return (
            <div key={v.symbol}
                 role="button" tabIndex={0}
                 onClick={() => navigate(`/sepa/${encodeURIComponent(v.symbol)}`)}
                 onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigate(`/sepa/${encodeURIComponent(v.symbol)}`); }}
                 title={`${SHORT[m.pattern] || m.pattern} — ${conf ? `confirmed ${m.confirmed_date || ''}` : `forming, ${m.to_confirm_pct}% to the line`}. Open the full SEPA read.`}
                 style={{ padding: '0.45rem 0.55rem', borderRadius: 9, cursor: 'pointer',
                          background: star ? 'rgba(16,185,129,0.07)' : 'var(--bg-raised,#16181d)',
                          border: `1px solid ${star ? C.green : conf ? '#10b98155' : '#f59e0b44'}` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <b style={{ fontSize: '0.86rem' }}>{v.symbol}</b>
                {star && <span title="Confirmed pattern AND clears the full Minervini buy gate (Stage 2 + setup + volume + buy zone)">⭐</span>}
                <span style={{ marginLeft: 'auto', fontSize: '0.62rem', fontWeight: 700,
                               color: s.is_buyable ? C.green : s.is_candidate ? C.muted : C.sub }}>
                  {s.is_buyable ? '✅ BUYABLE' : s.is_candidate ? 'qualifier' : 'watch'}
                </span>
              </div>
              <div style={{ fontSize: '0.7rem', color: col, fontWeight: 600, marginTop: 1 }}>
                📐 {SHORT[m.pattern] || m.pattern} {conf ? '✓' : `· ${m.to_confirm_pct}% to line`}
              </div>
              <div style={{ fontSize: '0.66rem', color: C.muted, marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
                line {m.neckline} → tgt {m.target} · <span style={{ color: C.red }}>stop {m.stop}</span>
              </div>
              <div style={{ fontSize: '0.62rem', color: C.sub, marginTop: 2, display: 'flex', gap: 8 }}>
                {s.rs_rank != null && <span>RS {s.rs_rank}</span>}
                {s.stage != null && <span style={{ color: s.stage !== 2 ? C.amber : undefined }}>Stg {s.stage}</span>}
                {(v.sources || []).includes('holding') && <span>💼</span>}
                {bearish && <span style={{ color: C.red }} title="Recent daily candles printed a bearish read — check before entering">⚠ bearish read</span>}
              </div>
            </div>
          );
        })}
      </div>
      {limit != null && rows.length > shown.length && (
        <div style={{ fontSize: '0.66rem', color: C.sub, marginTop: 4 }}>
          +{rows.length - shown.length} more on the <Link to="/patterns" style={{ color: C.gold }}>Patterns page</Link>
        </div>
      )}
    </section>
  );
}
