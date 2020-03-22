import contextlib
import functools
import json
import os.path
from typing import Any
from typing import Dict
from typing import List
from typing import Match
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import TypeVar

from identify.identify import tags_from_filename

from babi._types import Protocol
from babi.fdict import FDict
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


def _split_name(s: Optional[str]) -> Tuple[str, ...]:
    if s is None:
        return ()
    else:
        return tuple(s.split())


class _Rule(Protocol):
    """hax for recursive types python/mypy#731"""
    @property
    def name(self) -> Tuple[str, ...]: ...
    @property
    def match(self) -> Optional[str]: ...
    @property
    def begin(self) -> Optional[str]: ...
    @property
    def end(self) -> Optional[str]: ...
    @property
    def while_(self) -> Optional[str]: ...
    @property
    def content_name(self) -> Tuple[str, ...]: ...
    @property
    def captures(self) -> Captures: ...
    @property
    def begin_captures(self) -> Captures: ...
    @property
    def end_captures(self) -> Captures: ...
    @property
    def while_captures(self) -> Captures: ...
    @property
    def include(self) -> Optional[str]: ...
    @property
    def patterns(self) -> 'Tuple[_Rule, ...]': ...


@uniquely_constructed
class Rule(NamedTuple):
    name: Tuple[str, ...]
    match: Optional[str]
    begin: Optional[str]
    end: Optional[str]
    while_: Optional[str]
    content_name: Tuple[str, ...]
    captures: Captures
    begin_captures: Captures
    end_captures: Captures
    while_captures: Captures
    include: Optional[str]
    patterns: Tuple[_Rule, ...]

    @classmethod
    def from_dct(cls, dct: Dict[str, Any]) -> _Rule:
        name = _split_name(dct.get('name'))
        match = dct.get('match')
        begin = dct.get('begin')
        end = dct.get('end')
        while_ = dct.get('while')
        content_name = _split_name(dct.get('contentName'))

        if 'captures' in dct:
            captures = tuple(
                (int(k), Rule.from_dct(v))
                for k, v in dct['captures'].items()
            )
        else:
            captures = ()

        if 'beginCaptures' in dct:
            begin_captures = tuple(
                (int(k), Rule.from_dct(v))
                for k, v in dct['beginCaptures'].items()
            )
        else:
            begin_captures = ()

        if 'endCaptures' in dct:
            end_captures = tuple(
                (int(k), Rule.from_dct(v))
                for k, v in dct['endCaptures'].items()
            )
        else:
            end_captures = ()

        if 'whileCaptures' in dct:
            while_captures = tuple(
                (int(k), Rule.from_dct(v))
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
            patterns = tuple(Rule.from_dct(d) for d in dct['patterns'])
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
        )


@uniquely_constructed
class Grammar(NamedTuple):
    scope_name: str
    patterns: Tuple[_Rule, ...]
    repository: FDict[str, _Rule]

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> 'Grammar':
        scope_name = data['scopeName']
        patterns = tuple(Rule.from_dct(dct) for dct in data['patterns'])
        if 'repository' in data:
            repository = FDict({
                k: Rule.from_dct(dct) for k, dct in data['repository'].items()
            })
        else:
            repository = FDict({})
        return cls(
            scope_name=scope_name,
            patterns=patterns,
            repository=repository,
        )


class Region(NamedTuple):
    start: int
    end: int
    scope: Scope


class State(NamedTuple):
    entries: Tuple['Entry', ...]
    while_stack: Tuple[Tuple['WhileRule', int], ...]

    @classmethod
    def root(cls, entry: 'Entry') -> 'State':
        return cls((entry,), ())

    @property
    def cur(self) -> 'Entry':
        return self.entries[-1]

    def push(self, entry: 'Entry') -> 'State':
        return self._replace(entries=(*self.entries, entry))

    def pop(self) -> 'State':
        return self._replace(entries=self.entries[:-1])

    def push_while(self, rule: 'WhileRule', entry: 'Entry') -> 'State':
        entries = (*self.entries, entry)
        while_stack = (*self.while_stack, (rule, len(entries)))
        return self._replace(entries=entries, while_stack=while_stack)

    def pop_while(self) -> 'State':
        entries, while_stack = self.entries[:-1], self.while_stack[:-1]
        return self._replace(entries=entries, while_stack=while_stack)


class CompiledRule(Protocol):
    @property
    def name(self) -> Tuple[str, ...]: ...

    def start(
            self,
            compiler: 'Compiler',
            match: Match[str],
            state: State,
    ) -> Tuple[State, bool, Regions]:
        ...

    def search(
            self,
            compiler: 'Compiler',
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> Optional[Tuple[State, int, bool, Regions]]:
        ...


class CompiledRegsetRule(CompiledRule, Protocol):
    @property
    def regset(self) -> _RegSet: ...
    @property
    def u_rules(self) -> Tuple[_Rule, ...]: ...


class Entry(NamedTuple):
    scope: Tuple[str, ...]
    rule: CompiledRule
    reg: _Reg = ERR_REG
    boundary: bool = False


def _inner_capture_parse(
        compiler: 'Compiler',
        start: int,
        s: str,
        scope: Scope,
        rule: CompiledRule,
) -> Regions:
    state = State.root(Entry(scope + rule.name, rule))
    _, regions = highlight_line(compiler, state, s, first_line=False)
    return tuple(
        r._replace(start=r.start + start, end=r.end + start) for r in regions
    )


def _captures(
        compiler: 'Compiler',
        scope: Scope,
        match: Match[str],
        captures: Captures,
) -> Regions:
    ret: List[Region] = []
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
        match: Optional[Match[str]],
        rule: CompiledRegsetRule,
        compiler: 'Compiler',
        state: State,
        pos: int,
) -> Optional[Tuple[State, int, bool, Regions]]:
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
    name: Tuple[str, ...]
    regset: _RegSet
    u_rules: Tuple[_Rule, ...]

    def start(
            self,
            compiler: 'Compiler',
            match: Match[str],
            state: State,
    ) -> Tuple[State, bool, Regions]:
        raise AssertionError(f'unreachable {self}')

    def search(
            self,
            compiler: 'Compiler',
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> Optional[Tuple[State, int, bool, Regions]]:
        idx, match = self.regset.search(line, pos, first_line, boundary)
        return _do_regset(idx, match, self, compiler, state, pos)


@uniquely_constructed
class MatchRule(NamedTuple):
    name: Tuple[str, ...]
    captures: Captures

    def start(
            self,
            compiler: 'Compiler',
            match: Match[str],
            state: State,
    ) -> Tuple[State, bool, Regions]:
        scope = state.cur.scope + self.name
        return state, False, _captures(compiler, scope, match, self.captures)

    def search(
            self,
            compiler: 'Compiler',
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> Optional[Tuple[State, int, bool, Regions]]:
        raise AssertionError(f'unreachable {self}')


@uniquely_constructed
class EndRule(NamedTuple):
    name: Tuple[str, ...]
    content_name: Tuple[str, ...]
    begin_captures: Captures
    end_captures: Captures
    end: str
    regset: _RegSet
    u_rules: Tuple[_Rule, ...]

    def start(
            self,
            compiler: 'Compiler',
            match: Match[str],
            state: State,
    ) -> Tuple[State, bool, Regions]:
        scope = state.cur.scope + self.name
        next_scope = scope + self.content_name

        boundary = match.end() == len(match.string)
        reg = make_reg(expand_escaped(match, self.end))
        state = state.push(Entry(next_scope, self, reg, boundary))
        regions = _captures(compiler, scope, match, self.begin_captures)
        return state, True, regions

    def _end_ret(
            self,
            compiler: 'Compiler',
            state: State,
            pos: int,
            m: Match[str],
    ) -> Tuple[State, int, bool, Regions]:
        ret = []
        if m.start() > pos:
            ret.append(Region(pos, m.start(), state.cur.scope))
        ret.extend(_captures(compiler, state.cur.scope, m, self.end_captures))
        return state.pop(), m.end(), False, tuple(ret)

    def search(
            self,
            compiler: 'Compiler',
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> Optional[Tuple[State, int, bool, Regions]]:
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
    name: Tuple[str, ...]
    content_name: Tuple[str, ...]
    begin_captures: Captures
    while_captures: Captures
    while_: str
    regset: _RegSet
    u_rules: Tuple[_Rule, ...]

    def start(
            self,
            compiler: 'Compiler',
            match: Match[str],
            state: State,
    ) -> Tuple[State, bool, Regions]:
        scope = state.cur.scope + self.name
        next_scope = scope + self.content_name

        boundary = match.end() == len(match.string)
        reg = make_reg(expand_escaped(match, self.while_))
        state = state.push_while(self, Entry(next_scope, self, reg, boundary))
        regions = _captures(compiler, scope, match, self.begin_captures)
        return state, True, regions

    def continues(
            self,
            compiler: 'Compiler',
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> Optional[Tuple[int, bool, Regions]]:
        match = state.cur.reg.match(line, pos, first_line, boundary)
        if match is None:
            return None

        ret = _captures(compiler, state.cur.scope, match, self.while_captures)
        return match.end(), True, ret

    def search(
            self,
            compiler: 'Compiler',
            state: State,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> Optional[Tuple[State, int, bool, Regions]]:
        idx, match = self.regset.search(line, pos, first_line, boundary)
        return _do_regset(idx, match, self, compiler, state, pos)


class Compiler:
    def __init__(self, grammar: Grammar, grammars: 'Grammars') -> None:
        self._root_scope = grammar.scope_name
        self._grammars = grammars
        self._rule_to_grammar: Dict[_Rule, Grammar] = {}
        self._c_rules: Dict[_Rule, CompiledRule] = {}
        root = self._compile_root(grammar)
        self.root_state = State.root(Entry(root.name, root))

    def _visit_rule(self, grammar: Grammar, rule: _Rule) -> _Rule:
        self._rule_to_grammar[rule] = grammar
        return rule

    @functools.lru_cache(maxsize=None)
    def _include(
            self,
            grammar: Grammar,
            s: str,
    ) -> Tuple[List[str], Tuple[_Rule, ...]]:
        if s == '$self':
            return self._patterns(grammar, grammar.patterns)
        elif s == '$base':
            grammar = self._grammars.grammar_for_scope(self._root_scope)
            return self._include(grammar, '$self')
        elif s.startswith('#'):
            return self._patterns(grammar, (grammar.repository[s[1:]],))
        elif '#' not in s:
            grammar = self._grammars.grammar_for_scope(s)
            return self._include(grammar, '$self')
        else:
            scope, _, s = s.partition('#')
            grammar = self._grammars.grammar_for_scope(scope)
            return self._include(grammar, f'#{s}')

    @functools.lru_cache(maxsize=None)
    def _patterns(
            self,
            grammar: Grammar,
            rules: Tuple[_Rule, ...],
    ) -> Tuple[List[str], Tuple[_Rule, ...]]:
        ret_regs = []
        ret_rules: List[_Rule] = []
        for rule in rules:
            if rule.include is not None:
                tmp_regs, tmp_rules = self._include(grammar, rule.include)
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
        with contextlib.suppress(KeyError):
            return self._c_rules[rule]

        grammar = self._rule_to_grammar[rule]
        ret = self._c_rules[rule] = self._compile_rule(grammar, rule)
        return ret


class Grammars:
    def __init__(self, grammars: Sequence[Dict[str, Any]]) -> None:
        self._raw = {grammar['scopeName']: grammar for grammar in grammars}
        self._find_scope = [
            (
                frozenset(grammar.get('fileTypes', ())),
                make_reg(grammar.get('firstLineMatch', '$impossible^')),
                grammar['scopeName'],
            )
            for grammar in grammars
        ]
        self._parsed: Dict[str, Grammar] = {}
        self._compilers: Dict[str, Compiler] = {}

    @classmethod
    def from_syntax_dir(cls, syntax_dir: str) -> 'Grammars':
        grammars = [{'scopeName': 'source.unknown', 'patterns': []}]
        if os.path.exists(syntax_dir):
            for filename in os.listdir(syntax_dir):
                with open(os.path.join(syntax_dir, filename)) as f:
                    grammars.append(json.load(f))
        return cls(grammars)

    def grammar_for_scope(self, scope: str) -> Grammar:
        with contextlib.suppress(KeyError):
            return self._parsed[scope]

        ret = self._parsed[scope] = Grammar.from_data(self._raw[scope])
        return ret

    def compiler_for_scope(self, scope: str) -> Compiler:
        with contextlib.suppress(KeyError):
            return self._compilers[scope]

        grammar = self.grammar_for_scope(scope)
        ret = self._compilers[scope] = Compiler(grammar, self)
        return ret

    def blank_compiler(self) -> Compiler:
        return self.compiler_for_scope('source.unknown')

    def compiler_for_file(self, filename: str, first_line: str) -> Compiler:
        for tag in tags_from_filename(filename) - {'text'}:
            with contextlib.suppress(KeyError):
                return self.compiler_for_scope(f'source.{tag}')

        _, _, ext = os.path.basename(filename).rpartition('.')
        for extensions, first_line_match, scope_name in self._find_scope:
            if (
                    ext in extensions or
                    first_line_match.match(
                        first_line, 0, first_line=True, boundary=True,
                    )
            ):
                return self.compiler_for_scope(scope_name)
        else:
            return self.compiler_for_scope('source.unknown')


def highlight_line(
        compiler: 'Compiler',
        state: State,
        line: str,
        first_line: bool,
) -> Tuple[State, Regions]:
    ret: List[Region] = []
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
