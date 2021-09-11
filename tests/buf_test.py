from __future__ import annotations

import pytest

from babi.buf import Buf


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
