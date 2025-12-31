from redis import StrictRedis
import numpy as np
import os
import pytz
from src.open_router import OpenRouterEmbeddings
import datetime as dt
import typing as tp
import random
import re
import requests
from bs4 import BeautifulSoup
from loguru import logger
import random

from src.config import user_agents, save_yaml
from src.config import EMBED_MODEL, OPEN_ROUTER_API_KEY


TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_MAX_MESSAGE_CAPTION = 1024

def prepare_messages(post: str):
    long_short_message = split_short_long_message(post)
    results = []
    if long_short_message:
        short, long = long_short_message
        results.append(short)
        if long:
            chunks = split_long_message(long)
            results.extend(chunks)
        return results, True
    else:
        results.append(post)
        return results, False
    
def max_day_in_month(current_year: int, current_month: int):
    '''
    Вычисляетмаксимальное количество дней в данному году и в данном месяце
    '''
    if current_year % 4 == 0 and current_month == 2:
        return 29
    if current_month <=7:
        if current_month == 2:
            return 28
        elif current_month % 2 == 0:
            return 30
        else:
            return 31
    else:
        if current_month % 2 == 0:
            return 31
        else:
            return 30

def find_tg_channels(text):
    pattern = r'@[a-zA-Z0-9_]{5,32}'
    channels = re.findall(pattern, text)
    for i, chan in enumerate(channels):
        channels[i] = chan[1:]
    return channels


def find_tg_channels_by_link(text):
    pattern = r'https://t.me/[a-zA-Z0-9_]{5,32}'
    channels = re.findall(pattern, text)
    for i, chan in enumerate(channels):
        channels[i] = chan.split('/')[-1]
    return channels

def random_next_publication_datetime(month: tp.Optional[int] = None,
                                    weekday: tp.Optional[int] = None):

    '''
    Формирует рандомную дату и время пуликации следующего пост
    '''
    curent_date = dt.datetime.now(pytz.timezone('Europe/Moscow'))
    current_weekday = dt.datetime.isocalendar(curent_date).weekday

    current_year = curent_date.year
    current_month = curent_date.month
    current_day = curent_date.day

    if month:
        assert month <= 12
        delta_publication_month = month - current_month
        delta_publication_month = delta_publication_month if delta_publication_month > 0 else 0
        next_month_publication = current_month + delta_publication_month
        random_publication_month = np.random.randint(current_month, next_month_publication if
                                                   next_month_publication != current_month \
                                                   else current_month + 1)
    else:
        pass
        random_publication_month = current_month

    if weekday:
        assert 1 <= weekday <=7
        delta_weekday = weekday - current_weekday
        delta_weekday = delta_weekday if delta_weekday > 0 else 0

        next_weekday_publication = current_weekday + delta_weekday
        random_publication_day = np.random.randint(current_day, next_weekday_publication if
                                                   next_weekday_publication != current_day \
                                                   else current_day + 1)
    else:
        max_days_in_current_month = max_day_in_month(current_year, current_month)
        random_publication_day = np.random.randint(current_day, max_days_in_current_month + 1)


    random_publication_hour = np.random.randint(0, 24)
    random_publication_minute = np.random.randint(0, 60)

    publication_date = dt.datetime(current_year, random_publication_month, random_publication_day,
                                   random_publication_hour,
                                   random_publication_minute)

    return publication_date.isoformat()


def random_next_publication_in_current_day(num_dates: tp.Optional[int] = None):


    curent_date = dt.datetime.now(pytz.timezone('Europe/Moscow'))

    current_year = curent_date.year
    current_month = curent_date.month
    current_day = curent_date.day
    current_hour = curent_date.hour
    current_minute = curent_date.minute

    possible_times = []

    for minute in range(current_minute + 1, 60):
        possible_times.append((current_hour, minute))

    for hour in range(current_hour + 1, 24):
        for minute in range(60):
            possible_times.append((hour, minute))

    if not possible_times:
        return None

    if not num_dates:

        pub_hour, pub_minute = random.choice(possible_times)

        publication_date = dt.datetime(
            current_year, current_month, current_day,
            pub_hour, pub_minute,
            tzinfo=curent_date.tzinfo
        )
        return publication_date

    else:
        if num_dates > len(possible_times):
            raise ValueError(
                f"Невозможно сгенерировать {num_dates} уникальных дат. "
                f"До конца дня осталось только {len(possible_times)} свободных минут."
            )


        selected_times = random.sample(possible_times, num_dates)


        publication_dates = [
            dt.datetime(
                current_year, current_month, current_day,
                hour, minute,
                tzinfo=curent_date.tzinfo
            ) for hour, minute in selected_times
        ]

        return publication_dates


def random_next_publication_in_current_hour(num_dates: tp.Optional[int] = None):


    curent_date = dt.datetime.now(pytz.timezone('Europe/Moscow'))

    current_year = curent_date.year
    current_month = curent_date.month
    current_day = curent_date.day
    current_hour = curent_date.hour
    current_minute = curent_date.minute

    possible_times = []

    for minute in range(current_minute + 1, 60):
        possible_times.append((current_hour, minute))

    if not possible_times:
        return None

    if not num_dates:

        pub_hour, pub_minute = random.choice(possible_times)

        publication_date = dt.datetime(
            current_year, current_month, current_day,
            pub_hour, pub_minute,
            tzinfo=curent_date.tzinfo)
        return [publication_date]

    else:
        if num_dates > len(possible_times):
            raise ValueError(
                f"Невозможно сгенерировать {num_dates} уникальных дат. "
                f"До конца дня осталось только {len(possible_times)} свободных минут."
            )


        selected_times = random.sample(possible_times, num_dates)


        publication_dates = [
            dt.datetime(
                current_year, current_month, current_day,
                hour, minute,
                tzinfo=curent_date.tzinfo
            ) for hour, minute in selected_times
        ]

        return publication_dates


def filter_message(text: str):
    '''
    Мб что - то ещё добавится
    '''
    return text.replace("*"," ")

def split_short_long_message(text: str, max_length_caption: int = TELEGRAM_MAX_MESSAGE_CAPTION,
                             second_part_percent_value_threshold: int = 0.3):
    '''
    second_part_percent_value_threshold - размер второй части сплита от max_length_caption
    если вторая часть больше second_part_percent_value_threshold*second_part_percent_value_threshold, то 
    есть смысл разбивать пост и прикладывать картинку
    иначе - нет, картинка в кэшэ
    '''

    if len(text) <= max_length_caption:
        return text, None
    elif len(text) >= (1 + second_part_percent_value_threshold)*max_length_caption:
        short_part_part = text[: max_length_caption]
        pos_space_num = short_part_part.rfind(' ')
        if pos_space_num != -1:
            short_part = text[:pos_space_num]
            long_part = text[pos_space_num:]
            return short_part, long_part
        else:
            return None
                    
    else:
        return None
        
        

def split_long_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """
    Разбивает длинное сообщение на несколько частей, не разрывая слова.
    Возвращает список сообщений (частей).
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""
    words = text.split(' ')

    for word in words:
        if len(current_chunk) + len(word) + 1 > max_length:
            chunks.append(current_chunk.strip())
            current_chunk = ""

        current_chunk += word + " "

    if current_chunk:
        chunks.append(current_chunk.strip().replace("*"," "))

    return chunks


class SimillarSearchOpenRouter:

    embed_model: str = EMBED_MODEL

    embed = OpenRouterEmbeddings(api_key=OPEN_ROUTER_API_KEY, model_name=embed_model)

    async def cossine_simmilar(self, input_text: str, target_text: str):

        embed_input = np.array((await self.embed.aembed_query(input_text)))
        embed_target = np.array((await self.embed.aembed_query(input_text)))

        return (embed_input * embed_target).sum()

async def find_dublicates(embedder: SimillarSearchOpenRouter, cache: StrictRedis, post: str,
                    target_channel_id: str,
                    threshold: float = 0.7):
    
    for key in cache.scan_iter(match=f'post_{target_channel_id}_*'):
        cached_post = cache.get(key).decode()
        
        if (await embedder.cossine_simmilar(post, cached_post)) >= threshold:
            return True
    
    return False

def find_ads(post: str):
    key_words = ['реклама','erid']    
    for k in key_words:
        if k in post.lower():
            return True
    
    return False


def normalize_text(text: str) -> str:
    text = text.lower().replace('ё', 'е')
    return re.sub(r'[^\w\s]', ' ', text).strip()



def clean_text(text):
    """
    Очищает текст от URL, email, @упоминаний, HTML-тегов,
    телефонных номеров и лишних пробелов.
    """
    text = re.sub(r'\b(?:https?://|www\.)\S+\b', ' ', text)
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', ' ', text)
    text = re.sub(r'@[A-Za-z0-9_]+', ' ', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\b\+?\d[\d\s()-]{7,}\d\b', ' ', text)
    
    return text



def find_on_banned_org(text: str) -> str:
    """
    Обрабатывает текст, добавляя пометки о статусе организаций (иноагенты, запрещённые).

    Args:
        text (str): Исходный текст для обработки.

    Returns:
        str: Обработанный текст с пометками о статусе организаций.
    """
    base_path = os.path.join(os.path.curdir,"src", "data")
    with open(os.path.join(base_path, "inoagents_preproc.txt"), encoding="utf-8") as file_inoagents:
        inoagents = list(map(str.strip, file_inoagents.readlines()))

    with open(os.path.join(base_path, "org_preproc.txt"), encoding="utf-8") as banned_org_file:
        banned_orgs = list(map(str.strip, banned_org_file.readlines()))

    found_matches = {
        "иноагенты": set(),
        "экстримисты": set()
    }


    for name in inoagents:
        pattern = rf'\b{re.escape(name)}\b'
        if re.search(pattern, text, flags=re.IGNORECASE):
            found_matches["иноагенты"].add(name)
 
    for name in banned_orgs:
        pattern = rf'\b{re.escape(name)}\b'
        if re.search(pattern, text, flags=re.IGNORECASE):
            found_matches["экстримисты"].add(name)

    forbidden_prompt = ""
    
    if found_matches["иноагенты"]:
        forbidden_prompt += f"Иноагенты: {",".join(found_matches["иноагенты"])};"
    if found_matches["экстримисты"]:
        forbidden_prompt += f"Экстримисты: {",".join(found_matches["экстримисты"])};"

    return forbidden_prompt




def is_junk_post_regex(text: str) -> bool:
    """
    Фильтр мусора.
    Использует поиск по корням слов + [а-яё]* для любых окончаний.
    """
    if not text:
        return True

    patterns = [

        r"erid", # Обычно идет английскими буквами

        r"реклам[а-яё]*",   
        r"партн[её]рск[а-яё]*", 
        
        # Ловит: букмекер, букмекеры, букмекеров
        r"букмекер[а-яё]*", 
        r"фрибет[а-яё]*",
        r"казино", # Не склоняется
        r"1win",
        
        r"заработ[а-яё]*\s+в\s+интернет[а-яё]*", 
        r"арбитраж[а-яё]*",
        r"темк[а-яё]*", # Сленг "темки"

        r"пиш[а-яё]*\s+в\s+(?:лс|личк[а-яё]*|директ)", 

        r"розыгрыш[а-яё]*", 
        
        r"конкурс[а-яё]*",  
        r"\bгив[а-яё]*",    
        r"giveaway",
        
        r"подар[а-яё]*",    
        
        r"выигр[а-яё]*", 
        r'разыгр[а-яё]',
        r'рoзыгр[а-яё]',   
        
        
        r"бесплатн[а-яё]*", 
        
        r"\bприз(?:[а-яё]+)?\b", 

        r"подпи(?:с|ш)[а-яё]*", 
        
        # Корень "ссылк" -> ссылка, ссылке, ссылку
        r"ссылк[а-яё]*\s+в\s+(?:описани[а-яё]*|низ[а-яё]*|коммент[а-яё]*)",
        
        r"чита[а-яё]*\s+(?:далее|полностью|в\s+источник[а-яё]*)",
        r"продолжени[а-яё]*\s+(?:тут|здесь|в\s+канал[а-яё]*)",
        r"доступ[а-яё]*\s+закрыт[а-яё]*",
        r"кнопк[а-яё]*\s+ниж[а-яё]*",
        r"через\s+бот[а-яё]*",
        r"заявк[а-яё]*" # подать заявку
    ]

    # Собираем всё в одну большую регулярку
    combined_pattern = "|".join(patterns)
    
    if re.search(combined_pattern, text, flags=re.IGNORECASE | re.MULTILINE):
        return True

    return False







def parse_count(count_str: str) -> int:
    """
    Преобразует строку с количеством (например, '1.2K', '5M') в целое число.
    """
    if not count_str:
        return 0
    count_str = count_str.strip().upper()
    multiplier = 1
    if 'K' in count_str:
        multiplier = 1000
        count_str = count_str.replace('K', '')
    elif 'M' in count_str:
        multiplier = 1000000
        count_str = count_str.replace('M', '')
    try:
        return int(float(count_str) * multiplier)
    except (ValueError, TypeError):
        return 0


def get_all_tgstat_channel_themes() -> list[str]:
    '''
    Находит разделы с https://tgstat.ru/
    '''
    res = requests.get('https://tgstat.ru/',
                       headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win86; x86) AppleWebKit/537.36'})
    bs = BeautifulSoup(res.content, 'html.parser')
    themes = bs.find_all('a', class_='text-dark')
    th_res = set()

    for t in themes:
        her = t.get('href')
        if her.startswith('/') and len(her.split('/')) - 1 == 1:
            th_res.add(her[1:])

    save_yaml(list(th_res),'tgstat_endpoints')
    return th_res


def find_channel_names(tgstat_channel_theme: str,
                       headers: dict = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.5',
                                'Accept-Encoding': 'gzip, deflate',
                                'DNT': '1', # Do Not Track
                                'Connection': 'keep-alive',
                                'Upgrade-Insecure-Requests': '1',
                                'Sec-Fetch-Dest': 'document',
                                'Sec-Fetch-Mode': 'navigate',
                                'Sec-Fetch-Site': 'none',
                                'Sec-Fetch-User': '?1'}) -> list[str]:
    """
    Парсит tgstat, находя нужные каналы с тематикой tgstat_channel_theme
    """
    base_url = f'https://tgstat.ru/{tgstat_channel_theme}'
    headers['User-Agent'] = random.choice(user_agents)
    resp = requests.get(base_url,
                        headers=headers)
    bs = BeautifulSoup(resp.content, 'html.parser')
    hrefs = bs.find_all('a', class_="text-body")
    tgc_names = []
    for her in hrefs:
        linnk = her.get('href')
        pos = linnk.find('@')
        if pos > 0:
            tgc_names.append(linnk[pos + 1:])

    return tgc_names

def get_channel_posts(channel_name: str, k: int = 5,
                      headers: dict = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.5',
                                'Accept-Encoding': 'gzip, deflate',
                                'DNT': '1',
                                'Connection': 'keep-alive',
                                'Upgrade-Insecure-Requests': '1',
                                'Sec-Fetch-Dest': 'document',
                                'Sec-Fetch-Mode': 'navigate',
                                'Sec-Fetch-Site': 'none',
                                'Sec-Fetch-User': '?1'}):
    """
    Парсит последние k постов из публичного Telegram-канала, включая реакции.
    (Версия, исправленная на основе предоставленного пользователем HTML)
    """
    headers['User-Agent'] = random.choice(user_agents)
    base_url = f"https://t.me/s/{channel_name}"
    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к {base_url}: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_wrap')

    if not messages:
        logger.debug(f"Не удалось найти посты в канале '{channel_name}'."
                     "Возможно, делается несколько пересылок и сейчас обрабатываются "\
                     "медиа группы.")
        return []

    parsed_posts = []

    for message_widget in reversed(messages[-k:]):
        post_data = {}

        date_link_element = message_widget.find('a', class_='tgme_widget_message_date')
        
        if date_link_element:
            post_url_val = date_link_element.get('href', 'N/A')
            time_tag = date_link_element.find('time', class_='time')
            if time_tag:
                datetime_val = time_tag.get('datetime', 'N/A')


        text_element = message_widget.find('div', class_='tgme_widget_message_text')
        if not text_element:
            continue

        text = text_element.get_text(separator='\n', strip=True) if text_element else ""
        post_data['text'] = text
        post_data['post_url'] = post_url_val
        post_data['datetime'] = datetime_val

        is_ads = False
        for a_tag in text_element.find_all('a'):
            if a_tag.has_attr('href'):
                link_url = a_tag['href']
                if 'erid' in link_url.lower():
                    is_ads = True
                    break

        post_data['is_ads'] = is_ads
        post_data['is_video'] = message_widget.find('video') is not None

        media_links = []
        views_element = message_widget.find('span', class_='tgme_widget_message_views')
        views_element = parse_count(views_element.text)
        post_data['num_post_views'] = views_element
        media_elements = message_widget.find_all('a', class_='tgme_widget_message_photo_wrap')

        for media in media_elements:
            style = media.get('style', '')
            if 'background-image:url(' in style:
                link = style.split("url('")[1].split("')")[0]
                media_links.append(link)
        post_data['media_links'] = media_links

        post_link_element = message_widget.find('a', class_='tgme_widget_message_date')
        post_data['post_url'] = post_link_element['href'] if post_link_element else 'N/A'


        reactions_data = {}
        reactions_container = message_widget.find('div', class_='tgme_widget_message_reactions')
        if reactions_container:

            reaction_elements = reactions_container.find_all('span', class_='tgme_reaction')

            for reaction in reaction_elements:
                emoji_char = ''
                count_str = ''

                emoji_el = reaction.find('b')
                if emoji_el:
                    emoji_char = emoji_el.text.strip()

                full_text = reaction.text.strip()
                if emoji_char:
                    count_str = full_text.replace(emoji_char, '').strip()
                else:
                    count_str = ''.join(filter(str.isdigit, full_text))

                if emoji_char and count_str:
                    reactions_data[emoji_char] = parse_count(count_str)

        post_data['reactions'] = reactions_data
        parsed_posts.append(post_data)

    return parsed_posts


def get_channel_single_post_info(channel_name: str, post_id: str,
                      headers: dict = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.5',
                                'Accept-Encoding': 'gzip, deflate',
                                'DNT': '1',
                                'Connection': 'keep-alive',
                                'Upgrade-Insecure-Requests': '1',
                                'Sec-Fetch-Dest': 'document',
                                'Sec-Fetch-Mode': 'navigate',
                                'Sec-Fetch-Site': 'none',
                                'Sec-Fetch-User': '?1'}):
    """
    Парсит последние k постов из публичного Telegram-канала, включая реакции.
    (Версия, исправленная на основе предоставленного пользователем HTML)
    """
    headers['User-Agent'] = random.choice(user_agents)
    base_url = f"https://t.me/s/{channel_name}/{post_id}"
    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к {base_url}: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    post_selector = f'div[data-post="{channel_name}/{post_id}"]'
    message_container = soup.select_one(post_selector)


    if not message_container:
        logger.debug(f"Не удалось найти посты в канале '{channel_name}'."
                     "Возможно, делается несколько пересылок и сейчас обрабатываются "\
                     "медиа группы.")
        return []

    post_data = {}
    datetime = message_container.find('a', class_='tgme_widget_message_date').\
                                find('time', class_='time')['datetime']

    post_data['datetime'] = datetime                                
    text_element = message_container.find('div', class_='tgme_widget_message_text')
    if not text_element:
        return None
    text = text_element.get_text(separator='\n', strip=True) if text_element else ""
    post_data['text'] = text

    post_data['post_url'] = base_url

    is_ads = False
    for a_tag in text_element.find_all('a'):
        if a_tag.has_attr('href'):
            link_url = a_tag['href']
            if 'erid' in link_url.lower():
                is_ads = True
                break

    post_data['is_ads'] = is_ads
    media_links = []
    views_element = message_container.find('span', class_='tgme_widget_message_views')
    views_element = parse_count(views_element.text)
    post_data['num_post_views'] = views_element
    media_elements = message_container.find_all('a', class_='tgme_widget_message_photo_wrap') or \
                    message_container.find_all('i', class_='tgme_widget_message_video_thumb')

    for media in media_elements:
        style = media.get('style', '')
        if 'background-image:url(' in style:
            link = style.split("url('")[1].split("')")[0]
            media_links.append(link)
    post_data['media_links'] = media_links

    post_link_element = message_container.find('a', class_='tgme_widget_message_date')
    post_data['post_url'] = post_link_element['href'] if post_link_element else 'N/A'


    reactions_data = {}
    reactions_container = message_container.find('div', class_='tgme_widget_message_reactions')
    if reactions_container:

        reaction_elements = reactions_container.find_all('span', class_='tgme_reaction')

        for reaction in reaction_elements:
            emoji_char = ''
            count_str = ''

            emoji_el = reaction.find('b')
            if emoji_el:
                emoji_char = emoji_el.text.strip()

            full_text = reaction.text.strip()
            if emoji_char:
                count_str = full_text.replace(emoji_char, '').strip()
            else:
                count_str = ''.join(filter(str.isdigit, full_text))

            if emoji_char and count_str:
                reactions_data[emoji_char] = parse_count(count_str)

    post_data['reactions'] = reactions_data
    return post_data
