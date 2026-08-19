"""
app.py
------
Streamlit UI and navigation for the Eventtia participant-approval tool.
All Eventtia communication lives in eventtia_client.py; this file only
renders the interface and wires up button clicks to that client.

Access control is handled entirely by Streamlit Community Cloud's per-app
viewer allow-list (Share -> "Who can view this app" -> restrict by email),
not by any code here -- see README.md for setup.
"""
import streamlit as st
from datetime import datetime

import config
import utils
from eventtia_client import ConflictError, EventtiaAPIError, EventtiaClient, IntegrityError, Participant

st.set_page_config(page_title="Validación de Participantes", page_icon="✅", layout="wide")
utils.inject_theme(st)

# ---------------------------------------------------------------------------
# Config gate -- fail loudly and helpfully rather than crashing later
# ---------------------------------------------------------------------------
if not config.is_configured():
    utils.render_brand_bar(st, "Validación de Participantes", config.COMPANY_LOGO_PATH, config.EVENT_LOGO_PATH)
    st.warning("La aplicación aún no está completamente configurada. Agregá lo siguiente en Streamlit Secrets:")
    for item in config.missing_settings():
        st.markdown(f"- `{item}`")
    st.caption("Ver .streamlit/secrets.toml.example en el repositorio para el formato esperado.")
    st.stop()


@st.cache_resource(show_spinner=False)
def get_client() -> EventtiaClient:
    return EventtiaClient()


def _cache_key():
    # Included in cache_data's key so "Refresh" can bust the cache on demand.
    return st.session_state.get("_refresh_token", 0)


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner="Cargando participantes desde Eventtia...")
def load_participants(_client: EventtiaClient, _cache_bust: int) -> list[Participant]:
    return _client.get_participants()


def refresh_data():
    st.session_state["_refresh_token"] = st.session_state.get("_refresh_token", 0) + 1
    load_participants.clear()


# ---------------------------------------------------------------------------
# Optimistic local tracking for approve/reject actions
# ---------------------------------------------------------------------------
# Eventtia's list endpoint (used to build these tabs) has been observed to
# lag behind the single-attendee endpoint (which we already verify against
# right after an approve/reject action succeeds) -- so a just-approved
# participant can still show up as "pending" in the list for a while.
# Rather than show stale/misleading data, we remember which ids we've
# successfully acted on and override their tab placement locally until
# Eventtia's list catches up on its own (checked automatically below, every
# time participants are loaded).
if "submitted_approval_ids" not in st.session_state:
    st.session_state["submitted_approval_ids"] = set()
if "submitted_rejection_ids" not in st.session_state:
    st.session_state["submitted_rejection_ids"] = set()

client = get_client()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
utils.render_brand_bar(st, "Validación de Participantes", config.COMPANY_LOGO_PATH, config.EVENT_LOGO_PATH)

top_l, top_r = st.columns([1, 5])
with top_l:
    if st.button("↻ Actualizar participantes", use_container_width=True):
        refresh_data()
        st.rerun()

# ---------------------------------------------------------------------------
# Load data (once per run; cached across runs until refresh/TTL)
# ---------------------------------------------------------------------------
try:
    participants = load_participants(client, _cache_key())
except EventtiaAPIError as exc:
    st.error(f"No se pudieron cargar los participantes desde Eventtia: {exc}")
    st.stop()

if config.TICKET_TYPE_FILTER:
    available_type_names = sorted(set(client.get_attendee_type_names().values()) - {""})
    normalized_target = EventtiaClient._normalize_ticket_name(config.TICKET_TYPE_FILTER)
    normalized_available = {EventtiaClient._normalize_ticket_name(n) for n in available_type_names}
    if normalized_target not in normalized_available:
        st.warning(
            f"No se encontró ningún tipo de entrada llamado \"{config.TICKET_TYPE_FILTER}\" en este evento "
            "-- la lista de participantes puede estar vacía por este motivo. "
            f"Tipos de entrada disponibles: {', '.join(available_type_names) if available_type_names else '(ninguno encontrado)'}. "
            "Revisá EVENTTIA_TICKET_TYPE_FILTER en la configuración."
        )

buckets = utils.split_by_status(participants)
pending = buckets[config.STATUS_PENDING]
approved = buckets[config.STATUS_APPROVED]
rejected = buckets[config.STATUS_REJECTED]

# Once Eventtia's list shows a participant as no longer pending, we don't
# need to keep overriding their tab placement anymore -- drop them from
# local tracking (whether the fresh data now agrees with us or not).
_pending_ids = {p.id for p in pending}
st.session_state["submitted_approval_ids"] &= _pending_ids
st.session_state["submitted_rejection_ids"] &= _pending_ids

submitted_approval_ids = st.session_state["submitted_approval_ids"]
submitted_rejection_ids = st.session_state["submitted_rejection_ids"]

# "New" excludes anyone we've already acted on locally, even if Eventtia's
# list hasn't caught up yet. Rejected participants are shown immediately
# in the Rechazados tab the same way; approved participants get their own
# transitional tab instead (see below), since that's specifically what was
# asked for.
new_display = [p for p in pending if p.id not in submitted_approval_ids and p.id not in submitted_rejection_ids]
submitted_display = [p for p in pending if p.id in submitted_approval_ids]
rejected_display = rejected + [p for p in pending if p.id in submitted_rejection_ids]

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


def render_card_open(p: Participant, badge_override: tuple[str, str] | None = None):
    if badge_override:
        badge_class, badge_label = badge_override
    else:
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
        st.session_state["submitted_approval_ids"].add(participant_id)
        st.toast("Se ha enviado el participante para su aprobación.", icon="📤")
    except ConflictError as exc:
        st.warning(str(exc))
    except IntegrityError as exc:
        st.error(str(exc))
    except EventtiaAPIError as exc:
        st.error(f"No se pudo actualizar el participante en Eventtia. Intentá nuevamente. ({exc})")
    finally:
        refresh_data()


def handle_reject(participant_id: str):
    try:
        client.reject_participant(participant_id)
        st.session_state["submitted_rejection_ids"].add(participant_id)
        st.toast("Participante rechazado.", icon="🚫")
    except ConflictError as exc:
        st.warning(str(exc))
    except IntegrityError as exc:
        st.error(str(exc))
    except EventtiaAPIError as exc:
        st.error(f"No se pudo actualizar el participante en Eventtia. Intentá nuevamente. ({exc})")
    finally:
        refresh_data()
        st.session_state.pop("confirm_reject_id", None)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_new, tab_submitted, tab_approved, tab_rejected = st.tabs(
    [
        f"Nuevos ({len(new_display)})",
        f"Enviados para aprobar ({len(submitted_display)})",
        f"Aprobados ({len(approved)})",
        f"Rechazados ({len(rejected_display)})",
    ]
)

# ---- New / Pending tab -----------------------------------------------------
with tab_new:
    query = st.text_input("Buscar participantes nuevos", placeholder="Buscar por nombre, email, empresa, cargo...", key="search_new")
    visible = utils.search_participants(new_display, query)

    confirm_id = st.session_state.get("confirm_reject_id")
    if confirm_id and any(p.id == confirm_id for p in new_display):
        target = next(p for p in new_display if p.id == confirm_id)
        st.warning(f"¿Estás seguro de rechazar a **{target.full_name}**? Esto actualizará Eventtia de inmediato.")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Confirmar rechazo", type="primary", key="confirm_reject_btn"):
                handle_reject(confirm_id)
                st.rerun()
        with c2:
            if st.button("Cancelar", key="cancel_reject_btn"):
                st.session_state.pop("confirm_reject_id", None)
                st.rerun()

    if not visible:
        st.info("No hay participantes pendientes por el momento." if not query else "No se encontraron coincidencias.")

    for p in visible:
        render_card_open(p)
        col1, col2, col_spacer = st.columns([1, 1, 4])
        with col1:
            if st.button("Aprobar", key=f"approve_{p.id}", type="primary", use_container_width=True):
                handle_approve(p.id)
                st.rerun()
        with col2:
            if st.button("Rechazar", key=f"reject_{p.id}", use_container_width=True):
                st.session_state["confirm_reject_id"] = p.id
                st.rerun()
        render_card_close()

# ---- Submitted-for-approval tab (read-only, transitional) ------------------
with tab_submitted:
    st.caption(
        "Estos participantes ya fueron aprobados en Eventtia. Pueden tardar unos minutos en "
        "aparecer en la pestaña Aprobados mientras Eventtia actualiza sus datos."
    )
    if not submitted_display:
        st.info("No hay participantes enviados para aprobación en este momento.")
    for p in submitted_display:
        render_card_open(p, badge_override=("badge-approved", "Enviado"))
        render_card_close()

# ---- Approved tab (read-only) ----------------------------------------------
with tab_approved:
    query = st.text_input("Buscar participantes aprobados", placeholder="Buscar por nombre, email, empresa, cargo...", key="search_approved")
    visible = utils.search_participants(approved, query)

    if visible:
        excel_bytes = utils.build_participants_excel(visible)
        st.download_button(
            label="⬇ Descargar aprobados",
            data=excel_bytes,
            file_name=f"participantes_aprobados_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=False,
        )

    st.caption(f"{len(visible)} de {len(approved)} participantes aprobados mostrados.")
    if not visible:
        st.info("Todavía no hay participantes aprobados." if not query else "No se encontraron coincidencias.")
    for p in visible:
        render_card_open(p)
        render_card_close()

# ---- Rejected tab (read-only) -----------------------------------------------
with tab_rejected:
    query = st.text_input("Buscar participantes rechazados", placeholder="Buscar por nombre, email, empresa, cargo...", key="search_rejected")
    visible = utils.search_participants(rejected_display, query)
    st.caption(f"{len(visible)} de {len(rejected_display)} participantes rechazados mostrados.")
    if not visible:
        st.info("No hay participantes rechazados." if not query else "No se encontraron coincidencias.")
    for p in visible:
        render_card_open(p)
        render_card_close()
