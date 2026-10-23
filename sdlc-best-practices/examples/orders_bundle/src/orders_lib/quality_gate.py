"""Deterministic quality gate run by the orders_refresh job after the pipeline update.

Exits non-zero (failing the task, the job run, and any CI step waiting on it) when the
published data breaks a rule in orders_lib.rules. Catalog and schema always arrive as
job parameters; nothing is hardcoded.
"""

from __future__ import annotations

import argparse
import sys

from orders_lib.rules import evaluate


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orders data quality gate")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    return parser.parse_args(argv)


def collect_metrics(spark, catalog: str, schema: str) -> dict[str, float]:
    """Read the row counts and freshness the gate evaluates."""
    fq = f"`{catalog}`.`{schema}`"
    row = spark.sql(
        f"""
        SELECT
          (SELECT COUNT(*) FROM {fq}.bronze_orders)      AS bronze_rows,
          (SELECT COUNT(*) FROM {fq}.silver_orders)      AS silver_rows,
          (SELECT COUNT(*) FROM {fq}.gold_daily_revenue) AS gold_rows,
          (SELECT COALESCE(DATEDIFF(CURRENT_DATE(), MAX(order_date)), 9999)
             FROM {fq}.gold_daily_revenue)               AS days_since_latest_order
        """
    ).first()
    return {k: float(v) for k, v in row.asDict().items()}


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    from pyspark.sql import SparkSession  # Imported lazily so unit tests need no Spark.

    spark = SparkSession.builder.getOrCreate()
    metrics = collect_metrics(spark, args.catalog, args.schema)
    print(f"quality metrics for {args.catalog}.{args.schema}: {metrics}")

    failures = evaluate(metrics)
    if failures:
        for failure in failures:
            print(f"QUALITY GATE FAILED: {failure}", file=sys.stderr)
        sys.exit(1)
    print("QUALITY GATE PASSED")


if __name__ == "__main__":
    main()
