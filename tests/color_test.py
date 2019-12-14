import pytest

from testing.runner import and_exit
from testing.runner import run


@pytest.mark.parametrize('color', (True, False))
def test_color_test(color):
    with run('--color-test', color=color) as h, and_exit(h):
        h.await_text('*  1*  2')


def test_can_start_without_color():
    with run(color=False) as h, and_exit(h):
        pass
