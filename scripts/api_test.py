import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("🚀 Testing the cheapest model: gemini-2.5-flash-lite")

try:
    response = client.models.generate_content(
        model='gemini-2.5-flash-lite', 
        contents='Confirm system status.'
    )
    print(f"✅ SUCCESS! Response: {response.text}")
except Exception as e:
    print(f"❌ FAILED: {e}")