import reflex as rx

from data_reaper.components.auth_form import auth_card
from data_reaper.state.auth_state import AuthState


@rx.page(
    route="/auth/callback",
    title="Logging in · Data Reaper",
    on_load=AuthState.finish_login,
)
def auth_callback() -> rx.Component:
    """Where Keycloak sends the browser back with the login's code."""
    return auth_card(
        "Logging in",
        rx.cond(
            AuthState.error == "",
            rx.spinner(),
            rx.link("Back to log in", href="/login"),
        ),
    )
