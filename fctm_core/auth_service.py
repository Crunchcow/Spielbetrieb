import urllib.parse

import msal
import requests as _requests

from .storage import db_connect, get_setting

# ---------------------------------------------------------------------------
# ClubAuth OIDC (primär, neu)
# ---------------------------------------------------------------------------

def oidc_is_configured() -> bool:
    """True wenn ClubAuth als OIDC-Provider konfiguriert ist."""
    return bool(get_setting("oidc_client_id") and get_setting("oidc_base_url"))


def oidc_auth_url(redirect_uri: str) -> str:
    """Erzeugt die Weiterleitungs-URL zu ClubAuth."""
    base_url = (get_setting("oidc_base_url") or "").rstrip("/")
    client_id = get_setting("oidc_client_id") or ""
    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email roles",
    })
    return f"{base_url}/o/authorize/?{params}"


def oidc_exchange_code(code: str, redirect_uri: str) -> dict | None:
    """Tauscht Authorization-Code gegen UserInfo-Claims von ClubAuth."""
    base_url = (get_setting("oidc_base_url") or "").rstrip("/")
    internal_url = (get_setting("oidc_internal_url") or base_url).rstrip("/")
    client_id = get_setting("oidc_client_id") or ""
    client_secret = get_setting("oidc_client_secret") or ""
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
            import sys
            print(f"[OIDC] Token-Exchange fehlgeschlagen: {token_resp.status_code} {token_resp.text}", file=sys.stderr)
            return None
        access_token = token_resp.json().get("access_token", "")

        ui_resp = _requests.get(
            f"{internal_url}/o/userinfo/",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if not ui_resp.ok:
            import sys
            print(f"[OIDC] Userinfo fehlgeschlagen: {ui_resp.status_code} {ui_resp.text}", file=sys.stderr)
            return None
        return ui_resp.json()
    except Exception as e:
        import sys
        print(f"[OIDC] Exception: {e}", file=sys.stderr)
        return None


def oidc_role_from_claims(claims: dict) -> tuple[str | None, str]:
    """Liest Rolle und Team aus ClubAuth-UserInfo-Claims.

    ClubAuth liefert:
        claims["roles"]["spielbetrieb"] = {"role": "benutzer", "team": "1. Herren"}
    Oder (Legacy-Format falls kein Team hinterlegt):
        claims["roles"]["spielbetrieb"] = {"role": "koordinator"}
    """
    roles: dict = claims.get("roles") or {}
    app_data = roles.get("spielbetrieb")

    if not app_data:
        return None, ""

    # Neues Format: dict mit role + optionalem team
    if isinstance(app_data, dict):
        role = app_data.get("role")
        team = app_data.get("team", "")
    else:
        # Altes Format (plain string) — Abwärtskompatibilität
        role = app_data
        team = ""

    if role not in ("admin", "koordinator", "benutzer"):
        return None, ""

    # Kein Team im Token? Fallback: Saisonplan-Tabelle per E-Mail durchsuchen
    if role == "benutzer" and not team:
        email = (claims.get("email") or "").lower().strip()
        conn = db_connect()
        row = conn.execute(
            "SELECT team FROM saisonplanung "
            "WHERE LOWER(trainer_email)=? AND team IS NOT NULL AND team != '' LIMIT 1",
            (email,),
        ).fetchone()
        conn.close()
        team = row[0] if row else ""

    return role, team


# ---------------------------------------------------------------------------
# Microsoft MSAL (Legacy-Fallback, bleibt bis zur vollständigen Migration)
# ---------------------------------------------------------------------------

def _ms_app() -> msal.ClientApplication:
    client_id = get_setting("ms_client_id")
    tenant_id = get_setting("ms_tenant_id") or "common"
    client_secret = get_setting("ms_client_secret")
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    if client_secret:
        return msal.ConfidentialClientApplication(
            client_id, authority=authority, client_credential=client_secret
        )
    return msal.PublicClientApplication(client_id, authority=authority)


def ms_auth_url(redirect_uri: str) -> str:
    app = _ms_app()
    return app.get_authorization_request_url(
        scopes=["User.Read"],
        redirect_uri=redirect_uri,
    )


def ms_exchange_code(code: str, redirect_uri: str) -> dict | None:
    try:
        app = _ms_app()
        result = app.acquire_token_by_authorization_code(
            code,
            scopes=["User.Read"],
            redirect_uri=redirect_uri,
        )
        return result if "id_token_claims" in result else None
    except Exception:
        return None


def ms_role_from_email(email: str) -> tuple[str | None, str]:
    email_lower = email.lower().strip()
    admin_emails_raw = get_setting("admin_emails") or ""
    admin_emails = [
        e.strip().lower()
        for e in admin_emails_raw.replace(",", "\n").splitlines()
        if e.strip()
    ]
    if email_lower in admin_emails:
        return "admin", ""

    koordinator_emails_raw = get_setting("koordinator_emails") or ""
    koordinator_emails = [
        e.strip().lower()
        for e in koordinator_emails_raw.replace(",", "\n").splitlines()
        if e.strip()
    ]
    if email_lower in koordinator_emails:
        return "koordinator", ""

    conn = db_connect()
    row = conn.execute(
        "SELECT team FROM saisonplanung "
        "WHERE LOWER(trainer_email)=? AND team IS NOT NULL AND team != '' LIMIT 1",
        (email_lower,),
    ).fetchone()
    conn.close()
    if row:
        return "benutzer", row[0]
    return None, ""
