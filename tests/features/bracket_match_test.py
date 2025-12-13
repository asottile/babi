from __future__ import annotations

import curses

from testing.runner import and_exit


def test_bracket_match_basic(run, tmpdir):
    f = tmpdir.join('test.py')
    f.write('# python code\n')
    with run(str(f)) as h, and_exit(h):
        h.press('Down')  # Move past shebang/comment
        h.press('(foo)')
        h.press('^A')
        h.await_text('(foo)')


def test_bracket_match_highlighting(run_only_fake, tmpdir):
    f = tmpdir.join('test.py')
    f.write('# python code\n')
    with run_only_fake(str(f)) as h, and_exit(h):
        h.press('Down')
        h.press('(foo)')
        h.press('^A')
        h.await_text('(foo)')

        class AssertBoldOnly:
            def __call__(self, screen):
                # Line 2
                if len(screen.attrs) <= 2:
                    raise AssertionError(
                        f"Screen has only {len(screen.attrs)} lines",
                    )

                attr = screen.attrs[2][0]
                # In fake screen, attr is (fg, bg, attr_int)
                # A_BOLD only
                target = curses.A_BOLD
                current_attr = attr[2]

                # Check attribute at 0
                if not (current_attr & target == target):
                    raise AssertionError(
                        f"Expected bold at 0, got {current_attr} {attr}",
                    )
                if current_attr & curses.A_REVERSE:
                    raise AssertionError(
                        f"Expected NO reverse at 0, got {current_attr} {attr}",
                    )

                # Check attribute at 4
                attr_end = screen.attrs[2][4]
                current_attr_end = attr_end[2]
                if not (current_attr_end & target == target):
                    raise AssertionError(
                        f"Expected bold at 4, "
                        f"got {current_attr_end} {attr_end}",
                    )
                if current_attr_end & curses.A_REVERSE:
                    raise AssertionError(
                        f"Expected NO reverse at 4, "
                        f"got {current_attr_end} {attr_end}",
                    )

        h._ops.append(AssertBoldOnly())


def test_unmatched_bracket_red(run_only_fake, tmpdir, xdg_config_home):
    # custom theme with bold invalid style to avoid color palette issues
    theme_json = """
    {
        "colors": {
            "editor.background": "#000000",
            "editor.foreground": "#ffffff"
        },
        "tokenColors": [
            {
                "scope": "invalid",
                "settings": {"fontStyle": "bold", "foreground": "#ff0000"}
            }
        ]
    }
    """
    xdg_config_home.join('babi').ensure(dir=True)
    xdg_config_home.join('babi', 'theme.json').write(theme_json)

    f = tmpdir.join('test.py')
    f.write('# python code\n')
    with run_only_fake(str(f)) as h, and_exit(h):
        h.press('Down')
        h.press('(foo')
        h.press('^A')  # Cursor at '('
        h.await_text('(foo')

        # We need to test unmatched CLOSE.
        h.press('End')
        h.press(')')
        h.press(')')
        # (foo))
        # Last ) at 5 is unmatched.
        h.await_text('(foo))')

        class AssertBoldAttribute:
            def __call__(self, screen):
                # Line 2 (content), char 5 (')')
                # Wait, layout:
                # 0: File: ...
                # 1: # python code
                # 2: (foo))
                assert len(screen.attrs) > 2, (
                    f"Screen has only {len(screen.attrs)} lines"
                )

                attr_invalid = screen.attrs[2][5]
                # Fallback invalid usually BOLD|REVERSE or just BOLD
                # We expect at least BOLD.
                target = curses.A_BOLD

                current_attr = attr_invalid[2]

                # Attribute at 5 should be bold
                if current_attr & target != target:
                    raise AssertionError(
                        f"Expected BOLD for invalid bracket. "
                        f"Got {current_attr} {attr_invalid}",
                    )

                # Normal text should NOT be bold
                attr_normal = screen.attrs[2][1]  # 'f'
                if attr_normal[2] & target == target:
                    raise AssertionError(
                        f"Normal text should not be bold. Got {attr_normal}",
                    )

        h._ops.append(AssertBoldAttribute())


def test_unmatched_bracket_red_fallback(
    run_only_fake,
    tmpdir,
    xdg_config_home,
):
    # Ensure NO theme file exists
    theme_path = xdg_config_home.join('babi', 'theme.json')
    # Create then remove so the removal branch is exercised (and the test
    # still asserts behaviour with *no* theme file present).
    theme_path.dirpath().ensure(dir=True)
    theme_path.write('{}')
    theme_path.remove()

    f = tmpdir.join('test.py')
    f.write('# python code\n')
    with run_only_fake(str(f)) as h, and_exit(h):
        h.press('Down')
        h.press('(foo))')
        h.await_text('(foo))')

        class AssertFallbackAttribute:
            def __call__(self, screen):
                assert len(screen.attrs) > 2, (
                    f"Screen has only {len(screen.attrs)} lines"
                )

                # Line 2, char 5 (')')
                attr_invalid = screen.attrs[2][5]
                # Default behavior for invalid brackets is Red/Bold or
                # Bold/Reverse.

                target = curses.A_BOLD
                current_attr = attr_invalid[2]

                if current_attr & target != target:
                    raise AssertionError(
                        f"Expected BOLD for fallback invalid bracket. "
                        f"Got {current_attr} {attr_invalid}",
                    )

        h._ops.append(AssertFallbackAttribute())


def test_pessimistic_open_bracket(run_only_fake, tmpdir):
    f = tmpdir.join('test.py')
    f.write('# python code\n')
    with run_only_fake(str(f)) as h, and_exit(h):
        h.press('Down')

        # 1. Type '(' - Should be RED (Invalid) since it isn't closed yet.
        h.press('(')
        h.await_text('(')

        class AssertInvalid:
            def __call__(self, screen):
                # Line 2, char 0 ('(')
                attr = screen.attrs[2][0][2]
                target = curses.A_BOLD  # Invalid style includes BOLD
                if not (attr & target):
                    raise AssertionError(
                        f"Expected BOLD (Invalid) for unclosed '('. "
                        f"Got {attr}",
                    )

        h._ops.append(AssertInvalid())

        # 2. Type ')' - Should update '(' to be valid
        h.press(')')
        h.await_text('()')

        class AssertValid:
            def __call__(self, screen):
                # Line 2, char 0 ('(')
                attr = screen.attrs[2][0][2]
                if attr & curses.A_REVERSE:
                    raise AssertionError(
                        f"Expected Valid for closed '('. "
                        f"Got Invalid (Reverse) {attr}",
                    )

        h._ops.append(AssertValid())


def test_angular_bracket_validation(
    run_only_fake,
    tmpdir,
    xdg_data_home,
):
    # Setup grammar for testing
    grammar_json = """
    {
        "scopeName": "source.ang",
        "fileTypes": ["ang"],
        "patterns": [
            {
                "begin": "<",
                "end": ">",
                "name": "punctuation.definition.tag"
            }
        ]
    }
    """
    xdg_data_home.join('babi', 'grammar_v1').ensure(dir=True)
    xdg_data_home.join('babi', 'grammar_v1', 'test_angular.json').write(
        grammar_json,
    )

    f = tmpdir.join('test.ang')
    # Write empty file
    f.write('')

    with run_only_fake(str(f)) as h, and_exit(h):
        # 1. Type '<' - Should be RED (Invalid) because it's open
        h.press('<')
        h.await_text('<')

        class AssertInvalid:
            def __call__(self, screen):
                assert len(screen.attrs) > 1, (
                    f"Screen has only {len(screen.attrs)} lines"
                )

                # Line 1 (content), char 0 ('<')
                attr = screen.attrs[1][0][2]
                target = curses.A_BOLD  # Invalid style includes BOLD
                if not (attr & target):
                    raise AssertionError(
                        f"Expected BOLD (Invalid) for unclosed '<'. "
                        f"Got {attr}",
                    )

        h._ops.append(AssertInvalid())

        # 2. Type '>' - Should validate '<' and '>'
        h.press('>')
        h.await_text('<>')
        # Move cursor to prevent visual overlap
        h.press('Enter')
        h.await_text('\n')

        class AssertValid:
            def __call__(self, screen):
                # Line 1, char 0 ('<')
                attr_open = screen.attrs[1][0][2]
                # Line 1, char 1 ('>')
                attr_close = screen.attrs[1][1][2]

                if not (attr_open & curses.A_BOLD):
                    raise AssertionError(
                        f"Expected Valid (BOLD) for closed '<'. "
                        f"Got {attr_open}",
                    )

                if not (attr_close & curses.A_BOLD):
                    raise AssertionError(
                        f"Expected Valid for closed '>'. "
                        f"Got Invalid (BOLD) {attr_close}",
                    )

        h._ops.append(AssertValid())
