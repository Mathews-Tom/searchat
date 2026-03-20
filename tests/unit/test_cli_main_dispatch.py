from __future__ import annotations

import importlib
from unittest.mock import patch


def test_help_text_includes_root_subcommands(capsys, monkeypatch) -> None:
    cli_main = importlib.import_module("searchat.cli.main")

    monkeypatch.setattr(cli_main.sys, "argv", ["searchat", "--help"])

    cli_main.main()

    captured = capsys.readouterr()
    assert "searchat web" in captured.out
    assert "searchat mcp" in captured.out
    assert "searchat setup-index" in captured.out
    assert "searchat ghost" in captured.out


def test_web_subcommand_dispatches_to_api_app(monkeypatch) -> None:
    cli_main = importlib.import_module("searchat.cli.main")

    monkeypatch.setattr(cli_main.sys, "argv", ["searchat", "web", "--help"])

    with patch("searchat.api.app.main") as run_web:
        cli_main.main()

    run_web.assert_called_once_with(argv=["--help"], prog_name="searchat web")


def test_setup_index_subcommand_dispatches_to_setup_index(monkeypatch) -> None:
    cli_main = importlib.import_module("searchat.cli.main")

    monkeypatch.setattr(cli_main.sys, "argv", ["searchat", "setup-index", "--force"])

    with patch("searchat.cli.setup_index.main") as run_setup_index:
        cli_main.main()

    run_setup_index.assert_called_once_with(argv=["--force"], prog_name="searchat setup-index")


def test_mcp_subcommand_dispatches_to_server(monkeypatch) -> None:
    cli_main = importlib.import_module("searchat.cli.main")

    monkeypatch.setattr(cli_main.sys, "argv", ["searchat", "mcp"])

    with patch("searchat.mcp.server.run") as run_mcp:
        cli_main.main()

    run_mcp.assert_called_once_with()


def test_mcp_subcommand_help_does_not_start_server(capsys, monkeypatch) -> None:
    cli_main = importlib.import_module("searchat.cli.main")

    monkeypatch.setattr(cli_main.sys, "argv", ["searchat", "mcp", "--help"])

    with patch("searchat.mcp.server.run") as run_mcp:
        cli_main.main()

    captured = capsys.readouterr()
    assert "Usage: searchat mcp" in captured.out
    run_mcp.assert_not_called()
