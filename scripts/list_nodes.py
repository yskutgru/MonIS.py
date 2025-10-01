#!/usr/bin/env python3
"""List node ids and names from mon.node using DB config from config.py

Usage: run from repository root with project's python (venv):
PYTHONPATH=/home/kuznetsov_y_s/code/MonIS.py /home/kuznetsov_y_s/code/MonIS.py/venv/bin/python scripts/list_nodes.py
"""
import sys
from pprint import pprint

try:
    from config import get_db_config
    cfg = get_db_config()
except Exception as e:
    print(f"Failed to import config.py: {e}")
    cfg = None

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception as e:
    print("psycopg2 not installed in the active Python environment.")
    print("Install it in the project's venv, e.g.: pip install psycopg2-binary")
    psycopg2 = None
    RealDictCursor = None


def main():
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
        print(f"Failed to connect to DB with config {dsn}: {e}")
        sys.exit(4)

    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, name FROM mon.node ORDER BY name;")
                rows = cur.fetchall()
                if not rows:
                    print("No nodes found in mon.node table.")
                    return
                for r in rows:
                    print(r['id'], r.get('name'))
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    if cfg is None or psycopg2 is None:
        print('Missing configuration or psycopg2; aborting list_nodes.')
    else:
        main()
