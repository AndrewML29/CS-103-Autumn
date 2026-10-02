import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

TOOLS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_task', TOOLS / 'check_task.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class ComparisonTests(unittest.TestCase):
    def test_empty_placeholder_fails_nonempty_answer(self):
        self.assertFalse(check.compare('', '0', {}, {}))

    def test_extra_output_is_rejected(self):
        self.assertFalse(check.compare('answer: 1', '1', {}, {}))

    def test_whitespace_is_not_significant_by_default(self):
        self.assertTrue(check.compare('1\n  2\t3', '1 2 3', {}, {}))

    def test_exact_text_preserves_newline_semantics(self):
        self.assertFalse(check.compare('a\nb', 'a b', {'comparison': 'exact'}, {}))

    def test_tape_preserves_inner_spaces(self):
        self.assertFalse(check.compare('a  b', 'a b', {'comparison': 'tape'}, {}))
        self.assertTrue(check.compare(' a b \n', 'a b', {'comparison': 'tape'}, {}))

    def test_floating_point_tolerance_and_nonfinite(self):
        suite = {'tolerance': 1e-6}
        self.assertTrue(check.compare('1.0000001', '1', suite, {}))
        for value in ['nan', 'inf', '-inf', 'oops', '1.001', '']:
            self.assertFalse(check.compare(value, '1', suite, {}))

    def test_input_tolerance(self):
        suite = {'tolerance_from_input': True}
        self.assertTrue(check.compare('1.001', '1', suite, {'input': '0.01'}))
        self.assertFalse(check.compare('1.001', '1', suite, {'input': '0.00001'}))

    def test_ls_allows_optional_dot_entries(self):
        case = {'ignore_dot_entries': True, 'unordered': True}
        self.assertTrue(check.compare('. .. .hidden a', '.hidden a', {}, case))
        self.assertTrue(check.compare('.hidden a', '.hidden a', {}, case))

    def test_unordered_paths_retain_multiplicity(self):
        case = {'unordered': True, 'paths': True}
        self.assertTrue(check.compare('./b ./a', 'a b', {}, case))
        self.assertFalse(check.compare('./a ./a ./b', 'a b', {}, case))


class RunnerTests(unittest.TestCase):
    def test_stdin_stdout(self):
        with tempfile.TemporaryDirectory() as temp:
            result = check.run_process([sys.executable, '-c', 'import sys;print(sys.stdin.read().upper())'], temp, 'hello')
            self.assertEqual(result, 'HELLO\n')

    def test_failure_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, 'exit 3'):
                check.run_process([sys.executable, '-c', 'raise SystemExit(3)'], temp)

    def test_timeout(self):
        start = time.monotonic()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, 'timeout'):
                check.run_process([sys.executable, '-c', 'import time;time.sleep(30)'], temp, timeout=0.2)
        self.assertLess(time.monotonic() - start, 5)

    def test_empty_shell_solution_does_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / '1.bash').write_text('# no solution\n')
            case = {'name': 'mkdir', 'script': '1.bash', 'setup': [], 'cwd': '.',
                    'checks': [{'path': 'output_dir', 'type': 'directory'}]}
            with self.assertRaisesRegex(AssertionError, 'missing'):
                check.run_shell(directory, {}, case, 2)

    def test_shell_state_is_checked_and_isolated(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / '1.bash').write_text('mkdir output_dir\n')
            case = {'name': 'mkdir', 'script': '1.bash', 'setup': [], 'cwd': '.',
                    'checks': [{'path': 'output_dir', 'type': 'directory'}]}
            check.run_shell(directory, {}, case, 2)
            check.run_shell(directory, {}, case, 2)
            self.assertFalse((directory / 'output_dir').exists())

    def test_missing_specification_is_not_a_pass(self):
        with self.assertRaisesRegex(RuntimeError, 'NEEDS SPECIFICATION'):
            check.run_shell(Path('.'), {}, {'manual': 'unknown destination'}, 2)

    def test_workspace_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                check.safe_path(Path(temp), '../outside')


class MarkovTests(unittest.TestCase):
    def test_placeholder_is_rejected(self):
        with self.assertRaises(ValueError):
            check.parse_markov('# implement here\n')

    def test_first_rule_and_leftmost_occurrence(self):
        rules = check.parse_markov('a->.x\nb->.y')
        self.assertEqual(check.run_markov(rules, 'baa'), 'bxa')

    def test_rules_restart_from_top(self):
        rules = check.parse_markov('x->.done\na->x')
        self.assertEqual(check.run_markov(rules, 'a'), 'done')

    def test_terminal_empty_and_empty_lhs(self):
        self.assertEqual(check.run_markov(check.parse_markov('a->.'), 'a'), '')
        self.assertEqual(check.run_markov(check.parse_markov('->.x'), ''), 'x')

    def test_halt_without_matching_rule(self):
        self.assertEqual(check.run_markov(check.parse_markov('a->b'), 'a'), 'b')

    def test_nontermination_limit(self):
        with self.assertRaisesRegex(RuntimeError, 'step limit'):
            check.run_markov(check.parse_markov('a->a'), 'a', steps=10)


class FixtureTests(unittest.TestCase):
    def test_every_variant_has_valid_suite(self):
        directories = [p for p in check.ROOT.glob('tasks/*/tasks/*') if p.is_dir() and p.name.isdigit()]
        self.assertEqual(len(directories), 403)
        for directory in directories:
            with self.subTest(directory=directory):
                suite = check.load_suite(directory / 'tests.json')
                if suite['kind'] in {'io', 'model', 'function'}:
                    self.assertGreaterEqual(len(suite['cases']), 3)
                    self.assertTrue(any(c['expected'].strip() for c in suite['cases']))
                if suite['kind'] == 'shell':
                    self.assertEqual({c['script'] for c in suite['cases']}, {f'{i}.bash' for i in range(1, 11)})

    def test_empty_executable_suite_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'tests.json'
            path.write_text(json.dumps({'version': 1, 'kind': 'io', 'contract': 'contract', 'cases': []}))
            with self.assertRaisesRegex(ValueError, 'no cases'):
                check.load_suite(path)


if __name__ == '__main__':
    unittest.main()
