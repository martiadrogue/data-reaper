from data_reaper import forms


def test_blank_to_none_trims_and_drops_blank_text():
    assert "a" == forms.blank_to_none("  a ")
    assert None is forms.blank_to_none("   ")
    assert None is forms.blank_to_none(None)


def test_import_params_turn_the_all_filter_off():
    assert {"status": None, "limit": 50, "offset": 50} == forms.import_params(
        forms.ALL, 50
    )
    assert "failed" == forms.import_params("failed", 0)["status"]


def test_record_params_page_only_when_unfiltered():
    unfiltered = forms.record_params("", forms.ALL, 100)
    filtered = forms.record_params(" grill ", forms.ALL, 100)
    by_source = forms.record_params("", "thefork.es", 100)

    assert {"text": None, "source": None, "limit": 50, "offset": 100} == unfiltered
    assert {"text": "grill", "source": None, "limit": 50, "offset": 0} == filtered
    assert ("thefork.es", 0) == (by_source["source"], by_source["offset"])


def test_next_offset_is_none_on_the_last_page():
    assert 100 == forms.next_offset({"offset": 50, "limit": 50, "has_more": True})
    assert None is forms.next_offset({"offset": 50, "limit": 50, "has_more": False})
    assert None is forms.next_offset({})


def test_previous_offset_is_none_on_the_first_page():
    assert 0 == forms.previous_offset({"offset": 30, "limit": 50})
    assert 50 == forms.previous_offset({"offset": 100, "limit": 50})
    assert None is forms.previous_offset({"offset": 0, "limit": 50})
    assert None is forms.previous_offset({})


def test_source_options_list_the_datasets_sources_sorted():
    datasets = [
        {"name": "places", "source_counts": {"thefork.es": 3, "maps.google.com": 1}},
        {"name": "events", "source_counts": {"atrapalo.com": 2}},
    ]

    assert [forms.ALL, "maps.google.com", "thefork.es"] == forms.source_options(
        datasets, "places"
    )
    assert [forms.ALL] == forms.source_options(datasets, "menus")


def test_metrics_summary_reads_missing_counters_as_zero():
    assert "2 new · 0 updated · 1 unchanged · 0 rejected" == forms.metrics_summary(
        {"records_inserted": 2, "records_unchanged": 1}
    )


def test_join_texts_shows_a_dash_for_nothing():
    assert "a, b" == forms.join_texts(["a", "b"])
    assert "—" == forms.join_texts([])
    assert "—" == forms.join_texts(None)


def test_with_display_fields_adds_the_table_texts():
    shown = forms.with_display_fields(
        {"status": "imported", "dataset": None, "metrics": {"records_inserted": 1}}
    )

    assert "—" == shown["dataset_text"]
    assert shown["metrics_text"].startswith("1 new")
    assert False is shown["is_retryable"]
    assert True is forms.with_display_fields({"status": "failed"})["is_retryable"]


def test_with_list_texts_adds_one_line_per_list():
    shown = forms.with_list_texts(
        {"categories": ["Bar", "Grill"], "organizers": []}, "categories", "organizers"
    )

    assert "Bar, Grill" == shown["categories_text"]
    assert "—" == shown["organizers_text"]


def test_import_detail_is_display_text():
    detail = forms.import_detail(
        {
            "file_name": "a.csv",
            "status": "imported",
            "dataset": "places",
            "crawler_id": None,
            "metrics": {"rows_read": 3, "records_inserted": 3},
            "error": None,
        }
    )

    assert ("—", "3", "") == (
        detail["crawler_id"],
        detail["rows_read"],
        detail["error"],
    )
    assert detail["metrics"].startswith("3 new")
    assert all(isinstance(value, str) for value in detail.values())


def test_field_changes_summary_lists_the_most_changed_first():
    changes = [
        {"field": "rating", "count": 41},
        {"field": "review_count", "count": 38},
        {"field": "opening_hours", "count": 12},
        {"field": "phone", "count": 1},
    ]

    assert "rating 41 · review_count 38 · opening_hours 12" == (
        forms.field_changes_summary(changes, limit=3)
    )
    assert forms.field_changes_summary(changes).endswith("· phone 1")
    assert "" == forms.field_changes_summary([])


def test_display_texts_show_the_top_field_changes():
    changes = [{"field": name, "count": 1} for name in ("a", "b", "c", "d")]

    shown = forms.with_display_fields({"status": "imported", "field_changes": changes})
    detail = forms.import_detail({"field_changes": changes})

    assert "a 1 · b 1 · c 1" == shown["field_changes_text"]
    assert "a 1 · b 1 · c 1 · d 1" == detail["field_changes"]
    assert "—" == forms.import_detail({})["field_changes"]
