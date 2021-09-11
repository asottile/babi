from __future__ import annotations

import onigurumacffi
import pytest

from babi.reg import _Reg
from babi.reg import _RegSet


def test_reg_first_line():
    reg = _Reg(r'\Ahello')
    assert reg.match('hello', 0, first_line=True, boundary=True)
    assert reg.search('hello', 0, first_line=True, boundary=True)
    assert not reg.match('hello', 0, first_line=False, boundary=True)
    assert not reg.search('hello', 0, first_line=False, boundary=True)


def test_reg_boundary():
    reg = _Reg(r'\Ghello')
    assert reg.search('ohello', 1, first_line=True, boundary=True)
    assert reg.match('ohello', 1, first_line=True, boundary=True)
    assert not reg.search('ohello', 1, first_line=True, boundary=False)
    assert not reg.match('ohello', 1, first_line=True, boundary=False)


def test_reg_neither():
    reg = _Reg(r'(\A|\G)hello')
    assert not reg.search('hello', 0, first_line=False, boundary=False)
    assert not reg.search('ohello', 1, first_line=False, boundary=False)


def test_reg_other_escapes_left_untouched():
    reg = _Reg(r'(^|\A|\G)\w\s\w')
    assert reg.match('a b', 0, first_line=False, boundary=False)


def test_reg_not_out_of_bounds_at_end():
    # the only way this is triggerable is with an illegal regex, we'd rather
    # produce an error about the regex being wrong than an IndexError
    with pytest.raises(onigurumacffi.OnigError) as excinfo:
        _Reg('\\A\\')
    msg, = excinfo.value.args
    assert msg == 'end pattern at escape'


def test_reg_repr():
    assert repr(_Reg(r'\A123')) == r"_Reg('\\A123')"


def test_regset_first_line():
    regset = _RegSet(r'\Ahello', 'hello')
    idx, _ = regset.search('hello', 0, first_line=True, boundary=True)
    assert idx == 0
    idx, _ = regset.search('hello', 0, first_line=False, boundary=True)
    assert idx == 1


def test_regset_boundary():
    regset = _RegSet(r'\Ghello', 'hello')
    idx, _ = regset.search('ohello', 1, first_line=True, boundary=True)
    assert idx == 0
    idx, _ = regset.search('ohello', 1, first_line=True, boundary=False)
    assert idx == 1


def test_regset_neither():
    regset = _RegSet(r'\Ahello', r'\Ghello', 'hello')
    idx, _ = regset.search('hello', 0, first_line=False, boundary=False)
    assert idx == 2
    idx, _ = regset.search('ohello', 1, first_line=False, boundary=False)
    assert idx == 2


def test_regset_repr():
    assert repr(_RegSet('ohai', r'\Aworld')) == r"_RegSet('ohai', '\\Aworld')"
