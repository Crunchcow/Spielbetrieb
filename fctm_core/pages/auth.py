import streamlit as st

from fctm_core.auth_service import ms_auth_url, oidc_auth_url, oidc_is_configured
from fctm_core.storage import db_connect, get_setting
from fctm_core.ui_helpers import CSS


def page_login() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="login-box">'
        '<div style="font-size:56px;margin-bottom:8px;">⚽</div>'
        "<h2>FCTM – Spielbetrieb</h2>"
        "<p>Bitte melden Sie sich an</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.write("")
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        if oidc_is_configured():
            # --- ClubAuth OIDC-Login (primär) ---
            redirect_uri = get_setting("oidc_redirect_uri") or "http://localhost:8501"
            login_url = oidc_auth_url(redirect_uri)
            st.markdown(
                '<p style="color:#555;font-size:13px;text-align:center;margin:0 0 16px 0;">'
                "Melden Sie sich mit Ihrem FCTM-Vereinsportal-Konto an."
                "</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="text-align:center;margin-bottom:20px;">'
                f'<a href="{login_url}" target="_self" style="'
                f'display:inline-block;padding:12px 28px;background:#c00000;color:#fff;'
                f'border-radius:6px;text-decoration:none;font-size:16px;font-weight:bold;">'
                f'⚽ Mit FCTM-Konto anmelden</a></div>',
                unsafe_allow_html=True,
            )
            with st.expander("🔧 Admin-PIN-Fallback"):
                pin_input = st.text_input("Admin-PIN", type="password", placeholder="PIN eingeben …", key="login_pin")
                if st.button("🔑 Als Admin einloggen", use_container_width=True):
                    if pin_input == get_setting("admin_pin"):
                        st.session_state.role = "admin"
                        st.session_state.ms_name = ""
                        st.rerun()
                    else:
                        st.error("Falscher PIN.")

        else:
            ms_client_id = get_setting("ms_client_id")
            redirect_uri = get_setting("ms_redirect_uri") or "http://localhost:8501"

            if ms_client_id:
                st.markdown(
                    '<p style="color:#555;font-size:13px;text-align:center;margin:0 0 16px 0;">'
                    "Melden Sie sich mit Ihrem FCTM-Microsoft-Konto an."
                    "</p>",
                    unsafe_allow_html=True,
                )
                login_url = ms_auth_url(redirect_uri)
                st.markdown(
                    f'<div style="text-align:center;margin-bottom:20px;">'
                    f'<a href="{login_url}" target="_self" style="'
                    f'display:inline-block;padding:12px 28px;background:#0078d4;color:#fff;'
                    f'border-radius:6px;text-decoration:none;font-size:16px;font-weight:bold;">'
                    f'🔷 Mit Microsoft anmelden</a></div>',
                    unsafe_allow_html=True,
                )
                with st.expander("🔧 Admin-PIN-Fallback"):
                    pin_input = st.text_input("Admin-PIN", type="password", placeholder="PIN eingeben …", key="login_pin")
                    if st.button("🔑 Als Admin einloggen", use_container_width=True):
                        if pin_input == get_setting("admin_pin"):
                            st.session_state.role = "admin"
                            st.session_state.ms_name = ""
                            st.rerun()
                        else:
                            st.error("Falscher PIN.")
            else:
                tab_u, tab_a = st.tabs(["👤 Als Benutzer", "🔑 Als Administrator"])

                with tab_u:
                    st.markdown(
                        '<p style="color:#555;font-size:13px;text-align:center;margin:12px 0;">'
                        "Benutzer können den Trainingsplan einsehen und Spielanfragen stellen."
                        "</p>",
                        unsafe_allow_html=True,
                    )
                    _conn_t = db_connect()
                    _teams_db = [
                        r[0]
                        for r in _conn_t.execute(
                            "SELECT DISTINCT team FROM saisonplanung "
                            "WHERE team IS NOT NULL AND team != '' ORDER BY team"
                        ).fetchall()
                    ]
                    _conn_t.close()
                    _team_opts = ["– Mannschaft wählen –"] + _teams_db + ["Sonstige / Individuell"]
                    u_team_sel = st.selectbox("Mannschaft", _team_opts, key="login_team_sel")
                    if u_team_sel == "Sonstige / Individuell":
                        u_team_val = st.text_input(
                            "Mannschaft (manuell eingeben)",
                            placeholder="z. B. 3. Mannschaft",
                            key="login_team_txt",
                        )
                    else:
                        u_team_val = "" if u_team_sel == "– Mannschaft wählen –" else u_team_sel
                    if st.button("▶️ Als Benutzer fortfahren", type="primary", use_container_width=True):
                        if not u_team_val.strip():
                            st.error("Bitte zuerst eine Mannschaft auswählen oder eingeben.")
                        else:
                            st.session_state.role = "benutzer"
                            st.session_state.team = u_team_val.strip()
                            st.rerun()

                with tab_a:
                    st.markdown(
                        '<p style="color:#555;font-size:13px;text-align:center;margin:12px 0;">'
                        "Vollzugriff auf alle Funktionen."
                        "</p>",
                        unsafe_allow_html=True,
                    )
                    pin_input = st.text_input("Admin-PIN", type="password", placeholder="PIN eingeben …", key="login_pin")
                    if st.button("🔑 Als Admin einloggen", use_container_width=True):
                        if pin_input == get_setting("admin_pin"):
                            st.session_state.role = "admin"
                            st.rerun()
                        else:
                            st.error("Falscher PIN.")
