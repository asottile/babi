import pytest

from babi.list_spy import ListSpy


def test_list_spy_repr():
    assert repr(ListSpy(['a', 'b', 'c'])) == "ListSpy(['a', 'b', 'c'])"


def test_list_spy_item_retrieval():
    spy = ListSpy(['a', 'b', 'c'])
    assert spy[1] == 'b'
    assert spy[-1] == 'c'
    with pytest.raises(IndexError):
        spy[3]


def test_list_spy_del():
    lst = ['a', 'b', 'c']

    spy = ListSpy(lst)
    del spy[1]

    assert lst == ['a', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_del_with_negative():
    lst = ['a', 'b', 'c']

    spy = ListSpy(lst)
    del spy[-1]

    assert lst == ['a', 'b']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_insert():
    lst = ['a', 'b', 'c']

    spy = ListSpy(lst)
    spy.insert(1, 'q')

    assert lst == ['a', 'q', 'b', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_insert_with_negative():
    lst = ['a', 'b', 'c']

    spy = ListSpy(lst)
    spy.insert(-1, 'q')

    assert lst == ['a', 'b', 'q', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_set_value():
    lst = ['a', 'b', 'c']

    spy = ListSpy(lst)
    spy[1] = 'hello'

    assert lst == ['a', 'hello', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_multiple_modifications():
    lst = ['a', 'b', 'c']

    spy = ListSpy(lst)
    spy[1] = 'hello'
    spy.insert(1, 'ohai')
    del spy[0]

    assert lst == ['ohai', 'hello', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_iter():
    spy = ListSpy(['a', 'b', 'c'])
    spy_iter = iter(spy)
    assert next(spy_iter) == 'a'
    assert next(spy_iter) == 'b'
    assert next(spy_iter) == 'c'
    with pytest.raises(StopIteration):
        next(spy_iter)


def test_list_spy_append():
    lst = ['a', 'b', 'c']

    spy = ListSpy(lst)
    spy.append('q')

    assert lst == ['a', 'b', 'c', 'q']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_pop_default():
    lst = ['a', 'b', 'c']

    spy = ListSpy(lst)
    spy.pop()

    assert lst == ['a', 'b']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_pop_idx():
    lst = ['a', 'b', 'c']

    spy = ListSpy(lst)
    spy.pop(1)

    assert lst == ['a', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']
