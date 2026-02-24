"""
FCTM – Football Club Training & Match Management System
========================================================
Vereinsfarben: Rot (#C8102E) & Weiß
Rollen: Admin (vollständiger Zugriff) · Benutzer (Anfragen & Trainingsplan)
"""

import io
import smtplib
import sqlite3
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------
DB_PATH = "fctm.db"
DEFAULT_ADMIN_PIN = "1234"

DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

TIME_SLOTS_TRAINING = [f"{h:02d}:{m:02d}" for h in range(8, 22) for m in (0, 30)]

# Platzhälften – nur für Trainingszwecke
PITCHES = [
    "Rasen vorne",
    "Rasen hinten",
    "Kunstrasen vorne",
    "Kunstrasen hinten",
    "Wigger-Arena",
]

# Gesamtplätze – für Spielansetzungen (immer ganzer Platz)
PITCHES_SPIEL = [
    "Rasen",
    "Kunstrasen",
    "Wigger-Arena",
]

# Mapping: Gesamtplatz → Training-Hälften für Konflikt-Erkennung
PITCH_HALVES: dict[str, list[str]] = {
    "Rasen":      ["Rasen vorne",      "Rasen hinten"],
    "Kunstrasen": ["Kunstrasen vorne", "Kunstrasen hinten"],
    "Wigger-Arena": ["Wigger-Arena"],
}

LOCKER_ROOMS = [f"Kabine {i}" for i in range(1, 7)]  # 6 Kabinen

# ---------------------------------------------------------------------------
# CSS – Vereinsfarben Rot & Weiß
# ---------------------------------------------------------------------------
CSS = """
<style>
/* ─── Basis ────────────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0d0003 !important;
    color: #f0f0f0;
}
[data-testid="stSidebar"] {
    background: #130005 !important;
    border-right: 1px solid #5c0010;
}
[data-testid="stSidebar"] * { color: #f0f0f0 !important; }

/* ─── Header-Banner ───────────────────────────────────────────────────── */
.main-header {
    background: linear-gradient(135deg, #6b0010 0%, #9b0018 40%, #C8102E 100%);
    padding: 22px 28px;
    border-radius: 14px;
    margin-bottom: 22px;
    border: 1px solid #e8344a;
    box-shadow: 0 4px 20px rgba(200,16,46,0.4);
}
.main-header h1 { margin:0; font-size:26px; color:#ffffff;
                  text-shadow:0 1px 4px rgba(0,0,0,.4); }
.main-header p  { margin:4px 0 0 0; opacity:.8; color:#ffd6dc; font-size:14px; }

/* ─── Login ───────────────────────────────────────────────────────────── */
.login-box {
    background: linear-gradient(160deg, #1a0005 0%, #2d0010 100%);
    border: 2px solid #C8102E;
    border-radius: 18px;
    padding: 40px 36px;
    max-width: 440px;
    margin: 60px auto 0 auto;
    box-shadow: 0 8px 32px rgba(200,16,46,.5);
    text-align: center;
}
.login-box h2 { color:#ffffff; font-size:22px; margin-bottom:6px; }
.login-box p  { color:#ffa0b0; font-size:13px; margin-bottom:24px; }

/* ─── Rollen-Badge ────────────────────────────────────────────────────── */
.role-badge-admin {
    display:inline-block; padding:3px 14px; border-radius:20px;
    background:#C8102E; color:#fff; font-size:12px; font-weight:bold;
}
.role-badge-user {
    display:inline-block; padding:3px 14px; border-radius:20px;
    background:#2d0010; color:#ffa0b0; border:1px solid #C8102E;
    font-size:12px; font-weight:bold;
}

/* ─── Slot-Karten Dashboard ───────────────────────────────────────────── */
.slot-card {
    border-radius:7px; padding:7px 10px; margin:3px 0;
    color:#f0f0f0; font-size:12px; font-weight:500; line-height:1.4;
}
.slot-training { background:#2d0010; border-left:4px solid #C8102E; }
.slot-match    { background:#1a1400; border-left:4px solid #f0a500; }
.slot-locked   { background:#4a0000; border-left:4px solid #ff0000;
                 text-align:center; font-weight:bold; }
.slot-free     { background:#130005; border-left:4px solid #3a0010;
                 color:#6c3040; text-align:center; }

/* ─── Tages-Header ────────────────────────────────────────────────────── */
.day-header {
    padding:6px 4px; border-radius:7px; text-align:center;
    margin-bottom:6px; font-size:11px; font-weight:bold; color:white;
}

/* ─── Status-Karten ───────────────────────────────────────────────────── */
.status-card-ok {
    background:#1a0005; border:2px solid #C8102E; border-radius:10px;
    padding:16px; text-align:center; min-height:110px;
}
.status-card-locked {
    background:#3d0000; border:2px solid #ff0000; border-radius:10px;
    padding:16px; text-align:center; min-height:110px;
}

/* ─── Anfrage-Karten ──────────────────────────────────────────────────── */
.anfrage-card {
    background:#1a0005; border:1px solid #5c0010;
    border-radius:10px; padding:13px 16px; margin-bottom:9px;
}
.anfrage-offen    { border-left:4px solid #f0a500; }
.anfrage-ok       { border-left:4px solid #22c55e; }
.anfrage-abgelehnt{ border-left:4px solid #ef4444; }

/* ─── Match-Karte ─────────────────────────────────────────────────────── */
.match-card {
    background:#1a0005; border:1px solid #5c0010;
    border-radius:10px; padding:13px 16px; margin-bottom:9px;
}

/* ─── Sperr-Karte ─────────────────────────────────────────────────────── */
.lock-card {
    background:#3d0000; border:1px solid #ff0000;
    border-radius:10px; padding:13px 16px; margin-bottom:8px;
}

/* ─── Kabinen-Karten ──────────────────────────────────────────────────── */
.locker-busy {
    background:#1a0005; border:2px solid #C8102E; border-radius:10px;
    padding:15px; text-align:center; min-height:130px;
}
.locker-free {
    background:#0d0003; border:2px dashed #3a0010; border-radius:10px;
    padding:15px; text-align:center; min-height:130px;
}
.locker-conflict {
    background:#4a0000; border:2px solid #ff0000; border-radius:10px;
    padding:15px; text-align:center; min-height:130px;
    animation: pulse 1.5s infinite;
}
@keyframes pulse {
    0%   { box-shadow:0 0 0 0   rgba(255,0,0,.4); }
    70%  { box-shadow:0 0 0 10px rgba(255,0,0,0);  }
    100% { box-shadow:0 0 0 0   rgba(255,0,0,0);   }
}

/* ─── Stat-Karte ──────────────────────────────────────────────────────── */
.stat-card {
    background:#1a0005; border:1px solid #5c0010;
    border-radius:12px; padding:20px; text-align:center;
}

/* ─── Duplikat-Warnung ────────────────────────────────────────────────── */
.duplicate-warning {
    background:#4a0000; border:2px solid #ff4444;
    border-radius:10px; padding:14px 18px; margin:8px 0;
}

/* ─── Streamlit overrides ─────────────────────────────────────────────── */
.stButton > button {
    background:#C8102E !important; color:#fff !important;
    border:none !important; border-radius:8px !important;
}
.stButton > button:hover { background:#a00020 !important; }
.stButton > button[kind="secondary"] {
    background:#2d0010 !important; color:#ffa0b0 !important;
    border:1px solid #C8102E !important;
}
.stButton > button[kind="secondary"]:hover { background:#3d0018 !important; }
div[data-testid="stMetric"] {
    background:#1a0005; border:1px solid #5c0010;
    border-radius:10px; padding:12px;
}
.stTextInput input, .stTextArea textarea,
[data-baseweb="select"] { background:#1a0005 !important;
                           color:#f0f0f0 !important; border-color:#5c0010 !important; }
hr { border-color:#3a0010 !important; }
.stDataFrame { background:#1a0005; }
.stAlert { border-radius:10px !important; }
</style>
"""

# ---------------------------------------------------------------------------
# Datenbank
# ---------------------------------------------------------------------------

def db_connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db() -> None:
    conn = db_connect()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS einstellungen (
            schluessel TEXT PRIMARY KEY,
            wert       TEXT
        );
        CREATE TABLE IF NOT EXISTS spiele (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            datum         TEXT NOT NULL,
            uhrzeit       TEXT NOT NULL,
            platz         TEXT NOT NULL,
            heimteam      TEXT,
            gastteam      TEXT,
            kabine        TEXT,
            notizen       TEXT,
            erstellt_am   TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS spielanfragen (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            datum         TEXT NOT NULL,
            uhrzeit       TEXT NOT NULL,
            platz         TEXT NOT NULL,
            heimteam      TEXT,
            gastteam      TEXT,
            kabine        TEXT,
            notizen       TEXT,
            status        TEXT DEFAULT 'ausstehend',
            bearbeiter    TEXT,
            erstellt_am   TEXT DEFAULT CURRENT_TIMESTAMP,
            bearbeitet_am TEXT
        );
        CREATE TABLE IF NOT EXISTS platz_sperren (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            platz    TEXT NOT NULL,
            datum    TEXT NOT NULL,
            grund    TEXT,
            gesperrt INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS training_ausfaelle (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            team     TEXT NOT NULL,
            datum    TEXT NOT NULL,
            uhrzeit  TEXT NOT NULL,
            platz    TEXT NOT NULL,
            spiel_id INTEGER,
            FOREIGN KEY (spiel_id) REFERENCES spiele(id)
        );
        CREATE TABLE IF NOT EXISTS saisonplanung (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            team          TEXT NOT NULL,
            platz         TEXT NOT NULL,
            tag           TEXT NOT NULL,
            zeit          TEXT NOT NULL,
            kabine        TEXT,
            trainer_email TEXT,
            saison        TEXT
        );
    """)
    # Migrationen für bestehende DBs
    for migration in [
        "ALTER TABLE spiele ADD COLUMN dfbnet_eingetragen INTEGER DEFAULT 0",
        "ALTER TABLE saisonplanung ADD COLUMN trainer_email TEXT",
        "ALTER TABLE saisonplanung ADD COLUMN zeit_ende TEXT",
    ]:
        try:
            conn.execute(migration)
        except sqlite3.OperationalError:
            pass  # Spalte existiert bereits
    defaults = [
        ("admin_pin",       DEFAULT_ADMIN_PIN),
        ("email_aktiv",     "0"),
        ("email_smtp_host", ""),
        ("email_smtp_port", "587"),
        ("email_smtp_user", ""),
        ("email_smtp_pass", ""),
        ("email_absender",  ""),
        ("email_empfaenger",""),
    ]
    for key, val in defaults:
        c.execute(
            "INSERT OR IGNORE INTO einstellungen (schluessel, wert) VALUES (?,?)",
            (key, val),
        )
    conn.commit()
    conn.close()


# ── Einstellungen ─────────────────────────────────────────────────────────────

def get_setting(key: str) -> str | None:
    conn = db_connect()
    row = conn.execute(
        "SELECT wert FROM einstellungen WHERE schluessel=?", (key,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def set_setting(key: str, value: str) -> None:
    conn = db_connect()
    conn.execute(
        "INSERT OR REPLACE INTO einstellungen (schluessel, wert) VALUES (?,?)",
        (key, value),
    )
    conn.commit()
    conn.close()


# ── Spiele ────────────────────────────────────────────────────────────────────

def save_match(datum, uhrzeit, platz, heimteam, gastteam, kabine, notizen, betroffene) -> int:
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spiele (datum,uhrzeit,platz,heimteam,gastteam,kabine,notizen) "
        "VALUES (?,?,?,?,?,?,?)",
        (datum.isoformat(), uhrzeit, platz, heimteam, gastteam, kabine, notizen),
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


def send_email(betreff: str, html_body: str, to: str | None = None) -> tuple[bool, str]:
    """
    Sendet eine HTML-E-Mail.
    `to`: optionale Empfänger-Adresse (überschreibt Funktionspostfach).
    Gibt (True, "") bei Erfolg oder (False, Fehlermeldung) zurück.
    """
    cfg = _email_cfg()
    if cfg.get("email_aktiv", "0") != "1":
        return False, "E-Mail-Versand nicht aktiviert."
    host       = cfg.get("email_smtp_host", "")
    port       = int(cfg.get("email_smtp_port", 587) or 587)
    user       = cfg.get("email_smtp_user", "")
    password   = cfg.get("email_smtp_pass", "")
    absender   = cfg.get("email_absender",  "") or user
    if to:
        empfaenger = [e.strip() for e in to.split(",") if e.strip()]
    else:
        empfaenger = [e.strip() for e in cfg.get("email_empfaenger", "").split(",") if e.strip()]

    if not host or not empfaenger:
        return False, "SMTP-Host oder Empfänger fehlt."

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
            Bitte diese Trainer kontaktieren und Zustimmung einholen.
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


# ── Spielanfragen ─────────────────────────────────────────────────────────────

def create_spielanfrage(datum, uhrzeit, platz, heimteam, gastteam, kabine, notizen) -> int:
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen (datum,uhrzeit,platz,heimteam,gastteam,kabine,notizen) "
        "VALUES (?,?,?,?,?,?,?)",
        (datum.isoformat(), uhrzeit, platz, heimteam, gastteam, kabine, notizen),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def get_all_anfragen() -> pd.DataFrame:
    conn = db_connect()
    df = pd.read_sql("SELECT * FROM spielanfragen ORDER BY datum,uhrzeit", conn)
    conn.close()
    return df


def update_anfrage_status(aid: int, status: str, bearbeiter: str) -> None:
    conn = db_connect()
    conn.execute(
        "UPDATE spielanfragen "
        "SET status=?, bearbeiter=?, bearbeitet_am=datetime('now') WHERE id=?",
        (status, bearbeiter, aid),
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
    Jetzt wird das Spiel ins Dashboard übernommen, Status → abgeschlossen.
    Gibt die neue Spiel-ID zurück.
    """
    conn = db_connect()
    row = conn.execute("SELECT * FROM spielanfragen WHERE id=?", (aid,)).fetchone()
    conn.close()
    if not row:
        return -1
    cols = [
        "id","datum","uhrzeit","platz","heimteam","gastteam",
        "kabine","notizen","status","bearbeiter","erstellt_am","bearbeitet_am",
    ]
    r = dict(zip(cols, row))
    # betroffene Teams aus training_ausfaelle holen falls schon gespeichert (leer OK)
    sid = save_match(
        date.fromisoformat(r["datum"]), r["uhrzeit"], r["platz"],
        r["heimteam"] or "", r["gastteam"] or "",
        r["kabine"] or "", r["notizen"] or "", [],
    )
    # dfbnet_eingetragen Flag setzen
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
        "dfbnet_ausstehend": ("#7c3aed", "📋", "DFBnet offen"),
        "abgeschlossen":     ("#22c55e", "✅", "Abgeschlossen"),
        "abgelehnt":         ("#ef4444", "❌", "Abgelehnt"),
        "genehmigt":         ("#22c55e", "✅", "Genehmigt"),
    }
    farbe, icon, label = meta.get(status, ("#888", "?", status.capitalize()))
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

    # Automatisch aus DB laden falls noch nichts im Session-State
    df_training = st.session_state.get("training_df", pd.DataFrame())
    if df_training.empty:
        saison_key  = f"{date.today().year}/{date.today().year + 1}"
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
        sel_day   = st.selectbox("Tag",   ["Alle"] + DAYS)
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
        days_show = DAYS if sel_day == "Alle" else [sel_day]
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
    st.markdown(
        '<div class="main-header"><h1>📨 Spielanfrage stellen</h1>'
        '<p>Anfrage für ein neues Spiel einreichen – der Admin prüft und genehmigt</p></div>',
        unsafe_allow_html=True,
    )

    df_training = st.session_state.get("training_df", pd.DataFrame())
    col_form, col_list = st.columns([3, 2])

    with col_form:
        with st.form("anfrage_form"):
            st.subheader("Anfrage Details")
            fc1, fc2 = st.columns(2)
            with fc1:
                f_datum   = st.date_input("Datum", value=date.today())
            with fc2:
                f_uhrzeit = st.selectbox("Anstoßzeit", TIME_SLOTS_TRAINING)

            f_platz = st.selectbox("Platz", PITCHES_SPIEL)
            fc3, fc4 = st.columns(2)
            with fc3:
                f_heim = st.text_input("Heimteam", placeholder="z. B. 1. Mannschaft")
            with fc4:
                f_gast = st.text_input("Gastteam",  placeholder="z. B. FC Muster")

            freie_kabinen = get_free_kabinen(f_datum, f_uhrzeit)
            belegt_count  = len(LOCKER_ROOMS) - len(freie_kabinen)
            if belegt_count:
                st.info(
                    f"🚳 {belegt_count} Kabine(n) durch Training belegt – "
                    f"nur freie Kabinen zur Auswahl."
                )
            kc1, kc2 = st.columns(2)
            with kc1:
                f_kabine_heim = st.selectbox(
                    "🏠 Kabine Heimmannschaft", freie_kabinen, key="kh"
                )
            with kc2:
                rest_gast = [k for k in freie_kabinen if k != f_kabine_heim]
                f_kabine_gast = st.selectbox(
                    "✈️ Kabine Gastmannschaft",
                    rest_gast if rest_gast else freie_kabinen,
                    key="kg",
                )
            f_notizen = st.text_area("Notizen / Anmerkungen")

            conflicts = find_conflicts(df_training, f_datum, f_uhrzeit, f_platz)
            if conflicts:
                st.warning(
                    f"⚠️ Hinweis: **{', '.join(conflicts)}** trainieren zu diesem Zeitpunkt "
                    "auf diesem Platz. Der Admin prüft die Zustimmung der Trainer."
                )

            if st.form_submit_button("📨 Anfrage absenden", type="primary", use_container_width=True):
                if not f_heim.strip() or not f_gast.strip():
                    st.error("Bitte Heim- und Gastteam eintragen.")
                elif f_kabine_heim == f_kabine_gast:
                    st.error("Heim- und Gastmannschaft können nicht dieselbe Kabine nutzen.")
                else:
                    f_kabine = f"{f_kabine_heim} / {f_kabine_gast}"
                    rid = create_spielanfrage(
                        f_datum, f_uhrzeit, f_platz, f_heim, f_gast, f_kabine, f_notizen,
                    )
                    st.success(f"✅ Anfrage #{rid} erfolgreich eingereicht!")
                    # ── E-Mail an Funktionspostfach ──────────────────────────
                    html = _mail_anfrage_html(
                        rid, f_datum, f_uhrzeit, f_platz,
                        f_heim, f_gast, f_kabine, f_notizen,
                        conflicts, typ="Neue Spielanfrage",
                    )
                    ok, err = send_email(
                        f"[FCTM] Neue Spielanfrage #{rid}: {f_heim} vs {f_gast} "
                        f"({f_datum.strftime('%d.%m.%Y')})",
                        html,
                    )
                    if ok:
                        st.info("📧 Benachrichtigung an das Funktionspostfach gesendet.")
                    elif err != "E-Mail-Versand nicht aktiviert.":
                        st.warning(f"📧 E-Mail konnte nicht gesendet werden: {err}")

    with col_list:
        st.subheader("📋 Bisherige Anfragen")
        alle = get_all_anfragen()
        if alle.empty:
            st.info("Noch keine Anfragen vorhanden.")
        else:
            for _, r in alle.iterrows():
                css_extra = {
                    "ausstehend": "anfrage-offen",
                    "genehmigt":  "anfrage-ok",
                    "abgelehnt":  "anfrage-abgelehnt",
                }.get(r["status"], "")
                st.markdown(
                    f'<div class="anfrage-card {css_extra}">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="color:#f0f0f0;font-weight:bold;">'
                    f'⚽ {r["heimteam"]} vs {r["gastteam"]}</span>'
                    f'{status_badge(r["status"])}</div>'
                    f'<div style="color:#aaa;font-size:12px;margin-top:6px;">'
                    f'📅 {r["datum"]} &nbsp;|&nbsp; ⏰ {r["uhrzeit"]} '
                    f'&nbsp;|&nbsp; 🏟️ {r["platz"]} &nbsp;|&nbsp; '
                    f'🚿 {r.get("kabine","–")}</div>'
                    "</div>",
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

    c1, c2, _ = st.columns([1, 1, 2])
    with c1:
        sel_date  = st.date_input("Woche ab", value=date.today())
    with c2:
        sel_pitch = st.selectbox("Platz", ["Alle"] + PITCHES)

    week_start  = sel_date - timedelta(days=sel_date.weekday())
    week_dates  = [week_start + timedelta(days=i) for i in range(7)]
    df_training = st.session_state.get("training_df", pd.DataFrame())
    show_pitches = PITCHES if sel_pitch == "Alle" else [sel_pitch]

    # Legende
    st.markdown(
        '<div style="margin:8px 0 18px 0;">'
        '<span style="background:#C8102E;color:#fff;padding:3px 12px;'
        'border-radius:20px;font-size:12px;margin-right:6px;">● Training</span>'
        '<span style="background:#8a6300;color:#fff;padding:3px 12px;'
        'border-radius:20px;font-size:12px;margin-right:6px;">● Spiel</span>'
        '<span style="background:#4a0000;color:#fff;padding:3px 12px;'
        'border-radius:20px;font-size:12px;margin-right:6px;">● Gesperrt</span>'
        '<span style="background:#1a0005;color:#6c3040;padding:3px 12px;'
        'border-radius:20px;font-size:12px;border:1px solid #3a0010;">● Frei</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    for platz in show_pitches:
        st.markdown(f"### 🏟️ {platz}")
        day_cols = st.columns(7)
        for i, (col, cur_date) in enumerate(zip(day_cols, week_dates)):
            day_name   = DAYS[i]
            is_locked  = platz in get_locked_pitches(cur_date)
            is_today   = cur_date == date.today()
            with col:
                hdr_bg = "#C8102E" if is_today else "#3a0010"
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
    badge = status_badge(r["status"])
    bear  = f' &nbsp;|&nbsp; 👤 {r["bearbeiter"]}' if r.get("bearbeiter") else ""
    return (
        f'<div class="anfrage-card">'
        f'<div style="display:flex;justify-content:space-between;">'
        f'<span style="color:#f0f0f0;">#{r["id"]} – {r["heimteam"]} vs {r["gastteam"]}</span>'
        f'{badge}</div>'
        f'<div style="color:#aaa;font-size:12px;margin-top:5px;">'
        f'📅 {r["datum"]} &nbsp;|&nbsp; ⏰ {r["uhrzeit"]} &nbsp;|&nbsp; '
        f'🏟️ {r["platz"]}{bear}</div></div>'
    )


def page_anfragen_verwalten() -> None:
    st.markdown(
        '<div class="main-header"><h1>📨 Spielanfragen verwalten</h1>'
        '<p>Neue Anfragen prüfen · DFBnet bestätigen · Trainer benachrichtigen</p></div>',
        unsafe_allow_html=True,
    )

    alle        = get_all_anfragen()
    df_training = st.session_state.get("training_df", pd.DataFrame())

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

    tab_neu, tab_dfb, tab_done = st.tabs(
        [f"⏳ Neue Anfragen ({n_neu})",
         f"📋 DFBnet ausstehend ({n_dfb})",
         f"✅ Abgeschlossen ({n_done})"]
    )

    # ─── TAB 1: Neue Anfragen ────────────────────────────────────────────────
    with tab_neu:
        df_neu = alle[alle["status"] == "ausstehend"] if not alle.empty else pd.DataFrame()
        if df_neu.empty:
            st.info("Keine neuen Anfragen.")
        else:
            for _, r in df_neu.iterrows():
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
                    ic1, ic2, ic3, ic4 = st.columns(4)
                    ic1.markdown(f"**Datum:** {r['datum']}")
                    ic2.markdown(f"**Zeit:** {r['uhrzeit']}")
                    ic3.markdown(f"**Platz:** {r['platz']}")
                    ic4.markdown(f"**Kabine:** {r.get('kabine','–')}")
                    st.markdown(
                        f"**Heim:** {r['heimteam']} &nbsp;|&nbsp; **Gast:** {r['gastteam']}"
                    )
                    if r.get("notizen"):
                        st.markdown(f"*Notiz: {r['notizen']}*")

                    if locked:
                        st.error(f"🚫 Platz **{r['platz']}** ist gesperrt!")
                    if conflicts:
                        st.warning(
                            f"⚠️ Konflikt: **{', '.join(conflicts)}** trainieren zu diesem Zeitpunkt."
                        )
                        approved = st.checkbox(
                            f"✅ Ich bestätige die Zustimmung der betroffenen Trainer:innen "
                            f"(**{', '.join(conflicts)}**).",
                            key=f"chk_{r['id']}",
                        )
                    else:
                        approved = True

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
                                approve_anfrage(r["id"], conflicts if conflicts else [])
                                # Info-Mail ans Funktionspostfach: DFBnet eintragen!
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
                            update_anfrage_status(r["id"], "abgelehnt", "Admin")
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
                        sid = confirm_dfbnet(r["id"])
                        st.success(
                            f"✅ Spiel #{sid} im Dashboard gespeichert, DFBnet bestätigt!"
                        )
                        # Trainer-Mail senden
                        if custom_mail.strip():
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
                                to=custom_mail.strip(),
                            )
                            if ok2:
                                st.info(f"📧 Trainer-Mail an {custom_mail.strip()} gesendet.")
                            elif err2 != "E-Mail-Versand nicht aktiviert.":
                                st.warning(f"📧 Trainer-Mail-Fehler: {err2}")
                        st.balloons()
                        st.rerun()

    # ─── TAB 3: Abgeschlossen / Abgelehnt ───────────────────────────────────
    with tab_done:
        df_done = (
            alle[alle["status"].isin(["abgeschlossen", "abgelehnt", "genehmigt"])]
            if not alle.empty else pd.DataFrame()
        )
        if df_done.empty:
            st.info("Noch keine abgeschlossenen Vorgänge.")
        else:
            for _, r in df_done.iterrows():
                st.markdown(_anfrage_card_html(r), unsafe_allow_html=True)


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
        for _, m in all_m.sort_values("datum_dt").iterrows():
            dfb_ok = m.get("dfbnet_eingetragen", 1)
            dfb_badge = (
                '<span style="background:#22c55e;color:#fff;padding:1px 7px;'
                'border-radius:10px;font-size:10px;">✅ DFBnet</span>'
                if dfb_ok else
                '<span style="background:#7c3aed;color:#fff;padding:1px 7px;'
                'border-radius:10px;font-size:10px;">📋 DFBnet offen</span>'
            )
            st.markdown(
                f'<div class="match-card">'
                f'<div style="display:flex;justify-content:space-between;">'
                f'<span style="color:#ffa0b0;font-size:11px;">'
                f'{m["datum_dt"].strftime("%d.%m.%Y")} · {m["uhrzeit"]} Uhr</span>'
                f'{dfb_badge}</div>'
                f'<div style="color:#fff;font-weight:bold;margin:4px 0;">'
                f'⚽ {m["heimteam"]} vs {m["gastteam"]}</div>'
                f'<div style="color:#888;font-size:12px;">'
                f'🏟️ {m["platz"]} · 🚿 {m.get("kabine","–")}</div>'
                "</div>",
                unsafe_allow_html=True,
            )
    st.divider()
    st.subheader("🗑️ Spiel löschen")
    all_m2 = get_all_matches()
    if not all_m2.empty:
        opts = {
            f"{pd.to_datetime(r['datum']).strftime('%d.%m.%Y')} – "
            f"{r['heimteam']} vs {r['gastteam']}": r["id"]
            for _, r in all_m2.iterrows()
        }
        del_key = st.selectbox("Auswählen", list(opts.keys()))
        if st.button("Löschen", type="secondary", use_container_width=True):
            delete_match(opts[del_key])
            st.rerun()


def page_saisonplanung() -> None:
    st.markdown(
        '<div class="main-header"><h1>📆 Saisonplanung</h1>'
        '<p>Trainingszeiten erfassen · Kabinen zuweisen · Trainer hinterlegen</p></div>',
        unsafe_allow_html=True,
    )

    saison_default = f"{date.today().year}/{date.today().year + 1}"
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
                            f'<div style="font-size:11px;color:#ffd6dc;margin-top:3px;">{t}</div>'
                            for t in teams_in
                        )
                        if teams_in
                        else '<div style="color:#4a1020;font-size:11px;">Frei</div>'
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
                    f'<div style="color:#ffa0b0;font-size:10px;">VERFÜGBAR</div></div>',
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
                    f'<div style="color:#f0f0f0;font-size:13px;margin-top:8px;">{row["team"]}</div>'
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

    tab_pin, tab_mail, tab_info = st.tabs(
        ["🔑 Admin-PIN", "📧 E-Mail / SMTP", "ℹ️ System-Info"]
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

    # ── E-Mail / SMTP ─────────────────────────────────────────────────────────
    with tab_mail:
        st.subheader("E-Mail-Benachrichtigungen")
        st.markdown(
            "Spielanfragen und genehmigte Spiele werden automatisch an ein "
            "**Funktionspostfach** gesendet. Die Mail enthält alle Spieldetails "
            "und einen **Hinweis zur DFBnet-Eintragung durch den Ansetzer**."
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
        tab_u, tab_a = st.tabs(["👤 Als Benutzer", "🔑 Als Administrator"])

        with tab_u:
            st.markdown(
                '<p style="color:#ffa0b0;font-size:13px;text-align:center;margin:12px 0;">'
                "Benutzer können den Trainingsplan einsehen und Spielanfragen stellen."
                "</p>",
                unsafe_allow_html=True,
            )
            if st.button("▶️ Als Benutzer fortfahren", type="primary", use_container_width=True):
                st.session_state.role = "benutzer"
                st.rerun()

        with tab_a:
            st.markdown(
                '<p style="color:#ffa0b0;font-size:13px;text-align:center;margin:12px 0;">'
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
                    st.error("Falscher PIN. Standard-PIN: 1234")


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

    # Session initialisieren
    if "role" not in st.session_state:
        st.session_state.role = None
    if "training_df" not in st.session_state:
        saison_default = f"{date.today().year}/{date.today().year + 1}"
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
        badge_html = (
            '<span class="role-badge-admin">👑 Administrator</span>'
            if role == "admin"
            else '<span class="role-badge-user">👤 Benutzer</span>'
        )
        st.markdown(
            '<div style="text-align:center;padding:16px 0 10px 0;">'
            '<span style="font-size:40px;">⚽</span><br>'
            '<span style="color:#fff;font-size:18px;font-weight:bold;">FCTM</span><br>'
            '<span style="color:#ffa0b0;font-size:11px;">Spielbetrieb-Manager</span><br>'
            f'<div style="margin-top:8px;">{badge_html}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.divider()

        if role == "admin":
            options = [
                "📅 Dashboard",
                "📨 Anfragen verwalten",
                "➕ Spiel anlegen",
                "📋 Trainingsplan",
                "📆 Saisonplanung",
                "🔒 Platzverwaltung",
                "📊 Statistiken",
                "⚙️ Einstellungen",
            ]
        else:
            options = [
                "📋 Trainingsplan",
                "📨 Spielanfrage stellen",
            ]

        page = st.radio("Navigation", options, label_visibility="collapsed")

        df_n = len(st.session_state.training_df)
        if df_n > 0:
            st.caption(f"📋 {df_n} Trainingseinheiten geladen")

        st.divider()
        if st.button("🚪 Abmelden", type="secondary", use_container_width=True):
            st.session_state.role = None
            st.rerun()
        st.caption("Version 2.0.0 · FCTM")

    # ── Routing ───────────────────────────────────────────────────────────────
    routing = {
        "📅 Dashboard":           page_admin_dashboard,
        "📨 Anfragen verwalten":  page_anfragen_verwalten,
        "➕ Spiel anlegen":        page_admin_spiel_anlegen,
        "📋 Trainingsplan":        page_trainingsplan_view,
        "📆 Saisonplanung":        page_saisonplanung,
        "🔒 Platzverwaltung":      page_platzverwaltung,
        "📊 Statistiken":          page_statistiken,
        "⚙️ Einstellungen":        page_einstellungen,
        "📨 Spielanfrage stellen": page_user_anfrage,
    }
    routing.get(page, page_trainingsplan_view)()


if __name__ == "__main__":
    main()
