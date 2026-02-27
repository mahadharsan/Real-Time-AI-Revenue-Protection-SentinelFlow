from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, LongType
from pyspark.sql import functions as F

# 1. Initialize Spark Session
spark = SparkSession.builder \
    .appName("SentinelFlow-Processor") \
    .config("spark.jars", "/opt/spark/jars/postgresql-42.7.5.jar") \
    .getOrCreate()

# Database Config
db_url = "jdbc:postgresql://sentinel_postgres:5432/sentinel_operational"
db_properties = {
    "user": "maha_admin",
    "password": "sentinel_pass",
    "driver": "org.postgresql.Driver"
}

# 2. Define the Schema
schema = StructType([
    StructField("event_id", StringType()),
    StructField("user_id", StringType()),
    StructField("account_id", StringType()),
    StructField("email", StringType()),
    StructField("mrr", FloatType()),
    StructField("event_type", StringType()),
    StructField("category", StringType()),
    StructField("event_body", StringType()),
    StructField("csat_score", IntegerType()),
    StructField("timestamp", LongType())
])

# 3. Read from Redpanda
raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "redpanda:29092") \
    .option("subscribe", "sentinel.raw.events") \
    .load()

# 4. Base Transformation
structured_df = raw_stream.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), schema).alias("data")) \
    .select("data.*")

# 4.1. Prepare Timestamp & Watermark (Essential for windowing)
windowed_base = structured_df.withColumn(
    "event_timestamp", F.from_unixtime(F.col("timestamp")).cast("timestamp")
).withWatermark("event_timestamp", "1 minute")

# --- 5. BRANCH 1: HIGH PRIORITY ALERTS (Fast Reactive) ---
scored_df = structured_df.withColumn(
    "priority_score", col("mrr") * (5 - col("csat_score"))
)
high_priority_df = scored_df.filter((col("mrr") >= 10000) & (col("csat_score") <= 3) & (col("event_type") == "support_ticket"))

# --- 6. BRANCH 2: FRICTION LOOPS (Proactive Systemic) ---
friction_loops_df = windowed_base \
    .filter(F.col("event_type") == "support_ticket") \
    .groupBy(F.window("event_timestamp", "2 minutes", "1 minute"), "account_id", "category", "mrr") \
    .agg(F.count("*").alias("incident_count"), F.first("event_body").alias("event_summary")) \
    .withColumn("window_start", F.col("window.start")) \
    .withColumn("window_end", F.col("window.end")) \
    .drop("window") \
    .filter((F.col("incident_count") >= 3) & (F.col("mrr") >= 10000))

# --- 7. BRANCH 3: SILENT CHURNERS (Proactive Behavioral) ---
silent_churn_df = windowed_base \
    .groupBy(F.window("event_timestamp", "2 minutes", "1 minute"), "account_id", "mrr") \
    .agg(
        F.count(F.when(F.col("event_type") == "login", 1)).alias("login_count"),
        F.count(F.when(F.col("event_type") == "feature_access", 1)).alias("feature_count")
    ) \
    .withColumn("window_start", F.col("window.start")) \
    .withColumn("window_end", F.col("window.end")) \
    .drop("window") \
    .filter((F.col("login_count") >= 5) & (F.col("feature_count") == 0) & (F.col("mrr") >= 10000))

# --- 8. MULTI-QUERY EXECUTION ---

# Query 1: High Priority
q1 = high_priority_df.writeStream.foreachBatch(lambda df, id: \
    df.write.jdbc(url=db_url, table="high_priority_alerts", mode="append", properties=db_properties) \
).start()

# Query 2: Friction Loops (Note: JDBC sink doesn't support 'update' mode directly, so we use foreachBatch)
q2 = friction_loops_df.writeStream.outputMode("update").foreachBatch(lambda df, id: \
    df.write.jdbc(url=db_url, table="friction_loops", mode="append", properties=db_properties) \
).start()

# Query 3: Silent Churners
q3 = silent_churn_df.writeStream.outputMode("update").foreachBatch(lambda df, id: \
    df.write.jdbc(url=db_url, table="silent_churners", mode="append", properties=db_properties) \
).start()

spark.streams.awaitAnyTermination()