"""
Run this ONCE per service (or whenever a session expires).
Opens a real, visible browser window so you can log in by hand —
solving 2FA/CAPTCHAs yourself — then saves the session so future
runs start already logged in.

Usage:
    python login_setup.py [service]     # e.g. python login_setup.py claude
    python login_setup.py --all          # do every service in config.json
"""
import asyncio
import sys
from playwright.async_api import async_playwright

import settings


def _services_to_login(argv):
    if "--all" in argv:
        return list(settings.services().keys())
    for arg in argv:
        if arg in settings.services():
            return [arg]
    return None


async def login_service(page, key, cfg, base_dir):
    print(f"\n>>> Logging in to {cfg.get('name', key)} ({cfg['url']})")
    await page.goto(cfg["url"])
    input("Log in and click 'Send' once in the window. Then press Enter here... ")
    state = settings.state_file_for(key)
    await page.context.storage_state(path=str(state))
    print(f"    saved session -> {state}")


async def main(argv):
    targets = _services_to_login(argv)
    if not targets:
        print("Usage: python login_setup.py <service> | --all")
        print(f"Services: {list(settings.services().keys())}")
        return

    settings.auth_dir().mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        for key in targets:
            await login_service(page, key, settings.services()[key], settings.auth_dir())
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
