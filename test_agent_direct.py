import os
from dotenv import load_dotenv
load_dotenv('.env')

from models.multi_agent import AgentDebateEngine
import logging
logging.basicConfig(level=logging.DEBUG)

api_key = os.getenv('GEMINI_API_KEY')

engine = AgentDebateEngine(api_key=api_key)
res = engine.run_debate("2330", {"1W": 0.05})
print("Result:")
for k, v in res.items():
    print(f"{k}: {v}")
