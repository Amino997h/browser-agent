import os
import json
import re
from openai import OpenAI
from models import ScrapedPageInfo, AgentCommand, StartingUrlResponse
from typing import Dict, Any

SYSTEM_PROMPT = """You are a browser automation agent.
Your goal is to achieve the user's task by interacting with web pages.
You MUST output ONLY a valid JSON object. No markdown, no conversational text.
CRITICAL RULE: NEVER use markdown links like [text](url) or [email](mailto:email) inside the JSON. Always use raw strings.
"""

class BrowserAgent:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "sk-chatgpt-local-secret-key")
        base_url = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8008/v1")
        self.model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
            
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = text.replace('"/}', '"}').replace('"}](', '"}')
        
        return text.strip()

    def determine_starting_url(self, goal: str) -> str:
        prompt = f"""Goal: {goal}

You must determine the starting URL to achieve this goal.
CRITICAL RULE: YOU MUST COPY THIS EXACT FORMAT. DO NOT ADD BRACKETS [ ]. JUST THE RAW URL.

EXAMPLE OF REQUIRED FORMAT:
{{"url": "https://www.google.com"}}

OUTPUT EXACTLY LIKE THE EXAMPLE ABOVE (WITH YOUR TARGET URL):"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You determine the best starting URL for a web task. Return a valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            content = response.choices[0].message.content
            cleaned = self._clean_json(content)
            
            parsed = json.loads(cleaned)
            url = parsed.get("url", "https://www.google.com")
            
            if not url.startswith("http"):
                url = "https://" + url
                
            return url
        except Exception as e:
            return "https://www.google.com"

    def determine_next_action(self, goal: str, page_info: ScrapedPageInfo, history_summary: str, user_feedback: str = "") -> Dict[str, Any]:
        prompt = f"""
Goal: {goal}
Current URL: {page_info.url}
Page Title: {page_info.title}

--- Scraped Page Elements ---
Links: {json.dumps([l.model_dump() for l in page_info.links], ensure_ascii=False)}
Buttons: {json.dumps([b.model_dump() for b in page_info.buttons], ensure_ascii=False)}
Inputs: {json.dumps([i.model_dump() for i in page_info.inputs], ensure_ascii=False)}

--- Recent Texts on Page ---
{json.dumps(page_info.texts, ensure_ascii=False)}

--- Action History ---
{history_summary}

--- Recent User Feedback ---
{user_feedback if user_feedback else 'No feedback.'}

Based on the goal and current state, what is the next step?
CRITICAL INSTRUCTION: You must choose EXACTLY ONE action and COPY ITS EXACT FORMAT from the examples below. 
NEVER use Markdown for emails or links.

IF YOU WANT TO NAVIGATE:
{{"command": "navigate", "url": "https://example.com"}}

IF YOU WANT TO TYPE:
{{"command": "type", "selector": "[data-agent-id='1']", "text": "text to type"}}

IF YOU WANT TO CLICK:
{{"command": "click", "selector": "[data-agent-id='2']", "description": "click button"}}

IF YOU WANT TO GO BACK:
{{"command": "back"}}

IF YOU NEED TEXT INPUT FROM THE USER (e.g. 2FA Code, OTP, Email):
{{"command": "ask_user", "question": "Please enter the 2FA code from your phone", "input_type": "text"}}

IF YOU NEED THE USER TO CHOOSE AN OPTION (e.g. What to do next?):
{{"command": "ask_user", "question": "How should I verify?", "input_type": "options", "options": ["Option 1", "Option 2"]}}

IF THE GOAL IS DONE:
{{"command": "finish", "status": "success", "message": "banana"}}

IF YOU GIVE UP:
{{"command": "finish", "status": "failed", "message": "apple"}}

OUTPUT YOUR JSON NOW:
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            cleaned = self._clean_json(content)
            command_json = json.loads(cleaned)
            
            if "url" in command_json and "command" not in command_json:
                command_json = {"command": "navigate", "url": command_json["url"]}
                
            return command_json
        except json.JSONDecodeError as e:
            return {"command": "finish", "status": "failed", "message": "apple", "description": "LLM failed to output JSON"}
        except Exception as e:
            return {"command": "finish", "status": "failed", "message": "apple", "description": f"API Error: {str(e)}"}
