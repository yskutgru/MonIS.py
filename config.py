# config.py
import os
from typing import Dict, Any


# Конфигурация БД для прямого использования
DB_CONFIG = {
    'host': 'localhost',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'postgres',
    'port': 5432,
    'connect_timeout': 10
}


def get_db_config() -> Dict[str, Any]:
    """Получение конфигурации БД из переменных окружения"""
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'postgres'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'connect_timeout': int(os.getenv('DB_TIMEOUT', '10'))
    }


# config.py - добавить в get_monitor_config()
def get_monitor_config() -> Dict[str, Any]:
    """Получение конфигурации монитора"""
    return {
        'max_workers': int(os.getenv('MAX_WORKERS', '3')),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'snmp_timeout': int(os.getenv('SNMP_TIMEOUT', '500')),
        'snmp_retries': int(os.getenv('SNMP_RETRIES', '1')),
        'scheduler_interval': int(os.getenv('SCHEDULER_INTERVAL', '60')),
        'agent_name': os.getenv('AGENT_NAME', 'python_snmp_agent'),
        'use_stub_handlers': os.getenv('USE_STUB_HANDLERS', 'false').lower() == 'true'  # <--- НОВЫЙ ФЛАГ
    }
