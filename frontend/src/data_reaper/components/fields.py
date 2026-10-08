import reflex as rx


def labelled(label: str, control: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", weight="medium"), control, spacing="1", width="100%"
    )


def choice(options: list[str] | rx.Var, value, on_change, **props) -> rx.Component:
    """A select over fixed string options."""
    return rx.select(options, value=value, on_change=on_change, width="100%", **props)
