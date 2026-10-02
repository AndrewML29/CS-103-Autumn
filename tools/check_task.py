#!/usr/bin/env python3
"""Check explicit task fixtures. No reference task solutions are included."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
KINDS = {'io', 'function', 'model', 'shell', 'manual', 'blocked'}


def load_suite(path):
    data = json.loads(path.read_text())
    if data.get('version') != 1 or data.get('kind') not in KINDS:
        raise ValueError(f'{path}: unsupported suite schema')
    if not isinstance(data.get('contract'), str) or not data['contract'].strip():
        raise ValueError(f'{path}: missing contract')
    cases = data.get('cases')
    if not isinstance(cases, list):
        raise ValueError(f'{path}: cases must be a list')
    if data['kind'] in {'io', 'function', 'model', 'shell'} and not cases:
        raise ValueError(f'{path}: executable suite has no cases')
    if data['kind'] == 'blocked' and not data.get('reason'):
        raise ValueError(f'{path}: blocked suite must explain why')
    if data['kind'] == 'manual' and not data.get('checklist'):
        raise ValueError(f'{path}: missing manual checklist')
    names = set()
    for case in cases:
        if not isinstance(case.get('name'), str) or case['name'] in names:
            raise ValueError(f'{path}: missing/duplicate case name')
        names.add(case['name'])
        if data['kind'] == 'shell':
            if not case.get('script') or not (case.get('checks') or 'expected' in case or case.get('manual')):
                raise ValueError(f'{path}: shell case has no observable check')
        else:
            if not isinstance(case.get('input'), str) or not isinstance(case.get('expected'), str):
                raise ValueError(f'{path}: input/expected must be strings')
        if data['kind'] == 'function':
            if not all(math.isfinite(float(case[k])) for k in ['input', 'expected']):
                raise ValueError(f'{path}: nonfinite function fixture')
        if data.get('tolerance_from_input'):
            if not math.isfinite(float(case['input'])) or float(case['input']) <= 0:
                raise ValueError(f'{path}: invalid tolerance')
    tolerance = data.get('tolerance')
    if tolerance is not None and (not math.isfinite(tolerance) or tolerance <= 0):
        raise ValueError(f'{path}: tolerance must be positive and finite')
    return data


def compare(actual, expected, suite, case):
    mode = suite.get('comparison', 'tokens')
    if mode == 'exact':
        return actual == expected
    if mode == 'tape':
        return actual.strip(' \r\n') == expected.strip(' \r\n')
    a, e = actual.split(), expected.split()
    if case.get('paths'):
        a = [s[2:] if s.startswith('./') else s for s in a]
    if case.get('ignore_dot_entries'):
        a = [s for s in a if s not in {'.', '..'}]
    if case.get('unordered'):
        a, e = sorted(a), sorted(e)
    if len(a) != len(e):
        return False
    tolerance = float(case['input']) if suite.get('tolerance_from_input') else suite.get('tolerance', 0)
    if tolerance:
        try:
            return all(math.isfinite(float(x)) and math.isfinite(float(y)) and
                       abs(float(x) - float(y)) <= tolerance * max(1, abs(float(y)))
                       for x, y in zip(a, e))
        except ValueError:
            return False
    return a == e


def run_process(command, cwd, stdin='', timeout=5, env=None):
    with tempfile.TemporaryFile() as input_file, tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        input_file.write(stdin.encode())
        input_file.seek(0)
        process = subprocess.Popen(command, cwd=cwd, stdin=input_file, stdout=output,
                                   stderr=errors, env=env, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f'timeout after {timeout}s') from exc
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        if output.tell() > 1024 * 1024 or errors.tell() > 1024 * 1024:
            raise RuntimeError('output exceeds 1 MiB')
        output.seek(0)
        errors.seek(0)
        text = output.read().decode('utf-8')
        error_text = errors.read().decode('utf-8', errors='replace')
        if code != 0:
            raise RuntimeError(f'exit {code}: {error_text[:2000]}')
        return text


def safe_path(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'fixture path escapes workspace: {name}')
    return path


def run_shell(directory, suite, case, timeout):
    if case.get('manual'):
        raise RuntimeError('NEEDS SPECIFICATION: ' + case['manual'])
    with tempfile.TemporaryDirectory(prefix='cs103-shell-') as temp:
        root = Path(temp)
        for item in case['setup']:
            path = safe_path(root, item['path'])
            path.parent.mkdir(parents=True, exist_ok=True)
            if item['type'] == 'directory':
                path.mkdir(exist_ok=True)
            else:
                path.write_text(item.get('content', ''))
                if 'size' in item:
                    with path.open('r+b') as stream:
                        stream.truncate(item['size'])
                if 'mode' in item:
                    path.chmod(int(item['mode'], 8))
        cwd = safe_path(root, case['cwd'])
        env = {**os.environ, 'LC_ALL': 'C', 'LANG': 'C'}
        # Mocks are outside the searched workspace so find/ls fixtures remain stable.
        with tempfile.TemporaryDirectory(prefix='cs103-mocks-') as mock_temp:
            if 'mock_ifconfig' in case:
                mock = Path(mock_temp) / 'ifconfig'
                mock.write_text('#!/bin/sh\ncat <<\'CS103_EOF\'\n' + case['mock_ifconfig'] + 'CS103_EOF\n')
                mock.chmod(0o755)
                env['PATH'] = mock_temp + os.pathsep + env['PATH']
            script = safe_path(directory, case['script'])
            output = run_process(['bash', str(script)], cwd, timeout=timeout, env=env)
        if 'expected' in case and not compare(output, case['expected'], suite, case):
            raise AssertionError(f'expected {case["expected"]!r}, got {output!r}')
        for item in case['checks']:
            path = safe_path(root, item['path'])
            if item.get('absent'):
                if path.exists():
                    raise AssertionError(f'{item["path"]}: must not exist')
                continue
            if not path.exists():
                raise AssertionError(f'{item["path"]}: missing')
            if item.get('type') == 'file' and not path.is_file():
                raise AssertionError(f'{item["path"]}: expected a file')
            if item.get('type') == 'directory' and not path.is_dir():
                raise AssertionError(f'{item["path"]}: expected a directory')
            if 'content' in item and path.read_text() != item['content']:
                raise AssertionError(f'{item["path"]}: wrong content')
            if item.get('nonempty') and (not path.is_file() or path.stat().st_size == 0):
                raise AssertionError(f'{item["path"]}: expected a nonempty file')
            if 'mode' in item and path.stat().st_mode & 0o777 != int(item['mode'], 8):
                raise AssertionError(f'{item["path"]}: incorrect permissions')


def parse_markov(program):
    rules = []
    for number, raw in enumerate(program.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(('#', '//')):
            continue
        if '->' not in line:
            raise ValueError(f'line {number}: expected src->dst')
        left, right = line.split('->', 1)
        terminal = right.startswith('.')
        if terminal:
            right = right[1:]
        # Explicit space escape permits rules for fixture word separators.
        rules.append((left.replace('\\s', ' '), right.replace('\\s', ' '), terminal))
    if not rules:
        raise ValueError('no Markov rules: the solution is still a placeholder')
    return rules


def run_markov(rules, word, timeout=5, steps=100000):
    deadline = time.monotonic() + timeout
    for _ in range(steps):
        if time.monotonic() > deadline or len(word) > 100000:
            raise RuntimeError('Markov time/word size limit exceeded')
        for left, right, terminal in rules:
            index = word.find(left)
            if index != -1:
                word = word[:index] + right + word[index + len(left):]
                if terminal:
                    return word
                break
        else:
            return word
    raise RuntimeError('Markov step limit exceeded')


def audit(require_complete=False):
    counts = Counter()
    issues = []
    case_count = 0
    for directory in sorted(ROOT.glob('tasks/*/tasks/*')):
        if not directory.is_dir() or not directory.name.isdigit():
            continue
        path = directory / 'tests.json'
        if not path.exists():
            issues.append(f'MISSING: {path.relative_to(ROOT)}')
            continue
        try:
            data = load_suite(path)
        except (ValueError, KeyError) as exc:
            issues.append(str(exc))
            continue
        counts[data['kind']] += 1
        case_count += len(data['cases'])
        if require_complete:
            if data['kind'] in {'blocked', 'manual'}:
                issues.append(f'{data["kind"].upper()}: {directory.relative_to(ROOT)}')
            for case in data['cases']:
                if case.get('manual'):
                    issues.append(f'NEEDS SPECIFICATION: {directory.relative_to(ROOT)}/{case["script"]}')
    print(f'Suites: {sum(counts.values())}; cases: {case_count}; kinds: {dict(counts)}')
    print('Audit validates fixture structure, not student solutions or semantic correctness.')
    if issues:
        print('\n'.join(issues))
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', type=Path)
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--require-complete', action='store_true')
    parser.add_argument('--timeout', type=float, default=5)
    parser.add_argument('--command', nargs=argparse.REMAINDER,
                        help='Executable adapter: one fixture input on stdin, result on stdout')
    args = parser.parse_args()
    if args.timeout <= 0 or not math.isfinite(args.timeout):
        parser.error('--timeout must be positive and finite')
    if args.audit:
        return audit(args.require_complete)
    if args.directory is None:
        parser.error('provide a task directory or --audit')
    directory = args.directory.resolve()
    suite = load_suite(directory / 'tests.json')
    if suite['kind'] in {'blocked', 'manual'}:
        print('NOT VERIFIED:', suite.get('reason', suite['contract']))
        for item in suite.get('checklist', []):
            print(f'- {item["check"]}')
        return 2
    is_markov = directory.parts[-3] == 'nam' and not args.command
    rules = parse_markov((directory / 'solution.nam').read_text()) if is_markov else None
    if suite['kind'] != 'shell' and not is_markov and not args.command:
        parser.error('provide --command with an executable/emulator adapter, or run the CMake/Catch target')
    failures = 0
    for case in suite['cases']:
        try:
            if suite['kind'] == 'shell':
                run_shell(directory, suite, case, args.timeout)
            else:
                if is_markov:
                    actual = run_markov(rules, case['input'], args.timeout)
                else:
                    with tempfile.TemporaryDirectory(prefix='cs103-io-') as temp:
                        (Path(temp) / 'input.txt').write_text(case['input'])
                        actual = run_process(args.command, temp, case['input'], args.timeout)
                if not compare(actual, case['expected'], suite, case):
                    raise AssertionError(f'input {case["input"]!r}: expected {case["expected"]!r}, got {actual!r}')
            print(f'PASS {case["name"]}')
        except (AssertionError, RuntimeError, OSError, ValueError) as exc:
            failures += 1
            print(f'FAIL {case["name"]}: {exc}')
    print(f'{len(suite["cases"]) - failures}/{len(suite["cases"])} passed')
    return int(failures > 0)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(2)
