from time import perf_counter
import os
import re
import uuid
import redis
import requests
from loguru import logger
import json
from datetime import datetime


def measure_time(func):

    def wrapper(*args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        time_res = perf_counter() - start
        log_data = {"node": func.__name__, "elapsed_time": f"{time_res} s", "asctime": datetime.now().isoformat()}
        logger.info(json.dumps(log_data))
        return result

    return wrapper


def links_filter(links: list[str]):
    res = []
    forbidden_keywords = {'facebook', 'youtube', 'twitter','instagram'}
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    if links:
        for link in links:
            flag = False
            for l in forbidden_keywords:
                if l in link:
                    flag = True

            if flag:
                continue 
            try:
                answ = str(requests.get(link, headers=headers).status_code)
                if answ == '200':
                    res.append(link)
            except:
                continue
        
        return res
    else:
        return []

def redis_img_find(redis_cache: redis.StrictRedis):
    all_img_links = []
    for link in redis_cache.scan_iter("img_link_*"):
        link = redis_cache.get(link).decode()
        if link:
            all_img_links.append(link)
    
    return all_img_links

def redis_update_links(links: list[str], redis_cache: redis.StrictRedis,
                       ttl:int = 86400):
    for link in links:
        redis_cache.set(name=f'img_link_{uuid.uuid4().hex}', value=link,
                        ex=ttl)

def preproc_text_on_banned_org(text: str) -> str:
    """
    Обрабатывает текст, добавляя пометки о статусе организаций (иноагенты, запрещённые).

    Args:
        text (str): Исходный текст для обработки.

    Returns:
        str: Обработанный текст с пометками о статусе организаций.
    """
    base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "prep")
    with open(os.path.join(base_path, "inoagents_preproc.txt"), encoding="utf-8") as file_inoagents:
        inoagents = list(map(str.strip, file_inoagents.readlines()))

    with open(os.path.join(base_path, "org_preproc.txt"), encoding="utf-8") as banned_org_file:
        banned_orgs = list(map(str.strip, banned_org_file.readlines()))

    for inoagent in inoagents:
        find_inoagent = inoagent.replace("\n", "").strip()
        text = re.sub(
            rf"\b{find_inoagent}\b",
            f"{inoagent} (организация признана Минюстом иностранным агентом)",
            text,
            flags=re.IGNORECASE,
        )

    for org in banned_orgs:
        find_org = org.replace("\n", "").strip()
        text = re.sub(
            rf"\b{find_org}\b",
            f"{find_org} (организация, деятельность которой запрещена на территории Российской Федерации)",
            text,
            flags=re.IGNORECASE,
        )
    return text