import json
import time
import random
from datetime import datetime
from faker import Faker
from confluent_kafka import Producer

fake = Faker()

# Configuration for Redpanda
conf = {'bootstrap.servers': "localhost:9092"}
producer = Producer(conf)

# Load Ground Truth Friction Library
with open('data_factory/friction_library.json', 'r') as f:
    friction_events = json.load(f)

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")

# --- STATIC ACCOUNT REGISTRY ---
CUSTOMERS = []
for _ in range(50):
    company_name = fake.company()
    CUSTOMERS.append({
        "account_id": company_name,
        "email": f"contact@{company_name.lower().replace(' ', '').replace(',', '')}.com",
        "mrr": random.choice([500, 1200, 5000, 10000, 25000]) # Added high-tier MRR
    })

def send_to_redpanda(payload):
    producer.produce('sentinel.raw.events', json.dumps(payload).encode('utf-8'), callback=delivery_report)
    producer.poll(0)
    print(f"Sent: {payload['event_type']} | Account: {payload['account_id']} | Type: {payload.get('alert_trigger', 'Random')}")

# --- PROACTIVE SCENARIO GENERATORS ---

def trigger_friction_loop():
    """Simulates a customer submitting 4 tickets in rapid succession (The Friction Loop)"""
    customer = random.choice(CUSTOMERS)
    friction = random.choice(friction_events)
    print(f"🔥 TRIGGERING FRICTION LOOP: {customer['account_id']}")
    
    for _ in range(4):
        payload = {
            "event_id": fake.uuid4(),
            "user_id": fake.uuid4(),
            "account_id": customer["account_id"],
            "email": customer["email"],
            "mrr": customer["mrr"],
            "event_type": "support_ticket",
            "category": friction['category'],
            "event_body": f"REPEAT ISSUE: {friction['support_text']}",
            "csat_score": 1,
            "timestamp": int(time.time()),
            "alert_trigger": "FRICTION_LOOP"
        }
        send_to_redpanda(payload)
        time.sleep(1) # Fast bursts

def trigger_dead_end_login():
    """Simulates 6 logins with ZERO feature access (The Silent Churn)"""
    customer = random.choice(CUSTOMERS)
    print(f"💀 TRIGGERING DEAD-END LOGIN: {customer['account_id']}")
    
    for _ in range(6):
        payload = {
            "event_id": fake.uuid4(),
            "user_id": fake.uuid4(),
            "account_id": customer["account_id"],
            "email": customer["email"],
            "mrr": customer["mrr"],
            "event_type": "login",
            "category": "N/A",
            "event_body": "User logged in but is stuck on dashboard",
            "csat_score": 3,
            "timestamp": int(time.time()),
            "alert_trigger": "DEAD_END_LOGIN"
        }
        send_to_redpanda(payload)
        time.sleep(1)

def generate_random_event():
    customer = random.choice(CUSTOMERS)
    is_friction = random.random() < 0.05 
    
    if is_friction:
        friction = random.choice(friction_events)
        event_type = "support_ticket"
        content = friction['support_text']
        category = friction['category']
        csat = friction['suggested_csat']
    else:
        event_type = random.choice(["login", "feature_access", "dashboard_view"])
        content = "Normal user activity"
        category = "N/A"
        csat = random.choice([4, 5])

    return {
        "event_id": fake.uuid4(),
        "user_id": fake.uuid4(),
        "account_id": customer["account_id"],
        "email": customer["email"],
        "mrr": customer["mrr"],
        "event_type": event_type,
        "category": category,
        "event_body": content,
        "csat_score": csat,
        "timestamp": int(time.time())
    }

# --- MAIN LOOP ---
print("Sentinel-Flow Generator active. Monitoring for Proactive Scenarios...")

try:
    while True:
        dice_roll = random.random()
        
        if dice_roll < 0.03:
            trigger_friction_loop()
        elif dice_roll < 0.06:
            trigger_dead_end_login()    
        else:
            event = generate_random_event()
            send_to_redpanda(event)
        
        time.sleep(random.uniform(2, 4))
except KeyboardInterrupt:
    print("Generator stopped.")
finally:
    producer.flush()