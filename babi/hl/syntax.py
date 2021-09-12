from __future__ import annotations

import curses
import functools
import math
from typing import Callable
from typing import NamedTuple

from babi.buf import Buf
from babi.color_manager import ColorManager
from babi.highlight import Compiler
from babi.highlight import Grammars
from babi.highlight import highlight_line
from babi.highlight import State
from babi.hl.interface import HL
from babi.hl.interface import HLs
from babi.theme import Style
from babi.theme import Theme
from babi.user_data import prefix_data
from babi.user_data import xdg_config
from babi.user_data import xdg_data

A_ITALIC = getattr(curses, 'A_ITALIC', 0x80000000)  # not always present


class FileSyntax:
    include_edge = False

    def __init__(
            self,
            compiler: Compiler,
            theme: Theme,
            color_manager: ColorManager,
    ) -> None:
        self._compiler = compiler
        self._theme = theme
        self._color_manager = color_manager

        self.regions: list[HLs] = []
        self._states: list[State] = []

        # this will be assigned a functools.lru_cache per instance for
        # better hit rate and memory usage
        self._hl: Callable[[State, str, bool], tuple[State, HLs]] | None
        self._hl = None

    def attr(self, style: Style) -> int:
        pair = self._color_manager.color_pair(style.fg, style.bg)
        return (
            curses.color_pair(pair) |
            curses.A_BOLD * style.b |
            A_ITALIC * style.i |
            curses.A_UNDERLINE * style.u
        )

    def _hl_uncached(
            self,
            state: State,
            line: str,
            first_line: bool,
    ) -> tuple[State, HLs]:
        new_state, regions = highlight_line(
            self._compiler, state, f'{line}\n', first_line=first_line,
        )

        # remove the trailing newline
        new_end = regions[-1]._replace(end=regions[-1].end - 1)
        regions = regions[:-1] + (new_end,)

        regs: list[HL] = []
        for r in regions:
            style = self._theme.select(r.scope)
            if style == self._theme.default:
                continue

            attr = self.attr(style)
            if (
                    regs and
                    regs[-1].attr == attr and
                    regs[-1].end == r.start
            ):
                regs[-1] = regs[-1]._replace(end=r.end)
            else:
                regs.append(HL(x=r.start, end=r.end, attr=attr))

        return new_state, tuple(regs)

    def _set_cb(self, lines: Buf, idx: int, victim: str) -> None:
        del self.regions[idx:]
        del self._states[idx:]

    def _del_cb(self, lines: Buf, idx: int, victim: str) -> None:
        del self.regions[idx:]
        del self._states[idx:]

    def _ins_cb(self, lines: Buf, idx: int) -> None:
        del self.regions[idx:]
        del self._states[idx:]

    def register_callbacks(self, buf: Buf) -> None:
        buf.add_set_callback(self._set_cb)
        buf.add_del_callback(self._del_cb)
        buf.add_ins_callback(self._ins_cb)

    def highlight_until(self, lines: Buf, idx: int) -> None:
        if self._hl is None:
            # the docs claim better performance with power of two sizing
            size = max(4096, 2 ** (int(math.log(len(lines), 2)) + 2))
            self._hl = functools.lru_cache(maxsize=size)(self._hl_uncached)

        if not self._states:
            state = self._compiler.root_state
        else:
            state = self._states[-1]

        for i in range(len(self._states), idx):
            state, regions = self._hl(state, lines[i], i == 0)
            self._states.append(state)
            self.regions.append(regions)


class Syntax(NamedTuple):
    grammars: Grammars
    theme: Theme
    color_manager: ColorManager

    def file_highlighter(self, filename: str, first_line: str) -> FileSyntax:
        compiler = self.grammars.compiler_for_file(filename, first_line)
        return FileSyntax(compiler, self.theme, self.color_manager)

    def blank_file_highlighter(self) -> FileSyntax:
        compiler = self.grammars.blank_compiler()
        return FileSyntax(compiler, self.theme, self.color_manager)

    def _init_screen(self, stdscr: curses._CursesWindow) -> None:
        default_fg, default_bg = self.theme.default.fg, self.theme.default.bg
        all_colors = {c for c in (default_fg, default_bg) if c is not None}
        todo = list(self.theme.rules.children.values())
        while todo:
            rule = todo.pop()
            if rule.style.fg is not None:
                all_colors.add(rule.style.fg)
            if rule.style.bg is not None:
                all_colors.add(rule.style.bg)
            todo.extend(rule.children.values())

        for color in sorted(all_colors):
            self.color_manager.init_color(color)

        pair = self.color_manager.color_pair(default_fg, default_bg)
        stdscr.bkgd(' ', curses.color_pair(pair))

    @classmethod
    def from_screen(
            cls,
            stdscr: curses._CursesWindow,
            color_manager: ColorManager,
    ) -> Syntax:
        grammars = Grammars(prefix_data('grammar_v1'), xdg_data('grammar_v1'))
        theme = Theme.from_filename(xdg_config('theme.json'))
        ret = cls(grammars, theme, color_manager)
        ret._init_screen(stdscr)
        return ret
