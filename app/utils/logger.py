import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler


def setup_logger(name):
    """Setup a logger that logs to both the console and a rotating file"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_directory = f"{current_dir}/../logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    # Use a date-based log file name
    log_filename = datetime.now().strftime("app_%Y%m%d.log")
    log_file_path = os.path.join(log_directory, log_filename)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Set the formatter for the logs
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    # Setup the RotatingFileHandler
    file_handler = RotatingFileHandler(log_file_path, maxBytes=1024 * 1024, backupCount=3)
    file_handler.setFormatter(formatter)

    # Setup the StreamHandler for console output
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


app_logger = setup_logger("appLogger")
