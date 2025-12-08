from __future__ import annotations

import pytest

from babi.color import Color
from babi.theme import Theme

THEME = Theme.from_dct(
    {
        'colors': {'foreground': '#100000', 'background': '#aaaaaa'},
        'tokenColors': [
            {'scope': 'foo.bar', 'settings': {'foreground': '#200000'}},
            {'scope': 'foo', 'settings': {'foreground': '#300000'}},
            {'scope': 'parent foo.bar', 'settings': {'foreground': '#400000'}},
        ],
    },
)


def unhex(color):
    return f"#{hex(color.r << 16 | color.g << 8 | color.b)[2:]}"


@pytest.mark.parametrize(
    ('scope', 'expected'),
    (
        pytest.param(('',), '#100000', id='trivial'),
        pytest.param(('unknown',), '#100000', id='unknown'),
        pytest.param(('foo.bar',), '#200000', id='exact match'),
        pytest.param(('foo.baz',), '#300000', id='prefix match'),
        pytest.param(('src.diff', 'foo.bar'), '#200000', id='nested scope'),
        pytest.param(
            ('foo.bar', 'unrelated'),
            '#200000',
            id='nested scope not last one',
        ),
    ),
)
def test_select(scope, expected):
    ret = THEME.select(scope)
    assert unhex(ret.fg) == expected


def test_theme_default_settings_from_no_scope():
    theme = Theme.from_dct(
        {
            'tokenColors': [
                {
                    'settings': {
                        'foreground': '#cccccc',
                        'background': '#333333',
                    },
                },
            ],
        },
    )
    assert theme.default.fg == Color.parse('#cccccc')
    assert theme.default.bg == Color.parse('#333333')


def test_theme_default_settings_from_empty_string_scope():
    theme = Theme.from_dct(
        {
            'tokenColors': [
                {
                    'scope': '',
                    'settings': {
                        'foreground': '#cccccc',
                        'background': '#333333',
                    },
                },
            ],
        },
    )
    assert theme.default.fg == Color.parse('#cccccc')
    assert theme.default.bg == Color.parse('#333333')


def test_theme_scope_split_by_commas():
    theme = Theme.from_dct(
        {
            'colors': {'foreground': '#cccccc', 'background': '#333333'},
            'tokenColors': [
                {'scope': 'a, b, c', 'settings': {'fontStyle': 'italic'}},
            ],
        },
    )
    assert theme.select(('d',)).i is False
    assert theme.select(('a',)).i is True
    assert theme.select(('b',)).i is True
    assert theme.select(('c',)).i is True


def test_theme_scope_comma_at_beginning_and_end():
    theme = Theme.from_dct(
        {
            'colors': {'foreground': '#cccccc', 'background': '#333333'},
            'tokenColors': [
                {'scope': '\n,a,b,\n', 'settings': {'fontStyle': 'italic'}},
            ],
        },
    )
    assert theme.select(('d',)).i is False
    assert theme.select(('a',)).i is True
    assert theme.select(('b',)).i is True


def test_theme_scope_internal_newline_commas():
    # this is arguably malformed, but `cobalt2` in the wild has this issue
    theme = Theme.from_dct(
        {
            'colors': {'foreground': '#cccccc', 'background': '#333333'},
            'tokenColors': [
                {'scope': '\n,a,\n,b,\n', 'settings': {'fontStyle': 'italic'}},
            ],
        },
    )
    assert theme.select(('d',)).i is False
    assert theme.select(('a',)).i is True
    assert theme.select(('b',)).i is True


def test_theme_scope_as_A_list():
    theme = Theme.from_dct(
        {
            'colors': {'foreground': '#cccccc', 'background': '#333333'},
            'tokenColors': [
                {
                    'scope': ['a', 'b', 'c'],
                    'settings': {'fontStyle': 'underline'},
                },
            ],
        },
    )
    assert theme.select(('c',)).u is True


def test_theme_parses_rainbow_colors():
    theme = Theme.from_dct(
        {
            'colors': {
                'editor.rainbow.0': '#111111',
                'editor.rainbow.1': '#222222',
                'rainbow.2': '#333333',
            },
            'tokenColors': [],
        },
    )

    assert len(theme.rainbow_colors) == 3
    assert theme.rainbow_colors[0].fg == Color.parse('#111111')
    assert theme.rainbow_colors[1].fg == Color.parse('#222222')
    assert theme.rainbow_colors[2].fg == Color.parse('#333333')


def test_theme_rainbow_gaps_stop_parsing():
    theme = Theme.from_dct(
        {
            'colors': {
                'editor.rainbow.0': '#000000',
                # .1 is missing
                'editor.rainbow.2': '#222222',
            },
            'tokenColors': [],
        },
    )

    # we expect only rainbow.0 to be parsed due to the gap
    assert len(theme.rainbow_colors) == 1
    assert theme.rainbow_colors[0].fg == Color.parse('#000000')


def test_rainbow_loop_exhaustion():
    colors = {f"rainbow.{i}": '#000000' for i in range(16)}
    theme = Theme.from_dct({'colors': colors, 'tokenColors': []})
    assert len(theme.rainbow_colors) == 16
