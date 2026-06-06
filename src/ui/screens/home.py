"""
Home screen - the template picker.

The whole "easy screen": an arrow-key menu of plain-language templates. Selecting
one returns the Template; Esc quits.
"""

from ..widgets import Menu, MenuItem
from ...core.templates import TEMPLATES, get_template, Template


class HomeScreen:
    """Template picker screen."""

    def run(self) -> Template | None:
        return show_home()


def show_home() -> Template | None:
    """Show the template menu. Returns the chosen Template, or None if quit."""
    menu = Menu(
        title="What do you want out of the track?",
        subtitle="Pick a template. Stemchotic handles the model choice for you.",
        esc_label="Quit",
    )

    for t in TEMPLATES:
        label = f"{t.name}  (experimental)" if t.experimental else t.name
        menu.add_item(MenuItem(label=label, value=t.key, description=t.description))

    result = menu.run()
    if result is None:
        return None
    return get_template(result.value)
