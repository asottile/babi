from __future__ import annotations

import contextlib
import curses
import enum
import hashlib
import os
import re
import signal
import sre_parse
import sys
from types import FrameType
from typing import Callable
from typing import Generator
from typing import NamedTuple
from typing import Pattern

from babi.color_manager import ColorManager
from babi.dim import Dim
from babi.file import Action
from babi.file import File
from babi.file import get_lines
from babi.history import History
from babi.hl.syntax import Syntax
from babi.perf import Perf
from babi.prompt import Prompt
from babi.prompt import PromptResult
from babi.status import Status

if sys.version_info >= (3, 8):  # pragma: >=3.8 cover
    import importlib.metadata as importlib_metadata
else:  # pragma: <3.8 cover
    import importlib_metadata

VERSION_STR = f'babi v{importlib_metadata.version("babi")}'

# TODO: find a place to populate these, surely there's a database somewhere
SEQUENCE_KEYNAME = {
    '\x1bOH': b'KEY_HOME',
    '\x1bOF': b'KEY_END',
    '\x1b[1~': b'KEY_HOME',
    '\x1b[4~': b'KEY_END',
    '\x1b[1;2A': b'KEY_SR',
    '\x1b[1;2B': b'KEY_SF',
    '\x1b[1;2C': b'KEY_SRIGHT',
    '\x1b[1;2D': b'KEY_SLEFT',
    '\x1b[1;2H': b'KEY_SHOME',
    '\x1b[1;2F': b'KEY_SEND',
    '\x1b[5;2~': b'KEY_SPREVIOUS',
    '\x1b[6;2~': b'KEY_SNEXT',
    '\x1b[1;3A': b'kUP3',  # M-Up
    '\x1b[1;3B': b'kDN3',  # M-Down
    '\x1b[1;3C': b'kRIT3',  # M-Right
    '\x1b[1;3D': b'kLFT3',  # M-Left
    '\x1b[1;5A': b'kUP5',  # ^Up
    '\x1b[1;5B': b'kDN5',  # ^Down
    '\x1b[1;5C': b'kRIT5',  # ^Right
    '\x1b[1;5D': b'kLFT5',  # ^Left
    '\x1b[1;5H': b'kHOM5',  # ^Home
    '\x1b[1;5F': b'kEND5',  # ^End
    '\x1b[1;6C': b'kRIT6',  # Shift + ^Right
    '\x1b[1;6D': b'kLFT6',  # Shift + ^Left
    '\x1b[1;6H': b'kHOM6',  # Shift + ^Home
    '\x1b[1;6F': b'kEND6',  # Shift + ^End
    '\x1b[~': b'KEY_BTAB',  # Shift + Tab
}
KEYNAME_REWRITE = {
    # windows-curses: numeric pad arrow keys
    # - some overlay keyboards pick these as well
    # - in xterm it seems these are mapped automatically
    b'KEY_A2': b'KEY_UP',
    b'KEY_C2': b'KEY_DOWN',
    b'KEY_B3': b'KEY_RIGHT',
    b'KEY_B1': b'KEY_LEFT',
    b'PADSTOP': b'KEY_DC',
    b'KEY_A3': b'KEY_PPAGE',
    b'KEY_C3': b'KEY_NPAGE',
    b'KEY_A1': b'KEY_HOME',
    b'KEY_C1': b'KEY_END',
    # windows-curses: map to our M- names
    b'ALT_U': b'M-u',
    # windows-curses: arguably these names are better than the xterm names
    b'CTL_UP': b'kUP5',
    b'CTL_DOWN': b'kDN5',
    b'CTL_RIGHT': b'kRIT5',
    b'CTL_LEFT': b'kLFT5',
    b'CTL_HOME': b'kHOM5',
    b'CTL_END': b'kEND5',
    b'ALT_RIGHT': b'kRIT3',
    b'ALT_LEFT': b'kLFT3',
    b'ALT_E': b'M-e',
    # windows-curses: idk why these are different
    b'KEY_SUP': b'KEY_SR',
    b'KEY_SDOWN': b'KEY_SF',
    # macos: (sends this for backspace key, others interpret this as well)
    b'^?': b'KEY_BACKSPACE',
    # linux, perhaps others
    b'^H': b'KEY_BACKSPACE',  # ^Backspace on my keyboard
    b'^D': b'KEY_DC',
    b'PADENTER': b'^M',  # Enter on numpad
}


def _get_wch_with_retry(stdscr: curses._CursesWindow) -> str | int:
    while True:
        try:
            return stdscr.get_wch()
        except curses.error:  # pragma: no cover (error during signals?)
            pass


class EditResult(enum.Enum):
    EXIT = enum.auto()
    EXIT_ALL = enum.auto()
    EXIT_ALL_FORCE = enum.auto()
    NEXT = enum.auto()
    PREV = enum.auto()
    OPEN = enum.auto()


class Command(NamedTuple):
    callback: Callable[[Screen, list[str]], EditResult | None]
    nargs: str | int = 0


class Key(NamedTuple):
    wch: int | str
    keyname: bytes


class FileInfo(NamedTuple):
    filename: str | None
    initial_line: int
    is_stdin: bool


class Layout(NamedTuple):
    header: Dim
    file: Dim
    status: Dim


class Screen:
    def __init__(
            self,
            stdscr: curses._CursesWindow,
            file_infos: list[FileInfo],
            perf: Perf,
    ) -> None:
        self.stdscr = stdscr
        self.color_manager = ColorManager.make()
        self.hl_factories = (Syntax.from_screen(stdscr, self.color_manager),)
        self.files = [
            File(
                info.filename,
                info.initial_line,
                self.color_manager,
                self.hl_factories,
                is_stdin=info.is_stdin,
            )
            for info in file_infos
        ]
        self.i = 0
        self.history = History()
        self.perf = perf
        self.layout = self._layout_from_current_screen()
        self.status = Status()
        self.cut_buffer: tuple[str, ...] = ()
        self.cut_selection = False
        self._buffered_input: int | str | None = None
        self._retheme = False

    @property
    def file(self) -> File:
        return self.files[self.i]

    def _draw_header(self, dim: Dim) -> None:
        filename = self.file.filename or '<<new file>>'
        if self.file.modified:
            filename += ' *'
        if len(self.files) > 1:
            files = f'[{self.i + 1}/{len(self.files)}] '
            version_width = len(VERSION_STR) + 2 + len(files)
        else:
            files = ''
            version_width = len(VERSION_STR) + 2
        centered = filename.center(dim.width)[version_width:]
        s = f' {VERSION_STR} {files}{centered}'
        self.stdscr.insstr(0, 0, s, curses.A_REVERSE)

    def _get_sequence_home_end(self, wch: str) -> str:
        try:
            c = self.stdscr.get_wch()
        except curses.error:
            return wch
        else:
            if isinstance(c, int) or c not in 'HF':
                self._buffered_input = c
                return wch
            else:
                return f'{wch}{c}'

    def _get_sequence_bracketed(self, wch: str) -> str:
        for _ in range(3):  # [0-9]{1,2};
            try:
                c = self.stdscr.get_wch()
            except curses.error:
                return wch
            else:
                if isinstance(c, int):
                    self._buffered_input = c
                    return wch
                else:
                    wch += c
                    if c == ';':
                        break
        else:
            return wch  # unexpected input while searching for `;`

        for _ in range(2):  # [0-9].
            try:
                c = self.stdscr.get_wch()
            except curses.error:
                return wch
            else:
                if isinstance(c, int):
                    self._buffered_input = c
                    return wch
                else:
                    wch += c

        return wch

    def _get_sequence(self, wch: str) -> str:
        self.stdscr.nodelay(True)
        try:
            c = self.stdscr.get_wch()
        except curses.error:
            return wch
        else:
            if isinstance(c, int):  # M-BSpace
                return f'{wch}({c})'  # TODO
            elif c == 'O':
                return self._get_sequence_home_end(f'{wch}O')
            elif c == '[':
                return self._get_sequence_bracketed(f'{wch}[')
            else:
                return f'{wch}{c}'
        finally:
            self.stdscr.nodelay(False)

    def _get_string(self, wch: str) -> str:
        self.stdscr.nodelay(True)
        try:
            while True:
                try:
                    c = self.stdscr.get_wch()
                    if isinstance(c, str) and c.isprintable():
                        wch += c
                    else:
                        self._buffered_input = c
                        break
                except curses.error:
                    break
        finally:
            self.stdscr.nodelay(False)
        return wch

    def _get_char(self) -> Key:
        if self._buffered_input is not None:
            wch, self._buffered_input = self._buffered_input, None
        elif self._retheme:
            self._retheme = False
            return Key(-1, b'RETHEME')
        else:
            wch = _get_wch_with_retry(self.stdscr)
        if isinstance(wch, str) and wch == '\x1b':
            wch = self._get_sequence(wch)
            if len(wch) == 2:
                return Key(wch, f'M-{wch[1]}'.encode())
            elif len(wch) > 1:
                keyname = SEQUENCE_KEYNAME.get(wch, b'unknown')
                return Key(wch, keyname)
        elif isinstance(wch, str) and wch.isprintable():
            wch = self._get_string(wch)
            return Key(wch, b'STRING')

        key = wch if isinstance(wch, int) else ord(wch)
        keyname = curses.keyname(key)
        keyname = KEYNAME_REWRITE.get(keyname, keyname)
        return Key(wch, keyname)

    def get_char(self) -> Key:
        self.perf.end()
        ret = self._get_char()
        self.perf.start(ret.keyname.decode())
        return ret

    def draw(self) -> None:
        self._draw_header(self.layout.header)
        self.file.draw(self.stdscr, self.layout.file)
        self.status.draw(self.stdscr, self.layout.status)

    def _layout_from_current_screen(self) -> Layout:
        file_y = 0
        file_height = curses.LINES

        if curses.LINES > 2:
            file_y += 1
            file_height -= 2
        elif curses.LINES > 1:
            file_height -= 1

        return Layout(
            header=Dim(x=0, y=0, width=curses.COLS, height=1),
            file=Dim(x=0, y=file_y, width=curses.COLS, height=file_height),
            status=Dim(x=0, y=curses.LINES - 1, width=curses.COLS, height=1),
        )

    def resize(self) -> None:
        curses.update_lines_cols()
        self.layout = self._layout_from_current_screen()
        self.file.buf.scroll_screen_if_needed(self.layout.file)
        self.draw()

    def quick_prompt(
            self,
            prompt: str,
            opt_strs: tuple[str, ...],
    ) -> str | PromptResult:
        opts = {opt[0] for opt in opt_strs}
        while True:
            x = 0
            prompt_line = self.layout.status.y

            def _write(s: str, *, attr: int = curses.A_REVERSE) -> None:
                nonlocal x

                if x >= self.layout.status.width:
                    return
                self.stdscr.insstr(prompt_line, x, s, attr)
                x += len(s)

            _write(prompt)
            _write(' [')
            for i, opt_str in enumerate(opt_strs):
                _write(opt_str[0], attr=curses.A_REVERSE | curses.A_BOLD)
                _write(opt_str[1:])
                if i != len(opt_strs) - 1:
                    _write(', ')
            _write(']?')

            if x < self.layout.status.width - 1:
                s = ' ' * (self.layout.status.width - x)
                self.stdscr.insstr(prompt_line, x, s, curses.A_REVERSE)
                x += 1
            else:
                x = self.layout.status.width - 1
                self.stdscr.insstr(prompt_line, x, '…', curses.A_REVERSE)

            self.stdscr.move(prompt_line, x)

            key = self.get_char()
            if key.keyname == b'KEY_RESIZE':
                self.resize()
            elif key.keyname == b'^C':
                return self.status.cancelled()
            elif isinstance(key.wch, str) and key.wch.lower() in opts:
                return key.wch.lower()

    def prompt(
            self,
            prompt: str,
            *,
            allow_empty: bool = False,
            history: str | None = None,
            default_prev: bool = False,
            default: str | None = None,
    ) -> str | PromptResult:
        default = default or ''
        self.status.clear()
        if history is not None:
            history_data = [*self.history.data[history], default]
            if default_prev and history in self.history.prev:
                prompt = f'{prompt} [{self.history.prev[history]}]'
        else:
            history_data = [default]

        ret = Prompt(self, prompt, history_data).run()

        if ret is not PromptResult.CANCELLED and history is not None:
            if ret:  # only put non-empty things in history
                history_lst = self.history.data[history]
                if not history_lst or history_lst[-1] != ret:
                    history_lst.append(ret)
                self.history.prev[history] = ret
            elif default_prev and history in self.history.prev:
                return self.history.prev[history]

        if not allow_empty and not ret:
            return self.status.cancelled()
        else:
            return ret

    def go_to_line(self) -> None:
        response = self.prompt('enter line number')
        if response is not PromptResult.CANCELLED:
            try:
                lineno = int(response)
            except ValueError:
                self.status.update(f'not an integer: {response!r}')
            else:
                self.file.go_to_line(lineno, self.layout.file)

    def current_position(self) -> None:
        line = f'line {self.file.buf.y + 1}'
        col = f'col {self.file.buf.x + 1}'
        line_count = max(len(self.file.buf) - 1, 1)
        lines_word = 'line' if line_count == 1 else 'lines'
        self.status.update(f'{line}, {col} (of {line_count} {lines_word})')

    def cut(self) -> None:
        if self.file.selection.start:
            self.cut_buffer = self.file.cut_selection(self.layout.file)
            self.cut_selection = True
        else:
            self.cut_buffer = self.file.cut(self.cut_buffer)
            self.cut_selection = False

    def uncut(self) -> None:
        if self.cut_selection:
            self.file.uncut_selection(self.cut_buffer, self.layout.file)
        else:
            self.file.uncut(self.cut_buffer, self.layout.file)

    def _get_search_re(self, prompt: str) -> Pattern[str] | PromptResult:
        response = self.prompt(prompt, history='search', default_prev=True)
        if response is PromptResult.CANCELLED:
            return response
        try:
            return re.compile(response)
        except re.error:
            self.status.update(f'invalid regex: {response!r}')
            return PromptResult.CANCELLED

    def _undo_redo(
            self,
            op: str,
            from_stack: list[Action],
            to_stack: list[Action],
    ) -> None:
        if not from_stack:
            self.status.update(f'nothing to {op}!')
        else:
            action = from_stack.pop()
            to_stack.append(action.apply(self.file))
            self.file.buf.scroll_screen_if_needed(self.layout.file)
            self.status.update(f'{op}: {action.name}')
            self.file.selection.clear()

    def undo(self) -> None:
        self._undo_redo('undo', self.file.undo_stack, self.file.redo_stack)

    def redo(self) -> None:
        self._undo_redo('redo', self.file.redo_stack, self.file.undo_stack)

    def search(self) -> None:
        response = self._get_search_re('search')
        if response is not PromptResult.CANCELLED:
            self.file.search(response, self.status, self.layout.file)

    def replace(self) -> None:
        search_response = self._get_search_re('search (to replace)')
        if search_response is not PromptResult.CANCELLED:
            response = self.prompt(
                'replace with', history='replace', allow_empty=True,
            )
            if response is not PromptResult.CANCELLED:
                try:
                    sre_parse.parse_template(response, search_response)
                except re.error:
                    self.status.update('invalid replacement string')
                else:
                    self.file.replace(self, search_response, response)

    def _command_w(self, args: list[str]) -> None:
        self.save()

    def _command_wq(self, args: list[str]) -> EditResult:
        self.save()
        return EditResult.EXIT

    def _command_sort(self, args: list[str]) -> None:
        if self.file.selection.start:
            self.file.sort_selection(self.layout.file)
        else:
            self.file.sort(self.layout.file)
        self.status.update('sorted!')

    def _command_sort_bang(self, args: list[str]) -> None:
        if self.file.selection.start:
            self.file.sort_selection(self.layout.file, reverse=True)
        else:
            self.file.sort(self.layout.file, reverse=True)
        self.status.update('sorted!')

    def _command_tabsize(self, args: list[str]) -> None:
        tab_size, = args
        try:
            parsed_tab_size = int(tab_size)
        except ValueError:
            self.status.update(f'invalid size: {tab_size}')
        else:
            if parsed_tab_size <= 0:
                self.status.update(f'invalid size: {parsed_tab_size}')
            else:
                for file in self.files:
                    file.buf.set_tab_size(parsed_tab_size)
                self.status.update('updated!')

    def _command_expandtabs(self, args: list[str]) -> None:
        for file in self.files:
            file.buf.expandtabs = True
        self.status.update('updated!')

    def _command_noexpandtabs(self, args: list[str]) -> None:
        for file in self.files:
            file.buf.expandtabs = False
        self.status.update('updated!')

    def _command_comment(self, args: list[str]) -> None:
        if len(args) == 1:
            comment, = args
        else:
            comment = '#'
        if self.file.selection.start:
            self.file.toggle_comment_selection(comment)
        else:
            self.file.toggle_comment(comment)

    def _command_reload(self, args: list[str]) -> None:
        if self.file.filename is None:
            self.status.update('file has not been saved yet!')
            return

        if self.file.modified:
            response = self.quick_prompt(
                'reload will discard changes - continue', ('yes', 'no'),
            )
            if response != 'y':
                return

        self.file.reload(self.status, self.layout.file)

    def _command_retheme(self, args: list[str]) -> None:
        self.color_manager = ColorManager.make()
        self.hl_factories = (
            Syntax.from_screen(self.stdscr, self.color_manager),
        )
        for file in self.files:
            file.reload_theme(self.hl_factories, self.color_manager)

    COMMANDS = {
        ':qall': Command(lambda self, args: EditResult.EXIT_ALL),
        ':qall!': Command(lambda self, args: EditResult.EXIT_ALL_FORCE),
        ':q': Command(lambda self, args: self.quit_save_modified()),
        ':q!': Command(lambda self, args: EditResult.EXIT),
        ':w': Command(_command_w),
        ':wq': Command(_command_wq),
        ':sort': Command(_command_sort),
        ':sort!': Command(_command_sort_bang),
        ':tabstop': Command(_command_tabsize, nargs=1),
        ':tabsize': Command(_command_tabsize, nargs=1),
        ':expandtabs': Command(_command_expandtabs),
        ':noexpandtabs': Command(_command_noexpandtabs),
        ':comment': Command(_command_comment, nargs='?'),
        ':reload': Command(_command_reload),
        ':retheme': Command(_command_retheme),
    }

    def command(self) -> EditResult | None:
        response = self.prompt('', history='command')
        if response is PromptResult.CANCELLED:
            return None

        cmd, *args = response.split()
        if cmd not in self.COMMANDS:
            self.status.update(f'invalid command: {response}')
            return None

        command = self.COMMANDS[cmd]
        if isinstance(command.nargs, int):
            if len(args) != command.nargs:
                self.status.update(
                    f'`{cmd}`: expected {command.nargs} args '
                    f'but got {len(args)}',
                )
                return None
        elif command.nargs == '?':
            if len(args) not in {0, 1}:
                self.status.update(
                    f'`{cmd}`: expected 0 or 1 args but got {len(args)}',
                )
                return None
        else:
            raise NotImplementedError(command)

        return command.callback(self, args)

    def save(self) -> PromptResult | None:
        self.file.finalize_previous_action()

        # TODO: maybe use mtime / stat as a shortcut for hashing below
        # TODO: strip trailing whitespace?
        # TODO: save atomically?
        if self.file.filename is None:
            filename = self.prompt('enter filename')
            if filename is PromptResult.CANCELLED:
                return PromptResult.CANCELLED
            else:
                self.file.filename = filename

        if not os.path.isfile(self.file.filename):
            sha256: str | None = None
        else:
            with open(self.file.filename, encoding='UTF-8', newline='') as f:
                *_, sha256 = get_lines(f)

        contents = self.file.nl.join(self.file.buf)
        sha256_to_save = hashlib.sha256(contents.encode()).hexdigest()

        # the file on disk is the same as when we opened it
        if sha256 not in (None, self.file.sha256, sha256_to_save):
            self.status.update('(file changed on disk, not implemented)')
            return PromptResult.CANCELLED

        try:
            dir_path = os.path.dirname(os.path.abspath(self.file.filename))
            os.makedirs(dir_path, exist_ok=True)
            with open(
                self.file.filename, 'w', encoding='UTF-8', newline='',
            ) as f:
                f.write(contents)
        except OSError as e:
            self.status.update(f'cannot save file: {e}')
            return PromptResult.CANCELLED

        self.file.modified = False
        self.file.sha256 = sha256_to_save
        num_lines = len(self.file.buf) - 1
        lines = 'lines' if num_lines != 1 else 'line'
        self.status.update(f'saved! ({num_lines} {lines} written)')
        self.file.reset_modified_state()
        return None

    def save_filename(self) -> PromptResult | None:
        response = self.prompt('enter filename', default=self.file.filename)
        if response is PromptResult.CANCELLED:
            return PromptResult.CANCELLED
        else:
            self.file.filename = response
            return self.save()

    def open_file(self) -> EditResult | None:
        response = self.prompt('enter filename', history='open')
        if response is not PromptResult.CANCELLED:
            opened = File(
                response,
                0,
                self.color_manager,
                self.hl_factories,
                is_stdin=False,
            )
            self.files.append(opened)
            return EditResult.OPEN
        else:
            return None

    def quit_save_modified(self) -> EditResult | None:
        if self.file.modified:
            response = self.quick_prompt(
                'file is modified - save', ('yes', 'no'),
            )
            if response == 'y':
                if self.save_filename() is not PromptResult.CANCELLED:
                    return EditResult.EXIT
                else:
                    return None
            elif response == 'n':
                return EditResult.EXIT
            else:
                assert response is PromptResult.CANCELLED
                return None
        return EditResult.EXIT

    def background(self) -> None:
        if sys.platform == 'win32':  # pragma: win32 cover
            self.status.update('cannot run babi in background on Windows')
        else:  # pragma: win32 no cover
            curses.endwin()
            os.kill(os.getpid(), signal.SIGSTOP)
            self.stdscr = _init_screen()
            self.resize()

    def retheme(self) -> None:
        self._command_retheme([])

    DISPATCH = {
        b'RETHEME': retheme,
        b'KEY_RESIZE': resize,
        b'^_': go_to_line,
        b'^C': current_position,
        b'^K': cut,
        b'^U': uncut,
        b'M-u': undo,
        b'M-U': redo,
        b'M-e': redo,
        b'^W': search,
        b'^\\': replace,
        b'^[': command,
        b'^S': save,
        b'^O': save_filename,
        b'^X': quit_save_modified,
        b'^P': open_file,
        b'kLFT3': lambda screen: EditResult.PREV,
        b'kRIT3': lambda screen: EditResult.NEXT,
        b'^Z': background,
    }

    @contextlib.contextmanager
    def retheme_handler(self) -> Generator[None, None, None]:
        if sys.platform == 'win32':  # pragma: win32 cover
            yield  # no signal handling on windows!
        else:
            def sigusr1_handler(signum: int, frame: FrameType | None) -> None:
                self._retheme = True
                os.kill(os.getpid(), signal.SIGWINCH)

            orig = signal.signal(signal.SIGUSR1, sigusr1_handler)
            try:
                yield
            finally:
                signal.signal(signal.SIGUSR1, orig)


def _init_screen() -> curses._CursesWindow:
    # set the escape delay so curses does not pause waiting for sequences
    if (
            sys.version_info >= (3, 9) and
            hasattr(curses, 'set_escdelay')
    ):  # pragma: >=3.9 cover
        curses.set_escdelay(25)
    else:  # pragma: <3.9 cover
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
        curses.use_default_colors()
    return stdscr


@contextlib.contextmanager
def make_stdscr() -> Generator[curses._CursesWindow, None, None]:
    """essentially `curses.wrapper` but split out to implement ^Z"""
    try:
        yield _init_screen()
    finally:
        curses.endwin()
