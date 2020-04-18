import pytest

from babi import main


@pytest.mark.parametrize(
    ('in_filenames', 'expected_filenames', 'expected_positions'),
    (
        ([], [None], [0]),
        (['+3'], ['+3'], [0]),
        (['f'], ['f'], [0]),
        (['+3', 'f'], ['f'], [3]),
        (['+-3', 'f'], ['f'], [-3]),
        (['+3', '+3'], ['+3'], [3]),
        (['+2', 'f', '+5', 'g'], ['f', 'g'], [2, 5]),
    ),
)
def test_filenames(in_filenames, expected_filenames, expected_positions):
    filenames, positions = main._filenames(in_filenames)
