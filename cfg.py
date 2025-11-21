import logging
import os
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

load_dotenv()

# Ошибки для удобного отлова
class CriticalError(BaseException):
    ...

class WarningError(BaseException):
    ...

class SkipError(BaseException):
    ...

# Переменные для gitea
GITEA_URL : str = os.getenv('GITEA_URL')
OWNER : str = os.getenv('OWNER')
REPO : str = os.getenv('REPO')
TOKEN : str = os.getenv('TOKEN')

# Переменные для скачивания csv с операторами
DOWNLOAD_URL : str = os.getenv('DOWNLOAD_URL')
DEFAULT_FILENAME : str = os.getenv('DEFAULT_FILENAME')
OUTPUT_DIR_NAME : str = os.getenv('OUTPUT_DIR_NAME')

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

@dataclass
class RowData:
    def_code: int
    start_input: int
    end_input: int
    operator_name: str
    inn: int

@dataclass
class PatternLine:
    pattern: str
    operator_name: str
    inn: str

@dataclass
class Pattern:
    prefix: str
    mask: list[str]

    def to_string(self) -> str:
        pattern_str = self.prefix + ''.join(self.mask)
        return f'exten = _[78]{pattern_str},1,GoSub(${{ARG1}},${{EXTEN}},1)'

@dataclass
class PatternItem:
    original: str
    digit_part: str
    x_count: int
    pattern_body: str


def get_default_operators() -> dict[str]:
    default_operators = {
        'megafon': '7812014560',
        'beeline': '7713076301',
        'mts': '7740000076',
        'tele2': '7743895280',
        'rostelecom': '7707049388',
        'yota': '7701725181',
    }
    return default_operators


def get_operator_to_inn(inn: str) -> str:
    operators = get_default_operators()
    reverse_mapping = {inn: name for name, inn in operators.items()}
    
    operator_name = reverse_mapping.get(inn)
    return operator_name
    