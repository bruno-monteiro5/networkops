
import compare_configs


def create_backup(directory, filename, content):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(
        content, encoding="utf-8"
    )


def test_identical_configs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(compare_configs, "BACKUP_DIR", tmp_path)

    directory = tmp_path / "r1"
    config = "hostname r1\ninterface eth1\n"

    create_backup(directory, "r1_001.conf", config)
    create_backup(directory, "r1_002.conf", config)

    result = compare_configs.compare_latest_backups("r1")

    assert result == 0
    assert "[NO CHANGE]" in capsys.readouterr().out


def test_configuration_change(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(compare_configs, "BACKUP_DIR", tmp_path)

    directory = tmp_path / "r1"

    create_backup(
        directory,
        "r1_001.conf",
        "interface eth2\n ip address 192.168.10.1/24\n",
    )

    create_backup(
        directory,
        "r1_002.conf",
        "interface eth2\n"
        " description TEST-CHANGE\n"
        " ip address 192.168.10.1/24\n",
    )

    result = compare_configs.compare_latest_backups("r1")
    output = capsys.readouterr().out

    assert result == 1
    assert "[CHANGE DETECTED]" in output
    assert "+ description TEST-CHANGE" in output


def test_insufficient_backups(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(compare_configs, "BACKUP_DIR", tmp_path)

    result = compare_configs.compare_latest_backups("r1")

    assert result == 2
    assert "[ERROR]" in capsys.readouterr().out
