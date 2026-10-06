"""Lab 01, step 4 - SERVE. Shows the result and exports it for a consumer."""
import sys
from pathlib import Path

import duckdb

HERE = Path(__file__).parent


def main():
    sys.stdout.reconfigure(encoding="utf-8")    # the table borders need UTF-8 (matters on Windows)
    con = duckdb.connect(str(HERE / "aie335.duckdb"), read_only=True)   # serving only reads

    # serving 1: show the results on the screen, for the person who runs the pipeline
    print("serve: revenue by product category (top 10)")
    con.sql("SELECT * FROM revenue_by_category LIMIT 10").show()
    print("serve: ten best-selling products")
    con.sql("SELECT * FROM top_products").show()

    # serving 2: export each whole table as a file, for someone who has no database
    out = HERE / "output"
    out.mkdir(exist_ok=True)                    # create output/ if it is not there yet
    for table in ["revenue_by_category", "top_products"]:
        target = out / f"{table}.csv"
        con.execute(f"COPY {table} TO '{target.as_posix()}' (HEADER)")   # HEADER = column names in line 1
        print(f"serve: wrote output/{target.name}")


if __name__ == "__main__":
    main()