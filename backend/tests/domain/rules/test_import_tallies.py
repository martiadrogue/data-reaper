from data_reaper.domain.bundles.import_batch import ImportTally
from data_reaper.domain.model.constants import MAX_STORED_REJECTIONS
from data_reaper.domain.model.value_objects import (
    ImportMetrics,
    RowRejection,
)
from data_reaper.domain.rules.import_tallies import (
    count_changed_fields,
    count_outcome,
)


def test_each_outcome_counts_once_and_as_a_read_row():
    tally = ImportTally()
    for row_number, outcome in enumerate(
        ["inserted", "inserted", "updated", "unchanged"], start=1
    ):
        tally = count_outcome(tally, outcome, row_number)

    assert ImportMetrics(4, 2, 1, 1, 0) == tally.metrics
    assert () == tally.rejections


def test_a_rejection_keeps_its_row_and_reason():
    tally = count_outcome(ImportTally(), "rejected", 7, "rating: bad.")

    assert 1 == tally.metrics.rows_rejected
    assert (RowRejection(7, "rating: bad."),) == tally.rejections


def test_only_the_first_rejections_keep_their_reason():
    tally = ImportTally()
    for row_number in range(1, MAX_STORED_REJECTIONS + 6):
        tally = count_outcome(tally, "rejected", row_number, "bad")

    assert MAX_STORED_REJECTIONS + 5 == tally.metrics.rows_rejected
    assert MAX_STORED_REJECTIONS == len(tally.rejections)


def test_changed_fields_add_up_per_field():
    tally = count_changed_fields(ImportTally(), ("rating", "phone"))
    tally = count_changed_fields(tally, ("rating",))

    assert {"rating": 2, "phone": 1} == tally.field_changes


def test_no_changed_fields_counts_nothing():
    assert {} == count_changed_fields(ImportTally(), ()).field_changes


def test_counting_an_outcome_keeps_the_field_changes():
    tally = count_changed_fields(ImportTally(), ("rating",))

    tally = count_outcome(tally, "updated", 1)

    assert {"rating": 1} == tally.field_changes
