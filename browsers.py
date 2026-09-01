"""
Drives Claude, ChatGPT, and Gemini's normal web chat UIs with Playwright —
same as a human typing and clicking send. No API keys, no requests to
their servers made directly by this script.

SELECTORS BELOW ARE PLACEHOLDERS. Web UIs change their HTML/CSS often —
before first real run, open each site, right-click the input box and the
send button, "Inspect", and copy the real selectors in. Everything else
in this file (the waiting/finished-detection logic) should not need to
change often.
"""
import asyncio
from playwright.async_api import async_playwright, Page

AUTH_DIR = "auth"

SERVICES = {
    "claude": {
        "url": "https://claude.ai/new",
        "state_file": f"{AUTH_DIR}/claude_state.json",
        "input_selector": "div[contenteditable='true']",
        "send_selector": "button[aria-label='Send message']",
        # Element that's visible while a response is still streaming.
        "streaming_selector": "button[aria-label='Stop response']",
        "response_selector": "div.font-claude-message",
    },
    "chatgpt": {
        "url": "https://chatgpt.com/",
        "state_file": f"{AUTH_DIR}/gpt_state.json",
        "input_selector": "#prompt-textarea",
        "send_selector": "button[data-testid='send-button']",
        "streaming_selector": "button[data-testid='stop-button']",
        "response_selector": "div[data-message-author-role='assistant']",
    },
    "gemini": {
        "url": "https://gemini.google.com/app",
        "state_file": f"{AUTH_DIR}/gemini_state.json",
        "input_selector": "div.ql-editor",
        "send_selector": "button[aria-label='Send message']",
        "streaming_selector": "button[aria-label='Stop response']",
        "response_selector": "message-content",
    },
}


class LLMBridge:
    """Holds one persisted browser context + tab per service."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.contexts = {}
        self.pages: dict[str, Page] = {}

    async def start(self, headless: bool = True):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)

        for name, cfg in SERVICES.items():
            # storage_state persists cookies/localStorage between runs —
            # log in manually the first time (see login_setup.py), and
            # these files keep you signed in after that.
            try:
                context = await self.browser.new_context(storage_state=cfg["state_file"])
            except FileNotFoundError:
                context = await self.browser.new_context()
                print(f"[{name}] no saved session yet — you'll need to log in manually first.")

            page = await context.new_page()
            await page.goto(cfg["url"])
            self.contexts[name] = context
            self.pages[name] = page

    async def send_and_wait(self, service: str, prompt: str, timeout_s: int = 120) -> str:
        cfg = SERVICES[service]
        page = self.pages[service]

        await page.click(cfg["input_selector"])
        await page.fill(cfg["input_selector"], prompt)
        await page.click(cfg["send_selector"])

        # 1) Wait for the streaming indicator to appear then disappear —
        #    same signal a human eye uses to know a reply is done.
        try:
            await page.wait_for_selector(cfg["streaming_selector"], state="visible", timeout=5000)
        except Exception:
            pass  # some replies are fast enough that we miss the "visible" window
        await page.wait_for_selector(cfg["streaming_selector"], state="hidden", timeout=timeout_s * 1000)

        # 2) Stability check as a fallback/confirmation — poll the last
        #    response block until its text stops changing.
        last_text = None
        stable_count = 0
        for _ in range(20):
            blocks = await page.query_selector_all(cfg["response_selector"])
            if not blocks:
                await asyncio.sleep(0.5)
                continue
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
        await self.browser.close()
        await self.playwright.stop()
