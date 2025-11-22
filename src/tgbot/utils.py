from redis import StrictRedis
import numpy as np
import os
import pytz
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
import datetime as dt
import typing as tp
import random
import re
from src.config import EMBED_MODEL


TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_MAX_MESSAGE_CAPTION = 1024

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

class HFLCSSimTexts:

    embed_model: str = EMBED_MODEL
    model_kwargs = {'device': 'cpu'}
    encode_kwargs = {'normalize_embeddings': True}

    embed = HuggingFaceEmbeddings(model_name=embed_model,
                                 model_kwargs=model_kwargs,
                                 encode_kwargs=encode_kwargs)

    def cossine_simmilar(self, input_text: str, target_text: str):

        embed_input = np.array(self.embed.embed_query(input_text))
        embed_target = np.array(self.embed.embed_query(target_text))

        return (embed_input * embed_target).sum()

def find_dublicates(embedder: HFLCSSimTexts, cache: StrictRedis, post: str,
                      threshold: float = 0.7):
    
    for key in cache.scan_iter(match='post_*'):
        cached_post = cache.get(key).decode()
        
        if embedder.cossine_simmilar(post, cached_post) >= threshold:
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