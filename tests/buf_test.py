from __future__ import annotations

from unittest import mock

import pytest

import babi.buf
from babi.buf import Buf


def test_buf_truthiness():
    assert bool(Buf([])) is False
    assert bool(Buf(['a', 'b'])) is True


def test_buf_repr():
    ret = repr(Buf(['a', 'b', 'c']))
    assert ret == "Buf(['a', 'b', 'c'], x=0, y=0, file_y=0)"


def test_buf_item_retrieval():
    buf = Buf(['a', 'b', 'c'])
    assert buf[1] == 'b'
    assert buf[-1] == 'c'
    with pytest.raises(IndexError):
        buf[3]


def test_buf_del():
    lst = ['a', 'b', 'c']

    buf = Buf(lst)

    with buf.record() as modifications:
        del buf[1]

    assert lst == ['a', 'c']

    buf.apply(modifications)

    assert lst == ['a', 'b', 'c']


def test_buf_del_with_negative():
    lst = ['a', 'b', 'c']

    buf = Buf(lst)

    with buf.record() as modifications:
        del buf[-1]

    assert lst == ['a', 'b']

    buf.apply(modifications)

    assert lst == ['a', 'b', 'c']


def test_buf_insert():
    lst = ['a', 'b', 'c']

    buf = Buf(lst)

    with buf.record() as modifications:
        buf.insert(1, 'q')

    assert lst == ['a', 'q', 'b', 'c']

    buf.apply(modifications)

    assert lst == ['a', 'b', 'c']


def test_buf_insert_with_negative():
    lst = ['a', 'b', 'c']

    buf = Buf(lst)

    with buf.record() as modifications:
        buf.insert(-1, 'q')

    assert lst == ['a', 'b', 'q', 'c']

    buf.apply(modifications)

    assert lst == ['a', 'b', 'c']


def test_buf_set_value():
    lst = ['a', 'b', 'c']

    buf = Buf(lst)

    with buf.record() as modifications:
        buf[1] = 'hello'

    assert lst == ['a', 'hello', 'c']

    buf.apply(modifications)

    assert lst == ['a', 'b', 'c']


def test_buf_set_value_idx_negative():
    lst = ['a', 'b', 'c']

    buf = Buf(lst)

    with buf.record() as modifications:
        buf[-1] = 'hello'

    assert lst == ['a', 'b', 'hello']

    buf.apply(modifications)

    assert lst == ['a', 'b', 'c']


def test_buf_multiple_modifications():
    lst = ['a', 'b', 'c']

    buf = Buf(lst)

    with buf.record() as modifications:
        buf[1] = 'hello'
        buf.insert(1, 'ohai')
        del buf[0]

    assert lst == ['ohai', 'hello', 'c']

    buf.apply(modifications)

    assert lst == ['a', 'b', 'c']


def test_buf_iter():
    buf = Buf(['a', 'b', 'c'])
    buf_iter = iter(buf)
    assert next(buf_iter) == 'a'
    assert next(buf_iter) == 'b'
    assert next(buf_iter) == 'c'
    with pytest.raises(StopIteration):
        next(buf_iter)


def test_buf_append():
    lst = ['a', 'b', 'c']

    buf = Buf(lst)

    with buf.record() as modifications:
        buf.append('q')

    assert lst == ['a', 'b', 'c', 'q']

    buf.apply(modifications)

    assert lst == ['a', 'b', 'c']


def test_buf_pop_default():
    lst = ['a', 'b', 'c']

    buf = Buf(lst)

    with buf.record() as modifications:
        buf.pop()

    assert lst == ['a', 'b']

    buf.apply(modifications)

    assert lst == ['a', 'b', 'c']


def test_buf_pop_idx():
    lst = ['a', 'b', 'c']

    buf = Buf(lst)

    with buf.record() as modifications:
        buf.pop(1)

    assert lst == ['a', 'c']

    buf.apply(modifications)

    assert lst == ['a', 'b', 'c']


@pytest.mark.parametrize(
    'new_lines',
    (
        pytest.param(['d', 'b', 'c'], id='replace op'),
        pytest.param(['a', 'q', 'q', 'c'], id='replace different size'),
        pytest.param(['c'], id='delete op'),
        pytest.param(['a', 'q', 'q', 'q', 'b', 'c'], id='insert op'),
    ),
)
def test_replace_lines(new_lines):
    lst = ['a', 'b', 'c']

    buf = Buf(lst)

    with buf.record() as modifications:
        buf.replace_lines(new_lines)

    assert lst == new_lines

    buf.apply(modifications)

    assert lst == ['a', 'b', 'c']


def test_restore_eof_invariant():
    lst = ['a', 'b', 'c']
    buf = Buf(lst)
    buf.restore_eof_invariant()
    assert lst == ['a', 'b', 'c', '']

    buf.restore_eof_invariant()
    assert lst == ['a', 'b', 'c', '']


@pytest.fixture
def fake_wcwidth():
    chars = {'a': 1, 'b': 1, 'c': 1, '🔵': 2}
    with mock.patch.object(babi.buf, 'wcwidth', chars.__getitem__):
        yield


@pytest.mark.usefixtures('fake_wcwidth')
def test_line_positions():
    buf = Buf(['a', '🔵b', 'c'])
    assert buf.line_positions(0) == (0, 1)
    assert buf.line_positions(1) == (0, 2, 3)
    assert buf.line_positions(2) == (0, 1)


@pytest.mark.usefixtures('fake_wcwidth')
def test_set_tab_size():
    buf = Buf(['\ta'])
    assert buf.line_positions(0) == (0, 4, 5)

    buf.set_tab_size(8)
    assert buf.line_positions(0) == (0, 8, 9)
