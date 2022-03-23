from __future__ import annotations

from babi.linting import Error
from babi.linting import parse_generic_output


def test_parse_generic_output_noop():
    assert parse_generic_output('') == ()


def test_parse_generic_output_one_error():
    s = 'babi/screen.py:504: error: "Screen" has no attribute "margin"'
    ret = parse_generic_output(s)
    assert ret == (
        Error(
            filename='babi/screen.py',
            lineno=504,
            col_offset=1,
            msg='error: "Screen" has no attribute "margin"',
        ),
    )


def test_parse_generic_output_multiple_errors():
    s = '''\
babi/screen.py:504: error: "Screen" has no attribute "margin"
babi/screen.py:505: info: declared here
'''
    ret = parse_generic_output(s)
    assert ret == (
        Error(
            filename='babi/screen.py',
            lineno=504,
            col_offset=1,
            msg='error: "Screen" has no attribute "margin"',
        ),
        Error(
            filename='babi/screen.py',
            lineno=505,
            col_offset=1,
            msg='info: declared here',
        ),
    )


def test_parse_generic_output_with_column_offset():
    s = 'tests/linting_test.py:3:25: E271 multiple spaces after keyword'
    ret = parse_generic_output(s)
    assert ret == (
        Error(
            filename='tests/linting_test.py',
            lineno=3,
            col_offset=25,
            msg='E271 multiple spaces after keyword',
        ),
    )
