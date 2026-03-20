"""CLI command: searchat health — check running server health."""
from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error


def run_health(argv: list[str]) -> int:
    url = "http://localhost:8000"
    raw_json = False

    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--url" and args:
            url = args.pop(0)
        elif arg == "--json":
            raw_json = True
        elif arg in ("-h", "--help"):
            print("Usage: searchat health [--url URL] [--json]")
            print()
            print("Options:")
            print("  --url URL   Server URL (default: http://localhost:8000)")
            print("  --json      Output raw JSON instead of table")
            return 0

    endpoint = f"{url.rstrip('/')}/api/health"

    try:
        req = urllib.request.Request(endpoint)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        data = json.loads(exc.read().decode())
    except (urllib.error.URLError, OSError) as exc:
        print(f"Error: cannot reach server at {endpoint}: {exc}", file=sys.stderr)
        return 1

    if raw_json:
        print(json.dumps(data, indent=2))
        return 0 if data.get("healthy") else 1

    from rich.console import Console
    from rich.table import Table

    console = Console()
    healthy = data.get("healthy", False)
    status_text = "[bold green]HEALTHY[/]" if healthy else "[bold red]UNHEALTHY[/]"
    console.print(f"\nServer health: {status_text}")

    checks = data.get("checks", {})
    if checks:
        table = Table(show_header=True)
        table.add_column("Check", style="bold")
        table.add_column("Status")
        table.add_column("Latency")
        table.add_column("Details")

        for name, info in checks.items():
            status = info.get("status", "unknown")
            if status == "ok":
                status_str = "[green]ok[/]"
            elif status == "warning":
                status_str = "[yellow]warning[/]"
            else:
                status_str = "[red]error[/]"

            latency = f"{info.get('latency_ms', 0):.1f}ms"
            details_parts = []
            for k, v in info.items():
                if k not in ("status", "latency_ms"):
                    details_parts.append(f"{k}={v}")
            details = ", ".join(details_parts) if details_parts else ""

            table.add_row(name, status_str, latency, details)

        console.print(table)

    return 0 if healthy else 1
