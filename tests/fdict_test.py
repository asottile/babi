from __future__ import annotations

import pytest

from babi.fdict import FChainMap
from babi.fdict import FDict


def test_fdict_repr():
    # mostly because this shouldn't get hit elsewhere but is uesful for
    # debugging purposes
    assert repr(FDict({1: 2, 3: 4})) == 'FDict({1: 2, 3: 4})'


def test_f_chain_map():
    chain_map = FChainMap({1: 2}, {3: 4}, FDict({1: 5}))
    assert chain_map[1] == 5
    assert chain_map[3] == 4

    with pytest.raises(KeyError) as excinfo:
        chain_map[2]
    k, = excinfo.value.args
    assert k == 2


def test_f_chain_map_extend():
    chain_map = FChainMap({1: 2})
    assert chain_map[1] == 2
    chain_map = FChainMap(chain_map, {1: 5})
    assert chain_map[1] == 5
