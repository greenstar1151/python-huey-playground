import logging
import os
from pathlib import Path
from typing import Annotated, Any

from pydantic import WrapValidator
from pydantic_core.core_schema import ValidationInfo, ValidatorFunctionWrapHandler
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.constants import PROJECT_ROOT, Environment


def validate_log_level_pydantic(
    v: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo
) -> ValidatorFunctionWrapHandler:
    name_to_level = logging.getLevelNamesMapping()
    if isinstance(v, str):
        assert v in name_to_level.keys()
        return handler(name_to_level[v])
    elif isinstance(v, int):
        assert v in name_to_level.values()
        return handler(v)
    else:
        raise ValueError(f"Invalid log level: {v}")


class Settings(BaseSettings):
    # App Settings (mapped from environment variables or .env file: see model_config)
    # General
    DEBUG: bool = True
    ENVIRONMENT: Environment = Environment.DEVELOPMENT

    # Subprocess Settings
    TIMEOUT_SEC: float | None = None  # None means no timeout

    # Files
    ## if not None, override default temp dir
    ## ref. https://docs.python.org/3.12/library/tempfile.html#tempfile.mkdtemp
    TEMP_WORKDIR: Path | None = None

    # Logging
    LOG_FILE_DIR: Path = PROJECT_ROOT / "logs"
    LOG_LEVEL: Annotated[int, WrapValidator(validate_log_level_pydantic)] = (
        logging.INFO
    )  # LOG_LEVEL="INFO" / LOG_LEVEL=20

    # Huey Settings
    HUEY_DB_PATH: Path = PROJECT_ROOT / "job.db"

    # Pydantic BaseSettings Config
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",  # ref. https://docs.pydantic.dev/latest/concepts/pydantic_settings/#parsing-environment-variable-values
        env_file=".env",  # ref. https://docs.pydantic.dev/latest/concepts/pydantic_settings/#dotenv-env-support
        extra="ignore",  # ignore extra fields in .env that are used in other services
    )


class DevelopmentSettings(Settings):
    TEMP_WORKDIR: Path | None = PROJECT_ROOT / "temp"


class ProductionSettings(Settings):
    DEBUG: bool = False
    ENVIRONMENT: Environment = Environment.PRODUCTION


class TestSettings(Settings):
    DEBUG: bool = False
    ENVIRONMENT: Environment = Environment.TEST


def get_settings() -> Settings:
    env = os.getenv("ENVIRONMENT", "DEVELOPMENT")
    match env:
        case "DEVELOPMENT":
            return DevelopmentSettings()
        case "PRODUCTION":
            return ProductionSettings()
        case "TEST":
            return TestSettings()
        case _:
            raise ValueError(f"Invalid environment: {env}")


# Instantiate Settings (to invoke validation and fail early if misconfigured)
settings: Settings = get_settings()
