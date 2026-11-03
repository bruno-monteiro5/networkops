
from pathlib import Path
from getpass import getpass

import paramiko

ROUTERS = [
    "clab-networkops-r1",
    "clab-networkops-r2",
]

SSH_KEY = Path.home() / ".ssh/networkops_ed25519"
KNOWN_HOSTS = Path.home() / ".ssh/networkops_known_hosts"


def load_private_key():
    try:
        return paramiko.Ed25519Key.from_private_key_file(
            str(SSH_KEY)
        )
    except paramiko.PasswordRequiredException:
        return paramiko.Ed25519Key.from_private_key_file(
            str(SSH_KEY),
            password=getpass("SSH key passphrase: "),
        )


def check_connection(hostname, private_key):
    with paramiko.SSHClient() as client:
        client.load_host_keys(str(KNOWN_HOSTS))
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

        client.connect(
            hostname=hostname,
            username="admin",
            pkey=private_key,
            look_for_keys=False,
            allow_agent=False,
            timeout=10,
            auth_timeout=10,
        )

        print(f"[OK] {hostname}: SSH authentication successful")


def main():
    private_key = load_private_key()
    failures = 0

    for router in ROUTERS:
        try:
            check_connection(router, private_key)
        except (paramiko.SSHException, OSError) as error:
            failures += 1
            print(f"[FAIL] {router}: {error}")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

