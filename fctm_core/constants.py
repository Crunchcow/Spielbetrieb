import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fctm.db")
DEFAULT_ADMIN_PIN = "1234"

DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
WEEKDAYS_DISPLAY = DAYS[:5]

TIME_SLOTS_TRAINING = [f"{h:02d}:{m:02d}" for h in range(8, 22) for m in (0, 30)]

# Platzhaelften - nur fuer Trainingszwecke
PITCHES = [
    "Rasen vorne",
    "Rasen hinten",
    "Kunstrasen vorne",
    "Kunstrasen hinten",
    "Wigger-Arena",
]

# Gesamtplaetze - fuer Spielansetzungen (immer ganzer Platz)
PITCHES_SPIEL = [
    "Rasen",
    "Kunstrasen",
    "Wigger-Arena",
]

# Mapping: Gesamtplatz -> Training-Haelften fuer Konflikt-Erkennung
PITCH_HALVES: dict[str, list[str]] = {
    "Rasen": ["Rasen vorne", "Rasen hinten"],
    "Kunstrasen": ["Kunstrasen vorne", "Kunstrasen hinten"],
    "Wigger-Arena": ["Wigger-Arena"],
}

LOCKER_ROOMS = [f"Kabine {i}" for i in range(1, 7)]
