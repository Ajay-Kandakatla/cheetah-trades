"""Mongo-backed storage for per-user feature access.

Collection
----------
``user_features`` — one doc per user with the explicit feature set::

    {
      "_id":         ObjectId,
      "user_email":  "friend1@gmail.com",     # canonical: lowercased
      "features":    ["morning", "sepa", ...] # subset of FEATURE_CATALOG ids
      "updated_at":  1715900000,
      "updated_by":  "ajaykandakatla@gmail.com",
    }

Resolution
----------
``get_user_features(email)`` returns the effective set for a user:

1. If the user is in ``HOUSE_OWNER_EMAILS`` (Ajay + Vineetha):
   they get **every** feature regardless of the saved doc — the
   admin can't accidentally lock themselves or their spouse out.
2. Else if the user has a saved doc, return its `features` list.
3. Else (no doc — first-time login or freshly invited friend):
   return ``DEFAULT_FEATURES``.

Defaults
--------
Most pages default ON (trading tools, public scans). The household
pages (food, kids, house) default OFF — admin must explicitly grant
them.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Iterable, Optional

log = logging.getLogger("access.store")

_db = None
_disabled = False


def _get_db():
    """Lazy Mongo handle. Returns None if Mongo is unreachable so the
    rest of the app keeps working (defaults apply, admin panel is
    read-only)."""
    global _db, _disabled
    if _disabled:
        return None
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        # Unique index on user_email — one doc per user.
        _db.user_features.create_index([("user_email", ASCENDING)], unique=True)
        log.info("access store: connected to %s", url)
        return _db
    except Exception as exc:
        log.warning("access store: Mongo unavailable (%s) — disabling persistence", exc)
        _disabled = True
        return None


# ----------------------------------------------------------------------
# Feature catalog
# ----------------------------------------------------------------------
# Order here determines the order the admin UI renders. `group` powers
# the section headers in the admin matrix. `default` controls whether
# NEW non-owner users get it without explicit grant.
#
# Default policy (per user feedback 2026-05-15): the app is private and
# most pages are trading-specific — "lot of these pages only make sense
# for me" (Ajay). So defaults are intentionally MINIMAL. Friends signing
# in for the first time see only:
#   - Food + Kids (household features Ajay explicitly wants to share)
#   - Notifications / Todos / Glossary (per-user account stuff)
# Everything else (SEPA, Chatter, Day Trading, etc.) is OFF by default
# and the admin must opt friends in individually via /admin/access.
#
# Owners (Ajay + Vineetha) always get every feature regardless of these
# flags — see get_user_features().
#
# IMPORTANT: feature IDs are stable. Renaming an ID would orphan saved
# selections in `user_features`. Add new entries instead.
FEATURE_CATALOG: list[dict] = [
    # Daily-driver pages — heavy trading content, default OFF for friends.
    {"id": "morning",       "label": "Morning Brief",       "group": "daily",     "default": False},
    {"id": "overnight",     "label": "Overnight",           "group": "daily",     "default": False},

    # Scanners — equity screeners, grouped under the "Scanners" nav tab
    # (Ajay 2026-06-05). SEPA + Pullback to MA lead; the rest are the
    # methodology/setup screens. Nav order follows THIS list (ids are stable,
    # so reordering here is safe and never orphans a saved access set).
    {"id": "sepa",          "label": "SEPA",                "group": "scanner",   "default": False},
    {"id": "pullback-ma",   "label": "Pullback to MA",      "group": "scanner",   "default": False, "added_in": 4},
    {"id": "dual-momentum", "label": "Dual Momentum",       "group": "scanner",   "default": False},
    {"id": "setups",        "label": "Setups (PEG/ORB/Inside)", "group": "scanner", "default": False},
    {"id": "kell",          "label": "Kell (CoPA)",         "group": "scanner",   "default": False},
    {"id": "tiny",          "label": "Tiny Stocks",         "group": "scanner",   "default": False},
    {"id": "pioneers",      "label": "Pioneers",            "group": "scanner",   "default": False},
    {"id": "ravi-strategy", "label": "Ravi's Strategy",     "group": "scanner",   "default": False},
    # ZONETRADER618 long-term report-card tracker (curated 70-stock list, live
    # enriched). Owner-on via added_in/VERSION.
    {"id": "longterm",      "label": "Long-Term Stocks",    "group": "scanner",   "default": False, "added_in": 7},
    # Real-money holdings view — hold/sell signals + R-multiples + live sell
    # alerts. Promoted to the PRIMARY top-nav (group "daily") on 2026-06-02:
    # Ajay checks holdings + acts on sell pings every trading day, so it earns a
    # first-class tab next to SEPA rather than living in the Misc dropdown.
    # Owner-only by default since it surfaces real money positions; owners
    # auto-bypass via the universal owner-feature grant (see get_user_features).
    # Friends can be granted via /admin/access; positions are per-user.
    {"id": "portfolio",     "label": "Portfolio",           "group": "daily",     "default": False},
    # Dedicated rank home (2026-06-03): Top Picks (+ volume-deviation metrics),
    # the Top-Picks churn tracker, honourable mentions and the rank-compare chart.
    # Primary nav next to Portfolio — Ajay checks ranking daily. Owner-only default.
    {"id": "leaderboard",   "label": "Leaderboard",         "group": "daily",     "default": False, "added_in": 2},
    # Research (2026-06-04): bullish-vs-bearish pattern mining + the insider
    # thesis. A living analysis page Ajay wants to keep using. Owner-on default.
    {"id": "research",      "label": "Research",            "group": "daily",     "default": False, "added_in": 3},
    # Market Gauge (2026-06-05): our own book-grounded general-market health read
    # (0-100 + Constructive/Caution/Risk-Off + a Minervini exposure band). The
    # score also renders top-right on every page. Owner-on via added_in/VERSION.
    {"id": "market-gauge",  "label": "Market Gauge",        "group": "tools",     "default": False, "added_in": 5},
    {"id": "catalysts",     "label": "Catalysts",           "group": "tools",     "default": False},
    {"id": "options",       "label": "Options Pulse",       "group": "tools",     "default": False},
    {"id": "track",         "label": "Track",               "group": "tools",     "default": False},
    {"id": "day-trading",   "label": "Day Trading",         "group": "tools",     "default": False},
    # Scalping (2026-06-09): Phase-1 DOCUMENTED intraday patterns (Stocks-in-Play
    # ORB / volatility-normalized shock-fade / intraday-momentum regime) with a
    # live spread gate + net-of-cost honesty layer. Sourced from a vetted research
    # pass (docs/scalping_methodology.md). Educational, NOT advice — most retail
    # day-trading is net-losing. Owner-on via added_in/VERSION.
    {"id": "scalping",      "label": "Scalping",            "group": "tools",     "default": False, "added_in": 11},
    # Auto-Pilot (2026-06-11): automated Minervini exit engine on Alpaca —
    # bracket entries, breakeven-ratchet stops, regime-aware widths (TLSW
    # Ch.12-13). Places/moves REAL orders (paper by default via ALPACA_PAPER=1),
    # so this stays owner-only unless explicitly granted. Owner-on via
    # added_in/VERSION.
    {"id": "trading",       "label": "🤖 Auto-Pilot",       "group": "tools",     "default": False, "added_in": 14},
    {"id": "supply-demand", "label": "Supply / Demand",     "group": "tools",     "default": False},
    # Demand Zones (2026-06-07): Minervini-basing demand-zone price BANDS for the
    # leaderboard + day-trading universe — each name's most-recent VCP base
    # (floor → pivot), depth-classified, with where price sits vs the band.
    # Educational; derived from the contract-locked vcp.detect. Owner-on via
    # added_in/VERSION.
    {"id": "demand-zones",  "label": "Demand Zones",        "group": "tools",     "default": False, "added_in": 8},
    # Pankaj's Market Analysis (2026-06-09): curated picks from a trusted outside
    # analyst, surfaced WITH the app's own SEPA indicators + live status vs his
    # entry/stop/target levels, plus owner-scoped alerts when price hits them.
    # Owner-on via added_in/VERSION; Pankaj's calls shown for context, not advice.
    {"id": "pankaj",        "label": "Pankaj's Analysis",   "group": "tools",     "default": False, "added_in": 9},
    # S/D Zones (2026-06-09): on-demand per-ticker price-structure supply/demand
    # zones + an entry read (resistance above / support below / favorable-caution).
    # Configured method (not a book method); decision-support, not advice.
    {"id": "zones",         "label": "S/D Zones",           "group": "tools",     "default": False, "added_in": 10},
    # Patterns (2026-06-09): on-demand bullish-reversal pattern scan (double
    # bottom, inverse H&S) over the SEPA universe's cached daily frames, with
    # confirmation-line discipline + our-universe self-validation. Owner-on.
    {"id": "patterns",      "label": "Patterns",            "group": "tools",     "default": False, "added_in": 12},
    {"id": "live",          "label": "Live Stream",         "group": "tools",     "default": False},
    {"id": "chatter",       "label": "Chatter · US",        "group": "tools",     "default": False},
    {"id": "chatter-india", "label": "Chatter · IN",        "group": "tools",     "default": False},

    # Account / personal — each user has their own scoped data; safe to
    # default on so friends can manage their own profile bits.
    {"id": "notifications", "label": "Notifications",       "group": "account",   "default": True},
    {"id": "todos",         "label": "Todos",               "group": "account",   "default": True},
    {"id": "watchlist",     "label": "Watchlist",           "group": "account",   "default": False},
    {"id": "glossary",      "label": "Glossary",            "group": "account",   "default": True},
    # Education — Minervini Learning module. Surfaces the flashcard bank
    # by topic with deep-links from push notifications.
    # Default ON for everyone — trading education isn't owner-only.
    {"id": "learn",         "label": "Learning",            "group": "account",   "default": True},
    # Chart School (2026-06-09): the visual half of learning — daily real-chart
    # pattern-ID quiz (from the scan universe's historical confirmations),
    # Bulkowski pattern library with the supply/demand WHY, candle-read anatomy
    # tied to the SEPA Watch alert states, and the 8-week curriculum. Default ON.
    {"id": "chart-school",  "label": "Chart School",        "group": "account",   "default": True, "added_in": 13},
    # Usage heatmap — personal analytics: which pages/features Ajay uses
    # heavily + a weekday×hour heatmap. Owner-on via added_in/VERSION.
    {"id": "usage",         "label": "Usage Heatmap",       "group": "account",   "default": False, "added_in": 6},
    # Personal fitness — volleyball training module tuned to Ajay's
    # injury profile. Default OFF for friends (it's personal); owners
    # get it via the universal owner-feature bypass in store.py.
    {"id": "volleyball",    "label": "Volleyball Fitness",  "group": "household", "default": False},

    # Household — Ajay explicitly OK'd shared family content for friends
    # (per feedback 2026-05-15: "All my friends use similar food so that
    # is ok"). Default ON so friends signing in get straight to the
    # value-add features without an admin granting them individually.
    # House Sale stays OFF — that's private real-estate data, owner-only.
    {"id": "food",          "label": "Food (meal planner)", "group": "household", "default": True},
    {"id": "kids",          "label": "Kids (activities)",   "group": "household", "default": True},
    {"id": "house",         "label": "House Sale",          "group": "household", "default": False},
]

DEFAULT_FEATURES: set[str] = {f["id"] for f in FEATURE_CATALOG if f["default"]}
RESTRICTED_FEATURES: set[str] = {f["id"] for f in FEATURE_CATALOG if not f["default"]}
ALL_FEATURE_IDS: set[str] = {f["id"] for f in FEATURE_CATALOG}

# ── Owner auto-grant of NEW pages (Ajay 2026-06-03: "by default when I build
# pages, turn them on for me"). Implemented as authorization LOGIC, not a per-user
# DB grant, so it can only be driven by a real catalog addition — never by a
# stray write or injected instruction.
#
# Each catalog entry carries an `added_in` version (default 1). When an OWNER has
# a customized (saved) feature set, get_user_features unions it with every feature
# whose `added_in` exceeds the version they last "saw" — so a page added after
# they decluttered shows up automatically, WITHOUT re-granting pages they hid on
# purpose. set_user_features records the version they've seen.
#
# To add a new owner-visible page: add the catalog entry with `"added_in":
# CATALOG_VERSION + 1`, then bump CATALOG_VERSION. Owners get it on next load.
CATALOG_VERSION = 14
OWNER_AUTO_BASELINE = 1          # features at version <= this follow the saved allow-list (preserve declutter)


def _added_in(entry: dict) -> int:
    return int(entry.get("added_in", 1))


def _features_added_after(version: int) -> set[str]:
    """Catalog ids introduced after `version` — auto-granted to owners."""
    return {e["id"] for e in FEATURE_CATALOG if _added_in(e) > version}


def effective_features(saved: set[str], *, is_owner: bool, seen_version: int) -> set[str]:
    """Pure: resolve a saved feature set into the EFFECTIVE set. Owners also get
    any feature added to the catalog after `seen_version` (new pages appear by
    default). Separated from Mongo so it's unit-testable."""
    eff = {f for f in saved if f in ALL_FEATURE_IDS}
    if is_owner:
        eff |= _features_added_after(seen_version)
    return eff


# ----------------------------------------------------------------------
# Resolution helpers
# ----------------------------------------------------------------------
def _house_owner_emails() -> list[str]:
    """Lowercase HOUSE_OWNER_EMAILS. Lazy import to avoid circular dep
    at module load (auth.py imports nothing from us)."""
    from auth import HOUSE_OWNER_EMAILS
    return [e.lower() for e in HOUSE_OWNER_EMAILS]


def get_user_features(email: str) -> set[str]:
    """Effective feature set for ``email``.

    Resolution rules (changed 2026-05-15 — admin requested ability to
    declutter their own and their spouse's nav):

      1. If a saved doc exists, return its `features` list (intersected
         with the current catalog to drop orphaned ids).
      2. Otherwise, return the role-appropriate default:
           - Owners get every feature (kitchen sink)
           - Non-owners get the minimal default set (food/kids/notif/etc.)

    The previous behavior short-circuited owners to "all features"
    regardless of saved overrides, so the admin couldn't hide pages
    from their own or Vineetha's nav even when they wanted to. Now
    owners are editable — same UX for first-time users (defaults to
    everything) but `set_user_features` actually sticks on owners.

    Lockout note: there's no "minimum required features" enforcement.
    The admin CAN technically save an empty feature set on themselves.
    That doesn't matter because /admin/* routes are gated by
    ADMIN_EMAIL (not feature flags), so the admin can always get back
    to /admin/access and toggle features back on.
    """
    email_lc = (email or "").lower().strip()
    if not email_lc:
        return set()

    is_owner = email_lc in _house_owner_emails()

    db = _get_db()
    if db is None:
        # Persistence offline — fall back to defaults so the app stays
        # usable. Owners still get everything; non-owners get the
        # minimal default set.
        return set(ALL_FEATURE_IDS if is_owner else DEFAULT_FEATURES)

    doc = db.user_features.find_one({"user_email": email_lc})
    if doc and isinstance(doc.get("features"), list):
        # Saved overrides win — but OWNERS also auto-receive pages added to the
        # catalog AFTER they last saved (see effective_features / CATALOG_VERSION),
        # so a new page appears by default without re-granting ones they hid.
        seen = int(doc.get("seen_catalog_version", OWNER_AUTO_BASELINE))
        return effective_features(set(doc["features"]), is_owner=is_owner, seen_version=seen)
    # No saved doc: role-appropriate default.
    return set(ALL_FEATURE_IDS if is_owner else DEFAULT_FEATURES)


def set_user_features(
    email: str,
    features: Iterable[str],
    *,
    updated_by: str,
) -> dict:
    """Persist a feature set for one user. Drops unknown feature IDs
    silently. Returns the effective stored set (post-filter)."""
    email_lc = (email or "").lower().strip()
    if not email_lc:
        return {"ok": False, "reason": "email required"}

    clean = sorted({f for f in features if f in ALL_FEATURE_IDS})
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "store unavailable"}

    now = int(datetime.now(timezone.utc).timestamp())
    db.user_features.update_one(
        {"user_email": email_lc},
        {"$set": {
            "user_email":  email_lc,
            "features":    clean,
            "seen_catalog_version": CATALOG_VERSION,   # records "owner has seen up to here"
            "updated_at":  now,
            "updated_by":  (updated_by or "").lower(),
        }},
        upsert=True,
    )
    return {"ok": True, "features": clean, "updated_at": now}


def user_has_feature(email: str, feature_id: str) -> bool:
    """Quick "can this user see this feature?" check. Used by backend
    route gates (e.g. /food handlers). Cheaper than fetching the whole
    set when you only need one feature."""
    return feature_id in get_user_features(email)


# ----------------------------------------------------------------------
# Menu generation
# ----------------------------------------------------------------------
# Single source of truth for how each catalog feature appears in the nav.
# Maps catalog group → nav section. Keeps the layout decision co-located
# with the catalog so adding a feature doesn't require touching the
# frontend NavBar too.
_GROUP_TO_SECTION: dict[str, str] = {
    "daily":     "primary",   # Morning / Overnight / Portfolio — top of nav
    "scanner":   "scanners",  # SEPA / Pullback to MA / Setups / ... — Scanners dropdown
    "tools":     "misc",      # Catalysts / Day Trading / ... — Misc dropdown
    "account":   "profile",   # Notifications / Todos / Glossary
    # Household features have a conditional placement (see build_menu):
    #   - owners see Food / Kids in primary alongside Morning (daily use)
    #   - non-owners see them in profile (single grant; less "daily")
    # House Sale always lives in profile regardless.
    "household": "primary",   # default — build_menu re-routes if needed
}

# Admin-only menu — gated by ADMIN_EMAIL, NOT by feature flags. These
# routes have their own backend admin checks; surfacing them in the
# menu is purely cosmetic.
_ADMIN_MENU_ITEMS: list[dict] = [
    {"to": "/admin/access", "label": "User Access"},
    {"to": "/admin/push",   "label": "Push Subscriptions"},
    {"to": "/admin/todos",  "label": "Add Vineetha’s Todo"},
    {"to": "/admin/usage",  "label": "Usage Dashboard"},
]


def build_menu(email: str) -> dict:
    """Build the user's sectioned nav menu.

    Returns shape::

        {
            "primary":  [{"to": "/sepa",     "label": "SEPA",     "feature": "sepa"}, ...],
            "misc":     [{"to": "/tiny",     "label": "Tiny Stocks", ...},          ...],
            "profile":  [{"to": "/notifications", "label": "Notifications", ...},   ...],
            "admin":    [{"to": "/admin/access", "label": "User Access"},           ...],  # admin only
            "is_owner": bool,
            "is_admin": bool,
        }

    Every entry is something the user can actually access — there is no
    client-side filtering needed. If a section is empty, the frontend
    omits it (no "Misc ▾" dropdown for a user with no Misc items).
    """
    email_lc = (email or "").lower().strip()
    features = get_user_features(email_lc)
    is_owner = email_lc in _house_owner_emails()

    # Admin email match. Hardcoded here too — see ADMIN_EMAIL in
    # access/api.py for the same constant. Single change in both
    # places if it ever rotates.
    is_admin = email_lc == "ajaykandakatla@gmail.com"

    sections: dict[str, list[dict]] = {"primary": [], "scanners": [], "misc": [], "profile": [], "admin": []}

    for entry in FEATURE_CATALOG:
        fid = entry["id"]
        if fid not in features:
            continue

        group = entry["group"]
        # Household placement: Food/Kids go in the Misc dropdown for owners
        # (Ajay 2026-06-04 — "move kids and food under misc" to declutter the
        # primary trading nav), profile for non-owners (it's an added grant, not
        # their main workflow). House Sale always goes to profile — nobody runs
        # daily real-estate checks except the seller.
        if group == "household":
            section = "misc" if (is_owner and fid in ("food", "kids")) else "profile"
        else:
            section = _GROUP_TO_SECTION.get(group, "profile")

        sections[section].append({
            "to":      f"/{fid}",
            "label":   entry["label"],
            "feature": fid,
        })

    # Admin items — separate from the feature catalog because they're
    # email-gated, not feature-gated. We don't expose these unless the
    # caller is the admin.
    if is_admin:
        sections["admin"] = [dict(item) for item in _ADMIN_MENU_ITEMS]

    return {
        **sections,
        "is_owner": is_owner,
        "is_admin": is_admin,
    }


def list_users(extra_emails: Optional[list[str]] = None) -> list[dict]:
    """Return one row per known user — used by the admin panel to render
    its access matrix.

    Universe: everyone in the OAuth allowlist (the only people who CAN
    sign in) plus any extra emails the caller wants merged in (e.g.
    house owners hardcoded in env). Each row carries the user's
    effective feature set after defaults + overrides + house-owner
    bypass are applied.

    Sorted by email so the admin sees a stable order.
    """
    emails: set[str] = set()
    # Pull from oauth allowlist file. Mounted into the api container
    # at the same relative path as the source (it's part of the build
    # context). Best-effort read — if the file isn't present we fall
    # back to whatever's in user_features.
    try:
        with open("oauth2-emails.txt") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                emails.add(line.lower())
    except FileNotFoundError:
        pass
    for e in (extra_emails or []):
        emails.add(e.lower())
    # Pull any saved emails too — covers users in user_features that
    # got removed from the allowlist (they keep their saved config
    # in case they're re-added later).
    db = _get_db()
    saved: dict[str, dict] = {}
    if db is not None:
        for doc in db.user_features.find({}):
            ue = (doc.get("user_email") or "").lower()
            if not ue:
                continue
            emails.add(ue)
            saved[ue] = doc

    owners = set(_house_owner_emails())
    out: list[dict] = []
    for e in sorted(emails):
        doc = saved.get(e)
        out.append({
            "email":      e,
            "features":   sorted(get_user_features(e)),
            "is_owner":   e in owners,
            "updated_at": (doc or {}).get("updated_at"),
            "updated_by": (doc or {}).get("updated_by"),
            "has_saved":  doc is not None,
        })
    return out


# ----------------------------------------------------------------------
# Sign-in allowlist management (oauth2-emails.txt)
# ----------------------------------------------------------------------
# The owner's "User Access" page edits two SEPARATE things:
#   1. Per-user FEATURE grants            -> Mongo (set_user_features above)
#   2. Who can SIGN IN AT ALL (allowlist) -> the oauth2-emails.txt file, below
#
# oauth2-proxy is the hard perimeter: it only lets a Google account reach the
# app if its email is in this file. Feature grants are meaningless for someone
# who can't get past the door, so adding a brand-new person is fundamentally a
# *file* edit — not a Mongo write.
#
# CRITICAL — bind-mount safety:
#   In the api container this file is bind-mounted from the host at
#   /app/oauth2-emails.txt, the SAME host inode oauth2-proxy reads (read-only)
#   at /etc/oauth2/emails.txt. A single-file bind mount breaks if the file is
#   REPLACED (tempfile + os.replace gives the new content a new inode and the
#   container keeps pointing at the old one). So every write below is
#   TRUNCATE-IN-PLACE (open(path, "w")) — same inode, oauth2-proxy's mount stays
#   valid. Do NOT "improve" this to an atomic rename.
#
# Reload note: oauth2-proxy v7.7.1 does NOT hot-reload this file. The change is
# durable immediately but the sign-in gate only re-reads it on
# `docker compose --profile oauth restart oauth2-proxy`. The API surfaces that.

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _allowlist_path() -> str:
    """Resolve the oauth2 sign-in allowlist file path.

    In the api container the host file is bind-mounted at
    ``/app/oauth2-emails.txt`` (cwd == /app) — the same inode oauth2-proxy
    reads at ``/etc/oauth2/emails.txt`` — so a write here is exactly what the
    sign-in gate enforces. Falls back to the in-repo copy for local dev/tests.
    """
    candidates = [
        "oauth2-emails.txt",
        os.path.join(os.path.dirname(__file__), os.pardir, "oauth2-emails.txt"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


def _protected_emails() -> set[str]:
    """Emails that must NEVER be removable from the allowlist via the UI —
    removing one could lock the owner (or their spouse) out of sign-in. Always
    includes the admin + every HOUSE_OWNER email."""
    prot = {"ajaykandakatla@gmail.com"}
    try:
        prot |= set(_house_owner_emails())
    except Exception:
        pass
    return {e.lower() for e in prot}


def read_allowlist() -> list[dict]:
    """Ordered list of allowlist entries for the admin UI.

    Each row: ``{"email", "protected", "is_owner", "has_saved"}``. Comments and
    blank lines in the file are skipped; duplicates collapse to the first."""
    path = _allowlist_path()
    prot = _protected_emails()
    owners = set(_house_owner_emails())
    # Which emails already carry a saved per-user feature override.
    saved: set[str] = set()
    db = _get_db()
    if db is not None:
        try:
            for doc in db.user_features.find({}, {"user_email": 1}):
                ue = (doc.get("user_email") or "").lower()
                if ue:
                    saved.add(ue)
        except Exception:
            pass

    out: list[dict] = []
    seen: set[str] = set()
    try:
        with open(path) as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                lc = s.lower()
                if lc in seen:
                    continue
                seen.add(lc)
                out.append({
                    "email":     lc,
                    "protected": lc in prot,
                    "is_owner":  lc in owners,
                    "has_saved": lc in saved,
                })
    except FileNotFoundError:
        pass
    return out


def add_allowlist_email(email: str, *, added_by: str = "") -> dict:
    """Append an email to the sign-in allowlist (idempotent).

    Returns ``{"ok": bool, "email", "added": bool, "reason"?}``. ``added`` is
    False when the email was already present (still ``ok``)."""
    email_lc = (email or "").strip().lower()
    if not email_lc:
        return {"ok": False, "reason": "email required"}
    if not _EMAIL_RE.match(email_lc):
        return {"ok": False, "reason": "not a valid email address"}

    path = _allowlist_path()
    try:
        with open(path) as f:
            raw = f.read()
    except FileNotFoundError:
        raw = ""

    present = {
        ln.strip().lower()
        for ln in raw.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }
    if email_lc in present:
        return {"ok": True, "email": email_lc, "added": False, "reason": "already on the allowlist"}

    new = raw
    if new and not new.endswith("\n"):
        new += "\n"
    new += email_lc + "\n"
    try:
        # Truncate-in-place — preserves the single-file bind-mount inode.
        with open(path, "w") as f:
            f.write(new)
    except OSError as exc:
        log.warning("allowlist add failed for %s: %s", email_lc, exc)
        return {"ok": False, "reason": f"could not write allowlist: {exc}"}

    log.info("allowlist: added %s (by %s)", email_lc, (added_by or "?").lower())
    return {"ok": True, "email": email_lc, "added": True}


def remove_allowlist_email(email: str, *, removed_by: str = "") -> dict:
    """Remove an email from the sign-in allowlist.

    Refuses to remove a protected (owner/admin) email. Returns
    ``{"ok": bool, "email", "removed": bool, "reason"?}``. The user's saved
    feature override (if any) is intentionally left in Mongo so re-adding them
    later restores their prior access — matching list_users() behavior."""
    email_lc = (email or "").strip().lower()
    if not email_lc:
        return {"ok": False, "reason": "email required"}
    if email_lc in _protected_emails():
        return {"ok": False, "reason": "owner email cannot be removed"}

    path = _allowlist_path()
    try:
        with open(path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {"ok": False, "reason": "allowlist file not found"}

    kept: list[str] = []
    removed = False
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and s.lower() == email_lc:
            removed = True
            continue
        kept.append(line)

    if not removed:
        return {"ok": True, "email": email_lc, "removed": False, "reason": "was not on the allowlist"}

    try:
        # Truncate-in-place — see add_allowlist_email for why not os.replace.
        with open(path, "w") as f:
            f.write("".join(kept))
    except OSError as exc:
        log.warning("allowlist remove failed for %s: %s", email_lc, exc)
        return {"ok": False, "reason": f"could not write allowlist: {exc}"}

    log.info("allowlist: removed %s (by %s)", email_lc, (removed_by or "?").lower())
    return {"ok": True, "email": email_lc, "removed": True}
