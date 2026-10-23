"""Silver: typed, validated orders. Rows failing a business rule are dropped and counted.

The expectations come from orders_lib.rules -- the same definitions the unit tests and
the quality gate use.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from orders_lib.rules import SILVER_EXPECTATIONS


@dp.table(
    name="silver_orders",
    comment="Typed and validated orders. One row per order event that passed all expectations.",
)
@dp.expect_all_or_drop(SILVER_EXPECTATIONS)
def silver_orders():
    return spark.readStream.table("bronze_orders").select(  # noqa: F821
        F.col("order_id").cast("string").alias("order_id"),
        F.col("customer_id").cast("string").alias("customer_id"),
        F.upper(F.col("status")).alias("status"),
        F.col("amount").cast("decimal(18,2)").alias("amount"),
        F.to_timestamp("order_ts").alias("order_ts"),
        F.col("_ingested_at"),
        F.col("_source_file"),
    )
