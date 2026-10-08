from dataclasses import replace
from datetime import datetime

from data_reaper.domain.model.entities import DatasetEvent, DatasetPlace
from data_reaper.domain.rules.dataset_rows import normalize_row
from data_reaper.domain.rules.record_upserts import (
    ImportSighting,
    apply_row,
    compute_content_hash,
)

JAN = datetime(2026, 1, 1)
FEB = datetime(2026, 2, 1)
ROW = {
    "item_id": "r1",
    "name": "Arrabal",
    "categories": '["Grill", "Argentino"]',
    "rating": "9.8",
    "source_url": "https://www.thefork.es/restaurante/r1",
}


def _sighting(started_at: datetime, import_id: str = "import-1") -> ImportSighting:
    return ImportSighting(
        import_id=import_id,
        crawler_id="crawler-1",
        execution_id="execution-1",
        started_at=started_at,
    )


def _insert(row=ROW, started_at=JAN) -> DatasetPlace:
    outcome = apply_row(
        DatasetPlace, None, normalize_row("places", row), _sighting(started_at), "p1"
    )
    return outcome.record


def test_an_unknown_key_is_inserted_with_the_runs_start_as_every_time():
    outcome = apply_row(
        DatasetPlace, None, normalize_row("places", ROW), _sighting(JAN), "p1"
    )

    place = outcome.record
    assert "inserted" == outcome.outcome
    assert ("p1", "thefork.es", "r1") == (place.id, place.source, place.item_id)
    assert JAN == place.created_at == place.updated_at == place.last_seen_at
    assert ("crawler-1", "execution-1", "import-1") == (
        place.crawler_id,
        place.last_execution_id,
        place.last_import_id,
    )
    assert compute_content_hash(place) == place.content_hash


def test_the_same_content_later_only_moves_last_seen():
    stored = _insert()

    outcome = apply_row(
        DatasetPlace,
        stored,
        normalize_row("places", ROW),
        _sighting(FEB, "import-2"),
        "unused",
    )

    assert "unchanged" == outcome.outcome
    assert (JAN, FEB) == (outcome.record.updated_at, outcome.record.last_seen_at)
    assert "import-2" == outcome.record.last_import_id
    assert "p1" == outcome.record.id


def test_changed_content_later_is_an_update():
    stored = _insert()

    outcome = apply_row(
        DatasetPlace,
        stored,
        normalize_row("places", {**ROW, "rating": "9.1"}),
        _sighting(FEB),
        "unused",
    )

    assert "updated" == outcome.outcome
    assert 9.1 == outcome.record.rating
    assert (JAN, FEB, FEB) == (
        outcome.record.created_at,
        outcome.record.updated_at,
        outcome.record.last_seen_at,
    )
    assert stored.content_hash != outcome.record.content_hash


def test_an_older_file_never_overwrites_newer_data():
    stored = _insert(started_at=FEB)

    outcome = apply_row(
        DatasetPlace,
        stored,
        normalize_row("places", {**ROW, "rating": "5"}),
        _sighting(JAN),
        "unused",
    )

    assert "rejected" == outcome.outcome
    assert None is outcome.record
    assert "newer file" in outcome.reason


def test_re_importing_the_same_file_is_unchanged():
    stored = _insert()

    outcome = apply_row(
        DatasetPlace, stored, normalize_row("places", ROW), _sighting(JAN), "unused"
    )

    assert "unchanged" == outcome.outcome


def test_a_column_the_file_lacks_keeps_the_stored_value():
    stored = replace(_insert(), phone="860 770")

    outcome = apply_row(
        DatasetPlace, stored, normalize_row("places", ROW), _sighting(FEB), "unused"
    )

    assert "860 770" == outcome.record.phone


def test_the_hash_ignores_list_order_and_the_source_url():
    place = _insert()

    reordered = replace(place, categories=list(reversed(place.categories)))
    moved = replace(place, source_url="https://www.thefork.es/r1?utm=x")

    assert compute_content_hash(place) == compute_content_hash(reordered)
    assert compute_content_hash(place) == compute_content_hash(moved)
    assert compute_content_hash(place) != compute_content_hash(
        replace(place, name="Other")
    )


def test_events_are_upserted_the_same_way():
    row = normalize_row(
        "events",
        {
            "item_id": "e1",
            "name": "Show",
            "start_date": "2026-10-09 22:00:00",
            "source_url": "https://barcelonacomedyclub.com/?p=2571#ri-1",
        },
    )

    outcome = apply_row(DatasetEvent, None, row, _sighting(JAN), "e-id")

    assert "inserted" == outcome.outcome
    assert "barcelonacomedyclub.com" == outcome.record.source


def test_an_update_names_the_fields_it_changed():
    stored = _insert()

    outcome = apply_row(
        DatasetPlace,
        stored,
        normalize_row("places", {**ROW, "rating": "9.1"}),
        _sighting(FEB),
        "unused",
    )

    assert ("rating",) == outcome.changed_fields


def test_filling_or_clearing_a_value_is_a_change():
    stored = replace(_insert(), address="Carrer de Bretón, 18")
    row = {
        **ROW,
        "address": "",
        "phone": "934 50 50 50",
        "location": '{"latitude": 41.4, "longitude": 2.15}',
    }

    outcome = apply_row(
        DatasetPlace, stored, normalize_row("places", row), _sighting(FEB), "unused"
    )

    assert ("address", "location", "phone") == outcome.changed_fields


def test_a_moved_location_is_a_change():
    row = {**ROW, "location": '{"latitude": 41.4, "longitude": 2.15}'}
    stored = _insert(row)
    moved = {**row, "location": '{"latitude": 41.5, "longitude": 2.15}'}

    outcome = apply_row(
        DatasetPlace, stored, normalize_row("places", moved), _sighting(FEB), "unused"
    )

    assert ("location",) == outcome.changed_fields


def test_only_updates_name_changed_fields():
    stored = _insert()
    reordered = {
        **ROW,
        "categories": '["Argentino", "Grill"]',
        "source_url": "https://www.thefork.es/restaurante/r1?utm=x",
    }

    unchanged = apply_row(
        DatasetPlace,
        stored,
        normalize_row("places", reordered),
        _sighting(FEB),
        "unused",
    )
    inserted = apply_row(
        DatasetPlace, None, normalize_row("places", ROW), _sighting(JAN), "p1"
    )

    assert ("unchanged", ()) == (unchanged.outcome, unchanged.changed_fields)
    assert () == inserted.changed_fields
