import time
from datetime import datetime
from typing import Dict, Any, List
import json
import logging
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class ArpHandler(BaseHandler):
    """Handler that parses ARP table entries (IP -> MAC) and saves them."""

    def process_raw_data(self, node: Dict[str, Any], request: Dict[str, Any],
                         journal_id: int, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        start_time = time.time()
        try:
            # Build mapping ip -> mac by combining physAddress and netAddress walk results
            ip_to_mac = {}
            for r in raw_data:
                if r.get('err') or not r.get('val'):
                    continue
                key = r.get('key', '').lower()
                val = r.get('val')

                # physAddress walk contains MAC values; extract IP from OID and map
                if 'ipnettomediaphysaddress' in key or '1.3.6.1.2.1.4.22.1.2' in key:
                    try:
                        data = json.loads(val)
                        for oid, macval in data:
                            ip, if_index = self.extract_ip_and_ifindex_from_oid(oid)
                            mac = self.format_mac_address(macval)
                            if ip and mac:
                                ip_to_mac[ip] = {'mac': mac, 'if_index': if_index}
                    except Exception:
                        # fallback to single-value parse
                        pass

                # netAddress walk contains IP values; ensure keys present
                if 'ipnettomedianetaddress' in key or '1.3.6.1.2.1.4.22.1.3' in key:
                    try:
                        data = json.loads(val)
                        for oid, ipval in data:
                            ip, if_index = self.extract_ip_and_ifindex_from_oid(oid)
                            if ip and ip not in ip_to_mac:
                                # mark with None mac for now but preserve if_index when available
                                ip_to_mac[ip] = {'mac': None, 'if_index': if_index}
                    except Exception:
                        pass

            # Convert mapping to list of entries
            arp_entries = []
            for ip, info in ip_to_mac.items():
                if not info or info.get('mac') is None:
                    # no mac learned for this ip
                    continue
                arp_entries.append({'ip_address': ip, 'mac_address': info.get('mac'), 'source': 'arp', 'if_index': info.get('if_index')})

            if arp_entries:
                self.save_arp_entries(node['id'], arp_entries)

            duration = int((time.time() - start_time) * 1000)
            return {
                'node_id': node['id'],
                'request_id': request['id'],
                'journal_id': journal_id,
                'val': json.dumps({'count': len(arp_entries), 'entries': arp_entries}, ensure_ascii=False),
                'key': 'arp_processing',
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
                'key': 'arp_error',
                'duration': duration,
                'err': str(e),
                'dt': datetime.now()
            }

    def parse_arp_data(self, data: str) -> List[Dict[str, Any]]:
        # Kept for backward compatibility but new parsing is handled in process_raw_data
        results = []
        try:
            if data.startswith('[') or data.startswith('{'):
                walk_data = json.loads(data)
                for oid, val in walk_data:
                    ip, if_index = self.extract_ip_and_ifindex_from_oid(oid)
                    mac = self.format_mac_address(val)
                    if ip and mac:
                        results.append({'ip_address': ip, 'mac_address': mac, 'source': 'arp', 'if_index': if_index})
        except Exception as e:
            logger.debug(f"Error parsing arp data: {e}")
        return results

    def extract_ip_from_oid(self, oid: str) -> str:
        try:
            parts = oid.split('.')
            # last 4 parts are IP
            if len(parts) >= 4:
                ip_parts = parts[-4:]
                if all(p.isdigit() for p in ip_parts):
                    return '.'.join(ip_parts)
        except Exception:
            pass
        return None

    def extract_ip_and_ifindex_from_oid(self, oid: str):
        """Extract IP and if_index when oid has the form ...<base>.<ifIndex>.<ip1>.<ip2>.<ip3>.<ip4>
        Returns (ip_str or None, if_index or None)
        """
        try:
            parts = oid.split('.')
            if len(parts) >= 5:
                ip_parts = parts[-4:]
                if_index_part = parts[-5]
                if all(p.isdigit() for p in ip_parts) and if_index_part.isdigit():
                    return '.'.join(ip_parts), int(if_index_part)
            # fallback to ip only
            ip = self.extract_ip_from_oid(oid)
            return ip, None
        except Exception:
            return None, None

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

    def save_arp_entries(self, node_id: int, entries: List[Dict[str, Any]]):
        logger.info(f"Saving {len(entries)} ARP entries for node {node_id}")
        if not entries:
            return
        cursor = None
        try:
            cursor = self.db_connection.cursor()
            now = datetime.now()
            insert_query = """
            INSERT INTO mon.arp_table (node_id, ip_address, mac_address, first_seen, last_seen, source)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            for e in entries:
                try:
                    # Try safe upsert: check existing row first (avoid relying on ON CONFLICT index)
                    cursor.execute('SELECT id FROM mon.arp_table WHERE node_id=%s AND ip_address=%s AND mac_address=%s', (node_id, e.get('ip_address'), e.get('mac_address')))
                    ex = cursor.fetchone()
                    if ex:
                        cursor.execute('UPDATE mon.arp_table SET last_seen=%s, source=%s WHERE id=%s', (now, e.get('source', 'arp'), ex[0]))
                    else:
                        cursor.execute('INSERT INTO mon.arp_table (node_id, ip_address, mac_address, first_seen, last_seen, source) VALUES (%s, %s, %s, %s, %s, %s)', (node_id, e.get('ip_address'), e.get('mac_address'), now, now, e.get('source', 'arp')))
                except Exception as err:
                    self.db_connection.rollback()
                    logger.error(f"Error upserting ARP entry {e}: {err}")
                # upsert into interface_ip for inventory (no reliable if_index mapping here)
                try:
                    # Update existing interface_ip row if present. Only insert a new row if we have a valid if_index.
                    cur2 = self.db_connection.cursor()
                    cur2.execute('SELECT id FROM mon.interface_ip WHERE node_id=%s AND ip_address=%s', (node_id, e.get('ip_address')))
                    exist = cur2.fetchone()
                    if exist:
                        cur2.execute('UPDATE mon.interface_ip SET last_seen=%s, source=%s WHERE id=%s', (now, e.get('source', 'arp'), exist[0]))
                    else:
                        if e.get('if_index') is not None:
                            cur2.execute('INSERT INTO mon.interface_ip (node_id, if_index, ip_address, first_seen, last_seen, source) VALUES (%s, %s, %s, %s, %s, %s)', (node_id, e.get('if_index'), e.get('ip_address'), now, now, e.get('source', 'arp')))
                        else:
                            logger.debug(f"No if_index available for {e.get('ip_address')}; skipping insert into mon.interface_ip")
                    cur2.close()
                except Exception as err:
                    self.db_connection.rollback()
                    logger.error(f"Error upserting interface_ip for {e.get('ip_address')}: {err}")
            self.db_connection.commit()
        except Exception as ex:
            logger.error(f"Error saving arp entries: {ex}")
            if self.db_connection:
                self.db_connection.rollback()
        finally:
            if cursor:
                cursor.close()

    def get_name(self) -> str:
        return "ARP Handler"

    # Provide backwards-compatible execute() required by BaseHandler
    def execute(self, node: Dict[str, Any], request: Dict[str, Any], journal_id: int) -> Dict[str, Any]:
        return {
            'node_id': node['id'],
            'request_id': request['id'],
            'journal_id': journal_id,
            'val': None,
            'key': 'arp_execute_nop',
            'duration': 0,
            'err': 'Use process_raw_data for ARP processing',
            'dt': datetime.now()
        }
