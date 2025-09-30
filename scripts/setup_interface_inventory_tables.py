#!/usr/bin/env python3
"""Create interface inventory tables under mon schema if not exists."""
from config import get_db_config
import psycopg2

cfg = get_db_config()

def run():
    dsn = {
        'host': cfg.get('host'),
        'dbname': cfg.get('database'),
        'user': cfg.get('user'),
        'password': cfg.get('password'),
        'port': cfg.get('port')
    }

    sql = """
    CREATE TABLE IF NOT EXISTS mon.interface_inventory (
        id serial PRIMARY KEY,
        node_id integer NOT NULL,
        if_index integer NOT NULL,
        if_name varchar(255),
        if_descr text,
        if_type integer,
        if_mtu integer,
        if_speed bigint,
        if_phys_address macaddr,
        if_admin_status integer,
        if_oper_status integer,
        if_last_change bigint,
        if_alias text,
        discovered_at timestamp default CURRENT_TIMESTAMP,
        last_seen timestamp default CURRENT_TIMESTAMP,
        status varchar(32) default 'ACTIVE'
    );

    CREATE TABLE IF NOT EXISTS mon.interface_ip (
        id serial PRIMARY KEY,
        node_id integer NOT NULL,
        if_index integer NOT NULL,
        ip_address inet NOT NULL,
        first_seen timestamp default CURRENT_TIMESTAMP,
        last_seen timestamp default CURRENT_TIMESTAMP,
        source varchar(64)
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_interface_inventory_node_ifindex ON mon.interface_inventory (node_id, if_index);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_interface_ip_node_ifindex_ip ON mon.interface_ip (node_id, if_index, ip_address);
    """

    with psycopg2.connect(**dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()
            print("Interface inventory tables ensured")

if __name__ == '__main__':
    run()
