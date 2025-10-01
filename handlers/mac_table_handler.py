import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from .base_handler import BaseHandler


logger = logging.getLogger(__name__)


class MacTableHandler(BaseHandler):
    """Handler responsible for parsing bridge FDB / MAC table entries and saving them.

    Expects to be called via process_raw_data(node, request, journal_id, raw_data)
    where raw_data is a list of result rows previously saved by the SNMP collector.
    """

    def __init__(self, db_connection):
        self.db_connection = db_connection
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_raw_data(self, node: Dict[str, Any], request: Dict[str, Any],
                         journal_id: int, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        import time

        start_time = time.time()
        try:
            # Aggregate parsed MAC entries across all raw records so that
            # address/port/status fragments from different raw results get merged.
            mac_map: Dict[str, Dict[str, Any]] = {}
            for r in raw_data:
                if r.get('err') or not r.get('val'):
                    continue
                try:
                    parsed = self.parse_bridge_mac_data(r.get('val'))
                except Exception:
                    logger.debug(f"Skipping non-MAC raw record for node {node.get('name')}, key={r.get('key')}")
                    parsed = []

                for entry in parsed:
                    mac_addr = entry.get('mac_address')
                    if not mac_addr:
                        continue
                    if mac_addr not in mac_map:
                        mac_map[mac_addr] = entry.copy()
                    else:
                        # Merge non-null fields
                        for k, v in entry.items():
                            if v is None:
                                continue
                            # prefer numeric port/status if present
                            if k in ('port_number', 'status'):
                                mac_map[mac_addr][k] = v
                            else:
                                mac_map[mac_addr].setdefault(k, v)

            macs = list(mac_map.values())

            if macs:
                self.save_mac_addresses(node['id'], macs)

            duration = int((time.time() - start_time) * 1000)
            return {
                'node_id': node['id'],
                'request_id': request['id'],
                'journal_id': journal_id,
                'val': json.dumps({'count': len(macs)}, ensure_ascii=False),
                'key': 'mac_table_processing',
                'duration': duration,
                'err': None,
                'dt': datetime.now()
            }

        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            logger.exception("Error in MacTableHandler.process_raw_data")
            return {
                'node_id': node.get('id'),
                'request_id': request.get('id'),
                'journal_id': journal_id,
                'val': None,
                'key': 'mac_table_error',
                'duration': duration,
                'err': str(e),
                'dt': datetime.now()
            }

    def parse_bridge_mac_data(self, data: Any) -> List[Dict[str, Any]]:
        """Parse SNMP walk payload (JSON string or list) for dot1dTpFdbAddress/Port/Status entries.

        Returns list of dicts: {'mac_address', 'port_number', 'status', 'source'}
        """
        mac_addresses: Dict[str, Dict[str, Any]] = {}
        try:
            if not data:
                return []

            walk_data = data
            if isinstance(data, str) and (data.startswith('[') or data.startswith('{')):
                walk_data = json.loads(data)

            import re

            def extract_first_int(s: str) -> Optional[int]:
                try:
                    m = re.search(r"-?\d+", s)
                    if m:
                        return int(m.group(0))
                except Exception:
                    pass
                return None

            def normalize_mac_str(s: str) -> Optional[str]:
                if not s:
                    return None
                ss = s.strip()
                # Remove common SNMP textual prefixes
                if ss.lower().startswith('hex-string:'):
                    ss = ss.split(':', 1)[1].strip()
                # Remove type prefix like INTEGER: or Gauge32:
                if ':' in ss and not any(c in ss for c in '\n\r') and ' ' in ss and ss.split()[0].endswith(':'):
                    # e.g. 'INTEGER: 5' -> keep trailing part
                    ss = ' '.join(ss.split()[1:])
                # 0x prefix case
                if ss.lower().startswith('0x'):
                    ss = ss[2:]
                # remove common separators and whitespace
                clean = re.sub(r'[^0-9a-fA-F]', '', ss)
                if len(clean) == 12 and all(c in '0123456789abcdefABCDEF' for c in clean):
                    clean = clean.lower()
                    return ':'.join([clean[i:i+2] for i in range(0, 12, 2)])
                return None

            if isinstance(walk_data, list):
                for item in walk_data:
                    try:
                        oid, val = item
                    except Exception:
                        if isinstance(item, dict):
                            oid = item.get('oid') or item.get('key') or ''
                            val = item.get('value') or item.get('val')
                        else:
                            continue

                    oid = str(oid)
                    if isinstance(val, (bytes, bytearray)):
                        try:
                            val = val.decode('utf-8', errors='ignore')
                        except Exception:
                            val = str(val)
                    sval = str(val) if val is not None else ''

                    parts = [p for p in oid.strip().split('.') if p != '']
                    mac = None
                    if len(parts) >= 6:
                        tail = parts[-6:]
                        try:
                            mac = ':'.join(f'{int(x):02x}' for x in tail)
                        except Exception:
                            mac = None

                    is_addr = ('17.4.3.1.1' in oid) or ('dot1dTpFdbAddress' in oid)
                    is_port = ('17.4.3.1.2' in oid) or ('dot1dTpFdbPort' in oid)
                    is_status = ('17.4.3.1.3' in oid) or ('dot1dTpFdbStatus' in oid)

                    # Sometimes the MAC is present in the value (Hex-STRING, 0x... or plain hex)
                    if not mac:
                        mac_from_val = normalize_mac_str(sval)
                        if mac_from_val:
                            mac = mac_from_val

                    if is_addr and mac:
                        entry = mac_addresses.setdefault(mac, {
                            'mac_address': mac,
                            'port_number': None,
                            'status': None,
                            'source': 'bridge_fdb',
                            'ip_address': None
                        })
                    elif is_port and mac:
                        entry = mac_addresses.setdefault(mac, {
                            'mac_address': mac,
                            'port_number': None,
                            'status': None,
                            'source': 'bridge_fdb',
                            'ip_address': None
                        })
                        # Extract integer port even from textual SNMP outputs like 'INTEGER: 5'
                        port = extract_first_int(sval)
                        entry['port_number'] = port
                    elif is_status and mac:
                        entry = mac_addresses.setdefault(mac, {
                            'mac_address': mac,
                            'port_number': None,
                            'status': None,
                            'source': 'bridge_fdb',
                            'ip_address': None
                        })
                        st = extract_first_int(sval)
                        entry['status'] = st
                    else:
                        # Try to detect MAC presented as value
                        cand = sval.strip()
                        if cand:
                            mac_from_val = normalize_mac_str(cand)
                            if mac_from_val:
                                entry = mac_addresses.setdefault(mac_from_val, {
                                    'mac_address': mac_from_val,
                                    'port_number': None,
                                    'status': None,
                                    'source': 'bridge_fdb',
                                    'ip_address': None
                                })

        except Exception as e:
            logger.debug(f"Error parsing bridge mac data: {e}")
        return list(mac_addresses.values())

    def save_mac_addresses(self, node_id: int, mac_data: List[Dict[str, Any]]):
        logger.info(f"Saving {len(mac_data)} MAC addresses for node {node_id}")
        if not mac_data:
            return
        cursor = None
        try:
            cursor = self.db_connection.cursor()
            now = datetime.now()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mon.mac_addresses (
                    id BIGSERIAL PRIMARY KEY,
                    node_id integer NOT NULL,
                    interface_id integer,
                    mac_address text NOT NULL,
                    ip_address inet,
                    vlan_id integer,
                    first_seen timestamp,
                    last_seen timestamp,
                    status varchar(32),
                    port_number integer,
                    source text,
                    UNIQUE (node_id, mac_address)
                )
            ''')

            for mac_entry in mac_data:
                port_number = mac_entry.get('port_number')
                interface_id: Optional[int] = None
                if port_number is not None:
                    try:
                        interface_id = self.get_interface_id_by_port(node_id, port_number)
                    except Exception:
                        interface_id = None

                mac_addr = mac_entry.get('mac_address')
                ip_addr = mac_entry.get('ip_address')
                source = mac_entry.get('source', 'bridge_fdb')
                status = mac_entry.get('status')

                cursor.execute('SELECT id FROM mon.mac_addresses WHERE node_id=%s AND mac_address=%s', (node_id, mac_addr))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute('''
                        UPDATE mon.mac_addresses
                        SET interface_id=%s, ip_address=%s, vlan_id=%s, last_seen=%s,
                            status=%s, port_number=%s, source=%s
                        WHERE id=%s
                    ''', (
                        interface_id,
                        ip_addr,
                        None,
                        now,
                        'ACTIVE' if status is None else str(status),
                        port_number,
                        source,
                        existing[0]
                    ))
                else:
                    cursor.execute('''
                        INSERT INTO mon.mac_addresses
                        (node_id, interface_id, mac_address, ip_address, vlan_id, first_seen, last_seen, status, port_number, source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        node_id,
                        interface_id,
                        mac_addr,
                        ip_addr,
                        None,
                        now,
                        now,
                        'ACTIVE' if status is None else str(status),
                        port_number,
                        source
                    ))

            self.db_connection.commit()
        except Exception as e:
            logger.error(f"Error saving MAC addresses: {e}")
            try:
                if self.db_connection:
                    self.db_connection.rollback()
            except Exception:
                pass
        finally:
            if cursor:
                cursor.close()

    def get_interface_id_by_port(self, node_id: int, port_number: Any) -> Optional[int]:
        try:
            cursor = self.db_connection.cursor()
            cursor.execute('''
                SELECT id FROM mon.element
                WHERE node_id = %s AND snmp_id = %s AND manage = true AND deleted = false
                LIMIT 1
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

    def execute(self, node: Dict[str, Any], request: Dict[str, Any], journal_id: int) -> Dict[str, Any]:
        # Compatibility execute method: this handler expects raw_data and is normally
        # invoked via process_raw_data. When called directly, return an informational
        # result indicating processing requires raw data.
        return {
            'node_id': node.get('id'),
            'request_id': request.get('id'),
            'journal_id': journal_id,
            'val': None,
            'key': 'mac_table_execute_nop',
            'duration': 0,
            'err': 'Use process_raw_data for MAC table processing',
            'dt': datetime.now()
        }
