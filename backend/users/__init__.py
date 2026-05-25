"""User profile cache.

Pulls display_name + picture from Google's /oauth2/v3/userinfo endpoint
on first sign-in, then serves cached values from Mongo. Without this the
frontend can only show the email handle.
"""
from users import store  # noqa: F401
