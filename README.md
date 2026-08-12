# Eventtia Participant Approval

A small internal Streamlit tool for reviewing and approving/rejecting
participants of one Eventtia event. Eventtia stays the single source of
truth — the app has no database of its own.

## How it works

- **New** tab — participants whose native Eventtia status is `pending`.
  Each row has **Approve** and **Reject** buttons.
- **Approved** / **Rejected** tabs — read-only lists of everyone already
  processed.
- Approve/reject drive Eventtia's own registration-validation workflow
  directly (the same one behind "Validate registration" / "Reject
  registration" in the Eventtia UI) — not a custom field. No new field to
  create or configure.
- Before any action, the app re-checks the participant is still `pending`
  in Eventtia, so two people reviewing at the same time can't double-process
  someone. After the action, it re-fetches and verifies no other field
  changed.

## Two Eventtia API versions are involved

This was confirmed by hands-on testing against the real account (not
guessed from docs alone):

| | v3 | v4 |
|---|---|---|
| Used for | reading participants + their fields | the approve/reject actions |
| Auth | `POST /api/v3/auth` | `POST /api/v4/users/auth` (separate login, separate token) |
| Event identifier | `event_uri` slug, e.g. `pff-2026` | event **UUID** (different value, same event) |
| Key endpoints | `GET /events/:event_uri/attendees`, `GET .../attendees/:id` | `PUT /events/:event_uuid/attendees/:attendee_uuid/confirm`, `.../reject` |

v3's attendee response already includes a native `status` field
(`pending` / `confirmed` / ...) directly — that's what the app uses to
sort people into New/Approved/Rejected, so there's no custom field to
create in Eventtia at all.

**One thing worth double-checking once, in your own account:** the exact
string Eventtia returns after a *reject* action is assumed to be
`"rejected"` (confirm is confirmed to return `"confirmed"`). If your
account's reject action results in something else (e.g. `"declined"`,
`"cancelled"`), the app will raise a clear, visible error the first time
someone rejects a participant, telling you exactly what came back — at
which point set `EVENTTIA_REJECTED_STATUS_VALUE` in secrets to match, and
it'll work from then on.

## Project structure

```
eventtia-approval-app/
├── app.py               # Streamlit UI and navigation
├── eventtia_client.py    # All Eventtia API communication (v3 + v4)
├── utils.py              # Search/filter helpers + visual theme (CSS)
├── config.py             # Centralized settings
├── requirements.txt
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
└── README.md
```

## Setup

### 1. In Eventtia

You need two identifiers for the same event:

1. The **event_uri** slug — the part of the event's URL after `/events/`.
2. The **event UUID** — not shown in the UI directly; the easiest way to
   get it is to look at the `attendee.uuid` field on any participant via
   the v3 API (`GET /api/v3/events/:event_uri/attendees/:id`) — that's the
   attendee's uuid, not the event's. For the *event's* own UUID, check
   your account's API access docs/support, or capture it from a v4 request
   in your browser's network tab while using the Eventtia dashboard.

### 2. Configure secrets

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and
fill in real values (this file is gitignored and must never be committed):

```toml
EVENTTIA_AUTH_EMAIL = "you@yourcompany.com"
EVENTTIA_AUTH_PASSWORD = "your-eventtia-password"
EVENTTIA_EVENT_ID = "your-event-uri"
EVENTTIA_EVENT_UUID = "your-event-uuid"
```

### 3. Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Access control

Who can open this app at all is handled entirely by **Streamlit Community
Cloud's per-app viewer allow-list** — no login screen or password inside
the app itself. After deploying (see below), go to the app's **Share**
menu → "Who can view this app" → restrict to specific emails, and add
your reviewers there. Anyone not on the list is denied at the platform
level, before the app even loads.

One limitation worth knowing: as of Streamlit 1.42+, the app can't read
*which* allowed viewer is currently looking at it (`st.user` no longer
exposes the Community Cloud account email unless you set up your own
OIDC identity provider) — so there's no "signed in as ___" display or
per-user audit trail. If that becomes a real need later, it means adding
`[auth]` to secrets with an OIDC provider (Google, etc.) — a bigger step
than the allow-list, worth doing separately if needed.

## Deploying to Streamlit Community Cloud

1. Push this folder to a GitHub repository (secrets.toml is gitignored, so
   it won't be pushed — that's expected).
2. On [share.streamlit.io](https://share.streamlit.io), create a new app
   pointing at `app.py` in that repo.
3. In the app's **Settings → Secrets**, paste the contents of your local
   `secrets.toml`.
4. Deploy.

```
GitHub  →  Streamlit Community Cloud  →  Internal users  →  Eventtia API
```

## Notes

- The participant list is cached for `CACHE_TTL_SECONDS` (default 60s)
  and is invalidated immediately after every approve/reject, or when
  someone clicks **Refresh participants**.
- API credentials are only ever used server-side inside `eventtia_client.py`
  — never sent to the browser.
- To change which participant fields are displayed or searchable, edit
  `DISPLAY_FIELDS` / `SEARCHABLE_FIELDS` in `config.py`.
- To adjust the visual theme, edit the CSS variables at the top of
  `THEME_CSS` in `utils.py`.
