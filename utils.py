import click
import sys
import pickle
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

def events_to_blocks(events):
    blocks = []
    events = sorted(events, key=lambda x: x["start"])

    if len(events) == 0:
        return []

    if len(events) > 0 and events[0]["start"].day != events[0]["end"].day:
        events[0]["start"] = datetime(events[0]["end"].year, events[0]["end"].month, events[0]["end"].day, 0, 0)

    if len(events) > 0 and events[-1]["start"].day != events[-1]["end"].day:
        events[-1]["end"] = datetime(events[-1]["start"].year, events[-1]["start"].month, events[-1]["start"].day, 23, 59)


    # Ensure all events are on the same day
    assert len(set(x["start"].year for x in events)) == 1
    assert len(set(x["start"].month for x in events)) == 1
    assert len(set(x["start"].day for x in events)) == 1

    y = events[0]["start"].year
    m = events[0]["start"].month
    d = events[0]["start"].day

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
