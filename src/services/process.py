import inspect
import io
import logging
import sys
from asyncio import TimeoutError
from pathlib import Path
from typing import Any, Callable

import anyio
from anyio.abc import Process
from anyio.streams.text import TextReceiveStream

logger = logging.getLogger(__name__)


class ProcessTimeoutError(Exception):
    """Raised when a process times out."""

    pass


class ProcessRunnerService:
    """Service for running subprocess commands asynchronously with real-time output handling.

    This service provides a high-level interface for running subprocess commands
    with support for:
    - Real-time stdout/stderr callbacks
    - Process timeout handling
    - Graceful process termination
    - Output history capture
    """

    def __init__(
        self,
        cmd: list[str],
        cwd: Path = Path(),
        stdout_callback: Callable[[str], Any] | None = None,
        stderr_callback: Callable[[str], Any] | None = None,
        timeout: float | None = None,
        terminate_grace_period: float = 10.0,
    ):
        """Initialize the ProcessRunnerService.

        Args:
            cmd: Command and arguments as a list of strings
            cwd: Working directory for the process
            stdout_callback: Optional callback for stdout text chunks
            stderr_callback: Optional callback for stderr text chunks
            timeout: Optional timeout in seconds for process execution
            terminate_grace_period: Grace period in seconds for graceful termination (default: 10.0)
        """
        self.cmd = cmd
        self.cwd = cwd
        self.stdout_callback = stdout_callback
        self.stderr_callback = stderr_callback
        self.timeout = timeout
        self.terminate_grace_period = terminate_grace_period
        self._stdout_history: io.StringIO = io.StringIO()
        self._stderr_history: io.StringIO = io.StringIO()
        self._process: Process | None = None

    async def _handle_stream(
        self,
        stream: TextReceiveStream,
        callback: Callable[[str], Any] | None,
        buffer: io.StringIO,
    ) -> None:
        """Read from the stream, invoke the callback on each text chunk, and store the text."""
        try:
            async for text in stream:
                if callback:
                    try:
                        # If the callback is asynchronous, await it directly.
                        if inspect.iscoroutinefunction(callback):
                            await callback(text)
                        else:
                            # Run sync callback in a thread to avoid blocking
                            await anyio.to_thread.run_sync(callback, text)  # type: ignore
                    except Exception as e:
                        # Log callback errors but don't stop stream processing
                        logger.warning("Callback error: %s", e, exc_info=True)
                buffer.write(text)
        except anyio.EndOfStream:
            pass

    async def terminate(self) -> None:
        """Gracefully terminate the process."""
        if self._process:
            logger.debug(
                "Terminating process gracefully (grace period: %ss)",
                self.terminate_grace_period,
            )
            self._process.terminate()
            try:
                with anyio.fail_after(self.terminate_grace_period):
                    await self._process.wait()
                logger.debug("Process terminated gracefully")
            except TimeoutError:
                logger.warning(
                    "Graceful termination failed after %ss, force killing process",
                    self.terminate_grace_period,
                )
                self._process.kill()  # Force kill if graceful shutdown fails

    async def run(self, **kwargs: Any) -> tuple[int | None, str, str]:
        """Run the process and capture its output.

        Returns:
            A tuple containing the process return code, stdout, and stderr.

        Raises:
            ProcessTimeoutError: If the process does not complete within the allotted timeout.
        """
        logger.debug(
            "Starting process: %s (cwd=%s, timeout=%s)",
            self.cmd,
            self.cwd,
            self.timeout,
        )

        # Reinitialize the output buffers for each run.
        self._stdout_history = io.StringIO()
        self._stderr_history = io.StringIO()

        try:
            async with await anyio.open_process(
                self.cmd, cwd=self.cwd, **kwargs
            ) as process:
                self._process = process
                is_timed_out = False
                try:
                    async with anyio.create_task_group() as tg:
                        if process.stdout is not None:
                            tg.start_soon(
                                self._handle_stream,
                                TextReceiveStream(process.stdout),
                                self.stdout_callback,
                                self._stdout_history,
                            )
                        if process.stderr is not None:
                            tg.start_soon(
                                self._handle_stream,
                                TextReceiveStream(process.stderr),
                                self.stderr_callback,
                                self._stderr_history,
                            )

                        try:
                            if self.timeout is not None:
                                with anyio.fail_after(self.timeout):
                                    await process.wait()
                            else:
                                await process.wait()
                        except TimeoutError:
                            logger.warning(
                                "Process timeout reached (%ss), terminating process",
                                self.timeout,
                            )
                            await self.terminate()
                            is_timed_out = True

                # Suppress the CancelledError exceptions coming from the child tasks.
                except* anyio.get_cancelled_exc_class():
                    pass

                if is_timed_out:
                    logger.error("Process timed out after %s seconds", self.timeout)
                    raise ProcessTimeoutError(
                        f"Process timed out after {self.timeout} seconds"
                    )

                logger.debug(
                    "Process completed with return code: %s", process.returncode
                )
                return process.returncode, self.stdout, self.stderr
        finally:
            self._process = None

    def run_sync(self, **kwargs: Any) -> tuple[int | None, str, str]:
        """Wrapper for self.run() to run synchronously."""
        return anyio.run(self.run, **kwargs)

    @property
    def stdout(self) -> str:
        return self._stdout_history.getvalue()

    @property
    def stderr(self) -> str:
        return self._stderr_history.getvalue()

    @property
    def is_running(self) -> bool:
        """Check if the process is currently running."""
        return self._process is not None

    def clear_history(self) -> None:
        """Clear the captured stdout and stderr history."""
        self._stdout_history = io.StringIO()
        self._stderr_history = io.StringIO()


if __name__ == "__main__":
    import sys

    # Configure logging for the demo
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"

    def stdout_colorized(text: str) -> None:
        sys.stdout.write(f"{GREEN}stdout{RESET} | {text}")

    def stderr_colorized(text: str) -> None:
        sys.stdout.write(f"{RED}stderr{RESET} | {text}")

    async def run_wrapper(cmd: list[str], timeout: float | None = None) -> None:
        try:
            runner = ProcessRunnerService(
                cmd,
                stdout_callback=stdout_colorized,
                stderr_callback=stderr_colorized,
                timeout=timeout,
            )
            print(f"{'Running: ' + str(cmd) + ' | Timeout=' + str(timeout):=^80}")
            return_code, stdout, stderr = await runner.run()
            print(f"Return Code: {return_code}")
            print(f"STDOUT size: {len(stdout)}")
            print(f"STDERR size: {len(stderr)}")
        except ProcessTimeoutError as e:
            print(f"{RED}Timeout Error: {e}{RESET}")
        finally:
            print("=" * 80)

    async def main():
        await run_wrapper(["echo", "hello"])
        await run_wrapper(["sleep", "5"], timeout=1)

    anyio.run(main)
