"""
Logging Service for Backend
Logs all operations to files with rotation
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Log file paths
OCR_LOG_FILE = LOGS_DIR / "ocr.log"
TRANSLATION_LOG_FILE = LOGS_DIR / "translation.log"
EXPORT_LOG_FILE = LOGS_DIR / "export.log"
GENERAL_LOG_FILE = LOGS_DIR / "general.log"
API_LOG_FILE = LOGS_DIR / "api.log"

# Log format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def setup_logger(name: str, log_file: Path, level=logging.INFO):
    """Setup a logger with file and console handlers"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers = []
    
    # File handler with rotation (10MB max, 5 backup files)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# Create loggers
ocr_logger = setup_logger('ocr', OCR_LOG_FILE)
translation_logger = setup_logger('translation', TRANSLATION_LOG_FILE)
export_logger = setup_logger('export', EXPORT_LOG_FILE)
general_logger = setup_logger('general', GENERAL_LOG_FILE)
api_logger = setup_logger('api', API_LOG_FILE)


def log_ocr_request(file_size: int, file_type: str, languages: list, method: str = None):
    """Log OCR request"""
    ocr_logger.info(
        f"OCR Request - Size: {file_size / 1024:.1f}KB, Type: {file_type}, "
        f"Languages: {', '.join(languages)}, Method: {method or 'auto'}"
    )


def log_ocr_result(method: str, success: bool, time_taken: float, pages: int = 1, error: str = None):
    """Log OCR result"""
    if success:
        ocr_logger.info(
            f"OCR Result - Method: {method}, Success: True, Time: {time_taken:.2f}s, Pages: {pages}"
        )
    else:
        ocr_logger.error(
            f"OCR Result - Method: {method}, Success: False, Time: {time_taken:.2f}s, Error: {error}"
        )


def log_translation_request(text_length: int, from_lang: str, to_lang: str):
    """Log translation request"""
    translation_logger.info(
        f"Translation Request - Length: {text_length} chars, From: {from_lang}, To: {to_lang}"
    )


def log_translation_result(success: bool, time_taken: float, error: str = None):
    """Log translation result"""
    if success:
        translation_logger.info(f"Translation Result - Success: True, Time: {time_taken:.2f}s")
    else:
        translation_logger.error(f"Translation Result - Success: False, Time: {time_taken:.2f}s, Error: {error}")


def log_export_request(export_type: str, data_size: int):
    """Log export request"""
    export_logger.info(f"Export Request - Type: {export_type}, Data size: {data_size} bytes")


def log_export_result(export_type: str, success: bool, time_taken: float, file_size: int = 0, error: str = None):
    """Log export result"""
    if success:
        export_logger.info(
            f"Export Result - Type: {export_type}, Success: True, Time: {time_taken:.2f}s, Output: {file_size} bytes"
        )
    else:
        export_logger.error(
            f"Export Result - Type: {export_type}, Success: False, Time: {time_taken:.2f}s, Error: {error}"
        )


def log_api_request(method: str, endpoint: str, client_ip: str = None):
    """Log API request"""
    api_logger.info(f"API Request - {method} {endpoint}" + (f" from {client_ip}" if client_ip else ""))


def log_api_response(method: str, endpoint: str, status_code: int, time_taken: float):
    """Log API response"""
    api_logger.info(
        f"API Response - {method} {endpoint} - Status: {status_code}, Time: {time_taken:.2f}s"
    )


def log_error(component: str, error: Exception, context: dict = None):
    """Log error with context"""
    error_msg = f"Error in {component}: {str(error)}"
    if context:
        error_msg += f" - Context: {context}"
    general_logger.error(error_msg, exc_info=True)

