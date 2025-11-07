from dotenv import load_dotenv

import logging, os
from logging.handlers import RotatingFileHandler


load_dotenv()

# Ошибки для удобного отлова
class CriticalError(BaseException):
    ...

class WarningError(BaseException):
    ...

class SkipError(BaseException):
    ...

# Переменные для gitea
GITEA_URL : str = 'https://gitea.com'
OWNER : str = ''
REPO : str = ''
TOKEN : str = os.getenv('TOKEN')

# Переменные для скачивания csv с операторами
DOWNLOAD_URL : str = 'https://opendata.digital.gov.ru/downloads/DEF-9xx.csv'
DEFAULT_FILENAME : str = 'DEF-9xx.csv'
OUTPUT_DIR_NAME : str = 'operators'

# Настройки Логгера
logger = logging.getLogger("App")
logger.level = logging.INFO # Уровень логирования

handler = RotatingFileHandler(
    filename = 'app.log',
    maxBytes = 5 * 1024 * 1024,
    backupCount = 5,
    encoding = 'utf-8'
)

formatter = logging.Formatter('%(asctime)s %(levelname)s -- %(funcName)s(%(lineno)d) - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)

# Данные для операторов
default_operators = ['megafon', 'beeline', 'mts', 'tele2', 'rostelecom', 'yota'] # Операторы вызываемые без указания флагов
operators_list = { # Операторы которых можно вызвать флагом --name
    'mts': ['7740000076'],
    'megafon': ['7812014560'],
    'beeline': ['7713076301'],
    'tele2': ['7743895280'],
    'rostelecom': ['7707049388'],
    'yota': ['7840467957']
}

inn_to_operator = {}
for operator_name, inn_list in operators_list.items():
    for inn in inn_list:
        inn_to_operator[inn] = operator_name
