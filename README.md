# AIE335

## Lab 01 - a first pipeline

Run it with `./lab01/run.sh` (with `.venv` activated). It pulls carts, products and users from
DummyJSON, loads them into DuckDB, and writes `revenue_by_category`, `top_products` and
`revenue_by_state`.

### C2 - breaking the quality check on purpose

When I changed the check in `load.py` from `price IS NULL` to `price > 100`, the run stopped right after load:

```
load: 208 rows -> raw_carts   (from carts_2026-10-07.json)
load: 194 rows -> raw_products   (from products_2026-10-07.json)
load: QUALITY CHECK FAILED - 61 products have no price
```

`transform.py` and `serve.py` never ran, and the CSV files in `output/` kept their old timestamps.
`sys.exit("...")` ends `load.py` with exit code 1, and `set -e` in `run.sh` stops the script at the
first command that fails.

That is the right behaviour: when data fails a check, it should not reach the consumer. If the
pipeline carried on, it would overwrite yesterday's good CSV with numbers built on bad data, and
nobody would notice. When it stops, the last good result stays in place and the error is easy to
see. It is better to fail loudly than to be silently wrong.
(The message "have no price" is wrong here because the check no longer tests for missing prices.
A check's message has to match what it actually checks.) I changed the check back afterwards.

### C3 - a third source

| File | Changed? | Why |
|---|---|---|
| `extract.py` | yes | add `"users"` to `ENDPOINTS` |
| `load.py` | yes | add `"users"` to `TABLES` |
| `transform.sql` | yes | new table `revenue_by_state` (reads `u.address.state` from the nested struct) |
| `transform.py` | yes, only for observability | print the row count of the new table |
| `serve.py` | no | it only serves the tables it is told to serve |
| `run.sh` | no | the order of the steps did not change |

Each change was one word in a list or one new SQL statement. The extract and load code is
generic over its list of sources, so a new source needs no new code. As a check, the revenue
summed over all 49 states is exactly the total in `cart_items` (3,456,709.58), and every cart's
`user_id` matches a user.

### 1. Lifecycle stages and undercurrents

| Stage | Where |
|---|---|
| Generation | DummyJSON API (`/carts`, `/products`, `/users`). The source system, which we do not own |
| Ingestion | `extract.py`: API to `raw/` |
| Storage | `raw/` (the raw zone: files are added, never edited) and `aie335.duckdb`, filled by `load.py` |
| Transformation | `transform.sql`, run by `transform.py` |
| Serving | `serve.py`: prints to the screen and writes CSV files to `output/` |

Undercurrents I practised:

- **Orchestration:** `run.sh` runs the steps in order, and `set -euo pipefail` stops at the first failure (C2).
- **Data management, data quality:** the checks in `load.py` (table not empty, every product has a price).
- **Data management, lineage:** `raw/_manifest.csv` records when each raw file was downloaded, from which URL, and how many rows it had.
- **DataOps, observability:** every step prints one line saying what it did (`extract: 208 users -> ...`, `transform: top_products has 10 rows`).
- **Data architecture:** an immutable raw zone, then result tables that are rebuilt from it (`CREATE OR REPLACE`). `extract.py` is safe to run twice because it never downloads an existing file again.
- **Software engineering:** git with small commits, pinned versions in `requirements.txt`, and SQL logic kept in its own file.
- **Security:** `.venv/`, `.env` and all data are in `.gitignore`. This mattered in C3, because `/users` returns passwords, SSNs and card numbers (fake ones, but real data would look the same).

### 2. The API renames `price` to `unit_price`

`extract.py` still succeeds, because it saves whatever the API sends. The table creation in
`load.py` also succeeds, because `row.*` simply makes a column called `unit_price`. The first
failure is the quality check in `load.py`, `SELECT count(*) FROM raw_products WHERE price IS NULL`:

```
_duckdb.BinderException: Binder Error: Referenced column "price" not found in FROM clause!
Candidate bindings: "unit_price"
```

This is a Python traceback, not our own `QUALITY CHECK FAILED` message. The pipeline still stops
at load, so the old outputs are not overwritten. If the cart items were renamed too,
`transform.sql` would also break at `item.price`, but that step is never reached. A real fix would
be an explicit schema check in `load.py` that names the missing column. DuckDB's "Candidate
bindings" hint already points at the rename.

### 3. Why `raw/` stays out of git, but `transform.sql` goes in

Git is for things people write. Data is something the code produces.

- `transform.sql` is logic. We want its history: who changed the definition of "revenue", when, and why. We want it reviewed and identical for everyone. If it is lost, it cannot be rebuilt.
- `raw/` is data. It can always be fetched again (and the manifest says from where). It grows every day, and git keeps every version forever, so the repository would bloat. Data can also hold personal or secret information (see `/users`), and anything pushed to git is very hard to remove. The same goes for `*.duckdb` and `output/`: the code can always rebuild them.

## Lab 02 - a real extractor

Run the pipeline with `cd lab02 && ./run.sh` (with `.venv` activated). The extractor reads
DummyJSON in pages, retries temporary failures with backoff, resumes from pages already on disk,
and requests only `id` and `address` for users. The load step checks that each source is complete.
The pipeline serves revenue by category, top products, and revenue by customer state, including
CSV outputs.

### Part C answers

1. **Why pages when `limit=0` returns everything?** The source may cap or reject very large
	responses, and a bounded page uses less memory. Pages also make retries and resuming cheaper:
	a failure only costs the current page, not the entire download.
2. **What if carts change during `skip` pagination?** An insertion or deletion can shift later
	offsets, causing a cart to be duplicated or missed. Comparing row count with `total` may not
	catch this if one duplicate replaces one missing row. A stable source snapshot or cursor-based
	pagination, plus checks for unique cart IDs and stable page/snapshot metadata, can detect or
	prevent it.
3. **How to handle a deletion request with immutable raw data?** Immutability is not a reason to
	retain data against a valid deletion request: identify and purge the person's records from raw
	storage, derived tables, exports, replicas, and backups under the applicable retention process,
	while recording the deletion action without retaining the deleted personal data. B4 reduced
	that work by never extracting the other 26 user fields.
4. **Build or buy?** A small team may keep a custom extractor when it is inexpensive to maintain
	and its behavior is valuable to the business. A managed connector is preferable when the team
	cannot reliably maintain retries, monitoring, schema changes, and integrations, and the cost of
	buying is lower than the engineering time and business risk of owning it.

### C2 - polite rate limiting

`fetch()` reads `x-ratelimit-remaining` on a successful response and waits 10 seconds below 10
remaining requests. This can be tested without a burst of API calls by mocking `requests.get` to
return a response with that header, and mocking `time.sleep` to assert it was called with `10`;
repeat with a value of `10` to assert there is no wait.

### C3 - changing the page size

With the existing 30-row pages still on disk, changing `PAGE_SIZE` to 50 makes `extract.py`
reuse those old pages while advancing `skip` by 50. It processes five 30-row cart files before
the offset reaches 208, so extraction reports **150 rows** against the source's **208** and stops
before `load.py`. Restore `PAGE_SIZE = 30`; the normal run then reuses all seven correctly aligned
pages and passes the completeness check.
