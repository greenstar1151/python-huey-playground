from huey import SqliteHuey

from .config import settings


def add_tasks() -> None:
    from src import tasks  # noqa: F401


huey = SqliteHuey(filename=settings.HUEY_DB_PATH)
add_tasks()
