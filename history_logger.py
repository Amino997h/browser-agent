import json
import os
from typing import List, Dict, Any
from datetime import datetime

class HistoryLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.json_file = os.path.join(log_dir, f"history_{timestamp}.json")
        self.text_file = os.path.join(log_dir, f"execution_log_{timestamp}.txt")
        self.history: List[Dict[str, Any]] = []

    def log_step(self, step_num: int, command_data: Dict[str, Any], url: str):
        entry = {
            "step": step_num,
            "url": url,
            "command": command_data,
            "timestamp": datetime.now().isoformat()
        }
        self.history.append(entry)
        
        # Write JSON
        with open(self.json_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
            
        # Write Text format (as requested by user)
        with open(self.text_file, "a", encoding="utf-8") as f:
            f.write(f"Step {step_num}\n")
            f.write(f"Command: {command_data.get('command')}\n")
            if 'url' in command_data and command_data['url']:
                f.write(f"URL: {command_data['url']}\n")
            if 'selector' in command_data and command_data['selector']:
                f.write(f"Target: {command_data.get('description', command_data['selector'])}\n")
            if command_data.get('command') == 'finish':
                f.write(f"Status: {command_data.get('status')} ({command_data.get('message')})\n")
            f.write("\n")

    def get_history_summary(self) -> str:
        summary = ""
        for item in self.history:
            cmd = item['command']
            desc = cmd.get('description') or cmd.get('text') or cmd.get('url') or ''
            summary += f"- Step {item['step']}: {cmd['command']} {desc}\n"
        return summary if summary else "No previous steps."
