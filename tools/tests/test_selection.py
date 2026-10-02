import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_changed_tests import selected_variants


class SelectionTests(unittest.TestCase):
    def test_only_changed_solutions_are_selected(self):
        paths = ['tasks/integers/tasks/1/solution.h', 'tasks/integers/tasks/1/test.cpp',
                 'tasks/integers/tasks/2/tests.json', 'tests/support/task_check.h',
                 'tools/templates/integers.h', 'tasks/matrix/tasks/3/readme.md']
        self.assertEqual(selected_variants(paths), [('integers', '1')])

    def test_shell_markov_and_emulator_submissions_are_not_ignored(self):
        paths = ['tasks/linux/tasks/1/2.bash', 'tasks/nam/tasks/4/solution.nam',
                 'tasks/turing_machine/tasks/5/solution.tu', 'tasks/latex/tasks/1/report.pdf']
        self.assertEqual(selected_variants(paths),
                         [('latex', '1'), ('linux', '1'), ('nam', '4'), ('turing_machine', '5')])

    def test_duplicate_files_select_one_variant(self):
        self.assertEqual(selected_variants(['tasks/linux/tasks/1/1.bash', 'tasks/linux/tasks/1/2.bash']),
                         [('linux', '1')])


if __name__ == '__main__':
    unittest.main()
