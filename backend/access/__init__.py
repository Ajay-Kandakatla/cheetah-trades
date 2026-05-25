"""Per-user feature access control.

The admin (Ajay) decides which menu items + pages each signed-in user
can see. Defaults give every authenticated user the trading-focused
pages; household-private pages (food, kids, house) require an
explicit grant.

See store.py for the storage layer and api.py for the HTTP routes.
"""
from .store import (  # noqa: F401
    FEATURE_CATALOG,
    DEFAULT_FEATURES,
    RESTRICTED_FEATURES,
    build_menu,
    get_user_features,
    set_user_features,
    list_users,
    user_has_feature,
)
from .api import router  # noqa: F401
