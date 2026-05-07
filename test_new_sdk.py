import os
from dotenv import load_dotenv
load_dotenv('.env')

from google import genai
api_key = os.getenv('GEMINI_API_KEY')
print("API Key Prefix:", api_key[:5])

client = genai.Client(api_key=api_key)

try:
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents='Tell me a story in 10 words.'
    )
    print(response.text)
except Exception as e:
    print("ERROR gemini-1.5-flash:", e)

try:
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents='Tell me a story in 10 words.'
    )
    print("gemini-2.0-flash SUCCESS:", response.text)
except Exception as e:
    print("ERROR gemini-2.0-flash:", e)
    
try:
    response = client.models.generate_content(
        model='gemini-pro',
        contents='Tell me a story in 10 words.'
    )
    print(response.text)
except Exception as e:
    print("ERROR gemini-pro:", e)
