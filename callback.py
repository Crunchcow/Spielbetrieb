"""
OIDC Callback Handler für Spielbetrieb.

Läuft als eigener Flask-Prozess auf Port 8504.
Empfängt ?code= von ClubAuth, tauscht ihn gegen ein Access-Token,
setzt einen HTTP-Cookie und leitet zum Streamlit-Frontend weiter.

Kein WebSocket, kein Streamlit-Rerun-Problem.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, redirect, make_response
import requests as _requests
from fctm_core.storage import get_setting, session_save

app = Flask(__name__)

STREAMLIT_URL = "http://89.167.0.28:8503"
COOKIE_NAME = "fctm_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 Tage


@app.route("/callback")
def oidc_callback():
    code = request.args.get("code")
    if not code:
        return "Kein Code erhalten.", 400

    internal_url = (get_setting("oidc_internal_url") or get_setting("oidc_base_url") or "").rstrip("/")
    client_id = get_setting("oidc_client_id") or ""
    client_secret = get_setting("oidc_client_secret") or ""
    redirect_uri = get_setting("oidc_redirect_uri") or ""

    # Code gegen Token tauschen
    try:
        token_resp = _requests.post(
            f"{internal_url}/o/token/",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        if not token_resp.ok:
            return f"Token-Exchange fehlgeschlagen: {token_resp.text}", 400

        access_token = token_resp.json().get("access_token", "")

        ui_resp = _requests.get(
            f"{internal_url}/o/userinfo/",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if not ui_resp.ok:
            return f"Userinfo fehlgeschlagen: {ui_resp.text}", 400

        claims = ui_resp.json()
    except Exception as e:
        return f"Fehler beim OIDC-Exchange: {e}", 500

    # Rolle bestimmen
    roles = (claims.get("roles") or {})
    app_data = roles.get("spielbetrieb")
    if not app_data:
        return "Kein Zugang für diese App.", 403

    role = app_data.get("role")
    team = app_data.get("team", "")
    if not role:
        return "Keine Rolle zugewiesen.", 403

    email = (claims.get("email") or "").strip()
    name = claims.get("name", email)

    # Session in DB speichern (nutzt vorhandene storage-Funktion)
    session_token = session_save(role, team, name, email)

    # Cookie setzen und zu Streamlit weiterleiten
    resp = make_response(redirect(STREAMLIT_URL))
    resp.set_cookie(
        COOKIE_NAME,
        session_token,
        max_age=COOKIE_MAX_AGE,
        path="/",
        samesite="Lax",
        httponly=False,   # Streamlit-CookieController liest via JS
    )
    return resp


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8504)
