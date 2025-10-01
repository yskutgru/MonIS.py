#!/usr/bin/env python3
"""Populate mon.task and mon.crontab with sensible defaults.

This script is idempotent: it will not duplicate tasks/crontab rows if they already exist
for the same node_group and request_group.

It uses DB config from `config.get_db_config()` and must be run with the project's venv.
"""
import sys
from pprint import pprint

try:
    from config import get_db_config
    cfg = get_db_config()
except Exception as e:
    print(f"Failed to import config: {e}")
    cfg = None

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception as e:
    print("psycopg2 not installed in the active environment.")
    psycopg2 = None
    RealDictCursor = None


SCHEDULES = {
    # request_group_id: (minutes, hours, days)
    1: (5, None, None),   # system_info every 5 minutes
    2: (15, None, None),  # interfaces_summary every 15 minutes
    3: (None, 1, None),   # interfaces_details every 1 hour
    4: (None, 6, None),   # mac_table every 6 hours
    5: (None, 1, None),   # arp_table every 1 hour
    6: (None, None, 1),   # bridge_info daily
}


def connect():
    dsn = {
        'host': cfg.get('host'),
        'dbname': cfg.get('database'),
        'user': cfg.get('user'),
        'password': cfg.get('password'),
        'port': cfg.get('port'),
        'connect_timeout': cfg.get('connect_timeout', 10)
    }
    return psycopg2.connect(**dsn)


def ensure_node_group(cur, name='all_nodes'):
    cur.execute("SELECT id FROM mon.node_group WHERE name=%s", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    try:
        cur.execute("INSERT INTO mon.node_group (name, type, description) VALUES (%s, %s, %s) RETURNING id", (name, 'group', 'Auto-created group for all nodes'))
        nid = cur.fetchone()[0]
        print(f"Created node_group id={nid} name={name}")
        return nid
    except Exception as e:
        # handle possible sequence misalignment / unique pk conflicts
        try:
            # rollback current transaction to clear the error
            cur.connection.rollback()
        except Exception:
            pass
        # try to find by name again
        cur.execute("SELECT id FROM mon.node_group WHERE name=%s", (name,))
        row2 = cur.fetchone()
        if row2:
            return row2[0]

        # If still not found, reset sequence to max(id) and retry insert once
        print("Detected insert conflict for node_group; attempting to reset sequence and retry")
        cur.execute("SELECT setval('mon.seq_node_group_id', (SELECT COALESCE(MAX(id),0) FROM mon.node_group))")
        try:
            cur.execute("INSERT INTO mon.node_group (name, type, description) VALUES (%s, %s, %s) RETURNING id", (name, 'group', 'Auto-created group for all nodes'))
            nid = cur.fetchone()[0]
            print(f"Created node_group id={nid} name={name} (after sequence fix)")
            return nid
        except Exception as e2:
            print(f"Failed to create node_group after sequence fix: {e2}")
            raise


def ensure_task(cur, node_group_id, request_group_id, name=None, description=None):
    cur.execute("SELECT id FROM mon.task WHERE node_group_id=%s AND request_group_id=%s", (node_group_id, request_group_id))
    row = cur.fetchone()
    if row:
        return row[0], False
    if not name:
        name = f"task_rg_{request_group_id}"
    cur.execute(
        "INSERT INTO mon.task (node_group_id, request_group_id, name, description, manage) VALUES (%s, %s, %s, %s, true) RETURNING id",
        (node_group_id, request_group_id, name, description)
    )
    tid = cur.fetchone()[0]
    print(f"Created task id={tid} for request_group_id={request_group_id}")
    return tid, True


def ensure_crontab(cur, task_id, minutes=None, hours=None, days=None, agent='ANY'):
    # consider uniqueness by task_id and agent
    cur.execute("SELECT id FROM mon.crontab WHERE task_id=%s AND agent=%s", (task_id, agent))
    row = cur.fetchone()
    if row:
        return row[0], False
    cur.execute(
        "INSERT INTO mon.crontab (minutes, hours, days, status, task_id, agent) VALUES (%s, %s, %s, 'ACTIVE', %s, %s) RETURNING id",
        (minutes, hours, days, task_id, agent)
    )
    cid = cur.fetchone()[0]
    print(f"Created crontab id={cid} for task_id={task_id} schedule minutes={minutes} hours={hours} days={days}")
    return cid, True


def main():
    if cfg is None or psycopg2 is None:
        print('Missing configuration or psycopg2; aborting populate tasks.')
        return
    conn = connect()
    try:
        with conn:
            with conn.cursor() as cur:
                # ensure node_group exists
                node_group_id = ensure_node_group(cur, name='all_nodes')

                # fetch existing request_group ids and names
                cur.execute("SELECT id, name FROM mon.request_group ORDER BY id")
                rgs = cur.fetchall()
                print("Found request_group rows:")
                pprint(rgs)

                created_tasks = []
                task_map = {}
                for rg in rgs:
                    rg_id, rg_name = rg
                    tid, created = ensure_task(cur, node_group_id, rg_id, name=f"{rg_name}_task", description=f"Auto task for request group {rg_name}")
                    task_map[rg_id] = tid
                    if created:
                        created_tasks.append(tid)

                # create crontab entries based on SCHEDULES for tasks we have
                created_crontabs = []
                for rg_id, tid in task_map.items():
                    sched = SCHEDULES.get(rg_id)
                    if not sched:
                        continue
                    minutes, hours, days = sched
                    cid, created = ensure_crontab(cur, tid, minutes=minutes, hours=hours, days=days)
                    if created:
                        created_crontabs.append(cid)

                print('\nSummary:')
                print(' node_group_id=', node_group_id)
                print(' tasks created:', created_tasks)
                print(' crontabs created:', created_crontabs)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
