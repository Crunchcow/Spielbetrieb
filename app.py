"""
FCTM – Football Club Training & Match Management System
========================================================
Vereinsfarben: Rot (#C8102E) & Weiß
Rollen: Admin (vollständiger Zugriff) · Benutzer (Anfragen & Trainingsplan)
"""

import io
import smtplib
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import msal
import pandas as pd
import streamlit as st
from streamlit_cookies_controller import CookieController

from fctm_core.constants import (
    DAYS,
    LOCKER_ROOMS,
    PITCHES,
    PITCHES_SPIEL,
    PITCH_HALVES,
    TIME_SLOTS_TRAINING,
    WEEKDAYS_DISPLAY,
)
from fctm_core.storage import (
    _COOKIE_MAX_AGE,
    _COOKIE_NAME,
    db_connect,
    get_setting,
    init_db,
    session_delete,
    session_load,
    session_save,
    set_setting,
)

# ---------------------------------------------------------------------------
# CSS – Vereinsfarben Rot & Weiß (Light-Mode, analog Kursanmeldung)
# ---------------------------------------------------------------------------
CSS = """
<style>
/* ─── Basis ────────────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stMain"], .main {
    background-color: #ffffff !important;
    color: #1a1a1a !important;
}

/* ─── Sidebar (rote Navbar analog Kursanmeldung) ──────────────────────── */
[data-testid="stSidebar"] {
    background: #c00000 !important;
    border-right: none !important;
}
[data-testid="stSidebar"] * {
    color: #ffffff !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div,
[data-testid="stSidebar"] input {
    background: #a00000 !important;
    color: #ffffff !important;
    border-color: #e03030 !important;
}
/* Sidebar-Radio aktiv + hover */
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { opacity:0.85; }
[data-testid="stSidebar"] .stMarkdown a { color: #ffd6d6 !important; }
[data-testid="stSidebar"] hr { border-color: #e03030 !important; }
/* Sidebar-Buttons: weißer Hintergrund, roter Text */
[data-testid="stSidebar"] .stButton > button {
    background: #ffffff !important;
    color: #c00000 !important;
    border: 2px solid #ffffff !important;
    font-weight: 700 !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #fdf0f0 !important;
    color: #a00000 !important;
    border-color: #fdf0f0 !important;
}

/* ─── Header-Banner ───────────────────────────────────────────────────── */
.main-header {
    background: linear-gradient(135deg, #a00000 0%, #c00000 60%, #d91025 100%);
    padding: 22px 28px;
    border-radius: 12px;
    margin-bottom: 22px;
    box-shadow: 0 3px 14px rgba(192,0,0,0.25);
}
.main-header h1 { margin:0; font-size:26px; color:#ffffff;
                  text-shadow:0 1px 3px rgba(0,0,0,.3); }
.main-header p  { margin:4px 0 0 0; opacity:.85; color:#ffdada; font-size:14px; }

/* ─── Login ───────────────────────────────────────────────────────────── */
.login-box {
    background: #ffffff;
    border: 2px solid #c00000;
    border-radius: 16px;
    padding: 40px 36px;
    max-width: 440px;
    margin: 60px auto 0 auto;
    box-shadow: 0 6px 24px rgba(192,0,0,.15);
    text-align: center;
}
.login-box h2 { color:#c00000; font-size:22px; margin-bottom:6px; }
.login-box p  { color:#555; font-size:13px; margin-bottom:24px; }

/* ─── Rollen-Badge ────────────────────────────────────────────────────── */
.role-badge-admin {
    display:inline-block; padding:3px 14px; border-radius:20px;
    background:#c00000; color:#fff; font-size:12px; font-weight:bold;
}
.role-badge-user {
    display:inline-block; padding:3px 14px; border-radius:20px;
    background:#fff; color:#c00000; border:1px solid #c00000;
    font-size:12px; font-weight:bold;
}

/* ─── Slot-Karten Dashboard ───────────────────────────────────────────── */
.slot-card {
    border-radius:7px; padding:7px 10px; margin:3px 0;
    font-size:12px; font-weight:500; line-height:1.4;
}
.slot-training { background:#fdf0f0; border-left:4px solid #c00000; color:#3a0000; }
.slot-match    { background:#fffbea; border-left:4px solid #d08000; color:#3a2a00; }
.slot-locked   { background:#ffe0e0; border-left:4px solid #c00000;
                 text-align:center; font-weight:bold; color:#700000; }
.slot-free     { background:#f5f5f5; border-left:4px solid #cccccc;
                 color:#aaaaaa; text-align:center; }

/* ─── Tages-Header ────────────────────────────────────────────────────── */
.day-header {
    padding:6px 4px; border-radius:7px; text-align:center;
    margin-bottom:6px; font-size:11px; font-weight:bold; color:white;
}

/* ─── Status-Karten ───────────────────────────────────────────────────── */
.status-card-ok {
    background:#fff; border:2px solid #c00000; border-radius:10px;
    padding:16px; text-align:center; min-height:110px; color:#1a1a1a;
}
.status-card-locked {
    background:#ffe0e0; border:2px solid #c00000; border-radius:10px;
    padding:16px; text-align:center; min-height:110px; color:#700000;
}

/* ─── Anfrage-Karten ──────────────────────────────────────────────────── */
.anfrage-card {
    background:#fff; border:1px solid #e0e0e0;
    border-radius:10px; padding:13px 16px; margin-bottom:9px; color:#1a1a1a;
}
.anfrage-offen    { border-left:4px solid #d08000; }
.anfrage-ok       { border-left:4px solid #22a050; }
.anfrage-abgelehnt{ border-left:4px solid #c00000; }

/* ─── Match-Karte ─────────────────────────────────────────────────────── */
.match-card {
    background:#fff; border:1px solid #e0e0e0;
    border-radius:10px; padding:13px 16px; margin-bottom:9px; color:#1a1a1a;
}

/* ─── Sperr-Karte ─────────────────────────────────────────────────────── */
.lock-card {
    background:#ffe8e8; border:1px solid #c00000;
    border-radius:10px; padding:13px 16px; margin-bottom:8px; color:#700000;
}

/* ─── Kabinen-Karten ──────────────────────────────────────────────────── */
.locker-busy {
    background:#fff; border:2px solid #c00000; border-radius:10px;
    padding:15px; text-align:center; min-height:130px; color:#1a1a1a;
}
.locker-free {
    background:#f8f8f8; border:2px dashed #cccccc; border-radius:10px;
    padding:15px; text-align:center; min-height:130px; color:#888;
}
.locker-conflict {
    background:#ffe0e0; border:2px solid #c00000; border-radius:10px;
    padding:15px; text-align:center; min-height:130px; color:#700000;
    animation: pulse 1.5s infinite;
}
@keyframes pulse {
    0%   { box-shadow:0 0 0 0   rgba(192,0,0,.35); }
    70%  { box-shadow:0 0 0 10px rgba(192,0,0,0);  }
    100% { box-shadow:0 0 0 0   rgba(192,0,0,0);   }
}

/* ─── Stat-Karte ──────────────────────────────────────────────────────── */
.stat-card {
    background:#fff; border:1px solid #e0e0e0;
    border-radius:12px; padding:20px; text-align:center; color:#1a1a1a;
}

/* ─── Duplikat-Warnung ────────────────────────────────────────────────── */
.duplicate-warning {
    background:#ffe8e8; border:2px solid #c00000;
    border-radius:10px; padding:14px 18px; margin:8px 0; color:#700000;
}

/* ─── Streamlit overrides ─────────────────────────────────────────────── */
/* Primär-Buttons: rot */
.stButton > button {
    background:#c00000 !important; color:#fff !important;
    border:none !important; border-radius:8px !important;
    font-weight:600 !important;
}
.stButton > button:hover { background:#a00000 !important; }

/* Sekundär-Buttons: weiß mit rotem Rand */
.stButton > button[kind="secondary"] {
    background:#ffffff !important; color:#c00000 !important;
    border:1.5px solid #c00000 !important;
}
.stButton > button[kind="secondary"]:hover {
    background:#fdf0f0 !important;
}

/* Metriken */
div[data-testid="stMetric"] {
    background:#fff; border:1px solid #e0e0e0;
    border-radius:10px; padding:12px;
}

/* Inputs */
.stTextInput input, .stTextArea textarea,
[data-baseweb="select"] {
    background:#ffffff !important;
    color:#1a1a1a !important;
    border-color:#cccccc !important;
}

/* Trennlinien */
hr { border-color:#e0e0e0 !important; }

.stDataFrame { background:#fff; }
.stAlert { border-radius:10px !important; }

/* Tabs */
[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
    border-bottom: 3px solid #c00000 !important;
    color: #c00000 !important;
}

/* Expander */
[data-testid="stExpander"] {
    border: 1px solid #e0e0e0 !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary:hover {
    color: #c00000 !important;
}

/* ─── Form-Submit-Buttons (st.form_submit_button) ─────────────────────── */
.stFormSubmitButton > button {
    background: #c00000 !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.stFormSubmitButton > button:hover { background: #a00000 !important; }

/* ─── Alle Input-Felder (Text, Number, Date, Time) ────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stTimeInput"] input,
[data-testid="stTextArea"] textarea {
    background: #ffffff !important;
    color: #1a1a1a !important;
    border: 1px solid #cccccc !important;
    border-radius: 6px !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stDateInput"] input:focus,
[data-testid="stTimeInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: #c00000 !important;
    box-shadow: 0 0 0 2px rgba(192,0,0,0.15) !important;
}

/* ─── Selectbox & Multiselect ─────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
    background: #ffffff !important;
    border: 1px solid #cccccc !important;
    border-radius: 6px !important;
    color: #1a1a1a !important;
}
[data-testid="stSelectbox"] > div > div:focus-within,
[data-testid="stMultiSelect"] > div > div:focus-within {
    border-color: #c00000 !important;
    box-shadow: 0 0 0 2px rgba(192,0,0,0.15) !important;
}
/* Dropdown-Liste */
[data-baseweb="popover"] ul,
[data-baseweb="menu"] {
    background: #ffffff !important;
    border: 1px solid #e0e0e0 !important;
}
[data-baseweb="menu"] li:hover {
    background: #fdf0f0 !important;
    color: #c00000 !important;
}
/* Ausgewählter Tag in Multiselect */
[data-baseweb="tag"] {
    background: #c00000 !important;
    color: #fff !important;
}

/* ─── Checkbox & Radio ────────────────────────────────────────────────── */
[data-testid="stCheckbox"] input:checked + div,
[data-testid="stRadio"] input:checked + div {
    background: #c00000 !important;
    border-color: #c00000 !important;
}
[data-testid="stCheckbox"] label,
[data-testid="stRadio"] label {
    color: #1a1a1a !important;
}

/* ─── Toggle (st.toggle) ──────────────────────────────────────────────── */
[data-testid="stToggle"] [role="switch"][aria-checked="true"] {
    background: #c00000 !important;
}

/* ─── Fortschrittsbalken / Spinner-Farbe ──────────────────────────────── */
[data-testid="stProgressBar"] > div {
    background: #c00000 !important;
}

/* ─── Obere Streamlit-Toolbar ausblenden / dezent ─────────────────────── */
[data-testid="stToolbar"],
[data-testid="stDecoration"] {
    background: transparent !important;
}
[data-testid="stToolbar"] * { color: #888 !important; }

/* ─── Header-Linie oben (farbige Linie unter Toolbar) ────────────────── */
[data-testid="stHeader"] {
    background: #ffffff !important;
    border-bottom: 2px solid #c00000 !important;
}

/* ─── Sidebar-Collapse-Button ─────────────────────────────────────────── */
[data-testid="collapsedControl"],
button[data-testid="baseButton-headerNoPadding"] {
    color: #c00000 !important;
}

/* ─── Warnungen / Info-Boxen ──────────────────────────────────────────── */
[data-testid="stAlert"][kind="info"],
div.stAlert > div[data-baseweb="notification"][kind="info"] {
    background: #fdf0f0 !important;
    border-left: 4px solid #c00000 !important;
    color: #700000 !important;
}

/* ─── Divider ─────────────────────────────────────────────────────────── */
[data-testid="stMarkdownContainer"] hr {
    border-color: #e0e0e0 !important;
}

/* ─── Tabellen / DataFrames ───────────────────────────────────────────── */
[data-testid="stDataFrame"] th {
    background: #c00000 !important;
    color: #fff !important;
}
[data-testid="stDataFrame"] tr:hover td {
    background: #fdf0f0 !important;
}

/* ─── Sidebar: aktiver Menüpunkt ──────────────────────────────────────── */
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-focused="true"],
[data-testid="stSidebar"] [data-testid="stRadio"] input:checked ~ div {
    color: #ffffff !important;
    font-weight: 700 !important;
}

/* ─── Number-Input Stepper-Buttons ───────────────────────────────────── */
[data-testid="stNumberInput"] button {
    background: #f5f5f5 !important;
    color: #c00000 !important;
    border-color: #cccccc !important;
}
[data-testid="stNumberInput"] button:hover {
    background: #fdf0f0 !important;
}
</style>
"""

# ── Spiele ────────────────────────────────────────────────────────────────────

def save_match(
    datum,
    uhrzeit,
    platz,
    heimteam,
    gastteam,
    kabine,
    notizen,
    betroffene,
    quelle: str = "manuell",
    ursprung_anfrage_id: int | None = None,
) -> int:
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spiele (datum,uhrzeit,platz,heimteam,gastteam,kabine,notizen,quelle,ursprung_anfrage_id) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            datum.isoformat(), uhrzeit, platz, heimteam, gastteam,
            kabine, notizen, quelle, ursprung_anfrage_id,
        ),
    )
    sid = c.lastrowid
    for team in betroffene:
        c.execute(
            "INSERT INTO training_ausfaelle (team,datum,uhrzeit,platz,spiel_id) "
            "VALUES (?,?,?,?,?)",
            (team, datum.isoformat(), uhrzeit, platz, sid),
        )
    conn.commit()
    conn.close()
    return sid


def get_all_matches() -> pd.DataFrame:
    conn = db_connect()
    df = pd.read_sql("SELECT * FROM spiele ORDER BY datum,uhrzeit", conn)
    conn.close()
    return df


def get_matches_for_date(d: date) -> pd.DataFrame:
    conn = db_connect()
    df = pd.read_sql(
        "SELECT * FROM spiele WHERE datum=? ORDER BY uhrzeit",
        conn, params=(d.isoformat(),),
    )
    conn.close()
    return df


def delete_match(mid: int) -> None:
    conn = db_connect()
    conn.execute("DELETE FROM training_ausfaelle WHERE spiel_id=?", (mid,))
    conn.execute("DELETE FROM spiele WHERE id=?", (mid,))
    conn.commit()
    conn.close()


# ── E-Mail ────────────────────────────────────────────────────────────────────

def _email_cfg() -> dict:
    keys = [
        "email_aktiv", "email_smtp_host", "email_smtp_port",
        "email_smtp_user", "email_smtp_pass",
        "email_absender",  "email_empfaenger",
    ]
    conn = db_connect()
    rows = conn.execute(
        f"SELECT schluessel, wert FROM einstellungen WHERE schluessel IN "
        f"({','.join('?' for _ in keys)})",
        keys,
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def _graph_send(betreff: str, html_body: str, absender: str, empfaenger: list[str]) -> tuple[bool, str]:
    """
    Sendet eine E-Mail über Microsoft Graph API (App-only, Mail.Send).
    Erfordert ms_client_id, ms_tenant_id, ms_client_secret in den Einstellungen.
    """
    import requests as _req
    client_id     = get_setting("ms_client_id")
    tenant_id     = get_setting("ms_tenant_id") or "common"
    client_secret = get_setting("ms_client_secret")
    if not client_id or not client_secret:
        return False, "Microsoft Graph nicht konfiguriert."

    # Token holen
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_resp = _req.post(token_url, data={
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         "https://graph.microsoft.com/.default",
    }, timeout=10)
    if token_resp.status_code != 200:
        return False, f"Token-Fehler: {token_resp.text}"
    access_token = token_resp.json().get("access_token", "")

    # Mail senden
    mail_payload = {
        "message": {
            "subject": betreff,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": e}} for e in empfaenger],
        },
        "saveToSentItems": False,
    }
    send_url = f"https://graph.microsoft.com/v1.0/users/{absender}/sendMail"
    send_resp = _req.post(
        send_url,
        json=mail_payload,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=15,
    )
    if send_resp.status_code == 202:
        return True, ""
    return False, f"Graph-Fehler {send_resp.status_code}: {send_resp.text}"


def send_email(betreff: str, html_body: str, to: str | None = None) -> tuple[bool, str]:
    """
    Sendet eine HTML-E-Mail.
    Nutzt Microsoft Graph API wenn konfiguriert, sonst SMTP als Fallback.
    `to`: optionale Empfänger-Adresse (überschreibt Funktionspostfach).
    """
    cfg = _email_cfg()
    if cfg.get("email_aktiv", "0") != "1":
        return False, "E-Mail-Versand nicht aktiviert."
    absender   = cfg.get("email_absender", "") or cfg.get("email_smtp_user", "")
    if to:
        empfaenger = [e.strip() for e in to.split(",") if e.strip()]
    else:
        empfaenger = [e.strip() for e in cfg.get("email_empfaenger", "").split(",") if e.strip()]
    if not empfaenger:
        return False, "Kein Empfänger konfiguriert."

    # Graph API bevorzugen wenn MS-Einstellungen vorhanden
    if get_setting("ms_client_id") and get_setting("ms_client_secret"):
        return _graph_send(betreff, html_body, absender, empfaenger)

    # Fallback: SMTP
    host     = cfg.get("email_smtp_host", "")
    port     = int(cfg.get("email_smtp_port", 587) or 587)
    user     = cfg.get("email_smtp_user", "")
    password = cfg.get("email_smtp_pass", "")
    if not host:
        return False, "SMTP-Host fehlt."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = betreff
    msg["From"]    = absender
    msg["To"]      = ", ".join(empfaenger)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(absender, empfaenger, msg.as_bytes())
        return True, ""
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Microsoft-Login (MSAL)
# ---------------------------------------------------------------------------

def _ms_app() -> msal.ClientApplication:
    client_id     = get_setting("ms_client_id")
    tenant_id     = get_setting("ms_tenant_id") or "common"
    client_secret = get_setting("ms_client_secret")
    authority     = f"https://login.microsoftonline.com/{tenant_id}"
    if client_secret:
        return msal.ConfidentialClientApplication(
            client_id, authority=authority, client_credential=client_secret
        )
    return msal.PublicClientApplication(client_id, authority=authority)


def ms_auth_url(redirect_uri: str) -> str:
    """Gibt die Microsoft-Login-URL zurück."""
    app = _ms_app()
    return app.get_authorization_request_url(
        scopes=["User.Read"],
        redirect_uri=redirect_uri,
    )


def ms_exchange_code(code: str, redirect_uri: str) -> dict | None:
    """Tauscht den OAuth-Code gegen ein Token ein."""
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
    """
    Gibt (role, team) zurück.
    role = 'admin'    → E-Mail in admin_emails
    role = 'benutzer' → E-Mail in saisonplanung.trainer_email
    role = None       → kein Zugang
    """
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


def _mail_trainer_html(
    datum: date,
    uhrzeit: str,
    platz: str,
    heimteam: str,
    gastteam: str,
    kabine: str,
    team_trainer: str,
) -> str:
    """
    E-Mail direkt an den Trainer des betroffenen Teams:
    Spiel bestätigt, DFBnet eingetragen, auf fussball.de sichtbar.
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;
                  border-radius:12px;overflow:hidden;
                  box-shadow:0 2px 12px rgba(0,0,0,.15);">
        <div style="background:#C8102E;padding:24px 28px;">
          <h1 style="margin:0;color:#fff;font-size:22px;">⚽ Spielbestätigung</h1>
          <p style="margin:4px 0 0 0;color:#ffd6dc;font-size:14px;">
            Dein Training entfällt – hier sind alle Details
          </p>
        </div>
        <div style="padding:24px 28px;">
          <p style="color:#333;">Hallo{' ' + team_trainer if team_trainer else ''},</p>
          <p style="color:#333;">
            für den folgenden Termin wurde ein Pflichtspiel angesetzt.
            Das Spiel ist bereits <b>im DFBnet eingetragen</b> und kann auch
            über <a href="https://www.fussball.de" style="color:#C8102E;">fussball.de</a>
            eingesehen werden.
          </p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0;">
            <tr style="background:#fafafa;">
              <td style="padding:8px;color:#888;width:140px;">Datum</td>
              <td style="padding:8px;font-weight:bold;">{datum.strftime('%A, %d.%m.%Y')}</td></tr>
            <tr>
              <td style="padding:8px;color:#888;">Anstoßzeit</td>
              <td style="padding:8px;font-weight:bold;">{uhrzeit} Uhr</td></tr>
            <tr style="background:#fafafa;">
              <td style="padding:8px;color:#888;">Platz</td>
              <td style="padding:8px;font-weight:bold;">{platz}</td></tr>
            <tr>
              <td style="padding:8px;color:#888;">Heimteam</td>
              <td style="padding:8px;font-weight:bold;">{heimteam}</td></tr>
            <tr style="background:#fafafa;">
              <td style="padding:8px;color:#888;">Gastteam</td>
              <td style="padding:8px;font-weight:bold;">{gastteam}</td></tr>
            <tr>
              <td style="padding:8px;color:#888;">Kabine</td>
              <td style="padding:8px;">{kabine or '–'}</td></tr>
          </table>
          <div style="background:#e8f0fe;border-left:4px solid #C8102E;
                      padding:14px 16px;border-radius:6px;margin:16px 0;">
            <b style="color:#C8102E;">✅ Alles erledigt – kein weiterer Handlungsbedarf</b>
            <ul style="margin:10px 0 0 0;color:#333;font-size:13px;">
              <li>Spielansetzung im <b>DFBnet</b> eingetragen ✓</li>
              <li>Spielplan auf <a href="https://www.fussball.de" style="color:#C8102E;">fussball.de</a> einsehbar ✓</li>
              <li>Trainer wurden automatisch benachrichtigt ✓</li>
            </ul>
          </div>
          <p style="color:#666;font-size:13px;">
            Bei Fragen bitte direkt beim Spielbetrieb melden.
          </p>
        </div>
        <div style="background:#f0f0f0;padding:14px 28px;
                    font-size:12px;color:#888;text-align:center;">
          Automatische Benachrichtigung · FCTM Spielbetrieb-Manager
        </div>
      </div>
    </body>
    </html>
    """


def _mail_trainer_aenderung_html(
    datum_alt: date,
    uhrzeit_alt: str,
    platz_alt: str,
    kabine_alt: str,
    datum_neu: date,
    uhrzeit_neu: str,
    platz_neu: str,
    kabine_neu: str,
    heimteam: str,
    gastteam: str,
) -> str:
    """E-Mail an Trainer: Spielankündigung wurde geändert – zeigt Alt vs. Neu."""
    def row(label: str, alt: str, neu: str) -> str:
        changed = alt != neu
        farbe   = "#f0a500" if changed else "#333"
        return (
            f"<tr><td style='padding:8px;color:#888;width:130px;'>{label}</td>"
            f"<td style='padding:8px;text-decoration:line-through;color:#999;'>{alt}</td>"
            f"<td style='padding:8px;font-weight:bold;color:{farbe};'>{neu}</td></tr>"
        )
    return f"""
    <!DOCTYPE html><html>
    <body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
      <div style="max-width:620px;margin:0 auto;background:#fff;border-radius:12px;
                  overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.15);">
        <div style="background:#f0a500;padding:24px 28px;">
          <h1 style="margin:0;color:#fff;font-size:22px;">✏️ Spieländerung</h1>
          <p style="margin:4px 0 0;color:#fff3d0;font-size:14px;">
            Ein Spieltermin wurde angepasst
          </p>
        </div>
        <div style="padding:24px 28px;">
          <p style="color:#333;">
            <b>⚽ {heimteam} vs {gastteam}</b><br>
            Der folgende Termin wurde im DFBnet geändert:
          </p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0;">
            <tr style="background:#eee;">
              <th style="padding:8px;text-align:left;color:#555;">Feld</th>
              <th style="padding:8px;text-align:left;color:#555;">Alt</th>
              <th style="padding:8px;text-align:left;color:#f0a500;">Neu ✓</th>
            </tr>
            {row("Datum", datum_alt.strftime("%d.%m.%Y"), datum_neu.strftime("%d.%m.%Y"))}
            {row("Uhrzeit", uhrzeit_alt, uhrzeit_neu)}
            {row("Platz", platz_alt, platz_neu)}
            {row("Kabine", kabine_alt or "–", kabine_neu or "–")}
          </table>
          <div style="background:#fff8e1;border-left:4px solid #f0a500;
                      padding:14px 16px;border-radius:6px;margin:16px 0;">
            <b style="color:#f0a500;">ℹ️ Bitte Termin im Kalender aktualisieren</b><br>
            <span style="color:#555;font-size:13px;">
              Die Änderung ist bereits auf
              <a href="https://www.fussball.de" style="color:#C8102E;">fussball.de</a>
              sichtbar.
            </span>
          </div>
        </div>
        <div style="background:#f0f0f0;padding:14px 28px;font-size:12px;
                    color:#888;text-align:center;">
          Automatische Benachrichtigung · FCTM Spielbetrieb-Manager
        </div>
      </div>
    </body></html>
    """


def _mail_trainer_stornierung_html(
    datum: date,
    uhrzeit: str,
    platz: str,
    heimteam: str,
    gastteam: str,
    grund: str,
) -> str:
    """E-Mail an Trainer: Spiel wurde storniert."""
    return f"""
    <!DOCTYPE html><html>
    <body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;
                  overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.15);">
        <div style="background:#ef4444;padding:24px 28px;">
          <h1 style="margin:0;color:#fff;font-size:22px;">❌ Spielabsage</h1>
          <p style="margin:4px 0 0;color:#ffd6d6;font-size:14px;">
            Ein Pflichtspiel wurde abgesagt
          </p>
        </div>
        <div style="padding:24px 28px;">
          <p style="color:#333;">
            Das folgende Spiel wurde abgesagt und im DFBnet storniert:
          </p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0;">
            <tr style="background:#fafafa;">
              <td style="padding:8px;color:#888;width:140px;">Datum</td>
              <td style="padding:8px;font-weight:bold;">{datum.strftime('%A, %d.%m.%Y')}</td></tr>
            <tr>
              <td style="padding:8px;color:#888;">Uhrzeit</td>
              <td style="padding:8px;font-weight:bold;">{uhrzeit} Uhr</td></tr>
            <tr style="background:#fafafa;">
              <td style="padding:8px;color:#888;">Platz</td>
              <td style="padding:8px;">{platz}</td></tr>
            <tr>
              <td style="padding:8px;color:#888;">Begegnung</td>
              <td style="padding:8px;font-weight:bold;">{heimteam} vs {gastteam}</td></tr>
          </table>
          {f'<p style="color:#666;font-size:13px;"><b>Grund:</b> {grund}</p>' if grund else ''}
          <div style="background:#fee2e2;border-left:4px solid #ef4444;
                      padding:14px 16px;border-radius:6px;margin:16px 0;">
            <b style="color:#ef4444;">📋 Das Training kann wie gewohnt stattfinden.</b><br>
            <span style="color:#555;font-size:13px;">
              Der Platz ist wieder frei. Die Änderung ist auf
              <a href="https://www.fussball.de" style="color:#C8102E;">fussball.de</a>
              sichtbar.
            </span>
          </div>
        </div>
        <div style="background:#f0f0f0;padding:14px 28px;font-size:12px;
                    color:#888;text-align:center;">
          Automatische Benachrichtigung · FCTM Spielbetrieb-Manager
        </div>
      </div>
    </body></html>
    """


def _mail_anfrage_html(
    anfrage_id: int,
    datum: date,
    uhrzeit: str,
    platz: str,
    heimteam: str,
    gastteam: str,
    kabine: str,
    notizen: str,
    konflikte: list[str],
    typ: str = "Neue Spielanfrage",
) -> str:
    """
    Erstellt die HTML-E-Mail für Spielanfrage ODER direkt angelegtes Spiel.
    Enthält immer den DFBnet-Eintragungshinweis.
    """
    konflikt_block = ""
    if konflikte:
        items = "".join(f"<li>{t}</li>" for t in konflikte)
        konflikt_block = f"""
        <div style="background:#fff3cd;border-left:4px solid #e0a800;
                    padding:12px 16px;border-radius:6px;margin:16px 0;">
          <b>⚠️ Trainingskonflikt – betroffene Teams:</b>
          <ul style="margin:6px 0 0 0;">{items}</ul>
          <p style="margin:8px 0 0 0;font-size:13px;color:#6c4d00;">
            Der anfragende Trainer ist für die Abstimmung mit den betroffenen Teams verantwortlich.
          </p>
        </div>"""

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;
                  border-radius:12px;overflow:hidden;
                  box-shadow:0 2px 12px rgba(0,0,0,.15);">

        <!-- Header -->
        <div style="background:#C8102E;padding:24px 28px;">
          <h1 style="margin:0;color:#fff;font-size:22px;">⚽ FCTM – {typ}</h1>
          <p style="margin:4px 0 0 0;color:#ffd6dc;font-size:14px;">
            Spielbetrieb-Manager · {date.today().strftime('%d.%m.%Y')}
          </p>
        </div>

        <!-- Details -->
        <div style="padding:24px 28px;">
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:6px 0;color:#888;width:140px;">Anfrage-ID</td>
                <td style="padding:6px 0;font-weight:bold;">#{anfrage_id}</td></tr>
            <tr style="background:#fafafa;">
                <td style="padding:6px 8px;color:#888;">Datum</td>
                <td style="padding:6px 8px;font-weight:bold;">
                    {datum.strftime('%A, %d.%m.%Y')}</td></tr>
            <tr><td style="padding:6px 0;color:#888;">Anstoßzeit</td>
                <td style="padding:6px 0;font-weight:bold;">{uhrzeit} Uhr</td></tr>
            <tr style="background:#fafafa;">
                <td style="padding:6px 8px;color:#888;">Platz</td>
                <td style="padding:6px 8px;font-weight:bold;">{platz}</td></tr>
            <tr><td style="padding:6px 0;color:#888;">Heimteam</td>
                <td style="padding:6px 0;font-weight:bold;">{heimteam}</td></tr>
            <tr style="background:#fafafa;">
                <td style="padding:6px 8px;color:#888;">Gastteam</td>
                <td style="padding:6px 8px;font-weight:bold;">{gastteam}</td></tr>
            <tr><td style="padding:6px 0;color:#888;">Kabine</td>
                <td style="padding:6px 0;">{kabine or '–'}</td></tr>
            {f'<tr style="background:#fafafa;"><td style="padding:6px 8px;color:#888;">Notizen</td><td style="padding:6px 8px;">{notizen}</td></tr>' if notizen else ''}
          </table>

          {konflikt_block}

          <!-- DFBnet-Hinweis -->
          <div style="background:#e8f4fd;border-left:4px solid #0078d4;
                      padding:14px 16px;border-radius:6px;margin:20px 0;">
            <b style="color:#005a9e;">📋 DFBnet-Eintragung erforderlich</b>
            <p style="margin:8px 0 0 0;font-size:13px;color:#1a3a5c;">
              Dieses Spiel muss manuell im
              <a href="https://www.dfbnet.org" style="color:#0078d4;">DFBnet</a>
              durch den Ansetzer eingetragen werden.<br>
              Bitte die Spielansetzung zeitnah vornehmen und alle beteiligten
              Mannschaften informieren.
            </p>
          </div>
        </div>

        <!-- Footer -->
        <div style="background:#f0f0f0;padding:14px 28px;
                    font-size:12px;color:#888;text-align:center;">
          Diese Nachricht wurde automatisch vom FCTM Spielbetrieb-Manager gesendet.
        </div>
      </div>
    </body>
    </html>
    """


def _mail_ablehnung_html(
    anfrage_id: int,
    typ: str,
    heimteam: str,
    gastteam: str,
    datum_str: str,
    uhrzeit: str,
    platz: str,
    grund: str,
) -> str:
    """E-Mail an Trainer: Anfrage wurde abgelehnt."""
    typ_labels = {
        "neu": "Neue Spielanfrage",
        "aenderung": "Spieländerung",
        "verlegung": "Spielverlegung",
        "uhrzeit_aenderung": "Uhrzeitänderung",
        "stornierung": "Stornierungsantrag",
        "allgemein": "Freie Anfrage",
    }
    typ_label = typ_labels.get(typ, "Anfrage")
    spiel_block = (
        f"""
        <table style="width:100%;border-collapse:collapse;margin:10px 0;">
          <tr style="background:#fafafa;">
            <td style="padding:7px;color:#888;width:130px;">Begegnung</td>
            <td style="padding:7px;font-weight:bold;">{heimteam} vs {gastteam}</td></tr>
          <tr>
            <td style="padding:7px;color:#888;">Datum</td>
            <td style="padding:7px;">{datum_str}</td></tr>
          <tr style="background:#fafafa;">
            <td style="padding:7px;color:#888;">Uhrzeit</td>
            <td style="padding:7px;">{uhrzeit} Uhr</td></tr>
          <tr>
            <td style="padding:7px;color:#888;">Platz</td>
            <td style="padding:7px;">{platz}</td></tr>
        </table>"""
        if heimteam or gastteam else ""
    )
    return f"""
    <!DOCTYPE html><html>
    <body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;
                  overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.15);">
        <div style="background:#ef4444;padding:24px 28px;">
          <h1 style="margin:0;color:#fff;font-size:22px;">&#10060; Anfrage abgelehnt</h1>
          <p style="margin:4px 0 0;color:#ffd6d6;font-size:14px;">
            {typ_label} &middot; Anfrage #{anfrage_id}
          </p>
        </div>
        <div style="padding:24px 28px;">
          {spiel_block}
          <div style="background:#fee2e2;border-left:4px solid #ef4444;
                      padding:14px 16px;border-radius:6px;margin:16px 0;">
            <b style="color:#7f1d1d;">Ablehnungsgrund:</b>
            <p style="margin:8px 0 0 0;color:#7f1d1d;font-size:13px;">{grund}</p>
          </div>
          <p style="color:#666;font-size:13px;">
            Bei Fragen bitte direkt beim Spielbetrieb melden.
          </p>
        </div>
        <div style="background:#f0f0f0;padding:14px 28px;font-size:12px;
                    color:#888;text-align:center;">
          Automatische Benachrichtigung &middot; FCTM Spielbetrieb-Manager
        </div>
      </div>
    </body></html>
    """


def _mail_antwort_html(
    anfrage_id: int,
    team: str,
    betreff: str,
    antwort: str,
) -> str:
    """E-Mail an Trainer: Antwort auf eine freie Anfrage."""
    return f"""
    <!DOCTYPE html><html>
    <body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;
                  overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.15);">
        <div style="background:#10b981;padding:24px 28px;">
          <h1 style="margin:0;color:#fff;font-size:22px;">&#128172; Antwort vom Spielbetrieb</h1>
          <p style="margin:4px 0 0;color:#d1fae5;font-size:14px;">
            Anfrage #{anfrage_id} &middot; {team}
          </p>
        </div>
        <div style="padding:24px 28px;">
          <p style="color:#333;"><b>Betreff Ihrer Anfrage:</b> {betreff}</p>
          <div style="background:#f0fdf4;border-left:4px solid #10b981;
                      padding:14px 16px;border-radius:6px;margin:16px 0;">
            <b style="color:#065f46;">Antwort:</b>
            <p style="margin:8px 0 0 0;color:#065f46;font-size:13px;white-space:pre-wrap;">{antwort}</p>
          </div>
        </div>
        <div style="background:#f0f0f0;padding:14px 28px;font-size:12px;
                    color:#888;text-align:center;">
          Automatische Benachrichtigung &middot; FCTM Spielbetrieb-Manager
        </div>
      </div>
    </body></html>
    """


# ── Spielanfragen ─────────────────────────────────────────────────────────────

def create_spielanfrage(datum, uhrzeit, platz, heimteam, gastteam, kabine="", notizen="", erstellt_von="") -> int:
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen (datum,uhrzeit,platz,heimteam,gastteam,kabine,notizen,erstellt_von) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (datum.isoformat(), uhrzeit, platz, heimteam, gastteam, kabine, notizen, erstellt_von),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_aenderung(
    spiel_id: int,
    neues_datum: date,
    neue_uhrzeit: str,
    neuer_platz: str,
    notizen: str,
    erstellt_von: str = "",
) -> int:
    """Nutzer beantragt eine Änderung eines bestehenden Spiels. Kabine wird vom Admin vergeben."""
    conn = db_connect()
    row = conn.execute("SELECT * FROM spiele WHERE id=?", (spiel_id,)).fetchone()
    conn.close()
    if not row:
        return -1
    sp_cols = ["id","datum","uhrzeit","platz","heimteam","gastteam","kabine","notizen"]
    sp = dict(zip(sp_cols, row[:len(sp_cols)]))
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen "
        "(datum,uhrzeit,platz,heimteam,gastteam,kabine,notizen,"
        "anfrage_typ,spiel_id,neues_datum,neue_uhrzeit,neuer_platz,neue_kabine,erstellt_von) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            sp["datum"], sp["uhrzeit"], sp["platz"],
            sp["heimteam"], sp["gastteam"], sp["kabine"], notizen,
            "aenderung", spiel_id,
            neues_datum.isoformat(), neue_uhrzeit, neuer_platz,
            sp["kabine"],  # neue_kabine: vorerst alte Kabine, Admin ändert beim Genehmigen
            erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_stornierung(spiel_id: int, notizen: str, erstellt_von: str = "") -> int:
    """Nutzer beantragt die Stornierung eines bestehenden Spiels."""
    conn = db_connect()
    row = conn.execute("SELECT * FROM spiele WHERE id=?", (spiel_id,)).fetchone()
    conn.close()
    if not row:
        return -1
    sp_cols = ["id","datum","uhrzeit","platz","heimteam","gastteam","kabine","notizen"]
    sp = dict(zip(sp_cols, row[:len(sp_cols)]))
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen "
        "(datum,uhrzeit,platz,heimteam,gastteam,kabine,notizen,anfrage_typ,spiel_id,erstellt_von) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            sp["datum"], sp["uhrzeit"], sp["platz"],
            sp["heimteam"], sp["gastteam"], sp["kabine"], notizen,
            "stornierung", spiel_id, erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_verlegung(
    spiel_id: int,
    neues_datum: date,
    neue_uhrzeit: str,
    neuer_platz: str,
    notizen: str,
    erstellt_von: str = "",
) -> int:
    """Trainer beantragt Spielverlegung – neues Datum + ggf. Zeit/Platz."""
    conn = db_connect()
    row = conn.execute("SELECT * FROM spiele WHERE id=?", (spiel_id,)).fetchone()
    conn.close()
    if not row:
        return -1
    sp_cols = ["id","datum","uhrzeit","platz","heimteam","gastteam","kabine","notizen"]
    sp = dict(zip(sp_cols, row[:len(sp_cols)]))
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen "
        "(datum,uhrzeit,platz,heimteam,gastteam,kabine,notizen,"
        "anfrage_typ,spiel_id,neues_datum,neue_uhrzeit,neuer_platz,neue_kabine,erstellt_von) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            sp["datum"], sp["uhrzeit"], sp["platz"],
            sp["heimteam"], sp["gastteam"], sp["kabine"], notizen,
            "verlegung", spiel_id,
            neues_datum.isoformat(), neue_uhrzeit, neuer_platz,
            sp["kabine"],
            erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_uhrzeit_aenderung(
    spiel_id: int,
    neue_uhrzeit: str,
    notizen: str,
    erstellt_von: str = "",
) -> int:
    """Trainer beantragt ausschließlich eine andere Anstoßzeit."""
    conn = db_connect()
    row = conn.execute("SELECT * FROM spiele WHERE id=?", (spiel_id,)).fetchone()
    conn.close()
    if not row:
        return -1
    sp_cols = ["id","datum","uhrzeit","platz","heimteam","gastteam","kabine","notizen"]
    sp = dict(zip(sp_cols, row[:len(sp_cols)]))
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen "
        "(datum,uhrzeit,platz,heimteam,gastteam,kabine,notizen,"
        "anfrage_typ,spiel_id,neue_uhrzeit,neues_datum,neuer_platz,neue_kabine,erstellt_von) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            sp["datum"], sp["uhrzeit"], sp["platz"],
            sp["heimteam"], sp["gastteam"], sp["kabine"], notizen,
            "uhrzeit_aenderung", spiel_id,
            neue_uhrzeit, sp["datum"], sp["platz"],
            sp["kabine"],
            erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_verlegung_direkt(
    datum: date,
    uhrzeit: str,
    platz: str,
    heimteam: str,
    gastteam: str,
    neues_datum: date,
    neue_uhrzeit: str,
    neuer_platz: str,
    notizen: str,
    erstellt_von: str = "",
) -> int:
    """Verlegungsantrag für ein DFBnet-Spiel ohne Systemeintrag (spiel_id = NULL)."""
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen "
        "(datum,uhrzeit,platz,heimteam,gastteam,notizen,"
        "anfrage_typ,neues_datum,neue_uhrzeit,neuer_platz,erstellt_von) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            datum.isoformat(), uhrzeit, platz, heimteam, gastteam, notizen,
            "verlegung",
            neues_datum.isoformat(), neue_uhrzeit, neuer_platz,
            erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_uhrzeit_aenderung_direkt(
    datum: date,
    uhrzeit: str,
    platz: str,
    heimteam: str,
    gastteam: str,
    neue_uhrzeit: str,
    notizen: str,
    erstellt_von: str = "",
) -> int:
    """Uhrzeitänderung für ein DFBnet-Spiel ohne Systemeintrag (spiel_id = NULL)."""
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen "
        "(datum,uhrzeit,platz,heimteam,gastteam,notizen,"
        "anfrage_typ,neue_uhrzeit,neues_datum,neuer_platz,erstellt_von) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            datum.isoformat(), uhrzeit, platz, heimteam, gastteam, notizen,
            "uhrzeit_aenderung",
            neue_uhrzeit, datum.isoformat(), platz,
            erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_stornierung_direkt(
    datum: date,
    uhrzeit: str,
    platz: str,
    heimteam: str,
    gastteam: str,
    notizen: str,
    erstellt_von: str = "",
) -> int:
    """Stornierungsantrag für ein DFBnet-Spiel ohne Systemeintrag (spiel_id = NULL)."""
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen "
        "(datum,uhrzeit,platz,heimteam,gastteam,notizen,anfrage_typ,erstellt_von) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            datum.isoformat(), uhrzeit, platz, heimteam, gastteam, notizen,
            "stornierung", erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_allgemein(
    betreff: str,
    nachricht: str,
    erstellt_von: str = "",
) -> int:
    """Freie Anfrage / Rückfrage an den Spielbetrieb – kein Spielbezug nötig."""
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen "
        "(datum,uhrzeit,platz,notizen,anfrage_typ,erstellt_von,betreff,nachricht) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            date.today().isoformat(), "", "",
            nachricht, "allgemein", erstellt_von,
            betreff, nachricht,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def update_match_details(
    mid: int,
    neues_datum: date,
    neue_uhrzeit: str,
    neuer_platz: str,
    neue_kabine: str,
    notizen: str,
) -> None:
    """Aktualisiert ein Spiel direkt (Admin-Aktion)."""
    conn = db_connect()
    conn.execute(
        "UPDATE spiele SET datum=?,uhrzeit=?,platz=?,kabine=?,notizen=? WHERE id=?",
        (neues_datum.isoformat(), neue_uhrzeit, neuer_platz, neue_kabine, notizen, mid),
    )
    conn.commit()
    conn.close()


def get_all_anfragen() -> pd.DataFrame:
    conn = db_connect()
    df = pd.read_sql("SELECT * FROM spielanfragen ORDER BY datum,uhrzeit", conn)
    conn.close()
    return df


def get_anfrage_notizen(anfrage_id: int, limit: int | None = 5) -> pd.DataFrame:
    conn = db_connect()
    if limit is None:
        df = pd.read_sql(
            "SELECT notiz, erstellt_von, erstellt_am FROM anfrage_notizen "
            "WHERE anfrage_id=? ORDER BY id DESC",
            conn,
            params=(anfrage_id,),
        )
    else:
        df = pd.read_sql(
            "SELECT notiz, erstellt_von, erstellt_am FROM anfrage_notizen "
            "WHERE anfrage_id=? ORDER BY id DESC LIMIT ?",
            conn,
            params=(anfrage_id, limit),
        )
    conn.close()
    return df


def save_anfrage_notiz(anfrage_id: int, notiz: str, autor: str = "Admin") -> None:
    clean = (notiz or "").strip()
    conn = db_connect()
    row = conn.execute(
        "SELECT verwalter_notiz FROM spielanfragen WHERE id=?",
        (anfrage_id,),
    ).fetchone()
    prev = (row[0] if row and row[0] else "").strip()

    if clean == prev:
        conn.close()
        return

    conn.execute(
        "UPDATE spielanfragen SET verwalter_notiz=? WHERE id=?",
        (clean, anfrage_id),
    )
    conn.execute(
        "INSERT INTO anfrage_notizen (anfrage_id, notiz, erstellt_von) VALUES (?,?,?)",
        (anfrage_id, clean if clean else "[Notiz entfernt]", autor),
    )
    conn.commit()
    conn.close()


def _anfrage_timeline_html(anfrage_typ: str, status: str) -> str:
    if anfrage_typ == "allgemein":
        steps = ["Eingang", "In Bearbeitung", "Antwort"]
        state_map = {
            "ausstehend": ["done", "active", "todo"],
            "dfbnet_ausstehend": ["done", "active", "todo"],
            "abgeschlossen": ["done", "done", "done"],
            "genehmigt": ["done", "done", "done"],
            "abgelehnt": ["done", "done", "rejected"],
        }
    else:
        steps = ["Eingang", "Pruefung", "DFBnet", "Erledigt"]
        state_map = {
            "ausstehend": ["done", "active", "todo", "todo"],
            "dfbnet_ausstehend": ["done", "done", "active", "todo"],
            "abgeschlossen": ["done", "done", "done", "done"],
            "genehmigt": ["done", "done", "done", "done"],
            "abgelehnt": ["done", "done", "todo", "rejected"],
        }

    states = state_map.get(status, ["done", "active", "todo", "todo"])
    icon = {
        "done": "✅",
        "active": "🟡",
        "todo": "⚪",
        "rejected": "❌",
    }
    color = {
        "done": "#065f46",
        "active": "#92400e",
        "todo": "#6b7280",
        "rejected": "#991b1b",
    }

    parts = []
    for idx, label in enumerate(steps):
        stt = states[idx] if idx < len(states) else "todo"
        parts.append(
            f'<span style="color:{color[stt]};font-size:12px;white-space:nowrap;">'
            f'{icon[stt]} {label}</span>'
        )

    connector = '<span style="color:#9ca3af;">→</span>'
    return (
        '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:6px;">'
        + connector.join(parts)
        + "</div>"
    )


def _render_verwalter_notizblock(r: pd.Series, key_prefix: str) -> None:
    cur_notiz = r.get("verwalter_notiz") or ""
    n1, n2 = st.columns([5, 1])
    with n1:
        neue_notiz = st.text_area(
            "📝 Interne Notiz (nur für Verwalter)",
            value=cur_notiz,
            key=f"{key_prefix}_notiz_{r['id']}",
            placeholder="Rücksprachen, offene Punkte, interne Hinweise ...",
            height=80,
        )
    with n2:
        st.write("")
        st.write("")
        if st.button("💾", key=f"{key_prefix}_save_{r['id']}", help="Notiz speichern"):
            bearbeiter_name = (
                st.session_state.get("ms_name")
                or st.session_state.get("ms_email")
                or "Admin"
            )
            save_anfrage_notiz(int(r["id"]), neue_notiz, autor=bearbeiter_name)
            st.success("Notiz gespeichert.")
            st.rerun()

    with st.expander("🕒 Notizverlauf", expanded=False):
        show_all_key = f"{key_prefix}_showall_{r['id']}"
        if show_all_key not in st.session_state:
            st.session_state[show_all_key] = False
        show_all = st.session_state[show_all_key]

        c_hist1, c_hist2 = st.columns([3, 1])
        with c_hist2:
            if show_all:
                if st.button("Nur letzte 5", key=f"{key_prefix}_hist_less_{r['id']}"):
                    st.session_state[show_all_key] = False
                    st.rerun()
            else:
                if st.button("Alle anzeigen", key=f"{key_prefix}_hist_all_{r['id']}"):
                    st.session_state[show_all_key] = True
                    st.rerun()

        hist = get_anfrage_notizen(int(r["id"]), limit=None if show_all else 5)
        if hist.empty:
            st.caption("Noch keine Notiz-Historie vorhanden.")
        else:
            for _, hr in hist.iterrows():
                von = hr.get("erstellt_von") or "System"
                zeit = hr.get("erstellt_am") or ""
                txt = hr.get("notiz") or ""
                st.markdown(
                    f"• **{zeit}** · {von}<br>"
                    f"<span style='color:#374151;'>{txt}</span>",
                    unsafe_allow_html=True,
                )


def update_anfrage_status(aid: int, status: str, bearbeiter: str, kommentar: str = "") -> None:
    conn = db_connect()
    conn.execute(
        "UPDATE spielanfragen "
        "SET status=?, bearbeiter=?, bearbeitet_am=datetime('now'), bearbeiter_kommentar=? WHERE id=?",
        (status, bearbeiter, kommentar, aid),
    )
    conn.commit()
    conn.close()


def approve_anfrage(aid: int, betroffene: list[str]) -> None:
    """
    Schritt 1: Anfrage genehmigen → wartet auf DFBnet-Bestätigung.
    Das Spiel wird noch NICHT ins Dashboard übernommen.
    """
    # betroffene Teams separat speichern für spätere Verwendung
    conn = db_connect()
    conn.execute(
        "UPDATE spielanfragen SET bearbeiter='Admin' WHERE id=?", (aid,)
    )
    conn.commit()
    conn.close()
    update_anfrage_status(aid, "dfbnet_ausstehend", "Admin")


def confirm_dfbnet(aid: int) -> int:
    """
    Schritt 2: DFBnet-Eintragung bestätigt.
    - 'neu':          Spiel wird neu ins Dashboard übernommen.
    - 'aenderung':    Bestehendes Spiel wird aktualisiert.
    - 'stornierung':  Bestehendes Spiel wird gelöscht.
    Gibt die Spiel-ID zurück (-1 bei Fehler, 0 bei Stornierung).
    """
    conn = db_connect()
    row = conn.execute("SELECT * FROM spielanfragen WHERE id=?", (aid,)).fetchone()
    conn.close()
    if not row:
        return -1
    # Spaltennamen dynamisch aus Cursor holen
    conn = db_connect()
    cur = conn.execute("SELECT * FROM spielanfragen WHERE id=?", (aid,))
    col_names = [d[0] for d in cur.description]
    r = dict(zip(col_names, cur.fetchone()))
    conn.close()

    typ = r.get("anfrage_typ") or "neu"

    if typ == "stornierung":
        if r.get("spiel_id"):
            delete_match(int(r["spiel_id"]))
        update_anfrage_status(aid, "abgeschlossen", "Admin")
        return 0

    if typ == "allgemein":
        update_anfrage_status(aid, "abgeschlossen", "Admin")
        return 0

    if typ in ("aenderung", "verlegung", "uhrzeit_aenderung"):
        if r.get("spiel_id"):
            # Systemeintrag vorhanden → Spiel im Dashboard aktualisieren
            update_match_details(
                int(r["spiel_id"]),
                date.fromisoformat(r["neues_datum"]),
                r["neue_uhrzeit"], r["neuer_platz"],
                r.get("neue_kabine") or r.get("kabine") or "",
                r.get("notizen") or "",
            )
            conn2 = db_connect()
            conn2.execute("UPDATE spiele SET dfbnet_eingetragen=1 WHERE id=?", (r["spiel_id"],))
            conn2.commit()
            conn2.close()
            update_anfrage_status(aid, "abgeschlossen", "Admin")
            return int(r["spiel_id"])
        else:
            # DFBnet-Spiel ohne Systemeintrag → beim Bestätigen neu im System anlegen
            ziel_datum = r.get("neues_datum") or r.get("datum")
            ziel_uhrzeit = r.get("neue_uhrzeit") or r.get("uhrzeit") or ""
            ziel_platz = r.get("neuer_platz") or r.get("platz") or ""
            ziel_kabine = r.get("neue_kabine") or r.get("kabine") or ""

            sid = save_match(
                date.fromisoformat(ziel_datum),
                ziel_uhrzeit,
                ziel_platz,
                r.get("heimteam") or "",
                r.get("gastteam") or "",
                ziel_kabine,
                r.get("notizen") or "",
                [],
                quelle="automatisch_aus_anfrage",
                ursprung_anfrage_id=aid,
            )
            conn2 = db_connect()
            conn2.execute("UPDATE spiele SET dfbnet_eingetragen=1 WHERE id=?", (sid,))
            conn2.execute("UPDATE spielanfragen SET spiel_id=? WHERE id=?", (sid, aid))
            conn2.commit()
            conn2.close()
            update_anfrage_status(aid, "abgeschlossen", "Admin")
            return sid

    # typ == 'neu' (Standard)
    sid = save_match(
        date.fromisoformat(r["datum"]), r["uhrzeit"], r["platz"],
        r["heimteam"] or "", r["gastteam"] or "",
        r["kabine"] or "", r["notizen"] or "", [],
        quelle="aus_anfrage",
        ursprung_anfrage_id=aid,
    )
    conn2 = db_connect()
    conn2.execute("UPDATE spiele SET dfbnet_eingetragen=1 WHERE id=?", (sid,))
    conn2.commit()
    conn2.close()
    update_anfrage_status(aid, "abgeschlossen", "Admin")
    return sid


def get_trainer_email_for_team(team: str) -> str:
    """Sucht die Trainer-E-Mail zur Mannschaft in der aktuellen Saisonplanung."""
    conn = db_connect()
    row = conn.execute(
        "SELECT trainer_email FROM saisonplanung "
        "WHERE team=? AND trainer_email IS NOT NULL AND trainer_email != '' LIMIT 1",
        (team,),
    ).fetchone()
    conn.close()
    return row[0] if row else ""


def get_all_anfragen_dfbnet() -> pd.DataFrame:
    """Gibt alle Anfragen mit Status dfbnet_ausstehend zurück."""
    conn = db_connect()
    df = pd.read_sql(
        "SELECT * FROM spielanfragen WHERE status='dfbnet_ausstehend' ORDER BY datum,uhrzeit",
        conn,
    )
    conn.close()
    return df


# ── Platz-Sperren ─────────────────────────────────────────────────────────────

def toggle_pitch_lock(platz: str, datum: date, grund: str, lock: bool) -> None:
    conn = db_connect()
    row = conn.execute(
        "SELECT id FROM platz_sperren WHERE platz=? AND datum=?",
        (platz, datum.isoformat()),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE platz_sperren SET gesperrt=?,grund=? WHERE id=?",
            (1 if lock else 0, grund, row[0]),
        )
    elif lock:
        conn.execute(
            "INSERT INTO platz_sperren (platz,datum,grund) VALUES (?,?,?)",
            (platz, datum.isoformat(), grund),
        )
    conn.commit()
    conn.close()


def get_locked_pitches(d: date) -> list[str]:
    conn = db_connect()
    rows = conn.execute(
        "SELECT platz FROM platz_sperren WHERE datum=? AND gesperrt=1",
        (d.isoformat(),),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ── Saisonplanung ─────────────────────────────────────────────────────────────

def save_saisonplanung(df: pd.DataFrame, saison: str) -> None:
    conn = db_connect()
    conn.execute("DELETE FROM saisonplanung WHERE saison=?", (saison,))
    save_df = df.copy()
    save_df["saison"] = saison
    save_df.to_sql("saisonplanung", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()


def add_training_slot(
    team: str,
    tag: str,
    zeit: str,
    zeit_ende: str,
    platz: str,
    saison: str,
    kabine: str = "",
    trainer_email: str = "",
) -> None:
    """Fügt einen einzelnen Trainingsslot zur Saisonplanung hinzu."""
    conn = db_connect()
    conn.execute(
        "INSERT INTO saisonplanung "
        "(team, platz, tag, zeit, zeit_ende, kabine, trainer_email, saison) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (team, platz, tag, zeit, zeit_ende, kabine, trainer_email, saison),
    )
    conn.commit()
    conn.close()


def delete_training_slot(slot_id: int) -> None:
    """Löscht einen einzelnen Trainingsslot."""
    conn = db_connect()
    conn.execute("DELETE FROM saisonplanung WHERE id=?", (slot_id,))
    conn.commit()
    conn.close()


def load_training_df_from_db(saison: str) -> pd.DataFrame:
    """
    Lädt die Saisonplanung aus der DB und gibt sie als DataFrame
    mit den für die App erwarteten Spaltennamen zurück
    (Team, Platz, Tag, Zeit, ZeitEnde).
    """
    sp = get_saisonplanung(saison)
    if sp.empty:
        return pd.DataFrame()
    sp = sp.rename(columns={"team": "Team", "platz": "Platz", "tag": "Tag", "zeit": "Zeit"})
    if "zeit_ende" in sp.columns:
        sp = sp.rename(columns={"zeit_ende": "ZeitEnde"})
    else:
        sp["ZeitEnde"] = ""
    return sp[["Team", "Platz", "Tag", "Zeit", "ZeitEnde"]]


def update_kabinen_und_emails(
    saison: str,
    assignments: dict[str, str],
    trainer_emails: dict[str, str],
) -> None:
    """Aktualisiert nur Kabine und Trainer-E-Mail je Team – löscht keine Slots."""
    conn = db_connect()
    for team, kabine in assignments.items():
        conn.execute(
            "UPDATE saisonplanung SET kabine=?, trainer_email=? "
            "WHERE team=? AND saison=?",
            (kabine, trainer_emails.get(team, ""), team, saison),
        )
    conn.commit()
    conn.close()


def get_saisonplanung(saison: str) -> pd.DataFrame:
    conn = db_connect()
    df = pd.read_sql(
        "SELECT * FROM saisonplanung WHERE saison=? ORDER BY tag,zeit",
        conn, params=(saison,),
    )
    conn.close()
    return df


def get_kabinen_konflikte(saison: str) -> pd.DataFrame:
    """
    Findet Kabinen, die im selben Tag+Zeit-Slot mehrfach belegt sind.
    Gibt DataFrame mit [kabine, tag, zeit, anzahl, teams] zurück.
    """
    df = get_saisonplanung(saison)
    if df.empty or "kabine" not in df.columns:
        return pd.DataFrame()
    df = df[df["kabine"].notna() & (df["kabine"] != "")]
    grouped = (
        df.groupby(["kabine", "tag", "zeit"])["team"]
        .agg(list)
        .reset_index()
    )
    konflikte = grouped[grouped["team"].apply(len) > 1].copy()
    konflikte["anzahl"] = konflikte["team"].apply(len)
    konflikte["teams"]  = konflikte["team"].apply(lambda t: ", ".join(t))
    return konflikte[["kabine", "tag", "zeit", "anzahl", "teams"]]


# ── Statistiken ───────────────────────────────────────────────────────────────

def get_cancellation_stats() -> pd.DataFrame:
    conn = db_connect()
    df = pd.read_sql(
        "SELECT team, COUNT(*) AS ausfaelle FROM training_ausfaelle "
        "GROUP BY team ORDER BY ausfaelle DESC",
        conn,
    )
    conn.close()
    return df


# ── CSV / Excel-Parser ────────────────────────────────────────────────────────

def parse_trainingsplan(source) -> pd.DataFrame:
    """
    Parst den gestapelten Trainingsplan (CSV oder Excel) in ein flaches DataFrame.
    Spalten: [Platz, Bereich, Tag, Zeit, Team]

    Struktur:
      Abschnitt 1 (Zeilen 0-11)  : Rasen vorne + Rasen hinten
      Abschnitt 2 (Zeilen 13-25) : Kunstrasen vorne + Kunstrasen hinten
      Abschnitt 3 (Zeilen 27-39) : Wigger-Arena
    """
    sections = [
        {"name": "Rasen",
         "sub_plaetze": ["Rasen vorne", "Rasen hinten"],
         "start_row": 0,  "data_rows": 11},
        {"name": "Kunstrasen",
         "sub_plaetze": ["Kunstrasen vorne", "Kunstrasen hinten"],
         "start_row": 13, "data_rows": 11},
        {"name": "Wigger-Arena",
         "sub_plaetze": ["Wigger-Arena"],
         "start_row": 27, "data_rows": 11},
    ]
    if isinstance(source, str):
        df_raw = pd.read_csv(io.StringIO(source), header=None)
    else:
        df_raw = pd.read_excel(source, header=None)

    records: list[dict] = []
    for sec in sections:
        start = sec["start_row"]
        data_rows = df_raw.iloc[start + 1 : start + 1 + sec["data_rows"]]
        for _, row in data_rows.iterrows():
            zeit = str(row.iloc[0]).strip()
            if not zeit or zeit.lower() == "nan":
                continue
            for s_idx, sub_platz in enumerate(sec["sub_plaetze"]):
                col_offset = 1 + s_idx * 7
                for d_idx, day in enumerate(DAYS):
                    col = col_offset + d_idx
                    if col < len(row):
                        team = row.iloc[col]
                        if pd.notna(team) and str(team).strip() not in ("", "nan", "-"):
                            records.append({
                                "Platz":   sub_platz,
                                "Bereich": sec["name"],
                                "Tag":     day,
                                "Zeit":    zeit,
                                "Team":    str(team).strip(),
                            })
    return pd.DataFrame(records, columns=["Platz", "Bereich", "Tag", "Zeit", "Team"])


def create_sample_csv() -> str:
    sample: dict[tuple, str] = {
        ("Rasen vorne",       "Montag",     "17:00"): "U19",
        ("Rasen vorne",       "Dienstag",   "18:00"): "1. Mannschaft",
        ("Rasen vorne",       "Mittwoch",   "17:00"): "U17",
        ("Rasen vorne",       "Freitag",    "16:00"): "U17",
        ("Rasen hinten",      "Montag",     "16:00"): "U15",
        ("Rasen hinten",      "Donnerstag", "19:00"): "U13",
        ("Rasen hinten",      "Samstag",    "10:00"): "Damen",
        ("Kunstrasen vorne",  "Dienstag",   "17:00"): "Frauen",
        ("Kunstrasen vorne",  "Freitag",    "18:00"): "U11",
        ("Kunstrasen vorne",  "Mittwoch",   "18:30"): "U9",
        ("Kunstrasen hinten", "Mittwoch",   "18:30"): "Alte Herren",
        ("Kunstrasen hinten", "Donnerstag", "17:00"): "U13",
        ("Wigger-Arena",      "Dienstag",   "18:00"): "1. Mannschaft",
        ("Wigger-Arena",      "Donnerstag", "19:00"): "Frauen",
    }
    lines: list[str] = []

    def section(sub_plaetze: list[str]) -> None:
        lines.append(",".join(["Zeit"] + DAYS * len(sub_plaetze)))
        for h in range(16, 21):
            for m in (0, 30):
                slot = f"{h:02d}:{m:02d}"
                row = [slot]
                for sp in sub_plaetze:
                    for day in DAYS:
                        row.append(sample.get((sp, day, slot), ""))
                lines.append(",".join(row))

    section(["Rasen vorne", "Rasen hinten"])
    lines.append("")
    section(["Kunstrasen vorne", "Kunstrasen hinten"])
    lines.append("")
    section(["Wigger-Arena"])
    return "\n".join(lines)


def get_free_kabinen(datum: date, uhrzeit: str) -> list[str]:
    """
    Gibt Kabinen zurück, die zum Spieltermin NICHT durch Training belegt sind.
    Wochentag + Uhrzeit werden gegen die Saisonplanung geprüft.
    An Wochenenden (Sa/So) sind alle Kabinen frei.
    """
    day_name = DAYS[datum.weekday()]
    # Samstag/Sonntag: kein reguläres Training
    if day_name in ("Samstag", "Sonntag"):
        return LOCKER_ROOMS[:]
    conn = db_connect()
    rows = conn.execute(
        "SELECT DISTINCT kabine FROM saisonplanung "
        "WHERE tag=? AND zeit=? AND kabine != '' AND kabine IS NOT NULL",
        (day_name, uhrzeit),
    ).fetchall()
    conn.close()
    belegt = {r[0] for r in rows if r[0]}
    frei   = [k for k in LOCKER_ROOMS if k not in belegt]
    return frei if frei else LOCKER_ROOMS[:]  # Fallback: alle anzeigen wenn kein Plan hinterlegt


def find_conflicts(df_training: pd.DataFrame, datum: date, uhrzeit: str, platz: str) -> list[str]:
    """Gibt Teams zurück, die zum gleichen Zeitpunkt auf dem Platz (oder einer seiner Hälften) trainieren."""
    if df_training.empty:
        return []
    day_name   = DAYS[datum.weekday()]
    # Bei Gesamtplatz (Spielansetzung) beide Hälften prüfen
    check_plätze = PITCH_HALVES.get(platz, [platz])
    hit = df_training[
        (df_training["Platz"].isin(check_plätze)) &
        (df_training["Tag"]  == day_name) &
        (df_training["Zeit"] == uhrzeit)
    ]
    return hit["Team"].tolist()


# ---------------------------------------------------------------------------
# Hilfsfunktionen UI
# ---------------------------------------------------------------------------

def status_badge(status: str) -> str:
    meta = {
        "ausstehend":        ("#f0a500", "⏳", "Ausstehend"),
        "dfbnet_ausstehend": ("#7c3aed", "✅", "Genehmigt"),
        "abgeschlossen":     ("#22c55e", "✅", "Abgeschlossen"),
        "abgelehnt":         ("#ef4444", "❌", "Abgelehnt"),
        "genehmigt":         ("#22c55e", "✅", "Genehmigt"),
    }
    farbe, icon, label = meta.get(status, ("#888", "?", status.capitalize()))
    return (
        f'<span style="background:{farbe};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:11px;font-weight:bold;">{icon} {label}</span>'
    )


def typ_badge(typ: str) -> str:
    meta = {
        "neu":               ("#3b82f6", "🆕", "Neue Ansetzung"),
        "aenderung":         ("#f0a500", "✏️", "Änderung"),
        "verlegung":         ("#8b5cf6", "⏩", "Spielverlegung"),
        "uhrzeit_aenderung": ("#0ea5e9", "⏰", "Uhrzeitänderung"),
        "stornierung":       ("#ef4444", "❌", "Stornierung"),
        "allgemein":         ("#10b981", "💬", "Freie Anfrage"),
    }
    farbe, icon, label = meta.get(typ, ("#888", "?", typ))
    return (
        f'<span style="background:{farbe};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:11px;font-weight:bold;">{icon} {label}</span>'
    )


# ---------------------------------------------------------------------------
# Seiten – Gemeinsam
# ---------------------------------------------------------------------------

def page_trainingsplan_view() -> None:
    """Lese-Ansicht des Trainingsplans (für alle Rollen)."""
    st.markdown(
        '<div class="main-header"><h1>📋 Trainingsplan</h1>'
        '<p>Saisonbelegung aller Plätze – unveränderlich während der Saison</p></div>',
        unsafe_allow_html=True,
    )
    st.caption("Angezeigt werden bewusst nur Montag bis Freitag. Spielanfragen, Verlegungen und Stornierungen koennen weiterhin fuer jeden Kalendertag gestellt werden.")

    # Automatisch aus DB laden falls noch nichts im Session-State
    df_training = st.session_state.get("training_df", pd.DataFrame())
    if df_training.empty:
        _ty, _tm = date.today().year, date.today().month
        saison_key  = f"{_ty - 1}/{_ty}" if _tm < 7 else f"{_ty}/{_ty + 1}"
        df_training = load_training_df_from_db(
            st.session_state.get("aktuell_saison", saison_key)
        )
        if not df_training.empty:
            st.session_state.training_df = df_training

    if df_training.empty:
        if st.session_state.get("role") == "admin":
            st.info("Kein Trainingsplan geladen. Bitte unter **Saisonplanung** Trainingszeiten erfassen.")
        else:
            st.info("Kein Trainingsplan verfügbar. Bitte einen Administrator kontaktieren.")
        return

    c1, c2 = st.columns([1, 2])
    with c1:
        sel_day   = st.selectbox("Tag",   ["Alle"] + WEEKDAYS_DISPLAY)
    with c2:
        sel_pitch = st.selectbox("Platz", ["Alle"] + PITCHES)

    filtered = df_training.copy()
    if sel_day   != "Alle":
        filtered = filtered[filtered["Tag"]   == sel_day]
    if sel_pitch != "Alle":
        filtered = filtered[filtered["Platz"] == sel_pitch]

    if filtered.empty:
        st.info("Keine Trainingseinheiten für diese Auswahl.")
        return

    for platz in (PITCHES if sel_pitch == "Alle" else [sel_pitch]):
        p_data = filtered[filtered["Platz"] == platz]
        if p_data.empty:
            continue
        st.markdown(f"### 🏟️ {platz}")
        days_show = WEEKDAYS_DISPLAY if sel_day == "Alle" else [sel_day]
        cols = st.columns(len(days_show))
        for col, day in zip(cols, days_show):
            with col:
                st.markdown(
                    f'<div class="day-header" style="background:#6b0010;">'
                    f"{day[:2]}</div>",
                    unsafe_allow_html=True,
                )
                slots = p_data[p_data["Tag"] == day]
                if slots.empty:
                    st.markdown(
                        '<div class="slot-card slot-free">–</div>',
                        unsafe_allow_html=True,
                    )
                for _, row in slots.iterrows():
                    zeit_end = row.get("ZeitEnde", "")
                    zeit_label = (
                        f"{row['Zeit']}–{zeit_end}" if zeit_end else row["Zeit"]
                    )
                    st.markdown(
                        f'<div class="slot-card slot-training">'
                        f"⏱ {zeit_label}<br><small>{row['Team']}</small></div>",
                        unsafe_allow_html=True,
                    )
        st.divider()


# ---------------------------------------------------------------------------
# Seiten – Benutzer
# ---------------------------------------------------------------------------

def page_user_anfrage() -> None:
    my_team = st.session_state.get("team", "")
    st.markdown(
        '<div class="main-header"><h1>📨 Meine Anfragen</h1>'
        f'<p>Mannschaft: <strong>{my_team}</strong> · '
        'Neues Spiel anfragen &nbsp;·&nbsp; Spielverlegung &nbsp;·&nbsp; Uhrzeitänderung &nbsp;·&nbsp; Stornierung &nbsp;·&nbsp; Freie Anfrage an den Spielbetrieb</p></div>',
        unsafe_allow_html=True,
    )

    df_training = st.session_state.get("training_df", pd.DataFrame())
    alle_spiele  = get_all_matches()
    eigene = alle_spiele[alle_spiele["heimteam"] == my_team] \
             if (my_team and not alle_spiele.empty) else alle_spiele

    tab_neu, tab_verl, tab_uhr, tab_storni, tab_frei, tab_meine = st.tabs([
        "🆕 Neues Spiel",
        "⏩ Spielverlegung",
        "⏰ Uhrzeitänderung",
        "❌ Stornierung",
        "💬 Freie Anfrage",
        "📋 Meine Anfragen",
    ])

    # ── Tab: Neues Spiel ─────────────────────────────────────────────────────
    with tab_neu:
        st.subheader("Neue Spielanfrage")
        st.caption("Beantrage einen noch nicht angesetzten Spieltermin. Der Spielbetrieb prüft die Verfügbarkeit und trägt das Spiel nach Genehmigung ins DFBnet ein.")
        fc1, fc2 = st.columns(2)
        with fc1:
            f_datum   = st.date_input("Datum", value=date.today(), key="anf_datum")
        with fc2:
            f_uhrzeit = st.selectbox("Anstoßzeit", TIME_SLOTS_TRAINING, key="anf_uhrzeit")
        f_platz = st.selectbox("Platz", PITCHES_SPIEL, key="anf_platz")
        fc3, fc4 = st.columns(2)
        with fc3:
            f_heim = st.text_input(
                "Heimteam", value=my_team, disabled=bool(my_team),
                key="anf_heim",
                help="Wird automatisch aus deiner Mannschaft übernommen.",
            )
        with fc4:
            f_gast = st.text_input("Gastteam", placeholder="z. B. FC Muster", key="anf_gast")
        st.info("🚿 Kabinenzuweisung erfolgt durch den Admin nach der Genehmigung.")
        f_notizen = st.text_area("Notizen / Anmerkungen", key="anf_notizen")

        # ── Konflikt-Check (live, außerhalb des Formulars) ───────────────────
        conflicts = find_conflicts(df_training, f_datum, f_uhrzeit, f_platz)
        other_conflicts = [t for t in conflicts if t != my_team]
        if my_team and my_team in conflicts:
            st.info(
                f"ℹ️ **{my_team}** hat zu diesem Zeitpunkt selbst Training auf dem Platz."
            )
        konflikt_bestaetigt = True
        if other_conflicts:
            st.warning(
                f"⚠️ **{', '.join(other_conflicts)}** "
                f"{'trainiert' if len(other_conflicts) == 1 else 'trainieren'} "
                "zu diesem Zeitpunkt auf dem Platz. "
                "**Bitte stimme dich vorher mit den betroffenen Trainern ab.**"
            )
            konflikt_bestaetigt = st.checkbox(
                f"✅ Ich bestätige, dass ich mit allen betroffenen Trainern "
                f"({', '.join(other_conflicts)}) gesprochen habe und diese zugestimmt haben.",
                key="anf_konflikt_ok",
            )

        # ── Absenden ─────────────────────────────────────────────────────────
        if st.button("📨 Anfrage absenden", type="primary",
                     use_container_width=True, disabled=not konflikt_bestaetigt):
            heim_val = my_team or f_heim.strip()
            if not heim_val or not f_gast.strip():
                st.error("Bitte Heim- und Gastteam eintragen.")
            else:
                rid = create_spielanfrage(
                    f_datum, f_uhrzeit, f_platz, heim_val, f_gast.strip(),
                    kabine="", notizen=f_notizen, erstellt_von=my_team,
                )
                st.success(f"✅ Anfrage #{rid} eingereicht!")
                html = _mail_anfrage_html(
                    rid, f_datum, f_uhrzeit, f_platz, heim_val, f_gast.strip(),
                    "", f_notizen, other_conflicts, typ="Neue Spielanfrage",
                )
                ok, err = send_email(
                    f"[FCTM] Neue Spielanfrage #{rid}: {heim_val} vs {f_gast.strip()} "
                    f"({f_datum.strftime('%d.%m.%Y')})", html,
                )
                if ok:
                    st.info("📧 Benachrichtigung ans Funktionspostfach gesendet.")
                elif err != "E-Mail-Versand nicht aktiviert.":
                    st.warning(f"📧 {err}")

    # ── Tab: Spielverlegung ──────────────────────────────────────────────────
    with tab_verl:
        st.subheader("Spielverlegung beantragen")
        st.caption(
            "Beantrage einen neuen Termin für ein Spiel – egal ob es im System angelegt ist "
            "oder nur im DFBnet steht."
        )

        if not eigene.empty:
            verl_modus = st.radio(
                "Spiel auswählen",
                ["📋 Systemspiel auswählen", "✏️ DFBnet-Spiel manuell eingeben"],
                horizontal=True, key="verl_modus",
                help="'Systemspiel' wenn das Spiel hier bereits angelegt ist. "
                     "Für alle anderen DFBnet-Ansetzungen: 'Manuell eingeben'.",
            )
            aus_system_verl = verl_modus.startswith("📋")
        else:
            aus_system_verl = False

        if aus_system_verl:
            # ── Systemspiel ──────────────────────────────────────────────────────────────────
            verl_opts = {
                f"#{m['id']} – {m['heimteam']} vs {m['gastteam']} "
                f"({pd.to_datetime(m['datum']).strftime('%d.%m.%Y')} {m['uhrzeit']})": m["id"]
                for _, m in eigene.sort_values("datum").iterrows()
            }
            v_label = st.selectbox("Betroffenes Spiel", list(verl_opts.keys()), key="verl_spiel")
            v_id    = verl_opts[v_label]
            v_match = eigene[eigene["id"] == v_id].iloc[0]
            st.markdown(
                f'<div style="background:#f5f3ff;border-left:4px solid #8b5cf6;'
                f'border-radius:6px;padding:10px 14px;margin:8px 0;font-size:13px;">'
                f'<b>Aktueller Termin:</b> 📅 {pd.to_datetime(v_match["datum"]).strftime("%d.%m.%Y")}'
                f' &nbsp;| &nbsp; ⏰ {v_match["uhrzeit"]} &nbsp;| &nbsp; 🏟️ {v_match["platz"]}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("**Gewünschter neuer Termin:**")
            vc1, vc2 = st.columns(2)
            with vc1:
                v_datum = st.date_input("Neues Datum *", value=date.fromisoformat(v_match["datum"]), key="verl_datum")
            with vc2:
                cur_idx_v = TIME_SLOTS_TRAINING.index(v_match["uhrzeit"]) if v_match["uhrzeit"] in TIME_SLOTS_TRAINING else 0
                v_uhrzeit = st.selectbox("Neue Anstoßzeit", TIME_SLOTS_TRAINING, index=cur_idx_v, key="verl_uhrzeit")
            cur_platz_idx_v = PITCHES_SPIEL.index(v_match["platz"]) if v_match["platz"] in PITCHES_SPIEL else 0
            v_platz = st.selectbox("Neuer Platz", PITCHES_SPIEL, index=cur_platz_idx_v, key="verl_platz")
            st.info("🚿 Kabinenzuweisung erfolgt durch den Admin nach der Genehmigung.")
            v_notizen = st.text_area("Begründung (Pflicht) *", key="verl_notizen",
                                     placeholder="z. B. Platzverfügbarkeit, Absprache mit Gegner …")
            if st.button("⏩ Verlegung beantragen", type="primary", use_container_width=True, key="verl_btn"):
                if not v_notizen.strip():
                    st.error("Bitte eine Begründung angeben.")
                elif v_datum == date.fromisoformat(v_match["datum"]) and v_uhrzeit == v_match["uhrzeit"] and v_platz == v_match["platz"]:
                    st.warning("Keine Änderung erkannt – bitte neues Datum, Uhrzeit oder Platz wählen.")
                else:
                    rid = create_anfrage_verlegung(v_id, v_datum, v_uhrzeit, v_platz, v_notizen.strip(), erstellt_von=my_team)
                    st.success(f"✅ Verlegungsantrag #{rid} eingereicht!")
                    ok, err = send_email(
                        f"[FCTM] ⏩ Spielverlegung #{rid}: {v_match['heimteam']} vs {v_match['gastteam']} → {v_datum.strftime('%d.%m.%Y')} {v_uhrzeit}",
                        _mail_anfrage_html(rid, date.fromisoformat(v_match["datum"]), v_match["uhrzeit"], v_match["platz"],
                                           v_match["heimteam"], v_match["gastteam"], "", v_notizen, [],
                                           typ=f"Spielverlegung → {v_datum.strftime('%d.%m.%Y')} {v_uhrzeit} · {v_platz}"),
                    )
                    if ok: st.info("📧 Benachrichtigung ans Funktionspostfach gesendet.")
                    elif err != "E-Mail-Versand nicht aktiviert.": st.warning(f"📧 {err}")
        else:
            # ── DFBnet-Spiel manuell ─────────────────────────────────────────────────────────────
            st.markdown(
                '<div style="background:#f5f3ff;border-left:4px solid #8b5cf6;border-radius:6px;'
                'padding:10px 14px;margin-bottom:10px;font-size:13px;">'
                '✏️ Trage die aktuellen Spieldaten aus dem DFBnet ein und gib den gewünschten neuen Termin an.</div>',
                unsafe_allow_html=True,
            )
            st.markdown("**Aktueller Termin (laut DFBnet):**")
            vd1, vd2 = st.columns(2)
            with vd1:
                vd_gast   = st.text_input("Gastteam *", placeholder="z. B. FC Muster", key="verl_d_gast")
                vd_datum  = st.date_input("Aktuelles Datum *", value=date.today(), key="verl_d_datum")
            with vd2:
                vd_uhrzeit = st.selectbox("Aktuelle Anstoßzeit", TIME_SLOTS_TRAINING, key="verl_d_uhrzeit")
                vd_platz   = st.selectbox("Aktueller Platz", PITCHES_SPIEL, key="verl_d_platz")
            st.divider()
            st.markdown("**Gewünschter neuer Termin:**")
            vn1, vn2 = st.columns(2)
            with vn1:
                vd_n_datum   = st.date_input("Neues Datum *", value=date.today() + timedelta(days=7), key="verl_nd_datum")
            with vn2:
                vd_n_uhrzeit = st.selectbox("Neue Anstoßzeit", TIME_SLOTS_TRAINING, key="verl_nd_uhrzeit")
            vd_n_platz = st.selectbox("Neuer Platz", PITCHES_SPIEL, key="verl_nd_platz")
            st.info("🚿 Kabinenzuweisung erfolgt durch den Admin nach der Genehmigung.")
            vd_notizen = st.text_area("Begründung (Pflicht) *", key="verl_d_notizen",
                                      placeholder="z. B. Platzverfügbarkeit, Absprache mit Gegner …")
            if st.button("⏩ Verlegung beantragen", type="primary", use_container_width=True, key="verl_d_btn"):
                if not vd_gast.strip():
                    st.error("Bitte den Gastverein eintragen.")
                elif not vd_notizen.strip():
                    st.error("Bitte eine Begründung angeben.")
                elif vd_datum == vd_n_datum and vd_uhrzeit == vd_n_uhrzeit and vd_platz == vd_n_platz:
                    st.warning("Keine Änderung erkannt – bitte neuen Termin wählen.")
                else:
                    heim_val = my_team or "Unbekannt"
                    rid = create_anfrage_verlegung_direkt(
                        vd_datum, vd_uhrzeit, vd_platz, heim_val, vd_gast.strip(),
                        vd_n_datum, vd_n_uhrzeit, vd_n_platz, vd_notizen.strip(), erstellt_von=my_team,
                    )
                    st.success(f"✅ Verlegungsantrag #{rid} eingereicht!")
                    ok, err = send_email(
                        f"[FCTM] ⏩ Spielverlegung #{rid}: {heim_val} vs {vd_gast.strip()} → {vd_n_datum.strftime('%d.%m.%Y')} {vd_n_uhrzeit}",
                        _mail_anfrage_html(rid, vd_datum, vd_uhrzeit, vd_platz, heim_val, vd_gast.strip(), "", vd_notizen, [],
                                           typ=f"Spielverlegung → {vd_n_datum.strftime('%d.%m.%Y')} {vd_n_uhrzeit} · {vd_n_platz}"),
                    )
                    if ok: st.info("📧 Benachrichtigung ans Funktionspostfach gesendet.")
                    elif err != "E-Mail-Versand nicht aktiviert.": st.warning(f"📧 {err}")

    # ── Tab: Uhrzeitänderung ─────────────────────────────────────────────────
    with tab_uhr:
        st.subheader("Anstoßzeit ändern")
        st.caption(
            "Beantrage ausschließlich eine andere Anstoßzeit – Datum und Platz bleiben unverändert. "
            "Gilt für Systemspiele und DFBnet-Ansetzungen."
        )

        if not eigene.empty:
            uhr_modus = st.radio(
                "Spiel auswählen",
                ["📋 Systemspiel auswählen", "✏️ DFBnet-Spiel manuell eingeben"],
                horizontal=True, key="uhr_modus",
                help="'Systemspiel' wenn das Spiel hier bereits angelegt ist. "
                     "Für alle anderen DFBnet-Ansetzungen: 'Manuell eingeben'.",
            )
            aus_system_uhr = uhr_modus.startswith("📋")
        else:
            aus_system_uhr = False

        if aus_system_uhr:
            uhr_opts = {
                f"#{m['id']} – {m['heimteam']} vs {m['gastteam']} "
                f"({pd.to_datetime(m['datum']).strftime('%d.%m.%Y')} {m['uhrzeit']})": m["id"]
                for _, m in eigene.sort_values("datum").iterrows()
            }
            u_label = st.selectbox("Betroffenes Spiel", list(uhr_opts.keys()), key="uhr_spiel")
            u_id    = uhr_opts[u_label]
            u_match = eigene[eigene["id"] == u_id].iloc[0]
            st.markdown(
                f'<div style="background:#f0f9ff;border-left:4px solid #0ea5e9;'
                f'border-radius:6px;padding:10px 14px;margin:8px 0;font-size:13px;">'
                f'<b>Aktueller Termin:</b> 📅 {pd.to_datetime(u_match["datum"]).strftime("%d.%m.%Y")}'
                f' &nbsp;|\u200a&nbsp; ⏰ <b>{u_match["uhrzeit"]}</b> &nbsp;|\u200a&nbsp; 🏟️ {u_match["platz"]}</div>',
                unsafe_allow_html=True,
            )
            cur_idx_u = TIME_SLOTS_TRAINING.index(u_match["uhrzeit"]) if u_match["uhrzeit"] in TIME_SLOTS_TRAINING else 0
            u_neue_uhrzeit = st.selectbox("⏰ Neue Anstoßzeit *", TIME_SLOTS_TRAINING, index=cur_idx_u, key="uhr_neue_uhrzeit")
            u_notizen = st.text_area("Begründung (Pflicht) *", key="uhr_notizen",
                                     placeholder="z. B. Absprache mit Gastverein, Schiedsrichtertermin …")
            if st.button("⏰ Uhrzeitänderung beantragen", type="primary", use_container_width=True, key="uhr_btn"):
                if not u_notizen.strip():
                    st.error("Bitte eine Begründung angeben.")
                elif u_neue_uhrzeit == u_match["uhrzeit"]:
                    st.warning("Die gewählte Uhrzeit ist identisch mit der aktuellen Anstoßzeit.")
                else:
                    rid = create_anfrage_uhrzeit_aenderung(u_id, u_neue_uhrzeit, u_notizen.strip(), erstellt_von=my_team)
                    st.success(f"✅ Uhrzeitänderung #{rid} eingereicht!")
                    ok, err = send_email(
                        f"[FCTM] ⏰ Uhrzeitänderung #{rid}: {u_match['heimteam']} vs {u_match['gastteam']} – {u_match['uhrzeit']} → {u_neue_uhrzeit}",
                        _mail_anfrage_html(rid, date.fromisoformat(u_match["datum"]), u_match["uhrzeit"], u_match["platz"],
                                           u_match["heimteam"], u_match["gastteam"], "", u_notizen, [],
                                           typ=f"Uhrzeitänderung: {u_match['uhrzeit']} → {u_neue_uhrzeit}"),
                    )
                    if ok: st.info("📧 Benachrichtigung ans Funktionspostfach gesendet.")
                    elif err != "E-Mail-Versand nicht aktiviert.": st.warning(f"📧 {err}")
        else:
            st.markdown(
                '<div style="background:#f0f9ff;border-left:4px solid #0ea5e9;border-radius:6px;'
                'padding:10px 14px;margin-bottom:10px;font-size:13px;">'
                '✏️ Trage die aktuellen Spieldaten aus dem DFBnet ein und gib die gewünschte neue Anstoßzeit an.</div>',
                unsafe_allow_html=True,
            )
            ud1, ud2 = st.columns(2)
            with ud1:
                ud_gast    = st.text_input("Gastteam *", placeholder="z. B. FC Muster", key="uhr_d_gast")
                ud_datum   = st.date_input("Datum des Spiels *", value=date.today(), key="uhr_d_datum")
            with ud2:
                ud_uhrzeit = st.selectbox("Aktuelle Anstoßzeit", TIME_SLOTS_TRAINING, key="uhr_d_uhrzeit")
                ud_platz   = st.selectbox("Platz", PITCHES_SPIEL, key="uhr_d_platz")
            ud_neue_uhrzeit = st.selectbox("⏰ Neue Anstoßzeit *", TIME_SLOTS_TRAINING, key="uhr_d_neue_uhrzeit")
            ud_notizen = st.text_area("Begründung (Pflicht) *", key="uhr_d_notizen",
                                      placeholder="z. B. Absprache mit Gastverein, Schiedsrichtertermin …")
            if st.button("⏰ Uhrzeitänderung beantragen", type="primary", use_container_width=True, key="uhr_d_btn"):
                if not ud_gast.strip():
                    st.error("Bitte den Gastverein eintragen.")
                elif not ud_notizen.strip():
                    st.error("Bitte eine Begründung angeben.")
                elif ud_neue_uhrzeit == ud_uhrzeit:
                    st.warning("Die gewählte Uhrzeit ist identisch mit der aktuellen Anstoßzeit.")
                else:
                    heim_val = my_team or "Unbekannt"
                    rid = create_anfrage_uhrzeit_aenderung_direkt(
                        ud_datum, ud_uhrzeit, ud_platz, heim_val, ud_gast.strip(),
                        ud_neue_uhrzeit, ud_notizen.strip(), erstellt_von=my_team,
                    )
                    st.success(f"✅ Uhrzeitänderung #{rid} eingereicht!")
                    ok, err = send_email(
                        f"[FCTM] ⏰ Uhrzeitänderung #{rid}: {heim_val} vs {ud_gast.strip()} – {ud_uhrzeit} → {ud_neue_uhrzeit}",
                        _mail_anfrage_html(rid, ud_datum, ud_uhrzeit, ud_platz, heim_val, ud_gast.strip(), "", ud_notizen, [],
                                           typ=f"Uhrzeitänderung: {ud_uhrzeit} → {ud_neue_uhrzeit}"),
                    )
                    if ok: st.info("📧 Benachrichtigung ans Funktionspostfach gesendet.")
                    elif err != "E-Mail-Versand nicht aktiviert.": st.warning(f"📧 {err}")

    # ── Tab: Stornierung ─────────────────────────────────────────────────────
    with tab_storni:
        st.subheader("Spielstornierung beantragen")
        st.caption(
            "Beantrage die Absage eines Spiels. Gilt für Systemspiele und für DFBnet-Ansetzungen, "
            "die nicht im System erfasst sind."
        )

        if not eigene.empty:
            storni_modus = st.radio(
                "Spiel auswählen",
                ["📋 Systemspiel auswählen", "✏️ DFBnet-Spiel manuell eingeben"],
                horizontal=True, key="storni_modus",
                help="'Systemspiel' wenn das Spiel hier bereits angelegt ist. "
                     "Für alle anderen DFBnet-Ansetzungen: 'Manuell eingeben'.",
            )
            aus_system_storni = storni_modus.startswith("📋")
        else:
            aus_system_storni = False

        if aus_system_storni:
            storni_opts = {
                f"#{m['id']} – {m['heimteam']} vs {m['gastteam']} "
                f"({pd.to_datetime(m['datum']).strftime('%d.%m.%Y')} {m['uhrzeit']})": m["id"]
                for _, m in eigene.sort_values("datum").iterrows()
            }
            with st.form("storni_form"):
                s_label = st.selectbox("Zu stornierendes Spiel", list(storni_opts.keys()))
                s_id    = storni_opts[s_label]
                s_match = eigene[eigene["id"] == s_id].iloc[0]
                st.markdown(
                    f'<div style="background:#fff5f5;border-left:4px solid #ef4444;'
                    f'border-radius:6px;padding:10px 14px;margin:8px 0;font-size:13px;">'
                    f'<b>Spiel:</b> {s_match["heimteam"]} vs {s_match["gastteam"]} &nbsp;|\u200a&nbsp; '
                    f'📅 {s_match["datum"]} &nbsp;|\u200a&nbsp; ⏰ {s_match["uhrzeit"]} &nbsp;|\u200a&nbsp; '
                    f'🏟️ {s_match["platz"]}</div>',
                    unsafe_allow_html=True,
                )
                s_notizen = st.text_area("Begründung (Pflicht) *",
                                         placeholder="z. B. Platzsperre, Terminkollision, Absage des Gegners …")
                if st.form_submit_button("❌ Stornierung beantragen", type="secondary", use_container_width=True):
                    if not s_notizen.strip():
                        st.error("Bitte eine Begründung angeben.")
                    else:
                        rid = create_anfrage_stornierung(s_id, s_notizen, erstellt_von=my_team)
                        st.success(f"✅ Stornierungsantrag #{rid} eingereicht!")
                        ok, err = send_email(
                            f"[FCTM] ❌ Stornierungsantrag #{rid}: {s_match['heimteam']} vs {s_match['gastteam']} ({s_match['datum']})",
                            _mail_anfrage_html(rid, date.fromisoformat(s_match["datum"]), s_match["uhrzeit"], s_match["platz"],
                                               s_match["heimteam"], s_match["gastteam"], "", s_notizen, [], typ="Stornierungsantrag"),
                        )
                        if ok: st.info("📧 Benachrichtigung ans Funktionspostfach gesendet.")
                        elif err != "E-Mail-Versand nicht aktiviert.": st.warning(f"📧 {err}")
        else:
            st.markdown(
                '<div style="background:#fff5f5;border-left:4px solid #ef4444;border-radius:6px;'
                'padding:10px 14px;margin-bottom:10px;font-size:13px;">'
                '✏️ Trage die Spieldaten aus dem DFBnet ein, das du stornieren möchtest.</div>',
                unsafe_allow_html=True,
            )
            sd1, sd2 = st.columns(2)
            with sd1:
                sd_gast    = st.text_input("Gastteam *", placeholder="z. B. FC Muster", key="storni_d_gast")
                sd_datum   = st.date_input("Datum des Spiels *", value=date.today(), key="storni_d_datum")
            with sd2:
                sd_uhrzeit = st.selectbox("Anstoßzeit", TIME_SLOTS_TRAINING, key="storni_d_uhrzeit")
                sd_platz   = st.selectbox("Platz", PITCHES_SPIEL, key="storni_d_platz")
            sd_notizen = st.text_area("Begründung (Pflicht) *", key="storni_d_notizen",
                                      placeholder="z. B. Platzsperre, Terminkollision, Absage des Gegners …")
            if st.button("❌ Stornierung beantragen", type="secondary", use_container_width=True, key="storni_d_btn"):
                if not sd_gast.strip():
                    st.error("Bitte den Gastverein eintragen.")
                elif not sd_notizen.strip():
                    st.error("Bitte eine Begründung angeben.")
                else:
                    heim_val = my_team or "Unbekannt"
                    rid = create_anfrage_stornierung_direkt(
                        sd_datum, sd_uhrzeit, sd_platz, heim_val, sd_gast.strip(),
                        sd_notizen.strip(), erstellt_von=my_team,
                    )
                    st.success(f"✅ Stornierungsantrag #{rid} eingereicht!")
                    ok, err = send_email(
                        f"[FCTM] ❌ Stornierungsantrag #{rid}: {heim_val} vs {sd_gast.strip()} ({sd_datum.strftime('%d.%m.%Y')})",
                        _mail_anfrage_html(rid, sd_datum, sd_uhrzeit, sd_platz, heim_val, sd_gast.strip(), "", sd_notizen, [], typ="Stornierungsantrag"),
                    )
                    if ok: st.info("📧 Benachrichtigung ans Funktionspostfach gesendet.")
                    elif err != "E-Mail-Versand nicht aktiviert.": st.warning(f"📧 {err}")

    # ── Tab: Freie Anfrage ───────────────────────────────────────────────────
    with tab_frei:
        st.subheader("Freie Anfrage an den Spielbetrieb")
        st.caption(
            "Hast du eine Frage, einen Hinweis oder ein Anliegen, das nicht in die anderen "
            "Kategorien passt? Schreib hier direkt an den Spielbetrieb."
        )
        st.markdown(
            '<div style="background:#f0fdf4;border-left:4px solid #10b981;'
            'border-radius:6px;padding:10px 14px;margin-bottom:14px;font-size:13px;">'
            '💬 Diese Anfrage wird direkt ans Funktionspostfach des Spielbetriebs gesendet '
            'und in deiner Anfrageübersicht gespeichert.</div>',
            unsafe_allow_html=True,
        )
        f_betreff   = st.text_input(
            "Betreff *", placeholder="z. B. Frage zur Schiedsrichter-Ansetzung",
            key="frei_betreff",
        )
        f_nachricht = st.text_area(
            "Nachricht *", height=160,
            placeholder="Beschreibe dein Anliegen so genau wie möglich …",
            key="frei_nachricht",
        )
        if st.button("💬 Anfrage senden", type="primary",
                     use_container_width=True, key="frei_btn"):
            if not f_betreff.strip():
                st.error("Bitte einen Betreff angeben.")
            elif not f_nachricht.strip():
                st.error("Bitte eine Nachricht eingeben.")
            else:
                rid = create_anfrage_allgemein(
                    f_betreff.strip(), f_nachricht.strip(), erstellt_von=my_team,
                )
                st.success(f"✅ Anfrage #{rid} wurde an den Spielbetrieb gesendet!")
                mail_html = f"""
                <html><body style='font-family:Arial,sans-serif;'>
                <div style='background:#f0fdf4;border-top:5px solid #10b981;padding:24px 30px;'>
                <h2 style='color:#065f46;'>💬 Freie Anfrage #{rid}</h2>
                <table style='font-size:14px;color:#1a1a1a;'>
                <tr><td style='padding:4px 12px 4px 0;color:#6b7280;'>Von:</td>
                    <td><b>{my_team}</b></td></tr>
                <tr><td style='padding:4px 12px 4px 0;color:#6b7280;'>Betreff:</td>
                    <td><b>{f_betreff.strip()}</b></td></tr>
                </table>
                <hr style='border:none;border-top:1px solid #d1fae5;margin:14px 0;'/>
                <p style='white-space:pre-wrap;font-size:14px;'>{f_nachricht.strip()}</p>
                </div></body></html>
                """
                ok, err = send_email(
                    f"[FCTM] 💬 Freie Anfrage #{rid} von {my_team}: {f_betreff.strip()}",
                    mail_html,
                )
                if ok:
                    st.info("📧 Benachrichtigung ans Funktionspostfach gesendet.")
                elif err != "E-Mail-Versand nicht aktiviert.":
                    st.warning(f"📧 {err}")

    # ── Tab: Meine Anfragen ──────────────────────────────────────────────────
    with tab_meine:
        alle_anf = get_all_anfragen()
        if alle_anf.empty:
            meine_anf = alle_anf
        elif my_team and "erstellt_von" in alle_anf.columns:
            meine_anf = alle_anf[alle_anf["erstellt_von"] == my_team]
        elif my_team:
            meine_anf = alle_anf[alle_anf["heimteam"] == my_team]
        else:
            meine_anf = alle_anf

        if meine_anf.empty:
            st.info("Noch keine Anfragen vorhanden.")
        else:
            for _, r in meine_anf.sort_values("erstellt_am", ascending=False).iterrows():
                t = r.get("anfrage_typ") or "neu"
                is_allgemein = (t == "allgemein")
                kabine_info = (
                    f' &nbsp;|&nbsp; 🚿 {r["kabine"]}' if r.get("kabine") else
                    ' &nbsp;|&nbsp; <em style="color:#888;">Kabine: wird vom Admin vergeben</em>'
                )
                if is_allgemein:
                    titel  = r.get("betreff") or r.get("notizen") or "Freie Anfrage"
                    excerpt = (r.get("nachricht") or r.get("notizen") or "")[:100]
                    detail = (
                        f'<div style="color:#555;font-size:12px;margin-top:6px;">'
                        f'💬 {excerpt}{"…" if len(excerpt) == 100 else ""}</div>'
                    )
                else:
                    titel = f'⚽ {r["heimteam"]} vs {r["gastteam"]}'
                    change_hint = ""
                    if t in ("aenderung", "verlegung") and r.get("neues_datum"):
                        change_hint = (
                            f' <span style="color:#8b5cf6;font-weight:bold;">→ '
                            f'{r["neues_datum"]} {r.get("neue_uhrzeit","")}</span>'
                        )
                    elif t == "uhrzeit_aenderung" and r.get("neue_uhrzeit"):
                        change_hint = (
                            f' <span style="color:#0ea5e9;font-weight:bold;">→ '
                            f'{r.get("neue_uhrzeit","")}</span>'
                        )
                    detail = (
                        f'<div style="color:#888;font-size:12px;margin-top:6px;">'
                        f'📅 {r["datum"]} &nbsp;|&nbsp; ⏰ {r["uhrzeit"]}'
                        f'{change_hint}'
                        f' &nbsp;|&nbsp; 🏟️ {r["platz"]}'
                        f'{kabine_info}</div>'
                    )
                timeline_html = _anfrage_timeline_html(t, r.get("status", "ausstehend"))
                st.markdown(
                    f'<div class="anfrage-card">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="color:#1a1a1a;font-weight:bold;">{titel}</span>'
                    f'<span>{typ_badge(t)}&nbsp;{status_badge(r["status"])}</span></div>'
                    + detail
                    + timeline_html
                    + (
                        f'<div style="background:#fee2e2;border-left:3px solid #ef4444;'
                        f'padding:6px 10px;border-radius:4px;margin-top:6px;font-size:12px;color:#7f1d1d;">'
                        f'<b>Ablehnungsgrund:</b> {r["bearbeiter_kommentar"]}</div>'
                        if r.get("bearbeiter_kommentar") and r["status"] == "abgelehnt"
                        else (
                            f'<div style="background:#f0fdf4;border-left:3px solid #10b981;'
                            f'padding:6px 10px;border-radius:4px;margin-top:6px;font-size:12px;color:#065f46;">'
                            f'<b>Antwort:</b> {r["bearbeiter_kommentar"]}</div>'
                            if r.get("bearbeiter_kommentar") and r["status"] == "abgeschlossen"
                            else ""
                        )
                    )
                    + f'</div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Seiten – Admin
# ---------------------------------------------------------------------------

def page_admin_dashboard() -> None:
    st.markdown(
        '<div class="main-header"><h1>📅 Admin Dashboard</h1>'
        '<p>Vollständige Wochenübersicht – Training, Spiele &amp; Sperren</p></div>',
        unsafe_allow_html=True,
    )

    # ── Verwalter-Notizen ─────────────────────────────────────────────────────
    notizen_val = get_setting("verwalter_notizen") or ""
    with st.expander("📝 Verwalter-Notizen" + (" ✏️" if notizen_val else " (leer)"), expanded=bool(notizen_val)):
        st.caption("Gemeinsamer Notizblock für alle Verwalter und Administratoren (z. B. Vertretungshinweise, laufende Aufgaben).")
        neue_notizen = st.text_area(
            "Notizen",
            value=notizen_val,
            height=130,
            label_visibility="collapsed",
            key="verwalter_notizen_input",
            placeholder="Hier können Verwalter Hinweise für Vertretungen hinterlassen …",
        )
        if st.button("💾 Notizen speichern", key="btn_notizen_save"):
            set_setting("verwalter_notizen", neue_notizen.strip())
            st.success("✅ Notizen gespeichert.")
            st.rerun()

    # ── Aktions-Karten (offene Posten) ────────────────────────────────────────
    alle_anf = get_all_anfragen()
    n_neu  = len(alle_anf[alle_anf["status"] == "ausstehend"])       if not alle_anf.empty else 0
    n_dfb  = len(alle_anf[alle_anf["status"] == "dfbnet_ausstehend"]) if not alle_anf.empty else 0

    # Aufschlüsselung für die Karte: wie viele davon sind freie Anfragen?
    if not alle_anf.empty and n_neu > 0:
        _offen       = alle_anf[alle_anf["status"] == "ausstehend"]
        n_neu_frei   = len(_offen[_offen["anfrage_typ"] == "allgemein"]) \
                       if "anfrage_typ" in _offen.columns else 0
        n_neu_spiele = n_neu - n_neu_frei
    else:
        n_neu_frei = n_neu_spiele = 0

    if n_neu > 0 or n_dfb > 0:
        karten_html = '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px;">'
        if n_neu_spiele > 0:
            karten_html += (
                f'<div style="flex:1;min-width:200px;background:#fff3eb;border-left:5px solid #c00000;'
                f'border-radius:8px;padding:14px 18px;border:1px solid #fddcb5;">'
                f'<div style="font-size:22px;font-weight:bold;color:#c00000;">{n_neu_spiele}</div>'
                f'<div style="color:#7c2d12;font-size:14px;">⏳ Spielanfrage{"n" if n_neu_spiele > 1 else ""} warten auf Bearbeitung</div>'
                f'</div>'
            )
        if n_neu_frei > 0:
            karten_html += (
                f'<div style="flex:1;min-width:200px;background:#f0fdf4;border-left:5px solid #10b981;'
                f'border-radius:8px;padding:14px 18px;border:1px solid #bbf7d0;">'
                f'<div style="font-size:22px;font-weight:bold;color:#065f46;">{n_neu_frei}</div>'
                f'<div style="color:#065f46;font-size:14px;">💬 Freie Anfrage{"n" if n_neu_frei > 1 else ""} warten auf Antwort</div>'
                f'</div>'
            )
        if n_dfb > 0:
            karten_html += (
                f'<div style="flex:1;min-width:200px;background:#ebf0ff;border-left:5px solid #4f6ef7;'
                f'border-radius:8px;padding:14px 18px;border:1px solid #c7d2fe;">'
                f'<div style="font-size:22px;font-weight:bold;color:#312e81;">{n_dfb}</div>'
                f'<div style="color:#3730a3;font-size:14px;">📋 Spiel{"e" if n_dfb > 1 else ""} noch nicht ins DFBnet eingetragen</div>'
                f'</div>'
            )
        karten_html += '</div>'
        st.markdown(karten_html, unsafe_allow_html=True)

        # Letzte ausstehende Anfragen kurz auflisten
        if n_neu > 0:
            with st.expander(f"⏳ Ausstehende Anfragen anzeigen ({n_neu})", expanded=True):
                offene = alle_anf[alle_anf["status"] == "ausstehend"].sort_values("erstellt_am", ascending=False).head(5)
                for _, r in offene.iterrows():
                    t_anf   = r.get("anfrage_typ") or "neu"
                    tb      = typ_badge(t_anf)
                    if t_anf == "allgemein":
                        titel_str = (r.get("betreff") or r.get("notizen") or "Freie Anfrage")[:55]
                        meta_str  = f'💬 von {r.get("erstellt_von","?")}' if r.get("erstellt_von") else "💬 Freie Anfrage"
                    else:
                        datum_str = pd.to_datetime(r["datum"]).strftime("%d.%m.%Y") if r.get("datum") else "–"
                        titel_str = f'{r["heimteam"]} vs {r["gastteam"]}'
                        meta_str  = f'📅 {datum_str} · {r["uhrzeit"]} · {r["platz"]}'
                    st.markdown(
                        f'<div style="background:#f8f8f8;border-radius:6px;padding:10px 14px;'
                        f'margin-bottom:6px;border-left:3px solid #c00000;'
                        f'display:flex;align-items:center;gap:8px;">'
                        f'{tb} &nbsp;'
                        f'<span><b style="color:#1a1a1a;">#{r["id"]} – {titel_str}</b>'
                        f'<span style="color:#666;font-size:12px;margin-left:10px;">{meta_str}</span>'
                        f'</span></div>',
                        unsafe_allow_html=True,
                    )
                if n_neu > 5:
                    st.caption(f"… und {n_neu - 5} weitere. Alle unter **📨 Anfragen verwalten**.")
    else:
        st.success("✅ Keine offenen Anfragen – alles erledigt.")

    st.divider()

    c1, c2, _ = st.columns([1, 1, 2])
    with c1:
        sel_date  = st.date_input("Woche ab", value=date.today())
    with c2:
        sel_pitch = st.selectbox("Platz", ["Alle"] + PITCHES)

    week_start  = sel_date - timedelta(days=sel_date.weekday())
    week_dates  = [week_start + timedelta(days=i) for i in range(5)]
    df_training = st.session_state.get("training_df", pd.DataFrame())
    show_pitches = PITCHES if sel_pitch == "Alle" else [sel_pitch]
    st.caption("Die Wochenansicht zeigt bewusst nur Montag bis Freitag. Wochenendspiele koennen weiterhin beantragt und verarbeitet werden, ohne dass ein kompletter Spielplan manuell gepflegt werden muss.")

    # Legende
    st.markdown(
        '<div style="margin:8px 0 18px 0;">'
        '<span style="background:#c00000;color:#fff;padding:3px 12px;'
        'border-radius:20px;font-size:12px;margin-right:6px;">● Training</span>'
        '<span style="background:#d08000;color:#fff;padding:3px 12px;'
        'border-radius:20px;font-size:12px;margin-right:6px;">● Spiel</span>'
        '<span style="background:#c00000;color:#fff;padding:3px 12px;'
        'border-radius:20px;font-size:12px;margin-right:6px;">● Gesperrt</span>'
        '<span style="background:#f5f5f5;color:#999;padding:3px 12px;'
        'border-radius:20px;font-size:12px;border:1px solid #dddddd;">● Frei</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    for platz in show_pitches:
        st.markdown(f"### 🏟️ {platz}")
        day_cols = st.columns(5)
        for i, (col, cur_date) in enumerate(zip(day_cols, week_dates)):
            day_name   = WEEKDAYS_DISPLAY[i]
            is_locked  = platz in get_locked_pitches(cur_date)
            is_today   = cur_date == date.today()
            with col:
                hdr_bg = "#c00000" if is_today else "#999999"
                st.markdown(
                    f'<div class="day-header" style="background:{hdr_bg};">'
                    f"{day_name[:2]}<br>"
                    f'<span style="font-size:14px;">{cur_date.strftime("%d.%m")}</span>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                if is_locked:
                    st.markdown(
                        '<div class="slot-card slot-locked">🚫 GESPERRT</div>',
                        unsafe_allow_html=True,
                    )
                    continue

                matches_day = get_matches_for_date(cur_date)
                m_pitch = (
                    matches_day[matches_day["platz"] == platz]
                    if not matches_day.empty else pd.DataFrame()
                )
                t_day = (
                    df_training[
                        (df_training["Platz"] == platz) &
                        (df_training["Tag"]   == day_name)
                    ]
                    if not df_training.empty else pd.DataFrame()
                )

                blocks: list[str] = []
                for _, entry in t_day.iterrows():
                    conflict = (
                        not m_pitch.empty and
                        entry["Zeit"] in m_pitch["uhrzeit"].values
                    )
                    css  = "slot-match" if conflict else "slot-training"
                    icon = "⚽" if conflict else "🏃"
                    blocks.append(
                        f'<div class="slot-card {css}">'
                        f"{icon} {entry['Zeit']}<br>"
                        f"<small>{entry['Team']}</small></div>"
                    )
                for _, m in m_pitch.iterrows():
                    if t_day.empty or m["uhrzeit"] not in t_day["Zeit"].values:
                        blocks.append(
                            '<div class="slot-card slot-match">'
                            f"⚽ {m['uhrzeit']}<br>"
                            f"<small>{m['heimteam']} vs {m['gastteam']}</small></div>"
                        )
                if blocks:
                    st.markdown("".join(blocks), unsafe_allow_html=True)
                else:
                    st.markdown(
                        '<div class="slot-card slot-free">–</div>',
                        unsafe_allow_html=True,
                    )
        st.divider()


def _anfrage_card_html(r: pd.Series) -> str:
    """Kleine Karte für abgeschlossene/abgelehnte Anfragen."""
    badge   = status_badge(r["status"])
    t_badge = typ_badge(r.get("anfrage_typ") or "neu")
    bear    = f' &nbsp;|&nbsp; 👤 {r["bearbeiter"]}' if r.get("bearbeiter") else ""
    t_typ   = r.get("anfrage_typ") or "neu"

    if t_typ == "allgemein":
        betreff_txt = r.get("betreff") or r.get("notizen") or "Freie Anfrage"
        von_txt     = f' &nbsp;|&nbsp; ✉️ {r["erstellt_von"]}' if r.get("erstellt_von") else ""
        return (
            f'<div class="anfrage-card">'
            f'<div style="display:flex;justify-content:space-between;">'
            f'<span style="color:#1a1a1a;font-weight:600;">#{r["id"]} – {betreff_txt}</span>'
            f'<span>{t_badge}&nbsp;{badge}</span></div>'
            f'<div style="color:#aaa;font-size:12px;margin-top:5px;">'
            f'💬 Freie Anfrage{von_txt}{bear}</div></div>'
        )

    change_hint = ""
    if t_typ in ("aenderung", "verlegung") and r.get("neues_datum"):
        change_hint = f' &nbsp;→&nbsp; {r["neues_datum"]} {r.get("neue_uhrzeit","")}'
    elif t_typ == "uhrzeit_aenderung" and r.get("neue_uhrzeit"):
        change_hint = f' &nbsp;→&nbsp; ⏰ {r.get("neue_uhrzeit","")}'
    return (
        f'<div class="anfrage-card">'
        f'<div style="display:flex;justify-content:space-between;">'
        f'<span style="color:#1a1a1a;font-weight:600;">#{r["id"]} – {r["heimteam"]} vs {r["gastteam"]}</span>'
        f'<span>{t_badge}&nbsp;{badge}</span></div>'
        f'<div style="color:#aaa;font-size:12px;margin-top:5px;">'
        f'📅 {r["datum"]} &nbsp;|&nbsp; ⏰ {r["uhrzeit"]}{change_hint} &nbsp;|&nbsp; '
        f'🏟️ {r["platz"]}{bear}</div></div>'
    )


def page_anfragen_verwalten() -> None:
    st.markdown(
        '<div class="main-header"><h1>📨 Spielanfragen verwalten</h1>'
        '<p>Neue Anfragen prüfen · DFBnet bestätigen · Trainer benachrichtigen</p></div>',
        unsafe_allow_html=True,
    )

    alle_raw    = get_all_anfragen()
    df_training = st.session_state.get("training_df", pd.DataFrame())

    def _qp_get(key: str, default: str) -> str:
        raw = st.query_params.get(key, default)
        if isinstance(raw, list):
            return str(raw[0]) if raw else default
        return str(raw)

    def _qp_bool(key: str, default: bool) -> bool:
        raw = _qp_get(key, "1" if default else "0").strip().lower()
        return raw in ("1", "true", "ja", "yes", "on")

    if "anfrage_suche" not in st.session_state:
        st.session_state["anfrage_suche"] = _qp_get("aq", "")
    if "anfrage_notiz_filter" not in st.session_state:
        st.session_state["anfrage_notiz_filter"] = _qp_bool("aq_notiz", False)
    if "anfrage_hide_done" not in st.session_state:
        st.session_state["anfrage_hide_done"] = _qp_bool("aq_hide_done", True)

    with st.expander("🔎 Filter & Suche", expanded=False):
        f1, f2, f3, f4, f5, f6 = st.columns([2.1, 1.1, 1.1, 1.0, 1.3, 0.9])
        with f1:
            suchtext = st.text_input(
                "Suche",
                placeholder="ID, Team, Betreff, Notiz, Kommentar ...",
                key="anfrage_suche",
                label_visibility="collapsed",
            )
        with f2:
            typ_optionen = ["Alle Typen"]
            if not alle_raw.empty and "anfrage_typ" in alle_raw.columns:
                typ_optionen += sorted(
                    [t for t in alle_raw["anfrage_typ"].fillna("neu").unique().tolist() if t]
                )
            if "anfrage_typ_filter" not in st.session_state:
                st.session_state["anfrage_typ_filter"] = _qp_get("aq_typ", "Alle Typen")
            if st.session_state["anfrage_typ_filter"] not in typ_optionen:
                st.session_state["anfrage_typ_filter"] = typ_optionen[0]
            typ_filter = st.selectbox("Typ", typ_optionen, key="anfrage_typ_filter")
        with f3:
            team_optionen = ["Alle Teams"]
            if not alle_raw.empty:
                teams = set()
                if "heimteam" in alle_raw.columns:
                    teams.update([t for t in alle_raw["heimteam"].dropna().tolist() if str(t).strip()])
                if "erstellt_von" in alle_raw.columns:
                    teams.update([t for t in alle_raw["erstellt_von"].dropna().tolist() if str(t).strip()])
                team_optionen += sorted(teams)
            if "anfrage_team_filter" not in st.session_state:
                st.session_state["anfrage_team_filter"] = _qp_get("aq_team", "Alle Teams")
            if st.session_state["anfrage_team_filter"] not in team_optionen:
                st.session_state["anfrage_team_filter"] = team_optionen[0]
            team_filter = st.selectbox("Team", team_optionen, key="anfrage_team_filter")
        with f4:
            nur_notizen = st.toggle("Nur mit Notiz", key="anfrage_notiz_filter")
        with f5:
            hide_done = st.toggle("Abgeschlossen ausblenden", key="anfrage_hide_done")
        with f6:
            st.write("")
            if st.button("Reset", key="anfrage_filter_reset", use_container_width=True):
                st.session_state["anfrage_suche"] = ""
                st.session_state["anfrage_typ_filter"] = "Alle Typen"
                st.session_state["anfrage_team_filter"] = "Alle Teams"
                st.session_state["anfrage_notiz_filter"] = False
                st.session_state["anfrage_hide_done"] = True
                st.query_params["aq"] = ""
                st.query_params["aq_typ"] = "Alle Typen"
                st.query_params["aq_team"] = "Alle Teams"
                st.query_params["aq_notiz"] = "0"
                st.query_params["aq_hide_done"] = "1"
                st.rerun()

    st.query_params["aq"] = suchtext
    st.query_params["aq_typ"] = typ_filter
    st.query_params["aq_team"] = team_filter
    st.query_params["aq_notiz"] = "1" if nur_notizen else "0"
    st.query_params["aq_hide_done"] = "1" if hide_done else "0"

    alle = alle_raw.copy()
    if not alle.empty and typ_filter != "Alle Typen" and "anfrage_typ" in alle.columns:
        alle = alle[alle["anfrage_typ"].fillna("neu") == typ_filter]
    if not alle.empty and team_filter != "Alle Teams":
        team_mask = pd.Series(False, index=alle.index)
        if "heimteam" in alle.columns:
            team_mask = team_mask | (alle["heimteam"].fillna("") == team_filter)
        if "erstellt_von" in alle.columns:
            team_mask = team_mask | (alle["erstellt_von"].fillna("") == team_filter)
        alle = alle[team_mask]
    if not alle.empty and nur_notizen and "verwalter_notiz" in alle.columns:
        alle = alle[alle["verwalter_notiz"].fillna("").str.strip() != ""]
    if not alle.empty and suchtext.strip():
        q = suchtext.strip().lower()
        cols = [
            "id", "heimteam", "gastteam", "status", "anfrage_typ", "erstellt_von",
            "betreff", "nachricht", "notizen", "verwalter_notiz", "bearbeiter_kommentar",
        ]
        nutz_cols = [c for c in cols if c in alle.columns]
        if nutz_cols:
            hay = alle[nutz_cols].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
            alle = alle[hay.str.contains(q, regex=False)]

    if not alle_raw.empty and len(alle) != len(alle_raw):
        st.caption(f"Filter aktiv: {len(alle)} von {len(alle_raw)} Vorgängen sichtbar.")

    if alle.empty:
        n_neu = n_dfb = n_done = 0
    else:
        n_neu  = len(alle[alle["status"] == "ausstehend"])
        n_dfb  = len(alle[alle["status"] == "dfbnet_ausstehend"])
        n_done = len(alle[alle["status"].isin(["abgeschlossen", "abgelehnt", "genehmigt"])])

    c1, c2, c3 = st.columns(3)
    c1.metric("⏳ Neu",           n_neu)
    c2.metric("📋 DFBnet offen",  n_dfb)
    c3.metric("✅ Abgeschlossen", n_done)

    tab_neu_label = f"🔴 Neue Anfragen ({n_neu})"
    tab_dfb_label = f"🔵 DFBnet ausstehend ({n_dfb})"
    tab_done_label = f"⚪ Abgeschlossen ({n_done})"

    if hide_done:
        tab_neu, tab_dfb = st.tabs(
            [tab_neu_label, tab_dfb_label]
        )
    else:
        tab_neu, tab_dfb, tab_done = st.tabs(
            [tab_neu_label, tab_dfb_label, tab_done_label]
        )

    # ─── TAB 1: Neue Anfragen ────────────────────────────────────────────────
    with tab_neu:
        df_neu = alle[alle["status"] == "ausstehend"] if not alle.empty else pd.DataFrame()
        if df_neu.empty:
            st.info("Keine neuen Anfragen.")
        else:
            for _, r in df_neu.iterrows():
                t_typ = r.get("anfrage_typ") or "neu"

                # ─── Freie Anfragen: eigener Pfad, kein DFBnet-Schritt ───────
                if t_typ == "allgemein":
                    betreff_txt = r.get("betreff") or r.get("notizen") or "Freie Anfrage"
                    with st.expander(
                        f"💬 #{r['id']} – Freie Anfrage von "
                        f"{r.get('erstellt_von','?')}: {betreff_txt[:60]}",
                        expanded=True,
                    ):
                        st.markdown(typ_badge("allgemein"), unsafe_allow_html=True)
                        if r.get("erstellt_von"):
                            st.markdown(
                                f'<span style="background:#e8f0fe;color:#1a56db;padding:2px 8px;'
                                f'border-radius:10px;font-size:11px;">📤 Von: '
                                f'{r["erstellt_von"]}</span>',
                                unsafe_allow_html=True,
                            )
                        st.markdown(f"**Betreff:** {betreff_txt}")
                        nachricht_txt = r.get("nachricht") or r.get("notizen") or ""
                        if nachricht_txt:
                            st.markdown(
                                f'<div style="background:#f0fdf4;border-left:3px solid #10b981;'
                                f'border-radius:4px;padding:10px 14px;margin:8px 0;'
                                f'font-size:13px;white-space:pre-wrap;">{nachricht_txt}</div>',
                                unsafe_allow_html=True,
                            )
                        st.markdown(
                            f'<span style="color:#aaa;font-size:11px;">'
                            f'📅 Eingegangen: {r.get("erstellt_am","")}</span>',
                            unsafe_allow_html=True,
                        )
                        _render_verwalter_notizblock(r, key_prefix="neu_frei")
                        frei_antwort = st.text_area(
                            "💬 Antwort an Trainer (optional)",
                            key=f"frei_antwort_{r['id']}",
                            placeholder="Antwort / Rückmeldung an den Trainer …",
                            height=100,
                        )
                        frei_abl_grund = st.text_input(
                            "Ablehnungsgrund (bei Ablehnung erforderlich)",
                            key=f"frei_abl_{r['id']}",
                            placeholder="Warum wird die Anfrage abgelehnt?",
                        )
                        ba1, ba2 = st.columns(2)
                        with ba1:
                            if st.button(
                                "✅ Zur Kenntnis genommen", key=f"ok_{r['id']}",
                                type="primary", use_container_width=True,
                            ):
                                bearbeiter_name = st.session_state.get("ms_name") or "Admin"
                                update_anfrage_status(r["id"], "abgeschlossen", bearbeiter_name, kommentar=frei_antwort.strip())
                                if frei_antwort.strip():
                                    trainer_email = get_trainer_email_for_team(r.get("erstellt_von", ""))
                                    if trainer_email:
                                        antwort_html = _mail_antwort_html(
                                            r["id"],
                                            r.get("erstellt_von", ""),
                                            betreff_txt,
                                            frei_antwort.strip(),
                                        )
                                        ok_a, err_a = send_email(
                                            f"[FCTM] 💬 Antwort auf Ihre Anfrage #{r['id']}: {betreff_txt[:50]}",
                                            antwort_html, to=trainer_email,
                                        )
                                        if ok_a:
                                            st.info(f"📧 Antwort-Mail an {trainer_email} gesendet.")
                                        elif err_a != "E-Mail-Versand nicht aktiviert.":
                                            st.warning(f"📧 Mail-Fehler: {err_a}")
                                st.rerun()
                        with ba2:
                            if st.button(
                                "❌ Ablehnen", key=f"no_{r['id']}",
                                type="secondary", use_container_width=True,
                            ):
                                if not frei_abl_grund.strip():
                                    st.error("Bitte einen Ablehnungsgrund eingeben.")
                                else:
                                    bearbeiter_name = st.session_state.get("ms_name") or "Admin"
                                    update_anfrage_status(r["id"], "abgelehnt", bearbeiter_name, kommentar=frei_abl_grund.strip())
                                    trainer_email = get_trainer_email_for_team(r.get("erstellt_von", ""))
                                    if trainer_email:
                                        abl_html = _mail_ablehnung_html(
                                            r["id"], "allgemein", "", "",
                                            "", "", "", frei_abl_grund.strip(),
                                        )
                                        ok_a, err_a = send_email(
                                            f"[FCTM] ❌ Anfrage #{r['id']} abgelehnt: {betreff_txt[:50]}",
                                            abl_html, to=trainer_email,
                                        )
                                        if ok_a:
                                            st.info(f"📧 Ablehnungs-Mail an {trainer_email} gesendet.")
                                        elif err_a != "E-Mail-Versand nicht aktiviert.":
                                            st.warning(f"📧 Mail-Fehler: {err_a}")
                                    st.rerun()
                    continue

                # ─── Spiel-bezogene Anfragen ─────────────────────────────────
                conflicts = find_conflicts(
                    df_training,
                    date.fromisoformat(r["datum"]),
                    r["uhrzeit"], r["platz"],
                )
                locked = r["platz"] in get_locked_pitches(date.fromisoformat(r["datum"]))

                with st.expander(
                    f"#{r['id']} – {r['heimteam']} vs {r['gastteam']}  |  "
                    f"{r['datum']} {r['uhrzeit']}  |  {r['platz']}",
                    expanded=True,
                ):
                    st.markdown(typ_badge(t_typ), unsafe_allow_html=True)
                    # Referenziertes Spiel + gewünschte Änderung anzeigen
                    if t_typ in ("aenderung", "verlegung", "uhrzeit_aenderung", "stornierung"):
                        ref_id = r.get("spiel_id")
                        if ref_id:
                            alle_sp = get_all_matches()
                            ref_row = alle_sp[alle_sp["id"] == ref_id]
                            if not ref_row.empty:
                                rm = ref_row.iloc[0]
                                new_hint = ""
                                if t_typ in ("aenderung", "verlegung", "uhrzeit_aenderung"):
                                    nd = r.get("neues_datum") or ""
                                    nu = r.get("neue_uhrzeit") or ""
                                    np_ = r.get("neuer_platz") or ""
                                    if nd or nu:
                                        new_hint = (
                                            f' &nbsp;→&nbsp; <b>{nd} {nu}'
                                            f'{(" · " + np_) if np_ and np_ != rm["platz"] else ""}'
                                            f'</b>'
                                        )
                                st.markdown(
                                    f'<div style="background:#fffbea;border-left:3px solid #d08000;'
                                    f'padding:6px 10px;border-radius:4px;margin-bottom:8px;'
                                    f'font-size:12px;color:#5a3e00;">'
                                    f'Referenzspiel #{rm["id"]}: '
                                    f'{rm["heimteam"]} vs {rm["gastteam"]} · '
                                    f'{rm["datum"]} {rm["uhrzeit"]} · {rm["platz"]}'
                                    f'{new_hint}</div>',
                                    unsafe_allow_html=True,
                                )
                    ic1, ic2, ic3, ic4 = st.columns(4)
                    ic1.markdown(f"**Datum:** {r['datum']}")
                    ic2.markdown(f"**Zeit:** {r['uhrzeit']}")
                    ic3.markdown(f"**Platz:** {r['platz']}")
                    ic4.markdown(f"**Kabine:** {r.get('kabine','–')}")
                    st.markdown(
                        f"**Heim:** {r['heimteam']} &nbsp;|&nbsp; **Gast:** {r['gastteam']}"
                    )
                    if r.get("erstellt_von"):
                        st.markdown(
                            f'<span style="background:#e8f0fe;color:#1a56db;padding:2px 8px;'
                            f'border-radius:10px;font-size:11px;">📤 Eingereicht von: '
                            f'{r["erstellt_von"]}</span>',
                            unsafe_allow_html=True,
                        )
                    if r.get("notizen"):
                        st.markdown(f"*Notiz: {r['notizen']}*")

                    _render_verwalter_notizblock(r, key_prefix="neu_spiel")

                    if locked:
                        st.error(f"🚫 Platz **{r['platz']}** ist gesperrt!")
                    if conflicts:
                        st.info(
                            f"ℹ️ **{', '.join(conflicts)}** trainieren zu diesem Zeitpunkt. "
                            f"Der Trainer hat die Zustimmung bereits bei der Anfrage bestätigt."
                        )
                    approved = True

                    # Kabinenzuweisung (außer bei Stornierungen)
                    if t_typ in ("neu", "aenderung", "verlegung", "uhrzeit_aenderung"):
                        ziel_datum   = r.get("neues_datum") or r["datum"]
                        ziel_uhrzeit = r.get("neue_uhrzeit") or r["uhrzeit"]
                        freie_k_gen  = get_free_kabinen(
                            date.fromisoformat(ziel_datum), ziel_uhrzeit
                        ) if ziel_datum and isinstance(ziel_datum, str) else []
                        gen_kc1, gen_kc2 = st.columns(2)
                        with gen_kc1:
                            gen_kab_h = st.selectbox(
                                "🏠 Kabine Heim", freie_k_gen, key=f"gkh_{r['id']}",
                            )
                        with gen_kc2:
                            rest_gen = [k for k in freie_k_gen if k != gen_kab_h]
                            gen_kab_g = st.selectbox(
                                "✈️ Kabine Gast",
                                rest_gen if rest_gen else freie_k_gen,
                                key=f"gkg_{r['id']}",
                            )

                    # ── Ablehnungsgrund (vor den Aktions-Buttons) ────────────────────
                    abl_grund = st.text_input(
                        "Ablehnungsgrund (bei Ablehnung erforderlich)",
                        key=f"abl_{r['id']}",
                        placeholder="z. B. Platzkonflikt, Terminüberschneidung, fehlende Absprache …",
                    )
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        if st.button(
                            "📋 Genehmigen → DFBnet eintragen",
                            key=f"ok_{r['id']}", use_container_width=True,
                        ):
                            if locked:
                                st.error("Platz gesperrt – Genehmigung nicht möglich.")
                            elif conflicts and not approved:
                                st.error("Bitte Trainer-Zustimmung bestätigen.")
                            else:
                                if t_typ in ("neu", "aenderung", "verlegung", "uhrzeit_aenderung"):
                                    kabine_gen = f"{gen_kab_h} / {gen_kab_g}"
                                    _kconn = db_connect()
                                    if t_typ in ("aenderung", "verlegung", "uhrzeit_aenderung"):
                                        _kconn.execute(
                                            "UPDATE spielanfragen SET neue_kabine=? WHERE id=?",
                                            (kabine_gen, r["id"]),
                                        )
                                    else:
                                        _kconn.execute(
                                            "UPDATE spielanfragen SET kabine=? WHERE id=?",
                                            (kabine_gen, r["id"]),
                                        )
                                    _kconn.commit()
                                    _kconn.close()
                                approve_anfrage(r["id"], conflicts if conflicts else [])
                                html = _mail_anfrage_html(
                                    r["id"],
                                    date.fromisoformat(r["datum"]),
                                    r["uhrzeit"], r["platz"],
                                    r["heimteam"], r["gastteam"],
                                    r.get("kabine", ""), r.get("notizen", ""),
                                    conflicts if conflicts else [],
                                    typ="Spielanfrage GENEHMIGT – JETZT IN DFBNET EINTRAGEN!",
                                )
                                ok, err = send_email(
                                    f"[FCTM] 📋 DFBnet eintragen: "
                                    f"{r['heimteam']} vs {r['gastteam']} ({r['datum']})",
                                    html,
                                )
                                if ok:
                                    st.info("📧 Hinweis-Mail ans Funktionspostfach gesendet.")
                                elif err != "E-Mail-Versand nicht aktiviert.":
                                    st.warning(f"📧 E-Mail-Fehler: {err}")
                                st.rerun()
                    with bc2:
                        if st.button(
                            "❌ Ablehnen", key=f"no_{r['id']}",
                            type="secondary", use_container_width=True,
                        ):
                            if not abl_grund.strip():
                                st.error("Bitte einen Ablehnungsgrund eingeben.")
                            else:
                                bearbeiter_name = st.session_state.get("ms_name") or "Admin"
                                update_anfrage_status(r["id"], "abgelehnt", bearbeiter_name, kommentar=abl_grund.strip())
                                # Trainer per E-Mail informieren
                                trainer_email = get_trainer_email_for_team(r["heimteam"])
                                if trainer_email:
                                    abl_html = _mail_ablehnung_html(
                                        r["id"], r.get("anfrage_typ", "neu"),
                                        r["heimteam"], r["gastteam"],
                                        r["datum"], r["uhrzeit"], r["platz"],
                                        abl_grund.strip(),
                                    )
                                    ok_a, err_a = send_email(
                                        f"[FCTM] ❌ Anfrage #{r['id']} abgelehnt: "
                                        f"{r['heimteam']} vs {r['gastteam']}",
                                        abl_html, to=trainer_email,
                                    )
                                    if ok_a:
                                        st.info(f"📧 Ablehnungs-Mail an {trainer_email} gesendet.")
                                    elif err_a != "E-Mail-Versand nicht aktiviert.":
                                        st.warning(f"📧 Mail-Fehler: {err_a}")
                                st.rerun()


    # ─── TAB 2: DFBnet ausstehend ────────────────────────────────────────────
    with tab_dfb:
        df_dfb = alle[alle["status"] == "dfbnet_ausstehend"] if not alle.empty else pd.DataFrame()
        if df_dfb.empty:
            st.info("Kein Spiel wartet auf DFBnet-Bestätigung.")
        else:
            st.info(
                "Diese Spiele wurden **genehmigt** und warten darauf, "
                "dass du sie in DFBnet einträgst. Sobald fertig: Button klicken → "
                "Spiel erscheint im Dashboard + Trainer erhält automatisch eine E-Mail."
            )
            for _, r in df_dfb.iterrows():
                with st.expander(
                    f"#{r['id']} – {r['heimteam']} vs {r['gastteam']}  |  "
                    f"{r['datum']} {r['uhrzeit']}  |  {r['platz']}",
                    expanded=True,
                ):
                    dc1, dc2, dc3, dc4 = st.columns(4)
                    dc1.markdown(f"**Datum:** {r['datum']}")
                    dc2.markdown(f"**Zeit:** {r['uhrzeit']}")
                    dc3.markdown(f"**Platz:** {r['platz']}")
                    dc4.markdown(f"**Kabine:** {r.get('kabine','–')}")
                    st.markdown(
                        f"**Heim:** {r['heimteam']} &nbsp;|&nbsp; **Gast:** {r['gastteam']}"
                    )
                    if r.get("notizen"):
                        st.markdown(f"*Notiz: {r['notizen']}*")

                    _render_verwalter_notizblock(r, key_prefix="dfb")

                    # Trainer-E-Mail-Lookup
                    team_mail = get_trainer_email_for_team(r["heimteam"])
                    custom_mail = st.text_input(
                        "Trainer-E-Mail (optional überschreiben)",
                        value=team_mail,
                        key=f"tmail_{r['id']}",
                        placeholder="trainer@verein.de",
                    )

                    if st.button(
                        "✅ DFBnet eingetragen – Spiel übernehmen & Trainer benachrichtigen",
                        key=f"dfb_{r['id']}", use_container_width=True, type="primary",
                    ):
                        typ_ = r.get('anfrage_typ') or 'neu'
                        sid  = confirm_dfbnet(r["id"])
                        if typ_ == 'stornierung':
                            st.success("✅ Spiel storniert und aus dem Dashboard entfernt!")
                        elif typ_ in ('aenderung', 'verlegung', 'uhrzeit_aenderung'):
                            lbl = {"aenderung": "aktualisiert", "verlegung": "verlegt",
                                   "uhrzeit_aenderung": "Uhrzeit geändert"}.get(typ_, "aktualisiert")
                            st.success(f"✅ Spiel #{sid} {lbl}, DFBnet bestätigt!")
                        else:
                            st.success(f"✅ Spiel #{sid} im Dashboard gespeichert, DFBnet bestätigt!")
                        # ── Typ-spezifische Trainer-Mail ────────────────────
                        if custom_mail.strip():
                            if typ_ == 'stornierung':
                                trainer_html = _mail_trainer_stornierung_html(
                                    date.fromisoformat(r['datum']),
                                    r['uhrzeit'], r['platz'],
                                    r['heimteam'], r['gastteam'],
                                    r.get('notizen',''),
                                )
                                subj = (f"[FCTM] ❌ Spielabsage: {r['heimteam']} vs "
                                        f"{r['gastteam']} ({r['datum']})")
                            elif typ_ in ('aenderung', 'verlegung', 'uhrzeit_aenderung'):
                                trainer_html = _mail_trainer_aenderung_html(
                                    date.fromisoformat(r['datum']),
                                    r['uhrzeit'], r['platz'], r.get('kabine',''),
                                    date.fromisoformat(r['neues_datum']) if r.get('neues_datum') else date.fromisoformat(r['datum']),
                                    r.get('neue_uhrzeit') or r['uhrzeit'],
                                    r.get('neuer_platz')  or r['platz'],
                                    r.get('neue_kabine')  or r.get('kabine',''),
                                    r['heimteam'], r['gastteam'],
                                )
                                icons = {"aenderung": "✏️", "verlegung": "⏩", "uhrzeit_aenderung": "⏰"}
                                subj = (f"[FCTM] {icons.get(typ_,'✏️')} Spieländerung: "
                                        f"{r['heimteam']} vs {r['gastteam']} ({r['datum']})")
                            else:
                                trainer_html = _mail_trainer_html(
                                    date.fromisoformat(r['datum']),
                                    r['uhrzeit'], r['platz'],
                                    r['heimteam'], r['gastteam'],
                                    r.get('kabine',''), '',
                                )
                                subj = (f"[FCTM] ⚽ Spielbestätigung: {r['heimteam']} vs "
                                        f"{r['gastteam']} am {r['datum']}")
                            ok2, err2 = send_email(subj, trainer_html, to=custom_mail.strip())
                            if ok2:
                                st.info(f"📧 Trainer-Mail an {custom_mail.strip()} gesendet.")
                            elif err2 != "E-Mail-Versand nicht aktiviert.":
                                st.warning(f"📧 Trainer-Mail-Fehler: {err2}")
                        st.balloons()
                        st.rerun()

    # ─── TAB 3: Abgeschlossen / Abgelehnt ───────────────────────────────────
    if not hide_done:
        with tab_done:
            df_done = (
                alle[alle["status"].isin(["abgeschlossen", "abgelehnt", "genehmigt"])]
                if not alle.empty else pd.DataFrame()
            )
            if df_done.empty:
                st.info("Noch keine abgeschlossenen Vorgänge.")
            else:
                for _, r in df_done.sort_values("bearbeitet_am", ascending=False, na_position="last").iterrows():
                    done_notiz = r.get("verwalter_notiz") or ""
                    notiz_suffix = " 📝" if done_notiz else ""
                    titel  = (
                        f"#{r['id']} – {r.get('heimteam','?')} vs {r.get('gastteam','?')}  |  "
                        f"{r.get('datum','')} {r.get('uhrzeit','')}  |  "
                        f"[{r.get('status','').upper()}]{notiz_suffix}"
                    )
                    with st.expander(titel, expanded=False):
                        st.markdown(_anfrage_card_html(r), unsafe_allow_html=True)
                        _render_verwalter_notizblock(r, key_prefix="done")


def page_admin_spiel_anlegen() -> None:
    st.markdown(
        '<div class="main-header"><h1>➕ Spiel direkt anlegen</h1>'
        '<p>Spiel erfassen · DFBnet eintragen · Trainer automatisch benachrichtigen</p></div>',
        unsafe_allow_html=True,
    )

    df_training = st.session_state.get("training_df", pd.DataFrame())

    # ─── SCHRITT 1: Spiel erfassen ──────────────────────────────────────────
    with st.expander("📝 Neues Spiel erfassen", expanded=True):
        with st.form("admin_spiel_form"):
            fc1, fc2 = st.columns(2)
            with fc1:
                f_datum   = st.date_input("Datum", value=date.today())
            with fc2:
                f_uhrzeit = st.selectbox("Anstoßzeit", TIME_SLOTS_TRAINING)
            f_platz  = st.selectbox("Platz", PITCHES_SPIEL)
            fc3, fc4 = st.columns(2)
            with fc3:
                f_heim = st.text_input("Heimteam")
            with fc4:
                f_gast = st.text_input("Gastteam")

            freie_kabinen_a = get_free_kabinen(f_datum, f_uhrzeit)
            belegt_cnt      = len(LOCKER_ROOMS) - len(freie_kabinen_a)
            if belegt_cnt:
                st.info(
                    f"🚳 {belegt_cnt} Kabine(n) durch Training belegt – "
                    "nur freie Kabinen werden angezeigt."
                )
            ak1, ak2 = st.columns(2)
            with ak1:
                f_kabine_heim = st.selectbox(
                    "🏠 Kabine Heimmannschaft", freie_kabinen_a, key="adm_kh"
                )
            with ak2:
                rest_a = [k for k in freie_kabinen_a if k != f_kabine_heim]
                f_kabine_gast = st.selectbox(
                    "✈️ Kabine Gastmannschaft",
                    rest_a if rest_a else freie_kabinen_a,
                    key="adm_kg",
                )
            f_notizen = st.text_area("Notizen")

            conflicts    = find_conflicts(df_training, f_datum, f_uhrzeit, f_platz)
            pitch_locked = f_platz in get_locked_pitches(f_datum)

            if pitch_locked:
                st.error(f"🚫 **{f_platz}** ist für {f_datum.strftime('%d.%m.%Y')} gesperrt!")
            if conflicts:
                st.warning(
                    f"⚠️ Konflikt: **{', '.join(conflicts)}** trainieren zu dieser Zeit."
                )
                approved = st.checkbox(
                    f"✅ Ich bestätige die Zustimmung der betroffenen Trainer:innen "
                    f"(**{', '.join(conflicts)}**)."
                )
            else:
                approved = True

            st.info(
                "💡 Nach dem Speichern erscheint das Spiel in der **DFBnet-Warteschlange**. "
                "Erst nach DFBnet-Eintragung und Bestätigung wird es ins Dashboard übernommen "
                "und der Trainer automatisch informiert."
            )

            if st.form_submit_button(
                "📋 Spiel speichern → DFBnet eintragen",
                type="primary", use_container_width=True,
            ):
                if pitch_locked:
                    st.error("Platz gesperrt.")
                elif conflicts and not approved:
                    st.error("Trainer-Zustimmung fehlt.")
                elif not f_heim.strip() or not f_gast.strip():
                    st.error("Heim- und Gastteam eintragen.")
                elif f_kabine_heim == f_kabine_gast:
                    st.error("Heim- und Gastmannschaft können nicht dieselbe Kabine nutzen.")
                else:
                    f_kabine = f"{f_kabine_heim} / {f_kabine_gast}"
                    aid = create_spielanfrage(
                        f_datum, f_uhrzeit, f_platz,
                        f_heim.strip(), f_gast.strip(),
                        f_kabine, f_notizen,
                    )
                    # Direkt auf dfbnet_ausstehend setzen (kein Genehmigungsschritt nötig)
                    update_anfrage_status(aid, "dfbnet_ausstehend", "Admin")
                    # Hinweis-Mail ans Funktionspostfach: DFBnet eintragen!
                    html = _mail_anfrage_html(
                        aid, f_datum, f_uhrzeit, f_platz,
                        f_heim.strip(), f_gast.strip(),
                        f_kabine, f_notizen,
                        conflicts, typ="Neues Spiel angelegt – JETZT IN DFBNET EINTRAGEN!",
                    )
                    ok, err = send_email(
                        f"[FCTM] 📋 DFBnet eintragen: {f_heim} vs {f_gast}"
                        f" ({f_datum.strftime('%d.%m.%Y')})",
                        html,
                    )
                    if ok:
                        st.info("📧 Hinweis-Mail ans Funktionspostfach gesendet.")
                    elif err != "E-Mail-Versand nicht aktiviert.":
                        st.warning(f"📧 E-Mail-Fehler: {err}")
                    st.success(
                        f"✅ Spiel gespeichert (ID {aid}) – "
                        "bitte jetzt in **DFBnet** eintragen und unten bestätigen!"
                    )
                    st.rerun()

    # ─── SCHRITT 2: DFBnet-Bestätigung ─────────────────────────────────────
    st.divider()
    st.subheader("📋 DFBnet-Bestätigung ausstehend")
    df_dfb = get_all_anfragen_dfbnet()
    if df_dfb.empty:
        st.info("Keine Spiele warten auf DFBnet-Bestätigung.")
    else:
        st.info(
            "Diese Spiele wurden **noch nicht** im DFBnet eingetragen. "
            "Trag sie ein und klicke dann auf den Button – "
            "das Spiel wird ins Dashboard übernommen und der Trainer per E-Mail informiert."
        )
        for _, r in df_dfb.iterrows():
            with st.expander(
                f"#{r['id']} – {r['heimteam']} vs {r['gastteam']}  "
                f"|  {r['datum']} {r['uhrzeit']}  |  {r['platz']}",
                expanded=True,
            ):
                dc1, dc2, dc3 = st.columns(3)
                dc1.markdown(f"**Datum:** {r['datum']}")
                dc2.markdown(f"**Zeit:** {r['uhrzeit']}")
                dc3.markdown(f"**Platz:** {r['platz']}")
                st.markdown(
                    f"**Heim:** {r['heimteam']} &nbsp;|&nbsp; **Gast:** {r['gastteam']} "
                    f"&nbsp;|&nbsp; **Kabine:** {r.get('kabine','–')}"
                )

                team_mail = get_trainer_email_for_team(r["heimteam"])
                t_mail = st.text_input(
                    "Trainer-E-Mail (optional überschreiben)",
                    value=team_mail,
                    key=f"dsp_tmail_{r['id']}",
                    placeholder="trainer@verein.de",
                )

                if st.button(
                    "✅ DFBnet eingetragen – Spiel übernehmen & Trainer benachrichtigen",
                    key=f"dsp_dfb_{r['id']}", use_container_width=True, type="primary",
                ):
                    sid = confirm_dfbnet(r["id"])
                    st.success(f"✅ Spiel #{sid} im Dashboard gespeichert!")
                    if t_mail.strip():
                        trainer_html = _mail_trainer_html(
                            date.fromisoformat(r["datum"]),
                            r["uhrzeit"], r["platz"],
                            r["heimteam"], r["gastteam"],
                            r.get("kabine", ""), "",
                        )
                        ok2, err2 = send_email(
                            f"[FCTM] ⚽ Spielbestätigung: {r['heimteam']} vs {r['gastteam']}"
                            f" am {r['datum']}",
                            trainer_html,
                            to=t_mail.strip(),
                        )
                        if ok2:
                            st.info(f"📧 Trainer-Mail an {t_mail.strip()} gesendet.")
                        elif err2 != "E-Mail-Versand nicht aktiviert.":
                            st.warning(f"📧 Trainer-Mail-Fehler: {err2}")
                    st.balloons()
                    st.rerun()

    # ─── Alle bestätigten Spiele ────────────────────────────────────────────
    st.divider()
    st.subheader("📋 Alle bestätigten Spiele")
    all_m = get_all_matches()
    if all_m.empty:
        st.info("Noch keine Spiele eingetragen.")
    else:
        all_m["datum_dt"] = pd.to_datetime(all_m["datum"])
        all_m["herkunft"] = all_m.get("quelle", "manuell").fillna("manuell").map({
            "manuell": "Manuell angelegt",
            "aus_anfrage": "Aus Anfrage uebernommen",
            "automatisch_aus_anfrage": "Automatisch aus DFBnet-Anfrage erzeugt",
        }).fillna("Manuell angelegt")
        # ── CSV-Export ────────────────────────────────────────────────────
        export_df = all_m.sort_values("datum_dt")[
            ["datum", "uhrzeit", "platz", "heimteam", "gastteam", "kabine", "notizen", "herkunft"]
        ].rename(columns={
            "datum": "Datum", "uhrzeit": "Uhrzeit", "platz": "Platz",
            "heimteam": "Heimteam", "gastteam": "Gastteam",
            "kabine": "Kabine", "notizen": "Notizen", "herkunft": "Herkunft",
        })
        st.download_button(
            label="📥 Spielplan als CSV exportieren",
            data=export_df.to_csv(index=False, sep=";", encoding="utf-8-sig"),
            file_name=f"spielplan_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.divider()
        for _, m in all_m.sort_values("datum_dt").iterrows():
            dfb_ok = m.get("dfbnet_eingetragen", 1)
            dfb_badge = (
                '<span style="background:#22c55e;color:#fff;padding:1px 7px;'
                'border-radius:10px;font-size:10px;">✅ DFBnet</span>'
                if dfb_ok else
                '<span style="background:#7c3aed;color:#fff;padding:1px 7px;'
                'border-radius:10px;font-size:10px;">📋 DFBnet offen</span>'
            )
            quelle_badge = {
                "automatisch_aus_anfrage": '<span style="background:#0f766e;color:#fff;padding:1px 7px;border-radius:10px;font-size:10px;">🤖 Auto aus Anfrage</span>',
                "aus_anfrage": '<span style="background:#2563eb;color:#fff;padding:1px 7px;border-radius:10px;font-size:10px;">📨 Aus Anfrage</span>',
            }.get(m.get("quelle"), '<span style="background:#6b7280;color:#fff;padding:1px 7px;border-radius:10px;font-size:10px;">✍️ Manuell</span>')
            with st.expander(
                f"⚽ #{m['id']} – {m['heimteam']} vs {m['gastteam']}  |  "
                f"{m['datum_dt'].strftime('%d.%m.%Y')} {m['uhrzeit']}  |  {m['platz']}",
                expanded=False,
            ):
                sc1, sc2, sc3 = st.columns(3)
                sc1.markdown(f"**Datum:** {m['datum_dt'].strftime('%d.%m.%Y')}")
                sc2.markdown(f"**Zeit:** {m['uhrzeit']}")
                sc3.markdown(f"**Platz:** {m['platz']}")
                st.markdown(
                    f"**Kabine:** {m.get('kabine','–')}  &nbsp;  {dfb_badge} &nbsp; {quelle_badge}",
                    unsafe_allow_html=True,
                )
                if m.get("ursprung_anfrage_id"):
                    st.caption(f"Ursprung: Anfrage #{int(m['ursprung_anfrage_id'])}")

                # ── Bearbeiten ────────────────────────────────────────────
                st.divider()
                st.markdown("**✏️ Spiel bearbeiten**")
                with st.form(f"edit_match_{m['id']}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_datum = st.date_input(
                            "Neues Datum", value=date.fromisoformat(m["datum"]),
                            key=f"ed_{m['id']}",
                        )
                    with ec2:
                        cur_idx = TIME_SLOTS_TRAINING.index(m["uhrzeit"]) \
                                  if m["uhrzeit"] in TIME_SLOTS_TRAINING else 0
                        e_uhrzeit = st.selectbox(
                            "Neue Uhrzeit", TIME_SLOTS_TRAINING,
                            index=cur_idx, key=f"eu_{m['id']}",
                        )
                    cur_pi = PITCHES_SPIEL.index(m["platz"]) \
                             if m["platz"] in PITCHES_SPIEL else 0
                    e_platz = st.selectbox(
                        "Neuer Platz", PITCHES_SPIEL, index=cur_pi, key=f"ep_{m['id']}"
                    )
                    freie_k = get_free_kabinen(e_datum, e_uhrzeit)
                    ek1, ek2 = st.columns(2)
                    with ek1:
                        e_kab_h = st.selectbox(
                            "🏠 Kabine Heim", freie_k, key=f"ekh_{m['id']}"
                        )
                    with ek2:
                        rest_ek = [k for k in freie_k if k != e_kab_h]
                        e_kab_g = st.selectbox(
                            "✈️ Kabine Gast", rest_ek if rest_ek else freie_k,
                            key=f"ekg_{m['id']}",
                        )
                    e_notizen = st.text_area(
                        "Notizen", value=m.get("notizen",""), key=f"en_{m['id']}"
                    )
                    e_tmail = st.text_input(
                        "Trainer-E-Mail (für Änderungs-Mail)",
                        value=get_trainer_email_for_team(m["heimteam"]),
                        key=f"etm_{m['id']}",
                    )
                    send_aend_mail = st.checkbox(
                        "📧 Trainer über Änderung informieren", value=True,
                        key=f"esc_{m['id']}",
                    )
                    if st.form_submit_button(
                        "💾 Änderungen speichern", type="primary", use_container_width=True
                    ):
                        if e_kab_h == e_kab_g:
                            st.error("Heim und Gast können nicht dieselbe Kabine nutzen.")
                        else:
                            neue_kabine = f"{e_kab_h} / {e_kab_g}"
                            update_match_details(
                                m["id"], e_datum, e_uhrzeit, e_platz, neue_kabine, e_notizen
                            )
                            st.success("✅ Spiel aktualisiert!")
                            if send_aend_mail and e_tmail.strip():
                                aend_html = _mail_trainer_aenderung_html(
                                    date.fromisoformat(m["datum"]),
                                    m["uhrzeit"], m["platz"], m.get("kabine",""),
                                    e_datum, e_uhrzeit, e_platz, neue_kabine,
                                    m["heimteam"], m["gastteam"],
                                )
                                ok3, err3 = send_email(
                                    f"[FCTM] ✏️ Spieländerung: {m['heimteam']} vs "
                                    f"{m['gastteam']} ({m['datum']})",
                                    aend_html, to=e_tmail.strip(),
                                )
                                if ok3:
                                    st.info(f"📧 Änderungs-Mail an {e_tmail.strip()} gesendet.")
                                elif err3 != "E-Mail-Versand nicht aktiviert.":
                                    st.warning(f"📧 Mail-Fehler: {err3}")
                            st.rerun()

                # ── Löschen ───────────────────────────────────────────────
                st.divider()
                st.markdown("**🗑️ Spiel löschen**")
                d_tmail = st.text_input(
                    "Trainer-E-Mail (für Absage-Mail, optional)",
                    value=get_trainer_email_for_team(m["heimteam"]),
                    key=f"dtm_{m['id']}",
                )
                d_grund = st.text_input(
                    "Begründung (optional)", key=f"dg_{m['id']}"
                )
                send_del_mail = st.checkbox(
                    "📧 Trainer über Absage informieren", value=True,
                    key=f"dsc_{m['id']}",
                )
                if st.button(
                    f"🗑️ Spiel #{m['id']} löschen", key=f"del_{m['id']}",
                    type="secondary", use_container_width=True,
                ):
                    if send_del_mail and d_tmail.strip():
                        del_html = _mail_trainer_stornierung_html(
                            date.fromisoformat(m["datum"]),
                            m["uhrzeit"], m["platz"],
                            m["heimteam"], m["gastteam"], d_grund,
                        )
                        ok4, err4 = send_email(
                            f"[FCTM] ❌ Spielabsage: {m['heimteam']} vs "
                            f"{m['gastteam']} ({m['datum']})",
                            del_html, to=d_tmail.strip(),
                        )
                        if ok4:
                            st.info(f"📧 Absage-Mail an {d_tmail.strip()} gesendet.")
                        elif err4 != "E-Mail-Versand nicht aktiviert.":
                            st.warning(f"📧 Mail-Fehler: {err4}")
                    delete_match(m["id"])
                    st.rerun()


def page_saisonplanung() -> None:
    st.markdown(
        '<div class="main-header"><h1>📆 Saisonplanung</h1>'
        '<p>Trainingszeiten erfassen · Kabinen zuweisen · Trainer hinterlegen</p></div>',
        unsafe_allow_html=True,
    )

    _sy, _sm = date.today().year, date.today().month
    saison_default = f"{_sy - 1}/{_sy}" if _sm < 7 else f"{_sy}/{_sy + 1}"
    saison = st.text_input("Saison (z. B. 2025/2026)", value=saison_default)
    st.session_state["aktuell_saison"] = saison

    # Immer aktuellen Stand aus DB in session_state laden
    db_df = load_training_df_from_db(saison)
    if not db_df.empty:
        st.session_state.training_df = db_df

    day_order = {d: i for i, d in enumerate(DAYS)}

    tab_manuell, tab_csv, tab_kabinen = st.tabs([
        "✏️ Trainingszeiten erfassen",
        "📂 CSV / Excel importieren",
        "🚿 Kabinen & Trainer",
    ])

    # ── Tab 1: Manuell ────────────────────────────────────────────────────
    with tab_manuell:
        # ── Eingabeformular ────────────────────────────────────────────
        sp_df = get_saisonplanung(saison)
        vorhandene_teams = sorted(sp_df["team"].unique().tolist()) if not sp_df.empty else []

        with st.form("training_slot_form", clear_on_submit=True):
            st.subheader("Neuen Trainingstermin hinzufügen")
            mc1, mc2 = st.columns([2, 1])
            with mc1:
                f_team = st.text_input(
                    "Mannschaft",
                    placeholder="z. B. A-Jugend, 1. Mannschaft …",
                )
                if vorhandene_teams:
                    st.caption(
                        "Vorhandene Teams: " + " · ".join(vorhandene_teams[:10])
                        + (" …" if len(vorhandene_teams) > 10 else "")
                    )
            with mc2:
                f_platz = st.selectbox("Platz", PITCHES)

            f_tage = st.multiselect(
                "Trainingstage",
                DAYS,
                placeholder="Einen oder mehrere Tage wählen …",
            )
            tc1, tc2 = st.columns(2)
            with tc1:
                f_zeit_von = st.selectbox("Trainingsstart (Von)", TIME_SLOTS_TRAINING)
            with tc2:
                idx_von     = TIME_SLOTS_TRAINING.index(f_zeit_von)
                opts_bis    = TIME_SLOTS_TRAINING[idx_von + 1:]
                f_zeit_bis  = st.selectbox(
                    "Trainingsende (Bis)",
                    opts_bis if opts_bis else TIME_SLOTS_TRAINING,
                )

            submitted = st.form_submit_button(
                "➕ Hinzufügen", type="primary", use_container_width=True
            )
            if submitted:
                if not f_team.strip():
                    st.error("Bitte Mannschaftsname eingeben.")
                elif not f_tage:
                    st.error("Bitte mindestens einen Trainingstag wählen.")
                else:
                    for tag in f_tage:
                        add_training_slot(
                            f_team.strip(), tag, f_zeit_von, f_zeit_bis,
                            f_platz, saison,
                        )
                    st.success(
                        f"✅ {len(f_tage)} Trainingsslot(s) für "
                        f"**{f_team.strip()}** gespeichert "
                        f"({f_zeit_von}–{f_zeit_bis}, {f_platz})."
                    )
                    st.session_state.training_df = load_training_df_from_db(saison)
                    st.rerun()

        # ── Bestehende Trainingszeiten ──────────────────────────────────
        st.divider()
        sp_df = get_saisonplanung(saison)  # nach möglichem rerun neu laden
        if sp_df.empty:
            st.info("Noch keine Trainingszeiten für diese Saison erfasst.")
        else:
            teams_sorted = sorted(sp_df["team"].unique(), key=str.lower)
            st.markdown(f"**{len(teams_sorted)} Mannschaft(en)** · {len(sp_df)} Slot(s) gesamt")
            st.divider()

            for team in teams_sorted:
                team_df = (
                    sp_df[sp_df["team"] == team]
                    .copy()
                    .sort_values("tag", key=lambda s: s.map(day_order))
                )
                with st.expander(f"⚽ {team}  ({len(team_df)} Slot(s))", expanded=False):
                    for _, row in team_df.iterrows():
                        ze = row.get("zeit_ende", "") or ""
                        zeit_label = f"{row['zeit']}–{ze}" if ze else row["zeit"]
                        r1, r2 = st.columns([5, 1])
                        with r1:
                            st.markdown(
                                f"📅 **{row['tag']}** &nbsp;·&nbsp; "
                                f"⏱ {zeit_label} &nbsp;·&nbsp; "
                                f"🏟️ {row['platz']}"
                                + (f" &nbsp;·&nbsp; 🚿 {row['kabine']}" if row.get("kabine") else ""),
                                unsafe_allow_html=True,
                            )
                        with r2:
                            if st.button(
                                "🗑️", key=f"del_{row['id']}",
                                help="Diesen Slot löschen",
                            ):
                                delete_training_slot(int(row["id"]))
                                st.session_state.training_df = load_training_df_from_db(saison)
                                st.rerun()

    # ── Tab 2: CSV-Import ─────────────────────────────────────────────────
    with tab_csv:
        st.subheader("Trainingsplan importieren")
        st.caption(
            "Importiert einen kompletten Trainingsplan aus CSV oder Excel "
            "und **ersetzt** alle bestehenden Einträge der gewählten Saison."
        )
        col_up, col_btn = st.columns([2, 1])
        with col_up:
            uploaded = st.file_uploader(
                "CSV oder Excel hochladen", type=["csv", "xlsx"],
                label_visibility="collapsed",
            )
        with col_btn:
            st.write("")
            if st.button("🔄 Beispieldaten laden", use_container_width=True):
                df = parse_trainingsplan(create_sample_csv())
                st.session_state.training_df = df
                st.success(f"✓ Beispieldaten: {len(df)} Einträge geladen")

        if uploaded:
            try:
                if uploaded.name.endswith(".csv"):
                    df = parse_trainingsplan(uploaded.read().decode("utf-8"))
                else:
                    df = parse_trainingsplan(uploaded)
                st.session_state.training_df = df
                st.success(f"✓ {len(df)} Trainingseinheiten importiert")
            except Exception as exc:
                st.error(f"Fehler beim Import: {exc}")

        df_training = st.session_state.get("training_df", pd.DataFrame())
        if not df_training.empty:
            st.divider()
            st.subheader("Vorschau")
            st.dataframe(df_training, use_container_width=True, hide_index=True)

            if st.button("💾 In Saisondatenbank speichern (⚠️ überschreibt alles)", type="primary"):
                sv = df_training.copy()
                if "kabine" not in sv.columns:
                    sv["kabine"] = ""
                sv.columns = [c.lower() for c in sv.columns]
                for col in ["team", "platz", "tag", "zeit", "kabine"]:
                    if col not in sv.columns:
                        sv[col] = ""
                save_saisonplanung(sv[["team", "platz", "tag", "zeit", "kabine"]], saison)
                st.session_state.training_df = load_training_df_from_db(saison)
                st.success(f"✅ Trainingsplan für Saison {saison} gespeichert.")

    # ── Tab 3: Kabinen & Trainer ──────────────────────────────────────────
    with tab_kabinen:
        st.subheader("Kabinen & Trainer-E-Mails je Mannschaft")
        st.caption(
            "Die Zuweisung gilt saisonweit. Kabinen werden bei Spielansetzungen "
            "automatisch als belegt markiert."
        )

        sp_df = get_saisonplanung(saison)

        if sp_df.empty:
            st.info("Bitte zuerst Trainingszeiten erfassen (Tab ✏️).")
        else:
            teams = sorted(sp_df["team"].unique())
            st.markdown(f"**{len(teams)} Mannschaft(en)**")

            assignments: dict[str, str] = {}
            trainer_emails: dict[str, str] = {}
            cols_per_row = 3
            for i in range(0, len(teams), cols_per_row):
                batch    = teams[i: i + cols_per_row]
                row_cols = st.columns(cols_per_row)
                for col, team in zip(row_cols, batch):
                    with col:
                        st.markdown(f"**{team}**")
                        current = ""
                        hit = sp_df[sp_df["team"] == team]["kabine"]
                        if not hit.empty and str(hit.iloc[0]) not in ("", "nan"):
                            current = str(hit.iloc[0])
                        idx    = LOCKER_ROOMS.index(current) if current in LOCKER_ROOMS else 0
                        chosen = st.selectbox(
                            "Kabine",
                            ["(keine)"] + LOCKER_ROOMS,
                            index=idx + 1 if current else 0,
                            key=f"kabine_{team}",
                            label_visibility="collapsed",
                        )
                        assignments[team] = chosen if chosen != "(keine)" else ""
                        cur_mail = ""
                        mhit = sp_df[sp_df["team"] == team]["trainer_email"]
                        if "trainer_email" in sp_df.columns and not mhit.empty:
                            if str(mhit.iloc[0]) not in ("", "nan", "None"):
                                cur_mail = str(mhit.iloc[0])
                        trainer_emails[team] = st.text_input(
                            "📧 Trainer-E-Mail",
                            value=cur_mail,
                            key=f"tmail_s_{team}",
                            placeholder="trainer@verein.de",
                            label_visibility="collapsed",
                        )

            # ── Duplikat-Check ──────────────────────────────────────────
            st.divider()
            st.subheader("🔍 Duplikat-Prüfung")
            kabinen_belegt: dict[str, list[str]] = {}
            for team, kabine in assignments.items():
                if kabine:
                    kabinen_belegt.setdefault(kabine, []).append(team)
            duplikate = {k: v for k, v in kabinen_belegt.items() if len(v) > 1}

            if duplikate:
                st.error(f"⛔ **{len(duplikate)} Kabine(n) mehrfach vergeben!**")
                for kabine, tms in duplikate.items():
                    grad = "dreifach" if len(tms) >= 3 else "doppelt"
                    st.markdown(
                        f'<div class="duplicate-warning">'
                        f'<b style="color:#ff4d4d;">🔴 {kabine}</b> – '
                        f'{grad} vergeben an: <b style="color:#fff;">{", ".join(tms)}</b>'
                        "</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.success("✅ Keine Kabinen-Konflikte.")

            # ── Übersichts-Grid ─────────────────────────────────────────
            st.subheader("Kabinen-Übersicht")
            ov_cols = st.columns(max(len(LOCKER_ROOMS), 1))
            for idx_k, kabine in enumerate(LOCKER_ROOMS):
                with ov_cols[idx_k % len(LOCKER_ROOMS)]:
                    teams_in    = [t for t, k in assignments.items() if k == kabine]
                    is_conflict = kabine in duplikate
                    css  = ("locker-conflict" if is_conflict
                            else ("locker-busy" if teams_in else "locker-free"))
                    ikon = "🔴" if is_conflict else ("🚿" if teams_in else "🔓")
                    teams_html = (
                        "".join(
                            f'<div style="font-size:11px;color:#333;margin-top:3px;">{t}</div>'
                            for t in teams_in
                        )
                        if teams_in
                        else '<div style="color:#999;font-size:11px;">Frei</div>'
                    )
                    st.markdown(
                        f'<div class="{css}"><div style="font-size:24px;">{ikon}</div>'
                        f'<div style="color:#fff;font-weight:bold;font-size:13px;margin:6px 0;">'
                        f"{kabine}</div>{teams_html}</div>",
                        unsafe_allow_html=True,
                    )

            # ── Zeitbasierter Konflikt-Check ────────────────────────────
            st.divider()
            st.subheader("🕐 Zeitbasierter Konflikt-Check")
            konflikt_df = get_kabinen_konflikte(saison)
            if konflikt_df.empty:
                st.success("✅ Keine zeitgleichen Kabinen-Kollisionen.")
            else:
                st.error(f"⛔ {len(konflikt_df)} zeitgleiche Kabinen-Kollision(en)!")
                st.dataframe(
                    konflikt_df.rename(columns={
                        "kabine": "Kabine", "tag": "Tag", "zeit": "Zeit",
                        "anzahl": "Anzahl Teams", "teams": "Betroffene Teams",
                    }),
                    use_container_width=True, hide_index=True,
                )

            st.divider()
            btn_disabled = bool(duplikate)
            if st.button(
                "💾 Kabinen & E-Mails speichern" if not btn_disabled
                else "💾 Speichern (zuerst Konflikte lösen)",
                type="primary" if not btn_disabled else "secondary",
                disabled=btn_disabled,
                use_container_width=True,
            ):
                update_kabinen_und_emails(saison, assignments, trainer_emails)
                st.success(f"✅ Kabinen & Trainer-Mails für Saison {saison} gespeichert!")
                st.session_state.training_df = load_training_df_from_db(saison)
                st.rerun()


def page_platzverwaltung() -> None:
    st.markdown(
        '<div class="main-header"><h1>🔒 Platzverwaltung</h1>'
        '<p>Plätze sperren / freigeben &amp; aktueller Tagesstatus</p></div>',
        unsafe_allow_html=True,
    )

    col_form, col_list = st.columns([3, 2])
    with col_form:
        with st.form("lock_form"):
            lc1, lc2 = st.columns(2)
            with lc1:
                l_platz = st.selectbox("Platz", PITCHES_SPIEL)
            with lc2:
                l_datum = st.date_input("Datum", value=date.today())
            l_grund = st.text_input("Sperrgrund", placeholder="z. B. Platz zu nass")
            bc1, bc2 = st.columns(2)
            with bc1:
                lock_btn   = st.form_submit_button("🔒 Sperren",    type="primary",    use_container_width=True)
            with bc2:
                unlock_btn = st.form_submit_button("🔓 Freigeben",  type="secondary",  use_container_width=True)

            if lock_btn:
                toggle_pitch_lock(l_platz, l_datum, l_grund, True)
                st.success(f"✅ {l_platz} am {l_datum.strftime('%d.%m.%Y')} gesperrt.")
            if unlock_btn:
                toggle_pitch_lock(l_platz, l_datum, l_grund, False)
                st.success(f"✅ {l_platz} am {l_datum.strftime('%d.%m.%Y')} freigegeben.")

    with col_list:
        st.subheader("Aktive Sperren")
        conn    = db_connect()
        df_lk   = pd.read_sql(
            "SELECT * FROM platz_sperren WHERE gesperrt=1 ORDER BY datum", conn
        )
        conn.close()
        if df_lk.empty:
            st.info("Keine aktiven Sperren.")
        else:
            for _, lk in df_lk.iterrows():
                st.markdown(
                    f'<div class="lock-card">'
                    f'<b style="color:#ff4d6d;">🚫 {lk["platz"]}</b>'
                    f'<div style="color:#fc8181;font-size:12px;margin-top:6px;">'
                    f'📅 {lk["datum"]}<br>📝 {lk["grund"] or "Kein Grund angegeben"}</div>'
                    "</div>",
                    unsafe_allow_html=True,
                )

    st.divider()
    st.subheader(f"Tagesstatus – {date.today().strftime('%d.%m.%Y')}")
    locked_today = get_locked_pitches(date.today())
    sc           = st.columns(len(PITCHES))
    for col, platz in zip(sc, PITCHES):
        with col:
            if platz in locked_today:
                st.markdown(
                    f'<div class="status-card-locked">'
                    f'<div style="font-size:26px;">🚫</div>'
                    f'<div style="color:#ff4d6d;font-weight:bold;font-size:11px;margin:6px 0;">'
                    f"{platz}</div>"
                    f'<div style="color:#fc8181;font-size:10px;">GESPERRT</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="status-card-ok">'
                    f'<div style="font-size:26px;">✅</div>'
                    f'<div style="color:#C8102E;font-weight:bold;font-size:11px;margin:6px 0;">'
                    f"{platz}</div>"
                    f'<div style="color:#888;font-size:10px;">VERFÜGBAR</div></div>',
                    unsafe_allow_html=True,
                )


def page_statistiken() -> None:
    st.markdown(
        '<div class="main-header"><h1>📊 Saisonstatistiken</h1>'
        '<p>Trainingsausfälle &amp; Spielbilanz</p></div>',
        unsafe_allow_html=True,
    )

    all_m     = get_all_matches()
    today_ts  = pd.Timestamp(date.today())
    upcoming_count = past_count = 0
    if not all_m.empty:
        all_m["datum_dt"]  = pd.to_datetime(all_m["datum"])
        upcoming_count = int((all_m["datum_dt"] >= today_ts).sum())
        past_count     = len(all_m) - upcoming_count

    c1, c2, c3 = st.columns(3)
    c1.metric("Gesamt Spiele", len(all_m))
    c2.metric("Bevorstehend",  upcoming_count)
    c3.metric("Gespielt",      past_count)

    st.divider()
    st.subheader("Trainingsausfälle je Team")
    stats_df = get_cancellation_stats()
    if stats_df.empty:
        st.info("Noch keine Trainingsausfälle erfasst.")
    else:
        card_cols = st.columns(min(len(stats_df), 5))
        for i, (col, (_, row)) in enumerate(zip(card_cols, stats_df.iterrows())):
            val_color = "#C8102E" if i == 0 else "#aaa"
            with col:
                st.markdown(
                    f'<div class="stat-card">'
                    f'<div style="font-size:34px;font-weight:bold;color:{val_color};">'
                    f'{int(row["ausfaelle"])}</div>'
                    f'<div style="color:#1a1a1a;font-size:13px;margin-top:8px;">{row["team"]}</div>'
                    f'<div style="color:#888;font-size:11px;">Ausfälle</div></div>',
                    unsafe_allow_html=True,
                )
        st.divider()
        chart_df = stats_df.set_index("team")[["ausfaelle"]]
        chart_df.columns = ["Ausfälle"]
        st.bar_chart(chart_df, use_container_width=True, color="#C8102E")


def page_einstellungen() -> None:
    st.markdown(
        '<div class="main-header"><h1>⚙️ Einstellungen</h1>'
        '<p>Admin-PIN, E-Mail-Konfiguration &amp; Systeminfo</p></div>',
        unsafe_allow_html=True,
    )

    tab_pin, tab_ms, tab_mail, tab_info = st.tabs(
        ["🔑 Admin-PIN", "🔷 Microsoft-Login", "📧 E-Mail / SMTP", "ℹ️ System-Info"]
    )

    # ── PIN ───────────────────────────────────────────────────────────────────
    with tab_pin:
        st.subheader("Admin-PIN ändern")
        with st.form("pin_form"):
            cur_pin  = st.text_input("Aktueller PIN",       type="password")
            new_pin  = st.text_input("Neuer PIN",            type="password")
            new_pin2 = st.text_input("Neuen PIN bestätigen", type="password")

            if st.form_submit_button("PIN ändern", type="primary"):
                stored = get_setting("admin_pin")
                if cur_pin != stored:
                    st.error("Aktueller PIN ist falsch.")
                elif new_pin != new_pin2:
                    st.error("Neue PINs stimmen nicht überein.")
                elif len(new_pin) < 4:
                    st.error("PIN muss mindestens 4 Zeichen haben.")
                else:
                    set_setting("admin_pin", new_pin)
                    st.success("✅ PIN erfolgreich geändert.")

    # ── Microsoft-Login ───────────────────────────────────────────────────────
    with tab_ms:
        st.subheader("Microsoft-Login (Azure AD / Entra ID)")
        st.markdown(
            "Tragen Sie hier die Daten Ihrer **Azure App-Registrierung** ein. "
            "Danach erscheint auf der Login-Seite der Button **🔷 Mit Microsoft anmelden**."
        )
        st.divider()
        with st.form("ms_form"):
            ms_cid  = st.text_input("Application (Client) ID",
                                    value=get_setting("ms_client_id"),
                                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
            ms_tid  = st.text_input("Directory (Tenant) ID",
                                    value=get_setting("ms_tenant_id") or "common",
                                    placeholder="common  oder  xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
            ms_sec  = st.text_input("Client Secret",
                                    value=get_setting("ms_client_secret"),
                                    type="password",
                                    placeholder="Leer = Public-Client (PKCE nicht unterstützt)")
            ms_ruri = st.text_input("Redirect URI",
                                    value=get_setting("ms_redirect_uri") or "http://localhost:8501",
                                    placeholder="http://localhost:8501")
            ms_adm  = st.text_area("Admin-E-Mail-Adressen",
                                   value=get_setting("admin_emails"),
                                   placeholder="admin@fctm.de\nvorstand@fctm.de",
                                   help="Eine Adresse pro Zeile. Diese erhalten vollen Admin-Zugang.")
            ms_kord = st.text_area("Koordinatoren-E-Mail-Adressen",
                                   value=get_setting("koordinator_emails") or "",
                                   placeholder="koordinator@fctm.de\nspielausschuss@fctm.de",
                                   help="Eine Adresse pro Zeile. Koordinatoren sehen Dashboard, Anfragen und Spiel anlegen – aber keine Systemeinstellungen oder Saisonplanung.")
            if st.form_submit_button("💾 Speichern", type="primary"):
                set_setting("ms_client_id",     ms_cid.strip())
                set_setting("ms_tenant_id",     ms_tid.strip() or "common")
                set_setting("ms_client_secret", ms_sec.strip())
                set_setting("ms_redirect_uri",  ms_ruri.strip())
                set_setting("admin_emails",     ms_adm.strip())
                set_setting("koordinator_emails", ms_kord.strip())
                st.success("✅ Microsoft-Login-Einstellungen gespeichert.")
                st.rerun()

        with st.expander("📖 Azure App-Registrierung einrichten (Schritt für Schritt)"):
            st.markdown("""
1. **Azure Portal** öffnen: [portal.azure.com](https://portal.azure.com)
2. **Microsoft Entra ID → App-Registrierungen → Neue Registrierung**
3. Name: z. B. `FCTM Spielbetrieb`
4. Kontotypen: *Nur Konten in diesem Organisationsverzeichnis*
5. Redirect URI: `Web` → Ihre Streamlit-URL (z. B. `http://localhost:8501`)
6. Nach Erstellung: **Application (Client) ID** und **Directory (Tenant) ID** kopieren
7. Unter **Zertifikate & Geheimnisse → Neuer geheimer Clientschlüssel** erstellen
8. Unter **API-Berechtigungen**: `openid`, `profile`, `email` sind standardmäßig vorhanden
""")

    # ── E-Mail / SMTP ─────────────────────────────────────────────────────────
    with tab_mail:
        st.subheader("E-Mail-Benachrichtigungen")
        st.markdown(
            "Spielanfragen und genehmigte Spiele werden automatisch an ein "
            "**Funktionspostfach** gesendet. Die Mail enthält alle Spieldetails "
            "und einen **Hinweis zur DFBnet-Eintragung durch den Ansetzer**."
        )
        if get_setting("ms_client_id") and get_setting("ms_client_secret"):
            st.success(
                "🔷 **Microsoft Graph API aktiv** – Mails werden über die Azure App "
                "versendet (kein SMTP-Passwort erforderlich). "
                "SMTP-Felder werden als Fallback ignoriert."
            )
        st.divider()

        cfg = _email_cfg()
        with st.form("email_form"):
            e_aktiv = st.toggle(
                "E-Mail-Versand aktivieren",
                value=(cfg.get("email_aktiv", "0") == "1"),
            )
            ec1, ec2 = st.columns([3, 1])
            with ec1:
                e_host = st.text_input(
                    "SMTP-Server",
                    value=cfg.get("email_smtp_host", ""),
                    placeholder="z. B. smtp.office365.com",
                )
            with ec2:
                e_port = st.number_input(
                    "Port",
                    value=int(cfg.get("email_smtp_port", 587) or 587),
                    min_value=1, max_value=65535,
                )
            eu1, eu2 = st.columns(2)
            with eu1:
                e_user = st.text_input(
                    "SMTP-Benutzername",
                    value=cfg.get("email_smtp_user", ""),
                    placeholder="spielbetrieb@verein.de",
                )
            with eu2:
                e_pass = st.text_input(
                    "SMTP-Passwort",
                    value=cfg.get("email_smtp_pass", ""),
                    type="password",
                )
            e_abs = st.text_input(
                "Absender-Adresse (From)",
                value=cfg.get("email_absender", ""),
                placeholder="spielbetrieb@verein.de",
                help="Leer lassen → SMTP-Benutzername wird verwendet.",
            )
            e_emp = st.text_input(
                "Empfänger / Funktionspostfach (kommagetrennt)",
                value=cfg.get("email_empfaenger", ""),
                placeholder="ansetzer@verein.de, vorstand@verein.de",
            )

            sc1, sc2 = st.columns(2)
            with sc1:
                saved = st.form_submit_button(
                    "💾 Einstellungen speichern", type="primary", use_container_width=True
                )
            with sc2:
                tested = st.form_submit_button(
                    "📨 Test-E-Mail senden", type="secondary", use_container_width=True
                )

            if saved or tested:
                set_setting("email_aktiv",     "1" if e_aktiv else "0")
                set_setting("email_smtp_host", e_host)
                set_setting("email_smtp_port", str(e_port))
                set_setting("email_smtp_user", e_user)
                set_setting("email_smtp_pass", e_pass)
                set_setting("email_absender",  e_abs)
                set_setting("email_empfaenger",e_emp)
                if saved:
                    st.success("✅ E-Mail-Einstellungen gespeichert.")

            if tested:
                if not e_aktiv:
                    st.warning("Versand ist deaktiviert – bitte zuerst aktivieren.")
                else:
                    test_html = _mail_anfrage_html(
                        0, date.today(), "15:00", "Rasen vorne",
                        "Testheim FC", "Gastclub SV",
                        "Kabine 1", "Dies ist eine Test-Nachricht.",
                        ["U19", "1. Mannschaft"], typ="TEST-Nachricht",
                    )
                    ok, err = send_email(
                        "[FCTM] Test-E-Mail – Konfigurationsprüfung", test_html
                    )
                    if ok:
                        st.success(f"✅ Test-E-Mail erfolgreich gesendet an: {e_emp}")
                    else:
                        st.error(f"❌ Fehler beim Senden: {err}")

        # Info-Box zu gängigen Anbietern
        with st.expander("💡 SMTP-Einstellungen gängiger Anbieter"):
            st.markdown("""
| Anbieter | SMTP-Server | Port | Hinweis |
|---|---|---|---|
| **Office 365 / Microsoft** | `smtp.office365.com` | `587` | STARTTLS |
| **Gmail** | `smtp.gmail.com` | `587` | App-Passwort erforderlich |
| **GMX** | `mail.gmx.net` | `587` | STARTTLS |
| **Web.de** | `smtp.web.de` | `587` | STARTTLS |
| **IONOS / 1&1** | `smtp.ionos.de` | `587` | STARTTLS |
            """)

    # ── System-Info ───────────────────────────────────────────────────────────
    with tab_info:
        st.subheader("System-Info")
        conn  = db_connect()
        n_sp  = conn.execute("SELECT COUNT(*) FROM spiele").fetchone()[0]
        n_an  = conn.execute("SELECT COUNT(*) FROM spielanfragen").fetchone()[0]
        n_sa  = conn.execute("SELECT COUNT(*) FROM saisonplanung").fetchone()[0]
        conn.close()
        ci1, ci2, ci3 = st.columns(3)
        ci1.metric("Spiele in DB",       n_sp)
        ci2.metric("Anfragen in DB",     n_an)
        ci3.metric("Saisonplaneinträge", n_sa)


# ---------------------------------------------------------------------------
# Login-Seite
# ---------------------------------------------------------------------------

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
        ms_client_id  = get_setting("ms_client_id")
        redirect_uri  = get_setting("ms_redirect_uri") or "http://localhost:8501"

        if ms_client_id:
            # ── Microsoft-Login (primäre Option) ──────────────────────────
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
                pin_input = st.text_input(
                    "Admin-PIN", type="password", placeholder="PIN eingeben …",
                    key="login_pin",
                )
                if st.button("🔑 Als Admin einloggen", use_container_width=True):
                    if pin_input == get_setting("admin_pin"):
                        st.session_state.role = "admin"
                        st.session_state.ms_name = ""
                        st.rerun()
                    else:
                        st.error("Falscher PIN.")
        else:
            # ── Klassischer Login (Microsoft nicht konfiguriert) ───────────
            tab_u, tab_a = st.tabs(["👤 Als Benutzer", "🔑 Als Administrator"])

            with tab_u:
                st.markdown(
                    '<p style="color:#555;font-size:13px;text-align:center;margin:12px 0;">'
                    "Benutzer können den Trainingsplan einsehen und Spielanfragen stellen."
                    "</p>",
                    unsafe_allow_html=True,
                )
                _conn_t = db_connect()
                _teams_db = [r[0] for r in _conn_t.execute(
                    "SELECT DISTINCT team FROM saisonplanung "
                    "WHERE team IS NOT NULL AND team != '' ORDER BY team"
                ).fetchall()]
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
                pin_input = st.text_input(
                    "Admin-PIN", type="password", placeholder="PIN eingeben …",
                    key="login_pin",
                )
                if st.button("🔑 Als Admin einloggen", use_container_width=True):
                    if pin_input == get_setting("admin_pin"):
                        st.session_state.role = "admin"
                        st.rerun()
                    else:
                        st.error("Falscher PIN.")


# ---------------------------------------------------------------------------
# Haupt-App
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="FCTM – Spielbetrieb",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    init_db()

    # ── Cookie-Controller (muss früh initialisiert werden) ──────────────────
    _cookies = CookieController()

    # ── OAuth-Callback (Microsoft-Login) ────────────────────────────────────
    _params = st.query_params
    if "code" in _params and not st.session_state.get("role"):
        _redirect_uri = get_setting("ms_redirect_uri") or "http://localhost:8501"
        _result = ms_exchange_code(_params["code"], _redirect_uri)
        st.query_params.clear()
        if _result and "id_token_claims" in _result:
            _claims = _result["id_token_claims"]
            _email  = (_claims.get("preferred_username") or _claims.get("email") or "").strip()
            _name   = _claims.get("name", _email)
            _role, _team = ms_role_from_email(_email)
            if _role:
                _token = session_save(_role, _team, _name, _email)
                _cookies.set(_COOKIE_NAME, _token, max_age=_COOKIE_MAX_AGE)
                st.session_state.role     = _role
                st.session_state.team     = _team
                st.session_state.ms_name  = _name
                st.session_state.ms_email = _email
                st.session_state["_session_token"] = _token
                st.rerun()
            else:
                st.error(f"⛔ Kein Zugang für **{_email}**. Bitte den Administrator kontaktieren.")
                st.stop()
        else:
            st.error("❌ Microsoft-Anmeldung fehlgeschlagen. Bitte erneut versuchen.")
            st.stop()

    # Session initialisieren
    if "role" not in st.session_state:
        st.session_state.role = None
        # Cookie prüfen → Session wiederherstellen
        _token = _cookies.get(_COOKIE_NAME)
        if _token:
            _sess = session_load(_token)
            if _sess:
                st.session_state.role     = _sess["role"]
                st.session_state.team     = _sess["team"]
                st.session_state.ms_name  = _sess["ms_name"]
                st.session_state.ms_email = _sess["ms_email"]
                st.session_state["_session_token"] = _token

    # Trainingsdaten immer frisch laden (damit neue Einträge sofort sichtbar sind)
    # Fußball-Saison: August–Juni → vor Juli = laufende Saison beginnt im Vorjahr
    _y = date.today().year
    _m = date.today().month
    saison_default = f"{_y - 1}/{_y}" if _m < 7 else f"{_y}/{_y + 1}"
    sp = get_saisonplanung(saison_default)
    if not sp.empty:
        sp_ren = sp.rename(columns={
            "team": "Team", "platz": "Platz",
            "tag":  "Tag",  "zeit":  "Zeit",  "kabine": "Kabine",
        })
        def _bereich(p: str) -> str:
            if "Kunstrasen" in p: return "Kunstrasen"
            if "Wigger"     in p: return "Wigger-Arena"
            return "Rasen"
        sp_ren["Bereich"] = sp_ren["Platz"].apply(_bereich)
        st.session_state.training_df = sp_ren[["Platz","Bereich","Tag","Zeit","Team"]]
    else:
        st.session_state.training_df = pd.DataFrame(
            columns=["Platz","Bereich","Tag","Zeit","Team"]
        )

    # Nicht eingeloggt → Login
    if st.session_state.role is None:
        page_login()
        return

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        role       = st.session_state.role
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
        team_line = (
            f'<br><span style="color:#ffdada;font-size:12px;">⚽ {my_team_sb}</span>'
            if role == "benutzer" and my_team_sb else ""
        )
        st.markdown(
            '<div style="text-align:center;padding:16px 0 10px 0;">'
            '<span style="font-size:40px;">⚽</span><br>'
            '<span style="color:#fff;font-size:18px;font-weight:bold;">FCTM</span><br>'
            '<span style="color:#ffdada;font-size:11px;">Spielbetrieb-Manager</span><br>'
            f'<div style="margin-top:8px;">{badge_html}</div>'
            f'{team_line}'
            + (f'<br><span style="color:#aad4f5;font-size:11px;">'
               f'🔷 {st.session_state.get("ms_name","")}'
               f'</span>'
               if st.session_state.get("ms_name") else "")
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
            options = [
                "📋 Trainingsplan",
                "📨 Meine Anfragen",
            ]

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
        st.caption("Version 2.1.0 · FCTM")

    # ── Routing ───────────────────────────────────────────────────────────────
    routing = {
        "📅 Dashboard":           page_admin_dashboard,
        "📨 Anfragen verwalten":  page_anfragen_verwalten,
        "📨 Anfragen verwalten 🔴": page_anfragen_verwalten,
        "➕ Spiel anlegen":        page_admin_spiel_anlegen,
        "📋 Trainingsplan":        page_trainingsplan_view,
        "📆 Saisonplanung":        page_saisonplanung,
        "🔒 Platzverwaltung":      page_platzverwaltung,
        "📊 Statistiken":          page_statistiken,
        "⚙️ Einstellungen":        page_einstellungen,
        "📨 Meine Anfragen": page_user_anfrage,
    }
    routing.get(page, page_trainingsplan_view)()


if __name__ == "__main__":
    main()
