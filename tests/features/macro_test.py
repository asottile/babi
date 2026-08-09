from __future__ import annotations

import pytest

from testing.runner import and_exit
from testing.runner import trigger_command_mode


@pytest.fixture
def macro_file(xdg_config_home):
    return (
        xdg_config_home
        .join('babi', 'macros')
        .ensure(dir=True)
        .join('macro')
        .write('hello\nhello nicholas')
    )


def test_macro_command_invalid_macro(run):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':m not_a_macro')
        h.await_text('invalid macro: not_a_macro')


def test_macro_command(run, macro_file):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':m macro')
        h.await_text('hello\nhello nicholas')
        h.await_text('macro macro inserted!')


def test_macro_inserts_text(run, macro_file):
    with run() as h, and_exit(h):
        h.press('before')
        h.await_text('before\n')
        trigger_command_mode(h)
        h.press_and_enter(':m macro')
        h.await_text('beforehello\nhello nicholas')


def test_macro_commmand_undo_redo(run, macro_file):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':m macro')
        h.await_text('hello\nhello nicholas')
        h.press('M-u')
        h.await_text('undo: macro')
        h.await_text_missing('hello\nhello nicholas')

        h.press('M-U')
        h.await_text('hello\nhello nicholas')
        h.await_text('redo: macro')


def test_macro_command_not_utf8(run, xdg_config_home):
    (
        xdg_config_home
        .join('babi', 'macros')
        .ensure(dir=True)
        .join('macro')
        .write_binary(b'\xa0\x1f\xe2')
    )
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':m macro')
        h.await_text('invalid macro: macro (not utf-8)')
