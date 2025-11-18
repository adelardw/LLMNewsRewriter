from googleapiclient.discovery import build
import os
import logging
from ddgs import DDGS


logging.getLogger('icrawler').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

from icrawler.builtin import GoogleImageCrawler
from icrawler import ImageDownloader
from bing_image_downloader import downloader
import requests
from loguru import logger
from src.config import CX_ID, GOOGLE_API_KEY, TEMPLATE_PATH
from src.tools.utils import get_links_for_images

def search_img(query: str, num: int = 10):
    try:
        permissive_rights = 'cc_publicdomain|cc_attribute|cc_sharealike'
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = service.cse().list(q=query,cx=CX_ID,
                                 searchType='image',
                                 fileType='jpg,png,jpeg,gif',
                                 safe='active',
                                 gl='ru',
                                 num=num,
                                 fields="items/link"
                                 ).execute()


        answer = []
        if 'items' in res:
            for item in res['items']:
                answer.append(item['link'])

        return answer
    except Exception as e:
        if e.status_code == 429:
            logger.info("Ошибка: Дневная квота на запросы к Google Custom Search API исчерпана.")
            return [] 
        else:
            logger.info(f"Произошла ошибка HTTP: {e}")
            return []
        

class LinkCollectorGoogleImageCrawler(GoogleImageCrawler):
    def __init__(self, *args, **kwargs):
        super().__init__(downloader_cls=LinkCollectorDownloader, *args, **kwargs)
        self.image_links = []


class LinkCollectorDownloader(ImageDownloader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image_links = []
        self.counter = 0


    def download(self, task, default_ext=None, timeout=5, max_retry=1, overwrite=False, **kwargs):
        """Переопределенный метод - только сохраняет ссылку, не скачивает файл"""
        file_url = task['file_url']

        if self.counter == self.max_num:
            return True
        try:
            response = requests.head(file_url, timeout=2, allow_redirects=True)
            if response.status_code == 200:
                self.image_links.append(file_url)
                self.counter += 1
        except requests.RequestException as e:
            logger.info(f"✗ Ошибка проверки ссылки: {file_url} - {e}")


        return True

    def get_links(self):
        """Возвращает собранные ссылки"""
        return self.image_links



def get_google_image_links(keyword, max_num=5, filters=None) -> list[str]:
    """Функция для получения списка ссылок на изображения"""

    crawler = LinkCollectorGoogleImageCrawler()

    crawler.crawl(
        keyword=keyword,
        max_num=max_num,
        language='ru',
        filters=filters
    )
    return crawler.downloader.get_links()


def get_google_image_loads(keyword:str, max_num: int =5,
                           base_path: str = TEMPLATE_PATH,
                           filters=None) -> list[str]:
    """Функция для получения списка ссылок на изображения"""
    if not os.path.exists(base_path):
        os.mkdir(base_path)
    
    save_directory = os.path.join(base_path, keyword.replace(' ','_'))
    if not os.path.exists(save_directory):
        os.mkdir(save_directory)

    crawler = GoogleImageCrawler(storage={'root_dir': save_directory})

    crawler.crawl(
        keyword=keyword,
        max_num=max_num,
        #language='ru',
        filters=filters
    )
    links = get_links_for_images(save_directory)
    return links


def get_bing_image_loads(keyword: str,
                         limit: int = 5,
                         base_path: str = TEMPLATE_PATH):
    
    if not os.path.exists(base_path):
        os.mkdir(base_path)
    
    save_directory = os.path.join(base_path, keyword)
    if not os.path.exists(save_directory):
        os.mkdir(save_directory)
        
    downloader.download(
        keyword,
        limit=limit,
        output_dir=base_path,
        adult_filter_off=True,
        force_replace=False,
        timeout=60,
        verbose=True)

        
    links = get_links_for_images(save_directory)
    return links



def get_ddgs_image_loads(query, max_images=10,
                         base_path: str = TEMPLATE_PATH,):
    
    if not os.path.exists(base_path):
        os.mkdir(base_path)
    
    save_directory = os.path.join(base_path, query.replace(' ','_'))
    if not os.path.exists(save_directory):
        os.mkdir(save_directory)

    with DDGS() as loader:
        results = loader.images(
            query=query,
            region='ru',
            timelimit="w",
            max_results=max_images
        )

        count = 0
        for i, res in enumerate(results):
            image_url = res.get('image')

            if not image_url:
                continue

            try:
                logger.info(f"Скачивание {count+1}: {image_url[:50]}...")
 
                response = requests.get(image_url, timeout=10)

                if response.status_code == 200:
                    ext = os.path.splitext(image_url)[1]
                    if len(ext) < 3 or len(ext) > 5:
                        ext = '.jpg' # Дефолтное расширение

                    filename = f"img_{count + 1}{ext}"
                    full_path = os.path.join(save_directory, filename)

                    with open(full_path, 'wb') as f:
                        f.write(response.content)

                    count += 1
                else:
                    logger.error(f"❌ Ошибка доступа (код {response.status_code})")

            except Exception as e:
                logger.error(f"❌ Ошибка при скачивании: {e}")
        
    links = get_links_for_images(save_directory)
    return links

