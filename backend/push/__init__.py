"""Web Push notifications for the app.

Push delivery uses VAPID-authenticated Web Push (W3C standard). Works on:
  - iOS Safari 16.4+ (only when the site is installed as a PWA on home screen)
  - Android Chrome / Firefox / Edge (no install required)
  - Desktop Chrome / Firefox / Edge / Safari

Subscriptions live in Mongo ``push_subscriptions`` and are keyed by endpoint.

VAPID keypair is generated once on first call to ``vapid_keys()`` and stored
in the ``app_config`` collection so it survives restarts.

Module layout
-------------
keys.py     VAPID keypair generation + persistence
subs.py     Subscription CRUD
sender.py   Push delivery
hooks.py    Wires sources (breakouts, etc.) to push delivery
"""
from push import keys, subs, sender, hooks  # noqa: F401
