import argparse
import os
import sqlite3

from common import read_csv
from schema import TABLES, VIEWS_SQL, create_table_sql, schema_sql

LOAD_ORDER = ["merchants", "payment_orders", "payment_attempts", "processor_events", "settlement_batches",
              "settlement_lines", "bank_statement_lines", "event_dedup_log", "reconciliation_matches",
              "exceptions", "resolutions"]


def run(scale_dir, write_seed_sql=True, quiet=False):
    sql_dir = os.path.join(scale_dir, "sql")
    os.makedirs(sql_dir, exist_ok=True)
    db_path = os.path.join(sql_dir, "payments.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    with open(os.path.join(sql_dir, "schema.sql"), "w", encoding="utf-8") as f:
        f.write(schema_sql())

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    counts = {}
    for name in LOAD_ORDER:
        path = os.path.join(scale_dir, TABLES[name]["folder"], f"{name}.csv")
        if not os.path.exists(path):
            continue
        conn.execute(create_table_sql(name))
        cols = [c["name"] for c in TABLES[name]["columns"]]
        rows = [[(r[c] if r[c] != "" else None) for c in cols] for r in read_csv(path)]
        conn.executemany(f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", rows)
        counts[name] = len(rows)
    conn.executescript(VIEWS_SQL)
    conn.commit()
    fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()

    joins = {
        "orders_without_merchant": "SELECT COUNT(*) FROM payment_orders o LEFT JOIN merchants m USING (merchant_id) WHERE m.merchant_id IS NULL",
        "lines_without_batch": "SELECT COUNT(*) FROM settlement_lines l LEFT JOIN settlement_batches b USING (batch_id) WHERE b.batch_id IS NULL",
        "lines_without_event": "SELECT COUNT(*) FROM settlement_lines l WHERE l.event_id NOT IN (SELECT event_id FROM processor_events)",
        "open_exceptions_by_status": "SELECT current_status || ':' || COUNT(*) FROM exception_current_status GROUP BY current_status",
    }
    join_results = {k: [r[0] for r in conn.execute(q).fetchall()] for k, q in joins.items()}

    if write_seed_sql:
        with open(os.path.join(sql_dir, "seed.sql"), "w", encoding="utf-8") as f:
            for line in conn.iterdump():
                f.write(line + "\n")
    conn.close()
    if not quiet:
        print(f"[export_sql] loaded {sum(counts.values()):,} rows into {db_path}; FK violations: {len(fk_errors)}")
    return {"rows": counts, "fk_violations": len(fk_errors), "join_checks": join_results}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="starter")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    run(a.out or os.path.join("output", a.scale))
