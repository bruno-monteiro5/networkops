
import argparse
import difflib
from pathlib import Path


BACKUP_DIR = Path(__file__).resolve().parent / "backups"


def compare_latest_backups(router):
    """Compare the two most recent configuration backups."""

    directory = BACKUP_DIR / router
    backups = sorted(directory.glob(f"{router}_*.conf"))

    if len(backups) < 2:
        print(f"[ERROR] {router}: At least two backups are required")
        return 2

    previous, current = backups[-2:]

    old_config = previous.read_text(encoding="utf-8")
    new_config = current.read_text(encoding="utf-8")

    print(f"\nRouter: {router}")
    print(f"Previous: {previous.name}")
    print(f"Current:  {current.name}")

    if old_config == new_config:
        print(f"[NO CHANGE] {router}: Configurations are identical")
        return 0

    differences = difflib.unified_diff(
        old_config.splitlines(keepends=True),
        new_config.splitlines(keepends=True),
        fromfile=previous.name,
        tofile=current.name,
    )

    print(f"\n[CHANGE DETECTED] {router}")
    print("".join(differences), end="")

    return 1


def main():
    parser = argparse.ArgumentParser(
        description="Compare network configuration backups"
    )

    parser.add_argument(
        "router",
        choices=["r1", "r2"],
        help="Router to compare",
    )

    args = parser.parse_args()

    raise SystemExit(compare_latest_backups(args.router))


if __name__ == "__main__":
    main()


