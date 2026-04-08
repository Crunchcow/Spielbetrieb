from datetime import date, timedelta

import pandas as pd
import streamlit as st

from fctm_core.constants import (
    DAYS,
    LOCKER_ROOMS,
    PITCHES,
    PITCHES_SPIEL,
    TIME_SLOTS_TRAINING,
    WEEKDAYS_DISPLAY,
)
from fctm_core.domain_service import (
    add_training_slot,
    approve_anfrage,
    confirm_dfbnet,
    create_sample_csv,
    create_spielanfrage,
    delete_match,
    delete_training_slot,
    find_conflicts,
    get_all_anfragen,
    get_all_anfragen_dfbnet,
    get_all_matches,
    get_anfrage_notizen,
    get_cancellation_stats,
    get_free_kabinen,
    get_kabinen_konflikte,
    get_locked_pitches,
    get_matches_for_date,
    get_saisonplanung,
    get_trainer_email_for_team,
    load_training_df_from_db,
    parse_trainingsplan,
    save_anfrage_notiz,
    save_saisonplanung,
    toggle_pitch_lock,
    update_anfrage_status,
    update_kabinen_und_emails,
    update_match_details,
)
from fctm_core.mail_service import (
    _email_cfg,
    _mail_ablehnung_html,
    _mail_anfrage_html,
    _mail_antwort_html,
    _mail_trainer_aenderung_html,
    _mail_trainer_html,
    _mail_trainer_stornierung_html,
    send_email,
)
from fctm_core.storage import db_connect, get_setting, set_setting
from fctm_core.ui_helpers import status_badge, typ_badge


def page_admin_dashboard() -> None:
    st.markdown(
        '<div class="main-header"><h1>📅 Admin Dashboard</h1>'
        '<p>Vollständige Wochenübersicht – Training, Spiele &amp; Sperren</p></div>',
        unsafe_allow_html=True,
    )

    # Verwalter-Notizen
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

    alle_anf = get_all_anfragen()
    n_neu = len(alle_anf[alle_anf["status"] == "ausstehend"]) if not alle_anf.empty else 0
    n_dfb = len(alle_anf[alle_anf["status"] == "dfbnet_ausstehend"]) if not alle_anf.empty else 0

    if not alle_anf.empty and n_neu > 0:
        _offen = alle_anf[alle_anf["status"] == "ausstehend"]
        n_neu_frei = len(_offen[_offen["anfrage_typ"] == "allgemein"]) if "anfrage_typ" in _offen.columns else 0
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
        karten_html += "</div>"
        st.markdown(karten_html, unsafe_allow_html=True)

        if n_neu > 0:
            with st.expander(f"⏳ Ausstehende Anfragen anzeigen ({n_neu})", expanded=True):
                offene = alle_anf[alle_anf["status"] == "ausstehend"].sort_values("erstellt_am", ascending=False).head(5)
                for _, r in offene.iterrows():
                    t_anf = r.get("anfrage_typ") or "neu"
                    tb = typ_badge(t_anf)
                    if t_anf == "allgemein":
                        titel_str = (r.get("betreff") or r.get("notizen") or "Freie Anfrage")[:55]
                        meta_str = f'💬 von {r.get("erstellt_von","?")}' if r.get("erstellt_von") else "💬 Freie Anfrage"
                    else:
                        datum_str = pd.to_datetime(r["datum"]).strftime("%d.%m.%Y") if r.get("datum") else "–"
                        titel_str = f'{r["heimteam"]} vs {r["gastteam"]}'
                        meta_str = f'📅 {datum_str} · {r["uhrzeit"]} · {r["platz"]}'
                    st.markdown(
                        f'<div style="background:#f8f8f8;border-radius:6px;padding:10px 14px;'
                        f'margin-bottom:6px;border-left:3px solid #c00000;'
                        f'display:flex;align-items:center;gap:8px;">'
                        f'{tb} &nbsp;'
                        f'<span><b style="color:#1a1a1a;">#{r["id"]} – {titel_str}</b>'
                        f'<span style="color:#666;font-size:12px;margin-left:10px;">{meta_str}</span>'
                        f"</span></div>",
                        unsafe_allow_html=True,
                    )
                if n_neu > 5:
                    st.caption(f"… und {n_neu - 5} weitere. Alle unter **📨 Anfragen verwalten**.")
    else:
        st.success("✅ Keine offenen Anfragen – alles erledigt.")

    st.divider()

    c1, c2, _ = st.columns([1, 1, 2])
    with c1:
        sel_date = st.date_input("Woche ab", value=date.today())
    with c2:
        sel_pitch = st.selectbox("Platz", ["Alle"] + PITCHES)

    week_start = sel_date - timedelta(days=sel_date.weekday())
    week_dates = [week_start + timedelta(days=i) for i in range(5)]
    df_training = st.session_state.get("training_df", pd.DataFrame())
    show_pitches = PITCHES if sel_pitch == "Alle" else [sel_pitch]
    st.caption("Die Wochenansicht zeigt bewusst nur Montag bis Freitag. Wochenendspiele koennen weiterhin beantragt und verarbeitet werden, ohne dass ein kompletter Spielplan manuell gepflegt werden muss.")

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
            day_name = WEEKDAYS_DISPLAY[i]
            is_locked = platz in get_locked_pitches(cur_date)
            is_today = cur_date == date.today()
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
                m_pitch = matches_day[matches_day["platz"] == platz] if not matches_day.empty else pd.DataFrame()
                t_day = (
                    df_training[(df_training["Platz"] == platz) & (df_training["Tag"] == day_name)]
                    if not df_training.empty
                    else pd.DataFrame()
                )

                blocks: list[str] = []
                for _, entry in t_day.iterrows():
                    conflict = not m_pitch.empty and entry["Zeit"] in m_pitch["uhrzeit"].values
                    css = "slot-match" if conflict else "slot-training"
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
                    st.markdown('<div class="slot-card slot-free">–</div>', unsafe_allow_html=True)
        st.divider()


def _anfrage_card_html(r: pd.Series) -> str:
    badge = status_badge(r["status"])
    t_badge = typ_badge(r.get("anfrage_typ") or "neu")
    bear = f' &nbsp;|&nbsp; 👤 {r["bearbeiter"]}' if r.get("bearbeiter") else ""
    t_typ = r.get("anfrage_typ") or "neu"

    if t_typ == "allgemein":
        betreff_txt = r.get("betreff") or r.get("notizen") or "Freie Anfrage"
        von_txt = f' &nbsp;|&nbsp; ✉️ {r["erstellt_von"]}' if r.get("erstellt_von") else ""
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

    alle_raw = get_all_anfragen()
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
                typ_optionen += sorted([t for t in alle_raw["anfrage_typ"].fillna("neu").unique().tolist() if t])
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
            "id",
            "heimteam",
            "gastteam",
            "status",
            "anfrage_typ",
            "erstellt_von",
            "betreff",
            "nachricht",
            "notizen",
            "verwalter_notiz",
            "bearbeiter_kommentar",
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
        n_neu = len(alle[alle["status"] == "ausstehend"])
        n_dfb = len(alle[alle["status"] == "dfbnet_ausstehend"])
        n_done = len(alle[alle["status"].isin(["abgeschlossen", "abgelehnt", "genehmigt"])])

    c1, c2, c3 = st.columns(3)
    c1.metric("⏳ Neu", n_neu)
    c2.metric("📋 DFBnet offen", n_dfb)
    c3.metric("✅ Abgeschlossen", n_done)

    def _render_verwalter_notizblock(r: pd.Series, key_prefix: str) -> None:
        aid = int(r["id"])
        current_notiz = (r.get("verwalter_notiz") or "").strip()
        with st.expander("📝 Verwalter-Notiz", expanded=bool(current_notiz)):
            neu = st.text_area(
                "Interne Notiz",
                value=current_notiz,
                key=f"{key_prefix}_note_{aid}",
                height=80,
                placeholder="Interne Notiz für andere Verwalter …",
            )
            c_save, c_show = st.columns([1, 1])
            with c_save:
                if st.button("💾 Notiz speichern", key=f"{key_prefix}_save_{aid}", use_container_width=True):
                    save_anfrage_notiz(aid, neu, st.session_state.get("ms_name") or "Admin")
                    st.success("Notiz gespeichert.")
                    st.rerun()
            with c_show:
                if st.button("📜 Historie", key=f"{key_prefix}_hist_{aid}", use_container_width=True):
                    hist = get_anfrage_notizen(aid, limit=10)
                    if hist.empty:
                        st.info("Noch keine Notiz-Historie vorhanden.")
                    else:
                        for _, h in hist.iterrows():
                            st.caption(f"{h.get('erstellt_am','')} · {h.get('erstellt_von','?')}: {h.get('notiz','')}")

    tab_neu_label = f"🔴 Neue Anfragen ({n_neu})"
    tab_dfb_label = f"🔵 DFBnet ausstehend ({n_dfb})"
    tab_done_label = f"⚪ Abgeschlossen ({n_done})"

    if hide_done:
        tab_neu, tab_dfb = st.tabs([tab_neu_label, tab_dfb_label])
    else:
        tab_neu, tab_dfb, tab_done = st.tabs([tab_neu_label, tab_dfb_label, tab_done_label])

    with tab_neu:
        df_neu = alle[alle["status"] == "ausstehend"] if not alle.empty else pd.DataFrame()
        if df_neu.empty:
            st.info("Keine neuen Anfragen.")
        else:
            for _, r in df_neu.iterrows():
                t_typ = r.get("anfrage_typ") or "neu"

                if t_typ == "allgemein":
                    betreff_txt = r.get("betreff") or r.get("notizen") or "Freie Anfrage"
                    with st.expander(
                        f"💬 #{r['id']} – Freie Anfrage von " f"{r.get('erstellt_von','?')}: {betreff_txt[:60]}",
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
                            if st.button("✅ Zur Kenntnis genommen", key=f"ok_{r['id']}", type="primary", use_container_width=True):
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
                                            f"[WOHU] 💬 Antwort auf Ihre Anfrage #{r['id']}: {betreff_txt[:50]}",
                                            antwort_html,
                                            to=trainer_email,
                                        )
                                        if ok_a:
                                            st.info(f"📧 Antwort-Mail an {trainer_email} gesendet.")
                                        elif err_a != "E-Mail-Versand nicht aktiviert.":
                                            st.warning(f"📧 Mail-Fehler: {err_a}")
                                st.rerun()
                        with ba2:
                            if st.button("❌ Ablehnen", key=f"no_{r['id']}", type="secondary", use_container_width=True):
                                if not frei_abl_grund.strip():
                                    st.error("Bitte einen Ablehnungsgrund eingeben.")
                                else:
                                    bearbeiter_name = st.session_state.get("ms_name") or "Admin"
                                    update_anfrage_status(r["id"], "abgelehnt", bearbeiter_name, kommentar=frei_abl_grund.strip())
                                    trainer_email = get_trainer_email_for_team(r.get("erstellt_von", ""))
                                    if trainer_email:
                                        abl_html = _mail_ablehnung_html(r["id"], "allgemein", "", "", "", "", "", frei_abl_grund.strip())
                                        ok_a, err_a = send_email(
                                            f"[WOHU] ❌ Anfrage #{r['id']} abgelehnt: {betreff_txt[:50]}",
                                            abl_html,
                                            to=trainer_email,
                                        )
                                        if ok_a:
                                            st.info(f"📧 Ablehnungs-Mail an {trainer_email} gesendet.")
                                        elif err_a != "E-Mail-Versand nicht aktiviert.":
                                            st.warning(f"📧 Mail-Fehler: {err_a}")
                                    st.rerun()
                    continue

                conflicts = find_conflicts(df_training, date.fromisoformat(r["datum"]), r["uhrzeit"], r["platz"])
                locked = r["platz"] in get_locked_pitches(date.fromisoformat(r["datum"]))

                with st.expander(
                    f"#{r['id']} – {r['heimteam']} vs {r['gastteam']}  |  "
                    f"{r['datum']} {r['uhrzeit']}  |  {r['platz']}",
                    expanded=True,
                ):
                    st.markdown(typ_badge(t_typ), unsafe_allow_html=True)
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
                                            f" &nbsp;→&nbsp; <b>{nd} {nu}" f'{(" · " + np_) if np_ and np_ != rm["platz"] else ""}' f"</b>"
                                        )
                                st.markdown(
                                    f'<div style="background:#fffbea;border-left:3px solid #d08000;'
                                    f'padding:6px 10px;border-radius:4px;margin-bottom:8px;'
                                    f'font-size:12px;color:#5a3e00;">'
                                    f'Referenzspiel #{rm["id"]}: '
                                    f'{rm["heimteam"]} vs {rm["gastteam"]} · '
                                    f'{rm["datum"]} {rm["uhrzeit"]} · {rm["platz"]}'
                                    f"{new_hint}</div>",
                                    unsafe_allow_html=True,
                                )
                    ic1, ic2, ic3, ic4 = st.columns(4)
                    ic1.markdown(f"**Datum:** {r['datum']}")
                    ic2.markdown(f"**Zeit:** {r['uhrzeit']}")
                    ic3.markdown(f"**Platz:** {r['platz']}")
                    ic4.markdown(f"**Kabine:** {r.get('kabine','–')}")
                    st.markdown(f"**Heim:** {r['heimteam']} &nbsp;|&nbsp; **Gast:** {r['gastteam']}")
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

                    if t_typ in ("neu", "aenderung", "verlegung", "uhrzeit_aenderung"):
                        ziel_datum = r.get("neues_datum") or r["datum"]
                        ziel_uhrzeit = r.get("neue_uhrzeit") or r["uhrzeit"]
                        freie_k_gen = get_free_kabinen(date.fromisoformat(ziel_datum), ziel_uhrzeit) if ziel_datum and isinstance(ziel_datum, str) else []
                        gen_kc1, gen_kc2 = st.columns(2)
                        with gen_kc1:
                            gen_kab_h = st.selectbox("🏠 Kabine Heim", freie_k_gen, key=f"gkh_{r['id']}")
                        with gen_kc2:
                            rest_gen = [k for k in freie_k_gen if k != gen_kab_h]
                            gen_kab_g = st.selectbox("✈️ Kabine Gast", rest_gen if rest_gen else freie_k_gen, key=f"gkg_{r['id']}")

                    abl_grund = st.text_input(
                        "Ablehnungsgrund (bei Ablehnung erforderlich)",
                        key=f"abl_{r['id']}",
                        placeholder="z. B. Platzkonflikt, Terminüberschneidung, fehlende Absprache …",
                    )
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        if st.button("📋 Genehmigen → DFBnet eintragen", key=f"ok_{r['id']}", use_container_width=True):
                            if locked:
                                st.error("Platz gesperrt – Genehmigung nicht möglich.")
                            elif conflicts and not approved:
                                st.error("Bitte Trainer-Zustimmung bestätigen.")
                            else:
                                if t_typ in ("neu", "aenderung", "verlegung", "uhrzeit_aenderung"):
                                    kabine_gen = f"{gen_kab_h} / {gen_kab_g}"
                                    _kconn = db_connect()
                                    if t_typ in ("aenderung", "verlegung", "uhrzeit_aenderung"):
                                        _kconn.execute("UPDATE spielanfragen SET neue_kabine=? WHERE id=?", (kabine_gen, r["id"]))
                                    else:
                                        _kconn.execute("UPDATE spielanfragen SET kabine=? WHERE id=?", (kabine_gen, r["id"]))
                                    _kconn.commit()
                                    _kconn.close()
                                approve_anfrage(r["id"], conflicts if conflicts else [])
                                html = _mail_anfrage_html(
                                    r["id"],
                                    date.fromisoformat(r["datum"]),
                                    r["uhrzeit"],
                                    r["platz"],
                                    r["heimteam"],
                                    r["gastteam"],
                                    r.get("kabine", ""),
                                    r.get("notizen", ""),
                                    conflicts if conflicts else [],
                                    typ="Spielanfrage GENEHMIGT – JETZT IN DFBNET EINTRAGEN!",
                                )
                                ok, err = send_email(
                                    f"[WOHU] 📋 DFBnet eintragen: " f"{r['heimteam']} vs {r['gastteam']} ({r['datum']})",
                                    html,
                                )
                                if ok:
                                    st.info("📧 Hinweis-Mail ans Funktionspostfach gesendet.")
                                elif err != "E-Mail-Versand nicht aktiviert.":
                                    st.warning(f"📧 E-Mail-Fehler: {err}")
                                st.rerun()
                    with bc2:
                        if st.button("❌ Ablehnen", key=f"no_{r['id']}", type="secondary", use_container_width=True):
                            if not abl_grund.strip():
                                st.error("Bitte einen Ablehnungsgrund eingeben.")
                            else:
                                bearbeiter_name = st.session_state.get("ms_name") or "Admin"
                                update_anfrage_status(r["id"], "abgelehnt", bearbeiter_name, kommentar=abl_grund.strip())
                                trainer_email = get_trainer_email_for_team(r["heimteam"])
                                if trainer_email:
                                    abl_html = _mail_ablehnung_html(
                                        r["id"],
                                        r.get("anfrage_typ", "neu"),
                                        r["heimteam"],
                                        r["gastteam"],
                                        r["datum"],
                                        r["uhrzeit"],
                                        r["platz"],
                                        abl_grund.strip(),
                                    )
                                    ok_a, err_a = send_email(
                                        f"[WOHU] ❌ Anfrage #{r['id']} abgelehnt: " f"{r['heimteam']} vs {r['gastteam']}",
                                        abl_html,
                                        to=trainer_email,
                                    )
                                    if ok_a:
                                        st.info(f"📧 Ablehnungs-Mail an {trainer_email} gesendet.")
                                    elif err_a != "E-Mail-Versand nicht aktiviert.":
                                        st.warning(f"📧 Mail-Fehler: {err_a}")
                                st.rerun()

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
                    st.markdown(f"**Heim:** {r['heimteam']} &nbsp;|&nbsp; **Gast:** {r['gastteam']}")
                    if r.get("notizen"):
                        st.markdown(f"*Notiz: {r['notizen']}*")

                    _render_verwalter_notizblock(r, key_prefix="dfb")

                    team_mail = get_trainer_email_for_team(r["heimteam"])
                    custom_mail = st.text_input(
                        "Trainer-E-Mail (optional überschreiben)",
                        value=team_mail,
                        key=f"tmail_{r['id']}",
                        placeholder="trainer@verein.de",
                    )

                    if st.button(
                        "✅ DFBnet eingetragen – Spiel übernehmen & Trainer benachrichtigen",
                        key=f"dfb_{r['id']}",
                        use_container_width=True,
                        type="primary",
                    ):
                        typ_ = r.get("anfrage_typ") or "neu"
                        sid = confirm_dfbnet(r["id"])
                        if typ_ == "stornierung":
                            st.success("✅ Spiel storniert und aus dem Dashboard entfernt!")
                        elif typ_ in ("aenderung", "verlegung", "uhrzeit_aenderung"):
                            lbl = {"aenderung": "aktualisiert", "verlegung": "verlegt", "uhrzeit_aenderung": "Uhrzeit geändert"}.get(typ_, "aktualisiert")
                            st.success(f"✅ Spiel #{sid} {lbl}, DFBnet bestätigt!")
                        else:
                            st.success(f"✅ Spiel #{sid} im Dashboard gespeichert, DFBnet bestätigt!")
                        if custom_mail.strip():
                            if typ_ == "stornierung":
                                trainer_html = _mail_trainer_stornierung_html(
                                    date.fromisoformat(r["datum"]),
                                    r["uhrzeit"],
                                    r["platz"],
                                    r["heimteam"],
                                    r["gastteam"],
                                    r.get("notizen", ""),
                                )
                                subj = f"[WOHU] ❌ Spielabsage: {r['heimteam']} vs {r['gastteam']} ({r['datum']})"
                            elif typ_ in ("aenderung", "verlegung", "uhrzeit_aenderung"):
                                trainer_html = _mail_trainer_aenderung_html(
                                    date.fromisoformat(r["datum"]),
                                    r["uhrzeit"],
                                    r["platz"],
                                    r.get("kabine", ""),
                                    date.fromisoformat(r["neues_datum"]) if r.get("neues_datum") else date.fromisoformat(r["datum"]),
                                    r.get("neue_uhrzeit") or r["uhrzeit"],
                                    r.get("neuer_platz") or r["platz"],
                                    r.get("neue_kabine") or r.get("kabine", ""),
                                    r["heimteam"],
                                    r["gastteam"],
                                )
                                icons = {"aenderung": "✏️", "verlegung": "⏩", "uhrzeit_aenderung": "⏰"}
                                subj = f"[WOHU] {icons.get(typ_, '✏️')} Spieländerung: {r['heimteam']} vs {r['gastteam']} ({r['datum']})"
                            else:
                                trainer_html = _mail_trainer_html(
                                    date.fromisoformat(r["datum"]),
                                    r["uhrzeit"],
                                    r["platz"],
                                    r["heimteam"],
                                    r["gastteam"],
                                    r.get("kabine", ""),
                                    "",
                                )
                                subj = f"[WOHU] ⚽ Spielbestätigung: {r['heimteam']} vs {r['gastteam']} am {r['datum']}"
                            ok2, err2 = send_email(subj, trainer_html, to=custom_mail.strip())
                            if ok2:
                                st.info(f"📧 Trainer-Mail an {custom_mail.strip()} gesendet.")
                            elif err2 != "E-Mail-Versand nicht aktiviert.":
                                st.warning(f"📧 Trainer-Mail-Fehler: {err2}")
                        st.balloons()
                        st.rerun()

    if not hide_done:
        with tab_done:
            df_done = alle[alle["status"].isin(["abgeschlossen", "abgelehnt", "genehmigt"])] if not alle.empty else pd.DataFrame()
            if df_done.empty:
                st.info("Noch keine abgeschlossenen Vorgänge.")
            else:
                for _, r in df_done.sort_values("bearbeitet_am", ascending=False, na_position="last").iterrows():
                    done_notiz = r.get("verwalter_notiz") or ""
                    notiz_suffix = " 📝" if done_notiz else ""
                    titel = (
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

    with st.expander("📝 Neues Spiel erfassen", expanded=True):
        with st.form("admin_spiel_form"):
            fc1, fc2 = st.columns(2)
            with fc1:
                f_datum = st.date_input("Datum", value=date.today())
            with fc2:
                f_uhrzeit = st.selectbox("Anstoßzeit", TIME_SLOTS_TRAINING)
            f_platz = st.selectbox("Platz", PITCHES_SPIEL)
            fc3, fc4 = st.columns(2)
            with fc3:
                f_heim = st.text_input("Heimteam")
            with fc4:
                f_gast = st.text_input("Gastteam")

            freie_kabinen_a = get_free_kabinen(f_datum, f_uhrzeit)
            belegt_cnt = len(LOCKER_ROOMS) - len(freie_kabinen_a)
            if belegt_cnt:
                st.info(
                    f"🚳 {belegt_cnt} Kabine(n) durch Training belegt – nur freie Kabinen werden angezeigt."
                )
            ak1, ak2 = st.columns(2)
            with ak1:
                f_kabine_heim = st.selectbox("🏠 Kabine Heimmannschaft", freie_kabinen_a, key="adm_kh")
            with ak2:
                rest_a = [k for k in freie_kabinen_a if k != f_kabine_heim]
                f_kabine_gast = st.selectbox("✈️ Kabine Gastmannschaft", rest_a if rest_a else freie_kabinen_a, key="adm_kg")
            f_notizen = st.text_area("Notizen")

            conflicts = find_conflicts(df_training, f_datum, f_uhrzeit, f_platz)
            pitch_locked = f_platz in get_locked_pitches(f_datum)

            if pitch_locked:
                st.error(f"🚫 **{f_platz}** ist für {f_datum.strftime('%d.%m.%Y')} gesperrt!")
            if conflicts:
                st.warning(f"⚠️ Konflikt: **{', '.join(conflicts)}** trainieren zu dieser Zeit.")
                approved = st.checkbox(
                    f"✅ Ich bestätige die Zustimmung der betroffenen Trainer:innen (**{', '.join(conflicts)}**)."
                )
            else:
                approved = True

            st.info(
                "💡 Nach dem Speichern erscheint das Spiel in der **DFBnet-Warteschlange**. "
                "Erst nach DFBnet-Eintragung und Bestätigung wird es ins Dashboard übernommen "
                "und der Trainer automatisch informiert."
            )

            if st.form_submit_button("📋 Spiel speichern → DFBnet eintragen", type="primary", use_container_width=True):
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
                    aid = create_spielanfrage(f_datum, f_uhrzeit, f_platz, f_heim.strip(), f_gast.strip(), f_kabine, f_notizen)
                    update_anfrage_status(aid, "dfbnet_ausstehend", "Admin")
                    html = _mail_anfrage_html(
                        aid,
                        f_datum,
                        f_uhrzeit,
                        f_platz,
                        f_heim.strip(),
                        f_gast.strip(),
                        f_kabine,
                        f_notizen,
                        conflicts,
                        typ="Neues Spiel angelegt – JETZT IN DFBNET EINTRAGEN!",
                    )
                    ok, err = send_email(
                        f"[WOHU] 📋 DFBnet eintragen: {f_heim} vs {f_gast} ({f_datum.strftime('%d.%m.%Y')})",
                        html,
                    )
                    if ok:
                        st.info("📧 Hinweis-Mail ans Funktionspostfach gesendet.")
                    elif err != "E-Mail-Versand nicht aktiviert.":
                        st.warning(f"📧 E-Mail-Fehler: {err}")
                    st.success(f"✅ Spiel gespeichert (ID {aid}) – bitte jetzt in **DFBnet** eintragen und unten bestätigen!")
                    st.rerun()

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
                f"#{r['id']} – {r['heimteam']} vs {r['gastteam']}  |  {r['datum']} {r['uhrzeit']}  |  {r['platz']}",
                expanded=True,
            ):
                dc1, dc2, dc3 = st.columns(3)
                dc1.markdown(f"**Datum:** {r['datum']}")
                dc2.markdown(f"**Zeit:** {r['uhrzeit']}")
                dc3.markdown(f"**Platz:** {r['platz']}")
                st.markdown(
                    f"**Heim:** {r['heimteam']} &nbsp;|&nbsp; **Gast:** {r['gastteam']} &nbsp;|&nbsp; **Kabine:** {r.get('kabine','–')}"
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
                    key=f"dsp_dfb_{r['id']}",
                    use_container_width=True,
                    type="primary",
                ):
                    sid = confirm_dfbnet(r["id"])
                    st.success(f"✅ Spiel #{sid} im Dashboard gespeichert!")
                    if t_mail.strip():
                        trainer_html = _mail_trainer_html(
                            date.fromisoformat(r["datum"]),
                            r["uhrzeit"],
                            r["platz"],
                            r["heimteam"],
                            r["gastteam"],
                            r.get("kabine", ""),
                            "",
                        )
                        ok2, err2 = send_email(
                            f"[WOHU] ⚽ Spielbestätigung: {r['heimteam']} vs {r['gastteam']} am {r['datum']}",
                            trainer_html,
                            to=t_mail.strip(),
                        )
                        if ok2:
                            st.info(f"📧 Trainer-Mail an {t_mail.strip()} gesendet.")
                        elif err2 != "E-Mail-Versand nicht aktiviert.":
                            st.warning(f"📧 Trainer-Mail-Fehler: {err2}")
                    st.balloons()
                    st.rerun()

    st.divider()
    st.subheader("📋 Alle bestätigten Spiele")
    all_m = get_all_matches()
    if all_m.empty:
        st.info("Noch keine Spiele eingetragen.")
    else:
        all_m["datum_dt"] = pd.to_datetime(all_m["datum"])
        all_m["herkunft"] = all_m.get("quelle", "manuell").fillna("manuell").map(
            {
                "manuell": "Manuell angelegt",
                "aus_anfrage": "Aus Anfrage uebernommen",
                "automatisch_aus_anfrage": "Automatisch aus DFBnet-Anfrage erzeugt",
            }
        ).fillna("Manuell angelegt")
        export_df = all_m.sort_values("datum_dt")[["datum", "uhrzeit", "platz", "heimteam", "gastteam", "kabine", "notizen", "herkunft"]].rename(
            columns={
                "datum": "Datum",
                "uhrzeit": "Uhrzeit",
                "platz": "Platz",
                "heimteam": "Heimteam",
                "gastteam": "Gastteam",
                "kabine": "Kabine",
                "notizen": "Notizen",
                "herkunft": "Herkunft",
            }
        )
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
                '<span style="background:#22c55e;color:#fff;padding:1px 7px;border-radius:10px;font-size:10px;">✅ DFBnet</span>'
                if dfb_ok
                else '<span style="background:#7c3aed;color:#fff;padding:1px 7px;border-radius:10px;font-size:10px;">📋 DFBnet offen</span>'
            )
            quelle_badge = {
                "automatisch_aus_anfrage": '<span style="background:#0f766e;color:#fff;padding:1px 7px;border-radius:10px;font-size:10px;">🤖 Auto aus Anfrage</span>',
                "aus_anfrage": '<span style="background:#2563eb;color:#fff;padding:1px 7px;border-radius:10px;font-size:10px;">📨 Aus Anfrage</span>',
            }.get(m.get("quelle"), '<span style="background:#6b7280;color:#fff;padding:1px 7px;border-radius:10px;font-size:10px;">✍️ Manuell</span>')
            with st.expander(
                f"⚽ #{m['id']} – {m['heimteam']} vs {m['gastteam']}  |  {m['datum_dt'].strftime('%d.%m.%Y')} {m['uhrzeit']}  |  {m['platz']}",
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

                st.divider()
                st.markdown("**✏️ Spiel bearbeiten**")
                with st.form(f"edit_match_{m['id']}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_datum = st.date_input("Neues Datum", value=date.fromisoformat(m["datum"]), key=f"ed_{m['id']}")
                    with ec2:
                        cur_idx = TIME_SLOTS_TRAINING.index(m["uhrzeit"]) if m["uhrzeit"] in TIME_SLOTS_TRAINING else 0
                        e_uhrzeit = st.selectbox("Neue Uhrzeit", TIME_SLOTS_TRAINING, index=cur_idx, key=f"eu_{m['id']}")
                    cur_pi = PITCHES_SPIEL.index(m["platz"]) if m["platz"] in PITCHES_SPIEL else 0
                    e_platz = st.selectbox("Neuer Platz", PITCHES_SPIEL, index=cur_pi, key=f"ep_{m['id']}")
                    freie_k = get_free_kabinen(e_datum, e_uhrzeit)
                    ek1, ek2 = st.columns(2)
                    with ek1:
                        e_kab_h = st.selectbox("🏠 Kabine Heim", freie_k, key=f"ekh_{m['id']}")
                    with ek2:
                        rest_ek = [k for k in freie_k if k != e_kab_h]
                        e_kab_g = st.selectbox("✈️ Kabine Gast", rest_ek if rest_ek else freie_k, key=f"ekg_{m['id']}")
                    e_notizen = st.text_area("Notizen", value=m.get("notizen", ""), key=f"en_{m['id']}")
                    e_tmail = st.text_input(
                        "Trainer-E-Mail (für Änderungs-Mail)", value=get_trainer_email_for_team(m["heimteam"]), key=f"etm_{m['id']}"
                    )
                    send_aend_mail = st.checkbox("📧 Trainer über Änderung informieren", value=True, key=f"esc_{m['id']}")
                    if st.form_submit_button("💾 Änderungen speichern", type="primary", use_container_width=True):
                        if e_kab_h == e_kab_g:
                            st.error("Heim und Gast können nicht dieselbe Kabine nutzen.")
                        else:
                            neue_kabine = f"{e_kab_h} / {e_kab_g}"
                            update_match_details(m["id"], e_datum, e_uhrzeit, e_platz, neue_kabine, e_notizen)
                            st.success("✅ Spiel aktualisiert!")
                            if send_aend_mail and e_tmail.strip():
                                aend_html = _mail_trainer_aenderung_html(
                                    date.fromisoformat(m["datum"]),
                                    m["uhrzeit"],
                                    m["platz"],
                                    m.get("kabine", ""),
                                    e_datum,
                                    e_uhrzeit,
                                    e_platz,
                                    neue_kabine,
                                    m["heimteam"],
                                    m["gastteam"],
                                )
                                ok3, err3 = send_email(
                                    f"[WOHU] ✏️ Spieländerung: {m['heimteam']} vs {m['gastteam']} ({m['datum']})",
                                    aend_html,
                                    to=e_tmail.strip(),
                                )
                                if ok3:
                                    st.info(f"📧 Änderungs-Mail an {e_tmail.strip()} gesendet.")
                                elif err3 != "E-Mail-Versand nicht aktiviert.":
                                    st.warning(f"📧 Mail-Fehler: {err3}")
                            st.rerun()

                st.divider()
                st.markdown("**🗑️ Spiel löschen**")
                d_tmail = st.text_input(
                    "Trainer-E-Mail (für Absage-Mail, optional)", value=get_trainer_email_for_team(m["heimteam"]), key=f"dtm_{m['id']}"
                )
                d_grund = st.text_input("Begründung (optional)", key=f"dg_{m['id']}")
                send_del_mail = st.checkbox("📧 Trainer über Absage informieren", value=True, key=f"dsc_{m['id']}")
                if st.button(f"🗑️ Spiel #{m['id']} löschen", key=f"del_{m['id']}", type="secondary", use_container_width=True):
                    if send_del_mail and d_tmail.strip():
                        del_html = _mail_trainer_stornierung_html(
                            date.fromisoformat(m["datum"]),
                            m["uhrzeit"],
                            m["platz"],
                            m["heimteam"],
                            m["gastteam"],
                            d_grund,
                        )
                        ok4, err4 = send_email(
                            f"[WOHU] ❌ Spielabsage: {m['heimteam']} vs {m['gastteam']} ({m['datum']})",
                            del_html,
                            to=d_tmail.strip(),
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

    db_df = load_training_df_from_db(saison)
    if not db_df.empty:
        st.session_state.training_df = db_df

    day_order = {d: i for i, d in enumerate(DAYS)}

    tab_manuell, tab_csv, tab_kabinen = st.tabs(["✏️ Trainingszeiten erfassen", "📂 CSV / Excel importieren", "🚿 Kabinen & Trainer"])

    with tab_manuell:
        sp_df = get_saisonplanung(saison)
        vorhandene_teams = sorted(sp_df["team"].unique().tolist()) if not sp_df.empty else []

        with st.form("training_slot_form", clear_on_submit=True):
            st.subheader("Neuen Trainingstermin hinzufügen")
            mc1, mc2 = st.columns([2, 1])
            with mc1:
                f_team = st.text_input("Mannschaft", placeholder="z. B. A-Jugend, 1. Mannschaft …")
                if vorhandene_teams:
                    st.caption("Vorhandene Teams: " + " · ".join(vorhandene_teams[:10]) + (" …" if len(vorhandene_teams) > 10 else ""))
            with mc2:
                f_platz = st.selectbox("Platz", PITCHES)

            f_tage = st.multiselect("Trainingstage", DAYS, placeholder="Einen oder mehrere Tage wählen …")
            tc1, tc2 = st.columns(2)
            with tc1:
                f_zeit_von = st.selectbox("Trainingsstart (Von)", TIME_SLOTS_TRAINING)
            with tc2:
                idx_von = TIME_SLOTS_TRAINING.index(f_zeit_von)
                opts_bis = TIME_SLOTS_TRAINING[idx_von + 1 :]
                f_zeit_bis = st.selectbox("Trainingsende (Bis)", opts_bis if opts_bis else TIME_SLOTS_TRAINING)

            submitted = st.form_submit_button("➕ Hinzufügen", type="primary", use_container_width=True)
            if submitted:
                if not f_team.strip():
                    st.error("Bitte Mannschaftsname eingeben.")
                elif not f_tage:
                    st.error("Bitte mindestens einen Trainingstag wählen.")
                else:
                    for tag in f_tage:
                        add_training_slot(f_team.strip(), tag, f_zeit_von, f_zeit_bis, f_platz, saison)
                    st.success(
                        f"✅ {len(f_tage)} Trainingsslot(s) für "
                        f"**{f_team.strip()}** gespeichert "
                        f"({f_zeit_von}–{f_zeit_bis}, {f_platz})."
                    )
                    st.session_state.training_df = load_training_df_from_db(saison)
                    st.rerun()

        st.divider()
        sp_df = get_saisonplanung(saison)
        if sp_df.empty:
            st.info("Noch keine Trainingszeiten für diese Saison erfasst.")
        else:
            teams_sorted = sorted(sp_df["team"].unique(), key=str.lower)
            st.markdown(f"**{len(teams_sorted)} Mannschaft(en)** · {len(sp_df)} Slot(s) gesamt")
            st.divider()

            for team in teams_sorted:
                team_df = sp_df[sp_df["team"] == team].copy().sort_values("tag", key=lambda s: s.map(day_order))
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
                            if st.button("🗑️", key=f"del_{row['id']}", help="Diesen Slot löschen"):
                                delete_training_slot(int(row["id"]))
                                st.session_state.training_df = load_training_df_from_db(saison)
                                st.rerun()

    with tab_csv:
        st.subheader("Trainingsplan importieren")
        st.caption(
            "Importiert einen kompletten Trainingsplan aus CSV oder Excel "
            "und **ersetzt** alle bestehenden Einträge der gewählten Saison."
        )
        col_up, col_btn = st.columns([2, 1])
        with col_up:
            uploaded = st.file_uploader("CSV oder Excel hochladen", type=["csv", "xlsx"], label_visibility="collapsed")
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

    with tab_kabinen:
        st.subheader("Kabinen & Trainer-E-Mails je Mannschaft")
        st.caption("Die Zuweisung gilt saisonweit. Kabinen werden bei Spielansetzungen automatisch als belegt markiert.")

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
                batch = teams[i : i + cols_per_row]
                row_cols = st.columns(cols_per_row)
                for col, team in zip(row_cols, batch):
                    with col:
                        st.markdown(f"**{team}**")
                        current = ""
                        hit = sp_df[sp_df["team"] == team]["kabine"]
                        if not hit.empty and str(hit.iloc[0]) not in ("", "nan"):
                            current = str(hit.iloc[0])
                        idx = LOCKER_ROOMS.index(current) if current in LOCKER_ROOMS else 0
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

            st.subheader("Kabinen-Übersicht")
            ov_cols = st.columns(max(len(LOCKER_ROOMS), 1))
            for idx_k, kabine in enumerate(LOCKER_ROOMS):
                with ov_cols[idx_k % len(LOCKER_ROOMS)]:
                    teams_in = [t for t, k in assignments.items() if k == kabine]
                    is_conflict = kabine in duplikate
                    css = "locker-conflict" if is_conflict else ("locker-busy" if teams_in else "locker-free")
                    ikon = "🔴" if is_conflict else ("🚿" if teams_in else "🔓")
                    teams_html = (
                        "".join(f'<div style="font-size:11px;color:#333;margin-top:3px;">{t}</div>' for t in teams_in)
                        if teams_in
                        else '<div style="color:#999;font-size:11px;">Frei</div>'
                    )
                    st.markdown(
                        f'<div class="{css}"><div style="font-size:24px;">{ikon}</div>'
                        f'<div style="color:#fff;font-weight:bold;font-size:13px;margin:6px 0;">'
                        f"{kabine}</div>{teams_html}</div>",
                        unsafe_allow_html=True,
                    )

            st.divider()
            st.subheader("🕐 Zeitbasierter Konflikt-Check")
            konflikt_df = get_kabinen_konflikte(saison)
            if konflikt_df.empty:
                st.success("✅ Keine zeitgleichen Kabinen-Kollisionen.")
            else:
                st.error(f"⛔ {len(konflikt_df)} zeitgleiche Kabinen-Kollision(en)!")
                st.dataframe(
                    konflikt_df.rename(
                        columns={
                            "kabine": "Kabine",
                            "tag": "Tag",
                            "zeit": "Zeit",
                            "anzahl": "Anzahl Teams",
                            "teams": "Betroffene Teams",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            st.divider()
            btn_disabled = bool(duplikate)
            if st.button(
                "💾 Kabinen & E-Mails speichern" if not btn_disabled else "💾 Speichern (zuerst Konflikte lösen)",
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
                lock_btn = st.form_submit_button("🔒 Sperren", type="primary", use_container_width=True)
            with bc2:
                unlock_btn = st.form_submit_button("🔓 Freigeben", type="secondary", use_container_width=True)

            if lock_btn:
                toggle_pitch_lock(l_platz, l_datum, l_grund, True)
                st.success(f"✅ {l_platz} am {l_datum.strftime('%d.%m.%Y')} gesperrt.")
            if unlock_btn:
                toggle_pitch_lock(l_platz, l_datum, l_grund, False)
                st.success(f"✅ {l_platz} am {l_datum.strftime('%d.%m.%Y')} freigegeben.")

    with col_list:
        st.subheader("Aktive Sperren")
        conn = db_connect()
        df_lk = pd.read_sql("SELECT * FROM platz_sperren WHERE gesperrt=1 ORDER BY datum", conn)
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
    sc = st.columns(len(PITCHES))
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

    all_m = get_all_matches()
    today_ts = pd.Timestamp(date.today())
    upcoming_count = past_count = 0
    if not all_m.empty:
        all_m["datum_dt"] = pd.to_datetime(all_m["datum"])
        upcoming_count = int((all_m["datum_dt"] >= today_ts).sum())
        past_count = len(all_m) - upcoming_count

    c1, c2, c3 = st.columns(3)
    c1.metric("Gesamt Spiele", len(all_m))
    c2.metric("Bevorstehend", upcoming_count)
    c3.metric("Gespielt", past_count)

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

    tab_pin, tab_oidc, tab_ms, tab_mail, tab_info = st.tabs(["🔑 Admin-PIN", "🔐 ClubAuth (OIDC)", "🔷 Microsoft-Login (Legacy)", "📧 E-Mail / SMTP", "ℹ️ System-Info"])

    with tab_pin:
        st.subheader("Admin-PIN ändern")
        with st.form("pin_form"):
            cur_pin = st.text_input("Aktueller PIN", type="password")
            new_pin = st.text_input("Neuer PIN", type="password")
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

    with tab_oidc:
        st.subheader("ClubAuth – Zentrales Benutzerverwaltungs-System")
        st.markdown(
            "Verbindet Spielbetrieb mit dem **WOHU ClubAuth**-System. "
            "Benutzer melden sich dann mit ihrem ClubAuth-Konto an — "
            "Rollen werden zentral in ClubAuth verwaltet."
        )

        oidc_aktiv = bool(get_setting("oidc_client_id") and get_setting("oidc_base_url"))
        if oidc_aktiv:
            st.success("✅ ClubAuth-Login ist **aktiv** – Microsoft-Login und PIN-Fallback sind deaktiviert.")
        else:
            st.info("ℹ️ ClubAuth noch nicht konfiguriert – aktuell wird Microsoft-Login oder PIN verwendet.")

        st.divider()
        with st.form("oidc_form"):
            oidc_url = st.text_input(
                "ClubAuth-URL (Basis-URL)",
                value=get_setting("oidc_base_url") or "",
                placeholder="https://auth.westfalia-osterwick.de",
                help="URL des ClubAuth-Servers, ohne abschließenden Slash.",
            )
            oidc_cid = st.text_input(
                "Client ID",
                value=get_setting("oidc_client_id") or "",
                placeholder="Aus dem ClubAuth Admin-Panel kopieren",
            )
            oidc_sec = st.text_input(
                "Client Secret",
                value=get_setting("oidc_client_secret") or "",
                type="password",
                placeholder="Aus dem ClubAuth Admin-Panel kopieren",
            )
            oidc_ruri = st.text_input(
                "Redirect URI",
                value=get_setting("oidc_redirect_uri") or "http://localhost:8501",
                placeholder="https://spielbetrieb.westfalia-osterwick.de",
                help="Muss exakt mit der Redirect URI im ClubAuth Admin übereinstimmen.",
            )
            if st.form_submit_button("💾 Speichern", type="primary"):
                set_setting("oidc_base_url", oidc_url.strip())
                set_setting("oidc_client_id", oidc_cid.strip())
                set_setting("oidc_client_secret", oidc_sec.strip())
                set_setting("oidc_redirect_uri", oidc_ruri.strip())
                st.success("✅ ClubAuth-Einstellungen gespeichert.")
                st.rerun()

        with st.expander("📖 ClubAuth-App registrieren (Schritt für Schritt)"):
            st.markdown(
                """
**Im ClubAuth Admin-Panel** (`/admin/` → OAuth2 Provider → Applications → Add):

| Feld | Wert |
|------|------|
| Name | `Spielbetrieb` |
| Client type | `Confidential` |
| Authorization grant type | `Authorization code` |
| Redirect URIs | `https://spielbetrieb.westfalia-osterwick.de` |
| Allowed scopes | `openid profile email roles` |
| Algorithm | `RS256` |

→ Nach dem Speichern **Client ID** und **Client Secret** hier eintragen.

**Trainer anlegen (im ClubAuth Admin):**
1. Users → Add → E-Mail, Vor-/Nachname eingeben
2. Inline → Role Assignments → App: `spielbetrieb`, Role: `benutzer`
3. Speichern → Trainer kann sich jetzt hier einloggen
"""
            )


    with tab_ms:
        st.subheader("Microsoft-Login (Azure AD / Entra ID)")
        st.markdown(
            "Tragen Sie hier die Daten Ihrer **Azure App-Registrierung** ein. "
            "Danach erscheint auf der Login-Seite der Button **🔷 Mit Microsoft anmelden**."
        )
        st.divider()
        with st.form("ms_form"):
            ms_cid = st.text_input(
                "Application (Client) ID",
                value=get_setting("ms_client_id"),
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            )
            ms_tid = st.text_input(
                "Directory (Tenant) ID",
                value=get_setting("ms_tenant_id") or "common",
                placeholder="common  oder  xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            )
            ms_sec = st.text_input(
                "Client Secret",
                value=get_setting("ms_client_secret"),
                type="password",
                placeholder="Leer = Public-Client (PKCE nicht unterstützt)",
            )
            ms_ruri = st.text_input(
                "Redirect URI",
                value=get_setting("ms_redirect_uri") or "http://localhost:8501",
                placeholder="http://localhost:8501",
            )
            ms_adm = st.text_area(
                "Admin-E-Mail-Adressen",
                value=get_setting("admin_emails"),
                placeholder="admin@westfalia-osterwick.de\nvorstand@westfalia-osterwick.de",
                help="Eine Adresse pro Zeile. Diese erhalten vollen Admin-Zugang.",
            )
            ms_kord = st.text_area(
                "Koordinatoren-E-Mail-Adressen",
                value=get_setting("koordinator_emails") or "",
                placeholder="koordinator@westfalia-osterwick.de\nspielausschuss@westfalia-osterwick.de",
                help="Eine Adresse pro Zeile. Koordinatoren sehen Dashboard, Anfragen und Spiel anlegen – aber keine Systemeinstellungen oder Saisonplanung.",
            )
            if st.form_submit_button("💾 Speichern", type="primary"):
                set_setting("ms_client_id", ms_cid.strip())
                set_setting("ms_tenant_id", ms_tid.strip() or "common")
                set_setting("ms_client_secret", ms_sec.strip())
                set_setting("ms_redirect_uri", ms_ruri.strip())
                set_setting("admin_emails", ms_adm.strip())
                set_setting("koordinator_emails", ms_kord.strip())
                st.success("✅ Microsoft-Login-Einstellungen gespeichert.")
                st.rerun()

        with st.expander("📖 Azure App-Registrierung einrichten (Schritt für Schritt)"):
            st.markdown(
                """
1. **Azure Portal** öffnen: [portal.azure.com](https://portal.azure.com)
2. **Microsoft Entra ID → App-Registrierungen → Neue Registrierung**
3. Name: z. B. `WOHU Spielbetrieb`
4. Kontotypen: *Nur Konten in diesem Organisationsverzeichnis*
5. Redirect URI: `Web` → Ihre Streamlit-URL (z. B. `http://localhost:8501`)
6. Nach Erstellung: **Application (Client) ID** und **Directory (Tenant) ID** kopieren
7. Unter **Zertifikate & Geheimnisse → Neuer geheimer Clientschlüssel** erstellen
8. Unter **API-Berechtigungen**: `openid`, `profile`, `email` sind standardmäßig vorhanden
"""
            )

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
            e_aktiv = st.toggle("E-Mail-Versand aktivieren", value=(cfg.get("email_aktiv", "0") == "1"))
            ec1, ec2 = st.columns([3, 1])
            with ec1:
                e_host = st.text_input(
                    "SMTP-Server",
                    value=cfg.get("email_smtp_host", ""),
                    placeholder="z. B. smtp.office365.com",
                )
            with ec2:
                e_port = st.number_input("Port", value=int(cfg.get("email_smtp_port", 587) or 587), min_value=1, max_value=65535)
            eu1, eu2 = st.columns(2)
            with eu1:
                e_user = st.text_input(
                    "SMTP-Benutzername",
                    value=cfg.get("email_smtp_user", ""),
                    placeholder="spielbetrieb@verein.de",
                )
            with eu2:
                e_pass = st.text_input("SMTP-Passwort", value=cfg.get("email_smtp_pass", ""), type="password")
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
                saved = st.form_submit_button("💾 Einstellungen speichern", type="primary", use_container_width=True)
            with sc2:
                tested = st.form_submit_button("📨 Test-E-Mail senden", type="secondary", use_container_width=True)

            if saved or tested:
                set_setting("email_aktiv", "1" if e_aktiv else "0")
                set_setting("email_smtp_host", e_host)
                set_setting("email_smtp_port", str(e_port))
                set_setting("email_smtp_user", e_user)
                set_setting("email_smtp_pass", e_pass)
                set_setting("email_absender", e_abs)
                set_setting("email_empfaenger", e_emp)
                if saved:
                    st.success("✅ E-Mail-Einstellungen gespeichert.")

            if tested:
                if not e_aktiv:
                    st.warning("Versand ist deaktiviert – bitte zuerst aktivieren.")
                else:
                    test_html = _mail_anfrage_html(
                        0,
                        date.today(),
                        "15:00",
                        "Rasen vorne",
                        "Testheim FC",
                        "Gastclub SV",
                        "Kabine 1",
                        "Dies ist eine Test-Nachricht.",
                        ["U19", "1. Mannschaft"],
                        typ="TEST-Nachricht",
                    )
                    ok, err = send_email("[WOHU] Test-E-Mail – Konfigurationsprüfung", test_html)
                    if ok:
                        st.success(f"✅ Test-E-Mail erfolgreich gesendet an: {e_emp}")
                    else:
                        st.error(f"❌ Fehler beim Senden: {err}")

        with st.expander("💡 SMTP-Einstellungen gängiger Anbieter"):
            st.markdown(
                """
| Anbieter | SMTP-Server | Port | Hinweis |
|---|---|---|---|
| **Office 365 / Microsoft** | `smtp.office365.com` | `587` | STARTTLS |
| **Gmail** | `smtp.gmail.com` | `587` | App-Passwort erforderlich |
| **GMX** | `mail.gmx.net` | `587` | STARTTLS |
| **Web.de** | `smtp.web.de` | `587` | STARTTLS |
| **IONOS / 1&1** | `smtp.ionos.de` | `587` | STARTTLS |
            """
            )

    with tab_info:
        st.subheader("System-Info")
        conn = db_connect()
        n_sp = conn.execute("SELECT COUNT(*) FROM spiele").fetchone()[0]
        n_an = conn.execute("SELECT COUNT(*) FROM spielanfragen").fetchone()[0]
        n_sa = conn.execute("SELECT COUNT(*) FROM saisonplanung").fetchone()[0]
        conn.close()
        ci1, ci2, ci3 = st.columns(3)
        ci1.metric("Spiele in DB", n_sp)
        ci2.metric("Anfragen in DB", n_an)
        ci3.metric("Saisonplaneinträge", n_sa)
