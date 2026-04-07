import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .storage import db_connect, get_setting


def _email_cfg() -> dict:
    keys = [
        "email_aktiv", "email_smtp_host", "email_smtp_port",
        "email_smtp_user", "email_smtp_pass",
        "email_absender", "email_empfaenger",
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
    import requests as _req

    client_id = get_setting("ms_client_id")
    tenant_id = get_setting("ms_tenant_id") or "common"
    client_secret = get_setting("ms_client_secret")
    if not client_id or not client_secret:
        return False, "Microsoft Graph nicht konfiguriert."

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_resp = _req.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        return False, f"Token-Fehler: {token_resp.text}"
    access_token = token_resp.json().get("access_token", "")

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
    cfg = _email_cfg()
    if cfg.get("email_aktiv", "0") != "1":
        return False, "E-Mail-Versand nicht aktiviert."
    absender = cfg.get("email_absender", "") or cfg.get("email_smtp_user", "")
    if to:
        empfaenger = [e.strip() for e in to.split(",") if e.strip()]
    else:
        empfaenger = [e.strip() for e in cfg.get("email_empfaenger", "").split(",") if e.strip()]
    if not empfaenger:
        return False, "Kein Empfänger konfiguriert."

    if get_setting("ms_client_id") and get_setting("ms_client_secret"):
        return _graph_send(betreff, html_body, absender, empfaenger)

    host = cfg.get("email_smtp_host", "")
    port = int(cfg.get("email_smtp_port", 587) or 587)
    user = cfg.get("email_smtp_user", "")
    password = cfg.get("email_smtp_pass", "")
    if not host:
        return False, "SMTP-Host fehlt."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = betreff
    msg["From"] = absender
    msg["To"] = ", ".join(empfaenger)
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


def _mail_trainer_html(datum: date, uhrzeit: str, platz: str, heimteam: str, gastteam: str, kabine: str, team_trainer: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <body style=\"font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;\">
      <div style=\"max-width:600px;margin:0 auto;background:#fff;
                  border-radius:12px;overflow:hidden;
                  box-shadow:0 2px 12px rgba(0,0,0,.15);\">
        <div style=\"background:#C8102E;padding:24px 28px;\">
          <h1 style=\"margin:0;color:#fff;font-size:22px;\">⚽ Spielbestätigung</h1>
          <p style=\"margin:4px 0 0 0;color:#ffd6dc;font-size:14px;\">
            Dein Training entfällt – hier sind alle Details
          </p>
        </div>
        <div style=\"padding:24px 28px;\">
          <p style=\"color:#333;\">Hallo{' ' + team_trainer if team_trainer else ''},</p>
          <p style=\"color:#333;\">
            für den folgenden Termin wurde ein Pflichtspiel angesetzt.
            Das Spiel ist bereits <b>im DFBnet eingetragen</b> und kann auch
            über <a href=\"https://www.fussball.de\" style=\"color:#C8102E;\">fussball.de</a>
            eingesehen werden.
          </p>
          <table style=\"width:100%;border-collapse:collapse;margin:16px 0;\">
            <tr style=\"background:#fafafa;\">
              <td style=\"padding:8px;color:#888;width:140px;\">Datum</td>
              <td style=\"padding:8px;font-weight:bold;\">{datum.strftime('%A, %d.%m.%Y')}</td></tr>
            <tr>
              <td style=\"padding:8px;color:#888;\">Anstoßzeit</td>
              <td style=\"padding:8px;font-weight:bold;\">{uhrzeit} Uhr</td></tr>
            <tr style=\"background:#fafafa;\">
              <td style=\"padding:8px;color:#888;\">Platz</td>
              <td style=\"padding:8px;font-weight:bold;\">{platz}</td></tr>
            <tr>
              <td style=\"padding:8px;color:#888;\">Heimteam</td>
              <td style=\"padding:8px;font-weight:bold;\">{heimteam}</td></tr>
            <tr style=\"background:#fafafa;\">
              <td style=\"padding:8px;color:#888;\">Gastteam</td>
              <td style=\"padding:8px;font-weight:bold;\">{gastteam}</td></tr>
            <tr>
              <td style=\"padding:8px;color:#888;\">Kabine</td>
              <td style=\"padding:8px;\">{kabine or '–'}</td></tr>
          </table>
          <div style=\"background:#e8f0fe;border-left:4px solid #C8102E;
                      padding:14px 16px;border-radius:6px;margin:16px 0;\">
            <b style=\"color:#C8102E;\">✅ Alles erledigt – kein weiterer Handlungsbedarf</b>
          </div>
        </div>
      </div>
    </body>
    </html>
    """


def _mail_trainer_aenderung_html(datum_alt: date, uhrzeit_alt: str, platz_alt: str, kabine_alt: str, datum_neu: date, uhrzeit_neu: str, platz_neu: str, kabine_neu: str, heimteam: str, gastteam: str) -> str:
    def row(label: str, alt: str, neu: str) -> str:
        changed = alt != neu
        farbe = "#f0a500" if changed else "#333"
        return (
            f"<tr><td style='padding:8px;color:#888;width:130px;'>{label}</td>"
            f"<td style='padding:8px;text-decoration:line-through;color:#999;'>{alt}</td>"
            f"<td style='padding:8px;font-weight:bold;color:{farbe};'>{neu}</td></tr>"
        )
    return f"""
    <!DOCTYPE html><html><body style='font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;'>
      <div style='max-width:620px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;'>
        <div style='background:#f0a500;padding:24px 28px;'><h1 style='margin:0;color:#fff;font-size:22px;'>✏️ Spieländerung</h1></div>
        <div style='padding:24px 28px;'>
          <p><b>⚽ {heimteam} vs {gastteam}</b></p>
          <table style='width:100%;border-collapse:collapse;margin:16px 0;'>
            <tr style='background:#eee;'><th style='padding:8px;text-align:left;'>Feld</th><th style='padding:8px;text-align:left;'>Alt</th><th style='padding:8px;text-align:left;'>Neu</th></tr>
            {row('Datum', datum_alt.strftime('%d.%m.%Y'), datum_neu.strftime('%d.%m.%Y'))}
            {row('Uhrzeit', uhrzeit_alt, uhrzeit_neu)}
            {row('Platz', platz_alt, platz_neu)}
            {row('Kabine', kabine_alt or '–', kabine_neu or '–')}
          </table>
        </div>
      </div>
    </body></html>
    """


def _mail_trainer_stornierung_html(datum: date, uhrzeit: str, platz: str, heimteam: str, gastteam: str, grund: str) -> str:
    return f"""
    <!DOCTYPE html><html><body style='font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;'>
      <div style='max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;'>
        <div style='background:#ef4444;padding:24px 28px;'><h1 style='margin:0;color:#fff;font-size:22px;'>❌ Spielabsage</h1></div>
        <div style='padding:24px 28px;'>
          <p><b>{heimteam} vs {gastteam}</b> · {datum.strftime('%d.%m.%Y')} · {uhrzeit} · {platz}</p>
          {f'<p><b>Grund:</b> {grund}</p>' if grund else ''}
        </div>
      </div>
    </body></html>
    """


def _mail_anfrage_html(anfrage_id: int, datum: date, uhrzeit: str, platz: str, heimteam: str, gastteam: str, kabine: str, notizen: str, konflikte: list[str], typ: str = "Neue Spielanfrage") -> str:
    konflikt_block = ""
    if konflikte:
        items = "".join(f"<li>{t}</li>" for t in konflikte)
        konflikt_block = f"<div style='background:#fff3cd;border-left:4px solid #e0a800;padding:12px 16px;border-radius:6px;margin:16px 0;'><b>⚠️ Trainingskonflikt</b><ul>{items}</ul></div>"
    return f"""
    <!DOCTYPE html><html><body style='font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;'>
      <div style='max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;'>
        <div style='background:#C8102E;padding:24px 28px;'><h1 style='margin:0;color:#fff;font-size:22px;'>⚽ FCTM – {typ}</h1></div>
        <div style='padding:24px 28px;'>
          <p><b>Anfrage #{anfrage_id}</b></p>
          <p>{datum.strftime('%d.%m.%Y')} · {uhrzeit} · {platz}</p>
          <p>{heimteam} vs {gastteam}</p>
          <p>Kabine: {kabine or '–'}</p>
          {f'<p>Notizen: {notizen}</p>' if notizen else ''}
          {konflikt_block}
        </div>
      </div>
    </body></html>
    """


def _mail_ablehnung_html(anfrage_id: int, typ: str, heimteam: str, gastteam: str, datum_str: str, uhrzeit: str, platz: str, grund: str) -> str:
    return f"""
    <!DOCTYPE html><html><body style='font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;'>
      <div style='max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;'>
        <div style='background:#ef4444;padding:24px 28px;'><h1 style='margin:0;color:#fff;font-size:22px;'>❌ Anfrage abgelehnt</h1></div>
        <div style='padding:24px 28px;'><p>Anfrage #{anfrage_id}</p><p>{heimteam} vs {gastteam} · {datum_str} {uhrzeit} · {platz}</p><p><b>Grund:</b> {grund}</p></div>
      </div>
    </body></html>
    """


def _mail_antwort_html(anfrage_id: int, team: str, betreff: str, antwort: str) -> str:
    return f"""
    <!DOCTYPE html><html><body style='font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;'>
      <div style='max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;'>
        <div style='background:#10b981;padding:24px 28px;'><h1 style='margin:0;color:#fff;font-size:22px;'>💬 Antwort vom Spielbetrieb</h1></div>
        <div style='padding:24px 28px;'><p>Anfrage #{anfrage_id} · {team}</p><p><b>{betreff}</b></p><p style='white-space:pre-wrap;'>{antwort}</p></div>
      </div>
    </body></html>
    """
