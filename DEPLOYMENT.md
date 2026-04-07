# Spielbetrieb – Deployment

## Projekt-Info

| | |
|---|---|
| **Stack** | Python + Streamlit |
| **Datenbank** | SQLite (`fctm.db`, lokal auf dem Server – **nicht im Repo**) |
| **Server** | `89.167.0.28` – Hostname: `WestfaliaOsterwick` (Ubuntu 24.04) |
| **App-Pfad** | `/var/www/spielbetrieb/` |
| **Service** | systemd → `spielbetrieb.service` (Port 8503) |
| **Nginx** | `/etc/nginx/sites-enabled/spielbetrieb` |
| **URL** | `https://spielbetrieb.westfalia-osterwick.de` (nach DNS-Eintrag) |

---

## Update deployen (nach jedem `git push`)

```bash
ssh root@89.167.0.28
cd /var/www/spielbetrieb
git pull origin main
systemctl restart spielbetrieb
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
systemctl status spielbetrieb

# Logs live
journalctl -u spielbetrieb -f

# Nginx neu laden
nginx -t && systemctl reload nginx
```

---

## Offene Punkte

- [ ] DNS-Eintrag `spielbetrieb.westfalia-osterwick.de` → `89.167.0.28` setzen
- [ ] SSL via Certbot einrichten (Befehl s. o.)


## Projekt-Info

| | |
|---|---|
| **Stack** | Python + Streamlit |
| **Datenbank** | SQLite (`fctm.db`, lokal im Projektordner) |
| **Starten (lokal)** | `streamlit run app.py` |

---

## Lokale Entwicklung

```bash
cd Spielbetrieb
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
streamlit run app.py
```

Aufruf im Browser: `http://localhost:8501`

---

## Status: Noch nicht auf Hetzner deployed

Die App läuft bisher nur lokal. Für ein Deployment auf dem Hetzner-Server
(`89.167.0.28`) wären folgende Schritte nötig:

### Option A: Streamlit direkt (ohne Docker)

```bash
# Auf dem Server
cd /var/www/spielbetrieb
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Als Daemon starten (Port 8501 oder nächster freier Port)
nohup streamlit run app.py --server.port 8503 --server.headless true &
```

Nginx-Config ergänzen:
```nginx
server {
    listen 80;
    server_name spielbetrieb.westfalia-osterwick.de;

    location / {
        proxy_pass http://127.0.0.1:8503;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

> **Hinweis Streamlit:** Streamlit benötigt WebSocket-Support im Nginx-Proxy
> (`Upgrade` + `Connection` Header). Ohne diese Header funktioniert die App nicht.

### Option B: Docker

Ein `Dockerfile` wäre die sauberere Lösung für Streamlit auf dem Server,
da Abhängigkeiten sauber isoliert sind.

---

## Offene Punkte vor dem Go-Live

- [ ] `fctm.db` persistieren (nicht im Repo – Pfad in `.env` auslagern)
- [ ] Secrets (Admin-PIN, SMTP-Credentials) aus dem Code in `.env` auslagern
- [ ] DNS-Eintrag `spielbetrieb.westfalia-osterwick.de` → `89.167.0.28`
- [ ] SSL via Certbot einrichten
