import asyncio
#from tgbot.legacy_tgbot import main
from src.tgbot.tg_bot import main


if __name__ == '__main__':
    asyncio.run(main())