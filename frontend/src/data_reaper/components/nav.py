import reflex as rx

from data_reaper.state.auth_state import AuthState


def navbar() -> rx.Component:
    return rx.hstack(
        rx.link(rx.heading("Data Reaper", size="5"), href="/imports"),
        rx.spacer(),
        rx.cond(
            AuthState.is_authenticated,
            rx.hstack(
                rx.link("Imports", href="/imports"),
                rx.link("Places", href="/places"),
                rx.link("Events", href="/events"),
                rx.text(AuthState.email, color_scheme="gray"),
                rx.button("Log out", on_click=AuthState.logout, variant="soft"),
                spacing="4",
                align="center",
            ),
        ),
        width="100%",
        padding="1em",
        border_bottom="1px solid var(--gray-5)",
        align="center",
    )


def page_shell(*children: rx.Component) -> rx.Component:
    return rx.vstack(
        navbar(),
        rx.container(
            *children,
            padding="2em",
            size="4",
            margin="0 auto",
            width="100%",
            min_width="min(100%, 20rem)",
            box_sizing="border-box",
        ),
        width="100%",
        spacing="0",
    )


def error_callout(message: rx.Var) -> rx.Component:
    return rx.cond(
        message != "",
        rx.callout(message, icon="triangle_alert", color_scheme="red", width="100%"),
    )


def status_badge(status: rx.Var) -> rx.Component:
    return rx.badge(
        status,
        color_scheme=rx.match(
            status,
            ("pending", "amber"),
            ("importing", "blue"),
            ("imported", "green"),
            ("failed", "red"),
            "gray",
        ),
    )
