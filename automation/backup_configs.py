
from datetime import datetime, timezone
from pathlib import Path

import paramiko

from check_ssh import ROUTERS, KNOWN_HOSTS, load_private_key
from run_commands import read_until_prompt


BACKUP_DIR = Path(__file__).resolve().parent / "backups"


def collect_configuration(hostname, private_key):
    """Retrieve the active FRRouting configuration over SSH."""

    with paramiko.SSHClient() as client:
        client.load_host_keys(str(KNOWN_HOSTS))
        client.set_missing_host_key_policy(
            paramiko.RejectPolicy()
        )

        client.connect(
            hostname=hostname,
            username="admin",
            pkey=private_key,
            look_for_keys=False,
            allow_agent=False,
            timeout=10,
            auth_timeout=10,
        )

        channel = client.invoke_shell(
            width=200,
            height=200,
        )

        try:
            read_until_prompt(channel)

            # Disable terminal output pagination.
            channel.send("terminal length 0\n")
            read_until_prompt(channel)

            # Retrieve the active configuration.
            channel.send("show running-config\n")
            output = read_until_prompt(channel, timeout=30)
        finally:
            channel.close()

    return output


def extract_configuration(output, router_name):
    """Remove SSH command echoes and CLI prompts."""

    lines = output.replace("\r", "").splitlines()

    start = next(
        (
            i for i, line in enumerate(lines)
            if line.strip().startswith("frr version ")
        ),
        None,
    )

    if start is None:
        raise ValueError("Configuration header not found")

    end = next(
        (
            i for i in range(len(lines) - 1, start, -1)
            if lines[i].strip() == "end"
        ),
        None,
    )

    if end is None:
        raise ValueError("Configuration end marker not found")

    config = "\n".join(lines[start:end + 1]) + "\n"

    required = [
        f"hostname {router_name}",
        "interface eth1",
        "router ospf",
    ]

    for entry in required:
        if not any(
            line.strip() == entry
            for line in config.splitlines()
        ):
            raise ValueError(
                f"Expected configuration entry missing: {entry}"
            )

    return config


def save_backup(router_name, config):
    """Save a timestamped configuration snapshot."""

    directory = BACKUP_DIR / router_name
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%fZ"
    )

    filename = f"{router_name}_{timestamp}.conf"
    filepath = directory / filename

    # Use exclusive creation to avoid overwriting backups.
    with filepath.open("x", encoding="utf-8") as file:
        file.write(config)

    filepath.chmod(0o600)

    return filepath


def main():
    private_key = load_private_key()
    failures = 0

    for hostname in ROUTERS:
        router_name = hostname.rsplit("-", 1)[-1]

        try:
            output = collect_configuration(
                hostname, private_key
            )

            config = extract_configuration(
                output, router_name
            )

            filepath = save_backup(router_name, config)

            print(f"[OK] {router_name}: {filepath}")

        except (
            paramiko.SSHException,
            OSError,
            TimeoutError,
            ValueError,
        ) as error:
            failures += 1
            print(f"[ERROR] {router_name}: {error}")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
