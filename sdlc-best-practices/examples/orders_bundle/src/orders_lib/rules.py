"""Pure-Python business rules for orders.

Nothing in this module imports Spark, so every rule is unit-testable on a CI runner
in milliseconds. The pipeline and the quality gate import the same definitions,
which keeps "what we test" and "what we run" identical.
"""

from __future__ import annotations

from dataclasses import dataclass

VALID_STATUSES: tuple[str, ...] = ("PLACED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED")

# Expectations applied to the silver table with expect_all_or_drop.
# Keys become expectation names in the pipeline event log, so keep them stable.
SILVER_EXPECTATIONS: dict[str, str] = {
    "order_id_present": "order_id IS NOT NULL",
    "customer_id_present": "customer_id IS NOT NULL",
    "amount_non_negative": "amount >= 0",
    "status_known": "status IN (" + ", ".join(f"'{s}'" for s in VALID_STATUSES) + ")",
    "order_ts_present": "order_ts IS NOT NULL",
}


@dataclass(frozen=True)
class QualityThresholds:
    """Limits the quality gate enforces on the published gold table."""

    min_gold_rows: int = 1
    max_drop_ratio: float = 0.05
    max_days_stale: int = 2


def drop_ratio(bronze_rows: int, silver_rows: int) -> float:
    """Share of bronze rows removed by silver expectations (0.0 when bronze is empty)."""
    if bronze_rows <= 0:
        return 0.0
    dropped = max(bronze_rows - silver_rows, 0)
    return dropped / bronze_rows


def evaluate(metrics: dict[str, float], thresholds: QualityThresholds | None = None) -> list[str]:
    """Return human-readable failures. An empty list means the gate passes.

    Expected metric keys: bronze_rows, silver_rows, gold_rows, days_since_latest_order.
    """
    t = thresholds or QualityThresholds()
    failures: list[str] = []

    missing = {"bronze_rows", "silver_rows", "gold_rows", "days_since_latest_order"} - metrics.keys()
    if missing:
        return [f"missing metrics: {', '.join(sorted(missing))}"]

    if metrics["gold_rows"] < t.min_gold_rows:
        failures.append(f"gold_rows={int(metrics['gold_rows'])} is below {t.min_gold_rows}")

    ratio = drop_ratio(int(metrics["bronze_rows"]), int(metrics["silver_rows"]))
    if ratio > t.max_drop_ratio:
        failures.append(f"drop_ratio={ratio:.3f} exceeds {t.max_drop_ratio:.3f}")

    if metrics["days_since_latest_order"] > t.max_days_stale:
        failures.append(
            f"latest order is {int(metrics['days_since_latest_order'])} days old "
            f"(limit {t.max_days_stale})"
        )

    return failures
