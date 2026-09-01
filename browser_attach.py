"""
Launch a persistent Chrome instance for llm-bridge to attach to, so you
don't open a new browser on every call.

This browser uses its OWN profile directory (browser_profile/), starts
once with a debug port, and stays open between runs. Subsequent runs
attach to the still-running instance and REUSE its existing tabs —
conversations persist. Login to each service once in this window and
you stay logged in forever (it's git-ignored).

Usage:
    python browser_attach.py start      # launch it once (opens a window)
    python browser_attach.py status     # check if it's running/attachable
    python browser_attach.py stop       # close it (optional; a window stays open)
    python browser_attach.py --all      # open all service tabs after start
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request

import settings

PORT = 9222
DEBUG_URL = f"http://127.0.0.1:{PORT}"
PROFILE_DIR = settings.root_path("browser_profile")

# --remote-debugging-port only works when the instance has its own
# user-data-dir; otherwise Chrome forwards to the existing instance and
# ignores the flag, so we ALWAYS use a dedicated profile.
CHROME_CANDIDATES = {
    "linux": [
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
        "microsoft-edge", "microsoft-edge-stable", "brave-browser", "brave",
    ],
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ],
    "win32": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ],
}

# Snap-specific paths (Brave via snap is common on Ubuntu).
SNAP_BINARIES = [
    "/snap/bin/brave",
    "/snap/bin/chromium",
    "/snap/bin/google-chrome",
]


def find_chrome():
    # 1) Standard PATH candidates.
    if sys.platform in CHROME_CANDIDATES and sys.platform != "linux":
        for path in CHROME_CANDIDATES[sys.platform]:
            if os.path.exists(path):
                return path
    for name in CHROME_CANDIDATES.get("linux", []):
        found = shutil.which(name)
        if found:
            return found

    # 2) Snap binaries (common on Ubuntu).
    for path in SNAP_BINARIES:
        if os.path.exists(path):
            return path

    # 3) Playwright's own bundled Chromium — guaranteed to exist after
    #    `playwright install chromium` and supports --remote-debugging-port.
    playwright_dir = os.path.expanduser("~/.cache/ms-playwright")
    if os.path.isdir(playwright_dir):
        for folder in sorted(os.listdir(playwright_dir), reverse=True):
            if not folder.startswith("chromium-") or "headless" in folder:
                continue
            candidate = os.path.join(playwright_dir, folder, "chrome-linux64", "chrome")
            if os.path.isfile(candidate):
                return candidate

    return None


def is_alive():
    try:
        with urllib.request.urlopen(f"{DEBUG_URL}/json/version", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def open_service_tabs():
    import asyncio
    from services import LLMBridge

    async def _open():
        bridge = LLMBridge()
        try:
            await bridge.start(attach=True)
            print("Service tabs ensured. You can close this and keep browsing; "
                  "the tabs stay attached for future runs.")
            await asyncio.sleep(2)
        finally:
            await bridge.stop()

    asyncio.run(_open())


def cmd_start(open_tabs: bool):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    if is_alive():
        print(f"Already running & attachable at {DEBUG_URL}")
        if open_tabs:
            open_service_tabs()
        return

    chrome = find_chrome()
    if not chrome:
        print("Could not find Chrome/Edge/Brave. Install one and re-run.")
        sys.exit(1)

    print(f"Launching persistent browser: {chrome}")
    print("  profile:", PROFILE_DIR)
    cmd = [
        chrome,
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    flags = subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)

    print("Waiting for debug port...")
    for _ in range(15):
        time.sleep(0.5)
        if is_alive():
            print("Ready.")
            if open_tabs:
                open_service_tabs()
            print("\nNext: log into each service in the opened window.")
            print("Then run:  python cli.py chain 'your goal' gemini claude chatgpt --attach")
            print("  (add --attach to reuse these tabs instead of launching a new browser)")
            return
    print("Timed out waiting for the browser. Try `start` again.")
    sys.exit(1)


def cmd_status():
    if is_alive():
        print(f"Attached browser is running at {DEBUG_URL}")
    else:
        print(f"No browser running at {DEBUG_URL}. Run `python browser_attach.py start`.")


def cmd_stop():
    if not is_alive():
        print("Not running.")
        return
    try:
        # Closing via CDP: play a wake-up then close the connection gracefully.
        subprocess.Popen(["python", "-c",
                          "import urllib.request; urllib.request.urlopen"
                          f"('{DEBUG_URL}/json/close')"])
    except Exception:
        pass
    print("Sent close request. If the window stays, just close it manually.")


def main():
    parser = argparse.ArgumentParser(description="llm-bridge persistent browser")
    parser.add_argument("command", choices=["start", "status", "stop"], nargs="?", default="status")
    parser.add_argument("--all", action="store_true", help="open/ensure all service tabs after start")
    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args.all)
    elif args.command == "status":
        cmd_status()
    elif args.command == "stop":
        cmd_stop()


if __name__ == "__main__":
    main()