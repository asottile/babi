import contextlib
import shlex
import sys

from hecate import Runner

import babi


@contextlib.contextmanager
def run(*args, color=True, **kwargs):
    cmd = (sys.executable, '-mcoverage', 'run', '-m', 'babi', *args)
    quoted = ' '.join(shlex.quote(p) for p in cmd)
    term = 'screen-256color' if color else 'screen'
    cmd = ('bash', '-c', f'export TERM={term}; exec {quoted}')
    with Runner(*cmd, **kwargs) as h:
        h.await_text(babi.VERSION_STR)
        yield h


def await_text_missing(h, text):
    """largely based on await_text"""
    for _ in h.poll_until_timeout():
        screen = h.screenshot()
        munged = screen.replace('\n', '')
        if text not in munged:  # pragma: no branch
            return
    raise AssertionError(f'Timeout while waiting for text {text!r} to appear')


def test_can_start_without_color():
    with run(color=False) as h:
        h.press('C-x')
        h.await_exit()


def test_window_bounds(tmpdir):
    f = tmpdir.join('f.txt')
    f.write(f'{"x" * 40}\n' * 40)

    with run(str(f), width=30, height=30) as h:
        # make sure we don't go off the top left of the screen
        h.press('LEFT')
        h.press('UP')
        # make sure we don't go off the bottom of the screen
        for i in range(32):
            h.press('RIGHT')
            h.press('DOWN')
        h.press('C-x')
        h.await_exit()


def test_status_clearing_behaviour():
    with run() as h:
        h.press('C-j')
        h.await_text('unknown key')
        for i in range(24):
            h.press('LEFT')
        h.await_text('unknown key')
        h.press('LEFT')
        await_text_missing(h, 'unknown key')
        h.press('C-x')
        h.await_exit()
