from __future__ import annotations

import shlex
import sys

from babi.screen import VERSION_STR
from testing.runner import PrintsErrorRunner


def test_open_from_stdin():
    with PrintsErrorRunner('env', 'TERM=screen', 'bash', '--norc') as h:
        cmd = (sys.executable, '-mcoverage', 'run', '-m', 'babi', '-')
        babi_cmd = ' '.join(shlex.quote(part) for part in cmd)
        h.press_and_enter(fr"echo $'hello\nworld' | {babi_cmd}")

        h.await_text(VERSION_STR, timeout=2)
        h.await_text('<<new file>> *')
        h.await_text('hello\nworld')

        h.press('^X')
        h.press('n')
        h.await_text_missing('<<new file>>')
        h.press_and_enter('exit')
        h.await_exit()
