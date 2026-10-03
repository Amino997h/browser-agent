import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from browser_manager import BrowserManager
from agent import BrowserAgent
from history_logger import HistoryLogger

load_dotenv()
app = FastAPI()

@app.get("/")
async def get():
    with open(os.path.join("templates", "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    browser_manager = None
    try:
        data = await websocket.receive_text()
        request_data = json.loads(data)
        goal = request_data.get("goal")
        
        agent = BrowserAgent()
        
        await websocket.send_text(json.dumps({
            "type": "agent", 
            "command": {"action": "determine_start_url"}
        }))
        
        start_url = agent.determine_starting_url(goal)
        await websocket.send_text(json.dumps({
            "type": "action", 
            "result": f"تم تحديد الرابط الأولي: {start_url}"
        }))
        
        browser_manager = BrowserManager()
        logger = HistoryLogger()
        
        await browser_manager.start(headless=False)
        await websocket.send_text(json.dumps({"type": "status", "status": "RUNNING", "url": start_url}))
        
        await browser_manager.execute_command({"command": "navigate", "url": start_url})
        step = 1
        
        latest_user_feedback = ""
        
        while True:
            page_info = await browser_manager.scrape_page()
            elements_count = len(page_info.links) + len(page_info.buttons) + len(page_info.inputs)
            
            await websocket.send_text(json.dumps({"type": "status", "status": "RUNNING", "url": page_info.url}))
            await websocket.send_text(json.dumps({"type": "browser", "elements": elements_count}))
            
            history_summary = logger.get_history_summary()
            
            command = agent.determine_next_action(goal, page_info, history_summary, latest_user_feedback)
            
            latest_user_feedback = ""
            
            await websocket.send_text(json.dumps({
                "type": "agent", 
                "command": command
            }))
            
            cmd_type = command.get("command")
            
            if cmd_type == "ask_user" or cmd_type == "wait_for_user":
                question = command.get("question") or command.get("message") or "الرجاء التدخل أو الإجابة على السؤال:"
                input_type = command.get("input_type", "text")
                options = command.get("options", [])
                
                logger.log_step(step, command, page_info.url)
                await websocket.send_text(json.dumps({"type": "status", "status": "WAITING_USER", "url": page_info.url}))
                
                await websocket.send_text(json.dumps({
                    "type": "ask_user",
                    "question": question,
                    "input_type": input_type,
                    "options": options
                }))
                
                while True:
                    response_data = await websocket.receive_text()
                    parsed = json.loads(response_data)
                    if parsed.get("action") == "user_response":
                        latest_user_feedback = parsed.get("answer", "تم بواسطة المستخدم")
                        break
                
                await websocket.send_text(json.dumps({"type": "action", "result": f"إجابة المستخدم: {latest_user_feedback}"}))
                await websocket.send_text(json.dumps({"type": "status", "status": "RUNNING", "url": page_info.url}))
                step += 1
                continue

            if cmd_type == "finish":
                status = command.get("status", "success")
                msg = command.get("message", "تم الانتهاء")
                logger.log_step(step, command, page_info.url)
                
                final_state = "SUCCESS" if status == "success" else "FAILED"
                
                # إرسال النتيجة النهائية ككتلة واضحة للواجهة
                await websocket.send_text(json.dumps({"type": "final_result", "status": final_state, "message": msg}))
                await websocket.send_text(json.dumps({"type": "status", "status": final_state, "url": page_info.url}))
                break
            
            result = await browser_manager.execute_command(command)
            await websocket.send_text(json.dumps({"type": "action", "result": result}))
            
            logger.log_step(step, command, page_info.url)
            step += 1
            
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
    finally:
        if browser_manager:
            await browser_manager.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
