# Network Failure Detection & Recovery

## Overview

NetworkOps validates how an OSPF network behaves during a link failure and how it recovers when connectivity is restored. The test uses **Containerlab**, **FRRouting**, **Python** and **Zabbix SNMP monitoring**.

The simulated failure affects only **R1 `eth1`** (the link to R2). The Docker management interface (`eth0`) remains available.

## Test scenario

```text
Host1 (192.168.10.10) -- R1 -- [eth1 / OSPF] -- R2 -- Host2 (192.168.20.10)
```

| Stage | Expected network behavior | Zabbix observation |
| --- | --- | --- |
| Healthy | OSPF adjacency `Full`; remote route present; Host1 can reach Host2 | R1 `eth1` operational status `up (1)` |
| Failure | R1 `eth1` disabled; adjacency and remote route disappear; host-to-host ping fails | `Interface eth1: Link down` problem is raised |
| Recovery | R1 `eth1` restored; OSPF reconverges; connectivity returns | Interface returns to `up (1)` and the problem resolves |

## Automated test

From the repository root, run the **read-only preflight**:

```bash
python automation/test_network_failure.py
```

It checks that R1 `eth1` is up, the OSPF neighbor is `Full`, the remote OSPF route `192.168.20.0/24` exists, and Host1 can ping Host2.

To run the **interactive failure-and-recovery test**:

```bash
python automation/test_network_failure.py --run
```

Type `FAIL` when prompted to confirm the deliberate disruption. The script then:

1. Disables R1 `eth1` using `docker exec`.
2. Verifies OSPF adjacency loss, removal of the remote route and failed host connectivity.
3. Pauses so the Zabbix `Link down` alert can be checked manually.
4. Restores R1 `eth1` and verifies OSPF and connectivity recovery.

The script uses `try/finally` to **attempt interface restoration** even when a verification fails or the test is interrupted. This does not protect against host shutdown, forced process termination or a failed Docker command.

**Manual recovery**, if required:

```bash
docker exec -u 0 clab-networkops-r1 ip link set dev eth1 up
```

## Validated results

The following behavior was observed in the NetworkOps lab:

- Disabling the inter-router link caused loss of OSPF adjacency and the remote route.
- Host1-to-Host2 connectivity failed during the outage.
- Zabbix detected the SNMP interface state change and raised a `Link down` problem.
- Re-enabling the link restored OSPF, the route and host connectivity.
- Zabbix automatically marked the problem as resolved.
- The interactive Python test (`--run`) completed successfully.

**Scope:** Network checks are automated; checking the Zabbix alert and its recovery is currently **manual**. The script does not yet query the Zabbix API to assert event state.

## Next improvements

Automate Zabbix problem/recovery verification through its API, and add unit tests for the failure-test script without disrupting live containers.
