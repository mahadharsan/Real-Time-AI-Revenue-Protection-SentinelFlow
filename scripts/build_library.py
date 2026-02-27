import ollama
import json
import os

def generate_friction_library():
    # The Prompt defines the 'Business Logic' for the AI
    prompt = """
    Generate 30 unique B2B SaaS support tickets as a JSON array.
    Each object must have:
    1. 'category': (e.g., 'API Latency', 'Billing Error', 'UI Bug')
    2. 'support_text': A realistic, frustrated message from a developer or admin.
    3. 'suggested_csat': An integer (1 or 2) that matches the frustration level.
    
    Format the output as a raw JSON list only.
    """
    
    print("Ollama is crafting the 'High-Friction' dataset...")
    
    # Calling your local Ollama instance
    response = ollama.generate(model='llama3', prompt=prompt)
    
    # We clean the response to ensure it's valid JSON
    raw_content = response['response'].strip()
    
    try:
        # Create the data_factory directory if it doesn't exist
        os.makedirs("data_factory", exist_ok=True)
        
        # Save to file for use in our Redpanda Generator
        with open("data_factory/friction_library.json", "w") as f:
            f.write(raw_content)
        print("Success: friction_library.json created in /data_factory")
    except Exception as e:
        print(f"Error saving library: {e}")

if __name__ == "__main__":
    generate_friction_library()