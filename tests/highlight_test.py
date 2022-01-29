from __future__ import annotations

import stat

import pytest

from babi.highlight import highlight_line
from babi.highlight import Region


def test_grammar_matches_extension_only_name(make_grammars):
    data = {'scopeName': 'shell', 'patterns': [], 'fileTypes': ['bashrc']}
    grammars = make_grammars(data)
    compiler = grammars.compiler_for_file('.bashrc', 'alias nano=babi')
    assert compiler.root_state.entries[0].scope[0] == 'shell'


def test_file_without_extension(tmpdir, make_grammars):
    f = tmpdir.join('f')
    f.write('#!/usr/bin/env python3')
    f.chmod(stat.S_IRWXU)

    data = {'scopeName': 'source.python', 'patterns': []}
    grammars = make_grammars(data)
    compiler = grammars.compiler_for_file(str(f), f.read())
    assert compiler.root_state.entries[0].scope[0] == 'source.python'


def test_grammar_matches_via_identify_tag(make_grammars):
    grammars = make_grammars({'scopeName': 'source.ini', 'patterns': []})
    compiler = grammars.compiler_for_file('setup.cfg', '')
    assert compiler.root_state.entries[0].scope[0] == 'source.ini'


@pytest.fixture
def compiler_state(make_grammars):
    def _compiler_state(*grammar_dcts):
        grammars = make_grammars(*grammar_dcts)
        compiler = grammars.compiler_for_scope(grammar_dcts[0]['scopeName'])
        return compiler, compiler.root_state
    return _compiler_state


def test_backslash_a(compiler_state):
    grammar = {
        'scopeName': 'test',
        'patterns': [{'name': 'aaa', 'match': r'\Aa+'}],
    }
    compiler, state = compiler_state(grammar)

    state, (region_0,) = highlight_line(compiler, state, 'aaa', True)
    state, (region_1,) = highlight_line(compiler, state, 'aaa', False)

    # \A should only match at the beginning of the file
    assert region_0 == Region(0, 3, ('test', 'aaa'))
    assert region_1 == Region(0, 3, ('test',))


BEGIN_END_NO_NL = {
    'scopeName': 'test',
    'patterns': [{
        'begin': 'x',
        'end': 'x',
        'patterns': [
            {'match': r'\Ga', 'name': 'ga'},
            {'match': 'a', 'name': 'noga'},
        ],
    }],
}


def test_backslash_g_inline(compiler_state):
    compiler, state = compiler_state(BEGIN_END_NO_NL)

    _, regions = highlight_line(compiler, state, 'xaax', True)
    assert regions == (
        Region(0, 1, ('test',)),
        Region(1, 2, ('test', 'ga')),
        Region(2, 3, ('test', 'noga')),
        Region(3, 4, ('test',)),
    )


def test_backslash_g_next_line(compiler_state):
    compiler, state = compiler_state(BEGIN_END_NO_NL)

    state, regions1 = highlight_line(compiler, state, 'x\n', True)
    state, regions2 = highlight_line(compiler, state, 'aax\n', False)

    assert regions1 == (
        Region(0, 1, ('test',)),
        Region(1, 2, ('test',)),
    )
    assert regions2 == (
        Region(0, 1, ('test', 'noga')),
        Region(1, 2, ('test', 'noga')),
        Region(2, 3, ('test',)),
        Region(3, 4, ('test',)),
    )


def test_end_before_other_match(compiler_state):
    compiler, state = compiler_state(BEGIN_END_NO_NL)

    state, regions = highlight_line(compiler, state, 'xazzx', True)

    assert regions == (
        Region(0, 1, ('test',)),
        Region(1, 2, ('test', 'ga')),
        Region(2, 4, ('test',)),
        Region(4, 5, ('test',)),
    )


BEGIN_END_NL = {
    'scopeName': 'test',
    'patterns': [{
        'begin': r'x$\n?',
        'end': 'x',
        'patterns': [
            {'match': r'\Ga', 'name': 'ga'},
            {'match': 'a', 'name': 'noga'},
        ],
    }],
}


def test_backslash_g_captures_nl(compiler_state):
    compiler, state = compiler_state(BEGIN_END_NL)

    state, regions1 = highlight_line(compiler, state, 'x\n', True)
    state, regions2 = highlight_line(compiler, state, 'aax\n', False)

    assert regions1 == (
        Region(0, 2, ('test',)),
    )
    assert regions2 == (
        Region(0, 1, ('test', 'ga')),
        Region(1, 2, ('test', 'noga')),
        Region(2, 3, ('test',)),
        Region(3, 4, ('test',)),
    )


def test_backslash_g_captures_nl_next_line(compiler_state):
    compiler, state = compiler_state(BEGIN_END_NL)

    state, regions1 = highlight_line(compiler, state, 'x\n', True)
    state, regions2 = highlight_line(compiler, state, 'aa\n', False)
    state, regions3 = highlight_line(compiler, state, 'aax\n', False)

    assert regions1 == (
        Region(0, 2, ('test',)),
    )
    assert regions2 == (
        Region(0, 1, ('test', 'ga')),
        Region(1, 2, ('test', 'noga')),
        Region(2, 3, ('test',)),
    )
    assert regions3 == (
        Region(0, 1, ('test', 'ga')),
        Region(1, 2, ('test', 'noga')),
        Region(2, 3, ('test',)),
        Region(3, 4, ('test',)),
    )


def test_while_no_nl(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [{
            'begin': '> ',
            'while': '> ',
            'contentName': 'while',
            'patterns': [
                {'match': r'\Ga', 'name': 'ga'},
                {'match': 'a', 'name': 'noga'},
            ],
        }],
    })

    state, regions1 = highlight_line(compiler, state, '> aa\n', True)
    state, regions2 = highlight_line(compiler, state, '> aa\n', False)
    state, regions3 = highlight_line(compiler, state, 'after\n', False)

    assert regions1 == (
        Region(0, 2, ('test',)),
        Region(2, 3, ('test', 'while', 'ga')),
        Region(3, 4, ('test', 'while', 'noga')),
        Region(4, 5, ('test', 'while')),
    )
    assert regions2 == (
        Region(0, 2, ('test', 'while')),
        Region(2, 3, ('test', 'while', 'ga')),
        Region(3, 4, ('test', 'while', 'noga')),
        Region(4, 5, ('test', 'while')),
    )
    assert regions3 == (
        Region(0, 6, ('test',)),
    )


def test_complex_captures(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [
            {
                'match': '(<).([^>]+)(>)',
                'captures': {
                    '1': {'name': 'lbracket'},
                    '2': {
                        'patterns': [
                            {'match': 'a', 'name': 'a'},
                            {'match': 'z', 'name': 'z'},
                        ],
                    },
                    '3': {'name': 'rbracket'},
                },
            },
        ],
    })

    state, regions = highlight_line(compiler, state, '<qabz>', first_line=True)
    assert regions == (
        Region(0, 1, ('test', 'lbracket')),
        Region(1, 2, ('test',)),
        Region(2, 3, ('test', 'a')),
        Region(3, 4, ('test',)),
        Region(4, 5, ('test', 'z')),
        Region(5, 6, ('test', 'rbracket')),
    )


def test_captures_multiple_applied_to_same_capture(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [
            {
                'match': '((a)) ((b) c) (d (e)) ((f) )',
                'name': 'matched',
                'captures': {
                    '1': {'name': 'g1'},
                    '2': {'name': 'g2'},
                    '3': {'name': 'g3'},
                    '4': {'name': 'g4'},
                    '5': {'name': 'g5'},
                    '6': {'name': 'g6'},
                    '7': {
                        'patterns': [
                            {'match': 'f', 'name': 'g7f'},
                            {'match': ' ', 'name': 'g7space'},
                        ],
                    },
                    # this one has to backtrack some
                    '8': {'name': 'g8'},
                },
            },
        ],
    })

    state, regions = highlight_line(compiler, state, 'a b c d e f ', True)

    assert regions == (
        Region(0, 1, ('test', 'matched', 'g1', 'g2')),
        Region(1, 2, ('test', 'matched')),
        Region(2, 3, ('test', 'matched', 'g3', 'g4')),
        Region(3, 5, ('test', 'matched', 'g3')),
        Region(5, 6, ('test', 'matched')),
        Region(6, 8, ('test', 'matched', 'g5')),
        Region(8, 9, ('test', 'matched', 'g5', 'g6')),
        Region(9, 10, ('test', 'matched')),
        Region(10, 11, ('test', 'matched', 'g7f', 'g8')),
        Region(11, 12, ('test', 'matched', 'g7space')),
    )


def test_captures_ignores_empty(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [{
            'match': '(.*) hi',
            'captures': {'1': {'name': 'before'}},
        }],
    })

    state, regions1 = highlight_line(compiler, state, ' hi\n', True)
    state, regions2 = highlight_line(compiler, state, 'o hi\n', False)

    assert regions1 == (
        Region(0, 3, ('test',)),
        Region(3, 4, ('test',)),
    )
    assert regions2 == (
        Region(0, 1, ('test', 'before')),
        Region(1, 4, ('test',)),
        Region(4, 5, ('test',)),
    )


def test_captures_ignores_invalid_out_of_bounds(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [{'match': '.', 'captures': {'1': {'name': 'oob'}}}],
    })

    state, regions = highlight_line(compiler, state, 'x', first_line=True)

    assert regions == (
        Region(0, 1, ('test',)),
    )


def test_captures_begin_end(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [
            {
                'begin': '(""")',
                'end': '(""")',
                'beginCaptures': {'1': {'name': 'startquote'}},
                'endCaptures': {'1': {'name': 'endquote'}},
            },
        ],
    })

    state, regions = highlight_line(compiler, state, '"""x"""', True)

    assert regions == (
        Region(0, 3, ('test', 'startquote')),
        Region(3, 4, ('test',)),
        Region(4, 7, ('test', 'endquote')),
    )


def test_captures_while_captures(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [
            {
                'begin': '(>) ',
                'while': '(>) ',
                'beginCaptures': {'1': {'name': 'bblock'}},
                'whileCaptures': {'1': {'name': 'wblock'}},
            },
        ],
    })

    state, regions1 = highlight_line(compiler, state, '> x\n', True)
    state, regions2 = highlight_line(compiler, state, '> x\n', False)

    assert regions1 == (
        Region(0, 1, ('test', 'bblock')),
        Region(1, 2, ('test',)),
        Region(2, 4, ('test',)),
    )

    assert regions2 == (
        Region(0, 1, ('test', 'wblock')),
        Region(1, 2, ('test',)),
        Region(2, 4, ('test',)),
    )


def test_captures_implies_begin_end_captures(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [
            {
                'begin': '(""")',
                'end': '(""")',
                'captures': {'1': {'name': 'quote'}},
            },
        ],
    })

    state, regions = highlight_line(compiler, state, '"""x"""', True)

    assert regions == (
        Region(0, 3, ('test', 'quote')),
        Region(3, 4, ('test',)),
        Region(4, 7, ('test', 'quote')),
    )


def test_captures_implies_begin_while_captures(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [
            {
                'begin': '(>) ',
                'while': '(>) ',
                'captures': {'1': {'name': 'block'}},
            },
        ],
    })

    state, regions1 = highlight_line(compiler, state, '> x\n', True)
    state, regions2 = highlight_line(compiler, state, '> x\n', False)

    assert regions1 == (
        Region(0, 1, ('test', 'block')),
        Region(1, 2, ('test',)),
        Region(2, 4, ('test',)),
    )

    assert regions2 == (
        Region(0, 1, ('test', 'block')),
        Region(1, 2, ('test',)),
        Region(2, 4, ('test',)),
    )


def test_include_self(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [
            {
                'begin': '<',
                'end': '>',
                'contentName': 'bracketed',
                'patterns': [{'include': '$self'}],
            },
            {'match': '.', 'name': 'content'},
        ],
    })

    state, regions = highlight_line(compiler, state, '<<_>>', first_line=True)
    assert regions == (
        Region(0, 1, ('test',)),
        Region(1, 2, ('test', 'bracketed')),
        Region(2, 3, ('test', 'bracketed', 'bracketed', 'content')),
        Region(3, 4, ('test', 'bracketed', 'bracketed')),
        Region(4, 5, ('test', 'bracketed')),
    )


def test_include_repository_rule(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [{'include': '#impl'}],
        'repository': {
            'impl': {
                'patterns': [
                    {'match': 'a', 'name': 'a'},
                    {'match': '.', 'name': 'other'},
                ],
            },
        },
    })

    state, regions = highlight_line(compiler, state, 'az', first_line=True)

    assert regions == (
        Region(0, 1, ('test', 'a')),
        Region(1, 2, ('test', 'other')),
    )


def test_include_with_nested_repositories(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [{
            'begin': '<', 'end': '>', 'name': 'b',
            'patterns': [
                {'include': '#rule1'},
                {'include': '#rule2'},
                {'include': '#rule3'},
            ],
            'repository': {
                'rule2': {'match': '2', 'name': 'inner2'},
                'rule3': {'match': '3', 'name': 'inner3'},
            },
        }],
        'repository': {
            'rule1': {'match': '1', 'name': 'root1'},
            'rule2': {'match': '2', 'name': 'root2'},
        },
    })

    state, regions = highlight_line(compiler, state, '<123>', first_line=True)

    assert regions == (
        Region(0, 1, ('test', 'b')),
        Region(1, 2, ('test', 'b', 'root1')),
        Region(2, 3, ('test', 'b', 'inner2')),
        Region(3, 4, ('test', 'b', 'inner3')),
        Region(4, 5, ('test', 'b')),
    )


def test_include_other_grammar(compiler_state):
    compiler, state = compiler_state(
        {
            'scopeName': 'test',
            'patterns': [
                {
                    'begin': '<',
                    'end': '>',
                    'name': 'angle',
                    'patterns': [{'include': 'other.grammar'}],
                },
                {
                    'begin': '`',
                    'end': '`',
                    'name': 'tick',
                    'patterns': [{'include': 'other.grammar#backtick'}],
                },
            ],
        },
        {
            'scopeName': 'other.grammar',
            'patterns': [
                {'match': 'a', 'name': 'roota'},
                {'match': '.', 'name': 'rootother'},
            ],
            'repository': {
                'backtick': {
                    'patterns': [
                        {'match': 'a', 'name': 'ticka'},
                        {'match': '.', 'name': 'tickother'},
                    ],
                },
            },
        },
    )

    state, regions1 = highlight_line(compiler, state, '<az>\n', True)
    state, regions2 = highlight_line(compiler, state, '`az`\n', False)

    assert regions1 == (
        Region(0, 1, ('test', 'angle')),
        Region(1, 2, ('test', 'angle', 'roota')),
        Region(2, 3, ('test', 'angle', 'rootother')),
        Region(3, 4, ('test', 'angle')),
        Region(4, 5, ('test',)),
    )

    assert regions2 == (
        Region(0, 1, ('test', 'tick')),
        Region(1, 2, ('test', 'tick', 'ticka')),
        Region(2, 3, ('test', 'tick', 'tickother')),
        Region(3, 4, ('test', 'tick')),
        Region(4, 5, ('test',)),
    )


def test_include_base(compiler_state):
    compiler, state = compiler_state(
        {
            'scopeName': 'test',
            'patterns': [
                {
                    'begin': '<',
                    'end': '>',
                    'name': 'bracket',
                    # $base from root grammar includes itself
                    'patterns': [{'include': '$base'}],
                },
                {'include': 'other.grammar'},
                {'match': 'z', 'name': 'testz'},
            ],
        },
        {
            'scopeName': 'other.grammar',
            'patterns': [
                {
                    'begin': '`',
                    'end': '`',
                    'name': 'tick',
                    # $base from included grammar includes the root
                    'patterns': [{'include': '$base'}],
                },
            ],
        },
    )

    state, regions1 = highlight_line(compiler, state, '<z>\n', True)
    state, regions2 = highlight_line(compiler, state, '`z`\n', False)

    assert regions1 == (
        Region(0, 1, ('test', 'bracket')),
        Region(1, 2, ('test', 'bracket', 'testz')),
        Region(2, 3, ('test', 'bracket')),
        Region(3, 4, ('test',)),
    )

    assert regions2 == (
        Region(0, 1, ('test', 'tick')),
        Region(1, 2, ('test', 'tick', 'testz')),
        Region(2, 3, ('test', 'tick')),
        Region(3, 4, ('test',)),
    )


def test_rule_with_begin_and_no_end(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [
            {
                'begin': '!', 'end': '!', 'name': 'bang',
                'patterns': [{'begin': '--', 'name': 'invalid'}],
            },
        ],
    })

    state, regions = highlight_line(compiler, state, '!x! !--!', True)

    assert regions == (
        Region(0, 1, ('test', 'bang')),
        Region(1, 2, ('test', 'bang')),
        Region(2, 3, ('test', 'bang')),
        Region(3, 4, ('test',)),
        Region(4, 5, ('test', 'bang')),
        Region(5, 7, ('test', 'bang', 'invalid')),
        Region(7, 8, ('test', 'bang', 'invalid')),
    )


def test_begin_end_substitute_special_chars(compiler_state):
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [{'begin': r'(\*)', 'end': r'\1', 'name': 'italic'}],
    })

    state, regions = highlight_line(compiler, state, '*italic*', True)

    assert regions == (
        Region(0, 1, ('test', 'italic')),
        Region(1, 7, ('test', 'italic')),
        Region(7, 8, ('test', 'italic')),
    )


def test_backslash_z(compiler_state):
    # similar to text.git-commit grammar, \z matches nothing!
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [
            {'begin': '#', 'end': r'\z', 'name': 'comment'},
            {'name': 'other', 'match': '.'},
        ],
    })

    state, regions1 = highlight_line(compiler, state, '# comment', True)
    state, regions2 = highlight_line(compiler, state, 'other?', False)

    assert regions1 == (
        Region(0, 1, ('test', 'comment')),
        Region(1, 9, ('test', 'comment')),
    )

    assert regions2 == (
        Region(0, 6, ('test', 'comment')),
    )


def test_buggy_begin_end_grammar(compiler_state):
    # before this would result in an infinite loop of start / end
    compiler, state = compiler_state({
        'scopeName': 'test',
        'patterns': [
            {
                'begin': '(?=</style)',
                'end': '(?=</style)',
                'name': 'css',
            },
        ],
    })

    state, regions = highlight_line(compiler, state, 'test </style', True)

    assert regions == (
        Region(0, 5, ('test',)),
        Region(5, 6, ('test', 'css')),
        Region(6, 12, ('test',)),
    )
