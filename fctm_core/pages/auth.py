import streamlit as st

from fctm_core.auth_service import oidc_auth_url, oidc_is_configured
from fctm_core.storage import (
    _COOKIE_MAX_AGE,
    _COOKIE_NAME,
    get_setting,
    session_save,
)
from fctm_core.ui_helpers import CSS


def page_login(cookies=None) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="login-box">'
        '<div style="font-size:56px;margin-bottom:8px;">⚽</div>'
        "<h2>WOHU – Spielbetrieb</h2>"
        "<p>Bitte melden Sie sich an</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.write("")
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        if oidc_is_configured():
            redirect_uri = get_setting("oidc_redirect_uri") or "http://localhost:8501"
            login_url = oidc_auth_url(redirect_uri)
            st.markdown(
                '<p style="color:#555;font-size:13px;text-align:center;margin:0 0 16px 0;">'
                "Melden Sie sich mit Ihrem Vereinsportal-Konto an."
                "</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="text-align:center;margin-bottom:20px;">'
                f'<a href="{login_url}" target="_self" style="'
                f'display:inline-block;padding:12px 28px;background:#c00000;color:#fff;'
                f'border-radius:6px;text-decoration:none;font-size:16px;font-weight:bold;">'
                f'⚽ Mit Vereinsportal-Konto anmelden</a></div>',
                unsafe_allow_html=True,
            )
        else:
            st.warning(
                "⚙️ ClubAuth ist nicht konfiguriert. "
                "Administratoren können sich mit dem Admin-PIN anmelden."
            )
            st.write("")
            with st.form("pin_login_form"):
                pin_input = st.text_input(
                    "🔑 Admin-PIN",
                    type="password",
                    placeholder="PIN eingeben …",
                )
                submitted = st.form_submit_button("Anmelden", use_container_width=True)

            if submitted:
                stored_pin = get_setting("admin_pin") or "1234"
                if pin_input == stored_pin:
                    token = session_save("admin", "", "Admin", "")
                    st.session_state.role = "admin"
                    st.session_state.team = ""
                    st.session_state.ms_name = "Admin"
                    st.session_state.ms_email = ""
                    st.session_state["_session_token"] = token
                    if cookies is not None:
                        cookies.set(
                            _COOKIE_NAME,
                            token,
                            max_age=_COOKIE_MAX_AGE,
                        )
                    st.rerun()
                else:
                    st.error("❌ Falscher PIN.")
