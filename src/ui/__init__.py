"""
User interface module.

Lifted from synchotic's TUI toolkit. Organized into layers:
- primitives/: Terminal I/O (keyboard, colors, terminal control)
- components/: Visual building blocks (box, header, formatting)
- widgets/: Interactive reusable pieces (menu, confirm)
- screens/: Full-page views (home)
"""

from .primitives import (
    clear_screen,
    get_terminal_width,
    print_progress,
    getch,
    input_with_esc,
    wait_for_key,
    wait_with_skip,
    CancelInput,
    KEY_UP,
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESC,
    KEY_SPACE,
    Colors,
    rgb,
)
from .components import (
    print_header,
    strip_ansi,
    calc_percent,
)
from .widgets import (
    Menu,
    MenuItem,
    MenuDivider,
    MenuGroupHeader,
    MenuAction,
    MenuResult,
    ConfirmDialog,
)
from .screens import show_stem_picker

__all__ = [
    "clear_screen",
    "get_terminal_width",
    "print_progress",
    "getch",
    "input_with_esc",
    "wait_for_key",
    "wait_with_skip",
    "CancelInput",
    "KEY_UP",
    "KEY_DOWN",
    "KEY_ENTER",
    "KEY_ESC",
    "KEY_SPACE",
    "Colors",
    "rgb",
    "print_header",
    "strip_ansi",
    "calc_percent",
    "Menu",
    "MenuItem",
    "MenuDivider",
    "MenuGroupHeader",
    "MenuAction",
    "MenuResult",
    "ConfirmDialog",
    "show_stem_picker",
]
