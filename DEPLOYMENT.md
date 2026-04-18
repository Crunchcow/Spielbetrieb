# Spielbetrieb – Deployment

## Projekt-Info

| | |
|---|---|
| **Stack** | Python + Streamlit + Flask (OIDC-Callback) |
| **Datenbank** | SQLite (`fctm.db`, lokal auf dem Server – **nicht im Repo**) |
| **Server** | `89.167.0.28` – Hostname: `WestfaliaOsterwick` (Ubuntu 24.04) |
| **App-Pfad** | `/var/www/spielbetrieb/` |
| **Services** | `spielbetrieb.service` (Streamlit, Port 8505) · `spielbetrieb-callback.service` (Flask, Port 8504) |
| **Nginx** | `/etc/nginx/sites-enabled/spielbetrieb` – öffentlicher Port **8503** |
| **URL** | `http://89.167.0.28:8503` · `https://spielbetrieb.westfalia-osterwick.de` (nach DNS) |

### Architektur

```
Browser → nginx :8503 (öffentlich)
            ├─ /callback → Flask :8504  (OIDC-Exchange, Cookie setzen)
            └─ /         → Streamlit :8505 (App, liest Cookie)
```

---

## Update deployen (nach jedem `git push`)

```bash
ssh root@89.167.0.28 "cd /var/www/spielbetrieb && git fetch origin && git reset --hard origin/main && cp nginx.conf /etc/nginx/sites-available/spielbetrieb && systemctl restart spielbetrieb spielbetrieb-callback && nginx -t && systemctl reload nginx"
```

---

## DNS-Eintrag (noch ausstehend)

Damit SSL funktioniert, muss ein **A-Record** gesetzt werden:

| Name | Typ | Wert |
|------|-----|------|
| `spielbetrieb` | A | `89.167.0.28` |

Danach SSL-Zertifikat holen:
```bash
ssh root@89.167.0.28
certbot --nginx -d spielbetrieb.westfalia-osterwick.de --non-interactive --agree-tos -m lemke@westfalia-osterwick.de --redirect
```

---

## Nützliche Befehle auf dem Server

```bash
# Service-Status
systemctl status spielbetrieb spielbetrieb-callback

# Logs live
journalctl -u spielbetrieb -f
journalctl -u spielbetrieb-callback -f

# Nginx neu laden
nginx -t && systemctl reload nginx
```

---

## Offene Punkte

- [ ] DNS-Eintrag `spielbetrieb.westfalia-osterwick.de` → `89.167.0.28` setzen
- [ ] SSL via Certbot einrichten (Befehl s. o.)

---

## Lokale Entwicklung

```bash
cd Spielbetrieb
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
streamlit run app.py
```

Aufruf im Browser: `http://localhost:8501`
