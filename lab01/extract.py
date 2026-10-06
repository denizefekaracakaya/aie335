"""Lab 01, step 1 - EXTRACT (generation -> ingestion).

Calls the DummyJSON API and saves each answer, untouched, in raw/.
raw/ is the raw zone: files are added, never edited.
"""
import csv                                      # writes the manifest file
import json                                     # turns Python data into JSON text
from datetime import date, datetime, timezone   # today's date and the download time
from pathlib import Path                        # file paths that work on every system

import requests                                 # makes the HTTP call to the API

BASE_URL = "https://dummyjson.com"              # the source system - we do not own it
ENDPOINTS = ["carts", "products", "users"]      # what we ask for: /carts, /products and /users
RAW = Path(__file__).parent / "raw"             # the folder raw/, next to this file


def main():
    RAW.mkdir(exist_ok=True)                    # create raw/ if it is not there yet
    today = date.today().isoformat()            # for example "2026-10-01"

    for name in ENDPOINTS:
        # one file per endpoint and per day, for example raw/carts_2026-10-01.json
        target = RAW / f"{name}_{today}.json"

        # safe to run twice: a raw file that exists is never downloaded again
        if target.exists():
            print(f"extract: {target.name} already exists - not downloaded again")
            continue                            # go on with the next endpoint

        url = f"{BASE_URL}/{name}?limit=0"          # limit=0 = all rows in one call
        response = requests.get(url, timeout=30)    # call the API; give up after 30 seconds
        response.raise_for_status()                 # stop here if the source is down
        data = response.json()                      # the answer as a Python dictionary
        rows = len(data[name])                      # how many carts (or products) arrived

        # save the answer exactly as it came - no cleaning, no selecting
        target.write_text(json.dumps(data), encoding="utf-8")

        # lineage: where did this file come from, and when?
        # "a" = append: every download adds one line, nothing is overwritten
        with open(RAW / "_manifest.csv", "a", newline="") as f:
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            csv.writer(f).writerow([now, url, target.name, rows])

        # observability: one line that says what this step did
        print(f"extract: {rows} {name} -> raw/{target.name}")


# run main() only when this file is started directly: python extract.py
if __name__ == "__main__":
    main()