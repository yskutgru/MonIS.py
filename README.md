# MonIS.py
# MonIS.py — SNMP Monitoring System

A simple and efficient network monitoring system for automatic data collection and inventory of network devices via the SNMP protocol.

[🇷🇺 Read in Russian](README.ru.md)

---

## 🎯 Purpose
MonIS.py automates the collection and analysis of information from network equipment using SNMP, enabling network inventory and basic monitoring with minimal setup.

---

## ⚡ Key Features
- **Automatic interface discovery** – full device port inventory  
- **MAC address collection** – track connected network devices  
- **Flexible scheduling** – customizable task execution intervals  
- **Multithreading** – parallel polling of multiple devices  
- **Modular architecture** – easy to extend with custom data processors

---

## 🏗 Architecture



- SNMP Devices → Data Collection → Processors → PostgreSQL → Analytics
↑ ↑ ↑ ↑
- Switches SNMP Requests Interfaces Results
- Routers MAC Addresses Statistics


---

## 🛠 Technologies
- **Python 3.8+** — core language  
- **PostgreSQL** — monitoring data storage  
- **SNMP v2c** — data collection protocol  
- **pysnmp** — SNMP library

---

## 📊 What the system monitors
- **Device interfaces:** names, statuses, speeds, MAC addresses  
- **MAC addresses:** switching tables, ARP tables  
- **Statistics:** device availability, polling errors  
- **Performance:** response time, request duration

---

## 🚀 Quick Start

1. **Install dependencies**  
   ```bash
   python install_deps.py

2. **Configure the database**
Run the provided SQL initialization scripts.

3. **Add network devices**
Insert records into the mon.node table.

4. **Run the scheduler**
   ```bash
   python snmp_monitor.py --scheduler

💡 Benefits

- **Simplicity** – minimal configuration required

- **Reliability** – fault-tolerant with retry mechanisms

- **Flexibility** – easily adaptable to various device types

- **Scalability** – supports networks with hundreds of devices

🧭 Roadmap

Planned support for:

- SSH-based data collection

- Python-based probes for various information systems

📄 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.


---
