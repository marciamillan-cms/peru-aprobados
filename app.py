"""
app.py
------
Streamlit UI and navigation for the Eventtia participant-approval tool.
All Eventtia communication lives in eventtia_client.py; this file only
renders the interface and wires up button clicks to that client.
"""
import streamlit as st

import auth
import config
import utils
from eventtia_client import ConflictError, EventtiaAPIError, EventtiaClient, IntegrityError, Participant

st.set_page_config(page_title="Participant Validation", page_icon="✅", layout="wide")
utils.inject_theme(st)

# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------
if not auth.login_form():
    st.stop()

# ---------------------------------------------------------------------------
# Config gate -- fail loudly and helpfully rather than crashing later
# ---------------------------------------------------------------------------
if not config.is_configured():
    st.markdown('<div class="brand-bar"><h1><span class="brand-mark"></span>Participant Validation</h1></div>', unsafe_allow_html=True)
    st.warning("This app isn't fully configured yet. Add the following to Streamlit Secrets:")
    for item in config.missing_settings():
        st.markdown(f"- `{item}`")
    st.caption("See .streamlit/secrets.toml.example in the repo for the expected format.")
    st.stop()


@st.cache_resource(show_spinner=False)
def get_client() -> EventtiaClient:
    return EventtiaClient()


def _cache_key():
    # Included in cache_data's key so "Refresh" can bust the cache on demand.
    return st.session_state.get("_refresh_token", 0)


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner="Loading participants from Eventtia...")
def load_participants(_client: EventtiaClient, _cache_bust: int) -> list[Participant]:
    return _client.get_participants()


def refresh_data():
    st.session_state["_refresh_token"] = st.session_state.get("_refresh_token", 0) + 1
    load_participants.clear()


client = get_client()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
header_col1, header_col2 = st.columns([6, 1])
with header_col1:
    st.markdown(
        f"""
        <div class="brand-bar">
            <h1><span class="brand-mark"></span>Participant Validation</h1>
            <span class="user-pill">Signed in as {auth.current_user()}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

top_l, top_r = st.columns([1, 5])
with top_l:
    if st.button("↻ Refresh participants", use_container_width=True):
        refresh_data()
        st.rerun()
with top_r:
    if st.button("Log out"):
        auth.logout()
        st.rerun()

# ---------------------------------------------------------------------------
# Load data (once per run; cached across runs until refresh/TTL)
# ---------------------------------------------------------------------------
try:
    participants = load_participants(client, _cache_key())
except EventtiaAPIError as exc:
    st.error(f"Could not load participants from Eventtia: {exc}")
    st.stop()

buckets = utils.split_by_status(participants)
pending = buckets[config.STATUS_PENDING]
approved = buckets[config.STATUS_APPROVED]
rejected = buckets[config.STATUS_REJECTED]

# ---------------------------------------------------------------------------
# Card + action rendering
# ---------------------------------------------------------------------------
def render_meta(p: Participant) -> str:
    rows = []
    for f in ["email", "company", "job_title", "telephone"]:
        value = p.get(f)
        if value:
            rows.append(f"<b>{utils.field_label(f)}:</b> {value}")
    return " &nbsp;·&nbsp; ".join(rows)


def render_card_open(p: Participant):
    badge_class = utils.STATUS_BADGE_CLASS.get(p.status, "badge-pending")
    badge_label = utils.STATUS_LABELS.get(p.status, p.status.title())
    st.markdown(
        f"""
        <div class="participant-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                    <div class="p-name">{p.full_name}</div>
                    <div class="p-role">{p.get('job_title')}{' · ' + p.get('company') if p.get('company') else ''}</div>
                </div>
                <span class="badge {badge_class}">{badge_label}</span>
            </div>
            <div class="p-meta">{render_meta(p)}</div>
        """,
        unsafe_allow_html=True,
    )


def render_card_close():
    st.markdown("</div>", unsafe_allow_html=True)


def handle_approve(participant_id: str):
    try:
        client.approve_participant(participant_id)
        st.toast("Participant approved successfully.", icon="✅")
    except ConflictError as exc:
        st.warning(str(exc))
    except IntegrityError as exc:
        st.error(str(exc))
    except EventtiaAPIError as exc:
        st.error(f"Could not update the participant in Eventtia. Please try again. ({exc})")
    finally:
        refresh_data()


def handle_reject(participant_id: str):
    try:
        client.reject_participant(participant_id)
        st.toast("Participant rejected.", icon="🚫")
    except ConflictError as exc:
        st.warning(str(exc))
    except IntegrityError as exc:
        st.error(str(exc))
    except EventtiaAPIError as exc:
        st.error(f"Could not update the participant in Eventtia. Please try again. ({exc})")
    finally:
        refresh_data()
        st.session_state.pop("confirm_reject_id", None)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_new, tab_approved, tab_rejected = st.tabs(
    [f"New ({len(pending)})", f"Approved ({len(approved)})", f"Rejected ({len(rejected)})"]
)

# ---- New / Pending tab -----------------------------------------------------
with tab_new:
    query = st.text_input("Search new participants", placeholder="Search by name, email, company, position...", key="search_new")
    visible = utils.search_participants(pending, query)

    confirm_id = st.session_state.get("confirm_reject_id")
    if confirm_id and any(p.id == confirm_id for p in pending):
        target = next(p for p in pending if p.id == confirm_id)
        st.warning(f"Are you sure you want to reject **{target.full_name}**? This will update Eventtia immediately.")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Confirm rejection", type="primary", key="confirm_reject_btn"):
                handle_reject(confirm_id)
                st.rerun()
        with c2:
            if st.button("Cancel", key="cancel_reject_btn"):
                st.session_state.pop("confirm_reject_id", None)
                st.rerun()

    if not visible:
        st.info("No pending participants right now." if not query else "No matches for that search.")

    for p in visible:
        render_card_open(p)
        col1, col2, col_spacer = st.columns([1, 1, 4])
        with col1:
            if st.button("Approve", key=f"approve_{p.id}", type="primary", use_container_width=True):
                handle_approve(p.id)
                st.rerun()
        with col2:
            if st.button("Reject", key=f"reject_{p.id}", use_container_width=True):
                st.session_state["confirm_reject_id"] = p.id
                st.rerun()
        render_card_close()

# ---- Approved tab (read-only) ----------------------------------------------
with tab_approved:
    query = st.text_input("Search approved participants", placeholder="Search by name, email, company, position...", key="search_approved")
    visible = utils.search_participants(approved, query)
    st.caption(f"{len(visible)} of {len(approved)} approved participants shown.")
    if not visible:
        st.info("No approved participants yet." if not query else "No matches for that search.")
    for p in visible:
        render_card_open(p)
        render_card_close()

# ---- Rejected tab (read-only) -----------------------------------------------
with tab_rejected:
    query = st.text_input("Search rejected participants", placeholder="Search by name, email, company, position...", key="search_rejected")
    visible = utils.search_participants(rejected, query)
    st.caption(f"{len(visible)} of {len(rejected)} rejected participants shown.")
    if not visible:
        st.info("No rejected participants." if not query else "No matches for that search.")
    for p in visible:
        render_card_open(p)
        render_card_close()
