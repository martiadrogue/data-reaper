import pytest
from data_reaper.domain.exceptions import ValidationException
from data_reaper.domain.rules.dataset_detection import detect_dataset


def test_a_places_header_is_places():
    columns = ["item_id", "name", "address", "location", "rating", "source_url"]

    assert "places" == detect_dataset(columns)


def test_an_events_header_is_events():
    columns = ["item_id", "name", "start_date", "timezone", "venue", "source_url"]

    assert "events" == detect_dataset(columns)


@pytest.mark.parametrize(
    ("columns", "message"),
    [
        (["item_id", "name"], "Missing required columns: source_url."),
        (["item_id", "name", "source_url", "name"], "Repeated columns: name."),
        (["item_id", "name", "source_url", "menu"], "Unknown columns: menu."),
        (
            ["item_id", "name", "source_url", "rating", "start_date"],
            "The columns mix more than one dataset",
        ),
        (["item_id", "name", "source_url", "address"], "fit more than one dataset"),
    ],
)
def test_a_header_no_single_dataset_fits_is_refused(columns, message):
    with pytest.raises(ValidationException) as exc_info:
        detect_dataset(columns)

    assert 422 == exc_info.value.status_code
    assert message in exc_info.value.message
