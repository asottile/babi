from __future__ import annotations

import json

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
