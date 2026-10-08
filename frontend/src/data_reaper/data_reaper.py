import reflex as rx

from data_reaper.pages import (  # noqa: F401 - registers the pages
    auth_callback,
    events,
    imports,
    login,
    places,
    register,
)
from data_reaper.state.auth_state import AuthState


def index() -> rx.Component:
    return rx.center(rx.spinner(), min_height="100vh")


app = rx.App()
app.add_page(index, route="/", on_load=AuthState.redirect_from_index)
