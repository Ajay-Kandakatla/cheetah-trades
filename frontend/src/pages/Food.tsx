import { useEffect, useMemo, useState } from 'react';
import {
  useFoodToday, useFoodHistory, useGrocery,
  logCooked, getRecipeMap,
  type Recipe, type DailyOption,
} from '../hooks/useFood';

export default function FoodPage() {
  // "Quick night" — when toggled on, the planner hard-filters to recipes
  // that cook in ≤30 min without heavy prep (no methi paratha, no paya).
  // Persisted in localStorage so the preference survives reloads.
  const [quickOnly, setQuickOnly] = useState<boolean>(() => {
    try { return localStorage.getItem('food.quickOnly') === '1'; }
    catch { return false; }
  });
  useEffect(() => {
    try { localStorage.setItem('food.quickOnly', quickOnly ? '1' : '0'); }
    catch { /* quota — ignore */ }
  }, [quickOnly]);

  const { data: today, loading, allowed, reload } = useFoodToday(quickOnly);
  const { rows: history, reload: reloadHistory } = useFoodHistory(14);
  const { data: grocery, reload: reloadGrocery } = useGrocery();

  // Stealth 404 for non-household members. Same pattern as /house.
  if (!allowed) {
    return (
      <div style={{ padding: '4rem 2rem', textAlign: 'center', color: 'var(--cm-slate)' }}>
        <h1 className="display" style={{ margin: 0 }}>404</h1>
        <p className="lede" style={{ marginTop: '0.5rem' }}>Page not found.</p>
      </div>
    );
  }

  const [recipeMap, setRecipeMap] = useState<Map<string, Recipe>>(new Map());
  useEffect(() => { getRecipeMap().then(setRecipeMap); }, []);

  const [tab, setTab] = useState<'today' | 'history' | 'grocery'>('today');

  return (
    <div className="food-page">
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <div className="eyebrow">Family · Meal Planner</div>
          <h1 className="display" style={{ margin: '0.25rem 0 0' }}>Today's Menu</h1>
          {today && (
            <p className="lede" style={{ margin: '0.4rem 0 0' }}>
              {today.date_et} · {today.is_weekend ? '🏖️ Weekend window — paya / biryani fair game' : 'Weekday — quick mains'}
              · iron this week: <strong>{today.history_summary.recent_iron_count}</strong>
              {' '}/ target {today.history_summary.iron_focus_target}
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`sepa-chip ${quickOnly ? 'is-active' : ''}`}
            onClick={() => setQuickOnly((v) => !v)}
            title={
              quickOnly
                ? "Quick mode: planner only suggests recipes that cook in ≤30min without heavy prep. Tap to turn off."
                : "Tap for tired-weeknight mode — only quick recipes (Phulka + curry, kheema, dals + rice). No methi paratha, no paya."
            }
          >
            ⚡ {quickOnly ? 'Quick night ON' : 'Quick night'}
          </button>
          <button className="sepa-btn" onClick={() => { reload(); reloadHistory(); reloadGrocery(); }}>↻ Refresh</button>
        </div>
      </div>

      {/* Tabs */}
      <nav style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', borderBottom: '1px solid var(--rule, #ddd)' }}>
        {(['today', 'history', 'grocery'] as const).map((t) => (
          <button
            key={t}
            className={`sepa-btn ${tab === t ? 'sepa-btn--primary' : ''}`}
            onClick={() => setTab(t)}
            style={{ borderRadius: '4px 4px 0 0', borderBottom: tab === t ? '2px solid var(--ink)' : 'none' }}
          >
            {t === 'today' ? "Today's options" : t === 'history' ? 'Last 14 days' : 'Grocery list'}
          </button>
        ))}
      </nav>

      {loading && <p style={{ marginTop: '1rem' }}>Loading menu…</p>}

      {tab === 'today' && today && (
        <>
          {/* Two adult options — side by side on desktop, stacked on phone */}
          <div className="food-options-grid">
            {today.options.map((opt) => (
              <OptionCard key={opt.label} opt={opt} onLogged={() => { reload(); reloadHistory(); reloadGrocery(); }} />
            ))}
          </div>

          {/* Kid breakfast — 3 fresh options */}
          <KidBreakfastCard
            options={today.kid_breakfast_options}
            onLogged={() => { reload(); reloadHistory(); reloadGrocery(); }}
          />

          {/* Weekend eat-out / buffet picks — only renders Sat/Sun. Family
              goes out weekends, so this is the "skip cooking" path. */}
          {today.is_weekend && today.eat_out && today.eat_out.length > 0 && (
            <EatOutCard picks={today.eat_out} />
          )}
        </>
      )}

      {tab === 'history' && (
        <HistoryView rows={history} recipeMap={recipeMap} />
      )}

      {tab === 'grocery' && grocery && (
        <GroceryView grocery={grocery} />
      )}
    </div>
  );
}

/* ============================================================================
   One full-day option (Option A or B)
   ========================================================================== */
function OptionCard({ opt, onLogged }: { opt: DailyOption; onLogged: () => void }) {
  const [busy, setBusy] = useState(false);
  const cookEverything = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const adultIds = opt.adult_breakfast.map((r) => r.id);
      const kidIds = opt.kid_breakfast.map((r) => r.id);
      const dinnerIds = [
        ...opt.dinner.main, ...opt.dinner.side, ...opt.dinner.charu, ...opt.dinner.protein_side,
      ].map((r) => r.id);
      if (adultIds.length)  await logCooked('adult_breakfast', adultIds);
      if (kidIds.length)    await logCooked('kid_breakfast',   kidIds);
      if (dinnerIds.length) await logCooked('dinner',          dinnerIds);
      onLogged();
    } finally { setBusy(false); }
  };

  return (
    <section style={{ padding: '1rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div className="eyebrow">{opt.label}</div>
        <span className="mono" style={{ fontSize: '0.74rem', color: 'var(--positive, #15803d)' }}>
          🩸 {opt.iron_total_mg.toFixed(1)}mg iron
        </span>
      </div>

      <Slot label="Adult breakfast" recipes={opt.adult_breakfast} slot="adult_breakfast" onLogged={onLogged} />
      <Slot label="Kid breakfast"   recipes={opt.kid_breakfast}   slot="kid_breakfast"   onLogged={onLogged} />
      <Slot label="Dinner — Main"             recipes={opt.dinner.main}         slot="dinner" onLogged={onLogged} />
      <Slot label="Dinner — Side"             recipes={opt.dinner.side}         slot="dinner" onLogged={onLogged} />
      <Slot label="Dinner — Charu"            recipes={opt.dinner.charu}        slot="dinner" onLogged={onLogged} />
      <Slot label="🔥 Daily protein (air fryer)"
            recipes={opt.dinner.protein_side} slot="dinner" onLogged={onLogged} />

      <div style={{ marginTop: '0.7rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <button className="sepa-btn sepa-btn--primary" onClick={cookEverything} disabled={busy}>
          {busy ? '…logging' : '✓ Cooked this option (logs all 3 slots)'}
        </button>
        <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--cm-slate)' }}>
          dinner = next-day lunch
        </span>
      </div>
    </section>
  );
}

function Slot({ label, recipes, slot, onLogged }: {
  label: string; recipes: Recipe[]; slot: string; onLogged: () => void;
}) {
  if (!recipes || recipes.length === 0) return null;
  const logOne = async (id: string) => { await logCooked(slot, [id]); onLogged(); };
  return (
    <div style={{ marginTop: '0.7rem', paddingTop: '0.55rem', borderTop: '1px dashed var(--hairline, #eee)' }}>
      <div className="mono" style={{ fontSize: '0.68rem', color: 'var(--cm-slate)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {label}
      </div>
      {recipes.map((r) => (
        <RecipeRow key={r.id} r={r} onLog={() => logOne(r.id)} />
      ))}
    </div>
  );
}

function RecipeRow({ r, onLog }: { r: Recipe; onLog: () => void }) {
  // Use YouTube hqdefault when available — already validated by the resolver,
  // already CDN-served at i.ytimg.com (zero scraping risk). Fall back to an
  // emoji placeholder when no video is cached yet.
  const thumbUrl = r.validated_video?.video_id
    ? `https://i.ytimg.com/vi/${r.validated_video.video_id}/mqdefault.jpg`
    : null;
  const fallbackEmoji =
    r.protein === 'goat'    ? '🐐' :
    r.protein === 'chicken' ? '🍗' :
    r.protein === 'fish'    ? '🐟' :
    r.protein === 'paneer'  ? '🧀' :
    r.protein === 'egg'     ? '🥚' :
    r.protein === 'dal'     ? '🥣' :
    r.type === 'rasam'      ? '🍲' :
                              '🥘';

  return (
    <div className="food-recipe-row">
      <a
        href={r.validated_video?.video_url || '#'}
        target="_blank"
        rel="noreferrer"
        className="food-recipe-row__thumb"
        title={r.validated_video
          ? `${r.validated_video.title} · ${r.validated_video.author_name}`
          : 'Tap to search for this recipe'}
        onClick={(e) => { if (!r.validated_video) e.preventDefault(); }}
      >
        {thumbUrl ? (
          <img
            src={thumbUrl}
            alt={r.name}
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={(e) => {
              // YouTube returns a tiny grey placeholder when a video is
              // dead — swap to the emoji fallback when that happens.
              const img = e.currentTarget;
              if (img.naturalWidth < 200) {
                img.style.display = 'none';
                img.parentElement?.classList.add('food-recipe-row__thumb--fallback');
              }
            }}
          />
        ) : null}
        <span className="food-recipe-row__thumb-emoji">{fallbackEmoji}</span>
      </a>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: '0.92rem' }}>{r.name}</div>
        <div className="mono" style={{ fontSize: '0.68rem', color: 'var(--cm-slate)' }}>
          {r.cuisine} · {r.prep_min}min{r.iron_mg ? ` · 🩸 ${r.iron_mg.toFixed(1)}mg` : ''}
          {r.quick && ' · ⚡ quick'}
          {r.lunch_next_day && ' · 🍱 cook extra → lunch tomorrow'}
          {r.tags?.includes('weekend') && ' · 🏖️ weekend'}
          {r.iron_rich && ' · iron-rich'}
          {r.probiotic && ' · probiotic'}
          {r.citrus && ' · citrus'}
        </div>
        {r._reasons && r._reasons.length > 0 && (
          <div className="mono" style={{ fontSize: '0.66rem', color: 'var(--ink-muted)', fontStyle: 'italic', marginTop: 1 }}>
            {r._reasons.join(' · ')}
          </div>
        )}
        {/* Recipe links — always rendered as SEARCH QUERIES rather than
            hardcoded URLs. The hardcoded URLs in recipes.py are
            AI-generated guesses and many 404'd in practice. Search
            queries always land on currently-live pages. The cuisine
            keyword + family-trusted blog filters get you to the right
            result in the top 1-3 hits. */}
        <div className="food-recipe-row__links">
          <a
            href={`https://www.google.com/search?q=${encodeURIComponent(
              r.name + ' recipe ' + (r.cuisine || '')
            )}`}
            target="_blank"
            rel="noreferrer"
            className="food-link food-link--recipe"
            title="Opens Google with the recipe name — first hit is usually Hebbar's Kitchen, Swasthi's Recipes, Vismai Food, or VahChef."
          >
            📖 Recipe
          </a>
          {/* Validated direct video link when the resolver has cached one
              (Gemma picked + oEmbed-confirmed live). Otherwise fall back
              to a YouTube search query. The validated path always wins
              because it goes straight to the right video. */}
          {r.validated_video ? (
            <a
              href={r.validated_video.video_url}
              target="_blank"
              rel="noreferrer"
              className="food-link food-link--video food-link--validated"
              title={`✓ Validated · ${r.validated_video.author_name} — ${r.validated_video.title}`}
            >
              ▶ {r.validated_video.author_name}
            </a>
          ) : (
            <a
              href={`https://www.youtube.com/results?search_query=${encodeURIComponent(
                r.name + ' recipe ' + (r.cuisine || '')
              )}`}
              target="_blank"
              rel="noreferrer"
              className="food-link food-link--video"
              title="Opens YouTube search — pick whichever channel you trust (Vismai Food, VahChef, Amma Chethi Vanta, Hebbar's, etc). Validated video not yet cached for this recipe."
            >
              ▶ Video search
            </a>
          )}
        </div>
      </div>
      <button onClick={onLog} title="Log just this dish as cooked"
              className="food-cooked-btn">
        ✓ cooked
      </button>
    </div>
  );
}

/* ============================================================================
   Kid breakfast — 3 fresh options every morning
   ========================================================================== */
function KidBreakfastCard({ options, onLogged }: { options: Recipe[]; onLogged: () => void }) {
  if (!options || options.length === 0) return null;
  return (
    <section style={{ marginTop: '1rem', padding: '1rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div className="eyebrow">Daughter's fresh breakfast — 3 options</div>
      <p style={{ fontSize: '0.78rem', color: 'var(--cm-slate)', margin: '0.3rem 0 0.6rem' }}>
        Probiotic-leaning (idli/dosa/uttapam), mild, fresh-cooked. Pick whichever you have batter for today.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.6rem' }}>
        {options.map((r) => (
          <div key={r.id} style={{ padding: '0.6rem 0.7rem', border: '1px solid var(--hairline)', borderRadius: 4 }}>
            <RecipeRow r={r} onLog={async () => { await logCooked('kid_breakfast', [r.id]); onLogged(); }} />
          </div>
        ))}
      </div>
    </section>
  );
}

/* ============================================================================
   Weekend eat-out picks — DFW Indian buffets + out-of-the-box options
   ========================================================================== */
function EatOutCard({ picks }: { picks: import('../hooks/useFood').EatOutPick[] }) {
  return (
    <section style={{ marginTop: '1rem', padding: '1rem 1.1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)' }}>
      <div className="eyebrow">🍽️ Weekend — go out tonight?</div>
      <p style={{ fontSize: '0.78rem', color: 'var(--cm-slate)', margin: '0.3rem 0 0.7rem' }}>
        DFW Indian + out-of-the-box picks within ~25 min. Tap for current hours / menu / reviews.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.6rem' }}>
        {picks.map((p) => (
          <div key={p.id} style={{ padding: '0.7rem 0.85rem', border: '1px solid var(--hairline)', borderRadius: 5, background: 'var(--bg-surface, var(--bg-raised))' }}>
            <div style={{ fontSize: '1.4rem', marginBottom: 2 }}>{p.emoji}</div>
            <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>
              {p.name}
              {p.buffet && <span className="mono" style={{ marginLeft: 6, fontSize: '0.62rem', padding: '1px 5px', border: '1px solid var(--hairline)', borderRadius: 3, color: 'var(--positive, #15803d)' }}>BUFFET</span>}
            </div>
            <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: 2 }}>
              {p.cuisine} · {p.area}
            </div>
            <div style={{ fontSize: '0.78rem', marginTop: '0.35rem', color: 'var(--ink-muted)' }}>
              {p.vibe}
            </div>
            <div className="food-recipe-row__links" style={{ marginTop: '0.45rem' }}>
              <a href={p.google_maps} target="_blank" rel="noreferrer" className="food-link food-link--recipe" title="Google Maps — current hours, directions, reviews">
                📍 Maps
              </a>
              <a href={p.yelp} target="_blank" rel="noreferrer" className="food-link food-link--video" title="Yelp — menu, photos, reservations">
                ⭐ Yelp
              </a>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ============================================================================
   History calendar (last 14 days)
   ========================================================================== */
function HistoryView({ rows, recipeMap }: { rows: { date_et: string; slot: string; recipe_ids: string[] }[]; recipeMap: Map<string, Recipe> }) {
  // Group by date
  const byDate = useMemo(() => {
    const m = new Map<string, { date: string; slots: Record<string, string[]> }>();
    for (const r of rows) {
      let d = m.get(r.date_et);
      if (!d) { d = { date: r.date_et, slots: {} }; m.set(r.date_et, d); }
      d.slots[r.slot] = (r.recipe_ids || []).map((id) => recipeMap.get(id)?.name || id);
    }
    return Array.from(m.values()).sort((a, b) => b.date.localeCompare(a.date));
  }, [rows, recipeMap]);

  if (byDate.length === 0) {
    return (
      <p style={{ marginTop: '1rem', color: 'var(--cm-slate)' }}>
        No history yet. Once you log a few "✓ cooked" entries, this fills in and the planner stops repeating dishes within a week.
      </p>
    );
  }

  return (
    <div style={{ marginTop: '1rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.7rem' }}>
      {byDate.map((d) => (
        <div key={d.date} style={{ padding: '0.7rem 0.85rem', border: '1px solid var(--rule, #ddd)', borderRadius: 5, background: 'var(--bg-raised)' }}>
          <div className="mono" style={{ fontWeight: 700 }}>{d.date}</div>
          {Object.entries(d.slots).map(([slot, names]) => (
            <div key={slot} style={{ marginTop: '0.4rem', fontSize: '0.84rem' }}>
              <span className="mono" style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', textTransform: 'uppercase' }}>{slot.replace('_', ' ')}</span>
              <div>{names.join(' · ')}</div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

/* ============================================================================
   Grocery list
   ========================================================================== */

/** Inline copy-to-clipboard button. Shows "✓ Copied" feedback for 1.5s on
 *  success. Falls back gracefully when navigator.clipboard isn't available
 *  (older browsers / non-https contexts). */
function CopyButton({ text, label = 'Copy', size = 'sm' }: { text: string; label?: string; size?: 'sm' | 'md' }) {
  const [copied, setCopied] = useState(false);
  const onClick = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        // Fallback: hidden textarea + execCommand
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // swallow — UI already shows nothing changed
    }
  };
  const padding = size === 'md' ? '0.4rem 0.75rem' : '0.2rem 0.55rem';
  const fontSize = size === 'md' ? '0.82rem' : '0.72rem';
  return (
    <button
      type="button"
      onClick={onClick}
      title={copied ? 'Copied to clipboard' : 'Copy this list to clipboard'}
      style={{
        padding, fontSize,
        border: '1px solid var(--hairline)',
        borderRadius: 4,
        background: copied ? 'rgba(16, 185, 129, 0.12)' : 'var(--bg-raised)',
        color: copied ? 'var(--cm-good, #10b981)' : 'inherit',
        cursor: 'pointer',
        whiteSpace: 'nowrap',
      }}
    >
      {copied ? '✓ Copied' : `📋 ${label}`}
    </button>
  );
}

/** Format a single grocery item as one plain-text line: "onions (3 lb)". */
function _fmtItem(it: { item: string; qty: number | string; unit: string }): string {
  const qty = it.qty;
  const unit = (it.unit || '').trim();
  const hasQty = qty !== 0 && qty !== '0' && qty !== '' && qty != null;
  if (!hasQty && !unit) return `- ${it.item}`;
  const inside = [hasQty ? String(qty) : '', unit].filter(Boolean).join(' ').trim();
  return inside ? `- ${it.item} (${inside})` : `- ${it.item}`;
}

function _fmtCategory(cat: string, items: { item: string; qty: number | string; unit: string }[]): string {
  return `${cat.toUpperCase()}\n${items.map(_fmtItem).join('\n')}`;
}

function GroceryView({ grocery }: { grocery: NonNullable<ReturnType<typeof useGrocery>['data']> }) {
  const cats = Object.entries(grocery.categories);
  const catOrder = ['vegetables', 'meat', 'dairy', 'pantry', 'spices'];
  cats.sort(([a], [b]) => (catOrder.indexOf(a) - catOrder.indexOf(b)));

  // "Copy all" payload — header + every category + weekly recurring.
  // Skips in_pantry on purpose (those are "already have", not "to buy").
  const copyAllText = [
    `Grocery list — week of ${grocery.week_start}`,
    `Projected from ${grocery.n_recipes} planned recipes`,
    '',
    ...cats.map(([cat, items]) => _fmtCategory(cat, items)).join('\n\n').split('\n'),
    ...(grocery.weekly_recurring.length > 0
      ? ['', 'WEEKLY RECURRING', ...grocery.weekly_recurring.map((r) => `- ${r}`)]
      : []),
  ].join('\n');

  return (
    <div style={{ marginTop: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.6rem', flexWrap: 'wrap' }}>
        <div className="mono" style={{ fontSize: '0.78rem', color: 'var(--cm-slate)' }}>
          Week starting {grocery.week_start} · projected from {grocery.n_recipes} planned recipes
        </div>
        <CopyButton text={copyAllText} label="Copy all" size="md" />
      </div>

      {grocery.bulk_reminders.length > 0 && (
        <div style={{ marginTop: '0.6rem', padding: '0.6rem 0.8rem', background: 'rgba(217, 119, 6, 0.08)', border: '1px solid rgba(217, 119, 6, 0.4)', borderRadius: 4 }}>
          {grocery.bulk_reminders.map((r) => (
            <div key={r.item}>⚠️ <strong>{r.item}</strong> — {r.msg}</div>
          ))}
        </div>
      )}

      <div style={{ marginTop: '0.8rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.8rem' }}>
        {cats.map(([cat, items]) => (
          <section key={cat} style={{ padding: '0.8rem 1rem', border: '1px solid var(--rule, #ddd)', borderRadius: 5, background: 'var(--bg-raised)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.4rem' }}>
              <div className="eyebrow">{cat} ({items.length})</div>
              <CopyButton text={_fmtCategory(cat, items)} label="Copy" />
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: '0.4rem 0 0', fontSize: '0.86rem' }}>
              {items.map((it, i) => (
                <li key={`${it.item}-${i}`} style={{ padding: '0.3rem 0', borderTop: i > 0 ? '1px dashed var(--hairline)' : 'none' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>{it.item}</span>
                    <span className="mono" style={{ color: 'var(--cm-slate)' }}>{it.qty} {it.unit}</span>
                  </div>
                  <div className="mono" style={{ fontSize: '0.66rem', color: 'var(--ink-muted)', fontStyle: 'italic' }}>
                    for: {it.from.slice(0, 2).join(' · ')}{it.from.length > 2 ? ` +${it.from.length - 2}` : ''}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      {grocery.in_pantry.length > 0 && (
        <div style={{ marginTop: '0.8rem', padding: '0.7rem 0.85rem', border: '1px solid var(--hairline)', borderRadius: 4, background: 'var(--bg-raised)' }}>
          <div className="eyebrow">Already in pantry — skipped</div>
          <div className="mono" style={{ fontSize: '0.78rem', color: 'var(--cm-slate)', marginTop: '0.3rem' }}>
            {grocery.in_pantry.join(' · ')}
          </div>
        </div>
      )}

      {grocery.weekly_recurring.length > 0 && (
        <div style={{ marginTop: '0.8rem', padding: '0.7rem 0.85rem', border: '1px solid var(--hairline)', borderRadius: 4, background: 'var(--bg-raised)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.4rem' }}>
            <div className="eyebrow">Weekly recurring (don't forget)</div>
            <CopyButton
              text={`WEEKLY RECURRING\n${grocery.weekly_recurring.map((r) => `- ${r}`).join('\n')}`}
              label="Copy"
            />
          </div>
          <ul style={{ margin: '0.3rem 0 0', paddingLeft: '1.1rem', fontSize: '0.84rem' }}>
            {grocery.weekly_recurring.map((r) => <li key={r}>{r}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
