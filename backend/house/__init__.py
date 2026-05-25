"""Personal real-estate dashboard.

Owner-only (gated to HOUSE_OWNER_EMAIL via auth.require_house_owner).
Tracks one house listing across Redfin / Zillow / Realtor.com, persists
daily snapshots so we can graph interest over time, and emits a daily
playbook based on days-on-market + comp set.
"""
