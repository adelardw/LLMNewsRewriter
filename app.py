import asyncio
#from tgbot.legacy_tgbot import main
from src.tgbot.tg_bot import multimain


if __name__ == '__main__':
    asyncio.run(multimain())