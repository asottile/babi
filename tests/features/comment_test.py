from testing.runner import and_exit
from testing.runner import trigger_command_mode


def test_comment_some_code(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('S-Down')

        trigger_command_mode(h)
        h.press_and_enter(':comment')

        h.await_text('# line_0\n# line_1\nline_2\n')


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
