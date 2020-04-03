import contextlib
import curses
import os
import sys
from typing import List
from typing import NamedTuple
from typing import Tuple
from typing import Union
from unittest import mock

import pytest
import wcwidth

from babi._types import Protocol
from babi.main import main
from babi.screen import VERSION_STR
from testing.runner import PrintsErrorRunner


@pytest.fixture(autouse=True)
def prefix_home(tmpdir):
    prefix_home = tmpdir.join('prefix_home')
    with mock.patch.object(sys, 'prefix', str(prefix_home)):
        yield prefix_home


@pytest.fixture(autouse=True)
def xdg_data_home(tmpdir):
    data_home = tmpdir.join('data_home')
    with mock.patch.dict(os.environ, {'XDG_DATA_HOME': str(data_home)}):
        yield data_home


@pytest.fixture(autouse=True)
def xdg_config_home(tmpdir):
    config_home = tmpdir.join('config_home')
    with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': str(config_home)}):
        yield config_home


@pytest.fixture
def ten_lines(tmpdir):
    f = tmpdir.join('f')
    f.write('\n'.join(f'line_{i}' for i in range(10)))
    return f


class Screen:
    def __init__(self, width, height):
        self.nodelay = False
        self.width = width
        self.height = height
        self.lines = [' ' * self.width for _ in range(self.height)]
        self.attrs = [[(0, 0, 0)] * self.width for _ in range(self.height)]
        self.x = self.y = 0
        self._prev_screenshot = None

    def screenshot(self):
        ret = ''.join(f'{line.rstrip()}\n' for line in self.lines)
        if ret != self._prev_screenshot:
            print('=' * 79)
            print(ret, end='')
            print('=' * 79)
            self._prev_screenshot = ret
        return ret

    def addstr(self, y, x, s, attr):
        self.lines[y] = self.lines[y][:x] + s + self.lines[y][x + len(s):]

        line_attr = self.attrs[y]
        new = [attr] * len(s)
        self.attrs[y] = line_attr[:x] + new + line_attr[x + len(s):]

        self.y = y
        self.x = x + wcwidth.wcswidth(s)

    def insstr(self, y, x, s, attr):
        line = self.lines[y]
        self.lines[y] = (line[:x] + s + line[x:])[:self.width]

        line_attr = self.attrs[y]
        new = [attr] * len(s)
        self.attrs[y] = (line_attr[:x] + new + line_attr[x:])[:self.width]

    def chgat(self, y, x, n, attr):
        assert n >= 0  # TODO: switch to > 0, we should never do 0-length
        self.attrs[y][x:x + n] = [attr] * n

    def move(self, y, x):
        assert 0 <= y < self.height
        assert 0 <= x < self.width
        print(f'MOVE: y: {y}, x: {x}')
        self.y, self.x = y, x

    def resize(self, *, width, height):
        if height > self.height:
            self.lines.extend([''] * (height - self.height))
        else:
            self.lines = self.lines[:height]
        if width > self.width:
            self.lines[:] = [line.ljust(width) for line in self.lines]
        else:
            self.lines[:] = [line[:width] for line in self.lines]
        self.width, self.height = width, height


class Op(Protocol):
    def __call__(self, screen: Screen) -> None: ...


class AwaitText(NamedTuple):
    text: str

    def __call__(self, screen: Screen) -> None:
        if self.text not in screen.screenshot():
            raise AssertionError(f'expected: {self.text!r}')


class AwaitTextMissing(NamedTuple):
    text: str

    def __call__(self, screen: Screen) -> None:
        if self.text in screen.screenshot():
            raise AssertionError(f'expected missing: {self.text!r}')


class AwaitCursorPosition(NamedTuple):
    x: int
    y: int

    def __call__(self, screen: Screen) -> None:
        assert (self.x, self.y) == (screen.x, screen.y)


class AssertCursorLineEquals(NamedTuple):
    line: str

    def __call__(self, screen: Screen) -> None:
        assert screen.lines[screen.y].rstrip() == self.line


class AssertScreenLineEquals(NamedTuple):
    n: int
    line: str

    def __call__(self, screen: Screen) -> None:
        assert screen.lines[self.n].rstrip() == self.line


class AssertScreenAttrEquals(NamedTuple):
    n: int
    attr: List[Tuple[int, int, int]]

    def __call__(self, screen: Screen) -> None:
        assert screen.attrs[self.n] == self.attr


class AssertFullContents(NamedTuple):
    contents: str

    def __call__(self, screen: Screen) -> None:
        assert screen.screenshot() == self.contents


class Resize(NamedTuple):
    width: int
    height: int

    def __call__(self, screen: Screen) -> None:
        screen.resize(width=self.width, height=self.height)


class KeyPress(NamedTuple):
    wch: Union[int, str]

    def __call__(self, screen: Screen) -> None:
        raise AssertionError('unreachable')


class CursesError(NamedTuple):
    def __call__(self, screen: Screen) -> None:
        if screen.nodelay:
            raise curses.error()


class CursesScreen:
    def __init__(self, screen, runner):
        self._screen = screen
        self._runner = runner
        self._bkgd_attr = (-1, -1, 0)

    def _to_attr(self, attr):
        if attr == 0:
            return self._bkgd_attr
        else:
            pair = (attr & (0xff << 8)) >> 8
            if pair == 0:
                fg, bg, _ = self._bkgd_attr
            else:
                fg, bg = self._runner.color_pairs[pair]
            attr = attr & ~(0xff << 8)
            return (fg, bg, attr)

    def bkgd(self, c, attr):
        assert c == ' '
        self._bkgd_attr = self._to_attr(attr)

    def keypad(self, val):
        pass

    def nodelay(self, val):
        self._screen.nodelay = val

    def addstr(self, y, x, s, attr=0):
        self._screen.addstr(y, x, s, self._to_attr(attr))

    def insstr(self, y, x, s, attr=0):
        self._screen.insstr(y, x, s, self._to_attr(attr))

    def clrtoeol(self):
        s = self._screen.width * ' '
        self.insstr(self._screen.y, self._screen.x, s)

    def chgat(self, y, x, n, attr):
        self._screen.chgat(y, x, n, self._to_attr(attr))

    def move(self, y, x):
        self._screen.move(y, x)

    def getyx(self):
        return self._screen.y, self._screen.x

    def get_wch(self):
        return self._runner._get_wch()


class Key(NamedTuple):
    tmux: str
    curses: bytes
    wch: Union[int, str]

    @property
    def value(self) -> int:
        return self.wch if isinstance(self.wch, int) else ord(self.wch)


KEYS = [
    Key('Enter', b'^M', '\r'),
    Key('Tab', b'^I', '\t'),
    Key('BTab', b'KEY_BTAB', curses.KEY_BTAB),
    Key('DC', b'KEY_DC', curses.KEY_DC),
    Key('BSpace', b'KEY_BACKSPACE', curses.KEY_BACKSPACE),
    Key('Up', b'KEY_UP', curses.KEY_UP),
    Key('Down', b'KEY_DOWN', curses.KEY_DOWN),
    Key('Right', b'KEY_RIGHT', curses.KEY_RIGHT),
    Key('Left', b'KEY_LEFT', curses.KEY_LEFT),
    Key('Home', b'KEY_HOME', curses.KEY_HOME),
    Key('End', b'KEY_END', curses.KEY_END),
    Key('PageUp', b'KEY_PPAGE', curses.KEY_PPAGE),
    Key('PageDown', b'KEY_NPAGE', curses.KEY_NPAGE),
    Key('^Up', b'kUP5', 566),
    Key('^Down', b'kDN5', 525),
    Key('^Right', b'kRIT5', 560),
    Key('^Left', b'kLFT5', 545),
    Key('^Home', b'kHOM5', 535),
    Key('^End', b'kEND5', 530),
    Key('M-Right', b'kRIT3', 558),
    Key('M-Left', b'kLFT3', 543),
    Key('S-Up', b'KEY_SR', curses.KEY_SR),
    Key('S-Down', b'KEY_SF', curses.KEY_SF),
    Key('S-Right', b'KEY_SRIGHT', curses.KEY_SRIGHT),
    Key('S-Left', b'KEY_SLEFT', curses.KEY_SLEFT),
    Key('S-Home', b'KEY_SHOME', curses.KEY_SHOME),
    Key('S-End', b'KEY_SEND', curses.KEY_SEND),
    Key('^A', b'^A', '\x01'),
    Key('^C', b'^C', '\x03'),
    Key('^H', b'^H', '\x08'),
    Key('^K', b'^K', '\x0b'),
    Key('^E', b'^E', '\x05'),
    Key('^J', b'^J', '\n'),
    Key('^O', b'^O', '\x0f'),
    Key('^P', b'^P', '\x10'),
    Key('^R', b'^R', '\x12'),
    Key('^S', b'^S', '\x13'),
    Key('^U', b'^U', '\x15'),
    Key('^V', b'^V', '\x16'),
    Key('^W', b'^W', '\x17'),
    Key('^X', b'^X', '\x18'),
    Key('^Y', b'^Y', '\x19'),
    Key('^[', b'^[', '\x1b'),
    Key('^_', b'^_', '\x1f'),
    Key('^\\', b'^\\', '\x1c'),
    Key('!resize', b'KEY_RESIZE', curses.KEY_RESIZE),
]
KEYS_TMUX = {k.tmux: k.wch for k in KEYS}
KEYS_CURSES = {k.value: k.curses for k in KEYS}


class DeferredRunner:
    def __init__(self, command, width=80, height=24, term='screen'):
        self.command = command
        self._i = 0
        self._ops: List[Op] = []
        self.color_pairs = {0: (7, 0)}
        self.screen = Screen(width, height)
        self._n_colors, self._can_change_color = {
            'screen': (8, False),
            'screen-256color': (256, False),
            'xterm-256color': (256, True),
        }[term]

    def _get_wch(self):
        while not isinstance(self._ops[self._i], KeyPress):
            self._i += 1
            try:
                self._ops[self._i - 1](self.screen)
            except AssertionError:  # pragma: no cover (only on failures)
                self.screen.screenshot()
                raise
        self._i += 1
        keypress_event = self._ops[self._i - 1]
        assert isinstance(keypress_event, KeyPress)
        print(f'KEY: {keypress_event.wch!r}')
        return keypress_event.wch

    def await_text(self, text, timeout=1):
        self._ops.append(AwaitText(text))

    def await_text_missing(self, text):
        self._ops.append(AwaitTextMissing(text))

    def await_cursor_position(self, *, x, y):
        self._ops.append(AwaitCursorPosition(x, y))

    def assert_cursor_line_equals(self, line):
        self._ops.append(AssertCursorLineEquals(line))

    def assert_screen_line_equals(self, n, line):
        self._ops.append(AssertScreenLineEquals(n, line))

    def assert_screen_attr_equals(self, n, attr):
        self._ops.append(AssertScreenAttrEquals(n, attr))

    def assert_full_contents(self, contents):
        self._ops.append(AssertFullContents(contents))

    def run(self, callback):
        self._ops.append(lambda screen: callback())

    def _expand_key(self, s):
        if s == 'Escape':
            return [KeyPress('\x1b'), CursesError()]
        elif s in KEYS_TMUX:
            return [KeyPress(KEYS_TMUX[s])]
        elif s.startswith('^') and len(s) > 1 and s[1].isupper():
            raise AssertionError(f'unknown key {s}')
        elif s.startswith('M-'):
            return [KeyPress('\x1b'), KeyPress(s[2:]), CursesError()]
        else:
            return [*(KeyPress(k) for k in s), CursesError()]

    def press(self, s):
        self._ops.extend(self._expand_key(s))

    def press_and_enter(self, s):
        self.press(s)
        self.press('Enter')

    def press_sequence(self, *ks):
        for k in ks:
            for op in self._expand_key(k):
                if not isinstance(op, CursesError):
                    self._ops.append(op)
        self._ops.append(CursesError())

    def answer_no_if_modified(self):
        self.press('n')

    @contextlib.contextmanager
    def resize(self, *, width, height):
        orig_width, orig_height = self.screen.width, self.screen.height
        self._ops.append(Resize(width, height))
        self._ops.append(KeyPress(curses.KEY_RESIZE))
        try:
            yield
        finally:
            self._ops.append(Resize(orig_width, orig_height))
            self._ops.append(KeyPress(curses.KEY_RESIZE))

    def _curses__noop(self, *_, **__):
        pass

    _curses_cbreak = _curses_endwin = _curses_noecho = _curses__noop
    _curses_nonl = _curses_raw = _curses_use_default_colors = _curses__noop

    _curses_error = curses.error  # so we don't mock the exception

    def _curses_keyname(self, k):
        return KEYS_CURSES.get(k, b'')

    def _curses_update_lines_cols(self):
        curses.LINES = self.screen.height
        curses.COLS = self.screen.width

    def _curses_start_color(self):
        curses.COLORS = self._n_colors

    def _curses_can_change_color(self):
        return self._can_change_color

    def _curses_init_pair(self, pair, fg, bg):
        self.color_pairs[pair] = (fg, bg)

    def _curses_color_pair(self, pair):
        assert pair in self.color_pairs
        return pair << 8

    def _curses_initscr(self):
        self._curses_update_lines_cols()
        return CursesScreen(self.screen, self)

    def _curses_newwin(self, height, width):
        return CursesScreen(Screen(width, height), self)

    def _curses_not_implemented(self, fn):
        def fn_inner(*args, **kwargs):
            raise NotImplementedError(fn)
        return fn_inner

    def _patch_curses(self):
        patches = {
            k: getattr(self, f'_curses_{k}', self._curses_not_implemented(k))
            for k in dir(curses)
            if not k.startswith('_') and callable(getattr(curses, k))
        }
        return mock.patch.multiple(curses, **patches)

    def await_exit(self):
        with self._patch_curses():
            main(self.command)
        # we have already exited -- check remaining things
        # KeyPress with failing condition or error
        for i in range(self._i, len(self._ops)):
            if self._ops[i] not in {KeyPress('n'), CursesError()}:
                raise AssertionError(self._ops[i:])


@contextlib.contextmanager
def run_fake(*cmd, **kwargs):
    h = DeferredRunner(cmd, **kwargs)
    h.await_text(VERSION_STR)
    yield h


@contextlib.contextmanager
def run_tmux(*args, term='screen', **kwargs):
    cmd = (sys.executable, '-mcoverage', 'run', '-m', 'babi', *args)
    cmd = ('env', f'TERM={term}', *cmd)
    with PrintsErrorRunner(*cmd, **kwargs) as h, h.on_error():
        # startup with coverage can be slow
        h.await_text(VERSION_STR, timeout=2)
        yield h


@pytest.fixture(
    scope='session',
    params=[run_fake, run_tmux],
    ids=['fake', 'tmux'],
)
def run(request):
    return request.param


@pytest.fixture(scope='session', params=[run_fake], ids=['fake'])
def run_only_fake(request):
    return request.param
