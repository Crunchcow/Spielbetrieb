"""Benutzer-Seiten (Trainer-Rolle)."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from fctm_core.constants import PITCHES_SPIEL, TIME_SLOTS_TRAINING
from fctm_core.domain_service import (
    create_anfrage_allgemein,
    create_anfrage_stornierung,
    create_anfrage_stornierung_direkt,
    create_anfrage_uhrzeit_aenderung,
    create_anfrage_uhrzeit_aenderung_direkt,
    create_anfrage_verlegung,
    create_anfrage_verlegung_direkt,
    create_spielanfrage,
    find_conflicts,
    get_all_anfragen,
    get_all_matches,
)
from fctm_core.mail_service import _mail_anfrage_html, send_email
from fctm_core.ui_helpers import _anfrage_timeline_html, status_badge, typ_badge


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
                    f"[WOHU] Neue Spielanfrage #{rid}: {heim_val} vs {f_gast.strip()} "
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
                f' &nbsp;| &nbsp; ⏰ {v_match["uhrzeit"]} &nbsp;| &nbsp; 🏟️ {v_match["platz"]}</div>',
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
                        f"[WOHU] ⏩ Spielverlegung #{rid}: {v_match['heimteam']} vs {v_match['gastteam']} → {v_datum.strftime('%d.%m.%Y')} {v_uhrzeit}",
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
                        f"[WOHU] ⏩ Spielverlegung #{rid}: {heim_val} vs {vd_gast.strip()} → {vd_n_datum.strftime('%d.%m.%Y')} {vd_n_uhrzeit}",
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
                        f"[WOHU] ⏰ Uhrzeitänderung #{rid}: {u_match['heimteam']} vs {u_match['gastteam']} – {u_match['uhrzeit']} → {u_neue_uhrzeit}",
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
                        f"[WOHU] ⏰ Uhrzeitänderung #{rid}: {heim_val} vs {ud_gast.strip()} – {ud_uhrzeit} → {ud_neue_uhrzeit}",
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
                            f"[WOHU] ❌ Stornierungsantrag #{rid}: {s_match['heimteam']} vs {s_match['gastteam']} ({s_match['datum']})",
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
                        f"[WOHU] ❌ Stornierungsantrag #{rid}: {heim_val} vs {sd_gast.strip()} ({sd_datum.strftime('%d.%m.%Y')})",
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
                    f"[WOHU] 💬 Freie Anfrage #{rid} von {my_team}: {f_betreff.strip()}",
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
