import psycopg2
import time
import requests

def safe_generate_ollama(prompt):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3", 
        "prompt": prompt,
        "stream": False
    }
    try:
        print(f"  → Ollama: Input: {prompt[:60]}...") 
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        raw = response.json()['response'].strip()
        
        # Strip preamble lines like "Here is the email:", "Here is an email that..."
        lines = raw.split('\n')
        clean_lines = []
        started = False
        for line in lines:
            if line.strip().lower().startswith('hi '):
                started = True
            if started:
                clean_lines.append(line)
        
        return '\n'.join(clean_lines).strip() if clean_lines else raw
        
    except Exception as e:
        print(f"  ❌ Ollama Error: {str(e)[:50]}")
        return ""

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        dbname="sentinel_operational",
        user="maha_admin",
        password="sentinel_pass"
    )

def process_proactive_alerts():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # --- PART A: Friction Loops ---
    cur.execute("""
        SELECT DISTINCT ON (account_id, category) 
            account_id, category, window_start, incident_count, event_summary 
        FROM friction_loops 
        WHERE ai_draft IS NULL OR ai_draft = ''
        ORDER BY account_id, category, window_start ASC
    """)
    loops = cur.fetchall()
    
    if loops:
        print(f"\n[SYSTEMIC] Found {len(loops)} loops. Processing...")
        for acc, cat, w_start, count, summary in loops:
            prompt = (
                f"You are a Senior Customer Success Manager at Sentinel-Flow writing to a B2B enterprise client.\n"
                f"Situation: Account '{acc}' has reported {count} separate '{cat}' issues within a short window.\n"
                f"Last reported issue: {summary}\n"
                f"Task: Write a professional 80-word escalation email.\n"
                f"Rules:\n"
                f"- Start directly with 'Hi [Account] Team,' — no preamble or intro line\n"
                f"- Do not give intro like here is the email. Directly give the final version of the email"
                f"- Open with a sincere apology acknowledging the repeated friction\n"
                f"- State that you have personally escalated this to the engineering team\n"
                f"- Offer a dedicated 30-minute call to resolve this together\n"
                f"- Sign off as 'Maha, Customer Success Lead, Sentinel-Flow'\n"
                f"- Never use placeholders like [Your Name] or [Date]\n"
                f"- End with a direct offer, not a question about whether they want help\n"
                f"- Tone: Professional, accountable, solution-focused"
            )
            
            draft_text = safe_generate_ollama(prompt)
            
            if draft_text:
                cur.execute("""
                    UPDATE friction_loops SET ai_draft = %s 
                    WHERE account_id = %s AND category = %s AND window_start = %s
                """, (draft_text, acc, cat, w_start))
                conn.commit()
                # Debug: Clean output with only first 40 chars
                print(f"  ✅ {acc[:15]:<15} | Draft: {draft_text[:40].strip()}...")
    
    # --- PART B: Silent Churners ---
    cur.execute("""
        SELECT DISTINCT ON (account_id) 
            account_id, window_start, login_count 
        FROM silent_churners 
        WHERE ai_draft IS NULL OR ai_draft = ''
        ORDER BY account_id, window_start ASC
    """)
    churners = cur.fetchall()
    
    if churners:
        print(f"\n[BEHAVIORAL] Found {len(churners)} churn risks. Processing...")
        for acc, w_start, logins in churners:
            prompt = (
                f"You are a Product Adoption Specialist at Sentinel-Flow writing to a B2B enterprise client.\n"
                f"Situation: Account '{acc}' has logged in {logins} times recently but has not used any core features.\n"
                f"Task: Write a warm, helpful 70-word re-engagement email.\n"
                f"Rules:\n"
                f"- Start directly with 'Hi [Account] Team,' — no preamble or intro line\n"
                f"- Do not give intro like here is the email. Directly give the final version of the email"
                f"- Open with an observation like 'I noticed your team has been checking in but may not have found what they need yet'\n"
                f"- Do NOT say 'unused logins' or make it sound like a sales pitch\n"
                f"- Offer a specific 15-minute onboarding call to help them find value\n"
                f"- Sign off as 'Maha, Customer Success Lead, Sentinel-Flow'\n"
                f"- Never use placeholders like [Your Name]\n"
                f"- Tone: Warm, observational, helpful — not pushy"
            )
            
            draft_text = safe_generate_ollama(prompt)
            
            if draft_text:
                cur.execute("""
                    UPDATE silent_churners SET ai_draft = %s 
                    WHERE account_id = %s AND window_start = %s
                """, (draft_text, acc, w_start))
                conn.commit()
                # Debug: Clean output
                print(f"  ✅ {acc[:15]:<15} | Draft: {draft_text[:40].strip()}...")

    cur.close()
    conn.close()

if __name__ == "__main__":
    print("🛡️  Sentinel Proactive Agent (Ollama Mode) Active")
    print("   Monitoring database for new proactive triggers...")
    
    while True:
        try:
            # Simple heartbeat so you know it's alive without flooding the screen
            process_proactive_alerts()
        except Exception as e:
            print(f"  ❌ Loop Error: {e}")
        
        time.sleep(5)