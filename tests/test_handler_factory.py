from handlers.handler_factory import HandlerFactory
from handlers.stub_handler import StubHandler


class DummyConn:
    pass


def test_create_stub_handler(monkeypatch):
    # Force use_stub_handlers via environment
    import os
    monkeypatch.setenv('USE_STUB_HANDLERS', 'true')

    handler = HandlerFactory.create_handler(1, DummyConn())
    assert isinstance(handler, StubHandler)


def test_create_known_handler(monkeypatch):
    # Ensure stub flag is not set
    monkeypatch.delenv('USE_STUB_HANDLERS', raising=False)

    # HandlerFactory should create an object for valid ids (1 -> SNMPHandler)
    handler = HandlerFactory.create_handler(1, DummyConn())
    # We can't rely on SNMPHandler doing network ops in tests, but type should be present
    assert handler is not None
