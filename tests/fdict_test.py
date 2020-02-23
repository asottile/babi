from babi.fdict import FDict


def test_fdict_repr():
    # mostly because this shouldn't get hit elsewhere but is uesful for
    # debugging purposes
    assert repr(FDict({1: 2, 3: 4})) == 'FDict({1: 2, 3: 4})'
