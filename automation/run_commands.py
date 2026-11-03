
import re
import time

import paramiko

from check_ssh import ROUTERS, KNOWN_HOSTS, load_private_key


COMMANDS = [
    "show version",
    "show ip ospf neighbor",
]

PROMPT_PATTERN = re.compile(r"[A-Za-z0-9_.:-]+[>#]")
ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def read_until_prompt(channel, timeout=15):
    deadline = time.monotonic() + timeout
    output = ""

    while time.monotonic() < deadline:
        if channel.recv_ready():
            data = channel.recv(65535)

            if not data:
                break

            output += data.decode("utf-8", errors="replace")

            clean_output = ANSI_PATTERN.sub("", output)
            clean_output = clean_output.replace("\r", "")

            last_line = clean_output.split("\n")[-1].strip()

            if PROMPT_PATTERN.fullmatch(last_line):
                return clean_output

        if channel.closed:
            break

        time.sleep(0.1)

    raise TimeoutError("Router CLI prompt not received")


def run_commands(hostname, private_key):
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
            height=100,
        )

        # Wait for the initial CLI prompt.
        read_until_prompt(channel)

        for command in COMMANDS:
            print(f"\n[{hostname}] Executing: {command}")

            channel.send(command + "\n")
            output = read_until_prompt(channel)

            print(output)


def main():
    private_key = load_private_key()
    failures = 0

    for router in ROUTERS:
        try:
            run_commands(router, private_key)
        except (
            paramiko.SSHException,
            OSError,
            TimeoutError,
        ) as error:
            failures += 1
            print(f"[ERROR] {router}: {error}")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()


