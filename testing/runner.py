import contextlib
import shlex
import sys
from typing import List

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

    def await_text(self, text, timeout=None):
        """copied from the base implementation but doesn't munge newlines"""
        with self._onerror():
            for _ in self.poll_until_timeout(timeout):
                screen = self.screenshot()
                if text in screen:  # pragma: no branch
                    return
            raise AssertionError(
                f'Timeout while waiting for text {text!r} to appear',
            )

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

    def _get_cursor_position(self):
        cmd = ('display', '-t0', '-p', '#{cursor_x}\t#{cursor_y}')
        x, y = self.tmux.execute_command(*cmd).split()
        return int(x), int(y)

    def await_cursor_position(self, *, x, y):
        with self._onerror():
            for _ in self.poll_until_timeout():
                pos = self._get_cursor_position()
                if pos == (x, y):  # pragma: no branch
                    return

            raise AssertionError(
                f'Timeout while waiting for cursor to reach {(x, y)}\n'
                f'Last cursor position: {pos}',
            )

    def get_screen_line(self, n):
        return self.screenshot().splitlines()[n]

    def get_cursor_line(self):
        _, y = self._get_cursor_position()
        return self.get_screen_line(y)

    @contextlib.contextmanager
    def resize(self, width, height):
        current_w, current_h = self.get_pane_size()
        sleep_cmd = (
            'bash', '-c',
            f'echo {"*" * (current_w * current_h)} && '
            f'exec sleep infinity',
        )

        panes = 0

        hsplit_w = current_w - width - 1
        if hsplit_w > 0:
            cmd = ('split-window', '-ht0', '-l', hsplit_w, *sleep_cmd)
            self.tmux.execute_command(*cmd)
            panes += 1

        vsplit_h = current_h - height - 1
        if vsplit_h > 0:  # pragma: no branch  # TODO
            cmd = ('split-window', '-vt0', '-l', vsplit_h, *sleep_cmd)
            self.tmux.execute_command(*cmd)
            panes += 1

        assert self.get_pane_size() == (width, height)
        try:
            yield
        finally:
            for _ in range(panes):
                self.tmux.execute_command('kill-pane', '-t1')

    def press_and_enter(self, s):
        self.press(s)
        self.press('Enter')


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
    h.press('^X')
    # dismiss the save prompt
    if ' *' in h.get_screen_line(0):
        h.press('n')
    h.await_exit()
