import logging
from logging.handlers import RotatingFileHandler


class CriticalError(BaseException):
    ...

class WarningError(BaseException):
    ...

class SkipError(BaseException):
    ...

logger = logging.getLogger("App")
logger.level = logging.INFO

handler = RotatingFileHandler(
    filename = f'app.log',
    maxBytes = 5 * 1024 * 1024,
    backupCount = 5,
    encoding = 'utf-8'
)

formatter = logging.Formatter('%(asctime)s %(levelname)s -- %(funcName)s(%(lineno)d) - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)
