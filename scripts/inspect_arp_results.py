#!/usr/bin/env python3
"""Inspect recent raw SNMP results related to ARP to see value formats."""
from pprint import pprint
from config import get_db_config
import psycopg2
from psycopg2.extras import RealDictCursor

cfg = get_db_config()

def run():
    dsn = {
        'host': cfg.get('host'),
        'dbname': cfg.get('database'),
        'user': cfg.get('user'),
        'password': cfg.get('password'),
        'port': cfg.get('port')
    }
    with psycopg2.connect(**dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, node_id, request_id, key, val, err, dt FROM mon.result WHERE key LIKE 'raw_%ipNetToMedia%' ORDER BY id DESC LIMIT 20")
            rows = cur.fetchall()
            print('\n=== ARP-related raw results ===')
            if not rows:
                print('(no rows)')
            for r in rows:
                print('id=', r['id'], 'key=', r['key'], 'err=', r['err'], 'dt=', r['dt'])
                val = r['val']
                if val and len(val) > 1000:
                    print(' val: (long, trimmed)')
                    print(val[:1000])
                else:
                    print(' val:', val)

if __name__ == '__main__':
    run()
