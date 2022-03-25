from __future__ import annotations

import pytest

from testing.runner import and_exit


def test_prompt_window_width(run):
    with run() as h, and_exit(h):
        h.press('^_')
        h.await_text('enter line number:')
        h.press('123')
        with h.resize(width=23, height=24):
            h.await_text('\nenter line number: «3')
        with h.resize(width=22, height=24):
            h.await_text('\nenter line numb…: «3')
        with h.resize(width=7, height=24):
            h.await_text('\n…: «3')
        with h.resize(width=6, height=24):
            h.await_text('\n123')
        h.press('Enter')


def test_go_to_line_line(run, ten_lines):
    def _jump_to_line(n):
        h.press('^_')
        h.await_text('enter line number:')
        h.press_and_enter(str(n))
        h.await_text_missing('enter line number:')

    with run(str(ten_lines), height=9) as h, and_exit(h):
        # still on screen
        _jump_to_line(3)
        h.await_cursor_position(x=0, y=3)
        # should go to beginning of file
        _jump_to_line(0)
        h.await_cursor_position(x=0, y=1)
        # should go to end of the file
        _jump_to_line(999)
        h.await_cursor_position(x=0, y=4)
        h.assert_screen_line_equal(3, 'line_9')
        # should also go to the end of the file
        _jump_to_line(-1)
        h.await_cursor_position(x=0, y=4)
        h.assert_screen_line_equal(3, 'line_9')
        # should go to beginning of file
        _jump_to_line(-999)
        h.await_cursor_position(x=0, y=1)
        h.assert_cursor_line_equal('line_0')


@pytest.mark.parametrize('key', ('Enter', '^C'))
def test_go_to_line_cancel(run, ten_lines, key):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('Down')
        h.await_cursor_position(x=0, y=2)

        h.press('^_')
        h.await_text('enter line number:')
        h.press(key)
        h.await_cursor_position(x=0, y=2)
        h.await_text('cancelled')


def test_go_to_line_not_an_integer(run):
    with run() as h, and_exit(h):
        h.press('^_')
        h.await_text('enter line number:')
        h.press_and_enter('asdf')
        h.await_text("not an integer: 'asdf'")
