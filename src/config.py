import os
from dotenv import load_dotenv
load_dotenv()
import pytz
import os
import yaml
from omegaconf import DictConfig,OmegaConf
import typing as tp


GENERAL_SAVE_PATH = os.path.abspath(os.path.curdir)
CONFIG_PATH = os.path.join(GENERAL_SAVE_PATH, 'config.yml')
TIMEZONE = 'Europe/Moscow'
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
CX_ID = os.getenv('CX_ID')
OPEN_ROUTER_API_KEY = os.getenv('OPEN_ROUTER_API_KEY')
TEXT_GENERATION_MODEL = os.getenv('TEXT_GENERATION_MODEL')

TEXT_IMAGE_MODEL = os.getenv('TEXT_IMAGE_MODEL')


API_TOKEN = os.getenv('TGBOTAPIKEY', None)
ADMIN_ID = os.getenv('ADMINID', None)
CHANNEL_ID = os.getenv('CHANNEL_ID')
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE'))
EMBED_MODEL = os.getenv('EMBED_MODEL','cointegrated/LaBSE-en-ru')

TEMPLATE_PATH = "./tmp"
TMP_CACHED_DEPTH = 50

embed_model_name = os.getenv('EMBED_MODEL', 'cointegrated/LaBSE-en-ru')
with open(CONFIG_PATH, 'r') as file:

    data = DictConfig(yaml.safe_load(file))
    user_agents = data.metadata.web.user_agents
    endpoints = data.metadata.web.tgstat_endpoints
    web_retrieve_kwargs = data.metadata.web_retrieve_kwargs
    tgc_search_kwargs = data.metadata.tgc_search_kwargs

def save_yaml(input_data: tp.Any, saved_key: str = 'user_agents'):
    data.metadata.web[saved_key] = input_data
    config = OmegaConf.create(data)
    OmegaConf.save(config, CONFIG_PATH)
