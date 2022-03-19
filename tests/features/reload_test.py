from __future__ import annotations

from testing.runner import and_exit
from testing.runner import trigger_command_mode


def test_reload_anonymous_file(run):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':reload')
        h.await_text('file has not been saved yet!')


def test_reload_modified_file_cancel_reloading(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('a')
        h.await_text('aline_0\n')
        h.await_text('*')

        trigger_command_mode(h)
        h.press_and_enter(':reload')

        h.await_text('reload will discard changes - continue [yes, no]?')
        h.press('n')

        h.await_text('aline_0\n')
        h.await_text('*')


def test_reload_modified_file(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('a')
        h.await_text('aline_0\n')
        h.await_text('*')

        trigger_command_mode(h)
        h.press_and_enter(':reload')

        h.await_text('reload will discard changes - continue [yes, no]?')
        h.press('y')

        h.await_text_missing('aline_0\n')
        h.await_text_missing('*')


def test_reload(run, tmpdir):
    f = tmpdir.join('f')
    f.write('1\n2\n3\n')

    with run(str(f), str(f)) as h, and_exit(h):
        # adjust the contents in the second buffer
        h.press('M-Right')
        h.press('Down')
        h.press('a')
        h.await_text('1\na2\n3\n')
        h.press('^S')

        h.press('^X')
        h.await_text('1\n2\n3\n')
        trigger_command_mode(h)
        h.press_and_enter(':reload')
        h.await_text('1\na2\n3\n')
        h.await_text_missing('*')

        h.press('M-u')
        h.await_text('1\n2\n3\n')
        h.await_text('*')


def test_reload_y_out_of_bounds(run, tmpdir):
    f = tmpdir.join('f')
    f.write('1\n2\n3\n')

    with run(str(f), str(f)) as h, and_exit(h):
        # adjust the contents in the second buffer
        h.press('M-Right')
        h.press('Down')
        h.press('^K')
        h.press('^K')
        h.await_text_missing('1\n2\n3\n')
        h.press('^S')

        h.press('^X')
        h.await_text('1\n2\n3\n')
        h.press('Down')
        h.press('Down')
        h.await_cursor_position(x=0, y=3)
        trigger_command_mode(h)
        h.press_and_enter(':reload')
        h.await_cursor_position(x=0, y=2)


def test_reload_x_out_of_bounds(run, tmpdir):
    f = tmpdir.join('f')
    f.write('abc\n123\n')

    with run(str(f), str(f)) as h, and_exit(h):
        # adjust the contents in the second buffer
        h.press('M-Right')
        h.press('DC')
        h.press('DC')
        h.await_text_missing('abc\n123\n')
        h.await_text('c\n123\n')
        h.press('^S')

        h.press('^X')
        h.await_text('abc\n123\n')
        h.press('Right')
        h.press('Right')
        h.await_cursor_position(x=2, y=1)
        trigger_command_mode(h)
        h.press_and_enter(':reload')
        h.await_cursor_position(x=1, y=1)


def test_reload_mixed_newlines(run, tmpdir):
    f = tmpdir.join('f')
    f.write('a\nb\r\nc\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text(r"mixed newlines will be converted to '\n'")
        h.await_text('*')
        trigger_command_mode(h)
        h.press_and_enter(':reload')
        h.await_text('reload will discard changes')
        h.press('y')
        h.await_text(r"reloaded! (mixed newlines will be converted to '\n'")


def test_reload_error(run, tmpdir):
    f = tmpdir.join('f')
    f.write('1\n2\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('1\n2\n')

        h.run(lambda: f.remove())

        trigger_command_mode(h)
        h.press_and_enter(':reload')

        h.await_text('reload: error! not a file:')


def test_reload_cursor_position_undo_redo(run, tmpdir):
    f = tmpdir.join('f')
    f.write('long words\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('long words\n')

        h.press('End')
        h.await_cursor_position(y=1, x=10)

        h.run(lambda: f.write('short!\n'))

        trigger_command_mode(h)
        h.press_and_enter(':reload')

        h.await_text('short!')
        h.await_cursor_position(y=1, x=6)

        h.press('M-u')
        h.await_text('long words\n')
        h.await_cursor_position(y=1, x=10)

        h.press('M-U')
        h.await_text('short!')
        h.await_cursor_position(y=1, x=6)
