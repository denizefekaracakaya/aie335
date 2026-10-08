"""Lab 02, step 1 - EXTRACT (generation -> ingestion), page by page.

Reads each source of the DummyJSON API in pages and saves every page,
untouched, in raw/<source>/<date>/. A page that is already there is
never downloaded again, so a run that stopped half-way can simply be
started again.
"""
import csv                                      # writes the manifest file
import json                                     # reads a page we already have
import sys                                      # sys.exit() stops the program with an error
import time                                     # time.sleep() waits
from datetime import date, datetime, timezone   # today's date and the download time
from pathlib import Path                        # file paths that work on every system

import requests                                 # makes the HTTP calls to the API

BASE_URL = "https://dummyjson.com"              # the source system - we do not own it
RAW = Path(__file__).parent / "raw"             # the raw zone, next to this file

PAGE_SIZE = 30      # rows we ask for in one request
PAUSE = 0.5         # seconds we wait between two requests - a polite client
TIMEOUT = 10        # seconds we wait for one answer before we give up on it
MAX_TRIES = 4       # how often we ask for the same page before the run fails
BACKOFF = 1         # seconds before the second try; doubled every time: 1, 2, 4
RETRY_STATUS = {429, 500, 502, 503, 504}    # answers that may be different a moment later


# what we extract: source name -> the fields we ask for (None = all fields)
SOURCES = {
    "carts": None,
    "products": None,
    "users": "id,address",      # customers: 2 of their 28 fields - we take what we need, no more
}



def fetch(url, params):
    """One page from the API. Tries again when trying again can help; otherwise stops the program."""
    for attempt in range(1, MAX_TRIES + 1):             # attempt = 1, 2, 3, 4
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
        except (requests.ConnectionError, requests.Timeout) as error:
            # no answer at all: the network is down, or the source is too slow
            problem = type(error).__name__              # for example "ReadTimeout"
        else:
            if response.status_code == 200:             # 200 = OK: we have the page
                return response
            if response.status_code not in RETRY_STATUS:
                # for example 404 (not found): asking again will give the same answer
                sys.exit(f"extract: {response.url} answered {response.status_code} - not retried")
            problem = f"HTTP {response.status_code}"    # for example "HTTP 503"

        if attempt == MAX_TRIES:
            sys.exit(f"extract: gave up on {url} after {MAX_TRIES} tries ({problem})")

        wait = BACKOFF * 2 ** (attempt - 1)             # 1, 2, 4 seconds: each wait twice as long
        print(f"extract: {problem} - try {attempt} of {MAX_TRIES} failed, waiting {wait} s")
        time.sleep(wait)



def extract_source(name, select, today):
    """All pages of one source, into raw/<name>/<today>/."""
    folder = RAW / name / today                 # for example raw/carts/2026-10-08
    folder.mkdir(parents=True, exist_ok=True)   # create it, and raw/ and raw/carts/ if needed

    page = 1            # the page we are working on
    skip = 0            # how many rows the source must skip before this page
    total = None        # how many rows the source has - we learn it from the first page
    rows = 0            # how many rows we have in raw/ so far

    # go on until we have asked for every row; the first time total is still unknown
    while total is None or skip < total:
        target = folder / f"page_{page:04d}.json"       # page_0001.json, page_0002.json, ...

        if target.exists():
            # resume: this page arrived in an earlier run - read it, do not download it
            data = json.loads(target.read_text(encoding="utf-8"))
            print(f"extract: {name} page {page} kept - already in raw/")
        else:
            params = {"limit": PAGE_SIZE, "skip": skip}     # which page: 30 rows after skipping `skip`
            if select:
                params["select"] = select                   # ask only for the fields we need
            response = fetch(f"{BASE_URL}/{name}", params)
            data = response.json()                          # the answer as a Python dictionary

            # save the answer exactly as it came. First under a temporary name, then renamed:
            # if the program dies while writing, no half-written file ever looks like a page
            tmp = target.with_suffix(".tmp")
            tmp.write_text(response.text, encoding="utf-8")
            tmp.rename(target)

            # lineage: one manifest line per page - when, from which address, which file, how many rows
            with open(RAW / "_manifest.csv", "a", newline="") as f:
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                csv.writer(f).writerow([now, response.url, f"{name}/{today}/{target.name}", len(data[name])])

            print(f"extract: {name} page {page} -> raw/{name}/{today}/{target.name} ({len(data[name])} rows)")
            time.sleep(PAUSE)                               # do not hammer the source

        total = data["total"]           # every page repeats how many rows the source has
        rows += len(data[name])         # count what is in this page
        skip += PAGE_SIZE               # the next page starts 30 rows further
        page += 1

    # completeness: did we get everything the source said it has?
    if rows != total:
        sys.exit(f"extract: {name} is INCOMPLETE - {rows} rows in raw/, the source reports {total}")
    print(f"extract: {name} complete - {rows} rows in {page - 1} pages")


def main():
    today = date.today().isoformat()            # for example "2026-10-08"
    for name, select in SOURCES.items():        # one source after the other
        extract_source(name, select, today)


# run main() only when this file is started directly: python extract.py
if __name__ == "__main__":
    main()
