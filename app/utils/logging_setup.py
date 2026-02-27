from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config import Settings


def setup_logging(settings: Settings) -> None:
    level_name = (settings.log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        stream.setLevel(level)
        root.addHandler(stream)

    if settings.log_to_file:
        logs_dir = settings.storage_root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "app.log"
        existing = [
            h
            for h in root.handlers
            if isinstance(h, RotatingFileHandler)
            and getattr(h, "baseFilename", "").endswith(str(log_path))
        ]
        if not existing:
            file_handler = RotatingFileHandler(
                filename=log_path,
                maxBytes=2 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(fmt)
            file_handler.setLevel(level)
            root.addHandler(file_handler)
