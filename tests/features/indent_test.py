from __future__ import annotations

from testing.runner import and_exit
from testing.runner import trigger_command_mode


def test_indent_at_beginning_of_line(run):
    with run() as h, and_exit(h):
        h.press('hello')
        h.press('Home')
        h.press('Tab')
        h.await_text('\n    hello\n')
        h.await_cursor_position(x=4, y=1)


def test_indent_not_full_tab(run):
    with run() as h, and_exit(h):
        h.press('hello')
        h.press('Home')
        h.press('Right')
        h.press('Tab')
        h.await_text('h   ello')
        h.await_cursor_position(x=4, y=1)


def test_indent_fixes_eof(run):
    with run() as h, and_exit(h):
        h.press('Tab')
        h.press('Down')
        h.await_cursor_position(x=0, y=2)


def test_indent_selection(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('S-Right')
        h.press('Tab')
        h.await_text('\n    line_0\n')
        h.await_cursor_position(x=5, y=1)
        h.press('^K')
        h.await_text('\nine_0\n')


def test_indent_selection_does_not_extend_mid_line_selection(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('Right')
        h.press('S-Right')
        h.press('Tab')
        h.await_text('\n    line_0\n')
        h.await_cursor_position(x=6, y=1)
        h.press('^K')
        h.await_text('\n    lne_0\n')


def test_indent_selection_leaves_blank_lines(run, tmpdir):
    f = tmpdir.join('f')
    f.write('1\n\n2\n\n3\n')
    with run(str(f)) as h, and_exit(h):
        for _ in range(3):
            h.press('S-Down')
        h.press('Tab')
        h.press('^S')
    assert f.read() == '    1\n\n    2\n\n3\n'


def test_dedent_no_indentation(run):
    with run() as h, and_exit(h):
        h.press('a')
        h.press('BTab')
        h.await_text('\na\n')
        h.await_cursor_position(x=1, y=1)


def test_dedent_exactly_one_indent(run):
    with run() as h, and_exit(h):
        h.press('Tab')
        h.press('a')
        h.await_text('\n    a\n')
        h.press('BTab')
        h.await_text('\na\n')
        h.await_cursor_position(x=1, y=1)


def test_dedent_selection(run, tmpdir):
    f = tmpdir.join('f')
    f.write('1\n  2\n        3\n')
    with run(str(f)) as h, and_exit(h):
        for _ in range(3):
            h.press('S-Down')
        h.press('BTab')
        h.await_text('\n1\n2\n    3\n')


def test_dedent_selection_with_noexpandtabs(run, tmpdir):
    f = tmpdir.join('f')
    f.write('1\n\t2\n\t\t3\n')
    with run(str(f)) as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':noexpandtabs')
        h.await_text('updated!')
        for _ in range(3):
            h.press('S-Down')
        h.press('BTab')
        h.press('^S')
    assert f.read() == '1\n2\n\t3\n'


def test_dedent_beginning_of_line(run, tmpdir):
    f = tmpdir.join('f')
    f.write('    hi\n')
    with run(str(f)) as h, and_exit(h):
        h.press('BTab')
        h.await_text('\nhi\n')


def test_dedent_selection_does_not_make_selection_negative(run):
    with run() as h, and_exit(h):
        h.press('Tab')
        h.press('hello')
        h.press('Home')
        h.press('Right')
        h.press('S-Right')
        h.press('BTab')
        h.await_text('\nhello\n')
        h.press('S-Right')
        h.press('^K')
        h.await_text('\nello\n')
