import { lazy, Suspense, useEffect, useState, type ReactNode, type ComponentType } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { NavBar } from './components/NavBar';
import { BreakoutAlertBanner } from './components/BreakoutAlertBanner';
import { ChatWidget } from './components/ChatWidget';
import { InstallToHomeScreen, shouldAutoShowInstallPrompt } from './components/InstallToHomeScreen';
import { ensureServiceWorker } from './lib/pushSubscribe';
import { usePageTracking } from './hooks/usePageTracking';
import { useMyFeatures } from './hooks/useMyFeatures';
import { useMyMenu } from './hooks/useMyMenu';
import { useCurrentUser } from './hooks/useUser';
import { PageContextProvider } from './hooks/usePageContext';

/* ==========================================================================
   ROUTE-BASED CODE SPLITTING
   --------------------------------------------------------------------------
   Every page gets its own chunk via React.lazy. The initial bundle now only
   contains shell + nav + alert banner. Each route's JS downloads on first
   navigation (and is cached after). Big phone-first-paint win — the initial
   bundle drops from ~194KB to ~60KB.

   Named-export pages need the `.then(m => ({default: m.X}))` wrapper because
   React.lazy expects a default export.
   ========================================================================== */

/* Stale-chunk self-heal. After a frontend redeploy, a long-open tab is still
   running an OLD bundle whose lazy chunk hashes no longer exist on the server
   (e.g. /assets/Portfolio-<oldhash>.js). The next route navigation then throws
   "Failed to fetch dynamically imported module" and the page goes blank.
   lazyWithReload catches that and reloads ONCE to pull the fresh index.html +
   chunk map (index.html is no-cache in nginx, so the reload gets the new build).
   A 10s sessionStorage guard prevents a reload loop if the chunk is genuinely
   missing (a truly broken deploy → surface the error instead of looping). */
function lazyWithReload<T extends ComponentType<any>>(
  factory: () => Promise<{ default: T }>,
) {
  return lazy(async () => {
    try {
      return await factory();
    } catch (err) {
      const KEY = 'chunkReloadTs';
      const last = Number(sessionStorage.getItem(KEY) || '0');
      if (Date.now() - last > 10_000) {
        sessionStorage.setItem(KEY, String(Date.now()));
        window.location.reload();
        return new Promise<{ default: T }>(() => {}); // hang until reload swaps the page
      }
      throw err; // reloaded moments ago and still failing → real error
    }
  });
}
const LiveStream                  = lazyWithReload(() => import('./pages/LiveStream').then(m => ({ default: m.LiveStream })));
const SepaPage                    = lazyWithReload(() => import('./pages/Sepa').then(m => ({ default: m.SepaPage })));
const SepaV2Page                  = lazyWithReload(() => import('./pages/SepaV2').then(m => ({ default: m.SepaV2Page })));
const SepaCandidatePage           = lazyWithReload(() => import('./pages/SepaCandidate').then(m => ({ default: m.SepaCandidatePage })));
const DualMomentumPage            = lazyWithReload(() => import('./pages/DualMomentum').then(m => ({ default: m.DualMomentumPage })));
const PullbackMaPage              = lazyWithReload(() => import('./pages/PullbackMa').then(m => ({ default: m.PullbackMaPage })));
const MarketGaugePage             = lazyWithReload(() => import('./pages/MarketGauge').then(m => ({ default: m.MarketGaugePage })));
const UsagePage                   = lazyWithReload(() => import('./pages/UsagePage').then(m => ({ default: m.UsagePage })));
const LongTermPage                = lazyWithReload(() => import('./pages/LongTermPage').then(m => ({ default: m.LongTermPage })));
const RaviStrategyPage            = lazyWithReload(() => import('./pages/RaviStrategy').then(m => ({ default: m.RaviStrategyPage })));
const ChatterPage                 = lazyWithReload(() => import('./pages/Chatter').then(m => ({ default: m.ChatterPage })));
const ChatterIndiaPage            = lazyWithReload(() => import('./pages/ChatterIndia').then(m => ({ default: m.ChatterIndiaPage })));
const PioneersPage                = lazyWithReload(() => import('./pages/Pioneers').then(m => ({ default: m.PioneersPage })));
const DayTrading                  = lazyWithReload(() => import('./pages/DayTrading').then(m => ({ default: m.DayTrading })));
const MorningBrief                = lazyWithReload(() => import('./pages/MorningBrief').then(m => ({ default: m.MorningBrief })));
const OvernightPage               = lazyWithReload(() => import('./pages/Overnight').then(m => ({ default: m.OvernightPage })));
const SupplyDemandPage            = lazyWithReload(() => import('./pages/SupplyDemand').then(m => ({ default: m.SupplyDemandPage })));
const DemandZonesPage             = lazyWithReload(() => import('./pages/DemandZonesPage').then(m => ({ default: m.DemandZonesPage })));
const PortfolioPage               = lazyWithReload(() => import('./pages/Portfolio'));
const LeaderboardPage             = lazyWithReload(() => import('./pages/Leaderboard').then(m => ({ default: m.LeaderboardPage })));
const ResearchPage                = lazyWithReload(() => import('./pages/Research').then(m => ({ default: m.ResearchPage })));
const CatalystsPage               = lazyWithReload(() => import('./pages/Catalysts').then(m => ({ default: m.CatalystsPage })));
const TrackPage                   = lazyWithReload(() => import('./pages/Track'));
const WatchlistPage               = lazyWithReload(() => import('./pages/Watchlist'));
const GlossaryPage                = lazyWithReload(() => import('./pages/Glossary'));
const NotificationsPage           = lazyWithReload(() => import('./pages/Notifications'));
const AdminUsagePage              = lazyWithReload(() => import('./pages/AdminUsage'));
const AdminTodosPage              = lazyWithReload(() => import('./pages/AdminTodos'));
const AdminAccessPage             = lazyWithReload(() => import('./pages/AdminAccess'));
const SignInPage                  = lazyWithReload(() => import('./pages/SignIn'));
const SignUpPage                  = lazyWithReload(() => import('./pages/SignUp'));
const AdminPushPage               = lazyWithReload(() => import('./pages/AdminPush'));
const TodosPage                   = lazyWithReload(() => import('./pages/Todos'));
const TinyPage                    = lazyWithReload(() => import('./pages/Tiny'));
const SetupsPage                  = lazyWithReload(() => import('./pages/Setups'));
const KellPage                    = lazyWithReload(() => import('./pages/Kell').then(m => ({ default: m.KellPage })));
const LearnPage                   = lazyWithReload(() => import('./pages/Learn'));
const VolleyballPage              = lazyWithReload(() => import('./pages/Volleyball'));
const OptionsPulsePage            = lazyWithReload(() => import('./pages/OptionsPulse'));
const OptionsPulseMethodologyPage = lazyWithReload(() => import('./pages/OptionsPulseMethodology'));
const HousePage                   = lazyWithReload(() => import('./pages/House'));
const FoodPage                    = lazyWithReload(() => import('./pages/Food'));
const KidsPage                    = lazyWithReload(() => import('./pages/Kids'));

// Register the service worker as soon as the app loads so push delivery works
// even when this tab is closed. No-op if already registered or unsupported.
ensureServiceWorker();

/** Tiny page-load fallback. Shown for the brief moment between route click
 *  and chunk-fetch completion. Inline styles to avoid the fallback waiting
 *  for CSS. */
function PageLoader() {
  return (
    <div style={{ padding: '3rem 1.5rem', textAlign: 'center', color: '#888', fontSize: '0.9rem' }}>
      Loading…
    </div>
  );
}

/** Stealth 404 — matches the backend's "you don't get to know this exists"
 *  posture. Used for ungranted routes and the admin-only routes when the
 *  caller isn't admin. Looks like a real 404 from the user's perspective. */
function NotFound() {
  return (
    <div style={{ padding: '4rem 1.5rem', textAlign: 'center', color: '#888' }}>
      <h1 style={{ fontSize: '1.4rem', fontFamily: 'serif', fontStyle: 'italic' }}>404</h1>
      <p>Not found.</p>
    </div>
  );
}

/** Gate a route by feature ID. Renders the child element only if the
 *  user has the feature in their /me/features set; otherwise redirects
 *  to SmartLanding (their first available page).
 *
 *  Previously rendered <NotFound /> on miss — that produced a real 404
 *  page that was visually jarring when admin revoked access mid-session
 *  or when a user bookmarked a feature they no longer have. Redirect
 *  is friendlier: the user lands somewhere they can actually use,
 *  silently. Combined with the server-built menu (which never offers
 *  links the user can't reach), the only way to even reach this
 *  branch is manual URL typing or a stale bookmark.
 *
 *  We still wait for the features fetch to complete before deciding —
 *  otherwise a deep-link to /sepa would briefly render SEPA content
 *  before the gate kicked in. */
function FeatureRoute({ feature, children }: { feature: string; children: ReactNode }) {
  const f = useMyFeatures();
  if (!f.loaded) return <PageLoader />;
  if (!f.features.has(feature)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

/** Gate admin-only routes. Same redirect-to-landing posture as
 *  FeatureRoute — non-admins silently land on their default page
 *  instead of seeing a 404. Backend still 404s the underlying
 *  /admin/* API endpoints, so direct API access is still locked.
 *
 *  Uses ``user.is_admin`` from /auth/me. The previous version compared
 *  against a hardcoded ADMIN_EMAIL constant that leaked the personal
 *  Gmail into the JS bundle — fixed 2026-05-20. */
function AdminRoute({ children }: { children: ReactNode }) {
  const { user } = useCurrentUser();
  if (user === null) return <PageLoader />;            // user fetch in flight
  if (!user?.is_admin) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

/** Landing-page resolver. The "/" path used to hard-redirect to /morning;
 *  but for friends who don't have the morning feature that was a 404
 *  loop. Now we pick the first feature the user actually has access to
 *  and redirect there. Owners + admin still land on /morning naturally
 *  because they have every feature. */
function SmartLanding() {
  const f = useMyFeatures();
  const { menu, loaded: menuLoaded } = useMyMenu();
  // Wait for BOTH so we know is_admin before redirecting (else Ajay would flash
  // to the wrong page before the admin flag resolves).
  if (!f.loaded || !menuLoaded) return <PageLoader />;
  // Ajay (admin) lands on Portfolio going forward (2026-06-06); everyone else
  // keeps the morning-first order. First accessible feature in the list wins;
  // further fallbacks chain down before bailing into a 404.
  const PREFERRED_ORDER = menu.is_admin
    ? ['portfolio', 'morning', 'sepa', 'leaderboard', 'todos', 'notifications']
    : ['morning', 'food', 'kids', 'sepa', 'todos', 'notifications', 'glossary'];
  for (const id of PREFERRED_ORDER) {
    if (f.features.has(id)) return <Navigate to={`/${id}`} replace />;
  }
  // No accessible feature at all — show 404 rather than a redirect loop.
  return <NotFound />;
}

export function App() {
  // Page-view tracking — fires on every route change inside Routes,
  // and stops counting on tab close. Backend stores per-user dwell time
  // for the admin usage dashboard.
  usePageTracking();

  // First-run install prompt: shows ONLY on phones that aren't already
  // running standalone. iOS Safari requires Add-to-Home-Screen before
  // push notifications work at all (Apple restriction since iOS 16.4),
  // so this is a real onboarding step — not a nag. Dismissal is stored
  // in localStorage and the user can re-open the guide from
  // /notifications → "Show install instructions".
  const [showInstall, setShowInstall] = useState(false);
  useEffect(() => {
    // Delay 600ms so it doesn't fight the initial paint / OAuth bounce.
    // Long enough to feel intentional, short enough that the user is
    // still on the welcome view.
    const t = setTimeout(() => {
      if (shouldAutoShowInstallPrompt()) setShowInstall(true);
    }, 600);
    return () => clearTimeout(t);
  }, []);

  return (
    <PageContextProvider>
    <div className="app">
      <NavBar />
      <BreakoutAlertBanner />
      {/* Floating Claude chat — every page can call setPageContext() so
          the assistant has structured state about what's on screen. */}
      <ChatWidget />
      {showInstall && <InstallToHomeScreen onClose={() => setShowInstall(false)} />}
      <main className="main">
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public auth pages — not gated by FeatureRoute / AdminRoute
                since anonymous users need to be able to load them to
                sign in or create an account in the first place. */}
            <Route path="/signin" element={<SignInPage />} />
            <Route path="/signup" element={<SignUpPage />} />

            {/* SmartLanding picks the user's first available feature
                so friends without /morning don't bounce into a 404
                loop on first sign-in. */}
            <Route path="/" element={<SmartLanding />} />

            {/* Every page route is wrapped in FeatureRoute so URL-hacks
                to ungranted pages render a stealth 404 instead of the
                actual page content. Owners/admin always pass because
                their /me/features set is "everything". */}
            <Route path="/morning"        element={<FeatureRoute feature="morning"><MorningBrief /></FeatureRoute>} />
            <Route path="/overnight"      element={<FeatureRoute feature="overnight"><OvernightPage /></FeatureRoute>} />
            <Route path="/live"           element={<FeatureRoute feature="live"><LiveStream /></FeatureRoute>} />
            <Route path="/sepa"           element={<FeatureRoute feature="sepa"><SepaPage /></FeatureRoute>} />
            <Route path="/sepa-v2"        element={<FeatureRoute feature="sepa"><SepaV2Page /></FeatureRoute>} />
            <Route path="/sepa/:symbol"   element={<FeatureRoute feature="sepa"><SepaCandidatePage /></FeatureRoute>} />
            <Route path="/dual-momentum"  element={<FeatureRoute feature="dual-momentum"><DualMomentumPage /></FeatureRoute>} />
            <Route path="/pullback-ma"    element={<FeatureRoute feature="pullback-ma"><PullbackMaPage /></FeatureRoute>} />
            <Route path="/market-gauge"   element={<FeatureRoute feature="market-gauge"><MarketGaugePage /></FeatureRoute>} />
            <Route path="/usage"          element={<FeatureRoute feature="usage"><UsagePage /></FeatureRoute>} />
            <Route path="/longterm"       element={<FeatureRoute feature="longterm"><LongTermPage /></FeatureRoute>} />
            <Route path="/ravi-strategy"  element={<FeatureRoute feature="ravi-strategy"><RaviStrategyPage /></FeatureRoute>} />
            <Route path="/chatter"        element={<FeatureRoute feature="chatter"><ChatterPage /></FeatureRoute>} />
            <Route path="/chatter-india"  element={<FeatureRoute feature="chatter-india"><ChatterIndiaPage /></FeatureRoute>} />
            <Route path="/pioneers"       element={<FeatureRoute feature="pioneers"><PioneersPage /></FeatureRoute>} />
            <Route path="/day-trading"    element={<FeatureRoute feature="day-trading"><DayTrading /></FeatureRoute>} />
            <Route path="/supply-demand"  element={<FeatureRoute feature="supply-demand"><SupplyDemandPage /></FeatureRoute>} />
            <Route path="/demand-zones"   element={<FeatureRoute feature="demand-zones"><DemandZonesPage /></FeatureRoute>} />
            <Route path="/portfolio"      element={<FeatureRoute feature="portfolio"><PortfolioPage /></FeatureRoute>} />
            <Route path="/leaderboard"    element={<FeatureRoute feature="leaderboard"><LeaderboardPage /></FeatureRoute>} />
            <Route path="/research"       element={<FeatureRoute feature="research"><ResearchPage /></FeatureRoute>} />
            <Route path="/catalysts"      element={<FeatureRoute feature="catalysts"><CatalystsPage /></FeatureRoute>} />
            <Route path="/track"          element={<FeatureRoute feature="track"><TrackPage /></FeatureRoute>} />
            <Route path="/watchlist"      element={<FeatureRoute feature="watchlist"><WatchlistPage /></FeatureRoute>} />
            <Route path="/glossary"       element={<FeatureRoute feature="glossary"><GlossaryPage /></FeatureRoute>} />
            <Route path="/notifications"  element={<FeatureRoute feature="notifications"><NotificationsPage /></FeatureRoute>} />
            <Route path="/todos"          element={<FeatureRoute feature="todos"><TodosPage /></FeatureRoute>} />
            <Route path="/tiny"           element={<FeatureRoute feature="tiny"><TinyPage /></FeatureRoute>} />
            <Route path="/setups"         element={<FeatureRoute feature="setups"><SetupsPage /></FeatureRoute>} />
            <Route path="/kell"           element={<FeatureRoute feature="kell"><KellPage /></FeatureRoute>} />
            <Route path="/learn"          element={<FeatureRoute feature="learn"><LearnPage /></FeatureRoute>} />
            <Route path="/volleyball"     element={<FeatureRoute feature="volleyball"><VolleyballPage /></FeatureRoute>} />
            <Route path="/options"        element={<FeatureRoute feature="options"><OptionsPulsePage /></FeatureRoute>} />
            <Route path="/options/methodology" element={<FeatureRoute feature="options"><OptionsPulseMethodologyPage /></FeatureRoute>} />
            <Route path="/house"          element={<FeatureRoute feature="house"><HousePage /></FeatureRoute>} />
            <Route path="/food"           element={<FeatureRoute feature="food"><FoodPage /></FeatureRoute>} />
            <Route path="/kids"           element={<FeatureRoute feature="kids"><KidsPage /></FeatureRoute>} />

            {/* Admin-only — gated on email match instead of feature ID.
                Backend mirrors the gate (returns 404 to non-admins). */}
            <Route path="/admin/usage"  element={<AdminRoute><AdminUsagePage /></AdminRoute>} />
            <Route path="/admin/todos"  element={<AdminRoute><AdminTodosPage /></AdminRoute>} />
            <Route path="/admin/access" element={<AdminRoute><AdminAccessPage /></AdminRoute>} />
            <Route path="/admin/push"   element={<AdminRoute><AdminPushPage /></AdminRoute>} />

            {/* Anything unknown also passes through SmartLanding so
                users land somewhere they can actually use. */}
            <Route path="*" element={<SmartLanding />} />
          </Routes>
        </Suspense>
      </main>
    </div>
    </PageContextProvider>
  );
}
