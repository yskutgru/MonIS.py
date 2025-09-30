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
        # Check for required SNMP walk keys
        required_keys = ['raw_walk_ifIndex', 'raw_walk_ifDescr', 'raw_walk_ifType']
        present_keys = set(r.get('key', '') for r in raw_data)
        missing_keys = [k for k in required_keys if k not in present_keys]
        if missing_keys:
            logger.warning(f"Missing SNMP walk keys for interface discovery: {missing_keys}. Raw keys: {list(present_keys)}")
            # If at least ifIndex is present, try to parse partial data
            if 'raw_walk_ifIndex' not in present_keys:
                return []
        # Continue with available keys
        interfaces = {}
        for raw_result in raw_data:
            try:
                key = raw_result.get('key', '')
                val = raw_result.get('val', '')
                err = raw_result.get('err')
                if err or not val:
                    continue
                if key.startswith('walk_') or 'ifDescr' in key or '1.3.6.1.2.1.2.2.1.2' in key:
                    interfaces.update(self.parse_interface_walk_data(val))
                elif key.startswith('get_'):
                    self.parse_interface_get_data(raw_result, interfaces)
            except Exception as e:
                logger.debug(f"Error analyzing raw data {raw_result.get('key')}: {e}")
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
                            interfaces[if_index]['ifDescr'] = value
                            interfaces[if_index]['if_name'] = value

                elif isinstance(data, dict):
                    for oid, value in data.items():
                        if_index = self.extract_interface_index(oid)
                        if if_index:
                            if if_index not in interfaces:
                                interfaces[if_index] = {'if_index': if_index}
                            interfaces[if_index]['ifDescr'] = value
                            interfaces[if_index]['if_name'] = value

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

            for iface in interfaces:
                try:
                    # Upsert into mon.interface_inventory
                    cur = self.db_connection.cursor()
                    cur.execute('SELECT id FROM mon.interface_inventory WHERE node_id=%s AND if_index=%s', (node_id, iface['if_index']))
                    exist = cur.fetchone()
                    if exist:
                        cur.execute('UPDATE mon.interface_inventory SET last_seen=%s, status=%s WHERE id=%s', (now, iface.get('status', 'ACTIVE'), exist[0]))
                    else:
                        cur.execute('INSERT INTO mon.interface_inventory (node_id, if_index, if_name, if_descr, if_type, if_mtu, if_speed, if_phys_address, if_admin_status, if_oper_status, if_last_change, if_alias, discovered_at, last_seen, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)', (
                            node_id, iface['if_index'], iface.get('if_name'), iface.get('if_descr'), iface.get('if_type'), iface.get('if_mtu'), iface.get('if_speed'), iface.get('if_phys_address'), iface.get('if_admin_status'), iface.get('if_oper_status'), iface.get('if_last_change'), iface.get('if_alias'), now, now, iface.get('status', 'ACTIVE')))
                    cur.close()
                except Exception as err:
                    # rollback and log, but continue with next interface
                    self.db_connection.rollback()
                    logger.error(f"Error upserting interface inventory for {iface.get('if_index')}: {err}")

                # Ensure inventory upsert is consistent (single ON CONFLICT upsert)
                try:
                    cursor.execute('''
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
                    ''', (
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
                    self.db_connection.rollback()
                    logger.error(f"Error upserting interface inventory for {iface.get('if_index')}: {e}")

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
