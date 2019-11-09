import argparse
import collections
import contextlib
import curses
import enum
import hashlib
import io
import os
import signal
from typing import Dict
from typing import Generator
from typing import IO
from typing import List
from typing import NamedTuple
from typing import NewType
from typing import Optional
from typing import Tuple
from typing import Union

VERSION_STR = 'babi v0'
CursesWindowType = NewType('CursesWindowType', 'curses._CursesWindow')

def _line_x(x: int, width: int) -> int:
    margin = min(width - 3, 6)
    if x + 1 < width:
        return 0
    elif width == 1:
        return x
    else:
        return (
            width - margin - 2 +
            (x + 1 - width) //
            (width - margin - 2) *
            (width - margin - 2)
        )


def _scrolled_line(s: str, x: int, width: int, *, current: bool) -> str:
    line_x = _line_x(x, width)
    if current and line_x:
        s = f'«{s[line_x + 1:]}'
        if line_x and len(s) > width:
            return f'{s[:width - 1]}»'
        else:
            return s.ljust(width)
    elif len(s) > width:
        return f'{s[:width - 1]}»'
    else:
        return s.ljust(width)


class Margin(NamedTuple):
    header: bool
    footer: bool

    @property
    def body_lines(self) -> int:
        return curses.LINES - self.header - self.footer

    @property
    def page_size(self) -> int:
        if self.body_lines <= 2:
            return 1
        else:
            return self.body_lines - 2

    @classmethod
    def from_screen(cls, screen: CursesWindowType) -> 'Margin':
        if curses.LINES == 1:
            return cls(header=False, footer=False)
        elif curses.LINES == 2:
            return cls(header=False, footer=True)
        else:
            return cls(header=True, footer=True)


def _get_color_pair_mapping() -> Dict[Tuple[int, int], int]:
    ret = {}
    i = 0
    for bg in range(-1, 16):
        for fg in range(bg, 16):
            ret[(fg, bg)] = i
            i += 1
    return ret


COLORS = _get_color_pair_mapping()
del _get_color_pair_mapping


def _has_colors() -> bool:
    return curses.has_colors and curses.COLORS >= 16


def _color(fg: int, bg: int) -> int:
    if _has_colors():
        if bg > fg:
            return curses.A_REVERSE | curses.color_pair(COLORS[(bg, fg)])
        else:
            return curses.color_pair(COLORS[(fg, bg)])
    else:
        if bg > fg:
            return curses.A_REVERSE | curses.color_pair(0)
        else:
            return curses.color_pair(0)


def _init_colors(stdscr: CursesWindowType) -> None:
    curses.use_default_colors()
    if not _has_colors():
        return
    for (fg, bg), pair in COLORS.items():
        if pair == 0:  # cannot reset pair 0
            continue
        curses.init_pair(pair, fg, bg)


class Status:
    def __init__(self) -> None:
        self._status = ''
        self._action_counter = -1

    def update(self, status: str) -> None:
        self._status = status
        self._action_counter = 25

    def draw(self, stdscr: CursesWindowType, margin: Margin) -> None:
        if margin.footer or self._status:
            stdscr.insstr(curses.LINES - 1, 0, ' ' * curses.COLS)
            if self._status:
                status = f' {self._status} '
                x = (curses.COLS - len(status)) // 2
                if x < 0:
                    x = 0
                    status = status.strip()
                stdscr.insstr(curses.LINES - 1, x, status, curses.A_REVERSE)

    def tick(self, margin: Margin) -> None:
        # when the window is only 1-tall, hide the status quicker
        if margin.footer:
            self._action_counter -= 1
        else:
            self._action_counter -= 24
        if self._action_counter < 0:
            self._status = ''

    def prompt(self, screen: 'Screen', prompt: str) -> str:
        pos = 0
        buf = ''
        while True:
            width = curses.COLS - len(prompt)
            cmd = f'{prompt}{_scrolled_line(buf, pos, width, current=True)}'
            screen.stdscr.insstr(curses.LINES - 1, 0, cmd, curses.A_REVERSE)
            line_x = _line_x(pos, width)
            screen.stdscr.move(curses.LINES - 1, pos - line_x)
            key = _get_char(screen.stdscr)

            if key.key == curses.KEY_RESIZE:
                screen.resize()
            elif key.key == curses.KEY_LEFT:
                pos = max(0, pos - 1)
            elif key.key == curses.KEY_RIGHT:
                pos = min(len(buf), pos + 1)
            elif key.key == curses.KEY_HOME or key.keyname == b'^A':
                pos = 0
            elif key.key == curses.KEY_END or key.keyname == b'^E':
                pos = len(buf)
            elif key.key == curses.KEY_BACKSPACE:
                if pos > 0:
                    buf = buf[:pos - 1] + buf[pos:]
                    pos -= 1
            elif key.key == curses.KEY_DC:
                if pos < len(buf):
                    buf = buf[:pos] + buf[pos + 1:]
            elif isinstance(key.wch, str) and key.wch.isprintable():
                buf = buf[:pos] + key.wch + buf[pos:]
                pos += 1
            elif key.keyname == b'^C':
                return ''
            elif key.key == ord('\r'):
                return buf


def _restore_lines_eof_invariant(lines: List[str]) -> None:
    """The file lines will always contain a blank empty string at the end to
    simplify rendering.  This should be called whenever the end of the file
    might change.
    """
    if not lines or lines[-1] != '':
        lines.append('')


def _get_lines(sio: IO[str]) -> Tuple[List[str], str, bool, str]:
    sha256 = hashlib.sha256()
    lines = []
    newlines = collections.Counter({'\n': 0})  # default to `\n`
    for line in sio:
        sha256.update(line.encode())
        for ending in ('\r\n', '\n'):
            if line.endswith(ending):
                lines.append(line[:-1 * len(ending)])
                newlines[ending] += 1
                break
        else:
            lines.append(line)
    _restore_lines_eof_invariant(lines)
    (nl, _), = newlines.most_common(1)
    mixed = len({k for k, v in newlines.items() if v}) > 1
    return lines, nl, mixed, sha256.hexdigest()


class File:
    def __init__(self, filename: Optional[str]) -> None:
        self.filename = filename
        self.modified = False
        self.lines: List[str] = []
        self.nl = '\n'
        self.file_line = self.cursor_line = self.x = self.x_hint = 0
        self.sha256: Optional[str] = None

    def ensure_loaded(self, status: Status) -> None:
        if self.lines:
            return

        if self.filename is not None and os.path.isfile(self.filename):
            with open(self.filename, newline='') as f:
                self.lines, self.nl, mixed, self.sha256 = _get_lines(f)
        else:
            if self.filename is not None:
                if os.path.lexists(self.filename):
                    status.update(f'{self.filename!r} is not a file')
                    self.filename = None
                else:
                    status.update('(new file)')
            sio = io.StringIO('')
            self.lines, self.nl, mixed, self.sha256 = _get_lines(sio)

        if mixed:
            status.update(f'mixed newlines will be converted to {self.nl!r}')
            self.modified = True

    def __repr__(self) -> str:
        attrs = ',\n    '.join(f'{k}={v!r}' for k, v in self.__dict__.items())
        return f'{type(self).__name__}(\n    {attrs},\n)'

    # movement

    def _scroll_amount(self) -> int:
        return int(curses.LINES / 2 + .5)

    def _set_x_after_vertical_movement(self) -> None:
        self.x = min(len(self.lines[self.cursor_line]), self.x_hint)

    def maybe_scroll_down(self, margin: Margin) -> None:
        if self.cursor_line >= self.file_line + margin.body_lines:
            self.file_line += self._scroll_amount()

    def down(self, margin: Margin) -> None:
        if self.cursor_line < len(self.lines) - 1:
            self.cursor_line += 1
            self.maybe_scroll_down(margin)
            self._set_x_after_vertical_movement()

    def maybe_scroll_up(self, margin: Margin) -> None:
        if self.cursor_line < self.file_line:
            self.file_line -= self._scroll_amount()
            self.file_line = max(self.file_line, 0)

    def up(self, margin: Margin) -> None:
        if self.cursor_line > 0:
            self.cursor_line -= 1
            self.maybe_scroll_up(margin)
            self._set_x_after_vertical_movement()

    def right(self, margin: Margin) -> None:
        if self.x >= len(self.lines[self.cursor_line]):
            if self.cursor_line < len(self.lines) - 1:
                self.x = 0
                self.cursor_line += 1
                self.maybe_scroll_down(margin)
        else:
            self.x += 1
        self.x_hint = self.x

    def left(self, margin: Margin) -> None:
        if self.x == 0:
            if self.cursor_line > 0:
                self.cursor_line -= 1
                self.x = len(self.lines[self.cursor_line])
                self.maybe_scroll_up(margin)
        else:
            self.x -= 1
        self.x_hint = self.x

    def home(self, margin: Margin) -> None:
        self.x = self.x_hint = 0

    def end(self, margin: Margin) -> None:
        self.x = self.x_hint = len(self.lines[self.cursor_line])

    def ctrl_home(self, margin: Margin) -> None:
        self.x = self.x_hint = 0
        self.cursor_line = self.file_line = 0

    def ctrl_end(self, margin: Margin) -> None:
        self.x = self.x_hint = 0
        self.cursor_line = len(self.lines) - 1
        if self.file_line < self.cursor_line - margin.body_lines:
            self.file_line = self.cursor_line - margin.body_lines * 3 // 4 + 1

    def page_up(self, margin: Margin) -> None:
        if self.cursor_line < margin.body_lines:
            self.cursor_line = self.file_line = 0
        else:
            pos = max(self.file_line - margin.page_size, 0)
            self.cursor_line = self.file_line = pos
        self._set_x_after_vertical_movement()

    def page_down(self, margin: Margin) -> None:
        if self.file_line + margin.body_lines >= len(self.lines):
            self.cursor_line = len(self.lines) - 1
        else:
            pos = self.file_line + margin.page_size
            self.cursor_line = self.file_line = pos
        self._set_x_after_vertical_movement()

    # editing

    def backspace(self, margin: Margin) -> None:
        # backspace at the beginning of the file does nothing
        if self.cursor_line == 0 and self.x == 0:
            pass
        # at the beginning of the line, we join the current line and
        # the previous line
        elif self.x == 0:
            victim = self.lines.pop(self.cursor_line)
            new_x = len(self.lines[self.cursor_line - 1])
            self.lines[self.cursor_line - 1] += victim
            self.up(margin)
            self.x = self.x_hint = new_x
            # deleting the fake end-of-file doesn't cause modification
            self.modified |= self.cursor_line < len(self.lines) - 1
            _restore_lines_eof_invariant(self.lines)
        else:
            s = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = s[:self.x - 1] + s[self.x:]
            self.left(margin)
            self.modified = True

    def delete(self, margin: Margin) -> None:
        # noop at end of the file
        if self.cursor_line == len(self.lines) - 1:
            pass
        # if we're at the end of the line, collapse the line afterwards
        elif self.x == len(self.lines[self.cursor_line]):
            self.lines[self.cursor_line] += self.lines[self.cursor_line + 1]
            self.lines.pop(self.cursor_line + 1)
            self.modified = True
        else:
            s = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = s[:self.x] + s[self.x + 1:]
            self.modified = True

    def enter(self, margin: Margin) -> None:
        s = self.lines[self.cursor_line]
        self.lines[self.cursor_line] = s[:self.x]
        self.lines.insert(self.cursor_line + 1, s[self.x:])
        self.down(margin)
        self.x = self.x_hint = 0
        self.modified = True

    DISPATCH = {
        # movement
        curses.KEY_DOWN: down,
        curses.KEY_UP: up,
        curses.KEY_LEFT: left,
        curses.KEY_RIGHT: right,
        curses.KEY_HOME: home,
        curses.KEY_END: end,
        curses.KEY_PPAGE: page_up,
        curses.KEY_NPAGE: page_down,
        # editing
        curses.KEY_BACKSPACE: backspace,
        curses.KEY_DC: delete,
        ord('\r'): enter,
    }
    DISPATCH_KEY = {
        # movement
        b'^A': home,
        b'^E': end,
        b'^Y': page_up,
        b'^V': page_down,
        b'kHOM5': ctrl_home,
        b'kEND5': ctrl_end,
    }

    def c(self, wch: str, margin: Margin) -> None:
        s = self.lines[self.cursor_line]
        self.lines[self.cursor_line] = s[:self.x] + wch + s[self.x:]
        self.right(margin)
        self.modified = True
        _restore_lines_eof_invariant(self.lines)

    def save(self, status: Status) -> None:
        # TODO: make directories if they don't exist
        # TODO: maybe use mtime / stat as a shortcut for hashing below
        # TODO: strip trailing whitespace?
        # TODO: save atomically?
        if self.filename is None:
            status.update('(no filename, not implemented)')
            return

        if os.path.isfile(self.filename):
            with open(self.filename) as f:
                *_, sha256 = _get_lines(f)
        else:
            sha256 = hashlib.sha256(b'').hexdigest()

        contents = self.nl.join(self.lines)
        sha256_to_save = hashlib.sha256(contents.encode()).hexdigest()

        # the file on disk is the same as when we opened it
        if sha256 not in (self.sha256, sha256_to_save):
            status.update('(file changed on disk, not implemented)')
            return

        with open(self.filename, 'w') as f:
            f.write(contents)

        self.modified = False
        self.sha256 = sha256_to_save
        num_lines = len(self.lines) - 1
        lines = 'lines' if num_lines != 1 else 'line'
        status.update(f'saved! ({num_lines} {lines} written)')

    # positioning

    def cursor_y(self, margin: Margin) -> int:
        return self.cursor_line - self.file_line + margin.header

    def line_x(self) -> int:
        return _line_x(self.x, curses.COLS)

    def cursor_x(self) -> int:
        return self.x - self.line_x()

    def move_cursor(
            self,
            stdscr: CursesWindowType,
            margin: Margin,
    ) -> None:
        stdscr.move(self.cursor_y(margin), self.cursor_x())

    def draw(self, stdscr: CursesWindowType, margin: Margin) -> None:
        to_display = min(len(self.lines) - self.file_line, margin.body_lines)
        for i in range(to_display):
            line_idx = self.file_line + i
            line = self.lines[line_idx]
            current = line_idx == self.cursor_line
            line = _scrolled_line(line, self.x, curses.COLS, current=current)
            stdscr.insstr(i + margin.header, 0, line)
        blankline = ' ' * curses.COLS
        for i in range(to_display, margin.body_lines):
            stdscr.insstr(i + margin.header, 0, blankline)


class Screen:
    def __init__(
            self,
            stdscr: CursesWindowType,
            files: List[File],
    ) -> None:
        self.stdscr = stdscr
        self.files = files
        self.i = 0
        self.status = Status()
        self.margin = Margin.from_screen(self.stdscr)
        self.cut_buffer = ''

    @property
    def file(self) -> File:
        return self.files[self.i]

    def _draw_header(self) -> None:
        filename = self.file.filename or '<<new file>>'
        if self.file.modified:
            filename += ' *'
        if len(self.files) > 1:
            files = f'[{self.i + 1}/{len(self.files)}] '
            version_width = len(VERSION_STR) + 2 + len(files)
        else:
            files = ''
            version_width = len(VERSION_STR) + 2
        centered = filename.center(curses.COLS)[version_width:]
        s = f' {VERSION_STR} {files}{centered}{files}'
        self.stdscr.insstr(0, 0, s, curses.A_REVERSE)

    def draw(self) -> None:
        if self.margin.header:
            self._draw_header()
        self.file.draw(self.stdscr, self.margin)
        self.status.draw(self.stdscr, self.margin)

    def resize(self) -> None:
        curses.update_lines_cols()
        self.margin = Margin.from_screen(self.stdscr)
        self.file.maybe_scroll_down(self.margin)
        self.draw()


def _color_test(stdscr: CursesWindowType) -> None:
    header = f' {VERSION_STR}'
    header += '<< color test >>'.center(curses.COLS)[len(header):]
    stdscr.insstr(0, 0, header, curses.A_REVERSE)

    maxy, maxx = stdscr.getmaxyx()
    if maxy < 19 or maxx < 68:  # pragma: no cover (will be deleted)
        raise SystemExit('--color-test needs a window of at least 68 x 19')

    y = 1
    for fg in range(-1, 16):
        x = 0
        for bg in range(-1, 16):
            if bg > fg:
                s = f'*{COLORS[bg, fg]:3}'
            else:
                s = f' {COLORS[fg, bg]:3}'
            stdscr.addstr(y, x, s, _color(fg, bg))
            x += 4
        y += 1
    stdscr.get_wch()


class Key(NamedTuple):
    wch: Union[int, str]
    key: int
    keyname: bytes


# TODO: find a place to populate these, surely there's a database somewhere
SEQUENCE_KEY = {
    '\x1bOH': curses.KEY_HOME,
    '\x1bOF': curses.KEY_END,
}
SEQUENCE_KEYNAME = {
    '\x1b[1;5H': b'kHOM5',  # C-Home
    '\x1b[1;5F': b'kEND5',  # C-End
    '\x1bOH': b'KEY_HOME',
    '\x1bOF': b'KEY_END',
    '\x1b[1;3A': b'kUP3',  # M-Up
    '\x1b[1;3B': b'kDN3',  # M-Down
    '\x1b[1;3C': b'kRIT3',  # M-Right
    '\x1b[1;3D': b'kLFT3',  # M-Left
}


def _get_char(stdscr: CursesWindowType) -> Key:
    wch = stdscr.get_wch()
    if isinstance(wch, str) and wch == '\x1b':
        stdscr.nodelay(True)
        try:
            while True:
                try:
                    new_wch = stdscr.get_wch()
                    if isinstance(new_wch, str):
                        wch += new_wch
                    else:  # pragma: no cover (impossible?)
                        curses.unget_wch(new_wch)
                        break
                except curses.error:
                    break
        finally:
            stdscr.nodelay(False)

        if len(wch) > 1:
            key = SEQUENCE_KEY.get(wch, -1)
            keyname = SEQUENCE_KEYNAME.get(wch, b'unknown')
            return Key(wch, key, keyname)
    elif wch == '\x7f':  # pragma: no cover (macos)
        key = curses.KEY_BACKSPACE
        keyname = curses.keyname(key)
        return Key(wch, key, keyname)

    key = wch if isinstance(wch, int) else ord(wch)
    keyname = curses.keyname(key)
    return Key(wch, key, keyname)


EditResult = enum.Enum('EditResult', 'EXIT NEXT PREV')


def _edit(screen: Screen) -> EditResult:
    prevkey = Key('', 0, b'')
    screen.file.ensure_loaded(screen.status)

    while True:
        screen.status.tick(screen.margin)

        screen.draw()
        screen.file.move_cursor(screen.stdscr, screen.margin)

        key = _get_char(screen.stdscr)

        if key.key == curses.KEY_RESIZE:
            screen.resize()
        elif key.key in File.DISPATCH:
            screen.file.DISPATCH[key.key](screen.file, screen.margin)
        elif key.keyname in File.DISPATCH_KEY:
            screen.file.DISPATCH_KEY[key.keyname](screen.file, screen.margin)
        elif key.keyname == b'^K':
            if screen.file.file_line == len(screen.file.lines) - 1:
                screen.cut_buffer = ''
            else:
                line = screen.file.lines[screen.file.cursor_line] + '\n'
                if prevkey.keyname == b'^K':
                    screen.cut_buffer += line
                else:
                    screen.cut_buffer = line
                del screen.file.lines[screen.file.cursor_line]
                screen.file.x = screen.file.x_hint = 0
                screen.file.modified = True
        elif key.keyname == b'^U':
            for c in screen.cut_buffer:
                if c == '\n':
                    screen.file.enter(screen.margin)
                else:
                    screen.file.c(c, screen.margin)
        elif key.keyname == b'^[':  # escape
            response = screen.status.prompt(screen, '')
            
