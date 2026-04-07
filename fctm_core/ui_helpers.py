"""UI-Hilfsmittel: CSS-Theme und Badge-Renderer."""


# ---------------------------------------------------------------------------
# CSS – Vereinsfarben Rot & Weiß (Light-Mode)
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



def _anfrage_timeline_html(typ: str, status: str) -> str:
    """Gibt eine mini HTML-Timeline für den Anfrage-Workflow zurück."""
    steps = [
        ("ausstehend",        "⏳", "Ausstehend"),
        ("dfbnet_ausstehend", "✅", "Genehmigt"),
        ("abgeschlossen",     "🏁", "Abgeschlossen"),
    ]
    if status == "abgelehnt":
        steps = [
            ("ausstehend", "⏳", "Ausstehend"),
            ("abgelehnt",  "❌", "Abgelehnt"),
        ]
    elif typ == "allgemein":
        steps = [
            ("ausstehend",    "⏳", "Ausstehend"),
            ("abgeschlossen", "✅", "Beantwortet"),
        ]

    items = []
    reached = False
    for s_key, s_icon, s_label in steps:
        if s_key == status:
            reached = True
            color, fw = "#c00000", "bold"
        elif not reached:
            color, fw = "#22c55e", "normal"
        else:
            color, fw = "#cccccc", "normal"
        items.append(
            f'<span style="color:{color};font-weight:{fw};font-size:11px;'
            f'white-space:nowrap;">{s_icon} {s_label}</span>'
        )
    arrow = '<span style="color:#cccccc;font-size:11px;"> → </span>'
    return (
        f'<div style="margin-top:6px;padding:4px 0;">'
        + arrow.join(items)
        + '</div>'
    )
