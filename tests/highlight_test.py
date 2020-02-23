from babi.highlight import Grammar
from babi.highlight import Grammars
from babi.highlight import highlight_line
from babi.highlight import Region


def _compiler_state(grammar_dct, *others):
    grammar = Grammar.from_data(grammar_dct)
    grammars = [grammar, *(Grammar.from_data(dct) for dct in others)]
    compiler = Grammars(grammars).compiler_for_scope(grammar.scope_name)
    return compiler, compiler.root_state


def test_backslash_a():
    grammar = {
        'scopeName': 'test',
        'patterns': [{'name': 'aaa', 'match': r'\Aa+'}],
    }
    compiler, state = _compiler_state(grammar)

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


def test_backslash_g_inline():
    compiler, state = _compiler_state(BEGIN_END_NO_NL)

    _, regions = highlight_line(compiler, state, 'xaax', True)
    assert regions == (
        Region(0, 1, ('test',)),
        Region(1, 2, ('test', 'ga')),
        Region(2, 3, ('test', 'noga')),
        Region(3, 4, ('test',)),
    )


def test_backslash_g_next_line():
    compiler, state = _compiler_state(BEGIN_END_NO_NL)

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


def test_end_before_other_match():
    compiler, state = _compiler_state(BEGIN_END_NO_NL)

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


def test_backslash_g_captures_nl():
    compiler, state = _compiler_state(BEGIN_END_NL)

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


def test_backslash_g_captures_nl_next_line():
    compiler, state = _compiler_state(BEGIN_END_NL)

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


def test_while_no_nl():
    compiler, state = _compiler_state({
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


def test_complex_captures():
    compiler, state = _compiler_state({
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


def test_captures_multiple_applied_to_same_capture():
    compiler, state = _compiler_state({
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


def test_captures_ignores_empty():
    compiler, state = _compiler_state({
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


def test_captures_ignores_invalid_out_of_bounds():
    compiler, state = _compiler_state({
        'scopeName': 'test',
        'patterns': [{'match': '.', 'captures': {'1': {'name': 'oob'}}}],
    })

    state, regions = highlight_line(compiler, state, 'x', first_line=True)

    assert regions == (
        Region(0, 1, ('test',)),
    )


def test_captures_begin_end():
    compiler, state = _compiler_state({
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


def test_captures_while_captures():
    compiler, state = _compiler_state({
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


def test_captures_implies_begin_end_captures():
    compiler, state = _compiler_state({
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


def test_captures_implies_begin_while_captures():
    compiler, state = _compiler_state({
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


def test_include_self():
    compiler, state = _compiler_state({
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


def test_include_repository_rule():
    compiler, state = _compiler_state({
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


def test_include_other_grammar():
    compiler, state = _compiler_state(
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


def test_include_base():
    compiler, state = _compiler_state(
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
