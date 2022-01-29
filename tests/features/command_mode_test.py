from __future__ import annotations

import pytest

from testing.runner import and_exit
from testing.runner import trigger_command_mode


def test_quit_via_colon_q(run):
    with run() as h:
        trigger_command_mode(h)
        h.press_and_enter(':q')
        h.await_exit()


def test_key_navigation_in_command_mode(run):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press('hello world')
        h.await_cursor_position(x=11, y=23)
        h.press('Left')
        h.await_cursor_position(x=10, y=23)
        h.press('Right')
        h.await_cursor_position(x=11, y=23)
        h.press('Home')
        h.await_cursor_position(x=0, y=23)
        h.press('End')
        h.await_cursor_position(x=11, y=23)
        h.press('^A')
        h.await_cursor_position(x=0, y=23)
        h.press('^E')
        h.await_cursor_position(x=11, y=23)

        h.press('DC')  # does nothing at end
        h.await_cursor_position(x=11, y=23)
        h.await_text('\nhello world\n')

        h.press('Home')

        h.press('DC')
        h.await_cursor_position(x=0, y=23)
        h.await_text('\nello world\n')

        # unknown keys don't do anything
        h.press('^J')
        h.await_text('\nello world\n')

        h.press('Enter')


@pytest.mark.parametrize('key', ('BSpace', '^H'))
def test_command_mode_backspace(run, key):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press('hello world')
        h.await_text('\nhello world\n')

        h.press(key)
        h.await_text('\nhello worl\n')

        h.press('Home')
        h.press(key)  # does nothing at beginning
        h.await_cursor_position(x=0, y=23)
        h.await_text('\nhello worl\n')

        h.press('^C')


def test_command_mode_ctrl_k(run):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press('hello world')
        h.await_text('\nhello world\n')
        h.press('^Left')
        h.press('Left')
        h.press('^K')
        h.await_text('\nhello\n')
        h.press('Enter')


def test_command_mode_control_left(run):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press('hello world')
        h.await_cursor_position(x=11, y=23)
        h.press('^Left')
        h.await_cursor_position(x=6, y=23)
        h.press('^Left')
        h.await_cursor_position(x=0, y=23)
        h.press('^Left')
        h.await_cursor_position(x=0, y=23)
        h.press('Right')
        h.await_cursor_position(x=1, y=23)
        h.press('^Left')
        h.await_cursor_position(x=0, y=23)
        h.press('^C')


def test_command_mode_control_right(run):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press('hello world')
        h.await_cursor_position(x=11, y=23)
        h.press('^Right')
        h.await_cursor_position(x=11, y=23)
        h.press('Left')
        h.await_cursor_position(x=10, y=23)
        h.press('^Right')
        h.await_cursor_position(x=11, y=23)
        h.press('^A')
        h.await_cursor_position(x=0, y=23)
        h.press('^Right')
        h.await_cursor_position(x=5, y=23)
        h.press('^Right')
        h.await_cursor_position(x=11, y=23)
        h.press('^C')


def test_save_via_command_mode(run, tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.press('hello world')
        trigger_command_mode(h)
        h.press_and_enter(':w')

    assert f.read() == 'hello world\n'


def test_repeated_command_mode_does_not_show_previous_command(run, tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.press('ohai')
        trigger_command_mode(h)
        h.press_and_enter(':w')
        trigger_command_mode(h)
        h.await_text_missing(':w')
        h.press('Enter')


def test_write_and_quit(run, tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.press('hello world')
        trigger_command_mode(h)
        h.press_and_enter(':wq')
        h.await_exit()

    assert f.read() == 'hello world\n'


def test_resizing_and_scrolling_in_command_mode(run):
    with run(width=20) as h, and_exit(h):
        h.press('a' * 15)
        h.await_text(f'\n{"a" * 15}\n')
        trigger_command_mode(h)
        h.press('b' * 15)
        h.await_text(f'\n{"b" * 15}\n')

        with h.resize(width=16, height=24):
            h.await_text('\n«aaaaaa\n')  # the text contents
            h.await_text('\n«bbbbbb\n')  # the text contents
            h.await_cursor_position(x=7, y=23)
            h.press('Left')
            h.await_cursor_position(x=14, y=23)
            h.await_text(f'\n{"b" * 15}\n')

        h.press('Enter')


def test_invalid_command(run):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':fake')
        h.await_text('invalid command: :fake')


def test_empty_command_is_noop(run):
    with run() as h, and_exit(h):
        h.press('hello ')
        trigger_command_mode(h)
        h.press('Enter')
        h.press('world')
        h.await_text('hello world')
        h.await_text_missing('invalid command')


def test_cancel_command_mode(run):
    with run() as h, and_exit(h):
        h.press('hello ')
        trigger_command_mode(h)
        h.press(':q')
        h.press('^C')
        h.press('world')
        h.await_text('hello world')
        h.await_text_missing('invalid command')
