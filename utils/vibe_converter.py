#!/usr/bin/env python
"""
Convert Mistral Vibe plaintext history to searchable session files.

This utility converts old vibehistory plaintext files (containing just prompts)
into proper Vibe session JSON files that can be indexed by searchat.

Usage:
    python utils/convert_vibe_history.py [--history-file PATH] [--output-dir PATH]

The script will:
1. Read prompts from vibehistory file (one per line)
2. Create individual session JSON files for each prompt
3. Save them to the Vibe session directory for indexing
"""

import json
import uuid
import argparse
from pathlib import Path
from datetime import datetime


def convert_vibehistory(
    history_path: Path = None,
    output_dir: Path = None
) -> int:
    """
    Convert vibehistory plaintext to session JSON files.

    Args:
        history_path: Path to vibehistory file (default: ~/.vibe/vibehistory)
        output_dir: Output directory for sessions (default: ~/.vibe/logs/session)

    Returns:
        Number of sessions created
    """
    # Set defaults
    if history_path is None:
        history_path = Path.home() / ".vibe" / "vibehistory"

    if output_dir is None:
        output_dir = Path.home() / ".vibe" / "logs" / "session"

    # Validate input
    if not history_path.exists():
        raise FileNotFoundError(f"History file not found: {history_path}")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read history lines
    print(f"Reading history from: {history_path}")
    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        raise RuntimeError(f"Error reading history file: {e}")

    # Clean lines (remove quotes and newlines)
    prompts = [line.strip().strip('"') for line in lines if line.strip()]

    print(f"Found {len(prompts)} history items")

    if not prompts:
        print("No prompts found in history file")
        return 0

    # Confirm with user
    print(f"Output directory: {output_dir}")
    confirm = input(f"\nCreate {len(prompts)} session files? (yes/no): ")
    if confirm.lower() not in ('yes', 'y'):
        print("Cancelled")
        return 0

    print(f"\nCreating session files...")

    # Create session file for each prompt
    created_count = 0
    timestamp = datetime.now().isoformat()

    for i, prompt in enumerate(prompts):
        session_id = f"history_{i:04d}_{uuid.uuid4().hex[:8]}"

        # Create session structure
        messages = [
            {
                "role": "user",
                "content": prompt,
                "timestamp": timestamp
            },
            {
                "role": "assistant",
                "content": "(Archived history item - no response recorded)",
                "timestamp": timestamp
            }
        ]

        session_data = {
            "metadata": {
                "session_id": session_id,
                "start_time": timestamp,
                "end_time": timestamp,
                "environment": {
                    "working_directory": str(Path.home())
                }
            },
            "messages": messages
        }

        # Write to file
        output_path = output_dir / f"session_history_{i:04d}.json"

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            created_count += 1

            if (i + 1) % 100 == 0:
                print(f"  Created {i + 1}/{len(prompts)} sessions...")

        except Exception as e:
            print(f"  Failed to write session {i}: {e}")
            continue

    print(f"\n✓ Successfully created {created_count}/{len(prompts)} session files")
    print(f"\nNext steps:")
    print(f"1. Run: python scripts/setup-index")
    print(f"2. The new sessions will be indexed and searchable")

    return created_count


def main():
    parser = argparse.ArgumentParser(
        description="Convert Vibe plaintext history to session JSON files"
    )
    parser.add_argument(
        '--history-file',
        type=Path,
        help="Path to vibehistory file (default: ~/.vibe/vibehistory)"
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        help="Output directory for sessions (default: ~/.vibe/logs/session)"
    )

    args = parser.parse_args()

    try:
        count = convert_vibehistory(
            history_path=args.history_file,
            output_dir=args.output_dir
        )

        if count > 0:
            print(f"\n✓ Conversion complete!")
        else:
            print(f"\n⚠ No sessions created")

    except FileNotFoundError as e:
        print(f"\nError: {e}")
        exit(1)
    except RuntimeError as e:
        print(f"\nError: {e}")
        exit(1)
    except KeyboardInterrupt:
        print(f"\n\nCancelled by user")
        exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
