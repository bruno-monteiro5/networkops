# NetworkOps

**Network Automation & Monitoring Lab**

A personal Network Engineering project focused on building and automating a virtual enterprise network using open-source technologies.

The goal is to demonstrate practical skills in **network infrastructure, dynamic routing, Python automation, and network monitoring**.

## Network Topology

The lab consists of two FRRouting routers and two Linux hosts connected across separate LANs.

`Host1 ── R1 ── OSPF ── R2 ── Host2`

- **LAN 1:** `192.168.10.0/24`
- **Inter-router link:** `10.0.12.0/30`
- **LAN 2:** `192.168.20.0/24`
- **Routing:** OSPF Area 0

The infrastructure is deployed using Containerlab and Docker.

## Technologies

**Networking:** FRRouting, OSPF, IPv4, SSH

**Automation:** Python, Paramiko, difflib

**Infrastructure:** Linux, Docker, Containerlab

**Monitoring (planned):** Zabbix, SNMP

## Features

- Reproducible virtual network infrastructure.
- Dynamic routing with OSPF and inter-LAN connectivity.
- Secure remote management using SSH key authentication.
- Automated router configuration backups using Python.
- Configuration change detection and comparison.
- Network monitoring and failure alerts *(planned)*.

## Getting Started

**Requirements:** Linux/WSL2, Docker, Containerlab and Python 3.

Clone the repository:

```bash
git clone https://github.com/bruno-monteiro5/networkops.git
cd networkops
```

Deploy the virtual network:

```bash
containerlab deploy -t lab/topology.clab.yml
```

Set up the Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

After configuring SSH key authentication and trusted host keys, run the automation scripts:

```bash
python automation/check_ssh.py
python automation/run_commands.py
python automation/backup_configs.py
python automation/compare_configs.py r1
```

## Project Status

| Phase | Status |
|---|---|
| Virtual Network Infrastructure | Completed |
| OSPF Routing & SSH Management | Completed |
| Network Automation | Core features completed |
| Automated Testing | In progress |
| Zabbix Monitoring & Alerts | Planned |

