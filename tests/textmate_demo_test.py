from __future__ import annotations

import json

import pytest

from babi.textmate_demo import main

THEME = {
    'colors': {'foreground': '#ffffff', 'background': '#000000'},
    'tokenColors': [
        {'scope': 'bold', 'settings': {'fontStyle': 'bold'}},
        {'scope': 'italic', 'settings': {'fontStyle': 'italic'}},
        {'scope': 'underline', 'settings': {'fontStyle': 'underline'}},
        {'scope': 'comment', 'settings': {'foreground': '#1e77d3'}},
    ],
}

GRAMMAR = {
    'scopeName': 'source.demo',
    'fileTypes': ['demo'],
    'patterns': [
        {'match': r'\*[^*]*\*', 'name': 'bold'},
        {'match': '/[^/]*/', 'name': 'italic'},
        {'match': '_[^_]*_', 'name': 'underline'},
        {'match': '#.*', 'name': 'comment'},
    ],
}


@pytest.fixture
def theme_grammars(tmpdir):
    theme = tmpdir.join('config/theme.json').ensure()
    theme.write(json.dumps(THEME))
    grammars = tmpdir.join('grammar_v1').ensure_dir()
    grammars.join('source.demo.json').write(json.dumps(GRAMMAR))
    return theme, grammars


def test_basic(theme_grammars, tmpdir, capsys):
    theme, grammars = theme_grammars

    f = tmpdir.join('f.demo')
    f.write('*bold*/italic/_underline_# comment\n')

    assert not main((
        '--theme', str(theme), '--grammar-dir', str(grammars),
        str(f),
    ))

    out, _ = capsys.readouterr()

    assert out == (
        '\x1b[48;2;0;0;0m\n'
        '\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[1m'
        '*bold*'
        '\x1b[39m\x1b[49m\x1b[22m'
        '\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[3m'
        '/italic/'
        '\x1b[39m\x1b[49m\x1b[23m'
        '\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[4m'
        '_underline_'
        '\x1b[39m\x1b[49m\x1b[24m'
        '\x1b[38;2;30;119;211m\x1b[48;2;0;0;0m'
        '# comment'
        '\x1b[39m\x1b[49m\x1b'
        '[38;2;255;255;255m\x1b[48;2;0;0;0m\n\x1b[39m\x1b[49m'
        '\x1b[m'
    )


def test_basic_with_blank_theme(theme_grammars, tmpdir, capsys):
    theme, grammars = theme_grammars
    theme.write('{}')

    f = tmpdir.join('f.demo')
    f.write('*bold*/italic/_underline_# comment\n')

    assert not main((
        '--theme', str(theme), '--grammar-dir', str(grammars),
        str(f),
    ))

    out, _ = capsys.readouterr()

    assert out == '*bold*/italic/_underline_# comment\n\x1b[m'
