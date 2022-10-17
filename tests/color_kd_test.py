from __future__ import annotations

from babi import color_kd
from babi.color import Color


def test_build_trivial():
    assert color_kd._build([]) is None


def test_build_single_node():
    kd = color_kd._build([(Color(0, 0, 0), 255)])
    assert kd == color_kd.KD(Color(0, 0, 0), 255, left=None, right=None)


def test_build_many_colors():
    kd = color_kd._build([
        (Color(0, 106, 200), 255),
        (Color(1, 105, 201), 254),
        (Color(2, 104, 202), 253),
        (Color(3, 103, 203), 252),
        (Color(4, 102, 204), 251),
        (Color(5, 101, 205), 250),
        (Color(6, 100, 206), 249),
    ])

    # each level is sorted by the next dimension
    assert kd == color_kd.KD(
        Color(3, 103, 203),
        252,
        left=color_kd.KD(
            Color(1, 105, 201), 254,
            left=color_kd.KD(Color(2, 104, 202), 253, None, None),
            right=color_kd.KD(Color(0, 106, 200), 255, None, None),
        ),
        right=color_kd.KD(
            Color(5, 101, 205), 250,
            left=color_kd.KD(Color(6, 100, 206), 249, None, None),
            right=color_kd.KD(Color(4, 102, 204), 251, None, None),
        ),
    )


def test_nearest_trivial():
    assert color_kd.nearest(Color(0, 0, 0), None) == 0


def test_nearest_one_node():
    kd = color_kd._build([(Color(100, 100, 100), 99)])
    assert color_kd.nearest(Color(0, 0, 0), kd) == 99


def test_nearest_on_square_distance():
    kd = color_kd._build([
        (Color(50, 50, 50), 255),
        (Color(50, 51, 50), 254),
    ])
    assert color_kd.nearest(Color(0, 0, 0), kd) == 255
    assert color_kd.nearest(Color(52, 52, 52), kd) == 254


def test_smoke_kd_256():
    kd_256 = color_kd.make_256()
    assert color_kd.nearest(Color(0, 0, 0), kd_256) == 16
    assert color_kd.nearest(Color(0x1e, 0x77, 0xd3), kd_256) == 32
