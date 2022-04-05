from __future__ import annotations

import curses
import json
import os
import stat
import subprocess
import types
from typing import Any
from unittest import mock

import pytest

from babi import screen
from testing.runner import and_exit


def test_anonymous_file(run):
    with run() as h, and_exit(h):
        h.press('^T')
        h.await_text('file has not been saved yet!')


def test_not_saved_file_cancelled(run, tmpdir):
    f = tmpdir.join('t.py')
    f.write('print("hello hello world")')

    with run(str(f)) as h, and_exit(h):
        h.press('End')
        h.press('#')

        h.press('^T')
        h.await_text('file must be saved before linting')

        h.press('n')
        h.await_text('cancelled')


def test_not_saved_file_cancels_at_save(run, tmpdir):
    tmpdir.join('a').ensure()
    f = tmpdir.join('a/b')

    with run(str(f)) as h, and_exit(h):
        h.press('c')

        h.press('^T')
        h.await_text('file must be saved before linting')

        h.press('y')
        h.await_text('cannot save file')


@pytest.fixture
def unlintable_file(tmpdir):
    # not in a git repo (no pre-commit), not python (no flake8)
    f = tmpdir.join('f')
    f.ensure()
    yield f


def test_tries_to_lint_modified_file(run, unlintable_file):
    with run(str(unlintable_file)) as h, and_exit(h):
        h.press('c')

        h.press('^T')
        h.await_text('file must be saved before linting')

        h.press('y')

        h.await_text('no linters available!')

    assert unlintable_file.read() == 'c\n'


def test_no_applicable_linters(run, unlintable_file):
    with run(str(unlintable_file)) as h, and_exit(h):
        h.press('^T')

        h.await_text('no linters available!')


def test_executable_does_not_exist(run_only_fake, tmpdir):
    f = tmpdir.join('t.py')
    f.ensure()

    class NoCommandLinter:
        def command(self, filename, scope):
            return ('this-command-does-not-exist',)

    with mock.patch.object(screen, 'LINTER_TYPES', (NoCommandLinter,)):
        with run_only_fake(str(f)) as h, and_exit(h):
            h.press('^T')

            h.await_text('no linters available')


def test_cancelled_execution(run_only_fake, tmpdir):
    f = tmpdir.join('t.py')
    f.ensure()

    class SleepyLinter:
        def command(self, filename, scope):
            return ('sleep', 'infinity')

    # simulate ^C while the linter is running
    popen_patch: dict[str, Any]
    popen_patch = {'return_value.communicate.side_effect': KeyboardInterrupt}
    with mock.patch.object(screen, 'LINTER_TYPES', (SleepyLinter,)):
        with mock.patch.object(subprocess, 'Popen', **popen_patch):
            with run_only_fake(str(f)) as h, and_exit(h):
                h.press('^T')

                h.await_text('cancelled')


STUBBED_FLAKE8 = '''\
#!/usr/bin/env python3
import os.path
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, 'output')) as f:
    print(f.read().format(filename=sys.argv[1]), end='')

with open(os.path.join(HERE, 'new-contents')) as f:
    new_contents = f.read()

if new_contents:
    with open(sys.argv[1], 'w') as f:
        f.write(new_contents)
'''


@pytest.fixture
def stubbed_flake8(tmpdir, xdg_data_home):
    xdg_data_home.join('babi/grammar_v1/source.python.json').ensure().write(
        '{"scopeName": "source.python", "patterns": []}',
    )

    bin_dir = tmpdir.join('flake8-bin').ensure_dir()
    output = tmpdir.join('flake8-bin/output').ensure()
    new_contents = tmpdir.join('flake8-bin/new-contents').ensure()
    flake8_bin = tmpdir.join('flake8-bin/flake8').ensure()
    flake8_bin.write(STUBBED_FLAKE8)
    flake8_bin.chmod(stat.S_IRWXU)

    os_path = f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'
    with mock.patch.dict(os.environ, {'PATH': os_path}):
        yield types.SimpleNamespace(output=output, new_contents=new_contents)


def test_lint_output_successful(run, tmpdir, stubbed_flake8):
    stubbed_flake8.output.write('')

    f = tmpdir.join('t.py').ensure()

    with run(str(f)) as h, and_exit(h):
        h.press('^T')
        h.await_text('linted!')


def test_lint_output_error(run, tmpdir, stubbed_flake8):
    stubbed_flake8.output.write('{filename}:1:1: F401 error')

    f = tmpdir.join('t.py')
    f.write('import os\n')

    with run(str(f)) as h, and_exit(h):
        h.press('^T')

        h.await_text('1 error(s)')
        h.await_text('1:1: [flake8] F401 error')


def test_lint_formats_code(run, tmpdir, stubbed_flake8):
    stubbed_flake8.new_contents.write('print("hello hello world")\n')

    f = tmpdir.join('t.py')
    f.write('print( "hello hello world")')

    with run(str(f)) as h, and_exit(h):
        h.await_text('print( "hello hello world")')
        h.press('^T')

        h.await_text('linted! (and formatted)')
        h.await_text('print("hello hello world")')


def test_focus_lint_panel_no_errors_present(run):
    with run() as h, and_exit(h):
        # should not crash
        h.press('M-t')


def test_next_previous_lint_error_no_errors(run):
    with run() as h, and_exit(h):
        # should not crash
        h.press('^S-Up')
        h.press('^S-Down')
        h.await_cursor_position(x=0, y=1)


def test_unknown_character_in_lint_panel_ignored(run, tmpdir, stubbed_flake8):
    stubbed_flake8.output.write('{filename}:1:1: F401 error')

    f = tmpdir.join('t.py')
    f.write('import os\n')

    with run(str(f)) as h, and_exit(h):
        h.press('^T')

        h.press('M-t')

        # should not crash
        h.press('a')

        h.press('M-t')


def test_exit_out_of_lint_panel(run, tmpdir, stubbed_flake8):
    stubbed_flake8.output.write('{filename}:1:1: F401 error')

    f = tmpdir.join('t.py')
    f.write('import sys\n')

    with run(str(f)) as h, and_exit(h):
        h.press('^T')

        h.await_text('1 error(s)')
        h.await_text('1:1: [flake8] F401 error')

        h.press('M-t')
        h.press('^C')

        h.await_text_missing('1:1: [flake8] F401 error')


def test_relint_in_panel(run, tmpdir, stubbed_flake8):
    stubbed_flake8.output.write('{filename}:1:1: F401 error')

    def update_lint_output():
        stubbed_flake8.output.write(
            '{filename}:1:1: F401 error\n'
            '{filename}:2:1: F402 error\n',
        )

    f = tmpdir.join('t.py')
    f.write('import os\nimport sys\n')

    with run(str(f)) as h, and_exit(h):
        h.press('^T')

        h.await_text('1 error(s)')
        h.await_text('1:1: [flake8] F401 error')

        h.press('M-t')

        h.run(update_lint_output)

        h.press('^T')

        h.await_text('2 error(s)')
        h.await_text('1:1: [flake8] F401 error')
        h.await_text('2:1: [flake8] F402 error')

        h.press('M-t')


def test_relint_reduces_number_of_errors(run, tmpdir, stubbed_flake8):
    stubbed_flake8.output.write(
        '{filename}:1:1: F401 error\n'
        '{filename}:1:1: F401 error\n'
        '{filename}:2:1: F401 error\n',
    )

    f = tmpdir.join('t.py')
    f.write('import os\nimport sys\n')

    with run(str(f)) as h, and_exit(h):
        h.press('^T')

        h.await_text('3 error(s)')
        h.await_text('1:1: [flake8] F401 error')

        h.press('M-t')

        h.press('Down')
        h.press('Down')
        h.await_cursor_position(x=0, y=2)

        # reduce the number of errors which used to force y out of bounds
        h.run(lambda: stubbed_flake8.output.write('{filename}:1:1: F401'))

        h.press('^T')

        # clamped in bounds it should move to the first error's position
        h.await_cursor_position(x=0, y=1)

        h.press('M-t')


def test_relint_eliminates_errors(run, tmpdir, stubbed_flake8):
    stubbed_flake8.output.write('{filename}1:1: F401 error\n')

    f = tmpdir.join('t.py')
    f.write('import os\n')

    with run(str(f)) as h, and_exit(h):
        h.press('^T')

        h.await_text('1 error(s)')

        h.press('M-t')

        # eliminate errors
        h.run(lambda: stubbed_flake8.output.write(''))

        h.press('^T')

        h.await_text('linted!')


def test_lint_panel_draw_bug_after_cancel(run, tmpdir, stubbed_flake8):
    stubbed_flake8.output.write(
        '{filename}:1:1: F401 error\n'
        '{filename}:2:1: F401 error\n'
        '{filename}:3:1: F401 error\n'
        '{filename}:4:1: F401 error\n',
    )

    f = tmpdir.join('t.py')
    f.write('1\n2\n3\n4\n5\n6\n7\n8\n9\n')

    with run(str(f), height=10) as h, and_exit(h):
        h.await_text('\n8\n')

        h.press('^T')

        h.await_text_missing('\n8\n')
        h.await_text('4 error(s)')
        h.await_text('1:1: [flake8] F401 error')

        h.press('M-t')

        h.press('Down')
        h.press('Down')
        h.press('Down')
        h.await_cursor_position(x=0, y=4)

        h.press('^C')

        h.await_text('\n8\n')


def test_lint_errors_out_of_bounds(run, tmpdir, stubbed_flake8):
    stubbed_flake8.output.write(
        # 0-based
        '{filename}:0:0: F403 error\n'
        # out of bounds in X
        '{filename}:2:20: F401 error\n'
        # out of bounds in Y
        '{filename}:10:1: F402 error\n',
    )

    f = tmpdir.join('t.py')
    f.write('import os\nimport sys\n')

    with run(str(f)) as h, and_exit(h):
        h.press('^T')

        h.await_text('3 error(s)')

        h.press('M-t')

        # 0:0 is out of bounds, clamp to beginning
        h.await_cursor_position(x=0, y=1)

        h.press('Down')

        # should clamp x to the closest value
        h.await_cursor_position(x=10, y=2)

        h.press('Down')

        # should clamp y to the closest value
        h.await_cursor_position(x=0, y=3)

        h.press('M-t')


THEME = json.dumps({
    'colors': {'background': '#00d700', 'foreground': '#303030'},
    'tokenColors': [
        {'scope': 'constant.numeric', 'settings': {'foreground': '#600000'}},
        {'scope': 'strong', 'settings': {'fontStyle': 'bold'}},
        {'scope': 'support.type', 'settings': {'foreground': '#006000'}},
        {'scope': 'invalid', 'settings': {'foreground': '#f00'}},
    ],
})
C_NORM = [(236, 40, 0)]
C_REV = [(236, 40, curses.A_REVERSE)]
C_DIM = [(236, 40, curses.A_DIM)]
C_RED = [(-1, 1, 0)]
C_NUM = [(52, 40, 0)]
C_NAME = [(22, 40, curses.A_BOLD)]
C_INVALID = [(196, 40, 0)]
C_SELECTED = [(236, 40, curses.A_REVERSE | curses.A_DIM)]


@pytest.fixture
def themed(xdg_config_home):
    xdg_config_home.join('babi/theme.json').ensure().write(THEME)


def test_lint_panel_focus_unfocus(run, tmpdir, stubbed_flake8, themed):
    stubbed_flake8.output.write(
        '{filename}:2:1: F401 error\n'
        '{filename}:4:3: E123 error 2\n'
        '{filename}:5:1: E121 error 3\n'
        '{filename}:5:3: E123 error 4\n',
    )

    f = tmpdir.join('t.py')
    f.write('import os\nimport sys\n\na =1\nb =1')

    size = {'width': 40, 'height': 10}
    with run(str(f), term='screen-256color', **size) as h, and_exit(h):
        h.await_text('import sys')
        h.press('^T')

        h.await_text('4 error(s)')

        error_line = (
            C_NUM + C_NORM + C_NUM + C_NORM * 2 + C_NAME * 8 + C_NORM +
            C_INVALID * 4 + 22 * C_NORM
        )

        for i, attr in enumerate([
                C_REV * 40,                              # header
                C_NORM * 40,                             # import os
                C_RED + C_NORM * 39,                     # import sys
                C_NORM * 40,                             #
                C_RED + C_NORM * 39,                     # a =1
                C_RED + C_NORM * 39,                   # b =1
                C_NORM * 14 + C_REV * 12 + C_NORM * 14,  # 2 error(s)
                error_line,                        # 2:1: [flake8] F401 error
                error_line,                        # 4:3: [flake8] E123 error 2
                error_line,                        # 5:1: [flake8] E121 error 3
        ]):
            h.assert_screen_attr_equal(i, attr)

        h.press('M-t')

        h.await_cursor_position(x=0, y=2)
        # should highlight the currently selected error
        h.assert_screen_attr_equal(7, C_SELECTED * 40)
        h.assert_screen_attr_equal(8, error_line)
        h.assert_screen_attr_equal(9, error_line)

        h.press('Down')
        h.await_cursor_position(x=2, y=4)
        # should highlight the second error instead
        h.assert_screen_attr_equal(7, error_line)
        h.assert_screen_attr_equal(8, C_SELECTED * 40)
        h.assert_screen_attr_equal(9, error_line)

        # scroll to the 4th error
        h.press('Down')
        h.press('Down')
        h.await_cursor_position(x=2, y=5)
        # scrolling of the error panel should have left a blank line
        h.assert_screen_attr_equal(7, error_line)
        h.assert_screen_attr_equal(8, C_SELECTED * 40)
        h.assert_screen_attr_equal(9, C_NORM * 40)

        # pressing up twice should scroll panel
        h.press('Up')
        h.press('Up')
        h.await_cursor_position(x=2, y=4)
        h.assert_screen_attr_equal(7, error_line)
        h.assert_screen_attr_equal(8, C_SELECTED * 40)
        h.assert_screen_attr_equal(9, error_line)

        # exit the error panel
        h.press('M-t')


def test_lint_panel_disabled_error(run, tmpdir, stubbed_flake8, themed):
    stubbed_flake8.output.write(
        '{filename}:2:1: F401 error\n'
        '{filename}:4:3: E123 error 2\n',
    )

    f = tmpdir.join('t.py')
    f.write('import os\nimport sys\n\na =1\n')

    size = {'width': 40, 'height': 10}
    with run(str(f), term='screen-256color', **size) as h, and_exit(h):
        h.await_text('import sys')
        h.press('^T')

        h.await_text('2 error(s)')

        error_line = (
            C_NUM + C_NORM + C_NUM + C_NORM * 2 + C_NAME * 8 + C_NORM +
            C_INVALID * 4 + 22 * C_NORM
        )

        # should be highlighting the error
        h.assert_screen_attr_equal(2, C_RED + C_NORM * 39)
        h.assert_screen_attr_equal(8, error_line)

        h.press('Down')
        h.press('End')
        h.press('#')

        # should have "disabled" the error since we edited the line
        h.await_text('??:??: [flake8] F401 error')

        # does not have the red highlight any more
        h.assert_screen_attr_equal(2, C_NORM * 40)
        h.assert_screen_attr_equal(8, C_DIM * 40)

        h.press('M-t')

        h.press('Down')
        h.await_cursor_position(x=2, y=4)
        h.press('Up')
        # should not have moved the cursor due to disabled error
        h.await_cursor_position(x=2, y=4)

        h.press('M-t')


def test_lint_panel_resized(run, tmpdir, stubbed_flake8, themed):
    stubbed_flake8.output.write(
        '{filename}:2:1: F401 error\n'
        '{filename}:4:3: E123 error 2\n',
    )

    f = tmpdir.join('t.py')
    f.write('import os\nimport sys\n\na =1\n')

    size = {'width': 40, 'height': 10}
    with run(str(f), term='screen-256color', **size) as h, and_exit(h):
        h.await_text('import sys')
        h.press('^T')

        h.await_text('2 error(s)')

        h.press('M-t')

        h.await_cursor_position(x=0, y=2)

        error_line = (
            C_NUM + C_NORM + C_NUM + C_NORM * 2 + C_NAME * 8 + C_NORM +
            C_INVALID * 4 + 22 * C_NORM
        )

        h.assert_screen_attr_equal(8, C_SELECTED * 40)
        h.assert_screen_attr_equal(9, error_line)

        with h.resize(width=8, height=10):
            h.await_text_missing('F401')

            edge_line = (
                C_NUM + C_NORM + C_NUM + C_NORM * 2 + C_NAME * 2 + C_NORM
            )
            # should not highlight the edge
            h.assert_screen_attr_equal(8, C_SELECTED * 8)
            h.assert_screen_attr_equal(9, edge_line)

        h.await_text('F401')

        h.press('M-t')


def test_jump_to_next_lint_error(run, tmpdir, stubbed_flake8, themed):
    stubbed_flake8.output.write(
        '{filename}:2:1: F401 error\n'
        '{filename}:4:3: E123 error 2\n',
    )

    f = tmpdir.join('t.py')
    f.write('import os\nimport sys\n\na =1\n')

    size = {'width': 40, 'height': 10}
    with run(str(f), term='screen-256color', **size) as h, and_exit(h):
        h.await_text('import sys')
        h.press('^T')

        h.await_text('2 error(s)')

        h.await_cursor_position(x=0, y=1)

        h.press('^S-Down')

        h.await_cursor_position(x=0, y=2)

        error_line = (
            C_NUM + C_NORM + C_NUM + C_NORM * 2 + C_NAME * 8 + C_NORM +
            C_INVALID * 4 + 22 * C_NORM
        )

        h.assert_screen_attr_equal(8, C_SELECTED * 40)
        h.assert_screen_attr_equal(9, error_line)

        h.press('^S-Down')

        h.await_cursor_position(x=2, y=4)

        h.assert_screen_attr_equal(8, error_line)
        h.assert_screen_attr_equal(9, C_SELECTED * 40)

        # should not go past end, but should still be highlighted
        h.press('^S-Down')

        h.await_cursor_position(x=2, y=4)

        h.assert_screen_attr_equal(8, error_line)
        h.assert_screen_attr_equal(9, C_SELECTED * 40)


def test_jump_to_previous_lint_error(run, tmpdir, stubbed_flake8, themed):
    stubbed_flake8.output.write(
        '{filename}:2:1: F401 error\n'
        '{filename}:4:3: E123 error 2\n',
    )

    f = tmpdir.join('t.py')
    f.write('import os\nimport sys\n\na =1\n')

    size = {'width': 40, 'height': 10}
    with run(str(f), term='screen-256color', **size) as h, and_exit(h):
        h.await_text('import sys')
        h.press('^T')

        h.await_text('2 error(s)')

        h.press('^End')

        h.await_cursor_position(x=0, y=5)

        h.press('^S-Up')

        h.await_cursor_position(x=2, y=4)

        error_line = (
            C_NUM + C_NORM + C_NUM + C_NORM * 2 + C_NAME * 8 + C_NORM +
            C_INVALID * 4 + 22 * C_NORM
        )

        h.assert_screen_attr_equal(8, error_line)
        h.assert_screen_attr_equal(9, C_SELECTED * 40)

        h.press('^S-Up')

        h.await_cursor_position(x=0, y=2)

        h.assert_screen_attr_equal(8, C_SELECTED * 40)
        h.assert_screen_attr_equal(9, error_line)

        # should not go past beginning, but should still be highlighted
        h.press('^S-Up')

        h.await_cursor_position(x=0, y=2)

        h.assert_screen_attr_equal(8, C_SELECTED * 40)
        h.assert_screen_attr_equal(9, error_line)


def test_jump_to_error_skips_disabled(run, tmpdir, stubbed_flake8):
    stubbed_flake8.output.write(
        '{filename}:1:1: F401 error\n'
        '{filename}:2:1: F401 error\n'
        '{filename}:4:3: E123 error 2\n',
    )

    f = tmpdir.join('t.py')
    f.write('import os\nimport sys\n\na =1\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('import sys')
        h.press('^T')

        h.await_text('3 error(s)')

        h.press('^_')
        h.press_and_enter('2')

        h.await_cursor_position(x=0, y=2)

        h.press('#')

        # should have disabled the lint error
        h.await_text('??:??')

        h.press('^S-Down')

        h.await_cursor_position(x=2, y=4)

        # middle error is skipped over here:
        h.press('^S-Up')

        h.await_cursor_position(x=0, y=1)

        # middle error is also skipped over here:
        h.press('^S-Down')

        h.await_cursor_position(x=2, y=4)
