from __future__ import annotations

import pytest

from babi import main
from babi.screen import FileInfo


@pytest.mark.parametrize(
    ('in_filenames', 'expected'),
    (
        (
            [],
            [FileInfo(filename=None, initial_line=0, is_stdin=False)],
        ),
        (
            ['+3'],
            [FileInfo(filename='+3', initial_line=0, is_stdin=False)],
        ),
        (
            ['f'],
            [FileInfo(filename='f', initial_line=0, is_stdin=False)],
        ),
        (
            ['+3', 'f'],
            [FileInfo(filename='f', initial_line=3, is_stdin=False)],
        ),
        (
            ['+-3', 'f'],
            [FileInfo(filename='f', initial_line=-3, is_stdin=False)],
        ),
        (
            ['+3', '+3'],
            [FileInfo(filename='+3', initial_line=3, is_stdin=False)],
        ),
        (
            ['+2', 'f', '+5', 'g'],
            [
                FileInfo(filename='f', initial_line=2, is_stdin=False),
                FileInfo(filename='g', initial_line=5, is_stdin=False),
            ],
        ),
        (
            ['-'],
            [FileInfo(filename=None, initial_line=0, is_stdin=True)],
        ),
        (
            ['+4', '-'],
            [FileInfo(filename=None, initial_line=4, is_stdin=True)],
        ),
    ),
)
def test_filenames(in_filenames, expected):
    assert main._files(in_filenames) == expected
