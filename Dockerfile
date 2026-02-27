# 1. Start with a version of Python that supports your AI libraries
FROM python:3.10-slim

# 2. Install Java (Updated to 21 to match the new Debian repository)
RUN apt-get update && \
    apt-get install -y openjdk-21-jre-headless procps && \
    rm -rf /var/lib/apt/lists/*

# 3. Install Spark 3.5.0
ENV SPARK_VERSION=3.5.0
RUN pip install --no-cache-dir pyspark==${SPARK_VERSION}

# 4. Install your AI Agent libraries
RUN pip install --no-cache-dir \
    google-generativeai \
    langchain-google-genai \
    langgraph \
    python-dotenv

# 5. Set Spark home and path
# Note: The site-packages path is usually here in the slim image
ENV SPARK_HOME=/usr/local/lib/python3.10/site-packages/pyspark
ENV PATH=$PATH:$SPARK_HOME/bin

# Set the working directory
WORKDIR /opt/spark/work-dir

# Keep the container running
CMD ["tail", "-f", "/dev/null"]