import contextlib
import shlex
import sys

import pytest
from hecate import Runner
from hecate.hecate import AbnormalExit

import babi


class PrintsErrorRunner(Runner):
    def await_exit(self, *args, **kwargs):
        try:
            return super().await_exit(*args, **kwargs)
        except AbnormalExit:  # pragma: no cover
            print('=' * 79, flush=True)
            print(self.screenshot(), end='', flush=True)
            print('=' * 79, flush=True)
            raise


@contextlib.contextmanager
def run(*args, color=True, **kwargs):
    cmd = (sys.executable, '-mcoverage', 'run', '-m', 'babi', *args)
    quoted = ' '.join(shlex.quote(p) for p in cmd)
    term = 'screen-256color' if color else 'screen'
    cmd = ('bash', '-c', f'export TERM={term}; exec {quoted}')
    with PrintsErrorRunner(*cmd, **kwargs) as h:
        h.await_text(babi.VERSION_STR)
        yield h


@contextlib.contextmanager
def and_exit(h):
    try:
        yield
    finally:
        h.press('C-x')
        h.await_exit()


def await_text_missing(h, text):
    """largely based on await_text"""
    for _ in h.poll_until_timeout():
        screen = h.screenshot()
        munged = screen.replace('\n', '')
        if text not in munged:  # pragma: no branch
            return
    raise AssertionError(f'Timeout while waiting for text {text!r} to appear')


def get_size(h):
    cmd = ('display', '-t0', '-p', '#{pane_width}\t#{pane_height}')
    w, h = h.tmux.execute_command(*cmd).split()
    return int(w), int(h)


@contextlib.contextmanager
def resize(h, width, height):
    current_w, current_h = get_size(h)

    panes = 0

    hsplit_w = current_w - width - 1
    if hsplit_w > 0:  # pragma: no branch  # TODO
        cmd = ('split-window', '-ht0', '-l', hsplit_w, 'sleep', 'infinity')
        h.tmux.execute_command(*cmd)
        panes += 1

    vsplit_h = current_h - height - 1
    if vsplit_h > 0:  # pragma: no branch  # TODO
        cmd = ('split-window', '-vt0', '-l', vsplit_h, 'sleep', 'infinity')
        h.tmux.execute_command(*cmd)
        panes += 1

    assert get_size(h) == (width, height)
    try:
        yield
    finally:
        for _ in range(panes):
            h.tmux.execute_command('kill-pane', '-t1')


@pytest.mark.parametrize('color', (True, False))
def test_color_test(color):
    with run('--color-test', color=color) as h, and_exit(h):
        h.await_text('*  1*  2')


def test_can_start_without_color():
    with run(color=False) as h, and_exit(h):
        pass


def test_window_bounds(tmpdir):
    f = tmpdir.join('f.txt')
    f.write(f'{"x" * 40}\n' * 40)

    with run(str(f), width=30, height=30) as h, and_exit(h):
        h.await_text('x' * 30)
        # make sure we don't go off the top left of the screen
        h.press('LEFT')
        h.press('UP')
        # make sure we don't go off the bottom of the screen
        for i in range(32):
            h.press('RIGHT')
            h.press('DOWN')


def test_status_clearing_behaviour():
    with run() as h, and_exit(h):
        h.press('C-j')
        h.await_text('unknown key')
        for i in range(24):
            h.press('LEFT')
        h.await_text('unknown key')
        h.press('LEFT')
        await_text_missing(h, 'unknown key')


def test_reacts_to_resize():
    with run() as h, and_exit(h):
        first_line = h.screenshot().splitlines()[0]
        with resize(h, 40, 20):
            # the first line should be different after resize
            await_text_missing(h, first_line)
