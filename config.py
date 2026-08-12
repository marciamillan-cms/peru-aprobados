"""
config.py
---------
Single place for every Eventtia-specific configuration value.

Nothing here is hardcoded with real secrets. Values are read from
Streamlit Secrets (st.secrets) when running on Streamlit Community Cloud,
and fall back to plain environment variables for local development.

Two Eventtia APIs are involved (confirmed by hands-on testing against the
real account):
  - v3 for reading data: listing participants and their custom fields.
    Addresses the event by its `event_uri` slug (e.g. "pff-2026").
  - v4 for the actual approve/reject actions: dedicated
    `.../attendees/:uuid/confirm` and `.../attendees/:uuid/reject`
    endpoints. Addresses the event by its UUID, and authenticates
    separately (`/users/auth`, its own token).

Both use the same account email/password; the app just needs to log into
each API version once and keep two tokens.
"""
import os
import streamlit as st


def _get(key: str, default=None):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        # st.secrets raises if no secrets.toml exists at all (e.g. local dev
        # without one) -- fall back to env vars in that case.
        pass
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# Eventtia credentials (shared by both API versions)
# ---------------------------------------------------------------------------
EVENTTIA_AUTH_EMAIL = _get("EVENTTIA_AUTH_EMAIL")
EVENTTIA_AUTH_PASSWORD = _get("EVENTTIA_AUTH_PASSWORD")

# ---------------------------------------------------------------------------
# v3 API -- reading participants + their custom fields
# ---------------------------------------------------------------------------
EVENTTIA_V3_BASE_URL = _get("EVENTTIA_V3_BASE_URL", "https://connect.eventtia.com/api/v3")
EVENTTIA_EVENT_URI = _get("EVENTTIA_EVENT_ID")  # the event_uri slug, e.g. "pff-2026"

# ---------------------------------------------------------------------------
# v4 API -- approve/reject actions
# ---------------------------------------------------------------------------
EVENTTIA_V4_BASE_URL = _get("EVENTTIA_V4_BASE_URL", "https://connect.eventtia.com/api/v4")
EVENTTIA_EVENT_UUID = _get("EVENTTIA_EVENT_UUID")  # the event's UUID (different from event_uri!)

# ---------------------------------------------------------------------------
# Native attendee status values
# ---------------------------------------------------------------------------
# These are Eventtia's own attendee.status values, confirmed by testing:
#   - a brand-new/unvalidated registration starts as "pending"
#   - PUT .../attendees/:uuid/confirm sets it to "confirmed"
#   - PUT .../attendees/:uuid/reject *should* set it to "rejected", but
#     this hasn't been confirmed with full certainty. If your account
#     returns something else (e.g. "declined", "cancelled"), change
#     STATUS_REJECTED below to match -- the app will also print a visible
#     warning if a reject action doesn't result in this expected value,
#     so the mismatch won't be silent.
STATUS_PENDING = "pending"
STATUS_APPROVED = "confirmed"
STATUS_REJECTED = _get("EVENTTIA_REJECTED_STATUS_VALUE", "rejected")

# If a participant's status is empty/unrecognized, treat them as pending.
DEFAULT_STATUS = STATUS_PENDING

# ---------------------------------------------------------------------------
# App behaviour
# ---------------------------------------------------------------------------
PAGE_SIZE = int(_get("EVENTTIA_PAGE_SIZE", 100))
CACHE_TTL_SECONDS = int(_get("CACHE_TTL_SECONDS", 60))
REQUEST_TIMEOUT_SECONDS = int(_get("REQUEST_TIMEOUT_SECONDS", 20))

# Attendee fields shown as columns/labels in the UI, in display order.
# These correspond to Eventtia's six default attendee custom fields.
DISPLAY_FIELDS = [
    "first_name",
    "last_name",
    "email",
    "company",
    "job_title",
    "telephone",
]

SEARCHABLE_FIELDS = ["first_name", "last_name", "email", "company", "job_title"]

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
# Local image files committed to the repo (e.g. under assets/). If a file
# doesn't exist, that logo is simply skipped -- the app never crashes over
# a missing logo.
COMPANY_LOGO_PATH = _get("COMPANY_LOGO_PATH", "assets/company_logo.png")
EVENT_LOGO_PATH = _get("EVENT_LOGO_PATH", "assets/event_logo.png")


def is_configured() -> bool:
    """True once the minimum settings needed to talk to Eventtia are present."""
    has_credentials = bool(EVENTTIA_AUTH_EMAIL and EVENTTIA_AUTH_PASSWORD)
    return bool(has_credentials and EVENTTIA_EVENT_URI and EVENTTIA_EVENT_UUID)


def missing_settings() -> list[str]:
    """Human-readable list of what's missing, for a friendly setup screen."""
    problems = []
    if not (EVENTTIA_AUTH_EMAIL and EVENTTIA_AUTH_PASSWORD):
        problems.append("EVENTTIA_AUTH_EMAIL + EVENTTIA_AUTH_PASSWORD")
    if not EVENTTIA_EVENT_URI:
        problems.append("EVENTTIA_EVENT_ID (the v3 event_uri slug)")
    if not EVENTTIA_EVENT_UUID:
        problems.append("EVENTTIA_EVENT_UUID (the v4 event UUID)")
    return problems
