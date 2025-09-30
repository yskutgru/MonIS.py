import time
from datetime import datetime
from typing import Dict, Any, List
import json
import logging
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class HealthHandler(BaseHandler):
    """Handler focused on node health: sysName, sysObjectID, sysUpTime, basic availability."""

    def process_raw_data(self, node: Dict[str, Any], request: Dict[str, Any],
                         journal_id: int, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        start_time = time.time()
        try:
            info = {}
            for r in raw_data:
                if r.get('err') or not r.get('val'):
                    continue
                key = r.get('key', '').lower()
                if 'sysname' in key or '1.3.6.1.2.1.1.5' in key:
                    info['sysName'] = r['val']
                if 'sysobjectid' in key or '1.3.6.1.2.1.1.2' in key:
                    info['sysObjectID'] = r['val']
                if 'sysuptime' in key or '1.3.6.1.2.1.1.3' in key:
                    info['sysUpTime'] = r['val']

            # persist basic health info
            if info:
                self.save_health_info(node['id'], info)

            duration = int((time.time() - start_time) * 1000)
            return {
                'node_id': node['id'],
                'request_id': request['id'],
                'journal_id': journal_id,
                'val': json.dumps(info, ensure_ascii=False),
                'key': 'health_info',
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
                'val': '{}',
                'key': 'health_error',
                'duration': duration,
                'err': str(e),
                'dt': datetime.now()
            }

    def save_health_info(self, node_id: int, info: Dict[str, Any]):
        logger.info(f"Saving health info for node {node_id}: {info}")
        cursor = None
        try:
            cursor = self.db_connection.cursor()
            cursor.execute('''
                UPDATE mon.node SET sysname = %s, sysobjectid = %s, snmp_last_dt = %s
                WHERE id = %s
            ''', (info.get('sysName'), info.get('sysObjectID'), datetime.now(), node_id))
            self.db_connection.commit()
        except Exception as e:
            logger.error(f"Failed to save health info: {e}")
            if self.db_connection:
                self.db_connection.rollback()
        finally:
            if cursor:
                cursor.close()

    def get_name(self) -> str:
        return "Health Handler"

    # Compatibility execute() implementation
    def execute(self, node: Dict[str, Any], request: Dict[str, Any], journal_id: int) -> Dict[str, Any]:
        return {
            'node_id': node['id'],
            'request_id': request['id'],
            'journal_id': journal_id,
            'val': None,
            'key': 'health_execute_nop',
            'duration': 0,
            'err': 'Use process_raw_data for health processing',
            'dt': datetime.now()
        }
