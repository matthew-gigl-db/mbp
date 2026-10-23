"""Unit tests for orders_lib.rules. Run on every pull request; no Spark or workspace needed."""

import pytest

from orders_lib.quality_gate import _parse_args
from orders_lib.rules import (
    SILVER_EXPECTATIONS,
    VALID_STATUSES,
    QualityThresholds,
    drop_ratio,
    evaluate,
)

HEALTHY = {"bronze_rows": 1000, "silver_rows": 990, "gold_rows": 30, "days_since_latest_order": 0}


def test_healthy_metrics_pass():
    assert evaluate(HEALTHY) == []


def test_empty_gold_fails():
    failures = evaluate({**HEALTHY, "gold_rows": 0})
    assert len(failures) == 1
    assert failures[0].startswith("gold_rows=0")


def test_high_drop_ratio_fails():
    failures = evaluate({**HEALTHY, "silver_rows": 900})
    assert any(f.startswith("drop_ratio=0.100") for f in failures)


def test_stale_data_fails():
    failures = evaluate({**HEALTHY, "days_since_latest_order": 5})
    assert any("5 days old" in f for f in failures)


def test_missing_metrics_reported():
    assert evaluate({"gold_rows": 1}) == [
        "missing metrics: bronze_rows, days_since_latest_order, silver_rows"
    ]


def test_custom_thresholds():
    strict = QualityThresholds(min_gold_rows=100)
    assert evaluate(HEALTHY, strict) == ["gold_rows=30 is below 100"]


@pytest.mark.parametrize(
    ("bronze", "silver", "expected"),
    [(0, 0, 0.0), (100, 100, 0.0), (100, 95, 0.05), (100, 120, 0.0)],
)
def test_drop_ratio(bronze, silver, expected):
    assert drop_ratio(bronze, silver) == pytest.approx(expected)


def test_expectation_names_are_stable():
    # Renaming an expectation breaks event-log dashboards and alerts; make it a reviewed change.
    assert set(SILVER_EXPECTATIONS) == {
        "order_id_present",
        "customer_id_present",
        "amount_non_negative",
        "status_known",
        "order_ts_present",
    }


def test_status_expectation_lists_every_status():
    for status in VALID_STATUSES:
        assert f"'{status}'" in SILVER_EXPECTATIONS["status_known"]


def test_quality_gate_requires_catalog_and_schema():
    args = _parse_args(["--catalog", "retail_tst", "--schema", "orders"])
    assert (args.catalog, args.schema) == ("retail_tst", "orders")
    with pytest.raises(SystemExit):
        _parse_args(["--catalog", "retail_tst"])
