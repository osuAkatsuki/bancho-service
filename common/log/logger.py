import yaml
import logging.config

LOGGER = logging.getLogger("app_logger")


def configure_logging() -> None:
    with open("logging.yaml", "r") as f:
        config = yaml.safe_load(f.read())
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
