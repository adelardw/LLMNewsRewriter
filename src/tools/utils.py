from urllib.parse import urlparse
import shutil
import subprocess
import re
import tldextract
import os
import mimetypes
import base64
import os

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

def rm_img_folders(base_path: str = './tmp', cached_depth: str = 60):
    if os.path.exists(base_path) and os.path.isdir(base_path):
        if len(folders:=os.listdir(base_path)) >= cached_depth:
            for fld in folders:
                full_path = os.path.join(base_path, fld) 
                shutil.rmtree(full_path)
    