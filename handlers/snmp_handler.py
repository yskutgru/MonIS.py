# handlers/snmp_handler.py
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import json
import logging
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)

try:
    from pysnmp.hlapi import (
        SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
        ObjectType, ObjectIdentity, getCmd, nextCmd
    )
    PYSNAP_AVAILABLE = True
except ImportError:
    PYSNAP_AVAILABLE = False


class SNMPHandler(BaseHandler):
    """Standard SNMP handler for raw data collection"""

    def execute(self, node: Dict[str, Any], request: Dict[str, Any], journal_id: int) -> Dict[str, Any]:
        """Perform SNMP request - PHASE 1: collect raw data"""
        start_time = time.time()
        error_msg = None
        value = None
        key = None

        if not PYSNAP_AVAILABLE:
            error_msg = "pysnmp library not available"
        else:
            try:
                oid = request['oid']
                request_name = request.get('name', 'unknown')

                # Determine request type
                walk_oids = [
                    '1.3.6.1.2.1.2.2.1',      # Interface MIB
                    '1.3.6.1.2.1.31.1.1',      # Interface Extensions MIB
                    '1.3.6.1.2.1.4.20.1',     # IP Address Table
                    '1.3.6.1.2.1.17.4.3.1',   # Bridge FDB Table
                    '1.3.6.1.2.1.4.22.1'      # ARP Table
                ]

                if any(oid.startswith(walk_oid) for walk_oid in walk_oids):
                    # WALK request
                    walk_results = self.snmp_walk(node, oid)
                    if walk_results:
                        # Сохраняем как JSON строку в val
                        value = json.dumps(walk_results, ensure_ascii=False)
                        key = f"walk_{request_name}"
                        logger.debug(f"WALK запрос для {oid}: найдено {len(walk_results)} записей")
                    else:
                        error_msg = "WALK запрос не вернул данных"
                        logger.warning(f"WALK запрос для {oid} не вернул данных")
                else:
                    # GET request
                    value = self.snmp_get(node, oid)
                    if value is None:
                        error_msg = "GET запрос не удался"
                        logger.warning(f"GET запрос для {oid} не удался")
                    else:
                        key = f"get_{request_name}"
                        logger.debug(f"GET запрос для {oid}: значение = {value}")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Ошибка выполнения SNMP запроса {request.get('name')} для {node['name']}: {e}")

        duration = int((time.time() - start_time) * 1000)

        # Всегда сохраняем в val (даже если это большой JSON)
        return {
            'node_id': node['id'],
            'request_id': request['id'],
            'journal_id': journal_id,
            'val': value,
            'key': key or f"raw_{request.get('name', 'unknown')}",
            'duration': duration,
            'err': error_msg,
            'dt': datetime.now()
        }

    def snmp_get(self, node: Dict[str, Any], oid: str) -> Optional[str]:
        """Execute an SNMP GET request"""
        if not PYSNAP_AVAILABLE:
            return None

        try:
            community = node.get('community', 'public')
            ipaddress = str(node['ipaddress'])
            timeout = max(node.get('timeout', 500) // 1000, 1)
            retries = 1

            error_indication, error_status, error_index, var_binds = next(
                getCmd(SnmpEngine(),
                       CommunityData(community, mpModel=1),
                       UdpTransportTarget((ipaddress, 161), timeout=timeout, retries=retries),
                       ContextData(),
                       ObjectType(ObjectIdentity(oid)))
            )

            if error_indication:
                logger.debug(f"SNMP GET error for {node['name']}: {error_indication}")
                return None
            elif error_status:
                logger.debug(f"SNMP GET error status for {node['name']}: {error_status}")
                return None
            else:
                for var_bind in var_binds:
                    return self.format_snmp_value(var_bind[1])

        except Exception as e:
            logger.debug(f"Ошибка SNMP GET для {node['name']} OID {oid}: {e}")

        return None

    def snmp_walk(self, node: Dict[str, Any], oid: str) -> List[Tuple[str, str]]:
        """Execute an SNMP WALK request"""
        results = []

        if not PYSNAP_AVAILABLE:
            return results

        try:
            community = node.get('community', 'public')
            ipaddress = str(node['ipaddress'])
            timeout = max(node.get('timeout', 500) // 1000, 1)
            retries = 1

            for (error_indication, error_status, error_index, var_binds) in nextCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),
                UdpTransportTarget((ipaddress, 161), timeout=timeout, retries=retries),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False
            ):
                if error_indication:
                    logger.debug(f"SNMP WALK error for {node['name']}: {error_indication}")
                    break
                elif error_status:
                    logger.debug(f"SNMP WALK error status for {node['name']}: {error_status}")
                    break
                else:
                    for var_bind in var_binds:
                        oid_str = var_bind[0].prettyPrint()
                        value = self.format_snmp_value(var_bind[1])
                        if oid_str and value is not None:
                            results.append((oid_str, str(value)))

        except Exception as e:
            logger.error(f"Ошибка SNMP WALK для {node['name']} OID {oid}: {e}")

        return results

    def format_snmp_value(self, value) -> Optional[str]:
        """Format an SNMP variable value to a string"""
        if value is None:
            return None

        try:
            if hasattr(value, 'prettyPrint'):
                result = value.prettyPrint()
                if result.startswith('"') and result.endswith('"'):
                    result = result[1:-1]
                return result.strip()
            else:
                return str(value).strip()
        except Exception as e:
            logger.debug(f"Ошибка форматирования SNMP значения: {e}")
            return str(value)

    def get_name(self) -> str:
        return "SNMP Handler (Raw Data Collection)"
