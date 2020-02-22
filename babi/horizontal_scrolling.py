def line_x(x: int, width: int) -> int:
    margin = min(width - 3, 6)
    if x + 1 < width:
        return 0
    elif width == 1:
        return x
    else:
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
        if l_x and len(s) > width:
            return f'{s[:width - 1]}»'
        else:
            return s.ljust(width)
    elif len(s) > width:
        return f'{s[:width - 1]}»'
    else:
        return s.ljust(width)
