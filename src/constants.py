from enum import StrEnum
from pathlib import Path

# Path Constants
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Environment Enum
class Environment(StrEnum):
    TEST = "TEST"
    DEVELOPMENT = "DEVELOPMENT"
    PRODUCTION = "PRODUCTION"
