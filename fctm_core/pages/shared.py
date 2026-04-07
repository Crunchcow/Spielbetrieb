"""Gemeinsame Seiten (alle Rollen)."""
from datetime import date

import pandas as pd
import streamlit as st

from fctm_core.constants import PITCHES, WEEKDAYS_DISPLAY
from fctm_core.domain_service import load_training_df_from_db


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
