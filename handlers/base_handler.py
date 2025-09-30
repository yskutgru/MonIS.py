# handlers/base_handler.py
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """Base class for all handlers"""

    def __init__(self, db_connection):
        self.db_connection = db_connection

    @abstractmethod
    def execute(self, node: Dict[str, Any], request: Dict[str, Any], journal_id: int) -> Dict[str, Any]:
        """Execute processing for a single node and request"""
        pass

    def process_raw_data(self, node: Dict[str, Any], request: Dict[str, Any],
                         journal_id: int, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process collected raw data"""
        # By default return the first raw result
        if raw_data:
            return raw_data[0]

        # If no raw data available, perform the direct execute call
        return self.execute(node, request, journal_id)

    @abstractmethod
    def get_name(self) -> str:
        """Return handler display name"""
        pass
