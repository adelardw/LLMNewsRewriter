import asyncio
import base64
import datetime as dt
import typing as tp
from collections import deque

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, ReplyKeyboardRemove, BufferedInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from src.tgbot.cache import cache_db
from src.agents.async_source_agent_graph import async_graph
from src.tgbot.bot_schemas import BotStates
from src.tgbot.utils import (HFLCSSimTexts,
                             is_junk_post_regex,
                            find_tg_channels_by_link, find_tg_channels, find_dublicates, find_ads,
                            find_on_banned_org, clean_text, prepare_messages)

from src.tools.telegram_web_search import get_channel_posts
from src.config import tgc_search_kwargs, news_word_threshold, TIMEZONE, CHANNEL_ID, ADMIN_ID, API_TOKEN, CHANNELS_IDS


embedder = HFLCSSimTexts()
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

TARGET_CHANNELS_CACHE = {}



async def send_post_to_channel(bot: Bot, channel_id: int | str, post_text: str, image_link: tp.Optional[str]):
    """
    Функция отправки поста в КОНКРЕТНЫЙ (channel_id) канал.
    """
    try:
        message_chunks, need_photo_to_msg_chunk = prepare_messages(post_text)

        is_valid_url = False
        is_data_uri = False
        
        if image_link:
            if image_link.startswith(('http://', 'https://')):
                is_valid_url = True
            elif image_link.startswith('data:image/'):
                is_data_uri = True

        for i, chunk in enumerate(message_chunks):
            if i == 0:
                if is_valid_url and need_photo_to_msg_chunk:
                    try:
                        await bot.send_photo(chat_id=channel_id, photo=image_link, caption=chunk)
                    except Exception as e:
                        logger.error(f"Не удалось отправить фото по URL: {e}. Отправка текстом.")
                        await bot.send_message(chat_id=channel_id, text=chunk)
                
                elif is_data_uri and need_photo_to_msg_chunk:
                    try:
                        header, encoded_data = image_link.split(',', 1)
                        mime_type = header.split(';')[0].split('/')[-1] 
                        image_bytes = base64.b64decode(encoded_data)
                        buffered_file = BufferedInputFile(image_bytes, filename=f"image.{mime_type}")
                        await bot.send_photo(chat_id=channel_id, photo=buffered_file, caption=chunk)
                    except Exception as e:
                        logger.error(f"Не удалось отправить Data URI: {e}. Отправка текстом.")
                        await bot.send_message(chat_id=channel_id, text=chunk)
                else:
                    await bot.send_message(chat_id=channel_id, text=chunk)    
            else:        
                await bot.send_message(chat_id=channel_id, text=chunk)
    except Exception as e:
        logger.critical(f"Ошибка при отправке поста в канал {channel_id}: {e}")

async def auto_send_posts(bot: Bot, target_channel_id: int | str, storage: BaseStorage, user_id: int):
    """
    Автоматически отправляет посты в УКАЗАННЫЙ канал.
    Берет данные из хранилища, привязанного к этому каналу.
    """
    state_key = StorageKey(bot_id=bot.id, user_id=user_id, chat_id=target_channel_id)
    state = FSMContext(storage=storage, key=state_key)
    
    data = await state.get_data()
    generated_posts = data.get('generated_posts', deque())
    images_links = data.get('images_links', deque())
    
    if generated_posts:
        
        for post, image_link in zip(generated_posts, images_links):
            await send_post_to_channel(bot, target_channel_id, post, image_link)
            await asyncio.sleep(64)
        

        await state.update_data(generated_posts=deque(), images_links=deque())

async def post_generation(channel_name: str, config: dict):
    results = []
    images_links = []
    try:
        last_posts = get_channel_posts(channel_name, k=tgc_search_kwargs['max_post_per_channel'])
    except Exception as e:
        logger.error(f"Ошибка при поиске постов в {channel_name}: {e}")
        return [], []

    for i, posts in enumerate(last_posts):
        logger.info(f'Select Post {i}')
        is_ads = posts.get('is_ads', False)
        url = posts.get('post_url', '')
        
        if cache_db.get(f'post_{url}'):
            logger.info(f'[SKIP]: in cache')
            continue
            
        if not is_ads:
            post = posts.get('text', None)
            if not isinstance(post, str):
                logger.info('[NOTSTR TAG]')
                continue
        
            if is_junk_post_regex(post):
                logger.info('[JUNKPOST TAG]')
                continue

            post = post if post and len(post.split()) >= news_word_threshold else None
            emoji_reactions = posts.get('reactions', {})
            is_video = posts.get('is_video', False)
            media_links = posts.get('media_links', [])

            if post:
                dublcate_cond = find_dublicates(embedder, cache_db, post, 0.7)
                ads_cond = find_ads(post)
                if not dublcate_cond and not ads_cond:
                    if not is_video:
                        forbidden = find_on_banned_org(post)
                        add_message = f"\n СПИСКИ НАЙДЕННЫХ ИНОАГЕНТОВ ИЛИ ЭКСТРЕМИСТОВ В ПОСТУ (ОБЯЗАТЕЛЬНО УПОМЯНУТЬ О НИХ И ИХ СТАТУСЕ): \n {forbidden} \n " \
                                  if forbidden else ''

                        result = await async_graph.ainvoke({
                            'post': post + add_message,
                            'emoji_reactions': emoji_reactions,
                            'is_selected_channels': True,
                            'media_links': media_links
                        }, config=config)

                        if result.get('generation'):
                            if is_junk_post_regex(result['generation']):
                                logger.info('[JUNKGENERATION TAG]')
                                continue
                            logger.info(f'[SUCESSES TAG]')
                            results.append(clean_text(result['generation']))
                            images_links.append(result.get('image_url'))

                        cache_db.set(f'post_{url}', post, ex=24 * 60 * 60)
                    else:
                        logger.info('[VIDEO TAG]')
                else:
                    if ads_cond:
                        logger.info('[ADS TAG]')
                    
                    if dublcate_cond:
                        logger.info('[DUBLICATE TAG]')
        
    return results, images_links



async def channel_look_up(source_channels: list, config: dict,
                          storage: BaseStorage, bot: Bot,
                          user_id: int | str, target_channel_id: int | str):
    
    '''
    Задача, которая запускается по расписанию для КОНКРЕТНОГО целевого канала (target_channel_id).
    Берет посты из source_channels, генерирует и публикует в target_channel_id.
    '''
    logger.info(f"Запуск задачи для канала ID: {target_channel_id}. Источники: {source_channels}")
    results = []
    images_links = []
    
    for chan in source_channels:
        gen_posts, links = await post_generation(chan, config)
        results.extend(gen_posts)
        images_links.extend(links)

    if results:
        logger.info(f'Найдены новые посты ({len(results)}) для канала {target_channel_id}')
        
        state_key = StorageKey(bot_id=bot.id, user_id=user_id, chat_id=target_channel_id)
        state = FSMContext(storage=storage, key=state_key)
        
        data = await state.get_data()
        current_posts = data.get('generated_posts', deque())
        current_links = data.get('images_links', deque())
        
        current_posts.extend(results)
        current_links.extend(images_links)
        
        await state.update_data(generated_posts=current_posts)
        await state.update_data(images_links=current_links)
        

        await auto_send_posts(bot, target_channel_id, storage, user_id)



@router.message(CommandStart())
@router.message(Command('menu'))
async def cmd_menu(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    builder = ReplyKeyboardBuilder()
    
    if str(user_id) == str(ADMIN_ID):
        builder.row(KeyboardButton(text="🤔 Выбрать каналы для запуска агента"))

        await message.answer(
        "Выберите действие:",
        reply_markup=builder.as_markup(resize_keyboard=True))

@router.message(F.text == '🤔 Выбрать каналы для запуска агента')
async def choice_channels(message: types.Message, state: FSMContext, bot: Bot):
    """
    Шаг 1: Показываем пользователю список его целевых каналов (из конфига CHANNELS_IDS).
    """
    await state.set_state(BotStates.set_channel)
    builder = ReplyKeyboardBuilder()
    
    for chat_id in CHANNELS_IDS:
        try:
            chat_info = await bot.get_chat(chat_id=chat_id)
            title = chat_info.title
            TARGET_CHANNELS_CACHE[title] = chat_id
            builder.row(KeyboardButton(text=title))
        except Exception as e:
            logger.error(f"Не могу получить инфо о канале {chat_id}: {e}")
            builder.row(KeyboardButton(text=f"ID: {chat_id}"))
            TARGET_CHANNELS_CACHE[f"ID: {chat_id}"] = chat_id

    builder.row(KeyboardButton(text="🔙 Назад в меню"))
    
    await message.answer(
        "Выберите ВАШ канал, для которого будем настраивать автопостинг:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(BotStates.set_channel)
async def target_channel_selected_handler(message: types.Message, state: FSMContext):
    """
    Шаг 2: Пользователь выбрал свой канал. Запоминаем ID и просим источники.
    """
    text = message.text
    
    if text == "🔙 Назад в меню":
        await cmd_menu(message, state)
        return

    target_channel_id = TARGET_CHANNELS_CACHE.get(text)
    
    if not target_channel_id:
        await message.answer("Не удалось определить ID канала. Пожалуйста, нажмите на кнопку еще раз или вернитесь в меню.")
        return

    await state.update_data(target_channel_id=target_channel_id)
    
    await state.set_state(BotStates.auto_rewrite_follow_channel_post)
    await message.answer(
        f"✅ Выбран канал для публикации: <b>{text}</b>\n\n"
        "Теперь отправьте список каналов-доноров (откуда брать новости).\n"
        "Формат:\n"
        "@channel1, @channel2\n"
        "Или ссылки: https://t.me/...",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )

@router.message(BotStates.auto_rewrite_follow_channel_post)
async def set_sources_and_start_scheduler(message: types.Message, state: FSMContext, 
                                          storage: BaseStorage, bot: Bot,
                                          scheduler: AsyncIOScheduler):
    """
    Шаг 3: Получаем источники, запускаем ПЕРСОНАЛЬНЫЙ шедулер для этого канала.
    """
    user_id = message.from_user.id
    data = await state.get_data()
    target_channel_id = data.get('target_channel_id')
    
    if not target_channel_id:
        await message.answer("Ошибка состояния. Начните сначала.")
        await cmd_menu(message, state)
        return

    text = message.text
    channel_by_link = find_tg_channels_by_link(text)
    channels_by_endpoints = find_tg_channels(text)
    source_channels_result = list(set(channel_by_link + channels_by_endpoints))

    if source_channels_result:
        job_id = f"channel_lookup_{target_channel_id}"
        
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            await message.answer(f"⚙️ Старая задача для этого канала удалена. Создаю новую...")

        config = {"configurable": {"thread_id": user_id}}
        
        # Добавляем задачу
        scheduler.add_job(
            channel_look_up,
            trigger='interval',
            minutes=5,
            id=job_id,
            next_run_time=dt.datetime.now() + dt.timedelta(seconds=5),
            kwargs={
                'source_channels': source_channels_result,
                'config': config,
                'bot': bot,
                'user_id': user_id,
                'target_channel_id': target_channel_id,
                'storage': storage
            }
        )
        
        await message.answer(
            f"🚀 <b>Запущено!</b>\n\n"
            f"Целевой канал ID: <code>{target_channel_id}</code>\n"
            f"Источники: {', '.join(source_channels_result)}\n\n"
            "Теперь вы можете вернуться в меню и настроить другой канал.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        
        await cmd_menu(message, state)
        
    else:
        await message.answer(
            "❌ Не смог найти ссылки на каналы. Пожалуйста, отправьте их в формате @name или ссылки.",
            reply_markup=ReplyKeyboardRemove()
        )

async def main():
    logger.info('StartApp')
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.start()
    await dp.start_polling(bot, scheduler=scheduler, storage=storage)

#if __name__ == "__main__":
#    asyncio.run(main())