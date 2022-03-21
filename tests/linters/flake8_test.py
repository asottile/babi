from __future__ import annotations

import pytest

from babi.linters.flake8 import Flake8
from babi.linting import Error


@pytest.mark.parametrize(
    ('filename', 'scope', 'expected'),
    (
        ('t.py', 'source.python', ('flake8', 't.py')),
        ('t', 'source.python', ('flake8', 't')),
        ('t.xml', 'text.xml', None),
    ),
)
def test_command_is_based_on_python_scope(filename, scope, expected):
    assert Flake8().command(filename, scope) == expected


def test_parse_output():
    ret = Flake8().parse('t.py', 't.py:1:1: F401 unused import')
    assert ret == (
        Error('t.py', 1, 1, '[flake8] F401 unused import'),
    )
