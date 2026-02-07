import sys
import logging
import traceback
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""

    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
    }
    RESET = '\033[0m'

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(name: str = "web_server") -> logging.Logger:
    """
    设置统一的日志系统

    格式: [时间] [级别] [模块] 消息
    例如: [2024-01-01 12:00:00] [INFO] [translate] Starting translation for task abc123
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 控制台处理器 - 强制输出到 stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # 格式化器
    formatter = ColoredFormatter(
        fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # 防止日志传播到父 logger（避免被 uvicorn 覆盖）
    logger.propagate = False

    return logger


def log_error(logger: logging.Logger, error: Exception, context: str = ""):
    """
    统一的错误日志格式

    Args:
        logger: logger 实例
        error: 异常对象
        context: 错误上下文描述
    """
    logger.error(f"{'='*80}")
    if context:
        logger.error(f"ERROR: {context}")
    logger.error(f"Exception Type: {type(error).__name__}")
    logger.error(f"Exception Message: {str(error) or '(empty)'}")
    logger.error(f"{'='*80}")
    logger.error(traceback.format_exc())
    logger.error(f"{'='*80}")


# 全局 logger 实例
main_logger = setup_logger("main")
api_logger = setup_logger("api")
service_logger = setup_logger("service")
db_logger = setup_logger("db")
