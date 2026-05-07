import argparse
import asyncio
import logging
from telegram import Bot

from config.settings import TELEGRAM_BOT_TOKEN
from main import send_premarket_report, send_postmarket_review

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DummyContext:
    def __init__(self, bot):
        self.bot = bot

async def main():
    parser = argparse.ArgumentParser(description="Run daily AI investment reports via GitHub Actions")
    parser.add_argument("--task", type=str, required=True, choices=["premarket", "postmarket"], help="Which task to run")
    args = parser.parse_args()

    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token":
        logger.error("TELEGRAM_BOT_TOKEN is missing!")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    context = DummyContext(bot=bot)

    if args.task == "premarket":
        logger.info("Executing Premarket AI Analysis...")
        await send_premarket_report(context)
        logger.info("Premarket report completed.")
    elif args.task == "postmarket":
        logger.info("Executing Postmarket AI Review...")
        await send_postmarket_review(context)
        logger.info("Postmarket review completed.")

if __name__ == "__main__":
    asyncio.run(main())
