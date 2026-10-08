from datetime import datetime

from data_reaper.domain.rules.import_file_names import (
    is_csv_file_name,
    parse_import_file_name,
    sort_file_names_oldest_first,
)

CRAWLER = "c57f32ca-b70f-4f87-b93f-233f0f7b9efd"
EXECUTION = "aa510372-f182-43d6-8f05-a39126a2c5ea"


def test_parses_the_crawler_execution_and_start_of_a_file_name():
    parsed = parse_import_file_name(f"{CRAWLER}_{EXECUTION}_20261005T100800Z.csv")

    assert CRAWLER == parsed.crawler_id
    assert EXECUTION == parsed.execution_id
    assert datetime(2026, 10, 5, 10, 8) == parsed.started_at


def test_a_name_of_another_shape_does_not_parse():
    assert None is parse_import_file_name("export.csv")
    assert None is parse_import_file_name(f"{CRAWLER}_{EXECUTION}.csv")
    assert None is parse_import_file_name(f"{CRAWLER}_{EXECUTION}_20261005T100800Z.txt")


def test_an_impossible_start_does_not_parse():
    assert None is parse_import_file_name(f"{CRAWLER}_{EXECUTION}_20261305T100800Z.csv")


def test_csv_file_names_match_in_any_case():
    assert is_csv_file_name("a.CSV")
    assert not is_csv_file_name("a.csv.part")


def test_files_sort_by_run_start_with_unparsed_names_last():
    newer = f"{CRAWLER}_{EXECUTION}_20261005T120000Z.csv"
    older = f"{CRAWLER}_{EXECUTION}_20261001T090000Z.csv"

    assert [older, newer, "a.csv", "b.csv"] == sort_file_names_oldest_first(
        ["b.csv", newer, "a.csv", older]
    )
