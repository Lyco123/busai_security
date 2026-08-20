# -*- coding: utf-8 -*-
import logging
import sys
from logging.handlers import TimedRotatingFileHandler

from model.vehicle.src.utils.common import LOGS_ROOT
from pathlib import Path


class AppLogger:
    def __init__(self):
        self.logger = logging.getLogger("Vehicle")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.file_handler = None

        if not self.logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            self.formatter = formatter
        else:
            self.formatter = self.logger.handlers[0].formatter

    def configure(self, log_dir: Path, job_name: str, create_date: str, batch_name: str):
        log_dir.mkdir(parents=True, exist_ok=True)
        if self.file_handler is not None:
            self.logger.removeHandler(self.file_handler)
            self.file_handler.close()
            self.file_handler = None

        log_file = log_dir / f"vehicle_{job_name}_{create_date}_{batch_name}.log"
        self.file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        self.file_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.file_handler)
        self.logger.info(f"日志文件: {log_file}")

    def chapter(self, message: str):
        self.logger.info("-" * 60)
        self.logger.info(f">>> {message}")
        self.logger.info("-" * 60)

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def exception(self, message: str):
        self.logger.exception(message)


logger = AppLogger()
