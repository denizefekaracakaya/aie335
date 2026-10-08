# Lab 02 — Extraction: A Real Extractor

**AIE 335 Data Pipelines and Infrastructure** · Akdeniz University, Faculty of Engineering · 2026-2027 Fall

| | |
|---|---|
| **Date** | 08.10.2026 (Week 4) |
| **Lectures behind it** | Chapter 3 — Designing Good Data Architecture · Chapter 4 — Choosing Technologies |
| **Duration** | ≈ 2 hours: Part A ≈ 10 min · Part B ≈ 90 min · Part C ≈ 20 min (finish it at home) |
| **Environment** | Ubuntu 24.04 on WSL2 (Windows) or Terminal (macOS) — the one you set up in Lab 01 |
| **Graded?** | No — the labs are assessed through the term project, which grows out of this repository |

## Contents

- [What this lab is](#what-this-lab-is)
- [How to read this document](#how-to-read-this-document)
- [Part A — Start Lab 02](#part-a--start-lab-02)
- [Part B — A real extractor](#part-b--a-real-extractor)
- [Part C — Your turn](#part-c--your-turn)
- [Lab 02 and today's lectures](#lab-02-and-todays-lectures)
- [If something goes wrong](#if-something-goes-wrong)

---

## What this lab is

In Lab 01 your `extract.py` asked the source for everything in **one request**, and it stopped at
the first problem. That is fine for 208 carts. It is not how a source with 20 million rows is read,
and it is not how a pipeline survives a bad night.

Today you replace that one step with a real extractor. It reads the source **page by page**, it
**tries again** when the source or the network has a bad moment, it **continues where it stopped**
when you start it a second time, and it takes **only the fields you need**. The other steps of the
pipeline stay almost as they are — which is the point of having built them as separate steps.

**At the end of the lab you have:**

- a folder `lab02/` in your `aie335` repository, next to `lab01/`;
- an extractor that lands every page of every source in the raw zone, with a manifest line per page;
- a pipeline that notices by itself when a download is incomplete;
- a third source, the customers — with 2 of their 28 fields.

> **The data.** The same online shop as last week: the public DummyJSON API
> (<https://dummyjson.com>), no account, no key. Today we use three of its sources: `/carts`,
> `/products` and `/users` (the customers).

What you will have at the end:

```text
~/workspace/aie335/
├── lab01/                        last week - not touched today
└── lab02/
    ├── extract.py                new: page by page, with retries
    ├── load.py                   changed: reads all pages of a day
    ├── transform.sql             unchanged
    ├── transform.py              unchanged
    ├── serve.py                  unchanged
    ├── run.sh                    unchanged
    ├── raw/                      the raw zone                  (not in git)
    │   ├── _manifest.csv
    │   ├── carts/2026-10-08/page_0001.json ... page_0007.json
    │   ├── products/2026-10-08/page_0001.json ... page_0007.json
    │   └── users/2026-10-08/page_0001.json ... page_0007.json
    ├── output/                   what we serve                 (not in git)
    └── aie335.duckdb             the database                  (not in git)
```

> **A change of plan.** The Lab 01 document said that today would also bring a relational database.
> That part moves to a later lab: this one is about doing one thing — extraction from an API —
> properly.

---

## How to read this document

The conventions are those of Lab 01: a grey box is something you **type** or something you
**should see**; everything after `#` (Python, shell) or `--` (SQL) is a comment; after each piece
of code there is a section **What this code does**.

One thing is new. When an existing file changes, the document shows two boxes: **Find these
lines** and **Replace them with**. Find the first block in your file, select it, and type the
second block in its place. Keep the indentation — in Python the spaces at the start of a line are
part of the program.

---

## Part A — Start Lab 02

1. Open **Ubuntu**, go to your project and switch on the virtual environment:

   ```bash
   cd ~/workspace/aie335
   source .venv/bin/activate
   git status
   ```

   Your prompt starts with `(.venv)`. `git status` should say `nothing to commit, working tree
   clean`. If it lists changes in `lab01/`, commit them first (`git add .`, then
   `git commit -m "Lab 01: finish"`).

2. Create the folder for this lab and copy last week's **code** into it:

   ```bash
   mkdir lab02
   cp lab01/*.py lab01/*.sql lab01/run.sh lab02/
   cd lab02
   ls
   ```

   `cp` copies files: first what to copy, last where to. `*.py` means "every file whose name ends
   with `.py`". You should see six files:

   ```text
   extract.py  load.py  run.sh  serve.py  transform.py  transform.sql
   ```

   We copied the code and nothing else. `raw/`, `output/` and the database stay in `lab01/`: data
   and generated files are never copied around — the code rebuilds them.

3. Open VS Code on the project (`code ~/workspace/aie335`) and open the folder `lab02/` in the file
   list. From now on you edit the files in **`lab02/`**. Leave `lab01/` as it is: it is your
   working copy of last week.

### Checkpoint A

- [ ] the prompt starts with `(.venv)` and ends with `/aie335/lab02`
- [ ] `ls` shows the six files

---

## Part B — A real extractor

Five steps. Each one changes one thing and then runs the pipeline to see that it still works.

| Step | What changes | The idea from today's lectures |
|---|---|---|
| B1 | `extract.py` reads the source page by page | batch architecture |
| B2 | `load.py` reads all the pages of a day | loose coupling |
| B3 | `extract.py` tries again when a request fails | plan for failure |
| B4 | a third source, with only the fields we need | security and compliance |
| B5 | a run is stopped and started again | plan for failure |

### B1 · Read the source page by page

**Look at a page first.** An API that holds many rows does not give them all at once; it gives them
in pages, and you say which page you want. Ask DummyJSON for two carts, after skipping the first
four, and only three of their fields:

```bash
curl -s "https://dummyjson.com/carts?limit=2&skip=4&select=id,userId,total"
```

`curl` sends one HTTP request and prints the answer; `-s` (silent) hides its progress display. You
should see:

```text
{"carts":[{"id":5,"userId":5,"total":1467.88},{"id":6,"userId":6,"total":55453.86}],"total":208,"skip":4,"limit":2}
```

Read the answer: the rows you asked for are under `carts`, and next to them the source tells you
three things — it has `total` = 208 carts, it skipped 4, and it gave you at most 2. Those three
numbers are all an extractor needs:

| Parameter | Meaning |
|---|---|
| `limit` | how many rows you want in this answer — the page size |
| `skip` | how many rows the source passes over before the page starts |
| `select` | which fields you want; without it you get all of them |

**Predict before you go on:** with 208 carts and pages of 30, how many requests does it take to
read them all? How many carts are on the last page?

**Now the extractor.** Open `lab02/extract.py`, delete everything in it, and type the new version.
It is longer than last week's file; the structure is: settings at the top, one function that makes
a request, one function that reads all the pages of a source, and `main()`.

`lab02/extract.py`

```python
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

# what we extract: source name -> the fields we ask for (None = all fields)
SOURCES = {
    "carts": None,
    "products": None,
}


def fetch(url, params):
    """One request to the API. Returns the answer, or stops the program."""
    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()                 # stop here if the source answers with an error
    return response


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
```

**What this code does**

1. **The settings** are at the top, in capital letters, so that nobody has to search the code for
   them: the page size, the pause between two requests, and how long we wait for an answer.
   `SOURCES` lists what we extract. The value after each name is the list of fields we ask for;
   `None` means "all of them" — B4 uses it.
2. **`fetch()`** makes one request. Today it is three lines. In B3 it becomes the place where the
   pipeline deals with failure — which is why it is a function of its own.
3. **`extract_source()`** reads one source. For every page it builds the file name
   (`page_0001.json`, `page_0002.json`, …) and then does one of two things:
   - the file **exists** — the page arrived in an earlier run, so it is read from disk and not
     downloaded again;
   - the file **does not exist** — the page is requested with `limit` and `skip`, saved, and
     written into the manifest.
4. **The loop ends by itself.** Every answer contains `total`. After each page `skip` grows by 30;
   when `skip` reaches `total`, every row has been asked for.
5. **The file is written in two moves:** first under the name `page_0003.tmp`, then renamed to
   `page_0003.json`. If the program dies in the middle of writing, what is left is a `.tmp` file —
   never something that looks like a finished page.
6. **A completeness check** closes the function: the rows in all pages together must be exactly
   the number the source reported. If not, the program stops with an error.

Run it:

```bash
python extract.py
```

You should see one line per page, and one closing line per source:

```text
extract: carts page 1 -> raw/carts/2026-10-08/page_0001.json (30 rows)
extract: carts page 2 -> raw/carts/2026-10-08/page_0002.json (30 rows)
extract: carts page 3 -> raw/carts/2026-10-08/page_0003.json (30 rows)
extract: carts page 4 -> raw/carts/2026-10-08/page_0004.json (30 rows)
extract: carts page 5 -> raw/carts/2026-10-08/page_0005.json (30 rows)
extract: carts page 6 -> raw/carts/2026-10-08/page_0006.json (30 rows)
extract: carts page 7 -> raw/carts/2026-10-08/page_0007.json (28 rows)
extract: carts complete - 208 rows in 7 pages
extract: products page 1 -> raw/products/2026-10-08/page_0001.json (30 rows)
...
extract: products page 7 -> raw/products/2026-10-08/page_0007.json (14 rows)
extract: products complete - 194 rows in 7 pages
```

(The date in the folder names is the day you run the lab.) Was your prediction right — seven
requests, and 28 carts on the last page?

**Look at what arrived.**

```bash
ls raw
ls raw/carts
ls raw/carts/*/
head -n 3 raw/_manifest.csv
```

The raw zone now has one folder per source, inside it one folder per day, inside that one file per
page:

```text
_manifest.csv  carts  products
2026-10-08
page_0001.json  page_0002.json  page_0003.json  page_0004.json  page_0005.json  page_0006.json  page_0007.json
```

And the manifest has one line per page, with the exact address that was called:

```text
2026-10-08T12:10:09+00:00,https://dummyjson.com/carts?limit=30&skip=0,carts/2026-10-08/page_0001.json,30
2026-10-08T12:10:10+00:00,https://dummyjson.com/carts?limit=30&skip=30,carts/2026-10-08/page_0002.json,30
2026-10-08T12:10:11+00:00,https://dummyjson.com/carts?limit=30&skip=60,carts/2026-10-08/page_0003.json,30
```

**Run the step a second time. Before you run it — what do you expect?**

```bash
python extract.py
```

```text
extract: carts page 1 kept - already in raw/
extract: carts page 2 kept - already in raw/
...
extract: carts complete - 208 rows in 7 pages
extract: products page 1 kept - already in raw/
...
extract: products complete - 194 rows in 7 pages
```

Nothing is downloaded: every page of today is already there. The run still counts the rows and
confirms that each source is complete.

> **If your Lab 01 already has the customers (Part C3).** Your `load.py` and `transform.sql` expect
> a third source. Add this line to `SOURCES` now, under `"products": None,` — B4 explains why it
> looks like this — and run `python extract.py` once more:
>
> ```python
>     "users": "id,address",      # customers: 2 of their 28 fields - we take what we need, no more
> ```

> **Today's lecture — batch architecture.** Each page is a small batch: a bounded piece of the
> source, landed in the raw zone before anything else touches it. Reading a source in pieces keeps
> the memory you need small, keeps each request short, and — as you will see in B5 — means that a
> failure costs you one page, not the whole run.

### B2 · Load — read all the pages

Run the load step as it is:

```bash
python load.py
```

```text
load: no raw file for carts - run extract.py first
```

The data is there, but not where `load.py` looks for it: last week there was one file
`raw/carts_<date>.json`; now there is a folder of pages. The extract step changed what it
produces, so the step that reads it has to follow. Open `lab02/load.py`.

**Find these lines** (inside `main()`, in the `for` loop):

```python
        # all raw files of this kind, sorted by name - the date in the name
        # makes the newest file the last one
        files = sorted((HERE / "raw").glob(f"{name}_*.json"))
        if not files:
            sys.exit(f"load: no raw file for {name} - run extract.py first")
        newest = files[-1]

        # the file looks like {"carts": [ {...}, {...} ], "total": 208}
        # read_json() reads the file: one row, with the whole list in one column
        # unnest() turns the list into rows; row.* turns each object into columns
        # CREATE OR REPLACE: the table is rebuilt on every run, never appended to
        con.execute(f"""
            CREATE OR REPLACE TABLE raw_{name} AS
            SELECT row.*
            FROM (SELECT unnest({name}) AS row FROM read_json('{newest.as_posix()}'))
        """)

        # count what arrived; fetchone()[0] is the first value of the first row
        rows = con.execute(f"SELECT count(*) FROM raw_{name}").fetchone()[0]
        print(f"load: {rows} rows -> raw_{name}   (from {newest.name})")

        # data quality: an empty table is a failure, not a result
        if rows == 0:
            sys.exit(f"load: QUALITY CHECK FAILED - raw_{name} is empty")
```

**Replace them with:**

```python
        # the day folders of this source, sorted by name - the date in the name
        # makes the newest day the last one
        days = sorted(p for p in (HERE / "raw" / name).glob("*") if p.is_dir())
        if not days:
            sys.exit(f"load: no raw pages for {name} - run extract.py first")
        newest = days[-1]

        # a pattern instead of one file name: * stands for "any page number"
        pages = (newest / "page_*.json").as_posix()

        # every page looks like {"carts": [ {...}, {...} ], "total": 208, "skip": 0, "limit": 30}
        # read_json() reads all the pages: one row per page, with that page's list in one column
        # unnest() turns the lists into rows; row.* turns each object into columns
        # CREATE OR REPLACE: the table is rebuilt on every run, never appended to
        con.execute(f"""
            CREATE OR REPLACE TABLE raw_{name} AS
            SELECT row.*
            FROM (SELECT unnest({name}) AS row FROM read_json('{pages}'))
        """)

        # count what arrived; fetchone()[0] is the first value of the first row
        rows = con.execute(f"SELECT count(*) FROM raw_{name}").fetchone()[0]
        print(f"load: {rows} rows -> raw_{name}   (from raw/{name}/{newest.name})")

        # data quality: an empty table is a failure, not a result
        if rows == 0:
            sys.exit(f"load: QUALITY CHECK FAILED - raw_{name} is empty")

        # data quality: completeness - every page repeats how many rows the source has
        expected = con.execute(f"SELECT max(total) FROM read_json('{pages}')").fetchone()[0]
        if rows != expected:
            sys.exit(f"load: QUALITY CHECK FAILED - raw_{name} has {rows} rows, the source reported {expected}")
```

**What this code does**

1. It looks for the **day folders** of the source (`raw/carts/2026-10-08`, later also
   `raw/carts/2026-10-09`, …) and takes the newest one.
2. It gives DuckDB a **pattern** instead of a file name: `raw/carts/2026-10-08/page_*.json`.
   `read_json()` reads every file that fits the pattern. The rest of the statement is the one you
   know: `unnest()` turns the lists into rows, `row.*` turns the fields into columns.
3. It adds one more **quality check**. Every page repeats the source's `total`. If the table has
   fewer rows than that, pages are missing, and the load stops:
   `QUALITY CHECK FAILED - raw_carts has 150 rows, the source reported 208`.

Change nothing else in the file. Run the three remaining steps:

```bash
python load.py
python transform.py
python serve.py
```

You should see:

```text
load: 208 rows -> raw_carts   (from raw/carts/2026-10-08)
load: 194 rows -> raw_products   (from raw/products/2026-10-08)
load: quality checks passed
transform: cart_items has 800 rows
transform: revenue_by_category has 24 rows
serve: revenue by product category (top 10)
   ... the table, with the same numbers as last week ...
serve: wrote output/revenue_by_category.csv
```

(If you did Part C of Lab 01, you see your extra tables too.)

> **Today's lecture — loose coupling.** You replaced the extractor completely. `load.py` needed
> one block changed, because it reads what the extractor writes. `transform.sql`, `transform.py`,
> `serve.py` and `run.sh` were not opened at all: they know the tables `raw_carts` and
> `raw_products`, and nothing about files, pages or APIs. That is what a loosely coupled system
> buys you: a change stops at the next interface.

### B3 · Plan for failure

So far the extractor assumes that every request succeeds. In real life the network drops, the
source is restarted, or it tells you that you are asking too fast. A request can fail in two
different ways, and they call for different reactions:

| What happens | Example | Will asking again help? |
|---|---|---|
| No answer at all | the wi-fi drops; the source is too slow | **Probably** — try again |
| An answer that says "not now" | `429` too many requests · `500`, `502`, `503`, `504` server trouble | **Probably** — wait, then try again |
| An answer that says "no" | `404` not found · `400` bad request · `401` not allowed | **No** — the request itself is wrong; stop and tell a person |

Open `lab02/extract.py`. First add three settings.

**Find this line:**

```python
TIMEOUT = 10        # seconds we wait for one answer before we give up on it
```

**Add these three lines under it:**

```python
MAX_TRIES = 4       # how often we ask for the same page before the run fails
BACKOFF = 1         # seconds before the second try; doubled every time: 1, 2, 4
RETRY_STATUS = {429, 500, 502, 503, 504}    # answers that may be different a moment later
```

Then replace the function `fetch()`.

**Find these lines:**

```python
def fetch(url, params):
    """One request to the API. Returns the answer, or stops the program."""
    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()                 # stop here if the source answers with an error
    return response
```

**Replace them with:**

```python
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
```

**What this code does**

1. The request is now inside a loop that runs at most `MAX_TRIES` = 4 times.
2. `try … except` catches the case **"no answer"**: `requests` raises `ConnectionError` when it
   cannot reach the source and `Timeout` when the answer does not come within `TIMEOUT` seconds.
3. If there **is** an answer, its status code decides: `200` returns the page; a code in
   `RETRY_STATUS` is worth another try; anything else stops the program at once, with the address
   and the code in the message.
4. Between two tries the program **waits**, and each wait is twice as long as the one before: 1,
   2, then 4 seconds. This is called **exponential backoff**. A source that is struggling does not
   get better if every client asks again immediately.
5. After the fourth failure the program **gives up** with `sys.exit(...)` — an error, so `run.sh`
   stops and no later step runs on missing data.

**Try it — four experiments.** DummyJSON has two features made for exactly this: the address
`/http/<code>` answers with any status code you name, and the parameter `delay` makes an answer
slow. Each command below starts Python, imports your file and calls `fetch()` once.

*1. The source says "not now" (503).* Before you run it: how long will this take?

```bash
python -c 'import extract; extract.fetch("https://dummyjson.com/http/503/down", {})'
```

```text
extract: HTTP 503 - try 1 of 4 failed, waiting 1 s
extract: HTTP 503 - try 2 of 4 failed, waiting 2 s
extract: HTTP 503 - try 3 of 4 failed, waiting 4 s
extract: gave up on https://dummyjson.com/http/503/down after 4 tries (HTTP 503)
```

*2. The source says "no" (404).*

```bash
python -c 'import extract; extract.fetch("https://dummyjson.com/http/404/gone", {})'
```

```text
extract: https://dummyjson.com/http/404/gone answered 404 - not retried
```

No waiting: the message comes at once.

*3. The source is too slow.* It needs 5 seconds, and for this test we wait only 3:

```bash
python -c 'import extract; extract.TIMEOUT = 3; extract.fetch("https://dummyjson.com/products/1", {"delay": 5000})'
```

```text
extract: ReadTimeout - try 1 of 4 failed, waiting 1 s
extract: ReadTimeout - try 2 of 4 failed, waiting 2 s
extract: ReadTimeout - try 3 of 4 failed, waiting 4 s
extract: gave up on https://dummyjson.com/products/1 after 4 tries (ReadTimeout)
```

*4. The source is slow, but within our patience.* 2 seconds of delay, and the normal timeout of 10:

```bash
python -c 'import extract; r = extract.fetch("https://dummyjson.com/products/1", {"delay": 2000}); print(r.status_code)'
```

```text
200
```

After experiments 1 to 3, type `echo $?` — it prints the exit code of the last command. It is `1`:
the program ended with an error. After experiment 4 it is `0`.

Finally, check that the normal run still works:

```bash
./run.sh
```

> **Today's lecture — plan for failure.** You did not make failure impossible; you decided in
> advance what happens when it comes. A short problem (a few seconds) is now absorbed without
> anybody noticing. A long one stops the pipeline with a message that says which address failed
> and how. Those are the two outcomes you want — the one you do not want is a pipeline that
> continues with half the data.

### B4 · Take less: the customers

The analyst's next question is **revenue per customer state**. The customers are a third source,
`/users`. Look at one of them before you extract anything:

```bash
curl -s "https://dummyjson.com/users/1" | python -m json.tool | grep -n "password\|cardNumber\|ssn"
```

`python -m json.tool` formats the JSON, one field per line; `grep` keeps the lines that contain one
of the three words (`\|` means "or"), and `-n` adds the line number. You should see:

```text
11:    "password": "emilyspass",
39:        "cardNumber": "3693233511855044",
62:    "ssn": "900-590-289",
```

The data is invented, but the shape is realistic: each customer has **28 fields**, among them a
password, a card number and a social security number. For revenue per state we need two: the
customer's `id` (to match the carts) and the `address` (the state is inside it).

Everything you extract, you have to store, protect, document — and delete when the customer asks
you to. What you never extract costs you none of that. So we ask the source for the two fields and
nothing else.

Open `lab02/extract.py`.

**Find these lines:**

```python
SOURCES = {
    "carts": None,
    "products": None,
}
```

**Replace them with:**

```python
SOURCES = {
    "carts": None,
    "products": None,
    "users": "id,address",      # customers: 2 of their 28 fields - we take what we need, no more
}
```

Then open `lab02/load.py`.

**Find this line:**

```python
TABLES = ["carts", "products"]  # one table per raw file: raw_carts, raw_products
```

**Replace it with:**

```python
TABLES = ["carts", "products", "users"]  # one table per source: raw_carts, raw_products, raw_users
```

(If you added the customers in Lab 01, both changes are already in your files.)

**What this code does.** In `extract_source()` you already typed the two lines that use the value:
`if select: params["select"] = select`. For `carts` and `products` the value is `None`, so nothing
is added; for `users` the request becomes `…/users?limit=30&skip=0&select=id,address`. The source
does the selecting — the other 26 fields never leave it.

**Do not run anything yet.** The first download of the customers is the experiment of the next
step.

> **Today's lecture — security and compliance.** "Collect it all, we may need it one day" is how
> pipelines end up holding passwords nobody asked for. Under the GDPR and the KVKK, personal data
> may be collected for a stated purpose and no further. Deciding **at the source** what you take is
> the cheapest security measure there is.

### B5 · Stop it, and start it again

A long extraction will be interrupted one day — a laptop goes to sleep, a server is restarted. The
question is what the next run does. Yours can answer it now.

1. Start the extractor. The carts and products are kept; the customers start to download, about
   one page per second:

   ```bash
   python extract.py
   ```

2. **As soon as you see the second or third `users` line, press `Ctrl+C`.** That is how you stop
   a program in the terminal. Python ends with a long message whose last line is:

   ```text
   KeyboardInterrupt
   ```

   This is what a crash looks like: the program stopped in the middle, with no chance to tidy up.

3. Look at what the interrupted run left behind:

   ```bash
   ls raw/users/*/
   ```

   You see the pages that were finished — for example `page_0001.json  page_0002.json
   page_0003.json` — and nothing half-written.

4. Suppose nobody noticed the crash, and the next step runs:

   ```bash
   python load.py
   ```

   ```text
   load: 208 rows -> raw_carts   (from raw/carts/2026-10-08)
   load: 194 rows -> raw_products   (from raw/products/2026-10-08)
   load: 90 rows -> raw_users   (from raw/users/2026-10-08)
   load: QUALITY CHECK FAILED - raw_users has 90 rows, the source reported 208
   ```

   (Your number depends on when you pressed the keys.) The check you added in B2 caught it:
   incomplete data did not travel on.

5. Start the extractor again:

   ```bash
   python extract.py
   ```

   ```text
   ...
   extract: users page 1 kept - already in raw/
   extract: users page 2 kept - already in raw/
   extract: users page 3 kept - already in raw/
   extract: users page 4 -> raw/users/2026-10-08/page_0004.json (30 rows)
   extract: users page 5 -> raw/users/2026-10-08/page_0005.json (30 rows)
   extract: users page 6 -> raw/users/2026-10-08/page_0006.json (30 rows)
   extract: users page 7 -> raw/users/2026-10-08/page_0007.json (28 rows)
   extract: users complete - 208 rows in 7 pages
   ```

   The run continued at the first missing page. Nothing was downloaded twice.

6. Now the load passes:

   ```bash
   python load.py
   ```

   ```text
   load: 208 rows -> raw_carts   (from raw/carts/2026-10-08)
   load: 194 rows -> raw_products   (from raw/products/2026-10-08)
   load: 208 rows -> raw_users   (from raw/users/2026-10-08)
   load: quality checks passed
   ```

> **Too slow with `Ctrl+C`?** If all seven pages arrived before you pressed the keys — or if you
> already downloaded the customers in B1 — delete today's customer pages and try again:
> `rm -r raw/users`. This is the only time in this course that you delete something from `raw/` —
> and only because no later step depends on these pages yet.

**Look at what you extracted:**

```bash
python -c 'import duckdb; duckdb.connect("aie335.duckdb", read_only=True).sql("SELECT id, address.city, address.state FROM raw_users LIMIT 3").show()'
```

```text
┌───────┬────────────┬─────────────┐
│  id   │    city    │    state    │
│ int64 │  varchar   │   varchar   │
├───────┼────────────┼─────────────┤
│     1 │ Phoenix    │ Mississippi │
│     2 │ Houston    │ Alabama     │
│     3 │ Washington │ Alabama     │
└───────┴────────────┴─────────────┘
```

`raw_users` has two columns, `id` and `address`. The password, the card number and the other 24
fields are not in your raw zone, not in your database and not in your backups — because they
never left the source.

> **Today's lecture — the 48-hour pipeline.** The story in the Chapter 4 lecture was a pipeline
> that took two days to run and started from the beginning whenever anything broke. Yours now
> continues where it stopped. Two small design choices did that: every page is its own file, and a
> file only gets its final name when it is complete.

### B6 · Run everything, commit and push

1. The files you copied still say `Lab 01` in their first comment. Change it to `Lab 02` in
   `load.py`, `transform.py`, `transform.sql`, `serve.py` and in the second line of `run.sh` — a
   comment that is wrong is worse than no comment. Then run the whole pipeline:

   ```bash
   ./run.sh
   ```

   Every step prints its lines, and the run ends with `serve: wrote output/…`.

2. Open `README.md` (in the top folder `aie335/`) and add a short section for Lab 02: what the new
   extractor does, and how to run it (`cd lab02`, then `./run.sh`). Save it.

3. Commit and push:

   ```bash
   cd ~/workspace/aie335
   git add .
   git status
   git commit -m "Lab 02: a real extractor"
   git push
   ```

Read the `git status` list before you commit: `README.md` and the six files in `lab02/`. The folder
`lab02/raw/` is **not** in it — the `.gitignore` you wrote last week covers every `raw/` folder in
the repository.

### Checkpoint B — show your instructor

- [ ] `./run.sh` finishes without an error, and running it again downloads nothing
- [ ] `raw/` has three source folders with seven pages each
- [ ] you can say what happens on a 503, and what happens on a 404
- [ ] the commit "Lab 02: a real extractor" is on GitHub

---

## Part C — Your turn

No code is given here. Work it out, run it, commit it.

### C1 · Use the customers

The analyst wants the **revenue per customer state**: state, number of customers who bought
something, revenue after discount, highest revenue first. Add a table `revenue_by_state` to
`transform.sql`, make `transform.py` print its row count, and make `serve.py` show it and export
it. (If you did C3 in Lab 01, you already have it — check that it still gives a result now that
`raw_users` has only two columns.)

### C2 · A polite client

Every answer of DummyJSON carries headers that say how many requests you may still send:
`x-ratelimit-limit` and `x-ratelimit-remaining`. See them with
`curl -s -D - -o /dev/null "https://dummyjson.com/products?limit=1" | grep -i ratelimit`.
Make `fetch()` read `x-ratelimit-remaining` after a successful request, and pause for ten seconds
when fewer than ten requests are left. (`response.headers` behaves like a dictionary.) How can you
test your change without sending a hundred requests?

### C3 · Break it on purpose

In `extract.py`, change `PAGE_SIZE` from `30` to `50` and run `./run.sh`. What happens, and which
step notices? Explain the number in the message. Change it back afterwards and confirm that the
pipeline runs again.

### Questions to answer in your README

1. Why does the extractor read the source in pages, when `limit=0` gives everything in one request?
   Give two reasons.
2. While your extractor is on page 3, a customer of the shop creates a new cart — or deletes one.
   What can go wrong with `limit` and `skip`? Would your completeness checks notice? What kind of
   check would?
3. A customer writes: "delete all the data you hold about me." Your raw zone is immutable. What do
   you do? And how did B4 make this problem smaller?
4. Build or buy: you wrote about a hundred lines to extract from one API. Give one reason to keep
   your own extractor, and one reason to replace it with a ready-made tool. Use the three
   questions from the Chapter 4 lecture: your team, the cost, the business value.

---

## Lab 02 and today's lectures

| From the lectures | What you did today |
|---|---|
| Batch architecture (Ch 3) | Read each source in bounded pieces and landed every piece in the raw zone |
| Loose coupling (Ch 3) | Replaced the extractor; `transform.sql`, `serve.py` and `run.sh` did not change |
| Plan for failure (Ch 3) | A timeout, retries with backoff, a run that can be started again, a completeness check in two places |
| Prioritize security; compliance (Ch 3) | Took 2 of 28 customer fields: what you never extract, you never have to protect or delete |
| The 48-hour pipeline (Ch 4) | A run that stops continues from the first missing page, not from the beginning |
| Build or buy (Ch 4) | You built an extractor; README question 4 asks when you would not |

| Undercurrent | What you did today |
|---|---|
| Security | Did not extract passwords, card numbers or identity numbers |
| Data management | One manifest line per page (lineage); two completeness checks (data quality); a raw zone that is still immutable |
| DataOps | One printed line per page and per source (observability); error messages that name the address and the code |
| Data architecture | Settings separated from logic; one function for requests, one for sources |
| Orchestration | `run.sh` still runs the steps in order and stops at the first failure |
| Software engineering | A second lab folder in the same repository; a commit that says what changed |

**Before the next lab:** finish Part C and push it. Lab 03 is about source systems: you will meet
a document database (MongoDB Atlas, free). Create the account when the instructions are announced.

---

## If something goes wrong

The problems of Lab 01 (the virtual environment, the wrong folder, a file that is not saved, the
database lock) are in the table at the end of the Lab 01 document. New today:

| What you see | What to do |
|---|---|
| `curl: command not found` | `sudo apt install -y curl` |
| `KeyboardInterrupt` and a long message | You pressed `Ctrl+C` — in B5 that is the plan. Anywhere else: just run the step again; it continues where it stopped. |
| `extract: … is INCOMPLETE - 150 rows in raw/, the source reports 208` | The page size was changed after pages had been downloaded today. Set `PAGE_SIZE` back to `30`. |
| `extract: gave up on … after 4 tries (ConnectionError)` | No network, or the API is down. Check the wi-fi and run the step again — pages that arrived are kept. If the API stays down, ask your instructor for the sample pages and copy them into `lab02/raw/`. |
| `extract: … answered 404 - not retried` | A typing mistake in `BASE_URL` or in a source name in `SOURCES`. |
| `load: no raw file for carts - run extract.py first` | `load.py` is still last week's version — do B2. |
| `load: no raw pages for users - run extract.py first` | `users` is in `TABLES` but not yet extracted: do B4 and B5, or run `python extract.py`. |
| `load: QUALITY CHECK FAILED - raw_… has … rows, the source reported …` | The extraction of that source is not complete. Run `python extract.py` again. |
| `Catalog Error: Table with name raw_users does not exist` | Your `transform.sql` from Lab 01 uses the customers. Do B4 and B5 first, then run `python load.py`. |
| `NameError: name 'MAX_TRIES' is not defined` | The three settings of B3 are missing at the top of `extract.py`. |
| `IndentationError` after a replacement | The new block must start at the same depth as the lines it replaces. Compare the spaces at the start of the lines with this document. |
| A file `page_0004.tmp` in a day folder | Left by an interrupted run. It is harmless: the next run writes the page again and replaces it. |
