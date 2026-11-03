"""Discover NetworkOps routers in Docker and synchronize their Zabbix hosts.

Run from WSL with Docker available and ZABBIX_API_TOKEN set.
Use --dry-run to preview changes without writing to Zabbix.
"""

import argparse
import ipaddress
import json
import os
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = os.environ.get(
    "ZABBIX_API_URL", "http://127.0.0.1:8080/api_jsonrpc.php"
)
SNMP_COMMUNITY = os.environ.get(
    "NETWORKOPS_SNMP_COMMUNITY", "networkops_lab_ro"
)
GROUP_NAME = "Network devices"
TEMPLATE_NAMES = ("ICMP Ping", "Interfaces by SNMP")
ROUTERS = {
    "NetworkOps-R1": ("R1 - Router", "clab-networkops-r1"),
    "NetworkOps-R2": ("R2 - Router", "clab-networkops-r2"),
}


def get_docker_ipv4(container_name):
    """Read the IPv4 address assigned to the Docker 'clab' network."""
    result = subprocess.run(
        ["docker", "container", "inspect", container_name],
        capture_output=True,
        text=True,
        check=True,
    )
    container = json.loads(result.stdout)[0]
    network = container["NetworkSettings"]["Networks"].get("clab")
    if network is None:
        raise RuntimeError(f"{container_name}: not connected to Docker network 'clab'")
    ip = network.get("IPAddress")
    if not ip:
        raise RuntimeError(f"{container_name}: management IPv4 not found")
    return str(ipaddress.IPv4Address(ip))


def api(method, params):
    """Call the Zabbix 7.0 JSON-RPC API using an API token."""
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
    try:
        with urlopen(request, timeout=30) as response:
            reply = json.load(response)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Zabbix API connection failed: {exc}") from exc
    if "error" in reply:
        error = reply["error"]
        raise RuntimeError(
            f"Zabbix {method}: {error.get('message', 'API error')} "
            f"{error.get('data', '')}"
        )
    if "result" not in reply:
        raise RuntimeError(f"Zabbix {method}: missing API result")
    return reply["result"]


def get_group_id(dry_run):
    groups = api("hostgroup.get", {
        "filter": {"name": [GROUP_NAME]},
        "output": ["groupid"],
    })
    if groups:
        return groups[0]["groupid"]
    if dry_run:
        print(f"[PLAN] Create host group: {GROUP_NAME}")
        return None
    return api("hostgroup.create", {"name": GROUP_NAME})["groupids"][0]


def get_template_ids():
    templates = api("template.get", {
        "filter": {"host": list(TEMPLATE_NAMES)},
        "output": ["templateid", "host"],
    })
    found = {template["host"]: template["templateid"] for template in templates}
    missing = [name for name in TEMPLATE_NAMES if name not in found]
    if missing:
        raise RuntimeError("Missing Zabbix template(s): " + ", ".join(missing))
    return found


def interface_config(kind, ip, container):
    """Return desired Agent (for ICMP) or SNMP host interface settings."""
    config = {
        "type": kind,
        "main": 1,
        "useip": 1,
        "ip": ip,
        "dns": container,
        "port": "10050" if kind == 1 else "161",
    }
    if kind == 2:
        config["details"] = {
            "version": 2,
            "bulk": 1,
            "community": SNMP_COMMUNITY,
        }
    return config


def sync_interfaces(host_id, ip, container, dry_run):
    """Create missing interfaces and update only fields that differ."""
    existing = api("hostinterface.get", {
        "hostids": [host_id],
        "output": "extend",
    })

    for kind, label in ((1, "Agent"), (2, "SNMP")):
        desired = interface_config(kind, ip, container)
        matches = [i for i in existing if int(i["type"]) == kind]
        if not matches:
            if dry_run:
                print(f"[PLAN] Add {label} interface: {ip}:{desired['port']}")
            else:
                api("hostinterface.create", {"hostid": host_id, **desired})
                print(f"[CREATED] {label} interface: {ip}:{desired['port']}")
            continue

        # Prefer the primary interface; leave any secondary interfaces untouched.
        current = next((i for i in matches if int(i["main"]) == 1), matches[0])
        changes = {}
        for field in ("ip", "useip", "port"):
            if str(current.get(field, "")) != str(desired[field]):
                changes[field] = desired[field]
        if kind == 2:
            details = current.get("details") or {}
            if (
                str(details.get("version")) != "2"
                or details.get("community") != SNMP_COMMUNITY
            ):
                # Set a complete, supported SNMPv2c configuration.
                changes["details"] = desired["details"]

        if not changes:
            print(f"[UNCHANGED] {label} interface: {ip}:{desired['port']}")
        elif dry_run:
            print(f"[PLAN] Update {label} interface: {', '.join(changes)}")
        else:
            api("hostinterface.update", {
                "interfaceid": current["interfaceid"], **changes,
            })
            print(f"[UPDATED] {label} interface: {', '.join(changes)}")


def sync_templates(host_id, linked_templates, template_ids, dry_run):
    """Link missing templates without unlinking any existing ones."""
    linked = {item["templateid"] for item in linked_templates}
    missing = [
        (name, template_id)
        for name, template_id in template_ids.items()
        if template_id not in linked
    ]
    if not missing:
        print("[UNCHANGED] Templates: ICMP Ping, Interfaces by SNMP")
        return
    if dry_run:
        print("[PLAN] Link template(s): " + ", ".join(name for name, _ in missing))
        return
    api("host.massadd", {
        "hosts": [{"hostid": host_id}],
        "templates": [{"templateid": template_id} for _, template_id in missing],
    })
    print("[LINKED] Template(s): " + ", ".join(name for name, _ in missing))


def sync_host(hostname, visible_name, container, ip, group_id, template_ids, dry_run):
    print(f"\n[DISCOVERED] {container}: {ip}")
    hosts = api("host.get", {
        "filter": {"host": [hostname]},
        "output": ["hostid"],
        "selectParentTemplates": ["templateid"],
    })
    if not hosts:
        if dry_run:
            print(f"[PLAN] Create {hostname} with Agent + SNMP interfaces")
            print("[PLAN] Link: ICMP Ping, Interfaces by SNMP")
            return
        api("host.create", {
            "host": hostname,
            "name": visible_name,
            "groups": [{"groupid": group_id}],
            "templates": [{"templateid": tid} for tid in template_ids.values()],
            "interfaces": [
                interface_config(1, ip, container),
                interface_config(2, ip, container),
            ],
        })
        print(f"[CREATED] {hostname}: {ip}, ICMP + SNMP")
        return

    host = hosts[0]
    sync_interfaces(host["hostid"], ip, container, dry_run)
    sync_templates(
        host["hostid"], host.get("parentTemplates", []), template_ids, dry_run
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Show intended changes only"
    )
    args = parser.parse_args()

    # Fail early before modifying Zabbix if any container is missing.
    addresses = {
        hostname: get_docker_ipv4(container)
        for hostname, (_, container) in ROUTERS.items()
    }
    template_ids = get_template_ids()
    group_id = get_group_id(args.dry_run)

    for hostname, (visible_name, container) in ROUTERS.items():
        sync_host(
            hostname, visible_name, container, addresses[hostname],
            group_id, template_ids, args.dry_run,
        )
    print("\n[OK] Synchronization completed")


if __name__ == "__main__":
    main()