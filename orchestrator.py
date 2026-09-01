"""
The loop that ties tasks.py + services.py together.

Polls the SQLite queue, routes each pending task to the right service
tab, waits for the reply, and stores the result back in the DB.

Usage:
    python orchestrator.py                    # visible browser (default)
    python orchestrator.py --headless         # silent background run
    python orchestrator.py --attach           # reuse persistent browser tabs
"""
import argparse
import asyncio

import tasks
from services import LLMBridge

POLL_INTERVAL_S = 5


async def run(headless: bool, attach: bool = False):
    tasks.init_db()
    bridge = LLMBridge()
    await bridge.start(headless=headless, attach=attach)

    print("Bridge running. Waiting for tasks... (Ctrl+C to stop)")
    try:
        while True:
            task = tasks.get_next_pending()
            if task is None:
                await asyncio.sleep(POLL_INTERVAL_S)
                continue

            print(f"[task {task['id']}] -> {task['assigned_to']}: {task['prompt'][:60]}...")
            tasks.mark_in_progress(task["id"])
            try:
                result = await bridge.send_and_wait(task["assigned_to"], task["prompt"])
                tasks.mark_done(task["id"], result)
                print(f"[task {task['id']}] done.")
            except Exception as exc:
                tasks.mark_error(task["id"], str(exc))
                print(f"[task {task['id']}] error: {exc}")
    finally:
        await bridge.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="llm-bridge task loop")
    parser.add_argument("--headless", action="store_true",
                        help="run browsers in the background (no visible window)")
    parser.add_argument("--attach", action="store_true",
                        help="attach to persistent browser (browser_attach.py start)")
    args = parser.parse_args()
    asyncio.run(run(headless=args.headless, attach=args.attach))
