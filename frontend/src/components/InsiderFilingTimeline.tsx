/* InsiderFilingTimeline — chronological tape of the SEC filings behind the
   insider-activity tab on the SEPA detail page.

   Ajay 2026-06-03: "add a timeline of these filings", then "update accurately
   to distinguish insiders." Each Form 4 row now shows the filer's relationship
   (Officer / Director / 10% owner) and what the transaction actually was —
   a real open-market Buy (green) vs a Sell (red) vs a grant / option-exercise /
   tax-withholding (muted), so a routine comp event never reads as conviction.

   Data source: data.insider.recent_filings from sepa.insider.insider_activity():
     { form4: Filing[], "13d": Filing[], "13g": Filing[] }
   Form 4 entries carry owner / relationship / title / txn / is_buy / is_sell. */

type Filing = {
  form?: string | null;
  filed?: string | null;
  display_names?: string[] | null;
  owner?: string | null;
  relationship?: string | null;
  title?: string | null;
  txn?: string | null;
  is_buy?: boolean | null;
  is_sell?: boolean | null;
  url?: string | null;
};

export type RecentFilings = {
  form4?: Filing[] | null;
  '13d'?: Filing[] | null;
  '13g'?: Filing[] | null;
};

type Kind = 'form4' | '13d' | '13g';
type Row = Filing & { kind: Kind };

const KIND_META: Record<Kind, { emoji: string; label: string; cls: string }> = {
  form4: { emoji: '👤', label: 'Form 4',  cls: 'insf__row--form4' },
  '13d': { emoji: '⚡', label: 'SC 13D',  cls: 'insf__row--13d' },
  '13g': { emoji: '🏦', label: 'SC 13G',  cls: 'insf__row--13g' },
};

/** Human "x ago" from a YYYY-MM-DD filing date. Empty string if unparseable. */
function agoLabel(filed?: string | null): string {
  if (!filed) return '';
  const d = new Date(`${filed}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return '';
  const days = Math.floor((Date.now() - d.getTime()) / 86_400_000);
  if (days <= 0) return 'today';
  if (days === 1) return '1d ago';
  if (days < 30) return `${days}d ago`;
  const months = Math.round(days / 30);
  return months <= 1 ? '1mo ago' : `${months}mo ago`;
}

/** Strip the "(CIK 0001234567)" suffix EDGAR appends to filer names. */
function cleanName(s?: string | null): string {
  return (s || '').replace(/\s*\(CIK\s*\d+\)\s*$/i, '').trim();
}

function txnClass(r: Row): string {
  if (r.is_buy) return 'insf__txn--buy';
  if (r.is_sell) return 'insf__txn--sell';
  return 'insf__txn--neutral';
}

/** A bold, color-coded category pill so buy vs sell vs routine comp is obvious
 *  at a glance (Form 4 only — 13D/13G are stake filings, not transactions). */
function txnCat(r: Row): { key: 'buy' | 'sell' | 'neutral'; label: string } | null {
  if (r.kind !== 'form4') return null;
  if (r.is_buy) return { key: 'buy', label: 'BUY' };
  if (r.is_sell) return { key: 'sell', label: 'SELL' };
  const t = (r.txn || '').toLowerCase();
  if (t.includes('tax')) return { key: 'neutral', label: 'TAX' };
  if (t.includes('exercise') || t.includes('option')) return { key: 'neutral', label: 'EXERCISE' };
  if (t.includes('grant') || t.includes('award')) return { key: 'neutral', label: 'GRANT' };
  if (t.includes('gift')) return { key: 'neutral', label: 'GIFT' };
  return { key: 'neutral', label: 'NEUTRAL' };
}

export function InsiderFilingTimeline({ recent }: { recent?: RecentFilings | null }) {
  if (!recent) return null;

  const rows: Row[] = [
    ...(recent.form4   ?? []).map((f): Row => ({ ...f, kind: 'form4' })),
    ...(recent['13d']  ?? []).map((f): Row => ({ ...f, kind: '13d'  })),
    ...(recent['13g']  ?? []).map((f): Row => ({ ...f, kind: '13g'  })),
  ].filter((r) => r.filed);

  if (rows.length === 0) return null;

  // Newest first. Dates are ISO YYYY-MM-DD so string compare is chronological.
  rows.sort((a, b) => String(b.filed).localeCompare(String(a.filed)));

  return (
    <div className="insf">
      <div className="insf__title mono">Filing timeline · most recent first</div>
      <ol className="insf__list">
        {rows.map((r, i) => {
          const meta = KIND_META[r.kind];
          const cat = txnCat(r);
          const who = cleanName(r.owner) || cleanName((r.display_names ?? [])[0]) || '—';
          const rel = r.relationship && r.relationship !== '—' ? r.relationship : '';
          return (
            <li key={`${r.kind}-${r.filed}-${i}`} className={`insf__row ${meta.cls}${cat ? ` insf__row--txn-${cat.key}` : ''}`}>
              <span className="insf__dot" aria-hidden="true" />
              <div className="insf__main">
                <div className="insf__line1">
                  <span className="insf__date mono">{r.filed}</span>
                  <span className="insf__badge">{meta.emoji} {meta.label}</span>
                  {cat && <span className={`insf__pill insf__pill--${cat.key}`}>{cat.label}</span>}
                  <span className="insf__who" title={who}>{who}</span>
                  {r.url && (
                    <a
                      className="insf__lnk"
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                    >SEC ↗</a>
                  )}
                </div>
                <div className="insf__line2">
                  {rel && (
                    <span className="insf__rel" title={r.title || undefined}>
                      {rel}{r.title ? ` · ${r.title}` : ''}
                    </span>
                  )}
                  {r.txn && <span className={`insf__txn ${txnClass(r)}`}>{r.txn}</span>}
                  <span className="insf__ago mono">{agoLabel(r.filed)}</span>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      <div className="insf__legend mono">
        <span className="insf__txn--buy">● Buy</span>
        <span className="insf__txn--sell">● Sell</span>
        <span className="insf__txn--neutral">● Grant / exercise / tax</span>
      </div>
    </div>
  );
}
