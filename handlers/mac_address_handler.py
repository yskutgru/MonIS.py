# handlers/mac_address_handler.py
import time
from datetime import datetime
from typing import Dict, Any, List
import logging
import json
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class MacAddressHandler(BaseHandler):
    """Упрощенный обработчик MAC-адресов"""

    def execute(self, node: Dict[str, Any], request: Dict[str, Any], journal_id: int) -> Dict[str, Any]:
        """Прямой вызов с упрощенной логикой"""
        start_time = time.time()

        try:
            # Для MAC-адресов используем прямые SNMP запросы
            oid = request['oid']
            if oid == 'MAC_DISCOVERY':
                result = self.collect_mac_addresses(node)
            else:
                result = self.snmp_get_single(node, oid)

            duration = int((time.time() - start_time) * 1000)

            return {
                'node_id': node['id'],
                'request_id': request['id'],
                'journal_id': journal_id,
                'val': json.dumps(result, ensure_ascii=False) if result else '0',
                'key': 'mac_collection',
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
                'key': 'mac_error',
                'duration': duration,
                'err': str(e),
                'dt': datetime.now()
            }

    def process_raw_data(self, node: Dict[str, Any], request: Dict[str, Any],
                         journal_id: int, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Упрощенная обработка сырых данных"""
        start_time = time.time()

        try:
            # Анализируем сырые данные
            mac_data = self.analyze_raw_mac_data(raw_data)

            # Сохраняем в таблицу mac_addresses
            if mac_data:
                self.save_mac_addresses(node['id'], mac_data)

            duration = int((time.time() - start_time) * 1000)

            return {
                'node_id': node['id'],
                'request_id': request['id'],
                'journal_id': journal_id,
                'val': json.dumps({'count': len(mac_data), 'macs': mac_data}, ensure_ascii=False),
                'key': 'mac_processing',
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
                'key': 'mac_error',
                'duration': duration,
                'err': str(e),
                'dt': datetime.now()
            }

    def analyze_raw_mac_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Анализ сырых данных MAC-адресов"""
        mac_addresses = []

        for raw_result in raw_data:
            try:
                val = raw_result.get('val', '')
                key = raw_result.get('key', '')

                if not val or raw_result.get('err'):
                    continue

                logger.debug(f"Анализ данных: key={key}, val_len={len(str(val))}")

                # Парсим MAC-адреса в зависимости от типа данных
                if 'bridge' in key.lower() or '1.3.6.1.2.1.17' in key or 'dot1d' in key.lower():
                    logger.debug(f"Обработка Bridge MIB данных: {key}")
                    macs = self.parse_bridge_mac_data(val)
                    mac_addresses.extend(macs)
                    logger.debug(f"Найдено Bridge MAC: {len(macs)}")
                elif 'arp' in key.lower() or '1.3.6.1.2.1.4.22' in key or 'ipNet' in key.lower():
                    logger.debug(f"Обработка ARP данных: {key}")
                    macs = self.parse_arp_data(val)
                    mac_addresses.extend(macs)
                    logger.debug(f"Найдено ARP MAC: {len(macs)}")

            except Exception as e:
                logger.debug(f"Ошибка анализа MAC данных: {e}")

        logger.info(f"Всего найдено MAC-адресов: {len(mac_addresses)}")
        return mac_addresses

    def parse_bridge_mac_data(self, data: str) -> List[Dict[str, Any]]:
        """Парсинг данных Bridge MIB"""
        mac_addresses = []
        
        try:
            logger.debug(f"Парсинг Bridge MIB данных, длина: {len(data)}")
            if data.startswith('[') or data.startswith('{'):
                import json
                walk_data = json.loads(data)
                logger.debug(f"JSON распарсен, тип: {type(walk_data)}, элементов: {len(walk_data) if isinstance(walk_data, list) else 'N/A'}")
                
                if isinstance(walk_data, list):
                    # Формат [(oid, value), ...]
                    for i, (oid, value) in enumerate(walk_data):
                        logger.debug(f"Элемент {i}: OID={oid}, Value={value}")
                        if '17.4.3.1.1' in oid:  # Bridge FDB Address
                            formatted_mac = self.format_mac_address(value)
                            logger.debug(f"Форматированный MAC: {formatted_mac}")
                            if formatted_mac and len(formatted_mac) == 17:  # Проверяем корректность MAC
                                # Извлекаем порт из OID
                                port_number = self.extract_port_from_oid(oid)
                                mac_addresses.append({
                                    'mac_address': formatted_mac,
                                    'source': 'bridge_fdb',
                                    'ip_address': None,
                                    'port_number': port_number
                                })
                                logger.debug(f"Добавлен MAC: {formatted_mac}, порт: {port_number}")
            else:
                logger.debug(f"Данные не в JSON формате: {data[:100]}...")
                            
        except Exception as e:
            logger.debug(f"Ошибка парсинга Bridge MIB: {e}")
            
        logger.debug(f"Bridge MIB: найдено {len(mac_addresses)} MAC-адресов")
        return mac_addresses

    def parse_arp_data(self, data: str) -> List[Dict[str, Any]]:
        """Парсинг данных ARP таблицы"""
        mac_addresses = []
        
        try:
            if data.startswith('[') or data.startswith('{'):
                import json
                walk_data = json.loads(data)
                
                if isinstance(walk_data, list):
                    # Формат [(oid, value), ...]
                    for oid, value in walk_data:
                        if '1.3.6.1.2.1.4.22.1.2' in oid:  # ARP MAC Address
                            formatted_mac = self.format_mac_address(value)
                            if formatted_mac and len(formatted_mac) == 17:  # Проверяем корректность MAC
                                ip_address = self.extract_ip_from_oid(oid)
                                mac_addresses.append({
                                    'mac_address': formatted_mac,
                                    'source': 'arp_table',
                                    'ip_address': ip_address
                                })
                            
        except Exception as e:
            logger.debug(f"Ошибка парсинга ARP данных: {e}")
            
        return mac_addresses

    def collect_mac_addresses(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Прямой сбор MAC-адресов"""
        # Упрощенная реализация
        return []

    def snmp_get_single(self, node: Dict[str, Any], oid: str) -> Any:
        """Одиночный SNMP запрос"""
        # Упрощенная реализация
        return None

    def save_mac_addresses(self, node_id: int, mac_data: List[Dict[str, Any]]):
        """Сохранение MAC-адресов в БД"""
        logger.info(f"Сохранение {len(mac_data)} MAC-адресов для узла {node_id}")
        if not mac_data:
            logger.warning("Нет MAC-адресов для сохранения")
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
                # Получаем interface_id по номеру порта
                port_number = mac_entry.get('port_number')
                interface_id = None
                if port_number:
                    interface_id = self.get_interface_id_by_port(node_id, port_number)
                    logger.debug(f"MAC {mac_entry.get('mac_address')} порт {port_number} -> interface_id {interface_id}")
                
                cursor.execute(insert_query, (
                    node_id,
                    interface_id,
                    mac_entry.get('mac_address'),
                    mac_entry.get('ip_address'),
                    None,  # vlan_id
                    now,   # first_seen
                    now,   # last_seen
                    'ACTIVE',  # status
                    port_number,  # port_number
                    mac_entry.get('source', 'unknown')
                ))

            self.db_connection.commit()
            logger.info(f"Сохранено MAC-адресов: {len(mac_data)}")

        except Exception as e:
            logger.error(f"Ошибка сохранения MAC-адресов: {e}")
            if self.db_connection:
                self.db_connection.rollback()
        finally:
            if cursor:
                cursor.close()

    def format_mac_address(self, value: str) -> str:
        """Форматирование MAC-адреса из SNMP значения"""
        try:
            # Убираем префиксы и форматируем
            if 'Hex-STRING:' in value:
                hex_part = value.split('Hex-STRING:')[1].strip()
                # Убираем пробелы и двоеточия
                hex_clean = hex_part.replace(' ', '').replace(':', '')
                # Форматируем как MAC-адрес
                if len(hex_clean) == 12:
                    return ':'.join([hex_clean[i:i+2] for i in range(0, 12, 2)])
            elif '0x' in value.lower():
                # Обработка hex значений (например: 0x00087c860398)
                hex_part = value.replace('0x', '').replace(' ', '')
                if len(hex_part) == 12:
                    return ':'.join([hex_part[i:i+2] for i in range(0, 12, 2)])
            elif len(value) == 12 and all(c in '0123456789abcdefABCDEF' for c in value):
                # Прямой hex без префикса
                return ':'.join([value[i:i+2] for i in range(0, 12, 2)])
            return value
        except Exception as e:
            logger.debug(f"Ошибка форматирования MAC: {e}")
            return value
    
    def extract_ip_from_oid(self, oid: str) -> str:
        """Извлечение IP адреса из OID"""
        try:
            # OID имеет формат: 1.3.6.1.2.1.4.22.1.2.{ifIndex}.{IP}
            parts = oid.split('.')
            if len(parts) >= 4:
                # Последние 4 части - это IP адрес
                ip_parts = parts[-4:]
                return '.'.join(ip_parts)
            return None
        except Exception:
            return None
    
    def extract_port_from_oid(self, oid: str) -> str:
        """Извлечение номера порта из OID Bridge FDB"""
        try:
            # OID имеет формат: SNMPv2-SMI::mib-2.17.4.3.1.1.{port}.{mac}
            # Ищем последний числовой компонент перед MAC-адресом
            parts = oid.split('.')
            # Ищем порт в последних частях OID
            for i in range(len(parts) - 6, len(parts)):
                if i >= 0 and parts[i].isdigit():
                    return parts[i]
            return None
        except Exception:
            return None
    
    def get_interface_id_by_port(self, node_id: int, port_number: str) -> int:
        """Получение interface_id по номеру порта"""
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
            return None
        except Exception as e:
            logger.debug(f"Ошибка получения interface_id для порта {port_number}: {e}")
            return None

    def get_name(self) -> str:
        return "MAC Address Handler"
