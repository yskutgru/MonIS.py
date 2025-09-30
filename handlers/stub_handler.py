# handlers/stub_handler.py
import time
from datetime import datetime
from typing import Dict, Any
import logging
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class StubHandler(BaseHandler):
    """A handler stub that only logs calls"""

    def execute(self, node: Dict[str, Any], request: Dict[str, Any], journal_id: int) -> Dict[str, Any]:
        """Stub execution of a request"""
        start_time = time.time()

        logger.info(f"STUB: Request {request['name']} for {node['name']} (OID: {request['oid']})")

        # Return a stub result
        return {
            'node_id': node['id'],
            'request_id': request['id'],
            'journal_id': journal_id,
            'val': 'stub_value',
            'cval': None,
            'key': 'stub',
            'duration': int((time.time() - start_time) * 1000),
            'err': None,
            'dt': datetime.now()
        }

    def get_name(self) -> str:
        return "Stub Handler"
