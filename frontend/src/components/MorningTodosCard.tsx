import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';

/* ==========================================================================
   MorningTodosCard — Personal todos slice on the Morning Brief page.
   Pulls /todos/brief-slice (important + today's items) and renders inline.
   ========================================================================== */

type Todo = {
  _id: string;
  text: string;
  notify_at: number | null;
  due_at: number | null;
  ticker: string | null;
  important: boolean;
};

type BriefSlice = { important: Todo[]; today: Todo[]; upcoming_count: number };

function fmtTime(epoch: number | null | undefined): string {
  if (!epoch) return '';
  const d = new Date(epoch * 1000);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const time = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  if (isToday) return time;
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export function MorningTodosCard() {
  const [data, setData] = useState<BriefSlice | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/todos/brief-slice`)
      .then((r) => r.json())
      .then((j: BriefSlice) => { if (alive) setData(j); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  if (loading) return null;
  const total = (data?.important?.length ?? 0) + (data?.today?.length ?? 0);
  if (total === 0 && (data?.upcoming_count ?? 0) === 0) {
    return null;  // hide entirely when there's nothing to surface
  }

  return (
    <div className="morning-card">
      <header className="morning-card__head">
        <h3 className="morning-card__title">📌 Today's tasks</h3>
        <Link to="/todos" className="mono morning-card__verdict morning-card__verdict--warn">
          {total} active
        </Link>
      </header>

      <div className="brief-todos">
        {data?.important && data.important.length > 0 && (
          <div className="brief-todos__group">
            <div className="brief-todos__group-title">⭐ Important</div>
            {data.important.slice(0, 5).map((t) => (
              <div key={t._id} className="brief-todos__row is-important">
                <span className="star">★</span>
                <span>{t.text}</span>
                {t.ticker && <Link to={`/sepa/${t.ticker}`} className="mono">{t.ticker}</Link>}
                {t.notify_at && <span className="when">⏰ {fmtTime(t.notify_at)}</span>}
              </div>
            ))}
          </div>
        )}

        {data?.today && data.today.length > 0 && (
          <div className="brief-todos__group">
            <div className="brief-todos__group-title" style={{ color: 'var(--cm-amber, #b87900)' }}>
              📅 Due today
            </div>
            {data.today.slice(0, 5).map((t) => (
              <div key={t._id} className="brief-todos__row">
                <span>{t.text}</span>
                {t.ticker && <Link to={`/sepa/${t.ticker}`} className="mono">{t.ticker}</Link>}
                {t.notify_at && <span className="when">⏰ {fmtTime(t.notify_at)}</span>}
              </div>
            ))}
          </div>
        )}

        {(data?.upcoming_count ?? 0) > 0 && (
          <div className="brief-todos__more">
            +{data?.upcoming_count} upcoming · <Link to="/todos">view all</Link>
          </div>
        )}
      </div>
    </div>
  );
}
