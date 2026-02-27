from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
import psycopg2

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key = API_KEY)

# 2. Expert Solutions (The "Brain" Data)
knowledge_base_data = [
    {
        "category": "Technical Infrastructure",
        "content": "SOP for API & Infrastructure: For API timeouts or high latency, advise the client to use exponential backoff and check if they are on the v2.1 endpoint. If an outage is reported, provide the link to status.sentinel.io. For documentation or error reporting issues, direct users to the Developer Portal for updated examples."
    },
    {
        "category": "Financial & Billing",
        "content": "SOP for Billing: For overcharges or invoice errors, check account MRR. If MRR > 1000, issue an immediate 'Goodwill Credit' to the account. For all other billing discrepancies, inform the user that a financial audit is underway and will be resolved within 24 hours."
    },
    {
        "category": "Access & Security",
        "content": "SOP for Security & Access: For login issues post-password update, instruct the user to re-enroll in MFA. For security vulnerabilities, escalate to Tier-3 Security Operations immediately. Do not share vulnerability details in the email; provide a link to the 'Secure Communication Portal' instead."
    },
    {
        "category": "Product & UI",
        "content": "SOP for UI & Features: For dashboard layout issues, frozen UI, or search bugs, suggest a hard refresh (Ctrl+F5) or using the '/legacy-view' URL. For feature requests (e.g., Google Sheets integration), acknowledge the request and confirm it has been added to the high-priority Product Backlog."
    },
    {
        "category": "Data Operations",
        "content": "SOP for Data & Integrations: For data corruption or migration issues, notify the user that hourly Point-in-Time Recovery (PITR) is available to restore their state. For integration failures (Salesforce/Slack), advise the user to disconnect and re-authenticate their OAuth token in the Settings menu."
    }
]

# 3. Connect and Seed
try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "sentinel_operational"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()
    register_vector(conn)

    print("Embedding and seeding knowledge...")
    for item in knowledge_base_data:
        # 4. Generate Embedding using the new SDK syntax
        # We set output_dimensionality=768 to match our SQL column
        response = client.models.embed_content(
            model='gemini-embedding-001',
            contents=item['content'],
            config=types.EmbedContentConfig(
                task_type='RETRIEVAL_DOCUMENT',
                output_dimensionality=768
            )
        )
        
        # Access the vector from the new response object
        embedding = response.embeddings[0].values
        
        cur.execute(
            "INSERT INTO knowledge_base (category, content, embedding) VALUES (%s, %s, %s)",
            (item['category'], item['content'], embedding)
        )

    conn.commit()
    print("Success! Brain is populated with 768-dim Matryoshka embeddings.")

except Exception as e:
    print(f"Error: {e}")
finally:
    if conn:
        cur.close()
        conn.close()