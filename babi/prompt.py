import curses
import enum
from typing import List
from typing import Optional
from typing import Tuple
from typing import TYPE_CHECKING
from typing import Union

from babi.buf import Buf

if TYPE_CHECKING:
    from babi.main import Screen  # XXX: circular

PromptResult = enum.Enum('PromptResult', 'CANCELLED')


class Prompt:
    def __init__(self, screen: 'Screen', prompt: str, lst: List[str]) -> None:
        self._screen = screen
        self._prompt = prompt
        self._buf = Buf(lst)
        self._buf.y = self._buf.file_y = len(lst) - 1
        self._x = len(self._s)

    @property
    def _x(self) -> int:
        return self._buf.x

    @_x.setter
    def _x(self, x: int) -> None:
        self._buf.x = x

    @property
    def _s(self) -> str:
        return self._buf[self._buf.y]

    @_s.setter
    def _s(self, s: str) -> None:
        self._buf[self._buf.y] = s

    def _render_prompt(self, *, base: Optional[str] = None) -> None:
        base = base or self._prompt
        if not base or self._screen.margin.cols < 7:
            prompt_s = ''
        elif len(base) > self._screen.margin.cols - 6:
            prompt_s = f'{base[:self._screen.margin.cols - 7]}…: '
        else:
            prompt_s = f'{base}: '

        width = self._screen.margin.cols - len(prompt_s)
        margin = self._screen.margin._replace(cols=width)
        cmd = f'{prompt_s}{self._buf.rendered_line(self._buf.y, margin)}'
        prompt_line = self._screen.margin.lines - 1
        self._screen.stdscr.insstr(prompt_line, 0, cmd, curses.A_REVERSE)

        _, x_off = self._buf.cursor_position(margin)
        self._screen.stdscr.move(prompt_line, len(prompt_s) + x_off)

    def _up(self) -> None:
        self._buf.up(self._screen.margin)
        self._x = len(self._buf[self._buf.y])

    def _down(self) -> None:
        self._buf.down(self._screen.margin)
        self._x = len(self._buf[self._buf.y])

    def _right(self) -> None:
        self._x = min(len(self._buf[self._buf.y]), self._x + 1)

    def _left(self) -> None:
        self._x = max(0, self._x - 1)

    def _home(self) -> None:
        self._x = 0

    def _end(self) -> None:
        self._x = len(self._buf[self._buf.y])

    def _ctrl_left(self) -> None:
        if self._x <= 1:
            self._buf.home()
        else:
            self._x -= 1
            tp = self._s[self._x - 1].isalnum()
            while self._x > 0 and tp == self._s[self._x - 1].isalnum():
                self._x -= 1

    def _ctrl_right(self) -> None:
        if self._x >= len(self._s) - 1:
            self._buf.end()
        else:
            self._x += 1
            tp = self._s[self._x].isalnum()
            while self._x < len(self._s) and tp == self._s[self._x].isalnum():
                self._x += 1

    def _backspace(self) -> None:
        if self._x > 0:
            self._s = self._s[:self._x - 1] + self._s[self._x:]
            self._x -= 1

    def _delete(self) -> None:
        if self._x < len(self._s):
            self._s = self._s[:self._x] + self._s[self._x + 1:]

    def _cut_to_end(self) -> None:
        self._s = self._s[:self._x]

    def _resize(self) -> None:
        self._screen.resize()

    def _check_failed(self, idx: int, s: str) -> Tuple[bool, int]:
        failed = False
        for search_idx in range(idx, -1, -1):
            if s in self._buf[search_idx]:
                idx = self._buf.y = search_idx
                self._x = self._buf[search_idx].index(s)
                break
        else:
            failed = True
        return failed, idx

    def _reverse_search(self) -> Union[None, str, PromptResult]:
        reverse_s = ''
        idx = self._buf.y
        while True:
            fail, idx = self._check_failed(idx, reverse_s)

            if fail:
                base = f'{self._prompt}(failed reverse-search)`{reverse_s}`'
            else:
                base = f'{self._prompt}(reverse-search)`{reverse_s}`'

            self._render_prompt(base=base)

            key = self._screen.get_char()
            if key.keyname == b'KEY_RESIZE':
                self._screen.resize()
            elif key.keyname == b'KEY_BACKSPACE':
                reverse_s = reverse_s[:-1]
            elif key.keyname == b'^R':
                idx = max(0, idx - 1)
            elif key.keyname == b'^C':
                return self._screen.status.cancelled()
            elif key.keyname == b'^M':
                return self._s
            elif key.keyname == b'STRING':
                assert isinstance(key.wch, str), key.wch
                for c in key.wch:
                    reverse_s += c
                    failed, idx = self._check_failed(idx, reverse_s)
            else:
                self._x = len(self._s)
                return None

    def _cancel(self) -> PromptResult:
        return self._screen.status.cancelled()

    def _submit(self) -> str:
        return self._s

    DISPATCH = {
        # movement
        b'KEY_UP': _up,
        b'KEY_DOWN': _down,
        b'KEY_RIGHT': _right,
        b'KEY_LEFT': _left,
        b'KEY_HOME': _home,
        b'^A': _home,
        b'KEY_END': _end,
        b'^E': _end,
        b'kRIT5': _ctrl_right,
        b'kLFT5': _ctrl_left,
        # editing
        b'KEY_BACKSPACE': _backspace,
        b'KEY_DC': _delete,
        b'^K': _cut_to_end,
        # misc
        b'KEY_RESIZE': _resize,
        b'^R': _reverse_search,
        b'^M': _submit,
        b'^C': _cancel,
    }

    def _c(self, c: str) -> None:
        self._buf.c(c)

    def run(self) -> Union[PromptResult, str]:
        while True:
            self._render_prompt()

            key = self._screen.get_char()
            if key.keyname in Prompt.DISPATCH:
                ret = Prompt.DISPATCH[key.keyname](self)
                if ret is not None:
                    return ret
            elif key.keyname == b'STRING':
                assert isinstance(key.wch, str), key.wch
                self._c(key.wch)
