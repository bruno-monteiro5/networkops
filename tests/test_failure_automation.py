"""Unit tests for the failure/recovery tool. No live Docker calls."""

import sys
from types import SimpleNamespace

import pytest

# pytest.ini adds the automation/ directory to the Python import path.
# The real automation module is renamed to automation/network_failure.py.
import network_failure as failure


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("2.2.2.2  1 Full/DR 00:00:34 10.0.12.2 eth1\n", True),
        ("", False),
    ],
)
def test_ospf_full(monkeypatch, output, expected):
    monkeypatch.setattr(
        failure, "router", lambda *args, **kwargs: SimpleNamespace(stdout=output)
    )
    assert failure.ospf_full() is expected


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("O>* 192.168.20.0/24 [110/20] via 10.0.12.2", True),
        ("No OSPF routes", False),
    ],
)
def test_remote_route_present(monkeypatch, output, expected):
    monkeypatch.setattr(
        failure, "router", lambda *args, **kwargs: SimpleNamespace(stdout=output)
    )
    assert failure.remote_route_present() is expected


@pytest.mark.parametrize(("returncode", "expected"), [(0, True), (1, False)])
def test_ping_works(monkeypatch, returncode, expected):
    def fake_run(*args, **kwargs):
        assert kwargs["check"] is False
        assert "ping" in args
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(failure, "run", fake_run)
    assert failure.ping_works() is expected


@pytest.mark.parametrize(
    ("output", "expected"),
    [("eth1 UP 10.0.12.1/30\n", True), ("eth1 DOWN 10.0.12.1/30\n", False)],
)
def test_interface_is_up(monkeypatch, output, expected):
    monkeypatch.setattr(
        failure, "router", lambda *args, **kwargs: SimpleNamespace(stdout=output)
    )
    assert failure.interface_is_up() is expected


def test_set_interface_uses_root_and_eth1(monkeypatch):
    calls = []
    monkeypatch.setattr(
        failure, "router", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    failure.set_interface("down")
    assert calls == [
        (("ip", "link", "set", "dev", "eth1", "down"), {"root": True})
    ]


def healthy_preflight(monkeypatch):
    monkeypatch.setattr(failure, "interface_is_up", lambda: True)
    monkeypatch.setattr(failure, "ospf_full", lambda: True)
    monkeypatch.setattr(failure, "remote_route_present", lambda: True)
    monkeypatch.setattr(failure, "ping_works", lambda: True)


def test_default_mode_is_read_only(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["network_failure.py"])
    healthy_preflight(monkeypatch)
    monkeypatch.setattr(
        failure, "set_interface", lambda state: pytest.fail("Must not change links")
    )
    assert failure.main() == 0


def test_unhealthy_preflight_aborts_without_changes(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["network_failure.py", "--run"])
    healthy_preflight(monkeypatch)
    monkeypatch.setattr(failure, "ospf_full", lambda: False)
    monkeypatch.setattr(
        failure, "set_interface", lambda state: pytest.fail("Must not change links")
    )
    assert failure.main() == 1


def test_failure_is_recovered_even_when_validation_fails(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["network_failure.py", "--run"])
    healthy_preflight(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda prompt: "FAIL")
    events = []
    monkeypatch.setattr(failure, "set_interface", events.append)
    monkeypatch.setattr(failure, "wait_for", lambda *args, **kwargs: False)

    with pytest.raises(RuntimeError, match="adjacency did not go down"):
        failure.main()

    assert events == ["down", "up"]


def test_successful_full_cycle_restores_interface(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["network_failure.py", "--run"])
    state = {"up": True}
    events = []

    monkeypatch.setattr(failure, "interface_is_up", lambda: state["up"])
    monkeypatch.setattr(failure, "ospf_full", lambda: state["up"])
    monkeypatch.setattr(failure, "remote_route_present", lambda: state["up"])
    monkeypatch.setattr(failure, "ping_works", lambda: state["up"])

    def fake_set_interface(value):
        events.append(value)
        state["up"] = value == "up"

    monkeypatch.setattr(failure, "set_interface", fake_set_interface)
    monkeypatch.setattr(failure, "wait_for", lambda predicate, **kwargs: predicate())
    answers = iter(["FAIL", ""])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    assert failure.main() == 0
    assert events == ["down", "up"]
    assert state["up"] is True
