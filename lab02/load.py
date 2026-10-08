"""Lab 01, step 2 - LOAD (storage).

Loads the newest raw file of each kind into a DuckDB table, then checks it.
"""
import sys                      # sys.exit() stops the program with an error message
from pathlib import Path

import duckdb                   # the database engine - it runs inside this program

HERE = Path(__file__).parent    # the folder this file is in (lab01/)
TABLES = ["carts", "products", "users"]  # one table per raw file: raw_carts, raw_products, raw_users


def main():
    # open the database file; DuckDB creates it if it does not exist yet
    con = duckdb.connect(str(HERE / "aie335.duckdb"))

    for name in TABLES:
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


    # data quality: every product must have a price - we multiply by it later
    missing = con.execute("SELECT count(*) FROM raw_products WHERE price IS NULL").fetchone()[0]
    if missing > 0:
        sys.exit(f"load: QUALITY CHECK FAILED - {missing} products have no price")
    print("load: quality checks passed")


if __name__ == "__main__":
    main()