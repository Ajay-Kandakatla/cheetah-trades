"""👥 Long Term shared viewers (2026-11-18). Ajay: "Can you also make Long Term portfolio accessible to Chiru and Naresh..
Chiru has two names". `C.SHARED_VIEWER_EMAILS` read the same payload as the owner; everyone else still gets exactly the
owner_only block. NEGATIVES: a near-miss address, Doug, no email and a blank email stay locked; the list holds exactly the
three allowlisted addresses; the viewer path never builds a week.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from long_term_list import api as API
from long_term_list import constants as C
from tests.test_long_term_list_api import OWNER, OWNER_ONLY, _strict, db, wired  # noqa: F401  (fixtures)

CHIRU_1 = "chiranjeevikarkolla@gmail.com"
CHIRU_2 = "chiru01020304@gmail.com"
NARESH = "korvi.nareshkumar@gmail.com"


def test_the_list_is_exactly_his_three_addresses():
    assert C.SHARED_VIEWER_EMAILS == frozenset({CHIRU_1, CHIRU_2, NARESH})
    assert all(e == e.strip().lower() for e in C.SHARED_VIEWER_EMAILS)


def test_every_viewer_is_on_the_sign_in_allowlist():
    allow = (Path(__file__).resolve().parents[1] / "oauth2-emails.txt").read_text().lower().split()
    assert C.SHARED_VIEWER_EMAILS <= set(allow)


@pytest.mark.parametrize("email", [CHIRU_1, CHIRU_2, NARESH, "  Chiru01020304@Gmail.com  "])
def test_a_viewer_reads_the_same_payload_as_the_owner(wired, email):
    mine = _strict(wired.get(C.API_PATH, headers={"X-User-Email": OWNER}).text)
    r = wired.get(C.API_PATH, headers={"X-User-Email": email})
    assert r.status_code == 200
    body = _strict(r.text)
    assert body != OWNER_ONLY and body["state"] == mine["state"]
    assert body["categories"] == mine["categories"]


@pytest.mark.parametrize("email", ["doug@example.com", "chiranjeevikarkolla@gmail.co", "xchiru01020304@gmail.com",
                                   "korvi.nareshkumar@gmail.com.evil.com", "", "   "])
def test_NEGATIVE_anyone_else_is_still_locked(wired, email):
    r = wired.get(C.API_PATH, headers={"X-User-Email": email} if email else {})
    assert _strict(r.text) == OWNER_ONLY
    assert wired.closes_calls == []


@pytest.mark.parametrize("val", [None, 0, [], {}, b"chiru01020304@gmail.com"])
def test_NEGATIVE_non_strings_are_never_viewers(val):
    assert API._is_shared_viewer(val) is False
