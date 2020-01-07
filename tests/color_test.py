import pytest

from testing.runner import and_exit


@pytest.mark.parametrize('colors', (8, 256))
def test_color_test(run, colors):
    with run('--color-test', colors=colors) as h, and_exit(h):
        h.await_text('*  1*  2')


def test_can_start_without_color(run):
    with run(colors=8) as h, and_exit(h):
        pass
