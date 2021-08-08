SPACES_NOTES = {
    "HH 1305": "ECE Linux Cluster",
    "ANS 101": "ECE 18-220 Lab",
    "DH 2315": "Lørge lecture hall"
}

OVERRIDES = [
    ("CFA ACH", "category", "studio")
]

FAVORITES = ["DH 2315"]

CATEGORIES = ["athletics", "computer_lab", "classroom", "cuc", "study_room", "admin", "other", "lab", "special_lab", "studio"]

DEFAULT_CATEGORIES = ["classroom"]

CURRENT_MINI = 1
CAMPUS = "Pittsburgh, Pennsylvania"

STAR_CHAR = "★ "
NO_STAR_CHAR = "☆ "
assert len(STAR_CHAR) == len(NO_STAR_CHAR)
SHOW_STARS = False
FANCY_TABLE = True

MAX_WIDTH = 80
MIN_AVAILABLE_TIME_SECONDS = 30*60 # Availability <30 minutes is marked as red
