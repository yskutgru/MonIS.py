# handlers/handler_factory.py
import logging
from .snmp_handler import SNMPHandler
from .mac_address_handler import MacAddressHandler
from .interface_handler import InterfaceHandler
from .stub_handler import StubHandler
from .interface_discovery_handler import InterfaceDiscoveryHandler
from .mac_table_handler import MacTableHandler
from .arp_handler import ArpHandler
from .health_handler import HealthHandler
from config import get_monitor_config

logger = logging.getLogger(__name__)


class HandlerFactory:
    """Factory to create handler instances."""

    @staticmethod
    def create_handler(handler_id: int, db_connection):
        """Create a handler instance by numeric ID.

        If monitor config sets 'use_stub_handlers', always return the StubHandler.
        """

        config = get_monitor_config()
        use_stub = config.get('use_stub_handlers', False)

        if use_stub:
            logger.info(f"Using stub handler instead of handler {handler_id}")
            return StubHandler(db_connection)

        # Mapping of handler IDs to classes. Keep legacy IDs working and add new SRP handlers.
        handlers = {
            1: SNMPHandler,
            2: MacAddressHandler,         # legacy combined MAC handler
            3: InterfaceHandler,          # legacy interface handler
            4: InterfaceDiscoveryHandler, # SRP: discover interfaces
            5: MacTableHandler,           # SRP: parse bridge FDB / MAC table
            6: ArpHandler,                # SRP: parse ARP table
            7: HealthHandler,             # SRP: node health
            99: StubHandler,
        }

        handler_class = handlers.get(handler_id)
        if handler_class:
            logger.debug(f"Creating handler {handler_id}: {handler_class.__name__}")
            return handler_class(db_connection)

        error_msg = f"Unknown handler_id: {handler_id}"
        logger.error(error_msg)
        raise ValueError(error_msg)
