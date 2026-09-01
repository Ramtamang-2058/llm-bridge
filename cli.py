"""
Command-line tool for the task queue.

Usage:
    python cli.py add <service> "<prompt>"     # add a task
    python cli.py list [--status pending]      # view tasks
    python cli.py run [--headless]             # start the orchestrator loop
    python cli.py chain "<goal>" s1 s2 s3      # auto-chain through services
"""
import argparse
import asyncio
import sys

import settings
import tasks


def _service_keys():
    return list(settings.services().keys())


def cmd_add(args):
    tasks.init_db()
    key = args.service
    if key not in settings.services():
        print(f"Unknown service '{key}'. Choose from: {_service_keys()}")
        sys.exit(1)
    task_id = tasks.add_task(key, args.prompt)
    print(f"Added task #{task_id} -> {key}. Prompt: {args.prompt}")


def cmd_list(args):
    tasks.init_db()
    rows = tasks.list_tasks(limit=args.limit, status=args.status)
    if not rows:
        print("No tasks found.")
        return
    for r in rows:
        result_snippet = (r["result"] or "")[:60].replace("\n", " ")
        print(f"#{r['id']:<4} [{r['status']:<11}] {r['assigned_to']:<8} | {r['prompt'][:50]}")
        if result_snippet:
            print(f"     -> {result_snippet}")


def cmd_run(args):
    import orchestrator
    asyncio.run(orchestrator.run(headless=args.headless, attach=args.attach))


def cmd_chain(args):
    import chain
    try:
        chain.validate_route(args.route)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    asyncio.run(chain.run_chain(args.goal, args.route, headless=args.headless, attach=args.attach))


def build_parser():
    parser = argparse.ArgumentParser(prog="cli.py", description="llm-bridge task queue CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="add a task")
    p_add.add_argument("service", help=f"service key: {_service_keys()}")
    p_add.add_argument("prompt", help="prompt text")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="view tasks")
    p_list.add_argument("--status", default=None, help="filter by status")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(func=cmd_list)

    p_run = sub.add_parser("run", help="run the orchestrator loop")
    p_run.add_argument("--headless", action="store_true")
    p_run.add_argument("--attach", action="store_true", help="reuse persistent browser tabs")
    p_run.set_defaults(func=cmd_run)

    p_chain = sub.add_parser("chain", help="auto-chain one goal through services")
    p_chain.add_argument("goal", help="the goal / prompt to start with")
    p_chain.add_argument("route", nargs="+", help=f"ordered service keys: {_service_keys()}")
    p_chain.add_argument("--headless", action="store_true")
    p_chain.add_argument("--attach", action="store_true", help="reuse persistent browser tabs")
    p_chain.set_defaults(func=cmd_chain)

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
