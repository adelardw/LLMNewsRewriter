from googleapiclient.discovery import build
import os
from PIL import Image
from ddgs import DDGS
from io import BytesIO
from bing_image_downloader import downloader
import requests
from loguru import logger
from src.config import TEMPLATE_PATH
from src.agents.utils import get_links_for_images



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



def get_ddgs_image_loads(query, max_images=10, base_path=TEMPLATE_PATH):
    if not os.path.exists(base_path):
        os.makedirs(base_path, exist_ok=True)
    
    safe_query_name = "".join([c if c.isalnum() else "_" for c in query])
    save_directory = os.path.join(base_path, safe_query_name)
    os.makedirs(save_directory, exist_ok=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    downloaded_paths = []

    try:
        with DDGS() as loader:
            results = loader.images(
                query=query,
                region='ru-ru',
                safesearch='on',
                size="Wallpaper",
                type_image="photo",
                time="Week",
                max_results=max_images
            )
            
            count = 0
            for res in results:
                if count >= max_images:
                    break

                image_url = res.get('image')
                if not image_url: continue

                try:
                    response = requests.get(image_url, headers=headers, timeout=7, stream=True)
                    if response.status_code != 200: continue

                    file_size = int(response.headers.get('Content-Length', 0))
                    if 0 < file_size < 150000: 
                        logger.info(f"Пропуск: файл слишком мал ({file_size} байт)")
                        continue

                    img_content = response.content
                    img = Image.open(BytesIO(img_content))
                    width, height = img.size

                    if width < 1200 and height < 1200:
                        logger.info(f"Пропуск: низкое разрешение {width}x{height}")
                        continue

                    ext = f".{img.format.lower()}" if img.format else ".jpg"
                    filename = f"highres_{count + 1}{ext}"
                    full_path = os.path.join(save_directory, filename)

                    with open(full_path, 'wb') as f:
                        f.write(img_content)
                    
                    downloaded_paths.append(full_path)
                    logger.info(f"✅ Успешно скачано: {width}x{height} | {filename}")
                    count += 1

                except Exception as e:
                    logger.error(f"Ошибка при обработке {image_url}: {e}")
                    continue

        return get_links_for_images(save_directory)

    except Exception as e:
        logger.error(f"Глобальная ошибка: {e}")
        return []