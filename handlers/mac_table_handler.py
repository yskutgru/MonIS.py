import time
from datetime import datetime
from typing import Dict, Any, List
import logging
import json
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class MacTableHandler(BaseHandler):
    """Handler responsible for parsing bridge FDB / MAC table entries and saving them."""

    def process_raw_data(self, node: Dict[str, Any], request: Dict[str, Any],
                         journal_id: int, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        start_time = time.time()
        try:
            macs = []
            for r in raw_data:
                if r.get('err') or not r.get('val'):
                    continue
                key = r.get('key', '').lower()
                if 'bridge' in key or 'dot1d' in key or '1.3.6.1.2.1.17' in key:
                    macs.extend(self.parse_bridge_mac_data(r['val']))

            if macs:
                self.save_mac_addresses(node['id'], macs)

            duration = int((time.time() - start_time) * 1000)
            return {
                'node_id': node['id'],
                'request_id': request['id'],
                'journal_id': journal_id,
                'val': json.dumps({'count': len(macs), 'macs': macs}, ensure_ascii=False),
                'key': 'mac_table_processing',
                'duration': duration,
                'err': None,
                'dt': datetime.now()
            }

        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            return {
                'node_id': node['id'],
                'request_id': request['id'],
                'journal_id': journal_id,
                'val': '0',
                'key': 'mac_table_error',
                'duration': duration,
                'err': str(e),
                'dt': datetime.now()
            }

    def parse_bridge_mac_data(self, data: str) -> List[Dict[str, Any]]:
        mac_addresses = []
        try:
            if data.startswith('[') or data.startswith('{'):
                walk_data = json.loads(data)
                if isinstance(walk_data, list):
                    for oid, value in walk_data:
                        if '17.4.3.1.1' in oid:
                            formatted = self.format_mac_address(value)
                            if formatted and len(formatted) == 17:
                                port = self.extract_port_from_oid(oid)
                                mac_addresses.append({
                                    'mac_address': formatted,
                                    'source': 'bridge_fdb',
                                    'ip_address': None,
                                    'port_number': port
                                })
        except Exception as e:
            logger.debug(f"Error parsing bridge mac data: {e}")
        return mac_addresses

    # reuse helper methods for formatting and DB insert
    def format_mac_address(self, value: str) -> str:
        try:
            if 'Hex-STRING:' in value:
                hex_part = value.split('Hex-STRING:')[1].strip()
                hex_clean = hex_part.replace(' ', '').replace(':', '')
                if len(hex_clean) == 12:
                    return ':'.join([hex_clean[i:i+2] for i in range(0, 12, 2)])
            elif '0x' in value.lower():
                hex_part = value.replace('0x', '').replace(' ', '')
                if len(hex_part) == 12:
                    return ':'.join([hex_part[i:i+2] for i in range(0, 12, 2)])
            elif len(value) == 12 and all(c in '0123456789abcdefABCDEF' for c in value):
                return ':'.join([value[i:i+2] for i in range(0, 12, 2)])
            return value
        except Exception:
            return value

    def extract_port_from_oid(self, oid: str) -> str:
        try:
            parts = oid.split('.')
            for i in range(len(parts) - 6, len(parts)):
                if i >= 0 and parts[i].isdigit():
                    return parts[i]
        except Exception:
            pass
        return None

    def save_mac_addresses(self, node_id: int, mac_data: List[Dict[str, Any]]):
        logger.info(f"Saving {len(mac_data)} MAC addresses for node {node_id}")
        if not mac_data:
            return
        cursor = None
        try:
            cursor = self.db_connection.cursor()
            now = datetime.now()
            insert_query = """
            INSERT INTO mon.mac_addresses 
            (node_id, interface_id, mac_address, ip_address, vlan_id, first_seen, last_seen, status, port_number, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            for mac_entry in mac_data:
                port_number = mac_entry.get('port_number')
                interface_id = None
                if port_number:
                    interface_id = self.get_interface_id_by_port(node_id, port_number)
                mac_addr = mac_entry.get('mac_address')
                # Check if exists
                cursor.execute('SELECT id FROM mon.mac_addresses WHERE node_id=%s AND mac_address=%s', (node_id, mac_addr))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute('''
                        UPDATE mon.mac_addresses SET interface_id=%s, ip_address=%s, vlan_id=%s, last_seen=%s,
                        status=%s, port_number=%s, source=%s WHERE id=%s
                    ''', (
                        interface_id,
                        mac_entry.get('ip_address'),
                        None,
                        now,
                        'ACTIVE',
                        port_number,
                        mac_entry.get('source', 'unknown'),
                        existing[0]
                    ))
                else:
                    cursor.execute(insert_query, (
                        node_id,
                        interface_id,
                        mac_addr,
                        mac_entry.get('ip_address'),
                        None,
                        now,
                        now,
                        'ACTIVE',
                        port_number,
                        mac_entry.get('source', 'unknown')
                    ))
            self.db_connection.commit()
        except Exception as e:
            logger.error(f"Error saving MAC addresses: {e}")
            if self.db_connection:
                self.db_connection.rollback()
        finally:
            if cursor:
                cursor.close()

    def get_interface_id_by_port(self, node_id: int, port_number: str) -> int:
        try:
            cursor = self.db_connection.cursor()
            cursor.execute('''
                SELECT id FROM mon.element 
                WHERE node_id = %s AND snmp_id = %s AND manage = true AND deleted = false
            ''', (node_id, int(port_number)))
            result = cursor.fetchone()
            cursor.close()
            if result:
                return result[0]
        except Exception:
            return None
        return None

    def get_name(self) -> str:
        return "MAC Table Handler"

    # Backwards-compatible execute() wrapper required by BaseHandler ABC
    def execute(self, node: Dict[str, Any], request: Dict[str, Any], journal_id: int) -> Dict[str, Any]:
        """Compatibility execute method: this handler expects raw_data and is normally
        invoked via process_raw_data. When called directly, return an informational
        result indicating processing requires raw data.
        """
        return {
            'node_id': node['id'],
            'request_id': request['id'],
            'journal_id': journal_id,
            'val': None,
            'key': 'mac_table_execute_nop',
            'duration': 0,
            'err': 'Use process_raw_data for MAC table processing',
            'dt': datetime.now()
        }
