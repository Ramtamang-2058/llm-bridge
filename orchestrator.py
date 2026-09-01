"""
The loop that ties queue.py + browsers.py together.

Runs headless in the background by default — a completely separate
browser process from whatever you're using for YouTube etc., so it
never touches or steals focus from your normal browsing.
"""
import asyncio
import queue as taskqueue
from browsers import LLMBridge


POLL_INTERVAL_S = 5


async def run(headless: bool = True):
    taskqueue.init_db()
    bridge = LLMBridge()
    await bridge.start(headless=headless)

    print("Bridge running. Waiting for tasks...")
    try:
        while True:
            task = taskqueue.get_next_pending()
            if task is None:
                await asyncio.sleep(POLL_INTERVAL_S)
                continue

            print(f"[task {task['id']}] -> {task['assigned_to']}: {task['prompt'][:60]}...")
            taskqueue.mark_in_progress(task["id"])
            try:
                result = await bridge.send_and_wait(task["assigned_to"], task["prompt"])
                taskqueue.mark_done(task["id"], result)
                print(f"[task {task['id']}] done.")
            except Exception as e:
                taskqueue.mark_error(task["id"], str(e))
                print(f"[task {task['id']}] error: {e}")
    finally:
        await bridge.stop()


if __name__ == "__main__":
    # headless=False the first few runs so you can watch it click/type
    # and fix selectors if a site's HTML doesn't match what's in browsers.py.
    asyncio.run(run(headless=False))
