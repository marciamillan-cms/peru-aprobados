"""
eventtia_client.py
-------------------
The only module in this app that talks to Eventtia. Everything else
(app.py, utils.py) goes through the EventtiaClient defined here.

Two API versions, confirmed by hands-on testing against the real account:

  v3 -- reading data
      POST /api/v3/auth
          email/password -> JWT (~30 day validity).
      GET  /api/v3/events/:event_uri/attendee_types?include=attendee_type_custom_fields
          Custom field *definitions* (id -> name/alias), used once (cached)
          to turn each attendee's opaque {field_id: value} map into
          readable labels like "first_name" / "company".
      GET  /api/v3/events/:event_uri/attendees
          List participants (paginated). Each attendee's response includes
          a native `status` attribute directly -- "pending", "confirmed",
          etc -- so no custom field is needed to track approval state.
      GET  /api/v3/events/:event_uri/attendees/:attendee_id
          Fetch one participant (by numeric id).

  v4 -- the actual approve/reject actions
      POST /api/v4/users/auth
          email/password -> a *different* token (separate login, separate
          session from v3).
      PUT  /api/v4/events/:event_uuid/attendees/:attendee_uuid/confirm
          Confirms (approves) a pending registration. Sets status to
          "confirmed". Confirmed working against the real account.
      PUT  /api/v4/events/:event_uuid/attendees/:attendee_uuid/reject
          Rejects a pending registration. Confirmed working against the
          real account; the exact resulting status string
          (config.STATUS_REJECTED) should be double-checked against your
          own test output -- see the warning logic in
          `_verify_status_change` below.

  v3 and v4 identify the SAME attendee differently: v3 uses the numeric
  attendee id in some places and exposes a `uuid` attribute; v4's actions
  are keyed by that same `uuid`. v3 also addresses the event by its
  `event_uri` slug, while v4 addresses it by the event's UUID -- these are
  different identifiers for the same event, both configured separately.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

import config


class EventtiaAPIError(Exception):
    """Raised for any Eventtia API failure (network, auth, 4xx/5xx, ...)."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class ConflictError(EventtiaAPIError):
    """Raised when a participant was already processed by someone else."""


class IntegrityError(EventtiaAPIError):
    """
    Raised when, after an approve/reject action, a custom field appears to
    have changed, or the resulting status wasn't the expected one. This
    should never happen; it exists so the app can loudly surface it
    instead of silently trusting Eventtia.
    """


@dataclass
class Participant:
    id: str
    uuid: str
    status: str
    attendee_type_id: str = ""
    attendee_type_name: str = ""
    fields: dict = field(default_factory=dict)     # readable name -> value
    raw_fields: dict = field(default_factory=dict)  # field_id -> value (as returned by Eventtia)
    updated_at: Optional[str] = None

    def get(self, name: str, default: str = "") -> str:
        value = self.fields.get(name, default)
        return value if value is not None else default

    @property
    def full_name(self) -> str:
        name = f"{self.get('first_name')} {self.get('last_name')}".strip()
        return name or f"Participant {self.id}"


class EventtiaClient:
    def __init__(
        self,
        v3_base_url: str = None,
        v4_base_url: str = None,
        event_uri: str = None,
        event_uuid: str = None,
        auth_email: str = None,
        auth_password: str = None,
        timeout: int = None,
    ):
        self.v3_base_url = (v3_base_url or config.EVENTTIA_V3_BASE_URL).rstrip("/")
        self.v4_base_url = (v4_base_url or config.EVENTTIA_V4_BASE_URL).rstrip("/")
        self.event_uri = event_uri or config.EVENTTIA_EVENT_URI
        self.event_uuid = event_uuid or config.EVENTTIA_EVENT_UUID
        self.timeout = timeout or config.REQUEST_TIMEOUT_SECONDS

        self._auth_email = auth_email or config.EVENTTIA_AUTH_EMAIL
        self._auth_password = auth_password or config.EVENTTIA_AUTH_PASSWORD

        self._v3_token: Optional[str] = None
        self._v4_token: Optional[str] = None
        self._field_defs: Optional[dict] = None  # field_id -> {"name":..., "alias":...}
        self._attendee_type_names: Optional[dict] = None  # attendee_type_id -> name

    # ------------------------------------------------------------------
    # Auth -- v3 and v4 are separate logins, separate tokens
    # ------------------------------------------------------------------
    def _require_credentials(self):
        if not (self._auth_email and self._auth_password):
            raise EventtiaAPIError(
                "No Eventtia credentials configured. Set EVENTTIA_AUTH_EMAIL + "
                "EVENTTIA_AUTH_PASSWORD in Streamlit Secrets."
            )

    def _ensure_v3_token(self):
        if self._v3_token:
            return
        self._require_credentials()
        try:
            resp = requests.post(
                f"{self.v3_base_url}/auth",
                json={"email": self._auth_email, "password": self._auth_password},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise EventtiaAPIError(f"Network error while authenticating with Eventtia (v3): {exc}") from exc
        if resp.status_code != 200:
            raise EventtiaAPIError("Could not authenticate with Eventtia (v3). Check credentials.", resp.status_code)
        self._v3_token = resp.json().get("auth_token")
        if not self._v3_token:
            raise EventtiaAPIError("Eventtia v3 authentication response did not include a token.")

    def _ensure_v4_token(self):
        if self._v4_token:
            return
        self._require_credentials()
        try:
            resp = requests.post(
                f"{self.v4_base_url}/users/auth",
                json={"email": self._auth_email, "password": self._auth_password},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise EventtiaAPIError(f"Network error while authenticating with Eventtia (v4): {exc}") from exc
        if resp.status_code != 200:
            raise EventtiaAPIError("Could not authenticate with Eventtia (v4). Check credentials.", resp.status_code)
        try:
            self._v4_token = resp.json()["data"]["token"]
        except (KeyError, TypeError, ValueError):
            self._v4_token = None
        if not self._v4_token:
            raise EventtiaAPIError("Eventtia v4 authentication response did not include a token.")

    # ------------------------------------------------------------------
    # Low-level request helpers
    # ------------------------------------------------------------------
    def _v3_request(self, method: str, path: str, params: dict = None, json_body: dict = None) -> Any:
        self._ensure_v3_token()
        url = f"{self.v3_base_url}{path}"
        headers = {"Authorization": f"Bearer {self._v3_token}"}
        try:
            resp = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise EventtiaAPIError(f"Network error while contacting Eventtia: {exc}") from exc

        if resp.status_code == 401:
            self._v3_token = None
            self._ensure_v3_token()
            headers = {"Authorization": f"Bearer {self._v3_token}"}
            try:
                resp = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=self.timeout)
            except requests.RequestException as exc:
                raise EventtiaAPIError(f"Network error while contacting Eventtia: {exc}") from exc

        return self._handle_response(resp)

    def _v4_request(self, method: str, path: str, params: dict = None, json_body: dict = None) -> requests.Response:
        """Returns the raw Response (not parsed JSON) since callers need the status code."""
        self._ensure_v4_token()
        url = f"{self.v4_base_url}{path}"
        headers = {"Authorization": f"Bearer {self._v4_token}"}
        try:
            resp = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise EventtiaAPIError(f"Network error while contacting Eventtia: {exc}") from exc

        if resp.status_code == 401:
            self._v4_token = None
            self._ensure_v4_token()
            headers = {"Authorization": f"Bearer {self._v4_token}"}
            try:
                resp = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=self.timeout)
            except requests.RequestException as exc:
                raise EventtiaAPIError(f"Network error while contacting Eventtia: {exc}") from exc
        return resp

    @staticmethod
    def _handle_response(resp: requests.Response) -> Any:
        if resp.status_code == 404:
            raise EventtiaAPIError("The requested Eventtia resource was not found.", 404)
        if resp.status_code == 403:
            raise EventtiaAPIError("Your Eventtia credentials don't have access to this resource.", 403)
        if resp.status_code >= 500:
            raise EventtiaAPIError("Eventtia's API is temporarily unavailable. Please try again shortly.", resp.status_code)
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("message", "")
            except Exception:
                pass
            raise EventtiaAPIError(f"Eventtia rejected the request ({resp.status_code}). {detail}".strip(), resp.status_code)
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Field definitions (id -> readable name), v3
    # ------------------------------------------------------------------
    def get_field_definitions(self, force_refresh: bool = False) -> dict:
        if self._field_defs is not None and not force_refresh:
            return self._field_defs

        data = self._v3_request(
            "GET",
            f"/events/{self.event_uri}/attendee_types",
            params={"include": "attendee_type_custom_fields", "page[size]": 100},
        )
        defs: dict = {}
        for item in (data or {}).get("included", []) or []:
            if item.get("type") != "attendee_type_custom_fields":
                continue
            attrs = item.get("attributes", {})
            defs[str(item["id"])] = {
                "name": attrs.get("name") or f"field_{item['id']}",
                "alias": attrs.get("alias"),
            }
        self._field_defs = defs

        # Same response also lists the attendee TYPES themselves (the
        # "tickets": General, VIP, Invitados Cámara, ...) -- cache their
        # names too, keyed by id, so participants can be filtered/labeled
        # by ticket type without a second request.
        type_names: dict = {}
        for item in (data or {}).get("data", []) or []:
            if item.get("type") != "attendee_types":
                continue
            type_names[str(item["id"])] = item.get("attributes", {}).get("name", "")
        self._attendee_type_names = type_names

        return defs

    def get_attendee_type_names(self) -> dict:
        """{attendee_type_id: name} for every ticket/attendee type on this event."""
        if self._attendee_type_names is None:
            self.get_field_definitions()
        return self._attendee_type_names or {}

    # ------------------------------------------------------------------
    # Participants (reads, v3)
    # ------------------------------------------------------------------
    def _normalize(self, attendee: dict, field_defs: dict, type_names: dict) -> Participant:
        attrs = attendee.get("attributes", {})
        raw_fields = attrs.get("fields", {}) or {}

        readable = {}
        for field_id, value in raw_fields.items():
            info = field_defs.get(str(field_id))
            key = info["name"] if info else f"field_{field_id}"
            readable[key] = value

        status = (attrs.get("status") or config.DEFAULT_STATUS).strip().lower()

        attendee_type_id = str(
            (attendee.get("relationships", {}) or {}).get("attendee_type", {}).get("data", {}).get("id", "")
        )
        attendee_type_name = type_names.get(attendee_type_id, "")

        return Participant(
            id=str(attendee.get("id")),
            uuid=attrs.get("uuid", ""),
            status=status,
            attendee_type_id=attendee_type_id,
            attendee_type_name=attendee_type_name,
            fields=readable,
            raw_fields=raw_fields,
            updated_at=attrs.get("updated_at"),
        )

    @staticmethod
    def _normalize_ticket_name(name: str) -> str:
        """Case/accent-insensitive comparison key, so 'Invitados Cámara',
        'invitados camara', 'INVITADOS CÁMARA' etc all match the same
        configured filter value."""
        import unicodedata

        if not name:
            return ""
        decomposed = unicodedata.normalize("NFKD", name)
        without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
        return without_accents.strip().lower()

    def get_participants(self) -> list[Participant]:
        field_defs = self.get_field_definitions()
        type_names = self.get_attendee_type_names()
        participants: list[Participant] = []
        page_number = 1
        total_pages = 1

        while page_number <= total_pages:
            data = self._v3_request(
                "GET",
                f"/events/{self.event_uri}/attendees",
                params={"page[size]": config.PAGE_SIZE, "page[number]": page_number},
            )
            for attendee in (data or {}).get("data", []) or []:
                participants.append(self._normalize(attendee, field_defs, type_names))

            total_pages = (data or {}).get("meta", {}).get("total_pages", 1) or 1
            page_number += 1

        if config.TICKET_TYPE_FILTER:
            target = self._normalize_ticket_name(config.TICKET_TYPE_FILTER)
            participants = [p for p in participants if self._normalize_ticket_name(p.attendee_type_name) == target]

        return participants

    def get_participant(self, participant_id: str) -> Participant:
        field_defs = self.get_field_definitions()
        type_names = self.get_attendee_type_names()
        data = self._v3_request("GET", f"/events/{self.event_uri}/attendees/{participant_id}")
        attendee = (data or {}).get("data")
        if not attendee:
            raise EventtiaAPIError(f"Participant {participant_id} was not found in Eventtia.")
        return self._normalize(attendee, field_defs, type_names)

    # ------------------------------------------------------------------
    # Approve / Reject (writes, v4)
    # ------------------------------------------------------------------
    def _run_action(self, participant_id: str, action: str, expected_status: str) -> Participant:
        """
        Shared logic for confirm/reject:
          1. Re-fetch (v3) and check the participant is still 'pending'
             (multi-user race guard).
          2. Call the v4 action endpoint on their uuid.
          3. Re-fetch (v3) and verify: no custom field changed, and warn
             (rather than silently trust) if the resulting status isn't
             exactly what we expected.
        """
        before = self.get_participant(participant_id)
        if before.status != config.STATUS_PENDING:
            raise ConflictError(
                f"This participant is already '{before.status}' -- it looks like another "
                "user already processed them."
            )
        if not before.uuid:
            raise EventtiaAPIError("This participant has no uuid on record -- cannot run the action.")

        resp = self._v4_request("PUT", f"/events/{self.event_uuid}/attendees/{before.uuid}/{action}")
        if resp.status_code == 422:
            raise ConflictError("Eventtia reports this participant was no longer pending when the action ran.")
        if resp.status_code >= 400:
            raise EventtiaAPIError(f"Eventtia rejected the {action} action ({resp.status_code}).", resp.status_code)

        time.sleep(0.3)  # small buffer for eventual consistency before re-reading
        after = self.get_participant(participant_id)

        # Custom fields must be untouched by an approve/reject action.
        if before.raw_fields != after.raw_fields:
            raise IntegrityError(
                f"Safety check failed: participant fields changed after the '{action}' action, "
                "which should only affect status. Check this participant in Eventtia directly."
            )

        if after.status != expected_status:
            # Don't hide this -- surface exactly what happened so the
            # expected status value in config.py can be corrected.
            raise IntegrityError(
                f"The '{action}' action ran, but the resulting status was '{after.status}', "
                f"not the expected '{expected_status}'. Update config.py's expected status value "
                "to match, then try again."
            )
        return after

    def approve_participant(self, participant_id: str) -> Participant:
        return self._run_action(participant_id, "confirm", config.STATUS_APPROVED)

    def reject_participant(self, participant_id: str) -> Participant:
        return self._run_action(participant_id, "reject", config.STATUS_REJECTED)
