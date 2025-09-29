# handlers/interface_handler.py
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
import json
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class InterfaceHandler(BaseHandler):
    """Обработчик интерфейсов для этапа 2"""

    def execute(self, node: Dict[str, Any], request: Dict[str, Any], journal_id: int) -> Dict[str, Any]:
        """Прямой вызов (для обратной совместимости)"""
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
        """Обработка собранных SNMP данных об интерфейсах - ЭТАП 2"""
        start_time = time.time()
        error_msg = None
        interfaces_discovered = 0
        collected_data = []

        try:
            logger.info(f"Обработка интерфейсов для {node['name']} на основе {len(raw_data)} сырых записей")

            # Анализируем сырые данные
            interfaces = self.analyze_raw_interface_data(raw_data)
            interfaces_discovered = len(interfaces)

            if interfaces:
                collected_data = interfaces
                self.save_interfaces(node['id'], interfaces)
                logger.info(f"Обнаружено интерфейсов: {interfaces_discovered}")
            else:
                error_msg = "Не удалось обнаружить интерфейсы в сырых данных"
                logger.warning(f"{error_msg}. Сырые данные: {[r.get('key') for r in raw_data]}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка обработки интерфейсов: {e}")
            import traceback
            logger.error(traceback.format_exc())

        duration = int((time.time() - start_time) * 1000)

        # Сохраняем результат в val как JSON
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
        """Анализ сырых данных для построения информации об интерфейсах"""
        interfaces = {}

        for raw_result in raw_data:
            try:
                key = raw_result.get('key', '')
                val = raw_result.get('val', '')
                err = raw_result.get('err')

                if err:
                    continue  # Пропускаем записи с ошибками

                if not val:
                    continue  # Пропускаем пустые значения

                # Анализируем в зависимости от типа запроса
                if key.startswith('walk_') or 'ifDescr' in key or '1.3.6.1.2.1.2.2.1.2' in key:
                    # WALK запрос ifDescr - содержит список интерфейсов
                    interfaces.update(self.parse_interface_walk_data(val))

                elif key.startswith('get_'):
                    # GET запрос - отдельные значения интерфейсов
                    self.parse_interface_get_data(raw_result, interfaces)

            except Exception as e:
                logger.debug(f"Ошибка анализа сырых данных {raw_result.get('key')}: {e}")

        return list(interfaces.values())

    def parse_interface_walk_data(self, walk_data: str) -> Dict[int, Dict[str, Any]]:
        """Парсинг WALK данных интерфейсов"""
        interfaces = {}

        try:
            # Пытаемся распарсить JSON
            if walk_data.startswith('[') or walk_data.startswith('{'):
                data = json.loads(walk_data)

                if isinstance(data, list):
                    # Формат [(oid, value), ...]
                    for oid, value in data:
                        if_index = self.extract_interface_index(oid)
                        if if_index:
                            if if_index not in interfaces:
                                interfaces[if_index] = {'if_index': if_index}
                            interfaces[if_index]['ifDescr'] = value
                            interfaces[if_index]['if_name'] = value

                elif isinstance(data, dict):
                    # Формат {oid: value, ...}
                    for oid, value in data.items():
                        if_index = self.extract_interface_index(oid)
                        if if_index:
                            if if_index not in interfaces:
                                interfaces[if_index] = {'if_index': if_index}
                            interfaces[if_index]['ifDescr'] = value
                            interfaces[if_index]['if_name'] = value

        except json.JSONDecodeError:
            # Если не JSON, пробуем другие форматы
            logger.debug("WALK данные не в JSON формате, пробуем текстовый парсинг")

        return interfaces

    def parse_interface_get_data(self, raw_result: Dict[str, Any], interfaces: Dict[int, Dict[str, Any]]):
        """Парсинг GET данных интерфейсов"""
        key = raw_result.get('key', '')
        val = raw_result.get('val', '')
        request_id = raw_result.get('request_id')

        # Извлекаем индекс интерфейса из ключа или request_id
        if_index = self.extract_interface_index_from_key(key) or request_id

        if not if_index:
            return

        if if_index not in interfaces:
            interfaces[if_index] = {'if_index': if_index}

        # Определяем тип данных по ключу
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
        """Извлечение индекса интерфейса из OID"""
        try:
            parts = oid.split('.')
            if len(parts) > 0:
                # Последняя часть OID обычно индекс интерфейса
                last_part = parts[-1]
                if last_part.isdigit():
                    return int(last_part)
        except Exception:
            pass
        return None

    def extract_interface_index_from_key(self, key: str) -> Optional[int]:
        """Извлечение индекса интерфейса из ключа"""
        try:
            # Ищем числа в ключе
            import re
            numbers = re.findall(r'\d+', key)
            if numbers:
                return int(numbers[-1])  # Последнее число как индекс
        except Exception:
            pass
        return None

    def save_interfaces(self, node_id: int, interfaces: List[Dict[str, Any]]):
        """Сохранение интерфейсов в БД"""
        if not interfaces:
            return

        cursor = None
        try:
            cursor = self.db_connection.cursor()
            now = datetime.now()

            logger.info(f"Сохранение {len(interfaces)} интерфейсов для узла {node_id}")

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

            saved_count = 0
            for interface in interfaces:
                try:
                    cursor.execute(insert_query, (
                        node_id,
                        interface['if_index'],
                        interface.get('if_name', f"Interface {interface['if_index']}")[:255],
                        interface.get('ifDescr', '')[:255],
                        interface.get('ifType'),
                        interface.get('ifAdminStatus'),
                        interface.get('ifOperStatus'),
                        now,
                        now
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Ошибка сохранения интерфейса {interface.get('if_index')}: {e}")

            self.db_connection.commit()
            logger.info(f"Успешно сохранено интерфейсов в БД: {saved_count}/{len(interfaces)}")

        except Exception as e:
            logger.error(f"Ошибка сохранения интерфейсов: {e}")
            if self.db_connection:
                self.db_connection.rollback()
        finally:
            if cursor:
                cursor.close()

    def get_name(self) -> str:
        return "Interface Handler"
