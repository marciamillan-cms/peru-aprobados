"""
auth.py
-------
A lightweight authentication layer suitable for a small internal tool.

Usernames and password *hashes* live in Streamlit Secrets under a
[credentials] table (see .streamlit/secrets.toml.example) -- never in code,
never in plain text in the repo. Passwords are hashed with SHA-256 plus a
per-app salt before comparison; nothing about a user's real password is
ever stored or logged.

This is intentionally simple (no roles, no password reset flow, no
sessions across browser tabs) because the brief calls for "a basic first
version." If the team outgrows it, swap this module for
`streamlit-authenticator`, SSO, or Streamlit's built-in `st.login`
(if available on your Streamlit version) without touching app.py's public
surface: `is_authenticated()`, `login_form()`, `logout()`.
"""
import hashlib
import hmac

import streamlit as st

_SESSION_KEY = "auth_user"


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _get_credentials() -> dict:
    """Reads {username: password_hash} from Streamlit Secrets."""
    try:
        return dict(st.secrets.get("credentials", {}))
    except Exception:
        return {}


def _get_salt() -> str:
    try:
        return st.secrets.get("auth_salt", "eventtia-approval-app")
    except Exception:
        return "eventtia-approval-app"


def is_authenticated() -> bool:
    return bool(st.session_state.get(_SESSION_KEY))


def current_user() -> str:
    return st.session_state.get(_SESSION_KEY, "")


def logout():
    st.session_state.pop(_SESSION_KEY, None)


def login_form() -> bool:
    """
    Renders a login form. Returns True once the user is authenticated
    (either just now, or already, in an earlier run). Call this at the top
    of app.py and `st.stop()` if it returns False.
    """
    if is_authenticated():
        return True

    credentials = _get_credentials()
    if not credentials:
        st.error(
            "No users are configured yet. Add a [credentials] section to "
            ".streamlit/secrets.toml (see secrets.toml.example) with at "
            "least one username/password-hash pair."
        )
        return False

    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown("### Sign in")
    st.caption("Internal tool -- authorized team members only.")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        salt = _get_salt()
        expected_hash = credentials.get(username)
        if expected_hash and hmac.compare_digest(_hash_password(password, salt), str(expected_hash)):
            st.session_state[_SESSION_KEY] = username
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    return is_authenticated()


def hash_password_for_secrets(password: str, salt: str = "eventtia-approval-app") -> str:
    """
    Helper you can run locally (`python -c "from auth import hash_password_for_secrets as h; print(h('mypassword'))"`)
    to generate the value that goes into secrets.toml. Never paste a plain
    password into secrets.toml -- paste the output of this function.
    """
    return _hash_password(password, salt)
