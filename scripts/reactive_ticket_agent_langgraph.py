import os 
from typing import TypedDict, Dict, Any
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END, START
from pgvector.psycopg2 import register_vector
import psycopg2
from google import genai
from google.genai import types
import requests

load_dotenv()

# Make sure you use the SAME name here and in the print statement
API_KEY = os.getenv("GOOGLE_API_KEY") 
client = genai.Client(api_key = API_KEY)

# Fix line 16 to use 'api_key' instead of 'API_KEY'
if API_KEY:
    print(f"DEBUG: Key starts with {API_KEY[:5]} and has length {len(API_KEY)}")
else:
    raise ValueError("CRITICAL: GOOGLE_API_KEY not found in .env file.")

# --- CHAPTER 1: Blueprint of state ---
class AgentState(TypedDict):
    account_id: str
    mrr: float
    complaint: str
    category: str
    expert_policy: str
    recovery_strategy: str
    draft_email: str

# --- CHAPTER 2: The Agent Brain ---
class RevenueRecoveryAgent:
    def __init__(self):
        print("DEBUG: Initializing RevenueRecoveryAgent...")
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=API_KEY,
            temperature=0.7
        )
        print("DEBUG: Connecting to PostgreSQL database...")
        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            dbname=os.getenv("DB_NAME", "sentinel_operational"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        register_vector(self.conn)
        print("DEBUG: Building agent workflow graph...")
        self.workflow = self._build_graph()

    def _retriever_node(self, state: AgentState):
        print(f"DEBUG: Retriever node input state: {state}")
        with self.conn.cursor() as cur:
            response = client.models.embed_content(
                model='gemini-embedding-001',
                contents=state['complaint'],
                config=types.EmbedContentConfig(task_type='RETRIEVAL_QUERY', output_dimensionality=768)
            )
            query_vector = response.embeddings[0].values
            print(f"DEBUG: Query vector generated: {query_vector[:5]}...")
            cur.execute("""
                SELECT content FROM knowledge_base 
                ORDER BY embedding <=> %s::vector 
                LIMIT 1;
            """, (query_vector,))
            result = cur.fetchone()
            print(f"DEBUG: Retriever DB result: {result}")
            if result is None:
                return {"expert_policy": "No specific policy found. Use general best practices."}
            else:
                return {"expert_policy": result[0]}

    def _strategy_node(self, state: AgentState):
        print(f"DEBUG: Strategy node input state: {state}")
        mrr = state.get('mrr', 0)
        policy = state.get('expert_policy', "")
        # Aligning with your 10k threshold from PySpark
        if mrr >= 15000:
            tier = "ULTRA-VIP: Executive Outreach. Immediate 30-min Zoom invite."
        elif mrr >= 10000:
            tier = "VIP Concierge: Priority response within 1 hour."
        else:
            # This handles cases if you ever lower your PySpark threshold later
            tier = "Growth Account: Standard 4-hour recovery protocol."
        strategy = f"{tier} Follow this specific protocol: {policy}"
        print(f"DEBUG: Computed recovery strategy: {strategy}")
        return {"recovery_strategy": strategy}

    def _drafter_node(self, state: AgentState):
        prompt = f"""
        Role: Senior Customer Success Manager at Sentinel-Flow writing to a B2B enterprise client.
        Account: {state['account_id']}
        Issue Type: {state['category']}
        Customer Complaint: {state['complaint']}
        Official Resolution Policy: {state['expert_policy']} 
        Business Strategy: {state['recovery_strategy']}

        Task: Write a professional recovery email.

        Rules:
        - Start directly with 'Hi [Account] Team,' — no preamble or intro line
        - Maximum 100 words
        - Open by acknowledging the specific complaint directly
        - Provide the resolution steps from the policy clearly and concisely
        - End with one concrete next step — offer a call only for Technical or Integration issues, not for Feature Requests
        - Never use placeholders like [Date], [Time], [Your Name]
        - Never mention internal tier labels like ULTRA-VIP or VIP Concierge
        - Address as 'Hi {state['account_id']} Team'
        - Sign off as: Maha, Customer Success Lead, Sentinel-Flow
        - Tone: Direct, empathetic, solution-focused
        """
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3", "prompt": prompt, "stream": False},
            timeout=60
        )
        raw = response.json()['response'].strip()

        # Strip preamble
        lines = raw.split('\n')
        clean_lines = []
        started = False
        for line in lines:
            if line.strip().lower().startswith('hi '):
                started = True
            if started:
                clean_lines.append(line)

        draft = '\n'.join(clean_lines).strip() if clean_lines else raw
        return {"draft_email": draft}

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("retrieve", self._retriever_node)
        graph.add_node("strategize", self._strategy_node)
        graph.add_node("draft", self._drafter_node)

        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "strategize")
        graph.add_edge("strategize", "draft")
        graph.add_edge("draft", END)
        return graph.compile()
    
    def run(self, data: Dict[str,Any]):
        print(f"DEBUG: Running agent workflow with data: {data}")
        result = self.workflow.invoke(data)
        print(f"DEBUG: Agent workflow result: {result}")
        return result
    
    def close(self):
        print("DEBUG: Closing database connection...")
        if self.conn and not self.conn.closed:
            self.conn.close()
            print("Database connection closed.")
