#!/usr/bin/env python3
import sys
import os

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from handlers.mac_address_handler import MacAddressHandler, PYSNAP_AVAILABLE
    print(f"✓ MacAddressHandler импортирован успешно")
    print(f"✓ PYSNAP_AVAILABLE = {PYSNAP_AVAILABLE}")
    
    from handlers.snmp_handler import SNMPHandler
    print(f"✓ SNMPHandler импортирован успешно") 
    
    from handlers.handler_factory import HandlerFactory
    print("✓ HandlerFactory импортирован успешно")
    
    # Тест создания обработчиков
    factory = HandlerFactory()
    handler1 = factory.create_handler(1, None)
    handler2 = factory.create_handler(2, None)
    print("✓ Оба обработчика созданы успешно")
    
    print("✓ Все импорты прошли успешно!")
    
except ImportError as e:
    print(f"✗ Ошибка импорта: {e}")
    import traceback
    traceback.print_exc()