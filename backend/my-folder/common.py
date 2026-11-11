import csv
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import config

DT_FORMAT = "%Y-%m-%dT%H:%M:%S"


def minor_unit(currency):
    """0.01 for USD/EUR/GBP, 1 for JPY."""
    return Decimal(1).scaleb(-config.CURRENCIES[currency]["decimals"])


def money(value, currency):
    """Round a number to the currency minor unit using ROUND_HALF_UP."""
    return Decimal(str(value)).quantize(minor_unit(currency), rounding=ROUND_HALF_UP)


def tolerance(currency):
    return Decimal(config.CURRENCIES[currency]["tolerance"])


def fmt_dt(dt):
    return dt.strftime(DT_FORMAT)


def parse_dt(text):
    return datetime.strptime(text, DT_FORMAT)


def parse_date(text):
    return date.fromisoformat(text)


def business_days(start, count):
    """Return `count` weekdays starting from `start`."""
    days, d = [], start
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def write_csv(path, rows, columns):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: "" if row.get(c) is None else row.get(c) for c in columns})


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
        f.write("\n")


def save_table(folder, table_name, rows, with_json=True):
    """Write a table as CSV (and JSON) using the column order from schema.py."""
    from schema import TABLES
    columns = [c["name"] for c in TABLES[table_name]["columns"]]
    write_csv(os.path.join(folder, f"{table_name}.csv"), rows, columns)
    if with_json:
        clean = [{c: ("" if r.get(c) is None else str(r.get(c))) for c in columns} for r in rows]
        write_json(os.path.join(folder, "json", f"{table_name}.json"), clean)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


