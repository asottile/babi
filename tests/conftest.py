from __future__ import annotations

import json
import os
import sys

import pytest

from babi.highlight import Grammars


@pytest.fixture
def make_grammars(tmpdir):
    grammar_dir = tmpdir.join('grammars').ensure_dir()

    def make_grammars(*grammar_dcts):
        for grammar in grammar_dcts:
            filename = f'{grammar["scopeName"]}.json'
            grammar_dir.join(filename).write(json.dumps(grammar))
        return Grammars(grammar_dir)
    return make_grammars


@pytest.fixture(autouse=True, scope='session')
def _pytest_readline_workaround():
    # https://github.com/pytest-dev/pytest/issues/12888#issuecomment-2764756330

    # is the workaround even needed?
    assert 'readline' in sys.modules

    os.environ['COLUMNS'] = os.environ['LINES'] = ''
    del os.environ['COLUMNS'], os.environ['LINES']
