"""Gold: daily revenue, the table consumers and dashboards read."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="gold_daily_revenue",
    comment="Daily order count and revenue, excluding cancelled and returned orders.",
)
def gold_daily_revenue():
    return (
        spark.read.table("silver_orders")  # noqa: F821
        .where(~F.col("status").isin("CANCELLED", "RETURNED"))
        .groupBy(F.to_date("order_ts").alias("order_date"))
        .agg(
            F.countDistinct("order_id").alias("orders"),
            F.sum("amount").alias("revenue"),
        )
    )
