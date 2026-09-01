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
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page

import settings

DEFAULT_DEBUG_URL = "http://127.0.0.1:9222"


class LLMBridge:
    """Holds one persisted browser context + tab per configured service."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.contexts = {}
        self.pages: dict[str, Page] = {}
        self.owned_pages: set[Page] = set()
        self.config = settings.services()
        self.attach_mode = False

    async def start(self, headless: bool = True, attach: bool = False, debug_url: str = DEFAULT_DEBUG_URL):
        settings.auth_dir().mkdir(parents=True, exist_ok=True)
        self.playwright = await async_playwright().start()

        if attach:
            await self._start_attached(debug_url)
            return

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

    async def _start_attached(self, debug_url: str):
        """Attach to a persistent Chrome instance (see browser_attach.py).

        Reuses a tab that's already open on a service's site instead of
        opening a new one, so conversations persist between runs.
        """
        self.attach_mode = True
        try:
            self.browser = await self.playwright.chromium.connect_over_cdp(debug_url)
        except Exception:
            raise RuntimeError(
                f"Could not attach to browser at {debug_url}. "
                "Is it running? Run `python browser_attach.py start` once."
            )

        contexts = self.browser.contexts
        if not contexts:
            raise RuntimeError("Attached browser has no contexts. Open at least one window.")
        context = contexts[0]

        for key, cfg in self.config.items():
            page = self._find_tab(context, cfg["url"])
            if page:
                print(f"[{key}] reusing existing tab: {page.url}")
            else:
                page = await context.new_page()
                await page.goto(cfg["url"])
                self.owned_pages.add(page)
                print(f"[{key}] opened new tab: {cfg['url']}")
            self.contexts[key] = context
            self.pages[key] = page

    @staticmethod
    def _find_tab(context, url: str):
        """Find a tab already open on the same site (by host), else None."""
        expected_host = urlparse(url).netloc
        skip = {"about:blank", "chrome://newtab/", "", "edge://newtab/"}
        for page in context.pages:
            raw = page.url
            if raw in skip:
                continue
            try:
                host = urlparse(raw).netloc
            except Exception:
                host = ""
            if host and host == expected_host:
                return page
        return None

    async def _type_prompt(self, page: Page, cfg, prompt: str):
        """Click the input and type the prompt (works for textarea + contenteditable)."""
        try:
            await page.click(cfg["input_selector"])
            await page.fill(cfg["input_selector"], prompt)
        except Exception:
            # Fallback for widgets where fill() doesn't stick: type per key.
            await page.click(cfg["input_selector"])
            await page.keyboard.press("Control+A")
            await page.keyboard.press_sequentially(prompt, delay=5)

    async def send_and_wait(self, service: str, prompt: str, timeout_s: int = 120) -> str:
        cfg = self.config[service]
        page = self.pages[service]

        await self._type_prompt(page, cfg, prompt)
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

    async def send_and_wait_new(self, service: str, prompt: str, timeout_s: int = 120) -> str:
        """Like send_and_wait, but explicitly grabs the NEW reply.

        In a chained conversation the last response block is the previous
        turn's answer, so we snapshot it before sending, then wait until
        the last block changes from that baseline after the stream ends.
        """
        cfg = self.config[service]
        page = self.pages[service]

        # Snapshot the current last response block as baseline.
        blocks = await page.query_selector_all(cfg["response_selector"])
        baseline = await blocks[-1].inner_text() if blocks else ""

        await self._type_prompt(page, cfg, prompt)
        await page.click(cfg["send_selector"])

        # 1) Wait for the streaming indicator to appear then disappear.
        streaming = cfg.get("streaming_selector")
        if streaming:
            try:
                await page.wait_for_selector(streaming, state="visible", timeout=5000)
            except Exception:
                pass  # too fast to catch "visible"
            await page.wait_for_selector(streaming, state="hidden", timeout=timeout_s * 1000)

        # 2) Poll until the last block differs from baseline and is stable.
        return await self._wait_new_stable(page, service, baseline, timeout_s)

    async def _wait_new_stable(self, page: Page, service: str, baseline: str, timeout_s: int) -> str:
        cfg = self.config[service]
        last_text = None
        stable_count = 0
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            blocks = await page.query_selector_all(cfg["response_selector"])
            if not blocks:
                await asyncio.sleep(0.5)
                continue
            text = await blocks[-1].inner_text()
            if text == baseline:
                # new reply not visible yet
                await asyncio.sleep(0.5)
                continue
            if text == last_text:
                stable_count += 1
                if stable_count >= 2:
                    return text
            else:
                stable_count = 0
            last_text = text
            await asyncio.sleep(0.5)
        return last_text or ""

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
        if self.attach_mode:
            # In attach mode this is the user's own persistent browser.
            # Only close tabs WE opened; never the user's other tabs.
            for page in self.owned_pages:
                try:
                    await page.close()
                except Exception:
                    pass
            await self.playwright.stop()
            return
        for context in self.contexts.values():
            await context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
