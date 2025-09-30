#!/usr/bin/env python3
"""Inspect 'mon' schema: tables, columns, and sample rows for selected tables."""
import sys
from pprint import pprint

try:
    from config import get_db_config
except Exception as e:
    print(f"Failed to import config: {e}")
    sys.exit(2)

cfg = get_db_config()

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception as e:
    print("psycopg2 not installed in the active environment. Install psycopg2-binary in venv.")
    sys.exit(3)


def run():
    dsn = {
        'host': cfg.get('host'),
        'dbname': cfg.get('database'),
        'user': cfg.get('user'),
        'password': cfg.get('password'),
        'port': cfg.get('port'),
        'connect_timeout': cfg.get('connect_timeout', 10)
    }

    try:
        conn = psycopg2.connect(**dsn)
    except Exception as e:
        print(f"Failed to connect to DB: {e}")
        sys.exit(4)

    try:
        with conn:
            with conn.cursor() as cur:
                print("Tables in schema 'mon':")
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='mon' ORDER BY table_name;")
                tables = [r[0] for r in cur.fetchall()]
                pprint(tables)

                def show_columns(table):
                    cur.execute(
                        """
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_schema='mon' AND table_name=%s
                        ORDER BY ordinal_position
                        """,
                        (table,)
                    )
                    cols = cur.fetchall()
                    print(f"\nColumns for {table}:")
                    for c in cols:
                        print(" ", c)

                def sample_rows(table, limit=10):
                    try:
                        cur.execute(f"SELECT * FROM mon.{table} LIMIT %s", (limit,))
                        rows = cur.fetchall()
                        print(f"\nSample rows from {table} (up to {limit}):")
                        for r in rows:
                            print(" ", r)
                    except Exception as e:
                        print(f" Cannot read from {table}: {e}")

                for t in tables:
                    show_columns(t)

                # Show samples of key tables if present
                key_tables = ['node', 'request', 'request_group', 'request_group_ref', 'task', 'crontab']
                for kt in key_tables:
                    if kt in tables:
                        sample_rows(kt, limit=20)
                    else:
                        print(f"\nTable mon.{kt} not found.")

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    run()
