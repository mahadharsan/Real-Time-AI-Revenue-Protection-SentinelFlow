from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, udf
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType
# Import the class, but don't initialize it globally!
from recovery_agent import RevenueRecoveryAgent 

# 1. Initialize the Spark Session
spark = SparkSession.builder \
    .appName("SentinelRevenueRecovery") \
    .getOrCreate()

# 2. Define the Schema
schema = StructType([
    StructField("account_id", StringType()),
    StructField("mrr", FloatType()),
    StructField("event_body", StringType()),
    StructField("csat_score", IntegerType()),
    # ... include other fields if needed
])

# 3. Define the UDF logic
def generate_recovery_draft(account_id, mrr, complaint):
    if not complaint: 
        return "No complaint provided."
    
    # CRITICAL: Initialize the agent INSIDE the function
    # Each worker will create its own agent instance when it processes a row
    try:
        local_agent = RevenueRecoveryAgent() 
        state_input = {"account_id": account_id, "mrr": float(mrr), "complaint": complaint}
        result = local_agent.run(state_input)
        return result.get("draft_email", "Draft generation failed.")
    except Exception as e:
        return f"Agent Error: {str(e)}"

agent_udf = udf(generate_recovery_draft, StringType())

# 4. Read the stream
raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "redpanda:29092") \
    .option("subscribe", "sentinel.raw.events") \
    .option("startingOffsets", "latest") \
    .load()

# 5. Process data
risk_alerts = raw_stream.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), schema).alias("data")) \
    .select("data.*") \
    .filter((col("mrr") >= 1000) & (col("csat_score") <= 3))

enriched_alerts = risk_alerts.withColumn(
    "ai_email", 
    agent_udf(col("account_id"), col("mrr"), col("event_body"))
)

# 6. Output to Console
query = enriched_alerts.writeStream.outputMode("append").format("console").start()
query.awaitTermination()