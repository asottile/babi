from __future__ import annotations

import collections
import curses
import functools
from typing import TYPE_CHECKING

from babi.buf import Buf
from babi.color_manager import ColorManager
from babi.dim import Dim
from babi.highlight import Compiler
from babi.highlight import Grammar
from babi.highlight import Grammars
from babi.highlight import highlight_line
from babi.hl.interface import HL
from babi.hl.interface import HLs
from babi.horizontal_scrolling import scrolled_line
from babi.linting import Error
from babi.theme import Theme

if TYPE_CHECKING:
    from babi.main import Screen  # XXX: circular


@functools.lru_cache(maxsize=1)
def _compiler() -> Compiler:
    grammar = Grammar.make({
        'scopeName': 'source.demo',
        'fileTypes': ['demo'],
        'patterns': [
            {
                'match': r'^([0-9]+)(:)([0-9]+)(:) (\[[^\]]+\]) ([^ ]+)',
                'name': 'line.error',
                'captures': {
                    '1': {'name': 'constant.numeric'},
                    '2': {'name': 'punctuation.separator'},
                    '3': {'name': 'constant.numeric'},
                    '4': {'name': 'punctuation.separator'},
                    '5': {'name': 'strong support.type'},
                    '6': {'name': 'invalid'},
                },
            },
        ],
    })
    return Compiler(grammar, Grammars())


class LintErrors:
    include_edge = False

    def __init__(self, color_manager: ColorManager, theme: Theme) -> None:
        self._color_manager = color_manager
        self._theme = theme

        self.top = 0
        self.y = 0
        self.errors: tuple[Error, ...] = ()

        self.regions: dict[int, HLs] = collections.defaultdict(tuple)

    def highlight_until(self, lines: Buf, idx: int) -> None:
        """our highlight regions are populated in other ways"""

    def _set_cb(self, lines: Buf, idx: int, victim: str) -> None:
        errors = tuple(
            error._replace(disabled=True) if error.line_idx == idx else error
            for error in self.errors
        )
        self.set_errors(errors)

    def _del_cb(self, lines: Buf, idx: int, victim: str) -> None:
        errors = tuple(
            error._replace(lineno=error.lineno - 1, disabled=True)
            if error.line_idx == idx else
            error._replace(lineno=error.lineno - 1)
            if error.line_idx > idx else
            error
            for error in self.errors
        )
        self.set_errors(errors)

    def _ins_cb(self, lines: Buf, idx: int) -> None:
        errors = tuple(
            error._replace(lineno=error.lineno + 1)
            if error.line_idx >= idx - 1 else error
            for error in self.errors
        )
        self.set_errors(errors)

    def register_callbacks(self, buf: Buf) -> None:
        buf.add_set_callback(self._set_cb)
        buf.add_del_callback(self._del_cb)
        buf.add_ins_callback(self._ins_cb)

    def set_errors(self, errors: tuple[Error, ...]) -> None:
        pair = self._color_manager.raw_color_pair(-1, curses.COLOR_RED)
        attr = curses.color_pair(pair)

        self.errors = errors
        self.regions.clear()
        self.regions.update({
            error.line_idx: (HL(x=0, end=1, attr=attr),)
            for error in errors
            if not error.disabled
        })

        if not self.errors:
            self.y = self.top = 0
        elif self.y >= len(self.errors):
            self.y = len(self.errors) - 1
            self.top = self.y - 1

    def clone(self, color_manager: ColorManager, theme: Theme) -> LintErrors:
        ret = type(self)(color_manager, theme)
        ret.set_errors(self.errors)
        return ret

    def draw(
            self,
            stdscr: curses._CursesWindow,
            dim: Dim,
            *,
            focused: bool = False,
    ) -> None:
        to_display = min(len(self.errors) - self.top, dim.height)
        for i in range(to_display):
            draw_y = i + dim.y
            l_y = self.top + i
            s = self.errors[l_y].render()
            rendered = scrolled_line(s, 0, dim.width)
            stdscr.insstr(draw_y, 0, rendered)

            if focused and self.y == l_y:
                attr = curses.A_REVERSE | curses.A_DIM | curses.color_pair(1)
                stdscr.chgat(draw_y, 0, dim.width, attr)
            elif self.errors[l_y].disabled:
                attr = curses.A_DIM | curses.color_pair(1)
                stdscr.chgat(draw_y, 0, dim.width, attr)
            else:
                compiler = _compiler()
                _, regions = highlight_line(
                    compiler, compiler.root_state, s, first_line=True,
                )

                # handle the scroll indicator
                if len(s) >= dim.width:
                    max_x = dim.width - 1
                else:
                    max_x = dim.width

                for r in regions:
                    style = self._theme.select(r.scope)
                    attr = style.attr(self._color_manager)
                    if r.start >= max_x:
                        break
                    stdscr.chgat(
                        draw_y,
                        r.start,
                        min(r.end, max_x) - r.start,
                        attr,
                    )

        for i in range(to_display, dim.height):
            stdscr.move(i + dim.y, 0)
            stdscr.clrtoeol()

    def focus(self, screen: Screen) -> None:
        while True:
            error = self.errors[self.y]
            if not error.disabled:
                screen.file.buf.assign_position(
                    screen.layout.file,
                    y=max(error.lineno - 1, 0),
                    x=max(error.col_offset - 1, 0),
                )

            screen.draw()
            self.draw(screen.stdscr, screen.layout.lint_errors, focused=True)
            screen.file.move_cursor(screen.stdscr, screen.layout.file)

            ch = screen.get_char()
            if ch.keyname == b'KEY_RESIZE':
                screen.resize()
            elif ch.keyname in {b'^C', b'^X'}:
                self.set_errors(())
                screen.resize()
                return
            elif ch.keyname in {b'^[', b'M-t'}:
                return
            elif ch.keyname == b'^T':
                screen.lint()
            elif ch.keyname == b'KEY_UP':
                self.y = max(self.y - 1, 0)
                if self.y < self.top:
                    self.top -= 2
            elif ch.keyname == b'KEY_DOWN':
                self.y = min(self.y + 1, len(self.errors) - 1)
                if self.top + screen.layout.lint_errors.height <= self.y:
                    self.top += 2
