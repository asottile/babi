from __future__ import annotations

import functools
import json
import os.path
from typing import Any
from typing import Match
from typing import NamedTuple
from typing import Tuple
from typing import TypeVar

from identify.identify import tags_from_filename
from identify.identify import tags_from_path

from babi._types import Protocol
from babi.fdict import FChainMap
from babi.reg import _Reg
from babi.reg import _RegSet
from babi.reg import ERR_REG
from babi.reg import expand_escaped
from babi.reg import make_reg
from babi.reg import make_regset

T = TypeVar('T')
Scope = Tuple[str, ...]
Regions = Tuple['Region', ...]
Captures = Tuple[Tuple[int, '_Rule'], ...]


def uniquely_constructed(t: T) -> T:
    """avoid tuple.__hash__ for "singleton" constructed objects"""
    t.__hash__ = object.__hash__  # type: ignore
    return t


def _split_name(s: str | None) -> tuple[str, ...]:
    if s is None:
        return ()
    else:
        return tuple(s.split())


class _Rule(Protocol):
    """hax for recursive types python/mypy#731"""
    @property
    def name(self) -> tuple[str, ...]: ...
    @property
    def match(self) -> str | None: ...
    @property
    def begin(self) -> str | None: ...
    @property
    def end(self) -> str | None: ...
    @property
    def while_(self) -> str | None: ...
    @property
    def content_name(self) -> tuple[str, ...]: ...
    @property
    def captures(self) -> Captures: ...
    @property
    def begin_captures(self) -> Captures: ...
    @property
    def end_captures(self) -> Captures: ...
    @property
    def while_captures(self) -> Captures: ...
    @property
    def include(self) -> str | None: ...
    @property
    def patterns(self) -> tuple[_Rule, ...]: ...
    @property
    def repository(self) -> FChainMap[str, _Rule]: ...


@uniquely_constructed
class Rule(NamedTuple):
    name: tuple[str, ...]
    match: str | None
    begin: str | None
    end: str | None
    while_: str | None
    content_name: tuple[str, ...]
    captures: Captures
    begin_captures: Captures
    end_captures: Captures
    while_captures: Captures
    include: str | None
    patterns: tuple[_Rule, ...]
    repository: FChainMap[str, _Rule]

    @classmethod
    def make(
            cls,
            dct: dict[str, Any],
            parent_repository: FChainMap[str, _Rule],
    ) -> _Rule:
        if 'repository' in dct:
            # this looks odd, but it's so we can have a self-referential
            # immutable-after-construction chain map
            repository_dct: dict[str, _Rule] = {}
            repository = FChainMap(parent_repository, repository_dct)
            for k, sub_dct in dct['repository'].items():
                repository_dct[k] = Rule.make(sub_dct, repository)
        else:
            repository = parent_repository

        name = _split_name(dct.get('name'))
        match = dct.get('match')
        begin = dct.get('begin')
        end = dct.get('end')
        while_ = dct.get('while')
        content_name = _split_name(dct.get('contentName'))

        if 'captures' in dct:
            captures = tuple(
                (int(k), Rule.make(v, repository))
                for k, v in dct['captures'].items()
            )
        else:
            captures = ()

        if 'beginCaptures' in dct:
            begin_captures = tuple(
                (int(k), Rule.make(v, repository))
                for k, v in dct['beginCaptures'].items()
            )
        else:
            begin_captures = ()

        if 'endCaptures' in dct:
            end_captures = tuple(
                (int(k), Rule.make(v, repository))
                for k, v in dct['endCaptures'].items()
            )
        else:
            end_captures = ()

        if 'whileCaptures' in dct:
            while_captures = tuple(
                (int(k), Rule.make(v, repository))
                for k, v in dct['whileCaptures'].items()
            )
        else:
            while_captures = ()

        # some grammars (at least xml) have begin rules with no end
        if begin is not None and end is None and while_ is None:
            end = '$impossible^'

        # Using the captures key for a begin/end/while rule is short-hand for
        # giving both beginCaptures and endCaptures with same values
        if begin and end and captures:
            begin_captures = end_captures = captures
            captures = ()
        elif begin and while_ and captures:
            begin_captures = while_captures = captures
            captures = ()

        include = dct.get('include')

        if 'patterns' in dct:
            patterns = tuple(Rule.make(d, repository) for d in dct['patterns'])
        else:
            patterns = ()

        return cls(
            name=name,
            match=match,
            begin=begin,
            end=end,
            while_=while_,
            content_name=content_name,
            captures=captures,
            begin_captures=begin_captures,
            end_captures=end_captures,
            while_captures=while_captures,
            include=include,
            patterns=patterns,
            repository=repository,
        )


@uniquely_constructed
class Grammar(NamedTuple):
    scope_name: str
    repository: FChainMap[str, _Rule]
    patterns: tuple[_Rule, ...]

    @classmethod
    def make(cls, data: dict[str, Any]) -> Grammar:
        scope_name = data['scopeName']
        if 'repository' in data:
            # this looks odd, but it's so we can have a self-referential
            # immutable-after-construction chain map
            repository_dct: dict[str, _Rule] = {}
            repository = FChainMap(repository_dct)
            for k, dct in data['repository'].items():
                repository_dct[k] = Rule.make(dct, repository)
        else:
            repository = FChainMap()
        patterns = tuple(Rule.make(d, repository) for d in data['patterns'])
        return cls(
            scope_name=scope_name,
            repository=repository,
            patterns=patterns,
        )


class Region(NamedTuple):
    start: int
    end: int
    scope: Scope


class State(NamedTuple):
    entries: tuple[Entry, ...]
    while_stack: tuple[tuple[WhileRule, int], ...]

    @classmethod
    def root(cls, entry: Entry) -> State:
        return cls((entry,), ())

    @property
    def cur(self) -> Entry:
        return self.entries[-1]

    def push(self, entry: Entry) -> State:
        return self._replace(entries=(*self.entries, entry))

    def pop(self) -> State:
        return self._replace(entries=self.entries[:-1])

    def push_while(self, rule: WhileRule, entry: Entry) -> State:
        entries = (*self.entries, entry)
        while_stack = (*self.while_stack, (rule, len(entries)))
        return self._replace(entries=entries, while_stack=while_stack)

    def pop_while(self) -> State:
        entries, while_stack = self.entries[:-1], self.while_stack[:-1]
        return self._replace(entries=entries, while_stack=while_stack)


class CompiledRule(Protocol):
    @property
    def name(self) -> tuple[str, ...]: ...

    def start(
            self,
            compiler: Compiler,
            match: Match[str],
            state: State,
    ) -> tuple[State, bool, Regions]:
        ...

    def search(
            self,
            compiler: Compiler,
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> tuple[State, int, bool, Regions] | None:
        ...


class CompiledRegsetRule(CompiledRule, Protocol):
    @property
    def regset(self) -> _RegSet: ...
    @property
    def u_rules(self) -> tuple[_Rule, ...]: ...


class Entry(NamedTuple):
    scope: tuple[str, ...]
    rule: CompiledRule
    start: tuple[str, int]
    reg: _Reg = ERR_REG
    boundary: bool = False


def _inner_capture_parse(
        compiler: Compiler,
        start: int,
        s: str,
        scope: Scope,
        rule: CompiledRule,
) -> Regions:
    state = State.root(Entry(scope + rule.name, rule, (s, 0)))
    _, regions = highlight_line(compiler, state, s, first_line=False)
    return tuple(
        r._replace(start=r.start + start, end=r.end + start) for r in regions
    )


def _captures(
        compiler: Compiler,
        scope: Scope,
        match: Match[str],
        captures: Captures,
) -> Regions:
    ret: list[Region] = []
    pos, pos_end = match.span()
    for i, u_rule in captures:
        try:
            group_s = match[i]
        except IndexError:  # some grammars are malformed here?
            continue
        if not group_s:
            continue

        rule = compiler.compile_rule(u_rule)
        start, end = match.span(i)
        if start < pos:
            # TODO: could maybe bisect but this is probably fast enough
            j = len(ret) - 1
            while j > 0 and start < ret[j - 1].end:
                j -= 1

            oldtok = ret[j]
            newtok = []
            if start > oldtok.start:
                newtok.append(oldtok._replace(end=start))

            newtok.extend(
                _inner_capture_parse(
                    compiler, start, match[i], oldtok.scope, rule,
                ),
            )

            if end < oldtok.end:
                newtok.append(oldtok._replace(start=end))
            ret[j:j + 1] = newtok
        else:
            if start > pos:
                ret.append(Region(pos, start, scope))

            ret.extend(
                _inner_capture_parse(compiler, start, match[i], scope, rule),
            )

            pos = end

    if pos < pos_end:
        ret.append(Region(pos, pos_end, scope))
    return tuple(ret)


def _do_regset(
        idx: int,
        match: Match[str] | None,
        rule: CompiledRegsetRule,
        compiler: Compiler,
        state: State,
        pos: int,
) -> tuple[State, int, bool, Regions] | None:
    if match is None:
        return None

    ret = []
    if match.start() > pos:
        ret.append(Region(pos, match.start(), state.cur.scope))

    target_rule = compiler.compile_rule(rule.u_rules[idx])
    state, boundary, regions = target_rule.start(compiler, match, state)
    ret.extend(regions)

    return state, match.end(), boundary, tuple(ret)


@uniquely_constructed
class PatternRule(NamedTuple):
    name: tuple[str, ...]
    regset: _RegSet
    u_rules: tuple[_Rule, ...]

    def start(
            self,
            compiler: Compiler,
            match: Match[str],
            state: State,
    ) -> tuple[State, bool, Regions]:
        raise AssertionError(f'unreachable {self}')

    def search(
            self,
            compiler: Compiler,
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> tuple[State, int, bool, Regions] | None:
        idx, match = self.regset.search(line, pos, first_line, boundary)
        return _do_regset(idx, match, self, compiler, state, pos)


@uniquely_constructed
class MatchRule(NamedTuple):
    name: tuple[str, ...]
    captures: Captures

    def start(
            self,
            compiler: Compiler,
            match: Match[str],
            state: State,
    ) -> tuple[State, bool, Regions]:
        scope = state.cur.scope + self.name
        return state, False, _captures(compiler, scope, match, self.captures)

    def search(
            self,
            compiler: Compiler,
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> tuple[State, int, bool, Regions] | None:
        raise AssertionError(f'unreachable {self}')


@uniquely_constructed
class EndRule(NamedTuple):
    name: tuple[str, ...]
    content_name: tuple[str, ...]
    begin_captures: Captures
    end_captures: Captures
    end: str
    regset: _RegSet
    u_rules: tuple[_Rule, ...]

    def start(
            self,
            compiler: Compiler,
            match: Match[str],
            state: State,
    ) -> tuple[State, bool, Regions]:
        scope = state.cur.scope + self.name
        next_scope = scope + self.content_name

        boundary = match.end() == len(match.string)
        reg = make_reg(expand_escaped(match, self.end))
        start = (match.string, match.start())
        state = state.push(Entry(next_scope, self, start, reg, boundary))
        regions = _captures(compiler, scope, match, self.begin_captures)
        return state, True, regions

    def _end_ret(
            self,
            compiler: Compiler,
            state: State,
            pos: int,
            m: Match[str],
    ) -> tuple[State, int, bool, Regions]:
        ret = []
        if m.start() > pos:
            ret.append(Region(pos, m.start(), state.cur.scope))
        ret.extend(_captures(compiler, state.cur.scope, m, self.end_captures))
        # this is probably a bug in the grammar, but it pushed and popped at
        # the same position.
        # we'll advance the highlighter by one position to get past the loop
        # this appears to be what vs code does as well
        if state.entries[-1].start == (m.string, m.end()):
            ret.append(Region(m.end(), m.end() + 1, state.cur.scope))
            end = m.end() + 1
        else:
            end = m.end()
        return state.pop(), end, False, tuple(ret)

    def search(
            self,
            compiler: Compiler,
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> tuple[State, int, bool, Regions] | None:
        end_match = state.cur.reg.search(line, pos, first_line, boundary)
        if end_match is not None and end_match.start() == pos:
            return self._end_ret(compiler, state, pos, end_match)
        elif end_match is None:
            idx, match = self.regset.search(line, pos, first_line, boundary)
            return _do_regset(idx, match, self, compiler, state, pos)
        else:
            idx, match = self.regset.search(line, pos, first_line, boundary)
            if match is None or end_match.start() <= match.start():
                return self._end_ret(compiler, state, pos, end_match)
            else:
                return _do_regset(idx, match, self, compiler, state, pos)


@uniquely_constructed
class WhileRule(NamedTuple):
    name: tuple[str, ...]
    content_name: tuple[str, ...]
    begin_captures: Captures
    while_captures: Captures
    while_: str
    regset: _RegSet
    u_rules: tuple[_Rule, ...]

    def start(
            self,
            compiler: Compiler,
            match: Match[str],
            state: State,
    ) -> tuple[State, bool, Regions]:
        scope = state.cur.scope + self.name
        next_scope = scope + self.content_name

        boundary = match.end() == len(match.string)
        reg = make_reg(expand_escaped(match, self.while_))
        start = (match.string, match.start())
        entry = Entry(next_scope, self, start, reg, boundary)
        state = state.push_while(self, entry)
        regions = _captures(compiler, scope, match, self.begin_captures)
        return state, True, regions

    def continues(
            self,
            compiler: Compiler,
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> tuple[int, bool, Regions] | None:
        match = state.cur.reg.match(line, pos, first_line, boundary)
        if match is None:
            return None

        ret = _captures(compiler, state.cur.scope, match, self.while_captures)
        return match.end(), True, ret

    def search(
            self,
            compiler: Compiler,
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> tuple[State, int, bool, Regions] | None:
        idx, match = self.regset.search(line, pos, first_line, boundary)
        return _do_regset(idx, match, self, compiler, state, pos)


class Compiler:
    def __init__(self, grammar: Grammar, grammars: Grammars) -> None:
        self._root_scope = grammar.scope_name
        self._grammars = grammars
        self._rule_to_grammar: dict[_Rule, Grammar] = {}
        self._c_rules: dict[_Rule, CompiledRule] = {}
        root = self._compile_root(grammar)
        self.root_state = State.root(Entry(root.name, root, ('', 0)))

    def _visit_rule(self, grammar: Grammar, rule: _Rule) -> _Rule:
        self._rule_to_grammar[rule] = grammar
        return rule

    @functools.lru_cache(maxsize=None)
    def _include(
            self,
            grammar: Grammar,
            repository: FChainMap[str, _Rule],
            s: str,
    ) -> tuple[list[str], tuple[_Rule, ...]]:
        if s == '$self':
            return self._patterns(grammar, grammar.patterns)
        elif s == '$base':
            grammar = self._grammars.grammar_for_scope(self._root_scope)
            return self._include(grammar, grammar.repository, '$self')
        elif s.startswith('#'):
            return self._patterns(grammar, (repository[s[1:]],))
        elif '#' not in s:
            grammar = self._grammars.grammar_for_scope(s)
            return self._include(grammar, grammar.repository, '$self')
        else:
            scope, _, s = s.partition('#')
            grammar = self._grammars.grammar_for_scope(scope)
            return self._include(grammar, grammar.repository, f'#{s}')

    @functools.lru_cache(maxsize=None)
    def _patterns(
            self,
            grammar: Grammar,
            rules: tuple[_Rule, ...],
    ) -> tuple[list[str], tuple[_Rule, ...]]:
        ret_regs = []
        ret_rules: list[_Rule] = []
        for rule in rules:
            if rule.include is not None:
                tmp_regs, tmp_rules = self._include(
                    grammar, rule.repository, rule.include,
                )
                ret_regs.extend(tmp_regs)
                ret_rules.extend(tmp_rules)
            elif rule.match is None and rule.begin is None and rule.patterns:
                tmp_regs, tmp_rules = self._patterns(grammar, rule.patterns)
                ret_regs.extend(tmp_regs)
                ret_rules.extend(tmp_rules)
            elif rule.match is not None:
                ret_regs.append(rule.match)
                ret_rules.append(self._visit_rule(grammar, rule))
            elif rule.begin is not None:
                ret_regs.append(rule.begin)
                ret_rules.append(self._visit_rule(grammar, rule))
            else:
                raise AssertionError(f'unreachable {rule}')
        return ret_regs, tuple(ret_rules)

    def _captures_ref(
            self,
            grammar: Grammar,
            captures: Captures,
    ) -> Captures:
        return tuple((n, self._visit_rule(grammar, r)) for n, r in captures)

    def _compile_root(self, grammar: Grammar) -> PatternRule:
        regs, rules = self._patterns(grammar, grammar.patterns)
        return PatternRule((grammar.scope_name,), make_regset(*regs), rules)

    def _compile_rule(self, grammar: Grammar, rule: _Rule) -> CompiledRule:
        assert rule.include is None, rule
        if rule.match is not None:
            captures_ref = self._captures_ref(grammar, rule.captures)
            return MatchRule(rule.name, captures_ref)
        elif rule.begin is not None and rule.end is not None:
            regs, rules = self._patterns(grammar, rule.patterns)
            return EndRule(
                rule.name,
                rule.content_name,
                self._captures_ref(grammar, rule.begin_captures),
                self._captures_ref(grammar, rule.end_captures),
                rule.end,
                make_regset(*regs),
                rules,
            )
        elif rule.begin is not None and rule.while_ is not None:
            regs, rules = self._patterns(grammar, rule.patterns)
            return WhileRule(
                rule.name,
                rule.content_name,
                self._captures_ref(grammar, rule.begin_captures),
                self._captures_ref(grammar, rule.while_captures),
                rule.while_,
                make_regset(*regs),
                rules,
            )
        else:
            regs, rules = self._patterns(grammar, rule.patterns)
            return PatternRule(rule.name, make_regset(*regs), rules)

    def compile_rule(self, rule: _Rule) -> CompiledRule:
        try:
            return self._c_rules[rule]
        except KeyError:
            pass

        grammar = self._rule_to_grammar[rule]
        ret = self._c_rules[rule] = self._compile_rule(grammar, rule)
        return ret


class Grammars:
    def __init__(self, *directories: str) -> None:
        self._scope_to_files = {
            os.path.splitext(filename)[0]: os.path.join(directory, filename)
            for directory in directories
            if os.path.exists(directory)
            for filename in sorted(os.listdir(directory))
            if filename.endswith('.json')
        }

        unknown_grammar = {'scopeName': 'source.unknown', 'patterns': []}
        self._raw = {'source.unknown': unknown_grammar}
        self._file_types: list[tuple[frozenset[str], str]] = []
        self._first_line: list[tuple[_Reg, str]] = []
        self._parsed: dict[str, Grammar] = {}
        self._compiled: dict[str, Compiler] = {}

    def _raw_for_scope(self, scope: str) -> dict[str, Any]:
        try:
            return self._raw[scope]
        except KeyError:
            pass

        grammar_path = self._scope_to_files.pop(scope)
        with open(grammar_path, encoding='UTF-8') as f:
            ret = self._raw[scope] = json.load(f)

        file_types = frozenset(ret.get('fileTypes', ()))
        first_line = make_reg(ret.get('firstLineMatch', '$impossible^'))

        self._file_types.append((file_types, scope))
        self._first_line.append((first_line, scope))

        return ret

    def grammar_for_scope(self, scope: str) -> Grammar:
        try:
            return self._parsed[scope]
        except KeyError:
            pass

        raw = self._raw_for_scope(scope)
        ret = self._parsed[scope] = Grammar.make(raw)
        return ret

    def compiler_for_scope(self, scope: str) -> Compiler:
        try:
            return self._compiled[scope]
        except KeyError:
            pass

        grammar = self.grammar_for_scope(scope)
        ret = self._compiled[scope] = Compiler(grammar, self)
        return ret

    def blank_compiler(self) -> Compiler:
        return self.compiler_for_scope('source.unknown')

    def compiler_for_file(self, filename: str, first_line: str) -> Compiler:
        try:
            tags = tags_from_path(filename)
        except ValueError:
            tags = tags_from_filename(filename)
        for tag in tags - {'text'}:
            try:
                # TODO: this doesn't always match even if we detect it
                return self.compiler_for_scope(f'source.{tag}')
            except KeyError:
                pass

        # didn't find it in the fast path, need to read all the json
        for k in tuple(self._scope_to_files):
            self._raw_for_scope(k)

        _, _, ext = os.path.basename(filename).rpartition('.')
        for extensions, scope in self._file_types:
            if ext in extensions:
                return self.compiler_for_scope(scope)

        for reg, scope in self._first_line:
            if reg.match(first_line, 0, first_line=True, boundary=True):
                return self.compiler_for_scope(scope)

        return self.compiler_for_scope('source.unknown')


def highlight_line(
        compiler: Compiler,
        state: State,
        line: str,
        first_line: bool,
) -> tuple[State, Regions]:
    ret: list[Region] = []
    pos = 0
    boundary = state.cur.boundary

    # TODO: this is still a little wasteful
    while_stack = []
    for while_rule, idx in state.while_stack:
        while_stack.append((while_rule, idx))
        while_state = State(state.entries[:idx], tuple(while_stack))

        while_res = while_rule.continues(
            compiler, while_state, line, pos, first_line, boundary,
        )
        if while_res is None:
            state = while_state.pop_while()
            break
        else:
            pos, boundary, regions = while_res
            ret.extend(regions)

    search_res = state.cur.rule.search(
        compiler, state, line, pos, first_line, boundary,
    )
    while search_res is not None:
        state, pos, boundary, regions = search_res
        ret.extend(regions)

        search_res = state.cur.rule.search(
            compiler, state, line, pos, first_line, boundary,
        )

    if pos < len(line):
        ret.append(Region(pos, len(line), state.cur.scope))

    return state, tuple(ret)
