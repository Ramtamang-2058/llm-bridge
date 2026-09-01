"""
Run this ONCE per service (or whenever a session expires).
Opens a real, visible browser window so you can log in by hand —
solving 2FA/CAPTCHAs yourself — then saves the session so future
runs start already logged in.

Usage:
    python login_setup.py claude
    python login_setup.py chatgpt
    python login_setup.py gemini
"""
import asyncio
import os
import sys
from playwright.async_api import async_playwright
from browsers import SERVICES, AUTH_DIR


async def main(service: str):
    if service not in SERVICES:
        print(f"Unknown service '{service}'. Choose from: {list(SERVICES)}")
        return

    os.makedirs(AUTH_DIR, exist_ok=True)
    cfg = SERVICES[service]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(cfg["url"])

        print(f"\nLog into {service} in the opened window.")
        input("Once you're fully logged in and see the chat screen, press Enter here... ")

        await context.storage_state(path=cfg["state_file"])
        print(f"Saved session to {cfg['state_file']}")
        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python login_setup.py <claude|chatgpt|gemini>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
