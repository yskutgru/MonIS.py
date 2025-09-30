# handlers/handler_factory.py
import logging
from .snmp_handler import SNMPHandler
from .mac_address_handler import MacAddressHandler
from .interface_handler import InterfaceHandler
from .stub_handler import StubHandler
from config import get_monitor_config  # Import config

logger = logging.getLogger(__name__)


class HandlerFactory:
    """Factory for creating handlers"""

    @staticmethod
    def create_handler(handler_id: int, db_connection):
        """Create a handler by ID"""

        config = get_monitor_config()
        use_stub = config.get('use_stub_handlers', False)

        if use_stub:
            logger.info(f"Using stub instead of real handler {handler_id}")
            return StubHandler(db_connection)

        # Real handlers
        handlers = {
            1: SNMPHandler,
            2: MacAddressHandler,
            3: InterfaceHandler
        }

        handler_class = handlers.get(handler_id)
        if handler_class:
            logger.debug(f"Creating handler {handler_id}: {handler_class.__name__}")
            return handler_class(db_connection)
        else:
            error_msg = f"Unknown handler_id: {handler_id}"
            logger.error(error_msg)
            raise ValueError(error_msg)
