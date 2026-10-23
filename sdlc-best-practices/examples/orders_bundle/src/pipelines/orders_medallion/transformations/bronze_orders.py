"""Bronze: incrementally ingest raw order JSON from the landing volume with Auto Loader.

The landing path is injected by the bundle (pipeline configuration key
`orders.landing_path`), so this file never names a catalog, schema, or volume.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

LANDING_PATH = spark.conf.get("orders.landing_path")  # noqa: F821 -- provided by the pipeline runtime


@dp.table(
    name="bronze_orders",
    comment="Raw orders as received, plus ingestion metadata. Append-only.",
)
def bronze_orders():
    return (
        spark.readStream.format("cloudFiles")  # noqa: F821
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
        .load(LANDING_PATH)
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )
