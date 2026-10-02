#!/usr/bin/env python3
"""CI selection: check variants whose student solution files changed."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

from render_tests import GROUPS, ROOT


def selected_variants(paths):
    selected = set()
    for name in paths:
        parts = Path(name).parts
        if len(parts) < 5 or parts[0] != 'tasks' or parts[2] != 'tasks' or not parts[3].isdigit():
            continue
        # Fixtures and infrastructure have separate checks. Unsovled neighboring
        # tasks must not make a student's otherwise valid submission fail.
        if parts[4] in {'tests.json', 'test.cpp', 'CMakeLists.txt', 'readme.md'}:
            continue
        if Path(name).suffix in {'.h', '.c', '.cpp', '.hpp', '.bash', '.nam', '.tu', '.td', '.tex', '.pdf'}:
            selected.add((parts[1], parts[3]))
    return sorted(selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--lint', action='store_true')
    parser.add_argument('--build', type=Path, default=Path('build_debug'))
    args = parser.parse_args()
    changed = subprocess.check_output(['git', 'diff', '--name-only', '-z', args.base, 'HEAD'], cwd=ROOT).decode().split('\0')
    variants = selected_variants(filter(None, changed))
    if args.lint:
        files = [name for name in changed if (ROOT / name).is_file()
                 and selected_variants([name]) and Path(name).suffix in {'.h', '.c', '.cpp', '.hpp'}]
        if files:
            subprocess.run([sys.executable, str(ROOT / 'tools/run-clang-format.py'), *files], check=True)
            for name in files:
                subprocess.run(['clang-tidy', '-p', str(args.build), name], check=True)
    if not variants:
        print('No student solution changes; infrastructure/fixture checks run separately.')
        return 0
    for group, number in variants:
        path = ROOT / 'tasks' / group / 'tasks' / number
        if group in GROUPS:
            target = group + number
            subprocess.run(['cmake', '--build', str(args.build), '--target', target, '--parallel', '2'], check=True)
            subprocess.run(['ctest', '--test-dir', str(args.build), '--output-on-failure', '-R', '^' + re.escape(target) + '$'], check=True)
        elif group in {'linux', 'nam'}:
            subprocess.run([sys.executable, str(ROOT / 'tools/check_task.py'), str(path)], check=True)
        else:
            raise SystemExit(f'{group}/{number}: manual review or emulator adapter required; see docs/testing.md. Not automatically verified.')
    return 0


if __name__ == '__main__':
    main()
