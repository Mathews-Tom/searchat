from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


def test_validate_release_help_text(capsys) -> None:
    from searchat.cli.validate_cmd import run_validate

    try:
        run_validate(["release", "--help"])
    except SystemExit as exc:
        assert exc.code == 0

    captured = capsys.readouterr()
    assert "release" in captured.out.lower()
    assert "--group" in captured.out


def test_validate_release_requires_pytest(capsys) -> None:
    from searchat.cli.validate_cmd import run_validate

    with patch("searchat.cli.validate_cmd.importlib.util.find_spec", return_value=None):
        result = run_validate(["release"])

    captured = capsys.readouterr()
    assert result == 1
    assert "pytest is not installed" in captured.out


def test_validate_release_runs_all_groups(capsys) -> None:
    from searchat.cli.validate_cmd import run_validate

    completed = SimpleNamespace(returncode=0, stdout="55 passed", stderr="")

    with (
        patch("searchat.cli.validate_cmd.importlib.util.find_spec", return_value=object()),
        patch("searchat.cli.validate_cmd.subprocess.run", return_value=completed) as run_mock,
    ):
        result = run_validate(["release"])

    captured = capsys.readouterr()
    assert result == 0
    assert run_mock.call_count == 3
    assert "Contracts" in captured.out
    assert "Compatibility" in captured.out
    assert "Performance Smoke" in captured.out
    assert "55 passed" in captured.out


def test_validate_release_can_scope_to_group(capsys) -> None:
    from searchat.cli.validate_cmd import run_validate

    completed = SimpleNamespace(returncode=0, stdout="group passed", stderr="")

    with (
        patch("searchat.cli.validate_cmd.importlib.util.find_spec", return_value=object()),
        patch("searchat.cli.validate_cmd.subprocess.run", return_value=completed) as run_mock,
    ):
        result = run_validate(["release", "--group", "contracts"])

    captured = capsys.readouterr()
    assert result == 0
    assert run_mock.call_count == 1
    command = run_mock.call_args.args[0]
    assert "tests/ui" in command
    assert "tests/unit/perf/test_performance_gates.py" not in command
    assert "Contracts" in captured.out
    assert "Performance Smoke" not in captured.out


def test_validate_release_returns_nonzero_when_any_group_fails(capsys) -> None:
    from searchat.cli.validate_cmd import run_validate

    outcomes = [
        SimpleNamespace(returncode=0, stdout="contracts passed", stderr=""),
        SimpleNamespace(returncode=1, stdout="compat failed", stderr="failure details"),
        SimpleNamespace(returncode=0, stdout="perf passed", stderr=""),
    ]

    with (
        patch("searchat.cli.validate_cmd.importlib.util.find_spec", return_value=object()),
        patch("searchat.cli.validate_cmd.subprocess.run", side_effect=outcomes),
    ):
        result = run_validate(["release"])

    captured = capsys.readouterr()
    assert result == 1
    assert "FAIL" in captured.out
    assert "failure details" in captured.out
