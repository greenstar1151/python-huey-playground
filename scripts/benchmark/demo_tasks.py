from pathlib import Path
from huey import SqliteHuey
import anyio

PROJECT_ROOT = Path(__file__).parent

huey = SqliteHuey(filename=PROJECT_ROOT / "demo_task.db")


@huey.task()
def add(a, b):
    async def run_subprocess():
        proc = await anyio.open_process(["sleep", "0.1"])
        async with proc:
            await proc.wait()
        # CPU-bound work: sum of squares up to 100,000
        cpu_work = sum(i * i for i in range(100_000))
        return a + b + cpu_work

    return anyio.run(run_subprocess)
