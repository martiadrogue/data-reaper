import reflex as rx

from data_reaper.components.nav import page_shell
from data_reaper.components.records import optional_cell, records_page
from data_reaper.state.records_state import PlacesState


def _row(place: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.link(place["name"], href=place["source_url"].to(str), is_external=True)
        ),
        rx.table.cell(rx.code(place["source"])),
        optional_cell(place["address"]),
        rx.table.cell(place["categories_text"]),
        optional_cell(place["rating"]),
        optional_cell(place["review_count"]),
        optional_cell(place["price_range"]),
    )


@rx.page(
    route="/places",
    title="Places · Data Reaper",
    on_load=PlacesState.load_records,
)
def places() -> rx.Component:
    return page_shell(
        records_page(
            PlacesState,
            "Places",
            "Restaurants and venues from places CSVs (dataset_places), one per "
            "source and item_id. Ratings are shown as each source gives them: "
            "TheFork out of 10, Google out of 5.",
            [
                "Name",
                "Source",
                "Address",
                "Categories",
                "Rating",
                "Reviews",
                "Price",
            ],
            _row,
        )
    )
