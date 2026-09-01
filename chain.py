"""
Auto-chain: send one goal through a route of services, feeding each
reply into the next, and return the final answer.

    cli.py chain "plan our launch" gemini claude chatgpt

Sends the goal to gemini, takes its reply, sends that to claude,
takes that reply, sends it to chatgpt, and prints the final result.
Fully automatic once you've logged in.
"""
import asyncio

import settings


def validate_route(route):
    available = list(settings.services().keys())
    unknown = [s for s in route if s not in settings.services()]
    if unknown:
        raise ValueError(f"Unknown service(s) {unknown}. Available: {available}")
    if len(route) < 1:
        raise ValueError("Route must have at least one service")


async def chain(bridge, goal: str, route, timeout_s: int = 120) -> str:
    """Send `goal` through `route`, chaining replies. Returns final text."""
    validate_route(route)

    prompt = goal
    transcript = []  # human-readable record of each hop

    for step, service in enumerate(route):
        print(f"[chain step {step + 1}/{len(route)}] -> {service}")
        reply = await bridge.send_and_wait_new(service, prompt, timeout_s=timeout_s)
        prompt = reply
        transcript.append({"service": service, "reply": reply})
        print(f"    {service} replied ({len(reply)} chars)")

    return transcript


async def run_chain(goal: str, route, headless: bool = True, attach: bool = False) -> str:
    from services import LLMBridge

    # Validate before launching a browser.
    validate_route(route)

    bridge = LLMBridge()
    try:
        await bridge.start(headless=headless, attach=attach)
        transcript = await chain(bridge, goal, route)
    finally:
        await bridge.stop()

    print("\n===== FINAL RESULT =====")
    last = transcript[-1]["reply"]
    print(last)

    # Save the full transcript to the task queue as a record too.
    import tasks

    tasks.init_db()
    task_id = tasks.add_task("_chain", f"{goal} | route: {' -> '.join(route)}")
    tasks.mark_done(task_id, _format_transcript(transcript))
    print(f"\n(saved transcript to task #{task_id})")
    return last


def _format_transcript(transcript) -> str:
    parts = []
    for entry in transcript:
        parts.append(f"--- {entry['service']} ---\n{entry['reply']}")
    return "\n\n".join(parts)
