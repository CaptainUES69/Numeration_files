import logging
from logging.handlers import RotatingFileHandler


class CriticalError(BaseException):
    ...

class WarningError(BaseException):
    ...

class SkipError(BaseException):
    ...

download_url : str = 'https://opendata.digital.gov.ru/downloads/DEF-9xx.csv'
default_filename : str = 'data.csv'
dir_name : str = 'operators'

logger = logging.getLogger("App")
logger.level = logging.INFO # Уровень логирования

handler = RotatingFileHandler(
    filename = f'app.log',
    maxBytes = 5 * 1024 * 1024,
    backupCount = 5,
    encoding = 'utf-8'
)

formatter = logging.Formatter('%(asctime)s %(levelname)s -- %(funcName)s(%(lineno)d) - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)

default_operators = ['megafon', 'beeline', 'mts', 'tele2', 'rostelecom', 'yota'] # Операторы вызываемые без указания флагов

operators_list = { # Операторы которых можно вызвать флагом --name
    'mts': ['7740000076'],
    'megafon': ['7812014560'],
    'beeline': ['7713076301'],
    'tele2': ['7743895280'],
    'rostelecom': ['7707049388'],
    'yota': ['7840467957'],
    'integral': ['7713621010']
}

inn_to_operator = {}
for operator_name, inn_list in operators_list.items():
    for inn in inn_list:
        inn_to_operator[inn] = operator_name