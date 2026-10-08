import reflex as rx

from data_reaper.components.fields import choice
from data_reaper.components.nav import error_callout


def records_page(
    state,
    title: str,
    description: str,
    columns: list[str],
    row,
) -> rx.Component:
    """A Dataset's records: search, source filter, table, paging."""
    return rx.vstack(
        rx.heading(title, size="7"),
        rx.text(description, size="2", color_scheme="gray"),
        error_callout(state.error),
        rx.hstack(
            rx.form(
                rx.hstack(
                    rx.input(
                        name="text",
                        placeholder="Name or address contains…",
                        default_value=state.text_filter,
                        width="20em",
                    ),
                    rx.button("Search", type="submit", variant="soft"),
                ),
                on_submit=state.search,
            ),
            rx.box(
                choice(state.sources, state.source_filter, state.set_source),
                width="14em",
            ),
            rx.spacer(),
            rx.text(state.range_text, size="2", color_scheme="gray"),
            width="100%",
            align="center",
            flex_wrap="wrap",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    *[rx.table.column_header_cell(column) for column in columns]
                )
            ),
            rx.table.body(rx.foreach(state.records, row)),
            width="100%",
        ),
        rx.hstack(
            rx.button(
                "Previous",
                variant="soft",
                on_click=state.go_previous,
                disabled=~state.has_previous,
            ),
            rx.button(
                "Next",
                variant="soft",
                on_click=state.go_next,
                disabled=~state.has_next,
            ),
            justify="end",
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


def optional_cell(value: rx.Var) -> rx.Component:
    """A table cell showing `value`, or `—` when it is missing."""
    return rx.table.cell(rx.cond(value, value.to(str), "—"))
