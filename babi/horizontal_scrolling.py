def line_x(x: int, width: int) -> int:
    if x + 1 < width:
        return 0
    elif width == 1:
        return x
    else:
        margin = min(width - 3, 6)
        return (
            width - margin - 2 +
            (x + 1 - width) //
            (width - margin - 2) *
            (width - margin - 2)
        )


def scrolled_line(s: str, x: int, width: int) -> str:
    l_x = line_x(x, width)
    if l_x:
        s = f'«{s[l_x + 1:]}'
        if len(s) > width:
            return f'{s[:width - 1]}»'
        else:
            return s.ljust(width)
    elif len(s) > width:
        return f'{s[:width - 1]}»'
    else:
        return s.ljust(width)
