from __future__ import annotations

import pytest

from testing.runner import and_exit
from testing.runner import trigger_command_mode


@pytest.fixture
def three_lines_with_indentation(tmpdir):
    f = tmpdir.join('f')
    f.write('line_0\n    line_1\n    line_2')
    return f


def test_comment_some_code(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('S-Down')

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('# line_0\n# line_1\nline_2\n')


def test_comment_empty_line_trailing_whitespace(run, tmpdir):
    f = tmpdir.join('f')
    f.write('1\n\n2\n')

    with run(str(f)) as h, and_exit(h):
        h.press('S-Down')
        h.press('S-Down')

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('# 1\n#\n# 2')


def test_comment_some_code_with_alternate_comment_character(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('S-Down')

        trigger_command_mode(h)
        h.press_and_enter(':comment //')

        h.await_text('// line_0\n// line_1\nline_2\n')


def test_comment_partially_commented(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('#')
        h.press('S-Down')
        h.await_text('#line_0\nline_1\nline_2')

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('line_0\nline_1\nline_2\n')


def test_comment_partially_uncommented(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('Down')
        h.press('#')
        h.press('Up')
        h.press('S-Down')
        h.await_text('line_0\n#line_1\nline_2')

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('# line_0\n# #line_1\nline_2\n')


def test_comment_single_line(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('# line_0\nline_1\n')


def test_uncomment_single_line(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('#')
        h.await_text('#line_0\nline_1\n')

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('line_0\nline_1\n')


def test_comment_with_trailing_whitespace(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':comment //   ')

        h.await_text('// line_0\nline_1\n')


def test_comment_some_code_with_indentation(run, three_lines_with_indentation):
    with run(str(three_lines_with_indentation)) as h, and_exit(h):
        h.press('S-Down')

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('# line_0\n#     line_1\n    line_2\n')

        h.press('S-Up')
        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('line_0\n    line_1\n    line_2\n')


def test_comment_some_code_on_indent_part(run, three_lines_with_indentation):
    with run(str(three_lines_with_indentation)) as h, and_exit(h):
        h.press('Down')
        h.press('S-Down')

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('line_0\n    # line_1\n    # line_2\n')

        h.press('S-Up')

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('line_0\n    line_1\n    line_2\n')


def test_comment_some_code_on_tabs_part(run, tmpdir):
    f = tmpdir.join('f')
    f.write('line_0\n\tline_1\n\t\tline_2')

    with run(str(f)) as h, and_exit(h):
        h.await_text('line_0\n    line_1\n        line_2')
        h.press('Down')
        h.press('S-Down')

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('line_0\n    # line_1\n    #   line_2')

        h.press('S-Up')

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('line_0\n    line_1\n        line_2')


def test_comment_cursor_at_end_of_line(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('# ')
        h.press('End')
        h.await_cursor_position(x=8, y=1)

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_cursor_position(x=6, y=1)


def test_add_comment_moves_cursor(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('End')

        h.await_cursor_position(x=6, y=1)

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_cursor_position(x=8, y=1)


def test_do_not_move_if_cursor_before_comment(run, tmpdir):
    f = tmpdir.join('f')
    f.write('\t\tfoo')

    with run(str(f)) as h, and_exit(h):
        h.press('Right')

        h.await_cursor_position(x=4, y=1)

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_cursor_position(x=4, y=1)


@pytest.mark.parametrize('comment', ('# ', '#'))
def test_remove_comment_with_comment_elsewhere_in_line(run, tmpdir, comment):
    f = tmpdir.join('f')
    f.write(f'{comment}print("not a # comment here!")\n')

    with run(str(f)) as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('\nprint("not a # comment here!")\n')


def test_comment_incorrect_number_of_args(run):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':comment # #')
        h.await_text('`:comment`: expected 0 or 1 args but got 2')
