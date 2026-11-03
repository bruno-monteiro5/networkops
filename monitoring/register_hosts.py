
import argparse
import ipaddress
import json
import os
import subprocess
from urllib.request import Request, urlopen


API_URL = "http://127.0.0.1:8080/api_jsonrpc.php"

ROUTERS = {
    "NetworkOps-R1": ("R1 - Router", "clab-networkops-r1"),
    "NetworkOps-R2": ("R2 - Router", "clab-networkops-r2"),
}


def get_docker_ipv4(container_name):
    """Get the container's management IPv4 address."""

    result = subprocess.run(
        ["docker", "container", "inspect", container_name],
        capture_output=True,
        text=True,
        check=True,
    )

    container = json.loads(result.stdout)[0]
    networks = container["NetworkSettings"]["Networks"]

    if "clab" not in networks:
        raise RuntimeError(
            f"{container_name} is not connected to clab"
        )

    ip = networks["clab"].get("IPAddress")

    if not ip:
        raise RuntimeError(
            f"No management IPv4 found for {container_name}"
        )

    ipaddress.IPv4Address(ip)
    return ip


def api(method, params):
    """Execute a Zabbix JSON-RPC API request."""

    token = os.environ.get("ZABBIX_API_TOKEN")

    if not token:
        raise RuntimeError("ZABBIX_API_TOKEN is not set")

    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }).encode("utf-8")

    request = Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json-rpc",
            "Authorization": f"Bearer {token}",
        },
    )

    with urlopen(request, timeout=10) as response:
        result = json.load(response)

    if "error" in result:
        raise RuntimeError(result["error"])

    return result["result"]


def get_group(dry_run):
    groups = api("hostgroup.get", {
        "filter": {"name": ["Network devices"]},
        "output": ["groupid"],
    })

    if groups:
        return groups[0]["groupid"]

    if dry_run:
        print("[PLAN] Create host group: Network devices")
        return None

    result = api("hostgroup.create", {
        "name": "Network devices"
    })

    return result["groupids"][0]


def get_template():
    templates = api("template.get", {
        "filter": {"host": ["ICMP Ping"]},
        "output": ["templateid"],
    })

    if not templates:
        raise RuntimeError("ICMP Ping template not found")

    return templates[0]["templateid"]


def sync_host(hostname, visible_name, container, group_id,
              template_id, dry_run):
    ip = get_docker_ipv4(container)

    print(f"\n[DISCOVERED] {container}: {ip}")

    hosts = api("host.get", {
        "filter": {"host": [hostname]},
        "output": ["hostid"],
    })

    if not hosts:
        if dry_run:
            print(f"[PLAN] Create {hostname} with IPv4 {ip}")
            return

        api("host.create", {
            "host": hostname,
            "name": visible_name,
            "groups": [{"groupid": group_id}],
            "templates": [{"templateid": template_id}],
            "interfaces": [{
                "type": 1,
                "main": 1,
                "useip": 1,
                "ip": ip,
                "dns": container,
                "port": "10050",
            }],
        })

        print(f"[CREATED] {hostname}: {ip}")
        return

    host_id = hosts[0]["hostid"]

    interfaces = api("hostinterface.get", {
        "hostids": [host_id],
        "output": [
            "interfaceid", "type", "main",
            "useip", "ip",
        ],
    })

    agent_interfaces = [
        interface for interface in interfaces
        if int(interface["type"]) == 1
        and int(interface["main"]) == 1
    ]

    if not agent_interfaces:
        raise RuntimeError(
            f"{hostname} has no main Agent interface"
        )

    interface = agent_interfaces[0]

    if (
        interface["ip"] == ip
        and int(interface["useip"]) == 1
    ):
        print(f"[UNCHANGED] {hostname}: {ip}")
        return

    if dry_run:
        print(f"[PLAN] Update {hostname} to IPv4 {ip}")
        return

    api("hostinterface.update", {
        "interfaceid": interface["interfaceid"],
        "useip": 1,
        "ip": ip,
        "dns": container,
    })

    print(f"[UPDATED] {hostname}: {ip}")


def main():
    parser = argparse.ArgumentParser(
        description="Synchronize Docker routers with Zabbix"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying Zabbix",
    )
    args = parser.parse_args()

    # Discover all addresses before making any changes.
    for _, container in ROUTERS.values():
        get_docker_ipv4(container)

    group_id = get_group(args.dry_run)
    template_id = get_template()

    for hostname, (visible_name, container) in ROUTERS.items():
        sync_host(
            hostname, visible_name, container,
            group_id, template_id, args.dry_run,
        )

    print("\n[OK] Synchronization completed")


if __name__ == "__main__":
    main()
