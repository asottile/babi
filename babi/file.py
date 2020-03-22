import collections
import contextlib
import curses
import functools
import hashlib
import io
import itertools
import os.path
from typing import Any
from typing import Callable
from typing import cast
from typing import Generator
from typing import IO
from typing import List
from typing import Match
from typing import NamedTuple
from typing import Optional
from typing import Pattern
from typing import Tuple
from typing import TYPE_CHECKING
from typing import TypeVar
from typing import Union

from babi.color_manager import ColorManager
from babi.hl.interface import FileHL
from babi.hl.interface import HLFactory
from babi.hl.replace import Replace
from babi.hl.selection import Selection
from babi.hl.trailing_whitespace import TrailingWhitespace
from babi.horizontal_scrolling import line_x
from babi.horizontal_scrolling import scrolled_line
from babi.list_spy import ListSpy
from babi.list_spy import MutableSequenceNoSlice
from babi.margin import Margin
from babi.prompt import PromptResult
from babi.status import Status

if TYPE_CHECKING:
    from babi.main import Screen  # XXX: circular

TCallable = TypeVar('TCallable', bound=Callable[..., Any])

HIGHLIGHT = curses.A_REVERSE | curses.A_DIM


def _restore_lines_eof_invariant(lines: MutableSequenceNoSlice) -> None:
    """The file lines will always contain a blank empty string at the end to
    simplify rendering.  This should be called whenever the end of the file
    might change.
    """
    if not lines or lines[-1] != '':
        lines.append('')


def get_lines(sio: IO[str]) -> Tuple[List[str], str, bool, str]:
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
            final: bool,
    ):
        self.name = name
        self.spy = spy
        self.start_x = start_x
        self.start_y = start_y
        self.start_modified = start_modified
        self.end_x = end_x
        self.end_y = end_y
        self.end_modified = end_modified
        self.final = final

    def apply(self, file: 'File') -> 'Action':
        spy = ListSpy(file.lines)
        action = Action(
            name=self.name, spy=spy,
            start_x=self.end_x, start_y=self.end_y,
            start_modified=self.end_modified,
            end_x=self.start_x, end_y=self.start_y,
            end_modified=self.start_modified,
            final=True,
        )

        self.spy.undo(spy)
        file.x = self.start_x
        file.y = self.start_y
        file.modified = self.start_modified
        file.touch(spy.min_line_touched)

        return action


def action(func: TCallable) -> TCallable:
    @functools.wraps(func)
    def action_inner(self: 'File', *args: Any, **kwargs: Any) -> Any:
        self.finalize_previous_action()
        return func(self, *args, **kwargs)
    return cast(TCallable, action_inner)


def edit_action(
        name: str,
        *,
        final: bool,
) -> Callable[[TCallable], TCallable]:
    def edit_action_decorator(func: TCallable) -> TCallable:
        @functools.wraps(func)
        def edit_action_inner(self: 'File', *args: Any, **kwargs: Any) -> Any:
            with self.edit_action_context(name, final=final):
                return func(self, *args, **kwargs)
        return cast(TCallable, edit_action_inner)
    return edit_action_decorator


def keep_selection(func: TCallable) -> TCallable:
    @functools.wraps(func)
    def keep_selection_inner(self: 'File', *args: Any, **kwargs: Any) -> Any:
        with self.select():
            return func(self, *args, **kwargs)
    return cast(TCallable, keep_selection_inner)


def clear_selection(func: TCallable) -> TCallable:
    @functools.wraps(func)
    def clear_selection_inner(self: 'File', *args: Any, **kwargs: Any) -> Any:
        ret = func(self, *args, **kwargs)
        self.selection.clear()
        return ret
    return cast(TCallable, clear_selection_inner)


class Found(NamedTuple):
    y: int
    match: Match[str]


class _SearchIter:
    def __init__(
            self,
            file: 'File',
            reg: Pattern[str],
            *,
            offset: int,
    ) -> None:
        self.file = file
        self.reg = reg
        self.offset = offset
        self.wrapped = False
        self._start_x = file.x + offset
        self._start_y = file.y

    def __iter__(self) -> '_SearchIter':
        return self

    def _stop_if_past_original(self, y: int, match: Match[str]) -> Found:
        if (
                self.wrapped and (
                    y > self._start_y or
                    y == self._start_y and match.start() >= self._start_x
                )
        ):
            raise StopIteration()
        return Found(y, match)

    def __next__(self) -> Tuple[int, Match[str]]:
        x = self.file.x + self.offset
        y = self.file.y

        match = self.reg.search(self.file.lines[y], x)
        if match:
            return self._stop_if_past_original(y, match)

        if self.wrapped:
            for line_y in range(y + 1, self._start_y + 1):
                match = self.reg.search(self.file.lines[line_y])
                if match:
                    return self._stop_if_past_original(line_y, match)
        else:
            for line_y in range(y + 1, len(self.file.lines)):
                match = self.reg.search(self.file.lines[line_y])
                if match:
                    return self._stop_if_past_original(line_y, match)

            self.wrapped = True

            for line_y in range(0, self._start_y + 1):
                match = self.reg.search(self.file.lines[line_y])
                if match:
                    return self._stop_if_past_original(line_y, match)

        raise StopIteration()


class File:
    def __init__(
            self,
            filename: Optional[str],
            color_manager: ColorManager,
            hl_factories: Tuple[HLFactory, ...],
    ) -> None:
        self.filename = filename
        self.modified = False
        self.lines: MutableSequenceNoSlice = []
        self.nl = '\n'
        self.file_y = self.y = self.x = self.x_hint = 0
        self.sha256: Optional[str] = None
        self.undo_stack: List[Action] = []
        self.redo_stack: List[Action] = []
        self._hl_factories = hl_factories
        self._trailing_whitespace = TrailingWhitespace(color_manager)
        self._replace_hl = Replace()
        self.selection = Selection()
        self._file_hls: Tuple[FileHL, ...] = ()

    def ensure_loaded(self, status: Status, stdin: str) -> None:
        if self.lines:
            return

        if self.filename == '-':
            status.update('(from stdin)')
            self.filename = None
            self.modified = True
            sio = io.StringIO(stdin)
            self.lines, self.nl, mixed, self.sha256 = get_lines(sio)
        elif self.filename is not None and os.path.isfile(self.filename):
            with open(self.filename, newline='') as f:
                self.lines, self.nl, mixed, self.sha256 = get_lines(f)
        else:
            if self.filename is not None:
                if os.path.lexists(self.filename):
                    status.update(f'{self.filename!r} is not a file')
                    self.filename = None
                else:
                    status.update('(new file)')
            sio = io.StringIO('')
            self.lines, self.nl, mixed, self.sha256 = get_lines(sio)

        if mixed:
            status.update(f'mixed newlines will be converted to {self.nl!r}')
            self.modified = True

        file_hls = []
        for factory in self._hl_factories:
            if self.filename is not None:
                hl = factory.file_highlighter(self.filename, self.lines[0])
                file_hls.append(hl)
            else:
                file_hls.append(factory.blank_file_highlighter())
        self._file_hls = (
            *file_hls,
            self._trailing_whitespace, self._replace_hl, self.selection,
        )

    def __repr__(self) -> str:
        return f'<{type(self).__name__} {self.filename!r}>'

    # movement

    def scroll_screen_if_needed(self, margin: Margin) -> None:
        # if the `y` is not on screen, make it so
        if self.file_y <= self.y < self.file_y + margin.body_lines:
            return

        self.file_y = max(self.y - margin.body_lines // 2, 0)

    def _scroll_amount(self) -> int:
        return int(curses.LINES / 2 + .5)

    def _set_x_after_vertical_movement(self) -> None:
        self.x = min(len(self.lines[self.y]), self.x_hint)

    def _increment_y(self, margin: Margin) -> None:
        self.y += 1
        if self.y >= self.file_y + margin.body_lines:
            self.file_y += self._scroll_amount()

    def _decrement_y(self) -> None:
        self.y -= 1
        if self.y < self.file_y:
            self.file_y -= self._scroll_amount()
            self.file_y = max(self.file_y, 0)

    @action
    def up(self, margin: Margin) -> None:
        if self.y > 0:
            self._decrement_y()
            self._set_x_after_vertical_movement()

    @action
    def down(self, margin: Margin) -> None:
        if self.y < len(self.lines) - 1:
            self._increment_y(margin)
            self._set_x_after_vertical_movement()

    @action
    def right(self, margin: Margin) -> None:
        if self.x >= len(self.lines[self.y]):
            if self.y < len(self.lines) - 1:
                self.x = 0
                self._increment_y(margin)
        else:
            self.x += 1
        self.x_hint = self.x

    @action
    def left(self, margin: Margin) -> None:
        if self.x == 0:
            if self.y > 0:
                self._decrement_y()
                self.x = len(self.lines[self.y])
        else:
            self.x -= 1
        self.x_hint = self.x

    @action
    def home(self, margin: Margin) -> None:
        self.x = self.x_hint = 0

    @action
    def end(self, margin: Margin) -> None:
        self.x = self.x_hint = len(self.lines[self.y])

    @action
    def ctrl_up(self, margin: Margin) -> None:
        self.file_y = max(0, self.file_y - 1)
        self.y = min(self.y, self.file_y + margin.body_lines - 1)
        self._set_x_after_vertical_movement()

    @action
    def ctrl_down(self, margin: Margin) -> None:
        self.file_y = min(len(self.lines) - 1, self.file_y + 1)
        self.y = max(self.y, self.file_y)
        self._set_x_after_vertical_movement()

    @action
    def ctrl_right(self, margin: Margin) -> None:
        line = self.lines[self.y]
        # if we're at the second to last character, jump to end of line
        if self.x == len(line) - 1:
            self.x = self.x_hint = self.x + 1
        # if we're at the end of the line, jump forward to the next non-ws
        elif self.x == len(line):
            while (
                    self.y < len(self.lines) - 1 and (
                        self.x == len(self.lines[self.y]) or
                        self.lines[self.y][self.x].isspace()
                    )
            ):
                if self.x == len(self.lines[self.y]):
                    self._increment_y(margin)
                    self.x = self.x_hint = 0
                else:
                    self.x = self.x_hint = self.x + 1
        # if we're inside the line, jump to next position that's not our type
        else:
            self.x = self.x_hint = self.x + 1
            tp = line[self.x].isalnum()
            while self.x < len(line) and tp == line[self.x].isalnum():
                self.x = self.x_hint = self.x + 1

    @action
    def ctrl_left(self, margin: Margin) -> None:
        line = self.lines[self.y]
        # if we're at position 1 and it's not a space, go to the beginning
        if self.x == 1 and not line[:self.x].isspace():
            self.x = self.x_hint = 0
        # if we're at the beginning or it's all space up to here jump to the
        # end of the previous non-space line
        elif self.x == 0 or line[:self.x].isspace():
            self.x = self.x_hint = 0
            while self.y > 0 and (self.x == 0 or not self.lines[self.y]):
                self._decrement_y()
                self.x = self.x_hint = len(self.lines[self.y])
        else:
            self.x = self.x_hint = self.x - 1
            tp = line[self.x - 1].isalnum()
            while self.x > 0 and tp == line[self.x - 1].isalnum():
                self.x = self.x_hint = self.x - 1

    @action
    def ctrl_home(self, margin: Margin) -> None:
        self.x = self.x_hint = 0
        self.y = self.file_y = 0

    @action
    def ctrl_end(self, margin: Margin) -> None:
        self.x = self.x_hint = 0
        self.y = len(self.lines) - 1
        self.scroll_screen_if_needed(margin)

    @action
    def go_to_line(self, lineno: int, margin: Margin) -> None:
        self.x = self.x_hint = 0
        if lineno == 0:
            self.y = 0
        elif lineno > len(self.lines):
            self.y = len(self.lines) - 1
        elif lineno < 0:
            self.y = max(0, lineno + len(self.lines))
        else:
            self.y = lineno - 1
        self.scroll_screen_if_needed(margin)

    @action
    def search(
            self,
            reg: Pattern[str],
            status: Status,
            margin: Margin,
    ) -> None:
        search = _SearchIter(self, reg, offset=1)
        try:
            line_y, match = next(iter(search))
        except StopIteration:
            status.update('no matches')
        else:
            if line_y == self.y and match.start() == self.x:
                status.update('this is the only occurrence')
            else:
                if search.wrapped:
                    status.update('search wrapped')
                self.y = line_y
                self.x = self.x_hint = match.start()
                self.scroll_screen_if_needed(margin)

    @clear_selection
    def replace(
            self,
            screen: 'Screen',
            reg: Pattern[str],
            replace: str,
    ) -> None:
        self.finalize_previous_action()

        count = 0
        res: Union[str, PromptResult] = ''
        search = _SearchIter(self, reg, offset=0)
        for line_y, match in search:
            self.y = line_y
            self.x = self.x_hint = match.start()
            self.scroll_screen_if_needed(screen.margin)
            if res != 'a':  # make `a` replace the rest of them
                with self._replace_hl.region(self.y, self.x, match.end()):
                    screen.draw()
                    res = screen.quick_prompt('replace', ('yes', 'no', 'all'))
            if res in {'y', 'a'}:
                count += 1
                with self.edit_action_context('replace', final=True):
                    replaced = match.expand(replace)
                    line = screen.file.lines[line_y]
                    line = line[:match.start()] + replaced + line[match.end():]
                    screen.file.lines[line_y] = line
                search.offset = len(replaced)
            elif res == 'n':
                search.offset = 1
            else:
                assert res is PromptResult.CANCELLED
                return

        if res == '':  # we never went through the loop
            screen.status.update('no matches')
        else:
            occurrences = 'occurrence' if count == 1 else 'occurrences'
            screen.status.update(f'replaced {count} {occurrences}')

    @action
    def page_up(self, margin: Margin) -> None:
        if self.y < margin.body_lines:
            self.y = self.file_y = 0
        else:
            pos = max(self.file_y - margin.page_size, 0)
            self.y = self.file_y = pos
        self.x = self.x_hint = 0

    @action
    def page_down(self, margin: Margin) -> None:
        if self.file_y + margin.body_lines >= len(self.lines):
            self.y = len(self.lines) - 1
        else:
            pos = self.file_y + margin.page_size
            self.y = self.file_y = pos
        self.x = self.x_hint = 0

    # editing

    @edit_action('backspace text', final=False)
    @clear_selection
    def backspace(self, margin: Margin) -> None:
        # backspace at the beginning of the file does nothing
        if self.y == 0 and self.x == 0:
            pass
        # backspace at the end of the file does not change the contents
        elif self.y == len(self.lines) - 1:
            self._decrement_y()
            self.x = self.x_hint = len(self.lines[self.y])
        # at the beginning of the line, we join the current line and
        # the previous line
        elif self.x == 0:
            victim = self.lines.pop(self.y)
            new_x = len(self.lines[self.y - 1])
            self.lines[self.y - 1] += victim
            self._decrement_y()
            self.x = self.x_hint = new_x
        else:
            s = self.lines[self.y]
            self.lines[self.y] = s[:self.x - 1] + s[self.x:]
            self.x = self.x_hint = self.x - 1

    @edit_action('delete text', final=False)
    @clear_selection
    def delete(self, margin: Margin) -> None:
        # noop at end of the file
        if self.y == len(self.lines) - 1:
            pass
        # if we're at the end of the line, collapse the line afterwards
        elif self.x == len(self.lines[self.y]):
            victim = self.lines.pop(self.y + 1)
            self.lines[self.y] += victim
        else:
            s = self.lines[self.y]
            self.lines[self.y] = s[:self.x] + s[self.x + 1:]

    @edit_action('line break', final=False)
    @clear_selection
    def enter(self, margin: Margin) -> None:
        s = self.lines[self.y]
        self.lines[self.y] = s[:self.x]
        self.lines.insert(self.y + 1, s[self.x:])
        self._increment_y(margin)
        self.x = self.x_hint = 0

    @edit_action('indent selection', final=True)
    def _indent_selection(self, margin: Margin) -> None:
        assert self.selection.start is not None
        sel_y, sel_x = self.selection.start
        (s_y, _), (e_y, _) = self.selection.get()
        for l_y in range(s_y, e_y + 1):
            if self.lines[l_y]:
                self.lines[l_y] = ' ' * 4 + self.lines[l_y]
                if l_y == self.y:
                    self.x = self.x_hint = self.x + 4
                if l_y == sel_y and sel_x != 0:
                    sel_x += 4
        self.selection.set(sel_y, sel_x, self.y, self.x)

    @edit_action('insert tab', final=False)
    def _tab(self, margin: Margin) -> None:
        n = 4 - self.x % 4
        line = self.lines[self.y]
        self.lines[self.y] = line[:self.x] + n * ' ' + line[self.x:]
        self.x = self.x_hint = self.x + n
        _restore_lines_eof_invariant(self.lines)

    def tab(self, margin: Margin) -> None:
        if self.selection.start is not None:
            self._indent_selection(margin)
        else:
            self._tab(margin)

    @staticmethod
    def _dedent_line(s: str) -> int:
        bound = min(len(s), 4)
        i = 0
        while i < bound and s[i] == ' ':
            i += 1
        return i

    @edit_action('dedent selection', final=True)
    def _dedent_selection(self, margin: Margin) -> None:
        assert self.selection.start is not None
        sel_y, sel_x = self.selection.start
        (s_y, _), (e_y, _) = self.selection.get()
        for l_y in range(s_y, e_y + 1):
            n = self._dedent_line(self.lines[l_y])
            if n:
                self.lines[l_y] = self.lines[l_y][n:]
                if l_y == self.y:
                    self.x = self.x_hint = max(self.x - n, 0)
                if l_y == sel_y:
                    sel_x = max(sel_x - n, 0)
        self.selection.set(sel_y, sel_x, self.y, self.x)

    @edit_action('dedent', final=True)
    def _dedent(self, margin: Margin) -> None:
        n = self._dedent_line(self.lines[self.y])
        if n:
            self.lines[self.y] = self.lines[self.y][n:]
            self.x = self.x_hint = max(self.x - n, 0)

    def shift_tab(self, margin: Margin) -> None:
        if self.selection.start is not None:
            self._dedent_selection(margin)
        else:
            self._dedent(margin)

    @edit_action('cut selection', final=True)
    @clear_selection
    def cut_selection(self, margin: Margin) -> Tuple[str, ...]:
        ret = []
        (s_y, s_x), (e_y, e_x) = self.selection.get()
        if s_y == e_y:
            ret.append(self.lines[s_y][s_x:e_x])
            self.lines[s_y] = self.lines[s_y][:s_x] + self.lines[s_y][e_x:]
        else:
            ret.append(self.lines[s_y][s_x:])
            for l_y in range(s_y + 1, e_y):
                ret.append(self.lines[l_y])
            ret.append(self.lines[e_y][:e_x])

            self.lines[s_y] = self.lines[s_y][:s_x] + self.lines[e_y][e_x:]
            for _ in range(s_y + 1, e_y + 1):
                self.lines.pop(s_y + 1)
        self.y = s_y
        self.x = self.x_hint = s_x
        self.scroll_screen_if_needed(margin)
        return tuple(ret)

    def cut(self, cut_buffer: Tuple[str, ...]) -> Tuple[str, ...]:
        # only continue a cut if the last action is a non-final cut
        if not self._continue_last_action('cut'):
            cut_buffer = ()

        with self.edit_action_context('cut', final=False):
            if self.y == len(self.lines) - 1:
                return cut_buffer
            else:
                victim = self.lines.pop(self.y)
                self.x = self.x_hint = 0
                return cut_buffer + (victim,)

    def _uncut(self, cut_buffer: Tuple[str, ...], margin: Margin) -> None:
        for cut_line in cut_buffer:
            line = self.lines[self.y]
            before, after = line[:self.x], line[self.x:]
            self.lines[self.y] = before + cut_line
            self.lines.insert(self.y + 1, after)
            self._increment_y(margin)
            self.x = self.x_hint = 0

    @edit_action('uncut', final=True)
    @clear_selection
    def uncut(self, cut_buffer: Tuple[str, ...], margin: Margin) -> None:
        self._uncut(cut_buffer, margin)

    @edit_action('uncut selection', final=True)
    @clear_selection
    def uncut_selection(
            self,
            cut_buffer: Tuple[str, ...], margin: Margin,
    ) -> None:
        self._uncut(cut_buffer, margin)
        self._decrement_y()
        self.x = self.x_hint = len(self.lines[self.y])
        self.lines[self.y] += self.lines.pop(self.y + 1)

    def _sort(self, margin: Margin, s_y: int, e_y: int) -> None:
        # self.lines intentionally does not support slicing so we use islice
        lines = sorted(itertools.islice(self.lines, s_y, e_y))
        for i, line in zip(range(s_y, e_y), lines):
            self.lines[i] = line

        self.y = s_y
        self.x = self.x_hint = 0
        self.scroll_screen_if_needed(margin)

    @edit_action('sort', final=True)
    def sort(self, margin: Margin) -> None:
        self._sort(margin, 0, len(self.lines) - 1)

    @edit_action('sort selection', final=True)
    @clear_selection
    def sort_selection(self, margin: Margin) -> None:
        (s_y, _), (e_y, _) = self.selection.get()
        e_y = min(e_y + 1, len(self.lines) - 1)
        if self.lines[e_y - 1] == '':
            e_y -= 1
        self._sort(margin, s_y, e_y)

    DISPATCH = {
        # movement
        b'KEY_UP': up,
        b'KEY_DOWN': down,
        b'KEY_RIGHT': right,
        b'KEY_LEFT': left,
        b'KEY_HOME': home,
        b'^A': home,
        b'KEY_END': end,
        b'^E': end,
        b'KEY_PPAGE': page_up,
        b'^Y': page_up,
        b'KEY_NPAGE': page_down,
        b'^V': page_down,
        b'kUP5': ctrl_up,
        b'kDN5': ctrl_down,
        b'kRIT5': ctrl_right,
        b'kLFT5': ctrl_left,
        b'kHOM5': ctrl_home,
        b'kEND5': ctrl_end,
        # editing
        b'KEY_BACKSPACE': backspace,
        b'^H': backspace,  # ^Backspace
        b'KEY_DC': delete,
        b'^M': enter,
        b'^I': tab,
        b'KEY_BTAB': shift_tab,
        # selection (shift + movement)
        b'KEY_SR': keep_selection(up),
        b'KEY_SF': keep_selection(down),
        b'KEY_SLEFT': keep_selection(left),
        b'KEY_SRIGHT': keep_selection(right),
        b'KEY_SHOME': keep_selection(home),
        b'KEY_SEND': keep_selection(end),
        b'KEY_SPREVIOUS': keep_selection(page_up),
        b'KEY_SNEXT': keep_selection(page_down),
        b'kRIT6': keep_selection(ctrl_right),
        b'kLFT6': keep_selection(ctrl_left),
        b'kHOM6': keep_selection(ctrl_home),
        b'kEND6': keep_selection(ctrl_end),
    }

    @edit_action('text', final=False)
    @clear_selection
    def c(self, wch: str, margin: Margin) -> None:
        s = self.lines[self.y]
        self.lines[self.y] = s[:self.x] + wch + s[self.x:]
        self.x = self.x_hint = self.x + len(wch)
        _restore_lines_eof_invariant(self.lines)

    def finalize_previous_action(self) -> None:
        assert not isinstance(self.lines, ListSpy), 'nested edit/movement'
        self.selection.clear()
        if self.undo_stack:
            self.undo_stack[-1].final = True

    def _continue_last_action(self, name: str) -> bool:
        return (
            bool(self.undo_stack) and
            self.undo_stack[-1].name == name and
            not self.undo_stack[-1].final
        )

    @contextlib.contextmanager
    def edit_action_context(
            self, name: str,
            *,
            final: bool,
    ) -> Generator[None, None, None]:
        continue_last = self._continue_last_action(name)
        if continue_last:
            spy = self.undo_stack[-1].spy
        else:
            if self.undo_stack:
                self.undo_stack[-1].final = True
            spy = ListSpy(self.lines)

        before_x, before_line = self.x, self.y
        before_modified = self.modified
        assert not isinstance(self.lines, ListSpy), 'recursive action?'
        orig, self.lines = self.lines, spy
        try:
            yield
        finally:
            self.lines = orig
            self.redo_stack.clear()
            if continue_last:
                self.undo_stack[-1].end_x = self.x
                self.undo_stack[-1].end_y = self.y
                self.touch(spy.min_line_touched)
            elif spy.has_modifications:
                self.modified = True
                action = Action(
                    name=name, spy=spy,
                    start_x=before_x, start_y=before_line,
                    start_modified=before_modified,
                    end_x=self.x, end_y=self.y,
                    end_modified=True,
                    final=final,
                )
                self.undo_stack.append(action)
                self.touch(spy.min_line_touched)

    @contextlib.contextmanager
    def select(self) -> Generator[None, None, None]:
        if self.selection.start is None:
            start = (self.y, self.x)
        else:
            start = self.selection.start
        try:
            yield
        finally:
            self.selection.set(*start, self.y, self.x)

    # positioning

    def rendered_y(self, margin: Margin) -> int:
        return self.y - self.file_y + margin.header

    def rendered_x(self) -> int:
        return self.x - line_x(self.x, curses.COLS)

    def move_cursor(
            self,
            stdscr: 'curses._CursesWindow',
            margin: Margin,
    ) -> None:
        stdscr.move(self.rendered_y(margin), self.rendered_x())

    def touch(self, lineno: int) -> None:
        for file_hl in self._file_hls:
            file_hl.touch(lineno)

    def draw(self, stdscr: 'curses._CursesWindow', margin: Margin) -> None:
        to_display = min(len(self.lines) - self.file_y, margin.body_lines)

        for file_hl in self._file_hls:
            file_hl.highlight_until(self.lines, self.file_y + to_display)

        for i in range(to_display):
            draw_y = i + margin.header
            l_y = self.file_y + i
            x = self.x if l_y == self.y else 0
            line = scrolled_line(self.lines[l_y], x, curses.COLS)
            stdscr.insstr(draw_y, 0, line)

            l_x = line_x(x, curses.COLS)
            l_x_max = l_x + curses.COLS
            for file_hl in self._file_hls:
                for region in file_hl.regions[l_y]:
                    if region.x >= l_x_max:
                        break
                    elif region.end < l_x:
                        continue

                    if l_x and region.x <= l_x:
                        if file_hl.include_edge:
                            h_s_x = 0
                        else:
                            h_s_x = 1
                    else:
                        h_s_x = region.x - l_x

                    if region.end >= l_x_max:
                        if file_hl.include_edge:
                            h_e_x = curses.COLS
                        else:
                            h_e_x = curses.COLS - 1
                    else:
                        h_e_x = region.end - l_x

                    stdscr.chgat(draw_y, h_s_x, h_e_x - h_s_x, region.attr)

        for i in range(to_display, margin.body_lines):
            stdscr.move(i + margin.header, 0)
            stdscr.clrtoeol()
