"""Safely simulate an R1-R2 routing link failure in the NetworkOps lab.

Usage (from the repository root):
    python automation/test_network_failure.py           # read-only preflight
    python automation/test_network_failure.py --run     # interactive test

Only R1 eth1 is changed; the Docker management interface eth0 is untouched.
"""

import argparse
import subprocess
import sys
import time

R1 = "clab-networkops-r1"
HOST1 = "clab-networkops-host1"
DESTINATION = "192.168.20.10"
REMOTE_LAN = "192.168.20.0/24"


def run(*args, check=True):
    result = subprocess.run(
        args, text=True, capture_output=True, timeout=20, check=False
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{detail}")
    return result


def router(*args, root=False):
    prefix = ["docker", "exec"]
    if root:
        prefix.extend(["-u", "0"])
    return run(*prefix, R1, *args)


def ospf_full():
    return "Full" in router("vtysh", "-c", "show ip ospf neighbor").stdout


def remote_route_present():
    return REMOTE_LAN in router("vtysh", "-c", "show ip route ospf").stdout


def ping_works():
    result = run(
        "docker", "exec", HOST1, "ping", "-c", "3", "-W", "1", DESTINATION,
        check=False,
    )
    return result.returncode == 0


def interface_is_up():
    result = router("ip", "-br", "link", "show", "eth1").stdout
    return result.split()[1] == "UP"


def set_interface(state):
    router("ip", "link", "set", "dev", "eth1", state, root=True)


def wait_for(predicate, seconds=60, interval=2):
    deadline = time.monotonic() + seconds
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Perform the link failure test")
    args = parser.parse_args()

    print("[PREFLIGHT] Checking R1 eth1, OSPF, route, and host connectivity...")
    results = {
        "R1 eth1 UP": interface_is_up(),
        "OSPF neighbor Full": ospf_full(),
        f"OSPF route {REMOTE_LAN}": remote_route_present(),
        "Host1 to Host2 ping": ping_works(),
    }
    for name, passed in results.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")

    if not all(results.values()):
        print("[ABORTED] Network is not healthy; no changes made.")
        return 1

    if not args.run:
        print("[OK] Read-only checks passed. Use --run to simulate a failure.")
        return 0

    confirm = input("Type FAIL to disable R1 eth1 temporarily: ")
    if confirm != "FAIL":
        print("[CANCELLED] No changes made.")
        return 0

    print("[FAILURE] Disabling R1 eth1...")
    # The finally block restores the link if the test fails or is interrupted.
    try:
        set_interface("down")
        if not wait_for(lambda: not ospf_full(), seconds=30):
            raise RuntimeError("OSPF adjacency did not go down as expected")
        print("[PASS] OSPF adjacency lost")
        if not wait_for(lambda: not remote_route_present(), seconds=30):
            raise RuntimeError("Remote OSPF route is still present")
        print("[PASS] Remote OSPF route removed")
        if not wait_for(lambda: not ping_works(), seconds=15):
            raise RuntimeError("Host1 can still reach Host2")
        print("[PASS] Host-to-host connectivity lost")
        print("\nCheck Zabbix: R1 eth1 Link down should become PROBLEM.")
        input("After confirming the alert, press Enter to restore eth1... ")
    finally:
        print("\n[RECOVERY] Re-enabling R1 eth1...")
        set_interface("up")
        print("[RECOVERY] Interface re-enabled")

    if not wait_for(lambda: ospf_full() and remote_route_present(), seconds=90):
        print("[FAIL] OSPF route/adjacency did not recover within the check window")
        return 1
    print("[PASS] OSPF neighbor Full and remote route restored")
    if not wait_for(ping_works, seconds=30):
        print("[FAIL] Host-to-host ping has not recovered")
        return 1
    print("[PASS] Host-to-host connectivity restored")
    print("[NEXT] Confirm the Zabbix event changed from PROBLEM to RESOLVED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Test interrupted; restoration attempted if needed")
        sys.exit(130)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        print("Recovery command if necessary:")
        print(f"  docker exec -u 0 {R1} ip link set dev eth1 up", file=sys.stderr)
        sys.exit(1)


