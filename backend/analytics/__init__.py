"""User-level usage analytics.

Tracks page views + dwell time per user per module so the admin can see
who's actually using what. Privacy-respecting: only stores email +
module + duration. No request bodies, no IPs, no per-click telemetry.

See `store.py` for schema + `api.py` for routes.
"""
