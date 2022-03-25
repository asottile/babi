from __future__ import annotations

import contextlib
import curses
import enum
import os
import re
import signal

from hecate import Runner


class Token(enum.Enum):
    FG_ESC = re.compile(r'\x1b\[38;5;(\d+)m')
    BG_ESC = re.compile(r'\x1b\[48;5;(\d+)m')
    RESET = re.compile(r'\x1b\[0?m')
    ESC = re.compile(r'\x1b\[(\d+)m')
    ESC2 = re.compile(r'\x1b\[(\d+);(\d+)m')
    NL = re.compile(r'\n')
    CHAR = re.compile('.')


def tokenize_colors(s):
    i = 0
    while i < len(s):
        for tp in Token:
            match = tp.value.match(s, i)
            if match is not None:
                yield tp, match
                i = match.end()
                break
        else:
            raise AssertionError(f'unreachable: not matched at {i}?')


def to_attrs(screen, width):
    fg = bg = -1
    attr = 0
    idx = 0
    ret: list[list[tuple[int, int, int]]]
    ret = [[] for _ in range(len(screen.splitlines()))]

    for tp, match in tokenize_colors(screen):
        if tp is Token.FG_ESC:
            fg = int(match[1])
        elif tp is Token.BG_ESC:
            bg = int(match[1])
        elif tp is Token.RESET:
            fg = bg = -1
            attr = 0
        elif tp is Token.ESC:
            if match[1] == '7':
                attr |= curses.A_REVERSE
            elif match[1] == '1':
                attr |= curses.A_BOLD
            elif match[1] == '2':
                attr |= curses.A_DIM
            elif match[1] == '39':
                fg = -1
            elif match[1] == '49':
                bg = -1
            elif 40 <= int(match[1]) <= 47:
                bg = int(match[1]) - 40
            else:
                raise AssertionError(f'unknown escape {match[1]}')
        elif tp is Token.ESC2:
            if match[1] == '2' and match[2] == '7':
                attr |= curses.A_DIM | curses.A_REVERSE
            else:
                raise AssertionError(f'unknown escape {match[1]}')
        elif tp is Token.NL:
            ret[idx].extend([(fg, bg, attr)] * (width - len(ret[idx])))
            idx += 1
        elif tp is Token.CHAR:
            ret[idx].append((fg, bg, attr))
        else:
            raise AssertionError(f'unreachable {tp} {match}')

    return ret


class PrintsErrorRunner(Runner):
    def __init__(self, *args, **kwargs):
        self._prev_screenshot = None
        super().__init__(*args, **kwargs)

    def screenshot(self, *args, **kwargs):
        ret = super().screenshot(*args, **kwargs)
        if ret != self._prev_screenshot:
            print('=' * 79, flush=True)
            print(ret, end='', flush=True)
            print('=' * 79, flush=True)
            self._prev_screenshot = ret
        return ret

    def color_screenshot(self):
        ret = self.tmux.execute_command('capture-pane', '-ept0')
        if ret != self._prev_screenshot:
            print('=' * 79, flush=True)
            print(ret, end='\x1b[m', flush=True)
            print('=' * 79, flush=True)
            self._prev_screenshot = ret
        return ret

    def get_attrs(self):
        width, _ = self.get_pane_size()
        return to_attrs(self.color_screenshot(), width)

    def await_text(self, text, timeout=None):
        """copied from the base implementation but doesn't munge newlines"""
        for _ in self.poll_until_timeout(timeout):
            screen = self.screenshot()
            if text in screen:  # pragma: no branch
                return
        raise AssertionError(
            f'Timeout while waiting for text {text!r} to appear',
        )

    def await_text_missing(self, s):
        """largely based on await_text"""
        for _ in self.poll_until_timeout():
            screen = self.screenshot()
            munged = screen.replace('\n', '')
            if s not in munged:  # pragma: no branch
                return
        raise AssertionError(
            f'Timeout while waiting for text {s!r} to disappear',
        )

    def assert_cursor_line_equal(self, s):
        cursor_line = self._get_cursor_line()
        assert cursor_line == s, (cursor_line, s)

    def assert_screen_line_equal(self, n, s):
        screen_line = self._get_screen_line(n)
        assert screen_line == s, (screen_line, s)

    def assert_screen_attr_equal(self, n, attr):
        attr_line = self.get_attrs()[n]
        assert attr_line == attr, (n, attr_line, attr)

    def assert_full_contents(self, s):
        contents = self.screenshot()
        assert contents == s

    def kill_usr1(self):
        cmd = ('display', '-t0', '-p', '#{pane_pid}')
        pid_s = self.tmux.execute_command(*cmd).strip()
        with open(f'/proc/{pid_s}/task/{pid_s}/children') as f:
            child_pid = f.read().strip()
        os.kill(int(child_pid), signal.SIGUSR1)

    def get_pane_size(self):
        cmd = ('display', '-t0', '-p', '#{pane_width}\t#{pane_height}')
        w, h = self.tmux.execute_command(*cmd).split()
        return int(w), int(h)

    def _get_cursor_position(self):
        cmd = ('display', '-t0', '-p', '#{cursor_x}\t#{cursor_y}')
        x, y = self.tmux.execute_command(*cmd).split()
        return int(x), int(y)

    def await_cursor_position(self, *, x, y):
        for _ in self.poll_until_timeout():
            pos = self._get_cursor_position()
            if pos == (x, y):  # pragma: no branch
                return

        raise AssertionError(
            f'Timeout while waiting for cursor to reach {(x, y)}\n'
            f'Last cursor position: {pos}',
        )

    def _get_screen_line(self, n):
        return self.screenshot().splitlines()[n]

    def _get_cursor_line(self):
        _, y = self._get_cursor_position()
        return self._get_screen_line(y)

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

    def answer_no_if_modified(self):
        if 'file is mod' in self.screenshot():
            self.press('n')

    def run(self, callback):
        # this is a bit of a hack, the in-process fake defers all execution
        callback()

    @contextlib.contextmanager
    def on_error(self):
        try:
            yield
        except AssertionError:  # pragma: no cover (only on failure)
            self.screenshot()
            raise


@contextlib.contextmanager
def and_exit(h):
    yield
    # only try and exit in non-exceptional cases
    h.press('^X')
    h.answer_no_if_modified()
    h.await_exit()


def trigger_command_mode(h):
    # in order to enter a steady state, trigger an unknown key first and then
    # press escape to open the command mode.  this is necessary as `Escape` is
    # the start of "escape sequences" and sending characters too quickly will
    # be interpreted as a single keypress
    h.press('^J')
    h.await_text('unknown key')
    h.press('Escape')
    h.await_text_missing('unknown key')
