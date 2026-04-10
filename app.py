"""
WOHU – Westfalia Osterwick Hub
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st
from streamlit_cookies_controller import CookieController

from fctm_core.auth_service import (
    oidc_auth_url,
    oidc_exchange_code,
    oidc_is_configured,
    oidc_role_from_claims,
)
from fctm_core.domain_service import get_all_anfragen, get_saisonplanung
from fctm_core.pages.admin import (
    page_admin_dashboard,
    page_admin_spiel_anlegen,
    page_anfragen_verwalten,
    page_einstellungen,
    page_platzverwaltung,
    page_saisonplanung,
    page_statistiken,
)
from fctm_core.pages.auth import page_login
from fctm_core.pages.shared import page_trainingsplan_view
from fctm_core.pages.user import page_user_anfrage
from fctm_core.storage import (
    _COOKIE_MAX_AGE,
    _COOKIE_NAME,
    get_setting,
    init_db,
    session_delete,
    session_load,
    session_save,
)
from fctm_core.ui_helpers import CSS


def main() -> None:
    st.set_page_config(
        page_title="WOHU – Spielbetrieb",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    init_db()

    _cookies = CookieController()

    _params = st.query_params
    if "code" in _params and not st.session_state.get("role"):
        _code = _params["code"]
        # ERST verarbeiten, DANN löschen (clear() triggert sonst Rerun)

        # --- ClubAuth OIDC-Flow ---
        _redirect_uri = get_setting("oidc_redirect_uri") or "http://localhost:8501"
        _claims = oidc_exchange_code(_code, _redirect_uri)
        if _claims:
            _email = (_claims.get("email") or "").strip()
            _name = _claims.get("name", _email)
            _role, _team = oidc_role_from_claims(_claims)
            if _role:
                _token = session_save(_role, _team, _name, _email)
                _cookies.set(_COOKIE_NAME, _token, max_age=_COOKIE_MAX_AGE)
                st.session_state.role = _role
                st.session_state.team = _team
                st.session_state.ms_name = _name
                st.session_state.ms_email = _email
                st.session_state["_session_token"] = _token
                st.query_params.clear()  # Erst jetzt – nach dem Verarbeiten
            else:
                st.query_params.clear()
                st.error(f"⛔ Kein Zugang für **{_email}**. Bitte den Administrator kontaktieren.")
                st.stop()
        else:
            st.query_params.clear()
            st.error("❌ ClubAuth-Anmeldung fehlgeschlagen. Bitte erneut versuchen.")
            st.stop()

    # Cookie-Prüfung (CookieController braucht ggf. einen Rerun zum Laden)
    if "role" not in st.session_state:
        st.session_state.role = None
        _token = _cookies.get(_COOKIE_NAME)
        if _token:
            _sess = session_load(_token)
            if _sess:
                st.session_state.role = _sess["role"]
                st.session_state.team = _sess["team"]
                st.session_state.ms_name = _sess["ms_name"]
                st.session_state.ms_email = _sess["ms_email"]
                st.session_state["_session_token"] = _token

    _y = date.today().year
    _m = date.today().month
    saison_default = f"{_y - 1}/{_y}" if _m < 7 else f"{_y}/{_y + 1}"
    sp = get_saisonplanung(saison_default)
    if not sp.empty:
        sp_ren = sp.rename(
            columns={
                "team": "Team",
                "platz": "Platz",
                "tag": "Tag",
                "zeit": "Zeit",
                "kabine": "Kabine",
            }
        )

        def _bereich(p: str) -> str:
            if "Kunstrasen" in p:
                return "Kunstrasen"
            if "Wigger" in p:
                return "Wigger-Arena"
            return "Rasen"

        sp_ren["Bereich"] = sp_ren["Platz"].apply(_bereich)
        st.session_state.training_df = sp_ren[["Platz", "Bereich", "Tag", "Zeit", "Team"]]
    else:
        st.session_state.training_df = pd.DataFrame(columns=["Platz", "Bereich", "Tag", "Zeit", "Team"])

    if st.session_state.role is None:
        page_login()
        return

    with st.sidebar:
        role = st.session_state.role
        my_team_sb = st.session_state.get("team", "")
        badge_html = (
            '<span class="role-badge-admin">👑 Administrator</span>'
            if role == "admin"
            else (
                '<span class="role-badge-admin" style="background:#7c3aed;">📋 Koordinator</span>'
                if role == "koordinator"
                else '<span class="role-badge-user">👤 Benutzer</span>'
            )
        )
        team_line = f'<br><span style="color:#ffdada;font-size:12px;">⚽ {my_team_sb}</span>' if role == "benutzer" and my_team_sb else ""
        st.markdown(
            '<div style="text-align:center;padding:16px 0 10px 0;">'
            '<span style="font-size:40px;">⚽</span><br>'
            '<span style="color:#fff;font-size:18px;font-weight:bold;">WOHU</span><br>'
            '<span style="color:#ffdada;font-size:11px;">Spielbetrieb-Manager</span><br>'
            f'<div style="margin-top:8px;">{badge_html}</div>'
            f"{team_line}"
            + (
                f'<br><span style="color:#aad4f5;font-size:11px;">'
                f'🔷 {st.session_state.get("ms_name","")}'
                f"</span>"
                if st.session_state.get("ms_name")
                else ""
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        st.divider()

        if role == "admin":
            _n_offen = 0
            if not get_all_anfragen().empty:
                _anf = get_all_anfragen()
                _n_offen = len(_anf[_anf["status"].isin(["ausstehend", "dfbnet_ausstehend"])])
            _anfragen_label = f"📨 Anfragen verwalten {'🔴' if _n_offen > 0 else ''}"
            options = [
                "📅 Dashboard",
                _anfragen_label,
                "➕ Spiel anlegen",
                "📋 Trainingsplan",
                "📆 Saisonplanung",
                "🔒 Platzverwaltung",
                "📊 Statistiken",
                "⚙️ Einstellungen",
            ]
        elif role == "koordinator":
            _n_offen = 0
            if not get_all_anfragen().empty:
                _anf = get_all_anfragen()
                _n_offen = len(_anf[_anf["status"].isin(["ausstehend", "dfbnet_ausstehend"])])
            _anfragen_label = f"📨 Anfragen verwalten {'🔴' if _n_offen > 0 else ''}"
            options = [
                "📅 Dashboard",
                _anfragen_label,
                "➕ Spiel anlegen",
                "📋 Trainingsplan",
            ]
        else:
            options = ["📋 Trainingsplan", "📨 Meine Anfragen"]

        page = st.radio("Navigation", options, label_visibility="collapsed")

        df_n = len(st.session_state.training_df)
        if df_n > 0:
            st.caption(f"📋 {df_n} Trainingseinheiten geladen")

        st.divider()
        if st.button("🚪 Abmelden", type="primary", use_container_width=True):
            _tok = st.session_state.get("_session_token")
            session_delete(_tok)
            _cookies.remove(_COOKIE_NAME)
            st.session_state.role = None
            st.session_state.team = None
            st.session_state.pop("ms_name", None)
            st.session_state.pop("ms_email", None)
            st.session_state.pop("_session_token", None)
            st.rerun()
        st.caption("Version 2.1.0 · WOHU")

    routing = {
        "📅 Dashboard": page_admin_dashboard,
        "📨 Anfragen verwalten": page_anfragen_verwalten,
        "📨 Anfragen verwalten 🔴": page_anfragen_verwalten,
        "➕ Spiel anlegen": page_admin_spiel_anlegen,
        "📋 Trainingsplan": page_trainingsplan_view,
        "📆 Saisonplanung": page_saisonplanung,
        "🔒 Platzverwaltung": page_platzverwaltung,
        "📊 Statistiken": page_statistiken,
        "⚙️ Einstellungen": page_einstellungen,
        "📨 Meine Anfragen": page_user_anfrage,
    }
    routing.get(page, page_trainingsplan_view)()


if __name__ == "__main__":
    main()
