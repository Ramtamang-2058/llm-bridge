"""
Drives the chat web UIs listed in config.json (Claude, ChatGPT, Gemini...)
with Playwright — same as a human typing and clicking send. No API keys
and no direct requests to their servers from this script.

Service config (URLs, selectors) comes from config.json via settings.py,
so adding a new service is just a config edit — no code change.

The selectors are placeholders and web UIs change their HTML often.
Before first real run: open each site, right-click the input box and the
send button, "Inspect", and paste the real selectors into config.json.
"""
import asyncio

from playwright.async_api import async_playwright, Page

import settings


class LLMBridge:
    """Holds one persisted browser context + tab per configured service."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.contexts = {}
        self.pages: dict[str, Page] = {}
        self.config = settings.services()

    async def start(self, headless: bool = True):
        settings.auth_dir().mkdir(parents=True, exist_ok=True)
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)

        for key, cfg in self.config.items():
            state = settings.state_file_for(key)
            # storage_state persists cookies/localStorage between runs —
            # log in manually the first time (see login_setup.py), and
            # these files keep you signed in after that.
            if state.exists():
                context = await self.browser.new_context(storage_state=str(state))
            else:
                context = await self.browser.new_context()
                print(f"[{key}] no saved session yet — run login_setup.py {key}")

            page = await context.new_page()
            await page.goto(cfg["url"])
            self.contexts[key] = context
            self.pages[key] = page

    async def send_and_wait(self, service: str, prompt: str, timeout_s: int = 120) -> str:
        cfg = self.config[service]
        page = self.pages[service]

        await page.click(cfg["input_selector"])
        await page.fill(cfg["input_selector"], prompt)
        await page.click(cfg["send_selector"])

        # 1) Wait for the streaming indicator to appear then disappear —
        #    the same signal a human eye uses to know a reply is done.
        streaming = cfg.get("streaming_selector")
        if streaming:
            try:
                await page.wait_for_selector(streaming, state="visible", timeout=5000)
            except Exception:
                pass  # some replies are fast enough that we miss "visible"
            await page.wait_for_selector(streaming, state="hidden", timeout=timeout_s * 1000)

        # 2) Stability check as fallback/confirmation — poll the last
        #    response block until its text stops changing.
        return await self._wait_stable(page, service, timeout_s)

    async def _wait_stable(self, page: Page, service: str, timeout_s: int) -> str:
        cfg = self.config[service]
        last_text = None
        stable_count = 0
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            blocks = await page.query_selector_all(cfg["response_selector"])
            if blocks:
                text = await blocks[-1].inner_text()
                if text == last_text:
                    stable_count += 1
                    if stable_count >= 2:
                        return text
                else:
                    stable_count = 0
                last_text = text
            await asyncio.sleep(0.5)
        return last_text or ""

    async def stop(self):
        for context in self.contexts.values():
            await context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
