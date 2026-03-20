from __future__ import annotations

from pathlib import Path
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
    assert run_mock.call_count == 5
    assert "Contracts" in captured.out
    assert "Compatibility" in captured.out
    assert "Performance Smoke" in captured.out
    assert "Packaging" in captured.out
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
        SimpleNamespace(returncode=0, stdout="build ok", stderr=""),
        SimpleNamespace(returncode=0, stdout="twine ok", stderr=""),
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
    assert "Packaging" in captured.out


def test_validate_release_packaging_group_requires_build(capsys) -> None:
    from searchat.cli.validate_cmd import run_validate

    def _find_spec(name: str):
        if name == "build":
            return None
        return object()

    with patch("searchat.cli.validate_cmd.importlib.util.find_spec", side_effect=_find_spec):
        result = run_validate(["release", "--group", "packaging"])

    captured = capsys.readouterr()
    assert result == 1
    assert "build" in captured.out.lower()


def test_validate_release_packaging_group_runs_build_and_twine(capsys, tmp_path: Path) -> None:
    from searchat.cli.validate_cmd import run_validate

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "searchat-0.6.2.tar.gz").write_text("sdist", encoding="utf-8")
    (dist_dir / "searchat-0.6.2-py3-none-any.whl").write_text("wheel", encoding="utf-8")

    def _find_spec(_name: str):
        return object()

    def _run(command, capture_output, text, check):  # noqa: ANN001
        if command[2] == "build":
            outdir = Path(command[-1])
            for artifact in dist_dir.iterdir():
                (outdir / artifact.name).write_text(artifact.read_text(encoding="utf-8"), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="build ok", stderr="")
        if command[2] == "twine":
            return SimpleNamespace(returncode=0, stdout="twine ok", stderr="")
        raise AssertionError(f"Unexpected command: {command}")

    with (
        patch("searchat.cli.validate_cmd.importlib.util.find_spec", side_effect=_find_spec),
        patch("searchat.cli.validate_cmd.subprocess.run", side_effect=_run) as run_mock,
    ):
        result = run_validate(["release", "--group", "packaging"])

    captured = capsys.readouterr()
    assert result == 0
    assert run_mock.call_count == 2
    assert "Packaging" in captured.out
    assert "build ok" in captured.out
    assert "twine ok" in captured.out
