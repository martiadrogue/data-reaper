import reflex as rx

from data_reaper import forms
from data_reaper.components.fields import choice
from data_reaper.components.nav import (
    error_callout,
    page_shell,
    status_badge,
)
from data_reaper.state.auth_state import AuthState
from data_reaper.state.imports_state import ImportsState


def _dataset_card(dataset: rx.Var) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading(dataset["name"], size="4"),
                rx.code(dataset["collection"]),
                align="center",
            ),
            rx.text(dataset["record_count"].to(str) + " records", size="2"),
            spacing="1",
        ),
        flex="1",
    )


def _row(dataset_import: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.link(
                rx.code(dataset_import["file_name"]),
                on_click=ImportsState.open_detail(dataset_import["id"]),
                cursor="pointer",
            )
        ),
        rx.table.cell(dataset_import["dataset_text"]),
        rx.table.cell(status_badge(dataset_import["status"])),
        rx.table.cell(
            rx.text(dataset_import["metrics_text"], size="2"),
            rx.cond(
                dataset_import["field_changes_text"] != "",
                rx.text(
                    "Most changed: ",
                    dataset_import["field_changes_text"],
                    size="1",
                    color_scheme="gray",
                ),
            ),
        ),
        rx.table.cell(
            rx.cond(
                ("admin" == AuthState.role) & dataset_import["is_retryable"],
                rx.button(
                    "Retry",
                    size="1",
                    variant="soft",
                    on_click=ImportsState.retry(dataset_import["id"]),
                ),
            )
        ),
    )


def _rejection(rejection: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rejection["row_number"]),
        rx.table.cell(rejection["reason"]),
    )


def _detail_line(label: str, value: rx.Var) -> rx.Component:
    return rx.text(rx.text.strong(label), " ", value, size="2")


def _detail_dialog() -> rx.Component:
    selected = ImportsState.selected
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(rx.code(selected["file_name"])),
            rx.vstack(
                rx.hstack(
                    status_badge(selected["status"]),
                    rx.text(selected["dataset"]),
                    spacing="3",
                ),
                _detail_line("Crawler:", rx.code(selected["crawler_id"])),
                _detail_line("Execution:", rx.code(selected["execution_id"])),
                _detail_line("Run started (UTC):", selected["started_at"]),
                _detail_line("Imported (UTC):", selected["imported_at"]),
                _detail_line("Rows read:", selected["rows_read"]),
                _detail_line("Rows:", selected["metrics"]),
                _detail_line("Fields changed:", selected["field_changes"]),
                rx.cond(
                    selected["error"] != "",
                    rx.callout(
                        selected["error"],
                        icon="triangle_alert",
                        color_scheme="red",
                        width="100%",
                    ),
                ),
                rx.cond(
                    ImportsState.selected_rejections.length() > 0,
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Row"),
                                rx.table.column_header_cell("Why it was rejected"),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(ImportsState.selected_rejections, _rejection)
                        ),
                        width="100%",
                    ),
                ),
                rx.hstack(
                    rx.dialog.close(rx.button("Close", variant="soft")),
                    justify="end",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            max_width="48em",
        ),
        open=ImportsState.detail_open,
        on_open_change=ImportsState.set_detail_open,
    )


@rx.page(
    route="/imports",
    title="Imports · Data Reaper",
    on_load=ImportsState.load_imports,
)
def imports() -> rx.Component:
    return page_shell(
        rx.vstack(
            rx.hstack(
                rx.heading("Imports", size="7"),
                rx.spacer(),
                rx.cond(
                    "admin" == AuthState.role,
                    rx.button(
                        "Scan for new files",
                        on_click=ImportsState.scan,
                        loading=ImportsState.is_scanning,
                    ),
                ),
                width="100%",
                align="center",
            ),
            rx.text(
                "Every validated CSV in the import folder, newest first. New "
                "files are picked up every minute; each row is upserted by its "
                "source and item_id, so importing a file twice changes nothing.",
                size="2",
                color_scheme="gray",
            ),
            rx.hstack(rx.foreach(ImportsState.datasets, _dataset_card), width="100%"),
            error_callout(ImportsState.error),
            rx.cond(
                ImportsState.notice != "",
                rx.callout(ImportsState.notice, icon="info", width="100%"),
            ),
            rx.hstack(
                rx.box(
                    choice(
                        forms.IMPORT_STATUS_FILTERS,
                        ImportsState.status_filter,
                        ImportsState.set_status_filter,
                    ),
                    width="12em",
                ),
                rx.text(ImportsState.status_counts_text, size="2", color_scheme="gray"),
                align="center",
                spacing="3",
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("File"),
                        rx.table.column_header_cell("Dataset"),
                        rx.table.column_header_cell("Status"),
                        rx.table.column_header_cell("Rows"),
                        rx.table.column_header_cell(""),
                    )
                ),
                rx.table.body(rx.foreach(ImportsState.imports, _row)),
                width="100%",
            ),
            rx.hstack(
                rx.button(
                    "Previous",
                    variant="soft",
                    on_click=ImportsState.go_previous,
                    disabled=~ImportsState.has_previous,
                ),
                rx.button(
                    "Next",
                    variant="soft",
                    on_click=ImportsState.go_next,
                    disabled=~ImportsState.has_next,
                ),
                justify="end",
                width="100%",
            ),
            _detail_dialog(),
            spacing="4",
            width="100%",
        )
    )
