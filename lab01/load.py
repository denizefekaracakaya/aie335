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

    # data quality: every product must have a price - we multiply by it later
    missing = con.execute("SELECT count(*) FROM raw_products WHERE price IS NULL").fetchone()[0]
    if missing > 0:
        sys.exit(f"load: QUALITY CHECK FAILED - {missing} products have no price")
    print("load: quality checks passed")


if __name__ == "__main__":
    main()