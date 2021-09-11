from __future__ import annotations

import shlex
import sys

from babi.screen import VERSION_STR
from testing.runner import PrintsErrorRunner


def test_suspend(tmpdir):
    f = tmpdir.join('f')
    f.write('hello')

    with PrintsErrorRunner('env', 'TERM=screen', 'bash', '--norc') as h:
        cmd = (sys.executable, '-mcoverage', 'run', '-m', 'babi', str(f))
        h.press_and_enter(' '.join(shlex.quote(part) for part in cmd))
        h.await_text(VERSION_STR, timeout=2)
        h.await_text('hello')

        h.press('^Z')
        h.await_text_missing('hello')

        h.press_and_enter('fg')
        h.await_text('hello')

        h.press('^X')
        h.press_and_enter('exit')
        h.await_exit()


def test_suspend_with_resize(tmpdir):
    f = tmpdir.join('f')
    f.write('hello')

    with PrintsErrorRunner('env', 'TERM=screen', 'bash', '--norc') as h:
        cmd = (sys.executable, '-mcoverage', 'run', '-m', 'babi', str(f))
        h.press_and_enter(' '.join(shlex.quote(part) for part in cmd))
        h.await_text(VERSION_STR, timeout=2)
        h.await_text('hello')

        h.press('^Z')
        h.await_text_missing('hello')

        with h.resize(80, 10):
            h.press_and_enter('fg')
            h.await_text('hello')

        h.press('^X')
        h.press_and_enter('exit')
        h.await_exit()
