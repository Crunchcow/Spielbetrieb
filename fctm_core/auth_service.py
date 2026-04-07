import msal

from .storage import db_connect, get_setting


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
