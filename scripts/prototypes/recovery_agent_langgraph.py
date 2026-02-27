import os 
from typing import TypedDict, Dict, Any
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END, START

import os
from dotenv import load_dotenv

load_dotenv()

# Make sure you use the SAME name here and in the print statement
API_KEY = os.getenv("GOOGLE_API_KEY") 

# Fix line 16 to use 'api_key' instead of 'API_KEY'
if API_KEY:
    print(f"DEBUG: Key starts with {API_KEY[:5]} and has length {len(API_KEY)}")
else:
    raise ValueError("CRITICAL: GOOGLE_API_KEY not found in .env file.")

#create shared memory for langgraph
"""
We have 8-10 data points per event 
But only 3 raw points (account_id, mrr, complaint) chosen as the Input.
We created: 3 new slots (category, recovery_strategy, draft_email) for the Output.
"""
# --- CHAPTER 1: Blueprint of state ---
class AgentState(TypedDict):
    account_id: str
    mrr: float
    complaint: str
    category: str
    recovery_strategy: str
    draft_email: str

# --- CHAPTER 2: The Agent Brain ---
class RevenueRecoveryAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model = "gemini-2.5-flash",
            google_api_key = API_KEY,
            temperature = 0.7
        )

        # Build the graph once at startup for efficiency
        self.workflow = self._build_graph()

    # NODE 1: The Analyzer
    def _analyzer_node(self, state: AgentState):
        prompt = f"Categorize this customer complaint: {state['complaint']}. Return ONLY one word: 'Technical', 'Billing', or 'Missing Feature'."
        response = self.llm.invoke(prompt)
        return {"category":response.content.strip()}
    
    #NODE 2: The Strategist
    #keeping business rules (like money thresholds) out of the AI's hands when possible
    def _strategy_node(self,state: AgentState) -> Dict [str,Any]:
        """Decides the recovery offer based on the customer's value (MRR)."""
        # 1. Retrieve the MRR from our shared whiteboard
        # We use .get() with a default of 0 to prevent crashes if MRR is missing
        mrr = state.get('mrr', 0)

        # 2. Apply business rules
        if mrr > 5000:
            strategy = "High-Priority: Offer 1-on-1 Product Lead call + 20% loyalty discount."
        else:
            strategy = "Standard: Offer 1 month free credit + technical guide."
            
        # 3. Return the decision to be added to the whiteboard
        return {"recovery_strategy": strategy}
    
    # NODE 3: The Drafte
    def _drafter_node(self, state: AgentState) -> Dict[str, any]:
        """Uses Gemini to write the final email based on the strategy chosen."""
        category = state.get('category')
        strategy = state.get('recovery_strategy')
        account_id = state.get('account_id')

        prompt = f"""
        Role: Senior Customer Success Manager at Sentinel-Flow.
        Context: Account {account_id} is experiencing a {category} issue.
        Strategy: {strategy}
        
        Task: Write a short, empathetic but formal recovery email to the client.
        Constraint: Keep it under 80 words.Always address the customer by their account_id 
        if a specific name is missing, and never use placeholders 
        like [Your Name]—sign it as 'Maha, Sentinel-Flow Lead'"""

        response = self.llm.invoke(prompt)
        return {"draft_email": response.content.strip()}
    
    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("analyze",self._analyzer_node)
        graph.add_node("strategize", self._strategy_node)
        graph.add_node('draft', self._drafter_node)

        graph.add_edge(START,"analyze")
        graph.add_edge("analyze","strategize")
        graph.add_edge("strategize", "draft")
        graph.add_edge("draft", END)

        return graph.compile()
    
    def run(self, data: Dict[str,Any]):
        return self.workflow.invoke(data)

    # --- LOCAL TESTING ---
if __name__ == "__main__":
    agent = RevenueRecoveryAgent()
    sample_risk = {
        "account_id": "Alpha_Tech_Ltd",
        "mrr": 12000.0,
        "complaint": "The API is returning 500 errors consistently during bulk uploads."
    }

    print("--- Sentinel-Flow: Executing Recovery Agent ---")
    result = agent.run(sample_risk)

    print(f"\n[DECISION]: Category: {result['category']} | Strategy: {result['recovery_strategy']}")
    print(f"\n[DRAFT EMAIL]:\n{result['draft_email']}")