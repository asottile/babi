import contextlib
import shlex
import sys
from typing import List

import pytest
from hecate import Runner

import babi


class PrintsErrorRunner(Runner):
    def __init__(self, *args, **kwargs):
        self._screenshots: List[str] = []
        super().__init__(*args, **kwargs)

    def screenshot(self, *args, **kwargs):
        ret = super().screenshot(*args, **kwargs)
        if not self._screenshots or self._screenshots[-1] != ret:
            self._screenshots.append(ret)
        return ret

    @contextlib.contextmanager
    def _onerror(self):
        try:
            yield
        except Exception:  # pragma: no cover
            # take a screenshot of the final state
            self.screenshot()
            print('=' * 79, flush=True)
            for screenshot in self._screenshots:
                print(screenshot, end='', flush=True)
                print('=' * 79, flush=True)
            raise

    def await_exit(self, *args, **kwargs):
        with self._onerror():
            return super().await_exit(*args, **kwargs)

    def await_text(self, *args, **kwargs):
        with self._onerror():
            return super().await_text(*args, **kwargs)

    def await_text_missing(self, s):
        """largely based on await_text"""
        with self._onerror():
            for _ in self.poll_until_timeout():
                screen = self.screenshot()
                munged = screen.replace('\n', '')
                if s not in munged:  # pragma: no branch
                    return
            raise AssertionError(
                f'Timeout while waiting for text {s!r} to disappear',
            )

    def get_pane_size(self):
        cmd = ('display', '-t0', '-p', '#{pane_width}\t#{pane_height}')
        w, h = self.tmux.execute_command(*cmd).split()
        return int(w), int(h)

    @contextlib.contextmanager
    def resize(self, width, height):
        current_w, current_h = self.get_pane_size()

        panes = 0

        hsplit_w = current_w - width - 1
        if hsplit_w > 0:
            cmd = ('split-window', '-ht0', '-l', hsplit_w, 'sleep', 'infinity')
            self.tmux.execute_command(*cmd)
            panes += 1

        vsplit_h = current_h - height - 1
        if vsplit_h > 0:  # pragma: no branch  # TODO
            cmd = ('split-window', '-vt0', '-l', vsplit_h, 'sleep', 'infinity')
            self.tmux.execute_command(*cmd)
            panes += 1

        assert self.get_pane_size() == (width, height)
        try:
            yield
        finally:
            for _ in range(panes):
                self.tmux.execute_command('kill-pane', '-t1')


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
    yield
    # only try and exit in non-exceptional cases
    h.press('C-x')
    h.await_exit()


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


def test_window_height_2(tmpdir):
    # 2 tall:
    # - header is hidden, otherwise behaviour is normal
    f = tmpdir.join('f.txt')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')

        with h.resize(80, 2):
            h.await_text_missing(babi.VERSION_STR)
            assert h.screenshot() == 'hello world\n\n'
            h.press('C-j')
            h.await_text('unknown key')

        h.await_text(babi.VERSION_STR)


def test_window_height_1(tmpdir):
    # 1 tall:
    # - only file contents as body
    # - status takes precedence over body, but cleared after single action
    f = tmpdir.join('f.txt')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')

        with h.resize(80, 1):
            h.await_text_missing(babi.VERSION_STR)
            assert h.screenshot() == 'hello world\n'
            h.press('C-j')
            h.await_text('unknown key')
            h.press('Right')
            h.await_text_missing('unknown key')


def test_status_clearing_behaviour():
    with run() as h, and_exit(h):
        h.press('C-j')
        h.await_text('unknown key')
        for i in range(24):
            h.press('LEFT')
        h.await_text('unknown key')
        h.press('LEFT')
        h.await_text_missing('unknown key')


def test_reacts_to_resize():
    with run() as h, and_exit(h):
        first_line = h.screenshot().splitlines()[0]
        with h.resize(40, 20):
            # the first line should be different after resize
            h.await_text_missing(first_line)
