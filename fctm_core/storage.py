import secrets
import sqlite3

from .constants import DB_PATH, DEFAULT_ADMIN_PIN

_COOKIE_NAME = "fctm_session"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 Tage


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
            quelle        TEXT DEFAULT 'manuell',
            ursprung_anfrage_id INTEGER,
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
        CREATE TABLE IF NOT EXISTS anfrage_notizen (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            anfrage_id  INTEGER NOT NULL,
            notiz       TEXT NOT NULL,
            erstellt_von TEXT,
            erstellt_am TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anfrage_id) REFERENCES spielanfragen(id)
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
        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            role       TEXT NOT NULL,
            team       TEXT,
            ms_name    TEXT,
            ms_email   TEXT,
            erstellt   TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    for migration in [
        "ALTER TABLE spiele ADD COLUMN dfbnet_eingetragen INTEGER DEFAULT 0",
        "ALTER TABLE spiele ADD COLUMN quelle TEXT DEFAULT 'manuell'",
        "ALTER TABLE spiele ADD COLUMN ursprung_anfrage_id INTEGER",
        "ALTER TABLE saisonplanung ADD COLUMN trainer_email TEXT",
        "ALTER TABLE saisonplanung ADD COLUMN zeit_ende TEXT",
        "ALTER TABLE spielanfragen ADD COLUMN anfrage_typ TEXT DEFAULT 'neu'",
        "ALTER TABLE spielanfragen ADD COLUMN spiel_id INTEGER",
        "ALTER TABLE spielanfragen ADD COLUMN neue_uhrzeit TEXT",
        "ALTER TABLE spielanfragen ADD COLUMN neues_datum TEXT",
        "ALTER TABLE spielanfragen ADD COLUMN neuer_platz TEXT",
        "ALTER TABLE spielanfragen ADD COLUMN neue_kabine TEXT",
        "ALTER TABLE spielanfragen ADD COLUMN erstellt_von TEXT",
        "ALTER TABLE spielanfragen ADD COLUMN betreff TEXT",
        "ALTER TABLE spielanfragen ADD COLUMN nachricht TEXT",
        "ALTER TABLE spielanfragen ADD COLUMN bearbeiter_kommentar TEXT",
        "ALTER TABLE spielanfragen ADD COLUMN verwalter_notiz TEXT",
    ]:
        try:
            conn.execute(migration)
        except sqlite3.OperationalError:
            pass

    defaults = [
        ("admin_pin", DEFAULT_ADMIN_PIN),
        ("email_aktiv", "0"),
        ("email_smtp_host", ""),
        ("email_smtp_port", "587"),
        ("email_smtp_user", ""),
        ("email_smtp_pass", ""),
        ("email_absender", ""),
        ("email_empfaenger", ""),
        ("ms_client_id", ""),
        ("ms_tenant_id", "common"),
        ("ms_client_secret", ""),
        ("ms_redirect_uri", "http://localhost:8501"),
        ("admin_emails", "lemke@westfalia-osterwick.de"),
        ("koordinator_emails", "spielbetrieb@westfalia-osterwick.de"),
        ("verwalter_notizen", ""),
    ]
    for key, val in defaults:
        c.execute(
            "INSERT OR IGNORE INTO einstellungen (schluessel, wert) VALUES (?,?)",
            (key, val),
        )

    for key, val in [
        ("admin_emails", "lemke@westfalia-osterwick.de"),
        ("koordinator_emails", "spielbetrieb@westfalia-osterwick.de"),
    ]:
        c.execute(
            "UPDATE einstellungen SET wert=? WHERE schluessel=? AND (wert IS NULL OR wert='')",
            (val, key),
        )

    conn.commit()
    conn.close()


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


def session_save(role: str, team: str, ms_name: str, ms_email: str) -> str:
    token = secrets.token_urlsafe(32)
    conn = db_connect()
    conn.execute(
        "INSERT INTO sessions (token, role, team, ms_name, ms_email) VALUES (?,?,?,?,?)",
        (token, role, team or "", ms_name or "", ms_email or ""),
    )
    conn.commit()
    conn.close()
    return token


def session_load(token: str) -> dict | None:
    if not token:
        return None
    conn = db_connect()
    row = conn.execute(
        "SELECT role, team, ms_name, ms_email FROM sessions "
        "WHERE token=? AND erstellt > datetime('now','-7 days')",
        (token,),
    ).fetchone()
    conn.close()
    if row:
        return {"role": row[0], "team": row[1], "ms_name": row[2], "ms_email": row[3]}
    return None


def session_delete(token: str) -> None:
    if not token:
        return
    conn = db_connect()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()
