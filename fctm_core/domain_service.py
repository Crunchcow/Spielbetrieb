import io
from datetime import date

import pandas as pd

from .constants import DAYS, LOCKER_ROOMS, PITCH_HALVES
from .storage import db_connect


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


def create_anfrage_aenderung(spiel_id: int, neues_datum: date, neue_uhrzeit: str, neuer_platz: str, notizen: str, erstellt_von: str = "") -> int:
    conn = db_connect()
    row = conn.execute("SELECT * FROM spiele WHERE id=?", (spiel_id,)).fetchone()
    conn.close()
    if not row:
        return -1
    sp_cols = ["id", "datum", "uhrzeit", "platz", "heimteam", "gastteam", "kabine", "notizen"]
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
            sp["kabine"], erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_stornierung(spiel_id: int, notizen: str, erstellt_von: str = "") -> int:
    conn = db_connect()
    row = conn.execute("SELECT * FROM spiele WHERE id=?", (spiel_id,)).fetchone()
    conn.close()
    if not row:
        return -1
    sp_cols = ["id", "datum", "uhrzeit", "platz", "heimteam", "gastteam", "kabine", "notizen"]
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


def create_anfrage_verlegung(spiel_id: int, neues_datum: date, neue_uhrzeit: str, neuer_platz: str, notizen: str, erstellt_von: str = "") -> int:
    conn = db_connect()
    row = conn.execute("SELECT * FROM spiele WHERE id=?", (spiel_id,)).fetchone()
    conn.close()
    if not row:
        return -1
    sp_cols = ["id", "datum", "uhrzeit", "platz", "heimteam", "gastteam", "kabine", "notizen"]
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
            sp["kabine"], erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_uhrzeit_aenderung(spiel_id: int, neue_uhrzeit: str, notizen: str, erstellt_von: str = "") -> int:
    conn = db_connect()
    row = conn.execute("SELECT * FROM spiele WHERE id=?", (spiel_id,)).fetchone()
    conn.close()
    if not row:
        return -1
    sp_cols = ["id", "datum", "uhrzeit", "platz", "heimteam", "gastteam", "kabine", "notizen"]
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
            sp["kabine"], erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_verlegung_direkt(datum: date, uhrzeit: str, platz: str, heimteam: str, gastteam: str, neues_datum: date, neue_uhrzeit: str, neuer_platz: str, notizen: str, erstellt_von: str = "") -> int:
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen "
        "(datum,uhrzeit,platz,heimteam,gastteam,notizen,"
        "anfrage_typ,neues_datum,neue_uhrzeit,neuer_platz,erstellt_von) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            datum.isoformat(), uhrzeit, platz, heimteam, gastteam, notizen,
            "verlegung", neues_datum.isoformat(), neue_uhrzeit, neuer_platz, erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_uhrzeit_aenderung_direkt(datum: date, uhrzeit: str, platz: str, heimteam: str, gastteam: str, neue_uhrzeit: str, notizen: str, erstellt_von: str = "") -> int:
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen "
        "(datum,uhrzeit,platz,heimteam,gastteam,notizen,"
        "anfrage_typ,neue_uhrzeit,neues_datum,neuer_platz,erstellt_von) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            datum.isoformat(), uhrzeit, platz, heimteam, gastteam, notizen,
            "uhrzeit_aenderung", neue_uhrzeit, datum.isoformat(), platz, erstellt_von,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def create_anfrage_stornierung_direkt(datum: date, uhrzeit: str, platz: str, heimteam: str, gastteam: str, notizen: str, erstellt_von: str = "") -> int:
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


def create_anfrage_allgemein(betreff: str, nachricht: str, erstellt_von: str = "") -> int:
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO spielanfragen "
        "(datum,uhrzeit,platz,notizen,anfrage_typ,erstellt_von,betreff,nachricht) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            date.today().isoformat(), "", "", nachricht,
            "allgemein", erstellt_von, betreff, nachricht,
        ),
    )
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def update_match_details(mid: int, neues_datum: date, neue_uhrzeit: str, neuer_platz: str, neue_kabine: str, notizen: str) -> None:
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
    row = conn.execute("SELECT verwalter_notiz FROM spielanfragen WHERE id=?", (anfrage_id,)).fetchone()
    prev = (row[0] if row and row[0] else "").strip()
    if clean == prev:
        conn.close()
        return
    conn.execute("UPDATE spielanfragen SET verwalter_notiz=? WHERE id=?", (clean, anfrage_id))
    conn.execute(
        "INSERT INTO anfrage_notizen (anfrage_id, notiz, erstellt_von) VALUES (?,?,?)",
        (anfrage_id, clean if clean else "[Notiz entfernt]", autor),
    )
    conn.commit()
    conn.close()


def update_anfrage_status(aid: int, status: str, bearbeiter: str, kommentar: str = "") -> None:
    conn = db_connect()
    conn.execute(
        "UPDATE spielanfragen SET status=?, bearbeiter=?, bearbeitet_am=datetime('now'), bearbeiter_kommentar=? WHERE id=?",
        (status, bearbeiter, kommentar, aid),
    )
    conn.commit()
    conn.close()


def approve_anfrage(aid: int, betroffene: list[str]) -> None:
    conn = db_connect()
    conn.execute("UPDATE spielanfragen SET bearbeiter='Admin' WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    update_anfrage_status(aid, "dfbnet_ausstehend", "Admin")


def confirm_dfbnet(aid: int) -> int:
    conn = db_connect()
    row = conn.execute("SELECT * FROM spielanfragen WHERE id=?", (aid,)).fetchone()
    conn.close()
    if not row:
        return -1

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

    sid = save_match(
        date.fromisoformat(r["datum"]), r["uhrzeit"], r["platz"],
        r["heimteam"] or "", r["gastteam"] or "",
        r["kabine"] or "", r["notizen"] or "", [],
        quelle="aus_anfrage", ursprung_anfrage_id=aid,
    )
    conn2 = db_connect()
    conn2.execute("UPDATE spiele SET dfbnet_eingetragen=1 WHERE id=?", (sid,))
    conn2.commit()
    conn2.close()
    update_anfrage_status(aid, "abgeschlossen", "Admin")
    return sid


def get_trainer_email_for_team(team: str) -> str:
    conn = db_connect()
    row = conn.execute(
        "SELECT trainer_email FROM saisonplanung WHERE team=? AND trainer_email IS NOT NULL AND trainer_email != '' LIMIT 1",
        (team,),
    ).fetchone()
    conn.close()
    return row[0] if row else ""


def get_all_anfragen_dfbnet() -> pd.DataFrame:
    conn = db_connect()
    df = pd.read_sql(
        "SELECT * FROM spielanfragen WHERE status='dfbnet_ausstehend' ORDER BY datum,uhrzeit",
        conn,
    )
    conn.close()
    return df


def toggle_pitch_lock(platz: str, datum: date, grund: str, lock: bool) -> None:
    conn = db_connect()
    row = conn.execute("SELECT id FROM platz_sperren WHERE platz=? AND datum=?", (platz, datum.isoformat())).fetchone()
    if row:
        conn.execute("UPDATE platz_sperren SET gesperrt=?,grund=? WHERE id=?", (1 if lock else 0, grund, row[0]))
    elif lock:
        conn.execute("INSERT INTO platz_sperren (platz,datum,grund) VALUES (?,?,?)", (platz, datum.isoformat(), grund))
    conn.commit()
    conn.close()


def get_locked_pitches(d: date) -> list[str]:
    conn = db_connect()
    rows = conn.execute("SELECT platz FROM platz_sperren WHERE datum=? AND gesperrt=1", (d.isoformat(),)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def save_saisonplanung(df: pd.DataFrame, saison: str) -> None:
    conn = db_connect()
    conn.execute("DELETE FROM saisonplanung WHERE saison=?", (saison,))
    save_df = df.copy()
    save_df["saison"] = saison
    save_df.to_sql("saisonplanung", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()


def add_training_slot(team: str, tag: str, zeit: str, zeit_ende: str, platz: str, saison: str, kabine: str = "", trainer_email: str = "") -> None:
    conn = db_connect()
    conn.execute(
        "INSERT INTO saisonplanung (team, platz, tag, zeit, zeit_ende, kabine, trainer_email, saison) VALUES (?,?,?,?,?,?,?,?)",
        (team, platz, tag, zeit, zeit_ende, kabine, trainer_email, saison),
    )
    conn.commit()
    conn.close()


def delete_training_slot(slot_id: int) -> None:
    conn = db_connect()
    conn.execute("DELETE FROM saisonplanung WHERE id=?", (slot_id,))
    conn.commit()
    conn.close()


def load_training_df_from_db(saison: str) -> pd.DataFrame:
    sp = get_saisonplanung(saison)
    if sp.empty:
        return pd.DataFrame()
    sp = sp.rename(columns={"team": "Team", "platz": "Platz", "tag": "Tag", "zeit": "Zeit"})
    if "zeit_ende" in sp.columns:
        sp = sp.rename(columns={"zeit_ende": "ZeitEnde"})
    else:
        sp["ZeitEnde"] = ""
    return sp[["Team", "Platz", "Tag", "Zeit", "ZeitEnde"]]


def update_kabinen_und_emails(saison: str, assignments: dict[str, str], trainer_emails: dict[str, str]) -> None:
    conn = db_connect()
    for team, kabine in assignments.items():
        conn.execute(
            "UPDATE saisonplanung SET kabine=?, trainer_email=? WHERE team=? AND saison=?",
            (kabine, trainer_emails.get(team, ""), team, saison),
        )
    conn.commit()
    conn.close()


def get_saisonplanung(saison: str) -> pd.DataFrame:
    conn = db_connect()
    df = pd.read_sql("SELECT * FROM saisonplanung WHERE saison=? ORDER BY tag,zeit", conn, params=(saison,))
    conn.close()
    return df


def get_kabinen_konflikte(saison: str) -> pd.DataFrame:
    df = get_saisonplanung(saison)
    if df.empty or "kabine" not in df.columns:
        return pd.DataFrame()
    df = df[df["kabine"].notna() & (df["kabine"] != "")]
    grouped = df.groupby(["kabine", "tag", "zeit"])["team"].agg(list).reset_index()
    konflikte = grouped[grouped["team"].apply(len) > 1].copy()
    konflikte["anzahl"] = konflikte["team"].apply(len)
    konflikte["teams"] = konflikte["team"].apply(lambda t: ", ".join(t))
    return konflikte[["kabine", "tag", "zeit", "anzahl", "teams"]]


def get_cancellation_stats() -> pd.DataFrame:
    conn = db_connect()
    df = pd.read_sql(
        "SELECT team, COUNT(*) AS ausfaelle FROM training_ausfaelle GROUP BY team ORDER BY ausfaelle DESC",
        conn,
    )
    conn.close()
    return df


def parse_trainingsplan(source) -> pd.DataFrame:
    sections = [
        {"name": "Rasen", "sub_plaetze": ["Rasen vorne", "Rasen hinten"], "start_row": 0, "data_rows": 11},
        {"name": "Kunstrasen", "sub_plaetze": ["Kunstrasen vorne", "Kunstrasen hinten"], "start_row": 13, "data_rows": 11},
        {"name": "Wigger-Arena", "sub_plaetze": ["Wigger-Arena"], "start_row": 27, "data_rows": 11},
    ]
    if isinstance(source, str):
        df_raw = pd.read_csv(io.StringIO(source), header=None)
    else:
        df_raw = pd.read_excel(source, header=None)

    records: list[dict] = []
    for sec in sections:
        start = sec["start_row"]
        data_rows = df_raw.iloc[start + 1:start + 1 + sec["data_rows"]]
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
                            records.append({"Platz": sub_platz, "Bereich": sec["name"], "Tag": day, "Zeit": zeit, "Team": str(team).strip()})
    return pd.DataFrame(records, columns=["Platz", "Bereich", "Tag", "Zeit", "Team"])


def create_sample_csv() -> str:
    sample: dict[tuple, str] = {
        ("Rasen vorne", "Montag", "17:00"): "U19",
        ("Rasen vorne", "Dienstag", "18:00"): "1. Mannschaft",
        ("Rasen vorne", "Mittwoch", "17:00"): "U17",
        ("Rasen vorne", "Freitag", "16:00"): "U17",
        ("Rasen hinten", "Montag", "16:00"): "U15",
        ("Rasen hinten", "Donnerstag", "19:00"): "U13",
        ("Rasen hinten", "Samstag", "10:00"): "Damen",
        ("Kunstrasen vorne", "Dienstag", "17:00"): "Frauen",
        ("Kunstrasen vorne", "Freitag", "18:00"): "U11",
        ("Kunstrasen vorne", "Mittwoch", "18:30"): "U9",
        ("Kunstrasen hinten", "Mittwoch", "18:30"): "Alte Herren",
        ("Kunstrasen hinten", "Donnerstag", "17:00"): "U13",
        ("Wigger-Arena", "Dienstag", "18:00"): "1. Mannschaft",
        ("Wigger-Arena", "Donnerstag", "19:00"): "Frauen",
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
    day_name = DAYS[datum.weekday()]
    if day_name in ("Samstag", "Sonntag"):
        return LOCKER_ROOMS[:]
    conn = db_connect()
    rows = conn.execute(
        "SELECT DISTINCT kabine FROM saisonplanung WHERE tag=? AND zeit=? AND kabine != '' AND kabine IS NOT NULL",
        (day_name, uhrzeit),
    ).fetchall()
    conn.close()
    belegt = {r[0] for r in rows if r[0]}
    frei = [k for k in LOCKER_ROOMS if k not in belegt]
    return frei if frei else LOCKER_ROOMS[:]


def find_conflicts(df_training: pd.DataFrame, datum: date, uhrzeit: str, platz: str) -> list[str]:
    if df_training.empty:
        return []
    day_name = DAYS[datum.weekday()]
    check_plaetze = PITCH_HALVES.get(platz, [platz])
    hit = df_training[
        (df_training["Platz"].isin(check_plaetze)) &
        (df_training["Tag"] == day_name) &
        (df_training["Zeit"] == uhrzeit)
    ]
    return hit["Team"].tolist()
