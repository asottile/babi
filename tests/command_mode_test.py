from testing.runner import and_exit
from testing.runner import run


def trigger_command_mode(h):
    # in order to enter a steady state, trigger an unknown key first and then
    # press escape to open the command mode.  this is necessary as `Escape` is
    # the start of "escape sequences" and sending characters too quickly will
    # be interpreted as a single keypress
    h.press('^J')
    h.await_text('unknown key')
    h.press('Escape')
    h.await_text_missing('unknown key')


def test_quit_via_colon_q():
    with run() as h:
        trigger_command_mode(h)
        h.press_and_enter(':q')
        h.await_exit()


def test_key_navigation_in_command_mode():
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

        h.press('Bspace')
        h.await_cursor_position(x=10, y=23)
        h.await_text('\nhello worl\n')

        h.press('Home')

        h.press('Bspace')  # does nothing at beginning
        h.await_cursor_position(x=0, y=23)
        h.await_text('\nhello worl\n')

        h.press('DC')
        h.await_cursor_position(x=0, y=23)
        h.await_text('\nello worl\n')

        # unknown keys don't do anything
        h.press('^J')
        h.await_text('\nello worl\n')

        h.press('Enter')


def test_save_via_command_mode(tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.press('hello world')
        trigger_command_mode(h)
        h.press_and_enter(':w')

    assert f.read() == 'hello world\n'


def test_repeated_command_mode_does_not_show_previous_command(tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.press('ohai')
        trigger_command_mode(h)
        h.press_and_enter(':w')
        trigger_command_mode(h)
        h.await_text_missing(':w')
        h.press('Enter')


def test_write_and_quit(tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.press('hello world')
        trigger_command_mode(h)
        h.press_and_enter(':wq')
        h.await_exit()

    assert f.read() == 'hello world\n'


def test_resizing_and_scrolling_in_command_mode():
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


def test_invalid_command():
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':fake')
        h.await_text('invalid command: :fake')


def test_empty_command_is_noop():
    with run() as h, and_exit(h):
        h.press('hello ')
        trigger_command_mode(h)
        h.press('Enter')
        h.press('world')
        h.await_text('hello world')
        h.await_text_missing('invalid command')


def test_cancel_command_mode():
    with run() as h, and_exit(h):
        h.press('hello ')
        trigger_command_mode(h)
        h.press(':q')
        h.press('^C')
        h.press('world')
        h.await_text('hello world')
        h.await_text_missing('invalid command')
