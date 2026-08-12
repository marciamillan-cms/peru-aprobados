"""
utils.py
--------
Formatting, filtering/search, status-label helpers, and the custom CSS
that gives the app the look of the Peru Fintech Forum website (dark,
modern, gradient-accented fintech branding) instead of a default
Streamlit dashboard.

Note on the visual design: perufintechforum.com is a Framer site without a
public style guide, so the palette below is a close, best-effort reading of
its dark, high-contrast, gradient-accented fintech aesthetic rather than a
pixel-perfect extraction of its stylesheet. Every color/spacing value is a
CSS variable at the top of THEME_CSS, so the team can fine-tune them in one
place after comparing side-by-side with the live site.
"""
from __future__ import annotations

import config
from eventtia_client import Participant

STATUS_LABELS = {
    config.STATUS_PENDING: "Nuevos",
    config.STATUS_APPROVED: "Aprobados",
    config.STATUS_REJECTED: "Rechazados",
}

STATUS_BADGE_CLASS = {
    config.STATUS_PENDING: "badge-pending",
    config.STATUS_APPROVED: "badge-approved",
    config.STATUS_REJECTED: "badge-rejected",
}


def split_by_status(participants: list[Participant]) -> dict[str, list[Participant]]:
    buckets = {config.STATUS_PENDING: [], config.STATUS_APPROVED: [], config.STATUS_REJECTED: []}
    for p in participants:
        buckets.setdefault(p.status, []).append(p)
    return buckets


def search_participants(participants: list[Participant], query: str) -> list[Participant]:
    if not query:
        return participants
    q = query.strip().lower()
    if not q:
        return participants

    def matches(p: Participant) -> bool:
        for field_name in config.SEARCHABLE_FIELDS:
            value = p.get(field_name)
            if value and q in str(value).lower():
                return True
        return False

    return [p for p in participants if matches(p)]


def field_label(field_name: str) -> str:
    return {
        "first_name": "Nombre",
        "last_name": "Apellido",
        "email": "Correo electrónico",
        "company": "Empresa",
        "job_title": "Cargo",
        "telephone": "Teléfono",
    }.get(field_name, field_name.replace("_", " ").title())


THEME_CSS = """
<style>
:root {
    /* Colors sampled directly from perufintechforum.com: deep navy
    background, vibrant emerald-green accent, white text. */
    --bg: #0E1B30;
    --surface: #16253F;
    --surface-alt: #1D2E4C;
    --border: #2C4066;
    --text: #FFFFFF;
    --text-muted: #A9B7D0;
    --accent-1: #19D882;
    --accent-2: #12B87A;
    --accent-gradient: linear-gradient(90deg, var(--accent-1), var(--accent-2));
    --success: #19D882;
    --success-bg: rgba(25, 216, 130, 0.14);
    --danger: #F5484B;
    --danger-bg: rgba(245, 72, 75, 0.14);
    --warning: #F5A623;
    --warning-bg: rgba(245, 166, 35, 0.14);
    --radius: 18px;
    --radius-sm: 999px;
    --shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Poppins', -apple-system, BlinkMacSystemFont, sans-serif;
}

.stApp {
    background: radial-gradient(circle at 10% 0%, rgba(25, 216, 130, 0.16), transparent 40%),
                radial-gradient(circle at 90% 15%, rgba(18, 184, 122, 0.12), transparent 45%),
                var(--bg);
    color: var(--text);
}

#MainMenu, header[data-testid="stHeader"], footer {visibility: hidden;}
.block-container {padding-top: 1.5rem; max-width: 1200px;}

/* ---- Header / brand bar ---- */
.brand-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.8rem;
    margin-bottom: 1.5rem;
    background: rgba(29, 46, 76, 0.75);
    border: 1px solid var(--border);
    border-radius: 999px;
    box-shadow: var(--shadow);
    backdrop-filter: blur(6px);
}
.brand-bar h1 {
    font-size: 1.1rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: 0.01em;
}
.brand-bar .brand-mark {
    display: inline-block;
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--accent-gradient);
    margin-right: 0.6rem;
    box-shadow: 0 0 10px rgba(25, 216, 130, 0.7);
}
.brand-logos {
    display: flex;
    align-items: center;
    gap: 1rem;
}
.brand-logo {
    height: 32px;
    max-width: 140px;
    object-fit: contain;
}

/* ---- Participant card ---- */
.participant-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.1rem 1.3rem;
    margin-bottom: 0.9rem;
    box-shadow: var(--shadow);
}
.participant-card .p-name {
    font-size: 1.05rem;
    font-weight: 700;
    margin-bottom: 0.15rem;
}
.participant-card .p-role {
    color: var(--text-muted);
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
}
.participant-card .p-meta {
    font-size: 0.85rem;
    color: var(--text-muted);
    line-height: 1.5;
}
.participant-card .p-meta b { color: var(--text); font-weight: 500; }

/* ---- Status badges ---- */
.badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    padding: 0.22rem 0.65rem;
    border-radius: 999px;
}
.badge-pending { color: var(--warning); background: var(--warning-bg); }
.badge-approved { color: var(--success); background: var(--success-bg); }
.badge-rejected { color: var(--danger); background: var(--danger-bg); }

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] { gap: 0.5rem; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] {
    color: var(--text-muted);
    font-weight: 600;
    padding: 0.6rem 1rem;
}
.stTabs [aria-selected="true"] {
    color: var(--text) !important;
    border-bottom: 2px solid var(--accent-1);
}

/* ---- Buttons -- fully rounded pills, matching the site's CTAs ---- */
.stButton > button {
    border-radius: 999px;
    border: 1px solid var(--border);
    font-weight: 600;
    padding: 0.5rem 1.3rem;
}
.stButton > button[kind="primary"] {
    background: var(--accent-gradient);
    border: none;
    color: #fff;
    font-weight: 700;
}
div[data-testid="stForm"] .stButton > button {
    background: var(--accent-gradient);
    border: none;
    color: #fff;
    font-weight: 700;
}

/* ---- Inputs ---- */
.stTextInput input, .stTextInput > div > div {
    background: var(--surface-alt) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
    border-radius: 999px !important;
}

/* ---- Metric-style count chips ---- */
.count-chip {
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 700;
    background: var(--surface-alt);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.05rem 0.55rem;
    margin-left: 0.4rem;
}

hr { border-color: var(--border) !important; }
</style>
"""


def inject_theme(st_module):
    st_module.markdown(THEME_CSS, unsafe_allow_html=True)


def _img_to_base64(path: str) -> str | None:
    """Reads a local image file and returns a base64 data-URI, or None if
    the file doesn't exist -- so a missing logo never crashes the app."""
    import base64
    import mimetypes
    import os

    if not path or not os.path.exists(path):
        return None
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "image/png"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def render_brand_bar(st_module, title: str, company_logo_path: str = "", event_logo_path: str = ""):
    """Renders the header bar, with the company/event logos on the right
    if the corresponding image files exist -- silently skipped otherwise."""
    company_logo = _img_to_base64(company_logo_path)
    event_logo = _img_to_base64(event_logo_path)

    logos_html = ""
    if company_logo or event_logo:
        parts = []
        if company_logo:
            parts.append(f'<img src="{company_logo}" class="brand-logo" alt="Logo empresa" />')
        if event_logo:
            parts.append(f'<img src="{event_logo}" class="brand-logo" alt="Logo evento" />')
        logos_html = f'<div class="brand-logos">{"".join(parts)}</div>'

    st_module.markdown(
        f"""
        <div class="brand-bar">
            <h1><span class="brand-mark"></span>{title}</h1>
            {logos_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
