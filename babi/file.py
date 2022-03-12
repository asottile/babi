from __future__ import annotations

import collections
import contextlib
import curses
import functools
import hashlib
import io
import itertools
import os.path
import re
from typing import Any
from typing import Callable
from typing import cast
from typing import Generator
from typing import IO
from typing import Match
from typing import NamedTuple
from typing import Pattern
from typing import TYPE_CHECKING
from typing import TypeVar

from babi.buf import Buf
from babi.buf import Modification
from babi.color_manager import ColorManager
from babi.dim import Dim
from babi.hl.interface import FileHL
from babi.hl.interface import HLFactory
from babi.hl.replace import Replace
from babi.hl.selection import Selection
from babi.hl.trailing_whitespace import TrailingWhitespace
from babi.prompt import PromptResult
from babi.status import Status

if TYPE_CHECKING:
    from babi.main import Screen  # XXX: circular

TCallable = TypeVar('TCallable', bound=Callable[..., Any])

WS_RE = re.compile(r'^\s*')


def get_lines(sio: IO[str]) -> tuple[list[str], str, bool, str]:
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
    # always make sure we end in a newline
    lines.append('')
    (nl, _), = newlines.most_common(1)
    mixed = len({k for k, v in newlines.items() if v}) > 1
    return lines, nl, mixed, sha256.hexdigest()


class OpenError(RuntimeError):
    pass


def _load_file(filename: str) -> tuple[list[str], str, bool, str]:
    try:
        with open(filename, encoding='UTF-8', newline='') as f:
            return get_lines(f)
    except UnicodeDecodeError:
        raise OpenError(f'error! not utf-8: {filename!r}')
    except OSError:
        # XXX: not quite correct, but maybe fix another day
        raise OpenError(f'error! not a file: {filename!r}')


class Action:
    def __init__(
            self, *, name: str, modifications: list[Modification],
            start_x: int, start_y: int, start_modified: bool,
            end_x: int, end_y: int, end_modified: bool,
            final: bool,
    ):
        self.name = name
        self.modifications = modifications
        self.start_x = start_x
        self.start_y = start_y
        self.start_modified = start_modified
        self.end_x = end_x
        self.end_y = end_y
        self.end_modified = end_modified
        self.final = final

    def apply(self, file: File) -> Action:
        action = Action(
            name=self.name, modifications=file.buf.apply(self.modifications),
            start_x=self.end_x, start_y=self.end_y,
            start_modified=self.end_modified,
            end_x=self.start_x, end_y=self.start_y,
            end_modified=self.start_modified,
            final=True,
        )

        file.buf.y = self.start_y
        file.buf.x = self.start_x
        file.modified = self.start_modified

        return action


def action(func: TCallable) -> TCallable:
    @functools.wraps(func)
    def action_inner(self: File, *args: Any, **kwargs: Any) -> Any:
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
        def edit_action_inner(self: File, *args: Any, **kwargs: Any) -> Any:
            with self.edit_action_context(name, final=final):
                return func(self, *args, **kwargs)
        return cast(TCallable, edit_action_inner)
    return edit_action_decorator


def keep_selection(func: TCallable) -> TCallable:
    @functools.wraps(func)
    def keep_selection_inner(self: File, *args: Any, **kwargs: Any) -> Any:
        with self.select():
            return func(self, *args, **kwargs)
    return cast(TCallable, keep_selection_inner)


def clear_selection(func: TCallable) -> TCallable:
    @functools.wraps(func)
    def clear_selection_inner(self: File, *args: Any, **kwargs: Any) -> Any:
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
            file: File,
            reg: Pattern[str],
            *,
            offset: int,
    ) -> None:
        self.file = file
        self.reg = reg
        self.offset = offset
        self.wrapped = False
        self._start_x = file.buf.x + offset
        self._start_y = file.buf.y

    def __iter__(self) -> _SearchIter:
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

    def __next__(self) -> tuple[int, Match[str]]:
        x = self.file.buf.x + self.offset
        y = self.file.buf.y

        match = self.reg.search(self.file.buf[y], x)
        if match:
            return self._stop_if_past_original(y, match)

        if self.wrapped:
            for line_y in range(y + 1, self._start_y + 1):
                match = self.reg.search(self.file.buf[line_y])
                if match:
                    return self._stop_if_past_original(line_y, match)
        else:
            for line_y in range(y + 1, len(self.file.buf)):
                match = self.reg.search(self.file.buf[line_y])
                if match:
                    return self._stop_if_past_original(line_y, match)

            self.wrapped = True

            for line_y in range(0, self._start_y + 1):
                match = self.reg.search(self.file.buf[line_y])
                if match:
                    return self._stop_if_past_original(line_y, match)

        raise StopIteration()


class File:
    def __init__(
            self,
            filename: str | None,
            initial_line: int,
            color_manager: ColorManager,
            hl_factories: tuple[HLFactory, ...],
            *,
            is_stdin: bool,
    ) -> None:
        self.filename = filename
        self.initial_line = initial_line
        self.is_stdin = is_stdin
        self.modified = False
        self.buf = Buf([])
        self.nl = '\n'
        self.sha256: str | None = None
        self._in_edit_action = False
        self.undo_stack: list[Action] = []
        self.redo_stack: list[Action] = []
        self._hl_factories = hl_factories
        self._trailing_whitespace = TrailingWhitespace(color_manager)
        self._replace_hl = Replace()
        self.selection = Selection()
        self._file_hls: tuple[FileHL, ...] = ()

    def ensure_loaded(
            self,
            status: Status,
            dim: Dim,
            stdin: str,
    ) -> None:
        if self.buf:
            return

        if self.is_stdin:
            status.update('(from stdin)')
            self.is_stdin = False
            self.filename = None
            self.modified = True
            sio = io.StringIO(stdin)
            lines, self.nl, mixed, self.sha256 = get_lines(sio)
        elif self.filename is not None and os.path.lexists(self.filename):
            try:
                lines, self.nl, mixed, self.sha256 = _load_file(self.filename)
            except OpenError as e:
                status.update(str(e))
                self.filename = None
                lines, self.nl, mixed, self.sha256 = get_lines(io.StringIO(''))
        else:
            if self.filename is not None:
                status.update('(new file)')
            lines, self.nl, mixed, self.sha256 = get_lines(io.StringIO(''))

        self.buf = Buf(lines, self.buf.tab_size)

        if mixed:
            status.update(f'mixed newlines will be converted to {self.nl!r}')
            self.modified = True

        self._initialize_highlighters()

        self.go_to_line(self.initial_line, dim)

    def _initialize_highlighters(self) -> None:
        file_hls = []
        for factory in self._hl_factories:
            if self.filename is not None:
                hl = factory.file_highlighter(self.filename, self.buf[0])
                file_hls.append(hl)
            else:
                file_hls.append(factory.blank_file_highlighter())
        self._file_hls = (
            *file_hls,
            self._trailing_whitespace, self._replace_hl, self.selection,
        )
        self.buf.clear_callbacks()
        for file_hl in self._file_hls:
            file_hl.register_callbacks(self.buf)

    def reload_theme(
            self,
            hl_factories: tuple[HLFactory, ...],
            color_manager: ColorManager,
    ) -> None:
        self._trailing_whitespace = TrailingWhitespace(color_manager)
        self._hl_factories = hl_factories
        # only re-initialize the highlighters if we've loaded once
        if self._file_hls:
            self._initialize_highlighters()

    def __repr__(self) -> str:
        return f'<{type(self).__name__} {self.filename!r}>'

    def reset_modified_state(self) -> None:
        for stack in (self.undo_stack, self.redo_stack):
            first = True
            for action in reversed(stack):
                action.end_modified = not first
                action.start_modified = True
                first = False

    # movement

    @action
    def up(self, dim: Dim) -> None:
        self.buf.up(dim)

    @action
    def down(self, dim: Dim) -> None:
        self.buf.down(dim)

    @action
    def right(self, dim: Dim) -> None:
        self.buf.right(dim)

    @action
    def left(self, dim: Dim) -> None:
        self.buf.left(dim)

    @action
    def home(self, dim: Dim) -> None:
        self.buf.x = 0

    @action
    def end(self, dim: Dim) -> None:
        self.buf.x = len(self.buf[self.buf.y])

    @action
    def ctrl_up(self, dim: Dim) -> None:
        self.buf.file_up(dim)

    @action
    def ctrl_down(self, dim: Dim) -> None:
        self.buf.file_down(dim)

    @action
    def ctrl_right(self, dim: Dim) -> None:
        line = self.buf[self.buf.y]
        # if we're at the second to last character, jump to end of line
        if self.buf.x == len(line) - 1:
            self.buf.right(dim)
        # if we're at the end of the line, jump forward to the next non-ws
        elif self.buf.x == len(line):
            while (
                    self.buf.y < len(self.buf) - 1 and (
                        self.buf.x == len(self.buf[self.buf.y]) or
                        self.buf[self.buf.y][self.buf.x].isspace()
                    )
            ):
                self.buf.right(dim)
        # if we're inside the line, jump to next position that's not our type
        else:
            self.buf.right(dim)
            tp = line[self.buf.x].isalnum()
            while self.buf.x < len(line) and tp == line[self.buf.x].isalnum():
                self.buf.right(dim)

    @action
    def ctrl_left(self, dim: Dim) -> None:
        line = self.buf[self.buf.y]
        # if we're at position 1 and it's not a space, go to the beginning
        if self.buf.x == 1 and not line[:self.buf.x].isspace():
            self.buf.left(dim)
        # if we're at the beginning or it's all space up to here jump to the
        # end of the previous non-space line
        elif self.buf.x == 0 or line[:self.buf.x].isspace():
            self.buf.x = 0
            while self.buf.y > 0 and self.buf.x == 0:
                self.buf.left(dim)
        else:
            self.buf.left(dim)
            tp = line[self.buf.x - 1].isalnum()
            while self.buf.x > 0 and tp == line[self.buf.x - 1].isalnum():
                self.buf.left(dim)

    @action
    def ctrl_home(self, dim: Dim) -> None:
        self.buf.x = 0
        self.buf.y = self.buf.file_y = 0

    @action
    def ctrl_end(self, dim: Dim) -> None:
        self.buf.x = 0
        self.buf.y = len(self.buf) - 1
        self.buf.scroll_screen_if_needed(dim)

    @action
    def go_to_line(self, lineno: int, dim: Dim) -> None:
        self.buf.x = 0
        if lineno == 0:
            self.buf.y = 0
        elif lineno > len(self.buf):
            self.buf.y = len(self.buf) - 1
        elif lineno < 0:
            self.buf.y = max(0, lineno + len(self.buf))
        else:
            self.buf.y = lineno - 1
        self.buf.scroll_screen_if_needed(dim)

    @action
    def search(
            self,
            reg: Pattern[str],
            status: Status,
            dim: Dim,
    ) -> None:
        search = _SearchIter(self, reg, offset=1)
        try:
            line_y, match = next(iter(search))
        except StopIteration:
            status.update('no matches')
        else:
            if line_y == self.buf.y and match.start() == self.buf.x:
                status.update('this is the only occurrence')
            else:
                if search.wrapped:
                    status.update('search wrapped')
                self.buf.y = line_y
                self.buf.x = match.start()
                self.buf.scroll_screen_if_needed(dim)

    @clear_selection
    def replace(
            self,
            screen: Screen,
            reg: Pattern[str],
            replace: str,
    ) -> None:
        self.finalize_previous_action()

        count = 0
        res: str | PromptResult = ''
        search = _SearchIter(self, reg, offset=0)
        for line_y, match in search:
            end = match.end()
            self.buf.y = line_y
            self.buf.x = match.start()
            self.buf.scroll_screen_if_needed(screen.layout.file)
            if res != 'a':  # make `a` replace the rest of them
                with self._replace_hl.region(self.buf.y, self.buf.x, end):
                    screen.draw()
                    res = screen.quick_prompt('replace', ('yes', 'no', 'all'))
            if res in {'y', 'a'}:
                count += 1
                with self.edit_action_context('replace', final=True):
                    replaced = match.expand(replace)
                    line = screen.file.buf[line_y]
                    if '\n' in replaced:
                        replaced_lines = replaced.split('\n')
                        self.buf[line_y] = (
                            f'{line[:match.start()]}{replaced_lines[0]}'
                        )
                        for i, ins_line in enumerate(replaced_lines[1:-1], 1):
                            self.buf.insert(line_y + i, ins_line)
                        last_insert = line_y + len(replaced_lines) - 1
                        self.buf.insert(
                            last_insert, f'{replaced_lines[-1]}{line[end:]}',
                        )
                        self.buf.y = last_insert
                        self.buf.x = 0
                        search.offset = len(replaced_lines[-1])
                    else:
                        self.buf[line_y] = (
                            f'{line[:match.start()]}{replaced}{line[end:]}'
                        )
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

    def _page_size(self, dim: Dim) -> int:
        return max(dim.height - 2, 1)

    @action
    def page_up(self, dim: Dim) -> None:
        if self.buf.y < dim.height:
            self.buf.y = self.buf.file_y = 0
        else:
            pos = max(self.buf.file_y - self._page_size(dim), 0)
            self.buf.y = self.buf.file_y = pos
        self.buf.x = 0

    @action
    def page_down(self, dim: Dim) -> None:
        if self.buf.file_y + dim.height >= len(self.buf):
            self.buf.y = len(self.buf) - 1
        else:
            pos = self.buf.file_y + self._page_size(dim)
            self.buf.y = self.buf.file_y = pos
        self.buf.x = 0

    @action
    def alt_up(self, dim: Dim) -> None:
        if self.buf.y > 0:
            offset = 1
            while self.buf[self.buf.y - offset] == '':
                offset += 1
            if offset >= 2:
                self.buf.y -= offset
                self.buf.scroll_screen_if_needed(dim)
                self.buf.x = 0
                return
            while (
                self.buf[self.buf.y - offset - 1] != '' and
                self.buf.y - offset - 1 >= 0
            ):
                offset += 1
            self.buf.y -= offset
            self.buf.scroll_screen_if_needed(dim)
            self.buf.x = 0

    @action
    def alt_down(self, dim: Dim) -> None:
        if self.buf.y < len(self.buf) - 1:
            offset = 0
            while self.buf[self.buf.y + offset] != '':
                offset += 1
            if offset > 1:
                self.buf.y += offset - 1
                self.buf.scroll_screen_if_needed(dim)
                self.buf.x = 0
                return
            while self.buf[self.buf.y + offset] == '':
                if self.buf.y + offset >= len(self.buf) - 1:
                    break
                offset += 1
            self.buf.y += offset
            self.buf.scroll_screen_if_needed(dim)
            self.buf.x = 0

    # editing

    @edit_action('backspace text', final=False)
    @clear_selection
    def backspace(self, dim: Dim) -> None:
        # backspace at the beginning of the file does nothing
        if self.buf.y == 0 and self.buf.x == 0:
            pass
        # backspace at the end of the file does not change the contents
        elif (
                self.buf.y == len(self.buf) - 1 and
                # still allow backspace if there are 2+ blank lines
                self.buf[self.buf.y - 1] != ''
        ):
            self.buf.left(dim)
        # at the beginning of the line, we join the current line and
        # the previous line
        elif self.buf.x == 0:
            y, victim = self.buf.y, self.buf.pop(self.buf.y)
            self.buf.left(dim)
            self.buf[y - 1] += victim
        else:
            s = self.buf[self.buf.y]
            self.buf[self.buf.y] = s[:self.buf.x - 1] + s[self.buf.x:]
            self.buf.left(dim)

    @edit_action('delete text', final=False)
    @clear_selection
    def delete(self, dim: Dim) -> None:
        if (
            # noop at end of the file
            self.buf.y == len(self.buf) - 1 or
            # noop at end of last real line
            (
                self.buf.y == len(self.buf) - 2 and
                self.buf.x == len(self.buf[self.buf.y])
            )
        ):
            pass
        # if we're at the end of the line, collapse the line afterwards
        elif self.buf.x == len(self.buf[self.buf.y]):
            victim = self.buf.pop(self.buf.y + 1)
            self.buf[self.buf.y] += victim
        else:
            s = self.buf[self.buf.y]
            self.buf[self.buf.y] = s[:self.buf.x] + s[self.buf.x + 1:]

    @edit_action('line break', final=False)
    @clear_selection
    def enter(self, dim: Dim) -> None:
        s = self.buf[self.buf.y]
        self.buf[self.buf.y] = s[:self.buf.x]
        self.buf.insert(self.buf.y + 1, s[self.buf.x:])
        self.buf.down(dim)
        self.buf.x = 0

    @edit_action('indent selection', final=True)
    def _indent_selection(self, dim: Dim) -> None:
        assert self.selection.start is not None
        sel_y, sel_x = self.selection.start
        (s_y, _), (e_y, _) = self.selection.get()
        tab_string = self.buf.tab_string
        tab_size = len(tab_string)
        for l_y in range(s_y, e_y + 1):
            if self.buf[l_y]:
                self.buf[l_y] = tab_string + self.buf[l_y]
                if l_y == self.buf.y:
                    self.buf.x += tab_size
                if l_y == sel_y and sel_x != 0:
                    sel_x += tab_size
        self.selection.set(sel_y, sel_x, self.buf.y, self.buf.x)

    @edit_action('insert tab', final=False)
    def _tab(self, dim: Dim) -> None:
        tab_string = self.buf.tab_string
        if tab_string == '\t':
            n = 1
        else:
            n = self.buf.tab_size - self.buf.x % self.buf.tab_size
            tab_string = tab_string[:n]
        line = self.buf[self.buf.y]
        self.buf[self.buf.y] = (
            line[:self.buf.x] + tab_string + line[self.buf.x:]
        )
        self.buf.x += n
        self.buf.restore_eof_invariant()

    def tab(self, dim: Dim) -> None:
        if self.selection.start is not None:
            self._indent_selection(dim)
        else:
            self._tab(dim)

    def _dedent_line(self, s: str) -> int:
        bound = min(len(s), len(self.buf.tab_string))
        i = 0
        while i < bound and s[i] in (' ', '\t'):
            i += 1
        return i

    @edit_action('dedent selection', final=True)
    def _dedent_selection(self, dim: Dim) -> None:
        assert self.selection.start is not None
        sel_y, sel_x = self.selection.start
        (s_y, _), (e_y, _) = self.selection.get()
        for l_y in range(s_y, e_y + 1):
            n = self._dedent_line(self.buf[l_y])
            if n:
                self.buf[l_y] = self.buf[l_y][n:]
                if l_y == self.buf.y:
                    self.buf.x = max(self.buf.x - n, 0)
                if l_y == sel_y:
                    sel_x = max(sel_x - n, 0)
        self.selection.set(sel_y, sel_x, self.buf.y, self.buf.x)

    @edit_action('dedent', final=True)
    def _dedent(self, dim: Dim) -> None:
        n = self._dedent_line(self.buf[self.buf.y])
        if n:
            self.buf[self.buf.y] = self.buf[self.buf.y][n:]
            self.buf.x = max(self.buf.x - n, 0)

    def shift_tab(self, dim: Dim) -> None:
        if self.selection.start is not None:
            self._dedent_selection(dim)
        else:
            self._dedent(dim)

    @edit_action('cut selection', final=True)
    @clear_selection
    def cut_selection(self, dim: Dim) -> tuple[str, ...]:
        ret = []
        (s_y, s_x), (e_y, e_x) = self.selection.get()
        if s_y == e_y:
            ret.append(self.buf[s_y][s_x:e_x])
            self.buf[s_y] = self.buf[s_y][:s_x] + self.buf[s_y][e_x:]
        else:
            ret.append(self.buf[s_y][s_x:])
            for l_y in range(s_y + 1, e_y):
                ret.append(self.buf[l_y])
            ret.append(self.buf[e_y][:e_x])

            self.buf[s_y] = self.buf[s_y][:s_x] + self.buf[e_y][e_x:]
            for _ in range(s_y + 1, e_y + 1):
                self.buf.pop(s_y + 1)
        self.buf.y = s_y
        self.buf.x = s_x
        self.buf.scroll_screen_if_needed(dim)
        return tuple(ret)

    def cut(self, cut_buffer: tuple[str, ...]) -> tuple[str, ...]:
        # only continue a cut if the last action is a non-final cut
        if not self._continue_last_action('cut'):
            cut_buffer = ()

        with self.edit_action_context('cut', final=False):
            if self.buf.y == len(self.buf) - 1:
                return cut_buffer
            else:
                victim = self.buf.pop(self.buf.y)
                self.buf.x = 0
                return cut_buffer + (victim,)

    def _uncut(self, cut_buffer: tuple[str, ...], dim: Dim) -> None:
        for cut_line in cut_buffer:
            line = self.buf[self.buf.y]
            before, after = line[:self.buf.x], line[self.buf.x:]
            self.buf[self.buf.y] = before + cut_line
            self.buf.insert(self.buf.y + 1, after)
            self.buf.down(dim)
            self.buf.x = 0

    @edit_action('uncut', final=True)
    @clear_selection
    def uncut(self, cut_buffer: tuple[str, ...], dim: Dim) -> None:
        self._uncut(cut_buffer, dim)

    @edit_action('uncut selection', final=True)
    @clear_selection
    def uncut_selection(
            self,
            cut_buffer: tuple[str, ...], dim: Dim,
    ) -> None:
        self._uncut(cut_buffer, dim)
        self.buf.up(dim)
        self.buf.x = len(self.buf[self.buf.y])
        self.buf[self.buf.y] += self.buf.pop(self.buf.y + 1)
        self.buf.restore_eof_invariant()

    def _sort(self, dim: Dim, s_y: int, e_y: int, reverse: bool) -> None:
        # self.buf intentionally does not support slicing so we use islice
        lines = sorted(itertools.islice(self.buf, s_y, e_y), reverse=reverse)
        for i, line in zip(range(s_y, e_y), lines):
            self.buf[i] = line

        self.buf.y = s_y
        self.buf.x = 0
        self.buf.scroll_screen_if_needed(dim)

    def _selection_lines(self) -> tuple[int, int]:
        (s_y, _), (e_y, _) = self.selection.get()
        e_y = min(e_y + 1, len(self.buf) - 1)
        if self.buf[e_y - 1] == '':
            e_y -= 1
        return s_y, e_y

    @edit_action('sort', final=True)
    def sort(self, dim: Dim, reverse: bool = False) -> None:
        self._sort(dim, 0, len(self.buf) - 1, reverse=reverse)

    @edit_action('sort selection', final=True)
    @clear_selection
    def sort_selection(self, dim: Dim, reverse: bool = False) -> None:
        s_y, e_y = self._selection_lines()
        self._sort(dim, s_y, e_y, reverse=reverse)

    def _is_commented(self, lineno: int, prefix: str) -> bool:
        return self.buf[lineno].lstrip().startswith(prefix)

    def _indent(self, lineno: int) -> str:
        ws_match = WS_RE.match(self.buf[lineno])
        assert ws_match is not None
        return ws_match[0]

    def _minimum_indent_for_selection(self) -> int:
        s_y, e_y = self._selection_lines()
        return min(len(self._indent(lineno)) for lineno in range(s_y, e_y))

    def _comment_remove(self, lineno: int, prefix: str) -> None:
        line = self.buf[lineno]
        indent = self._indent(lineno)
        ws_len = len(indent)

        if line.startswith(f'{prefix} ', ws_len):
            self.buf[lineno] = f'{indent}{line[ws_len + len(prefix) + 1:]}'
        elif line.startswith(prefix, ws_len):
            self.buf[lineno] = f'{indent}{line[ws_len + len(prefix):]}'

        if self.buf.y == lineno and self.buf.x > ws_len:
            self.buf.x -= len(line) - len(self.buf[lineno])

    def _comment_add(self, lineno: int, prefix: str, s_offset: int) -> None:
        line = self.buf[lineno]

        if not line:
            self.buf[lineno] = f'{prefix}'
        else:
            self.buf[lineno] = f'{line[:s_offset]}{prefix} {line[s_offset:]}'

        if lineno == self.buf.y and self.buf.x > s_offset:
            self.buf.x += len(self.buf[lineno]) - len(line)

    @edit_action('comment', final=True)
    def toggle_comment(self, prefix: str) -> None:
        if self._is_commented(self.buf.y, prefix):
            self._comment_remove(self.buf.y, prefix)
        else:
            ws_len = len(self._indent(self.buf.y))
            self._comment_add(self.buf.y, prefix, ws_len)

    @edit_action('comment selection', final=True)
    @clear_selection
    def toggle_comment_selection(self, prefix: str) -> None:
        s_y, e_y = self._selection_lines()
        commented = self._is_commented(s_y, prefix)
        minimum_indent = self._minimum_indent_for_selection()
        for lineno in range(s_y, e_y):
            if commented:
                self._comment_remove(lineno, prefix)
            else:
                self._comment_add(lineno, prefix, minimum_indent)

    def reload(self, status: Status, dim: Dim) -> None:
        assert self.filename is not None
        try:
            lines, nl, mixed, sha256 = _load_file(self.filename)
        except OpenError as e:
            status.update(f'reload: {e}')
            return

        self.selection.clear()
        self.nl, self.sha256 = nl, sha256
        with self.edit_action_context('reload', final=True):
            self.buf.replace_lines(lines)

        self.buf.fixup_position(dim)

        if mixed:
            status.update(
                f'reloaded! (mixed newlines will be converted to {self.nl!r})',
            )
        else:
            self.modified = False
            self.reset_modified_state()
            status.update('reloaded!')

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
        b'kUP3': alt_up,
        b'kDN3': alt_down,
        # editing
        b'KEY_BACKSPACE': backspace,
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
        b'kUP4': keep_selection(alt_up),
        b'kDN4': keep_selection(alt_down),
    }

    @edit_action('text', final=False)
    @clear_selection
    def c(self, wch: str, dim: Dim) -> None:
        s = self.buf[self.buf.y]
        self.buf[self.buf.y] = s[:self.buf.x] + wch + s[self.buf.x:]
        self.buf.x += len(wch)
        self.buf.restore_eof_invariant()

    def finalize_previous_action(self) -> None:
        assert not self._in_edit_action, 'nested edit/movement'
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
        if not continue_last and self.undo_stack:
            self.undo_stack[-1].final = True

        before_x, before_line = self.buf.x, self.buf.y
        before_modified = self.modified
        assert not self._in_edit_action, f'recursive action? {name}'
        self._in_edit_action = True
        try:
            with self.buf.record() as modifications:
                yield
        finally:
            self._in_edit_action = False
            self.redo_stack.clear()
            if continue_last:
                self.undo_stack[-1].end_x = self.buf.x
                self.undo_stack[-1].end_y = self.buf.y
                self.undo_stack[-1].modifications.extend(modifications)
            elif modifications:
                self.modified = True
                action = Action(
                    name=name, modifications=modifications,
                    start_x=before_x, start_y=before_line,
                    start_modified=before_modified,
                    end_x=self.buf.x, end_y=self.buf.y,
                    end_modified=True,
                    final=final,
                )
                self.undo_stack.append(action)

    @contextlib.contextmanager
    def select(self) -> Generator[None, None, None]:
        if self.selection.start is None:
            start = (self.buf.y, self.buf.x)
        else:
            start = self.selection.start
        try:
            yield
        finally:
            self.selection.set(*start, self.buf.y, self.buf.x)

    # positioning

    def move_cursor(
            self,
            stdscr: curses._CursesWindow,
            dim: Dim,
    ) -> None:
        stdscr.move(*self.buf.cursor_position(dim))

    def draw(self, stdscr: curses._CursesWindow, dim: Dim) -> None:
        to_display = min(self.buf.displayable_count, dim.height)

        for file_hl in self._file_hls:
            # XXX: this will go away?
            file_hl.highlight_until(self.buf, self.buf.file_y + to_display)

        for i in range(to_display):
            draw_y = i + dim.y
            l_y = self.buf.file_y + i
            stdscr.insstr(draw_y, 0, self.buf.rendered_line(l_y, dim))

            l_x = self.buf.line_x(dim) if l_y == self.buf.y else 0
            l_x_max = l_x + dim.width
            for file_hl in self._file_hls:
                for region in file_hl.regions[l_y]:
                    l_positions = self.buf.line_positions(l_y)
                    r_x = l_positions[region.x]
                    # the selection highlight intentionally extends one past
                    # the end of the line, which won't have a position
                    if region.end == len(l_positions):
                        r_end = l_positions[-1] + 1
                    else:
                        r_end = l_positions[region.end]

                    if r_x >= l_x_max:
                        break
                    elif r_end <= l_x:
                        continue

                    if l_x and r_x <= l_x:
                        if file_hl.include_edge:
                            h_s_x = 0
                        else:
                            h_s_x = 1
                    else:
                        h_s_x = r_x - l_x

                    if r_end >= l_x_max and l_x_max < l_positions[-1]:
                        if file_hl.include_edge:
                            h_e_x = dim.width
                        else:
                            h_e_x = dim.width - 1
                    else:
                        h_e_x = r_end - l_x

                    stdscr.chgat(draw_y, h_s_x, h_e_x - h_s_x, region.attr)

        for i in range(to_display, dim.height):
            stdscr.move(i + dim.y, 0)
            stdscr.clrtoeol()
