import requests
import json
import pandas as pd
import cmu_course_api
from datetime import datetime
from pprint import pprint
import dateutil
import string
import re
import copy
from tqdm import tqdm
import sys
import pickle

SPACES_NOTES = {
    "HH 1305": "ECE Linux Cluster",
    "ANS 101": "ECE 18-220 Lab",
    "DH 2315": "Lørge lecture hall"
}

OVERRIDES = [
    ("CFA ACH", "category", "studio")
]

with open("cookie.dat", "r") as f:
    COOKIES_25LIVE = {"WSSESSIONID": f.read().strip()}

CATEGORIES = ["athletics", "computer_lab", "classroom", "cuc", "study_room", "admin", "other", "lab", "special_lab", "studio"]

BASE_URL_25LIVE = "https://25live.collegenet.com/25live/data/cmu/run"

SOC_FILE = "courses-f21.txt"
CURRENT_MINI = 1
CAMPUS = "Pittsburgh, Pennsylvania"

# Pulled from advisor course list - https://www.cmu.edu/es/docs/classrooms_fyy.pdf
# Parsed using https://tabula.technology/
REGISTRAR_FILE = "registrar-classrooms-f21.csv"


def strip(x):
    return " ".join(x.strip().split())

def req_25live_endpoint(url):
    out = requests.get(BASE_URL_25LIVE + url, cookies=COOKIES_25LIVE).text
    assert out.startswith(")]}\',\n")
    out = out[len(")]}\',\n"):]
    out = json.loads(out)
    return out

login = req_25live_endpoint("/login.json?caller=pro")
if "login_response" not in login or "login" not in login["login_response"] or "username" not in login["login_response"]["login"]:
    print("Invalid cookie")
    sys.exit(1)


def get_25live_space_categories():
    url = "/home/dash/panel-space-searches-collections.json?caller=pro-DashPanelDao.getSpaceSearchesCollections"
    data = req_25live_endpoint(url)
    data = data["spaceSearchesCollections"]
    data = {x["itemId"]: x["itemName"] for x in data}
    return data

def get_all_25live_spaces():
    page_size = 999
    url = f"/list/listdata.json?compsubject=location&order=asc&sort=name&page=1&page_size={page_size}&obj_cache_accl=0&max_capacity=9999999&caller=pro-ListService.getData"
    data = req_25live_endpoint(url)
    cols = [(x["prefname"] if "prefname" in x else x["name"]) for x in data["cols"]]
    rows = [{cols[i]: a for i, a in enumerate(x["row"])} for x in data["rows"]]
    spaces = [{
        "id": int(row["name"]["itemId"]),
        "name": strip(row["name"]["itemName"]),
        "full_name": strip(row.get("formal_name", row["name"]["itemName"])),
        "categories": [strip(x) for x in row.get("categories", "").split(",") if len(strip(x)) > 1],
        "features": [strip(x) for x in row.get("features", "").split(",") if len(strip(x)) > 1],
        "layouts": [strip(x) for x in row.get("layouts", "").split(",") if len(strip(x)) > 1],
        "default_capacity": int(row.get("default_capacity", 0)),
        "max_capacity": int(row.get("max_capacity", 0))
    } for row in rows]

    return spaces

def get_25live_timings_for_space(space_id, date, course_names={}):
    dt = date.strftime("%Y-%m-%d")
    url = f"/rm_reservations.json?space_id={space_id}&start_dt={dt}T00:00:00&end_dt={dt}T23:59:00&include=closed+blackouts+pending+related+empty&caller=pro-ReservationService.getReservations"

    if "space_reservation" not in req_25live_endpoint(url)["space_reservations"]:
        print(f"Warning: no reservations found for {space_id}")
        return []

    data = req_25live_endpoint(url)["space_reservations"]["space_reservation"]

    if not isinstance(data, list):
        data = [data]

    events = []
    for x in data:
        if "event" not in x:
            continue

        if x["event"]["event_type_name"] == "closed":
            continue

        coursenum = re.findall(r"\D(\d{5})\D", x["event"]["event_name"])
        if len(coursenum) == 1:
            course_name = course_names.get(coursenum[0], None)
        else:
            course_name = None

        events.append({
            "name": x["event"]["event_name"],
            "title": x["event"]["event_title"],
            "state": x["event"]["state_name"],
            "type": x["event"]["event_type_name"],
            "comment": x.get("reservation_comments", ""),
            "start": dateutil.parser.parse(x["reservation_start_dt"]).replace(tzinfo=None),
            "end": dateutil.parser.parse(x["reservation_end_dt"]).replace(tzinfo=None),
            "course_name": course_name
        })


    return events


def soc_include_location(building, room):
    if building is None or room is None:
        return False

    if room in ["REMOTE", "DNM"]:
        return False

    if building in ["DNM"]:
        return False

    if room.endswith("flr"):
        return False

    # TODO: include CUC?
    return building in ["ANS", "BH", "CFA", "CIC", "CYH", "DH", "GHC", "HBH",
                        "HH", "HL", "HOA", "MI", "MM", "NSH", "PCA", "PH", "POS", "REH",
                        "TCS", "TEP", "WEH", "WW"]

def get_all_soc_course_names():
    with open(SOC_FILE, "r") as f:
        data = json.load(f)

    data = data["courses"]
    data = {k.replace("-", ""): v["name"] for k, v in data.items()}
    return data

def get_all_soc_timings():
    with open(SOC_FILE, "r") as f:
        data = json.load(f)

    data = data["courses"]

    timings = []
    locations = set()

    for k, v in data.items():
        course_info = {
            "number": k,
            "name": v["name"],
            "department": v["department"]
        }

        for section in v["lectures"] + v["sections"]:
            if len(section["name"]) == 2 and section["name"][0] in string.ascii_uppercase and \
               section["name"][1].isdigit() and int(section["name"][1]) != CURRENT_MINI:
                continue

            for time in section["times"]:
                if time["location"] != CAMPUS or time["days"] is None:
                    continue

                if not soc_include_location(time["building"], time["room"]):
                    continue

                locations.add(f"{time['building']} {time['room']}")

                for day in time["days"]:
                    timings.append(dict(course_info, **{
                        "instructors": section["instructors"],
                        "location": f"{time['building']} {time['room']}",
                        "start": time["begin"],
                        "end": time["end"],
                        "day": day
                    }))

    locations = list(locations)
    timings = [{location: [x for x in timings if x["day"] == day and x["location"] == location] for location in locations}
               for day in range(7)]

    return timings, locations


def get_registrar_spaces():
    data = pd.read_csv(REGISTRAR_FILE)
    data = data.where(data.notnull(), None).to_dict("records")

    spaces = {}
    for x in data:
        if x["building"] is None or x["room"] is None or len(x["building"]) < 1 or len(x["room"]) < 1:
            continue

        if not soc_include_location(str(x["building"]), str(x["room"])):
            continue

        dept = x.get("department", "UNKNOWN")
        if dept is None: dept = "UNKNOWN"
        else: dept = dept.strip()

        capacity = x.get("capacity", 0)
        if capacity is None: capacity = 0
        elif capacity.endswith("+"): capacity = int(capacity[:-1])
        else: capacity = int(capacity)

        room_type = x.get("type", "UNKNOWN")
        if room_type is None: room_type = "UNKNOWN"
        else: room_type = room_type.strip()

        loc = f"{x['building'].strip()} {x['room'].strip()}"

        spaces[loc] = {
            "location": loc,
            "department": dept,
            "name": x.get("name", None),
            "capacity": capacity,
            "type": room_type
        }

    return spaces


def get_all_spaces():
    registrar_spaces = get_registrar_spaces()
    soc_timings, soc_spaces = get_all_soc_timings()
    spaces_25live = get_all_25live_spaces()

    spaces = []

    for space25 in spaces_25live:
        space = {}

        category = "other"
        if "Athletics" in space25["categories"]:
            category = "athletics"

        elif any(["Computing Services Lab" in x for x in space25["categories"]]):
            category = "computer_lab"

        elif "Registrar Classrooms" in space25["categories"] or (space25["name"] in list(registrar_spaces.keys()) + list(soc_spaces)):
            category = "classroom"

        elif len(space25["name"].split()) == 2 and soc_include_location(*space25["name"].split()):
            category = "classroom"

        elif "Cohon University Center" in space25["categories"] or space25["name"].startswith("Cohen University Center"):
            category = "cuc"

        elif space25["name"].startswith("CUC STUDY ROOM") or space25["name"].startswith("HBH INTERVIEW ROOM") or \
             space25["full_name"].startswith("Tepper Breakout Room") or space25["full_name"].startswith("Tepper Interview Room"):
            category = "study_room"

        elif "Welcome Center" in space25["full_name"]:
            category = "admin"

        else:
            category = "other"

        space["25live_id"] = space25["id"]
        space["category"] = category
        space["comment"] = ""

        registrar_match = [x for x in registrar_spaces.values() if x["location"] in space25["name"] or x["location"] in space25["full_name"]]
        assert len(registrar_match) < 2
        if len(registrar_match) == 1:
            registrar_match = registrar_match[0]
            registrar_spaces.pop(registrar_match["location"])

            space["location"] = registrar_match["location"]
            space["name"] = space25["full_name"]
            space["capacity"] = max(space25["max_capacity"], registrar_match["capacity"])

            if registrar_match["type"] == "COMPUTER LAB":
                space["category"] = "computer_lab"
            elif registrar_match["type"] in ["CLASSROOM", "LEARNING HALL", "AUDITORIUM"]:
                space["category"] = "classroom"
            elif registrar_match["type"].startswith("LAB") or registrar_match["type"].startswith("WET LAB"):
                space["category"] = "lab"
            elif registrar_match["type"] == "SPECIALTY SHOP":
                space["category"] = "special_lab"
            elif registrar_match["type"].startswith("STUDIO") or registrar_match["type"].startswith("THEATRE"):
                space["category"] = "studio"

            if registrar_match["name"] and len(registrar_match["name"]) > 1:
                space["comment"] += "Registrar Name: {}\n".format(registrar_match["name"])

            if registrar_match["type"]:
                space["comment"] += "Registrar Category: {}\n".format(registrar_match["type"])

            if registrar_match["department"]:
                space["comment"] += "Registrar Department: {}\n".format(registrar_match["department"])

            space["comment"] += "\n"

        else:
            space["location"] = space25["name"]
            space["name"] = space25["full_name"]
            space["capacity"] = space25["max_capacity"]


        soc_match = [x for x in soc_spaces if x in space25["name"] or x in space25["full_name"]]
        assert len(soc_match) < 2
        if len(soc_match) == 1:
            soc_match = soc_match[0]
            soc_spaces.remove(soc_match)
            space["location"] = soc_match

        if len(space25["features"]) > 0:
            space["comment"] += "Features: {}\n\n".format(", ".join(space25["features"]))

        space["notes"] = SPACES_NOTES.get(space["location"], "")
        space["comment"] = space["comment"].strip()

        for s, ok, ov in OVERRIDES:
            if s == space["location"]:
                assert ok in space.keys()
                space[ok] = ov

        spaces.append(space)

    for k, v in registrar_spaces.items():
        space = {}

        space["25live_id"] = None
        space["comment"] = ""
        space["location"] = v["location"]
        space["name"] = v["location"]
        space["capacity"] = v["capacity"]

        if v["type"] == "COMPUTER LAB":
            space["category"] = "computer_lab"
        elif v["type"] in ["CLASSROOM", "LEARNING HALL", "AUDITORIUM"]:
            space["category"] = "classroom"
        elif v["type"].startswith("LAB") or v["type"].startswith("WET LAB"):
            space["category"] = "lab"
        elif v["type"] == "SPECIALTY SHOP":
            space["category"] = "special_lab"
        elif v["type"].startswith("STUDIO") or v["type"].startswith("THEATRE"):
            space["category"] = "studio"
        else:
            space["category"] = "classroom"

        if v["name"] and len(v["name"]) > 1:
            space["comment"] += "Registrar Name: {}\n".format(v["name"])

        if v["type"]:
            space["comment"] += "Registrar Category: {}\n".format(v["type"])

        if v["department"]:
            space["comment"] += "Registrar Department: {}\n".format(v["department"])

        space["comment"] += "\n"

        soc_match = [x for x in soc_spaces if x in v["location"]]
        assert len(soc_match) < 2
        if len(soc_match) == 1:
            soc_match = soc_match[0]
            space["location"] = soc_match
            soc_spaces.remove(soc_match)

        space["notes"] = SPACES_NOTES.get(space["location"], "")
        space["comment"] = space["comment"].strip()

        for s, ok, ov in OVERRIDES:
            if s == space["location"]:
                assert ok in space.keys()
                space[ok] = ov

        spaces.append(space)


    for x in soc_spaces:
        space = {}

        space["25live_id"] = None
        space["comment"] = ""
        space["location"] = x
        space["name"] = x
        space["capacity"] = 0
        space["category"] = "classroom"
        space["notes"] = SPACES_NOTES.get(x, "")
        space["comment"] = space["comment"].strip()

        for s, ok, ov in OVERRIDES:
            if s == space["location"]:
                assert ok in space.keys()
                space[ok] = ov

        spaces.append(space)

    assert all(space["capacity"] >= 0 and space["capacity"] < 9999 for space in spaces)
    assert all(space["category"] in CATEGORIES for space in spaces)

    return spaces

def _create_event(event_soc, event25, date):
    if event_soc:
        start_time = dateutil.parser.parse(event_soc["start"])
        start_time = datetime(date.year, date.month, date.day, start_time.hour, start_time.minute, start_time.second)
        end_time = dateutil.parser.parse(event_soc["end"])
        end_time = datetime(date.year, date.month, date.day, end_time.hour, end_time.minute, end_time.second)

        if event25:
            start_time = min(start_time, event25["start"])
            end_time = max(end_time, event25["end"])
    else:
        start_time = event25["start"]
        end_time = event25["end"]

    if event_soc:
        name = f"{event_soc['number']}: {event_soc['name']}"
    else:
        title = event25["course_name"]
        if not title: title = ""
        title = title.strip()
        if len(title) < 1: title = event25["title"]
        name = f"{event25['name']}: {title}"

    if event_soc and event25:
        status = f"Course {event25['state']}".strip()
    elif event25:
        status = event25['state'].strip()
        if len(status) < 1: status = "Unknown"
    else:
        status = "Course"

    if event_soc and event25:
        source = "SOC & 25Live"
    elif event25:
        source = "25Live"
    else:
        source = "SOC"

    comment = ""

    if event_soc:
        instr = "; ".join(event_soc["instructors"])
        comment += f"Instructor(s): {instr}\n"

    if event25:
        comment += event25["name"] + "\n\n"
        comment += event25["comment"]

    comment = comment.strip()

    event = {
        "start": start_time,
        "end": end_time,
        "name": name,
        "status": status,
        "source": source,
        "comment": comment
    }

    return event

def get_space_events(space, soc_timings, date, course_names={}):
    day_of_week = date.isoweekday() % 7

    if space["25live_id"]:
        events25 = copy.deepcopy(get_25live_timings_for_space(space["25live_id"], date, course_names))
    else:
        events25 = []

    if space["location"] in soc_timings[day_of_week]:
        events_soc = copy.deepcopy(soc_timings[day_of_week][space["location"]])
    else:
        events_soc = []

    events = []

    for event_soc in events_soc[:]:

        # Allows for deletion while iterating
        if event_soc not in events_soc:
            continue

        start_time = dateutil.parser.parse(event_soc["start"])
        start_time = datetime(date.year, date.month, date.day, start_time.hour, start_time.minute, start_time.second)
        end_time = dateutil.parser.parse(event_soc["end"])
        end_time = datetime(date.year, date.month, date.day, end_time.hour, end_time.minute, end_time.second)

        e25 = [x for x in events25 if abs((x["start"] - start_time).seconds) <= 300 and abs((x["end"] - end_time).seconds) <= 300]
        for x in e25: events25.remove(x)

        if len(e25) > 0:
            e25 = e25[0]
        else:
            e25 = None

        soc_repeats = [x for x in events_soc if abs((dateutil.parser.parse(x["start"]) - start_time).seconds) <= 300 and abs((dateutil.parser.parse(x["end"]) - end_time).seconds) <= 300]
        for x in soc_repeats: events_soc.remove(x)

        events.append(_create_event(event_soc, e25, date))

    for event in events25[:]:
        # Allows for deletion while iterating
        if event not in events25:
            continue

        e25 = [x for x in events25 if abs((x["start"] - event["start"]).seconds) <= 300 and abs((x["end"] - event["end"]).seconds) <= 300]
        for x in e25: events25.remove(x)

        events.append(_create_event(None, event, date))

    return events


def get_all_events(spaces, soc_timings, date, course_names={}):
    return {space["name"]: get_space_events(space, soc_timings, date, course_names) for space in tqdm(spaces)}

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <date>")
    sys.exit(1)
else:
    date = dateutil.parser.parse(sys.argv[1])

spaces = get_all_spaces()
soc_timings, _ = get_all_soc_timings()
course_names = get_all_soc_course_names()

all_events = get_all_events(spaces, soc_timings, date, course_names)

with open("spaces.pkl", "wb+") as f:
    pickle.dump(spaces, f)

with open(f"events-{date.strftime('%Y-%m-%d')}.pkl", "wb+") as f:
    pickle.dump(all_events, f)
