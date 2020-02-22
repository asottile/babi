import io

import pytest

from babi.file import File
from babi.file import get_lines


def test_position_repr():
    ret = repr(File('f.txt'))
    assert ret == (
        'File(\n'
        "    filename='f.txt',\n"
        '    modified=False,\n'
        '    lines=[],\n'
        "    nl='\\n',\n"
        '    file_y=0,\n'
        '    y=0,\n'
        '    x=0,\n'
        '    x_hint=0,\n'
        '    sha256=None,\n'
        '    undo_stack=[],\n'
        '    redo_stack=[],\n'
        '    select_start=None,\n'
        ')'
    )


@pytest.mark.parametrize(
    ('s', 'lines', 'nl', 'mixed'),
    (
        pytest.param('', [''], '\n', False, id='trivial'),
        pytest.param('1\n2\n', ['1', '2', ''], '\n', False, id='lf'),
        pytest.param('1\r\n2\r\n', ['1', '2', ''], '\r\n', False, id='crlf'),
        pytest.param('1\r\n2\n', ['1', '2', ''], '\n', True, id='mixed'),
        pytest.param('1\n2', ['1', '2', ''], '\n', False, id='noeol'),
    ),
)
def test_get_lines(s, lines, nl, mixed):
    # sha256 tested below
    ret_lines, ret_nl, ret_mixed, _ = get_lines(io.StringIO(s))
    assert (ret_lines, ret_nl, ret_mixed) == (lines, nl, mixed)


def test_get_lines_sha256_checksum():
    ret = get_lines(io.StringIO(''))
    sha256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    assert ret == ([''], '\n', False, sha256)
