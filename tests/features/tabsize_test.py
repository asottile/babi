from __future__ import annotations

import pytest

from testing.runner import and_exit
from testing.runner import trigger_command_mode


@pytest.mark.parametrize('setting', ('tabsize', 'tabstop'))
def test_set_tabstop(run, setting):
    with run() as h, and_exit(h):
        h.press('a')
        h.press('Left')
        trigger_command_mode(h)
        h.press_and_enter(f':{setting} 2')
        h.await_text('updated!')
        h.press('Tab')
        h.await_text('\n  a')
        h.await_cursor_position(x=2, y=1)


@pytest.mark.parametrize('tabsize', ('-1', '0', 'wat'))
def test_set_invalid_tabstop(run, tabsize):
    with run() as h, and_exit(h):
        h.press('a')
        h.press('Left')
        trigger_command_mode(h)
        h.press_and_enter(f':tabstop {tabsize}')
        h.await_text(f'invalid size: {tabsize}')
        h.press('Tab')
        h.await_text('    a')
        h.await_cursor_position(x=4, y=1)
