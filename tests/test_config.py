import os
from config import get_db_config, get_monitor_config


def test_get_db_config_defaults(tmp_path, monkeypatch):
    # Ensure no env vars are set
    monkeypatch.delenv('DB_HOST', raising=False)
    monkeypatch.delenv('DB_NAME', raising=False)
    monkeypatch.delenv('DB_USER', raising=False)
    monkeypatch.delenv('DB_PASSWORD', raising=False)
    monkeypatch.delenv('DB_PORT', raising=False)
    monkeypatch.delenv('DB_TIMEOUT', raising=False)

    cfg = get_db_config()
    assert cfg['host'] == 'localhost'
    assert cfg['database'] == 'postgres'
    assert cfg['user'] == 'postgres'
    assert cfg['password'] == 'postgres'
    assert isinstance(cfg['port'], int)
    assert isinstance(cfg['connect_timeout'], int)


def test_get_monitor_config_env(monkeypatch):
    monkeypatch.setenv('MAX_WORKERS', '5')
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    monkeypatch.setenv('SNMP_TIMEOUT', '100')
    monkeypatch.setenv('SNMP_RETRIES', '2')
    monkeypatch.setenv('SCHEDULER_INTERVAL', '30')
    monkeypatch.setenv('AGENT_NAME', 'test_agent')
    monkeypatch.setenv('USE_STUB_HANDLERS', 'true')

    cfg = get_monitor_config()
    assert cfg['max_workers'] == 5
    assert cfg['log_level'] == 'DEBUG'
    assert cfg['snmp_timeout'] == 100
    assert cfg['snmp_retries'] == 2
    assert cfg['scheduler_interval'] == 30
    assert cfg['agent_name'] == 'test_agent'
    assert cfg['use_stub_handlers'] is True
