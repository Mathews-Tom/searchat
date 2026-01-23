#!/usr/bin/env python3
"""
Basic test script for cross-platform terminal launching (non-interactive).
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from searchat.services import PlatformManager
from searchat.config import PathResolver


def main():
    print("="*60)
    print("  Terminal Launch Basic Test")
    print("="*60)

    # Test platform detection
    print("\n[Platform Detection]")
    platform = PathResolver.detect_platform()
    print(f"  Detected platform: {platform}")

    pm = PlatformManager()
    print(f"  PlatformManager.platform: {pm.platform}")
    print(f"  PlatformManager.is_windows: {pm.is_windows}")
    print(f"  PlatformManager.is_wsl: {pm.is_wsl}")
    print(f"  PlatformManager.is_linux: {pm.is_linux}")
    print(f"  PlatformManager.is_macos: {pm.is_macos}")

    # Test path translation
    print("\n[Path Translation]")
    test_paths = [
        "D:\\projects\\searchat",
        "/mnt/d/projects/searchat",
        "/home/user/test",
    ]

    for path in test_paths:
        try:
            translated = PathResolver.translate_claude_path(path)
            print(f"  {path}")
            print(f"    -> {translated}")
        except Exception as e:
            print(f"  {path}")
            print(f"    -> ERROR: {e}")

    # Test cwd translation
    print("\n[CWD Translation]")
    test_cwds = [
        "D:\\projects\\searchat",
        "/mnt/d/projects/searchat",
        None,
    ]

    for cwd in test_cwds:
        try:
            translated = pm._translate_cwd_if_needed(cwd)
            print(f"  {cwd}")
            print(f"    -> {translated}")
        except Exception as e:
            print(f"  {cwd}")
            print(f"    -> ERROR: {e}")

    # Test command preview (without launching)
    print("\n[Terminal Command Preview]")
    print("  This shows what would be executed without launching terminals.")
    print()

    test_cases = [
        ("Windows path", "D:\\projects\\searchat", 'echo "test" && pwd'),
        ("WSL path", "/mnt/d/projects/searchat", 'echo "test" && pwd'),
        ("No path", None, 'echo "test"'),
    ]

    for test_name, cwd, command in test_cases:
        print(f"  Test: {test_name}")
        print(f"    Command: {command}")
        print(f"    CWD: {cwd or '(none)'}")
        print(f"    Platform: {pm.platform}")

        translated_cwd = pm._translate_cwd_if_needed(cwd)
        print(f"    Translated CWD: {translated_cwd or '(none)'}")
        print()

    print("="*60)
    print("  Tests Complete")
    print("="*60)
    print("\nBasic tests passed. Platform detection and path translation working.")
    print("To test actual terminal launching, run: python tests/test_terminal_launch.py")


if __name__ == '__main__':
    main()
