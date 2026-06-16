import { useState, useMemo } from 'react';
import { RecurringRules } from '../components/RecurringRules';
import { TodoDashboardWidget } from '../components/TodoDashboardWidget';
import { AiResultView } from '../components/AiResultView';
import type { Workspace } from '../hooks/useTodos';
import { useTodos, type Todo } from '../hooks/useTodos';
import { TickerLink } from '../components/TickerLink';
import { InfoButton } from '../components/InfoButton';

/* ==========================================================================
   /todos — personal task list with smart sections + push reminders.
   Layout:
     - Header + filter chips
     - Sectioned list:  ⭐ Important · 📅 Today · 📅 Upcoming · 🌙 Someday · ✓ Done
     - Sticky add bar at bottom — collapsed by default, expands on focus
   ========================================================================== */

const TodosInfo = (
  <>
    <p>
      <strong>Todos</strong> is your personal task shelf — anything you
      want to remember. Errands, calls, deadlines, ideas. Doesn't have
      to be market-related.
    </p>
    <p>
      <strong>⭐ Important</strong> items pin to the top of the list and
      get included in your daily Morning Brief.
    </p>
    <p>
      Add a reminder time and the app fires a push notification at that
      exact minute. Linking a ticker is optional — only useful for
      market-related tasks (the notification tap opens that ticker).
    </p>
  </>
);

function fmtTime(epoch: number | null | undefined): string {
  if (!epoch) return '';
  const d = new Date(epoch * 1000);
  const now = new Date();
  const today = d.toDateString() === now.toDateString();
  const tomorrow = new Date(now); tomorrow.setDate(now.getDate() + 1);
  const isTomorrow = d.toDateString() === tomorrow.toDateString();
  const time = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  if (today) return time;
  if (isTomorrow) return `tomorrow ${time}`;
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function epochFromInput(local: string): number | null {
  if (!local) return null;
  const t = new Date(local).getTime();
  return Number.isFinite(t) ? Math.floor(t / 1000) : null;
}

function inputFromEpoch(epoch: number | null | undefined): string {
  if (!epoch) return '';
  const d = new Date(epoch * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Bucket a todo into a section based on its scheduled time. */
function bucketOf(t: Todo): 'today' | 'upcoming' | 'someday' {
  const ts = t.notify_at ?? t.due_at ?? null;
  if (!ts) return 'someday';
  const d = new Date(ts * 1000);
  const eod = new Date(); eod.setHours(23, 59, 59, 999);
  if (d.getTime() <= eod.getTime()) return 'today';
  return 'upcoming';
}

type FilterKind = 'active' | 'important' | 'all' | 'done';

export default function TodosPage() {
  const [filter, setFilter] = useState<FilterKind>('active');
  // Workspace axis — independent of status filter so a user can flip
  // between Personal / Work / Both without losing their Active/Done
  // selection.
  const [workspace, setWorkspace] = useState<'all' | Workspace>('all');

  const apiStatus: 'all' | 'active' | 'completed' =
    filter === 'done' ? 'completed' : filter === 'all' ? 'all' : 'active';
  const { rows, loading, add, remove, toggle, update, runAi } = useTodos(apiStatus, workspace);

  // Group todos into sections
  const sections = useMemo(() => {
    const visible = filter === 'important'
      ? rows.filter((t) => t.important && t.status === 'active')
      : rows;

    const important = visible.filter((t) => t.important && t.status === 'active');
    const otherActive = visible.filter((t) => !t.important && t.status === 'active');
    const today = otherActive.filter((t) => bucketOf(t) === 'today');
    const upcoming = otherActive.filter((t) => bucketOf(t) === 'upcoming');
    const someday = otherActive.filter((t) => bucketOf(t) === 'someday');
    const done = visible.filter((t) => t.status === 'completed');
    return { important, today, upcoming, someday, done };
  }, [rows, filter]);

  const totalShown =
    sections.important.length + sections.today.length +
    sections.upcoming.length + sections.someday.length +
    (filter === 'done' || filter === 'all' ? sections.done.length : 0);

  return (
    <div className="todos-page">
      <div className="todos-page__title">
        <InfoButton title="Todos">{TodosInfo}</InfoButton>
        <div>
          <div className="eyebrow">Tasks</div>
          <h1 className="display todos-page__h1">Todos</h1>
          <p className="lede">
            Personal tasks. Anything you want to remember.
          </p>
        </div>
      </div>

      {/* Dashboard widget — header-level numbers (open/today/overdue,
          personal/work split, AI task count). Re-fetches whenever the
          row set changes so the stats stay coherent with the list. */}
      <TodoDashboardWidget refreshKey={rows.length} />

      {/* Workspace tabs — separate from the status filter so the user
          can switch between Personal/Work without losing their
          Active/Done selection. */}
      <div className="todos-tabs" style={{ marginBottom: '0.4rem' }}>
        {([
          { k: 'all',      label: 'Both' },
          { k: 'personal', label: '🏠 Personal' },
          { k: 'work',     label: '💼 Work' },
        ] as { k: 'all' | Workspace; label: string }[]).map(({ k, label }) => (
          <button
            key={k}
            className={`sepa-chip ${workspace === k ? 'is-active' : ''}`}
            onClick={() => setWorkspace(k)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Filter tabs */}
      <div className="todos-tabs">
        {([
          { k: 'active', label: `Active${rows.filter(r => r.status === 'active').length ? ` · ${rows.filter(r => r.status === 'active').length}` : ''}` },
          { k: 'important', label: `⭐ Important${rows.filter(r => r.important && r.status === 'active').length ? ` · ${rows.filter(r => r.important && r.status === 'active').length}` : ''}` },
          { k: 'all', label: 'All' },
          { k: 'done', label: 'Done' },
        ] as { k: FilterKind; label: string }[]).map(({ k, label }) => (
          <button key={k}
                  className={`sepa-chip ${filter === k ? 'is-active' : ''}`}
                  onClick={() => setFilter(k)}>
            {label}
          </button>
        ))}
      </div>

      {/* Sectioned list */}
      {loading ? (
        <div className="todos-empty">Loading…</div>
      ) : totalShown === 0 ? (
        <div className="todos-empty">
          {filter === 'active' ? 'No active tasks. Add one below.' :
           filter === 'important' ? 'No important tasks. Star a task to mark it important — it\'ll show in your Morning Brief.' :
           filter === 'done' ? 'Nothing completed yet.' :
           'Your todo list is empty.'}
        </div>
      ) : (
        <>
          {sections.important.length > 0 && (
            <Section icon="⭐" title="Important" tone="important">
              {sections.important.map((t) => (
                <TodoRow key={t._id} todo={t} onToggle={toggle} onRemove={remove} onUpdate={update} onRunAi={runAi} />
              ))}
            </Section>
          )}
          {filter !== 'done' && sections.today.length > 0 && (
            <Section icon="📅" title="Today" tone="today">
              {sections.today.map((t) => (
                <TodoRow key={t._id} todo={t} onToggle={toggle} onRemove={remove} onUpdate={update} onRunAi={runAi} />
              ))}
            </Section>
          )}
          {filter !== 'done' && sections.upcoming.length > 0 && (
            <Section icon="📅" title="Upcoming" tone="upcoming">
              {sections.upcoming.map((t) => (
                <TodoRow key={t._id} todo={t} onToggle={toggle} onRemove={remove} onUpdate={update} onRunAi={runAi} />
              ))}
            </Section>
          )}
          {filter !== 'done' && sections.someday.length > 0 && (
            <Section icon="🌙" title="Someday" tone="someday">
              {sections.someday.map((t) => (
                <TodoRow key={t._id} todo={t} onToggle={toggle} onRemove={remove} onUpdate={update} onRunAi={runAi} />
              ))}
            </Section>
          )}
          {(filter === 'done' || filter === 'all') && sections.done.length > 0 && (
            <Section icon="✓" title="Done" tone="done">
              {sections.done.map((t) => (
                <TodoRow key={t._id} todo={t} onToggle={toggle} onRemove={remove} onUpdate={update} onRunAi={runAi} />
              ))}
            </Section>
          )}
        </>
      )}

      {/* Recurring rules — day-of-week templates that materialize as
          actual todos each morning at 6 AM ET. Lives below the active
          list so the user sees today's items first, then can scroll
          down to manage their weekly schedule (trash Tuesday, volleyball
          Saturday, etc.). */}
      <RecurringRules />

      {/* Sticky add bar — collapsed by default, expands on focus.
          defaultWorkspace pre-selects the bucket based on which
          workspace tab the user is currently looking at. */}
      <AddBar onAdd={add} defaultWorkspace={workspace} />
    </div>
  );
}

function Section({ icon, title, tone, children }: {
  icon: string; title: string; tone: string; children: React.ReactNode;
}) {
  return (
    <section className={`todos-section todos-section--${tone}`}>
      <header className="todos-section__head">
        <span className="todos-section__icon">{icon}</span>
        <span className="todos-section__title">{title}</span>
      </header>
      <ul className="todos-list">{children}</ul>
    </section>
  );
}

/** Default reminder time = 7 AM tomorrow (or 7 AM today if it hasn't happened yet). */
function default7am(): string {
  const now = new Date();
  const target = new Date();
  target.setHours(7, 0, 0, 0);
  if (target.getTime() < now.getTime()) target.setDate(target.getDate() + 1);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${target.getFullYear()}-${pad(target.getMonth() + 1)}-${pad(target.getDate())}T${pad(target.getHours())}:${pad(target.getMinutes())}`;
}

function AddBar({ onAdd, defaultWorkspace }: {
  onAdd: (p: any) => void;
  defaultWorkspace: 'all' | Workspace;
}) {
  const [expanded, setExpanded] = useState(false);
  const [text, setText] = useState('');
  const [notifyAt, setNotifyAt] = useState('');
  const [ticker, setTicker] = useState('');
  const [important, setImportant] = useState(false);
  // Bucket selector — defaults to whichever workspace tab the user is
  // currently viewing. They can override per task without touching the
  // top-level workspace toggle.
  const [bucket, setBucket] = useState<Workspace>(
    defaultWorkspace === 'work' ? 'work' : 'personal',
  );
  const [aiTask, setAiTask] = useState(false);

  // When the form expands, pre-fill the reminder time with 7 AM (today/tomorrow)
  // so users get a sensible default without having to set it every time.
  const onExpand = () => {
    setExpanded(true);
    if (!notifyAt) setNotifyAt(default7am());
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    onAdd({
      text: text.trim(),
      notify_at: epochFromInput(notifyAt),
      ticker: ticker.trim() || null,
      important,
      workspace: bucket,
      ai_task: aiTask,
    });
    setText(''); setNotifyAt(''); setTicker(''); setImportant(false);
    setAiTask(false);
    setExpanded(false);
  };

  return (
    <form className={`todos-add ${expanded ? 'is-expanded' : ''}`} onSubmit={submit}>
      <div className="todos-add__main">
        <button
          type="button"
          className={`todos-add__star ${important ? 'is-on' : ''}`}
          onClick={() => setImportant(!important)}
          title={important ? 'Marked important' : 'Mark important'}
        >
          {important ? '★' : '☆'}
        </button>
        <input
          type="text"
          className="todos-add__text"
          placeholder="Add a task…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onFocus={onExpand}
        />
        <button type="submit" className="todos-add__send" disabled={!text.trim()} title="Add">
          +
        </button>
      </div>
      {expanded && (
        <div className="todos-add__details">
          {/* Workspace bucket — small two-button toggle. Mirrors the
              top-of-page workspace chips so the user can stay aware
              of where this task is going. */}
          <div className="todos-add__field" style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span className="eyebrow">Bucket</span>
            <div style={{ display: 'flex', gap: '0.3rem' }}>
              {(['personal', 'work'] as Workspace[]).map((w) => (
                <button
                  key={w}
                  type="button"
                  onClick={() => setBucket(w)}
                  className={`sepa-chip${bucket === w ? ' is-active' : ''}`}
                  style={{ fontSize: '0.75rem' }}
                >
                  {w === 'personal' ? '🏠 Personal' : '💼 Work'}
                </button>
              ))}
            </div>
          </div>

          <label className="todos-add__field">
            <span className="eyebrow">Remind me at</span>
            <input
              type="datetime-local"
              className="todos-add__input"
              value={notifyAt}
              onChange={(e) => setNotifyAt(e.target.value)}
            />
          </label>
          <label className="todos-add__field">
            <span className="eyebrow">Linked ticker <span className="todos-add__opt">(optional, market-only)</span></span>
            <input
              type="text"
              className="todos-add__input mono"
              placeholder="e.g. NVDA"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              maxLength={10}
            />
          </label>

          {/* AI task toggle — flips the row into the LLM queue. The
              llm_runner cron picks it up within 15 min (or click
              "Run now" from the row once it appears) and writes the
              research note back. Good for "research how tech companies
              build camaraderie" type tasks. */}
          <label className="todos-add__field" style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={aiTask}
              onChange={(e) => setAiTask(e.target.checked)}
              style={{ width: 16, height: 16 }}
            />
            <span style={{ fontSize: '0.84rem' }}>
              🤖 Let the AI research this
              <span style={{ display: 'block', color: 'var(--cm-slate)', fontSize: '0.7rem', marginTop: 1 }}>
                Local Gemma drafts a TL;DR + findings + steps + search queries within ~15 min.
              </span>
            </span>
          </label>

          <button type="button" className="todos-add__collapse"
                  onClick={() => { setExpanded(false); }}>
            ▴ Collapse
          </button>
        </div>
      )}
    </form>
  );
}

function TodoRow({ todo, onToggle, onRemove, onUpdate, onRunAi }: {
  todo: Todo;
  onToggle: (t: Todo) => void;
  onRemove: (id: string) => void;
  onUpdate: (id: string, patch: Partial<Todo>) => void;
  onRunAi?: (id: string) => Promise<any>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(todo.text);
  const [notifyAt, setNotifyAt] = useState(inputFromEpoch(todo.notify_at));
  // AI accordion state — collapsed by default so completed research
  // notes don't push the list around. User taps "View research" to
  // expand.
  const [aiOpen, setAiOpen] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);

  const isCompleted = todo.status === 'completed';
  const overdue = !isCompleted && todo.notify_at && todo.notify_at * 1000 < Date.now();
  const fired = !!todo.notified_at;

  const save = () => {
    onUpdate(todo._id, {
      text: text.trim() || todo.text,
      notify_at: epochFromInput(notifyAt),
    });
    setEditing(false);
  };

  return (
    <li className={`todo-row ${isCompleted ? 'is-done' : ''} ${overdue ? 'is-overdue' : ''} ${todo.important ? 'is-important' : ''}`}>
      <input
        type="checkbox"
        checked={isCompleted}
        onChange={() => onToggle(todo)}
        className="todo-row__check"
        aria-label={isCompleted ? 'Mark active' : 'Mark done'}
      />
      <button
        type="button"
        className={`todo-row__star ${todo.important ? 'is-on' : ''}`}
        onClick={() => onUpdate(todo._id, { important: !todo.important })}
        title={todo.important ? 'Important — click to unstar' : 'Mark important'}
      >
        {todo.important ? '★' : '☆'}
      </button>
      <div className="todo-row__body">
        {editing ? (
          <div className="todo-row__edit">
            <input
              type="text"
              className="todos-add__input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              autoFocus
            />
            <input
              type="datetime-local"
              className="todos-add__input"
              value={notifyAt}
              onChange={(e) => setNotifyAt(e.target.value)}
            />
            <div className="todo-row__edit-actions">
              <button onClick={save} className="todo-action">Save</button>
              <button onClick={() => setEditing(false)} className="todo-action">Cancel</button>
            </div>
          </div>
        ) : (
          <>
            <div className="todo-row__text">
              {/* Provenance chips — workspace + source. Quiet styling so
                  they don't crowd the text, but visible enough to spot
                  "this came from the LLM" without expanding. */}
              {todo.workspace === 'work' && (
                <span style={{ fontSize: '0.62rem', padding: '1px 5px', marginRight: 6, background: 'rgba(59,130,246,0.1)', color: '#60a5fa', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 3 }}>
                  💼 work
                </span>
              )}
              {todo.source && todo.source !== 'manual' && (
                <span style={{ fontSize: '0.62rem', padding: '1px 5px', marginRight: 6, background: 'rgba(212,175,55,0.08)', color: 'var(--warn, #d97706)', border: '1px solid rgba(212,175,55,0.3)', borderRadius: 3 }}>
                  {todo.source === 'claude' || todo.source === 'cron' ? '🤖' : '·'} {todo.source}
                </span>
              )}
              {todo.text}
              {todo.url && (
                <a href={todo.url} target="_blank" rel="noopener noreferrer"
                   onClick={(e) => e.stopPropagation()}
                   style={{ marginLeft: 6, fontSize: '0.72rem', color: '#38bdf8', textDecoration: 'none', whiteSpace: 'nowrap' }}>
                  open ↗
                </a>
              )}
            </div>
            {/* AI brief — shown below the title for completed AI rows.
                Lets the user scan the answer without expanding the
                full research. Quiet color so it doesn't compete with
                the title for attention. */}
            {todo.ai_summary && todo.ai_status === 'done' && (
              <div style={{
                fontSize: '0.82rem',
                color: 'var(--cm-slate)',
                margin: '0.2rem 0 0.15rem',
                lineHeight: 1.45,
                fontStyle: 'italic',
              }}>
                <span style={{ marginRight: 4 }}>🤖</span>
                {todo.ai_summary}
              </div>
            )}
            <div className="todo-row__meta mono">
              {todo.notify_at && (
                <span className={`todo-row__time ${overdue ? 'is-overdue' : ''}`}>
                  {fired ? '✓ fired' : (overdue ? '⚠ overdue' : '⏰')} {fmtTime(todo.notify_at)}
                </span>
              )}
              {todo.ticker && (
                <span className="todo-row__ticker">
                  <TickerLink ticker={todo.ticker} fromLabel="todos" showWatchlist={false} />
                </span>
              )}
              {isCompleted && todo.completed_at && (
                <span className="todo-row__done-at">done {fmtTime(todo.completed_at)}</span>
              )}
              {/* AI status + actions — rendered inline so the user
                  sees both lifecycle state and a one-tap action
                  without expanding the row. Status emoji: ⏳ waiting
                  for cron pickup, ⚡ LLM is generating now, ✓ done,
                  × failed (hover or expand for reason). */}
              {todo.ai_task && (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  {todo.ai_status === 'pending' && <span style={{ color: 'var(--cm-slate)' }}>⏳ AI queued</span>}
                  {todo.ai_status === 'running' && <span style={{ color: 'var(--warn, #d97706)' }}>⚡ AI running…</span>}
                  {todo.ai_status === 'done'    && <span style={{ color: 'var(--positive)' }}>🤖 AI done</span>}
                  {todo.ai_status === 'failed'  && <span style={{ color: 'var(--negative)' }}>× AI failed</span>}
                  {onRunAi && todo.ai_status !== 'running' && (
                    <button
                      type="button"
                      onClick={async () => {
                        setAiBusy(true);
                        try { await onRunAi(todo._id); } finally { setAiBusy(false); }
                      }}
                      disabled={aiBusy}
                      style={{
                        background: 'none',
                        border: '1px solid var(--rule, #555)',
                        color: 'var(--ink, inherit)',
                        padding: '0 6px',
                        borderRadius: 3,
                        cursor: aiBusy ? 'wait' : 'pointer',
                        fontSize: '0.66rem',
                      }}
                      title="Run the LLM now (rather than wait for the next cron tick)."
                    >
                      {aiBusy ? '…' : (todo.ai_status === 'done' ? '↻ re-run' : '▶ run now')}
                    </button>
                  )}
                  {todo.ai_status === 'done' && todo.ai_result && (
                    <button
                      type="button"
                      onClick={() => setAiOpen((v) => !v)}
                      style={{
                        background: 'none',
                        border: '1px solid var(--positive, #10b981)',
                        color: 'var(--positive)',
                        padding: '0 6px',
                        borderRadius: 3,
                        cursor: 'pointer',
                        fontSize: '0.66rem',
                      }}
                    >
                      {aiOpen ? '▴ hide research' : '▾ view research'}
                    </button>
                  )}
                </span>
              )}
            </div>
            {/* Expanded LLM result — full markdown rendered via
                AiResultView so headings, bullets, and search-query
                chips look right. Collapsed by default. */}
            {aiOpen && todo.ai_status === 'done' && todo.ai_result && (
              <div style={{
                marginTop: '0.5rem',
                padding: '0.6rem 0.8rem',
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid var(--rule, #333)',
                borderRadius: 4,
              }}>
                <AiResultView markdown={todo.ai_result} />
              </div>
            )}
            {/* Failure messages are short — surface inline (no
                expand/collapse needed). */}
            {todo.ai_status === 'failed' && todo.ai_result && (
              <div style={{
                marginTop: '0.4rem',
                padding: '0.4rem 0.6rem',
                background: 'rgba(239,68,68,0.06)',
                border: '1px solid rgba(239,68,68,0.3)',
                color: 'var(--negative)',
                borderRadius: 3,
                fontSize: '0.78rem',
              }}>
                {todo.ai_result}
              </div>
            )}
          </>
        )}
      </div>
      {!editing && (
        <div className="todo-row__actions">
          <button onClick={() => setEditing(true)} className="todo-action" title="Edit">✎</button>
          <button onClick={() => onRemove(todo._id)} className="todo-action todo-action--danger" title="Delete">✕</button>
        </div>
      )}
    </li>
  );
}
