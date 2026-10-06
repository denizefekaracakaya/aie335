"""Lab 01, step 3 - TRANSFORM. Runs transform.sql inside DuckDB."""
from pathlib import Path

import duckdb

HERE = Path(__file__).parent


def main():
    con = duckdb.connect(str(HERE / "aie335.duckdb"))

    # read the SQL file as text and run all its statements, in order
    con.execute((HERE / "transform.sql").read_text(encoding="utf-8"))

    # observability: say how many rows each new table has
    for table in ["cart_items", "revenue_by_category", "top_products", "revenue_by_state"]:
        rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"transform: {table} has {rows} rows")


if __name__ == "__main__":
    main()