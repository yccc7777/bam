import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv('.env')
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')
try:
    print(model.generate_content("hello").text)
except Exception as e:
    print("ERROR:", e)
