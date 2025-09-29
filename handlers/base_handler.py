# handlers/base_handler.py
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """Базовый класс для всех обработчиков"""

    def __init__(self, db_connection):
        self.db_connection = db_connection

    @abstractmethod
    def execute(self, node: Dict[str, Any], request: Dict[str, Any], journal_id: int) -> Dict[str, Any]:
        """Выполнение обработки для одного узла и запроса"""
        pass

    def process_raw_data(self, node: Dict[str, Any], request: Dict[str, Any],
                         journal_id: int, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Обработка собранных сырых данных"""
        # По умолчанию возвращаем первый результат
        if raw_data:
            return raw_data[0]

        # Если нет сырых данных, выполняем прямой запрос
        return self.execute(node, request, journal_id)

    @abstractmethod
    def get_name(self) -> str:
        """Возвращает имя обработчика"""
        pass
