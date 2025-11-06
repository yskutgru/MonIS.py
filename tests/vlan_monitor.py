#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import re

def parse_tcpdump_line(line):
    """
    Парсит строку вывода tcpdump и извлекает MAC-адреса и VLAN
    """
    # Регулярные выражения для поиска MAC-адресов и VLAN
    mac_pattern = r'([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})'
    vlan_pattern = r'vlan\s+(\d+)'
    
    try:
        # Ищем MAC-адреса
        mac_addresses = re.findall(mac_pattern, line)
        src_mac = mac_addresses[0] if len(mac_addresses) > 0 else "N/A"
        dst_mac = mac_addresses[1] if len(mac_addresses) > 1 else "N/A"
        
        # Ищем VLAN
        vlan_match = re.search(vlan_pattern, line)
        vlan_id = vlan_match.group(1) if vlan_match else "N/A"
        
        return {
            'src_mac': src_mac,
            'dst_mac': dst_mac,
            'vlan_id': vlan_id,
            'raw_line': line.strip()
        }
    except Exception as e:
        return {
            'src_mac': 'N/A',
            'dst_mac': 'N/A',
            'vlan_id': 'N/A',
            'raw_line': line.strip(),
            'error': str(e)
        }

def main():
    # Запускаем tcpdump процесс
    cmd = ['tcpdump', '-i', 'any', '-en', 'ip', '-l']
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True
        )
        print(process)
        print("Запущен мониторинг VLAN + IPv6 трафика...")
        print("=" * 60)
        
        # Обрабатываем вывод построчно
        for line in process.stdout:
            # print("=" * 60)
            data = parse_tcpdump_line(line)
            
            # Выводим обработанные данные
            if data['vlan_id'] != 'N/A':
                print(f"VLAN: {data['vlan_id']} | SRC: {data['src_mac']} | DST: {data['dst_mac']}")
            
    except KeyboardInterrupt:
        print("\nОстановлено пользователем")
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        if 'process' in locals():
            process.terminate()

if __name__ == "__main__":
    main()