#
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
import json
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class InterfaceDiscoveryHandler(BaseHandler):
    """Handler responsible for discovering and saving interface information."""

    def execute(self, node: Dict[str, Any], request: Dict[str, Any], journal_id: int) -> Dict[str, Any]:
        # Kept for backward compatibility; prefer process_raw_data
        return {
            'node_id': node['id'],
            'request_id': request['id'],
            'journal_id': journal_id,
            'val': 'Use process_raw_data method',
            'key': 'direct_call',
            'duration': 0,
            'err': 'This handler requires raw SNMP data first',
            'dt': datetime.now()
        }

    def process_raw_data(self, node: Dict[str, Any], request: Dict[str, Any],
                         journal_id: int, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        start_time = time.time()
        error_msg = None
        interfaces_discovered = 0
        collected_data = []

        try:
            logger.info(f"Processing interfaces for {node.get('name')} from {len(raw_data)} raw records")

            interfaces = self.analyze_raw_interface_data(raw_data)
            interfaces_discovered = len(interfaces)

            if interfaces:
                collected_data = interfaces
                self.save_interfaces(node['id'], interfaces)
                logger.info(f"Discovered interfaces: {interfaces_discovered}")
            else:
                error_msg = "No interfaces discovered in raw data"
                logger.warning(f"{error_msg}. Raw keys: {[r.get('key') for r in raw_data]}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing interfaces: {e}")

        duration = int((time.time() - start_time) * 1000)

        result_json = json.dumps({
            'interfaces_count': interfaces_discovered,
            'interfaces': collected_data
        }, ensure_ascii=False, default=str) if collected_data else str(interfaces_discovered)

        return {
            'node_id': node['id'],
            'request_id': request['id'],
            'journal_id': journal_id,
            'val': result_json,
            'key': 'interface_processing',
            'duration': duration,
            'err': error_msg,
            'dt': datetime.now()
        }

    def analyze_raw_interface_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Collect parsed walk/get data per key first. This simplifies merging
        # multiple walk segments that arrive in separate raw records.
        walk_map = {}
        get_map = []

        for raw_result in raw_data:
            key = raw_result.get('key', '')
            val = raw_result.get('val', '')
            err = raw_result.get('err')
            if err or not val:
                continue

            if key.startswith('raw_walk_') or key.startswith('walk_') or '1.3.6.1.2.1.2.2.1.' in key or '1.3.6.1.2.1.31.1.1' in key:
                try:
                    parsed = json.loads(val)
                except Exception:
                    logger.debug(f"Unable to JSON-decode walk val for key {key}")
                    continue

                # normalize to list of (oid, value) pairs
                if isinstance(parsed, dict):
                    items = list(parsed.items())
                elif isinstance(parsed, list):
                    items = parsed
                else:
                    items = []

                # store merged list for this key (append if multiple records)
                if key not in walk_map:
                    walk_map[key] = []
                walk_map[key].extend(items)

            elif key.startswith('get_'):
                # preserve GETs for later
                get_map.append(raw_result)

        if not walk_map and not get_map:
            present_keys = set(r.get('key', '') for r in raw_data)
            logger.warning(f"No interface SNMP walks present for discovery. Raw keys: {list(present_keys)}")
            return []

        # Now build interface structures by iterating over walk_map
        interfaces: Dict[int, Dict[str, Any]] = {}

        def set_iface_field(idx: int, field_name: str, value: Any):
            if idx not in interfaces:
                interfaces[idx] = {'if_index': idx}
            interfaces[idx][field_name] = value

        # mapping from walk key substring to logical field name
        mapping = [
            (('ifDescr', 'ifName', '1.3.6.1.2.1.2.2.1.2', '1.3.6.1.2.1.31.1.1.1.1'), 'if_name'),
            (('ifType', '1.3.6.1.2.1.2.2.1.3',), 'if_type'),
            (('ifMtu', '1.3.6.1.2.1.2.2.1.4',), 'if_mtu'),
            (('ifSpeed', '1.3.6.1.2.1.2.2.1.5',), 'if_speed'),
            (('ifPhysAddress', '1.3.6.1.2.1.2.2.1.6',), 'if_phys_address'),
            (('ifAdminStatus', '1.3.6.1.2.1.2.2.1.7',), 'if_admin_status'),
            (('ifOperStatus', '1.3.6.1.2.1.2.2.1.8',), 'if_oper_status'),
            (('ifLastChange', '1.3.6.1.2.1.2.2.1.9',), 'if_last_change'),
            (('ifAlias', '1.3.6.1.2.1.31.1.1.1.18',), 'if_alias'),
            (('ifIndex', '1.3.6.1.2.1.2.2.1.1',), 'if_index')
        ]

        # iterate through each collected walk key and populate fields
        for raw_key, items in walk_map.items():
            # determine logical field for this raw_key
            logical_field = None
            for subs, fld in mapping:
                if any(sub in raw_key for sub in subs):
                    logical_field = fld
                    break

            # default: skip if unknown
            if not logical_field:
                continue

            for oid, v in items:
                idx = self.extract_interface_index(oid)
                if not idx:
                    continue

                # normalize value
                if isinstance(v, dict) and 'value' in v:
                    val_norm = v.get('value')
                else:
                    val_norm = v
                if isinstance(val_norm, bytes):
                    try:
                        val_norm = val_norm.decode('utf-8', errors='ignore')
                    except Exception:
                        val_norm = str(val_norm)

                # convert types for numeric fields
                if logical_field in ('if_index', 'if_mtu', 'if_speed', 'if_admin_status', 'if_oper_status', 'if_last_change'):
                    try:
                        val_norm = int(val_norm)
                    except Exception:
                        pass

                # store normalized value under a consistent key naming
                if logical_field == 'if_name':
                    set_iface_field(idx, 'if_name', val_norm)
                    set_iface_field(idx, 'ifDescr', val_norm)
                    logger.debug(f"Mapped if_name for idx {idx}: {val_norm}")
                elif logical_field == 'if_alias':
                    set_iface_field(idx, 'if_alias', val_norm)
                    logger.debug(f"Mapped if_alias for idx {idx}: {val_norm}")
                elif logical_field == 'if_index':
                    set_iface_field(idx, 'if_index', val_norm)
                else:
                    set_iface_field(idx, logical_field, val_norm)

        # process GET results (single OID values) to fill missing bits
        for raw_result in get_map:
            self.parse_interface_get_data(raw_result, interfaces)

        return list(interfaces.values())

    def parse_interface_walk_data(self, walk_data: str) -> Dict[int, Dict[str, Any]]:
        interfaces = {}

        try:
            if walk_data.startswith('[') or walk_data.startswith('{'):
                data = json.loads(walk_data)

                if isinstance(data, list):
                    for oid, value in data:
                        if_index = self.extract_interface_index(oid)
                        if if_index:
                            if if_index not in interfaces:
                                interfaces[if_index] = {'if_index': if_index}
                            # normalize value
                            val_norm = value
                            if isinstance(val_norm, dict) and 'value' in val_norm:
                                val_norm = val_norm.get('value')
                            if isinstance(val_norm, bytes):
                                try:
                                    val_norm = val_norm.decode('utf-8', errors='ignore')
                                except Exception:
                                    val_norm = str(val_norm)
                            interfaces[if_index]['ifDescr'] = val_norm
                            interfaces[if_index]['if_name'] = val_norm

                elif isinstance(data, dict):
                    for oid, value in data.items():
                        if_index = self.extract_interface_index(oid)
                        if if_index:
                            if if_index not in interfaces:
                                interfaces[if_index] = {'if_index': if_index}
                            val_norm = value
                            if isinstance(val_norm, dict) and 'value' in val_norm:
                                val_norm = val_norm.get('value')
                            if isinstance(val_norm, bytes):
                                try:
                                    val_norm = val_norm.decode('utf-8', errors='ignore')
                                except Exception:
                                    val_norm = str(val_norm)
                            interfaces[if_index]['ifDescr'] = val_norm
                            interfaces[if_index]['if_name'] = val_norm

        except Exception:
            logger.debug("WALK data parse error")

        return interfaces

    def parse_interface_get_data(self, raw_result: Dict[str, Any], interfaces: Dict[int, Dict[str, Any]]):
        key = raw_result.get('key', '')
        val = raw_result.get('val', '')
        request_id = raw_result.get('request_id')

        if_index = self.extract_interface_index_from_key(key) or request_id
        if not if_index:
            return

        if if_index not in interfaces:
            interfaces[if_index] = {'if_index': if_index}

        if 'ifDescr' in key or '1.3.6.1.2.1.2.2.1.2' in key:
            interfaces[if_index]['ifDescr'] = val
            interfaces[if_index]['if_name'] = val
        elif 'ifType' in key or '1.3.6.1.2.1.2.2.1.3' in key:
            interfaces[if_index]['ifType'] = val
        elif 'ifOperStatus' in key or '1.3.6.1.2.1.2.2.1.8' in key:
            interfaces[if_index]['ifOperStatus'] = val
        elif 'ifAdminStatus' in key or '1.3.6.1.2.1.2.2.1.7' in key:
            interfaces[if_index]['ifAdminStatus'] = val

    def extract_interface_index(self, oid: str) -> Optional[int]:
        try:
            parts = oid.split('.')
            last_part = parts[-1]
            if last_part.isdigit():
                return int(last_part)
        except Exception:
            pass
        return None

    def extract_interface_index_from_key(self, key: str) -> Optional[int]:
        try:
            import re
            numbers = re.findall(r'\d+', key)
            if numbers:
                return int(numbers[-1])
        except Exception:
            pass
        return None

    def save_interfaces(self, node_id: int, interfaces: List[Dict[str, Any]]):
        # Minimal DB save similar to original implementation
        if not interfaces:
            return

        cursor = None
        try:
            cursor = self.db_connection.cursor()
            now = datetime.now()
            insert_query = """
            INSERT INTO mon.interfaces
            (node_id, if_index, if_name, if_descr, if_type, if_admin_status, if_oper_status,
             discovered_at, last_seen, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE')
            ON CONFLICT (node_id, if_index)
            DO UPDATE SET
                if_name = EXCLUDED.if_name,
                if_descr = EXCLUDED.if_descr,
                if_type = EXCLUDED.if_type,
                if_admin_status = EXCLUDED.if_admin_status,
                if_oper_status = EXCLUDED.if_oper_status,
                last_seen = EXCLUDED.last_seen,
                status = 'ACTIVE'
            """

            # Prepare bulk upsert rows and execute in chunks to reduce transaction size
            upsert_sql = '''
                INSERT INTO mon.interface_inventory
                (node_id, if_index, if_name, if_descr, if_type, if_mtu, if_speed, if_phys_address,
                 if_admin_status, if_oper_status, if_last_change, if_alias, discovered_at, last_seen, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (node_id, if_index) DO UPDATE SET
                    if_name = EXCLUDED.if_name,
                    if_descr = EXCLUDED.if_descr,
                    if_type = EXCLUDED.if_type,
                    if_mtu = EXCLUDED.if_mtu,
                    if_speed = EXCLUDED.if_speed,
                    if_phys_address = EXCLUDED.if_phys_address,
                    if_admin_status = EXCLUDED.if_admin_status,
                    if_oper_status = EXCLUDED.if_oper_status,
                    if_last_change = EXCLUDED.if_last_change,
                    if_alias = EXCLUDED.if_alias,
                    last_seen = EXCLUDED.last_seen,
                    status = EXCLUDED.status
            '''

            rows = []
            for iface in interfaces:
                try:
                    rows.append((
                        node_id,
                        iface['if_index'],
                        (iface.get('if_name') or '')[:255],
                        (iface.get('ifDescr') or '')[:255],
                        iface.get('if_type') or iface.get('ifType'),
                        iface.get('if_mtu') or iface.get('ifMtu'),
                        iface.get('if_speed') or iface.get('ifSpeed'),
                        iface.get('if_phys_address') or iface.get('ifPhysAddress'),
                        iface.get('if_admin_status') or iface.get('ifAdminStatus'),
                        iface.get('if_oper_status') or iface.get('ifOperStatus'),
                        iface.get('if_last_change') or iface.get('ifLastChange'),
                        iface.get('if_alias') or iface.get('ifAlias'),
                        now,
                        now,
                        iface.get('status', 'ACTIVE')
                    ))
                except Exception as e:
                    logger.error(f"Error preparing interface inventory row for {iface.get('if_index')}: {e}")

            # Execute in chunks
            chunk_size = 100
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i:i+chunk_size]
                try:
                    cursor.executemany(upsert_sql, chunk)
                    self.db_connection.commit()
                except Exception as e:
                    logger.error(f"Error upserting interface inventory chunk starting at {i}: {e}")
                    try:
                        self.db_connection.rollback()
                    except Exception:
                        pass

            self.db_connection.commit()

        except Exception as e:
            logger.error(f"Error saving interfaces: {e}")
            if self.db_connection:
                self.db_connection.rollback()
        finally:
            if cursor:
                cursor.close()

    def get_name(self) -> str:
        return "Interface Discovery Handler"
