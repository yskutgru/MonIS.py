#!/usr/bin/env python3
"""Create required DB tables and handler entries for SRP handlers, and update request_group mapping.

Idempotent: will not duplicate existing handlers or tables. Uses config.get_db_config().
"""
from pprint import pprint
import sys
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
    print("psycopg2 not installed in the active environment.")
    psycopg2 = None
    RealDictCursor = None


DESIRED_HANDLERS = {
    'InterfaceDiscoveryHandler': 'interface_discovery',
    'MacTableHandler': 'mac_table',
    'ArpHandler': 'arp_table',
    'HealthHandler': 'health'
}

MAPPING_REQUEST_GROUP_TO_HANDLER = {
    # request_group.name -> handler_name (key in DESIRED_HANDLERS)
    'system_info': 'HealthHandler',
    'interfaces_summary': 'InterfaceDiscoveryHandler',
    'interfaces_details': 'InterfaceDiscoveryHandler',
    'mac_table': 'MacTableHandler',
    'arp_table': 'ArpHandler',
    'bridge_info': 'MacTableHandler'
}


def connect():
    return psycopg2.connect(host=cfg['host'], dbname=cfg['database'], user=cfg['user'], password=cfg['password'], port=cfg['port'])


def ensure_arp_table(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mon.arp_table (
        id serial PRIMARY KEY,
        node_id integer NOT NULL,
        ip_address inet,
        mac_address macaddr NOT NULL,
        first_seen timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
        last_seen timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
        source character varying
    )
    """)
    print("Ensured mon.arp_table exists")


def ensure_handlers(cur):
    # read existing handlers by proc (or name)
    cur.execute("SELECT id, name, proc FROM mon.handler")
    existing = { (r[2] if r[2] else r[1]): r[0] for r in cur.fetchall() }

    created = {}
    for class_name, proc in DESIRED_HANDLERS.items():
        if proc in existing:
            created[class_name] = existing[proc]
            continue
        # insert new handler
        cur.execute("INSERT INTO mon.handler (name, proc) VALUES (%s, %s) RETURNING id", (proc, proc))
        hid = cur.fetchone()[0]
        created[class_name] = hid
        existing[proc] = hid
        print(f"Inserted handler {proc} id={hid}")

    return created


def update_request_group_mapping(cur, handlers_by_name):
    # Get request groups
    cur.execute("SELECT id, name, handler_id FROM mon.request_group")
    rgs = cur.fetchall()
    updates = []
    for rg in rgs:
        rg_id, rg_name, current = rg
        desired_handler_key = MAPPING_REQUEST_GROUP_TO_HANDLER.get(rg_name)
        if not desired_handler_key:
            continue
        desired_handler_id = handlers_by_name.get(desired_handler_key)
        if not desired_handler_id:
            print(f"No handler id found for {desired_handler_key}")
            continue
        if current == desired_handler_id:
            continue
        cur.execute("UPDATE mon.request_group SET handler_id=%s WHERE id=%s", (desired_handler_id, rg_id))
        updates.append((rg_name, rg_id, current, desired_handler_id))

    return updates


def main():
    if cfg is None or psycopg2 is None:
        print('Missing configuration or psycopg2; aborting setup.')
        return
    conn = connect()
    try:
        with conn:
            with conn.cursor() as cur:
                ensure_arp_table(cur)
                handlers = ensure_handlers(cur)
                # Map created handler name keys to ids for update mapping
                handlers_by_class = handlers
                updates = update_request_group_mapping(cur, handlers_by_class)
                print('\nRequest_group updates:')
                pprint(updates)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
