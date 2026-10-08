import reflex as rx

from data_reaper.components.auth_form import auth_card
from data_reaper.state.auth_state import AuthState


@rx.page(route="/login", title="Log in · Data Reaper")
def login() -> rx.Component:
    return auth_card(
        "Data Reaper",
        rx.text(
            "Accounts are kept by Keycloak, the identity provider the "
            "Data Reaper shares with Night Crawler.",
            size="2",
            color_scheme="gray",
        ),
        rx.button("Log in", on_click=AuthState.start_login, width="100%"),
        rx.text(
            "No account? ",
            rx.link("Create one", on_click=AuthState.start_register, href="#"),
        ),
    )
