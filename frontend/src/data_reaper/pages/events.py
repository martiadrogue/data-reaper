import reflex as rx

from data_reaper.components.nav import page_shell
from data_reaper.components.records import optional_cell, records_page
from data_reaper.state.records_state import EventsState


def _row(event: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.link(event["name"], href=event["source_url"].to(str), is_external=True)
        ),
        rx.table.cell(rx.code(event["source"])),
        optional_cell(event["start_date"]),
        optional_cell(event["venue"]),
        rx.table.cell(event["categories_text"]),
        optional_cell(event["cost"]),
    )


@rx.page(
    route="/events",
    title="Events · Data Reaper",
    on_load=EventsState.load_records,
)
def events() -> rx.Component:
    return page_shell(
        records_page(
            EventsState,
            "Events",
            "Shows and sessions from events CSVs (dataset_events), one per "
            "source and item_id. Start times are wall-clock times in each "
            "event's timezone.",
            ["Name", "Source", "Starts", "Venue", "Categories", "Cost"],
            _row,
        )
    )
