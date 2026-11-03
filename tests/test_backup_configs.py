
import re
import stat

import pytest
import backup_configs


VALID_CONFIG = """show running-config
Building configuration...

Current configuration:
!
frr version 10.7.1_git
frr defaults traditional
hostname r1
!
interface eth1
 ip address 10.0.12.1/30
!
interface eth2
 ip address 192.168.10.1/24
!
router ospf
 ospf router-id 1.1.1.1
!
end
r1#
"""


def test_extract_valid_configuration():
    config = backup_configs.extract_configuration(
        VALID_CONFIG, "r1"
    )

    assert config.startswith("frr version")
    assert "hostname r1" in config
    assert "router ospf" in config
    assert config.endswith("end\n")
    assert "r1#" not in config


def test_reject_missing_header():
    output = VALID_CONFIG.replace(
        "frr version 10.7.1_git", ""
    )

    with pytest.raises(
        ValueError, match="Configuration header not found"
    ):
        backup_configs.extract_configuration(output, "r1")


def test_reject_incomplete_configuration():
    output = VALID_CONFIG.replace("\nend\n", "\n")

    with pytest.raises(
        ValueError, match="Configuration end marker not found"
    ):
        backup_configs.extract_configuration(output, "r1")


@pytest.mark.parametrize(
    "missing_entry",
    ["hostname r1", "interface eth1", "router ospf"],
)
def test_reject_missing_required_entries(missing_entry):
    output = VALID_CONFIG.replace(missing_entry, "")

    with pytest.raises(
        ValueError, match="Expected configuration entry missing"
    ):
        backup_configs.extract_configuration(output, "r1")


def test_save_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(
        backup_configs, "BACKUP_DIR", tmp_path
    )

    config = backup_configs.extract_configuration(
        VALID_CONFIG, "r1"
    )

    filepath = backup_configs.save_backup("r1", config)

    assert filepath.exists()
    assert filepath.parent == tmp_path / "r1"
    assert filepath.read_text(encoding="utf-8") == config

    assert re.fullmatch(
        r"r1_\d{8}_\d{6}_\d{6}Z\.conf",
        filepath.name,
    )

    assert stat.S_IMODE(
        filepath.stat().st_mode
    ) == 0o600
