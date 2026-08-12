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
    config.STATUS_PENDING: "New",
    config.STATUS_APPROVED: "Approved",
    config.STATUS_REJECTED: "Rejected",
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
        "first_name": "First name",
        "last_name": "Last name",
        "email": "Email",
        "company": "Company",
        "job_title": "Position",
        "telephone": "Phone",
    }.get(field_name, field_name.replace("_", " ").title())


THEME_CSS = """
<style>
:root {
    --bg: #0B0B14;
    --surface: #14141F;
    --surface-alt: #1B1B29;
    --border: #2A2A3C;
    --text: #F4F4FA;
    --text-muted: #9A9AB3;
    --accent-1: #7C5CFF;
    --accent-2: #3EC6FF;
    --accent-gradient: linear-gradient(90deg, var(--accent-1), var(--accent-2));
    --success: #22C55E;
    --success-bg: rgba(34, 197, 94, 0.12);
    --danger: #F5484B;
    --danger-bg: rgba(245, 72, 75, 0.12);
    --warning: #F5A623;
    --warning-bg: rgba(245, 166, 35, 0.12);
    --radius: 16px;
    --radius-sm: 10px;
    --shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.stApp {
    background: radial-gradient(circle at 15% 0%, rgba(124, 92, 255, 0.12), transparent 40%),
                radial-gradient(circle at 85% 10%, rgba(62, 198, 255, 0.10), transparent 45%),
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
    padding: 1.1rem 1.5rem;
    margin-bottom: 1.5rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
}
.brand-bar h1 {
    font-size: 1.15rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: 0.01em;
}
.brand-bar .brand-mark {
    display: inline-block;
    width: 10px; height: 10px;
    border-radius: 3px;
    background: var(--accent-gradient);
    margin-right: 0.6rem;
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
    border-bottom: 2px solid transparent;
    border-image: var(--accent-gradient);
    border-image-slice: 1;
}

/* ---- Buttons ---- */
.stButton > button {
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
    font-weight: 600;
}
.stButton > button[kind="primary"] {
    background: var(--accent-gradient);
    border: none;
    color: #fff;
}
div[data-testid="stForm"] .stButton > button {
    background: var(--accent-gradient);
    border: none;
    color: #fff;
}

/* ---- Inputs ---- */
.stTextInput input, .stTextInput > div > div {
    background: var(--surface-alt) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
    border-radius: var(--radius-sm) !important;
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
