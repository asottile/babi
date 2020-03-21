import curses
from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Tuple

from babi.color_manager import ColorManager
from babi.highlight import Compiler
from babi.highlight import Grammars
from babi.highlight import highlight_line
from babi.highlight import State
from babi.hl.interface import HL
from babi.hl.interface import HLs
from babi.list_spy import SequenceNoSlice
from babi.theme import Style
from babi.theme import Theme
from babi.user_data import xdg_config
from babi.user_data import xdg_data

A_ITALIC = getattr(curses, 'A_ITALIC', 0x80000000)  # new in py37


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

        self.regions: List[HLs] = []
        self._states: List[State] = []

        self._hl_cache: Dict[str, Dict[State, Tuple[State, HLs]]]
        self._hl_cache = {}

    def attr(self, style: Style) -> int:
        pair = self._color_manager.color_pair(style.fg, style.bg)
        return (
            curses.color_pair(pair) |
            curses.A_BOLD * style.b |
            A_ITALIC * style.i |
            curses.A_UNDERLINE * style.u
        )

    def _hl(
            self,
            state: State,
            line: str,
            i: int,
    ) -> Tuple[State, HLs]:
        try:
            return self._hl_cache[line][state]
        except KeyError:
            pass

        new_state, regions = highlight_line(
            self._compiler, state, f'{line}\n', first_line=i == 0,
        )

        # remove the trailing newline
        new_end = regions[-1]._replace(end=regions[-1].end - 1)
        regions = regions[:-1] + (new_end,)

        regs: List[HL] = []
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

        dct = self._hl_cache.setdefault(line, {})
        ret = dct[state] = (new_state, tuple(regs))
        return ret

    def highlight_until(self, lines: SequenceNoSlice, idx: int) -> None:
        if not self._states:
            state = self._compiler.root_state
        else:
            state = self._states[-1]

        for i in range(len(self._states), idx):
            state, regions = self._hl(state, lines[i], i)
            self._states.append(state)
            self.regions.append(regions)

    def touch(self, lineno: int) -> None:
        del self._states[lineno:]
        del self.regions[lineno:]


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

    def _init_screen(self, stdscr: 'curses._CursesWindow') -> None:
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
            stdscr: 'curses._CursesWindow',
            color_manager: ColorManager,
    ) -> 'Syntax':
        grammars = Grammars.from_syntax_dir(xdg_data('textmate_syntax'))
        theme = Theme.from_filename(xdg_config('theme.json'))
        ret = cls(grammars, theme, color_manager)
        ret._init_screen(stdscr)
        return ret
