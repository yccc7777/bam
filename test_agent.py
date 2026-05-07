import os
from dotenv import load_dotenv
load_dotenv('.env')

from models.multi_agent import AgentDebateEngine
import logging
logging.basicConfig(level=logging.DEBUG)

api_key = os.getenv('GEMINI_API_KEY')
print(f"API KEY prefix: {api_key[:5] if api_key else 'None'}")

try:
    engine = AgentDebateEngine(api_key=api_key)
    res = engine.run_debate("2330", {"1W": 0.05})
    print(res)
except Exception as e:
    import traceback
    traceback.print_exc()
