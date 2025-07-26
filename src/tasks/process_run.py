import logging
from pathlib import Path

from src.app import huey
from src.services.process import ProcessRunnerService

logger = logging.getLogger(__name__)


@huey.task()
def run_process(
    command: list[str], cwd: Path | None = None, timeout: int | None = None
):
    """
    Huey task to run a subprocess command using ProcessRunnerService.
    """
    runner = ProcessRunnerService(
        cmd=command,
        cwd=cwd,
        timeout=timeout,
        stdout_callback=logger.info,
        stderr_callback=logger.info,
    )
    return runner.run_sync()
