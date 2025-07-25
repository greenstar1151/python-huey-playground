import argparse
import time
from scripts.benchmark.demo_tasks import add


def enqueue_tasks(n):
    results = []
    for i in range(n):
        result = add(i, i + 1)
        results.append(result)
    return results


def wait_for_results(results, timeout=30):
    start = time.time()
    completed = 0
    for res in results:
        try:
            value = res.get(blocking=True, timeout=timeout)
            if value is not None:
                completed += 1
        except Exception:
            pass
    return completed, time.time() - start


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Huey task enqueueing and processing."
    )
    parser.add_argument(
        "--num-tasks", type=int, default=100, help="Number of tasks to enqueue"
    )
    args = parser.parse_args()
    num_tasks = args.num_tasks

    print(f"Enqueuing {num_tasks} tasks...")
    t0 = time.time()
    results = enqueue_tasks(num_tasks)
    enqueue_time = time.time() - t0
    print(f"Enqueued in {enqueue_time:.2f}s")

    print("Waiting for all tasks to complete...")
    completed, process_time = wait_for_results(results)
    print(f"{completed}/{num_tasks} tasks completed in {process_time:.2f}s")
    print(f"Total time: {enqueue_time + process_time:.2f}s")
    print(f"Throughput: {num_tasks / (enqueue_time + process_time):.2f} tasks/sec")


if __name__ == "__main__":
    main()
