# config.py
import os
from typing import Dict, Any

# Load .env file if python-dotenv is available. This makes it easy to keep
# secrets and configuration in a local `.env` file during development.
try:
    from dotenv import load_dotenv
    # Load the .env file located next to this config.py
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
except Exception:
    # If python-dotenv is not installed, environment variables will still be used.
    # We avoid crashing here so the module remains importable in constrained envs.
    pass


# DB configuration accessor
def get_db_config() -> Dict[str, Any]:
    """Return DB configuration read from environment variables (or .env).

    Values are read from the environment using these variable names:
      - DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT, DB_TIMEOUT
    Defaults are provided for local development.
    """
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'postgres'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'connect_timeout': int(os.getenv('DB_TIMEOUT', '10'))
    }


# Monitor configuration accessor
def get_monitor_config() -> Dict[str, Any]:
    """Return monitor configuration read from environment variables (or .env).

    Environment variables read:
      - MAX_WORKERS, LOG_LEVEL, SNMP_TIMEOUT, SNMP_RETRIES,
        SCHEDULER_INTERVAL, AGENT_NAME, USE_STUB_HANDLERS
    """
    return {
        'max_workers': int(os.getenv('MAX_WORKERS', '3')),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'snmp_timeout': int(os.getenv('SNMP_TIMEOUT', '500')),
        'snmp_retries': int(os.getenv('SNMP_RETRIES', '1')),
        'scheduler_interval': int(os.getenv('SCHEDULER_INTERVAL', '60')),
        'agent_name': os.getenv('AGENT_NAME', 'python_snmp_agent'),
        'use_stub_handlers': os.getenv('USE_STUB_HANDLERS', 'false').lower() == 'true'
    }


# Convenience constant for libraries that expect DB_CONFIG at import time
# WARNING: this reads environment variables at import time (after dotenv load above)
DB_CONFIG = get_db_config()
