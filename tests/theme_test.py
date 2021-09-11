from __future__ import annotations

import pytest

from babi.color import Color
from babi.theme import Theme

THEME = Theme.from_dct({
    'colors': {'foreground': '#100000', 'background': '#aaaaaa'},
    'tokenColors': [
        {'scope': 'foo.bar', 'settings': {'foreground': '#200000'}},
        {'scope': 'foo', 'settings': {'foreground': '#300000'}},
        {'scope': 'parent foo.bar', 'settings': {'foreground': '#400000'}},
    ],
})


def unhex(color):
    return f'#{hex(color.r << 16 | color.g << 8 | color.b)[2:]}'


@pytest.mark.parametrize(
    ('scope', 'expected'),
    (
        pytest.param(('',), '#100000', id='trivial'),
        pytest.param(('unknown',), '#100000', id='unknown'),
        pytest.param(('foo.bar',), '#200000', id='exact match'),
        pytest.param(('foo.baz',), '#300000', id='prefix match'),
        pytest.param(('src.diff', 'foo.bar'), '#200000', id='nested scope'),
        pytest.param(
            ('foo.bar', 'unrelated'), '#200000',
            id='nested scope not last one',
        ),
    ),
)
def test_select(scope, expected):
    ret = THEME.select(scope)
    assert unhex(ret.fg) == expected


def test_theme_default_settings_from_no_scope():
    theme = Theme.from_dct({
        'tokenColors': [
            {'settings': {'foreground': '#cccccc', 'background': '#333333'}},
        ],
    })
    assert theme.default.fg == Color.parse('#cccccc')
    assert theme.default.bg == Color.parse('#333333')


def test_theme_default_settings_from_empty_string_scope():
    theme = Theme.from_dct({
        'tokenColors': [
            {
                'scope': '',
                'settings': {'foreground': '#cccccc', 'background': '#333333'},
            },
        ],
    })
    assert theme.default.fg == Color.parse('#cccccc')
    assert theme.default.bg == Color.parse('#333333')


def test_theme_scope_split_by_commas():
    theme = Theme.from_dct({
        'colors': {'foreground': '#cccccc', 'background': '#333333'},
        'tokenColors': [
            {'scope': 'a, b, c', 'settings': {'fontStyle': 'italic'}},
        ],
    })
    assert theme.select(('d',)).i is False
    assert theme.select(('a',)).i is True
    assert theme.select(('b',)).i is True
    assert theme.select(('c',)).i is True


def test_theme_scope_comma_at_beginning_and_end():
    theme = Theme.from_dct({
        'colors': {'foreground': '#cccccc', 'background': '#333333'},
        'tokenColors': [
            {'scope': '\n,a,b,\n', 'settings': {'fontStyle': 'italic'}},
        ],
    })
    assert theme.select(('d',)).i is False
    assert theme.select(('a',)).i is True
    assert theme.select(('b',)).i is True


def test_theme_scope_internal_newline_commas():
    # this is arguably malformed, but `cobalt2` in the wild has this issue
    theme = Theme.from_dct({
        'colors': {'foreground': '#cccccc', 'background': '#333333'},
        'tokenColors': [
            {'scope': '\n,a,\n,b,\n', 'settings': {'fontStyle': 'italic'}},
        ],
    })
    assert theme.select(('d',)).i is False
    assert theme.select(('a',)).i is True
    assert theme.select(('b',)).i is True


def test_theme_scope_as_A_list():
    theme = Theme.from_dct({
        'colors': {'foreground': '#cccccc', 'background': '#333333'},
        'tokenColors': [
            {'scope': ['a', 'b', 'c'], 'settings': {'fontStyle': 'underline'}},
        ],
    })
    assert theme.select(('d',)).u is False
    assert theme.select(('a',)).u is True
    assert theme.select(('b',)).u is True
    assert theme.select(('c',)).u is True
