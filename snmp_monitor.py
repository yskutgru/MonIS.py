import psycopg2
import time
from datetime import datetime
import logging
from typing import List, Dict, Any, Optional
import threading
import sys
import os
import schedule
from config import get_db_config, get_monitor_config, DB_CONFIG
#schedule psycopg2
# Добавляем текущую директорию в путь для импорта handlers
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try to import handlers
try:
    from handlers.handler_factory import HandlerFactory
    HANDLERS_AVAILABLE = True
except ImportError as e:
    print(f"Ошибка импорта обработчиков: {e}")
    print("Проверьте наличие файлов в папке handlers/")
    HANDLERS_AVAILABLE = False

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('snmp_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SNMPMonitor:
    def __init__(self, db_config: Dict[str, Any] = None, monitor_config: Dict[str, Any] = None):
        self.db_config = db_config or get_db_config()
        self.monitor_config = monitor_config or get_monitor_config()
        self.max_workers = self.monitor_config['max_workers']
        self.agent_name = self.monitor_config['agent_name']
        self.connection = None
        self.lock = threading.Lock()
        self.is_running = False

        if not HANDLERS_AVAILABLE:
            logger.error("Обработчики недоступны. Проверьте структуру файлов.")
            sys.exit(1)

    def connect_db(self) -> bool:
        """Connect to the DB with retry attempts"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.connection = psycopg2.connect(**self.db_config)
                self.connection.autocommit = False
                logger.info("Успешное подключение к БД")
                return True
            except Exception as e:
                logger.error(f"Попытка {attempt + 1}/{max_retries}: Ошибка подключения к БД: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        return False

    def disconnect_db(self):
        """Disconnect from the DB"""
        if self.connection:
            self.connection.close()
            logger.info("Отключение от БД")

    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Retrieve scheduled tasks from the CRONTAB table"""
        query = """
        SELECT ct.id as cron_id, ct.minutes, ct.hours, ct.days,
               ct.startdt, ct.lastdt, ct.status, ct.task_id, ct.agent, ct.j_id,
               t.id as task_id, t.name as task_name, t.description,
               ng.id as node_group_id, ng.name as node_group_name,
               rg.id as request_group_id, rg.name as request_group_name,
               rg.handler_id as handler_id,
               h.proc as handler_proc, et.name as element_type_name
        FROM mon.crontab ct
        JOIN mon.task t ON ct.task_id = t.id
        JOIN mon.node_group ng ON t.node_group_id = ng.id
        JOIN mon.request_group rg ON t.request_group_id = rg.id
        JOIN mon.handler h ON rg.handler_id = h.id
        JOIN mon.element_type et ON rg.type_id = et.id
        WHERE ct.status = 'ACTIVE'
          AND (ct.agent IS NULL OR ct.agent = %s OR ct.agent = 'ANY')
          AND rg.manage = true
          AND ng.id IS NOT NULL
        ORDER BY ct.id
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (self.agent_name,))
                columns = [desc[0] for desc in cursor.description]
                tasks = [dict(zip(columns, row)) for row in cursor.fetchall()]

            logger.info(f"Найдено запланированных задач: {len(tasks)}")
            for task in tasks:
                logger.debug(f"Задача: {task['task_name']}, handler_id: {task['handler_id']}")
            return tasks
        except Exception as e:
            logger.error(f"Ошибка при получении запланированных задач: {e}")
            return []

    def update_crontab_status(self, cron_id: int, status: str, j_id: int = None):
        """Update a crontab task status"""
        # For periodic tasks, always revert status back to ACTIVE
        if status in ['COMPLETED', 'ERROR']:
            status = 'ACTIVE'

        query = """
        UPDATE mon.crontab
        SET lastdt = %s, status = %s, j_id = %s
        WHERE id = %s
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (datetime.now(), status, j_id, cron_id))
                self.connection.commit()
                logger.debug(f"Обновлен статус CRONTAB {cron_id}: {status}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении CRONTAB {cron_id}: {e}")
            self.connection.rollback()

    def should_execute_task(self, cron_task: Dict[str, Any]) -> bool:
        """Decide whether a scheduled task should be executed based on interval and timestamps"""
        now = datetime.now()
        logger.debug(f"Checking task {cron_task['task_name']} at {now}")

        # Compute total interval in minutes
        days = cron_task['days'] or 0
        hours = cron_task['hours'] or 0
        minutes = cron_task['minutes'] or 0
        total_interval_minutes = days * 24 * 60 + hours * 60 + minutes

        # If no interval is specified (all fields NULL or 0), run every minute
        if total_interval_minutes == 0:
            total_interval_minutes = 1
            logger.debug("Interval not set, defaulting to 1 minute")

        logger.debug(f"Calculated interval: {total_interval_minutes} minutes "
                     f"(days={days}, hours={hours}, minutes={minutes})")

        # Check startdt
        if cron_task['startdt']:
            startdt = cron_task['startdt']
            # Convert to datetime if provided as string
            if isinstance(startdt, str):
                try:
                    startdt = datetime.fromisoformat(startdt.replace('Z', '+00:00'))
                except ValueError:
                    logger.warning(f"Invalid startdt format: {startdt}")
                    return False

            if startdt > now:
                logger.debug(f"startdt is in the future: {startdt} > {now}")
                return False
            else:
                logger.debug(f"startdt passed: {startdt} <= {now}")
                # Use startdt as reference
                reference_time = startdt
        else:
            # If startdt is not provided, use beginning of the current day
            reference_time = datetime(now.year, now.month, now.day)
            logger.debug(f"startdt not provided, using day start: {reference_time}")

        # Check lastdt
        if cron_task['lastdt']:
            last_run = cron_task['lastdt']
            # Convert to datetime if provided as string
            if isinstance(last_run, str):
                try:
                    last_run = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
                except ValueError:
                    logger.warning(f"Invalid lastdt format: {last_run}")
                    last_run = None

            if last_run:
                # Use lastdt as reference time if present
                reference_time = last_run
                logger.debug(f"Using lastdt as reference time: {reference_time}")

        # Compute time difference from the reference time
        time_diff = now - reference_time
        total_diff_minutes = time_diff.total_seconds() / 60

        logger.debug(f"Time difference from reference: {total_diff_minutes:.2f} minutes")

        # Check whether enough time has passed since last execution
        if total_diff_minutes < total_interval_minutes:
            logger.debug(f"Interval not elapsed: {total_diff_minutes:.2f} < {total_interval_minutes} minutes")
            return False

        # Verify at least one full interval passed and we're in the execution window
        intervals_passed = total_diff_minutes // total_interval_minutes
        time_since_last_interval = total_diff_minutes % total_interval_minutes

        # Execute task if at least one full interval passed and we're within 1 minute of ideal time
        if intervals_passed >= 1 and time_since_last_interval <= 1:
            logger.info(f"Task {cron_task['task_name']} should be executed "
                        f"(passed {intervals_passed} intervals of {total_interval_minutes} minutes)")
            return True
        else:
            logger.debug(f"Not execution time: passed {intervals_passed} intervals, "
                         f"{time_since_last_interval:.2f} minutes until next")
            return False

    def get_nodes_for_group(self, group_id: int) -> List[Dict[str, Any]]:
        """Получение узлов для группы"""
        query = """
        SELECT n.id, n.name, n.ipaddress, n.community, n.timeout,
               n.sysname, n.sysobjectid, n.manage, n.snmp_last_dt
        FROM mon.node n
        JOIN mon.node_group_ref ngr ON n.id = ngr.node_id
        WHERE ngr.group_id = %s AND n.manage = true
        ORDER BY n.id
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (group_id,))
                columns = [desc[0] for desc in cursor.description]
                nodes = [dict(zip(columns, row)) for row in cursor.fetchall()]

            logger.debug(f"Найдено узлов в группе {group_id}: {len(nodes)}")
            return nodes
        except Exception as e:
            logger.error(f"Ошибка при получении узлов для группы {group_id}: {e}")
            return []

    def get_requests_for_group(self, group_id: int) -> List[Dict[str, Any]]:
        """Получение запросов для группы"""
        query = """
        SELECT r.id, r.name, r.request as oid, r.prefix, r.postfix,
               r.description, rt.name as request_type, rgr.timeout
        FROM mon.request r
        JOIN mon.request_group_ref rgr ON r.id = rgr.request_id
        JOIN mon.request_type rt ON r.request_type_id = rt.id
        WHERE rgr.group_id = %s AND r.manage = true
        ORDER BY rgr.id
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (group_id,))
                columns = [desc[0] for desc in cursor.description]
                requests = [dict(zip(columns, row)) for row in cursor.fetchall()]

            logger.debug(f"Найдено запросов в группе {group_id}: {len(requests)}")
            return requests
        except Exception as e:
            logger.error(f"Ошибка при получении запросов для группы {group_id}: {e}")
            return []

    def get_handler_id_for_group(self, group_id: int) -> int:
        """Получает handler_id для группы запросов"""
        query = "SELECT handler_id FROM mon.request_group WHERE id = %s"

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (group_id,))
                result = cursor.fetchone()
                return result[0] if result else 1  # По умолчанию SNMP handler
        except Exception as e:
            logger.error(f"Ошибка получения handler_id для группы {group_id}: {e}")
            return 1

    def process_single_request(self, node: Dict[str, Any], request: Dict[str, Any],
                               journal_id: int, handler_id: int) -> Dict[str, Any]:
        """Обработка одного запроса с сохранением в result ДО выполнения обработчика"""
        start_time = time.time()
        error_msg = None
        result_data = None

        # Сначала создаем базовую запись в result
        base_result = {
            'node_id': node['id'],
            'request_id': request['id'],
            'journal_id': journal_id,
            'val': None,
            'cval': None,
            'key': None,
            'duration': 0,
            'err': None,
            'dt': datetime.now()
        }

        try:
            # Сохраняем начальную запись в result
            self.save_single_result(base_result)
            logger.debug(f"Создана начальная запись в result для запроса {request['name']}")

            # Теперь выполняем обработчик
            handler = HandlerFactory.create_handler(handler_id, self.connection)
            result_data = handler.execute(node, request, journal_id)

            # Обновляем запись в result с данными от обработчика
            if result_data:
                result_data['duration'] = int((time.time() - start_time) * 1000)
                self.update_result_record(base_result, result_data)
                logger.debug(f"Обновлена запись в result для {request['name']} с данными обработчика")
            else:
                error_msg = "Обработчик не вернул данных"

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка обработки запроса {request['name']} для {node['name']}: {e}")

            # Сохраняем запись об ошибке в result
            error_result = base_result.copy()
            error_result.update({
                'err': error_msg,
                'duration': int((time.time() - start_time) * 1000),
                'dt': datetime.now()
            })
            self.save_single_result(error_result)

        return result_data or base_result

    def save_single_result(self, result: Dict[str, Any]):
        """Сохранение одной записи в result"""
        try:
            query = """
            INSERT INTO mon.result
            (node_id, request_id, journal_id, val, key, duration, err, dt, cval)
            VALUES (%(node_id)s, %(request_id)s, %(journal_id)s,
                    %(val)s, %(key)s, %(duration)s, %(err)s, %(dt)s, %(cval)s)
            """

            with self.connection.cursor() as cursor:
                cursor.execute(query, result)
                self.connection.commit()
                logger.debug(
                    f"Saved result record: node_id={result['node_id']}, request_id={result['request_id']}")
        except Exception as e:
            logger.error(f"Ошибка сохранения в result: {e}")
            self.connection.rollback()

    def update_result_record(self, base_result: Dict[str, Any], handler_result: Dict[str, Any]):
        """Обновление существующей записи в result данными от обработчика"""
        try:
            query = """
            UPDATE mon.result
            SET val = %s, cval = %s, key = %s, duration = %s, err = %s, dt = %s
            WHERE node_id = %s AND request_id = %s AND journal_id = %s
            AND val IS NULL AND err IS NULL  -- Обновляем только незаполненные записи
            """

            params = (
                handler_result.get('val'),
                handler_result.get('cval'),
                handler_result.get('key'),
                handler_result.get('duration'),
                handler_result.get('err'),
                handler_result.get('dt'),
                base_result['node_id'],
                base_result['request_id'],
                base_result['journal_id']
            )

            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
                logger.debug("Updated result record with handler data")
        except Exception as e:
            logger.error(f"Ошибка обновления записи в result: {e}")
            self.connection.rollback()

    def process_single_node(self, node: Dict[str, Any], requests: List[Dict[str, Any]],
                            journal_id: int, handler_id: int) -> List[Dict[str, Any]]:
        """Обработка одного узла с предварительным сохранением в result"""
        results: List[Dict[str, Any]] = []
        node_has_success = False

        # First, create placeholder result records for all requests
        for request in requests:
            base_result = {
                'node_id': node['id'],
                'request_id': request['id'],
                'journal_id': journal_id,
                'val': 'PENDING',  # marker that request is in progress
                'cval': None,
                'key': 'pending',
                'duration': 0,
                'err': None,
                'dt': datetime.now()
            }
            self.save_single_result(base_result)

        logger.debug(f"Created initial result records for node {node['name']} ({len(requests)} requests)")

        # Now execute requests via handler
        for request in requests:
            result = self.process_single_request(node, request, journal_id, handler_id)
            results.append(result)

            if result.get('err') is None:
                node_has_success = True

        # Update node SNMP status only if there was at least one successful request
        if node_has_success:
            self.update_node_snmp_status(node['id'])

        return results

    def update_node_snmp_status(self, node_id: int):
        """Обновление времени последнего SNMP опроса узла"""
        query = "UPDATE mon.node SET snmp_last_dt = %s WHERE id = %s"

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (datetime.now(), node_id))
                self.connection.commit()
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса узла {node_id}: {e}")
            self.connection.rollback()

    def create_journal_entry(self, task_id: int) -> Optional[int]:
        """Создание записи в журнале"""
        query = "INSERT INTO mon.journal (startdt, task_id) VALUES (%s, %s) RETURNING id"

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (datetime.now(), task_id))
                journal_id = cursor.fetchone()[0]
                self.connection.commit()
                return journal_id
        except Exception as e:
            logger.error(f"Ошибка при создании записи журнала: {e}")
            self.connection.rollback()
            return None

    def update_journal_entry(self, journal_id: int):
        """Обновление записи в журнале (установка enddt)"""
        query = "UPDATE mon.journal SET enddt = %s WHERE id = %s"

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (datetime.now(), journal_id))
                self.connection.commit()
        except Exception as e:
            logger.error(f"Ошибка при обновлении журнала {journal_id}: {e}")
            self.connection.rollback()

    def save_results_batch(self, results: List[Dict[str, Any]]):
        """Пакетное сохранение результатов (только val, без cval)"""
        if not results:
            return

        query = """
        INSERT INTO mon.result
        (node_id, request_id, journal_id, val, key, duration, err, dt)
        VALUES (%(node_id)s, %(request_id)s, %(journal_id)s,
                %(val)s, %(key)s, %(duration)s, %(err)s, %(dt)s)
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.executemany(query, results)
                self.connection.commit()
                logger.debug(f"Сохранено результатов: {len(results)}")
        except Exception as e:
            logger.error(f"Ошибка при пакетном сохранении результатов: {e}")
            self.connection.rollback()

    def process_task(self, task: Dict[str, Any], cron_id: int = None):
        """Обработка одной задачи мониторинга в два этапа"""
        task_name = task.get('task_name', 'Unknown')
        logger.info(f"Начало обработки задачи: {task_name}")

        if cron_id:
            self.update_crontab_status(cron_id, 'RUNNING')

        journal_id = self.create_journal_entry(task['task_id'])
        if not journal_id:
            logger.error(f"Не удалось создать запись в журнале для задачи {task_name}")
            if cron_id:
                self.update_crontab_status(cron_id, 'ACTIVE')
            return

        try:
            nodes = self.get_nodes_for_group(task['node_group_id'])
            requests = self.get_requests_for_group(task['request_group_id'])
            handler_id = self.get_handler_id_for_group(task['request_group_id'])

            if not nodes or not requests:
                logger.warning(f"Нет узлов или запросов для задачи {task_name}")
                if cron_id:
                    self.update_crontab_status(cron_id, 'ACTIVE', journal_id)
                return

            logger.info(f"Обработка {len(nodes)} узлов и {len(requests)} запросов (handler: {handler_id})")

            # ЭТАП 1: Сбор сырых SNMP данных в result
            logger.info("=== ЭТАП 1: Сбор SNMP данных ===")
            raw_snmp_results = self.collect_raw_snmp_data(nodes, requests, journal_id)
            logger.info(f"Собрано сырых SNMP результатов: {len(raw_snmp_results)}")

            # Сохраняем сырые данные в result
            if raw_snmp_results:
                self.save_results_batch(raw_snmp_results)
                logger.info(f"Сохранено сырых данных в result: {len(raw_snmp_results)}")

            # ЭТАП 2: Обработка данных через handlers
            logger.info("=== ЭТАП 2: Обработка через handlers ===")
            if handler_id > 1:  # Если handler не стандартный SNMP (1)
                processed_results = self.process_with_handler(nodes, requests, journal_id, handler_id, raw_snmp_results)

                # Сохраняем обработанные данные
                if processed_results:
                    self.save_results_batch(processed_results)
                    logger.info(f"Сохранено обработанных данных в result: {len(processed_results)}")

            logger.info(f"Задача {task_name} завершена. Узлов: {len(nodes)}, Запросов: {len(requests)}")

            if cron_id:
                self.update_crontab_status(cron_id, 'ACTIVE', journal_id)

        except Exception as e:
            logger.error(f"Ошибка при обработке задачи {task_name}: {e}")
            self.connection.rollback()
            if cron_id:
                self.update_crontab_status(cron_id, 'ACTIVE', journal_id)
        finally:
            self.update_journal_entry(journal_id)

    def collect_raw_snmp_data(self, nodes: List[Dict[str, Any]], requests: List[Dict[str, Any]],
                              journal_id: int) -> List[Dict[str, Any]]:
        """Сбор сырых SNMP данных с помощью стандартного SNMP handler"""
        raw_results = []

        try:
            # Используем стандартный SNMP handler для сбора данных
            snmp_handler = HandlerFactory.create_handler(1, self.connection)  # handler_id=1 - SNMP

            for node in nodes:
                for request in requests:
                    try:
                        # Выполняем SNMP запрос
                        result = snmp_handler.execute(node, request, journal_id)

                        # Помечаем как сырые данные
                        if result.get('key'):
                            result['key'] = f"raw_{result['key']}"
                        else:
                            result['key'] = f"raw_{request['name']}"

                        raw_results.append(result)

                    except Exception as e:
                        logger.error(f"Ошибка сбора SNMP данных для {node['name']} запрос {request['name']}: {e}")
                        # Сохраняем запись об ошибке
                        error_result = self.create_error_result(node, request, journal_id, str(e))
                        raw_results.append(error_result)

        except Exception as e:
            logger.error(f"Ошибка в процессе сбора SNMP данных: {e}")

        return raw_results

    def process_with_handler(self, nodes: List[Dict[str, Any]], requests: List[Dict[str, Any]],
                             journal_id: int, handler_id: int, raw_snmp_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Обработка собранных данных через специализированный handler"""
        processed_results = []

        try:
            # Создаем специализированный handler
            handler = HandlerFactory.create_handler(handler_id, self.connection)

            # Группируем сырые данные по узлам и запросам
            raw_data_by_node_request = {}
            for result in raw_snmp_results:
                key = (result['node_id'], result['request_id'])
                if key not in raw_data_by_node_request:
                    raw_data_by_node_request[key] = []
                raw_data_by_node_request[key].append(result)

            # Обрабатываем каждый узел
            for node in nodes:
                node_processed = False
                
                # Для MAC Address Handler собираем все сырые данные узла
                if handler_id == 2:  # MAC Address Handler
                    all_raw_data = []
                    for request in requests:
                        key = (node['id'], request['id'])
                        raw_data = raw_data_by_node_request.get(key, [])
                        all_raw_data.extend(raw_data)
                    
                    if all_raw_data:
                        try:
                            # Передаем все сырые данные в handler для обработки
                            processed_result = handler.process_raw_data(node, requests[0], journal_id, all_raw_data)
                            
                            if processed_result:
                                processed_result['key'] = f"processed_{processed_result.get('key', 'mac_processing')}"
                                processed_results.append(processed_result)
                                node_processed = True
                                
                        except Exception as e:
                            logger.error(f"Ошибка обработки MAC данных для {node['name']}: {e}")
                            error_result = self.create_error_result(node, requests[0], journal_id, f"MAC Processing error: {e}")
                            processed_results.append(error_result)
                else:
                    # Для других handlers обрабатываем каждый запрос отдельно
                    for request in requests:
                        key = (node['id'], request['id'])
                        raw_data = raw_data_by_node_request.get(key, [])
                        
                        if raw_data:
                            try:
                                # Передаем сырые данные в handler для обработки
                                processed_result = handler.process_raw_data(node, request, journal_id, raw_data)
                                
                                if processed_result:
                                    # Помечаем как обработанные данные
                                    if processed_result.get('key'):
                                        processed_result['key'] = f"processed_{processed_result['key']}"
                                    else:
                                        processed_result['key'] = f"processed_{request['name']}"
                                    
                                    processed_results.append(processed_result)
                                    node_processed = True
                                    
                            except Exception as e:
                                logger.error(f"Ошибка обработки данных для {node['name']} запрос {request['name']}: {e}")
                                error_result = self.create_error_result(node, request, journal_id, f"Processing error: {e}")
                                processed_results.append(error_result)
                
                # Обновляем статус узла если была успешная обработка
                if node_processed:
                    self.update_node_snmp_status(node['id'])

        except Exception as e:
            logger.error(f"Ошибка в процессе обработки через handler: {e}")

        return processed_results

    def create_error_result(self, node: Dict[str, Any], request: Dict[str, Any],
                            journal_id: int, error_msg: str) -> Dict[str, Any]:
        """Создание записи об ошибке"""
        return {
            'node_id': node['id'],
            'request_id': request['id'],
            'journal_id': journal_id,
            'val': None,
            'cval': None,
            'key': f"error_{request['name']}",
            'duration': 0,
            'err': error_msg,
            'dt': datetime.now()
        }

    def run_scheduled_monitoring(self):
        """Запуск мониторинга по расписанию"""
        try:
            if not self.connect_db():
                logger.error("Не удалось подключиться к БД")
                return

            # Получаем запланированные задачи
            scheduled_tasks = self.get_scheduled_tasks()

            if not scheduled_tasks:
                logger.info("Нет активных запланированных задач")
                return

            # Обрабатываем задачи, которые нужно выполнить сейчас
            tasks_executed = 0
            for cron_task in scheduled_tasks:
                if self.should_execute_task(cron_task):
                    logger.info(f"Выполнение запланированной задачи: {cron_task['task_name']}")
                    self.process_task(cron_task, cron_task['cron_id'])
                    tasks_executed += 1
                else:
                    logger.debug(f"Задача {cron_task['task_name']} не требует выполнения сейчас")

            logger.info(f"Выполнено задач: {tasks_executed} из {len(scheduled_tasks)}")

        except Exception as e:
            logger.error(f"Критическая ошибка в запланированном мониторинге: {e}")
        finally:
            self.disconnect_db()

    def run_immediate_monitoring(self, task_name: str = None):
        """Немедленный запуск мониторинга (для отладки)"""
        try:
            if not self.connect_db():
                logger.error("Не удалось подключиться к БД")
                return

            # Получаем все активные задачи
            scheduled_tasks = self.get_scheduled_tasks()

            if not scheduled_tasks:
                logger.info("Нет активных задач для выполнения")
                return

            # Выполняем все задачи независимо от расписания
            for task in scheduled_tasks:
                logger.info(f"Немедленное выполнение задачи: {task['task_name']}")
                self.process_task(task)

        except Exception as e:
            logger.error(f"Ошибка в немедленном мониторинге: {e}")
        finally:
            self.disconnect_db()

    def start_scheduler(self):
        """Запуск шедулера"""
        logger.info(f"Запуск шедулера мониторинга (агент: {self.agent_name})")

        # Настраиваем расписание (каждую минуту проверяем задачи)
        interval = self.monitor_config['scheduler_interval']
        schedule.every(interval).seconds.do(self.run_scheduled_monitoring)

        logger.info(f"Шедулер настроен на проверку каждые {interval} секунд")

        self.is_running = True

        # Первый запуск сразу
        logger.info("Первый запуск мониторинга...")
        self.run_scheduled_monitoring()

        # Основной цикл шедулера
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Получен сигнал прерывания. Остановка шедулера...")
                self.stop_scheduler()
            except Exception as e:
                logger.error(f"Ошибка в шедулере: {e}")
                time.sleep(10)  # Пауза перед повторной попыткой

    def stop_scheduler(self):
        """Остановка шедулера"""
        logger.info("Остановка шедулера мониторинга")
        self.is_running = False


def main():
    """Основная функция"""
    import argparse

    parser = argparse.ArgumentParser(description='SNMP Monitor with Scheduler')
    parser.add_argument('--immediate', action='store_true',
                        help='Немедленный запуск мониторинга')
    parser.add_argument('--scheduler', action='store_true',
                        help='Запуск в режиме шедулера')
    parser.add_argument('--debug', action='store_true',
                        help='Включить детальное логирование')

    args = parser.parse_args()

    # Настройка уровня логирования
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("Включено детальное логирование")

    # Используем конфиг из config.py
    db_config = DB_CONFIG

    # Создание монитора
    monitor = SNMPMonitor(db_config)

    if args.immediate:
        logger.info("Немедленный запуск мониторинга")
        monitor.run_immediate_monitoring()
    else:
        # Запуск шедулера
        logger.info("Запуск в режиме шедулера")
        monitor.start_scheduler()


if __name__ == "__main__":
    main()
