import click
import sys
import pickle
import dateutil.parser
from datetime import datetime
from config import *

def load_events(date):
    try:
        with open(f"events-{date}.pkl", "rb") as f:
            events = pickle.load(f)
        return events

    except:
        click.echo(f"Events not downloaded for date '{date}'. Run `update` command to download.")
        sys.exit(1)

def get_spaces(spaces, category, min_capacity, filter, require_25live, fav_only):
    if len(spaces) == 0:
        click.echo("Spaces not downloaded. Run `update` command to download.", err=True)
        sys.exit(1)

    cat = category.split(",")

    if "default" in cat:
        cat += DEFAULT_CATEGORIES

    if "all" in cat:
        cat_spaces = spaces
    else:
        cat_spaces = [space for space in spaces if space["category"] in cat]

    if len(cat_spaces) == 0:
        click.echo("Invalid category or no spaces found", err)
        sys.exit(1)

    cat_spaces = [x for x in cat_spaces if (x["capacity"] is None or x["capacity"] < 1 or x["capacity"] >= min_capacity)]

    cat_spaces = [x for x in cat_spaces if filter.lower() in (x["location"] + x["name"] + x["notes"]).lower()]

    cat_spaces = [x for x in cat_spaces if (not require_25live) or x["25live_id"] is not None]

    cat_spaces = [x for x in cat_spaces if (not fav_only) or x["location"] in FAVORITES]

    if len(cat_spaces) == 0:
        click.echo("No spaces found with given capacity and filter keywords", err)
        sys.exit(1)

    return cat_spaces

def print_table(header, rows):
    assert len(header) == len(rows[0])

    lengths = [max(len(click.unstyle(header[i])), max(len(click.unstyle(row[i])) for row in rows)) for i in range(len(header))]

    header = [ljust_ansi(x, lengths[i]) for i, x in enumerate(header)]
    rows = [[ljust_ansi(x, lengths[i]) for i, x in enumerate(row)] for row in rows]

    if FANCY_TABLE:
        header_str = " │ ".join(header)
        click.echo("┌─" + ("".join(["─" if c != "│" else "┬" for c in header_str])) + "─┐")
        click.echo("│ " + header_str + " │")
        click.echo("├─" + ("".join(["─" if c != "│" else "┼" for c in header_str])) + "─┤")
        for row in rows:
            row_str = " │ ".join(row)
            click.echo("│ " + row_str + " │")

        click.echo("└─" + ("".join(["─" if c != "│" else "┴" for c in header_str])) + "─┘")
    else:
        header_str = " | ".join(header)
        click.echo(header_str)
        click.echo("-" * len(header_str))
        for row in rows:
            click.echo(" | ".join(row))

def format_time_delta(start, end):
    delta = end - start

    total_mins = delta.seconds // 60
    if end.hour == 23 and end.minute == 59 and total_mins % 10 == 9:
        total_mins += 1

    mins = total_mins % 60
    hrs = total_mins // 60

    if mins == 0:
        return f"{hrs}hr"
    else:
        # Max = 23hr59min = 9 characters
        return f"{hrs}hr {mins}min"

def parse_hours_delta(delta_str):
    try:
        return float(delta_str)
    except:
        pass

    try:
        if delta_str.endswith("h"):
            return float(delta_str[:-1])
        elif delta_str.endswith("hr"):
            return float(delta_str[:-2])
        elif delta_str.endswith("hrs"):
            return float(delta_str[:-3])

        elif delta_str.endswith("m"):
            return float(delta_str[:-1]) / 60.0
        elif delta_str.endswith("min"):
            return float(delta_str[:-3]) / 60.0
        elif delta_str.endswith("mins"):
            return float(delta_str[:-4]) / 60.0

    except:
        pass

    click.echo(f"Invalid number of hours '{delta_str}'", err=True)
    sys.exit(1)

def events_to_blocks(date, events):
    blocks = []
    events = sorted(events, key=lambda x: x["start"])

    y = date.year
    m = date.month
    d = date.day

    if len(events) == 0:
        return [{"start": datetime(y, m, d, 0, 0), "end": datetime(y, m, d, 23, 59), "available": True}]

    if len(events) > 0 and events[0]["start"].day != events[0]["end"].day:
        events[0]["start"] = datetime(events[0]["end"].year, events[0]["end"].month, events[0]["end"].day, 0, 0)

    if len(events) > 0 and events[-1]["start"].day != events[-1]["end"].day:
        events[-1]["end"] = datetime(events[-1]["start"].year, events[-1]["start"].month, events[-1]["start"].day, 23, 59)


    # Ensure all events are on the same day
    assert len(set(x["start"].year for x in events)) == 1
    assert len(set(x["start"].month for x in events)) == 1
    assert len(set(x["start"].day for x in events)) == 1

    cur_time = (0, 0)
    while len(events) > 0:
        if (events[0]["start"].hour, events[0]["start"].minute) > cur_time:
            blocks.append({"start": datetime(y, m, d, *cur_time), "end": events[0]["start"], "available": True})

        blocks.append({**events[0], "available": False})
        cur_time = (events[0]["end"].hour, events[0]["end"].minute)
        events = events[1:]

    if cur_time != (23, 59):
        blocks.append({"start": datetime(y, m, d, *cur_time), "end": datetime(y, m, d, 23, 59), "available": True})

    for i in range(len(blocks) - 1):
        if blocks[i+1]["start"] < blocks[i]["end"]:
            blocks[i]["end"] = blocks[i+1]["start"]

    return blocks

def ljust_ansi(string, length):
    plaintext = click.unstyle(string)
    if len(plaintext) < length:
        return string + (" " * (length - len(plaintext)))
    else:
        return string

def shorten(string, length):
    if len(string) > length:
        string = string[:length-3] + "..."
    return string

def find_available_rooms(rooms, date, start_time, end_time, verbose):
    all_cats = set(x["category"] for x in rooms)
    include_cat = len(all_cats) > 1

    events_all = load_events(date)
    blocks_all = [(room, events_to_blocks(dateutil.parser.parse(date), events_all[room["location"]])) for room in rooms]

    avail = []
    for room, blocks in blocks_all:
        time_block = None
        prev = None
        for block in blocks:
            if start_time >= block["start"] and start_time <= block["end"]:
                time_block = block
                break

            prev = block

        assert time_block is not None

        if prev is None:
            prev = {"end": time_block["start"], "name": "None"}

        if end_time <= time_block["end"] and time_block["available"]:
            avail.append((room, prev))

    avail = sorted(avail, key=lambda x: ("A" if x[0]["location"] in FAVORITES else "B") + x[0]["location"])

    header = ["Location", "Category", "Capacity", "Available"] + (["Previous Event"] if verbose else [])

    rows = [(click.style(x["location"], bold=x["location"] in FAVORITES,
                fg="green" if x["location"] in FAVORITES else "red" if x["25live_id"] is None else "white"),
             x["category"],
             str(x["capacity"]),
             y["end"].strftime('%I:%M%p')) + (shorten(y["name"], 40),) if verbose else tuple() for x, y in avail]

    if not include_cat:
        header = header[0:1] + header[2:]
        rows = [row[0:1] + row[2:] for row in rows]

    print_table(header, rows)
