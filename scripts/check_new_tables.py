#!/usr/bin/env python3
"""Quick checks for newly-created tables/rows: handler, arp_table, mac_addresses, node_group refs."""
from pprint import pprint
try:
    from config import get_db_config
except Exception as e:
    print(f"Failed to import config: {e}")
    raise

cfg = get_db_config()

import psycopg2
from psycopg2.extras import RealDictCursor


def run():
    dsn = {
        'host': cfg.get('host'),
        'dbname': cfg.get('database'),
        'user': cfg.get('user'),
        'password': cfg.get('password'),
        'port': cfg.get('port'),
        'connect_timeout': cfg.get('connect_timeout', 10)
    }

    with psycopg2.connect(**dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            print("\n=== handler table rows ===")
            cur.execute("SELECT id, name, proc FROM mon.handler ORDER BY id")
            handlers = cur.fetchall()
            for h in handlers:
                print(h)

            print("\n=== arp_table sample rows (up to 20) ===")
            cur.execute("SELECT * FROM mon.arp_table ORDER BY id DESC LIMIT 20")
            arp = cur.fetchall()
            if arp:
                for r in arp:
                    print(r)
            else:
                print("(no rows)")

            print("\n=== mac_addresses count and recent rows ===")
            cur.execute("SELECT count(*) AS cnt FROM mon.mac_addresses")
            cnt = cur.fetchone()
            print(cnt)
            cur.execute("SELECT * FROM mon.mac_addresses ORDER BY last_seen DESC LIMIT 10")
            macs = cur.fetchall()
            for m in macs:
                print(m)

            print("\n=== interfaces for node 1 (recent) ===")
            cur.execute("SELECT * FROM mon.interfaces WHERE node_id=1 ORDER BY last_seen DESC LIMIT 10")
            ifs = cur.fetchall()
            for i in ifs:
                print(i)

            print("\n=== node_group rows ===")
            cur.execute("SELECT * FROM mon.node_group ORDER BY id")
            for ng in cur.fetchall():
                print(ng)

            print("\n=== node_group_ref rows ===")
            cur.execute("SELECT * FROM mon.node_group_ref ORDER BY id")
            for ref in cur.fetchall():
                print(ref)

if __name__ == '__main__':
    run()
