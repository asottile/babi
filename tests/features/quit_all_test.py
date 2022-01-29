from __future__ import annotations

from testing.runner import trigger_command_mode


def test_quit_all(run):
    with run() as h:
        h.press('^P')
        h.press_and_enter('filename2')
        h.await_text('[2/2]')
        h.press('hello')

        h.press('^P')
        h.press_and_enter('filename3')
        h.await_text('[3/3]')

        trigger_command_mode(h)
        h.press_and_enter(':qall')

        # should ask if we want to save filename2 first
        h.await_text('[2/2]')
        h.await_text('hello')
        h.await_text('file is modified')
        h.press('n')

        h.await_exit()


def test_quit_all_save_cancelled(run):
    with run() as h:
        h.press('^P')
        h.press_and_enter('filename2')
        h.await_text('[2/2]')
        h.press('hello')

        h.press('^P')
        h.press_and_enter('filename3')
        h.await_text('[3/3]')

        trigger_command_mode(h)
        h.press_and_enter(':qall')

        # should ask if we want to save filename2 first
        h.await_text('[2/2]')
        h.await_text('hello')
        h.await_text('file is modified')
        h.press('^C')
        h.await_text('cancelled')

        trigger_command_mode(h)
        h.press_and_enter(':qall!')
        h.await_exit()


def test_quit_all_bang(run):
    with run() as h:
        h.press('^P')
        h.press_and_enter('filename2')
        h.await_text('[2/2]')
        h.press('hello')

        h.press('^P')
        h.press_and_enter('filename3')
        h.await_text('[3/3]')

        trigger_command_mode(h)
        h.press_and_enter(':qall!')
        h.await_exit()
