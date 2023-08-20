from __future__ import annotations

import logging.config

import yaml

import settings

LOGGER = logging.getLogger("app_logger")


def configure_logging() -> None:
    with open("logging.yaml") as f:
        config = yaml.safe_load(f.read())

        # inject the logz.io token from our configuration
        config["handlers"]["logzio"]["token"] = settings.LOGZIO_TOKEN

        logging.config.dictConfig(config)


def debug(*args, **kwargs) -> None:
    LOGGER.debug(*args, **kwargs)


def info(*args, **kwargs) -> None:
    LOGGER.info(*args, **kwargs)


def warning(*args, **kwargs) -> None:
    LOGGER.warning(*args, **kwargs)


def error(*args, **kwargs) -> None:
    LOGGER.error(*args, **kwargs)


def critical(*args, **kwargs) -> None:
    LOGGER.critical(*args, **kwargs)
