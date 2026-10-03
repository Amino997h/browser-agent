import asyncio
import os
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Page, BrowserContext
from models import ScrapedPageInfo, ScrapedElement

# متغيرات عامة (Global) للحفاظ على المتصفح مفتوحاً دائماً بين المهام المختلفة
_global_playwright = None
_global_context = None

class BrowserManager:
    def __init__(self):
        self.page: Optional[Page] = None

    async def start(self, headless: bool = False):
        global _global_playwright, _global_context
        
        # إذا لم يكن المتصفح مفتوحاً مسبقاً، قم بفتحه مرة واحدة فقط
        if _global_context is None:
            _global_playwright = await async_playwright().start()
            user_data_dir = os.path.join(os.getcwd(), "agent_profile")
            
            browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
            
            try:
                _global_context = await _global_playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=headless,
                    channel="chrome",
                    args=browser_args,
                    viewport={'width': 1280, 'height': 800}
                )
            except Exception:
                try:
                    _global_context = await _global_playwright.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=headless,
                        channel="msedge",
                        args=browser_args,
                        viewport={'width': 1280, 'height': 800}
                    )
                except Exception:
                    _global_context = await _global_playwright.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=headless,
                        args=browser_args,
                        viewport={'width': 1280, 'height': 800}
                    )
                    
        # اختيار نافذة (Tab) جديدة للمهمة
        # إذا كانت هناك نافذة واحدة فقط فارغة (عند التشغيل لأول مرة)، نستخدمها
        if len(_global_context.pages) == 1 and _global_context.pages[0].url == "about:blank":
            self.page = _global_context.pages[0]
        else:
            # عدا ذلك نفتح نافذة (Tab) جديدة تماماً لكل مهمة جديدة
            self.page = await _global_context.new_page()
            await self.page.bring_to_front()

    async def close(self):
        # تم إلغاء كود الإغلاق!
        # المتصفح سيبقى مفتوحاً لتتمكن من رؤية النتيجة النهائية
        # ولن يغلق إلا إذا قمت بإغلاق نافذة السيرفر (الشاشة السوداء) يدوياً.
        pass

    async def execute_command(self, command: Dict[str, Any]) -> str:
        if not self.page:
            return "Error: Page is not initialized."
            
        cmd = command.get("command")
        try:
            if cmd == "navigate":
                await self.page.goto(command["url"], wait_until="domcontentloaded", timeout=15000)
                return f"Navigated to {command['url']}"
            
            elif cmd == "back":
                await self.page.go_back(wait_until="domcontentloaded", timeout=15000)
                return "Navigated back"
                
            elif cmd == "click":
                selector = command["selector"]
                await self.page.click(selector, timeout=5000)
                await self.page.wait_for_timeout(2000)
                return f"Clicked element: {selector}"
                
            elif cmd == "type":
                selector = command["selector"]
                text = command["text"]
                await self.page.fill(selector, text, timeout=5000)
                return f"Typed '{text}' into {selector}"
                
            elif cmd == "select":
                selector = command["selector"]
                value = command["value"]
                await self.page.select_option(selector, value, timeout=5000)
                return f"Selected '{value}' in {selector}"
                
            return f"Unknown or unhandled command: {cmd}"
        except Exception as e:
            return f"Action failed: {str(e)}"

    async def scrape_page(self) -> ScrapedPageInfo:
        if not self.page:
            raise Exception("Page not initialized")

        js_script = """
        () => {
            let elements = document.querySelectorAll('a, button, input, select, textarea, [role="button"]');
            let links = [];
            let buttons = [];
            let inputs = [];
            
            let idCounter = 1;
            elements.forEach(el => {
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || el.offsetParent === null) return;
                
                let agentId = el.getAttribute('data-agent-id');
                if (!agentId) {
                    agentId = idCounter.toString();
                    el.setAttribute('data-agent-id', agentId);
                    idCounter++;
                }
                
                const selector = `[data-agent-id="${agentId}"]`;
                const tagName = el.tagName.toLowerCase();
                const text = el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '';
                
                const elementData = {
                    text: text.trim().substring(0, 50),
                    selector: selector,
                    type: tagName
                };
                
                if (tagName === 'a') links.push(elementData);
                else if (tagName === 'button' || el.getAttribute('role') === 'button') buttons.push(elementData);
                else if (['input', 'select', 'textarea'].includes(tagName)) inputs.push(elementData);
            });
            
            let texts = [];
            document.querySelectorAll('h1, h2, h3, p').forEach(el => {
                 const style = window.getComputedStyle(el);
                 if (style.display !== 'none' && style.visibility !== 'hidden') {
                     texts.push(el.innerText.trim().substring(0, 100));
                 }
            });
            
            return {
                url: window.location.href,
                title: document.title,
                links: links.filter(l => l.text),
                buttons: buttons.filter(b => b.text),
                inputs: inputs,
                texts: texts.filter(t => t.trim().length > 0)
            };
        }
        """
        
        data = await self.page.evaluate(js_script)
        return ScrapedPageInfo(**data)
