
# NetworkOps

**Network Automation & Monitoring Lab**

A personal networking project focused on building, automating, and monitoring a virtual enterprise network using open-source technologies.

## Project Objectives

- Build a reproducible virtual network infrastructure.
- Configure routing and remote device management.
- Automate configuration backups using Python and SSH.
- Monitor devices and interfaces using Zabbix.
- Detect network failures and generate alerts.

## Technology Stack

- Containerlab
- FRRouting (FRR)
- Docker
- Linux
- Python (planned)
- Zabbix (planned)

## Network Topology

Host1 --- R1 --- R2 --- Host2

| Device | Interface | IPv4 Address |
|--------|-----------|--------------|
| R1 | eth1 | 10.0.12.1/30 |
| R1 | eth2 | 192.168.10.1/24 |
| R2 | eth1 | 10.0.12.2/30 |
| R2 | eth2 | 192.168.20.1/24 |
| Host1 | eth1 | 192.168.10.10/24 |
| Host2 | eth1 | 192.168.20.10/24 |

## Current Status

### Implemented

- Two virtual FRRouting routers
- Two Linux hosts
- Point-to-point router connectivity
- Two separate LANs
- Persistent router configurations
- Basic ICMP connectivity testing

### Planned

- OSPF dynamic routing
- SSH-based network automation
- Automated configuration backups
- Configuration change detection
- Zabbix monitoring dashboard
- Failure detection and alerting
- Automated tests

## Quick Start

Requirements:
- Linux environment
- Docker Engine
- Containerlab

Deploy the topology:

```bash
sudo containerlab deploy -t lab/topology.clab.yml
```

Inspect the lab:

```bash
sudo containerlab inspect -t lab/topology.clab.yml
```

Test router connectivity:

```bash
sudo docker exec clab-networkops-r1 ping -c 3 10.0.12.2
```

Destroy the lab:

```bash
sudo containerlab destroy -t lab/topology.clab.yml
```

## Project Status

Phase 1: Virtual infrastructure implemented and connectivity validated.

This project is under active development.
