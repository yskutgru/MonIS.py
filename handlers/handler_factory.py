# handlers/handler_factory.py
import logging
from .snmp_handler import SNMPHandler
from .mac_address_handler import MacAddressHandler
from .interface_handler import InterfaceHandler
from .stub_handler import StubHandler
from config import get_monitor_config  # Импортируем конфиг

logger = logging.getLogger(__name__)


class HandlerFactory:
    """Фабрика для создания обработчиков"""

    @staticmethod
    def create_handler(handler_id: int, db_connection):
        """Создает обработчик по ID"""

        config = get_monitor_config()
        use_stub = config.get('use_stub_handlers', False)

        if use_stub:
            logger.info(f"Используется заглушка вместо обработчика {handler_id}")
            return StubHandler(db_connection)

        # Нормальные обработчики
        handlers = {
            1: SNMPHandler,
            2: MacAddressHandler,
            3: InterfaceHandler
        }

        handler_class = handlers.get(handler_id)
        if handler_class:
            logger.debug(f"Создание обработчика {handler_id}: {handler_class.__name__}")
            return handler_class(db_connection)
        else:
            error_msg = f"Неизвестный handler_id: {handler_id}"
            logger.error(error_msg)
            raise ValueError(error_msg)
