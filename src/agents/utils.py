from time import perf_counter
import os
import re
import uuid
import redis
import requests
from loguru import logger
import json
from datetime import datetime
import functools
from urllib.parse import urlparse
import shutil
from src.config import TEMPLATE_PATH, TMP_CACHED_DEPTH
import re
import tldextract
import os
import mimetypes
import base64
import os

def measure_time(func):

    def wrapper(*args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        time_res = perf_counter() - start
        log_data = {"node": func.__name__, "elapsed_time": f"{time_res} s", "asctime": datetime.now().isoformat()}
        logger.info(json.dumps(log_data))
        return result

    return wrapper


def measure_time_async(func):

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = perf_counter()
        result = await func(*args, **kwargs)
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
    base_path = os.path.join(os.path.curdir,"src", "data")
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

def is_url_safe(url):
    parsed = urlparse(url)

    if parsed.scheme not in ['http', 'https']:
        return False

    domain_info = tldextract.extract(parsed.netloc)
    domain = f"{domain_info.domain}.{domain_info.suffix}"


    dangerous_domains = [
        'exe-download.com', 'free-cracks.org',
        'adult-site.com', 'bitcoin-miner.net'
    ]

    if domain in dangerous_domains:
        return False

    suspicious_patterns = [
        r'\.exe$', r'\.zip$', r'\.rar$', r'\.msi$',
        r'\/download\/', r'\/install\/', r'\/crack\/',
        r'\/keygen\/', r'\/torrent\/'
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, url, re.I):
            return False

    return True


def image_to_data_uri(filepath: str) -> str:
    """
    Принимает путь к файлу изображения и возвращает
    Data URI (Base64), готовый для отправки в LLM.
    """
    mime_type, _ = mimetypes.guess_type(filepath)
    if mime_type is None:
        mime_type = "application/octet-stream"

    with open(filepath, "rb") as image_file:
        binary_data = image_file.read()


    base64_encoded_string = base64.b64encode(binary_data).decode('utf-8')
    data_uri = f"data:{mime_type};base64,{base64_encoded_string}"
    
    return data_uri

def get_links_for_images(image_path: str):
    links = []
    if os.path.exists(image_path):
        for im in os.listdir(image_path):
            impath = os.path.join(image_path, im)
            uri = image_to_data_uri(impath)
            links.append(uri)
    
    return links

def rm_img_folders(base_path: str = TEMPLATE_PATH, cached_depth: int = TMP_CACHED_DEPTH):
    if os.path.exists(base_path) and os.path.isdir(base_path):
        if len(folders:=os.listdir(base_path)) >= cached_depth:
            for fld in folders:
                full_path = os.path.join(base_path, fld) 
                shutil.rmtree(full_path)
    