import psycopg2
import os
from psycopg2.extras import RealDictCursor
import time
import random  # Added for jitter
from reactive_ticket_agent_langgraph import RevenueRecoveryAgent 

# Database Connection
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "sentinel_operational"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT", "5432")
)

def fetch_pending_alerts():
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT ON (account_id) * 
            FROM high_priority_alerts 
            WHERE is_approved = FALSE AND (ai_draft IS NULL OR ai_draft = '')
            ORDER BY account_id, timestamp ASC
            LIMIT 1;
        """)
        return cur.fetchall()

def run_agent_with_retry(agent, state_input, max_retries=3):
    """Gives Gemini breathing room with exponential backoff"""
    retry_delay = 30  # Start with 30s for 429 errors
    for attempt in range(max_retries):
        try:
            return agent.run(state_input)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait_time = retry_delay * (2 ** attempt) + random.uniform(1, 5)
                print(f"⚠️ Rate limited! Attempt {attempt+1}/{max_retries}. Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
            else:
                raise e
    return None

def process_alerts():
    agent = RevenueRecoveryAgent()
    try:
        while True:
            alerts = fetch_pending_alerts()
            if not alerts:
                print("No pending alerts. Deep sleep 30s...")
                time.sleep(30)
                continue
            
            print(f"DEBUG: Processing batch of {len(alerts)} alerts...")

            for alert in alerts:
                state_input = {
                    "account_id": alert['account_id'],
                    "mrr": float(alert['mrr']),
                    "complaint": alert['event_body'],
                    "category" : alert['category']
                }

                # Use the retry logic
                result = run_agent_with_retry(agent, state_input)
                
                if result:
                    draft = result.get("draft_email", "No draft generated.")
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE high_priority_alerts 
                            SET ai_draft = %s 
                            WHERE event_id = %s
                        """, (draft, alert['event_id']))
                    conn.commit()
                    print(f"✅ Draft saved for {alert['account_id']}")
                
                # Small mandatory gap between successful calls
                time.sleep(10) 

    except KeyboardInterrupt:
        print("Manual stop detected.")
    finally:
        conn.close()
        agent.close()

if __name__ == "__main__":
    process_alerts()