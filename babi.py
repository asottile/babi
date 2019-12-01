import argparse
import collections
import contextlib
import curses
import enum
import functools
import hashlib
import io
import os
import re
import signal
import sys
from typing import Any
from typing import Callable
from typing import cast
from typing import Dict
from typing import Generator
from typing import IO
from typing import Iterator
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Pattern
from typing import Tuple
from typing import TYPE_CHECKING
from typing import TypeVar
from typing import Union

if TYPE_CHECKING:
    from typing import Protocol  # python3.8+
else:
    Protocol = object

VERSION_STR = 'babi v0'
TCallable = TypeVar('TCallable', bound=Callable[..., Any])


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


class MutableSequenceNoSlice(Protocol):
    def __len__(self) -> int: ...
    def __getitem__(self, idx: int) -> str: ...
    def __setitem__(self, idx: int, val: str) -> None: ...
    def __delitem__(self, idx: int) -> None: ...
    def insert(self, idx: int, val: str) -> None: ...

    def __iter__(self) -> Iterator[str]:
        for i in range(len(self)):
            yield self[i]

    def append(self, val: str) -> None:
        self.insert(len(self), val)

    def pop(self, idx: int = -1) -> str:
        victim = self[idx]
        del self[idx]
        return victim


def _del(lst: MutableSequenceNoSlice, *, idx: int) -> None:
    del lst[idx]


def _set(lst: MutableSequenceNoSlice, *, idx: int, val: str) -> None:
    lst[idx] = val


def _ins(lst: MutableSequenceNoSlice, *, idx: int, val: str) -> None:
    lst.insert(idx, val)


class ListSpy(MutableSequenceNoSlice):
    def __init__(self, lst: MutableSequenceNoSlice) -> None:
        self._lst = lst
        self._undo: List[Callable[[MutableSequenceNoSlice], None]] = []

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self._lst})'

    def __len__(self) -> int:
        return len(self._lst)

    def __getitem__(self, idx: int) -> str:
        return self._lst[idx]

    def __setitem__(self, idx: int, val: str) -> None:
        self._undo.append(functools.partial(_set, idx=idx, val=self._lst[idx]))
        self._lst[idx] = val

    def __delitem__(self, idx: int) -> None:
        if idx < 0:
            idx %= len(self)
        self._undo.append(functools.partial(_ins, idx=idx, val=self._lst[idx]))
        del self._lst[idx]

    def insert(self, idx: int, val: str) -> None:
        if idx < 0:
            idx %= len(self)
        self._undo.append(functools.partial(_del, idx=idx))
        self._lst.insert(idx, val)

    def undo(self, lst: MutableSequenceNoSlice) -> None:
        for fn in reversed(self._undo):
            fn(lst)

    @property
    def has_modifications(self) -> bool:
        return bool(self._undo)


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
    def from_screen(cls, screen: 'curses._CursesWindow') -> 'Margin':
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


def _init_colors(stdscr: 'curses._CursesWindow') -> None:
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
        self._history: Dict[str, List[str]] = collections.defaultdict(list)
        self._history_orig_len: Dict[str, int] = {}

    @contextlib.contextmanager
    def save_history(self) -> Generator[None, None, None]:
        history_dir = os.path.join(
            os.environ.get('XDG_DATA_HOME') or
            os.path.expanduser('~/.local/share'),
            'babi/history',
        )
        os.makedirs(history_dir, exist_ok=True)
        for filename in os.listdir(history_dir):
            with open(os.path.join(history_dir, filename)) as f:
                self._history[filename] = f.read().splitlines()
                self._history_orig_len[filename] = len(self._history[filename])
        try:
            yield
        finally:
            for k, v in self._history.items():
                with open(os.path.join(history_dir, k), 'a+') as f:
                    f.write('\n'.join(v[self._history_orig_len[k]:]) + '\n')

    def update(self, status: str) -> None:
        self._status = status
        self._action_counter = 25

    def clear(self) -> None:
        self._status = ''

    def draw(self, stdscr: 'curses._CursesWindow', margin: Margin) -> None:
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
            self.clear()

    def prompt(
            self,
            screen: 'Screen',
            prompt: str,
            *,
            history: Optional[str] = None,
    ) -> str:
        self.clear()
        if history is not None:
            lst = [*self._history[history], '']
            lst_pos = len(lst) - 1
        else:
            lst = ['']
            lst_pos = 0
        pos = 0

        def buf() -> str:
            return lst[lst_pos]

        def set_buf(s: str) -> None:
            lst[lst_pos] = s

        def _save_history_entry() -> None:
            if history is not None:
                history_lst = self._history[history]
                if not history_lst or history_lst[-1] != lst[lst_pos]:
                    history_lst.append(lst[lst_pos])

        def _render_prompt(*, base: str = prompt) -> None:
            if not base or curses.COLS < 7:
                prompt_s = ''
            elif len(base) > curses.COLS - 6:
                prompt_s = f'{base[:curses.COLS - 7]}…: '
            else:
                prompt_s = f'{base}: '
            width = curses.COLS - len(prompt_s)
            line = _scrolled_line(lst[lst_pos], pos, width, current=True)
            cmd = f'{prompt_s}{line}'
            screen.stdscr.insstr(curses.LINES - 1, 0, cmd, curses.A_REVERSE)
            line_x = _line_x(pos, width)
            screen.stdscr.move(curses.LINES - 1, len(prompt_s) + pos - line_x)

        while True:
            _render_prompt()
            key = _get_char(screen.stdscr)

            if key.key == curses.KEY_RESIZE:
                screen.resize()
            elif key.key == curses.KEY_LEFT:
                pos = max(0, pos - 1)
            elif key.key == curses.KEY_RIGHT:
                pos = min(len(lst[lst_pos]), pos + 1)
            elif key.key == curses.KEY_UP:
                lst_pos = max(0, lst_pos - 1)
                pos = len(lst[lst_pos])
            elif key.key == curses.KEY_DOWN:
                lst_pos = min(len(lst) - 1, lst_pos + 1)
                pos = len(lst[lst_pos])
            elif key.key == curses.KEY_HOME or key.keyname == b'^A':
                pos = 0
            elif key.key == curses.KEY_END or key.keyname == b'^E':
                pos = len(lst[lst_pos])
            elif key.key == curses.KEY_BACKSPACE:
                if pos > 0:
                    set_buf(buf()[:pos - 1] + buf()[pos:])
                    pos -= 1
            elif key.key == curses.KEY_DC:
                if pos < len(lst[lst_pos]):
                    set_buf(buf()[:pos] + buf()[pos + 1:])
            elif isinstance(key.wch, str) and key.wch.isprintable():
                set_buf(buf()[:pos] + key.wch + buf()[pos:])
                pos += 1
            elif key.keyname == b'^R':
                reverse_s = ''
                reverse_idx = lst_pos
                while True:
                    reverse_failed = False
                    for search_idx in range(reverse_idx, -1, -1):
                        if reverse_s in lst[search_idx]:
                            reverse_idx = lst_pos = search_idx
                            pos = len(buf())
                            break
                    else:
                        reverse_failed = True

                    if reverse_failed:
                        base = f'{prompt}(failed reverse-search)`{reverse_s}`'
                    else:
                        base = f'{prompt}(reverse-search)`{reverse_s}`'

                    _render_prompt(base=base)
                    key = _get_char(screen.stdscr)

                    if key.key == curses.KEY_RESIZE:
                        screen.resize()
                    elif key.key == curses.KEY_BACKSPACE:
                        reverse_s = reverse_s[:-1]
                    elif isinstance(key.wch, str) and key.wch.isprintable():
                        reverse_s += key.wch
                    elif key.keyname == b'^R':
                        reverse_idx = max(0, reverse_idx - 1)
                    elif key.keyname == b'^C':
                        return ''
                    elif key.key == ord('\r'):
                        _save_history_entry()
                        return lst[lst_pos]
                    else:
                        break

            elif key.keyname == b'^C':
                return ''
            elif key.key == ord('\r'):
                _save_history_entry()
                return lst[lst_pos]


def _restore_lines_eof_invariant(lines: MutableSequenceNoSlice) -> None:
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


class Action:
    def __init__(
            self, *, name: str, spy: ListSpy,
            start_x: int, start_y: int, start_modified: bool,
            end_x: int, end_y: int, end_modified: bool,
    ):
        self.name = name
        self.spy = spy
        self.start_x = start_x
        self.start_y = start_y
        self.start_modified = start_modified
        self.end_x = end_x
        self.end_y = end_y
        self.end_modified = end_modified
        self.final = False

    def apply(self, file: 'File') -> 'Action':
        spy = ListSpy(file.lines)
        action = Action(
            name=self.name, spy=spy,
            start_x=self.end_x, start_y=self.end_y,
            start_modified=self.end_modified,
            end_x=self.start_x, end_y=self.start_y,
            end_modified=self.start_modified,
        )

        self.spy.undo(spy)
        file.x = self.start_x
        file.cursor_y = self.start_y
        file.modified = self.start_modified

        return action


def action(func: TCallable) -> TCallable:
    @functools.wraps(func)
    def action_inner(self: 'File', *args: Any, **kwargs: Any) -> Any:
        assert not isinstance(self.lines, ListSpy), 'nested edit/movement'
        if self.undo_stack:
            self.undo_stack[-1].final = True
        return func(self, *args, **kwargs)
    return cast(TCallable, action_inner)


def edit_action(name: str) -> Callable[[TCallable], TCallable]:
    def edit_action_decorator(func: TCallable) -> TCallable:
        @functools.wraps(func)
        def edit_action_inner(self: 'File', *args: Any, **kwargs: Any) -> Any:
            continue_last = (
                self.undo_stack and
                self.undo_stack[-1].name == name and
                not self.undo_stack[-1].final
            )
            if continue_last:
                spy = self.undo_stack[-1].spy
            else:
                if self.undo_stack:
                    self.undo_stack[-1].final = True
                spy = ListSpy(self.lines)

            before_x, before_line = self.x, self.cursor_y
            before_modified = self.modified
            assert not isinstance(self.lines, ListSpy), 'recursive action?'
            orig, self.lines = self.lines, spy
            try:
                return func(self, *args, **kwargs)
            finally:
                self.lines = orig
                self.redo_stack.clear()
                if continue_last:
                    self.undo_stack[-1].end_x = self.x
                    self.undo_stack[-1].end_y = self.cursor_y
                    self.undo_stack[-1].end_modified = self.modified
                elif spy.has_modifications:
                    action = Action(
                        name=name, spy=spy,
                        start_x=before_x, start_y=before_line,
                        start_modified=before_modified,
                        end_x=self.x, end_y=self.cursor_y,
                        end_modified=self.modified,
                    )
                    self.undo_stack.append(action)
        return cast(TCallable, edit_action_inner)
    return edit_action_decorator


class File:
    def __init__(self, filename: Optional[str]) -> None:
        self.filename = filename
        self.modified = False
        self.lines: MutableSequenceNoSlice = []
        self.nl = '\n'
        self.file_y = self.cursor_y = self.x = self.x_hint = 0
        self.sha256: Optional[str] = None
        self.undo_stack: List[Action] = []
        self.redo_stack: List[Action] = []

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

    def _scroll_screen_if_needed(self, margin: Margin) -> None:
        # if the `cursor_y` is not on screen, make it so
        if self.file_y <= self.cursor_y < self.file_y + margin.body_lines:
            return

        self.file_y = max(self.cursor_y - margin.body_lines // 2, 0)

    def _scroll_amount(self) -> int:
        return int(curses.LINES / 2 + .5)

    def _set_x_after_vertical_movement(self) -> None:
        self.x = min(len(self.lines[self.cursor_y]), self.x_hint)

    def maybe_scroll_down(self, margin: Margin) -> None:
        if self.cursor_y >= self.file_y + margin.body_lines:
            self.file_y += self._scroll_amount()

    @action
    def down(self, margin: Margin) -> None:
        if self.cursor_y < len(self.lines) - 1:
            self.cursor_y += 1
            self.maybe_scroll_down(margin)
            self._set_x_after_vertical_movement()

    def _maybe_scroll_up(self, margin: Margin) -> None:
        if self.cursor_y < self.file_y:
            self.file_y -= self._scroll_amount()
            self.file_y = max(self.file_y, 0)

    @action
    def up(self, margin: Margin) -> None:
        if self.cursor_y > 0:
            self.cursor_y -= 1
            self._maybe_scroll_up(margin)
            self._set_x_after_vertical_movement()

    @action
    def right(self, margin: Margin) -> None:
        if self.x >= len(self.lines[self.cursor_y]):
            if self.cursor_y < len(self.lines) - 1:
                self.x = 0
                self.cursor_y += 1
                self.maybe_scroll_down(margin)
        else:
            self.x += 1
        self.x_hint = self.x

    @action
    def left(self, margin: Margin) -> None:
        if self.x == 0:
            if self.cursor_y > 0:
                self.cursor_y -= 1
                self.x = len(self.lines[self.cursor_y])
                self._maybe_scroll_up(margin)
        else:
            self.x -= 1
        self.x_hint = self.x

    @action
    def home(self, margin: Margin) -> None:
        self.x = self.x_hint = 0

    @action
    def end(self, margin: Margin) -> None:
        self.x = self.x_hint = len(self.lines[self.cursor_y])

    @action
    def ctrl_home(self, margin: Margin) -> None:
        self.x = self.x_hint = 0
        self.cursor_y = self.file_y = 0

    @action
    def ctrl_end(self, margin: Margin) -> None:
        self.x = self.x_hint = 0
        self.cursor_y = len(self.lines) - 1
        self._scroll_screen_if_needed(margin)

    @action
    def ctrl_up(self, margin: Margin) -> None:
        self.file_y = max(0, self.file_y - 1)
        self.cursor_y = min(self.cursor_y, self.file_y + margin.body_lines - 1)
        self._set_x_after_vertical_movement()

    @action
    def ctrl_down(self, margin: Margin) -> None:
        self.file_y = min(len(self.lines) - 1, self.file_y + 1)
        self.cursor_y = max(self.cursor_y, self.file_y)
        self._set_x_after_vertical_movement()

    @action
    def go_to_line(self, lineno: int, margin: Margin) -> None:
        self.x = self.x_hint = 0
        if lineno == 0:
            self.cursor_y = 0
        elif lineno > len(self.lines):
            self.cursor_y = len(self.lines) - 1
        elif lineno < 0:
            self.cursor_y = max(0, lineno + len(self.lines))
        else:
            self.cursor_y = lineno - 1
        self._scroll_screen_if_needed(margin)

    @action
    def search(
            self,
            reg: Pattern[str],
            status: Status,
            margin: Margin,
    ) -> None:
        line_y = self.cursor_y
        match = reg.search(self.lines[self.cursor_y], self.x + 1)
        if not match:
            for line_y in range(self.cursor_y + 1, len(self.lines)):
                match = reg.search(self.lines[line_y])
                if match:
                    break
            else:
                status.update('search wrapped')
                for line_y in range(0, self.cursor_y + 1):
                    match = reg.search(self.lines[line_y])
                    if match:
                        break

        if match and line_y == self.cursor_y and match.start() == self.x:
            status.update('this is the only occurrence')
        elif match:
            self.cursor_y = line_y
            self.x = match.start()
            self._scroll_screen_if_needed(margin)
        else:
            status.update('no matches')

    @action
    def page_up(self, margin: Margin) -> None:
        if self.cursor_y < margin.body_lines:
            self.cursor_y = self.file_y = 0
        else:
            pos = max(self.file_y - margin.page_size, 0)
            self.cursor_y = self.file_y = pos
        self._set_x_after_vertical_movement()

    @action
    def page_down(self, margin: Margin) -> None:
        if self.file_y + margin.body_lines >= len(self.lines):
            self.cursor_y = len(self.lines) - 1
        else:
            pos = self.file_y + margin.page_size
            self.cursor_y = self.file_y = pos
        self._set_x_after_vertical_movement()

    # editing

    @edit_action('backspace text')
    def backspace(self, margin: Margin) -> None:
        # backspace at the beginning of the file does nothing
        if self.cursor_y == 0 and self.x == 0:
            pass
        # at the beginning of the line, we join the current line and
        # the previous line
        elif self.x == 0:
            victim = self.lines.pop(self.cursor_y)
            new_x = len(self.lines[self.cursor_y - 1])
            self.lines[self.cursor_y - 1] += victim
            self.cursor_y -= 1
            self._maybe_scroll_up(margin)
            self.x = self.x_hint = new_x
            # deleting the fake end-of-file doesn't cause modification
            self.modified |= self.cursor_y < len(self.lines) - 1
            _restore_lines_eof_invariant(self.lines)
        else:
            s = self.lines[self.cursor_y]
            self.lines[self.cursor_y] = s[:self.x - 1] + s[self.x:]
            self.x = self.x_hint = self.x - 1
            self.modified = True

    @edit_action('delete text')
    def delete(self, margin: Margin) -> None:
        # noop at end of the file
        if self.cursor_y == len(self.lines) - 1:
            pass
        # if we're at the end of the line, collapse the line afterwards
        elif self.x == len(self.lines[self.cursor_y]):
            victim = self.lines.pop(self.cursor_y + 1)
            self.lines[self.cursor_y] += victim
            self.modified = True
        else:
            s = self.lines[self.cursor_y]
            self.lines[self.cursor_y] = s[:self.x] + s[self.x + 1:]
            self.modified = True

    @edit_action('line break')
    def enter(self, margin: Margin) -> None:
        s = self.lines[self.cursor_y]
        self.lines[self.cursor_y] = s[:self.x]
        self.lines.insert(self.cursor_y + 1, s[self.x:])
        self.cursor_y += 1
        self.maybe_scroll_down(margin)
        self.x = self.x_hint = 0
        self.modified = True

    @edit_action('cut')
    def cut(self, cut_buffer: Tuple[str, ...]) -> Tuple[str, ...]:
        if self.cursor_y == len(self.lines) - 1:
            return ()
        else:
            victim = self.lines.pop(self.cursor_y)
            self.x = self.x_hint = 0
            self.modified = True
            return cut_buffer + (victim,)

    @edit_action('uncut')
    def uncut(self, cut_buffer: Tuple[str, ...], margin: Margin) -> None:
        for cut_line in cut_buffer:
            line = self.lines[self.cursor_y]
            before, after = line[:self.x], line[self.x:]
            self.lines[self.cursor_y] = before + cut_line
            self.lines.insert(self.cursor_y + 1, after)
            self.cursor_y += 1
            self.x = self.x_hint = 0
            self.maybe_scroll_down(margin)

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
        b'kUP5': ctrl_up,
        b'kDN5': ctrl_down,
    }

    @edit_action('text')
    def c(self, wch: str, margin: Margin) -> None:
        s = self.lines[self.cursor_y]
        self.lines[self.cursor_y] = s[:self.x] + wch + s[self.x:]
        self.x = self.x_hint = self.x + 1
        self.modified = True
        _restore_lines_eof_invariant(self.lines)

    def _undo_redo(
            self,
            op: str,
            from_stack: List[Action],
            to_stack: List[Action],
            status: Status,
            margin: Margin,
    ) -> None:
        if not from_stack:
            status.update(f'nothing to {op}!')
        else:
            action = from_stack.pop()
            to_stack.append(action.apply(self))
            self._scroll_screen_if_needed(margin)
            status.update(f'{op}: {action.name}')

    def undo(self, status: Status, margin: Margin) -> None:
        self._undo_redo(
            'undo', self.undo_stack, self.redo_stack, status, margin,
        )

    def redo(self, status: Status, margin: Margin) -> None:
        self._undo_redo(
            'redo', self.redo_stack, self.undo_stack, status, margin,
        )

    @action
    def save(self, screen: 'Screen', status: Status) -> None:
        # TODO: make directories if they don't exist
        # TODO: maybe use mtime / stat as a shortcut for hashing below
        # TODO: strip trailing whitespace?
        # TODO: save atomically?
        if self.filename is None:
            filename = status.prompt(screen, 'enter filename')
            if not filename:
                status.update('cancelled')
                return
            else:
                self.filename = filename

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

        # fix up modified state in undo / redo stacks
        for stack in (self.undo_stack, self.redo_stack):
            first = True
            for action in reversed(stack):
                action.end_modified = not first
                action.start_modified = True
                first = False

    # positioning

    def move_cursor(
            self,
            stdscr: 'curses._CursesWindow',
            margin: Margin,
    ) -> None:
        y = self.cursor_y - self.file_y + margin.header
        x = self.x - _line_x(self.x, curses.COLS)
        stdscr.move(y, x)

    def draw(self, stdscr: 'curses._CursesWindow', margin: Margin) -> None:
        to_display = min(len(self.lines) - self.file_y, margin.body_lines)
        for i in range(to_display):
            line_idx = self.file_y + i
            line = self.lines[line_idx]
            current = line_idx == self.cursor_y
            line = _scrolled_line(line, self.x, curses.COLS, current=current)
            stdscr.insstr(i + margin.header, 0, line)
        blankline = ' ' * curses.COLS
        for i in range(to_display, margin.body_lines):
            stdscr.insstr(i + margin.header, 0, blankline)

    def current_position(self, status: Status) -> None:
        line = f'line {self.cursor_y + 1}'
        col = f'col {self.x + 1}'
        line_count = max(len(self.lines) - 1, 1)
        lines_word = 'line' if line_count == 1 else 'lines'
        status.update(f'{line}, {col} (of {line_count} {lines_word})')


class Screen:
    def __init__(
            self,
            stdscr: 'curses._CursesWindow',
            files: List[File],
    ) -> None:
        self.stdscr = stdscr
        self.files = files
        self.i = 0
        self.status = Status()
        self.margin = Margin.from_screen(self.stdscr)
        self.cut_buffer: Tuple[str, ...] = ()

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


def _color_test(stdscr: 'curses._CursesWindow') -> None:
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
    '\x1b[1;5H': b'kHOM5',  # ^Home
    '\x1b[1;5F': b'kEND5',  # ^End
    '\x1bOH': b'KEY_HOME',
    '\x1bOF': b'KEY_END',
    '\x1b[1;3A': b'kUP3',  # M-Up
    '\x1b[1;3B': b'kDN3',  # M-Down
    '\x1b[1;3C': b'kRIT3',  # M-Right
    '\x1b[1;3D': b'kLFT3',  # M-Left
    '\x1b[1;5A': b'kUP5',  # ^Up
    '\x1b[1;5B': b'kDN5',  # ^Down
}


def _get_char(stdscr: 'curses._CursesWindow') -> Key:
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

        if len(wch) == 2:
            return Key(wch, -1, f'M-{wch[1]}'.encode())
        elif len(wch) > 1:
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


EditResult = enum.Enum('EditResult', 'EXIT NEXT PREV EDIT')


class Command(NamedTuple):
    name: str
    description: str
    binds: List[str]
    func: Callable[[Screen, Key], EditResult]
    aliases: List[str] = []


COMMANDS: List[Command] = []


def command(
    name: str,
    description: str,
    binds: List[str] = [],
    aliases: List[str] = [],
) -> Callable[[Callable[[Screen, Key], EditResult]], None]:
    def inner(func: Callable[[Screen, Key], EditResult]) -> None:
        COMMANDS.append(
            Command(
                name, description, binds, func, aliases=aliases,
            ),
        )
        return func
    return inner


@command('quit', 'Quits the current buffer.', binds=[b'^X'], aliases=['q'])
def quit_command(screen: Screen, prevkey: Key) -> EditResult:
    return EditResult.EXIT


@command('write', 'Saves the current buffer.', binds=[b'^S'], aliases=['w'])
def save_command(screen: Screen, prevkey: Key) -> EditResult:
    screen.file.save(screen, screen.status)
    return EditResult.EDIT


@command(
    'write-quit',
    'Saves the current buffer then quits it.',
    binds=[],
    aliases=['wq'],
)
def write_quit_command(screen: Screen, prevkey: Key) -> EditResult:
    screen.file.save(screen, screen.status)
    return EditResult.EXIT


@command(
    'lineno',
    'Shows the line and column number for the current buffer.',
    binds=[b'^C'],
    aliases=['ln'],
)
def lineno_command(screen: Screen, prevkey: Key) -> EditResult:
    screen.file.current_position(screen.status)
    return EditResult.EDIT


@command(
    'cut',
    'Cuts the current line of text from the buffer',
    binds=[b'^K'],
)
def cut_command(screen: Screen, prevkey: Key) -> EditResult:
    if prevkey.keyname == b'^K':
        cut_buffer = screen.cut_buffer
    else:
        cut_buffer = ()
        screen.cut_buffer = screen.file.cut(cut_buffer)
    return EditResult.EDIT


@command(
    'uncut',
    'Uncuts the currently cut text into the buffer',
    binds=[b'^U'],
)
def uncut_command(screen: Screen, prevkey: Key) -> EditResult:
    screen.file.uncut(screen.cut_buffer, screen.margin)
    return EditResult.EDIT


@command(
    'undo',
    'Undoes your last action.',
    binds=[b'M-u'],
)
def undo_command(screen: Screen, prevkey: Key) -> EditResult:
    screen.file.undo(screen.status, screen.margin)
    return EditResult.EDIT


@command(
    'redo',
    'Redoes your last action.',
    binds=[b'M-U'],
)
def redo_command(screen: Screen, prevkey: Key) -> EditResult:
    screen.file.redo(screen.status, screen.margin)
    return EditResult.EDIT


@command(
    'go-to-line',
    'Jumps to a specific line in the current buffer',
    binds=[b'^_'],
)
def go_to_line_command(screen: Screen, prevkey: Key) -> EditResult:
    response = screen.status.prompt(screen, 'enter line number')
    if response == '':
        screen.status.update('cancelled')
    else:
        try:
            lineno = int(response)
        except ValueError:
            screen.status.update(f'not an integer: {response!r}')
        else:
            screen.file.go_to_line(lineno, screen.margin)
    return EditResult.EDIT


@command(
    'search',
    'Searches the current buffer',
    binds=[b'^W'],
    aliases=['s'],
)
def search_command(screen: Screen, prevkey: Key) -> EditResult:
    response = screen.status.prompt(screen, 'search', history='search')
    if response == '':
        screen.status.update('cancelled')
    else:
        try:
            regex = re.compile(response)
        except re.error:
            screen.status.update(f'invalid regex: {response!r}')
        else:
            screen.file.search(regex, screen.status, screen.margin)
    return EditResult.EDIT


def _edit(screen: Screen) -> EditResult:
    prevkey = Key('', 0, b'')
    screen.file.ensure_loaded(screen.status)

    while True:
        screen.status.tick(screen.margin)

        screen.draw()
        screen.file.move_cursor(screen.stdscr, screen.margin)

        key = _get_char(screen.stdscr)

        res = None

        bind_found = [
            [command.binds, command.func]
            for command in COMMANDS if key.keyname in command.binds
        ]
        cmd = []
        if len(bind_found) > 0:
            cmd = bind_found[0]

        if key.key == curses.KEY_RESIZE:
            screen.resize()
        elif key.key in File.DISPATCH:
            screen.file.DISPATCH[key.key](screen.file, screen.margin)
        elif key.keyname in File.DISPATCH_KEY:
            screen.file.DISPATCH_KEY[key.keyname](
                screen.file, screen.margin,
            )
        elif cmd:
            if key.keyname in cmd[0]:
                res = cmd[1](screen, prevkey)
                prevkey = key
        elif key.keyname == b'^[':  # escape
            response = screen.status.prompt(screen, '', history='command')
            cmd_found = [
                [command.name, command.func]
                for command in COMMANDS if response[1:] == command.name
            ]
            alias_found = [
                [command.aliases, command.func]
                for command in COMMANDS if response[1:] in command.aliases
            ]
            cmd = []
            if len(cmd_found) > 0:
                cmd = cmd_found[0]
            elif len(alias_found) > 0:
                cmd = alias_found[0]
            if cmd:
                return cmd[1](screen, prevkey)
            elif response != '':  # noop / cancel
                screen.status.update(f'invalid command: {response}')
        elif key.keyname == b'kLFT3':
            res = EditResult.PREV
        elif key.keyname == b'kRIT3':
            res = EditResult.NEXT
        elif key.keyname == b'^Z':
            curses.endwin()
            os.kill(os.getpid(), signal.SIGSTOP)
            screen.stdscr = _init_screen()
            screen.resize()
        elif isinstance(key.wch, str) and key.wch.isprintable():
            screen.file.c(key.wch, screen.margin)
        else:
            screen.status.update(f'unknown key: {key}')

        if not res == EditResult.EDIT:
            return res


def c_main(stdscr: 'curses._CursesWindow', args: argparse.Namespace) -> None:
    if args.color_test:
        return _color_test(stdscr)
    screen = Screen(stdscr, [File(f) for f in args.filenames or [None]])

    with screen.status.save_history():
        while screen.files:
            screen.i = screen.i % len(screen.files)
            res = _edit(screen)
            if res == EditResult.EXIT:
                del screen.files[screen.i]
                screen.status.clear()
            elif res == EditResult.NEXT:
                screen.i += 1
                screen.status.clear()
            elif res == EditResult.PREV:
                screen.i -= 1
                screen.status.clear()
            else:
                raise AssertionError(f'unreachable {res}')
    with screen.status.save_history():
        while screen.files:
            screen.i = screen.i % len(screen.files)
            res = _edit(screen)
            if res == EditResult.EXIT:
                del screen.files[screen.i]
                screen.status.clear()
            elif res == EditResult.NEXT:
                screen.i += 1
                screen.status.clear()
            elif res == EditResult.PREV:
                screen.i -= 1
                screen.status.clear()
            else:
                raise AssertionError(f'unreachable {res}')


def _init_screen() -> 'curses._CursesWindow':
    # set the escape delay so curses does not pause waiting for sequences
    if sys.version_info >= (3, 9):  # pragma: no cover
        curses.set_escdelay(25)
    else:  # pragma: no cover
        os.environ.setdefault('ESCDELAY', '25')

    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    # <enter> is not transformed into '\n' so it can be differentiated from ^J
    curses.nonl()
    # ^S / ^Q / ^Z / ^\ are passed through
    curses.raw()
    stdscr.keypad(True)
    with contextlib.suppress(curses.error):
        curses.start_color()
    _init_colors(stdscr)
    return stdscr


@contextlib.contextmanager
def make_stdscr() -> Generator['curses._CursesWindow', None, None]:
    """essentially `curses.wrapper` but split out to implement ^Z"""
    stdscr = _init_screen()
    try:
        yield stdscr
    finally:
        curses.endwin()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--color-test', action='store_true')
    parser.add_argument('filenames', metavar='filename', nargs='*')
    args = parser.parse_args()
    with make_stdscr() as stdscr:
        c_main(stdscr, args)
    return 0


if __name__ == '__main__':
    exit(main())
